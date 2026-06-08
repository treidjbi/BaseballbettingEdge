from analytics.diagnostics import workload_no_vig_ev_audit as audit


def test_no_vig_labels_confirmed_thin_and_price_only_edges():
    assert (
        audit.no_vig_edge_label({"model_no_vig_gap": 0.05, "ev": 0.08})
        == "no_vig_confirmed_edge"
    )
    assert (
        audit.no_vig_edge_label({"model_no_vig_gap": 0.025, "ev": 0.08})
        == "no_vig_thin_edge"
    )
    assert (
        audit.no_vig_edge_label({"model_no_vig_gap": 0.005, "ev": 0.08})
        == "no_vig_price_only_edge"
    )
    assert (
        audit.no_vig_edge_label({"model_no_vig_gap": -0.01, "ev": -0.02})
        == "no_vig_no_edge"
    )


def test_no_vig_missing_values_stay_unknown():
    assert audit.no_vig_edge_label({"model_no_vig_gap": None, "ev": 0.08}) == "unknown"


def test_no_vig_labels_include_market_and_referee_interactions():
    market_disagrees = {
        "model_no_vig_gap": 0.01,
        "ev": 0.04,
        "model_market_relationship": "model_fades_favorite",
    }
    assert audit.no_vig_edge_label(market_disagrees) == "no_vig_market_disagrees"

    referee_agrees = {
        "confidence_referee": {"applied": True},
        "model_no_vig_gap": 0.01,
        "model_market_relationship": "model_fades_favorite",
    }
    assert audit.no_vig_edge_label(referee_agrees) == "no_vig_referee_agrees"

    referee_disagrees = {
        "confidence_referee": {"applied": True},
        "model_no_vig_gap": 0.05,
        "beat_close_price": True,
    }
    assert audit.no_vig_edge_label(referee_disagrees) == "no_vig_referee_disagrees"


def test_workload_sensitivity_labels_use_projection_margin():
    assert (
        audit.workload_sensitivity_label({"k_margin_to_line": 0.25})
        == "workload_sensitivity_half_k"
    )
    assert (
        audit.workload_sensitivity_label({"k_margin_to_line": 0.75})
        == "workload_sensitivity_one_k"
    )
    assert (
        audit.workload_sensitivity_label({"k_margin_to_line": 1.25})
        == "workload_stable_margin"
    )


def test_workload_risk_label_uses_existing_opportunity_fields():
    row = {
        "leash_risk_bucket": "high",
        "opportunity_bucket": "short_leash",
        "quality_gate_level": "capped",
    }
    assert audit.workload_risk_label(row) == "workload_fragile"

    row = {
        "leash_risk_bucket": "normal",
        "opportunity_bucket": "normal",
        "quality_gate_level": "clean",
    }
    assert audit.workload_risk_label(row) == "workload_stable"


def test_path_b_coverage_bucket_uses_real_split_count():
    assert (
        audit.path_b_coverage_bucket(
            {"batter_handedness_mode": "path_b", "lineup_real_split_count": 0}
        )
        == "path_b_zero_real_splits"
    )
    assert (
        audit.path_b_coverage_bucket(
            {"batter_handedness_mode": "path_b", "lineup_real_split_count": 4}
        )
        == "path_b_1_4_real_splits"
    )
    assert (
        audit.path_b_coverage_bucket(
            {"batter_handedness_mode": "path_b", "lineup_real_split_count": 8}
        )
        == "path_b_5_8_real_splits"
    )
    assert (
        audit.path_b_coverage_bucket(
            {"batter_handedness_mode": "path_b", "lineup_real_split_count": 9}
        )
        == "path_b_9_real_splits"
    )
    assert (
        audit.path_b_coverage_bucket(
            {"batter_handedness_mode": "path_a", "lineup_real_split_count": 9}
        )
        == "path_a_or_unknown"
    )


def test_path_b_coverage_bucket_accepts_current_lineup_handedness_fields():
    row = {
        "lineup_handedness_runtime_safe": True,
        "lineup_right_batters": 4,
        "lineup_left_batters": 4,
        "lineup_switch_batters": 1,
    }

    assert audit.path_b_coverage_bucket(row) == "path_b_9_real_splits"


def test_referee_interaction_label_compares_cap_to_no_vig_and_workload():
    capped = {
        "confidence_referee": {"applied": True},
        "model_no_vig_gap": 0.01,
        "leash_risk_bucket": "high",
    }
    assert (
        audit.referee_interaction_label(capped)
        == "referee_cap_supported_by_no_vig_or_workload"
    )

    contradicted = {
        "confidence_referee": {"applied": True},
        "model_no_vig_gap": 0.05,
        "leash_risk_bucket": "normal",
    }
    assert (
        audit.referee_interaction_label(contradicted)
        == "referee_cap_contradicted_by_no_vig"
    )

    uncapped = {
        "confidence_referee": {"applied": False},
        "model_no_vig_gap": 0.01,
        "leash_risk_bucket": "high",
    }
    assert audit.referee_interaction_label(uncapped) == "uncapped_row_with_shadow_warning"


def test_build_summary_counts_candidate_labels():
    rows = [
        {
            "model_no_vig_gap": 0.05,
            "ev": 0.08,
            "k_margin_to_line": 0.4,
            "leash_risk_bucket": "normal",
            "opportunity_bucket": "normal",
            "quality_gate_level": "clean",
            "result": "win",
            "pnl": 1.0,
        },
        {
            "model_no_vig_gap": 0.005,
            "ev": 0.08,
            "k_margin_to_line": 0.3,
            "leash_risk_bucket": "high",
            "opportunity_bucket": "short_leash",
            "quality_gate_level": "capped",
            "result": "loss",
            "pnl": -1.0,
        },
    ]

    summary = audit.build_summary(rows)

    assert summary["total_rows"] == 2
    assert summary["analysis_rows"] == 2
    assert summary["no_vig_labels"]["no_vig_confirmed_edge"]["rows"] == 1
    assert summary["workload_risk_labels"]["workload_fragile"]["rows"] == 1


def test_build_summary_counts_path_b_cross_slices():
    rows = [
        {
            "model_no_vig_gap": 0.05,
            "ev": 0.08,
            "batter_handedness_mode": "path_b",
            "lineup_real_split_count": 9,
            "confidence_referee": {"applied": True},
            "leash_risk_bucket": "normal",
            "result": "win",
            "pnl": 1.0,
        },
        {
            "model_no_vig_gap": 0.005,
            "ev": 0.08,
            "batter_handedness_mode": "path_b",
            "lineup_real_split_count": 3,
            "leash_risk_bucket": "high",
            "result": "loss",
            "pnl": -1.0,
        },
    ]

    summary = audit.build_summary(rows)

    assert (
        summary["path_b_no_vig_labels"]["path_b_9_real_splits | no_vig_referee_disagrees"][
            "rows"
        ]
        == 1
    )
    assert (
        summary["path_b_referee_interaction_labels"][
            "path_b_1_4_real_splits | uncapped_row_with_shadow_warning"
        ]["rows"]
        == 1
    )


def test_render_report_keeps_shadow_warning_and_gate_e_f_language():
    summary = {
        "total_rows": 0,
        "analysis_rows": 0,
        "no_vig_labels": {},
        "workload_risk_labels": {},
        "workload_sensitivity_labels": {},
        "path_b_coverage_buckets": {},
        "referee_interaction_labels": {},
        "path_b_no_vig_labels": {},
        "path_b_referee_interaction_labels": {},
    }

    report = audit.render_report(summary)

    assert "Shadow-only" in report
    assert "Gate E" in report
    assert "Gate F" in report
    assert "Path B By No-Vig Label" in report
    assert "Path B By Referee Interaction" in report
