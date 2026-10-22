from analytics.diagnostics.confidence_referee_shadow_report import (
    build_report,
    referee_bucket,
    summarize_slice,
    summarize_buckets,
)


def _row(
    *,
    pitcher="Test Pitcher",
    side="over",
    result="win",
    pnl=0.91,
    verdict="FIRE 1u",
    timing="pre_15",
    fades_favorite=False,
    large_edge=False,
    leash="normal",
    opportunity="normal",
    beat_close_price=False,
    beat_close_line=False,
    price_sign="minus",
    line_bucket="5.5",
    quality_gate_level="clean",
):
    return {
        "slate_date": "2026-05-22",
        "context_snapshot": "official_close",
        "pitcher": pitcher,
        "side": side,
        "result": result,
        "is_tracked_pick": True,
        "verdict": verdict,
        "pick_history_pnl": pnl,
        "theoretical_pnl": pnl,
        "bet_timing_window": timing,
        "large_edge_skepticism_flag": large_edge,
        "model_market_relationship": (
            "model_fades_favorite" if fades_favorite else "model_agrees_with_favorite"
        ),
        "leash_risk_bucket": leash,
        "opportunity_bucket": opportunity,
        "beat_close_price": beat_close_price,
        "beat_close_line": beat_close_line,
        "process_outcome_bucket": "good_process_win"
        if beat_close_price or beat_close_line
        else "weak_process_win",
        "model_edge_bucket": "5%+",
        "projection_margin_bucket": "1.0-1.5",
        "price_sign": price_sign,
        "line_bucket": line_bucket,
        "quality_gate_level": quality_gate_level,
    }


def test_referee_bucket_uses_runtime_safe_caution_before_hindsight_clv():
    strong_late_clv_loss = _row(
        result="loss",
        pnl=-1.0,
        timing="pre_15",
        beat_close_price=True,
        fades_favorite=True,
        large_edge=True,
    )

    assert referee_bucket(strong_late_clv_loss) == "skip_or_demand_better_price"


def test_referee_bucket_identifies_late_clean_fire_candidate():
    row = _row(timing="pre_5", beat_close_price=True)

    assert referee_bucket(row) == "bet_late_if_still_available"


def test_summarize_buckets_scores_rows_without_changing_labels():
    rows = [
        _row(timing="pre_5", beat_close_price=True),
        _row(result="loss", pnl=-1.0, timing="pre_30"),
        _row(result="loss", pnl=-1.0, large_edge=True),
        _row(verdict="LEAN"),
    ]

    summary = summarize_buckets(rows)

    assert summary["bet_late_if_still_available"]["rows"] == 1
    assert summary["wait_for_late_data"]["rows"] == 1
    assert summary["skip_or_demand_better_price"]["rows"] == 1
    assert summary["monitor_only"]["rows"] == 1
    assert summary["bet_late_if_still_available"]["clv_edge_rows"] == 1


def test_build_report_names_runtime_and_hindsight_boundaries():
    report = build_report([_row(timing="pre_5", beat_close_price=True)])

    assert "# Confidence Referee Shadow Report" in report
    assert "Runtime-safe label inputs" in report
    assert "Hindsight validation fields" in report
    assert "`bet_late_if_still_available`" in report
    assert "shadow-only" in report


def test_summarize_slice_scores_runtime_safe_dimensions():
    rows = [
        _row(side="over", result="win", pnl=0.91, price_sign="minus"),
        _row(side="over", result="loss", pnl=-1.0, price_sign="plus"),
        _row(side="under", result="loss", pnl=-1.0, price_sign="plus"),
    ]

    summary = summarize_slice(rows, ["side", "price_sign"])

    assert summary[("over", "minus")]["rows"] == 1
    assert summary[("over", "minus")]["wins"] == 1
    assert summary[("over", "minus")]["roi"] == 0.91
    assert summary[("under", "plus")]["losses"] == 1


def test_build_report_includes_gate_c_cross_slice_scoreboards():
    report = build_report(
        [
            _row(side="over", result="win", pnl=0.91, timing="pre_5"),
            _row(
                side="under",
                result="loss",
                pnl=-1.0,
                timing="pre_30",
                price_sign="plus",
                line_bucket="4.5",
                quality_gate_level="capped",
            ),
        ]
    )

    assert "## Gate C Cross-Slice Scoreboards" in report
    assert "### Referee Bucket By Side" in report
    assert "### Side By Price Sign" in report
    assert "### Side By K-Line Bucket" in report
    assert "| `under` | `plus` |" in report
    assert "| `under` | `4.5` |" in report
