"""Main window of the CANopen Lens GUI."""

from __future__ import annotations

import sys
import time
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
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QScrollBar,
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
from ..explain import GLOSSARY
from ..log import CanopenLog
from .dialogs import glossary_dialog, help_dialog
from .i18n import Tr
from .models import KIND_COLORS, FrameTableModel
from .live_page import LivePage
from . import theme
from .summary import SummaryPage
from .timeline import TimelineWidget

# pages of the main area, in the order of the navigation bar
OVERVIEW_TAB, FRAMES_TAB, TIMELINE_TAB, LIVE_TAB = 0, 1, 2, 3

EXAMPLE_DIR = Path(__file__).resolve().parent.parent / "examples"
SAMPLE_LOG = EXAMPLE_DIR / "sample_cia402.log"
# (file, i18n key) shown under "Try the sample log"
EXAMPLES = [("sample_cia402.log", "example_mixed"), ("sample_amr_2wheel.log", "example_amr")]

# (label key, kinds, glossary term used as tooltip)
FILTER_KINDS = [
    ("chip_pdo", [Kind.TPDO, Kind.RPDO], "PDO (TPDO / RPDO)"),
    ("chip_sdo", [Kind.SDO_REQ, Kind.SDO_RESP], "SDO"),
    ("chip_emcy", [Kind.EMCY], "EMCY"),
    ("chip_nmt", [Kind.NMT], "NMT"),
    ("chip_hb", [Kind.HEARTBEAT], "하트비트 (Heartbeat)"),
    ("chip_sync", [Kind.SYNC, Kind.TIME], "SYNC"),
    ("chip_etc", [Kind.LSS, Kind.ERROR_FRAME, Kind.UNKNOWN], "에러 프레임"),
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
        root = QWidget()
        root.setObjectName("ground")
        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        self.setCentralWidget(root)

        # --- header: name, the open file, and the few actions people need
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(56)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(10)
        hl.addWidget(theme.WaveLogo())
        self.app_name = QLabel("CANopen Lens")
        f = self.app_name.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() * 1.15)
        self.app_name.setFont(f)
        hl.addWidget(self.app_name)
        hl.addSpacing(10)
        self.file_label = QLabel()
        self.file_label.setObjectName("fileInfo")
        self.file_label.setFont(theme.mono_font(-0.5))
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.file_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)   # never widens the window
        hl.addWidget(self.file_label, 1)
        self.btn_open_top = QPushButton()
        self.btn_open_top.setObjectName("primary")
        self.btn_open_top.setShortcut(QKeySequence.Open)
        self.btn_open_top.clicked.connect(self.open_dialog)
        hl.addWidget(self.btn_open_top)
        # one menu with every example, used by the header and the start page
        self.sample_menu = QMenu(self)
        self.sample_actions = []
        for name, key in EXAMPLES:
            act = self.sample_menu.addAction("", lambda p=str(EXAMPLE_DIR / name): self.load(p))
            self.sample_actions.append((act, key))
        self.btn_sample_tb = QToolButton()
        self.btn_sample_tb.setPopupMode(QToolButton.InstantPopup)
        self.btn_sample_tb.setMenu(self.sample_menu)
        hl.addWidget(self.btn_sample_tb)
        self.btn_export = QToolButton()
        self.btn_export.setPopupMode(QToolButton.InstantPopup)
        self.export_menu = QMenu(self)
        self.act_export_txt = self.export_menu.addAction("", lambda: self.export("txt"))
        self.act_export_json = self.export_menu.addAction("", lambda: self.export("json"))
        self.act_export_csv = self.export_menu.addAction("", lambda: self.export("csv"))
        self.btn_export.setMenu(self.export_menu)
        self.btn_export.setEnabled(False)
        hl.addWidget(self.btn_export)
        self.btn_glossary = QPushButton()
        self.btn_glossary.clicked.connect(lambda: glossary_dialog(self.tr_, self).exec())
        hl.addWidget(self.btn_glossary)
        self.btn_help = QPushButton("?")
        self.btn_help.setShortcut(QKeySequence.HelpContents)
        self.btn_help.clicked.connect(lambda: help_dialog(self.tr_, self).exec())
        hl.addWidget(self.btn_help)
        self.btn_lang = QPushButton("KO / EN")
        self.btn_lang.clicked.connect(self.toggle_language)
        hl.addWidget(self.btn_lang)
        rl.addWidget(header)

        # --- one navigation bar for everything
        nav = QFrame()
        nav.setObjectName("nav")
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(20, 0, 20, 0)
        nl.setSpacing(2)
        self.nav_buttons: list[QPushButton] = []
        for k in range(4):
            b = QPushButton()
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=k: self.center_tabs.setCurrentIndex(k))
            nl.addWidget(b)
            self.nav_buttons.append(b)
        nl.addStretch(1)
        rl.addWidget(nav)

        self.center_tabs = QStackedWidget()          # summary · messages · timeline · live
        self.center_tabs.currentChanged.connect(self._page_changed)
        rl.addWidget(self.center_tabs, 1)
        self.live = LivePage(self.tr_, str(SAMPLE_LOG))
        self.live.openInAnalysis.connect(self._open_live_recording)

        # --- summary (or the start page while nothing is open)
        self.stack = QStackedWidget()
        self.drop = DropArea()
        self.drop.setObjectName("ground")
        self.drop.fileDropped.connect(self.load)
        dl = QVBoxLayout(self.drop)
        dl.addStretch(2)
        start = QFrame()
        start.setObjectName("card")
        start.setMaximumWidth(760)
        sl = QVBoxLayout(start)
        sl.setContentsMargins(40, 36, 40, 32)
        sl.setSpacing(10)
        self.drop_title = QLabel()
        f = self.drop_title.font()
        f.setPointSizeF(f.pointSizeF() * 1.6)
        f.setBold(True)
        self.drop_title.setFont(f)
        self.drop_title.setAlignment(Qt.AlignCenter)
        sl.addWidget(self.drop_title)
        self.drop_sub = QLabel()
        self.drop_sub.setAlignment(Qt.AlignCenter)
        self.drop_sub.setWordWrap(True)
        self.drop_sub.setObjectName("muted")
        sl.addWidget(self.drop_sub)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_open = QPushButton()
        self.btn_open.setObjectName("primary")
        self.btn_open.setMinimumHeight(40)
        self.btn_open.clicked.connect(self.open_dialog)
        btns.addWidget(self.btn_open)
        self.btn_sample = QPushButton()
        self.btn_sample.setMinimumHeight(40)
        self.btn_sample.setMenu(self.sample_menu)
        btns.addWidget(self.btn_sample)
        btns.addStretch(1)
        sl.addSpacing(12)
        sl.addLayout(btns)
        self.welcome_steps = QLabel()
        self.welcome_steps.setTextFormat(Qt.RichText)
        self.welcome_steps.setAlignment(Qt.AlignCenter)
        self.welcome_steps.setWordWrap(True)
        self.welcome_steps.setStyleSheet(f"color:{theme.TEXT_2}; background:{theme.HEAD}; border-radius:4px; padding:10px;")
        sl.addSpacing(14)
        sl.addWidget(self.welcome_steps)
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        sl.addWidget(self.status_label)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(start, 3)
        row.addStretch(1)
        dl.addLayout(row)
        dl.addStretch(3)
        self.stack.addWidget(self.drop)
        self.summary = SummaryPage(self.tr_)
        self.summary.showRow.connect(self.goto_row)
        self.summary.showTimeline.connect(self.show_on_timeline)
        self.summary.changed.connect(lambda: QTimer.singleShot(0, lambda: self.refresh_all(keep_selection=True)))
        self.stack.addWidget(self.summary)
        self.overview = self.summary                 # name used by older code and tests
        self.center_tabs.addWidget(self.stack)

        frames_page = QWidget()
        frames_page.setObjectName("ground")
        fpl = QHBoxLayout(frames_page)
        fpl.setContentsMargins(16, 12, 16, 12)
        msplit = QSplitter(Qt.Horizontal)
        fpl.addWidget(msplit)
        frames_left = QWidget()
        fl = QVBoxLayout(frames_left)
        fl.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.kind_buttons: list[tuple[QToolButton, list]] = []
        glossary = {term: (ko, en) for term, ko, en in GLOSSARY}
        for key, kinds, term in FILTER_KINDS:
            b = QToolButton()
            b.setProperty("i18n", key)
            b.setProperty("help", glossary.get(term))
            b.setProperty("term", term)
            b.setCheckable(True)
            b.setChecked(True)
            color = KIND_COLORS[kinds[0]]
            b.setStyleSheet(f"QToolButton {{ border:1px solid {theme.LINE}; border-radius:{theme.RADIUS}px; padding:3px 9px;"
                            f" color:{theme.TEXT_2}; background:{theme.SURFACE}; }}"
                            f" QToolButton:checked {{ border:1px solid {color}; color:{theme.TEXT}; background:{theme.HEAD};"
                            f" border-left:4px solid {color}; }}")
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
        self.raw_box = QCheckBox()
        self.raw_box.toggled.connect(self._show_raw)
        bar.addWidget(self.raw_box)
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
        self._show_raw(False)
        fl.addWidget(self.table, 1)
        msplit.addWidget(frames_left)
        # right: what the selected message means
        right = QFrame()
        right.setObjectName("card")
        rl2 = QVBoxLayout(right)
        rl2.setContentsMargins(14, 10, 14, 10)
        self.detail_title = QLabel()
        f = self.detail_title.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() * 1.1)
        self.detail_title.setFont(f)
        self.detail_title.setWordWrap(True)
        self.detail_title.setMinimumWidth(1)
        rl2.addWidget(self.detail_title)
        self.detail = QTextBrowser()
        self.detail.setOpenLinks(False)
        self.detail.setStyleSheet("QTextBrowser { border: none; }")
        self.detail.anchorClicked.connect(lambda url: self.goto_row(int(url.toString().split(":")[1])))
        rl2.addWidget(self.detail, 1)
        right.setMinimumWidth(340)
        msplit.addWidget(right)
        msplit.setSizes([900, 420])
        msplit.setStretchFactor(0, 1)
        self.center_tabs.addWidget(frames_page)

        tl_page = QWidget()
        tl_page.setObjectName("ground")
        tll = QVBoxLayout(tl_page)
        tll.setContentsMargins(20, 12, 20, 12)
        bar = QHBoxLayout()
        self.btn_zoom_in = QPushButton("＋")
        self.btn_zoom_out = QPushButton("－")
        self.btn_zoom_fit = QPushButton()
        for b in (self.btn_zoom_out, self.btn_zoom_in):
            b.setFixedWidth(34)
        bar.addWidget(self.btn_zoom_out)
        bar.addWidget(self.btn_zoom_in)
        bar.addWidget(self.btn_zoom_fit)
        self.timeline_range = QLabel()
        self.timeline_range.setStyleSheet("color:#334155; padding-left:8px;")
        bar.addWidget(self.timeline_range)
        bar.addStretch(1)
        tll.addLayout(bar)
        self.timeline_hint = QLabel()
        self.timeline_hint.setStyleSheet("color:#64748b;")
        self.timeline_hint.setWordWrap(True)
        tll.addWidget(self.timeline_hint)
        self.timeline = TimelineWidget(self.tr_)
        self.timeline.rowActivated.connect(self.goto_row)
        self.btn_zoom_in.clicked.connect(lambda: self.timeline.zoom(0.5, self.timeline.cursor_t))
        self.btn_zoom_out.clicked.connect(lambda: self.timeline.zoom(2.0, self.timeline.cursor_t))
        self.btn_zoom_fit.clicked.connect(self.timeline.fit)
        tl_scroll = QScrollArea()
        tl_scroll.setWidgetResizable(True)
        tl_scroll.setWidget(self.timeline)
        tll.addWidget(tl_scroll, 1)
        # horizontal position inside the log while zoomed in (in ms steps)
        self.timeline_scroll = QScrollBar(Qt.Horizontal)
        self.timeline_scroll.valueChanged.connect(self._timeline_scrolled)
        tll.addWidget(self.timeline_scroll)
        self.timeline_cursor = QLabel()
        self.timeline_cursor.setStyleSheet("color:#0f172a;")
        tll.addWidget(self.timeline_cursor)
        self.timeline.viewChanged.connect(self._timeline_view_changed)
        self.timeline.cursorChanged.connect(self.timeline_cursor.setText)
        self.center_tabs.addWidget(tl_page)
        self.center_tabs.addWidget(self.live)
        self._page_changed(0)

    def _page_changed(self, k: int):
        for i, b in enumerate(self.nav_buttons):
            b.setChecked(i == k)

    # ------------------------------------------------------------------ i18n
    def _retranslate(self):
        tr = self.tr_
        self.setWindowTitle(f"{tr('app_title')} {__version__}" + (f" – {Path(self.path).name}" if self.path else ""))
        self.btn_open_top.setText(tr("open"))
        self.btn_sample_tb.setText(tr("open_sample"))
        for act, key in self.sample_actions:
            act.setText(tr(key))
        self.btn_lang.setToolTip(tr("language"))
        self.drop_title.setText(tr("drop_title"))
        self.drop_sub.setText(tr("drop_sub"))
        self.btn_open.setText(tr("open"))
        self.btn_sample.setText(tr("open_sample"))
        for b, key in zip(self.nav_buttons, ("tab_overview", "tab_frames", "tab_timeline", "mode_live")):
            b.setText(tr(key))
        has_log = self.log is not None
        self.nav_buttons[FRAMES_TAB].setEnabled(has_log)
        self.nav_buttons[TIMELINE_TAB].setEnabled(has_log)
        self.welcome_steps.setText(tr("welcome_steps"))
        self.btn_export.setText(tr("export"))
        self.act_export_txt.setText(tr("export_txt"))
        self.act_export_json.setText(tr("export_json"))
        self.act_export_csv.setText(tr("export_csv"))
        self.btn_glossary.setText(tr("glossary"))
        self.btn_help.setToolTip(tr("help"))
        self.raw_box.setText(tr("raw_cols"))
        for b, _ in self.kind_buttons:
            b.setText(tr(b.property("i18n")))
            help_text = b.property("help")
            term = b.property("term") or ""
            if help_text:
                b.setToolTip(f"<b>{term}</b><br>" + (help_text[0] if tr.lang == "ko" else help_text[1]))
        self.index_edit.setPlaceholderText(tr("filter_index"))
        self.issues_only.setText(tr("filter_issues"))
        self.timeline_hint.setText(tr("timeline_hint"))
        self.btn_zoom_fit.setText(tr("timeline_fit"))
        self.btn_zoom_in.setToolTip(tr("timeline_zoom_in"))
        self.btn_zoom_out.setToolTip(tr("timeline_zoom_out"))
        self._timeline_view_changed(self.timeline.v0, self.timeline.v1)
        self.model.headerDataChanged.emit(Qt.Horizontal, 0, self.model.columnCount() - 1)
        if self.current_frame_row() is None:
            self.detail_title.setText(tr("details"))
            self.detail.setPlainText(tr("select_frame"))

    def toggle_language(self):
        self.tr_.lang = "en" if self.tr_.lang == "ko" else "ko"
        self._retranslate()
        self.live.retranslate()
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

    def _open_live_recording(self, path: str):
        self.load(path, display_name=self.tr_("mode_live") + " " + time.strftime("%H:%M:%S"))

    def closeEvent(self, ev):
        self.live.shutdown()
        super().closeEvent(ev)

    def load(self, path: str, display_name: Optional[str] = None):
        if self._thread is not None:
            return
        self._pending_name = display_name
        self.center_tabs.setCurrentIndex(OVERVIEW_TAB)
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
        self.set_log(log, path, self._pending_name)

    def set_log(self, log: CanopenLog, path: Optional[str] = None, display_name: Optional[str] = None):
        self._display_name = display_name
        self.log = log
        self.path = path
        self.stack.setCurrentIndex(1)
        self._retranslate()
        self.btn_export.setEnabled(True)
        self.refresh_all()
        self.center_tabs.setCurrentIndex(OVERVIEW_TAB)
        self.detail_title.setText(self.tr_("details"))
        self.detail.setPlainText(self.tr_("select_frame"))

    # ------------------------------------------------------------------ refresh
    def refresh_all(self, keep_selection: bool = False):
        log = self.log
        tr = self.tr_
        current = self.current_frame_row() if keep_selection else None
        name = getattr(self, "_display_name", None) or (Path(self.path).name if self.path else "-")
        unit = "초" if tr.lang == "ko" else "s"
        self.file_label.setText(f"{name}  ·  {log.trace.duration:.1f} {unit}  ·  {len(log):,} {tr('frames')}"
                                f"  ·  {len(log.nodes)} {tr('nodes')}")

        self.node_combo.blockSignals(True)
        prev = self.node_combo.currentData()
        self.node_combo.clear()
        self.node_combo.addItem(tr("filter_all_nodes"), -1)
        for ni in log.nodes:
            self.node_combo.addItem(f"{tr('col_node')} {ni.node}", ni.node)
        idx = self.node_combo.findData(prev) if prev is not None else 0
        self.node_combo.setCurrentIndex(max(idx, 0))
        self.node_combo.blockSignals(False)

        self.model.set_log(log, None)
        self.apply_filter()
        self.timeline.set_log(log)
        tab = self.center_tabs.currentIndex()
        self.summary.set_log(log, keep_selection=keep_selection)
        if current is not None:
            self.goto_row(current)
            self.center_tabs.setCurrentIndex(tab)

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

    # -- timeline zoom ---------------------------------------------------------------
    def show_on_timeline(self, t: float):
        self.center_tabs.setCurrentIndex(TIMELINE_TAB)
        if t >= 0:
            self.timeline.focus_time(t)
        self.timeline.setFocus()

    def _timeline_view_changed(self, v0: float, v1: float):
        tl = self.timeline
        ms = lambda s: int(round(s * 1000))  # noqa: E731
        sb = self.timeline_scroll
        sb.blockSignals(True)
        page = max(ms(v1 - v0), 1)
        sb.setRange(0, max(ms(tl.duration) - page, 0))
        sb.setPageStep(page)
        sb.setSingleStep(max(page // 10, 1))
        sb.setValue(ms(v0))
        sb.blockSignals(False)
        sb.setEnabled(tl.is_zoomed())
        from .timeline import format_duration
        self.timeline_range.setText(self.tr_("timeline_range").format(
            a=f"{v0:.3f}", b=f"{v1:.3f}", span=format_duration(v1 - v0)))

    def _timeline_scrolled(self, value: int):
        tl = self.timeline
        span = tl.span
        tl.set_view(value / 1000.0, value / 1000.0 + span)

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
        self.center_tabs.setCurrentIndex(FRAMES_TAB)
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
        rec = self.log.trace.record(row)
        self.detail_title.setText(f"#{row + 1} · {describe.kind_label(rec.kind, lang)}")
        html = [f"<div style='background:{theme.HEAD}; padding:8px; border-radius:4px'>"
                f"<b>{_esc(tr('plain'))}</b><br>{_esc(self.log.summary(row, lang))}<br>"
                f"<span style='color:#475569'>{_esc(describe.kind_help(rec.kind, lang))}</span></div>"]
        related = [i for i in self.log.issues if i.row == row]
        if related:
            html.append(f"<h4>{_esc(tr('frame_findings'))}</h4>")
            for issue in related:
                html.append(self._explanation_html(issue))
        breakdown = self.log.byte_breakdown(row, lang)
        if breakdown:
            html.append(f"<h4>{_esc(tr('bytes_title'))}</h4><p style='color:#64748b'>{_esc(tr('bytes_hint'))}</p>"
                        "<table cellspacing='0' cellpadding='4' width='100%'>")
            for b, m in breakdown:
                html.append(f"<tr><td valign='top' style='font-family:monospace; white-space:nowrap; background:{theme.HEAD}'>{_esc(b)}</td>"
                            f"<td valign='top'>{_esc(m)}</td></tr>")
            html.append("</table><h4>" + _esc(tr("details")) + "</h4>")
        html.append("<table cellspacing='0' cellpadding='4' width='100%'>")
        skip = {_k for _k in (describe._p(lang, "해석", "Meaning"), describe._p(lang, "설명", "What it is"))}
        for k, v in rows:
            if k in skip:
                continue
            html.append(f"<tr><td valign='top' width='38%' style='color:#64748b'>{_esc(k)}</td><td valign='top'>{_esc(v)}</td></tr>")
        html.append("</table>")
        self.detail.setHtml("".join(html))

    def _explanation_html(self, issue) -> str:
        tr = self.tr_
        ex = self.log.explain(issue, tr.lang)
        color = {Severity.ERROR: theme.RED, Severity.WARNING: theme.AMBER, Severity.INFO: theme.CYAN}[issue.severity]
        sev = describe.severity_text(issue.severity, tr.lang)
        out = [f"<p style='color:{color}; font-size:large'><b>[{sev}] {_esc(ex.title)}</b></p>",
               f"<p><b>{_esc(tr('what'))}</b><br>{_esc(ex.what)}</p>"]
        if ex.why:
            out.append(f"<p><b>{_esc(tr('why'))}</b><br>{_esc(ex.why)}</p>")
        if ex.steps:
            items = "".join(f"<li style='margin-bottom:4px'>{_esc(s)}</li>" for s in ex.steps)
            out.append(f"<p><b>{_esc(tr('steps'))}</b></p><ol>{items}</ol>")
        return "".join(out)

    def _show_raw(self, on: bool):
        for col in (5, 6):
            self.table.setColumnHidden(col, not on)

    def export(self, kind: str):
        if self.log is None:
            return
        tr = self.tr_
        stem = Path(self.path).stem if self.path else "canopen-lens"
        filters = {"txt": "Text (*.txt)", "json": "JSON (*.json)", "csv": "CSV (*.csv)"}
        path, _ = QFileDialog.getSaveFileName(self, tr("export"), f"{stem}-report.{kind}", filters[kind])
        if not path:
            return
        try:
            if kind == "txt":
                Path(path).write_text(self.log.report(tr.lang), encoding="utf-8-sig")
            elif kind == "json":
                self.log.to_json(path, tr.lang)
            else:
                self.log.to_csv(path, tr.lang)
        except Exception as exc:
            QMessageBox.warning(self, tr("export"), str(exc))
            return
        self.statusBar().showMessage(tr("export_done").format(path), 8000)


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")).replace("\n", "<br>")


def _apply_style(app: QApplication) -> None:
    theme.apply(app)


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    from ..cli import default_lang

    lang = default_lang()
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
    if "--self-test" in argv:
        # used by the release build to check that the packaged app really works
        from ..log import open_log

        win = MainWindow(lang)
        win.set_log(open_log(SAMPLE_LOG), str(SAMPLE_LOG))
        app.processEvents()
        ok = win.model.rowCount() > 0 and bool(win.summary.ov and win.summary.ov.incidents)
        try:  # the live monitor's bus drivers must be bundled too
            import can  # noqa: F401
            import can.interfaces.virtual  # noqa: F401
        except ImportError:
            ok = False
        print(f"canopen-lens {__version__} self-test: {'ok' if ok else 'FAILED'}", flush=True)
        return 0 if ok else 1
    win = MainWindow(lang)
    win.show()
    if files:
        win.load(files[0])
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
