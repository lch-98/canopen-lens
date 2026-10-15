"""Human readable explanations (Korean / English) for decoded CANopen data.

All user-facing wording lives here so it can be reviewed and translated in one
place. The C++ core only produces structured data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ._core import AxisState, CwCommand, IssueType, Kind, SdoType, Severity, decode_controlword, decode_statusword
from .objects import MODES_OF_OPERATION, axis_base, axis_of, format_value, mapping_entry_text, to_signed

if TYPE_CHECKING:  # pragma: no cover
    from .log import CanopenLog

LANGS = ("ko", "en")


def _p(lang: str, ko: str, en: str) -> str:
    return ko if lang == "ko" else en


# --------------------------------------------------------------------------
# Basic vocabularies
# --------------------------------------------------------------------------

KIND_LABEL = {
    Kind.NMT: ("NMT", "NMT"),
    Kind.SYNC: ("SYNC", "SYNC"),
    Kind.EMCY: ("EMCY(비상)", "EMCY"),
    Kind.TIME: ("TIME", "TIME"),
    Kind.TPDO: ("TPDO", "TPDO"),
    Kind.RPDO: ("RPDO", "RPDO"),
    Kind.SDO_REQ: ("SDO 요청", "SDO request"),
    Kind.SDO_RESP: ("SDO 응답", "SDO response"),
    Kind.HEARTBEAT: ("하트비트", "Heartbeat"),
    Kind.LSS: ("LSS", "LSS"),
    Kind.ERROR_FRAME: ("에러 프레임", "Error frame"),
    Kind.UNKNOWN: ("알 수 없음", "Unknown"),
}

KIND_HELP = {
    Kind.NMT: ("마스터가 노드 전체의 동작 상태(시작/정지/리셋)를 바꾸는 명령입니다.",
               "Master command that changes the operating state of nodes (start/stop/reset)."),
    Kind.SYNC: ("주기적으로 보내는 동기 신호입니다. PDO 송수신 타이밍의 기준이 됩니다.",
                "Periodic synchronization tick. PDOs are often sent in step with it."),
    Kind.EMCY: ("노드가 내부 오류를 알릴 때 한 번 보내는 비상 메시지입니다.",
                "Emergency message a node sends once when an internal error occurs."),
    Kind.TIME: ("네트워크 시간 정보입니다.", "Network time stamp."),
    Kind.TPDO: ("노드가 마스터로 보내는 실시간 데이터입니다 (예: 상태, 실제 위치/속도).",
                "Real-time data sent by a node to the master (e.g. status, actual position/velocity)."),
    Kind.RPDO: ("마스터가 노드로 보내는 실시간 명령 데이터입니다 (예: 컨트롤워드, 목표 위치/속도).",
                "Real-time data the master sends to a node (e.g. controlword, target position/velocity)."),
    Kind.SDO_REQ: ("마스터가 노드의 오브젝트 딕셔너리 값을 읽거나 쓰는 요청입니다. 설정값 변경에 주로 씁니다.",
                   "Master request to read or write an object in the node's object dictionary."),
    Kind.SDO_RESP: ("노드가 SDO 요청에 대답한 메시지입니다.", "The node's answer to an SDO request."),
    Kind.HEARTBEAT: ("노드가 '살아 있음'과 현재 NMT 상태를 주기적으로 알리는 메시지입니다.",
                     "Periodic 'I am alive' message carrying the node's NMT state."),
    Kind.LSS: ("노드-ID와 통신 속도를 설정하는 LSS 서비스입니다.", "Layer setting service (node-ID / bit rate setup)."),
    Kind.ERROR_FRAME: ("CAN 드라이버가 버스 오류를 보고한 프레임입니다. 배선·종단저항·통신속도를 의심해야 합니다.",
                       "Bus error reported by the CAN driver. Check wiring, termination and bit rate."),
    Kind.UNKNOWN: ("CANopen 기본 ID 배치에 해당하지 않는 프레임입니다.",
                   "Frame outside the CANopen predefined connection set."),
}

NMT_CMD = {
    0x01: ("Start (운전 시작 → Operational)", "Start remote node → Operational"),
    0x02: ("Stop (정지 → Stopped)", "Stop remote node → Stopped"),
    0x80: ("Enter Pre-operational (설정 모드)", "Enter pre-operational"),
    0x81: ("Reset node (노드 재시작)", "Reset node"),
    0x82: ("Reset communication (통신 재시작)", "Reset communication"),
}

HB_STATE = {
    0x00: ("Boot-up (방금 켜짐)", "Boot-up"),
    0x04: ("Stopped (정지)", "Stopped"),
    0x05: ("Operational (운전 중)", "Operational"),
    0x7F: ("Pre-operational (설정 모드)", "Pre-operational"),
}

AXIS_STATE = {
    AxisState.UNKNOWN: ("알 수 없음", "Unknown"),
    AxisState.NOT_READY_TO_SWITCH_ON: ("Not ready to switch on (초기화 중)", "Not ready to switch on"),
    AxisState.SWITCH_ON_DISABLED: ("Switch on disabled (대기, 전원 차단)", "Switch on disabled"),
    AxisState.READY_TO_SWITCH_ON: ("Ready to switch on (준비 완료)", "Ready to switch on"),
    AxisState.SWITCHED_ON: ("Switched on (전원 인가, 토크 없음)", "Switched on"),
    AxisState.OPERATION_ENABLED: ("Operation enabled (토크 ON, 운전 가능)", "Operation enabled"),
    AxisState.QUICK_STOP_ACTIVE: ("Quick stop active (급정지 중)", "Quick stop active"),
    AxisState.FAULT_REACTION_ACTIVE: ("Fault reaction active (폴트 처리 중)", "Fault reaction active"),
    AxisState.FAULT: ("Fault (오류로 정지)", "Fault"),
}

AXIS_STATE_SHORT = {
    AxisState.UNKNOWN: ("?", "?"),
    AxisState.NOT_READY_TO_SWITCH_ON: ("초기화 중", "Not ready"),
    AxisState.SWITCH_ON_DISABLED: ("대기", "Switch on disabled"),
    AxisState.READY_TO_SWITCH_ON: ("준비 완료", "Ready"),
    AxisState.SWITCHED_ON: ("스위치 온", "Switched on"),
    AxisState.OPERATION_ENABLED: ("운전 중", "Enabled"),
    AxisState.QUICK_STOP_ACTIVE: ("급정지", "Quick stop"),
    AxisState.FAULT_REACTION_ACTIVE: ("폴트 처리 중", "Fault reaction"),
    AxisState.FAULT: ("폴트", "Fault"),
}

CW_COMMAND = {
    CwCommand.NONE: ("명령 없음", "No command"),
    CwCommand.SHUTDOWN: ("Shutdown (준비 상태로)", "Shutdown"),
    CwCommand.SWITCH_ON: ("Switch on / Disable operation", "Switch on / Disable operation"),
    CwCommand.ENABLE_OPERATION: ("Enable operation (토크 ON 요청)", "Enable operation"),
    CwCommand.DISABLE_VOLTAGE: ("Disable voltage (전원 차단)", "Disable voltage"),
    CwCommand.QUICK_STOP: ("Quick stop (급정지)", "Quick stop"),
    CwCommand.FAULT_RESET: ("Fault reset (폴트 해제)", "Fault reset"),
}

STATUSWORD_BITS = [
    (0, "Ready to switch on", "준비 완료"),
    (1, "Switched on", "스위치 온"),
    (2, "Operation enabled", "운전 가능"),
    (3, "Fault", "폴트"),
    (4, "Voltage enabled", "전원 인가"),
    (5, "Quick stop not active", "급정지 아님"),
    (6, "Switch on disabled", "스위치 온 금지"),
    (7, "Warning", "경고"),
    (9, "Remote", "원격 제어"),
    (10, "Target reached", "목표 도달"),
    (11, "Internal limit active", "내부 제한 동작"),
    (12, "Mode specific (bit 12)", "모드별 비트 12"),
    (13, "Mode specific (bit 13)", "모드별 비트 13"),
]

ERROR_REGISTER_BITS = [
    (0, "generic", "일반"),
    (1, "current", "전류"),
    (2, "voltage", "전압"),
    (3, "temperature", "온도"),
    (4, "communication", "통신"),
    (5, "device profile", "프로파일"),
    (7, "manufacturer", "제조사"),
]

# --------------------------------------------------------------------------
# SDO abort codes (CiA 301, table 22): code -> (ko, en, hint ko, hint en)
# --------------------------------------------------------------------------

SDO_ABORT = {
    0x05030000: ("토글 비트가 번갈아 바뀌지 않음", "Toggle bit not alternated",
                 "분할 전송 중 프레임이 빠졌거나 중복되었습니다. 버스 부하와 재전송 여부를 확인하세요.",
                 "A segment was lost or repeated. Check bus load and retransmissions."),
    0x05040000: ("SDO 프로토콜 시간 초과", "SDO protocol timed out",
                 "상대가 제때 응답하지 않았습니다. 노드가 켜져 있는지, 바쁜 상태인지 확인하세요.",
                 "The other side did not answer in time. Check that the node is alive and not overloaded."),
    0x05040001: ("알 수 없는 명령 지정자", "Client/server command specifier not valid or unknown",
                 "SDO 첫 바이트가 잘못되었습니다. 마스터 SDO 구현이나 블록 전송 지원 여부를 확인하세요.",
                 "First SDO byte is invalid. Check the master's SDO implementation / block transfer support."),
    0x05040002: ("잘못된 블록 크기", "Invalid block size", "블록 전송 설정을 확인하세요.", "Check block transfer settings."),
    0x05040003: ("잘못된 시퀀스 번호", "Invalid sequence number", "블록 전송 중 프레임이 빠졌습니다.",
                 "A block transfer frame was lost."),
    0x05040004: ("CRC 오류", "CRC error", "블록 전송 데이터가 손상되었습니다.", "Block transfer data was corrupted."),
    0x05040005: ("메모리 부족", "Out of memory", "노드 내부 메모리가 부족합니다. 데이터 크기를 줄이세요.",
                 "The node ran out of memory. Send less data."),
    0x06010000: ("지원하지 않는 접근", "Unsupported access to an object",
                 "이 오브젝트는 이 방식으로 접근할 수 없습니다. EDS의 AccessType을 확인하세요.",
                 "This object cannot be accessed this way. Check AccessType in the EDS."),
    0x06010001: ("쓰기 전용 오브젝트를 읽으려 함", "Attempt to read a write-only object",
                 "읽기가 불가능한 오브젝트입니다. 인덱스를 다시 확인하세요.", "The object is write-only."),
    0x06010002: ("읽기 전용 오브젝트에 쓰려 함", "Attempt to write a read-only object",
                 "값을 바꿀 수 없는 오브젝트입니다. 인덱스/서브인덱스를 잘못 지정했는지 확인하세요.",
                 "The object is read-only. Check index/sub-index."),
    0x06020000: ("오브젝트가 존재하지 않음", "Object does not exist in the object dictionary",
                 "노드에 이 인덱스가 없습니다. 장치 매뉴얼/EDS와 인덱스를 비교하세요.",
                 "The node has no such index. Compare with the device manual/EDS."),
    0x06040041: ("PDO에 매핑할 수 없는 오브젝트", "Object cannot be mapped to the PDO",
                 "PDO 매핑이 허용되지 않은 오브젝트입니다. EDS의 PDOMapping=1인지 확인하세요.",
                 "The object is not PDO-mappable (check PDOMapping in the EDS)."),
    0x06040042: ("PDO 길이 초과", "Number/length of mapped objects exceeds PDO length",
                 "매핑한 항목들의 비트 합이 64비트(8바이트)를 넘습니다.", "Mapped objects exceed 64 bits."),
    0x06040043: ("파라미터 호환성 문제", "General parameter incompatibility",
                 "다른 설정과 충돌합니다. PDO를 비활성화한 뒤 매핑을 바꿨는지 확인하세요.",
                 "Conflicts with another setting. Was the PDO disabled before remapping?"),
    0x06040047: ("장치 내부 호환성 문제", "General internal incompatibility in the device",
                 "장치 내부 조건 때문에 거부되었습니다. 매뉴얼을 확인하세요.", "Rejected by an internal condition."),
    0x06060000: ("하드웨어 오류로 접근 실패", "Access failed due to a hardware error",
                 "노드 하드웨어 문제입니다. 장치 상태를 점검하세요.", "Hardware problem in the node."),
    0x06070010: ("데이터 타입/길이 불일치", "Data type does not match, length does not match",
                 "보낸 데이터 크기가 오브젝트 타입과 다릅니다 (예: UINT16에 4바이트 전송).",
                 "Data size differs from the object type (e.g. 4 bytes for a UINT16)."),
    0x06070012: ("데이터 길이가 너무 김", "Data type does not match, length too high",
                 "오브젝트보다 큰 데이터를 보냈습니다.", "More data than the object holds."),
    0x06070013: ("데이터 길이가 너무 짧음", "Data type does not match, length too low",
                 "오브젝트보다 작은 데이터를 보냈습니다.", "Less data than the object needs."),
    0x06090011: ("서브인덱스가 존재하지 않음", "Sub-index does not exist",
                 "인덱스는 있지만 해당 서브인덱스가 없습니다.", "The index exists but not this sub-index."),
    0x06090030: ("허용되지 않는 값", "Invalid value for parameter",
                 "값의 범위나 허용 목록을 벗어났습니다.", "Value outside the allowed set."),
    0x06090031: ("값이 너무 큼", "Value of parameter written too high", "최댓값을 확인하세요.", "Check the maximum."),
    0x06090032: ("값이 너무 작음", "Value of parameter written too low", "최솟값을 확인하세요.", "Check the minimum."),
    0x06090036: ("최댓값이 최솟값보다 작음", "Maximum value is less than minimum value",
                 "범위 설정이 뒤바뀌었습니다.", "Min/max are swapped."),
    0x060A0023: ("SDO 연결 자원 없음", "Resource not available: SDO connection",
                 "동시에 너무 많은 SDO 연결을 시도했습니다.", "Too many concurrent SDO connections."),
    0x08000000: ("일반 오류", "General error", "장치 매뉴얼의 에러 설명을 확인하세요.", "See the device manual."),
    0x08000020: ("데이터를 저장/전달할 수 없음", "Data cannot be transferred or stored to the application",
                 "장치가 지금은 값을 받을 수 없습니다.", "The application cannot accept the value now."),
    0x08000021: ("로컬 제어 중이라 거부됨", "Data cannot be transferred because of local control",
                 "장치가 로컬(패널/다른 마스터) 제어 상태입니다.", "The device is under local control."),
    0x08000022: ("현재 장치 상태에서 불가", "Data cannot be transferred because of the present device state",
                 "흔한 원인: 운전 중(Operation enabled)에 변경할 수 없는 값을 쓰거나, NMT Operational 상태에서 PDO 매핑을 바꾼 경우입니다. 장치를 Pre-operational/정지 상태로 바꾼 뒤 다시 시도하세요.",
                 "Common cause: writing a value that cannot change while running, or remapping PDOs in "
                 "Operational. Put the device into pre-operational / disabled state first."),
    0x08000023: ("오브젝트 딕셔너리 없음", "Object dictionary not present", "장치 펌웨어를 확인하세요.",
                 "Check the device firmware."),
    0x08000024: ("데이터 없음", "No data available", "아직 유효한 값이 없습니다.", "No valid data yet."),
}

# --------------------------------------------------------------------------
# EMCY error codes (CiA 301 table 21 + common CiA 402 codes)
# --------------------------------------------------------------------------

EMCY_EXACT = {
    0x8110: ("CAN 오버런 (메시지 유실)", "CAN overrun (objects lost)"),
    0x8120: ("CAN Error passive 상태", "CAN in error passive mode"),
    0x8130: ("라이프가드/하트비트 오류", "Life guard or heartbeat error"),
    0x8140: ("Bus-off에서 복구됨", "Recovered from bus off"),
    0x8150: ("CAN-ID 충돌", "CAN-ID collision"),
    0x8210: ("PDO 길이 오류로 처리 안 됨", "PDO not processed due to length error"),
    0x8220: ("PDO 길이 초과", "PDO length exceeded"),
    0x8230: ("DAM MPDO 처리 안 됨", "DAM MPDO not processed"),
    0x8240: ("예상치 못한 SYNC 데이터 길이", "Unexpected SYNC data length"),
    0x8250: ("RPDO 타임아웃", "RPDO timeout"),
    0x2310: ("과전류 (지속)", "Continuous over current"),
    0x2320: ("단락 / 지락", "Short circuit / earth leakage"),
    0x3210: ("DC 링크 과전압", "DC link over-voltage"),
    0x3220: ("DC 링크 저전압", "DC link under-voltage"),
    0x4210: ("장치 과열", "Excess temperature device"),
    0x7121: ("모터 구속 (회전 불가)", "Motor blocked"),
    0x7305: ("엔코더(증분형 센서 1) 오류", "Incremental sensor 1 fault"),
    0x8611: ("추종 오차 초과 (Following error)", "Following error"),
    0x8612: ("기준 위치 한계", "Reference limit"),
}

EMCY_GROUP = [  # (mask, value, ko, en) — first match wins
    (0xFF00, 0x0000, "에러 해제 / 오류 없음", "Error reset or no error"),
    (0xFF00, 0x1000, "일반 오류", "Generic error"),
    (0xFF00, 0x2100, "전류 오류 (입력측)", "Current, device input side"),
    (0xFF00, 0x2200, "전류 오류 (장치 내부)", "Current inside the device"),
    (0xFF00, 0x2300, "전류 오류 (출력측)", "Current, device output side"),
    (0xF000, 0x2000, "전류 오류", "Current"),
    (0xFF00, 0x3100, "전원 전압 오류", "Mains voltage"),
    (0xFF00, 0x3200, "장치 내부 전압 오류", "Voltage inside the device"),
    (0xFF00, 0x3300, "출력 전압 오류", "Output voltage"),
    (0xF000, 0x3000, "전압 오류", "Voltage"),
    (0xFF00, 0x4100, "주변 온도 오류", "Ambient temperature"),
    (0xFF00, 0x4200, "장치 온도 오류", "Device temperature"),
    (0xFF00, 0x4300, "드라이브 온도 오류", "Drive temperature"),
    (0xF000, 0x4000, "온도 오류", "Temperature"),
    (0xF000, 0x5000, "장치 하드웨어 오류", "Device hardware"),
    (0xFF00, 0x6100, "내부 소프트웨어 오류", "Internal software"),
    (0xFF00, 0x6200, "사용자 소프트웨어 오류", "User software"),
    (0xFF00, 0x6300, "데이터 세트 오류", "Data set"),
    (0xF000, 0x6000, "장치 소프트웨어 오류", "Device software"),
    (0xFF00, 0x7100, "모터/구동부 오류", "Additional modules: motor"),
    (0xFF00, 0x7300, "센서(엔코더) 오류", "Additional modules: sensor"),
    (0xF000, 0x7000, "추가 모듈 오류", "Additional modules"),
    (0xFF00, 0x8100, "통신 오류", "Communication"),
    (0xFF00, 0x8200, "프로토콜 오류", "Protocol error"),
    (0xFF00, 0x8400, "속도 제어 오류", "Velocity / speed controller"),
    (0xFF00, 0x8500, "위치 제어 오류", "Position controller"),
    (0xFF00, 0x8600, "위치 제어 오류", "Positioning controller"),
    (0xF000, 0x8000, "감시(모니터링) 오류", "Monitoring"),
    (0xF000, 0x9000, "외부 오류", "External error"),
    (0xFF00, 0xF000, "추가 기능 오류", "Additional functions"),
    (0xFF00, 0xFF00, "제조사 전용 오류 (매뉴얼 참고)", "Device specific (see manual)"),
]


def sdo_abort_text(code: int, lang: str) -> tuple[str, str]:
    """(description, what to check)"""
    entry = SDO_ABORT.get(code)
    if entry is None:
        return (_p(lang, "알 수 없는 중단 코드 (제조사 전용일 수 있음)", "Unknown abort code (may be vendor specific)"),
                _p(lang, "장치 매뉴얼에서 이 코드를 찾아보세요.", "Look this code up in the device manual."))
    ko, en, hko, hen = entry
    return (_p(lang, ko, en), _p(lang, hko, hen))


def emcy_text(code: int, lang: str) -> str:
    if code in EMCY_EXACT:
        ko, en = EMCY_EXACT[code]
        return _p(lang, ko, en)
    for mask, value, ko, en in EMCY_GROUP:
        if code & mask == value:
            return _p(lang, ko, en)
    return _p(lang, "알 수 없는 오류 코드", "Unknown error code")


def error_register_text(reg: int, lang: str) -> str:
    names = [_p(lang, ko, en) for bit, en, ko in ERROR_REGISTER_BITS if reg & (1 << bit)]
    return ", ".join(names) if names else _p(lang, "없음", "none")


def axis_state_text(state: AxisState, lang: str, short: bool = False) -> str:
    table = AXIS_STATE_SHORT if short else AXIS_STATE
    ko, en = table.get(state, table[AxisState.UNKNOWN])
    return _p(lang, ko, en)


def cw_command_text(cmd: CwCommand, lang: str) -> str:
    ko, en = CW_COMMAND.get(cmd, CW_COMMAND[CwCommand.NONE])
    return _p(lang, ko, en)


def hb_state_text(state: int, lang: str) -> str:
    if state in HB_STATE:
        ko, en = HB_STATE[state]
        return _p(lang, ko, en)
    return _p(lang, f"알 수 없는 상태 0x{state:02X}", f"Unknown state 0x{state:02X}")


def nmt_cmd_text(cmd: int, lang: str) -> str:
    if cmd in NMT_CMD:
        ko, en = NMT_CMD[cmd]
        return _p(lang, ko, en)
    return _p(lang, f"알 수 없는 명령 0x{cmd:02X}", f"Unknown command 0x{cmd:02X}")


def kind_label(kind: Kind, lang: str) -> str:
    ko, en = KIND_LABEL[kind]
    return _p(lang, ko, en)


def kind_help(kind: Kind, lang: str) -> str:
    ko, en = KIND_HELP[kind]
    return _p(lang, ko, en)


def statusword_bits(sw: int, lang: str) -> list[str]:
    return [_p(lang, ko, en) for bit, en, ko in STATUSWORD_BITS if sw & (1 << bit)]


# --------------------------------------------------------------------------
# Frame summaries
# --------------------------------------------------------------------------

def who(log: "CanopenLog", node: int, axis: int, lang: str) -> str:
    """'노드 3' or, for multi-axis drives, '노드 3 · 축 2'."""
    if log.trace.axis_count(node) > 1:
        return _p(lang, f"노드 {node} · 축 {axis + 1}", f"Node {node} axis {axis + 1}")
    return _p(lang, f"노드 {node}", f"Node {node}")


def _axis_prefix(log: "CanopenLog", node: int, axis: int, lang: str) -> str:
    if log.trace.axis_count(node) > 1:
        return _p(lang, f"축{axis + 1} ", f"axis{axis + 1} ")
    return ""


def _obj(log: "CanopenLog", node: int, index: int, sub: int, lang: str) -> str:
    info = log.object_info(node, index, sub)
    name = f" {info.name(lang)}" if info else ""
    return f"0x{index:04X}:{sub:02X}{name}"


def _value_text(log: "CanopenLog", node: int, index: int, sub: int, raw: int, nbytes: int, lang: str) -> str:
    info = log.object_info(node, index, sub)
    dtype = info.dtype if info else None
    if 0x1600 <= index <= 0x17FF or 0x1A00 <= index <= 0x1BFF:
        if sub > 0 and nbytes == 4:
            return mapping_entry_text(raw)
    base = axis_base(index)
    if base == 0x6040 and nbytes == 2:
        return f"0x{raw:04X} → {cw_command_text(decode_controlword(raw), lang)}"
    if base == 0x6041 and nbytes == 2:
        return f"0x{raw:04X} → {axis_state_text(decode_statusword(raw), lang)}"
    if base in (0x6060, 0x6061) and nbytes >= 1:
        mode = to_signed(raw, 8)
        if mode in MODES_OF_OPERATION:
            ko, en = MODES_OF_OPERATION[mode]
            return f"{mode} → {_p(lang, ko, en)}"
    text = format_value(raw, nbytes, dtype)
    if info and info.unit:
        text += f" {info.unit}"
    return text


def frame_summary(log: "CanopenLog", row: int, lang: str = "ko") -> str:
    r = log.trace.record(row)
    f = log.trace.frame(row)
    k = r.kind
    if k == Kind.NMT:
        target = _p(lang, "모든 노드", "all nodes") if r.nmt_target == 0 else _p(lang, f"노드 {r.nmt_target}", f"node {r.nmt_target}")
        return f"{nmt_cmd_text(r.nmt_cmd, lang)} → {target}"
    if k == Kind.SYNC:
        return "SYNC" + (f" (counter {f.data[0]})" if f.dlc >= 1 else "")
    if k == Kind.EMCY:
        if r.emcy_code == 0:
            return _p(lang, "에러 해제 (EMCY 0x0000)", "Error reset (EMCY 0x0000)")
        return f"EMCY 0x{r.emcy_code:04X}: {emcy_text(r.emcy_code, lang)} [{_p(lang, '에러 레지스터', 'error register')}: {error_register_text(r.error_register, lang)}]"
    if k == Kind.HEARTBEAT:
        if f.rtr:
            return _p(lang, "노드 가딩 요청 (RTR)", "Node guarding request (RTR)")
        return hb_state_text(r.hb_state, lang)
    if k in (Kind.TPDO, Kind.RPDO):
        name = f"{'TPDO' if k == Kind.TPDO else 'RPDO'}{r.pdo_num}"
        parts = []
        for w in (log.trace.axis_words(row) if r.words_count else []):
            pre = _axis_prefix(log, r.node, w.axis, lang)
            if w.is_statusword:
                parts.append(f"{pre}{_p(lang, '상태', 'state')}: {axis_state_text(w.state, lang, short=True)} (SW 0x{w.word:04X})")
            elif w.command != CwCommand.NONE:
                parts.append(f"{pre}{_p(lang, '명령', 'cmd')}: {cw_command_text(w.command, lang)} (CW 0x{w.word:04X})")
            else:
                parts.append(f"{pre}CW 0x{w.word:04X}")
        for fld in log.trace.pdo_fields(row):
            if r.words_count and axis_base(fld.index) in (0x6040, 0x6041):
                continue
            info = log.object_info(r.node, fld.index, fld.sub)
            label = info.name(lang) if info else f"0x{fld.index:04X}:{fld.sub:02X}"
            if axis_of(fld.index) == 0 and log.trace.axis_count(r.node) > 1:
                label = _p(lang, "축 1 ", "Axis 1 ") + label
            value = format_value(fld.raw, fld.bits, info.dtype if info else None, bits=True)
            if axis_base(fld.index) in (0x6060, 0x6061):
                mode = to_signed(fld.raw, 8)
                if mode in MODES_OF_OPERATION:
                    value = _p(lang, *MODES_OF_OPERATION[mode])
            elif "(" in value:
                value = value.split(" (")[0]
            parts.append(f"{label}={value}")
        return f"{name}: " + (", ".join(parts) if parts else f.data.hex(" ").upper())
    if k in (Kind.SDO_REQ, Kind.SDO_RESP):
        return _sdo_summary(log, r, f, lang)
    if k == Kind.ERROR_FRAME:
        return _p(lang, "CAN 버스 오류 보고", "CAN bus error reported")
    if k == Kind.LSS:
        return "LSS"
    return f.data.hex(" ").upper()


def _sdo_summary(log, r, f, lang) -> str:
    req = r.kind == Kind.SDO_REQ
    obj = _obj(log, r.node, r.index, r.sub, lang) if r.sdo_index_known else ""
    t = r.sdo_type
    if t == SdoType.ABORT:
        desc, _ = sdo_abort_text(r.abort_code, lang)
        who = _p(lang, "마스터가", "master") if req else _p(lang, "노드가", "node")
        return _p(lang, f"SDO 중단 ({who} 중단): {obj} → 0x{r.abort_code:08X} {desc}",
                  f"SDO abort by {who}: {obj} → 0x{r.abort_code:08X} {desc}")
    if t == SdoType.DOWNLOAD_INIT:
        if req:
            if r.sdo_expedited and r.value_len:
                val = _value_text(log, r.node, r.index, r.sub, r.value, r.value_len, lang)
                return _p(lang, f"쓰기 요청 {obj} = {val}", f"Write {obj} = {val}")
            size = f" ({r.sdo_size} bytes)" if r.sdo_size else ""
            return _p(lang, f"쓰기 요청 (분할 전송) {obj}{size}", f"Write (segmented) {obj}{size}")
        return _p(lang, f"쓰기 성공 {obj}", f"Write OK {obj}")
    if t == SdoType.UPLOAD_INIT:
        if req:
            return _p(lang, f"읽기 요청 {obj}", f"Read {obj}")
        if r.sdo_expedited and r.value_len:
            val = _value_text(log, r.node, r.index, r.sub, r.value, r.value_len, lang)
            return _p(lang, f"읽기 응답 {obj} = {val}", f"Read reply {obj} = {val}")
        size = f" ({r.sdo_size} bytes)" if r.sdo_size else ""
        return _p(lang, f"읽기 응답 (분할 전송 시작) {obj}{size}", f"Read reply (segmented){size} {obj}")
    if t in (SdoType.DOWNLOAD_SEGMENT, SdoType.UPLOAD_SEGMENT):
        upload = t == SdoType.UPLOAD_SEGMENT
        carries_data = (upload and not req) or (not upload and req)
        if not carries_data:
            if req:
                return _p(lang, f"다음 조각 요청 {obj}", f"Request next segment {obj}")
            return _p(lang, f"조각 수신 확인 {obj}", f"Segment acknowledged {obj}")
        b0 = f.data[0] if f.dlc else 0
        n_unused = (b0 >> 1) & 0x7
        data = bytes(f.data[1:8 - n_unused])
        last = _p(lang, " (마지막 조각)", " (last)") if b0 & 0x01 else ""
        text = repr(data.decode("latin-1")) if data and all(32 <= c < 127 for c in data) else data.hex(" ").upper()
        return _p(lang, f"분할 데이터 {obj}: {text}{last}", f"Segment {obj}: {text}{last}")
    if t == SdoType.BLOCK:
        return _p(lang, f"블록 전송 {obj}", f"Block transfer {obj}")
    return _p(lang, "잘못된 SDO 프레임", "Invalid SDO frame")


# --------------------------------------------------------------------------
# Frame details (for the side panel)
# --------------------------------------------------------------------------

def frame_details(log: "CanopenLog", row: int, lang: str = "ko") -> list[tuple[str, str]]:
    r = log.trace.record(row)
    f = log.trace.frame(row)
    rows: list[tuple[str, str]] = [
        (_p(lang, "종류", "Type"), kind_label(r.kind, lang)),
        (_p(lang, "설명", "What it is"), kind_help(r.kind, lang)),
        (_p(lang, "시간", "Time"), f"{f.t:.6f} s"),
        ("COB-ID", f"0x{f.id:03X}" + (" (29-bit)" if f.ext else "")),
    ]
    if r.node:
        rows.append((_p(lang, "노드", "Node"), str(r.node)))
    rows.append(("DLC", str(f.dlc) + (" (RTR)" if f.rtr else "")))
    rows.append((_p(lang, "데이터", "Data"), f.data.hex(" ").upper() or "-"))
    rows.append((_p(lang, "해석", "Meaning"), frame_summary(log, row, lang)))

    if r.kind in (Kind.TPDO, Kind.RPDO) and r.map_ref is not None:
        m = log.trace.mapping(r.map_ref)
        origin = {
            "CIA402_DEFAULT": _p(lang, "CiA 402 기본 매핑 (추정)", "CiA 402 default mapping (assumed)"),
            "EDS": "EDS",
            "LOG_SDO": _p(lang, f"로그 안의 SDO 설정 (행 {m.since_row + 1})", f"SDO configuration in the log (row {m.since_row + 1})"),
        }.get(m.origin.name, "-")
        rows.append((_p(lang, "PDO 매핑 출처", "Mapping source"), origin))
        for fld in log.trace.pdo_fields(row):
            info = log.object_info(r.node, fld.index, fld.sub)
            label = f"0x{fld.index:04X}:{fld.sub:02X} " + (info.name(lang) if info else "")
            val = format_value(fld.raw, fld.bits, info.dtype if info else None, bits=True)
            if not fld.complete:
                val += _p(lang, " (프레임이 짧아 값이 잘림)", " (frame too short)")
            rows.append((label.strip(), val))
    multi = log.trace.axis_count(r.node) > 1
    for w in (log.trace.axis_words(row) if r.words_count else []):
        ax = _p(lang, f"축 {w.axis + 1} ", f"Axis {w.axis + 1} ") if multi else ""
        if w.is_statusword:
            bits = ", ".join(statusword_bits(w.word, lang)) or "-"
            rows.append((ax + _p(lang, "상태", "state") if multi else _p(lang, "축 상태", "Axis state"),
                         axis_state_text(w.state, lang)))
            rows.append((ax + _p(lang, "스테이터스워드 비트", "statusword bits"), bits))
        else:
            rows.append((ax + _p(lang, "컨트롤워드 명령", "controlword command"), cw_command_text(w.command, lang)))
    if r.kind == Kind.EMCY and r.emcy_code:
        rows.append((_p(lang, "에러 코드", "Error code"), f"0x{r.emcy_code:04X} {emcy_text(r.emcy_code, lang)}"))
        rows.append((_p(lang, "에러 레지스터", "Error register"), f"0x{r.error_register:02X} ({error_register_text(r.error_register, lang)})"))
        if f.dlc >= 8:
            rows.append((_p(lang, "제조사 데이터", "Manufacturer data"), bytes(f.data[3:8]).hex(" ").upper()))
    if r.sdo_type == SdoType.ABORT:
        desc, hint = sdo_abort_text(r.abort_code, lang)
        rows.append((_p(lang, "중단 사유", "Abort reason"), desc))
        rows.append((_p(lang, "확인할 것", "What to check"), hint))
    rows.append((_p(lang, "원본 줄 번호", "Source line"), str(f.line)))
    return rows


# --------------------------------------------------------------------------
# Issues
# --------------------------------------------------------------------------

SEVERITY = {
    Severity.INFO: ("정보", "Info"),
    Severity.WARNING: ("경고", "Warning"),
    Severity.ERROR: ("오류", "Error"),
}


def severity_text(sev: Severity, lang: str) -> str:
    return _p(lang, *SEVERITY[sev])


def issue_text(log: "CanopenLog", issue, lang: str = "ko") -> tuple[str, str]:
    """(one-line title, explanation with what to check)"""
    n = issue.node
    T = issue.type
    if T == IssueType.SDO_ABORT:
        desc, hint = sdo_abort_text(issue.code, lang)
        obj = _obj(log, n, issue.index, issue.sub, lang)
        return (_p(lang, f"노드 {n}: SDO 실패 – {desc}", f"Node {n}: SDO failed – {desc}"),
                _p(lang, f"{obj} 접근이 중단되었습니다 (코드 0x{issue.code:08X}). {hint}",
                   f"Access to {obj} was aborted (code 0x{issue.code:08X}). {hint}"))
    if T == IssueType.SDO_NO_RESPONSE:
        obj = _obj(log, n, issue.index, issue.sub, lang)
        what = _p(lang, "읽기", "read") if issue.code else _p(lang, "쓰기", "write")
        return (_p(lang, f"노드 {n}: SDO 응답 없음", f"Node {n}: no SDO response"),
                _p(lang, f"{obj} {what} 요청에 {issue.value:g}초 안에 응답이 없었습니다. 노드-ID가 맞는지, 노드 전원과 배선, NMT 상태(Stopped면 SDO에 응답하지 않음)를 확인하세요.",
                   f"The {what} of {obj} got no answer within {issue.value:g} s. Check the node-ID, power, wiring and NMT state (a Stopped node does not answer SDO)."))
    if T == IssueType.EMCY:
        reg = error_register_text(issue.index, lang)
        return (_p(lang, f"노드 {n}: EMCY 0x{issue.code:04X} {emcy_text(issue.code, lang)}",
                   f"Node {n}: EMCY 0x{issue.code:04X} {emcy_text(issue.code, lang)}"),
                _p(lang, f"노드가 비상 메시지를 보냈습니다. 에러 레지스터: {reg}. 정확한 원인은 장치 매뉴얼의 에러 코드표에서 0x{issue.code:04X}를 찾아보세요. 드라이브라면 0x603F(에러 코드)도 함께 확인하세요.",
                   f"The node reported an emergency. Error register: {reg}. Look up 0x{issue.code:04X} in the device manual; for drives also read 0x603F."))
    if T == IssueType.EMCY_RESET:
        return (_p(lang, f"노드 {n}: 오류 해제 알림", f"Node {n}: error reset"),
                _p(lang, "노드가 이전 오류가 해제되었다고 알렸습니다 (EMCY 0x0000).", "The node reports that previous errors are cleared (EMCY 0x0000)."))
    if T == IssueType.HEARTBEAT_GAP:
        return (_p(lang, f"노드 {n}: 하트비트가 {issue.value:.3f}초 끊김", f"Node {n}: heartbeat gap of {issue.value:.3f} s"),
                _p(lang, f"평소에는 {issue.expected * 1000:.0f} ms마다 오던 하트비트가 {issue.value:.3f}초 동안 오지 않았습니다. 순간적인 통신 단절, 버스 과부하, 노드 CPU 과부하를 의심할 수 있습니다. 같은 시점의 에러 프레임과 다른 노드 상태를 함께 보세요.",
                   f"Normally every {issue.expected * 1000:.0f} ms, but nothing arrived for {issue.value:.3f} s. Suspect a short disconnect, bus overload or node CPU overload."))
    if T == IssueType.HEARTBEAT_LOST:
        return (_p(lang, f"노드 {n}: 하트비트 끊김 (응답 없음)", f"Node {n}: heartbeat lost"),
                _p(lang, f"마지막 하트비트 이후 로그 끝까지 {issue.value:.2f}초 동안 아무 하트비트가 없습니다 (평소 주기 {issue.expected * 1000:.0f} ms). 노드 전원, 커넥터, 노드 리셋 여부를 확인하세요.",
                   f"No heartbeat for {issue.value:.2f} s until the end of the log (normal period {issue.expected * 1000:.0f} ms). Check power, connectors and whether the node reset."))
    if T == IssueType.NODE_REBOOT:
        if issue.code:
            return (_p(lang, f"노드 {n}: 리셋 후 재부팅", f"Node {n}: rebooted after reset command"),
                    _p(lang, "NMT 리셋 명령 뒤의 정상적인 재부팅입니다.", "Normal reboot after an NMT reset command."))
        return (_p(lang, f"노드 {n}: 예상치 못한 재부팅", f"Node {n}: unexpected reboot"),
                _p(lang, "리셋 명령이 없었는데 노드가 Boot-up 메시지를 다시 보냈습니다. 전원 순간 저하(브라운아웃), 워치독 리셋, 펌웨어 크래시를 의심하세요.",
                   "The node sent boot-up again without a reset command. Suspect a brown-out, watchdog reset or firmware crash."))
    off = 0x800 * issue.axis
    cw_idx, err_idx = 0x6040 + off, 0x603F + off
    if T == IssueType.AXIS_FAULT:
        extra = ""
        if issue.related_row is not None:
            r = log.trace.record(issue.related_row)
            extra = _p(lang, f" 같은 시점에 보고된 EMCY 0x{r.emcy_code:04X}({emcy_text(r.emcy_code, lang)})가 원인일 가능성이 큽니다.",
                       f" The EMCY 0x{r.emcy_code:04X} ({emcy_text(r.emcy_code, lang)}) reported at the same time is the likely cause.")
        return (_p(lang, f"{who(log, n, issue.axis, lang)}: 드라이브 폴트 발생", f"{who(log, n, issue.axis, lang)}: drive entered Fault"),
                _p(lang, f"스테이터스워드 0x{issue.code:04X}에서 Fault 비트가 켜졌습니다.{extra} 원인을 해결한 뒤 컨트롤워드(0x{cw_idx:04X}) bit 7(Fault reset)을 0→1로 올려야 해제됩니다. 드라이브 에러 코드는 0x{err_idx:04X}에서 읽을 수 있습니다.",
                   f"Statusword 0x{issue.code:04X} shows Fault.{extra} Fix the cause, then raise bit 7 (fault reset) of the controlword (0x{cw_idx:04X}) from 0 to 1. The drive error code is in 0x{err_idx:04X}."))
    if T == IssueType.AXIS_QUICK_STOP:
        return (_p(lang, f"{who(log, n, issue.axis, lang)}: 급정지 동작", f"{who(log, n, issue.axis, lang)}: quick stop active"),
                _p(lang, "드라이브가 Quick stop 상태로 들어갔습니다. 마스터가 Quick stop 명령(컨트롤워드 bit 2 = 0)을 보냈는지 확인하세요.",
                   "The drive is in quick stop. Check whether the master sent quick stop (controlword bit 2 = 0)."))
    if T == IssueType.AXIS_ENABLE_FAILED:
        code = issue.code if issue.code < 0x80 else -1
        state = axis_state_text(AxisState(code), lang)
        return (_p(lang, f"{who(log, n, issue.axis, lang)}: 운전 허가(Enable)가 적용되지 않음", f"{who(log, n, issue.axis, lang)}: enable operation did not take effect"),
                _p(lang, f"Enable operation 명령 후 {issue.value:g}초가 지나도 Operation enabled가 되지 않았습니다 (현재: {state}). CiA 402는 컨트롤워드(0x{cw_idx:04X})에 Shutdown(0x06) → Switch on(0x07) → Enable operation(0x0F) 순서로 보내야 하며, 드라이브가 Fault 상태면 먼저 Fault reset이 필요합니다. 주전원(모터 전원) 인가 여부도 확인하세요.",
                   f"Operation enabled was not reached {issue.value:g} s after the command (now: {state}). CiA 402 needs Shutdown (0x06) → Switch on (0x07) → Enable operation (0x0F) on the controlword (0x{cw_idx:04X}); a faulted drive needs a fault reset first. Also check motor power."))
    if T == IssueType.AXIS_FAULT_RESET_FAILED:
        return (_p(lang, f"{who(log, n, issue.axis, lang)}: 폴트 리셋 실패", f"{who(log, n, issue.axis, lang)}: fault reset failed"),
                _p(lang, f"Fault reset 후 {issue.value:g}초가 지나도 폴트가 풀리지 않았습니다. 오류 원인이 아직 남아 있습니다 (예: 과전류, 엔코더 오류, 비상정지 입력). EMCY와 0x{err_idx:04X} 값을 확인하세요.",
                   f"The fault is still present {issue.value:g} s after the reset. The cause is still active (e.g. over current, encoder fault, e-stop input). Check EMCY and 0x{err_idx:04X}."))
    if T == IssueType.BUS_ERROR_FRAME:
        return (_p(lang, "CAN 버스 에러 프레임", "CAN bus error frames"),
                _p(lang, "CAN 드라이버가 버스 오류를 보고했습니다. 종단저항(양 끝 120Ω), 통신 속도 일치, 배선 길이, GND 연결을 확인하세요.",
                   "The CAN driver reported bus errors. Check termination (120 Ω at both ends), bit rate, cable length and ground."))
    if T == IssueType.PARSE_ERRORS:
        return (_p(lang, f"해석하지 못한 줄 {issue.code}개", f"{issue.code} lines could not be parsed"),
                _p(lang, f"candump 형식이 아닌 줄을 건너뛰었습니다 (첫 번째: {int(issue.value)}번째 줄). 로그 형식을 확인하세요.",
                   f"Skipped lines that are not candump output (first: line {int(issue.value)})."))
    return (str(T), "")
