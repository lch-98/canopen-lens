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


def test_timeline_zoom(app):
    from canopen_lens.gui.app import EXAMPLE_DIR, TIMELINE_TAB
    from canopen_lens.gui.timeline import format_duration, nice_step

    assert nice_step(32.0, 10) == 5.0 and nice_step(0.45, 10) == 0.05 and nice_step(0.004, 8) == 0.0005
    assert format_duration(0.04) == "40 ms" and format_duration(1.5) == "1.50 s" and format_duration(0.0004) == "0.40 ms"

    p = str(EXAMPLE_DIR / "sample_amr_2wheel.log")
    w = MainWindow("ko")
    w.resize(1400, 900)
    w.show()
    w.set_log(open_log(p), p)
    w.center_tabs.setCurrentIndex(TIMELINE_TAB)
    app.processEvents()
    tl = w.timeline
    assert (tl.v0, tl.v1) == (0.0, tl.duration) and not w.timeline_scroll.isEnabled()

    # zooming keeps the time under the pointer in place and never goes past the log
    tl.zoom(0.1, anchor=3.1)
    assert abs((3.1 - tl.v0) / tl.span - 3.1 / tl.duration) < 1e-6 and tl.is_zoomed()
    assert w.timeline_scroll.isEnabled()
    tl.set_view(1.0, 1.0001)
    assert abs(tl.span - tl.MIN_SPAN) < 1e-12
    tl.set_view(-5, -4)
    assert tl.v0 == 0.0 and abs(tl.span - 1.0) < 1e-9
    tl.set_view(tl.duration - 1, tl.duration + 5)
    assert abs(tl.v1 - tl.duration) < 1e-9

    # a 40 ms state is wide enough to hover once zoomed in, and can be found from a few px away
    tl.set_view(2.95, 3.40)
    lane = tl.lanes[0]
    short = next(s for s in lane.segments if 0.03 < s.t1 - s.t0 < 0.05)
    x0, x1 = tl._x(short.t0), tl._x(short.t1)
    assert x1 - x0 > 20
    assert tl._segment_at(lane, (x0 + x1) / 2) is short
    tl.fit()
    assert tl._segment_at(lane, tl._x(short.t0) + 1) is short     # drawn at least MIN_SEG_PX wide

    # keyboard: next state change, Enter opens the message
    tl.sel_lane, tl.cursor_t = 0, 2.9
    tl.step_change(1)
    first = tl.cursor_t
    tl.step_change(1)
    assert tl.cursor_t > first and "Enter" in w.timeline_cursor.text()
    rows = []
    tl.rowActivated.connect(rows.append)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    app.sendEvent(tl, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
    assert rows

    # "show on timeline" from a finding zooms there and selects the faulted axis
    fault = next(i for i in w.log.issues if i.axis == 1)
    w.show_on_timeline(float(fault.t))
    assert w.center_tabs.currentIndex() == TIMELINE_TAB
    assert tl.v0 <= fault.t <= tl.v1 and tl.span <= 2.0 + 1e-9
    assert "축 2" in tl.lanes[tl.sel_lane].title and "Fault" in w.timeline_cursor.text()

    # scroll bar moves the zoomed view
    w.timeline_scroll.setValue(w.timeline_scroll.value() + 1000)
    assert tl.v0 > fault.t - 1.0
    tl.fit()
    assert not tl.is_zoomed()
    w.close()
