from analytics.diagnostics.pitcher_k_outcome_dataset import (
    APPROVED_CONTEXT_SNAPSHOTS,
    REQUIRED_DATASET_FIELDS,
    build_dataset_key,
    validate_dataset_row,
)


def _complete_row(**overrides):
    row = {
        "dataset_key": "2026-05-12:official_close:bryan woo:under:5.5",
        "slate_date": "2026-05-12",
        "context_snapshot": "official_close",
        "pitcher": "Bryan Woo",
        "normalized_pitcher": "bryan woo",
        "side": "under",
        "k_line": 5.5,
        "bookmaker_key": "fanduel",
        "american_odds": 104,
        "price_sign": "plus",
        "price_bucket": "+100 to +119",
        "market_favorite_side": "over",
        "model_side": "under",
        "model_win_prob": 0.57,
        "model_no_vig_gap": 0.04,
        "projected_ks": 4.9,
        "k_margin_to_line": 0.6,
        "verdict": "FIRE 2u",
        "quality_gate_level": "clean",
        "actual_ks": 4,
        "result": "win",
        "theoretical_pnl": 1.04,
        "home_away": "home",
        "opp_team": "NYY",
        "lineup_used": "confirmed",
        "provider": None,
        "market_consensus": None,
        "bet_value_consensus": None,
        "broad_confirmation": False,
        "source_artifact_path": "dashboard/data/processed/2026-05-12.json",
        "is_tracked_pick": True,
        "bet_time_line": 5.5,
        "bet_time_odds": 110,
        "bet_time_book": "FanDuel",
        "closing_line": 5.5,
        "price_clv_cents": 6,
        "line_clv_delta": 0.0,
        "beat_close_price": True,
        "beat_close_line": False,
        "clv_type": "price_only",
        "process_outcome_bucket": "good_process_win",
        "bet_timing_window": "pre_30",
        "model_market_relationship": "model_fades_favorite",
        "model_edge_bucket": "5%+",
        "projection_margin_bucket": "0.5-1.0",
        "large_edge_skepticism_flag": False,
        "large_edge_skepticism_reasons": [],
        "pitcher_archetype_bucket": "standard_starter",
        "pitcher_throws": "R",
        "lineup_count": 9,
        "lineup_right_batters": None,
        "lineup_left_batters": None,
        "lineup_switch_batters": None,
        "handedness_matchup_bucket": None,
        "lineup_handedness_source": None,
        "lineup_handedness_runtime_safe": None,
        "lineup_handedness_game_pk": None,
        "lineup_handedness_count_matches_existing": None,
        "batter_handedness_mode": None,
        "lineup_split_source": None,
        "lineup_real_split_count": None,
        "lineup_path_a_fallback_count": None,
        "confidence_referee": None,
        "locked_verdict": None,
        "display_verdict": None,
        "actionable_verdict": None,
        "locked_adj_ev": None,
        "verdict_cap_reason": None,
        "avg_ip": 5.8,
        "recent_start_count": 5,
        "opportunity_bucket": "normal",
        "leash_risk_bucket": "normal",
        "actual_ip": None,
        "actual_pitch_count": None,
        "batters_faced": None,
    }
    row.update(overrides)
    return row


def test_required_dataset_fields_cover_identity_market_model_result_and_context():
    assert {"dataset_key", "slate_date", "context_snapshot", "pitcher"} <= REQUIRED_DATASET_FIELDS
    assert {"side", "k_line", "american_odds", "market_favorite_side"} <= REQUIRED_DATASET_FIELDS
    assert {"model_side", "model_win_prob", "projected_ks", "verdict"} <= REQUIRED_DATASET_FIELDS
    assert {"actual_ks", "result", "theoretical_pnl"} <= REQUIRED_DATASET_FIELDS
    assert {"bet_time_odds", "price_clv_cents", "beat_close_price"} <= REQUIRED_DATASET_FIELDS
    assert {"model_market_relationship", "model_edge_bucket"} <= REQUIRED_DATASET_FIELDS
    assert {"clv_type", "process_outcome_bucket", "bet_timing_window"} <= REQUIRED_DATASET_FIELDS
    assert {"large_edge_skepticism_flag", "large_edge_skepticism_reasons"} <= REQUIRED_DATASET_FIELDS
    assert {"pitcher_archetype_bucket"} <= REQUIRED_DATASET_FIELDS
    assert {"pitcher_throws", "opportunity_bucket", "handedness_matchup_bucket"} <= REQUIRED_DATASET_FIELDS
    assert {"lineup_handedness_source", "lineup_handedness_runtime_safe"} <= REQUIRED_DATASET_FIELDS
    assert {"batter_handedness_mode", "lineup_split_source"} <= REQUIRED_DATASET_FIELDS
    assert {"lineup_real_split_count", "lineup_path_a_fallback_count"} <= REQUIRED_DATASET_FIELDS
    assert {"confidence_referee", "locked_verdict", "display_verdict"} <= REQUIRED_DATASET_FIELDS
    assert {"actionable_verdict", "locked_adj_ev", "verdict_cap_reason"} <= REQUIRED_DATASET_FIELDS


def test_build_dataset_key_is_stable_for_pitcher_side_line_and_snapshot():
    key = build_dataset_key(
        slate_date="2026-05-12",
        context_snapshot="official_close",
        normalized_pitcher="Bryan Woo",
        side="Under",
        k_line=5.5,
    )

    assert key == "2026-05-12:official_close:bryan woo:under:5.5"


def test_validate_dataset_row_accepts_complete_shadow_row():
    errors = validate_dataset_row(_complete_row())

    assert errors == []


def test_validate_dataset_row_rejects_unknown_context_snapshot():
    errors = validate_dataset_row(_complete_row(context_snapshot="post_start"))

    assert "context_snapshot must be one of approved pregame/official values" in errors
    assert "post_start" not in APPROVED_CONTEXT_SNAPSHOTS


def test_validate_dataset_row_requires_missing_values_to_be_explicit_none():
    row = _complete_row()
    del row["provider"]

    errors = validate_dataset_row(row)

    assert "missing required field: provider" in errors
