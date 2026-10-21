"""Turning a decoded log into tables (CSV, pandas) and JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Optional, Union

from . import __version__, describe
from ._core import Kind

if TYPE_CHECKING:  # pragma: no cover
    from .log import CanopenLog

FRAME_COLUMNS = ["row", "time_s", "node", "type", "cob_id", "dlc", "data", "meaning",
                 "statusword", "axis_state", "controlword", "command", "has_issue"]


def _kind_name(r) -> str:
    name = r.kind.name
    if r.kind in (Kind.TPDO, Kind.RPDO):
        name += str(r.pdo_num)
    return name


def iter_frames(log: "CanopenLog", lang: str = "ko", rows=None) -> Iterator[dict]:
    """One dict per frame. `rows` limits the output (e.g. log.trace.filter(...))."""
    tr = log.trace
    for row in (range(len(tr)) if rows is None else rows):
        row = int(row)
        f = tr.frame(row)
        r = tr.record(row)
        yield {
            "row": row + 1,
            "time_s": round(f.t, 6),
            "node": r.node or None,
            "type": _kind_name(r),
            "cob_id": f"0x{f.id:08X}" if f.ext else f"0x{f.id:03X}",
            "dlc": f.dlc,
            "data": "RTR" if f.rtr else f.data.hex(" ").upper(),
            "meaning": describe.frame_summary(log, row, lang),
            "statusword": f"0x{r.statusword:04X}" if r.has_statusword else None,
            "axis_state": r.axis_state.name if r.has_statusword else None,
            "controlword": f"0x{r.controlword:04X}" if r.has_controlword else None,
            "command": r.cw_command.name if r.has_controlword else None,
            "has_issue": r.has_issue,
        }


def to_csv(log: "CanopenLog", path: Union[str, Path], lang: str = "ko", rows=None) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=FRAME_COLUMNS)
        w.writeheader()
        for d in iter_frames(log, lang, rows):
            w.writerow(d)


def to_dataframe(log: "CanopenLog", lang: str = "ko", rows=None):
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover
        raise ImportError("to_dataframe() needs pandas: pip install pandas") from exc
    df = pd.DataFrame(list(iter_frames(log, lang, rows)), columns=FRAME_COLUMNS)
    df["node"] = df["node"].astype("Int64")   # keeps "no node" as <NA> instead of turning ints into floats
    return df


def issue_dict(log: "CanopenLog", issue, lang: str = "ko") -> dict:
    ex = log.explain(issue, lang)
    d = ex.as_dict()
    d.update({
        "type": issue.type.name.lower(),
        "time_s": round(issue.t, 6),
        "row": issue.row + 1,
        "node": issue.node or None,
        "axis": issue.axis + 1 if issue.node and log.trace.axis_count(issue.node) > 1 else None,
    })
    return d


def report_dict(log: "CanopenLog", lang: str = "ko") -> dict:
    h = log.health(lang)
    ov = log.overview(lang)
    tr = log.trace
    return {
        "summary": {"level": ov.level, "headline": ov.headline, "sentence": ov.sentence, "counts": ov.counts},
        "incidents": [i.as_dict() for i in ov.incidents],
        "devices": [{"node": d.node, "kind": d.kind, "status": d.status, "status_text": d.status_word} for d in ov.devices],
        "tool": f"canopen-lens {__version__}",
        "file": log.path,
        "frames": len(tr),
        "duration_s": round(tr.duration, 6),
        "format": tr.format,
        "verdict": h.level,
        "headline": h.headline,
        "overview": h.overview,
        "looks_like_canopen": h.protocol.looks_like_canopen if h.protocol else None,
        "protocol_note": h.protocol.text if h.protocol else "",
        "traffic_by_id": log.id_statistics(lang),
        "nodes": [{"node": n.node, "status": n.level, "headline": n.headline, "details": n.details} for n in h.nodes],
        "findings": [
            dict(issue_dict(log, g.first, lang), count=g.count,
                 first_time_s=round(g.t_first, 6), last_time_s=round(g.t_last, 6))
            for g in h.groups
        ],
        "all_findings": [issue_dict(log, i, lang) for i in tr.issues],
    }


def to_json(log: "CanopenLog", path: Optional[Union[str, Path]] = None, lang: str = "ko") -> str:
    text = json.dumps(report_dict(log, lang), ensure_ascii=False, indent=2)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text
