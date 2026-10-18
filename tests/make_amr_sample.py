"""Generates src/canopen_lens/examples/sample_amr_2wheel.log.

A candump log of a two-wheel AMR built like a typical ros2_canopen setup:

  * node 2 = Raspberry Pi running ros2_canopen (lely master), node 1 = STM32 running
    CANopenNode with two CiA 402 axes (axis 1 = 0x60xx = right wheel, axis 2 = 0x68xx =
    left wheel), 500 kbit/s, SYNC every 20 ms, heartbeats every 100 ms
  * boot: NMT reset communication -> boot-up -> SDO read of 0x1000 -> the concise DCF
    (bus.yml -> dcfgen -> motor.bin) is written with SDO: heartbeat settings, then for
    every PDO "disable (bit 31) -> mapping -> enable" -> NMT start
  * every SYNC the drive sends TPDO1..4 (state + mode, velocity + position, per axis);
    the master sends RPDO1..4 (controlword + mode, target velocity, per axis)
  * the ROS driver reads 0x6502/0x6D02 (supported drive modes), a drive_enabler enables
    both axes (06 -> 07 -> 0F) and selects profile velocity (3)
  * the robot drives; at t=18.2 s the E-stop is pressed: the firmware puts both axes into
    Fault without sending an EMCY; after release the operator runs recover
    (fault reset -> 06 -> 07 -> 0F) and the robot drives again

Velocities are in mm/s and positions in encoder counts (1320 counts per wheel turn,
wheel diameter 65 mm), as in the firmware.
"""

from __future__ import annotations

import math
import random
import struct
import sys
from pathlib import Path

T0 = 1792040400.0          # 2026-10-14 09:00 KST, any fixed epoch would do
DRIVE, MASTER = 1, 2
SYNC_PERIOD = 0.020
HB_PERIOD = 0.100
COUNTS_PER_MM = 1320.0 / (math.pi * 65.0)

SW_SOD, SW_RTSO, SW_SO, SW_OE, SW_FAULT = 0x0040, 0x0021, 0x0023, 0x0027, 0x0008


class Log:
    def __init__(self):
        self.frames: list[tuple[float, str]] = []

    def add(self, t: float, cob: int, data: bytes = b""):
        self.frames.append((t, f"{cob:03X}#{data.hex().upper()}"))

    def text(self) -> str:
        self.frames.sort(key=lambda x: x[0])
        return "".join(f"({T0 + t:.6f}) can0 {body}\n" for t, body in self.frames)


# --- concise DCF that dcfgen makes from bus.yml (same order as motor.bin) ---------------

def concise_dcf() -> list[tuple[int, int, int, int]]:
    """(index, sub, value, size) entries, in the order the master writes them."""
    e = [(0x1016, 1, (MASTER << 16) | 300, 4),      # watch master heartbeat, 300 ms
         (0x1017, 0, 100, 2)]                         # send own heartbeat every 100 ms
    rpdo = [[(0x6040, 0, 16), (0x6060, 0, 8)], [(0x60FF, 0, 32)],
            [(0x6840, 0, 16), (0x6860, 0, 8)], [(0x68FF, 0, 32)]]
    for n, entries in enumerate(rpdo):
        e.append((0x1600 + n, 0, 0, 1))
        for k, (idx, sub, bits) in enumerate(entries, 1):
            e.append((0x1600 + n, k, (idx << 16) | (sub << 8) | bits, 4))
        e.append((0x1600 + n, 0, len(entries), 1))
        e.append((0x1400 + n, 1, 0x200 + 0x100 * n + DRIVE, 4))
    tpdo = [[(0x6041, 0, 16), (0x6061, 0, 8)], [(0x606C, 0, 32), (0x6064, 0, 32)],
            [(0x6841, 0, 16), (0x6861, 0, 8)], [(0x686C, 0, 32), (0x6864, 0, 32)]]
    for n, entries in enumerate(tpdo):
        cob = 0x180 + 0x100 * n + DRIVE
        e.append((0x1800 + n, 1, 0x80000000 | cob, 4))   # disable while changing
        e.append((0x1800 + n, 2, 0x01, 1))               # send on every SYNC
        e.append((0x1A00 + n, 0, 0, 1))
        for k, (idx, sub, bits) in enumerate(entries, 1):
            e.append((0x1A00 + n, k, (idx << 16) | (sub << 8) | bits, 4))
        e.append((0x1A00 + n, 0, len(entries), 1))
        e.append((0x1800 + n, 1, cob, 4))                 # enable
    return e


# --- the drive (firmware behaviour, simplified) ---------------------------------------

class Axis:
    def __init__(self):
        self.state = SW_SOD
        self.cw = 0
        self.prev_cw = 0
        self.mode = 0
        self.target = 0
        self.vel = 0.0
        self.pos = 0.0


def step_state(ax: Axis, operational: bool) -> None:
    cw = ax.cw
    if ax.state == SW_FAULT:
        return
    if not operational:
        ax.state = SW_SOD
        return
    if cw & 0x80:                       # fault reset bit: no command while it is set
        return
    if (cw & 0x82) == 0x00:
        ax.state = SW_SOD
    elif (cw & 0x86) == 0x02:           # quick stop: not implemented in the firmware
        pass
    elif (cw & 0x87) == 0x06:
        if ax.state in (SW_SOD, SW_SO, SW_OE):
            ax.state = SW_RTSO
    elif (cw & 0x8F) == 0x07:
        if ax.state in (SW_RTSO, SW_OE):
            ax.state = SW_SO
    elif (cw & 0x8F) == 0x0F:
        if ax.state == SW_RTSO:
            ax.state = SW_SO
        elif ax.state == SW_SO:
            ax.state = SW_OE


def build() -> str:
    L = Log()
    rnd = random.Random(20261014)

    def jit(ms: float = 0.15) -> float:
        return rnd.uniform(-ms, ms) / 1000.0

    # 1) master starts: reset communication of all nodes, own boot-up
    L.add(0.0000, 0x000, bytes([0x82, 0x00]))
    L.add(0.0014, 0x700 + MASTER, b"\x00")
    L.add(0.0121, 0x700 + DRIVE, b"\x00")

    # 2) boot slave: read device type (the STM32 reports 0, no profile set), then
    #    write the concise DCF
    t = 0.0205
    L.add(t, 0x600 + DRIVE, struct.pack("<BHBI", 0x40, 0x1000, 0, 0))
    L.add(t + 0.00062, 0x580 + DRIVE, struct.pack("<BHBI", 0x43, 0x1000, 0, 0x00000000))
    t += 0.0021
    hb_drive_from = None
    for index, sub, value, size in concise_dcf():
        cmd = {1: 0x2F, 2: 0x2B, 4: 0x23}[size]
        L.add(t, 0x600 + DRIVE, struct.pack("<BHBI", cmd, index, sub, value))
        L.add(t + 0.00058 + jit(0.05), 0x580 + DRIVE, struct.pack("<BHBI", 0x60, index, sub, 0))
        if index == 0x1017:
            hb_drive_from = t + 0.0006
        t += 0.0019 + jit(0.2)
    t_start = t + 0.0040
    L.add(t_start, 0x000, bytes([0x01, DRIVE]))          # NMT start node 1
    sync_from = t_start + 0.0102

    # 3) cyclic traffic
    right, left = Axis(), Axis()
    axes = (right, left)
    t_end = 32.0
    estop_at, estop_release = 18.20, 22.0
    fault = False
    master_op_at = sync_from

    # master commands: (time, axis, controlword) and (time, axis, mode)
    cw_events: list[tuple[float, int, int]] = []
    mode_events: list[tuple[float, int, int]] = []

    def enable(t0: float, a: int, with_reset: bool) -> float:
        seq = [0x0080] if with_reset else []
        seq += [0x0006, 0x0007, 0x000F]
        for k, cw in enumerate(seq):
            cw_events.append((t0 + 0.040 * k, a, cw))
        return t0 + 0.040 * len(seq) + 0.010

    # drive_enabler: init (06 07 0F) for each channel, then velocity_mode for each
    tt = enable(3.000, 0, True)
    tt = enable(tt + 0.030, 1, True)
    mode_events += [(tt + 0.050, 0, 3), (tt + 0.110, 1, 3)]
    # recover after the E-stop was released (operator, J-7 procedure)
    tt = enable(24.000, 0, True)
    tt = enable(tt + 0.030, 1, True)
    mode_events += [(tt + 0.050, 0, 3), (tt + 0.110, 1, 3)]

    def target_speed(t: float) -> tuple[int, int]:
        """diff_drive_controller output in mm/s (right, left), acceleration limited later."""
        if 5.0 <= t < 9.0:
            return 200, 200
        if 9.0 <= t < 11.0:
            return 260, 140              # turning left
        if 11.0 <= t < 14.0:
            return 300, 300
        if 16.5 <= t < 18.6:
            return 150, 150              # joystick released shortly after the E-stop
        if 26.0 <= t < 30.0:
            return 200, 200
        if 30.0 <= t < 31.0:
            return 120, 280              # turning right
        return 0, 0

    cmd_r = cmd_l = 0.0
    k = 0
    next_hb_drive = (hb_drive_from or 0.1) + HB_PERIOD
    next_hb_master = 0.1014
    ros_up = 2.000                   # ros2_control active: master starts sending RPDOs
    sdo_6502_at = 1.80               # Cia402Driver reads the supported drive modes
    L.add(sdo_6502_at, 0x600 + DRIVE, struct.pack("<BHBI", 0x40, 0x6502, 0, 0))
    L.add(sdo_6502_at + 0.0011, 0x580 + DRIVE, struct.pack("<BHBI", 0x43, 0x6502, 0, 0x00000004))
    L.add(sdo_6502_at + 0.0040, 0x600 + DRIVE, struct.pack("<BHBI", 0x40, 0x6D02, 0, 0))
    L.add(sdo_6502_at + 0.0051, 0x580 + DRIVE, struct.pack("<BHBI", 0x43, 0x6D02, 0, 0x00000004))

    while True:
        ts = sync_from + k * SYNC_PERIOD + jit(0.05)
        if ts > t_end:
            break
        dt = SYNC_PERIOD

        # heartbeats that fall into this cycle
        while next_hb_drive < ts + SYNC_PERIOD and next_hb_drive < t_end:
            L.add(next_hb_drive + jit(0.3), 0x700 + DRIVE, bytes([0x05 if next_hb_drive > t_start else 0x7F]))
            next_hb_drive += HB_PERIOD
        while next_hb_master < ts + SYNC_PERIOD and next_hb_master < t_end:
            L.add(next_hb_master + jit(0.2), 0x700 + MASTER, bytes([0x05 if next_hb_master > master_op_at else 0x7F]))
            next_hb_master += HB_PERIOD

        # firmware: safety, state machine, PID (applied before this SYNC's TPDOs)
        if estop_at <= ts and not fault and ts < estop_release:
            fault = True
            for ax in axes:
                ax.state = SW_FAULT
        if fault and ts >= estop_release:
            if any((ax.cw & 0x80) and not (ax.prev_cw & 0x80) for ax in axes):
                fault = False
                for ax in axes:
                    ax.state = SW_SOD
        for ax in axes:
            step_state(ax, True)
            ax.prev_cw = ax.cw
            running = ax.state == SW_OE and ax.mode == 3
            goal = ax.target if running else 0.0
            tau = 0.12 if running else 0.07       # coasts down quicker with PWM off
            ax.vel += (goal - ax.vel) * (1 - math.exp(-dt / tau))
            if abs(ax.vel) < 1.0 and goal == 0:
                ax.vel = 0.0
            ax.pos += ax.vel * dt * COUNTS_PER_MM

        def meas(ax: Axis) -> int:
            return int(round(ax.vel + (rnd.uniform(-2.5, 2.5) if abs(ax.vel) > 20 else 0)))

        L.add(ts, 0x080)
        L.add(ts + 0.00031, 0x181, struct.pack("<Hb", right.state, right.mode))
        L.add(ts + 0.00052, 0x281, struct.pack("<ii", meas(right), int(right.pos)))
        L.add(ts + 0.00083, 0x381, struct.pack("<Hb", left.state, left.mode))
        L.add(ts + 0.00104, 0x481, struct.pack("<ii", meas(left), int(left.pos)))

        # master: apply events due this cycle, then send RPDO1..4 a few ms after SYNC
        tr = ts + 0.0046 + jit(0.4)
        if tr >= ros_up:
            for (te, a, cw) in cw_events:
                if ts - SYNC_PERIOD < te <= ts:
                    axes[a].cw = cw
            for (te, a, mode) in mode_events:
                if ts - SYNC_PERIOD < te <= ts:
                    axes[a].mode = mode
            want_r, want_l = target_speed(ts)
            step = 600.0 * SYNC_PERIOD                # 0.6 m/s^2 limit in diff_drive
            cmd_r += max(-step, min(step, want_r - cmd_r))
            cmd_l += max(-step, min(step, want_l - cmd_l))
            right.target, left.target = int(round(cmd_r)), int(round(cmd_l))
            L.add(tr, 0x201, struct.pack("<Hb", right.cw, right.mode))
            L.add(tr + 0.00024, 0x301, struct.pack("<i", right.target))
            L.add(tr + 0.00048, 0x401, struct.pack("<Hb", left.cw, left.mode))
            L.add(tr + 0.00072, 0x501, struct.pack("<i", left.target))
        k += 1
    return L.text()


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else (
        Path(__file__).resolve().parent.parent / "src" / "canopen_lens" / "examples" / "sample_amr_2wheel.log")
    out.write_text(build(), encoding="ascii", newline="\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv)
