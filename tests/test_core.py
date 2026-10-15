from pathlib import Path

import pytest

from canopen_lens import (
    AxisState,
    CanopenLog,
    CwCommand,
    EdsFile,
    IssueType,
    Kind,
    MapOrigin,
    SdoType,
    Severity,
    decode_controlword,
    decode_statusword,
    open_log,
)

HERE = Path(__file__).resolve().parent
SAMPLE = HERE.parent / "src" / "canopen_lens" / "examples" / "sample_cia402.log"
EDS = HERE / "data" / "sample_drive.eds"


def types(log):
    return [i.type for i in log.issues]


# --------------------------------------------------------------------------- parser

def test_log_format_basic():
    log = CanopenLog.from_text(
        "(1700000000.000100) can0 701#00\n"
        "(1700000000.000200) can0 181#3102E8030000\n"
        "(1700000000.100200) vcan1 12345678#DEAD\n"
    )
    tr = log.trace
    assert len(log) == 3
    assert tr.format == "candump-log"
    assert tr.has_timestamps
    assert tr.interfaces == ["can0", "vcan1"]
    f = tr.frame(1)
    assert f.id == 0x181 and f.dlc == 6 and f.data == bytes.fromhex("3102E8030000")
    assert abs(f.t - 0.0001) < 1e-9
    assert abs(tr.frame(2).t - 0.1001) < 1e-9
    assert tr.frame(2).ext and tr.record(2).kind == Kind.UNKNOWN


def test_console_format_with_and_without_time():
    text = (
        " (1700000000.500000)  can0  601   [8]  40 00 10 00 00 00 00 00\n"
        "  can0  581   [8]  43 00 10 00 92 01 02 00   'C.......'\n"
    )
    log = CanopenLog.from_text(text)
    assert len(log) == 2
    assert log.trace.format == "candump-console"
    assert not log.trace.has_timestamps  # second line has no timestamp
    assert log.trace.record(1).value == 0x00020192


def test_rtr_fd_error_and_junk():
    text = (
        "(1.000000) can0 701#R\n"
        "(1.000100) can0 123##1" + "11" * 12 + "\n"
        "(1.000200) can0 20000004#0004000000000000\n"
        "this is not a can frame\n"
        "\r\n"
        "(1.000300) can0 080#\r\n"
    )
    log = CanopenLog.from_text(text)
    tr = log.trace
    assert len(log) == 4
    assert tr.frame(0).rtr and tr.record(0).kind == Kind.HEARTBEAT
    assert tr.frame(1).fd and tr.frame(1).dlc == 12
    assert tr.frame(2).error and tr.record(2).kind == Kind.ERROR_FRAME
    assert tr.record(3).kind == Kind.SYNC and tr.frame(3).dlc == 0
    assert tr.skipped_lines == 1
    assert IssueType.PARSE_ERRORS in types(log)
    assert IssueType.BUS_ERROR_FRAME in types(log)


def test_delta_timestamps_are_integrated():
    lines = []
    for k in range(20):
        lines.append(f"({0.010 if k else 0.0:.6f}) can0 080#")
    log = CanopenLog.from_text("\n".join(lines))
    assert log.trace.format.endswith("-delta")
    assert abs(log.trace.duration - 0.19) < 1e-6


def test_empty_input():
    log = CanopenLog.from_text("")
    assert len(log) == 0 and list(log.issues) == []


# --------------------------------------------------------------------------- decoding

def test_sdo_expedited_and_abort():
    log = CanopenLog.from_text(
        "(0.0) can0 605#2B17100064000000\n"   # write 0x1017 = 100 (2 bytes)
        "(0.001) can0 585#6017100000000000\n"
        "(0.002) can0 605#4018100100000000\n"   # read 0x1018:01
        "(0.003) can0 585#8018100100000206\n"  # abort 0x06020000
    )
    tr = log.trace
    w = tr.record(0)
    assert w.kind == Kind.SDO_REQ and w.sdo_type == SdoType.DOWNLOAD_INIT
    assert (w.index, w.sub, w.value, w.value_len) == (0x1017, 0, 100, 2)
    assert tr.record(1).sdo_type == SdoType.DOWNLOAD_INIT and tr.record(1).kind == Kind.SDO_RESP
    a = tr.record(3)
    assert a.sdo_type == SdoType.ABORT and a.abort_code == 0x06020000
    issue = next(i for i in log.issues if i.type == IssueType.SDO_ABORT)
    assert issue.node == 5 and issue.index == 0x1018 and issue.sub == 1
    title, text = log.issue_text(issue, "en")
    assert "does not exist" in title
    assert "0x1018:01" in text


def test_sdo_without_answer_is_reported():
    log = CanopenLog.from_text("(0.0) can0 607#4000100000000000\n(2.0) can0 080#\n")
    issue = next(i for i in log.issues if i.type == IssueType.SDO_NO_RESPONSE)
    assert issue.node == 7 and issue.index == 0x1000


def test_nmt_heartbeat_emcy():
    log = CanopenLog.from_text(
        "(0.0) can0 000#8100\n"
        "(0.5) can0 703#00\n"
        "(0.6) can0 083#1023030000000000\n"
        "(0.7) can0 703#7F\n"
    )
    tr = log.trace
    assert tr.record(0).kind == Kind.NMT and tr.record(0).nmt_cmd == 0x81
    assert tr.record(1).kind == Kind.HEARTBEAT and tr.record(1).hb_state == 0
    e = tr.record(2)
    assert e.kind == Kind.EMCY and e.node == 3 and e.emcy_code == 0x2310 and e.error_register == 3
    assert "over current" in log.summary(2, "en")


def test_unexpected_reboot():
    lines = [f"({t / 10:.1f}) can0 702#05" for t in range(10)]
    lines.append("(1.05) can0 702#00")
    log = CanopenLog.from_text("\n".join(lines))
    reboot = next(i for i in log.issues if i.type == IssueType.NODE_REBOOT)
    assert reboot.severity == Severity.WARNING and reboot.code == 0


def test_reboot_after_reset_is_info():
    lines = [f"({t / 10:.1f}) can0 702#05" for t in range(10)]
    lines += ["(1.00) can0 000#8102", "(1.05) can0 702#00"]
    log = CanopenLog.from_text("\n".join(lines))
    reboot = next(i for i in log.issues if i.type == IssueType.NODE_REBOOT)
    assert reboot.severity == Severity.INFO


# --------------------------------------------------------------------------- CiA 402

@pytest.mark.parametrize(
    "sw,state",
    [
        (0x0000, AxisState.NOT_READY_TO_SWITCH_ON),
        (0x0250, AxisState.SWITCH_ON_DISABLED),
        (0x0231, AxisState.READY_TO_SWITCH_ON),
        (0x0233, AxisState.SWITCHED_ON),
        (0x0237, AxisState.OPERATION_ENABLED),
        (0x0217, AxisState.QUICK_STOP_ACTIVE),
        (0x021F, AxisState.FAULT_REACTION_ACTIVE),
        (0x0218, AxisState.FAULT),
    ],
)
def test_statusword(sw, state):
    assert decode_statusword(sw) == state


@pytest.mark.parametrize(
    "cw,prev,cmd",
    [
        (0x06, 0, CwCommand.SHUTDOWN),
        (0x07, 0, CwCommand.SWITCH_ON),
        (0x0F, 0, CwCommand.ENABLE_OPERATION),
        (0x00, 0, CwCommand.DISABLE_VOLTAGE),
        (0x02, 0, CwCommand.QUICK_STOP),
        (0x80, 0, CwCommand.FAULT_RESET),
        (0x80, 0x80, CwCommand.NONE),
    ],
)
def test_controlword(cw, prev, cmd):
    assert decode_controlword(cw, prev) == cmd


def _drive_log(sequence):
    """sequence: list of (t, controlword, statusword)"""
    lines = ["(0.0) can0 601#4000100000000000", "(0.001) can0 581#4300100092010200"]
    for t, cw, sw in sequence:
        lines.append(f"({t:.3f}) can0 201#{cw & 0xFF:02X}{cw >> 8:02X}")
        lines.append(f"({t + 0.0005:.4f}) can0 181#{sw & 0xFF:02X}{sw >> 8:02X}")
    return CanopenLog.from_text("\n".join(lines))


def test_enable_failure_is_detected():
    seq = [(0.1 + 0.01 * k, 0x06, 0x0231) for k in range(5)]
    seq += [(0.2 + 0.01 * k, 0x0F, 0x0231) for k in range(200)]  # drive never enables
    log = _drive_log(seq)
    assert log.trace.nodes[0].is_drive
    issue = next(i for i in log.issues if i.type == IssueType.AXIS_ENABLE_FAILED)
    assert issue.node == 1 and abs(issue.t - 0.2) < 1e-6


def test_successful_enable_has_no_issue():
    seq = [(0.1, 0x06, 0x0231), (0.11, 0x07, 0x0233), (0.12, 0x0F, 0x0233), (0.13, 0x0F, 0x0237)]
    log = _drive_log(seq + [(0.2 + 0.01 * k, 0x0F, 0x0237) for k in range(150)])
    assert not [i for i in log.issues if i.severity != Severity.INFO]
    states = [p.state for p in log.trace.axis_timeline(1)]
    assert states == [AxisState.READY_TO_SWITCH_ON, AxisState.SWITCHED_ON, AxisState.OPERATION_ENABLED]


def test_node_without_evidence_is_not_a_drive_until_forced():
    log = CanopenLog.from_text("(0.0) can0 181#5002\n(0.1) can0 181#3102\n")
    assert not log.trace.record(0).has_statusword
    log.set_drive(1, True)
    assert log.trace.record(0).has_statusword
    assert log.trace.record(1).axis_state == AxisState.READY_TO_SWITCH_ON
    log.set_drive(1, None)
    assert not log.trace.record(0).has_statusword


def test_pdo_mapping_from_sdo_in_log():
    log = CanopenLog.from_text(
        "(0.000) can0 601#2F001A0000000000\n(0.001) can0 581#60001A0000000000\n"
        "(0.002) can0 601#23001A0120006C60\n(0.003) can0 581#60001A0100000000\n"   # 0x606C0020 first
        "(0.004) can0 601#23001A0210004160\n(0.005) can0 581#60001A0200000000\n"   # then 0x60410010
        "(0.006) can0 601#2F001A0002000000\n(0.007) can0 581#60001A0000000000\n"
        "(0.010) can0 181#E803000037020000\n"
    )
    tr = log.trace
    r = tr.record(8)
    assert r.has_statusword and r.statusword == 0x0237  # found after the 32-bit velocity
    m = tr.mapping(r.map_ref)
    assert m.origin == MapOrigin.LOG_SDO
    assert [(e.index, e.bits) for e in m.entries] == [(0x606C, 32), (0x6041, 16)]
    fields = tr.pdo_fields(8)
    assert fields[0].raw == 1000


# --------------------------------------------------------------------------- sample log

def test_sample_log_findings():
    log = open_log(SAMPLE)
    found = {(i.type, i.node) for i in log.issues}
    assert (IssueType.SDO_ABORT, 2) in found
    assert (IssueType.SDO_NO_RESPONSE, 4) in found
    assert (IssueType.EMCY, 2) in found
    assert (IssueType.AXIS_FAULT, 2) in found
    assert (IssueType.AXIS_FAULT_RESET_FAILED, 2) in found
    assert (IssueType.HEARTBEAT_GAP, 3) in found
    assert (IssueType.HEARTBEAT_LOST, 3) in found
    assert (IssueType.BUS_ERROR_FRAME, 0) in found
    # healthy things must stay quiet
    assert not any(i.node == 1 and i.severity != Severity.INFO for i in log.issues)
    fault = next(i for i in log.issues if i.type == IssueType.AXIS_FAULT)
    assert fault.related_row is not None and log.trace.record(fault.related_row).emcy_code == 0x2310
    nodes = {n.node: n for n in log.nodes}
    assert nodes[1].is_drive and nodes[2].is_drive and not nodes[3].is_drive
    assert abs(nodes[3].hb_period - 0.1) < 1e-3


def test_every_frame_has_a_summary_in_both_languages():
    log = open_log(SAMPLE)
    for row in range(0, len(log), 7):
        for lang in ("ko", "en"):
            assert log.summary(row, lang)
            assert log.details(row, lang)
    for issue in log.issues:
        for lang in ("ko", "en"):
            title, text = log.issue_text(issue, lang)
            assert title and text


def test_filter():
    log = open_log(SAMPLE)
    tr = log.trace
    emcy = tr.filter(kinds=[Kind.EMCY])
    assert len(emcy) == 2 and all(tr.record(r).kind == Kind.EMCY for r in emcy)
    node3 = tr.filter(node=3)
    assert all(tr.record(r).node == 3 for r in node3)
    problems = tr.filter(issues_only=True)
    assert all(tr.record(r).has_issue for r in problems)
    sw = tr.filter(index=0x606C)
    assert len(sw) > 0 and all(tr.record(r).node == 1 for r in sw)
    assert memoryview(tr.filter(node=3)).format in ("I", "L", "=I", "<I")


# --------------------------------------------------------------------------- EDS

def test_eds_parse():
    eds = EdsFile.load(EDS)
    assert eds.title == "Example Motion / EM-2 Velocity Drive"
    assert eds.is_cia402
    assert eds.pdo_mapping(True, 1) == [(0x6041, 0, 16), (0x606C, 0, 32)]
    assert eds.pdo_mapping(False, 1) == [(0x6040, 0, 16), (0x60FF, 0, 32)]
    assert eds.pdo_mapping(True, 2) is None
    assert eds.int_value(0x1800, 1, node_id=5) == 0x185
    assert eds.lookup(0x2001, 0).name_en == "Wheel diameter"


def test_eds_drives_mapping_and_names():
    log = CanopenLog.from_text("(0.0) can0 185#3702E8030000\n(0.1) can0 605#2B01200064000000\n")
    assert log.trace.record(0).map_ref is None
    log.attach_eds(5, EDS)
    r = log.trace.record(0)
    assert r.has_statusword and r.axis_state == AxisState.OPERATION_ENABLED
    assert log.trace.mapping(r.map_ref).origin == MapOrigin.EDS
    assert "Wheel diameter" in log.summary(1, "en")
    assert "실제 속도=1000" in log.summary(0, "ko")
    log.detach_eds(5)
    assert log.trace.record(0).map_ref is None
