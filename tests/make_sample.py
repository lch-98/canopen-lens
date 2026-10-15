"""Generates src/canopen_lens/examples/sample_cia402.log, a synthetic but realistic candump log.

Scenario (two CiA 402 drives + one I/O node):
  * node 1: drive, PDO mapping configured over SDO, enables and runs in profile velocity
  * node 2: drive with default mapping; an SDO write is aborted, EMCY over-current at
    t=3.0 s puts it into Fault, the first fault reset fails, the second one works
  * node 3: I/O module; heartbeat gap at t=4.0 s and lost for good at t=5.5 s
  * an SDO request to node 4, which does not exist, gets no answer
  * two bus error frames at t=4.1 s
  * node 5: two-axis drive (CiA 402-2, axis 2 objects at 0x6800+). Axis 2 is blocked
    at t=2.0 s (EMCY 0x7121) and recovers with a fault reset at t=2.5 s while axis 1
    keeps running
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

T0 = 1760500000.0


class Log:
    def __init__(self):
        self.frames: list[tuple[float, str]] = []

    def add(self, t: float, cob: int, data: bytes = b"", ext: bool = False, rtr: bool = False):
        ident = f"{cob:08X}" if ext else f"{cob:03X}"
        body = "R" if rtr else data.hex().upper()
        self.frames.append((t, f"{ident}#{body}"))

    def sdo_write(self, t, node, index, sub, value, size, abort=None, answer=True):
        cmd = {1: 0x2F, 2: 0x2B, 3: 0x27, 4: 0x23}[size]
        self.add(t, 0x600 + node, struct.pack("<BHBI", cmd, index, sub, value & 0xFFFFFFFF))
        if not answer:
            return
        if abort is not None:
            self.add(t + 0.0012, 0x580 + node, struct.pack("<BHBI", 0x80, index, sub, abort))
        else:
            self.add(t + 0.0012, 0x580 + node, struct.pack("<BHBI", 0x60, index, sub, 0))

    def sdo_read(self, t, node, index, sub, value, size):
        self.add(t, 0x600 + node, struct.pack("<BHBI", 0x40, index, sub, 0))
        cmd = {1: 0x4F, 2: 0x4B, 3: 0x47, 4: 0x43}[size]
        self.add(t + 0.0011, 0x580 + node, struct.pack("<BHBI", cmd, index, sub, value))

    def text(self) -> str:
        self.frames.sort(key=lambda x: x[0])
        return "".join(f"({T0 + t:.6f}) can0 {body}\n" for t, body in self.frames)


def build() -> str:
    L = Log()
    # boot-up
    for n in (1, 2, 3, 5):
        L.add(0.010 * n, 0x700 + n, b"\x00")

    # identify devices
    L.sdo_read(0.100, 1, 0x1000, 0, 0x00020192, 4)
    L.sdo_read(0.110, 2, 0x1000, 0, 0x00020192, 4)
    L.sdo_read(0.120, 3, 0x1000, 0, 0x000F0191, 4)

    # node 2: read device name with a segmented upload ("MotorDrv")
    L.add(0.130, 0x602, struct.pack("<BHBI", 0x40, 0x1008, 0, 0))
    L.add(0.131, 0x582, struct.pack("<BHBI", 0x41, 0x1008, 0, 8))
    L.add(0.132, 0x602, bytes([0x60]) + bytes(7))
    L.add(0.133, 0x582, bytes([0x00]) + b"MotorDr")
    L.add(0.134, 0x602, bytes([0x70]) + bytes(7))
    L.add(0.135, 0x582, bytes([0x1D]) + b"v" + bytes(6))

    # node 1: remap TPDO1 = statusword + velocity actual, RPDO1 = controlword + target velocity
    t = 0.200
    for index, sub, value, size in [
        (0x1A00, 0, 0, 1), (0x1A00, 1, 0x60410010, 4), (0x1A00, 2, 0x606C0020, 4), (0x1A00, 0, 2, 1),
        (0x1600, 0, 0, 1), (0x1600, 1, 0x60400010, 4), (0x1600, 2, 0x60FF0020, 4), (0x1600, 0, 2, 1),
        (0x6060, 0, 3, 1), (0x1017, 0, 100, 2),
    ]:
        L.sdo_write(t, 1, index, sub, value, size)
        t += 0.005
    # node 2: profile velocity, plus a write to an object that does not exist
    L.sdo_write(0.260, 2, 0x6060, 0, 3, 1)
    L.sdo_write(0.265, 2, 0x2001, 0, 1, 2, abort=0x06020000)
    L.sdo_write(0.270, 2, 0x1017, 0, 100, 2)
    # node 5: two-axis drive, both axes configured over SDO
    L.sdo_read(0.140, 5, 0x1000, 0, 0x00020192, 4)
    t = 0.285
    for index, sub, value, size in [
        (0x1A00, 0, 0, 1), (0x1A00, 1, 0x60410010, 4), (0x1A00, 2, 0x68410010, 4), (0x1A00, 3, 0x606C0020, 4),
        (0x1A00, 0, 3, 1),
        (0x1A01, 0, 0, 1), (0x1A01, 1, 0x686C0020, 4), (0x1A01, 0, 1, 1),
        (0x1600, 0, 0, 1), (0x1600, 1, 0x60400010, 4), (0x1600, 2, 0x68400010, 4), (0x1600, 0, 2, 1),
        (0x1601, 0, 0, 1), (0x1601, 1, 0x60FF0020, 4), (0x1601, 2, 0x68FF0020, 4), (0x1601, 0, 2, 1),
        (0x6060, 0, 3, 1), (0x6860, 0, 3, 1), (0x1017, 0, 100, 2),
    ]:
        L.sdo_write(t, 5, index, sub, value, size)
        t += 0.005

    # node 4 does not exist
    L.sdo_read(0.280, 4, 0x1000, 0, 0, 4)
    L.frames.pop()  # drop the answer: nobody replies

    # start all nodes
    L.add(0.400, 0x000, b"\x01\x00")

    hb_state = {1: 0x7F, 2: 0x7F, 3: 0x7F, 5: 0x7F}
    # keys: node number, or (node, axis) for the two-axis node 5
    sw = {1: 0x0250, 2: 0x0250, (5, 0): 0x0250, (5, 1): 0x0250}
    cw = {1: 0x0000, 2: 0x0000, (5, 0): 0x0000, (5, 1): 0x0000}
    vel = {1: 0, 2: 0, (5, 0): 0, (5, 1): 0}

    def drive_step(n, t):
        c = cw[n]
        s = sw[n]
        state = s & 0x6F
        if s & 0x08:  # fault: only a fault reset helps (node 2 ignores the first one)
            return
        if c & 0x80:
            return
        if (c & 0x87) == 0x06 and state in (0x40, 0x60, 0x23, 0x27):
            sw[n] = 0x0231
        elif (c & 0x8F) == 0x07 and (s & 0x6F) == 0x21:
            sw[n] = 0x0233
        elif (c & 0x8F) == 0x0F and (s & 0x6F) in (0x23, 0x21):
            sw[n] = 0x0237

    n2_fault_reset_works_after = 4.4
    k = 0
    t = 0.0
    while t < 6.0:
        t = round(0.5 + k * 0.010, 6)
        k += 1
        if t >= 6.0:
            break
        L.add(t, 0x080)  # SYNC

        for n in (1, 2):
            # master command sequence
            if t < 0.6:
                cw[n] = 0x06
            elif t < 0.7:
                cw[n] = 0x07
            elif n == 2 and 3.40 <= t < 3.42:
                cw[n] = 0x80  # first fault reset (does not help)
            elif n == 2 and 3.42 <= t < 4.50:
                cw[n] = 0x00
            elif n == 2 and 4.50 <= t < 4.52:
                cw[n] = 0x80  # second fault reset (works)
            elif n == 2 and 4.52 <= t < 4.60:
                cw[n] = 0x06
            elif n == 2 and 4.60 <= t < 4.70:
                cw[n] = 0x07
            else:
                cw[n] = 0x0F

            if n == 2 and abs(t - 3.000) < 1e-9:
                L.add(t + 0.0004, 0x082, struct.pack("<HB5s", 0x2310, 0x03, b"\x00\x12\x00\x00\x00"))
                sw[2] = 0x0218  # fault
                vel[2] = 0
            if n == 2 and (cw[2] & 0x80) and (sw[2] & 0x08) and t >= n2_fault_reset_works_after:
                sw[2] = 0x0250
                L.add(t + 0.0006, 0x082, struct.pack("<HB5s", 0x0000, 0x00, bytes(5)))
            drive_step(n, t)

            target = 1000 if n == 1 else 500
            if (sw[n] & 0x6F) == 0x27:
                vel[n] += (target - vel[n]) // 8 if abs(target - vel[n]) > 8 else target - vel[n]
            else:
                vel[n] = 0

        # node 5: two axes, axis 2 gets blocked at 2.0 s and is reset at 2.5 s
        for ax in ((5, 0), (5, 1)):
            if t < 0.6:
                cw[ax] = 0x06
            elif t < 0.7:
                cw[ax] = 0x07
            elif ax == (5, 1) and 2.50 <= t < 2.52:
                cw[ax] = 0x80
            elif ax == (5, 1) and 2.52 <= t < 2.60:
                cw[ax] = 0x06
            elif ax == (5, 1) and 2.60 <= t < 2.70:
                cw[ax] = 0x07
            else:
                cw[ax] = 0x0F
            if ax == (5, 1) and abs(t - 2.000) < 1e-9:
                L.add(t + 0.0004, 0x085, struct.pack("<HB5s", 0x7121, 0x01, b"\x02\x00\x00\x00\x00"))
                sw[ax] = 0x0218
            if ax == (5, 1) and (cw[ax] & 0x80) and (sw[ax] & 0x08):
                sw[ax] = 0x0250
                L.add(t + 0.0006, 0x085, struct.pack("<HB5s", 0x0000, 0x00, bytes(5)))
            drive_step(ax, t)
            target = 800 if ax == (5, 0) else -800
            if (sw[ax] & 0x6F) == 0x27:
                vel[ax] += (target - vel[ax]) // 8 if abs(target - vel[ax]) > 8 else target - vel[ax]
            else:
                vel[ax] = 0
        L.add(t + 0.00025, 0x185, struct.pack("<HHi", sw[(5, 0)], sw[(5, 1)], vel[(5, 0)]))
        L.add(t + 0.00035, 0x285, struct.pack("<i", vel[(5, 1)]))
        L.add(t + 0.00055, 0x205, struct.pack("<HH", cw[(5, 0)], cw[(5, 1)]))
        L.add(t + 0.00065, 0x305, struct.pack("<ii", 800 if cw[(5, 0)] == 0x0F else 0,
                                                 -800 if cw[(5, 1)] == 0x0F else 0))

        # PDOs: node 1 uses the custom mapping, node 2 the CiA 402 default
        L.add(t + 0.0002, 0x181, struct.pack("<Hi", sw[1], vel[1]))
        L.add(t + 0.0003, 0x182, struct.pack("<H", sw[2]))
        L.add(t + 0.0005, 0x201, struct.pack("<Hi", cw[1], 1000 if cw[1] == 0x0F else 0))
        L.add(t + 0.0006, 0x202, struct.pack("<H", cw[2]))
        if k % 10 == 0:
            L.add(t + 0.0007, 0x183, bytes([0x05 if (k // 50) % 2 else 0x01]))

        # heartbeats every 100 ms
        if k % 10 == 3:
            for n in (1, 2, 3, 5):
                if t >= 0.41:
                    hb_state[n] = 0x05
                if n == 3 and (4.0 <= t < 4.6 or t >= 5.5):
                    continue
                L.add(t + 0.0008 + 0.0001 * n, 0x700 + n, bytes([hb_state[n]]))

        if abs(t - 4.1) < 1e-9:
            L.add(t + 0.0009, 0x20000004, bytes([0, 0x04, 0, 0, 0, 0, 0, 0]), ext=True)
            L.add(t + 0.0019, 0x20000004, bytes([0, 0x04, 0, 0, 0, 0, 0, 0]), ext=True)
    return L.text()


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent / "src" / "canopen_lens" / "examples" / "sample_cia402.log"
    out.write_text(build(), encoding="ascii", newline="\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv)
