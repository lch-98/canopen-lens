"""Library-facing features: plain-language explanations, export, live decoding, CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from canopen_lens import IssueType, LiveDecoder, Severity, glossary, open_log

HERE = Path(__file__).resolve().parent
SAMPLE = HERE.parent / "src" / "canopen_lens" / "examples" / "sample_cia402.log"
EDS = HERE / "data" / "sample_drive.eds"


@pytest.fixture(scope="module")
def log():
    return open_log(SAMPLE)


def test_every_finding_has_a_full_explanation(log):
    for issue in log.issues:
        for lang in ("ko", "en"):
            ex = log.explain(issue, lang)
            assert ex.title and ex.what
            if issue.severity != Severity.INFO:
                assert ex.why and ex.steps, issue.type


def test_health_summary(log):
    h = log.health("en")
    assert h.level == "error"
    levels = {n.node: n.level for n in h.nodes}
    assert levels[1] == "ok"
    assert levels[5] == "warning"          # faulted but recovered
    assert levels[3] == "error"            # heartbeat lost at the end
    assert any("recovered" in d for d in next(n for n in h.nodes if n.node == 5).details)
    text = log.report("ko")
    assert "먼저 확인할 것" in text and "노드 5가" in text


def test_grouping_collapses_repeats():
    lines = [f"({k * 0.1:.1f}) can0 601#2B01200001000000\n({k * 0.1 + 0.001:.3f}) can0 581#8001200000000206"
             for k in range(20)]
    from canopen_lens import CanopenLog

    lg = CanopenLog.from_text("\n".join(lines))
    groups = lg.grouped_issues()
    assert len(lg.issues) == 20 and len(groups) == 1 and groups[0].count == 20


def test_korean_particles():
    from canopen_lens.explain import josa

    assert josa(2, "이가") == "2가" and josa(3, "이가") == "3이" and josa(10, "은는") == "10은"


def test_export_dataframe_csv_json(log, tmp_path):
    pd = pytest.importorskip("pandas")
    df = log.to_dataframe("en")
    assert len(df) == len(log) and str(df["node"].dtype) == "Int64"
    assert df["meaning"].str.contains("Fault").any()
    csv_path = tmp_path / "frames.csv"
    log.to_csv(csv_path, "ko")
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")     # Excel-friendly UTF-8
    back = pd.read_csv(csv_path, encoding="utf-8-sig")
    assert len(back) == len(log)
    d = json.loads(log.to_json(tmp_path / "r.json", "en"))
    assert d["verdict"] == "error" and d["findings"] and d["findings"][0]["steps"]
    assert (tmp_path / "r.json").exists()
    emcy_rows = log.trace.filter(kinds=[__import__("canopen_lens").Kind.EMCY])
    assert len(list(log.frames("en", emcy_rows))) == len(emcy_rows)


def test_live_decoder_matches_offline(log):
    dec = LiveDecoder()
    tr = log.trace
    found = []
    for i in range(len(tr)):
        f = tr.frame(i)
        found += dec.feed(tr.t0 + f.t, f.id, f.data, is_extended=f.ext, is_remote=f.rtr, is_error=f.error)
    found += dec.tick(tr.t0 + tr.duration)
    key = lambda i: (int(i.type), i.node, i.axis)  # noqa: E731
    # Same findings as offline. Live also says "heartbeat lost" while a gap is still
    # going on (it cannot know yet that the node will come back), so compare as sets.
    assert set(map(key, found)) == set(map(key, log.issues))
    assert dec.frame_count == len(tr)
    nodes = {n.node: n for n in dec.nodes}
    assert nodes[5].axis_count == 2 and nodes[5].is_drive and not nodes[3].is_drive


def test_live_decoder_reports_silence_and_explains():
    dec = LiveDecoder()
    for k in range(10):
        assert dec.feed(100.0 + k * 0.1, 0x703, b"\x05") == []
    assert "Operational" in dec.last_summary("en")
    found = dec.tick(100.0 + 0.9 + 1.0)
    assert [i.type for i in found] == [IssueType.HEARTBEAT_LOST]
    assert dec.explain(found[0], "en").steps
    assert dec.tick(100.0 + 3.0) == []          # reported once


def test_live_decoder_with_eds_and_python_can():
    can = pytest.importorskip("can")
    dec = LiveDecoder(eds={5: EDS})
    msg = can.Message(timestamp=10.0, arbitration_id=0x185, data=bytes.fromhex("3702E8030000"), is_extended_id=False)
    dec.feed_message(msg)
    assert "1000" in dec.last_summary("en") and "Enabled" in dec.last_summary("en")


def test_feed_lines():
    dec = LiveDecoder()
    found = dec.feed_lines(["(1.000000) can0 605#4000100000000000", "(1.000500) can0 585#80001000000002060"[:-1]])
    assert [i.type for i in found] == [IssueType.SDO_ABORT]


def test_glossary_terms():
    assert len(glossary("ko")) == len(glossary("en")) >= 15


def test_cli_json_and_brief(tmp_path):
    out = tmp_path / "r.json"
    cmd = [sys.executable, "-m", "canopen_lens", "report", str(SAMPLE), "--format", "json", "-o", str(out)]
    assert subprocess.run(cmd).returncode == 0
    assert json.loads(out.read_text(encoding="utf-8"))["frames"] > 0
    r = subprocess.run([sys.executable, "-m", "canopen_lens", "report", str(SAMPLE), "--brief", "--fail-on-error"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "fault" in r.stdout


def test_axis1_objects_are_labelled_on_multi_axis_nodes(log):
    rows = log.trace.filter(kinds=[__import__("canopen_lens").Kind.TPDO], node=5)
    row = int(rows[0])
    labels = [k for k, _ in log.details(row, "ko")]
    assert "0x6041:00 축 1 스테이터스워드" in labels
    assert "0x6841:00 축 2 스테이터스워드" in labels
    # single-axis drives keep the plain name
    row2 = int(log.trace.filter(kinds=[__import__("canopen_lens").Kind.TPDO], node=2)[0])
    assert "0x6041:00 스테이터스워드" in [k for k, _ in log.details(row2, "ko")]


def test_assumed_mapping_explains_why(log):
    row = int(log.trace.filter(kinds=[__import__("canopen_lens").Kind.TPDO], node=2)[0])
    d = dict(log.details(row, "ko"))
    assert "추정" in d["PDO 매핑 출처"]
    assert "8행" in d["추정 근거"] and "0x1000" in d["추정 근거"] and "EDS" in d["추정 근거"]
    d_en = dict(log.details(row, "en"))
    assert "Row 8" in d_en["Why assumed"]


def test_byte_breakdown_explains_sdo_bytes(log):
    rows = log.byte_breakdown(7, "en")           # 43 00 10 00 92 01 02 00
    assert [b for b, _ in rows] == ["43", "00 10", "00", "92 01 02 00"]
    assert "read reply" in rows[0][1] and "e=1" in rows[0][1]
    assert "0x1000" in rows[1][1]
    assert "0x00020192 = 131474" in rows[3][1] and "CiA 402" in rows[3][1] and "servo" in rows[3][1]
    assert "least significant byte first" in rows[3][1]
    ko = log.byte_breakdown(7, "ko")
    assert "서보 드라이브" in ko[3][1]


def test_byte_breakdown_other_kinds(log):
    from canopen_lens import Kind

    tr = log.trace
    for kind, expect in ((Kind.EMCY, "error code"), (Kind.HEARTBEAT, "NMT state"), (Kind.NMT, "NMT command")):
        row = int(tr.filter(kinds=[kind])[0])
        assert expect in log.byte_breakdown(row, "en")[0][1]
    pdo = int(tr.filter(kinds=[Kind.TPDO], node=5)[0])
    assert len(log.byte_breakdown(pdo, "en")) == 3


def test_non_canopen_log_is_flagged():
    import random

    from canopen_lens import CanopenLog

    rnd = random.Random(1)
    lines = []
    for k in range(200):
        t = k * 0.01
        lines.append(f"({t:.6f}) can0 316#{rnd.randbytes(8).hex()}")
        lines.append(f"({t + 0.002:.6f}) can0 1A0#{rnd.randbytes(4).hex()}")
    lg = CanopenLog.from_text("\n".join(lines))
    p = lg.protocol_check("en")
    assert p.looks_like_canopen is False and "management" in p.text
    h = lg.health("en")
    assert h.level == "warning" and h.headline == p.title
    stats = {d["id"]: d for d in lg.id_statistics()}
    assert stats["0x316"]["count"] == 200 and abs(stats["0x316"]["period_ms"] - 10.0) < 0.01
    assert "Traffic by ID" in lg.report("en")

    j1939 = CanopenLog.from_text("\n".join(f"({k * 0.1:.1f}) can0 18FEF100#0102030405060708" for k in range(30)))
    assert j1939.protocol_check("en").looks_like_canopen is False and "29-bit" in j1939.protocol_check("en").text


def test_sample_is_canopen(log):
    assert log.protocol_check().looks_like_canopen is True


def test_live_snapshots_keep_their_meaning(log):
    dec = LiveDecoder()
    tr = log.trace
    snaps = []
    for i in range(200):
        f = tr.frame(i)
        dec.feed(tr.t0 + f.t, f.id, f.data, is_extended=f.ext, is_remote=f.rtr, is_error=f.error)
        snaps.append(dec.snapshot())
    for i in (7, 25, 86, 150):
        assert snaps[i].summary("ko") == log.summary(i, "ko")
    assert snaps[7].byte_breakdown("en")[3][0] == "92 01 02 00"


def test_live_clock_alignment():
    can = pytest.importorskip("can")
    import time

    dec = LiveDecoder()
    # an interface that stamps frames with "seconds since boot"
    for k in range(10):
        dec.feed_message(can.Message(timestamp=5.0 + k * 0.1, arbitration_id=0x701, data=b"\x05", is_extended_id=False))
    assert dec.tick(time.time()) == []           # must not look like a 1.7-billion-second silence


def test_missing_gui_explains_how_to_install(monkeypatch, capsys):
    import importlib.util
    from canopen_lens import gui

    monkeypatch.setitem(sys.modules, "canopen_lens.gui.app", None)       # import fails
    monkeypatch.setenv("CANOPEN_LENS_LANG", "ko")
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "PySide6" else real(name, *a))
    with pytest.raises(SystemExit):
        gui.main([])
    err = capsys.readouterr().err
    assert 'pip install "canopen-lens[gui]"' in err and "canopen-lens examples" in err and "PySide6가" in err


def test_missing_gui_message_follows_lang_option(monkeypatch, capsys):
    import importlib.util
    from canopen_lens import gui

    monkeypatch.setitem(sys.modules, "canopen_lens.gui.app", None)
    monkeypatch.setenv("CANOPEN_LENS_LANG", "ko")                         # computer says Korean …
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "PySide6" else real(name, *a))
    with pytest.raises(SystemExit):
        gui.main(["canopen-lens", "--lang", "en"])                       # … but English was asked for
    err = capsys.readouterr().err
    assert err.startswith("canopen-lens: the desktop app needs PySide6")
    assert "한국어:" in err                                                # one line in the other language
