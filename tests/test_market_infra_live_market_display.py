from datetime import datetime, timezone

from market_infra.live_market_display import build_live_market_display_rows


def _pick(**overrides):
    row = {
        "slate_date": "2026-05-12",
        "pitcher": "Bryan Woo",
        "normalized_pitcher": "bryan woo",
        "side": "under",
        "current_verdict": "FIRE 2u",
        "k_line": 5.5,
        "game_time": "2026-05-12T23:00:00+00:00",
        "current_book": "FanDuel",
        "current_odds": 104,
    }
    row.update(overrides)
    return row


def _snapshot(book, odds, observed_at, line=5.5, side="under", player="Bryan Woo"):
    return {
        "id": f"{book}-{observed_at}",
        "provider": "boltodds",
        "player_name": player,
        "normalized_player_name": player.lower(),
        "bookmaker_key": book,
        "side": side,
        "line": line,
        "american_odds": odds,
        "observed_at": observed_at,
    }


def test_builds_consensus_and_best_actionable_for_fire_pick():
    snapshots = [
        _snapshot("fanduel", 104, "2026-05-12T20:00:00+00:00"),
        _snapshot("fanduel", -116, "2026-05-12T20:10:00+00:00"),
        _snapshot("betmgm", 100, "2026-05-12T20:00:00+00:00"),
        _snapshot("betmgm", 112, "2026-05-12T20:10:00+00:00"),
        _snapshot("caesars", 104, "2026-05-12T20:00:00+00:00"),
        _snapshot("caesars", -110, "2026-05-12T20:10:00+00:00"),
    ]

    rows = build_live_market_display_rows(
        slate_date="2026-05-12",
        live_picks=[_pick()],
        snapshot_rows=snapshots,
        provider="boltodds",
        observed_at=datetime(2026, 5, 12, 20, 10, 30, tzinfo=timezone.utc),
        source_artifact_path="https://example.test/today.json",
        source_artifact_sha256="sha",
    )

    assert rows[0]["market_consensus"] == "toward_pick"
    assert rows[0]["bet_value_consensus"] == "worse_now"
    assert rows[0]["market_status"] == "market_confirmed_worse_number"
    assert rows[0]["actionable_state"] == "playable_now"
    assert rows[0]["main_line"] == 5.5
    assert rows[0]["best_book"] == "betmgm"
    assert rows[0]["best_odds"] == 112
    assert rows[0]["broad_confirmation"] is True


def test_flags_off_market_book_without_turning_it_into_consensus():
    snapshots = [
        _snapshot("fanduel", -110, "2026-05-12T20:00:00+00:00"),
        _snapshot("fanduel", -112, "2026-05-12T20:10:00+00:00"),
        _snapshot("betmgm", -110, "2026-05-12T20:00:00+00:00"),
        _snapshot("betmgm", 118, "2026-05-12T20:10:00+00:00"),
        _snapshot("caesars", -110, "2026-05-12T20:00:00+00:00"),
        _snapshot("caesars", -108, "2026-05-12T20:10:00+00:00"),
    ]

    rows = build_live_market_display_rows(
        slate_date="2026-05-12",
        live_picks=[_pick()],
        snapshot_rows=snapshots,
        provider="boltodds",
        observed_at=datetime(2026, 5, 12, 20, 10, 30, tzinfo=timezone.utc),
        source_artifact_path="https://example.test/today.json",
        source_artifact_sha256="sha",
    )

    assert rows[0]["market_consensus"] == "none"
    assert rows[0]["best_book"] == "betmgm"
    assert rows[0]["best_is_off_market"] is True
    assert rows[0]["off_market_books"][0]["book"] == "betmgm"
    assert rows[0]["actionable_state"] == "off_market"


def test_stale_snapshots_block_actionable_state():
    rows = build_live_market_display_rows(
        slate_date="2026-05-12",
        live_picks=[_pick()],
        snapshot_rows=[
            _snapshot("fanduel", 120, "2026-05-12T19:00:00+00:00"),
            _snapshot("betmgm", 118, "2026-05-12T19:00:00+00:00"),
        ],
        provider="boltodds",
        observed_at=datetime(2026, 5, 12, 20, 10, 30, tzinfo=timezone.utc),
        source_artifact_path="https://example.test/today.json",
        source_artifact_sha256="sha",
        stale_after_seconds=900,
    )

    assert rows[0]["freshness_status"] == "stale"
    assert rows[0]["actionable_state"] == "stale"
    assert rows[0]["best_book"] is None
