"""The overview page: verdict, status of each node, and what to check first."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import describe
from .._core import Severity
from ..explain import HealthSummary
from ..log import CanopenLog
from .i18n import Tr

LEVEL_COLORS = {
    "ok": ("#16a34a", "#f0fdf4", "✔"),
    "warning": ("#d97706", "#fffbeb", "▲"),
    "error": ("#dc2626", "#fef2f2", "✖"),
}
SEV_LEVEL = {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.INFO: "ok"}


def _label(text: str, *, bold=False, size=1.0, color: Optional[str] = None, wrap=True, rich=False) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(wrap)
    lab.setTextFormat(Qt.RichText if rich else Qt.PlainText)
    lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    f = lab.font()
    if bold:
        f.setBold(True)
    if size != 1.0:
        f.setPointSizeF(f.pointSizeF() * size)
    lab.setFont(f)
    if color:
        lab.setStyleSheet(f"color:{color};")
    lab.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    return lab


def _card(border: str, background: str = "palette(base)") -> tuple[QFrame, QVBoxLayout]:
    fr = QFrame()
    fr.setObjectName("card")
    fr.setStyleSheet(f"#card {{ border:1px solid {border}; border-radius:10px; background:{background}; }}")
    lay = QVBoxLayout(fr)
    lay.setContentsMargins(16, 12, 16, 12)
    lay.setSpacing(6)
    return fr, lay


class OverviewPage(QScrollArea):
    showRow = Signal(int)
    showTimeline = Signal()

    def __init__(self, tr: Tr, parent=None):
        super().__init__(parent)
        self.tr_ = tr
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)

    def set_log(self, log: Optional[CanopenLog]) -> None:
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)
        if log is not None:
            h = log.health(self.tr_.lang)
            self._verdict(lay, h)
            self._nodes(lay, h)
            self._findings(lay, log, h)
        lay.addStretch(1)
        self.setWidget(body)

    # ------------------------------------------------------------------ sections
    def _verdict(self, lay: QVBoxLayout, h: HealthSummary) -> None:
        fg, bg, icon = LEVEL_COLORS[h.level]
        fr, cl = _card(fg, bg)
        row = QHBoxLayout()
        badge = _label(icon, bold=True, size=2.2, color=fg, wrap=False)
        badge.setFixedWidth(48)
        badge.setAlignment(Qt.AlignCenter)
        row.addWidget(badge)
        col = QVBoxLayout()
        col.addWidget(_label(h.headline, bold=True, size=1.35, color=fg))
        col.addWidget(_label(h.overview, color="#475569"))
        row.addLayout(col, 1)
        cl.addLayout(row)
        lay.addWidget(fr)

    def _nodes(self, lay: QVBoxLayout, h: HealthSummary) -> None:
        lay.addWidget(_label(self.tr_("ov_nodes"), bold=True, size=1.15))
        grid = QGridLayout()
        grid.setSpacing(10)
        cols = 2
        for k, n in enumerate(h.nodes):
            fg, bg, icon = LEVEL_COLORS[n.level]
            fr, cl = _card("#e2e8f0")
            fr.setStyleSheet(fr.styleSheet() + f" #card {{ border-left: 5px solid {fg}; }}")
            cl.addWidget(_label(f"{icon}  {n.headline}", bold=True, color=fg if n.level != "ok" else None))
            for d in n.details:
                cl.addWidget(_label(f"• {d}", color="#334155"))
            cl.addStretch(1)
            grid.addWidget(fr, k // cols, k % cols)
        for c in range(cols):
            grid.setColumnStretch(c, 1)
        lay.addLayout(grid)

    def _findings(self, lay: QVBoxLayout, log: CanopenLog, h: HealthSummary) -> None:
        tr = self.tr_
        lang = tr.lang
        todo = [g for g in h.groups if g.severity != Severity.INFO]
        info = [g for g in h.groups if g.severity == Severity.INFO]
        lay.addWidget(_label(tr("ov_todo"), bold=True, size=1.15))
        if not todo:
            fr, cl = _card("#bbf7d0", "#f0fdf4")
            cl.addWidget(_label(tr("ov_none"), color="#166534"))
            lay.addWidget(fr)
        else:
            lay.addWidget(_label(tr("ov_todo_hint"), color="#64748b"))
        for k, g in enumerate(todo, 1):
            lay.addWidget(self._finding_card(log, g, k, lang))
        if info:
            lay.addWidget(_label(tr("ov_info"), bold=True, size=1.05))
            for g in info:
                ex = log.explain(g.first, lang)
                lay.addWidget(_label(f"ℹ  {ex.title} — {ex.what}", color="#475569"))

    def _finding_card(self, log: CanopenLog, g, number: int, lang: str) -> QFrame:
        tr = self.tr_
        ex = log.explain(g.first, lang)
        fg, bg, icon = LEVEL_COLORS[SEV_LEVEL[g.severity]]
        fr, cl = _card("#e2e8f0")
        fr.setStyleSheet(fr.styleSheet() + f" #card {{ border-left: 5px solid {fg}; }}")
        sev = describe.severity_text(g.severity, lang)
        cl.addWidget(_label(f"{number}. [{sev}] {ex.title}", bold=True, size=1.08, color=fg))
        when = (tr("times").format(g.count, g.t_first, g.t_last) if g.count > 1
                else tr("time_once").format(g.t_first))
        cl.addWidget(_label(when, color="#64748b"))

        cl.addWidget(_label(tr("what"), bold=True))
        cl.addWidget(_label(ex.what))
        if ex.why:
            cl.addWidget(_label(tr("why"), bold=True))
            cl.addWidget(_label(ex.why))
        if ex.steps:
            cl.addWidget(_label(tr("steps"), bold=True))
            for s_i, step in enumerate(ex.steps, 1):
                cl.addWidget(_label(f"  {s_i}. {step}"))

        btns = QHBoxLayout()
        b1 = QPushButton(tr("show_frame"))
        b1.setStyleSheet("QPushButton { background:#2563eb; color:white; border-radius:6px; padding:5px 14px; }")
        row = g.first.row
        b1.clicked.connect(lambda _=False, r=row: self.showRow.emit(r))
        btns.addWidget(b1)
        b2 = QPushButton(tr("show_timeline"))
        b2.clicked.connect(lambda _=False: self.showTimeline.emit())
        btns.addWidget(b2)
        btns.addStretch(1)
        cl.addLayout(btns)
        return fr
