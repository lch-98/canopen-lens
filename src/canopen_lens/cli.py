"""Command line interface.

    canopen-lens robot.log                 what happened, in about ten lines
    canopen-lens robot.log -d 1            problem 1 in detail (-d all: every problem)
    canopen-lens robot.log -s result.csv   save (.txt report, .csv messages, .json data)
    canopen-lens examples                  copy the example logs into this folder
    canopen-lens live can0                 watch a bus as it runs (needs python-can)
    canopen-lens                           open the window (GUI)

Help, messages and results follow the computer's language (Korean or English);
--lang changes that. `canopen-lens report …` from earlier versions still works.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Optional

from . import __version__
from ._core import Severity

# ----------------------------------------------------------------------------------
# language, colour and text width


def default_lang() -> str:
    """'ko' when the computer is set to Korean, otherwise 'en'. CANOPEN_LENS_LANG overrides."""
    forced = os.environ.get("CANOPEN_LENS_LANG", "").lower()
    if forced in ("ko", "en"):
        return forced
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        val = os.environ.get(var, "")
        if val:
            return "ko" if val.lower().startswith("ko") else "en"
    if sys.platform.startswith("win"):
        try:
            import ctypes

            if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x12:   # LANG_KOREAN
                return "ko"
        except Exception:  # pragma: no cover
            pass
    try:
        import locale

        name = (locale.getlocale()[0] or "").lower()
        if name.startswith("ko") or "korean" in name:
            return "ko"
    except Exception:  # pragma: no cover
        pass
    return "en"


class Style:
    def __init__(self, on: bool):
        self.on = on

    def _c(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.on else text

    def red(self, t): return self._c("1;31", t)          # noqa: E704
    def teal(self, t): return self._c("36", t)           # noqa: E704
    def amber(self, t): return self._c("33", t)          # noqa: E704
    def green(self, t): return self._c("32", t)          # noqa: E704
    def dim(self, t): return self._c("2", t)             # noqa: E704
    def bold(self, t): return self._c("1", t)            # noqa: E704


def _color_wanted(no_color: bool) -> bool:
    if no_color or os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if sys.platform.startswith("win"):
        try:  # switch on ANSI colours in the classic Windows console
            import ctypes

            k32 = ctypes.windll.kernel32
            h = k32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if k32.GetConsoleMode(h, ctypes.byref(mode)):
                k32.SetConsoleMode(h, mode.value | 0x0004)
        except Exception:  # pragma: no cover
            return False
    return True


def width(text: str) -> int:
    """Columns a string takes in a terminal (Korean letters take two)."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def pad(text: str, cols: int) -> str:
    return text + " " * max(cols - width(text), 0)


def _p(lang: str, ko: str, en: str) -> str:
    return ko if lang == "ko" else en


def _secs(lang: str, t: float, digits: int = 2) -> str:
    return f"{t:.{digits}f}초" if lang == "ko" else f"{t:.{digits}f} s"


# ----------------------------------------------------------------------------------
# texts

HELP = {
    "ko": """CANopen Lens — candump 로그를 쉬운 말로 풀어 줍니다

사용법
  canopen-lens 로그.log                 요약 보기
  canopen-lens 로그.log -d 1            1번 문제 자세히 (-d all: 전부)
  canopen-lens 로그.log -s 결과.csv     저장 (.txt 보고서 · .csv 메시지 표 · .json)
  canopen-lens examples                 예제 로그 2개를 지금 폴더에 받기
  canopen-lens live can0                실시간으로 보기 (자세히: canopen-lens live -h)
  canopen-lens                          창(GUI)으로 열기

자주 쓰는 옵션
  --eds 1=드라이브.eds    노드 1에 EDS 연결 (여러 번 쓸 수 있음)
  --check                 해결 안 된 문제가 있으면 종료 코드 1 (자동 점검용)
  --lang en               영어로 보기 (기본: 컴퓨터 언어 설정)
  --no-color              색 끄기

처음이라면   canopen-lens examples  →  canopen-lens sample_cia402.log
""",
    "en": """CANopen Lens — explains a candump log in plain words

Usage
  canopen-lens robot.log                what happened, in short
  canopen-lens robot.log -d 1           problem 1 in detail (-d all: every problem)
  canopen-lens robot.log -s result.csv  save (.txt report · .csv messages · .json data)
  canopen-lens examples                 copy the two example logs into this folder
  canopen-lens live can0                watch a bus as it runs (more: canopen-lens live -h)
  canopen-lens                          open the window (GUI)

Common options
  --eds 1=drive.eds       attach an EDS to node 1 (repeat for more nodes)
  --check                 exit status 1 if a problem is unresolved (for scripts / CI)
  --lang ko               Korean output (default: the computer's language)
  --no-color              no colours

New here?   canopen-lens examples  →  canopen-lens sample_cia402.log
""",
}

LIVE_HELP = {
    "ko": """사용법: canopen-lens live [채널] [옵션]

  canopen-lens live can0                       Linux / 라즈베리파이 (SocketCAN)
  canopen-lens live PCAN_USBBUS1 -b 500000     PCAN-USB (Windows)
  canopen-lens live COM3 -b 500000             USB-시리얼 어댑터 (slcan)

옵션
  -b, --bitrate 속도     통신 속도 bit/s (PCAN·slcan 등은 필요)
  --interface 이름       python-can 인터페이스 직접 지정 (kvaser, ixxat, vector, gs_usb …)
  --eds 노드=파일        EDS 연결
  -v                     문제마다 확인 방법까지 출력
  --frames               모든 메시지 출력

필요한 패키지: pip install "canopen-lens[live]"
""",
    "en": """Usage: canopen-lens live [CHANNEL] [options]

  canopen-lens live can0                       Linux / Raspberry Pi (SocketCAN)
  canopen-lens live PCAN_USBBUS1 -b 500000     PCAN-USB (Windows)
  canopen-lens live COM3 -b 500000             USB-serial adapter (slcan)

Options
  -b, --bitrate BITS     bit rate in bit/s (needed by PCAN, slcan, …)
  --interface NAME       python-can interface (kvaser, ixxat, vector, gs_usb, …)
  --eds NODE=FILE        attach an EDS
  -v                     print what to check for each problem
  --frames               print every message

Needs: pip install "canopen-lens[live]"
""",
}


class UsageError(Exception):
    """A mistake in how the command was used; shown as a plain message, no traceback."""


class ArgError(UsageError):
    """argparse's own (English) wording, wrapped in a plain sentence when shown."""


class _Parser(argparse.ArgumentParser):
    """argparse with our own help and with mistakes explained in the user's language."""

    def __init__(self, *a, lang: str = "en", help_text: str = "", **kw):
        super().__init__(*a, add_help=False, **kw)
        self._lang = lang
        self._help_text = help_text

    def error(self, message):  # noqa: D401 - argparse API
        raise ArgError(message)

    def print_help(self, file=None):
        print(self._help_text, end="", file=file)


def _eds_arg(text: str) -> tuple[int, str]:
    node, _, path = text.partition("=")
    if not path:
        raise argparse.ArgumentTypeError("NODE=PATH")
    return int(node, 0), path


def _write(text: str, output: Optional[str] = None) -> None:
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text)
        return
    enc = sys.stdout.encoding or "utf-8"
    sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace"))
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()


# ----------------------------------------------------------------------------------
# the summary and the detail view


def _status_label(lang: str, status: str) -> str:
    return {"open": _p(lang, "해결 안 됨", "Unresolved"), "recovered": _p(lang, "회복됨", "Recovered"),
            "warning": _p(lang, "경고", "Warning")}[status]


def summary_lines(log, ov, name: str, lang: str, st: Style) -> list[str]:
    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731
    out = []
    mark = {"error": st.red("✖"), "warning": st.amber("▲"), "ok": st.green("✔")}[ov.level]
    head = {"error": st.red, "warning": st.amber, "ok": st.green}[ov.level](ov.headline)
    c = ov.counts
    counts = "  ".join(x for x in (
        st.red(L(f"해결 안 됨 {c['open']}", f"unresolved {c['open']}")) if c["open"] else "",
        st.teal(L(f"회복 {c['recovered']}", f"recovered {c['recovered']}")) if c["recovered"] else "",
        st.amber(L(f"경고 {c['warning']}", f"warnings {c['warning']}")) if c["warning"] else "",
        st.dim(L(f"정상 {c['ok']}", f"OK {c['ok']}")) if c["ok"] else "") if x)
    out.append(f"{mark} {head}   {counts}".rstrip())
    out.append(st.dim("  " + L(f"{name} · {ov.duration:.1f}초 · 메시지 {ov.frames:,}개 · 노드 {len(ov.devices)}개",
                               f"{name} · {ov.duration:.1f} s · {ov.frames:,} messages · {len(ov.devices)} nodes")))

    if ov.looks_like_canopen is False:
        out += ["", "  " + ov.sentence, ""]
        from .explain import id_statistics

        stats = id_statistics(log, lang)
        out.append(st.bold(L("  ID별 통계 (많은 순 10개)", "  Traffic by ID (top 10)")))
        out.append(st.dim("  " + pad("ID", 12) + pad(L("개수", "count"), 10) + pad(L("평균 주기", "period"), 14) + L("최대 간격", "largest gap")))
        for s in sorted(stats, key=lambda s: -s["count"])[:10]:
            per = f"{s['period_ms']} ms" if s["period_ms"] else "-"
            gap = f"{s['max_gap_ms']} ms" if s["max_gap_ms"] else "-"
            out.append("  " + pad(s["id"], 12) + pad(f"{s['count']:,}", 10) + pad(per, 14) + gap)
        return out

    main = [i for i in ov.incidents if i.status in ("open", "recovered")]
    where_w = max([width(i.where) for i in main] + [6]) + 2
    title_w = min(max([width(i.title) for i in main] + [10]) + 2, 64)
    for status, colour in (("open", st.red), ("recovered", st.teal)):
        group = [i for i in main if i.status == status]
        if not group:
            continue
        out.append("")
        out.append(colour(_status_label(lang, status)))
        for i in group:
            when = _secs(lang, i.t)
            title = pad(i.title, title_w) if width(i.title) < title_w else i.title + "  "
            out.append(f"  {colour(f'{i.number:>2}')}  {pad(i.where, where_w)}{title}{st.dim(when)}")
    warnings = ov.by_status("warning")
    tail = []
    if warnings:
        shown = [(f"{i.where} " if i.node else "") + getattr(i, "short", i.title) for i in warnings[:3]]
        more = L(f" 외 {len(warnings) - 3}건", f" and {len(warnings) - 3} more") if len(warnings) > 3 else ""
        tail.append(st.amber(pad(L("경고", "Warnings"), 10)) + " · ".join(shown) + more)
    ok = [d for d in ov.devices if d.status == "ok"]
    if ok:
        tail.append(st.dim(pad(L("정상", "OK"), 10)) + ", ".join(L(f"노드 {d.node}", f"Node {d.node}") for d in ok))
    if tail:
        out.append("")
        out += tail
    if not ov.incidents:
        out += ["", "  " + ov.sentence]
    return out


def detail_lines(inc, lang: str, st: Style) -> list[str]:
    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731
    colour = {"open": st.red, "recovered": st.teal, "warning": st.amber}[inc.status]
    out = [f"{colour(f'{inc.number}  {_status_label(lang, inc.status)}')}  {st.bold(inc.where + ' · ' + inc.title)}",
           f"   {inc.hint}", ""]
    if inc.events:
        out.append(st.bold("   " + L("무슨 일이 있었나요", "What happened")))
        tw = max(width(_secs(lang, e.t, 3)) for e in inc.events) + 2
        tone = {"bad": st.red, "warn": st.amber, "good": st.teal, "info": lambda x: x}
        for e in inc.events:
            out.append(f"   {st.dim(pad(_secs(lang, e.t, 3), tw))}{tone[e.tone](e.text)}")
        out.append("")
    if inc.steps:
        out.append(st.bold("   " + L("먼저 확인할 것", "Check first")))
        for k, s in enumerate(inc.steps, 1):
            out.append(f"   {k}. {s}")
        out.append("")
    if inc.why:
        out.append(st.dim("   " + L("왜 중요한가요  ", "Why it matters  ")) + inc.why)
    rows = inc.rows
    shown = " ".join(f"#{r + 1}" for r in rows[:8]) + (" …" if len(rows) > 8 else "")
    out.append(st.dim("   " + L("근거 메시지    ", "Messages        ")) + shown)
    return out


def _full_text(log, ov, name: str, lang: str) -> str:
    st = Style(False)
    lines = summary_lines(log, ov, name, lang, st)
    for inc in ov.incidents:
        lines += ["", "─" * 60, ""] + detail_lines(inc, lang, st)
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------------
# commands


def run_log(argv: list[str], lang: str) -> int:
    p = _Parser(prog="canopen-lens", lang=lang, help_text=HELP[lang])
    p.add_argument("log")
    p.add_argument("-d", "--detail", action="append", default=[])
    p.add_argument("-s", "--save", action="append", default=[])
    p.add_argument("--eds", type=_eds_arg, action="append", default=[])
    p.add_argument("--check", action="store_true")
    p.add_argument("--lang", choices=["ko", "en"])
    p.add_argument("--no-color", action="store_true")
    p.add_argument("-h", "--help", action="store_true")
    args = p.parse_args(argv)
    lang = args.lang or lang
    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731
    if args.help:
        _write(HELP[lang])
        return 0
    path = Path(args.log)
    if not path.is_file():
        raise UsageError(L(f"파일을 찾을 수 없습니다: {args.log}", f"File not found: {args.log}")
                         + "\n" + L("  경로를 확인하거나, 예제로 먼저 해 보세요: canopen-lens examples",
                                    "  Check the path, or try an example first: canopen-lens examples"))
    for target in args.save:
        if Path(target).suffix.lower() not in (".txt", ".csv", ".json"):
            raise UsageError(L(f"저장 형식을 알 수 없습니다: {target}  (.txt · .csv · .json 중 하나)",
                               f"Unknown file type: {target}  (use .txt, .csv or .json)"))
    from .log import open_log

    for node, eds in args.eds:
        if not Path(eds).is_file():
            raise UsageError(L(f"EDS 파일을 찾을 수 없습니다: {eds}", f"EDS file not found: {eds}"))
    log = open_log(path, eds=dict(args.eds))
    if len(log) == 0:
        raise UsageError(L(f"{path.name}에서 CAN 메시지를 하나도 읽지 못했습니다. candump로 저장한 파일인지 확인하세요.",
                           f"No CAN messages could be read from {path.name}. Is it a candump log?"))
    st = Style(_color_wanted(args.no_color))
    ov = log.overview(lang)
    lines = summary_lines(log, ov, path.name, lang, st)

    wanted: list[int] = []
    for d in args.detail:
        for part in d.replace(",", " ").split():
            if part.lower() == "all":
                wanted = [i.number for i in ov.incidents]
                break
            if not part.isdigit() or ov.get(int(part)) is None:
                raise UsageError(L(f"{part}번 문제는 없습니다. 1~{len(ov.incidents)} 중에서 고르세요.",
                                   f"There is no problem {part}. Pick 1–{len(ov.incidents)}.") if ov.incidents else
                                 L("이 로그에는 자세히 볼 문제가 없습니다.", "This log has no problems to show."))
            wanted.append(int(part))
    if wanted:
        lines = []
        for k, n in enumerate(dict.fromkeys(wanted)):
            if k:
                lines += ["", st.dim("─" * 60), ""]
            lines += detail_lines(ov.get(n), lang, st)
    else:
        hints = []
        if ov.incidents:
            hints.append(st.dim(pad(L("자세히 보기", "Details"), 14)) + f"canopen-lens {path.name} -d 1")
        hints.append(st.dim(pad(L("결과 저장", "Save"), 14)) + f"canopen-lens {path.name} -s "
                     + L("결과.csv", "result.csv"))
        lines += [""] + hints

    for target in args.save:
        suffix = Path(target).suffix.lower()
        if suffix == ".csv":
            log.to_csv(target, lang)
        elif suffix == ".json":
            log.to_json(target, lang)
        else:
            Path(target).write_text(_full_text(log, ov, path.name, lang), encoding="utf-8-sig")
        lines.append(st.green("✔ ") + L(f"저장했습니다: {target}", f"Saved: {target}"))
    _write("\n".join(lines))
    return 1 if (args.check and ov.counts["open"]) else 0


def run_examples(argv: list[str], lang: str) -> int:
    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731
    if argv and argv[0] in ("-h", "--help"):
        _write(L("사용법: canopen-lens examples [폴더]   예제 로그를 폴더(기본: 지금 폴더)에 복사합니다",
                 "Usage: canopen-lens examples [FOLDER]   copies the example logs (default: this folder)"))
        return 0
    dest = Path(argv[0]) if argv else Path.cwd()
    dest.mkdir(parents=True, exist_ok=True)
    src = Path(__file__).resolve().parent / "examples"
    names = {"sample_cia402.log": L("여러 장치 · 문제 여러 개", "mixed network, several problems"),
             "sample_amr_2wheel.log": L("2륜 AMR · 부팅부터 비상정지까지", "two-wheel AMR, boot to E-stop")}
    lines = []
    for name, what in names.items():
        target = dest / name
        if not target.exists():
            shutil.copyfile(src / name, target)
        lines.append(f"  {pad(name, 24)}{what}")
    shown = dest if argv else Path(".")
    lines = [L(f"예제 로그를 {dest}에 두었습니다.", f"Example logs are in {dest}.")] + lines + [
        "", L("다음으로 해 보세요", "Try next") + f":  canopen-lens {shown / 'sample_cia402.log' if argv else 'sample_cia402.log'}"]
    _write("\n".join(lines))
    return 0


def run_live(argv: list[str], lang: str) -> int:
    p = _Parser(prog="canopen-lens live", lang=lang, help_text=LIVE_HELP[lang])
    p.add_argument("channel_pos", nargs="?")
    p.add_argument("--channel")
    p.add_argument("--interface")
    p.add_argument("-b", "--bitrate", type=int)
    p.add_argument("--eds", type=_eds_arg, action="append", default=[])
    p.add_argument("--lang", choices=["ko", "en"])
    p.add_argument("--frames", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("-h", "--help", action="store_true")
    args = p.parse_args(argv)
    lang = args.lang or lang
    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731
    if args.help:
        _write(LIVE_HELP[lang])
        return 0
    try:
        import can
    except ImportError:
        raise UsageError(L('실시간 보기에는 python-can이 필요합니다:  pip install "canopen-lens[live]"',
                           'Live mode needs python-can:  pip install "canopen-lens[live]"'))
    from .live import LiveDecoder

    channel = args.channel or args.channel_pos or ("can0" if sys.platform.startswith("linux") else None)
    if channel is None:
        raise UsageError(L("채널을 알려 주세요. 예: canopen-lens live PCAN_USBBUS1 -b 500000",
                           "Tell me the channel, e.g. canopen-lens live PCAN_USBBUS1 -b 500000"))
    iface = args.interface
    if iface is None:
        up = channel.upper()
        iface = "pcan" if up.startswith("PCAN") else "slcan" if up.startswith("COM") or "/dev/tty" in channel else "socketcan"
    kwargs = {"interface": iface, "channel": channel}
    if args.bitrate:
        kwargs["bitrate"] = args.bitrate
    dec = LiveDecoder(eds=dict(args.eds))
    st = Style(_color_wanted(False))
    _write(L(f"{iface} {channel}에서 버스를 듣는 중입니다… (Ctrl+C로 종료)", f"Listening on {iface} {channel}… (Ctrl+C to stop)"))

    def on_frame(msg, text):
        if args.frames:
            print(f"0x{msg.arbitration_id:03X}  {text}", flush=True)

    def on_issue(issue, ex):
        mark = {Severity.ERROR: st.red("✖"), Severity.WARNING: st.amber("▲"), Severity.INFO: st.dim("·")}[issue.severity]
        print(f"{mark} {ex.title}", flush=True)
        if args.verbose:
            for k, s in enumerate(ex.steps[:3], 1):
                print(f"    {k}. {s}", flush=True)

    try:
        with can.Bus(**kwargs) as bus:
            dec.run(bus, on_issue=on_issue, on_frame=on_frame, lang=lang)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        raise UsageError(L(f"CAN 어댑터에 연결하지 못했습니다: {exc}", f"Could not open the CAN adapter: {exc}"))
    return 0


# ----------------------------------------------------------------------------------
# `canopen-lens report …` from 0.4 and earlier (kept so existing scripts keep working)


def report(args) -> int:
    from .log import open_log

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


def run_report(argv: list[str]) -> int:
    r = argparse.ArgumentParser(prog="canopen-lens report")
    r.add_argument("log")
    r.add_argument("--eds", type=_eds_arg, action="append", metavar="NODE=PATH")
    r.add_argument("--lang", choices=["ko", "en"], default="en")
    r.add_argument("--format", choices=["text", "json", "csv"], default="text")
    r.add_argument("-o", "--output")
    r.add_argument("--brief", action="store_true")
    r.add_argument("--frames", action="store_true")
    r.add_argument("--min-severity", type=lambda s: Severity.__members__[s.upper()], default=Severity.INFO)
    r.add_argument("--fail-on-error", action="store_true")
    return report(r.parse_args(argv))


# ----------------------------------------------------------------------------------


def _usage_hint(lang: str) -> str:
    return _p(lang, "도움말: canopen-lens --help", "Help: canopen-lens --help")


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    lang = default_lang()
    for k, a in enumerate(argv):
        if a == "--lang" and k + 1 < len(argv) and argv[k + 1] in ("ko", "en"):
            lang = argv[k + 1]
        elif a.startswith("--lang=") and a[7:] in ("ko", "en"):
            lang = a[7:]
    try:
        if not argv:
            from .gui import main as gui_main

            return gui_main(["canopen-lens"])
        head = argv[0]
        if head in ("-h", "--help", "help"):
            _write(HELP[lang])
            return 0
        if head == "--version":
            _write(f"canopen-lens {__version__}")
            return 0
        if head == "--gui":
            from .gui import main as gui_main

            return gui_main(["canopen-lens", *argv[1:]])
        if head == "report":
            return run_report(argv[1:])
        if head == "live":
            return run_live(argv[1:], lang)
        if head == "examples":
            return run_examples(argv[1:], lang)
        return run_log(argv, lang)
    except UsageError as exc:
        msg = str(exc)
        if isinstance(exc, ArgError):
            msg = _p(lang, f"명령을 이해하지 못했습니다 ({msg})", f"Could not understand the command ({msg})")
        sys.stderr.write(f"canopen-lens: {msg}\n{_usage_hint(lang)}\n")
        return 2
    except BrokenPipeError:
        # the output was cut short on purpose (e.g. `| head`): stop quietly
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except Exception:  # pragma: no cover
            pass
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
