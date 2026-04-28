import pytest

from analytics.diagnostics.e4_bet_selection_audit import (
    adj_ev_bucket,
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
