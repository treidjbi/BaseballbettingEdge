from market_infra.market_evidence import build_market_pick_evidence_rows


def _heartbeat(**overrides):
    row = {
        "provider": "boltodds",
        "slate_date": "2026-05-08",
        "observed_at": "2026-05-08T18:10:20+00:00",
        "last_message_at": "2026-05-08T18:10:15+00:00",
        "books_seen": ["fanduel", "betmgm"],
        "metadata": {"event": "flush", "target_books": ["fanduel", "betmgm"]},
    }
    row.update(overrides)
    return row


def test_under_line_drop_tracks_market_confirmation_but_worse_available_value():
    rows = build_market_pick_evidence_rows(
        slate_date="2026-05-08",
        live_picks=[{
            "pitcher": "Kyle Bradish",
            "normalized_pitcher": "kyle bradish",
            "side": "under",
            "current_verdict": "FIRE 1u",
            "k_line": 5.5,
            "game_time": "2026-05-08T18:00:00+00:00",
            "game_state": "scheduled",
            "is_fire": True,
        }],
        snapshot_rows=[
            {
                "id": "snapshot-old",
                "provider": "propline",
                "normalized_player_name": "kyle bradish",
                "player_name": "Kyle Bradish",
                "bookmaker_key": "betrivers",
                "side": "under",
                "line": 5.5,
                "american_odds": -118,
                "observed_at": "2026-05-08T17:30:00+00:00",
            },
            {
                "id": "snapshot-new",
                "provider": "propline",
                "normalized_player_name": "kyle bradish",
                "player_name": "Kyle Bradish",
                "bookmaker_key": "betrivers",
                "side": "under",
                "line": 4.5,
                "american_odds": 175,
                "observed_at": "2026-05-08T17:55:00+00:00",
            },
        ],
        observed_at="2026-05-08T17:55:00+00:00",
        source_artifact_path="https://raw.example/today.json",
        source_artifact_sha256="abc",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "propline"
    assert row["market_consensus"] == "toward_pick"
    assert row["bet_value_consensus"] == "worse_now"
    assert row["toward_pick_count"] == 1
    assert row["worse_now_count"] == 1
    assert row["touching_pick_line_count"] == 1
    assert row["time_window"] == "pre_5"
    assert row["dedupe_key"] == "2026-05-08:market_evidence:propline:kyle bradish:under"
    assert row["metadata"]["book_summaries"]["betrivers"]["market_direction"] == "toward_pick"
    assert row["metadata"]["book_summaries"]["betrivers"]["bet_value_direction"] == "worse_now"


def test_provider_rollup_marks_mixed_book_evidence():
    rows = build_market_pick_evidence_rows(
        slate_date="2026-05-08",
        live_picks=[{
            "pitcher": "Tarik Skubal",
            "normalized_pitcher": "tarik skubal",
            "side": "over",
            "current_verdict": "FIRE 2u",
            "k_line": 6.5,
            "game_time": "2026-05-08T20:00:00+00:00",
            "game_state": "scheduled",
            "is_fire": True,
        }],
        snapshot_rows=[
            {
                "id": "fd-old",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-08T18:00:00+00:00",
            },
            {
                "id": "fd-new",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 5.5,
                "american_odds": -115,
                "observed_at": "2026-05-08T18:10:00+00:00",
            },
            {
                "id": "mgm-old",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "bookmaker_key": "betmgm",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-08T18:00:00+00:00",
            },
            {
                "id": "mgm-new",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "bookmaker_key": "betmgm",
                "side": "over",
                "line": 7.5,
                "american_odds": 120,
                "observed_at": "2026-05-08T18:10:00+00:00",
            },
        ],
        observed_at="2026-05-08T18:10:00+00:00",
        source_artifact_path="https://raw.example/today.json",
        source_artifact_sha256="abc",
        providers={"boltodds"},
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "boltodds"
    assert row["book_count"] == 2
    assert row["market_consensus"] == "mixed"
    assert row["bet_value_consensus"] == "mixed"
    assert row["toward_pick_count"] == 1
    assert row["away_from_pick_count"] == 1
    assert row["better_now_count"] == 1
    assert row["worse_now_count"] == 1
    assert row["time_window"] == "pre_120"


def test_book_reversal_count_tracks_churn_before_current_state():
    rows = build_market_pick_evidence_rows(
        slate_date="2026-05-08",
        live_picks=[{
            "pitcher": "Kyle Bradish",
            "normalized_pitcher": "kyle bradish",
            "side": "under",
            "current_verdict": "FIRE 1u",
            "k_line": 5.5,
            "game_time": "2026-05-08T19:00:00+00:00",
            "game_state": "scheduled",
            "is_fire": True,
        }],
        snapshot_rows=[
            {
                "id": "one",
                "provider": "boltodds",
                "normalized_player_name": "kyle bradish",
                "bookmaker_key": "betrivers",
                "side": "under",
                "line": 5.5,
                "american_odds": -110,
                "observed_at": "2026-05-08T17:00:00+00:00",
            },
            {
                "id": "two",
                "provider": "boltodds",
                "normalized_player_name": "kyle bradish",
                "bookmaker_key": "betrivers",
                "side": "under",
                "line": 4.5,
                "american_odds": 170,
                "observed_at": "2026-05-08T17:05:00+00:00",
            },
            {
                "id": "three",
                "provider": "boltodds",
                "normalized_player_name": "kyle bradish",
                "bookmaker_key": "betrivers",
                "side": "under",
                "line": 5.5,
                "american_odds": -115,
                "observed_at": "2026-05-08T17:10:00+00:00",
            },
        ],
        observed_at="2026-05-08T17:10:00+00:00",
        source_artifact_path="https://raw.example/today.json",
        source_artifact_sha256="abc",
        providers={"boltodds"},
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["reversal_book_count"] == 1
    assert row["volatile_book_count"] == 1
    assert row["metadata"]["book_summaries"]["betrivers"]["reversal_count"] == 1


def test_fresh_boltodds_heartbeat_marks_unchanged_stale_evidence_fresh():
    rows = build_market_pick_evidence_rows(
        slate_date="2026-05-08",
        live_picks=[{
            "pitcher": "Tarik Skubal",
            "normalized_pitcher": "tarik skubal",
            "side": "over",
            "current_verdict": "FIRE 2u",
            "k_line": 6.5,
            "game_time": "2026-05-08T20:00:00+00:00",
            "game_state": "scheduled",
            "is_fire": True,
        }],
        snapshot_rows=[
            {
                "id": "fd-old",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-08T17:00:00+00:00",
            },
            {
                "id": "mgm-old",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "bookmaker_key": "betmgm",
                "side": "over",
                "line": 6.5,
                "american_odds": -105,
                "observed_at": "2026-05-08T17:00:00+00:00",
            },
        ],
        observed_at="2026-05-08T18:10:30+00:00",
        source_artifact_path="https://raw.example/today.json",
        source_artifact_sha256="abc",
        stale_after_seconds=900,
        provider_heartbeats=[_heartbeat()],
        providers={"boltodds"},
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "boltodds"
    assert row["metadata"]["freshness_status"] == "fresh"
    assert row["metadata"]["freshness_seconds"] == 15
    assert row["metadata"]["line_freshness_seconds"] == 4230
    assert row["metadata"]["heartbeat_hold"] is True
    assert row["metadata"]["book_summaries"]["fanduel"]["heartbeat_hold"] is True
    assert row["metadata"]["book_summaries"]["betmgm"]["heartbeat_hold"] is True


def test_active_default_tracks_therundown_and_skips_retired_boltodds():
    rows = build_market_pick_evidence_rows(
        slate_date="2026-06-17",
        live_picks=[{
            "pitcher": "Tarik Skubal",
            "normalized_pitcher": "tarik skubal",
            "side": "over",
            "current_verdict": "FIRE 1u",
            "k_line": 6.5,
            "game_time": "2026-06-17T20:00:00+00:00",
            "game_state": "scheduled",
            "is_fire": True,
        }],
        snapshot_rows=[
            {
                "id": "tr-old",
                "provider": "therundown",
                "normalized_player_name": "tarik skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -115,
                "observed_at": "2026-06-17T18:00:00+00:00",
            },
            {
                "id": "tr-new",
                "provider": "therundown",
                "normalized_player_name": "tarik skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -130,
                "observed_at": "2026-06-17T18:10:00+00:00",
            },
            {
                "id": "bolt-old",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "bookmaker_key": "betmgm",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-06-17T18:00:00+00:00",
            },
            {
                "id": "bolt-new",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "bookmaker_key": "betmgm",
                "side": "over",
                "line": 7.5,
                "american_odds": 120,
                "observed_at": "2026-06-17T18:10:00+00:00",
            },
        ],
        observed_at="2026-06-17T18:10:00+00:00",
        source_artifact_path="https://example.test/.netlify/functions/get-artifact?type=today",
        source_artifact_sha256="abc",
    )

    assert {row["provider"] for row in rows} == {"therundown"}
    assert rows[0]["dedupe_key"] == "2026-06-17:market_evidence:therundown:tarik skubal:over"
