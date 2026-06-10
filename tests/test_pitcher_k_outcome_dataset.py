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
            "ev_under": {"win_prob": 0.57, "edge": 0.04, "ev": 0.09, "adj_ev": 0.09, "verdict": "FIRE 1u"},
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
    assert under["model_market_relationship"] == "model_fades_favorite"
    assert under["projection_margin_bucket"] == "0.5-1.0"
    assert under["pitcher_throws"] == "R"
    assert under["opportunity_bucket"] == "normal"
    assert under["leash_risk_bucket"] == "normal"
    assert under["large_edge_skepticism_flag"] is False
    assert under["large_edge_skepticism_reasons"] == []
    assert under["pitcher_archetype_bucket"] == "standard_starter"
    assert under["lineup_count"] == 9
    assert under["batter_handedness_mode"] == "path_b"
    assert under["lineup_split_source"] == "real_split_cache"
    assert under["lineup_real_split_count"] == 7
    assert under["lineup_path_a_fallback_count"] == 2
    assert under["lineup_handedness_source"] is None
    assert under["lineup_handedness_runtime_safe"] is None


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
        "https://example.test/.netlify/functions/get-artifact?type=picks_history"
    ]


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
