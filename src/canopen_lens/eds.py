"""Minimal EDS / DCF reader.

Only what the viewer needs: object names, data types, the device type and the
default PDO mapping. Values that depend on $NODEID are resolved when a node-ID
is given.
"""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from .objects import ObjectInfo

_SUB_RE = re.compile(r"^([0-9a-f]{4})(?:sub([0-9a-f]{1,2}))?$", re.IGNORECASE)


def _parse_int(text: Optional[str], node_id: Optional[int] = None) -> Optional[int]:
    if text is None:
        return None
    s = text.strip()
    if not s:
        return None
    if "$NODEID" in s.upper():
        if node_id is None:
            return None
        s = re.sub(r"\$NODEID", str(node_id), s, flags=re.IGNORECASE)
        total = 0
        for part in s.split("+"):
            v = _parse_int(part)
            if v is None:
                return None
            total += v
        return total
    try:
        if s.lower().startswith("0x"):
            return int(s, 16)
        if s.startswith("0") and len(s) > 1 and s.isdigit():
            return int(s, 8)  # EDS allows octal with a leading zero
        return int(s, 10)
    except ValueError:
        return None


@dataclass
class EdsObject:
    index: int
    sub: Optional[int]
    name: str
    dtype: Optional[int] = None
    access: str = ""
    default: Optional[str] = None
    pdo_mappable: bool = False


@dataclass
class EdsFile:
    path: str
    objects: dict[tuple[int, Optional[int]], EdsObject] = field(default_factory=dict)
    vendor_name: str = ""
    product_name: str = ""
    node_id: Optional[int] = None  # only present in DCF files

    # -- loading -----------------------------------------------------------
    @classmethod
    def load(cls, path: Union[str, Path]) -> "EdsFile":
        raw = Path(path).read_bytes()
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        return cls.parse(text, str(path))

    @classmethod
    def parse(cls, text: str, path: str = "<memory>") -> "EdsFile":
        cp = configparser.RawConfigParser(strict=False, comment_prefixes=(";", "#"), inline_comment_prefixes=None)
        cp.optionxform = str.lower  # keys are case-insensitive in EDS
        cp.read_string(text)
        eds = cls(path=path)
        for section in cp.sections():
            sec = cp[section]
            low = section.lower()
            if low == "deviceinfo":
                eds.vendor_name = sec.get("vendorname", "").strip()
                eds.product_name = sec.get("productname", "").strip()
                continue
            if low == "devicecomissioning" or low == "devicecommissioning":
                eds.node_id = _parse_int(sec.get("nodeid"))
                continue
            m = _SUB_RE.match(section.strip())
            if not m:
                continue
            index = int(m.group(1), 16)
            sub = int(m.group(2), 16) if m.group(2) else None
            obj = EdsObject(
                index=index,
                sub=sub,
                name=sec.get("parametername", "").strip(),
                dtype=_parse_int(sec.get("datatype")),
                access=sec.get("accesstype", "").strip().lower(),
                default=sec.get("parametervalue", sec.get("defaultvalue")),
                pdo_mappable=sec.get("pdomapping", "0").strip() in ("1", "true"),
            )
            eds.objects[(index, sub)] = obj
        return eds

    # -- queries -------------------------------------------------------------
    def lookup(self, index: int, sub: int) -> Optional[ObjectInfo]:
        obj = self.objects.get((index, sub))
        top = self.objects.get((index, None))
        if obj is None and sub == 0:
            obj = top
        if obj is None:
            return None
        name = obj.name
        if top is not None and obj is not top and top.name and top.name not in name:
            name = f"{top.name}: {name}"
        return ObjectInfo(name, name, obj.dtype)

    def int_value(self, index: int, sub: Optional[int], node_id: Optional[int] = None) -> Optional[int]:
        obj = self.objects.get((index, sub))
        if obj is None and sub == 0:
            obj = self.objects.get((index, None))
        if obj is None:
            return None
        return _parse_int(obj.default, node_id if node_id is not None else self.node_id)

    @property
    def device_type(self) -> Optional[int]:
        return self.int_value(0x1000, 0)

    @property
    def is_cia402(self) -> bool:
        dt = self.device_type
        return dt is not None and (dt & 0xFFFF) == 402

    def pdo_mapping(self, tx: bool, num: int) -> Optional[list[tuple[int, int, int]]]:
        """Default mapping of TPDO/RPDO `num` (1..4) as (index, sub, bits) tuples."""
        base = (0x1A00 if tx else 0x1600) + num - 1
        count = self.int_value(base, 0)
        if count is None:
            return None
        out = []
        for sub in range(1, count + 1):
            v = self.int_value(base, sub)
            if v is None:
                return None
            out.append((v >> 16, (v >> 8) & 0xFF, v & 0xFF))
        return out

    @property
    def title(self) -> str:
        parts = [p for p in (self.vendor_name, self.product_name) if p]
        return " / ".join(parts) or Path(self.path).name
