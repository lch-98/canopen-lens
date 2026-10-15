"""Command line interface.

    canopen-lens                      open the GUI
    canopen-lens robot.log            open the GUI with a log
    canopen-lens report robot.log     print a text diagnosis
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from . import __version__
from ._core import Severity
from .log import open_log


def _eds_arg(text: str) -> tuple[int, str]:
    node, _, path = text.partition("=")
    if not path:
        raise argparse.ArgumentTypeError("use NODE=PATH, e.g. 1=drive.eds")
    return int(node, 0), path


def report(args) -> int:
    log = open_log(args.log, eds=dict(args.eds or []))
    lang = args.lang
    out = sys.stdout
    trace = log.trace
    counts = log.count_issues()
    if lang == "ko":
        out.write(f"{args.log}: 프레임 {len(log):,}개, {trace.duration:.3f}초, 형식 {trace.format}\n")
        out.write(f"오류 {counts[Severity.ERROR]} · 경고 {counts[Severity.WARNING]} · 정보 {counts[Severity.INFO]}\n\n")
    else:
        out.write(f"{args.log}: {len(log):,} frames, {trace.duration:.3f} s, format {trace.format}\n")
        out.write(f"errors {counts[Severity.ERROR]} · warnings {counts[Severity.WARNING]} · info {counts[Severity.INFO]}\n\n")
    marks = {Severity.ERROR: "[E]", Severity.WARNING: "[W]", Severity.INFO: "[i]"}
    for issue in log.issues:
        if int(issue.severity) < int(args.min_severity):
            continue
        title, text = log.issue_text(issue, lang)
        out.write(f"{marks[issue.severity]} {issue.t:10.6f}s  #{issue.row + 1:<7d} {title}\n")
        if args.verbose:
            out.write(f"    {text}\n")
    if args.frames:
        out.write("\n")
        for row in range(len(log)):
            f = trace.frame(row)
            out.write(f"{row + 1:7d} {f.t:12.6f}  0x{f.id:03X}  {log.summary(row, lang)}\n")
    return 1 if counts[Severity.ERROR] and args.fail_on_error else 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("report", "-h", "--help", "--version"):
        from .gui import main as gui_main

        return gui_main(["canopen-lens", *argv])

    p = argparse.ArgumentParser(prog="canopen-lens", description="Beginner-friendly CANopen log viewer")
    p.add_argument("--version", action="version", version=f"canopen-lens {__version__}")
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("report", help="print the diagnosis of a candump log")
    r.add_argument("log")
    r.add_argument("--eds", type=_eds_arg, action="append", metavar="NODE=PATH", help="attach an EDS to a node")
    r.add_argument("--lang", choices=["ko", "en"], default="en")
    r.add_argument("-v", "--verbose", action="store_true", help="also print what to check")
    r.add_argument("--frames", action="store_true", help="also print every decoded frame")
    r.add_argument("--min-severity", type=lambda s: Severity.__members__[s.upper()], default=Severity.INFO,
                   help="info, warning or error")
    r.add_argument("--fail-on-error", action="store_true", help="exit with status 1 when errors are found")
    args = p.parse_args(argv)
    if args.cmd == "report":
        return report(args)
    p.print_help()
    return 0
