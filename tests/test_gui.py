import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from canopen_lens import Severity, open_log  # noqa: E402
from canopen_lens.gui.app import SAMPLE_LOG, MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_gui_shows_sample(app):
    w = MainWindow("ko")
    w.set_log(open_log(SAMPLE_LOG), str(SAMPLE_LOG))
    app.processEvents()
    assert w.model.rowCount() == len(w.log)
    errors = w.log.count_issues()[Severity.ERROR]
    assert w.card_err.value.text() == str(errors)
    # selecting the first finding jumps to its frame
    first = w.issue_list.currentItem().data(0x0100)
    assert w.current_frame_row() == first.row
    # filters
    w.issues_only.setChecked(True)
    assert 0 < w.model.rowCount() < len(w.log)
    w.toggle_language()
    app.processEvents()
    assert w.tr_.lang == "en"
    w.center_tabs.setCurrentIndex(1)
    app.processEvents()
    assert w.timeline.lanes
    w.close()


def test_sample_is_packaged():
    assert Path(SAMPLE_LOG).is_file()
