"""Built-in knowledge about common CiA 301 / CiA 402 objects.

Used to name objects and format values when no EDS file has been loaded.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

# CANopen data type codes (CiA 301, table 44)
DT_BOOL = 0x01
DT_INT8 = 0x02
DT_INT16 = 0x03
DT_INT32 = 0x04
DT_UINT8 = 0x05
DT_UINT16 = 0x06
DT_UINT32 = 0x07
DT_REAL32 = 0x08
DT_VISIBLE_STRING = 0x09
DT_OCTET_STRING = 0x0A
DT_DOMAIN = 0x0F
DT_INT24 = 0x10
DT_REAL64 = 0x11
DT_INT64 = 0x15
DT_UINT24 = 0x16
DT_UINT64 = 0x1B

SIGNED_TYPES = {DT_INT8: 8, DT_INT16: 16, DT_INT24: 24, DT_INT32: 32, DT_INT64: 64}
STRING_TYPES = {DT_VISIBLE_STRING, DT_OCTET_STRING, DT_DOMAIN}


@dataclass(frozen=True)
class ObjectInfo:
    name_en: str
    name_ko: str
    dtype: int = DT_UINT32
    unit: str = ""

    def name(self, lang: str) -> str:
        return self.name_ko if lang == "ko" else self.name_en


_FIXED: dict[tuple[int, Optional[int]], ObjectInfo] = {
    (0x1000, None): ObjectInfo("Device type", "장치 종류", DT_UINT32),
    (0x1001, None): ObjectInfo("Error register", "에러 레지스터", DT_UINT8),
    (0x1003, None): ObjectInfo("Pre-defined error field", "에러 이력", DT_UINT32),
    (0x1005, None): ObjectInfo("COB-ID SYNC", "SYNC COB-ID", DT_UINT32),
    (0x1006, None): ObjectInfo("Communication cycle period", "통신 주기", DT_UINT32, "us"),
    (0x1008, None): ObjectInfo("Device name", "장치 이름", DT_VISIBLE_STRING),
    (0x1009, None): ObjectInfo("Hardware version", "하드웨어 버전", DT_VISIBLE_STRING),
    (0x100A, None): ObjectInfo("Software version", "소프트웨어 버전", DT_VISIBLE_STRING),
    (0x100C, None): ObjectInfo("Guard time", "가드 시간", DT_UINT16, "ms"),
    (0x100D, None): ObjectInfo("Life time factor", "라이프 타임 계수", DT_UINT8),
    (0x1010, None): ObjectInfo("Store parameters", "파라미터 저장", DT_UINT32),
    (0x1011, None): ObjectInfo("Restore default parameters", "기본값 복원", DT_UINT32),
    (0x1014, None): ObjectInfo("COB-ID EMCY", "EMCY COB-ID", DT_UINT32),
    (0x1016, None): ObjectInfo("Consumer heartbeat time", "하트비트 감시 시간", DT_UINT32),
    (0x1017, None): ObjectInfo("Producer heartbeat time", "하트비트 송신 주기", DT_UINT16, "ms"),
    (0x1018, 0): ObjectInfo("Identity: number of entries", "장치 식별 정보: 항목 수", DT_UINT8),
    (0x1018, 1): ObjectInfo("Vendor-ID", "제조사 ID", DT_UINT32),
    (0x1018, 2): ObjectInfo("Product code", "제품 코드", DT_UINT32),
    (0x1018, 3): ObjectInfo("Revision number", "리비전 번호", DT_UINT32),
    (0x1018, 4): ObjectInfo("Serial number", "시리얼 번호", DT_UINT32),
    (0x1029, None): ObjectInfo("Error behavior", "에러 시 동작", DT_UINT8),
    (0x603F, None): ObjectInfo("Error code", "드라이브 에러 코드", DT_UINT16),
    (0x6040, None): ObjectInfo("Controlword", "컨트롤워드", DT_UINT16),
    (0x6041, None): ObjectInfo("Statusword", "스테이터스워드", DT_UINT16),
    (0x605A, None): ObjectInfo("Quick stop option code", "급정지 동작 옵션", DT_INT16),
    (0x605B, None): ObjectInfo("Shutdown option code", "셧다운 동작 옵션", DT_INT16),
    (0x605E, None): ObjectInfo("Fault reaction option code", "폴트 반응 옵션", DT_INT16),
    (0x6060, None): ObjectInfo("Modes of operation", "운전 모드 설정", DT_INT8),
    (0x6061, None): ObjectInfo("Modes of operation display", "현재 운전 모드", DT_INT8),
    (0x6062, None): ObjectInfo("Position demand value", "위치 지령값", DT_INT32, "inc"),
    (0x6063, None): ObjectInfo("Position actual internal value", "내부 실제 위치", DT_INT32, "inc"),
    (0x6064, None): ObjectInfo("Position actual value", "실제 위치", DT_INT32, "inc"),
    (0x6065, None): ObjectInfo("Following error window", "추종 오차 허용 범위", DT_UINT32, "inc"),
    (0x6069, None): ObjectInfo("Velocity sensor actual value", "속도 센서 값", DT_INT32),
    (0x606B, None): ObjectInfo("Velocity demand value", "속도 지령값", DT_INT32),
    (0x606C, None): ObjectInfo("Velocity actual value", "실제 속도", DT_INT32),
    (0x6071, None): ObjectInfo("Target torque", "목표 토크", DT_INT16, "‰"),
    (0x6072, None): ObjectInfo("Max torque", "최대 토크", DT_UINT16, "‰"),
    (0x6073, None): ObjectInfo("Max current", "최대 전류", DT_UINT16, "‰"),
    (0x6074, None): ObjectInfo("Torque demand", "토크 지령값", DT_INT16, "‰"),
    (0x6077, None): ObjectInfo("Torque actual value", "실제 토크", DT_INT16, "‰"),
    (0x6078, None): ObjectInfo("Current actual value", "실제 전류", DT_INT16, "‰"),
    (0x6079, None): ObjectInfo("DC link circuit voltage", "DC 링크 전압", DT_UINT32, "mV"),
    (0x607A, None): ObjectInfo("Target position", "목표 위치", DT_INT32, "inc"),
    (0x607C, None): ObjectInfo("Home offset", "원점 오프셋", DT_INT32),
    (0x607D, None): ObjectInfo("Software position limit", "소프트웨어 위치 제한", DT_INT32),
    (0x6081, None): ObjectInfo("Profile velocity", "프로파일 속도", DT_UINT32),
    (0x6083, None): ObjectInfo("Profile acceleration", "프로파일 가속도", DT_UINT32),
    (0x6084, None): ObjectInfo("Profile deceleration", "프로파일 감속도", DT_UINT32),
    (0x6085, None): ObjectInfo("Quick stop deceleration", "급정지 감속도", DT_UINT32),
    (0x6098, None): ObjectInfo("Homing method", "원점 복귀 방식", DT_INT8),
    (0x6099, None): ObjectInfo("Homing speeds", "원점 복귀 속도", DT_UINT32),
    (0x609A, None): ObjectInfo("Homing acceleration", "원점 복귀 가속도", DT_UINT32),
    (0x60B0, None): ObjectInfo("Position offset", "위치 오프셋", DT_INT32),
    (0x60B1, None): ObjectInfo("Velocity offset", "속도 오프셋", DT_INT32),
    (0x60B2, None): ObjectInfo("Torque offset", "토크 오프셋", DT_INT16),
    (0x60C2, None): ObjectInfo("Interpolation time period", "보간 주기", DT_UINT8),
    (0x60F4, None): ObjectInfo("Following error actual value", "실제 추종 오차", DT_INT32, "inc"),
    (0x60FD, None): ObjectInfo("Digital inputs", "디지털 입력", DT_UINT32),
    (0x60FE, None): ObjectInfo("Digital outputs", "디지털 출력", DT_UINT32),
    (0x60FF, None): ObjectInfo("Target velocity", "목표 속도", DT_INT32),
    (0x6502, None): ObjectInfo("Supported drive modes", "지원 운전 모드", DT_UINT32),
}

# (Korean, English), like the other name tables
MODES_OF_OPERATION = {
    -1: ("제조사 전용", "Manufacturer specific"),
    0: ("모드 없음", "No mode"),
    1: ("프로파일 위치 (PP)", "Profile position (PP)"),
    2: ("속도 (VL)", "Velocity (VL)"),
    3: ("프로파일 속도 (PV)", "Profile velocity (PV)"),
    4: ("프로파일 토크 (PT)", "Profile torque (PT)"),
    6: ("원점 복귀 (HM)", "Homing (HM)"),
    7: ("보간 위치 (IP)", "Interpolated position (IP)"),
    8: ("주기 동기 위치 (CSP)", "Cyclic sync position (CSP)"),
    9: ("주기 동기 속도 (CSV)", "Cyclic sync velocity (CSV)"),
    10: ("주기 동기 토크 (CST)", "Cyclic sync torque (CST)"),
}


AXIS_OFFSET = 0x800


def axis_of(index: int) -> int:
    """0-based CiA 402 axis of a profile object (0x6841 -> 1), -1 outside 0x6000-0x9FFF."""
    if 0x6000 <= index <= 0x9FFF:
        return (index - 0x6000) // AXIS_OFFSET
    return -1


def axis_base(index: int) -> int:
    """The axis-1 equivalent of a profile object (0x6841 -> 0x6041)."""
    a = axis_of(index)
    return index - a * AXIS_OFFSET if a > 0 else index


_PDO_COMM_SUBS = {
    0: ("number of entries", "항목 수", DT_UINT8, ""),
    1: ("COB-ID", "COB-ID (번호표)", DT_UINT32, ""),
    2: ("transmission type", "전송 방식", DT_UINT8, ""),
    3: ("inhibit time", "최소 전송 간격", DT_UINT16, "x100us"),
    5: ("event timer", "이벤트 타이머", DT_UINT16, "ms"),
    6: ("SYNC start value", "SYNC 시작값", DT_UINT8, ""),
}


def _pdo_comm(pdo: str, sub: int) -> ObjectInfo:
    if sub in _PDO_COMM_SUBS:
        en, ko, dtype, unit = _PDO_COMM_SUBS[sub]
        return ObjectInfo(f"{pdo} {en}", f"{pdo} {ko}", dtype, unit)
    return ObjectInfo(f"{pdo} communication parameter", f"{pdo} 통신 설정")


def builtin_object(index: int, sub: int) -> Optional[ObjectInfo]:
    """Look up a well-known object, including the PDO parameter ranges."""
    a = axis_of(index)
    if a > 0:
        base = builtin_object(axis_base(index), sub)
        if base is None:
            return None
        return ObjectInfo(f"Axis {a + 1} {base.name_en}", f"축 {a + 1} {base.name_ko}", base.dtype, base.unit)
    info = _FIXED.get((index, sub)) or _FIXED.get((index, None))
    if info:
        return info
    if 0x1400 <= index <= 0x15FF:
        n = index - 0x1400 + 1
        return _pdo_comm(f"RPDO{n}", sub)
    if 0x1600 <= index <= 0x17FF:
        n = index - 0x1600 + 1
        if sub == 0:
            return ObjectInfo(f"RPDO{n} mapping: number of entries", f"RPDO{n} 매핑 개수", DT_UINT8)
        return ObjectInfo(f"RPDO{n} mapping entry {sub}", f"RPDO{n} 매핑 {sub}번", DT_UINT32)
    if 0x1800 <= index <= 0x19FF:
        n = index - 0x1800 + 1
        return _pdo_comm(f"TPDO{n}", sub)
    if 0x1A00 <= index <= 0x1BFF:
        n = index - 0x1A00 + 1
        if sub == 0:
            return ObjectInfo(f"TPDO{n} mapping: number of entries", f"TPDO{n} 매핑 개수", DT_UINT8)
        return ObjectInfo(f"TPDO{n} mapping entry {sub}", f"TPDO{n} 매핑 {sub}번", DT_UINT32)
    if 0x2000 <= index <= 0x5FFF:
        return ObjectInfo("Manufacturer specific object", "제조사 전용 오브젝트")
    return None


def to_signed(raw: int, bits: int) -> int:
    if bits <= 0:
        return raw
    raw &= (1 << bits) - 1
    if raw & (1 << (bits - 1)):
        return raw - (1 << bits)
    return raw


def format_value(raw: int, nbytes_or_bits: int, dtype: Optional[int], *, bits: bool = False) -> str:
    """Formats a raw little-endian value according to a CANopen data type."""
    nbits = nbytes_or_bits if bits else nbytes_or_bits * 8
    if dtype in SIGNED_TYPES:
        return str(to_signed(raw, SIGNED_TYPES[dtype] if SIGNED_TYPES[dtype] <= nbits else nbits))
    if dtype == DT_REAL32 and nbits == 32:
        return f"{struct.unpack('<f', raw.to_bytes(4, 'little'))[0]:.6g}"
    if dtype == DT_BOOL:
        return "TRUE" if raw else "FALSE"
    if dtype == DT_VISIBLE_STRING:
        data = raw.to_bytes(max(1, nbits // 8), "little")
        return repr(data.rstrip(b"\x00").decode("latin-1"))
    width = max(1, (nbits + 3) // 4)
    return f"{raw} (0x{raw:0{width}X})"


def mapping_entry_text(value: int) -> str:
    """0x60410010 -> '0x6041:00, 16 bit'"""
    return f"0x{value >> 16:04X}:{(value >> 8) & 0xFF:02X}, {value & 0xFF} bit"
