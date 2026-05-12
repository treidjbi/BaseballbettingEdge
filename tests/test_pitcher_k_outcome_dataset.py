from analytics.diagnostics.pitcher_k_outcome_dataset import (
    build_official_close_rows,
    build_summary,
    enrich_rows_with_pick_history,
    load_archived_markets_for_dataset,
    reconcile_picks_history,
    theoretical_pnl,
)


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
            "opening_under_odds": -110,
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
            "quality_gate_level": "clean",
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
    assert under["lineup_count"] == 9


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
            "opportunity_bucket": "normal",
            "leash_risk_bucket": "normal",
            "model_market_relationship": "model_fades_favorite",
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
            "opportunity_bucket": "unknown",
            "leash_risk_bucket": "high",
            "model_market_relationship": "unknown",
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
            "locked_at": "2026-05-12T22:30:00Z",
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
