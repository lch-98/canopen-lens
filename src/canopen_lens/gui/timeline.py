"""Per-node state timeline: CiA 402 axis state and NMT state from heartbeats.

The visible time range can be zoomed (Ctrl+wheel, dragging over a range, +/-) and
moved (Shift+wheel, horizontal wheel, the scroll bar next to it, arrow keys), so that
states lasting only a few milliseconds can be read and clicked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
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


def format_duration(sec: float) -> str:
    """0.04 -> '40 ms', 1.5 -> '1.50 s', 0.0004 -> '0.40 ms'."""
    sec = abs(sec)
    if sec >= 1.0:
        return f"{sec:.2f} s"
    if sec >= 0.01:
        return f"{sec * 1000:.0f} ms"
    if sec >= 0.001:
        return f"{sec * 1000:.1f} ms"
    return f"{sec * 1000:.2f} ms"


def nice_step(span: float, target: int = 10) -> float:
    """A 1/2/5 x 10^k step that splits `span` into about `target` parts."""
    raw = max(span, 1e-9) / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


class TimelineWidget(QWidget):
    rowActivated = Signal(int)
    viewChanged = Signal(float, float)       # visible start, end (s)
    cursorChanged = Signal(str)              # text describing the state under the keyboard cursor

    LABEL_W = 150
    LANE_H = 26
    LANE_GAP = 10
    TOP = 34
    MIN_SPAN = 0.001                         # cannot zoom in further than 1 ms across the view
    MIN_SEG_PX = 4.0                         # very short states are still drawn (and hit) this wide
    SNAP_PX = 6.0                            # hover/click finds a state this close to the pointer
    DRAG_PX = 5.0                            # moving further than this while pressed selects a range

    def __init__(self, tr: Tr, parent=None):
        super().__init__(parent)
        self.tr_ = tr
        self.log: Optional[CanopenLog] = None
        self.lanes: list[Lane] = []
        self.duration = 1.0
        self.v0, self.v1 = 0.0, 1.0          # visible time range
        self.sel_lane = 0                    # lane used by the keyboard cursor
        self.cursor_t: Optional[float] = None
        self._press = None                   # (x, y) where the left button went down
        self._drag_x: Optional[float] = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    # -- data ------------------------------------------------------------------
    def set_log(self, log: Optional[CanopenLog]) -> None:
        self.log = log
        self.rebuild()

    def rebuild(self) -> None:
        self.lanes = []
        log = self.log
        if log is None or len(log) == 0:
            self.cursor_t = None
            self.update()
            return
        lang = self.tr_.lang
        trace = log.trace
        new_duration = max(trace.duration, 1e-6)
        if abs(new_duration - self.duration) > 1e-9 or self.v1 > new_duration:
            self.v0, self.v1 = 0.0, new_duration        # a different log: show all of it
        self.duration = new_duration
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
        self.sel_lane = min(self.sel_lane, max(len(self.lanes) - 1, 0))
        self.update()
        self.viewChanged.emit(self.v0, self.v1)

    # -- view range ----------------------------------------------------------------
    @property
    def span(self) -> float:
        return self.v1 - self.v0

    def is_zoomed(self) -> bool:
        return self.span < self.duration - 1e-9

    def set_view(self, t0: float, t1: float) -> None:
        """Shows [t0, t1], kept inside the log and no narrower than MIN_SPAN."""
        span = min(max(t1 - t0, self.MIN_SPAN), self.duration)
        t0 = min(max(t0, 0.0), self.duration - span)
        if abs(t0 - self.v0) < 1e-12 and abs(t0 + span - self.v1) < 1e-12:
            return
        self.v0, self.v1 = t0, t0 + span
        self.update()
        self.viewChanged.emit(self.v0, self.v1)

    def fit(self) -> None:
        self.set_view(0.0, self.duration)

    def zoom(self, factor: float, anchor: Optional[float] = None) -> None:
        """factor < 1 zooms in; the time under `anchor` stays where it is on screen."""
        if anchor is None:
            anchor = (self.v0 + self.v1) / 2
        rel = (anchor - self.v0) / self.span if self.span else 0.5
        new_span = min(max(self.span * factor, self.MIN_SPAN), self.duration)
        self.set_view(anchor - rel * new_span, anchor - rel * new_span + new_span)

    def pan(self, fraction: float) -> None:
        """Moves the view by a fraction of its width (negative = earlier)."""
        d = self.span * fraction
        self.set_view(self.v0 + d, self.v1 + d)

    def focus_time(self, t: float, span: float = 2.0) -> None:
        """Zooms to `span` seconds around `t` and puts the keyboard cursor there."""
        span = min(span, self.duration)
        self.set_view(t - span / 2, t + span / 2)
        self.cursor_t = t
        for k, lane in enumerate(self.lanes):
            if any(abs(m[0] - t) < 1e-6 for m in lane.markers):
                self.sel_lane = k
                break
        self._emit_cursor()
        self.update()

    # -- geometry ----------------------------------------------------------------
    def _plot_w(self) -> float:
        return max(self.width() - self.LABEL_W - 20, 10)

    def _x(self, t: float) -> float:
        return self.LABEL_W + (t - self.v0) / self.span * self._plot_w()

    def _t(self, x: float) -> float:
        t = self.v0 + (x - self.LABEL_W) / self._plot_w() * self.span
        return max(0.0, min(self.duration, t))

    def _lane_rect(self, k: int) -> QRectF:
        y = self.TOP + k * (self.LANE_H + self.LANE_GAP)
        return QRectF(self.LABEL_W, y, self._plot_w(), self.LANE_H)

    def _lane_at(self, y: float) -> Optional[int]:
        for k in range(len(self.lanes)):
            rect = self._lane_rect(k)
            if rect.top() - 8 <= y <= rect.bottom():
                return k
        return None

    def _seg_span_px(self, s: Segment) -> tuple[float, float]:
        """Screen extent of a state as drawn (short states get MIN_SEG_PX)."""
        x0, x1 = self._x(s.t0), self._x(s.t1)
        if x1 - x0 < self.MIN_SEG_PX:
            x1 = x0 + self.MIN_SEG_PX
        return x0, x1

    def _segment_at(self, lane: Lane, x: float) -> Optional[Segment]:
        """The state under x; short states win, and a state a few pixels away still counts."""
        visible = [s for s in lane.segments if s.t1 >= self.v0 and s.t0 <= self.v1]
        best, best_d = None, None
        for short_first in (True, False):
            for s in visible:
                x0, x1 = self._seg_span_px(s)
                if short_first != (self._x(s.t1) - self._x(s.t0) < self.MIN_SEG_PX):
                    continue
                if x0 <= x <= x1:
                    return s
        for s in visible:
            x0, x1 = self._seg_span_px(s)
            d = min(abs(x - x0), abs(x - x1))
            if d <= self.SNAP_PX and (best_d is None or d < best_d):
                best, best_d = s, d
        return best

    def _hit(self, pos) -> tuple[Optional[Lane], Optional[Segment], Optional[tuple]]:
        k = self._lane_at(pos.y())
        if k is None or pos.x() < self.LABEL_W:
            return (self.lanes[k] if k is not None else None), None, None
        lane = self.lanes[k]
        rect = self._lane_rect(k)
        for m in lane.markers:
            if self.v0 <= m[0] <= self.v1 and abs(self._x(m[0]) - pos.x()) <= 6 and pos.y() < rect.top() + 6:
                return lane, None, m
        if pos.y() < rect.top():
            return lane, None, None
        return lane, self._segment_at(lane, pos.x()), None

    def segment_text(self, lane: Lane, s: Segment) -> str:
        return (f"{lane.title}\n{s.label}\n{s.t0:.3f} s – {s.t1:.3f} s ({format_duration(s.t1 - s.t0)})")

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

        # time axis: 1/2/5 steps that follow the zoom level
        p.setPen(QPen(QColor("#94a3b8"), 1))
        small = QFont(self.font())
        small.setPointSizeF(max(7.0, small.pointSizeF() - 1))
        p.setFont(small)
        label_px = p.fontMetrics().horizontalAdvance("0000.000s") + 16
        step = nice_step(self.span, max(2, int(self._plot_w() // label_px)))
        decimals = max(0, -int(math.floor(math.log10(step) + 1e-9)))
        t = math.ceil(self.v0 / step - 1e-9) * step
        while t <= self.v1 + 1e-12:
            x = self._x(t)
            p.drawLine(QPointF(x, self.TOP - 8), QPointF(x, self.TOP - 4))
            p.drawText(QRectF(x - 45, 2, 90, self.TOP - 12), Qt.AlignCenter, f"{t:.{decimals}f}s")
            t += step

        p.setFont(self.font())
        plot = QRectF(self.LABEL_W, 0, self._plot_w(), self.height())
        for k, lane in enumerate(self.lanes):
            rect = self._lane_rect(k)
            p.setClipping(False)
            title_font = QFont(self.font())
            title_font.setBold(k == self.sel_lane and self.hasFocus())
            p.setFont(title_font)
            p.setPen(text_color)
            p.drawText(QRectF(4, rect.top(), self.LABEL_W - 10, rect.height()), Qt.AlignVCenter | Qt.AlignLeft, lane.title)
            p.setFont(self.font())
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#f1f5f9"))
            p.drawRoundedRect(rect, 4, 4)
            p.setClipRect(plot.adjusted(-6, 0, 6, 0))
            visible = [s for s in lane.segments if s.t1 >= self.v0 and s.t0 <= self.v1]
            short = []
            for s in visible:
                x0, x1 = self._x(s.t0), self._x(s.t1)
                if x1 - x0 < self.MIN_SEG_PX:
                    short.append(s)
                    continue
                x0, x1 = max(x0, rect.left()), min(x1, rect.right())
                p.setBrush(QColor(s.color))
                p.drawRect(QRectF(x0, rect.top() + 2, x1 - x0, rect.height() - 4))
            for s in short:                       # on top, so a 1 ms state is not hidden
                x0, x1 = self._seg_span_px(s)
                p.setBrush(QColor(s.color))
                p.setPen(QPen(QColor("#334155"), 0.6))
                p.drawRect(QRectF(x0, rect.top() + 2, x1 - x0, rect.height() - 4))
                p.setPen(Qt.NoPen)
            for t, row, tip in lane.markers:
                if not (self.v0 <= t <= self.v1):
                    continue
                x = self._x(t)
                path = QPainterPath()
                path.moveTo(x - 5, rect.top() - 7)
                path.lineTo(x + 5, rect.top() - 7)
                path.lineTo(x, rect.top() + 1)
                path.closeSubpath()
                p.setBrush(QColor("#dc2626"))
                p.drawPath(path)
        p.setClipping(False)

        # keyboard cursor
        if self.cursor_t is not None and self.v0 <= self.cursor_t <= self.v1:
            x = self._x(self.cursor_t)
            p.setPen(QPen(QColor("#0f172a"), 1, Qt.DashLine))
            bottom = self.TOP + len(self.lanes) * (self.LANE_H + self.LANE_GAP) - self.LANE_GAP
            p.drawLine(QPointF(x, self.TOP - 4), QPointF(x, bottom))

        # range being selected with the mouse
        if self._press is not None and self._drag_x is not None:
            a, b = sorted((self._press[0], self._drag_x))
            a, b = max(a, self.LABEL_W), min(b, self.LABEL_W + self._plot_w())
            p.setPen(QPen(QColor("#2563eb"), 1))
            p.setBrush(QColor(37, 99, 235, 40))
            p.drawRect(QRectF(a, self.TOP - 10, b - a,
                              len(self.lanes) * (self.LANE_H + self.LANE_GAP) + 4))
            p.setPen(QColor("#1d4ed8"))
            p.setFont(small)
            p.drawText(QRectF(a, self.TOP - 26, max(b - a, 90), 14), Qt.AlignLeft | Qt.AlignVCenter,
                       format_duration(self._t(b) - self._t(a)))

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

    # -- mouse -------------------------------------------------------------------
    def mouseMoveEvent(self, ev):
        pos = ev.position()
        if self._press is not None:
            if self._drag_x is not None or abs(pos.x() - self._press[0]) > self.DRAG_PX:
                self._drag_x = pos.x()
                QToolTip.hideText()
                self.update()
                return
        lane, seg, marker = self._hit(pos)
        if marker:
            QToolTip.showText(ev.globalPosition().toPoint(), marker[2], self)
        elif seg:
            QToolTip.showText(ev.globalPosition().toPoint(), self.segment_text(lane, seg), self)
        else:
            QToolTip.hideText()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and ev.position().x() >= self.LABEL_W:
            self._press = (ev.position().x(), ev.position().y())
            self._drag_x = None
        k = self._lane_at(ev.position().y())
        if k is not None:
            self.sel_lane = k
            self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.LeftButton or self._press is None:
            return
        press, drag = self._press, self._drag_x
        self._press = self._drag_x = None
        if drag is not None:                       # a range was selected: zoom to it
            a, b = sorted((self._t(press[0]), self._t(drag)))
            self.set_view(a, b)
            self.update()
            return
        lane, seg, marker = self._hit(ev.position())
        if marker:
            self.rowActivated.emit(marker[1])
        elif seg:
            self.rowActivated.emit(seg.row)

    def mouseDoubleClickEvent(self, ev):
        self._press = self._drag_x = None
        self.fit()

    def wheelEvent(self, ev):
        dy, dx = ev.angleDelta().y(), ev.angleDelta().x()
        mods = ev.modifiers()
        if mods & Qt.ControlModifier and dy:
            anchor = self._t(ev.position().x()) if ev.position().x() >= self.LABEL_W else None
            self.zoom(0.8 ** (dy / 120.0), anchor)
            ev.accept()
        elif (mods & Qt.ShiftModifier and dy) or (dx and abs(dx) > abs(dy)):
            if self.is_zoomed():
                self.pan(-(dx or dy) / 120.0 * 0.1)
                ev.accept()
            else:
                ev.ignore()
        else:
            ev.ignore()                            # plain wheel scrolls the lanes up and down

    def event(self, ev):
        # pinch on a touchpad (Windows precision touchpads, macOS)
        if ev.type() == QEvent.NativeGesture and ev.gestureType() == Qt.ZoomNativeGesture:
            anchor = self._t(ev.position().x()) if ev.position().x() >= self.LABEL_W else None
            self.zoom(1.0 / (1.0 + ev.value()) if ev.value() > -0.99 else 2.0, anchor)
            return True
        return super().event(ev)

    # -- keyboard ------------------------------------------------------------------
    def keyPressEvent(self, ev):
        key = ev.key()
        if key in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom(0.5, self.cursor_t)
        elif key == Qt.Key_Minus:
            self.zoom(2.0, self.cursor_t)
        elif key in (Qt.Key_0, Qt.Key_Home):
            self.fit()
        elif key in (Qt.Key_Up, Qt.Key_Down) and self.lanes:
            self.sel_lane = max(0, min(len(self.lanes) - 1, self.sel_lane + (-1 if key == Qt.Key_Up else 1)))
            self._emit_cursor()
            self.update()
        elif key in (Qt.Key_Left, Qt.Key_Right) and self.lanes:
            self.step_change(-1 if key == Qt.Key_Left else 1)
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            seg = self._cursor_segment()
            if seg is not None:
                self.rowActivated.emit(seg.row)
        else:
            super().keyPressEvent(ev)

    def step_change(self, direction: int) -> None:
        """Moves the keyboard cursor to the previous/next state change of the selected lane."""
        lane = self.lanes[self.sel_lane]
        starts = sorted({s.t0 for s in lane.segments})
        if not starts:
            return
        cur = self.cursor_t if self.cursor_t is not None else (self.v0 if direction > 0 else self.v1)
        if direction > 0:
            nxt = [t for t in starts if t > cur + 1e-9]
            target = nxt[0] if nxt else starts[-1]
        else:
            prv = [t for t in starts if t < cur - 1e-9]
            target = prv[-1] if prv else starts[0]
        self.cursor_t = target
        if not (self.v0 <= target <= self.v1):
            self.set_view(target - self.span / 2, target + self.span / 2)
        self._emit_cursor()
        self.update()

    def _cursor_segment(self) -> Optional[Segment]:
        if self.cursor_t is None or not self.lanes:
            return None
        for s in self.lanes[self.sel_lane].segments:
            if s.t0 - 1e-9 <= self.cursor_t < s.t1 or (s.t0 == s.t1 == self.cursor_t):
                return s
        return None

    def _emit_cursor(self) -> None:
        seg = self._cursor_segment()
        if seg is None or not self.lanes:
            self.cursorChanged.emit("")
            return
        lane = self.lanes[self.sel_lane]
        self.cursorChanged.emit(self.tr_("timeline_cursor").format(
            lane=lane.title, state=seg.label, t=f"{seg.t0:.3f}", dur=format_duration(seg.t1 - seg.t0)))
