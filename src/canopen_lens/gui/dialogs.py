"""Help and glossary dialogs."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

from ..explain import glossary
from .i18n import Tr


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _code(s: str) -> str:
    # `like this` -> <code>like this</code>
    parts = _esc(s).split("`")
    return "".join(f"<code>{p}</code>" if i % 2 else p for i, p in enumerate(parts))


class TextDialog(QDialog):
    def __init__(self, title: str, html: str, parent=None, close_text: str = "Close"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 620)
        lay = QVBoxLayout(self)
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        view.setHtml(html)
        lay.addWidget(view)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText(close_text)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)


def glossary_dialog(tr: Tr, parent=None) -> TextDialog:
    rows = "".join(
        f"<tr><td valign='top' style='padding:6px 14px 6px 0; white-space:nowrap'><b>{_esc(term)}</b></td>"
        f"<td valign='top' style='padding:6px 0'>{_code(text)}</td></tr>"
        for term, text in glossary(tr.lang))
    html = f"<h3>{_esc(tr('glossary_title'))}</h3><table cellspacing='0'>{rows}</table>"
    return TextDialog(tr("glossary"), html, parent, tr("close"))


def help_dialog(tr: Tr, parent=None) -> TextDialog:
    return TextDialog(tr("help"), tr("help_html"), parent, tr("close"))
