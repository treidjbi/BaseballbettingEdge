import pytest

from analytics.diagnostics.e4_bet_selection_audit import (
    adj_ev_bucket,
    build_bet_selection_report,
    edge_bucket,
    stake_units,
    summarize_by_adj_ev_bucket,
    summarize_by_edge_bucket,
    summarize_by_verdict,
    verdict_bucket,
)


def test_stake_units_for_current_verdicts():
    assert stake_units("LEAN") == 0
    assert stake_units("FIRE 1u") == 1
    assert stake_units("FIRE 2u") == 2


def test_stake_units_unknown_verdict_defaults_zero():
    assert stake_units("PASS") == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "unknown"),
        (0.0199, "<2%"),
        (0.02, "2-6%"),
        (0.0599, "2-6%"),
        (0.06, "6-17%"),
        (0.1699, "6-17%"),
        (0.17, "17%+"),
    ],
)
def test_adj_ev_bucket_uses_verdict_threshold_boundaries(value, expected):
    assert adj_ev_bucket(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "unknown"),
        (-0.0001, "<0%"),
        (0.0, "0-2%"),
        (0.0199, "0-2%"),
        (0.02, "2-4%"),
        (0.0399, "2-4%"),
        (0.04, "4-6%"),
        (0.0599, "4-6%"),
        (0.06, "6%+"),
    ],
)
def test_edge_bucket_uses_probability_gap_bands(value, expected):
    assert edge_bucket(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("PASS", "PASS"),
        ("LEAN", "LEAN"),
        ("FIRE 1u", "FIRE 1u"),
        ("FIRE 2u", "FIRE 2u"),
        ("sprinkle", "other"),
        (None, "other"),
    ],
)
def test_verdict_bucket_normalizes_known_and_unknown_verdicts(value, expected):
    assert verdict_bucket(value) == expected


def test_summarize_by_verdict_prefers_locked_verdict_for_staking():
    rows = [
        {
            "verdict": "LEAN",
            "locked_verdict": "FIRE 2u",
            "result": "win",
            "pnl": 0.91,
        },
        {
            "verdict": "FIRE 1u",
            "result": "loss",
            "pnl": -1.0,
        },
    ]

    summary = summarize_by_verdict(rows)

    assert summary["FIRE 2u"]["rows"] == 1
    assert summary["FIRE 2u"]["units_risked"] == 2.0
    assert summary["FIRE 2u"]["weighted_pnl"] == pytest.approx(1.82)
    assert summary["FIRE 2u"]["roi"] == pytest.approx(0.91)
    assert summary["FIRE 1u"]["units_risked"] == 1.0
    assert summary["FIRE 1u"]["weighted_pnl"] == pytest.approx(-1.0)


def test_summarize_by_adj_ev_bucket_prefers_locked_adj_ev():
    rows = [
        {
            "adj_ev": 0.04,
            "locked_adj_ev": 0.18,
            "verdict": "LEAN",
            "locked_verdict": "FIRE 2u",
            "result": "loss",
            "pnl": -1.0,
        }
    ]

    summary = summarize_by_adj_ev_bucket(rows)

    assert "17%+" in summary
    assert "2-6%" not in summary
    assert summary["17%+"]["units_risked"] == 2.0


def test_summarize_by_edge_bucket_is_stake_aware():
    rows = [
        {
            "edge": 0.045,
            "verdict": "LEAN",
            "result": "win",
            "pnl": 0.91,
        },
        {
            "edge": 0.041,
            "verdict": "FIRE 1u",
            "result": "loss",
            "pnl": -1.0,
        },
    ]

    summary = summarize_by_edge_bucket(rows)

    assert summary["4-6%"]["graded_rows"] == 2
    assert summary["4-6%"]["wins"] == 1
    assert summary["4-6%"]["losses"] == 1
    assert summary["4-6%"]["units_risked"] == 1.0
    assert summary["4-6%"]["weighted_pnl"] == pytest.approx(-1.0)
    assert summary["4-6%"]["roi"] == pytest.approx(-1.0)


def test_report_presents_clean_window_before_all_history_context():
    rows = [
        {
            "date": "2026-04-27",
            "edge": 0.045,
            "adj_ev": 0.08,
            "verdict": "FIRE 1u",
            "result": "win",
            "pnl": 0.5,
        },
        {
            "date": "2026-04-28",
            "edge": 0.045,
            "adj_ev": 0.08,
            "verdict": "FIRE 1u",
            "result": "loss",
            "pnl": -1.0,
        },
    ]

    report = build_bet_selection_report(rows)

    clean_heading = "## Clean Post-ROI Window (2026-04-28+)"
    context_heading = "## All-History Context"
    clean_start = report.index(clean_heading)
    context_start = report.index(context_heading)
    clean_section = report[clean_start:context_start]
    context_section = report[context_start:]

    assert clean_start < context_start
    assert (
        "- `FIRE 1u`: graded=1, wins=0, losses=1, units=1.0, "
        "weighted_pnl=-1.00, roi=-100.00%"
    ) in clean_section
    assert (
        "- `FIRE 1u`: graded=2, wins=1, losses=1, units=2.0, "
        "weighted_pnl=-0.50, roi=-25.00%"
    ) in context_section


def test_report_says_when_clean_window_has_no_graded_rows():
    rows = [
        {
            "date": "2026-04-27",
            "edge": 0.045,
            "adj_ev": 0.08,
            "verdict": "FIRE 1u",
            "result": "win",
            "pnl": 0.5,
        },
    ]

    report = build_bet_selection_report(rows)
    clean_section = report[
        report.index("## Clean Post-ROI Window (2026-04-28+)"):
        report.index("## All-History Context")
    ]

    assert "- No graded rows in this section yet." in clean_section
