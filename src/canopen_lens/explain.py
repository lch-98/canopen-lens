"""Plain-language explanations for findings, a health summary of a whole log,
and a small glossary of CANopen terms.

Every finding is explained in three parts so that someone who has never read
the CANopen standard can still act on it:

* **what** – what happened, in one or two sentences
* **why** – why it matters for the machine
* **steps** – what to check, in the order a field engineer would check it
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ._core import AxisState, IssueType, Severity
from .describe import (
    _obj,
    _p,
    axis_state_text,
    emcy_text,
    error_register_text,
    hb_state_text,
    sdo_abort_text,
    severity_text,
    who,
)

if TYPE_CHECKING:  # pragma: no cover
    from .log import CanopenLog


def josa(n: int, pair: str) -> str:
    """Korean particle after a number: josa(5, "이가") -> "5가", josa(3, "은는") -> "3은"."""
    has_final = str(n)[-1] in "013678"
    return f"{n}{pair[0] if has_final else pair[1]}"


@dataclass
class Explanation:
    title: str
    what: str
    why: str
    steps: list[str]
    severity: Severity

    def as_text(self, lang: str = "ko") -> str:
        lines = [self.what, self.why]
        if self.steps:
            lines.append(_p(lang, "확인 순서:", "What to check:"))
            lines += [f"  {k}. {s}" for k, s in enumerate(self.steps, 1)]
        return "\n".join(line for line in lines if line)

    def as_dict(self) -> dict:
        return {"title": self.title, "what": self.what, "why": self.why, "steps": list(self.steps),
                "severity": self.severity.name.lower()}


def explain_issue(log: "CanopenLog", issue, lang: str = "ko") -> Explanation:
    n = issue.node
    T = issue.type
    sev = issue.severity
    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731

    def E(title, what, why, steps):
        return Explanation(title, what, why, steps, sev)

    if T == IssueType.SDO_ABORT:
        desc, hint = sdo_abort_text(issue.code, lang)
        obj = _obj(log, n, issue.index, issue.sub, lang)
        return E(
            L(f"노드 {n}: 설정값 읽기/쓰기 실패 – {desc}", f"Node {n}: SDO failed – {desc}"),
            L(f"마스터가 노드 {n}의 {obj} 값을 읽거나 쓰려고 했는데, 노드가 거절했습니다 (중단 코드 0x{issue.code:08X}).",
              f"The master tried to read or write {obj} on node {n}, and the node refused (abort code 0x{issue.code:08X})."),
            L("설정이 적용되지 않았기 때문에, 장치가 예상과 다른 값(이전 값이나 기본값)으로 동작하고 있을 수 있습니다.",
              "The setting was not applied, so the device may be running with a different (old or default) value."),
            [hint,
             L("장치 매뉴얼의 오브젝트 표에서 인덱스·서브인덱스·데이터 크기·읽기/쓰기 권한을 비교해 보세요.",
               "Compare index, sub-index, data size and access rights with the object table in the device manual."),
             L("같은 설정을 하는 마스터 코드(또는 설정 파일)를 찾아 값을 고친 뒤 다시 로그를 떠 보세요.",
               "Fix the value in the master code or configuration that sends it, then record a new log.")])

    if T == IssueType.SDO_NO_RESPONSE:
        obj = _obj(log, n, issue.index, issue.sub, lang)
        what = L("읽기", "read") if issue.code else L("쓰기", "write")
        return E(
            L(f"노드 {n}: 설정값 {what} 요청에 응답 없음", f"Node {n}: no answer to an SDO {what}"),
            L(f"마스터가 노드 {n}에 {obj} {what}를 요청했지만 {issue.value:g}초 안에 아무 대답이 없었습니다.",
              f"The master asked node {n} to {what} {obj}, but nothing came back within {issue.value:g} s."),
            L("노드가 꺼져 있거나 통신이 안 되는 상태일 수 있고, 마스터는 설정이 됐는지 알 수 없습니다.",
              "The node may be off or unreachable, and the master cannot know whether the setting took effect."),
            [L(f"노드-ID가 정말 {n}번인지 확인하세요 (장치의 DIP 스위치나 설정 툴).",
               f"Check that the device really has node-ID {n} (DIP switches or its configuration tool)."),
             L("노드의 전원과 CAN 커넥터, 통신 속도(bit rate)가 맞는지 확인하세요.",
               "Check the node's power, CAN connector and bit rate."),
             L("로그에서 이 노드의 하트비트가 오는지 보세요. 하트비트도 없으면 노드가 버스에 없는 것입니다.",
               "Look for this node's heartbeat in the log. No heartbeat either means the node is not on the bus."),
             L("NMT Stopped 상태의 노드는 SDO에 응답하지 않습니다. 상태 타임라인에서 NMT 상태를 확인하세요.",
               "A node in NMT Stopped does not answer SDO. Check its NMT state on the timeline.")])

    if T == IssueType.EMCY:
        reg = error_register_text(issue.index, lang)
        err = 0x603F + 0x800 * issue.axis
        return E(
            L(f"노드 {n}: 비상 메시지 – {emcy_text(issue.code, lang)}", f"Node {n}: emergency – {emcy_text(issue.code, lang)}"),
            L(f"노드 {josa(n, "이가")} 스스로 오류를 감지하고 비상(EMCY) 메시지를 보냈습니다. 오류 코드 0x{issue.code:04X}, 오류 종류: {reg}.",
              f"Node {n} detected an error itself and sent an emergency (EMCY) message. Error code 0x{issue.code:04X}, category: {reg}."),
            L("대부분의 장치는 EMCY를 보낸 뒤 동작을 멈추거나 제한합니다. 같은 시점의 드라이브 폴트와 함께 보는 것이 좋습니다.",
              "Most devices stop or limit operation after an EMCY. Look at it together with any drive fault at the same time."),
            [L(f"장치 매뉴얼의 오류 코드표에서 0x{issue.code:04X} 항목을 찾아 정확한 원인을 확인하세요.",
               f"Look up 0x{issue.code:04X} in the error code table of the device manual."),
             L(f"드라이브라면 0x{err:04X}(드라이브 에러 코드)를 SDO로 읽으면 더 자세한 코드가 나옵니다.",
               f"For a drive, reading 0x{err:04X} (error code) over SDO gives a more specific code."),
             L("원인을 없앤 뒤, 같은 노드에서 '오류 해제(EMCY 0x0000)'가 오는지 확인하세요.",
               "After fixing the cause, check that the node sends an error reset (EMCY 0x0000).")])

    if T == IssueType.EMCY_RESET:
        return E(
            L(f"노드 {n}: 오류 해제 알림", f"Node {n}: error reset"),
            L(f"노드 {josa(n, "이가")} 이전 오류가 모두 사라졌다고 알렸습니다 (EMCY 0x0000).",
              f"Node {n} reported that all previous errors are cleared (EMCY 0x0000)."),
            L("문제가 해결됐다는 좋은 신호입니다. 앞의 오류와 짝을 맞춰 보면 오류가 얼마나 지속됐는지 알 수 있습니다.",
              "A good sign. Pair it with the earlier error to see how long the problem lasted."),
            [])

    if T == IssueType.HEARTBEAT_GAP:
        period = issue.expected * 1000
        return E(
            L(f"노드 {n}: 생존 신호(하트비트)가 {issue.value:.2f}초 끊김", f"Node {n}: heartbeat gap of {issue.value:.2f} s"),
            L(f"노드 {josa(n, "은는")} 평소 {period:.0f} ms마다 '살아 있음' 신호를 보내는데, {issue.value:.2f}초 동안 보내지 않았다가 다시 보냈습니다.",
              f"Node {n} normally says 'I am alive' every {period:.0f} ms, but went silent for {issue.value:.2f} s and then came back."),
            L("잠깐이라도 통신이 끊기면 마스터가 노드를 잃은 것으로 판단해 장비를 멈출 수 있습니다.",
              "Even a short silence can make the master think the node is gone and stop the machine."),
            [L("같은 시점에 'CAN 버스 에러 프레임'이 있는지 보세요. 있으면 배선·종단저항 문제일 가능성이 큽니다.",
               "Look for CAN bus error frames at the same time. If there are any, suspect wiring or termination."),
             L("커넥터를 흔들었을 때 재현되는지, 케이블이 움직이는 부분을 지나는지 확인하세요.",
               "Check whether moving the connector reproduces it, and whether the cable runs through moving parts."),
             L("노드 펌웨어가 바쁜 작업(플래시 쓰기 등) 중에 하트비트를 못 보내는 경우도 있습니다.",
               "Some firmware stops sending heartbeats while busy (e.g. writing flash).")])

    if T == IssueType.HEARTBEAT_LOST:
        period = issue.expected * 1000
        return E(
            L(f"노드 {n}: 생존 신호(하트비트)가 끊긴 뒤 돌아오지 않음", f"Node {n}: heartbeat stopped"),
            L(f"노드 {josa(n, "은는")} 평소 {period:.0f} ms마다 하트비트를 보냈는데, 마지막 하트비트 이후 {issue.value:.2f}초 동안 아무 신호가 없습니다.",
              f"Node {n} sent a heartbeat every {period:.0f} ms, but nothing for {issue.value:.2f} s after the last one."),
            L("노드가 꺼졌거나, 멈췄거나, 버스에서 떨어져 나간 상태로 보입니다.",
              "The node looks switched off, hung, or disconnected from the bus."),
            [L("노드의 전원 LED와 상태 LED를 확인하세요.", "Check the node's power and status LEDs."),
             L("CAN 커넥터와 케이블이 빠지거나 끊어지지 않았는지 확인하세요.",
               "Check that the CAN connector and cable are not loose or broken."),
             L("노드가 리셋 중이었다면 잠시 뒤 'Boot-up' 메시지가 와야 합니다. 로그를 조금 더 길게 떠 보세요.",
               "If the node was resetting, a boot-up message should follow. Record a longer log.")])

    if T == IssueType.NODE_REBOOT:
        if issue.code:
            return E(
                L(f"노드 {n}: 리셋 명령 후 재시작", f"Node {n}: restarted after a reset command"),
                L(f"마스터의 리셋 명령 직후 노드 {josa(n, "이가")} 다시 켜졌다는 메시지(Boot-up)를 보냈습니다.",
                  f"Node {n} sent boot-up right after the master's reset command."),
                L("정상적인 동작입니다.", "This is normal."),
                [])
        return E(
            L(f"노드 {n}: 예상치 못한 재시작", f"Node {n}: unexpected restart"),
            L(f"리셋 명령이 없었는데 노드 {josa(n, "이가")} 방금 켜졌다는 메시지(Boot-up)를 다시 보냈습니다.",
              f"Node {n} sent boot-up again although nobody asked it to reset."),
            L("노드가 스스로 재시작했다는 뜻이라, 그 순간 설정과 상태가 초기화됐을 수 있습니다.",
              "The node restarted on its own, so its settings and state may have been reset at that moment."),
            [L("전원이 순간적으로 떨어지지 않았는지 확인하세요 (모터가 가속할 때 전압이 내려가는 경우가 많습니다).",
               "Check for a short power dip (often when motors accelerate)."),
             L("노드 펌웨어의 워치독 리셋이나 크래시 기록이 있는지 확인하세요.",
               "Check the firmware for watchdog resets or crash logs."),
             L("재시작 직후 마스터가 설정(SDO)을 다시 보내는지 확인하세요. 안 보내면 기본값으로 동작합니다.",
               "Check that the master re-sends its configuration after the restart; otherwise defaults are used.")])

    off = 0x800 * issue.axis
    cw_idx, err_idx = 0x6040 + off, 0x603F + off
    whom = who(log, n, issue.axis, lang)

    if T == IssueType.AXIS_FAULT:
        cause = ""
        if issue.related_row is not None and issue.related_code:
            cause = L(f" 같은 시점에 보고된 비상 메시지(EMCY 0x{issue.related_code:04X}, {emcy_text(issue.related_code, lang)})가 원인일 가능성이 큽니다.",
                      f" The emergency reported at the same time (EMCY 0x{issue.related_code:04X}, {emcy_text(issue.related_code, lang)}) is the likely cause.")
        return E(
            L(f"{whom}: 드라이브가 오류로 멈춤 (Fault)", f"{whom}: drive stopped with a fault"),
            L(f"드라이브 상태(스테이터스워드 0x{issue.code:04X})가 'Fault'로 바뀌었습니다.{cause}",
              f"The drive state (statusword 0x{issue.code:04X}) changed to Fault.{cause}"),
            L("Fault 상태의 드라이브는 모터 토크를 끄고 명령을 받지 않습니다. 해제하기 전까지 움직이지 않습니다.",
              "A faulted drive turns motor torque off and ignores motion commands until the fault is reset."),
            [L("먼저 원인을 확인하세요: 같은 노드의 EMCY 메시지와 드라이브 에러 코드(0x{0:04X}).".format(err_idx),
               "First find the cause: the node's EMCY message and the drive error code (0x{0:04X}).".format(err_idx)),
             L("원인을 없앤 뒤 컨트롤워드(0x{0:04X})의 bit 7을 0→1로 올려 Fault reset을 보내세요.".format(cw_idx),
               "After removing the cause, send a fault reset by raising bit 7 of the controlword (0x{0:04X}) from 0 to 1.".format(cw_idx)),
             L("그다음 Shutdown(0x06) → Switch on(0x07) → Enable operation(0x0F) 순서로 다시 운전 허가를 주세요.",
               "Then enable again: Shutdown (0x06) → Switch on (0x07) → Enable operation (0x0F).")])

    if T == IssueType.AXIS_QUICK_STOP:
        return E(
            L(f"{whom}: 급정지(Quick stop) 동작", f"{whom}: quick stop active"),
            L("드라이브가 급정지 상태로 들어갔습니다.", "The drive entered quick stop."),
            L("급정지 중에는 모터가 설정된 감속으로 멈추고, 다시 운전하려면 Enable 과정을 다시 거쳐야 합니다.",
              "The motor brakes to a stop and needs to be enabled again afterwards."),
            [L(f"마스터가 컨트롤워드(0x{cw_idx:04X})의 bit 2를 0으로 보내 급정지를 걸었는지 확인하세요.",
               f"Check whether the master cleared bit 2 of the controlword (0x{cw_idx:04X}) to request quick stop."),
             L("비상정지 버튼이나 안전 입력이 눌렸는지 확인하세요.", "Check emergency-stop buttons and safety inputs.")])

    if T == IssueType.AXIS_ENABLE_FAILED:
        code = issue.code if issue.code < 0x80 else -1
        state = axis_state_text(AxisState(code), lang)
        return E(
            L(f"{whom}: 운전 허가(Enable)를 보냈지만 켜지지 않음", f"{whom}: enable was sent but the drive did not turn on"),
            L(f"마스터가 '운전 허가(Enable operation)' 명령을 보냈지만 {issue.value:g}초가 지나도 드라이브가 운전 상태가 되지 않았습니다. 그때 상태: {state}.",
              f"The master sent 'enable operation', but the drive was still not running {issue.value:g} s later. State at that time: {state}."),
            L("모터에 토크가 걸리지 않아 이동 명령을 보내도 움직이지 않습니다.",
              "Without torque the motor will not follow any motion command."),
            [L(f"CiA 402는 순서를 지켜야 합니다. 컨트롤워드(0x{cw_idx:04X})에 Shutdown(0x06) → Switch on(0x07) → Enable operation(0x0F)을 차례로 보냈는지 확인하세요.",
               f"CiA 402 needs the right order: Shutdown (0x06) → Switch on (0x07) → Enable operation (0x0F) on the controlword (0x{cw_idx:04X})."),
             L("드라이브가 Fault 상태였다면 먼저 Fault reset이 필요합니다.", "A faulted drive needs a fault reset first."),
             L("모터 주전원(파워 전원)이 들어와 있는지 확인하세요. 제어 전원만 있으면 'Switched on'에서 멈춥니다.",
               "Check that motor (power stage) supply is on; with only logic power the drive stays in 'Switched on'."),
             L("STO(안전 토크 차단) 입력이 풀려 있는지 확인하세요.", "Check that the STO (safe torque off) input is released.")])

    if T == IssueType.AXIS_FAULT_RESET_FAILED:
        return E(
            L(f"{whom}: 오류 해제(Fault reset)가 먹히지 않음", f"{whom}: fault reset did not work"),
            L(f"마스터가 Fault reset을 보냈지만 {issue.value:g}초가 지나도 드라이브가 여전히 Fault 상태입니다.",
              f"The master sent a fault reset, but the drive was still faulted {issue.value:g} s later."),
            L("오류의 원인이 아직 남아 있다는 뜻입니다. 원인이 사라지기 전에는 리셋해도 바로 다시 Fault가 됩니다.",
              "The cause is still present; resetting again will not help until it is gone."),
            [L(f"같은 노드의 EMCY 메시지와 드라이브 에러 코드(0x{err_idx:04X})를 확인하세요.",
               f"Check the node's EMCY messages and drive error code (0x{err_idx:04X})."),
             L("과전류·과열·엔코더 오류·비상정지 입력처럼 계속 유지되는 원인이 있는지 확인하세요.",
               "Look for causes that persist: over current, over temperature, encoder fault, e-stop input."),
             L(f"Fault reset은 bit 7의 0→1 변화로만 동작합니다. 컨트롤워드(0x{cw_idx:04X})가 0x80을 계속 유지하고 있지는 않은지 보세요.",
               f"A fault reset needs bit 7 to go from 0 to 1; holding the controlword (0x{cw_idx:04X}) at 0x80 does nothing.")])

    if T == IssueType.BUS_ERROR_FRAME:
        return E(
            L("CAN 통신선 오류 감지", "CAN bus errors detected"),
            L("CAN 컨트롤러가 버스에서 깨진 신호를 감지했습니다 (에러 프레임).",
              "The CAN controller saw corrupted traffic on the bus (error frames)."),
            L("오류가 계속되면 메시지가 재전송되거나 유실되어 하트비트 끊김, SDO 실패 같은 다른 문제로 이어집니다.",
              "Ongoing errors cause retransmissions or lost messages, which show up as heartbeat gaps or SDO failures."),
            [L("버스 양 끝에 120Ω 종단저항이 하나씩만 있는지 확인하세요 (전원 끈 상태에서 CAN_H–CAN_L 사이 약 60Ω).",
               "Check for exactly one 120 Ω terminator at each end (about 60 Ω between CAN_H and CAN_L with power off)."),
             L("모든 노드의 통신 속도(bit rate)가 같은지 확인하세요.", "Check that every node uses the same bit rate."),
             L("CAN_GND 연결과 케이블 길이, 모터 전원선과 너무 가깝게 지나지 않는지 확인하세요.",
               "Check CAN_GND, cable length, and distance from motor power cables.")])

    if T == IssueType.PARSE_ERRORS:
        return E(
            L(f"읽지 못한 줄 {issue.code}개", f"{issue.code} lines could not be read"),
            L(f"candump 형식이 아닌 줄을 건너뛰었습니다 (처음 나온 곳: {int(issue.value)}번째 줄).",
              f"Lines that are not candump output were skipped (first at line {int(issue.value)})."),
            L("건너뛴 줄에 CAN 프레임이 있었다면 분석에서 빠졌습니다.", "Any frames on those lines are missing from the analysis."),
            [L("로그를 `candump -l can0`으로 저장했는지 확인하세요.", "Record logs with `candump -l can0`."),
             L("텍스트 편집기로 해당 줄을 열어 다른 프로그램의 출력이 섞이지 않았는지 보세요.",
               "Open the file and check whether other program output got mixed in.")])

    return E(str(T), "", "", [])


# --------------------------------------------------------------------------
# Grouping repeated findings
# --------------------------------------------------------------------------

@dataclass
class IssueGroup:
    """Identical findings (same type, node, axis and code) collapsed into one entry."""
    first: object
    issues: list = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.issues)

    @property
    def severity(self) -> Severity:
        return self.first.severity

    @property
    def t_first(self) -> float:
        return self.issues[0].t

    @property
    def t_last(self) -> float:
        return self.issues[-1].t


def _group_key(i):
    if i.type in (IssueType.SDO_ABORT, IssueType.SDO_NO_RESPONSE):
        return (i.type, i.node, i.index, i.sub, i.code)
    if i.type in (IssueType.HEARTBEAT_GAP, IssueType.BUS_ERROR_FRAME, IssueType.EMCY_RESET):
        return (i.type, i.node)
    return (i.type, i.node, i.axis, i.code)


def group_issues(issues) -> list[IssueGroup]:
    """Groups repeated findings; most severe first, then by first occurrence."""
    groups: dict = {}
    for i in issues:
        g = groups.get(_group_key(i))
        if g is None:
            g = groups[_group_key(i)] = IssueGroup(i)
        g.issues.append(i)
    return sorted(groups.values(), key=lambda g: (-int(g.severity), g.t_first))


# --------------------------------------------------------------------------
# Health summary of a whole log
# --------------------------------------------------------------------------

@dataclass
class NodeHealth:
    node: int
    level: str            # "ok" | "warning" | "error"
    headline: str         # one plain sentence
    details: list[str]


@dataclass
class HealthSummary:
    level: str            # "ok" | "warning" | "error"
    headline: str
    overview: str
    nodes: list[NodeHealth]
    groups: list[IssueGroup]


_LEVEL = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}
_LEVEL_NAME = ["ok", "warning", "error"]


def health_summary(log: "CanopenLog", lang: str = "ko") -> HealthSummary:
    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731
    trace = log.trace
    issues = list(trace.issues)
    groups = group_issues(issues)
    nodes = []
    for ni in trace.nodes:
        mine = [i for i in issues if i.node == ni.node]
        # warning: something went wrong but the node recovered;
        # error: the problem was still there at the end, or a setting was not applied
        level = 1 if any(i.severity != Severity.INFO for i in mine) else 0
        if any(i.type in (IssueType.HEARTBEAT_LOST, IssueType.SDO_ABORT, IssueType.SDO_NO_RESPONSE) for i in mine):
            level = 2
        details = []
        # communication
        if ni.last_hb_state >= 0:
            hb = hb_state_text(ni.last_hb_state, lang).split(" (")[0]
            period = f", {ni.hb_period * 1000:.0f} ms" if ni.hb_period else ""
            lost = any(i.type == IssueType.HEARTBEAT_LOST for i in mine)
            gaps = sum(1 for i in mine if i.type == IssueType.HEARTBEAT_GAP)
            if lost:
                details.append(L("생존 신호가 로그 끝에서 끊긴 상태입니다.", "Its heartbeat had stopped at the end of the log."))
            elif gaps:
                details.append(L(f"생존 신호가 {gaps}번 잠깐 끊겼다가 돌아왔습니다.", f"Its heartbeat dropped out {gaps} time(s) and came back."))
            else:
                details.append(L(f"생존 신호 정상 ({hb}{period}).", f"Heartbeat OK ({hb}{period})."))
        else:
            details.append(L("생존 신호(하트비트)를 보내지 않습니다.", "It sends no heartbeat."))
        # drive
        if ni.is_drive:
            states = list(ni.axis_states) or [ni.axis_state]
            faults = [i for i in mine if i.type == IssueType.AXIS_FAULT]
            for a, s in enumerate(states):
                ax = L(f"축 {a + 1}: ", f"Axis {a + 1}: ") if len(states) > 1 else ""
                n_f = sum(1 for i in faults if i.axis == a)
                if s in (AxisState.FAULT, AxisState.FAULT_REACTION_ACTIVE):
                    details.append(ax + L("폴트 상태로 끝났습니다 (해제되지 않음).", "ended in Fault (never cleared)."))
                    level = 2
                elif n_f:
                    details.append(ax + L(f"폴트가 {n_f}번 났지만 다시 {axis_state_text(s, lang, short=True)} 상태로 돌아왔습니다.",
                                          f"faulted {n_f} time(s) but recovered to {axis_state_text(s, lang, short=True)}."))
                else:
                    details.append(ax + L(f"마지막 상태: {axis_state_text(s, lang)}.", f"last state: {axis_state_text(s, lang)}."))
        n_sdo = sum(1 for i in mine if i.type in (IssueType.SDO_ABORT, IssueType.SDO_NO_RESPONSE))
        if n_sdo:
            details.append(L(f"설정값 읽기/쓰기(SDO) 실패 {n_sdo}건.", f"{n_sdo} failed SDO access(es)."))
        n_emcy = sum(1 for i in mine if i.type == IssueType.EMCY)
        if n_emcy:
            details.append(L(f"비상 메시지(EMCY) {n_emcy}건.", f"{n_emcy} emergency message(s)."))

        kind = L("CiA 402 드라이브", "CiA 402 drive") if ni.is_drive else L("일반 노드", "node")
        if level == 2:
            head = L(f"노드 {ni.node} ({kind}): 확인이 필요한 문제가 있습니다", f"Node {ni.node} ({kind}): needs attention")
        elif level == 1:
            head = L(f"노드 {ni.node} ({kind}): 문제가 있었지만 지금은 회복된 상태입니다",
                     f"Node {ni.node} ({kind}): had problems but recovered")
        else:
            head = L(f"노드 {ni.node} ({kind}): 정상", f"Node {ni.node} ({kind}): OK")
        nodes.append(NodeHealth(ni.node, _LEVEL_NAME[level], head, details))

    # bus-wide findings (error frames, unreadable lines) count too
    overall = max([_LEVEL_NAME.index(n.level) for n in nodes] +
                  [_LEVEL[i.severity] for i in issues if i.node == 0], default=0)
    n_err = sum(1 for g in groups if g.severity == Severity.ERROR)
    n_warn = sum(1 for g in groups if g.severity == Severity.WARNING)
    if overall == 2:
        headline = L(f"문제가 발견되었습니다 – 오류 {n_err}종류, 경고 {n_warn}종류",
                     f"Problems found – {n_err} kind(s) of error, {n_warn} kind(s) of warning")
    elif overall == 1:
        headline = L(f"큰 문제는 없지만 주의할 점이 {n_warn}종류 있습니다", f"No errors, but {n_warn} kind(s) of warning")
    else:
        headline = L("문제가 발견되지 않았습니다", "No problems found")
    overview = L(f"{trace.duration:.1f}초 동안 {len(trace):,}개 메시지, 노드 {len(nodes)}개를 분석했습니다.",
                 f"Analyzed {len(trace):,} messages from {len(nodes)} node(s) over {trace.duration:.1f} s.")
    return HealthSummary(_LEVEL_NAME[overall], headline, overview, nodes, groups)


def summary_text(log: "CanopenLog", lang: str = "ko") -> str:
    """The health summary as plain text (used by the CLI report)."""
    L = lambda ko, en: _p(lang, ko, en)  # noqa: E731
    h = health_summary(log, lang)
    marks = {"ok": "✔", "warning": "▲", "error": "✖"}
    out = [f"{marks[h.level]} {h.headline}", h.overview, ""]
    out.append(L("[노드별 상태]", "[Nodes]"))
    for n in h.nodes:
        out.append(f"  {marks[n.level]} {n.headline}")
        out += [f"      - {d}" for d in n.details]
    todo = [g for g in h.groups if g.severity != Severity.INFO]
    if todo:
        out += ["", L("[먼저 확인할 것]", "[Check first]")]
        for k, g in enumerate(todo, 1):
            ex = explain_issue(log, g.first, lang)
            times = (L(f" (총 {g.count}번, {g.t_first:.2f}–{g.t_last:.2f}초)", f" ({g.count}×, {g.t_first:.2f}–{g.t_last:.2f} s)")
                     if g.count > 1 else L(f" ({g.t_first:.2f}초)", f" (at {g.t_first:.2f} s)"))
            out.append(f"  {k}. [{severity_text(g.severity, lang)}] {ex.title}{times}")
            out.append(f"     {ex.what}")
            if ex.why:
                out.append(f"     {ex.why}")
            for s_i, step in enumerate(ex.steps, 1):
                out.append(f"       {s_i}) {step}")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Glossary
# --------------------------------------------------------------------------

GLOSSARY: list[tuple[str, str, str]] = [
    # (term, Korean explanation, English explanation)
    ("CAN", "기계 안의 여러 장치가 두 가닥 선(CAN_H, CAN_L)으로 메시지를 주고받는 통신 방식입니다. 한 메시지는 ID와 최대 8바이트 데이터로 되어 있습니다.",
     "A two-wire bus (CAN_H, CAN_L) that devices in a machine use to exchange short messages: an ID plus up to 8 data bytes."),
    ("CANopen", "CAN 위에서 '어떤 ID로 어떤 내용을 보낼지'를 정해 놓은 약속(프로토콜)입니다. 제조사가 달라도 같은 방식으로 설정하고 제어할 수 있게 해 줍니다.",
     "A set of rules on top of CAN that fixes which ID carries what, so devices from different vendors are configured and controlled the same way."),
    ("candump", "리눅스에서 CAN 메시지를 그대로 기록하는 명령어입니다. `candump -l can0`으로 저장한 파일을 이 프로그램에 넣으면 됩니다.",
     "The Linux command that records raw CAN traffic. Save with `candump -l can0` and open the file here."),
    ("노드 / Node-ID", "CANopen 네트워크에 붙은 장치 하나가 노드이고, 1~127 사이의 번호(Node-ID)로 구분합니다.",
     "Each device on the network is a node, identified by a node-ID from 1 to 127."),
    ("COB-ID", "CAN 메시지의 ID입니다. CANopen에서는 'ID = 메시지 종류 + 노드 번호'로 정해져 있어서, ID만 봐도 누가 무엇을 보냈는지 알 수 있습니다 (예: 0x185 = 노드 5의 TPDO1).",
     "The CAN identifier. In CANopen it is 'message type + node-ID', so the ID alone tells who sent what (e.g. 0x185 = TPDO1 of node 5)."),
    ("오브젝트 딕셔너리 (OD)", "장치 안의 모든 설정값과 상태값 목록입니다. 각 항목은 '인덱스:서브인덱스'(예: 0x6041:00)로 찾습니다.",
     "The list of every setting and status value inside a device, addressed as index:sub-index (e.g. 0x6041:00)."),
    ("EDS", "장치 제조사가 주는 오브젝트 딕셔너리 설명 파일입니다. 넣어 주면 값의 이름과 단위, PDO 구성을 정확히 해석합니다.",
     "The vendor's description file of a device's object dictionary. With it, names, types and PDO layout are decoded exactly."),
    ("NMT", "마스터가 노드를 시작·정지·리셋시키는 명령입니다. 노드는 Pre-operational(설정 모드) → Operational(운전) 상태를 거칩니다.",
     "Master commands that start, stop or reset nodes. Nodes go from pre-operational (setup) to operational (running)."),
    ("하트비트 (Heartbeat)", "노드가 일정한 주기로 보내는 '살아 있음' 신호입니다. 이 신호가 끊기면 노드가 꺼졌거나 통신이 끊긴 것입니다.",
     "A periodic 'I am alive' message from each node. If it stops, the node is off or disconnected."),
    ("SDO", "설정값을 하나씩 읽거나 쓰는 질문-대답 방식의 통신입니다. 주로 시작할 때 장치를 설정하는 데 씁니다. 거절되면 '중단 코드'가 옵니다.",
     "Question-and-answer access to one value at a time, mostly used for configuration. A refusal comes back as an abort code."),
    ("PDO (TPDO / RPDO)", "운전 중에 계속 주고받는 실시간 데이터입니다. TPDO는 장치→마스터(현재 위치, 상태), RPDO는 마스터→장치(목표값, 명령)입니다.",
     "Real-time data exchanged continuously while running. TPDO: device → master (actual values, status). RPDO: master → device (targets, commands)."),
    ("PDO 매핑", "PDO 8바이트 안에 어떤 값이 어떤 순서로 들어가는지 정한 표입니다. 이 표를 알아야 PDO를 숫자로 풀 수 있어서, EDS나 로그 안의 SDO 설정에서 찾아옵니다.",
     "The layout of values inside a PDO. It comes from the EDS or from SDO configuration found in the log."),
    ("EMCY", "장치가 스스로 오류를 감지했을 때 한 번 보내는 비상 메시지입니다. 오류 코드로 원인을 알 수 있고, 0x0000은 '오류 해제'입니다.",
     "Emergency message a device sends once when it detects an error. The code tells the cause; 0x0000 means 'cleared'."),
    ("SYNC", "마스터가 일정한 주기로 보내는 박자 신호입니다. 여러 장치가 이 박자에 맞춰 PDO를 보내고 받습니다.",
     "A periodic tick from the master; devices send and apply PDOs in step with it."),
    ("CiA 402", "모터 드라이브(서보/스텝 드라이버)를 위한 CANopen 표준입니다. 어떤 제조사 드라이브든 같은 순서와 같은 오브젝트로 켜고 움직입니다.",
     "The CANopen standard for motor drives: every vendor's drive is switched on and moved with the same objects and sequence."),
    ("컨트롤워드 / 스테이터스워드", "컨트롤워드(0x6040)는 마스터가 드라이브에 보내는 명령, 스테이터스워드(0x6041)는 드라이브가 알려주는 현재 상태입니다.",
     "The controlword (0x6040) is the master's command to a drive; the statusword (0x6041) reports the drive's state."),
    ("드라이브 상태", "드라이브는 '대기 → 준비 완료 → 스위치 온 → 운전 중' 순서로 켜집니다. 문제가 생기면 'Fault'로 멈추고, Fault reset으로 해제합니다.",
     "A drive turns on in steps: switch-on disabled → ready → switched on → operation enabled. Problems put it into Fault; a fault reset clears it."),
    ("다축 드라이브", "한 장치가 모터 여러 개를 제어하는 경우입니다. 축 2의 오브젝트는 축 1보다 0x800 큰 번호를 씁니다 (예: 축 2 스테이터스워드 0x6841).",
     "One device controlling several motors. Axis 2 objects are offset by 0x800 (axis 2 statusword = 0x6841)."),
    ("에러 프레임", "CAN 선 위에서 신호가 깨졌을 때 컨트롤러가 보고하는 것입니다. 배선, 종단저항, 통신 속도 문제를 의미합니다.",
     "Reported by the CAN controller when traffic on the wires is corrupted: wiring, termination or bit-rate trouble."),
]


def glossary(lang: str = "ko") -> list[tuple[str, str]]:
    return [(term, ko if lang == "ko" else en) for term, ko, en in GLOSSARY]
