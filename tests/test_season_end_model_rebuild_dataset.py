from analytics.diagnostics import season_end_model_rebuild_dataset as rebuild


def test_build_row_marks_hindsight_fields_as_not_runtime_safe():
    source = {
        "slate_date": "2026-06-23",
        "pitcher": "Example Starter",
        "side": "over",
        "k_line": 5.5,
        "actual_ks": 7,
        "pnl": 0.91,
        "beat_close_price": True,
        "model_market_relationship": "model_agrees_with_favorite",
        "quality_gate_level": "clean",
    }

    row = rebuild.build_row(source)

    assert row["available_pre_lock"] is True
    assert row["hindsight_labels"]["actual_ks"] == 7
    assert row["hindsight_labels"]["beat_close_price"] is True
    assert "actual_ks" not in row["runtime_features"]
    assert "beat_close_price" not in row["runtime_features"]


def test_build_row_moves_unsafe_gate_c_reconstructions_to_hindsight_labels():
    source = {
        "slate_date": "2026-04-28",
        "pitcher": "Clay Holmes",
        "normalized_pitcher": "clay holmes",
        "side": "over",
        "k_line": 3.5,
        "lineup_handedness_runtime_safe": False,
        "lineup_handedness_source": "mlb_boxscore_reconstructed",
        "lineup_handedness_game_pk": 823636,
        "lineup_right_batters": 9,
        "lineup_left_batters": 0,
        "lineup_switch_batters": 0,
        "lineup_used": True,
        "handedness_matchup_bucket": "same_hand_heavy",
        "actual_opportunity_runtime_safe": False,
        "actual_opportunity_source": "mlb_boxscore_reconstructed",
        "actual_ip": 6.0,
        "actual_pitch_count": 94,
        "batters_faced": 22,
        "opportunity_bucket": "normal",
        "model_win_prob": 0.683,
        "theoretical_pnl": 0.65,
        "pick_history_pnl": 0.6493506493506493,
        "result": "win",
    }

    row = rebuild.build_row(source)

    assert row["available_pre_lock"] is False
    for key in (
        "lineup_right_batters",
        "lineup_left_batters",
        "lineup_switch_batters",
        "lineup_used",
        "handedness_matchup_bucket",
        "opportunity_bucket",
    ):
        assert key not in row["runtime_features"]
        assert row["hindsight_labels"][key] == source[key]
    assert row["hindsight_labels"]["theoretical_pnl"] == 0.65
    assert row["hindsight_labels"]["pick_history_pnl"] == 0.6493506493506493
    assert row["hindsight_explanation_only"]["lineup_right_batters"] is True
    assert row["runtime_feature_group"]["model_win_prob"] == "model"


def test_season_bucket_preserves_early_mid_late_context():
    assert rebuild.season_bucket("2026-03-28") == "early_season"
    assert rebuild.season_bucket("2026-05-15") == "spring_midseason"
    assert rebuild.season_bucket("2026-07-15") == "summer_midseason"
    assert rebuild.season_bucket("2026-09-10") == "late_season"


def test_summarize_reports_runtime_and_hindsight_coverage():
    rows = [
        {
            "available_pre_lock": True,
            "runtime_features": {"quality_gate_level": "clean"},
            "hindsight_labels": {"beat_close_price": True},
            "season_bucket": "early_season",
        }
    ]

    summary = rebuild.summarize(rows)

    assert summary["rows"] == 1
    assert summary["available_pre_lock_rows"] == 1
    assert summary["season_buckets"] == {"early_season": 1}
    assert summary["hindsight_label_counts"]["beat_close_price"] == 1
