"""Live monitor: watch a CAN bus as it runs.

Frames are received on a background thread (python-can, or a replay of a log
for trying the feature without hardware) and decoded on the GUI thread in
batches every 100 ms. Only the newest frames are kept on screen; everything is
also written to a candump log so it can be opened in the log analysis tab.
"""

from __future__ import annotations

import collections
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import describe
from .._core import AxisState, Severity, Trace
from ..live import FrameSnapshot, LiveDecoder
from . import theme
from .i18n import Tr
from .models import KIND_COLORS

DEMO = "demo"
DEMO_AMR = "demo-amr"
DEMOS = {DEMO: "sample_cia402.log", DEMO_AMR: "sample_amr_2wheel.log"}
INTERFACES = [
    # (python-can interface, default channel, needs bitrate)
    (DEMO, "", False),
    (DEMO_AMR, "", False),
    ("socketcan", "can0", False),
    ("pcan", "PCAN_USBBUS1", True),
    ("kvaser", "0", True),
    ("ixxat", "0", True),
    ("vector", "0", True),
    ("slcan", "COM3" if sys.platform.startswith("win") else "/dev/ttyACM0", True),
    ("gs_usb", "0", True),
    ("virtual", "test", False),
]
BITRATES = ["1000000", "800000", "500000", "250000", "125000", "50000", "20000", "10000"]
MAX_ROWS = 5000

SEV_STYLE = {
    Severity.ERROR: ("●", "#dc2626"),
    Severity.WARNING: ("▲", "#d97706"),
    Severity.INFO: ("ℹ", "#2563eb"),
}


# ----------------------------------------------------------------------- sources

class _Source(QThread):
    """Pushes (wall_time, id, data, ext, rtr, err, fd) tuples into `queue`."""

    failed = Signal(str)
    finished_replay = Signal()

    def __init__(self, queue: collections.deque):
        super().__init__()
        self.queue = queue
        self._stop = False

    def stop(self):
        self._stop = True


class BusSource(_Source):
    def __init__(self, queue, interface: str, channel: str, bitrate: Optional[int]):
        super().__init__(queue)
        self.kwargs = {"interface": interface, "channel": channel}
        if bitrate:
            self.kwargs["bitrate"] = bitrate

    def run(self):
        try:
            import can
        except ImportError:
            self.failed.emit("python-can")
            return
        try:
            bus = can.Bus(**self.kwargs)
        except Exception as exc:  # pragma: no cover - depends on hardware
            self.failed.emit(str(exc))
            return
        offset = None
        try:
            while not self._stop:
                msg = bus.recv(0.1)
                if msg is None:
                    continue
                if offset is None:
                    offset = time.time() - msg.timestamp
                self.queue.append((msg.timestamp + offset, msg.arbitration_id, bytes(msg.data), msg.is_extended_id,
                                   msg.is_remote_frame, msg.is_error_frame, getattr(msg, "is_fd", False)))
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))
        finally:
            bus.shutdown()


class ReplaySource(_Source):
    """Plays a candump log back in real time (or faster), as if it came from a bus."""

    def __init__(self, queue, path: str, speed: float = 1.0):
        super().__init__(queue)
        self.path = path
        self.speed = speed

    def run(self):
        try:
            tr = Trace.from_bytes(Path(self.path).read_bytes())
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        start = time.time()
        i, n = 0, len(tr)
        while not self._stop and i < n:
            now = (time.time() - start) * self.speed
            while i < n and tr.frame(i).t <= now:
                f = tr.frame(i)
                self.queue.append((start + f.t / self.speed, f.id, f.data, f.ext, f.rtr, f.error, f.fd))
                i += 1
            self.msleep(5)
        if not self._stop:
            self.finished_replay.emit()


# ----------------------------------------------------------------------- frame model

class LiveFrameModel(QAbstractTableModel):
    COLS = ["col_time", "col_node", "col_kind", "col_meaning", "col_id", "col_data"]

    def __init__(self, tr: Tr, parent=None):
        super().__init__(parent)
        self.tr_ = tr
        self.rows: collections.deque = collections.deque(maxlen=MAX_ROWS)  # (seq, t, FrameSnapshot)
        self._mono = QFont("monospace")
        self._mono.setStyleHint(QFont.Monospace)
        self._cache: dict[int, str] = {}
        self._issue_bg = QBrush(QColor("#fde8e8"))
        self.issue_seqs: set[int] = set()

    def extend(self, items) -> None:
        if not items:
            return
        self.beginResetModel()
        self.rows.extend(items)
        if len(self._cache) > MAX_ROWS * 2:
            keep = {seq for seq, _, _ in self.rows}
            self._cache = {k: v for k, v in self._cache.items() if k in keep}
            self.issue_seqs &= keep
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self.rows.clear()
        self._cache.clear()
        self.issue_seqs.clear()
        self.endResetModel()

    def snapshot(self, row: int) -> Optional[FrameSnapshot]:
        if 0 <= row < len(self.rows):
            return self.rows[row][2]
        return None

    def row_of_seq(self, seq: int) -> Optional[int]:
        for k, (s, _, _) in enumerate(self.rows):
            if s == seq:
                return k
        return None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.tr_(self.COLS[section])
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        seq, t, snap = self.rows[index.row()]
        col = index.column()
        f, r = snap.frame, snap.record
        if role == Qt.DisplayRole:
            if col == 0:
                return time.strftime("%H:%M:%S", time.localtime(t)) + f".{int((t % 1) * 1000):03d}"
            if col == 1:
                return str(r.node) if r.node else "-"
            if col == 2:
                label = describe.kind_label(r.kind, self.tr_.lang)
                return label + (str(r.pdo_num) if r.pdo_num else "")
            if col == 3:
                key = seq * 2 + (self.tr_.lang == "en")
                s = self._cache.get(key)
                if s is None:
                    s = self._cache[key] = snap.summary(self.tr_.lang)
                return s
            if col == 4:
                return f"0x{f.id:08X}" if f.ext else f"0x{f.id:03X}"
            if col == 5:
                return "RTR" if f.rtr else f.data.hex(" ").upper()
        elif role == Qt.ForegroundRole and col == 2:
            return QBrush(QColor(KIND_COLORS.get(r.kind, "#334155")))
        elif role == Qt.BackgroundRole and seq in self.issue_seqs:
            return self._issue_bg
        elif role == Qt.FontRole and col in (4, 5):
            return self._mono
        elif role == Qt.TextAlignmentRole and col in (0, 1):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None


# ----------------------------------------------------------------------- page

class LivePage(QWidget):
    openInAnalysis = Signal(str)

    def __init__(self, tr: Tr, sample_log: str, parent=None):
        super().__init__(parent)
        self.tr_ = tr
        self.sample_log = sample_log
        self.queue: collections.deque = collections.deque()
        self.source: Optional[_Source] = None
        self.decoder = LiveDecoder()
        self.seq = 0
        self.findings: list = []
        self.record_path: Optional[str] = None
        self._record_fh = None
        self._rate_window: collections.deque = collections.deque()
        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain)
        self._timer.start(100)
        self._slow = QTimer(self)
        self._slow.timeout.connect(self._refresh_nodes)
        self._slow.start(1000)
        self.retranslate()

    # ------------------------------------------------------------------ layout
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)

        bar_frame = QFrame()
        bar_frame.setObjectName("bar")
        bar_frame.setStyleSheet(f"#bar {{ border:1px solid {theme.LINE}; border-radius:{theme.RADIUS}px; background:{theme.SURFACE}; }}")
        bar = QHBoxLayout(bar_frame)
        self.lbl_iface = QLabel()
        bar.addWidget(self.lbl_iface)
        self.iface = QComboBox()
        for name, ch, _ in INTERFACES:
            self.iface.addItem(name, (name, ch))
        self.iface.currentIndexChanged.connect(self._iface_changed)
        bar.addWidget(self.iface)
        self.lbl_channel = QLabel()
        bar.addWidget(self.lbl_channel)
        self.channel = QLineEdit()
        self.channel.setMaximumWidth(170)
        bar.addWidget(self.channel)
        self.lbl_bitrate = QLabel()
        bar.addWidget(self.lbl_bitrate)
        self.bitrate = QComboBox()
        self.bitrate.addItems(BITRATES)
        self.bitrate.setCurrentText("500000")
        bar.addWidget(self.bitrate)
        self.btn_eds = QPushButton()
        self.btn_eds.clicked.connect(self._choose_eds)
        bar.addWidget(self.btn_eds)
        bar.addSpacing(10)
        self.btn_connect = QPushButton()
        self.btn_connect.setMinimumHeight(34)
        self.btn_connect.clicked.connect(self.toggle)
        bar.addWidget(self.btn_connect)
        self.status = QLabel()
        self.status.setStyleSheet(f"color:{theme.TEXT_2};")
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # the status text grows while running; it must not push the window wider
        self.status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        bar.addWidget(self.status, 1)
        lay.addWidget(bar_frame)
        # hint on the left, what to do with the recording on the right
        hint_row = QHBoxLayout()
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setMinimumWidth(1)
        self.hint.setStyleSheet(f"color:{theme.TEXT_2};")
        hint_row.addWidget(self.hint, 1)
        self.btn_save = QPushButton()
        self.btn_save.clicked.connect(self.save_log)
        hint_row.addWidget(self.btn_save)
        self.btn_analyze = QPushButton()
        self.btn_analyze.setObjectName("primary")
        self.btn_analyze.clicked.connect(self._open_in_analysis)
        hint_row.addWidget(self.btn_analyze)
        lay.addLayout(hint_row)

        split = QSplitter(Qt.Horizontal)
        lay.addWidget(split, 1)

        # left: live findings
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.lbl_findings = QLabel()
        f = self.lbl_findings.font()
        f.setBold(True)
        self.lbl_findings.setFont(f)
        ll.addWidget(self.lbl_findings)
        self.finding_list = QListWidget()
        self.finding_list.setWordWrap(True)
        self.finding_list.setTextElideMode(Qt.ElideNone)
        self.finding_list.setResizeMode(QListWidget.Adjust)
        self.finding_list.viewport().installEventFilter(self)
        self.finding_list.currentItemChanged.connect(self._finding_selected)
        ll.addWidget(self.finding_list, 1)
        left.setMinimumWidth(240)
        split.addWidget(left)

        # center: frames + nodes
        self.center = QTabWidget()
        frames = QWidget()
        fl = QVBoxLayout(frames)
        fl.setContentsMargins(0, 4, 0, 0)
        opts = QHBoxLayout()
        self.autoscroll = QCheckBox()
        self.autoscroll.setChecked(True)
        opts.addWidget(self.autoscroll)
        self.pause = QCheckBox()
        opts.addWidget(self.pause)
        self.raw = QCheckBox()
        self.raw.toggled.connect(self._show_raw)
        opts.addWidget(self.raw)
        opts.addStretch(1)
        self.btn_clear = QPushButton()
        self.btn_clear.clicked.connect(self.clear)
        opts.addWidget(self.btn_clear)
        fl.addLayout(opts)
        self.model = LiveFrameModel(self.tr_)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        for col, w in enumerate([100, 44, 90, 480, 80]):
            hh.resizeSection(col, w)
        hh.setStretchLastSection(True)
        hh.setSectionResizeMode(QHeaderView.Interactive)
        self.table.clicked.connect(self._frame_clicked)
        fl.addWidget(self.table, 1)
        self.center.addTab(frames, "")

        self.node_table = QTableWidget(0, 6)
        self.node_table.verticalHeader().setVisible(False)
        self.node_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.node_table.horizontalHeader().setStretchLastSection(True)
        self.center.addTab(self.node_table, "")
        split.addWidget(self.center)

        # right: explanation
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 0, 0, 0)
        self.detail_title = QLabel()
        f = self.detail_title.font()
        f.setBold(True)
        self.detail_title.setFont(f)
        self.detail_title.setWordWrap(True)
        rl.addWidget(self.detail_title)
        self.detail = QTextBrowser()
        rl.addWidget(self.detail, 1)
        right.setMinimumWidth(300)
        split.addWidget(right)
        split.setSizes([300, 720, 400])
        split.setStretchFactor(1, 1)
        self._show_raw(False)
        self._iface_changed()

    def retranslate(self):
        tr = self.tr_
        self.lbl_iface.setText(tr("live_iface"))
        self.lbl_channel.setText(tr("live_channel"))
        self.lbl_bitrate.setText(tr("live_bitrate"))
        self.btn_eds.setText(tr("live_eds"))
        self.btn_connect.setText(tr("live_stop") if self.running else tr("live_start"))
        self.btn_connect.setStyleSheet(
            "QPushButton { background:%s; color:white; border:none; border-radius:%dpx; padding:5px 18px; font-weight:bold; }"
            % (theme.RED if self.running else theme.ACCENT, theme.RADIUS))
        self.iface.setItemText(0, tr("live_demo"))
        self.iface.setItemText(1, tr("live_demo_amr"))
        self.lbl_findings.setText(tr("live_findings"))
        self.center.setTabText(0, tr("live_frames"))
        self.center.setTabText(1, tr("live_nodes"))
        self.autoscroll.setText(tr("live_autoscroll"))
        self.pause.setText(tr("live_pause"))
        self.pause.setToolTip(tr("live_pause_tip"))
        self.raw.setText(tr("raw_cols"))
        self.btn_clear.setText(tr("live_clear"))
        self.btn_save.setText(tr("live_save"))
        self.btn_analyze.setText(tr("live_analyze"))
        self.detail_title.setText(tr("details"))
        self.node_table.setHorizontalHeaderLabels([tr("col_node"), tr("live_col_kind"), tr("node_nmt"),
                                                   tr("node_hb"), tr("live_col_last"), tr("node_axis")])
        self.model.headerDataChanged.emit(Qt.Horizontal, 0, self.model.columnCount() - 1)
        self.model._cache.clear()
        self._iface_changed()
        self._update_status()
        if not self.findings and self.finding_list.count() == 0:
            self.detail.setPlainText(tr("live_select"))

    # ------------------------------------------------------------------ connection
    @property
    def running(self) -> bool:
        return self.source is not None

    def _iface_changed(self, *_):
        name, ch = self.iface.currentData()
        demo = name in DEMOS
        if not self.running:
            self.channel.setText(ch)
        self.channel.setEnabled(not demo)
        needs_bitrate = next(b for n, _, b in INTERFACES if n == name)
        self.bitrate.setEnabled(needs_bitrate)
        tr = self.tr_
        if demo:
            self.hint.setText(tr("live_hint_demo"))
        elif name == "socketcan":
            self.hint.setText(tr("live_hint_socketcan"))
        else:
            self.hint.setText(tr("live_hint_other"))

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self, speed: float = 1.0):
        if self.running:
            return
        name, _ = self.iface.currentData()
        self.queue.clear()
        if name in DEMOS:
            path = str(Path(self.sample_log).with_name(DEMOS[name]))
            self.source = ReplaySource(self.queue, path, speed)
            self.source.finished_replay.connect(self._replay_done)
            channel = "demo"
        else:
            bitrate = int(self.bitrate.currentText()) if self.bitrate.isEnabled() else None
            channel = self.channel.text().strip()
            self.source = BusSource(self.queue, name, channel, bitrate)
        self.source.failed.connect(self._failed)
        self._open_record(channel or name)
        self.source.start()
        self.iface.setEnabled(False)
        self.channel.setEnabled(False)
        self.bitrate.setEnabled(False)
        self.retranslate()

    def stop(self):
        if not self.running:
            return
        src, self.source = self.source, None
        src.stop()
        src.wait(2000)
        self._drain()
        self._close_record()
        self.iface.setEnabled(True)
        self.retranslate()

    def _replay_done(self):
        self.stop()
        self.status.setText(self.status.text() + " · " + self.tr_("live_replay_done"))

    def _failed(self, msg: str):
        src, self.source = self.source, None
        if src is not None:
            src.wait(2000)
        self._close_record()
        self.iface.setEnabled(True)
        self.retranslate()
        if msg == "python-can":
            QMessageBox.warning(self, self.tr_("live_title"), self.tr_("live_need_can"))
        else:
            QMessageBox.warning(self, self.tr_("live_title"), self.tr_("live_failed").format(msg))

    def _choose_eds(self):
        path, _ = QFileDialog.getOpenFileName(self, self.tr_("live_eds"), "", self.tr_("eds_filter"))
        if not path:
            return
        text, ok = _ask_node(self)
        if not ok:
            return
        try:
            self.decoder.attach_eds(text, path)
        except Exception as exc:
            QMessageBox.warning(self, self.tr_("load_failed"), str(exc))
            return
        self.status.setText(self.tr_("live_eds_set").format(text, Path(path).name))

    # ------------------------------------------------------------------ recording
    def _open_record(self, channel: str):
        self._close_record()
        fd, path = tempfile.mkstemp(prefix="canopen-lens-live-", suffix=".log")
        os.close(fd)
        self.record_path = path
        self._record_fh = open(path, "w", encoding="ascii", newline="\n")
        self._record_channel = "".join(c for c in channel if c.isalnum() or c in "_-") or "can0"

    def _close_record(self):
        if self._record_fh:
            self._record_fh.close()
            self._record_fh = None

    def _record(self, t, can_id, data, ext, rtr, err):
        if not self._record_fh:
            return
        if err:
            can_id |= 0x20000000
            ext = True
        ident = f"{can_id:08X}" if ext else f"{can_id:03X}"
        body = "R" if rtr else data.hex().upper()
        self._record_fh.write(f"({t:.6f}) {self._record_channel} {ident}#{body}\n")

    def save_log(self):
        if not self.record_path or not Path(self.record_path).exists():
            QMessageBox.information(self, self.tr_("live_title"), self.tr_("live_nothing"))
            return
        if self._record_fh:
            self._record_fh.flush()
        name = time.strftime("candump-%Y-%m-%d_%H%M%S.log")
        path, _ = QFileDialog.getSaveFileName(self, self.tr_("live_save"), name, self.tr_("log_filter"))
        if path:
            Path(path).write_bytes(Path(self.record_path).read_bytes())
            self.status.setText(self.tr_("export_done").format(path))

    def _open_in_analysis(self):
        if not self.record_path or not Path(self.record_path).exists() or Path(self.record_path).stat().st_size == 0:
            QMessageBox.information(self, self.tr_("live_title"), self.tr_("live_nothing"))
            return
        if self._record_fh:
            self._record_fh.flush()
        self.openInAnalysis.emit(self.record_path)

    # ------------------------------------------------------------------ decoding
    def _drain(self):
        q = self.queue
        new_rows = []
        dec = self.decoder
        found = []
        budget = 50000
        while q and budget:
            t, can_id, data, ext, rtr, err, fd = q.popleft()
            budget -= 1
            issues = dec.feed(t, can_id, data, is_extended=ext, is_remote=rtr, is_error=err, is_fd=fd)
            self._record(t, can_id, data, ext, rtr, err)
            self.seq += 1
            new_rows.append((self.seq, t, dec.snapshot()))
            self._rate_window.append(t)
            for i in issues:
                found.append((i, self.seq))
        if self.running and not new_rows:
            for i in dec.tick():
                found.append((i, None))
        if not self.pause.isChecked():
            self.model.extend(new_rows)
            if new_rows and self.autoscroll.isChecked():
                self.table.scrollToBottom()
        for issue, seq in found:
            if seq is not None:
                self.model.issue_seqs.add(seq)
            self._add_finding(issue, seq)
        self._update_status()

    def _add_finding(self, issue, seq):
        lang = self.tr_.lang
        ex = self.decoder.explain(issue, lang)
        icon, color = SEV_STYLE[issue.severity]
        when = time.strftime("%H:%M:%S", time.localtime(self.decoder.core.t0 + issue.t))
        item = QListWidgetItem(f"{icon}  {ex.title}\n      {when}")
        item.setForeground(QColor(color) if issue.severity == Severity.ERROR else self.palette().text().color())
        item.setData(Qt.UserRole, (issue, seq))
        self.findings.append((issue, seq))
        self.finding_list.insertItem(0, item)
        self._fit_item(item)

    def _fit_item(self, item):
        # QListWidget does not re-measure wrapped text reliably, so size items ourselves
        width = max(self.finding_list.viewport().width() - 12, 120)
        fm = self.finding_list.fontMetrics()
        rect = fm.boundingRect(QRect(0, 0, width, 10000), int(Qt.TextWordWrap), item.text())
        item.setSizeHint(QSize(width, rect.height() + 8))

    def eventFilter(self, obj, ev):
        if obj is self.finding_list.viewport() and ev.type() == QEvent.Resize:
            for k in range(self.finding_list.count()):
                self._fit_item(self.finding_list.item(k))
        return super().eventFilter(obj, ev)

    def _update_status(self):
        now = time.time()
        w = self._rate_window
        while w and now - w[0] > 2.0:
            w.popleft()
        rate = len(w) / 2.0
        errs = sum(1 for i, _ in self.findings if i.severity == Severity.ERROR)
        warns = sum(1 for i, _ in self.findings if i.severity == Severity.WARNING)
        state = self.tr_("live_running") if self.running else self.tr_("live_stopped")
        self.status.setText(self.tr_("live_status").format(state, self.decoder.frame_count, rate, errs, warns))

    def _refresh_nodes(self):
        lang = self.tr_.lang
        nodes = self.decoder.nodes
        self.node_table.setRowCount(len(nodes))
        now = time.time()
        problem_nodes = {i.node for i, _ in self.findings if i.severity != Severity.INFO}
        for r, ni in enumerate(nodes):
            states = list(ni.axis_states) or ([ni.axis_state] if ni.is_drive else [])
            axis = " / ".join(describe.axis_state_text(s, lang, short=True) for s in states) if ni.is_drive else "-"
            last = now - (self.decoder.core.t0 + ni.last_seen)
            vals = [str(ni.node),
                    self.tr_("node_drive") if ni.is_drive else self.tr_("node_generic"),
                    describe.hb_state_text(ni.last_hb_state, lang) if ni.last_hb_state >= 0 else self.tr_("node_none_hb"),
                    f"{ni.hb_period * 1000:.0f} ms" if ni.hb_period else "-",
                    self.tr_("live_ago").format(max(last, 0.0)),
                    axis]
            fault = any(s in (AxisState.FAULT, AxisState.FAULT_REACTION_ACTIVE) for s in states)
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if fault or (ni.node in problem_nodes and c == 0):
                    item.setForeground(QColor("#dc2626"))
                self.node_table.setItem(r, c, item)
        self.node_table.resizeColumnsToContents()

    def clear(self):
        running = self.running
        self.decoder.reset()
        self.model.clear()
        self.findings.clear()
        self.finding_list.clear()
        self.seq = 0
        self.node_table.setRowCount(0)
        self.detail.setPlainText(self.tr_("live_select"))
        if running:
            self._open_record(self._record_channel)
        self._update_status()

    # ------------------------------------------------------------------ details
    def _show_raw(self, on: bool):
        for col in (4, 5):
            self.table.setColumnHidden(col, not on)

    def _frame_clicked(self, index):
        snap = self.model.snapshot(index.row())
        if snap is None:
            return
        self._show_snapshot(snap)

    def _show_snapshot(self, snap: FrameSnapshot, extra_html: str = ""):
        tr = self.tr_
        lang = tr.lang
        rec = snap.record
        self.detail_title.setText(describe.kind_label(rec.kind, lang))
        html = [extra_html,
                f"<div style='background:#eff6ff; padding:8px'><b>{_esc(tr('plain'))}</b><br>{_esc(snap.summary(lang))}"
                f"<br><span style='color:#475569'>{_esc(describe.kind_help(rec.kind, lang))}</span></div>"]
        breakdown = snap.byte_breakdown(lang)
        if breakdown:
            html.append(f"<h4>{_esc(tr('bytes_title'))}</h4><table cellspacing='0' cellpadding='4' width='100%'>")
            for b, m in breakdown:
                html.append(f"<tr><td valign='top' style='font-family:monospace; white-space:nowrap; background:#f1f5f9'>{_esc(b)}</td>"
                            f"<td valign='top'>{_esc(m)}</td></tr>")
            html.append("</table>")
        html.append("<table cellspacing='0' cellpadding='4' width='100%'>")
        skip = {describe._p(lang, "해석", "Meaning"), describe._p(lang, "설명", "What it is"),
                describe._p(lang, "시간", "Time"), describe._p(lang, "원본 줄 번호", "Source line")}
        for k, v in snap.details(lang):
            if k not in skip:
                html.append(f"<tr><td valign='top' width='38%' style='color:#64748b'>{_esc(k)}</td><td>{_esc(v)}</td></tr>")
        html.append("</table>")
        self.detail.setHtml("".join(html))

    def _finding_selected(self, item, _prev):
        if item is None:
            return
        issue, seq = item.data(Qt.UserRole)
        tr = self.tr_
        ex = self.decoder.explain(issue, tr.lang)
        _, color = SEV_STYLE[issue.severity]
        html = [f"<p style='color:{color}; font-size:large'><b>{_esc(ex.title)}</b></p>",
                f"<p><b>{_esc(tr('what'))}</b><br>{_esc(ex.what)}</p>"]
        if ex.why:
            html.append(f"<p><b>{_esc(tr('why'))}</b><br>{_esc(ex.why)}</p>")
        if ex.steps:
            html.append(f"<p><b>{_esc(tr('steps'))}</b></p><ol>" + "".join(f"<li>{_esc(s)}</li>" for s in ex.steps) + "</ol>")
        self.detail_title.setText(tr("details"))
        row = self.model.row_of_seq(seq) if seq is not None else None
        if row is not None:
            self.table.selectRow(row)
            self.table.scrollTo(self.model.index(row, 0), QAbstractItemView.PositionAtCenter)
        self.detail.setHtml("".join(html))

    def shutdown(self):
        self.stop()
        if self.record_path:
            try:
                os.unlink(self.record_path)
            except OSError:
                pass


def _ask_node(parent) -> tuple[int, bool]:
    from PySide6.QtWidgets import QInputDialog

    return QInputDialog.getInt(parent, "EDS", "Node-ID", 1, 1, 127)


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")).replace("\n", "<br>")
