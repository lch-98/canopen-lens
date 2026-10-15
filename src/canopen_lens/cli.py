"""Command line interface.

    canopen-lens                          open the GUI
    canopen-lens robot.log                open the GUI with a log
    canopen-lens report robot.log         print an easy-to-read diagnosis
    canopen-lens report robot.log --format json -o result.json
    canopen-lens live --channel can0      watch a live bus (needs python-can)
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


def _write(text: str, output: Optional[str]) -> None:
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        # Windows consoles may not be UTF-8; never crash on a character
        enc = sys.stdout.encoding or "utf-8"
        sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace"))
        if not text.endswith("\n"):
            sys.stdout.write("\n")


def report(args) -> int:
    log = open_log(args.log, eds=dict(args.eds or []))
    lang = args.lang
    fmt = args.format
    if fmt == "json":
        _write(log.to_json(lang=lang), args.output)
    elif fmt == "csv":
        if not args.output:
            raise SystemExit("--format csv needs -o FILE")
        log.to_csv(args.output, lang)
    else:
        if args.brief:
            from .describe import severity_text

            lines = []
            for i in log.issues:
                if int(i.severity) < int(args.min_severity):
                    continue
                lines.append(f"[{severity_text(i.severity, lang)}] {i.t:10.6f}s  #{i.row + 1:<7d} {log.explain(i, lang).title}")
            text = "\n".join(lines)
        else:
            text = log.report(lang)
        if args.frames:
            rows = [f"{d['row']:7d} {d['time_s']:12.6f}  {d['cob_id']}  {d['meaning']}" for d in log.frames(lang)]
            text += "\n\n" + "\n".join(rows)
        _write(text, args.output)
    counts = log.count_issues()
    return 1 if counts[Severity.ERROR] and args.fail_on_error else 0


def live(args) -> int:
    try:
        import can
    except ImportError:
        raise SystemExit('Live mode needs python-can:  pip install "canopen-lens[live]"')
    from .live import LiveDecoder

    dec = LiveDecoder(eds=dict(args.eds or []))
    lang = args.lang
    kwargs = {"interface": args.interface, "channel": args.channel}
    if args.bitrate:
        kwargs["bitrate"] = args.bitrate
    print(("버스를 듣는 중입니다… (Ctrl+C로 종료)" if lang == "ko" else "Listening… (Ctrl+C to stop)"), flush=True)

    def on_frame(msg, text):
        if args.frames:
            print(f"0x{msg.arbitration_id:03X}  {text}", flush=True)

    def on_issue(issue, ex):
        from .describe import severity_text

        print(f"[{severity_text(issue.severity, lang)}] {ex.title}", flush=True)
        if args.verbose:
            print("    " + ex.as_text(lang).replace("\n", "\n    "), flush=True)

    with can.Bus(**kwargs) as bus:
        dec.run(bus, on_issue=on_issue, on_frame=on_frame, lang=lang)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("report", "live", "-h", "--help", "--version"):
        from .gui import main as gui_main

        return gui_main(["canopen-lens", *argv])

    p = argparse.ArgumentParser(prog="canopen-lens", description="Beginner-friendly CANopen log analyzer")
    p.add_argument("--version", action="version", version=f"canopen-lens {__version__}")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("report", help="explain what happened in a candump log")
    r.add_argument("log")
    r.add_argument("--eds", type=_eds_arg, action="append", metavar="NODE=PATH", help="attach an EDS to a node")
    r.add_argument("--lang", choices=["ko", "en"], default="en")
    r.add_argument("--format", choices=["text", "json", "csv"], default="text",
                   help="text: readable report, json: findings for other tools, csv: every decoded frame")
    r.add_argument("-o", "--output", help="write to this file instead of the screen")
    r.add_argument("--brief", action="store_true", help="one line per finding instead of the full report")
    r.add_argument("--frames", action="store_true", help="also list every decoded frame (text format)")
    r.add_argument("--min-severity", type=lambda s: Severity.__members__[s.upper()], default=Severity.INFO,
                   help="with --brief: info, warning or error")
    r.add_argument("--fail-on-error", action="store_true", help="exit with status 1 when errors are found")

    lv = sub.add_parser("live", help="watch a live CAN bus (needs python-can)")
    lv.add_argument("--interface", default="socketcan", help="python-can interface, e.g. socketcan, pcan, slcan")
    lv.add_argument("--channel", default="can0", help="e.g. can0, PCAN_USBBUS1, COM3")
    lv.add_argument("--bitrate", type=int, help="e.g. 500000 (needed by some interfaces)")
    lv.add_argument("--eds", type=_eds_arg, action="append", metavar="NODE=PATH")
    lv.add_argument("--lang", choices=["ko", "en"], default="en")
    lv.add_argument("--frames", action="store_true", help="print every decoded frame")
    lv.add_argument("-v", "--verbose", action="store_true", help="print what to check for each finding")

    args = p.parse_args(argv)
    if args.cmd == "report":
        return report(args)
    if args.cmd == "live":
        return live(args)
    p.print_help()
    return 0
