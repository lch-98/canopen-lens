"""The summary page: the verdict, the problems as incidents, the devices, and one
incident at a time in detail.

    verdict card          ✖ 확인이 필요합니다 · 해결 안 됨 3 · 회복 2 · 경고 2 · 정상 1
    incident table        # · 장치 · 무슨 일 · 시각 · 상태       (click a row → detail panel)
    devices / detail      장치 상태 list, replaced by the selected incident's story
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..incidents import Incident, Overview
from ..log import CanopenLog
from . import theme
from .i18n import Tr

COLS = (44, 140, 0, 92, 84)       # #, where, what (stretch), when, status


def _label(text: str = "", *, bold=False, size=1.0, color: Optional[str] = None, wrap=True,
           mono=False, rich=False) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(wrap)
    lab.setTextFormat(Qt.RichText if rich else Qt.PlainText)
    f = theme.mono_font() if mono else lab.font()
    if bold:
        f.setBold(True)
    if size != 1.0:
        f.setPointSizeF(f.pointSizeF() * size)
    lab.setFont(f)
    if color:
        lab.setStyleSheet(f"color:{color}; background: transparent;")
    else:
        lab.setStyleSheet("background: transparent;")
    lab.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
    return lab


class ElideLabel(QLabel):
    """One line of text that ends in … when the column is too narrow (full text on hover)."""

    def __init__(self, text: str = "", *, bold=False, size=1.0, color: Optional[str] = None, parent=None):
        super().__init__(text, parent)
        f = self.font()
        if bold:
            f.setBold(True)
        if size != 1.0:
            f.setPointSizeF(f.pointSizeF() * size)
        self.setFont(f)
        self.setStyleSheet(f"color:{color or theme.TEXT}; background: transparent;")
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setToolTip(text)

    def minimumSizeHint(self):
        return QSize(20, self.fontMetrics().height())

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 4, self.fontMetrics().height() + 2)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setPen(self.palette().windowText().color())
        text = self.fontMetrics().elidedText(self.text(), Qt.ElideRight, self.width())
        p.drawText(self.rect(), Qt.AlignVCenter | Qt.AlignLeft, text)
        p.end()


def _card() -> tuple[QFrame, QVBoxLayout]:
    fr = QFrame()
    fr.setObjectName("card")
    lay = QVBoxLayout(fr)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    return fr, lay


def _pill(text: str, color: str, filled: bool) -> QLabel:
    lab = QLabel(text)
    lab.setAlignment(Qt.AlignCenter)
    f = lab.font()
    f.setBold(True)
    f.setPointSizeF(f.pointSizeF() * 0.88)
    lab.setFont(f)
    if filled:
        lab.setStyleSheet(f"background:{color}; color:white; border-radius:3px; padding:1px 8px;")
    else:
        lab.setStyleSheet(f"background:transparent; color:{color}; border:1px solid {color}; border-radius:3px; padding:0 7px;")
    lab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return lab


class _Row(QFrame):
    """One clickable line of the incident table."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("row")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._selected = False
        self._restyle()

    def set_selected(self, on: bool):
        self._selected = on
        self._restyle()

    def _restyle(self):
        bg = theme.SELECT if self._selected else theme.SURFACE
        self.setStyleSheet(f"#row {{ background:{bg}; border-bottom:1px solid {theme.LINE_SOFT}; }}"
                           f" #row:hover {{ background:{theme.SELECT if self._selected else '#F8FAFC'}; }}")

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.clicked.emit()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(ev)


def _grid_row(cells: list[QWidget], margins=(16, 10, 16, 10)) -> QGridLayout:
    g = QGridLayout()
    g.setContentsMargins(*margins)
    g.setHorizontalSpacing(0)
    for c, (w, cell) in enumerate(zip(COLS, cells)):
        stretch = not w
        g.addWidget(cell, 0, c, Qt.AlignVCenter if stretch else Qt.AlignVCenter | Qt.AlignLeft)
        if w:
            g.setColumnMinimumWidth(c, w)
        else:
            g.setColumnStretch(c, 1)
    return g


class SummaryPage(QWidget):
    showRow = Signal(int)
    showTimeline = Signal(float)
    changed = Signal()              # a device setting changed (EDS, treat as drive): re-analyse

    def __init__(self, tr: Tr, parent=None):
        super().__init__(parent)
        self.tr_ = tr
        self.log: Optional[CanopenLog] = None
        self.ov: Optional[Overview] = None
        self.rows: dict[int, _Row] = {}
        self.selected: Optional[int] = None
        self._warn_rows: list[_Row] = []

        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(20)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)
        lay.addWidget(self.scroll, 1)
        self.side = QStackedWidget()
        self.side.setFixedWidth(330)
        lay.addWidget(self.side)
        self.devices_box = QWidget()
        self.detail_box = QWidget()
        self.side.addWidget(self.devices_box)
        self.side.addWidget(self.detail_box)

    # ------------------------------------------------------------------ building
    def set_log(self, log: Optional[CanopenLog], keep_selection: bool = False) -> None:
        self.log = log
        prev = self.selected if keep_selection else None
        self.selected = None
        self.rows = {}
        self._warn_rows = []
        body = QWidget()
        body.setObjectName("ground")
        col = QVBoxLayout(body)
        col.setContentsMargins(0, 0, 4, 0)
        col.setSpacing(16)
        if log is not None:
            self.ov = log.overview(self.tr_.lang)
            col.addWidget(self._verdict(self.ov))
            if self.ov.looks_like_canopen is False:
                col.addWidget(self._not_canopen(log))
            else:
                col.addWidget(self._incident_table(self.ov))
        col.addStretch(1)
        self.scroll.setWidget(body)
        self._build_devices()
        if prev is not None and self.ov and self.ov.get(prev):
            self.select(prev)
        else:
            self.close_detail()

    def _verdict(self, ov: Overview) -> QFrame:
        tr = self.tr_
        fr = QFrame()
        fr.setObjectName("card")
        row = QHBoxLayout(fr)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        color, _bg = theme.LEVEL[ov.level]
        block = QLabel({"error": "!", "warning": "!", "ok": "✓"}[ov.level])
        block.setAlignment(Qt.AlignCenter)
        f = block.font()
        f.setPointSizeF(f.pointSizeF() * 2.2)
        f.setBold(True)
        block.setFont(f)
        block.setFixedWidth(80)
        block.setStyleSheet(f"background:{color}; color:white; border-top-left-radius:{theme.RADIUS}px;"
                            f" border-bottom-left-radius:{theme.RADIUS}px;")
        row.addWidget(block)
        text = QVBoxLayout()
        text.setContentsMargins(20, 14, 20, 14)
        text.setSpacing(4)
        self.headline = _label(ov.headline, bold=True, size=1.55)
        text.addWidget(self.headline)
        text.addWidget(_label(ov.sentence, color=theme.TEXT_2))
        row.addLayout(text, 1)
        counts = [("open", tr("st_open"), theme.RED), ("recovered", tr("st_recovered"), theme.CYAN),
                  ("warning", tr("st_warning"), theme.AMBER), ("ok", tr("st_ok_devices"), theme.TEXT_2)]
        self.count_labels = {}
        for key, name, c in counts:
            cell = QFrame()
            cell.setStyleSheet(f"border-left:1px solid {theme.LINE_SOFT}; background:transparent;")
            cell.setFixedWidth(92)
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(0, 10, 0, 10)
            cl.setSpacing(0)
            num = _label(str(ov.counts[key]), bold=True, size=1.9, color=c if ov.counts[key] else "#94A3B8", mono=True)
            num.setAlignment(Qt.AlignCenter)
            cap = _label(name, color=theme.TEXT_2, size=0.9)
            cap.setAlignment(Qt.AlignCenter)
            cl.addWidget(num)
            cl.addWidget(cap)
            self.count_labels[key] = num
            row.addWidget(cell)
        return fr

    def _incident_table(self, ov: Overview) -> QFrame:
        tr = self.tr_
        fr, lay = _card()
        head = QFrame()
        head.setObjectName("cardHead")
        head.setLayout(_grid_row([_label(t, bold=True, color=theme.TEXT_2, size=0.9, wrap=False) for t in
                                  ("#", tr("col_where"), tr("col_what"), tr("col_when"), tr("col_status"))],
                                 margins=(16, 7, 16, 7)))
        lay.addWidget(head)
        main = [i for i in ov.incidents if i.status != "warning"]
        warns = ov.by_status("warning")
        if not ov.incidents:
            ok = _label(tr("ov_all_ok"), color=theme.GREEN)
            ok.setContentsMargins(16, 16, 16, 16)
            lay.addWidget(ok)
        for inc in main:
            lay.addWidget(self._row(inc))
        if warns:
            toggle = _Row()
            names = " · ".join((f"{i.where} " if i.node else "") + getattr(i, "short", i.title) for i in warns[:3])
            if len(warns) > 3:
                names += tr("and_more").format(len(warns) - 3)
            self.warn_toggle_label = _label(tr("expand"), bold=True, color=theme.AMBER, size=0.9, wrap=False)
            toggle.setLayout(_grid_row([_label("!", bold=True, color=theme.AMBER, wrap=False),
                                        _label(tr("warnings_n").format(len(warns)), bold=True, color=theme.AMBER, wrap=False),
                                        ElideLabel(names, color="#78350F"), QLabel(""), self.warn_toggle_label]))
            toggle.setStyleSheet(f"#row {{ background:{theme.AMBER_BG}; }}")
            toggle._restyle = lambda: None          # keep the amber band
            toggle.clicked.connect(self._toggle_warnings)
            lay.addWidget(toggle)
            for inc in warns:
                r = self._row(inc)
                r.setVisible(False)
                self._warn_rows.append(r)
                lay.addWidget(r)
        return fr

    def _row(self, inc: Incident) -> _Row:
        tr = self.tr_
        r = _Row()
        color, _ = theme.STATUS[inc.status]
        num = _label(f"{inc.number:02d}", mono=True, color=theme.TEXT_2, wrap=False)
        where = _label(inc.where, bold=True, wrap=False)
        what = QVBoxLayout()
        what.setSpacing(1)
        what.setContentsMargins(0, 0, 12, 0)
        what.addWidget(ElideLabel(inc.title, bold=inc.status == "open"))
        if inc.status == "open":
            what.addWidget(ElideLabel(inc.hint, color=theme.TEXT_2, size=0.92))
        what_w = QWidget()
        what_w.setStyleSheet("background: transparent;")
        what_w.setLayout(what)
        when = _label(f"{inc.t:.2f}" + ("초" if tr.lang == "ko" else " s"), mono=True, color=theme.TEXT_2, wrap=False)
        pill = _pill({"open": tr("pill_open"), "recovered": tr("pill_recovered"), "warning": tr("pill_warning")}[inc.status],
                     color, inc.status == "open")
        r.setLayout(_grid_row([num, where, what_w, when, pill]))
        r.clicked.connect(lambda n=inc.number: self.select(n))
        r.setToolTip(inc.hint)
        self.rows[inc.number] = r
        return r

    def _toggle_warnings(self):
        show = not (self._warn_rows and self._warn_rows[0].isVisible())
        for r in self._warn_rows:
            r.setVisible(show)
        self.warn_toggle_label.setText(self.tr_("collapse") if show else self.tr_("expand"))

    def _not_canopen(self, log: CanopenLog) -> QWidget:
        tr = self.tr_
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(_label(tr("id_stats"), bold=True, size=1.1))
        lay.addWidget(_label(tr("id_stats_hint"), color=theme.TEXT_2))
        rows = log.id_statistics(tr.lang)
        table = QTableWidget(len(rows), 5)
        table.setHorizontalHeaderLabels(["ID", tr("col_count"), tr("col_period"), tr("col_gap"), "DLC"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        for r, d in enumerate(rows):
            vals = [d["id"], f"{d['count']:,}", f"{d['period_ms']:.2f}" if d["period_ms"] else "-",
                    f"{d['max_gap_ms']:.2f}" if d["max_gap_ms"] else "-", d["dlc"]]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if c:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(r, c, item)
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()
        table.setMinimumHeight(min(420, 30 + 24 * max(len(rows), 1)))
        lay.addWidget(table)
        lay.addWidget(_label(tr("assumed_canopen"), color=theme.AMBER))
        return box

    # ------------------------------------------------------------------ devices
    def _build_devices(self):
        tr = self.tr_
        old = self.devices_box.layout()
        if old is not None:
            QWidget().setLayout(old)          # drop the previous layout and its widgets
        outer = QVBoxLayout(self.devices_box)
        outer.setContentsMargins(0, 0, 0, 0)
        fr, lay = _card()
        head = QFrame()
        head.setObjectName("cardHead")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(16, 10, 16, 10)
        hl.addWidget(_label(tr("devices_title"), bold=True))
        lay.addWidget(head)
        body = QGridLayout()
        body.setContentsMargins(16, 6, 8, 10)
        body.setHorizontalSpacing(10)
        body.setVerticalSpacing(2)
        body.setColumnStretch(2, 1)
        if self.ov is not None:
            for r, d in enumerate(self.ov.devices):
                color, _ = theme.STATUS[d.status]
                mark = QLabel()
                mark.setFixedSize(10, 10)
                if d.status == "recovered":
                    mark.setStyleSheet(f"border:2px solid {color}; background:transparent;")
                else:
                    mark.setStyleSheet(f"background:{color};")
                body.addWidget(mark, r, 0, Qt.AlignVCenter)
                body.addWidget(_label(tr("node_n").format(d.node), bold=True, wrap=False), r, 1)
                body.addWidget(_label(d.kind, color=theme.TEXT_2, wrap=False), r, 2)
                body.addWidget(_label(d.status_word, color=color if d.status != "ok" else theme.GREEN, wrap=False), r, 3)
                more = QToolButton()
                more.setText("⋯")
                more.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0; } QToolButton { padding: 0 6px; }")
                more.setAutoRaise(True)
                more.setToolTip(tr("device_menu"))
                more.setAccessibleName(tr("device_menu"))
                more.setPopupMode(QToolButton.InstantPopup)
                more.setMenu(self._device_menu(d.node, more))
                body.addWidget(more, r, 4)
        lay.addLayout(body)
        link = QPushButton(tr("devices_timeline"))
        link.setObjectName("link")
        link.setCursor(Qt.PointingHandCursor)
        link.clicked.connect(lambda: self.showTimeline.emit(-1.0))
        wrap = QHBoxLayout()
        wrap.setContentsMargins(16, 0, 16, 12)
        wrap.addWidget(link)
        wrap.addStretch(1)
        lay.addLayout(wrap)
        outer.addWidget(fr)
        outer.addStretch(1)

    def _device_menu(self, node: int, parent) -> QMenu:
        tr = self.tr_
        log = self.log
        menu = QMenu(parent)
        ni = next((n for n in log.nodes if n.node == node), None) if log else None
        act = menu.addAction(tr("node_treat_drive"))
        act.setCheckable(True)
        act.setChecked(bool(ni and ni.is_drive))
        act.toggled.connect(lambda on, n=node: (self.log.set_drive(n, on), self.changed.emit()))
        eds = log.eds.get(node) if log else None
        if eds:
            menu.addAction(tr("node_eds_remove") + f" ({eds.title})",
                           lambda n=node: (self.log.detach_eds(n), self.changed.emit()))
        else:
            menu.addAction(tr("node_eds"), lambda n=node: self._attach_eds(n))
        return menu

    def _attach_eds(self, node: int):
        path, _ = QFileDialog.getOpenFileName(self, self.tr_("node_eds"), "", self.tr_("eds_filter"))
        if not path:
            return
        try:
            self.log.attach_eds(node, path)
        except Exception as exc:
            QMessageBox.warning(self, self.tr_("load_failed"), str(exc))
            return
        self.changed.emit()

    # ------------------------------------------------------------------ one incident
    def select(self, number: int) -> None:
        if self.ov is None:
            return
        inc = self.ov.get(number)
        if inc is None:
            return
        if inc.status == "warning" and self._warn_rows and not self._warn_rows[0].isVisible():
            self._toggle_warnings()
        for n, r in self.rows.items():
            r.set_selected(n == number)
        self.selected = number
        self._build_detail(inc)
        self.side.setFixedWidth(440)
        self.side.setCurrentWidget(self.detail_box)
        row = self.rows.get(number)
        if row is not None:
            self.scroll.ensureWidgetVisible(row)

    def close_detail(self) -> None:
        for r in self.rows.values():
            r.set_selected(False)
        self.selected = None
        self.side.setFixedWidth(330)
        self.side.setCurrentWidget(self.devices_box)

    def _build_detail(self, inc: Incident) -> None:
        tr = self.tr_
        old = self.detail_box.layout()
        if old is not None:
            QWidget().setLayout(old)
        outer = QVBoxLayout(self.detail_box)
        outer.setContentsMargins(0, 0, 0, 0)
        fr = QFrame()
        fr.setObjectName("card")
        outer.addWidget(fr, 1)
        lay = QVBoxLayout(fr)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)

        top = QHBoxLayout()
        color, _ = theme.STATUS[inc.status]
        top.addWidget(_pill({"open": tr("pill_open"), "recovered": tr("pill_recovered"), "warning": tr("pill_warning")}[inc.status],
                            color, inc.status == "open"))
        top.addWidget(_label(inc.where, color=theme.TEXT_2, wrap=False))
        top.addStretch(1)
        close = QToolButton()
        close.setText("✕")
        close.setAutoRaise(True)
        close.setToolTip(tr("close"))
        close.setAccessibleName(tr("close"))
        close.clicked.connect(self.close_detail)
        top.addWidget(close)
        lay.addLayout(top)
        lay.addWidget(_label(inc.title, bold=True, size=1.25))
        lay.addWidget(_label(inc.hint, color=theme.TEXT_2))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 4, 0, 0)
        il.setSpacing(12)
        if inc.events:
            il.addWidget(_label(tr("what_happened"), bold=True, color=theme.TEXT_2, size=0.92))
            g = QGridLayout()
            g.setHorizontalSpacing(10)
            g.setVerticalSpacing(8)
            g.setColumnStretch(2, 1)
            tone = {"bad": theme.RED, "warn": theme.AMBER, "good": theme.CYAN, "info": theme.TEXT_2}
            for k, e in enumerate(inc.events):
                t = QLabel(f"<a href='{e.row}' style='color:{theme.TEXT_2}; text-decoration:none'>{e.t:.3f} s</a>")
                t.setFont(theme.mono_font(-0.5))
                t.setToolTip(tr("open_message").format(e.row + 1))
                t.linkActivated.connect(lambda href: self.showRow.emit(int(href)))
                g.addWidget(t, k, 0, Qt.AlignTop)
                dot = QLabel()
                dot.setFixedSize(10, 10)
                dot.setStyleSheet(f"background:{tone[e.tone]}; border-radius:5px;")
                g.addWidget(dot, k, 1, Qt.AlignTop | Qt.AlignHCenter)
                g.addWidget(_label(e.text), k, 2)
            il.addLayout(g)
        if inc.steps:
            box = QFrame()
            box.setStyleSheet(f"background:{theme.HEAD}; border-radius:{theme.RADIUS}px;")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(14, 10, 14, 12)
            bl.setSpacing(6)
            bl.addWidget(_label(tr("check_first"), bold=True, color=theme.TEXT_2, size=0.92))
            for k, s in enumerate(inc.steps, 1):
                bl.addWidget(_label(f"{k}. {s}"))
            il.addWidget(box)
        if inc.why:
            il.addWidget(self._fold(tr("why"), _label(inc.why, color=theme.TEXT_2)))
        rows = inc.rows
        links = " ".join(f"<a href='{r}'>#{r + 1}</a>" for r in rows[:12]) + (" …" if len(rows) > 12 else "")
        ev = QLabel(links)
        ev.setTextFormat(Qt.RichText)
        ev.setWordWrap(True)
        ev.setFont(theme.mono_font(-0.5))
        ev.linkActivated.connect(lambda href: self.showRow.emit(int(href)))
        il.addWidget(self._fold(tr("evidence_n").format(len(rows)), ev))
        il.addStretch(1)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        btns = QHBoxLayout()
        b1 = QPushButton(tr("show_frame"))
        b1.setObjectName("primary")
        b1.clicked.connect(lambda: self.showRow.emit(inc.first_row))
        b2 = QPushButton(tr("show_timeline"))
        b2.clicked.connect(lambda: self.showTimeline.emit(float(inc.t)))
        btns.addWidget(b1)
        btns.addWidget(b2)
        btns.addStretch(1)
        lay.addLayout(btns)

    def _fold(self, title: str, content: QWidget) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(6)
        b = QToolButton()
        b.setText(title)
        b.setCheckable(True)
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setArrowType(Qt.RightArrow)
        b.setAutoRaise(True)
        b.setStyleSheet("QToolButton { border:none; padding:2px 0; }")
        content.setVisible(False)

        def flip(on):
            content.setVisible(on)
            b.setArrowType(Qt.DownArrow if on else Qt.RightArrow)

        b.toggled.connect(flip)
        l.addWidget(b)
        l.addWidget(content)
        return w
