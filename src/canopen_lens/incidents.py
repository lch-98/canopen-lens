"""Incidents: what happened, told as one story per problem.

The analyzer reports individual findings (a drive fault, the EMCY that came with it,
a fault reset that did not work, ...). Shown one by one they look like many separate
problems. This module groups them into incidents, decides whether each one was still
unresolved at the end of the log, and gives each a short title, a one-line hint, the
events in time order and at most three things to check.

    ov = log.overview("ko")
    ov.headline                      # "확인이 필요합니다"
    for inc in ov.incidents:
        print(inc.number, inc.where, inc.title, inc.hint)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ._core import AxisState, IssueType, Kind, Severity
from .describe import _p, emcy_text, sdo_abort_text

if TYPE_CHECKING:  # pragma: no cover
    from .log import CanopenLog

OPEN, RECOVERED, WARNING = "open", "recovered", "warning"
_STATUS_ORDER = {OPEN: 0, RECOVERED: 1, WARNING: 2}
_FAULTY = (AxisState.FAULT, AxisState.FAULT_REACTION_ACTIVE)
_ORDINAL_KO = {1: "첫", 2: "두", 3: "세", 4: "네", 5: "다섯"}


@dataclass
class Event:
    t: float
    row: int
    text: str
    tone: str = "info"          # "bad", "warn", "good", "info"


@dataclass
class Incident:
    status: str                 # OPEN / RECOVERED / WARNING
    node: int                   # 0 = the bus as a whole
    axes: list[int]             # 0-based axes of a drive, empty if not about an axis
    where: str                  # "노드 5 · 축 2"
    title: str                  # "모터 구속으로 멈춤 → 리셋 후 회복"
    hint: str                   # one line: what it means and what to check first
    status_word: str            # short status for the device list ("끊김", "설정 실패")
    t: float
    t_end: Optional[float] = None
    events: list[Event] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    why: str = ""
    issues: list = field(default_factory=list)
    number: int = 0
    priority: int = 5           # lower = shown first among incidents of the same status

    @property
    def rows(self) -> list[int]:
        return sorted({int(i.row) for i in self.issues} | {e.row for e in self.events if e.row >= 0})

    @property
    def first_row(self) -> int:
        return int(min(self.issues, key=lambda i: i.t).row) if self.issues else (self.events[0].row if self.events else 0)

    def as_dict(self) -> dict:
        return {
            "number": self.number, "status": self.status, "node": self.node, "axes": [a + 1 for a in self.axes],
            "where": self.where, "title": self.title, "hint": self.hint,
            "time_s": round(self.t, 6), "end_time_s": None if self.t_end is None else round(self.t_end, 6),
            "events": [{"time_s": round(e.t, 6), "row": e.row + 1, "text": e.text, "tone": e.tone} for e in self.events],
            "check": self.steps, "why": self.why, "rows": [r + 1 for r in self.rows],
        }


@dataclass
class Device:
    node: int
    kind: str                   # "드라이브", "2축 드라이브", "일반 장치", "마스터로 보임", "알 수 없음"
    status: str                 # OPEN / RECOVERED / WARNING / "ok"
    status_word: str            # "정상", "끊김", ...


@dataclass
class Overview:
    level: str                  # "error" / "warning" / "ok"
    headline: str
    sentence: str
    counts: dict                # {"open": n, "recovered": n, "warning": n, "ok": devices without problems}
    incidents: list[Incident]
    devices: list[Device]
    duration: float
    frames: int
    looks_like_canopen: Optional[bool] = True
    protocol_text: str = ""

    def by_status(self, status: str) -> list[Incident]:
        return [i for i in self.incidents if i.status == status]

    def get(self, number: int) -> Optional[Incident]:
        return next((i for i in self.incidents if i.number == number), None)


# ----------------------------------------------------------------------------------
# helpers

def _strip(text: str) -> str:
    """'과전류 (지속)' -> '과전류'."""
    return text.split(" (")[0].strip()


def _ro(word: str) -> str:
    """Korean particle 로/으로 after `word` (ㄹ final and no final consonant take 로)."""
    ch = word[-1:] if word else ""
    if "가" <= ch <= "힣":
        final = (ord(ch) - 0xAC00) % 28
        return "로" if final in (0, 8) else "으로"
    return "(으)로"


def _where(lang: str, node: int, axes: list[int], multi_axis: bool) -> str:
    if node == 0:
        return _p(lang, "CAN 버스", "CAN bus")
    base = _p(lang, f"노드 {node}", f"Node {node}")
    if axes and multi_axis:
        ax = "·".join(str(a + 1) for a in axes)
        return base + _p(lang, f" · 축 {ax}", f" · axis {ax}")
    return base


def _t(t: float) -> str:
    return f"{t:.2f}"


# ----------------------------------------------------------------------------------
# building

def build_incidents(log: "CanopenLog", lang: str = "ko") -> list[Incident]:
    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731
    trace = log.trace
    issues = sorted(trace.issues, key=lambda i: (i.t, int(i.row)))
    nodes = {ni.node: ni for ni in trace.nodes}
    used: set[int] = set()            # ids of issues already placed in an incident
    out: list[Incident] = []

    def multi(node: int) -> bool:
        ni = nodes.get(node)
        return bool(ni and ni.axis_count > 1)

    def explain(issue):
        return log.explain(issue, lang)

    # --- drive faults (with the EMCY that caused them, failed resets and the recovery)
    faults = [i for i in issues if i.type == IssueType.AXIS_FAULT]
    groups: list[list] = []
    for f in faults:
        for g in groups:
            if g[0].node == f.node and abs(g[0].t - f.t) < 0.1:
                g.append(f)
                break
        else:
            groups.append([f])
    for g in groups:
        node = g[0].node
        axes = sorted({int(f.axis) for f in g})
        t0 = min(f.t for f in g)
        for f in g:
            used.add(id(f))
        # cause: an EMCY linked to the fault, or one from the same node right around it
        emcys = [i for i in issues if i.type == IssueType.EMCY and i.node == node and id(i) not in used
                 and (any(f.related_row is not None and int(i.row) == int(f.related_row) for f in g)
                      or abs(i.t - t0) < 0.1)]
        for e in emcys:
            used.add(id(e))
        # when did every axis of the group leave the fault again?
        recovered_at, running_at, rec_row, run_row = None, None, -1, -1
        for a in axes:
            pts = [p for p in trace.axis_timeline(node, a) if p.t > t0 + 1e-9]
            leave = next((p for p in pts if p.state not in _FAULTY), None)
            if leave is None:
                recovered_at = None
                break
            if recovered_at is None or leave.t > recovered_at:
                recovered_at, rec_row = leave.t, int(leave.row)
            run = next((p for p in pts if p.t >= leave.t and p.state == AxisState.OPERATION_ENABLED), None)
            if run is not None and (running_at is None or run.t > running_at):
                running_at, run_row = run.t, int(run.row)
        end = recovered_at          # None: at least one axis was still faulted at the end
        resets = [i for i in issues if i.type == IssueType.AXIS_FAULT_RESET_FAILED and i.node == node
                  and int(i.axis) in axes and i.t >= t0 and (end is None or i.t <= end)]
        for r in resets:
            used.add(id(r))
        clears = [i for i in issues if i.type == IssueType.EMCY_RESET and i.node == node and i.t >= t0
                  and (end is None or i.t <= end + 0.5)]
        for c in clears:
            used.add(id(c))

        events = [Event(f.t, int(f.row), L("Fault로 정지 — 모터 토크가 꺼짐", "Fault — motor torque switched off")
                        if len(axes) == 1 else
                        L(f"축 {f.axis + 1} Fault로 정지", f"Axis {f.axis + 1} faulted"), "bad") for f in g]
        for e in emcys:
            events.append(Event(e.t, int(e.row), L(f"원인 보고: {emcy_text(e.code, lang)} · EMCY 0x{e.code:04X}",
                                                   f"Cause reported: {emcy_text(e.code, lang)} · EMCY 0x{e.code:04X}"), "bad"))
        for k, r in enumerate(resets, 1):
            nth = _ORDINAL_KO.get(k, str(k))
            events.append(Event(r.t, int(r.row), L(f"{nth} 번째 리셋 실패 — 원인이 아직 남아 있음",
                                                   f"Fault reset #{k} did not work — the cause was still there"), "warn"))
        for c in clears:
            if end is None or abs(c.t - end) > 0.05:
                events.append(Event(c.t, int(c.row), L("장치가 오류 해제를 알림 (EMCY 0x0000)",
                                                       "Device reported errors cleared (EMCY 0x0000)"), "good"))
        if end is not None:
            events.append(Event(end, rec_row, L("Fault가 풀림", "Fault cleared"), "good"))
            if running_at is not None:
                events.append(Event(running_at, run_row, L("다시 운전", "Running again"), "good"))
        events.sort(key=lambda e: e.t)

        cause = _strip(emcy_text(emcys[0].code, lang)) if emcys else ""
        if emcys:
            title = L(f"{cause}{_ro(cause)} 멈춤", f"Stopped: {cause.lower() if cause else 'fault'}")
        elif len(axes) > 1:
            title = L("두 축이 함께 멈춤 (원인 보고 없음)" if len(axes) == 2 else f"축 {len(axes)}개가 함께 멈춤 (원인 보고 없음)",
                      "All axes stopped together (no cause reported)")
        else:
            title = L("Fault로 멈춤 (원인 보고 없음)", "Stopped with a fault (no cause reported)")
        if end is not None:
            tries = len(resets) + 1
            if resets:
                title += L(f" → {_ORDINAL_KO.get(tries, str(tries))} 번째 리셋에서 회복", f" → recovered on reset #{tries}")
            else:
                title += L(" → 리셋 후 회복", " → recovered after a reset")
        if emcys:
            hint = L(f"원인: {emcy_text(emcys[0].code, lang)} (EMCY 0x{emcys[0].code:04X})",
                     f"Cause: {emcy_text(emcys[0].code, lang)} (EMCY 0x{emcys[0].code:04X})")
            steps = [L("장치 매뉴얼의 오류 코드표에서 0x{:04X} 항목 찾기".format(emcys[0].code),
                       "Look up 0x{:04X} in the device manual's error table".format(emcys[0].code)),
                     L(f"드라이브 에러 코드(0x{0x603F + 0x800 * axes[0]:04X})를 읽어 자세한 원인 확인",
                       f"Read the drive error code (0x{0x603F + 0x800 * axes[0]:04X}) for the exact cause"),
                     L("원인을 없앤 뒤 Fault reset → 0x06 → 0x07 → 0x0F 순서로 다시 운전",
                       "Remove the cause, then fault reset → 0x06 → 0x07 → 0x0F")]
        else:
            hint = L("장치가 원인(EMCY)을 보내지 않았습니다 · 비상정지·STO·전원 같은 안전 입력부터 확인",
                     "The device sent no cause (EMCY) · check E-stop, STO and power first")
            steps = [L("비상정지·STO·전원처럼 장치 전체를 멈추는 입력 확인", "Check inputs that stop the whole device: E-stop, STO, power"),
                     L(f"드라이브 에러 코드(0x{0x603F + 0x800 * axes[0]:04X})를 읽어 원인 확인",
                       f"Read the drive error code (0x{0x603F + 0x800 * axes[0]:04X})"),
                     L("원인을 없앤 뒤 Fault reset → 0x06 → 0x07 → 0x0F 순서로 다시 운전",
                       "Remove the cause, then fault reset → 0x06 → 0x07 → 0x0F")]
        if resets:
            hint += L(f" · 리셋 {len(resets)}번 실패", f" · {len(resets)} failed reset(s)")
        ex = explain(g[0])
        out.append(Incident(OPEN if end is None else RECOVERED, node, axes, _where(lang, node, axes, multi(node)),
                            title, hint, L("Fault", "fault") if end is None else L("회복됨", "recovered"),
                            t0, end, events, steps, ex.why, list(g) + emcys + resets + clears,
                            priority=1))

    # --- EMCY without a drive fault
    for e in issues:
        if e.type != IssueType.EMCY or id(e) in used:
            continue
        used.add(id(e))
        clear = next((c for c in issues if c.type == IssueType.EMCY_RESET and c.node == e.node and c.t > e.t
                      and id(c) not in used), None)
        events = [Event(e.t, int(e.row), L(f"비상 메시지: {emcy_text(e.code, lang)} · EMCY 0x{e.code:04X}",
                                           f"Emergency: {emcy_text(e.code, lang)} · EMCY 0x{e.code:04X}"), "bad")]
        members = [e]
        if clear is not None:
            used.add(id(clear))
            members.append(clear)
            events.append(Event(clear.t, int(clear.row), L("오류 해제 알림 (EMCY 0x0000)", "Errors cleared (EMCY 0x0000)"), "good"))
        name = _strip(emcy_text(e.code, lang))
        ex = explain(e)
        out.append(Incident(RECOVERED if clear else OPEN, e.node, [], _where(lang, e.node, [], False),
                            L(f"장치가 오류를 알림: {name}", f"Device reported an error: {name}")
                            + (L(" → 해제됨", " → cleared") if clear else ""),
                            L(f"EMCY 0x{e.code:04X} · 매뉴얼의 오류 코드표에서 확인", f"EMCY 0x{e.code:04X} · see the device manual"),
                            L("오류", "error") if not clear else L("회복됨", "recovered"),
                            e.t, clear.t if clear else None, events, ex.steps[:3], ex.why, members, priority=2))

    # --- heartbeat stopped for good
    for h in issues:
        if h.type != IssueType.HEARTBEAT_LOST or id(h) in used:
            continue
        used.add(id(h))
        last = h.t - h.value
        ex = explain(h)
        out.append(Incident(OPEN, h.node, [], _where(lang, h.node, [], False),
                            L("통신이 끊긴 뒤 돌아오지 않음", "Went silent and never came back"),
                            L(f"{_t(last)}초 이후 생존 신호가 없습니다 · 전원과 커넥터부터 확인",
                              f"No heartbeat after {_t(last)} s · check power and connector first"),
                            L("끊김", "silent"), h.t, None,
                            [Event(last, int(h.row), L("마지막 생존 신호", "Last heartbeat"), "info"),
                             Event(h.t, int(h.row), L("이후 신호 없음 — 로그 끝까지", "Nothing after that, until the end of the log"), "bad")],
                            ex.steps[:3], ex.why, [h], priority=0))

    # --- SDO requests nobody answered (per node)
    by_node: dict[int, list] = {}
    for s in issues:
        if s.type == IssueType.SDO_NO_RESPONSE and id(s) not in used:
            by_node.setdefault(s.node, []).append(s)
    for node, lst in by_node.items():
        for s in lst:
            used.add(id(s))
        ni = nodes.get(node)
        absent = ni is None or (ni.hb_count == 0 and set(ni.kind_counts) <= {Kind.SDO_REQ, Kind.RPDO, Kind.NMT})
        ex = explain(lst[0])
        n = len(lst)
        if absent:
            title = L("응답 없음 — 버스에 없는 것으로 보임", "No answer — the device seems to be missing")
            hint = L("설정 요청에도, 생존 신호에도 반응이 없습니다 · 노드 번호와 배선 확인",
                     "No answer to requests and no heartbeat · check node-ID and wiring")
            word = L("응답 없음", "missing")
        else:
            title = L("설정 요청에 대답하지 않음", "Did not answer configuration requests")
            hint = L("통신은 되지만 SDO 요청에 응답이 없습니다 · NMT 상태(Stopped) 확인",
                     "The device is on the bus but ignores SDO · check its NMT state (Stopped)")
            word = L("응답 없음", "no answer")
        if n > 1:
            hint = L(f"요청 {n}건 모두 응답 없음 · ", f"{n} requests unanswered · ") + hint
        out.append(Incident(OPEN, node, [], _where(lang, node, [], False), title, hint, word, lst[0].t, None,
                            [Event(s.t, int(s.row), L(f"요청에 {s.value:g}초 동안 대답 없음", f"No answer within {s.value:g} s"), "bad")
                             for s in lst[:5]], ex.steps[:3], ex.why, lst, priority=0))

    # --- SDO aborts (per node and object)
    aborts: dict[tuple, list] = {}
    for s in issues:
        if s.type == IssueType.SDO_ABORT and id(s) not in used:
            aborts.setdefault((s.node, s.index, s.sub, s.code), []).append(s)
    for (node, index, sub, code), lst in aborts.items():
        for s in lst:
            used.add(id(s))
        desc, _hint = sdo_abort_text(code, lang)
        ex = explain(lst[0])
        n = len(lst)
        out.append(Incident(OPEN, node, [], _where(lang, node, [], False),
                            L("설정이 적용되지 않음", "A setting was not applied"),
                            L(f"0x{index:04X}:{sub:02X} — {desc} · 마스터 설정 확인", f"0x{index:04X}:{sub:02X} — {desc} · check the master's configuration")
                            + (L(f" ({n}번)", f" ({n} times)") if n > 1 else ""),
                            L("설정 실패", "setting failed"), lst[0].t, None,
                            [Event(s.t, int(s.row), L(f"장치가 거절: {desc} (0x{code:08X})", f"Refused: {desc} (0x{code:08X})"), "bad")
                             for s in lst[:5]], ex.steps[:3], ex.why, lst, priority=2))

    # --- drive did not enable / quick stop / reboot
    for i in issues:
        if id(i) in used:
            continue
        ex = None
        if i.type == IssueType.AXIS_ENABLE_FAILED:
            used.add(id(i))
            later = next((p for p in trace.axis_timeline(i.node, i.axis)
                          if p.t > i.t and p.state == AxisState.OPERATION_ENABLED), None)
            ex = explain(i)
            out.append(Incident(RECOVERED if later else OPEN, i.node, [int(i.axis)], _where(lang, i.node, [int(i.axis)], multi(i.node)),
                                L("운전 허가가 들어가지 않음", "Enable operation did not take effect")
                                + (L(" → 나중에 운전됨", " → enabled later") if later else ""),
                                L("0x0F를 보냈지만 운전 상태가 되지 않았습니다 · 순서(06→07→0F)와 모터 전원 확인",
                                  "0x0F was sent but the drive did not enable · check the 06→07→0F order and motor power"),
                                L("운전 안 됨", "not enabled") if not later else L("회복됨", "recovered"),
                                i.t, later.t if later else None,
                                [Event(i.t, int(i.row), L("운전 허가 명령이 먹히지 않음", "Enable command had no effect"), "bad")]
                                + ([Event(later.t, int(later.row), L("운전 시작", "Running"), "good")] if later else []),
                                ex.steps[:3], ex.why, [i], priority=1))
        elif i.type == IssueType.NODE_REBOOT:
            used.add(id(i))
            ex = explain(i)
            out.append(Incident(RECOVERED, i.node, [], _where(lang, i.node, [], False),
                                L("예고 없이 다시 켜짐", "Restarted without being told to"),
                                L("리셋 명령 없이 부팅 메시지가 왔습니다 · 전원 흔들림·워치독 확인",
                                  "Boot-up without a reset command · check power dips and watchdogs"),
                                L("재시작", "restarted"), i.t, i.t,
                                [Event(i.t, int(i.row), L("부팅 메시지 (Boot-up)", "Boot-up message"), "warn")],
                                ex.steps[:3], ex.why, [i], priority=1))

    # --- warnings, grouped by kind and node
    warn_groups: dict[tuple, list] = {}
    for i in issues:
        if id(i) in used or i.severity == Severity.INFO:
            continue
        warn_groups.setdefault((int(i.type), i.node), []).append(i)
        used.add(id(i))
    for (_typ, node), lst in warn_groups.items():
        first = lst[0]
        ex = explain(first)
        n = len(lst)
        T = first.type
        if T == IssueType.HEARTBEAT_GAP:
            longest = max(i.value for i in lst)
            title = (L(f"통신이 {longest:.1f}초 끊겼다가 돌아옴", f"Went silent for {longest:.1f} s, then came back") if n == 1 else
                     L(f"통신이 {n}번 끊겼다가 돌아옴 (최대 {longest:.1f}초)", f"Went silent {n} times (up to {longest:.1f} s)"))
            short = L(f"통신 {longest:.1f}초 끊김", f"silent {longest:.1f} s")
            hint = L("커넥터 접촉이나 순간 전원 강하를 의심해 보세요", "Suspect a loose connector or a short power dip")
        elif T == IssueType.BUS_ERROR_FRAME:
            title = L(f"CAN 선 오류 {n}회", f"{n} CAN bus error(s)")
            short = title
            hint = L("종단 저항(120 Ω 두 개), 배선, 통신 속도 확인", "Check termination (two 120 Ω), cabling and bit rate")
        elif T == IssueType.AXIS_QUICK_STOP:
            title = L("급정지(Quick stop)로 들어감", "Entered quick stop")
            short = title
            hint = L("마스터가 급정지를 보냈거나 드라이브가 스스로 멈췄습니다", "The master sent quick stop or the drive stopped by itself")
        elif T == IssueType.PARSE_ERRORS:
            title = L(f"읽지 못한 줄 {first.code}개", f"{first.code} unreadable line(s)")
            short = title
            hint = L("candump 형식이 아닌 줄이 섞여 있습니다", "Some lines are not in candump format")
        else:
            title = ex.title
            short = title
            hint = ex.what.split(". ")[0]
        inc = Incident(WARNING, node, [int(first.axis)] if T == IssueType.AXIS_QUICK_STOP else [],
                       _where(lang, node, [int(first.axis)] if T == IssueType.AXIS_QUICK_STOP else [], multi(node)),
                       title, hint, L("경고", "warning"), first.t, lst[-1].t,
                       [Event(i.t, int(i.row), ex.title if T != IssueType.HEARTBEAT_GAP else
                              L(f"{i.value:.2f}초 동안 신호 없음", f"No heartbeat for {i.value:.2f} s"), "warn") for i in lst[:5]],
                       ex.steps[:3], ex.why, lst, priority=3)
        inc.short = short          # used where warnings are listed on one line
        out.append(inc)

    out.sort(key=lambda i: (_STATUS_ORDER[i.status], i.priority, i.t))
    for k, inc in enumerate(out, 1):
        inc.number = k
    return out


def build_devices(log: "CanopenLog", incidents: list[Incident], lang: str = "ko") -> list[Device]:
    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731
    trace = log.trace
    has_master_traffic = bool(len(trace.filter(kinds=[Kind.NMT, Kind.SYNC])))
    devices = []
    for ni in trace.nodes:
        mine = [i for i in incidents if i.node == ni.node]
        kinds = set(ni.kind_counts)
        if ni.is_drive:
            kind = L(f"{ni.axis_count}축 드라이브", f"{ni.axis_count}-axis drive") if ni.axis_count > 1 else L("드라이브", "drive")
        elif ni.hb_count == 0 and kinds <= {Kind.SDO_REQ, Kind.RPDO, Kind.NMT}:
            kind = L("알 수 없음", "unknown")
        elif has_master_traffic and ni.hb_count and not (kinds & {Kind.TPDO, Kind.RPDO, Kind.SDO_REQ, Kind.SDO_RESP, Kind.EMCY}):
            kind = L("마스터로 보임", "probably the master")
        else:
            kind = L("일반 장치", "device")
        open_ = [i for i in mine if i.status == OPEN]
        if open_:
            devices.append(Device(ni.node, kind, OPEN, open_[0].status_word))
        elif any(i.status == RECOVERED for i in mine):
            devices.append(Device(ni.node, kind, RECOVERED, L("회복됨", "recovered")))
        elif mine:
            devices.append(Device(ni.node, kind, WARNING, L("경고", "warning")))
        else:
            devices.append(Device(ni.node, kind, "ok", L("정상", "OK")))
    return devices


def build_overview(log: "CanopenLog", lang: str = "ko") -> Overview:
    from .explain import protocol_check

    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731
    incidents = build_incidents(log, lang)
    devices = build_devices(log, incidents, lang)
    counts = {OPEN: sum(1 for i in incidents if i.status == OPEN),
              RECOVERED: sum(1 for i in incidents if i.status == RECOVERED),
              WARNING: sum(1 for i in incidents if i.status == WARNING),
              "ok": sum(1 for d in devices if d.status == "ok")}
    if counts[OPEN]:
        level, head = "error", L("확인이 필요합니다", "Needs attention")
        sentence = L(f"로그가 끝날 때까지 해결되지 않은 문제가 {counts[OPEN]}건 있습니다. 위에서부터 확인하세요.",
                     f"{counts[OPEN]} problem(s) were still unresolved at the end of the log. Start from the top.")
    elif counts[RECOVERED]:
        level, head = "warning", L("문제가 있었지만 모두 회복됐습니다", "Problems occurred, all recovered")
        sentence = L(f"문제 {counts[RECOVERED]}건이 있었지만 로그가 끝날 때는 정상이었습니다.",
                     f"{counts[RECOVERED]} problem(s) occurred but everything was fine at the end of the log.")
    elif counts[WARNING]:
        level, head = "warning", L("큰 문제는 없습니다", "No real problems")
        sentence = L(f"주의해서 볼 경고가 {counts[WARNING]}건 있습니다.", f"{counts[WARNING]} warning(s) worth a look.")
    else:
        level, head = "ok", L("문제가 없습니다", "No problems found")
        sentence = L(f"장치 {len(devices)}개가 모두 정상입니다.", f"All {len(devices)} device(s) look fine.")
    proto = protocol_check(log, lang)
    ov = Overview(level, head, sentence, counts, incidents, devices, log.trace.duration, len(log.trace),
                  proto.looks_like_canopen, proto.text if proto.looks_like_canopen is not True else "")
    if proto.looks_like_canopen is False:
        ov.level = "warning"
        ov.headline = proto.title
        ov.sentence = proto.text
    return ov
