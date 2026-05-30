from analytics.diagnostics import gate_ef_candidate_shadow_lab as lab


def test_under_skeptic_reasons_use_runtime_safe_fields_only():
    row = {
        "side": "under",
        "line_bucket": "5.5",
        "price_sign": "minus",
        "model_market_relationship": "model_agrees_with_favorite",
        "bet_timing_window": "pre_15",
        "quality_gate_level": "capped",
        "pitcher_archetype_bucket": "high_k_standard",
        "opportunity_bucket": "deep_starter",
        "result": "loss",
        "actual_ks": 8,
        "pick_history_pnl": -1,
    }

    reasons = lab.under_skeptic_reasons(row)

    assert reasons == [
        "under_high_line",
        "under_minus_price",
        "under_market_favorite_agreement",
        "under_late_or_unknown_timing",
        "under_capped_or_unknown_quality",
        "under_high_k_archetype",
        "under_deep_starter_opportunity",
    ]
    assert "result" not in lab.RUNTIME_SAFE_FIELDS
    assert "actual_ks" not in lab.RUNTIME_SAFE_FIELDS
    assert "pick_history_pnl" not in lab.RUNTIME_SAFE_FIELDS


def test_candidate_flags_mark_multi_reason_under_skeptic_rows():
    row = {
        "side": "under",
        "line_bucket": "6.5",
        "price_sign": "minus",
        "model_market_relationship": "model_fades_favorite",
        "bet_timing_window": "pre_30",
        "quality_gate_level": "clean",
        "pitcher_archetype_bucket": "standard_starter",
        "opportunity_bucket": "normal",
        "verdict": "FIRE 1u",
        "edge": 0.055,
        "adj_ev": 0.12,
        "projected_ks": 5.9,
        "k_line": 6.5,
    }

    flags = lab.candidate_flags(row)

    assert flags["current_fire_flat"] is True
    assert flags["current_fire_under"] is True
    assert flags["under_skeptic_2plus"] is True
    assert flags["under_skeptic_3plus"] is False
    assert flags["fire_without_under_skeptic_2plus"] is False
    assert flags["fire_mid_edge"] is True
    assert flags["fire_not_high_adj_ev"] is True
    assert flags["fire_model_margin_under_1_5"] is True


def test_under_skeptic_high_line_handles_plus_bucket():
    row = {
        "side": "under",
        "line_bucket": "7.5+",
    }

    assert lab.under_skeptic_reasons(row) == [
        "under_high_line",
        "under_late_or_unknown_timing",
        "under_capped_or_unknown_quality",
    ]


def test_candidate_flags_include_documented_labels_and_mid_edge_floor():
    row = {
        "side": "over",
        "line_bucket": "4.5",
        "price_sign": "plus",
        "model_market_relationship": "model_fades_favorite",
        "bet_timing_window": "pre_30",
        "quality_gate_level": "clean",
        "pitcher_archetype_bucket": "standard_starter",
        "opportunity_bucket": "normal",
        "verdict": "FIRE 2u",
        "edge": 0.03,
        "adj_ev": 0.16,
        "projected_ks": 5.2,
        "k_line": 4.5,
    }

    flags = lab.candidate_flags(row)

    assert set(flags) == {
        "current_fire_flat",
        "current_fire_over",
        "current_fire_under",
        "under_skeptic_2plus",
        "under_skeptic_3plus",
        "fire_without_under_skeptic_2plus",
        "fire_without_under_skeptic_3plus",
        "fire_mid_edge",
        "fire_not_high_adj_ev",
        "fire_model_margin_under_1_5",
        "fire_clean_quality",
        "fire_combined_skeptic",
    }
    assert flags["current_fire_over"] is True
    assert flags["current_fire_under"] is False
    assert flags["fire_without_under_skeptic_2plus"] is True
    assert flags["fire_without_under_skeptic_3plus"] is True
    assert flags["fire_mid_edge"] is True
    assert flags["fire_clean_quality"] is True


def test_fire_combined_skeptic_excludes_high_adj_ev_and_high_edge():
    base_row = {
        "side": "over",
        "line_bucket": "4.5",
        "price_sign": "plus",
        "model_market_relationship": "model_fades_favorite",
        "bet_timing_window": "pre_30",
        "quality_gate_level": "clean",
        "pitcher_archetype_bucket": "standard_starter",
        "opportunity_bucket": "normal",
        "verdict": "FIRE 1u",
        "edge": 0.055,
        "adj_ev": 0.12,
        "projected_ks": 5.2,
        "k_line": 4.5,
    }

    assert lab.candidate_flags(base_row)["fire_combined_skeptic"] is True

    high_adj_ev = {**base_row, "adj_ev": 0.20}
    assert lab.candidate_flags(high_adj_ev)["fire_combined_skeptic"] is False

    high_edge = {**base_row, "edge": 0.08}
    assert lab.candidate_flags(high_edge)["fire_combined_skeptic"] is False


def test_candidate_flags_fail_closed_for_missing_edge_and_adj_ev():
    row = {
        "side": "over",
        "line_bucket": "4.5",
        "price_sign": "plus",
        "model_market_relationship": "model_fades_favorite",
        "bet_timing_window": "pre_30",
        "quality_gate_level": "clean",
        "pitcher_archetype_bucket": "standard_starter",
        "opportunity_bucket": "normal",
        "verdict": "FIRE 1u",
        "projected_ks": 5.2,
        "k_line": 4.5,
    }

    flags = lab.candidate_flags(row)

    assert flags["fire_mid_edge"] is False
    assert flags["fire_not_high_adj_ev"] is False
    assert flags["fire_combined_skeptic"] is False


def test_under_skeptic_reasons_treat_unexpected_timing_bucket_as_unknown():
    row = {
        "side": "under",
        "line_bucket": "4.5",
        "bet_timing_window": "pre_45",
        "quality_gate_level": "clean",
    }

    assert lab.under_skeptic_reasons(row) == ["under_late_or_unknown_timing"]


def test_summarize_candidate_reports_retention_and_avoided_losses():
    rows = [
        {
            "side": "under",
            "line_bucket": "6.5",
            "price_sign": "minus",
            "model_market_relationship": "model_agrees_with_favorite",
            "bet_timing_window": "pre_15",
            "quality_gate_level": "capped",
            "pitcher_archetype_bucket": "high_k_standard",
            "opportunity_bucket": "normal",
            "verdict": "FIRE 1u",
            "edge": 0.08,
            "adj_ev": 0.2,
            "projected_ks": 5.7,
            "k_line": 6.5,
            "result": "loss",
            "pick_history_pnl": -1.0,
            "is_tracked_pick": True,
            "slate_date": "2026-05-01",
            "dataset_key": "row-a",
        },
        {
            "side": "over",
            "line_bucket": "4.5",
            "price_sign": "minus",
            "model_market_relationship": "model_agrees_with_favorite",
            "bet_timing_window": "pre_30",
            "quality_gate_level": "clean",
            "pitcher_archetype_bucket": "standard_starter",
            "opportunity_bucket": "normal",
            "verdict": "FIRE 2u",
            "edge": 0.05,
            "adj_ev": 0.11,
            "projected_ks": 5.2,
            "k_line": 4.5,
            "result": "win",
            "pick_history_pnl": 1.8,
            "is_tracked_pick": True,
            "slate_date": "2026-05-01",
            "dataset_key": "row-b",
        },
    ]

    summary = lab.summarize_candidate("fire_without_under_skeptic_2plus", rows)

    assert summary["selected"] == 1
    assert summary["wins"] == 1
    assert summary["losses"] == 0
    assert summary["flat_pnl"] == 1.8
    assert summary["current_fire_rows"] == 2
    assert summary["current_fire_1u_losses_avoided"] == 1
    assert summary["current_fire_2u_wins_retained"] == 1


def test_summarize_candidate_does_not_collapse_rows_missing_dataset_key():
    rows = [
        {
            "side": "under",
            "line_bucket": "6.5",
            "price_sign": "minus",
            "model_market_relationship": "model_agrees_with_favorite",
            "bet_timing_window": "pre_15",
            "quality_gate_level": "capped",
            "pitcher_archetype_bucket": "high_k_standard",
            "opportunity_bucket": "normal",
            "verdict": "FIRE 1u",
            "edge": 0.08,
            "adj_ev": 0.2,
            "projected_ks": 5.7,
            "k_line": 6.5,
            "result": "loss",
            "pick_history_pnl": -1.0,
            "is_tracked_pick": True,
            "slate_date": "2026-05-01",
        },
        {
            "side": "over",
            "line_bucket": "4.5",
            "price_sign": "minus",
            "model_market_relationship": "model_agrees_with_favorite",
            "bet_timing_window": "pre_30",
            "quality_gate_level": "clean",
            "pitcher_archetype_bucket": "standard_starter",
            "opportunity_bucket": "normal",
            "verdict": "FIRE 2u",
            "edge": 0.05,
            "adj_ev": 0.11,
            "projected_ks": 5.2,
            "k_line": 4.5,
            "result": "win",
            "pick_history_pnl": 1.8,
            "is_tracked_pick": True,
            "slate_date": "2026-05-01",
        },
    ]

    summary = lab.summarize_candidate("fire_without_under_skeptic_2plus", rows)

    assert summary["selected"] == 1
    assert summary["current_fire_1u_losses_avoided"] == 1
    assert summary["current_fire_2u_wins_retained"] == 1


def test_build_report_includes_shadow_warning_and_candidate_rows():
    rows = [
        {
            "side": "over",
            "line_bucket": "4.5",
            "price_sign": "plus",
            "model_market_relationship": "model_fades_favorite",
            "bet_timing_window": "pre_30",
            "quality_gate_level": "clean",
            "pitcher_archetype_bucket": "standard_starter",
            "opportunity_bucket": "normal",
            "verdict": "FIRE 1u",
            "edge": 0.05,
            "adj_ev": 0.11,
            "projected_ks": 5.2,
            "k_line": 4.5,
            "result": "win",
            "pick_history_pnl": 0.9,
            "is_tracked_pick": True,
            "slate_date": "2026-05-01",
        },
    ]

    report = lab.build_report(rows)

    assert "Shadow-only" in report
    assert "current_fire_flat" in report
    assert "fire_without_under_skeptic_2plus" in report
    assert "Promotion Discussion Check" in report


def test_build_report_includes_input_warning_for_missing_dataset():
    warning = (
        "Input dataset is missing. zero-row output is not decision evidence."
    )

    report = lab.build_report([], input_warning=warning)

    assert warning in report
    assert "Input Warning" in report
    assert "zero-row output is not decision evidence" in report
