from analytics.diagnostics import gate_f_projection_challenger_shadow_report as report


def test_gate_f_decision_requires_mae_and_slice_survival():
    candidate = {
        "name": "market_shrink_25",
        "holdout_mae_delta": -0.03,
        "holdout_rmse_delta": -0.02,
        "side_accuracy_delta": 0.0,
        "bad_slice_count": 0,
        "fire_2u_degradation": False,
        "positive_rolling_windows": 2,
        "runtime_safe": True,
    }

    decision = report.gate_f_decision(candidate)

    assert decision["status"] == "promotion_plan_candidate"


def test_gate_f_decision_blocks_hindsight_only_candidate():
    candidate = {
        "name": "handedness_bucket_adjust",
        "holdout_mae_delta": -0.04,
        "holdout_rmse_delta": -0.02,
        "side_accuracy_delta": 0.01,
        "bad_slice_count": 0,
        "fire_2u_degradation": False,
        "positive_rolling_windows": 2,
        "runtime_safe": False,
    }

    decision = report.gate_f_decision(candidate)

    assert decision["status"] == "blocked_hindsight_only"


def test_build_report_includes_shadow_scope_and_decisions():
    rows = [
        {
            "slate_date": f"2026-05-{day:02d}",
            "context_snapshot": "official_close",
            "pitcher": f"Pitcher {day}",
            "normalized_pitcher": f"pitcher-{day}",
            "side": "over",
            "result": "win" if day % 2 else "loss",
            "actual_ks": 6 if day % 2 else 4,
            "projected_ks": 5.8,
            "k_line": 5.5,
            "line_bucket": "5.5",
            "price_sign": "minus",
            "quality_gate_level": "clean",
            "model_market_relationship": "model_agrees_with_favorite",
            "bet_timing_window": "pre_30",
            "opportunity_bucket": "normal",
            "leash_risk_bucket": "normal",
            "pitcher_archetype_bucket": "standard_starter",
            "is_tracked_pick": True,
            "verdict": "FIRE 1u",
            "pick_history_pnl": 0.91 if day % 2 else -1.0,
        }
        for day in range(1, 31)
    ]

    output = report.build_report(rows)

    assert "# Gate F Projection Challenger Shadow Report" in output
    assert "Shadow-only" in output
    assert "Decision Summary" in output
    assert "`market_shrink_25`" in output
