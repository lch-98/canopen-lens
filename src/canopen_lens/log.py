"""High-level API: open a log, attach EDS files, get explanations."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from . import describe
from ._core import Options, PdoMapEntry, Severity, Trace
from .eds import EdsFile
from .objects import ObjectInfo, builtin_object

PathLike = Union[str, Path]


class CanopenLog:
    """A candump log decoded as CANopen traffic.

    >>> log = CanopenLog.open("robot.log")
    >>> for issue in log.issues:
    ...     print(log.issue_text(issue)[0])
    """

    def __init__(self, trace: Trace, path: Optional[str] = None):
        self.trace = trace
        self.path = path
        self.eds: dict[int, EdsFile] = {}

    # -- construction --------------------------------------------------------
    @classmethod
    def open(cls, path: PathLike, options: Optional[Options] = None) -> "CanopenLog":
        data = Path(path).read_bytes()
        return cls(Trace.from_bytes(data, options or Options()), str(path))

    @classmethod
    def from_text(cls, text: str, options: Optional[Options] = None) -> "CanopenLog":
        return cls(Trace.from_text(text, options or Options()))

    # -- EDS -----------------------------------------------------------------
    def attach_eds(self, node: int, eds: Union[EdsFile, PathLike], reanalyze: bool = True) -> EdsFile:
        """Uses an EDS/DCF for naming objects and as the default PDO mapping of `node`."""
        if not isinstance(eds, EdsFile):
            eds = EdsFile.load(eds)
        self.eds[node] = eds
        self._apply_eds()
        if eds.device_type is not None:
            self.trace.set_drive(node, eds.is_cia402)
        if reanalyze:
            self.trace.analyze()
        return eds

    def detach_eds(self, node: int, reanalyze: bool = True) -> None:
        if self.eds.pop(node, None) is not None:
            self.trace.clear_drive_override(node)
            self._apply_eds()
            if reanalyze:
                self.trace.analyze()

    def _apply_eds(self) -> None:
        self.trace.clear_base_mappings()
        for node, eds in self.eds.items():
            for tx in (True, False):
                for num in range(1, 5):
                    entries = eds.pdo_mapping(tx, num)
                    if entries:
                        self.trace.set_base_mapping(node, tx, num, [PdoMapEntry(i, s, b) for i, s, b in entries])

    def set_drive(self, node: int, is_drive: Optional[bool]) -> None:
        """Force (True/False) or reset (None) CiA 402 handling for a node, then re-analyze."""
        if is_drive is None:
            self.trace.clear_drive_override(node)
        else:
            self.trace.set_drive(node, is_drive)
        self.trace.analyze()

    # -- lookups ---------------------------------------------------------------
    def object_info(self, node: int, index: int, sub: int) -> Optional[ObjectInfo]:
        eds = self.eds.get(node)
        if eds is not None:
            info = eds.lookup(index, sub)
            if info is not None:
                builtin = builtin_object(index, sub)
                if builtin is not None and not (0x2000 <= index <= 0x5FFF):
                    # keep the localized name and unit of well-known objects; the EDS type wins
                    dtype = info.dtype if info.dtype is not None else builtin.dtype
                    return ObjectInfo(info.name_en or builtin.name_en, builtin.name_ko, dtype, builtin.unit)
                return info
        return builtin_object(index, sub)

    # -- convenience -------------------------------------------------------------
    def __len__(self) -> int:
        return len(self.trace)

    @property
    def issues(self):
        return self.trace.issues

    @property
    def nodes(self):
        return self.trace.nodes

    def summary(self, row: int, lang: str = "ko") -> str:
        return describe.frame_summary(self, row, lang)

    def details(self, row: int, lang: str = "ko") -> list[tuple[str, str]]:
        return describe.frame_details(self, row, lang)

    def issue_text(self, issue, lang: str = "ko") -> tuple[str, str]:
        return describe.issue_text(self, issue, lang)

    def count_issues(self) -> dict[Severity, int]:
        out = {Severity.ERROR: 0, Severity.WARNING: 0, Severity.INFO: 0}
        for i in self.trace.issues:
            out[i.severity] += 1
        return out


def open_log(path: PathLike, eds: Optional[dict[int, PathLike]] = None, options: Optional[Options] = None) -> CanopenLog:
    """Opens a candump log and optionally attaches EDS files ({node_id: path})."""
    log = CanopenLog.open(path, options)
    if eds:
        for node, p in eds.items():
            log.attach_eds(node, p, reanalyze=False)
        log.trace.analyze()
    return log
