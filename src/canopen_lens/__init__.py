"""canopen-lens: beginner-friendly CANopen log viewer.

Quick start::

    from canopen_lens import open_log
    log = open_log("candump.log")
    for issue in log.issues:
        title, detail = log.issue_text(issue, lang="en")
        print(title)
"""

from ._core import (
    AxisState,
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
from .eds import EdsFile
from .log import CanopenLog, open_log

__version__ = "0.1.0"

__all__ = [
    "AxisState",
    "CanopenLog",
    "CwCommand",
    "EdsFile",
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
