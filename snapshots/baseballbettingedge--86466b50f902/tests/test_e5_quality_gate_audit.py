import json

from analytics.diagnostics.e5_quality_gate_audit import (
    build_report,
    filter_rows,
    load_history,
)


def test_load_history_reads_json_list(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(json.dumps([{"date": "2026-04-28", "pitcher": "A"}]), encoding="utf-8")

    assert load_history(path) == [{"date": "2026-04-28", "pitcher": "A"}]


def test_default_since_filter_excludes_pre_cutover_rows():
    rows = [
        {"date": "2026-04-27", "pitcher": "Transition"},
        {"date": "2026-04-28", "pitcher": "Clean start"},
        {"date": "2026-04-29", "pitcher": "Clean next"},
    ]

    filtered = filter_rows(rows)

    assert [row["pitcher"] for row in filtered] == ["Clean start", "Clean next"]


def test_all_history_bypasses_default_since_filter():
    rows = [
        {"date": "2026-04-27", "pitcher": "Transition"},
        {"date": "2026-04-28", "pitcher": "Clean"},
    ]

    assert filter_rows(rows, all_history=True) == rows


def test_raw_and_actionable_counts_differ_when_fire_2u_is_capped():
    rows = [
        {
            "date": "2026-04-28",
            "pitcher": "Capped Arm",
            "raw_verdict": "FIRE 2u",
            "actionable_verdict": "LEAN",
            "quality_gate_level": "capped",
            "input_quality_flags": ["projected_lineup"],
        },
        {
            "date": "2026-04-28",
            "pitcher": "Clean Arm",
            "raw_verdict": "FIRE 1u",
            "actionable_verdict": "FIRE 1u",
            "quality_gate_level": "clean",
        },
    ]

    report = build_report(rows)

    assert "- `FIRE 2u`: 1" in report
    assert "- `LEAN`: 1" in report
    assert "- `FIRE 1u`: 1" in report
    assert "- Protected raw `FIRE 2u` rows: 1" in report


def test_blocked_raw_fire_2u_is_counted_as_protection():
    rows = [
        {
            "date": "2026-04-28",
            "pitcher": "Blocked Arm",
            "team": "ARI",
            "opp_team": "LAD",
            "side": "over",
            "line": 5.5,
            "raw_verdict": "FIRE 2u",
            "actionable_verdict": "PASS",
            "quality_gate_level": "blocked",
            "verdict_cap_reason": "starter_mismatch",
            "input_quality_flags": ["starter_mismatch"],
            "raw_adj_ev": 0.21,
        }
    ]

    report = build_report(rows)

    assert "- Protected raw `FIRE 2u` rows: 1" in report
    assert "- `blocked`: 1" in report
    assert "`Blocked Arm`" in report
    assert "starter_mismatch" in report


def test_missing_quality_fields_default_clean_and_verdict_fallback_works():
    rows = [
        {
            "date": "2026-04-28",
            "pitcher": "Legacy Arm",
            "verdict": "FIRE 2u",
            "result": "win",
            "pnl": 0.91,
        }
    ]

    report = build_report(rows)

    assert "- `FIRE 2u`: 1" in report
    assert "- `clean`: 1" in report
    assert "- No input quality flags found." in report
    assert "- `clean`: graded=1, wins=1, losses=0, avg_pnl=+0.91" in report


def test_report_includes_flag_names_and_gate_levels():
    rows = [
        {
            "date": "2026-04-28",
            "pitcher": "Flagged Arm",
            "verdict": "FIRE 1u",
            "raw_verdict": "FIRE 2u",
            "actionable_verdict": "FIRE 1u",
            "quality_gate_level": "capped",
            "input_quality_flags": ["projected_lineup", "thin_recent_start_sample"],
            "result": "loss",
            "pnl": -1.0,
        }
    ]

    report = build_report(rows)

    assert "## Quality Gate Levels" in report
    assert "- `capped`: 1" in report
    assert "## Input Quality Flags" in report
    assert "- `projected_lineup`: 1" in report
    assert "- `thin_recent_start_sample`: 1" in report
