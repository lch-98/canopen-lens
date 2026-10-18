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
        return _p(lang, f"축 {axis + 1} ", f"Axis {axis + 1} ")
    return ""


def obj_name(log: "CanopenLog", node: int, index: int, sub: int, lang: str) -> str:
    """Name of an object; on multi-axis drives axis-1 objects (0x6000-0x67FF) are
    labelled "축 1" so they cannot be mistaken for the whole device."""
    info = log.object_info(node, index, sub)
    name = info.name(lang) if info else ""
    if name and axis_of(index) == 0 and log.trace.axis_count(node) > 1:
        name = _p(lang, "축 1 ", "Axis 1 ") + name
    return name


def _obj(log: "CanopenLog", node: int, index: int, sub: int, lang: str) -> str:
    name = obj_name(log, node, index, sub, lang)
    return f"0x{index:04X}:{sub:02X}" + (f" {name}" if name else "")


CIA402_OBJECTS = {0x603F, 0x6040, 0x6041, 0x6060, 0x6061, 0x6064, 0x606C, 0x6071, 0x6077, 0x607A,
                  0x6081, 0x6083, 0x6084, 0x6098, 0x60FF, 0x6502}


def drive_reason(log: "CanopenLog", node: int, lang: str = "ko") -> str:
    """Why a node is treated as a CiA 402 drive, pointing at the evidence in the log."""
    eds = getattr(log, "eds", {}).get(node)
    if eds is not None and eds.is_cia402:
        return _p(lang, f"지정한 EDS({eds.title})의 장치 종류가 CiA 402(드라이브)입니다.",
                  f"The attached EDS ({eds.title}) declares device profile CiA 402 (drive).")
    try:
        forced = any(n.node == node and n.drive_forced for n in log.trace.nodes)
    except (AttributeError, TypeError):
        forced = False
    if forced:
        return _p(lang, "노드 탭에서 'CiA 402 드라이브로 해석'을 직접 선택했습니다.",
                  "'Decode as CiA 402 drive' was selected in the Nodes tab.")
    if not hasattr(log.trace, "filter"):
        return ""
    sdo_rows = log.trace.filter(kinds=[Kind.SDO_REQ, Kind.SDO_RESP], node=node)
    other = None
    for row in sdo_rows:
        r = log.trace.record(int(row))
        if not r.sdo_index_known:
            continue
        if (r.kind == Kind.SDO_RESP and r.sdo_type == SdoType.UPLOAD_INIT and r.index == 0x1000
                and r.value_len and (r.value & 0xFFFF) == 402):
            return _p(lang, f"{int(row) + 1}행에서 장치 종류(0x1000)를 읽었더니 0x{r.value:08X}, 즉 CiA 402(드라이브)였습니다.",
                      f"Row {int(row) + 1} read the device type (0x1000) as 0x{r.value:08X}, i.e. CiA 402 (drive).")
        if other is None and r.kind == Kind.SDO_REQ and r.sub == 0 and axis_base(r.index) in CIA402_OBJECTS:
            other = _p(lang, f"{int(row) + 1}행에서 CiA 402 드라이브에만 있는 오브젝트 {_obj(log, node, r.index, r.sub, lang)}에 접근했습니다.",
                       f"Row {int(row) + 1} accessed {_obj(log, node, r.index, r.sub, lang)}, an object only CiA 402 drives have.")
        if (other is None and r.kind == Kind.SDO_REQ and r.sdo_type == SdoType.DOWNLOAD_INIT and r.sub >= 1
                and (0x1600 <= r.index <= 0x1603 or 0x1A00 <= r.index <= 0x1A03)
                and axis_base(r.value >> 16) in (0x6040, 0x6041)):
            other = _p(lang, f"{int(row) + 1}행에서 컨트롤워드/스테이터스워드를 PDO에 매핑했습니다.",
                       f"Row {int(row) + 1} mapped the controlword/statusword into a PDO.")
    return other or ""


def _value_text(log: "CanopenLog", node: int, index: int, sub: int, raw: int, nbytes: int, lang: str) -> str:
    info = log.object_info(node, index, sub)
    dtype = info.dtype if info else None
    if 0x1600 <= index <= 0x17FF or 0x1A00 <= index <= 0x1BFF:
        if sub > 0 and nbytes == 4:
            name = obj_name(log, node, raw >> 16, (raw >> 8) & 0xFF, lang) if raw else ""
            return mapping_entry_text(raw) + (f" ({name})" if name else "")
    if index == 0x1000 and sub == 0 and nbytes == 4:
        return f"0x{raw:08X} → {device_type_text(raw, lang)}"
    if (0x1400 <= index <= 0x15FF or 0x1800 <= index <= 0x19FF) and sub == 1 and nbytes == 4:
        return f"0x{raw:08X} → {pdo_cob_id_text(raw, node, index, lang)}"
    if (0x1400 <= index <= 0x15FF or 0x1800 <= index <= 0x19FF) and sub == 2 and nbytes == 1:
        return f"0x{raw:02X} → {transmission_type_text(raw, index >= 0x1800, lang)}"
    if index == 0x1016 and sub >= 1 and nbytes == 4:
        return f"0x{raw:08X} → {consumer_hb_text(raw, lang)}"
    if axis_base(index) == 0x6502 and nbytes == 4:
        return f"0x{raw:08X} → {drive_modes_text(raw, lang)}"
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
            label = obj_name(log, r.node, fld.index, fld.sub, lang) or f"0x{fld.index:04X}:{fld.sub:02X}"
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
            "CIA402_DEFAULT": _p(lang, "CiA 402 표준 기본 매핑 (추정)", "CiA 402 default mapping (assumed)"),
            "EDS": _p(lang, "지정한 EDS 파일", "the attached EDS file"),
            "LOG_SDO": _p(lang, f"로그 안의 SDO 설정 ({m.since_row + 1}행에서 완료)",
                          f"SDO configuration in the log (completed at row {m.since_row + 1})"),
        }.get(m.origin.name, "-")
        rows.append((_p(lang, "PDO 매핑 출처", "Mapping source"), origin))
        if m.origin.name == "CIA402_DEFAULT":
            layout = " + ".join(_obj(log, r.node, e.index, e.sub, lang) for e in m.entries)
            pdo = f"{'TPDO' if m.tx else 'RPDO'}{m.num}"
            reason = drive_reason(log, r.node, lang)
            rows.append((_p(lang, "추정 근거", "Why assumed"), _p(lang,
                f"{reason} 로그에 이 PDO의 매핑 설정이 없고 EDS도 지정되지 않아, CiA 402 표준 기본 배치({pdo} = {layout})를 적용했습니다. "
                "장치가 다른 배치를 쓰면 값이 틀릴 수 있으니, 노드 탭에서 EDS를 지정하면 정확해집니다.",
                f"{reason} The log contains no mapping for this PDO and no EDS is attached, so the CiA 402 default layout "
                f"({pdo} = {layout}) is used. If the device uses a different layout the values may be wrong; attach the EDS in the Nodes tab to be sure.").strip()))
        for fld in log.trace.pdo_fields(row):
            info = log.object_info(r.node, fld.index, fld.sub)
            label = f"0x{fld.index:04X}:{fld.sub:02X} " + obj_name(log, r.node, fld.index, fld.sub, lang)
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
    """(one-line title, explanation). See explain.explain_issue for the structured form."""
    from .explain import explain_issue

    ex = explain_issue(log, issue, lang)
    return ex.title, ex.as_text(lang)


# --------------------------------------------------------------------------
# Device type (object 0x1000)
# --------------------------------------------------------------------------

DEVICE_PROFILES = {
    401: ("범용 입출력(I/O) 모듈", "generic I/O module"),
    402: ("드라이브·모션 제어 (CiA 402)", "drive and motion control (CiA 402)"),
    404: ("측정 장치·폐루프 제어기", "measuring device / closed-loop controller"),
    405: ("PLC (IEC 61131-3)", "PLC (IEC 61131-3)"),
    406: ("엔코더", "encoder"),
    408: ("유압 밸브", "hydraulic valve"),
    410: ("경사계", "inclinometer"),
    417: ("엘리베이터", "lift / elevator"),
    418: ("배터리", "battery module"),
    419: ("충전기", "battery charger"),
}

CIA402_TYPES = {
    0x01: ("주파수 변환기(인버터)", "frequency converter"),
    0x02: ("서보 드라이브", "servo drive"),
    0x03: ("스테퍼 모터 드라이브", "stepper motor drive"),
}


def pdo_cob_id_text(raw: int, node: int, index: int, lang: str) -> str:
    """0x80000181 on 0x1800 -> 'ID 0x181 (노드 1 TPDO1 기본값), 꺼짐 — 설정을 바꾸는 중'."""
    tx = index >= 0x1800
    n = index - (0x1800 if tx else 0x1400)          # 0-based PDO number
    can_id = raw & (0x1FFFFFFF if raw & 0x20000000 else 0x7FF)
    parts = [f"ID 0x{can_id:03X}"]
    if n < 4 and 0 < node < 128 and not raw & 0x20000000:
        default = (0x180 if tx else 0x200) + 0x100 * n + node
        pdo = f"{'TPDO' if tx else 'RPDO'}{n + 1}"
        if can_id == default:
            parts[0] += _p(lang, f" (노드 {node} {pdo} 기본값)", f" (node {node} {pdo} default)")
        else:
            parts[0] += _p(lang, f" (기본값 0x{default:03X}과 다름)", f" (default would be 0x{default:03X})")
    if raw & 0x20000000:
        parts.append(_p(lang, "29비트 ID", "29-bit ID"))
    if raw & 0x80000000:
        parts.append(_p(lang, "꺼짐 (사용 안 함, 보통 설정을 바꾸는 동안)",
                        "disabled (usually while it is being reconfigured)"))
    else:
        parts.append(_p(lang, "켜짐 (사용 중)", "enabled"))
    if tx and raw & 0x40000000:
        parts.append(_p(lang, "RTR 요청 받지 않음", "no RTR"))
    return ", ".join(parts)


def transmission_type_text(t: int, tx: bool, lang: str) -> str:
    if t == 0:
        return _p(lang, "SYNC 때, 값이 바뀌었을 때만", "on SYNC, only when changed (acyclic)")
    if 1 <= t <= 240:
        if tx:
            return _p(lang, f"SYNC {t}번마다 보냄", f"sent every {t} SYNC")
        return _p(lang, "받은 값을 다음 SYNC 때 적용", "applied at the next SYNC")
    if t in (252, 253):
        return _p(lang, "RTR 요청이 오면 보냄", "sent on RTR request")
    if t == 254:
        return _p(lang, "이벤트 (제조사 정의, 보통 값이 바뀌거나 타이머마다)",
                  "event driven (manufacturer specific)")
    if t == 255:
        return _p(lang, "이벤트 (프로파일 정의)", "event driven (device profile)")
    return _p(lang, "예약된 값", "reserved")


def consumer_hb_text(raw: int, lang: str) -> str:
    node = (raw >> 16) & 0x7F
    ms = raw & 0xFFFF
    if not node or not ms:
        return _p(lang, "감시 안 함", "not monitored")
    return _p(lang, f"노드 {node}의 하트비트를 {ms} ms 안에 못 받으면 이상으로 판단",
              f"node {node} must send a heartbeat within {ms} ms")


_DRIVE_MODE_BITS = [(0, "PP"), (1, "VL"), (2, "PV"), (3, "PT"), (5, "HM"), (6, "IP"),
                    (7, "CSP"), (8, "CSV"), (9, "CST")]


def drive_modes_text(raw: int, lang: str) -> str:
    names = [name for bit, name in _DRIVE_MODE_BITS if raw & (1 << bit)]
    if not names:
        return _p(lang, "표준 운전 모드 없음", "no standard mode")
    return _p(lang, "지원: ", "supports: ") + ", ".join(names)


def device_type_text(raw: int, lang: str) -> str:
    """0x00020192 -> 'CiA 402 드라이브·모션 제어, 추가 정보 0x0002 (서보 드라이브)'."""
    profile = raw & 0xFFFF
    extra = (raw >> 16) & 0xFFFF
    if profile == 0:
        name = _p(lang, "프로파일이 적혀 있지 않음 (장치가 따르는 표준을 알려 주지 않음)",
                  "no profile given (the device does not say which standard it follows)")
    elif profile in DEVICE_PROFILES:
        name = _p(lang, *DEVICE_PROFILES[profile])
    else:
        name = _p(lang, f"CiA {profile} 프로파일", f"CiA {profile} profile")
    text = f"{name}"
    if profile and profile not in (402,) and profile in DEVICE_PROFILES:
        text = f"CiA {profile} {name}"
    if extra:
        detail = ""
        if profile == 402 and (extra & 0xFF) in CIA402_TYPES:
            detail = f" ({_p(lang, *CIA402_TYPES[extra & 0xFF])})"
        text += _p(lang, f", 추가 정보 0x{extra:04X}{detail}", f", additional info 0x{extra:04X}{detail}")
    return text


# --------------------------------------------------------------------------
# What each byte means (for people learning to read raw frames)
# --------------------------------------------------------------------------

_SDO_REQ_CS = {
    0: ("분할 쓰기 데이터 조각", "download segment"),
    1: ("쓰기 시작 (initiate download)", "initiate download (write)"),
    2: ("읽기 시작 (initiate upload)", "initiate upload (read)"),
    3: ("다음 조각 요청 (upload segment)", "upload segment request"),
    4: ("전송 중단 (abort)", "abort"),
    5: ("블록 읽기 (block upload)", "block upload"),
    6: ("블록 쓰기 (block download)", "block download"),
}
_SDO_RESP_CS = {
    0: ("분할 읽기 데이터 조각", "upload segment"),
    1: ("조각 수신 확인", "download segment acknowledge"),
    2: ("읽기 응답 (initiate upload response)", "initiate upload response (read reply)"),
    3: ("쓰기 성공 응답 (initiate download response)", "initiate download response (write OK)"),
    4: ("전송 중단 (abort)", "abort"),
    5: ("블록 쓰기", "block download"),
    6: ("블록 읽기", "block upload"),
}


def _hex(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


def _le(b: bytes) -> int:
    return int.from_bytes(b, "little")


def _le_text(b: bytes, lang: str) -> str:
    """'92 01 02 00' -> '거꾸로 읽으면 0x00020192'."""
    v = _le(b)
    width = len(b) * 2
    if len(b) == 1:
        return f"0x{v:02X} = {v}"
    return _p(lang, f"뒤에서부터 읽으면 0x{v:0{width}X} = {v} (CANopen은 작은 자리 바이트가 먼저 옵니다)",
              f"read back to front: 0x{v:0{width}X} = {v} (CANopen sends the least significant byte first)")


def _sdo_bytes(log, r, f, lang) -> list[tuple[str, str]]:
    d = bytes(f.data)
    if not d:
        return []
    req = r.kind == Kind.SDO_REQ
    b0 = d[0]
    cs = b0 >> 5
    table = _SDO_REQ_CS if req else _SDO_RESP_CS
    name = _p(lang, *table.get(cs, ("알 수 없는 명령", "unknown command")))
    who = _p(lang, "마스터 → 노드 요청", "master → node request") if req else _p(lang, "노드 → 마스터 응답", "node → master reply")
    parts = [_p(lang, f"명령 바이트. 2진수 {b0 >> 5:03b} {b0 & 0x1F:05b} → 앞 3비트 {cs} = {name} ({who})",
                f"command byte, binary {b0 >> 5:03b} {b0 & 0x1F:05b} → top 3 bits {cs} = {name} ({who})")]
    initiate = (req and cs == 1) or (not req and cs == 2)
    if initiate:
        e, sflag, n = (b0 >> 1) & 1, b0 & 1, (b0 >> 2) & 3
        if e:
            nbytes = 4 - n if sflag else 4
            parts.append(_p(lang, f"e=1: 값이 이 프레임 안에 바로 들어 있음(빠른 전송), s={sflag}, n={n}: 뒤 4바이트 중 {nbytes}바이트가 값",
                            f"e=1: the value is inside this frame (expedited), s={sflag}, n={n}: {nbytes} of the last 4 bytes hold it"))
        else:
            parts.append(_p(lang, "e=0: 값이 길어서 여러 프레임으로 나눠 보냄(분할 전송)" + (", s=1: 뒤 4바이트가 전체 크기" if sflag else ""),
                            "e=0: the value is long and follows in segments" + (", s=1: the last 4 bytes give the total size" if sflag else "")))
    elif (req and cs in (0, 3)) or (not req and cs in (0, 1)):
        t = (b0 >> 4) & 1
        parts.append(_p(lang, f"토글 비트 t={t} (조각마다 0과 1을 번갈아 씀)", f"toggle bit t={t} (alternates 0/1 per segment)"))
    rows = [(_hex(d[:1]), "; ".join(parts))]
    if (req and cs in (0, 3)) or (not req and cs in (0, 1)):
        carries = (req and cs == 0) or (not req and cs == 0)
        if len(d) > 1 and carries:
            unused = (b0 >> 1) & 7
            data = d[1:8 - unused]
            text = f" '{data.decode('latin-1')}'" if data and all(32 <= c < 127 for c in data) else ""
            last = _p(lang, ", c=1: 마지막 조각", ", c=1: last segment") if b0 & 1 else ""
            rows.append((_hex(data), _p(lang, f"조각 데이터{text}", f"segment data{text}") + last))
            if unused:
                rows.append((_hex(d[8 - unused:]), _p(lang, f"사용하지 않는 바이트 {unused}개 (n={unused})", f"{unused} unused byte(s) (n={unused})")))
        elif len(d) > 1:
            rows.append((_hex(d[1:]), _p(lang, "사용하지 않음 (0)", "unused (0)")))
        return rows
    if len(d) >= 3:
        idx = _le(d[1:3])
        rows.append((_hex(d[1:3]), _p(lang, f"오브젝트 인덱스: 두 바이트를 거꾸로 읽어 0x{idx:04X}", f"object index: the two bytes read back to front = 0x{idx:04X}")
                     + (f" ({obj_name(log, r.node, idx, d[3] if len(d) > 3 else 0, lang)})" if obj_name(log, r.node, idx, d[3] if len(d) > 3 else 0, lang) else "")))
    if len(d) >= 4:
        rows.append((_hex(d[3:4]), _p(lang, f"서브인덱스: {d[3]}", f"sub-index: {d[3]}")))
    if len(d) >= 8:
        payload = d[4:8]
        if cs == 4:
            rows.append((_hex(payload), _p(lang, "중단 코드. ", "abort code. ") + _le_text(payload, lang)
                         + f" → {sdo_abort_text(_le(payload), lang)[0]}"))
        elif initiate and (b0 >> 1) & 1:
            n = (b0 >> 2) & 3 if b0 & 1 else 0
            used = payload[:4 - n]
            v = _le(used)
            meaning = _p(lang, "값: ", "value: ") + _le_text(used, lang)
            if r.sdo_index_known:
                info = log.object_info(r.node, r.index, r.sub)
                vt = _value_text(log, r.node, r.index, r.sub, v, len(used), lang)
                plain = format_value(v, len(used), info.dtype if info else None)
                for prefix in (f"0x{v:0{len(used) * 2}X} → ", f"{v} → "):
                    if vt.startswith(prefix):
                        vt = vt[len(prefix):]
                if vt != plain and vt.split(" (")[0] != str(v):
                    meaning += f" → {vt}"
            rows.append((_hex(used), meaning))
            if n:
                rows.append((_hex(payload[4 - n:]), _p(lang, "사용하지 않는 바이트", "unused")))
        elif initiate and b0 & 1:
            rows.append((_hex(payload), _p(lang, "전체 데이터 크기: ", "total size: ") + _le_text(payload, lang) + _p(lang, " 바이트", " bytes")))
        else:
            rows.append((_hex(payload), _p(lang, "사용하지 않음 (0)", "unused (0)")))
    return rows


def byte_breakdown(log: "CanopenLog", row: int, lang: str = "ko") -> list[tuple[str, str]]:
    rows = _byte_breakdown(log, row, lang)
    # say once that bytes are little-endian, not on every line
    note = _p(lang, " (CANopen은 작은 자리 바이트가 먼저 옵니다)", " (CANopen sends the least significant byte first)")
    seen = False
    out = []
    for b, m in rows:
        if note in m:
            if seen:
                m = m.replace(note, "")
            seen = True
        out.append((b, m))
    return out


def _byte_breakdown(log: "CanopenLog", row: int, lang: str = "ko") -> list[tuple[str, str]]:
    r = log.trace.record(row)
    f = log.trace.frame(row)
    d = bytes(f.data)
    k = r.kind
    if f.rtr or not d:
        return []
    if k in (Kind.SDO_REQ, Kind.SDO_RESP):
        return _sdo_bytes(log, r, f, lang)
    if k == Kind.NMT and len(d) >= 2:
        return [(_hex(d[:1]), _p(lang, "NMT 명령: ", "NMT command: ") + nmt_cmd_text(d[0], lang)),
                (_hex(d[1:2]), _p(lang, "대상 노드 (0이면 모든 노드)", "target node (0 = all nodes)") + f": {d[1]}")]
    if k == Kind.HEARTBEAT:
        return [(_hex(d[:1]), _p(lang, "노드의 현재 NMT 상태: ", "the node's NMT state: ") + hb_state_text(d[0] & 0x7F, lang))]
    if k == Kind.SYNC:
        return [(_hex(d[:1]), _p(lang, "SYNC 카운터 (1부터 세는 번호)", "SYNC counter"))]
    if k == Kind.EMCY and len(d) >= 3:
        code = _le(d[0:2])
        rows = [(_hex(d[0:2]), _p(lang, "오류 코드. ", "error code. ") + _le_text(d[0:2], lang) + f" → {emcy_text(code, lang)}"),
                (_hex(d[2:3]), _p(lang, "에러 레지스터(0x1001): ", "error register (0x1001): ") + error_register_text(d[2], lang))]
        if len(d) > 3:
            rows.append((_hex(d[3:]), _p(lang, "제조사 전용 데이터 (장치 매뉴얼 참고)", "manufacturer specific data (see the device manual)")))
        return rows
    if k in (Kind.TPDO, Kind.RPDO) and r.map_ref is not None:
        rows = []
        off = 0
        for fld in log.trace.pdo_fields(row):
            name = obj_name(log, r.node, fld.index, fld.sub, lang) or f"0x{fld.index:04X}:{fld.sub:02X}"
            info = log.object_info(r.node, fld.index, fld.sub)
            value = format_value(fld.raw, fld.bits, info.dtype if info else None, bits=True)
            if off % 8 == 0 and fld.bits % 8 == 0:
                chunk = d[off // 8:(off + fld.bits) // 8]
                rows.append((_hex(chunk), f"{name} ({fld.bits} bit). " + (_le_text(chunk, lang) if len(chunk) > 1 else f"{value}")
                             + (f" → {value}" if len(chunk) > 1 and value.split(' (')[0] != str(_le(chunk)) else "")))
            else:
                rows.append((_p(lang, f"비트 {off}–{off + fld.bits - 1}", f"bits {off}–{off + fld.bits - 1}"), f"{name}: {value}"))
            off += fld.bits
        if off // 8 < len(d) and off % 8 == 0:
            rows.append((_hex(d[off // 8:]), _p(lang, "매핑되지 않은 바이트", "not mapped")))
        return rows
    return []
