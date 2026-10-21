"""canopen-lens: beginner-friendly CANopen log viewer.

Quick start::

    from canopen_lens import open_log
    log = open_log("candump.log")
    print(log.report(lang="en"))          # plain-language diagnosis

    for issue in log.issues:
        ex = log.explain(issue, lang="en")
        print(ex.title, ex.steps)
"""

from ._core import (
    AxisState,
    AxisWord,
    CwCommand,
    IssueType,
    Kind,
    MapOrigin,
    Options,
    PdoMapEntry,
    SdoType,
    Severity,
    Trace,
    decode_controlword,
    decode_statusword,
)
__version__ = "0.4.2"

from .eds import EdsFile  # noqa: E402
from .explain import Explanation, HealthSummary, IssueGroup, glossary  # noqa: E402
from .incidents import Device, Event, Incident, Overview  # noqa: E402
from .live import LiveDecoder  # noqa: E402
from .log import CanopenLog, open_log  # noqa: E402

__all__ = [
    "AxisState",
    "AxisWord",
    "CanopenLog",
    "CwCommand",
    "Device",
    "Event",
    "Incident",
    "Overview",
    "EdsFile",
    "Explanation",
    "HealthSummary",
    "IssueGroup",
    "LiveDecoder",
    "glossary",
    "IssueType",
    "Kind",
    "MapOrigin",
    "Options",
    "PdoMapEntry",
    "SdoType",
    "Severity",
    "Trace",
    "decode_controlword",
    "decode_statusword",
    "open_log",
]
