"""Findings grouped into incidents: one story per problem."""

from pathlib import Path

import pytest

from canopen_lens import open_log

HERE = Path(__file__).resolve().parent
EX = HERE.parent / "src" / "canopen_lens" / "examples"


@pytest.fixture(scope="module")
def mixed():
    return open_log(EX / "sample_cia402.log")


@pytest.fixture(scope="module")
def amr():
    return open_log(EX / "sample_amr_2wheel.log")


def test_mixed_example_becomes_five_problems_and_two_warnings(mixed):
    ov = mixed.overview("ko")
    assert ov.level == "error" and ov.headline == "확인이 필요합니다"
    assert ov.counts == {"open": 3, "recovered": 2, "warning": 2, "ok": 1}
    assert [i.number for i in ov.incidents] == list(range(1, 8))
    # unresolved first, then recovered, then warnings
    assert [i.status for i in ov.incidents] == ["open"] * 3 + ["recovered"] * 2 + ["warning"] * 2
    # every finding that matters ends up in exactly one incident
    placed = [id(x) for i in ov.incidents for x in i.issues]
    assert len(placed) == len(set(placed))
    important = [x for x in mixed.issues if int(x.severity) > 0]
    assert all(any(x.row == y.row and x.type == y.type for i in ov.incidents for y in i.issues) for x in important)


def test_fault_emcy_and_failed_reset_are_one_story(mixed):
    inc = next(i for i in mixed.incidents("ko") if i.node == 2 and i.status == "recovered")
    assert inc.title == "과전류로 멈춤 → 두 번째 리셋에서 회복"
    texts = [e.text for e in inc.events]
    assert texts[0].startswith("Fault로 정지") and "과전류" in texts[1] and "첫 번째 리셋 실패" in texts[2]
    assert texts[-1] == "다시 운전" and inc.t < inc.t_end
    assert len(inc.steps) <= 3
    en = next(i for i in mixed.incidents("en") if i.node == 2 and i.status == "recovered")
    assert "reset #2" in en.title


def test_missing_node_and_devices(mixed):
    ov = mixed.overview("ko")
    missing = next(i for i in ov.incidents if i.node == 4)
    assert "버스에 없는" in missing.title and missing.status == "open"
    words = {d.node: d.status_word for d in ov.devices}
    assert words == {1: "정상", 2: "설정 실패", 3: "끊김", 4: "응답 없음", 5: "회복됨"}
    assert next(d for d in ov.devices if d.node == 5).kind == "2축 드라이브"


def test_amr_estop_is_one_incident_on_both_axes(amr):
    ov = amr.overview("ko")
    assert ov.level == "warning" and ov.counts["open"] == 0 and ov.counts["recovered"] == 1
    inc = ov.incidents[0]
    assert inc.where == "노드 1 · 축 1·2" and inc.axes == [0, 1]
    assert "원인 보고 없음" in inc.title and "비상정지" in inc.hint
    assert {d.node: d.kind for d in ov.devices}[2] == "마스터로 보임"


def test_incident_dict_is_json_ready(mixed):
    import json

    d = [i.as_dict() for i in mixed.incidents("en")]
    assert json.loads(json.dumps(d))[0]["number"] == 1
