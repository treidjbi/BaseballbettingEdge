from analytics.diagnostics.gate_c_holdout_shadow_lab import (
    build_report,
    candidate_side,
    fit_handedness_adjustments,
    rolling_validation_windows,
    split_holdout_rows,
    summarize_candidate,
)


def _market_row(
    *,
    slate_date="2026-05-01",
    pitcher="Test Pitcher",
    k_line=5.5,
    projected_ks=5.8,
    actual_ks=6,
    market_favorite_side="over",
    handedness_matchup_bucket="same_hand_heavy",
    is_tracked_pick=False,
    side="over",
    result="win",
    pnl=0.91,
):
    return {
        "slate_date": slate_date,
        "context_snapshot": "official_close",
        "pitcher": pitcher,
        "normalized_pitcher": pitcher.lower(),
        "k_line": k_line,
        "projected_ks": projected_ks,
        "actual_ks": actual_ks,
        "market_favorite_side": market_favorite_side,
        "handedness_matchup_bucket": handedness_matchup_bucket,
        "lineup_handedness_runtime_safe": False,
        "is_tracked_pick": is_tracked_pick,
        "side": side,
        "result": result,
        "theoretical_pnl": pnl,
        "pick_history_pnl": pnl,
    }


def test_split_holdout_rows_uses_ordered_slates_without_leakage():
    rows = [
        _market_row(slate_date="2026-05-04", pitcher="D"),
        _market_row(slate_date="2026-05-01", pitcher="A"),
        _market_row(slate_date="2026-05-03", pitcher="C"),
        _market_row(slate_date="2026-05-02", pitcher="B"),
    ]

    split = split_holdout_rows(rows, train_fraction=0.5)

    assert split["train_dates"] == ["2026-05-01", "2026-05-02"]
    assert split["validate_dates"] == ["2026-05-03", "2026-05-04"]
    assert {row["slate_date"] for row in split["train_rows"]}.isdisjoint(
        {row["slate_date"] for row in split["validate_rows"]}
    )


def test_fit_handedness_adjustments_learns_from_training_residuals_only():
    training_rows = [
        _market_row(projected_ks=5.0, actual_ks=6.0, pitcher="A"),
        _market_row(projected_ks=6.0, actual_ks=7.0, pitcher="B"),
        _market_row(projected_ks=7.0, actual_ks=6.0, pitcher="C", handedness_matchup_bucket="opposite_hand_heavy"),
    ]

    adjustments = fit_handedness_adjustments(training_rows, min_rows=2, shrink_base=0, max_abs_delta=2)

    assert adjustments["same_hand_heavy"]["delta"] == 1.0
    assert "opposite_hand_heavy" not in adjustments

    validation_row = _market_row(projected_ks=5.2, actual_ks=6.0)
    assert candidate_side(validation_row, "handedness_bucket_adjust", adjustments=adjustments) == "over"


def test_summarize_candidate_scores_projection_and_side_baselines():
    rows = [
        _market_row(pitcher="Win", projected_ks=5.8, actual_ks=6.0, k_line=5.5),
        _market_row(pitcher="Loss", projected_ks=6.2, actual_ks=4.0, k_line=5.5, result="loss", pnl=-1.0),
    ]

    current = summarize_candidate("current_model", rows)
    over_only = summarize_candidate("over_only", rows)

    assert current["rows"] == 2
    assert current["mae"] == 1.2
    assert current["side_wins"] == 1
    assert current["side_losses"] == 1
    assert over_only["mae"] is None
    assert over_only["side_wins"] == 1
    assert over_only["side_losses"] == 1


def test_build_report_includes_holdout_and_lambda_guardrails():
    rows = [
        _market_row(slate_date="2026-05-01", pitcher="A", projected_ks=5.2, actual_ks=6.0),
        _market_row(slate_date="2026-05-02", pitcher="B", projected_ks=5.1, actual_ks=6.0),
        _market_row(slate_date="2026-05-03", pitcher="C", projected_ks=6.2, actual_ks=4.0, result="loss", pnl=-1.0),
        _market_row(slate_date="2026-05-04", pitcher="D", projected_ks=4.9, actual_ks=6.0),
    ]

    report = build_report(rows)

    assert "# Gate C Holdout Shadow Lab" in report
    assert "shadow-only" in report
    assert "Do not discard lambda from this report alone" in report
    assert "`over_only`" in report
    assert "`market_favorite_only`" in report
    assert "`handedness_bucket_adjust`" in report
    assert "## Validation Holdout" in report


def test_rolling_validation_windows_keep_chronological_train_then_validate():
    rows = [
        {"slate_date": f"2026-05-{day:02d}", "context_snapshot": "official_close"}
        for day in range(1, 13)
    ]

    windows = rolling_validation_windows(rows, train_dates=6, validate_dates=3, step_dates=3)

    assert windows[0]["train_dates"] == [
        "2026-05-01",
        "2026-05-02",
        "2026-05-03",
        "2026-05-04",
        "2026-05-05",
        "2026-05-06",
    ]
    assert windows[0]["validate_dates"] == ["2026-05-07", "2026-05-08", "2026-05-09"]
    assert windows[1]["validate_dates"] == ["2026-05-10", "2026-05-11", "2026-05-12"]
