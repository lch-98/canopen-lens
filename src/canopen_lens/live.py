"""Decoding frames as they arrive from a live CAN bus.

Works with any frame source. With python-can::

    import can
    from canopen_lens import LiveDecoder

    dec = LiveDecoder(eds={1: "drive.eds"})
    with can.Bus(interface="socketcan", channel="can0") as bus:
        for msg in bus:
            for issue in dec.feed_message(msg):
                print(dec.explain(issue, "en").title)

Only the newest frame is kept, so memory use stays flat however long it runs.
"""

from __future__ import annotations

import time
from typing import Callable, Iterable, Optional, Union

from . import describe
from ._core import LiveDecoder as _CoreLive
from ._core import Options, PdoMapEntry
from .eds import EdsFile
from .log import ObjectNames, PathLike


class _CurrentFrameView:
    """Gives describe.* the same interface as a Trace, for the newest frame only."""

    def __init__(self, core: _CoreLive):
        self._c = core

    def record(self, row):
        return self._c.last_record()

    def frame(self, row):
        return self._c.last_frame()

    def axis_words(self, row):
        return self._c.last_words()

    def pdo_fields(self, row):
        return self._c.last_pdo_fields()

    def axis_count(self, node):
        return self._c.axis_count(node)

    def mapping(self, ref):
        return self._c.mapping(ref)


class FrameSnapshot:
    """A decoded frame kept for later display. Cheap to store; text is made on demand."""

    __slots__ = ("frame", "record", "words", "fields", "_names")

    def __init__(self, frame, record, words, fields, names: "LiveDecoder"):
        self.frame = frame
        self.record = record
        self.words = words
        self.fields = fields
        self._names = names

    def _view(self):
        return _SnapshotLog(self)

    def summary(self, lang: str = "ko") -> str:
        return describe.frame_summary(self._view(), 0, lang)

    def details(self, lang: str = "ko") -> list[tuple[str, str]]:
        return describe.frame_details(self._view(), 0, lang)

    def byte_breakdown(self, lang: str = "ko") -> list[tuple[str, str]]:
        return describe.byte_breakdown(self._view(), 0, lang)


class _SnapshotTrace:
    def __init__(self, snap: FrameSnapshot):
        self._s = snap

    def record(self, row):
        return self._s.record

    def frame(self, row):
        return self._s.frame

    def axis_words(self, row):
        return self._s.words

    def pdo_fields(self, row):
        return self._s.fields

    def axis_count(self, node):
        return self._s._names.core.axis_count(node)

    def mapping(self, ref):
        return self._s._names.core.mapping(ref)


class _SnapshotLog:
    def __init__(self, snap: FrameSnapshot):
        self.trace = _SnapshotTrace(snap)
        self._names = snap._names
        self.eds = snap._names.eds

    def object_info(self, node, index, sub):
        return self._names.object_info(node, index, sub)


class LiveDecoder(ObjectNames):
    def __init__(self, eds: Optional[dict] = None, options: Optional[Options] = None):
        self._clock_offset: Optional[float] = None
        self.core = _CoreLive(options or Options())
        self.trace = _CurrentFrameView(self.core)  # used by the shared explanation code
        self.eds: dict[int, EdsFile] = {}
        for node, path in (eds or {}).items():
            self.attach_eds(node, path)

    # -- configuration (call before feeding; changing it restarts the analysis) ----
    def attach_eds(self, node: int, eds: Union[EdsFile, PathLike]) -> EdsFile:
        if not isinstance(eds, EdsFile):
            eds = EdsFile.load(eds)
        self.eds[node] = eds
        for tx in (True, False):
            for num in range(1, 5):
                entries = eds.pdo_mapping(tx, num)
                if entries:
                    self.core.set_base_mapping(node, tx, num, [PdoMapEntry(i, s, b) for i, s, b in entries])
        if eds.device_type is not None:
            self.core.set_drive(node, eds.is_cia402)
        return eds

    def set_drive(self, node: int, is_drive: bool) -> None:
        self.core.set_drive(node, is_drive)

    def reset(self) -> None:
        self.core.reset()
        self._clock_offset = None

    # -- feeding -----------------------------------------------------------------------
    def feed(self, t: float, can_id: int, data: bytes = b"", *, is_extended: bool = False,
             is_remote: bool = False, is_error: bool = False, is_fd: bool = False) -> list:
        """Decodes one frame. Returns the findings it produced (usually an empty list)."""
        start = self.core.issue_count
        n = self.core.feed(t, can_id, bytes(data), is_extended, is_remote, is_error, is_fd)
        return self.core.issues_from(start) if n else []

    def to_wall_clock(self, timestamp: float) -> float:
        """Some interfaces stamp frames with time since boot instead of the wall clock.
        Frames are shifted onto time.time() so that tick() compares like with like."""
        if self._clock_offset is None:
            self._clock_offset = time.time() - timestamp
        return timestamp + self._clock_offset

    def feed_message(self, msg) -> list:
        """Same as feed() for a python-can `can.Message`."""
        return self.feed(self.to_wall_clock(msg.timestamp), msg.arbitration_id, bytes(msg.data),
                         is_extended=msg.is_extended_id, is_remote=msg.is_remote_frame,
                         is_error=msg.is_error_frame, is_fd=getattr(msg, "is_fd", False))

    def tick(self, t: Optional[float] = None) -> list:
        """Time-based checks while the bus is quiet (lost heartbeats, unanswered SDO).
        `t` defaults to time.time(), which matches python-can timestamps."""
        start = self.core.issue_count
        n = self.core.tick(time.time() if t is None else t)
        return self.core.issues_from(start) if n else []

    def run(self, bus, on_issue: Optional[Callable] = None, on_frame: Optional[Callable] = None,
            lang: str = "ko", timeout: float = 0.2, stop: Optional[Callable[[], bool]] = None) -> None:
        """Reads a python-can bus until `stop()` returns True (or Ctrl+C).
        `on_issue(issue, explanation)` defaults to printing the finding."""
        if on_issue is None:
            def on_issue(issue, ex):
                print(f"[{describe.severity_text(issue.severity, lang)}] {ex.title}")
        try:
            while not (stop and stop()):
                msg = bus.recv(timeout)
                found = self.feed_message(msg) if msg is not None else self.tick()
                if msg is not None and on_frame:
                    on_frame(msg, self.last_summary(lang))
                for issue in found:
                    on_issue(issue, self.explain(issue, lang))
        except KeyboardInterrupt:
            pass

    def feed_lines(self, lines: Iterable[str]) -> list:
        """Feeds candump text lines (e.g. `candump -L can0 | python script.py`)."""
        from ._core import Trace

        found = []
        for line in lines:
            tr = Trace.from_text(line)
            if len(tr) == 1:
                f = tr.frame(0)
                found += self.feed(tr.t0 if tr.has_timestamps else time.time(), f.id, f.data,
                                   is_extended=f.ext, is_remote=f.rtr, is_error=f.error, is_fd=f.fd)
        return found

    def snapshot(self) -> FrameSnapshot:
        """The newest frame with its decoding, to keep for display (see FrameSnapshot)."""
        c = self.core
        return FrameSnapshot(c.last_frame(), c.last_record(), c.last_words(), c.last_pdo_fields(), self)

    # -- results -----------------------------------------------------------------------
    def last_summary(self, lang: str = "ko") -> str:
        """Plain-language meaning of the newest frame."""
        return describe.frame_summary(self, 0, lang)

    def last_details(self, lang: str = "ko") -> list[tuple[str, str]]:
        return describe.frame_details(self, 0, lang)

    @property
    def issues(self):
        return self.core.issues

    @property
    def nodes(self):
        return self.core.nodes

    @property
    def frame_count(self) -> int:
        return self.core.frame_count
