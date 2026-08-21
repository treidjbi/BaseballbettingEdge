import json

from analytics.diagnostics.pitcher_k_outcome_dataset import (
    actual_opportunity_lookup_key,
    build_official_close_rows,
    build_summary,
    enrich_rows_with_actual_opportunity,
    enrich_rows_with_pick_history,
    enrich_rows_with_lineup_handedness,
    lineup_handedness_lookup_key,
    load_archived_markets_for_dataset,
    reconcile_picks_history,
    theoretical_pnl,
)
from analytics.diagnostics import pitcher_k_outcome_dataset as dataset


def test_theoretical_pnl_uses_one_unit_risk_for_american_odds():
    assert theoretical_pnl("win", -120) == 0.83
    assert theoretical_pnl("win", 130) == 1.3
    assert theoretical_pnl("loss", -120) == -1.0
    assert theoretical_pnl(None, -120) is None


def test_build_dataset_prefers_explicit_history_over_remote_artifact(tmp_path, monkeypatch):
    history_path = tmp_path / "picks_history.json"
    calls = []

    def fake_load_history(path, artifact_api_url, **kwargs):
        calls.append((path, artifact_api_url, kwargs))
        return []

    monkeypatch.setattr(dataset, "_load_picks_history", fake_load_history)
    monkeypatch.setattr(dataset, "load_archived_markets_for_dataset", lambda *args, **kwargs: [])
    monkeypatch.setattr(dataset, "build_official_close_rows", lambda rows: [])
    monkeypatch.setattr(dataset, "enrich_rows_with_lineup_handedness", lambda rows, **kwargs: rows)
    monkeypatch.setattr(dataset, "enrich_rows_with_actual_opportunity", lambda rows, **kwargs: rows)
    monkeypatch.setattr(dataset, "enrich_rows_with_pick_history", lambda rows, **kwargs: rows)
    monkeypatch.setattr(dataset, "enrich_rows_with_market_agreement", lambda rows, **kwargs: rows)
    monkeypatch.setattr(dataset, "enrich_rows_with_live_market_display", lambda rows, **kwargs: rows)

    assert dataset.build_dataset(
        start_date="2026-08-20",
        end_date="2026-08-20",
        artifact_api_url="https://example.test/.netlify/functions/get-artifact",
        picks_history_path=history_path,
    ) == []
    assert calls == [
        (
            history_path,
            None,
            {"start_date": "2026-08-20", "end_date": "2026-08-20"},
        )
    ]


def test_build_official_close_rows_creates_one_row_per_side():
    markets = [
        {
            "date": "2026-05-12",
            "pitcher": "Bryan Woo",
            "normalized_pitcher": "bryan woo",
            "k_line": 5.5,
            "actual_ks": 4,
            "winning_side": "under",
            "over_odds": -125,
            "under_odds": 104,
            "opening_over_odds": -110,
            "opening_under_odds": 104,
            "ref_book": "FanDuel",
            "model_side": "under",
            "model_win_prob": 0.57,
            "applied_lambda": 4.9,
            "ev_over": {"win_prob": 0.43, "edge": -0.02, "ev": -0.04, "adj_ev": -0.04, "verdict": "PASS"},
            "ev_under": {
                "win_prob": 0.57,
                "edge": 0.04,
                "ev": 0.09,
                "adj_ev": 0.09,
                "verdict": "FIRE 1u",
                "market_anchor_selector": {
                    "mode": "shadow",
                    "labels": ["market_anchor_strict"],
                    "applied": False,
                },
            },
            "team": "SEA",
            "opp_team": "NYY",
            "home_away": "home",
            "lineup_used": "confirmed",
            "lineup_count": 9,
            "batter_handedness_mode": "path_b",
            "lineup_split_source": "real_split_cache",
            "lineup_real_split_count": 7,
            "lineup_path_a_fallback_count": 2,
            "quality_gate_level": "clean",
            "quality_gate_reasons": [],
            "odds_source": "therundown+propline",
            "market_source_mode": "therundown_propline",
            "line_source_provider": "propline",
            "archive_outcome_reconciliation_source": "picks_history_exact",
            "source_artifact_path": "dashboard/data/processed/2026-05-12.json",
            "pitcher_throws": "R",
            "avg_ip": 5.8,
            "recent_start_count": 5,
            "last_pitch_count": 92,
        }
    ]

    rows = build_official_close_rows(markets)

    assert [row["side"] for row in rows] == ["over", "under"]
    under = rows[1]
    assert under["dataset_key"] == "2026-05-12:official_close:bryan woo:under:5.5"
    assert under["result"] == "win"
    assert under["theoretical_pnl"] == 1.04
    assert under["market_favorite_side"] == "over"
    assert under["price_sign"] == "plus"
    assert under["model_no_vig_gap"] is not None
    assert under["k_margin_to_line"] == 0.6
    assert under["provider"] is None
    assert under["official_odds_source"] == "therundown+propline"
    assert under["official_market_source_mode"] == "therundown_propline"
    assert under["official_line_source_provider"] == "propline"
    assert under["model_market_relationship"] == "model_fades_favorite"
    assert under["projection_margin_bucket"] == "0.5-1.0"
    assert under["pitcher_throws"] == "R"
    assert under["opportunity_bucket"] == "normal"
    assert under["leash_risk_bucket"] == "normal"
    assert under["large_edge_skepticism_flag"] is False
    assert under["large_edge_skepticism_reasons"] == []
    assert under["pitcher_archetype_bucket"] == "standard_starter"
    assert under["market_anchor_selector"]["mode"] == "shadow"
    assert under["market_anchor_selector_mode"] == "shadow"
    assert under["market_anchor_selector_labels"] == ["market_anchor_strict"]
    assert under["market_anchor_selector_applied"] is False
    assert under["lineup_count"] == 9
    assert under["batter_handedness_mode"] == "path_b"
    assert under["lineup_split_source"] == "real_split_cache"
    assert under["lineup_real_split_count"] == 7
    assert under["lineup_path_a_fallback_count"] == 2
    assert under["lineup_handedness_source"] is None
    assert under["lineup_handedness_runtime_safe"] is None
    assert under["archive_outcome_reconciliation_source"] == "picks_history_exact"


def test_build_official_close_rows_keeps_missing_official_sources_explicitly_null():
    base_market = {
        "date": "2026-04-28",
        "pitcher": "Bryan Woo",
        "k_line": 5.5,
        "actual_ks": 4,
        "winning_side": "under",
        "over_odds": -125,
        "under_odds": 104,
    }

    for source_fields in (
        {},
        {
            "odds_source": "   ",
            "market_source_mode": "",
            "line_source_provider": None,
        },
    ):
        rows = build_official_close_rows([{**base_market, **source_fields}])

        assert len(rows) == 2
        assert rows[0]["official_odds_source"] is None
        assert rows[0]["official_market_source_mode"] is None
        assert rows[0]["official_line_source_provider"] is None
        assert rows[0]["provider"] is None


def test_enrich_rows_with_market_agreement_uses_latest_pre_start_tracker_row(tmp_path):
    markets = [
        {
            "date": "2026-05-12",
            "pitcher": "Bryan Woo",
            "normalized_pitcher": "bryan woo",
            "k_line": 5.5,
            "actual_ks": 4,
            "winning_side": "under",
            "over_odds": -125,
            "under_odds": 104,
            "opening_over_odds": -110,
            "opening_under_odds": 104,
            "ref_book": "FanDuel",
            "model_side": "under",
            "model_win_prob": 0.57,
            "applied_lambda": 4.9,
            "ev_over": {"win_prob": 0.43, "edge": -0.02, "ev": -0.04, "adj_ev": -0.04, "verdict": "PASS"},
            "ev_under": {"win_prob": 0.57, "edge": 0.04, "ev": 0.09, "adj_ev": 0.09, "verdict": "FIRE 1u"},
            "team": "SEA",
            "opp_team": "NYY",
            "home_away": "home",
            "lineup_used": "confirmed",
            "quality_gate_level": "clean",
        }
    ]
    tracker_path = tmp_path / "market_agreement_tracker.jsonl"
    tracker_path.write_text(
        "\n".join(
            [
                '{"slate_date":"2026-05-12","normalized_pitcher":"bryan woo","side":"under","k_line":"5.5","checkpoint":"post_start","provider":"boltodds","book_count":9,"toward_pick_count":9,"away_from_pick_count":0,"better_now_count":0,"worse_now_count":9,"market_consensus":"toward_pick","bet_value_consensus":"worse_now","broad_confirmation":true,"reversal_book_count":0,"volatile_book_count":0,"books_seen":["fanduel","draftkings"],"movement_agreement_label":"market_with_model","movement_strength_label":"broad_with_model","movement_value_label":"number_worse_now","movement_magnitude_bucket":"line_half_plus","tracker_bucket":"fire_market_with_us"}',
                '{"slate_date":"2026-05-12","normalized_pitcher":"bryan woo","side":"under","k_line":"5.5","checkpoint":"pre_30","provider":"propline","book_count":1,"toward_pick_count":1,"away_from_pick_count":0,"better_now_count":0,"worse_now_count":1,"market_consensus":"toward_pick","bet_value_consensus":"worse_now","broad_confirmation":false,"reversal_book_count":0,"volatile_book_count":0,"books_seen":["fanduel"],"movement_agreement_label":"market_with_model","movement_strength_label":"single_book_with_model","movement_value_label":"number_worse_now","movement_magnitude_bucket":"odds_10_19c","tracker_bucket":"fire_market_with_us"}',
                '{"slate_date":"2026-05-12","normalized_pitcher":"bryan woo","side":"under","k_line":"5.5","checkpoint":"pre_5","provider":"boltodds","book_count":3,"toward_pick_count":2,"away_from_pick_count":0,"better_now_count":1,"worse_now_count":2,"market_consensus":"toward_pick","bet_value_consensus":"mixed","broad_confirmation":true,"reversal_book_count":0,"volatile_book_count":0,"books_seen":["fanduel","betmgm","betrivers"],"movement_agreement_label":"market_with_model","movement_strength_label":"broad_with_model","movement_value_label":"value_mixed","movement_magnitude_bucket":"odds_20c_plus","tracker_bucket":"fire_market_with_us"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = dataset.enrich_rows_with_market_agreement(
        build_official_close_rows(markets),
        tracker_path=tracker_path,
    )

    under = next(row for row in rows if row["side"] == "under")
    over = next(row for row in rows if row["side"] == "over")
    assert under["provider"] == "boltodds"
    assert under["market_agreement_checkpoint"] == "pre_5"
    assert under["book_count"] == 3
    assert under["books_seen"] == ["fanduel", "betmgm", "betrivers"]
    assert under["toward_pick_count"] == 2
    assert under["away_from_pick_count"] == 0
    assert under["better_now_count"] == 1
    assert under["worse_now_count"] == 2
    assert under["market_consensus"] == "toward_pick"
    assert under["bet_value_consensus"] == "mixed"
    assert under["broad_confirmation"] is True
    assert under["movement_strength_label"] == "broad_with_model"
    assert under["market_agreement_label"] == "market_with_model"
    assert over["provider"] is None
    assert over["book_count"] is None


def test_enrich_rows_with_live_market_display_adds_book_board_confidence_fields(tmp_path):
    markets = [
        {
            "date": "2026-05-12",
            "pitcher": "Bryan Woo",
            "normalized_pitcher": "bryan woo",
            "k_line": 5.5,
            "actual_ks": 4,
            "winning_side": "under",
            "over_odds": -125,
            "under_odds": 104,
            "opening_over_odds": -110,
            "opening_under_odds": 104,
            "ref_book": "FanDuel",
            "model_side": "under",
            "model_win_prob": 0.57,
            "applied_lambda": 4.9,
            "ev_over": {"win_prob": 0.43, "edge": -0.02, "ev": -0.04, "adj_ev": -0.04, "verdict": "PASS"},
            "ev_under": {"win_prob": 0.57, "edge": 0.04, "ev": 0.09, "adj_ev": 0.09, "verdict": "FIRE 1u"},
            "team": "SEA",
            "opp_team": "NYY",
            "home_away": "home",
            "lineup_used": "confirmed",
            "quality_gate_level": "clean",
        }
    ]
    display_path = tmp_path / "live_market_display_state.json"
    display_path.write_text(
        """
        {
          "rows": [
            {
              "slate_date": "2026-05-12",
              "normalized_pitcher": "bryan woo",
              "side": "under",
              "k_line": "5.5",
              "game_state": "in_progress",
              "game_time": "2026-05-12T22:40:00+00:00",
              "latest_snapshot_at": "2026-05-12T22:50:00+00:00",
              "provider": "boltodds",
              "book_count": 6,
              "books_seen": ["fanduel", "draftkings"],
              "broad_confirmation": true,
              "best_is_off_market": true,
              "best_book": "draftkings",
              "best_line": 6.5,
              "best_odds": 180,
              "actionable_state": "off_market"
            },
            {
              "slate_date": "2026-05-12",
              "normalized_pitcher": "bryan woo",
              "side": "under",
              "k_line": "5.5",
              "game_state": "pregame",
              "game_time": "2026-05-12T22:40:00+00:00",
              "latest_snapshot_at": "2026-05-12T22:10:00+00:00",
              "provider": "propline",
              "book_count": 3,
              "books_seen": ["fanduel", "draftkings", "betrivers"],
              "market_consensus": "toward_pick",
              "bet_value_consensus": "worse_now",
              "broad_confirmation": true,
              "best_is_off_market": true,
              "best_book": "draftkings",
              "best_line": 5.5,
              "best_odds": 124,
              "actionable_state": "off_market"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    rows = dataset.enrich_rows_with_live_market_display(
        build_official_close_rows(markets),
        live_market_display_path=display_path,
    )

    under = next(row for row in rows if row["side"] == "under")
    assert under["live_display_provider"] == "propline"
    assert under["live_display_state"] == "off_market"
    assert under["live_display_latest_snapshot_at"] == "2026-05-12T22:10:00+00:00"
    assert under["broad_confirmation"] is True
    assert under["best_is_off_market"] is True
    assert under["best_book"] == "draftkings"
    assert under["best_line"] == 5.5
    assert under["best_odds"] == 124
    assert under["book_count"] == 3
    assert under["books_seen"] == ["betrivers", "draftkings", "fanduel"]


def test_build_official_close_rows_flags_large_edge_skepticism():
    markets = [
        {
            "date": "2026-05-12",
            "pitcher": "Short Leash",
            "normalized_pitcher": "short leash",
            "k_line": 5.5,
            "actual_ks": 4,
            "winning_side": "under",
            "over_odds": -130,
            "under_odds": 110,
            "opening_over_odds": -110,
            "opening_under_odds": 100,
            "ref_book": "FanDuel",
            "model_side": "under",
            "applied_lambda": 4.4,
            "ev_over": {"win_prob": 0.39, "edge": -0.10, "verdict": "PASS"},
            "ev_under": {"win_prob": 0.61, "edge": 0.09, "verdict": "FIRE 2u"},
            "team": "SEA",
            "opp_team": "NYY",
            "home_away": "home",
            "lineup_used": "projected",
            "quality_gate_level": "soft_cap",
            "quality_gate_reasons": ["projected_lineup"],
            "avg_ip": 4.2,
            "recent_start_count": 3,
            "last_pitch_count": 108,
        }
    ]

    rows = build_official_close_rows(markets)
    under = rows[1]

    assert under["model_edge_bucket"] == "5%+"
    assert under["large_edge_skepticism_flag"] is True
    assert under["large_edge_skepticism_reasons"] == [
        "model_fades_market_favorite",
        "quality_gate_soft_cap",
        "lineup_or_quality_gate_reason",
        "market_moved_against_side",
        "leash_risk_high",
        "short_leash_opportunity",
    ]
    assert under["pitcher_archetype_bucket"] == "short_leash"


def test_build_summary_tracks_coverage_and_duplicates():
    rows = [
        {
            "dataset_key": "a",
            "slate_date": "2026-05-12",
            "result": "win",
            "team": "SEA",
            "opp_team": "NYY",
            "american_odds": -110,
            "model_win_prob": 0.55,
            "model_side": "under",
            "context_snapshot": "official_close",
            "is_tracked_pick": True,
            "price_clv_cents": 8,
            "beat_close_price": True,
            "clv_type": "price_only",
            "process_outcome_bucket": "good_process_win",
            "bet_timing_window": "pre_30",
            "large_edge_skepticism_flag": False,
            "pitcher_archetype_bucket": "standard_starter",
            "opportunity_bucket": "normal",
            "leash_risk_bucket": "normal",
            "model_market_relationship": "model_fades_favorite",
            "lineup_right_batters": 5,
            "lineup_left_batters": 3,
            "lineup_switch_batters": 1,
            "lineup_handedness_source": "mlb_boxscore_reconstructed",
            "actual_ip": 5.667,
            "actual_pitch_count": 91,
            "batters_faced": 22,
            "actual_opportunity_source": "mlb_boxscore_reconstructed",
            "provider": "boltodds",
            "official_odds_source": "therundown+propline",
            "official_market_source_mode": "therundown_propline",
            "official_line_source_provider": "propline",
            "live_display_provider": "propline",
            "live_display_state": "off_market",
            "live_display_latest_snapshot_at": "2026-05-12T22:10:00+00:00",
            "book_count": 3,
            "toward_pick_count": 2,
            "away_from_pick_count": 0,
            "market_agreement_label": "market_with_model",
            "best_is_off_market": True,
            "broad_confirmation": True,
        },
        {
            "dataset_key": "a",
            "slate_date": "2026-05-12",
            "result": None,
            "team": "",
            "opp_team": "",
            "american_odds": None,
            "model_win_prob": None,
            "context_snapshot": "official_close",
            "is_tracked_pick": False,
            "price_clv_cents": None,
            "beat_close_price": None,
            "clv_type": "not_tracked",
            "process_outcome_bucket": "unknown",
            "bet_timing_window": "unknown",
            "large_edge_skepticism_flag": True,
            "pitcher_archetype_bucket": "opener_or_mismatch",
            "opportunity_bucket": "unknown",
            "leash_risk_bucket": "high",
            "model_market_relationship": "unknown",
            "lineup_right_batters": None,
            "lineup_left_batters": None,
            "lineup_switch_batters": None,
            "lineup_handedness_source": None,
            "actual_ip": None,
            "actual_pitch_count": None,
            "batters_faced": None,
            "actual_opportunity_source": None,
            "provider": None,
            "official_odds_source": None,
            "official_market_source_mode": None,
            "official_line_source_provider": None,
            "live_display_provider": None,
            "live_display_state": None,
            "live_display_latest_snapshot_at": None,
            "book_count": None,
            "toward_pick_count": None,
            "away_from_pick_count": None,
            "market_agreement_label": None,
            "best_is_off_market": None,
            "broad_confirmation": False,
        },
    ]

    summary = build_summary(rows)

    assert summary["total_rows"] == 2
    assert summary["graded_rows"] == 1
    assert summary["duplicate_dataset_keys"] == 1
    assert summary["missing_team_or_opponent"] == 1
    assert summary["missing_book_odds"] == 1
    assert summary["missing_model_fields"] == 1
    assert summary["tracked_pick_rows"] == 1
    assert summary["rows_with_price_clv"] == 1
    assert summary["beat_close_price_rows"] == 1
    assert summary["model_market_relationship_counts"]["model_fades_favorite"] == 1
    assert summary["opportunity_bucket_counts"]["normal"] == 1
    assert summary["clv_type_counts"]["price_only"] == 1
    assert summary["process_outcome_bucket_counts"]["good_process_win"] == 1
    assert summary["large_edge_skepticism_rows"] == 1
    assert summary["pitcher_archetype_bucket_counts"]["opener_or_mismatch"] == 1
    assert summary["lineup_hand_count_rows"] == 1
    assert summary["lineup_handedness_source_counts"]["mlb_boxscore_reconstructed"] == 1
    assert summary["actual_opportunity_rows"] == 1
    assert summary["actual_pitch_count_rows"] == 1
    assert summary["batters_faced_rows"] == 1
    assert summary["actual_opportunity_source_counts"]["mlb_boxscore_reconstructed"] == 1
    assert summary["market_agreement_rows"] == 1
    assert summary["market_book_count_rows"] == 1
    assert summary["toward_away_count_rows"] == 1
    assert summary["live_display_rows"] == 1
    assert summary["best_off_market_rows"] == 1
    assert summary["market_broad_confirmation_rows"] == 1
    assert summary["market_agreement_label_counts"]["market_with_model"] == 1
    assert summary["official_odds_source_rows"] == 1
    assert summary["official_market_source_mode_rows"] == 1
    assert summary["official_line_source_provider_rows"] == 1
    assert summary["official_odds_source_counts"] == {
        "missing": 1,
        "therundown+propline": 1,
    }
    assert summary["official_market_source_mode_counts"] == {
        "missing": 1,
        "therundown_propline": 1,
    }
    assert summary["official_line_source_provider_counts"] == {
        "missing": 1,
        "propline": 1,
    }


def test_load_archived_markets_for_dataset_preserves_baseball_context(tmp_path):
    archive = tmp_path / "2026-05-12.json"
    archive.write_text(
        """
        {
          "generated_at": "2026-05-12T13:00:00Z",
          "pitchers": [
            {
              "pitcher": "Bryan Woo",
              "team": "SEA",
              "opp_team": "NYY",
              "k_line": 5.5,
              "actual_ks": 4,
              "best_over_odds": -125,
              "best_under_odds": 104,
              "opening_over_odds": -110,
              "opening_under_odds": -110,
              "ref_book": "FanDuel",
              "ev_over": {"win_prob": 0.43, "verdict": "PASS"},
              "ev_under": {"win_prob": 0.57, "verdict": "FIRE 1u"}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    markets = load_archived_markets_for_dataset(
        tmp_path,
        start_date="2026-05-12",
        end_date="2026-05-12",
    )

    assert len(markets) == 1
    assert markets[0]["team"] == "SEA"
    assert markets[0]["opp_team"] == "NYY"
    assert markets[0]["winning_side"] == "under"
    assert markets[0]["source_artifact_path"] == "dashboard/data/processed/2026-05-12.json"


def test_load_archived_markets_recovers_missing_actual_from_one_exact_graded_history_row(
    tmp_path,
):
    archive = tmp_path / "2026-06-16.json"
    archive.write_text(
        json.dumps(
            {
                "pitchers": [
                    {
                        "pitcher": "Adrian Houser",
                        "k_line": 3.5,
                        "actual_ks": None,
                        "result": None,
                        "best_over_odds": 114,
                        "best_under_odds": -146,
                        "ev_over": {"verdict": "PASS"},
                        "ev_under": {"verdict": "LEAN"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    stats = {}

    markets = load_archived_markets_for_dataset(
        tmp_path,
        start_date="2026-06-16",
        end_date="2026-06-16",
        outcome_history_rows=[
            {
                "date": "2026-06-16",
                "pitcher": "Adrian Houser",
                "side": "under",
                "locked_k_line": 3.5,
                "result": "win",
                "actual_ks": 2,
            }
        ],
        outcome_reconciliation_stats=stats,
    )

    assert len(markets) == 1
    assert markets[0]["actual_ks"] == 2
    assert markets[0]["winning_side"] == "under"
    assert markets[0]["archive_outcome_reconciliation_source"] == "picks_history_exact"
    assert stats == {"recovered_markets": 1, "ambiguous_markets": 0}


def test_load_archived_markets_recovers_pitcher_game_actual_when_market_line_moved(
    tmp_path,
):
    archive = tmp_path / "2026-06-03.json"
    archive.write_text(
        json.dumps(
            {
                "pitchers": [
                    {
                        "pitcher": "Robert Gasser",
                        "k_line": 4.5,
                        "actual_ks": None,
                        "best_over_odds": 118,
                        "best_under_odds": -144,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    stats = {}

    markets = load_archived_markets_for_dataset(
        tmp_path,
        start_date="2026-06-03",
        end_date="2026-06-03",
        outcome_history_rows=[
            {
                "date": "2026-06-03",
                "pitcher": "Robert Gasser",
                "side": "under",
                "locked_k_line": 3.5,
                "result": "loss",
                "actual_ks": 5,
            }
        ],
        outcome_reconciliation_stats=stats,
    )

    assert len(markets) == 1
    assert markets[0]["actual_ks"] == 5
    assert markets[0]["k_line"] == 4.5
    assert markets[0]["winning_side"] == "over"
    assert (
        markets[0]["archive_outcome_reconciliation_source"]
        == "picks_history_pitcher_game"
    )
    assert stats == {"recovered_markets": 1, "ambiguous_markets": 0}


def test_load_archived_markets_conflicting_pitcher_game_actuals_fail_closed(tmp_path):
    archive = tmp_path / "2026-06-03.json"
    archive.write_text(
        json.dumps(
            {
                "pitchers": [
                    {
                        "pitcher": "Robert Gasser",
                        "k_line": 4.5,
                        "actual_ks": None,
                        "best_over_odds": 118,
                        "best_under_odds": -144,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    stats = {}

    markets = load_archived_markets_for_dataset(
        tmp_path,
        start_date="2026-06-03",
        end_date="2026-06-03",
        outcome_history_rows=[
            {
                "date": "2026-06-03",
                "pitcher": "Robert Gasser",
                "locked_k_line": 3.5,
                "result": "loss",
                "actual_ks": 5,
            },
            {
                "date": "2026-06-03",
                "pitcher": "Robert Gasser",
                "locked_k_line": 5.5,
                "result": "win",
                "actual_ks": 6,
            },
        ],
        outcome_reconciliation_stats=stats,
    )

    assert markets == []
    assert stats == {"recovered_markets": 0, "ambiguous_markets": 1}


def test_load_archived_markets_exact_line_ambiguity_never_uses_pitcher_game_fallback(
    tmp_path,
):
    archive = tmp_path / "2026-06-03.json"
    archive.write_text(
        json.dumps(
            {
                "pitchers": [
                    {
                        "pitcher": "Robert Gasser",
                        "k_line": 4.5,
                        "actual_ks": None,
                        "best_over_odds": 118,
                        "best_under_odds": -144,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    markets = load_archived_markets_for_dataset(
        tmp_path,
        start_date="2026-06-03",
        end_date="2026-06-03",
        outcome_history_rows=[
            {
                "date": "2026-06-03",
                "pitcher": "Robert Gasser",
                "locked_k_line": 4.5,
                "side": "over",
                "result": "win",
                "actual_ks": 5,
            },
            {
                "date": "2026-06-03",
                "pitcher": "Robert Gasser",
                "locked_k_line": 4.5,
                "side": "under",
                "result": "loss",
                "actual_ks": 5,
            },
        ],
    )

    assert markets == []


def test_load_archived_markets_never_overwrites_archive_actual(tmp_path):
    archive = tmp_path / "2026-06-16.json"
    archive.write_text(
        json.dumps(
            {
                "pitchers": [
                    {
                        "pitcher": "Adrian Houser",
                        "k_line": 3.5,
                        "actual_ks": 5,
                        "best_over_odds": 114,
                        "best_under_odds": -146,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    stats = {}

    markets = load_archived_markets_for_dataset(
        tmp_path,
        start_date="2026-06-16",
        end_date="2026-06-16",
        outcome_history_rows=[
            {
                "date": "2026-06-16",
                "pitcher": "Adrian Houser",
                "side": "under",
                "locked_k_line": 3.5,
                "result": "win",
                "actual_ks": 2,
            }
        ],
        outcome_reconciliation_stats=stats,
    )

    assert markets[0]["actual_ks"] == 5
    assert markets[0]["winning_side"] == "over"
    assert markets[0]["archive_outcome_reconciliation_source"] == "archive"
    assert stats == {"recovered_markets": 0, "ambiguous_markets": 0}


def test_load_archived_markets_missing_actual_fails_closed_without_graded_history_actual(
    tmp_path,
):
    archive = tmp_path / "2026-06-16.json"
    archive.write_text(
        json.dumps(
            {
                "pitchers": [
                    {
                        "pitcher": "Adrian Houser",
                        "k_line": 3.5,
                        "actual_ks": None,
                        "best_over_odds": 114,
                        "best_under_odds": -146,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    invalid_history_cases = [
        [
            {
                "date": "2026-06-16",
                "pitcher": "Adrian Houser",
                "locked_k_line": 3.5,
                "result": None,
                "actual_ks": 2,
            }
        ],
        [
            {
                "date": "2026-06-16",
                "pitcher": "Adrian Houser",
                "locked_k_line": 3.5,
                "result": "win",
                "actual_ks": None,
            }
        ],
    ]

    for history_rows in invalid_history_cases:
        stats = {}
        markets = load_archived_markets_for_dataset(
            tmp_path,
            start_date="2026-06-16",
            end_date="2026-06-16",
            outcome_history_rows=history_rows,
            outcome_reconciliation_stats=stats,
        )
        assert markets == []
        assert stats == {"recovered_markets": 0, "ambiguous_markets": 0}


def test_load_archived_markets_ambiguous_exact_history_fails_closed(tmp_path):
    archive = tmp_path / "2026-06-16.json"
    archive.write_text(
        json.dumps(
            {
                "pitchers": [
                    {
                        "pitcher": "Adrian Houser",
                        "k_line": 3.5,
                        "actual_ks": None,
                        "best_over_odds": 114,
                        "best_under_odds": -146,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    history_row = {
        "date": "2026-06-16",
        "pitcher": "Adrian Houser",
        "locked_k_line": 3.5,
        "result": "win",
        "actual_ks": 2,
    }
    stats = {}

    markets = load_archived_markets_for_dataset(
        tmp_path,
        start_date="2026-06-16",
        end_date="2026-06-16",
        outcome_history_rows=[history_row, dict(history_row)],
        outcome_reconciliation_stats=stats,
    )

    assert markets == []
    assert stats == {"recovered_markets": 0, "ambiguous_markets": 1}


def test_load_archived_markets_can_read_production_artifact_api(monkeypatch):
    seen_urls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            import json

            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(url, timeout=20):
        seen_urls.append(url)
        if "type=index" in url:
            return Response(
                {
                    "dates": [
                        {"date": "2026-05-13"},
                        {"date": "2026-05-12"},
                        {"date": "2026-04-27"},
                    ]
                }
            )
        assert "type=dated_slate" in url
        assert "date=2026-05-12" in url
        return Response(
            {
                "generated_at": "2026-05-12T13:00:00Z",
                "pitchers": [
                    {
                        "pitcher": "Bryan Woo",
                        "team": "SEA",
                        "opp_team": "NYY",
                        "k_line": 5.5,
                        "actual_ks": 4,
                        "best_over_odds": -125,
                        "best_under_odds": 104,
                        "opening_over_odds": -110,
                        "opening_under_odds": -110,
                        "ref_book": "FanDuel",
                        "ev_over": {"win_prob": 0.43, "verdict": "PASS"},
                        "ev_under": {"win_prob": 0.57, "verdict": "FIRE 1u"},
                    }
                ],
            }
        )

    monkeypatch.setattr(dataset, "urlopen", fake_urlopen)

    markets = load_archived_markets_for_dataset(
        start_date="2026-05-12",
        end_date="2026-05-12",
        artifact_api_url="https://example.test/.netlify/functions/get-artifact",
    )

    assert len(markets) == 1
    assert markets[0]["source_artifact_path"].startswith(
        "https://example.test/.netlify/functions/get-artifact?"
    )
    assert any("type=index" in url for url in seen_urls)
    assert any("type=dated_slate" in url and "date=2026-05-12" in url for url in seen_urls)


def test_load_archived_markets_fetches_requested_remote_date_range_when_index_is_incomplete(monkeypatch):
    seen_urls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            import json

            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(url, timeout=20):
        seen_urls.append(url)
        if "type=index" in url:
            return Response({"dates": [{"date": "2026-05-30"}]})
        assert "type=dated_slate" in url
        assert "date=2026-06-01" in url
        return Response(
            {
                "generated_at": "2026-06-02T01:08:52Z",
                "pitchers": [
                    {
                        "pitcher": "Example Starter",
                        "team": "SEA",
                        "opp_team": "NYY",
                        "k_line": 4.5,
                        "actual_ks": 6,
                        "best_over_odds": -110,
                        "best_under_odds": -110,
                        "ev_over": {"win_prob": 0.55, "verdict": "LEAN"},
                        "ev_under": {"win_prob": 0.45, "verdict": "PASS"},
                    }
                ],
            }
        )

    monkeypatch.setattr(dataset, "urlopen", fake_urlopen)

    markets = load_archived_markets_for_dataset(
        start_date="2026-06-01",
        end_date="2026-06-01",
        artifact_api_url="https://example.test/.netlify/functions/get-artifact",
    )

    assert len(markets) == 1
    assert markets[0]["date"] == "2026-06-01"
    assert any("type=index" in url for url in seen_urls)
    assert any("type=dated_slate" in url and "date=2026-06-01" in url for url in seen_urls)


def test_load_archived_markets_skips_missing_production_dated_archives(monkeypatch, capsys):
    from urllib.error import HTTPError

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            import json

            return json.dumps(
                {"dates": [{"date": "2026-05-21"}, {"date": "2026-05-20"}]}
            ).encode("utf-8")

    def fake_urlopen(url, timeout=20):
        if "type=index" in url:
            return Response()
        if "date=2026-05-20" in url:
            raise HTTPError(url, 404, "Not Found", hdrs=None, fp=None)
        return Response()

    monkeypatch.setattr(dataset, "urlopen", fake_urlopen)

    markets = load_archived_markets_for_dataset(
        start_date="2026-05-20",
        end_date="2026-05-21",
        artifact_api_url="https://example.test/.netlify/functions/get-artifact",
    )

    assert markets == []
    assert "skipped missing production dated_slate artifacts: 2026-05-20" in capsys.readouterr().err


def test_reconcile_picks_history_matches_dataset_keys(tmp_path):
    history = tmp_path / "picks_history.json"
    history.write_text(
        """
        [
          {
            "date": "2026-05-12",
            "pitcher": "Bryan Woo",
            "side": "under",
            "k_line": 5.5,
            "result": "win"
          },
          {
            "date": "2026-05-12",
            "pitcher": "Other Pitcher",
            "side": "over",
            "k_line": 4.5,
            "result": "loss"
          }
        ]
        """,
        encoding="utf-8",
    )
    rows = [
        {
            "dataset_key": "2026-05-12:official_close:bryan woo:under:5.5",
        }
    ]

    result = reconcile_picks_history(rows, history_path=history, start_date="2026-05-12")

    assert result["graded_pick_rows"] == 2
    assert result["matched_pick_rows"] == 1
    assert result["unmatched_pick_rows"] == 1
    assert result["unmatched_examples"][0]["pitcher"] == "Other Pitcher"


def test_reconcile_picks_history_can_read_production_artifact_api(monkeypatch):
    seen_urls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            import json

            return json.dumps(
                [
                    {
                        "date": "2026-05-12",
                        "pitcher": "Bryan Woo",
                        "side": "under",
                        "k_line": 5.5,
                        "result": "win",
                    }
                ]
            ).encode("utf-8")

    def fake_urlopen(url, timeout=20):
        seen_urls.append(url)
        assert "type=picks_history" in url
        return Response()

    monkeypatch.setattr(dataset, "urlopen", fake_urlopen)
    rows = [
        {
            "dataset_key": "2026-05-12:official_close:bryan woo:under:5.5",
        }
    ]

    result = reconcile_picks_history(
        rows,
        start_date="2026-05-12",
        artifact_api_url="https://example.test/.netlify/functions/get-artifact",
    )

    assert result["graded_pick_rows"] == 1
    assert result["matched_pick_rows"] == 1
    assert seen_urls == [
        "https://example.test/.netlify/functions/get-artifact?"
        "type=picks_history&start_date=2026-05-12"
    ]


def test_build_dataset_bounds_remote_history_and_recovers_june_3_pitcher_game(
    monkeypatch,
    tmp_path,
):
    seen_urls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(url, timeout=20):
        seen_urls.append(url)
        if "type=picks_history" in url:
            return Response(
                [
                    {
                        "date": "2026-06-03",
                        "pitcher": "Robert Gasser",
                        "side": "under",
                        "k_line": 3.5,
                        "result": "loss",
                        "actual_ks": 5,
                    }
                ]
            )
        if "type=index" in url:
            return Response({"dates": [{"date": "2026-06-03"}]})
        assert "type=dated_slate" in url
        assert "date=2026-06-03" in url
        return Response(
            {
                "pitchers": [
                    {
                        "pitcher": "Robert Gasser",
                        "k_line": 4.5,
                        "actual_ks": None,
                        "best_over_odds": 118,
                        "best_under_odds": -144,
                    }
                ]
            }
        )

    monkeypatch.setattr(dataset, "urlopen", fake_urlopen)

    rows = dataset.build_dataset(
        start_date="2026-06-03",
        end_date="2026-06-03",
        artifact_api_url="https://example.test/.netlify/functions/get-artifact",
        lineup_handedness_backfill_path=tmp_path / "missing-lineups.json",
        actual_opportunity_backfill_path=tmp_path / "missing-opportunity.json",
        market_agreement_tracker_path=None,
        live_market_display_path=None,
    )

    assert any(
        "type=picks_history&start_date=2026-06-03&end_date=2026-06-03" in url
        for url in seen_urls
    )
    assert {row["actual_ks"] for row in rows} == {5}
    assert {
        row["archive_outcome_reconciliation_source"] for row in rows
    } == {"picks_history_pitcher_game"}


def test_enrich_rows_with_lineup_handedness_marks_reconstructed_context(tmp_path):
    key = lineup_handedness_lookup_key(
        "2026-05-12",
        "Seattle Mariners",
        "New York Yankees",
        "2026-05-12T22:40:00Z",
    )
    artifact = tmp_path / "lineup_handedness_backfill.json"
    artifact.write_text(
        """
        {
          "lineups": {
            "2026-05-12|seattle mariners|new york yankees|2026-05-12T22:40:00Z": {
              "game_pk": 101,
              "lineup_count": 9,
              "lineup_right_batters": 5,
              "lineup_left_batters": 3,
              "lineup_switch_batters": 1,
              "lineup_handedness_source": "mlb_boxscore_reconstructed",
              "lineup_handedness_runtime_safe": false
            }
          }
        }
        """,
        encoding="utf-8",
    )
    rows = [
        {
            "slate_date": "2026-05-12",
            "team": "Seattle Mariners",
            "opp_team": "New York Yankees",
            "game_time": "2026-05-12T22:40:00Z",
            "pitcher_throws": "R",
            "lineup_count": 9,
            "lineup_right_batters": None,
            "lineup_left_batters": None,
            "lineup_switch_batters": None,
            "handedness_matchup_bucket": None,
        }
    ]

    enriched = enrich_rows_with_lineup_handedness(rows, backfill_path=artifact)

    assert key in artifact.read_text(encoding="utf-8")
    assert enriched[0]["lineup_right_batters"] == 5
    assert enriched[0]["lineup_left_batters"] == 3
    assert enriched[0]["lineup_switch_batters"] == 1
    assert enriched[0]["handedness_matchup_bucket"] == "balanced"
    assert enriched[0]["lineup_handedness_source"] == "mlb_boxscore_reconstructed"
    assert enriched[0]["lineup_handedness_runtime_safe"] is False
    assert enriched[0]["lineup_handedness_count_matches_existing"] is True


def test_enrich_rows_with_actual_opportunity_marks_reconstructed_context(tmp_path):
    key = actual_opportunity_lookup_key(
        "2026-05-12",
        "Seattle Mariners",
        "New York Yankees",
        "2026-05-12T22:40:00Z",
        "Bryan Woo",
    )
    artifact = tmp_path / "actual_opportunity_backfill.json"
    artifact.write_text(
        """
        {
          "opportunities": {
            "2026-05-12|seattle mariners|new york yankees|2026-05-12T22:40:00Z|bryan woo": {
              "game_pk": 101,
              "actual_ip": 5.6666666667,
              "actual_pitch_count": 91,
              "batters_faced": 22,
              "actual_opportunity_source": "mlb_boxscore_reconstructed",
              "actual_opportunity_runtime_safe": false,
              "pitcher_match_type": "normalized_name"
            }
          }
        }
        """,
        encoding="utf-8",
    )
    rows = [
        {
            "slate_date": "2026-05-12",
            "team": "Seattle Mariners",
            "opp_team": "New York Yankees",
            "game_time": "2026-05-12T22:40:00Z",
            "pitcher": "Bryan Woo",
            "side": "over",
        },
        {
            "slate_date": "2026-05-12",
            "team": "Seattle Mariners",
            "opp_team": "New York Yankees",
            "game_time": "2026-05-12T22:40:00Z",
            "pitcher": "Bryan Woo",
            "side": "under",
        },
    ]

    enriched = enrich_rows_with_actual_opportunity(rows, backfill_path=artifact)

    assert key in artifact.read_text(encoding="utf-8")
    assert [row["actual_pitch_count"] for row in enriched] == [91, 91]
    assert [row["batters_faced"] for row in enriched] == [22, 22]
    assert round(enriched[0]["actual_ip"], 3) == 5.667
    assert enriched[0]["actual_opportunity_source"] == "mlb_boxscore_reconstructed"
    assert enriched[0]["actual_opportunity_runtime_safe"] is False
    assert enriched[0]["actual_opportunity_game_pk"] == 101
    assert enriched[0]["actual_opportunity_pitcher_match_type"] == "normalized_name"


def test_reconcile_picks_history_allows_unique_pitcher_side_fallback(tmp_path):
    history = tmp_path / "picks_history.json"
    history.write_text(
        """
        [
          {
            "date": "2026-05-12",
            "pitcher": "Bryan Woo",
            "side": "under",
            "k_line": 5.5,
            "result": "win"
          }
        ]
        """,
        encoding="utf-8",
    )
    rows = [
        {
            "dataset_key": "2026-05-12:official_close:bryan woo:under:6.5",
            "slate_date": "2026-05-12",
            "normalized_pitcher": "bryan woo",
            "side": "under",
        }
    ]

    result = reconcile_picks_history(rows, history_path=history, start_date="2026-05-12")

    assert result["graded_pick_rows"] == 1
    assert result["matched_pick_rows"] == 1
    assert result["unique_side_fallback_matches"] == 1


def test_reconcile_picks_history_can_limit_to_loaded_slate_dates(tmp_path):
    history = tmp_path / "picks_history.json"
    history.write_text(
        """
        [
          {
            "date": "2026-05-12",
            "pitcher": "Bryan Woo",
            "side": "under",
            "k_line": 5.5,
            "result": "win"
          },
          {
            "date": "2026-05-13",
            "pitcher": "Other Pitcher",
            "side": "over",
            "k_line": 4.5,
            "result": "loss"
          }
        ]
        """,
        encoding="utf-8",
    )
    rows = [
        {
            "dataset_key": "2026-05-12:official_close:bryan woo:under:5.5",
            "slate_date": "2026-05-12",
            "normalized_pitcher": "bryan woo",
            "side": "under",
        }
    ]

    result = reconcile_picks_history(
        rows,
        history_path=history,
        start_date="2026-05-12",
        included_slate_dates={"2026-05-12"},
    )

    assert result["graded_pick_rows"] == 1
    assert result["matched_pick_rows"] == 1
    assert result["unmatched_pick_rows"] == 0


def test_enrich_rows_with_pick_history_adds_bet_time_and_clv_fields(tmp_path):
    history = tmp_path / "picks_history.json"
    history.write_text(
        """
        [
          {
            "date": "2026-05-12",
            "pitcher": "Bryan Woo",
            "side": "under",
            "k_line": 5.5,
            "result": "win",
            "odds": 110,
            "ref_book": "FanDuel",
            "locked_k_line": 5.5,
            "locked_odds": 110,
            "locked_verdict": "LEAN",
            "display_verdict": "LEAN",
            "actionable_verdict": "LEAN",
            "raw_verdict": "FIRE 1u",
            "locked_adj_ev": 0.12,
            "verdict_cap_reason": "confidence referee: market fade",
            "confidence_referee": {
              "mode": "enforce",
              "applied": true,
              "would_cap_to": "LEAN",
              "reasons": ["price_driven_market_fade"]
            },
            "market_anchor_selector": {
              "mode": "shadow",
              "labels": ["market_anchor_side_agrees"],
              "applied": false
            },
            "projection_challenger": {
              "mode": "shadow",
              "candidate": "market_shrink_25",
              "applied": false,
              "current_lambda": 5.9,
              "would_lambda": 5.8
            },
            "locked_at": "2026-05-12T22:30:00Z",
            "game_time": "2026-05-12T23:05:00Z",
            "pnl": 1.1
          }
        ]
        """,
        encoding="utf-8",
    )
    rows = [
        {
            "dataset_key": "2026-05-12:official_close:bryan woo:under:5.5",
            "slate_date": "2026-05-12",
            "normalized_pitcher": "bryan woo",
            "side": "under",
            "k_line": 5.5,
            "closing_line": 5.5,
            "closing_odds": 104,
            "bookmaker_key": "FanDuel",
            "result": "win",
            "game_time": "2026-05-12T23:05:00Z",
        }
    ]

    enriched = enrich_rows_with_pick_history(rows, history_path=history, start_date="2026-05-12")

    assert enriched[0]["is_tracked_pick"] is True
    assert enriched[0]["bet_time_line"] == 5.5
    assert enriched[0]["bet_time_odds"] == 110
    assert enriched[0]["bet_time_book"] == "FanDuel"
    assert enriched[0]["price_clv_cents"] == 6
    assert enriched[0]["beat_close_price"] is True
    assert enriched[0]["line_clv_delta"] == 0.0
    assert enriched[0]["beat_close_line"] is False
    assert enriched[0]["pick_history_match_type"] == "exact_line"
    assert enriched[0]["clv_type"] == "price_only"
    assert enriched[0]["process_outcome_bucket"] == "good_process_win"
    assert enriched[0]["bet_timing_window"] == "pre_60"
    assert enriched[0]["locked_verdict"] == "LEAN"
    assert enriched[0]["display_verdict"] == "LEAN"
    assert enriched[0]["actionable_verdict"] == "LEAN"
    assert enriched[0]["raw_verdict"] == "FIRE 1u"
    assert enriched[0]["locked_adj_ev"] == 0.12
    assert enriched[0]["verdict_cap_reason"] == "confidence referee: market fade"
    assert enriched[0]["confidence_referee"]["applied"] is True
    assert enriched[0]["market_anchor_selector"]["mode"] == "shadow"
    assert enriched[0]["market_anchor_selector_mode"] == "shadow"
    assert enriched[0]["market_anchor_selector_labels"] == ["market_anchor_side_agrees"]
    assert enriched[0]["market_anchor_selector_applied"] is False
    assert enriched[0]["projection_challenger"]["candidate"] == "market_shrink_25"
    assert enriched[0]["projection_challenger"]["applied"] is False
