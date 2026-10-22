from analytics.diagnostics.k_projection_shadow_lab import (
    build_report,
    challenger_projection,
    market_projection_rows,
    summarize_challenger_slices,
    summarize_projection,
)


def _side_row(
    *,
    side,
    result,
    pitcher="Test Pitcher",
    projected_ks=5.8,
    actual_ks=6,
    k_line=5.5,
    slate_date="2026-05-12",
    opportunity_bucket="normal",
    leash_risk_bucket="normal",
    pitcher_archetype_bucket="standard_starter",
    avg_ip=6.0,
    recent_k9=9.0,
    season_k9=8.5,
    career_k9=8.0,
):
    return {
        "slate_date": slate_date,
        "context_snapshot": "official_close",
        "pitcher": pitcher,
        "normalized_pitcher": pitcher.lower(),
        "side": side,
        "result": result,
        "actual_ks": actual_ks,
        "projected_ks": projected_ks,
        "k_line": k_line,
        "line_bucket": "5.5" if k_line == 5.5 else "7.5+",
        "opportunity_bucket": opportunity_bucket,
        "leash_risk_bucket": leash_risk_bucket,
        "pitcher_archetype_bucket": pitcher_archetype_bucket,
        "avg_ip": avg_ip,
        "recent_k9": recent_k9,
        "season_k9": season_k9,
        "career_k9": career_k9,
        "rest_k9_delta": 0.0,
        "ump_k_adj": 0.0,
        "is_tracked_pick": side == "over",
        "verdict": "FIRE 1u" if side == "over" else "PASS",
        "theoretical_pnl": 0.91 if result == "win" else -1.0,
    }


def test_market_projection_rows_dedupes_side_rows_and_keeps_clean_graded_official_close():
    rows = [
        _side_row(side="over", result="win"),
        _side_row(side="under", result="loss"),
        _side_row(side="over", result="win", slate_date="2026-04-27"),
        {**_side_row(side="over", result="win"), "context_snapshot": "pre_5"},
        {**_side_row(side="over", result=None), "actual_ks": None},
    ]

    markets = market_projection_rows(rows)

    assert len(markets) == 1
    assert markets[0]["pitcher"] == "Test Pitcher"
    assert markets[0]["winning_side"] == "over"


def test_challenger_projection_applies_transparent_adjustments():
    high_line_short_leash = _side_row(
        side="over",
        result="loss",
        projected_ks=8.2,
        actual_ks=6,
        k_line=7.5,
        opportunity_bucket="short_leash",
        leash_risk_bucket="high",
        pitcher_archetype_bucket="short_leash",
    )

    assert challenger_projection(high_line_short_leash, "current_model") == 8.2
    assert challenger_projection(high_line_short_leash, "market_shrink_25") == 8.025
    assert challenger_projection(high_line_short_leash, "high_line_temper") == 7.65
    assert challenger_projection(high_line_short_leash, "leash_cap") == 7.65

    rate_blend = challenger_projection(high_line_short_leash, "recent_rate_blend")
    assert rate_blend is not None
    assert round(rate_blend, 3) == 7.592


def test_market_shrink_family_moves_projection_toward_line():
    row = {
        "projected_ks": 7.0,
        "k_line": 5.0,
    }

    assert challenger_projection(row, "market_shrink_15") == 6.7
    assert challenger_projection(row, "market_shrink_25") == 6.5
    assert challenger_projection(row, "market_shrink_35") == 6.3


def test_market_shrink_family_handles_missing_line_without_change():
    row = {
        "projected_ks": 7.0,
        "k_line": None,
    }

    assert challenger_projection(row, "market_shrink_15") == 7.0
    assert challenger_projection(row, "market_shrink_35") == 7.0


def test_summarize_projection_scores_accuracy_and_side_calls():
    rows = [
        _side_row(side="over", result="win", projected_ks=5.8, actual_ks=6, k_line=5.5),
        _side_row(side="over", result="loss", projected_ks=6.2, actual_ks=4, k_line=5.5, pitcher="Miss"),
    ]

    summary = summarize_projection("current_model", rows)

    assert summary["rows"] == 2
    assert summary["mean_error"] == -1.0
    assert summary["mae"] == 1.2
    assert summary["rmse"] == 1.562
    assert summary["side_wins"] == 1
    assert summary["side_losses"] == 1
    assert summary["side_accuracy"] == 0.5


def test_summarize_challenger_slices_marks_sample_status():
    rows = [
        {
            "slate_date": "2026-06-01",
            "context_snapshot": "official_close",
            "result": "win",
            "actual_ks": 6,
            "projected_ks": 5.8,
            "k_line": 5.5,
            "line_bucket": "5.5",
            "side": "over",
            "winning_side": "over",
            "price_sign": "minus",
        }
    ]

    slices = summarize_challenger_slices("current_model", rows, "line_bucket", min_rows=10)

    assert slices[0]["bucket"] == "5.5"
    assert slices[0]["rows"] == 1
    assert slices[0]["sample_status"] == "small_sample"


def test_build_report_includes_shadow_guardrail_and_challenger_table():
    rows = [
        _side_row(side="over", result="win"),
        _side_row(side="under", result="loss"),
    ]

    report = build_report(rows)

    assert "# K Projection Shadow Lab" in report
    assert "shadow-only" in report
    assert "`current_model`" in report
    assert "`market_shrink_25`" in report
    assert "`recent_rate_blend`" in report
    assert "Do not promote" in report
