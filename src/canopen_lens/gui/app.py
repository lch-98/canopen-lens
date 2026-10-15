"""Main window of the CANopen Lens GUI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableView,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, describe
from .._core import Kind, Severity
from ..log import CanopenLog
from .i18n import Tr
from .models import KIND_COLORS, FrameTableModel
from .timeline import TimelineWidget

SAMPLE_LOG = Path(__file__).resolve().parent.parent / "examples" / "sample_cia402.log"

SEV_STYLE = {
    Severity.ERROR: ("●", "#dc2626"),
    Severity.WARNING: ("▲", "#d97706"),
    Severity.INFO: ("ℹ", "#2563eb"),
}

FILTER_KINDS = [
    ("PDO", [Kind.TPDO, Kind.RPDO]),
    ("SDO", [Kind.SDO_REQ, Kind.SDO_RESP]),
    ("EMCY", [Kind.EMCY]),
    ("NMT", [Kind.NMT]),
    ("HB", [Kind.HEARTBEAT]),
    ("SYNC", [Kind.SYNC, Kind.TIME]),
    ("ETC", [Kind.LSS, Kind.ERROR_FRAME, Kind.UNKNOWN]),
]


class _Loader(QObject):
    done = Signal(object, str)
    failed = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):
        try:
            log = CanopenLog.open(self.path)
            self.done.emit(log, self.path)
        except Exception as exc:  # pragma: no cover - surfaced to the user
            self.failed.emit(str(exc))


class DropArea(QFrame):
    fileDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        urls = ev.mimeData().urls()
        if urls:
            self.fileDropped.emit(urls[0].toLocalFile())


class StatCard(QFrame):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setStyleSheet(f"#statCard {{ border: 1px solid #e2e8f0; border-radius: 8px; background: palette(base); }}"
                           f" QLabel#value {{ color: {color}; }}")
        self.setMinimumWidth(96)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(0)
        self.value = QLabel("0")
        self.value.setObjectName("value")
        f = self.value.font()
        f.setPointSizeF(f.pointSizeF() * 1.8)
        f.setBold(True)
        self.value.setFont(f)
        self.caption = QLabel("")
        self.caption.setStyleSheet("color: #64748b;")
        lay.addWidget(self.value)
        lay.addWidget(self.caption)


class NodeCard(QFrame):
    changed = Signal()
    jump = Signal(int)

    def __init__(self, win: "MainWindow", ni, parent=None):
        super().__init__(parent)
        self.win = win
        self.node = ni.node
        tr = win.tr_
        lang = tr.lang
        log = win.log
        self.setObjectName("nodeCard")
        self.setStyleSheet("#nodeCard { border: 1px solid #e2e8f0; border-radius: 8px; background: palette(base); }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)

        head = QHBoxLayout()
        title = QLabel(f"<b>{tr('col_node')} {ni.node}</b>")
        f = title.font()
        f.setPointSizeF(f.pointSizeF() * 1.2)
        title.setFont(f)
        head.addWidget(title)
        kind = tr("node_drive") if ni.is_drive else tr("node_generic")
        badge = QLabel(kind)
        badge.setStyleSheet("background: %s; color: white; border-radius: 4px; padding: 1px 6px;"
                            % ("#0f766e" if ni.is_drive else "#64748b"))
        head.addWidget(badge)
        head.addStretch(1)
        lay.addLayout(head)

        problems = [i for i in log.issues if i.node == ni.node and i.severity != Severity.INFO]
        lines = []
        if ni.last_hb_state >= 0:
            lines.append((tr("node_nmt"), describe.hb_state_text(ni.last_hb_state, lang)))
        else:
            lines.append((tr("node_nmt"), tr("node_none_hb")))
        if ni.hb_period:
            lines.append((tr("node_hb"), f"{ni.hb_period * 1000:.0f} ms"))
        if ni.is_drive:
            states = list(ni.axis_states) or [ni.axis_state]
            if len(states) > 1:
                lines.append((tr("node_axes"), str(len(states))))
                for k, state in enumerate(states):
                    lines.append((tr("node_axis_n").format(k + 1), describe.axis_state_text(state, lang)))
            else:
                lines.append((tr("node_axis"), describe.axis_state_text(states[0], lang)))
        if ni.device_type_known:
            profile = ni.device_type & 0xFFFF
            lines.append((tr("node_device_type"), f"0x{ni.device_type:08X} (CiA {profile})"))
        top = sorted(ni.kind_counts.items(), key=lambda kv: -kv[1])[:3]
        counts = ", ".join(f"{describe.kind_label(k, lang)} {v:,}" for k, v in top)
        lines.append((tr("node_counts"), f"{ni.frame_count:,} ({counts})"))
        lines.append((tr("node_problems"), str(len(problems))))
        eds = log.eds.get(ni.node)
        lines.append(("EDS", eds.title if eds else tr("node_eds_none")))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(3)
        grid.setColumnStretch(1, 1)
        for r, (k, v) in enumerate(lines):
            key = QLabel(k)
            key.setStyleSheet("color:#64748b;")
            key.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            val = QLabel(v)
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if k == tr("node_problems") and problems:
                val.setStyleSheet("color:#dc2626; font-weight:bold;")
            grid.addWidget(key, r, 0)
            grid.addWidget(val, r, 1)
        lay.addLayout(grid)

        row = QHBoxLayout()
        self.drive_box = QCheckBox(tr("node_treat_drive"))
        self.drive_box.setChecked(ni.is_drive)
        self.drive_box.toggled.connect(self._toggle_drive)
        row.addWidget(self.drive_box)
        row.addStretch(1)
        eds_btn = QPushButton(tr("node_eds_remove") if eds else tr("node_eds"))
        eds_btn.clicked.connect(self._eds_clicked)
        row.addWidget(eds_btn)
        lay.addLayout(row)

    def _toggle_drive(self, on: bool):
        self.win.log.set_drive(self.node, on)
        self.changed.emit()

    def _eds_clicked(self):
        log = self.win.log
        if self.node in log.eds:
            log.detach_eds(self.node)
            self.changed.emit()
            return
        path, _ = QFileDialog.getOpenFileName(self, self.win.tr_("node_eds"), "", self.win.tr_("eds_filter"))
        if not path:
            return
        try:
            log.attach_eds(self.node, path)
        except Exception as exc:
            QMessageBox.warning(self, self.win.tr_("load_failed"), str(exc))
            return
        self.changed.emit()


class MainWindow(QMainWindow):
    def __init__(self, lang: str = "ko"):
        super().__init__()
        self.tr_ = Tr(lang)
        self.log: Optional[CanopenLog] = None
        self.path: Optional[str] = None
        self._thread: Optional[QThread] = None
        self.resize(1360, 860)
        self.setAcceptDrops(True)
        self._build()
        self._retranslate()

    # ------------------------------------------------------------------ layout
    def _build(self):
        tb = self.addToolBar("main")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.act_open = QAction(self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self.open_dialog)
        tb.addAction(self.act_open)
        self.act_sample = QAction(self)
        self.act_sample.triggered.connect(lambda: self.load(str(SAMPLE_LOG)))
        tb.addAction(self.act_sample)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        self.act_lang = QAction(self)
        self.act_lang.triggered.connect(self.toggle_language)
        tb.addAction(self.act_lang)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # --- welcome page
        self.drop = DropArea()
        self.drop.fileDropped.connect(self.load)
        dl = QVBoxLayout(self.drop)
        dl.addStretch(2)
        self.drop_title = QLabel()
        f = self.drop_title.font()
        f.setPointSizeF(f.pointSizeF() * 1.7)
        f.setBold(True)
        self.drop_title.setFont(f)
        self.drop_title.setAlignment(Qt.AlignCenter)
        dl.addWidget(self.drop_title)
        self.drop_sub = QLabel()
        self.drop_sub.setAlignment(Qt.AlignCenter)
        self.drop_sub.setStyleSheet("color: #64748b;")
        dl.addWidget(self.drop_sub)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_open = QPushButton()
        self.btn_open.setMinimumHeight(40)
        self.btn_open.setStyleSheet("QPushButton { background:#2563eb; color:white; border-radius:6px; padding:6px 22px; font-weight:bold; }")
        self.btn_open.clicked.connect(self.open_dialog)
        btns.addWidget(self.btn_open)
        self.btn_sample = QPushButton()
        self.btn_sample.setMinimumHeight(40)
        self.btn_sample.clicked.connect(lambda: self.load(str(SAMPLE_LOG)))
        btns.addWidget(self.btn_sample)
        btns.addStretch(1)
        dl.addSpacing(18)
        dl.addLayout(btns)
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        dl.addSpacing(10)
        dl.addWidget(self.status_label)
        dl.addStretch(3)
        self.drop.setStyleSheet("DropArea { border: 2px dashed #94a3b8; border-radius: 16px; margin: 40px; }")
        self.stack.addWidget(self.drop)

        # --- analysis page
        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(10, 8, 10, 8)

        head = QHBoxLayout()
        self.file_label = QLabel()
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        head.addWidget(self.file_label, 1)
        self.card_err = StatCard("#dc2626")
        self.card_warn = StatCard("#d97706")
        self.card_nodes = StatCard("#0f766e")
        for c in (self.card_err, self.card_warn, self.card_nodes):
            head.addWidget(c)
        pl.addLayout(head)

        split = QSplitter(Qt.Horizontal)
        pl.addWidget(split, 1)

        # left: diagnosis + nodes
        self.left_tabs = QTabWidget()
        self.issue_list = QListWidget()
        self.issue_list.setWordWrap(True)
        self.issue_list.setSpacing(2)
        self.issue_list.currentItemChanged.connect(self._issue_selected)
        self.left_tabs.addTab(self.issue_list, "")
        self.node_scroll = QScrollArea()
        self.node_scroll.setWidgetResizable(True)
        self.node_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.left_tabs.setMinimumWidth(300)
        self.left_tabs.addTab(self.node_scroll, "")
        split.addWidget(self.left_tabs)

        # center: frames + timeline
        self.center_tabs = QTabWidget()
        frames_page = QWidget()
        fl = QVBoxLayout(frames_page)
        fl.setContentsMargins(0, 4, 0, 0)
        bar = QHBoxLayout()
        self.kind_buttons: list[tuple[QToolButton, list]] = []
        for label, kinds in FILTER_KINDS:
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)
            b.setChecked(True)
            color = KIND_COLORS[kinds[0]]
            b.setStyleSheet(f"QToolButton {{ border:1px solid {color}; border-radius:10px; padding:2px 8px; color:{color}; }}"
                            f" QToolButton:checked {{ background:{color}; color:white; }}")
            b.toggled.connect(self.apply_filter)
            bar.addWidget(b)
            self.kind_buttons.append((b, kinds))
        bar.addStretch(1)
        fl.addLayout(bar)
        bar = QHBoxLayout()
        self.node_combo = QComboBox()
        self.node_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.node_combo.currentIndexChanged.connect(self.apply_filter)
        bar.addWidget(self.node_combo)
        self.index_edit = QLineEdit()
        self.index_edit.setMinimumWidth(170)
        self.index_edit.setMaximumWidth(200)
        self.index_edit.setClearButtonEnabled(True)
        self.index_edit.textChanged.connect(lambda _: self._filter_timer.start(250))
        bar.addWidget(self.index_edit)
        self.issues_only = QCheckBox()
        self.issues_only.toggled.connect(self.apply_filter)
        bar.addWidget(self.issues_only)
        bar.addStretch(1)
        self.count_label = QLabel()
        self.count_label.setStyleSheet("color:#64748b;")
        bar.addWidget(self.count_label)
        fl.addLayout(bar)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self.apply_filter)

        self.model = FrameTableModel(self.tr_)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        hh = self.table.horizontalHeader()
        for col, w in enumerate([58, 84, 44, 86, 430, 80]):
            hh.resizeSection(col, w)
        hh.setStretchLastSection(True)
        hh.setSectionResizeMode(QHeaderView.Interactive)
        self.table.selectionModel().currentRowChanged.connect(self._frame_selected)
        fl.addWidget(self.table, 1)
        self.center_tabs.addTab(frames_page, "")

        tl_page = QWidget()
        tll = QVBoxLayout(tl_page)
        self.timeline_hint = QLabel()
        self.timeline_hint.setStyleSheet("color:#64748b;")
        tll.addWidget(self.timeline_hint)
        self.timeline = TimelineWidget(self.tr_)
        self.timeline.rowActivated.connect(self.goto_row)
        tl_scroll = QScrollArea()
        tl_scroll.setWidgetResizable(True)
        tl_scroll.setWidget(self.timeline)
        tll.addWidget(tl_scroll, 1)
        self.center_tabs.addTab(tl_page, "")
        split.addWidget(self.center_tabs)

        # right: explanation
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)
        self.detail_title = QLabel()
        f = self.detail_title.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() * 1.15)
        self.detail_title.setFont(f)
        self.detail_title.setWordWrap(True)
        self.detail_title.setMinimumWidth(1)
        rl.addWidget(self.detail_title)
        self.detail = QTextBrowser()
        self.detail.setOpenLinks(False)
        self.detail.anchorClicked.connect(lambda url: self.goto_row(int(url.toString().split(":")[1])))
        rl.addWidget(self.detail, 1)
        split.addWidget(right)

        split.setSizes([320, 780, 340])
        split.setStretchFactor(1, 1)
        self.stack.addWidget(page)

    # ------------------------------------------------------------------ i18n
    def _retranslate(self):
        tr = self.tr_
        self.setWindowTitle(f"{tr('app_title')} {__version__}" + (f" – {Path(self.path).name}" if self.path else ""))
        self.act_open.setText(tr("open"))
        self.act_sample.setText(tr("open_sample"))
        self.act_lang.setText(tr("language"))
        self.drop_title.setText(tr("drop_title"))
        self.drop_sub.setText(tr("drop_sub"))
        self.btn_open.setText(tr("open"))
        self.btn_sample.setText(tr("open_sample"))
        self.left_tabs.setTabText(0, tr("tab_issues"))
        self.left_tabs.setTabText(1, tr("tab_nodes"))
        self.center_tabs.setTabText(0, tr("tab_frames"))
        self.center_tabs.setTabText(1, tr("tab_timeline"))
        self.index_edit.setPlaceholderText(tr("filter_index"))
        self.issues_only.setText(tr("filter_issues"))
        self.card_err.caption.setText(tr("errors"))
        self.card_warn.caption.setText(tr("warnings"))
        self.card_nodes.caption.setText(tr("nodes"))
        self.timeline_hint.setText(tr("timeline_hint"))
        self.detail_title.setText(tr("details"))
        self.model.headerDataChanged.emit(Qt.Horizontal, 0, self.model.columnCount() - 1)
        if self.log is None:
            self.detail.setPlainText(tr("select_frame"))

    def toggle_language(self):
        self.tr_.lang = "en" if self.tr_.lang == "ko" else "ko"
        self._retranslate()
        if self.log is not None:
            self.model.clear_cache()
            self.refresh_all(keep_selection=True)

    # ------------------------------------------------------------------ loading
    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr_("open"), "", self.tr_("log_filter"))
        if path:
            self.load(path)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        urls = ev.mimeData().urls()
        if urls:
            self.load(urls[0].toLocalFile())

    def load(self, path: str):
        if self._thread is not None:
            return
        self.status_label.setText(self.tr_("loading"))
        self.statusBar().showMessage(self.tr_("loading"))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self._thread = QThread(self)
        self._loader = _Loader(path)
        self._loader.moveToThread(self._thread)
        self._thread.started.connect(self._loader.run)
        self._loader.done.connect(self._loaded)
        self._loader.failed.connect(self._load_failed)
        self._thread.start()

    def _finish_thread(self):
        QApplication.restoreOverrideCursor()
        self._thread.quit()
        self._thread.wait()
        self._thread = None
        self.status_label.setText("")
        self.statusBar().clearMessage()

    def _load_failed(self, msg: str):
        self._finish_thread()
        QMessageBox.critical(self, self.tr_("load_failed"), msg)

    def _loaded(self, log: CanopenLog, path: str):
        self._finish_thread()
        if len(log) == 0:
            QMessageBox.warning(self, self.tr_("load_failed"), self.tr_("no_frames"))
            return
        self.set_log(log, path)

    def set_log(self, log: CanopenLog, path: Optional[str] = None):
        self.log = log
        self.path = path
        self.stack.setCurrentIndex(1)
        self._retranslate()
        self.refresh_all()
        # start on the first real problem if there is one
        for k in range(self.issue_list.count()):
            item = self.issue_list.item(k)
            if item.data(Qt.UserRole + 1) != int(Severity.INFO):
                self.issue_list.setCurrentRow(k)
                break

    # ------------------------------------------------------------------ refresh
    def refresh_all(self, keep_selection: bool = False):
        log = self.log
        tr = self.tr_
        current = self.current_frame_row() if keep_selection else None
        name = Path(self.path).name if self.path else "-"
        fmt = log.trace.format
        self.file_label.setText(
            f"<b>{name}</b><br><span style='color:#64748b'>{len(log):,} {tr('frames')} · "
            f"{tr('duration')} {log.trace.duration:.3f} s · {fmt} · {', '.join(log.trace.interfaces)}</span>")
        counts = log.count_issues()
        self.card_err.value.setText(str(counts[Severity.ERROR]))
        self.card_warn.value.setText(str(counts[Severity.WARNING]))
        self.card_nodes.value.setText(str(len(log.nodes)))

        self.node_combo.blockSignals(True)
        prev = self.node_combo.currentData()
        self.node_combo.clear()
        self.node_combo.addItem(tr("filter_all_nodes"), -1)
        for ni in log.nodes:
            self.node_combo.addItem(f"{tr('col_node')} {ni.node}", ni.node)
        idx = self.node_combo.findData(prev) if prev is not None else 0
        self.node_combo.setCurrentIndex(max(idx, 0))
        self.node_combo.blockSignals(False)

        self._fill_issues()
        self._fill_nodes()
        self.model.set_log(log, None)
        self.apply_filter()
        self.timeline.set_log(log)
        if current is not None:
            self.goto_row(current)

    def _fill_issues(self):
        self.issue_list.blockSignals(True)
        self.issue_list.clear()
        lang = self.tr_.lang
        issues = sorted(self.log.issues, key=lambda i: (-int(i.severity), i.t))
        if not issues:
            item = QListWidgetItem(self.tr_("no_issues"))
            item.setFlags(Qt.NoItemFlags)
            self.issue_list.addItem(item)
        for issue in issues:
            title, _ = self.log.issue_text(issue, lang)
            icon, color = SEV_STYLE[issue.severity]
            item = QListWidgetItem(f"{icon}  {title}\n      {issue.t:.3f} s")
            item.setForeground(QColor(color) if issue.severity == Severity.ERROR else self.palette().text().color())
            item.setData(Qt.UserRole, issue)
            item.setData(Qt.UserRole + 1, int(issue.severity))
            self.issue_list.addItem(item)
        self.issue_list.blockSignals(False)

    def _fill_nodes(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(4, 4, 4, 4)
        for ni in self.log.nodes:
            card = NodeCard(self, ni)
            card.changed.connect(lambda: QTimer.singleShot(0, lambda: self.refresh_all(keep_selection=True)))
            lay.addWidget(card)
        lay.addStretch(1)
        self.node_scroll.setWidget(box)

    # ------------------------------------------------------------------ filtering
    def apply_filter(self, *_):
        if self.log is None:
            return
        kinds = [k for b, ks in self.kind_buttons if b.isChecked() for k in ks]
        node = self.node_combo.currentData()
        node = -1 if node is None else int(node)
        text = self.index_edit.text().strip().lower().replace("0x", "")
        index = -1
        if text:
            try:
                index = int(text.split(":")[0], 16)
            except ValueError:
                index = -1
        current = self.current_frame_row()
        rows = self.log.trace.filter(kinds=kinds, node=node, issues_only=self.issues_only.isChecked(), index=index)
        self.model.set_rows(rows)
        self.count_label.setText(f"{len(rows):,} / {len(self.log):,} {self.tr_('shown')}")
        if current is not None:
            vr = self.model.nearest_view_row(current)
            if vr is not None:
                self.table.selectRow(vr)
                self.table.scrollTo(self.model.index(vr, 0), QAbstractItemView.PositionAtCenter)

    def current_frame_row(self) -> Optional[int]:
        idx = self.table.selectionModel().currentIndex()
        if not idx.isValid() or idx.row() >= self.model.rowCount():
            return None
        return self.model.frame_row(idx.row())

    def goto_row(self, frame_row: int):
        if self.log is None:
            return
        vr = self.model.view_row_of(frame_row)
        if vr is None:
            # the frame is hidden by a filter: show everything again
            for b, _ in self.kind_buttons:
                b.blockSignals(True)
                b.setChecked(True)
                b.blockSignals(False)
            self.node_combo.blockSignals(True)
            self.node_combo.setCurrentIndex(0)
            self.node_combo.blockSignals(False)
            self.issues_only.blockSignals(True)
            self.issues_only.setChecked(False)
            self.issues_only.blockSignals(False)
            self.index_edit.blockSignals(True)
            self.index_edit.clear()
            self.index_edit.blockSignals(False)
            self.apply_filter()
            vr = self.model.view_row_of(frame_row)
        if vr is None:
            return
        self.center_tabs.setCurrentIndex(0)
        self.table.selectRow(vr)
        self.table.scrollTo(self.model.index(vr, 0), QAbstractItemView.PositionAtCenter)
        self.table.setFocus()

    # ------------------------------------------------------------------ details
    def _frame_selected(self, current, _previous):
        if self.log is None or not current.isValid():
            return
        row = self.model.frame_row(current.row())
        tr = self.tr_
        lang = tr.lang
        rows = self.log.details(row, lang)
        self.detail_title.setText(f"#{row + 1} · {self.log.summary(row, lang)[:60]}")
        html = ["<table cellspacing='0' cellpadding='4' width='100%'>"]
        for k, v in rows:
            html.append(f"<tr><td valign='top' width='38%' style='color:#64748b'>{_esc(k)}</td><td valign='top'>{_esc(v)}</td></tr>")
        html.append("</table>")
        related = [i for i in self.log.issues if i.row == row]
        for issue in related:
            title, text = self.log.issue_text(issue, lang)
            _, color = SEV_STYLE[issue.severity]
            html.append(f"<hr><p style='color:{color}'><b>{_esc(title)}</b></p><p>{_esc(text)}</p>")
        self.detail.setHtml("".join(html))

    def _issue_selected(self, item, _prev):
        if item is None or self.log is None:
            return
        issue = item.data(Qt.UserRole)
        if issue is None:
            return
        tr = self.tr_
        title, text = self.log.issue_text(issue, tr.lang)
        _, color = SEV_STYLE[issue.severity]
        sev = describe.severity_text(issue.severity, tr.lang)
        html = [f"<p style='color:{color}'><b>[{sev}] {_esc(title)}</b></p>",
                f"<p>{_esc(text)}</p>",
                f"<p><a href='row:{issue.row}'>▶ {tr('go_to_frame')} (#{issue.row + 1}, {issue.t:.3f} s)</a></p>"]
        if issue.related_row is not None:
            html.append(f"<p><a href='row:{issue.related_row}'>▶ {tr('go_to_related')} (#{issue.related_row + 1})</a></p>")
        self.goto_row(issue.row)
        self.detail_title.setText(tr("details"))
        self.detail.setHtml("".join(html))
        self.issue_list.setFocus()


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")).replace("\n", "<br>")


def _apply_style(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = app.palette()
    if pal.color(QPalette.Window).lightness() > 128:
        pal.setColor(QPalette.Window, QColor("#f8fafc"))
        pal.setColor(QPalette.AlternateBase, QColor("#f8fafc"))
        pal.setColor(QPalette.Highlight, QColor("#2563eb"))
        app.setPalette(pal)
    font = app.font()
    if sys.platform.startswith("win"):
        font.setFamily("Malgun Gothic")
    font.setPointSizeF(max(font.pointSizeF(), 10.0))
    app.setFont(font)


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    lang = "ko"
    files = []
    for a in argv[1:]:
        if a in ("--en", "--lang=en"):
            lang = "en"
        elif a in ("--ko", "--lang=ko"):
            lang = "ko"
        elif not a.startswith("-"):
            files.append(a)
    app = QApplication.instance() or QApplication(argv[:1])
    app.setApplicationName("CANopen Lens")
    _apply_style(app)
    win = MainWindow(lang)
    win.show()
    if files:
        win.load(files[0])
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
