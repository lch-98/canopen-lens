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
    from canopen_lens.gui.app import FRAMES_TAB, OVERVIEW_TAB, TIMELINE_TAB

    w = MainWindow("ko")
    w.set_log(open_log(SAMPLE_LOG), str(SAMPLE_LOG))
    app.processEvents()
    assert w.model.rowCount() == len(w.log)
    assert w.center_tabs.currentIndex() == OVERVIEW_TAB          # beginners land on the overview
    groups = w.log.grouped_issues()
    assert w.card_err.value.text() == str(sum(1 for g in groups if g.severity == Severity.ERROR))
    assert w.issue_list.count() == len(groups)                    # repeats are grouped
    # selecting a finding jumps to its frame and explains it
    w.issue_list.setCurrentRow(0)
    first = w.issue_list.currentItem().data(0x0100).first
    assert w.center_tabs.currentIndex() == FRAMES_TAB
    assert w.current_frame_row() == first.row
    assert "확인" in w.detail.toPlainText()
    # raw data is hidden for beginners until asked for
    assert w.table.isColumnHidden(5) and w.table.isColumnHidden(6)
    w.raw_box.setChecked(True)
    assert not w.table.isColumnHidden(5)
    # filters
    w.issues_only.setChecked(True)
    assert 0 < w.model.rowCount() < len(w.log)
    w.toggle_language()
    app.processEvents()
    assert w.tr_.lang == "en"
    w.center_tabs.setCurrentIndex(TIMELINE_TAB)
    app.processEvents()
    assert w.timeline.lanes
    w.close()


def test_export_from_gui(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    w = MainWindow("en")
    w.set_log(open_log(SAMPLE_LOG), str(SAMPLE_LOG))
    for kind in ("txt", "json", "csv"):
        target = tmp_path / f"out.{kind}"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
        w.export(kind)
        assert target.stat().st_size > 100
    w.close()


def test_dialogs(app):
    from canopen_lens.gui.dialogs import glossary_dialog, help_dialog
    from canopen_lens.gui.i18n import Tr

    for lang in ("ko", "en"):
        assert glossary_dialog(Tr(lang)).windowTitle()
        assert help_dialog(Tr(lang)).windowTitle()


def test_sample_is_packaged():
    assert Path(SAMPLE_LOG).is_file()


def test_live_monitor_demo(app, tmp_path):
    import time

    from PySide6.QtCore import QEventLoop, QTimer

    w = MainWindow("ko")
    live = w.live
    live.start(speed=50.0)                      # replay the sample 50x faster
    deadline = time.time() + 15
    while live.running and time.time() < deadline:
        loop = QEventLoop()
        QTimer.singleShot(100, loop.quit)
        loop.exec()
    assert not live.running                     # the replay finished on its own
    assert live.decoder.frame_count == len(open_log(SAMPLE_LOG))
    assert live.model.rowCount() > 0 and live.finding_list.count() > 0
    live._refresh_nodes()
    assert live.node_table.rowCount() == 5
    live.finding_list.setCurrentRow(0)
    assert live.detail.toPlainText()
    live._open_in_analysis()                    # the recording opens in the analysis tab
    deadline = time.time() + 10
    while w.log is None and time.time() < deadline:
        loop = QEventLoop()
        QTimer.singleShot(100, loop.quit)
        loop.exec()
    assert w.modes.currentIndex() == 0 and len(w.log) == live.decoder.frame_count
    w.close()
