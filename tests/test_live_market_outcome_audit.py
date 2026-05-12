from analytics.diagnostics.live_market_outcome_audit import (
    build_checkpoint_evidence_rows,
    build_report,
    join_evidence_to_results,
    summarize_buckets,
)


def test_join_evidence_to_results_matches_slate_pitcher_and_side():
    evidence = [
        {
            "slate_date": "2026-05-12",
            "normalized_pitcher": "bryan woo",
            "side": "under",
            "provider": "boltodds",
        },
        {
            "slate_date": "2026-05-12",
            "normalized_pitcher": "logan gilbert",
            "side": "over",
            "provider": "boltodds",
        },
    ]
    history = [
        {
            "date": "2026-05-12",
            "normalized_pitcher": "bryan woo",
            "side": "under",
            "result": "win",
            "pnl": 0.91,
        }
    ]

    joined = join_evidence_to_results(evidence, history)

    assert joined[0]["result"] == "win"
    assert joined[0]["pnl"] == 0.91
    assert joined[1]["result"] is None


def test_summarize_buckets_groups_consensus_and_outcomes():
    rows = [
        {
            "provider": "boltodds",
            "checkpoint": "pre_30",
            "side": "over",
            "market_consensus": "toward_pick",
            "bet_value_consensus": "worse_now",
            "current_verdict": "FIRE 1u",
            "result": "win",
            "pnl": 0.91,
        },
        {
            "provider": "boltodds",
            "checkpoint": "pre_30",
            "side": "over",
            "market_consensus": "toward_pick",
            "bet_value_consensus": "worse_now",
            "current_verdict": "LEAN",
            "result": "loss",
            "pnl": -1.0,
        },
    ]

    summary = summarize_buckets(
        rows,
        ("provider", "checkpoint", "side", "market_consensus", "bet_value_consensus"),
    )

    bucket = summary[("boltodds", "pre_30", "over", "toward_pick", "worse_now")]
    assert bucket["rows"] == 2
    assert bucket["fire_rows"] == 1
    assert bucket["graded"] == 2
    assert bucket["wins"] == 1
    assert bucket["losses"] == 1
    assert bucket["pnl"] == -0.09
    assert bucket["roi"] == -0.045


def test_build_checkpoint_evidence_rows_rebuilds_pregame_market_state():
    picks = [
        {
            "slate_date": "2026-05-12",
            "pitcher": "Tarik Skubal",
            "normalized_pitcher": "tarik skubal",
            "side": "over",
            "current_verdict": "FIRE 2u",
            "k_line": 6.5,
            "game_time": "2026-05-12T22:00:00+00:00",
        }
    ]
    snapshots = [
        {
            "provider": "boltodds",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "side": "over",
            "line": 6.5,
            "american_odds": -105,
            "observed_at": "2026-05-12T20:00:00+00:00",
        },
        {
            "provider": "boltodds",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "side": "over",
            "line": 6.5,
            "american_odds": -125,
            "observed_at": "2026-05-12T21:25:00+00:00",
        },
        {
            "provider": "boltodds",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "betmgm",
            "side": "over",
            "line": 6.5,
            "american_odds": 100,
            "observed_at": "2026-05-12T20:10:00+00:00",
        },
        {
            "provider": "boltodds",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "betmgm",
            "side": "over",
            "line": 6.5,
            "american_odds": -115,
            "observed_at": "2026-05-12T21:20:00+00:00",
        },
        {
            "provider": "boltodds",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "side": "over",
            "line": 7.5,
            "american_odds": 130,
            "observed_at": "2026-05-12T21:45:00+00:00",
        },
    ]

    rows = build_checkpoint_evidence_rows(
        pick_rows=picks,
        snapshot_rows=snapshots,
        checkpoints_minutes=[30],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "boltodds"
    assert row["checkpoint"] == "pre_30"
    assert row["book_count"] == 2
    assert row["market_consensus"] == "toward_pick"
    assert row["bet_value_consensus"] == "worse_now"
    assert row["toward_pick_count"] == 2
    assert row["worse_now_count"] == 2
    assert row["broad_confirmation"] is True


def test_build_report_includes_shadow_sections():
    rows = [
        {
            "provider": "boltodds",
            "checkpoint": "latest_rollup",
            "side": "under",
            "market_consensus": "away_from_pick",
            "bet_value_consensus": "better_now",
            "current_verdict": "FIRE 1u",
            "result": "loss",
            "pnl": -1.0,
        }
    ]

    report = build_report(rows, title="Live Market Outcome Audit")

    assert "# Live Market Outcome Audit" in report
    assert "Shadow-only" in report
    assert "## Consensus Outcome Buckets" in report
    assert "## Side Buckets" in report
    assert "`boltodds`" in report
