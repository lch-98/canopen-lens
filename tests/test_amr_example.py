"""The two-wheel AMR example: a ros2_canopen master configuring an STM32 two-axis drive."""

from pathlib import Path

import pytest

from canopen_lens import IssueType, open_log

HERE = Path(__file__).resolve().parent
AMR = HERE.parent / "src" / "canopen_lens" / "examples" / "sample_amr_2wheel.log"


@pytest.fixture(scope="module")
def log():
    return open_log(AMR)


def _row(log, frame: str) -> int:
    for i, line in enumerate(AMR.read_text().splitlines()):
        if line.endswith(frame):
            return i
    raise AssertionError(frame)


def test_example_is_up_to_date(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_amr_sample", HERE / "make_amr_sample.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.build() == AMR.read_text()


def test_drive_found_although_device_type_is_zero(log):
    # the STM32 answers 0x1000 with 0 (no profile); the PDO mapping still identifies it
    nodes = {n.node: n for n in log.trace.nodes}
    assert nodes[1].is_drive and nodes[1].axis_count == 2
    assert not nodes[2].is_drive
    assert "프로파일이 적혀 있지 않음" in log.summary(_row(log, "581#4300100000000000"), "ko")


def test_pdo_cob_id_writes_are_explained(log):
    off = log.summary(_row(log, "601#2300180181010080"), "ko")
    on = log.summary(_row(log, "601#2300180181010000"), "ko")
    assert "ID 0x181" in off and "꺼짐" in off and "기본값" in off
    assert "켜짐" in on
    assert "SYNC 1번마다" in log.summary(_row(log, "601#2F00180201000000"), "ko")
    assert "노드 2의 하트비트를 300 ms" in log.summary(_row(log, "601#231610012C010200"), "ko")
    assert "PV" in log.summary(_row(log, "581#4302650004000000"), "ko")


def test_all_four_tpdos_follow_the_sdo_mapping(log):
    text = " ".join(log.summary(i, "ko") for i in range(len(log.trace))
                    if log.trace.frame(i).id in (0x181, 0x281, 0x381, 0x481) and log.trace.frame(i).t > 6.0)
    for word in ("축 1 상태", "축 1 실제 속도", "축 1 실제 위치", "축 2 상태", "축 2 실제 속도", "축 2 실제 위치"):
        assert word in text
    assert "추정" not in text


def test_estop_faults_both_axes_without_emcy_and_recovers(log):
    faults = [i for i in log.issues if i.type == IssueType.AXIS_FAULT]
    assert sorted(i.axis for i in faults) == [0, 1]
    assert {i.type for i in log.issues} == {IssueType.AXIS_FAULT}
    ex = log.explain(faults[0], "ko")
    assert "EMCY)는 없었습니다" in ex.what and "축 2도 같은 순간" in ex.what
    h = log.health("ko")
    assert h.level == "warning" and "회복" in h.headline


def test_mode_names_are_in_the_chosen_language(log):
    row = _row(log, "181#270003")
    assert "프로파일 속도 (PV)" in log.summary(row, "ko")
    assert "Profile velocity (PV)" in log.summary(row, "en")


def test_live_decoder_explains_the_same_faults():
    from canopen_lens import LiveDecoder
    dec = LiveDecoder()
    dec.feed_lines(AMR.read_text().splitlines())
    faults = [i for i in dec.issues if i.type == IssueType.AXIS_FAULT]
    assert sorted(i.axis for i in faults) == [0, 1]
    assert "EMCY)는 없었습니다" in dec.explain(faults[-1], "ko").what
