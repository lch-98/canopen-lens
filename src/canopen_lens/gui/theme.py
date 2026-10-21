"""Look of the app: industrial navy with a signal-orange accent (design direction A).

Every colour used by the GUI is defined here once, so the look can be changed in one place.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QApplication, QWidget

# --- tokens -----------------------------------------------------------------------
NAVY = "#0F1B2D"          # header
NAVY_2 = "#1B2A41"        # navigation bar
NAVY_LINE = "#475569"     # outlines of buttons on navy
ON_NAVY = "#FFFFFF"
ON_NAVY_2 = "#CBD5E1"
ACCENT = "#C2410C"        # primary buttons (white text on it passes contrast)
ACCENT_HOVER = "#9A3412"
ACCENT_BRIGHT = "#FB923C" # small marks on navy (logo, selected tab)
GROUND = "#EDF0F4"
SURFACE = "#FFFFFF"
HEAD = "#F1F5F9"          # table headers, panel titles
LINE = "#CBD5E1"
LINE_SOFT = "#E2E8F0"
TEXT = "#0F1B2D"
TEXT_2 = "#475569"
SELECT = "#DBEAFE"

RED = "#C81E1E"           # unresolved
RED_BG = "#FEF2F2"
CYAN = "#0E7490"          # recovered
CYAN_BG = "#ECFEFF"
AMBER = "#B45309"         # warning
AMBER_BG = "#FFFBEB"
AMBER_LINE = "#FDE68A"
GREEN = "#15803D"         # OK

STATUS = {
    "open": (RED, RED_BG),
    "recovered": (CYAN, CYAN_BG),
    "warning": (AMBER, AMBER_BG),
    "ok": (GREEN, "#F0FDF4"),
}
LEVEL = {"error": STATUS["open"], "warning": STATUS["warning"], "ok": STATUS["ok"]}

RADIUS = 4


def mono_font(size_delta: float = 0.0) -> QFont:
    f = QFont("Consolas" if sys.platform.startswith("win") else "DejaVu Sans Mono")
    f.setStyleHint(QFont.Monospace)
    base = QApplication.font().pointSizeF() if QApplication.instance() else 10.0
    f.setPointSizeF(max(base + size_delta, 7.0))
    return f


STYLESHEET = f"""
QMainWindow, #ground {{ background: {GROUND}; }}
QWidget {{ color: {TEXT}; }}
QToolTip {{ color: {TEXT}; background: {SURFACE}; border: 1px solid {LINE}; padding: 4px; }}

#header {{ background: {NAVY}; }}
#header QLabel {{ color: {ON_NAVY}; }}
#header QLabel#fileInfo {{ color: {ON_NAVY_2}; }}
#header QPushButton, #header QToolButton {{
    color: {ON_NAVY}; background: transparent; border: 1px solid {NAVY_LINE};
    border-radius: {RADIUS}px; padding: 6px 12px; }}
#header QPushButton:hover, #header QToolButton:hover {{ background: {NAVY_2}; }}
#header QPushButton:disabled, #header QToolButton:disabled {{ color: #64748B; border-color: #334155; }}
#header QPushButton#primary {{ background: {ACCENT}; border: none; font-weight: bold; padding: 6px 16px; }}
#header QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
#header QToolButton::menu-indicator {{ image: none; width: 0; }}

#nav {{ background: {NAVY_2}; }}
#nav QPushButton {{ color: {ON_NAVY_2}; background: transparent; border: none; border-top: 3px solid transparent;
    padding: 9px 18px 10px 18px; font-size: 10.5pt; }}
#nav QPushButton:hover {{ color: {ON_NAVY}; }}
#nav QPushButton:checked {{ color: {ON_NAVY}; background: {NAVY}; border-top: 3px solid {ACCENT_BRIGHT}; font-weight: bold; }}
#nav QPushButton:disabled {{ color: #64748B; }}

#card {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: {RADIUS}px; }}
#cardHead {{ background: {HEAD}; border-bottom: 1px solid {LINE}; border-top-left-radius: {RADIUS}px; border-top-right-radius: {RADIUS}px; }}
#muted {{ color: {TEXT_2}; }}

QPushButton {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: {RADIUS}px; padding: 5px 12px; }}
QPushButton:hover {{ background: {HEAD}; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: none; font-weight: bold; padding: 6px 16px; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#link {{ border: none; background: transparent; color: {ACCENT}; padding: 2px 0; text-align: left; }}
QPushButton#link:hover {{ color: {ACCENT_HOVER}; text-decoration: underline; }}

QTableView, QTableWidget, QListWidget, QTextBrowser {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: {RADIUS}px;
    selection-background-color: {SELECT}; selection-color: {TEXT}; }}
QHeaderView::section {{ background: {HEAD}; color: {TEXT_2}; border: none; border-bottom: 1px solid {LINE};
    border-right: 1px solid {LINE_SOFT}; padding: 5px 6px; font-weight: bold; }}
QLineEdit, QComboBox {{ background: {SURFACE}; border: 1px solid {LINE}; border-radius: {RADIUS}px; padding: 4px 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QSplitter::handle {{ background: {GROUND}; }}
"""


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(GROUND))
    pal.setColor(QPalette.Base, QColor(SURFACE))
    pal.setColor(QPalette.AlternateBase, QColor("#F8FAFC"))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(SURFACE))
    pal.setColor(QPalette.Highlight, QColor(SELECT))
    pal.setColor(QPalette.HighlightedText, QColor(TEXT))
    app.setPalette(pal)
    font = app.font()
    if sys.platform.startswith("win"):
        font.setFamily("Malgun Gothic")
    font.setPointSizeF(max(font.pointSizeF(), 10.0))
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)


class WaveLogo(QWidget):
    """The small signal-trace mark in the header."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(24, 24))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(ACCENT_BRIGHT), 2.2)
        pen.setCapStyle(Qt.SquareCap)
        p.setPen(pen)
        path = QPainterPath(QPointF(3, 12))
        for x, y in ((7, 12), (9, 6), (13, 18), (15, 12), (21, 12)):
            path.lineTo(x, y)
        p.drawPath(path)
        p.end()
