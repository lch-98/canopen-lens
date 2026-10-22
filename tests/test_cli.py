"""The command line: short summary by default, details and saving on request, ko/en."""

import json
from pathlib import Path

import pytest

from canopen_lens.cli import default_lang, main, pad, width

EX = Path(__file__).resolve().parent.parent / "src" / "canopen_lens" / "examples"
MIXED = str(EX / "sample_cia402.log")
AMR = str(EX / "sample_amr_2wheel.log")


@pytest.fixture(autouse=True)
def korean(monkeypatch):
    monkeypatch.setenv("CANOPEN_LENS_LANG", "ko")
    monkeypatch.setenv("NO_COLOR", "1")


def run(capsys, *args):
    code = main(list(args))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_summary_is_short_and_grouped(capsys):
    code, out, _ = run(capsys, MIXED)
    assert code == 0
    lines = out.strip().splitlines()
    assert len(lines) <= 20
    assert lines[0].startswith("✖ 확인이 필요합니다") and "해결 안 됨 3" in lines[0]
    assert "과전류로 멈춤 → 두 번째 리셋에서 회복" in out
    assert "경고" in out and "CAN 선 오류 1회" in out and "정상      노드 1" in out
    assert f"canopen-lens {Path(MIXED).name} -d 1" in out
    assert "\033[" not in out                     # NO_COLOR


def test_english_and_language_switch(capsys, monkeypatch):
    _, out, _ = run(capsys, MIXED, "--lang", "en")
    assert out.startswith("✖ Needs attention") and "Unresolved" in out
    monkeypatch.setenv("CANOPEN_LENS_LANG", "en")
    assert default_lang() == "en"
    _, out, _ = run(capsys, "--help")
    assert "Usage" in out and "canopen-lens examples" in out


def test_detail_and_all(capsys):
    _, out, _ = run(capsys, MIXED, "-d", "5")
    assert out.startswith("5  회복됨  노드 2") and "무슨 일이 있었나요" in out and "먼저 확인할 것" in out
    assert "첫 번째 리셋 실패" in out and "#2465" in out
    _, out, _ = run(capsys, MIXED, "-d", "all")
    assert out.count("먼저 확인할 것") == 7


def test_save_by_extension_and_check(capsys, tmp_path):
    txt, csv, js = tmp_path / "r.txt", tmp_path / "r.csv", tmp_path / "r.json"
    code, out, _ = run(capsys, MIXED, "-s", str(txt), "-s", str(csv), "-s", str(js), "--check")
    assert code == 1 and out.count("저장했습니다") == 3
    assert txt.read_text(encoding="utf-8-sig").count("먼저 확인할 것") == 7
    assert csv.read_bytes().startswith(b"\xef\xbb\xbf")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["summary"]["counts"]["open"] == 3 and data["incidents"][0]["number"] == 1
    code, _, _ = run(capsys, AMR, "--check")          # everything recovered
    assert code == 0


def test_mistakes_are_explained(capsys):
    code, _, err = run(capsys, "nope.log")
    assert code == 2 and "파일을 찾을 수 없습니다" in err and "Traceback" not in err
    code, _, err = run(capsys, MIXED, "-d", "42")
    assert code == 2 and "1~7" in err
    code, _, err = run(capsys, MIXED, "--bogus")
    assert code == 2 and "명령을 이해하지 못했습니다" in err
    code, _, err = run(capsys, MIXED, "-s", "x.xlsx")
    assert code == 2 and ".csv" in err


def test_examples_command(capsys, tmp_path):
    code, out, _ = run(capsys, "examples", str(tmp_path))
    assert code == 0 and (tmp_path / "sample_cia402.log").is_file() and (tmp_path / "sample_amr_2wheel.log").is_file()
    assert "sample_cia402.log" in out


def test_legacy_report_still_works(capsys):
    code, out, _ = run(capsys, "report", MIXED, "--brief", "--fail-on-error")
    assert code == 1 and "fault" in out


def test_wide_characters_line_up():
    assert width("노드 2") == 6 and width(pad("노드 2", 10)) == 10


def test_lang_only_opens_window_in_that_language(monkeypatch):
    import canopen_lens.gui as gui

    seen = {}
    monkeypatch.setattr(gui, "main", lambda argv: seen.setdefault("argv", argv) and 0)
    main(["--lang", "en"])
    assert seen["argv"] == ["canopen-lens", "--lang=en"]
