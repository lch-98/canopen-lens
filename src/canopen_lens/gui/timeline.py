"""Per-node state timeline: CiA 402 axis state and NMT state from heartbeats."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .. import describe
from .._core import AxisState, IssueType, Kind, Severity
from ..log import CanopenLog
from .i18n import Tr

AXIS_COLORS = {
    AxisState.UNKNOWN: "#e2e8f0",
    AxisState.NOT_READY_TO_SWITCH_ON: "#cbd5e1",
    AxisState.SWITCH_ON_DISABLED: "#94a3b8",
    AxisState.READY_TO_SWITCH_ON: "#93c5fd",
    AxisState.SWITCHED_ON: "#60a5fa",
    AxisState.OPERATION_ENABLED: "#22c55e",
    AxisState.QUICK_STOP_ACTIVE: "#f59e0b",
    AxisState.FAULT_REACTION_ACTIVE: "#f87171",
    AxisState.FAULT: "#dc2626",
}

NMT_COLORS = {
    0x00: "#cbd5e1",   # boot-up
    0x04: "#ef4444",   # stopped
    0x05: "#22c55e",   # operational
    0x7F: "#facc15",   # pre-operational
}


@dataclass
class Segment:
    t0: float
    t1: float
    color: str
    label: str
    row: int


@dataclass
class Lane:
    title: str
    segments: list[Segment]
    markers: list[tuple[float, int, str]]  # (t, row, tooltip)


class TimelineWidget(QWidget):
    rowActivated = Signal(int)

    LABEL_W = 150
    LANE_H = 26
    LANE_GAP = 10
    TOP = 34

    def __init__(self, tr: Tr, parent=None):
        super().__init__(parent)
        self.tr_ = tr
        self.log: Optional[CanopenLog] = None
        self.lanes: list[Lane] = []
        self.duration = 1.0
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    # -- data ------------------------------------------------------------------
    def set_log(self, log: Optional[CanopenLog]) -> None:
        self.log = log
        self.rebuild()

    def rebuild(self) -> None:
        self.lanes = []
        log = self.log
        if log is None or len(log) == 0:
            self.update()
            return
        lang = self.tr_.lang
        trace = log.trace
        self.duration = max(trace.duration, 1e-6)
        issues_by_node: dict[int, list] = {}
        for i in trace.issues:
            if i.node and i.severity != Severity.INFO:
                issues_by_node.setdefault(i.node, []).append(i)

        axis_types = {IssueType.AXIS_FAULT, IssueType.AXIS_QUICK_STOP, IssueType.AXIS_ENABLE_FAILED,
                      IssueType.AXIS_FAULT_RESET_FAILED}
        for ni in trace.nodes:
            n = ni.node
            node_issues = issues_by_node.get(n, [])

            def marks(sel):
                return [(i.t, i.row, log.issue_text(i, lang)[0]) for i in node_issues if sel(i)]

            # node-level findings go on the node's first lane
            markers = marks(lambda i: i.type not in axis_types)
            if ni.is_drive:
                multi = ni.axis_count > 1
                for axis in range(max(ni.axis_count, 1)):
                    pts = trace.axis_timeline(n, axis)
                    segs = []
                    for k, p in enumerate(pts):
                        t1 = pts[k + 1].t if k + 1 < len(pts) else self.duration
                        segs.append(Segment(p.t, t1, AXIS_COLORS[p.state],
                                            describe.axis_state_text(p.state, lang), int(p.row)))
                    axis_marks = marks(lambda i, a=axis: i.type in axis_types and i.axis == a)
                    if not segs and not axis_marks:
                        continue
                    label = self.tr_("timeline_axis_n").format(axis + 1) if multi else self.tr_("timeline_axis")
                    self.lanes.append(Lane(f"{self.tr_('col_node')} {n} · {label}", segs, markers + axis_marks))
                    markers = []
            if ni.hb_count:
                rows = trace.filter(kinds=[Kind.HEARTBEAT], node=n)
                period = ni.hb_period or 0.0
                limit = max(period * trace.options.hb_gap_factor, period + 0.02) if period else None
                segs = []
                prev_t = prev_state = prev_row = None
                for row in rows:
                    rec = trace.record(row)
                    f = trace.frame(row)
                    if f.rtr:
                        continue
                    if prev_t is not None:
                        end = f.t
                        if limit and f.t - prev_t > limit and prev_state != 0:
                            end = prev_t + period
                        segs.append(Segment(prev_t, end, NMT_COLORS.get(prev_state, "#e2e8f0"),
                                            describe.hb_state_text(prev_state, lang), prev_row))
                    prev_t, prev_state, prev_row = f.t, rec.hb_state, int(row)
                if prev_t is not None:
                    end = self.duration
                    if limit and self.duration - prev_t > limit:
                        end = prev_t + period
                    segs.append(Segment(prev_t, end, NMT_COLORS.get(prev_state, "#e2e8f0"),
                                        describe.hb_state_text(prev_state, lang), prev_row))
                merged: list[Segment] = []
                for seg in segs:
                    last = merged[-1] if merged else None
                    if last and last.label == seg.label and abs(last.t1 - seg.t0) < 1e-9:
                        last.t1 = seg.t1
                    else:
                        merged.append(seg)
                self.lanes.append(Lane(f"{self.tr_('col_node')} {n} · {self.tr_('timeline_nmt')}", merged, markers))
        h = self.TOP + len(self.lanes) * (self.LANE_H + self.LANE_GAP) + 40
        self.setMinimumHeight(max(h, 160))
        self.update()

    # -- geometry ----------------------------------------------------------------
    def _x(self, t: float) -> float:
        w = max(self.width() - self.LABEL_W - 20, 10)
        return self.LABEL_W + (t / self.duration) * w

    def _t(self, x: float) -> float:
        w = max(self.width() - self.LABEL_W - 20, 10)
        return max(0.0, min(self.duration, (x - self.LABEL_W) / w * self.duration))

    def _lane_rect(self, k: int) -> QRectF:
        y = self.TOP + k * (self.LANE_H + self.LANE_GAP)
        return QRectF(self.LABEL_W, y, max(self.width() - self.LABEL_W - 20, 10), self.LANE_H)

    def _hit(self, pos) -> tuple[Optional[Lane], Optional[Segment], Optional[tuple]]:
        for k, lane in enumerate(self.lanes):
            rect = self._lane_rect(k)
            if rect.top() - 8 <= pos.y() <= rect.bottom():
                for m in lane.markers:
                    if abs(self._x(m[0]) - pos.x()) <= 6 and pos.y() < rect.top() + 6:
                        return lane, None, m
                if pos.y() < rect.top():
                    return lane, None, None
                t = self._t(pos.x())
                for s in lane.segments:
                    if s.t0 <= t <= s.t1:
                        return lane, s, None
                return lane, None, None
        return None, None, None

    # -- painting ------------------------------------------------------------------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        p.fillRect(self.rect(), pal.base())
        text_color = pal.text().color()
        if not self.lanes:
            p.setPen(text_color)
            p.drawText(self.rect(), Qt.AlignCenter, self.tr_("timeline_empty"))
            return

        # time axis
        p.setPen(QPen(QColor("#94a3b8"), 1))
        small = QFont(self.font())
        small.setPointSizeF(max(7.0, small.pointSizeF() - 1))
        p.setFont(small)
        ticks = 10
        for k in range(ticks + 1):
            t = self.duration * k / ticks
            x = self._x(t)
            p.drawLine(QPointF(x, self.TOP - 8), QPointF(x, self.TOP - 4))
            p.drawText(QRectF(x - 40, 2, 80, self.TOP - 12), Qt.AlignCenter, f"{t:.2f}s")

        p.setFont(self.font())
        for k, lane in enumerate(self.lanes):
            rect = self._lane_rect(k)
            p.setPen(text_color)
            p.drawText(QRectF(4, rect.top(), self.LABEL_W - 10, rect.height()), Qt.AlignVCenter | Qt.AlignLeft, lane.title)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#f1f5f9"))
            p.drawRoundedRect(rect, 4, 4)
            for s in lane.segments:
                x0, x1 = self._x(s.t0), self._x(s.t1)
                p.setBrush(QColor(s.color))
                p.drawRect(QRectF(x0, rect.top() + 2, max(x1 - x0, 1.5), rect.height() - 4))
            for t, row, tip in lane.markers:
                x = self._x(t)
                path = QPainterPath()
                path.moveTo(x - 5, rect.top() - 7)
                path.lineTo(x + 5, rect.top() - 7)
                path.lineTo(x, rect.top() + 1)
                path.closeSubpath()
                p.setBrush(QColor("#dc2626"))
                p.drawPath(path)

        # legend
        y = self.TOP + len(self.lanes) * (self.LANE_H + self.LANE_GAP) + 4
        x = float(self.LABEL_W)
        p.setFont(small)
        lang = self.tr_.lang
        legend = [(AXIS_COLORS[s], describe.axis_state_text(s, lang, short=True)) for s in (
            AxisState.SWITCH_ON_DISABLED, AxisState.READY_TO_SWITCH_ON, AxisState.SWITCHED_ON,
            AxisState.OPERATION_ENABLED, AxisState.QUICK_STOP_ACTIVE, AxisState.FAULT)]
        legend += [(NMT_COLORS[s], describe.hb_state_text(s, lang).split(" (")[0]) for s in (0x7F, 0x05, 0x04)]
        for color, label in legend:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawRect(QRectF(x, y + 4, 12, 12))
            p.setPen(text_color)
            w = p.fontMetrics().horizontalAdvance(label) + 28
            p.drawText(QRectF(x + 16, y, w, 20), Qt.AlignVCenter | Qt.AlignLeft, label)
            x += w
            if x > self.width() - 120:
                x = float(self.LABEL_W)
                y += 20
        p.end()

    def mouseMoveEvent(self, ev):
        lane, seg, marker = self._hit(ev.position())
        if marker:
            QToolTip.showText(ev.globalPosition().toPoint(), marker[2], self)
        elif seg:
            QToolTip.showText(ev.globalPosition().toPoint(), f"{seg.label}\n{seg.t0:.3f} s – {seg.t1:.3f} s", self)
        else:
            QToolTip.hideText()

    def mousePressEvent(self, ev):
        lane, seg, marker = self._hit(ev.position())
        if marker:
            self.rowActivated.emit(marker[1])
        elif seg:
            self.rowActivated.emit(seg.row)
