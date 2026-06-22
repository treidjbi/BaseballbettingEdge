from analytics.diagnostics import market_shrink_projection_canary_audit as audit


def test_summarize_counts_shadow_and_enforce_rows():
    rows = [
        {
            "slate_date": "2026-06-22",
            "result": "win",
            "is_tracked_pick": True,
            "projection_challenger": {
                "mode": "shadow",
                "candidate": "market_shrink_25",
                "applied": False,
                "current_lambda": 6.0,
                "would_lambda": 5.875,
            },
        },
        {
            "slate_date": "2026-06-22",
            "result": "loss",
            "is_tracked_pick": True,
            "projection_challenger": {
                "mode": "enforce",
                "candidate": "market_shrink_25",
                "applied": True,
                "current_lambda": 6.0,
                "would_lambda": 5.875,
            },
        },
    ]

    summary = audit.summarize(rows)

    assert summary["rows_with_metadata"] == 2
    assert summary["mode_counts"] == {"shadow": 1, "enforce": 1}
    assert summary["applied_rows"] == 1
    assert summary["changed_lambda_rows"] == 2


def test_summarize_scores_tracked_graded_rows_with_metadata():
    rows = [
        {
            "slate_date": "2026-06-22",
            "result": "win",
            "is_tracked_pick": True,
            "display_verdict": "FIRE 1u",
            "side": "over",
            "line_bucket": "5.5",
            "model_market_relationship": "model_agrees_with_favorite",
            "quality_gate_level": "clean",
            "opportunity_bucket": "normal",
            "model_no_vig_gap": 0.05,
            "leash_risk_bucket": "normal",
            "k_margin_to_line": 1.2,
            "pick_history_pnl": 0.91,
            "projection_challenger": {
                "mode": "shadow",
                "candidate": "market_shrink_25",
                "applied": False,
                "current_lambda": 6.0,
                "would_lambda": 5.875,
            },
        },
        {
            "slate_date": "2026-06-22",
            "result": "loss",
            "is_tracked_pick": True,
            "display_verdict": "LEAN",
            "side": "under",
            "line_bucket": "4.5",
            "model_market_relationship": "model_fades_favorite",
            "quality_gate_level": "capped",
            "opportunity_bucket": "short_leash",
            "model_no_vig_gap": 0.01,
            "leash_risk_bucket": "high",
            "k_margin_to_line": 0.4,
            "pick_history_pnl": -1.0,
            "projection_challenger": {
                "mode": "shadow",
                "candidate": "market_shrink_25",
                "applied": False,
                "current_lambda": 4.2,
                "would_lambda": 4.275,
            },
        },
    ]

    summary = audit.summarize(rows)

    assert summary["tracked_graded"]["rows"] == 2
    assert summary["tracked_graded"]["wins"] == 1
    assert summary["tracked_graded"]["losses"] == 1
    assert summary["tracked_graded"]["pnl"] == -0.09
    assert summary["by_verdict"]["FIRE 1u"]["rows"] == 1
    assert summary["by_side"]["under"]["losses"] == 1
    assert summary["by_model_market_relationship"]["model_fades_favorite"]["rows"] == 1
    assert summary["by_no_vig_label"]["no_vig_market_disagrees"]["pnl"] == -1.0
    assert summary["by_workload_risk_label"]["workload_fragile"]["losses"] == 1
    assert summary["by_workload_sensitivity_label"]["workload_sensitivity_half_k"]["rows"] == 1


def test_report_handles_pre_shadow_zero_metadata_state():
    report = audit.build_report([{"is_tracked_pick": True, "result": "win"}])

    assert "Rows with projection metadata: `0`" in report
    assert "No projection metadata found yet" in report
    assert "keep `MARKET_SHRINK_PROJECTION_MODE=off`" in report
