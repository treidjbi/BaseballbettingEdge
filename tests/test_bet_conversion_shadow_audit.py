import pytest

from analytics.diagnostics.bet_conversion_shadow_audit import (
    build_report,
    clean_win_loss_rows,
    picked_side_model_margin,
    summarize_strategy,
)


def test_clean_win_loss_rows_keeps_only_post_cutover_win_loss_rows():
    rows = [
        {"date": "2026-04-27", "result": "win", "pitcher": "Transition"},
        {"date": "2026-04-28", "result": "void", "pitcher": "Void"},
        {"date": "2026-04-28", "result": "win", "pitcher": "Clean Win"},
        {"date": "2026-05-07", "result": None, "pitcher": "Open"},
    ]

    filtered = clean_win_loss_rows(rows)

    assert [row["pitcher"] for row in filtered] == ["Clean Win"]


def test_picked_side_model_margin_supports_over_and_under():
    over = {"side": "over", "k_line": 4.5, "applied_lambda": 5.25}
    under = {"side": "under", "k_line": 5.5, "applied_lambda": 4.75}

    assert picked_side_model_margin(over) == 0.75
    assert picked_side_model_margin(under) == 0.75


def test_picked_side_model_margin_uses_locked_line_when_available():
    row = {
        "side": "under",
        "k_line": 6.5,
        "locked_k_line": 5.5,
        "applied_lambda": 4.75,
    }

    assert picked_side_model_margin(row) == 0.75


def test_summarize_strategy_uses_flat_one_unit_pnl():
    rows = [
        {"result": "win", "pnl": 0.91, "verdict": "FIRE 1u"},
        {"result": "loss", "pnl": -1.0, "verdict": "FIRE 2u"},
        {"result": "win", "pnl": 0.83, "verdict": "LEAN"},
    ]

    summary = summarize_strategy(
        "current_fire_flat",
        rows,
        lambda row: str(row.get("verdict", "")).startswith("FIRE"),
    )

    assert summary["selected"] == 2
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["flat_pnl"] == pytest.approx(-0.09)
    assert summary["flat_roi"] == pytest.approx(-0.045)


def test_summarize_strategy_tracks_fire_one_losses_and_fire_two_wins():
    rows = [
        {"result": "loss", "pnl": -1.0, "verdict": "FIRE 1u"},
        {"result": "win", "pnl": 0.91, "verdict": "FIRE 2u"},
        {"result": "loss", "pnl": -1.0, "verdict": "FIRE 2u"},
    ]

    summary = summarize_strategy("all", rows, lambda row: True)

    assert summary["current_fire_1u_losses_selected"] == 1
    assert summary["current_fire_2u_wins_selected"] == 1


def test_build_report_includes_shadow_strategy_sections():
    rows = [
        {
            "date": "2026-04-28",
            "result": "win",
            "pnl": 0.91,
            "verdict": "FIRE 2u",
            "edge": 0.05,
            "adj_ev": 0.19,
            "side": "under",
            "k_line": 5.5,
            "applied_lambda": 4.8,
            "quality_gate_level": "clean",
        }
    ]

    report = build_report(rows)

    assert "# Bet Conversion Shadow Audit" in report
    assert "`current_fire_flat`" in report
    assert "`edge_4_to_6`" in report
    assert "`adj_ev_17_plus`" in report
    assert "`current_fire_under`" in report
