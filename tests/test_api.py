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
