"""High-level API: open a log, attach EDS files, get explanations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from . import describe
from ._core import Options, PdoMapEntry, Severity, Trace
from .eds import EdsFile
from .objects import ObjectInfo, builtin_object

if TYPE_CHECKING:  # pragma: no cover
    from .explain import Explanation, HealthSummary, IssueGroup, ProtocolCheck

PathLike = Union[str, Path]


class ObjectNames:
    """Object names/types from attached EDS files, falling back to built-in knowledge."""

    eds: dict

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

    def explain(self, issue, lang: str = "ko") -> "Explanation":
        """Structured plain-language explanation: what happened, why it matters, what to check."""
        from .explain import explain_issue

        return explain_issue(self, issue, lang)

    def issue_text(self, issue, lang: str = "ko") -> tuple[str, str]:
        """(title, explanation) of a finding as plain strings."""
        return describe.issue_text(self, issue, lang)


class CanopenLog(ObjectNames):
    """A candump log decoded as CANopen traffic.

    >>> log = CanopenLog.open("robot.log")
    >>> print(log.report())                    # plain-language diagnosis
    >>> for issue in log.issues:
    ...     print(log.explain(issue).title)
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

    def count_issues(self) -> dict[Severity, int]:
        out = {Severity.ERROR: 0, Severity.WARNING: 0, Severity.INFO: 0}
        for i in self.trace.issues:
            out[i.severity] += 1
        return out

    # -- plain-language results ----------------------------------------------------
    def health(self, lang: str = "ko") -> "HealthSummary":
        """Overall verdict, one status line per node, and grouped findings."""
        from .explain import health_summary

        return health_summary(self, lang)

    def overview(self, lang: str = "ko") -> "Overview":
        """The verdict and the problems as incidents (one story per problem), most urgent first."""
        from .incidents import build_overview

        return build_overview(self, lang)

    def incidents(self, lang: str = "ko") -> "list[Incident]":
        """Findings grouped into incidents: a fault, its cause and its recovery belong together."""
        from .incidents import build_incidents

        return build_incidents(self, lang)

    def grouped_issues(self) -> "list[IssueGroup]":
        """Findings with identical repeats collapsed (most severe first)."""
        from .explain import group_issues

        return group_issues(self.trace.issues)

    def protocol_check(self, lang: str = "ko") -> "ProtocolCheck":
        """Whether the log looks like CANopen at all (and why not)."""
        from .explain import protocol_check

        return protocol_check(self, lang)

    def id_statistics(self, lang: str = "ko") -> list:
        """Count, period and largest gap per CAN identifier. Useful for any CAN log."""
        from .explain import id_statistics

        return id_statistics(self, lang)

    def byte_breakdown(self, row: int, lang: str = "ko") -> list[tuple[str, str]]:
        """What each byte of a frame means, e.g. [("43", "command: read reply, 4 data bytes"), ...]."""
        return describe.byte_breakdown(self, row, lang)

    def report(self, lang: str = "ko") -> str:
        """The whole diagnosis as readable text."""
        from .explain import summary_text

        return summary_text(self, lang)

    # -- export ----------------------------------------------------------------------
    def frames(self, lang: str = "ko", rows=None):
        """Yields one dict per frame: time, node, type, meaning, raw data, ..."""
        from .export import iter_frames

        return iter_frames(self, lang, rows)

    def to_dataframe(self, lang: str = "ko", rows=None):
        """All (or the given) frames as a pandas DataFrame. Needs `pip install pandas`."""
        from .export import to_dataframe

        return to_dataframe(self, lang, rows)

    def to_csv(self, path: PathLike, lang: str = "ko", rows=None) -> None:
        """Writes decoded frames to CSV (UTF-8 with BOM, so Excel shows Korean correctly)."""
        from .export import to_csv

        to_csv(self, path, lang, rows)

    def to_dict(self, lang: str = "ko") -> dict:
        """Summary, nodes and findings as plain Python data (JSON-ready)."""
        from .export import report_dict

        return report_dict(self, lang)

    def to_json(self, path: Optional[PathLike] = None, lang: str = "ko") -> str:
        """Diagnosis as JSON; also written to `path` when given."""
        from .export import to_json

        return to_json(self, path, lang)


def open_log(path: PathLike, eds: Optional[dict[int, PathLike]] = None, options: Optional[Options] = None) -> CanopenLog:
    """Opens a candump log and optionally attaches EDS files ({node_id: path})."""
    log = CanopenLog.open(path, options)
    if eds:
        for node, p in eds.items():
            log.attach_eds(node, p, reanalyze=False)
        log.trace.analyze()
    return log
