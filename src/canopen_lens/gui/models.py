"""Qt models backed by the C++ trace. Rows are formatted lazily, so even very
large logs stay responsive: only the visible rows are ever turned into text."""

from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from .. import describe
from .._core import AxisState, Kind
from ..log import CanopenLog
from .i18n import Tr

KIND_COLORS = {
    Kind.NMT: "#7c3aed",
    Kind.SYNC: "#64748b",
    Kind.EMCY: "#dc2626",
    Kind.TIME: "#64748b",
    Kind.TPDO: "#0f766e",
    Kind.RPDO: "#2563eb",
    Kind.SDO_REQ: "#b45309",
    Kind.SDO_RESP: "#b45309",
    Kind.HEARTBEAT: "#475569",
    Kind.LSS: "#64748b",
    Kind.ERROR_FRAME: "#dc2626",
    Kind.UNKNOWN: "#94a3b8",
}


class FrameTableModel(QAbstractTableModel):
    COLS = ["col_no", "col_time", "col_node", "col_kind", "col_meaning", "col_id", "col_data"]

    def __init__(self, tr: Tr, parent=None):
        super().__init__(parent)
        self.tr_ = tr
        self.log: Optional[CanopenLog] = None
        self.rows = []  # IndexList or list of frame indices
        self._cache: "OrderedDict[int, str]" = OrderedDict()
        self._mono = QFont("monospace")
        self._mono.setStyleHint(QFont.Monospace)
        self._issue_bg = QBrush(QColor("#fde8e8"))
        self._fault_fg = QBrush(QColor("#b91c1c"))

    # -- data source ---------------------------------------------------------
    def set_log(self, log: Optional[CanopenLog], rows) -> None:
        self.beginResetModel()
        self.log = log
        self.rows = rows if rows is not None else []
        self._cache.clear()
        self.endResetModel()

    def set_rows(self, rows) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def clear_cache(self) -> None:
        self._cache.clear()
        if self.rowCount():
            self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))

    def frame_row(self, view_row: int) -> int:
        return int(self.rows[view_row])

    def view_row_of(self, frame_row: int) -> Optional[int]:
        # rows are sorted, so a binary search is enough
        lo, hi = 0, len(self.rows)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.rows[mid] < frame_row:
                lo = mid + 1
            else:
                hi = mid
        if lo < len(self.rows) and self.rows[lo] == frame_row:
            return lo
        return None

    def nearest_view_row(self, frame_row: int) -> Optional[int]:
        if not len(self.rows):
            return None
        lo, hi = 0, len(self.rows)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.rows[mid] < frame_row:
                lo = mid + 1
            else:
                hi = mid
        return min(lo, len(self.rows) - 1)

    def _summary(self, row: int) -> str:
        s = self._cache.get(row)
        if s is None:
            s = describe.frame_summary(self.log, row, self.tr_.lang)
            self._cache[row] = s
            if len(self._cache) > 5000:
                self._cache.popitem(last=False)
        return s

    # -- Qt interface ----------------------------------------------------------
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.tr_(self.COLS[section])
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or self.log is None:
            return None
        row = int(self.rows[index.row()])
        col = index.column()
        tr = self.log.trace
        if role == Qt.DisplayRole:
            f = tr.frame(row)
            if col == 0:
                return row + 1
            if col == 1:
                return f"{f.t:.6f}"
            if col == 2:
                r = tr.record(row)
                return str(r.node) if r.node else "-"
            if col == 3:
                r = tr.record(row)
                label = describe.kind_label(r.kind, self.tr_.lang)
                if r.pdo_num:
                    label += str(r.pdo_num)
                return label
            if col == 4:
                return self._summary(row)
            if col == 5:
                return f"0x{f.id:08X}" if f.ext else f"0x{f.id:03X}"
            if col == 6:
                return "RTR" if f.rtr else f.data.hex(" ").upper()
        elif role == Qt.ForegroundRole:
            r = tr.record(row)
            if col == 3:
                return QBrush(QColor(KIND_COLORS.get(r.kind, "#334155")))
            if col == 4 and r.has_statusword and r.axis_state in (AxisState.FAULT, AxisState.FAULT_REACTION_ACTIVE):
                return self._fault_fg
        elif role == Qt.BackgroundRole:
            if tr.record(row).has_issue:
                return self._issue_bg
        elif role == Qt.FontRole:
            if col in (5, 6):
                return self._mono
        elif role == Qt.TextAlignmentRole:
            if col in (0, 1, 2):
                return int(Qt.AlignRight | Qt.AlignVCenter)
        elif role == Qt.ToolTipRole and col in (3, 4):
            r = tr.record(row)
            help_text = describe.kind_help(r.kind, self.tr_.lang)
            return f"{self._summary(row)}\n\n{help_text}" if col == 4 else help_text
        return None
