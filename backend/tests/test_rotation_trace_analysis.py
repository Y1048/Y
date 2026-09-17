import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "tools" / "analyze_rotation_trace.py"
SPEC = importlib.util.spec_from_file_location("rotation_analysis", PATH)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def MakeRow(time_s, sequence=0, session="a"):
    return dict(time_s=time_s, tracked=True, engagement_revision=1,
                anatomical_used=True, source_wrist=[0, 0, 0, 1],
                semantic_wrist=[0, 0, 0, 1], heading=[0, 0, 0, 1],
                last_sent_packet=json.dumps(dict(session_id=session, sequence=sequence,
                                                right=dict(valid=True, rot=[0, 0, 0, 1]))))


def test_sign_and_duplicate_packet_are_not_events():
    rows = [MakeRow(0), MakeRow(.1)]
    rows[1]["source_wrist"] = [0, 0, 0, -1]
    result = analysis.AnalyzeRows(rows)
    assert result["events"] == []
    assert result["unique_packet_snapshots"] == 1


def test_semantic_change_is_distinguished_from_source():
    rows = [MakeRow(0), MakeRow(.1)]
    rows[1]["semantic_wrist"] = [0, 0, 1, 0]
    rows[1]["anatomical_used"] = False
    event = analysis.AnalyzeRows(rows)["events"][0]
    assert event["sample_steps_deg"]["source_wrist"] == 0
    assert event["sample_steps_deg"]["semantic_wrist"] == 180
    assert event["anatomical_selection_changed"]


def test_new_session_does_not_compare_packet_rotation():
    rows = [MakeRow(0, 10), MakeRow(.1, 0, "b")]
    packet = json.loads(rows[1]["last_sent_packet"])
    packet["right"]["rot"] = [0, 1, 0, 0]
    rows[1]["last_sent_packet"] = json.dumps(packet)
    assert analysis.AnalyzeRows(rows)["events"] == []


def test_packet_jump_and_cli_output(tmp_path):
    import subprocess
    import sys

    rows = [MakeRow(0), MakeRow(.1, 1)]
    packet = json.loads(rows[1]["last_sent_packet"])
    packet["right"]["rot"] = [1, 0, 0, 0]
    rows[1]["last_sent_packet"] = json.dumps(packet)
    path = tmp_path / "trace.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    result = subprocess.run([sys.executable, str(PATH), str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(path.with_suffix(".analysis.json").read_text())
    assert report["events"][0]["packet_step_deg"] == 180
    assert "Result saved to:" in result.stdout


def test_tracking_loss_skips_source_delta_but_reports_revision():
    rows = [MakeRow(0), MakeRow(.1)]
    rows[0]["tracked"] = False
    rows[1]["engagement_revision"] = 2
    event = analysis.AnalyzeRows(rows)["events"][0]
    assert event["sample_steps_deg"] == {}
    assert event["engagement_revision_changed"]


@pytest.mark.parametrize("case", ["time", "sequence", "quaternion"])
def test_invalid_input_is_rejected(case):
    rows = [MakeRow(0, 2), MakeRow(.1, 3)]
    if case == "time":
        rows[1]["time_s"] = 0
    elif case == "sequence":
        rows[1] = MakeRow(.1, 1)
    else:
        rows[1]["source_wrist"] = [0, 0, 0, 0]
    with pytest.raises(ValueError):
        analysis.AnalyzeRows(rows)
