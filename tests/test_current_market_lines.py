from datetime import datetime, timezone

from market_infra.current_market_lines import (
    build_opening_baseline_rows,
    build_current_market_lines,
    normalize_book_key,
    normalize_market_key,
)


NOW = datetime(2026, 5, 13, 19, 0, tzinfo=timezone.utc)


def _run(run_id="run-1", slate_date="2026-05-13", provider="boltodds"):
    return {
        "id": run_id,
        "slate_date": slate_date,
        "provider": provider,
    }


def _snapshot(
    snapshot_id,
    *,
    run_id="run-1",
    provider="boltodds",
    book="fanduel",
    book_name="FanDuel",
    player="Jose Berrios",
    market="pitcher_strikeouts",
    side="over",
    line=5.5,
    odds=-110,
    observed_at="2026-05-13T18:58:00+00:00",
):
    return {
        "id": snapshot_id,
        "run_id": run_id,
        "provider": provider,
        "provider_event_id": "event-1",
        "bookmaker_key": book,
        "bookmaker_title": book_name,
        "player_name": player,
        "market_key": market,
        "side": side,
        "line": line,
        "american_odds": odds,
        "observed_at": observed_at,
        "raw_payload": {"snapshot": snapshot_id},
    }


def test_normalize_book_key_accepts_common_book_shapes():
    assert normalize_book_key({"bookmaker_title": "FanDuel Sportsbook"}) == "fanduel"
    assert normalize_book_key({"book_name": "Draft Kings"}) == "draftkings"
    assert normalize_book_key({"book_key": "bet_rivers"}) == "betrivers"
    assert normalize_book_key("Caesars Sportsbook") == "caesars"


def test_normalize_market_key_accepts_boltodds_market_label():
    assert normalize_market_key("Pitcher Strikeouts") == "pitcher_strikeouts"
    assert normalize_market_key("player strikeouts") == "pitcher_strikeouts"


def test_complete_over_under_pair_builds_current_market_line():
    rows = build_current_market_lines(
        [
            _snapshot(1, side="over", odds=-115),
            _snapshot(2, side="under", odds=-105, observed_at="2026-05-13T18:59:00+00:00"),
        ],
        [_run()],
        NOW,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["slate_date"] == "2026-05-13"
    assert row["provider"] == "boltodds"
    assert row["book_key"] == "fanduel"
    assert row["book_name"] == "FanDuel"
    assert row["provider_event_id"] == "event-1"
    assert row["player_name"] == "Jose Berrios"
    assert row["normalized_player_name"] == "jose berrios"
    assert row["market_key"] == "pitcher_strikeouts"
    assert row["line"] == 5.5
    assert row["over_odds"] == -115
    assert row["under_odds"] == -105
    assert row["over_snapshot_id"] == 1
    assert row["under_snapshot_id"] == 2
    assert row["first_seen_at"] == "2026-05-13T18:58:00+00:00"
    assert row["last_seen_at"] == "2026-05-13T18:59:00+00:00"
    assert row["source_run_id"] == "run-1"
    assert row["is_complete"] is True
    assert row["freshness_seconds"] == 60
    assert row["quality_flags"] == []
    assert row["raw_payload"]["over"]["snapshot"] == 1
    assert row["raw_payload"]["under"]["snapshot"] == 2
    assert row["updated_at"] == "2026-05-13T19:00:00+00:00"


def test_real_boltodds_market_label_and_uuid_snapshot_ids_build_line():
    rows = build_current_market_lines(
        [
            _snapshot(
                "9dfe50e7-daf8-49f2-a771-37c231f2e143",
                side="over",
                market="Pitcher Strikeouts",
            ),
            _snapshot(
                "99fcdcd2-e4c9-46fa-adf4-a41042cc6343",
                side="under",
                market="Pitcher Strikeouts",
            ),
        ],
        [_run()],
        NOW,
    )

    assert len(rows) == 1
    assert rows[0]["market_key"] == "pitcher_strikeouts"
    assert rows[0]["over_snapshot_id"] == "9dfe50e7-daf8-49f2-a771-37c231f2e143"
    assert rows[0]["under_snapshot_id"] == "99fcdcd2-e4c9-46fa-adf4-a41042cc6343"


def test_single_sided_rows_are_incomplete():
    rows = build_current_market_lines(
        [_snapshot(1, side="over", odds=-125)],
        [_run()],
        NOW,
    )

    assert len(rows) == 1
    assert rows[0]["is_complete"] is False
    assert rows[0]["over_odds"] == -125
    assert rows[0]["under_odds"] is None
    assert rows[0]["quality_flags"] == ["missing_under"]


def test_stale_rows_are_flagged_by_latest_side_timestamp():
    rows = build_current_market_lines(
        [
            _snapshot(1, side="over", observed_at="2026-05-13T18:00:00+00:00"),
            _snapshot(2, side="under", observed_at="2026-05-13T18:10:00+00:00"),
        ],
        [_run()],
        NOW,
        stale_after_seconds=900,
    )

    assert rows[0]["freshness_seconds"] == 3000
    assert rows[0]["quality_flags"] == ["stale"]


def test_unsupported_book_is_ignored():
    rows = build_current_market_lines(
        [
            _snapshot(1, book="kalshi", book_name="Kalshi", side="over"),
            _snapshot(2, book="kalshi", book_name="Kalshi", side="under"),
        ],
        [_run()],
        NOW,
    )

    assert rows == []


def test_same_player_different_lines_remain_separate_rows():
    rows = build_current_market_lines(
        [
            _snapshot(1, side="over", line=5.5),
            _snapshot(2, side="under", line=5.5),
            _snapshot(3, side="over", line=6.5, odds=120),
            _snapshot(4, side="under", line=6.5, odds=-140),
        ],
        [_run()],
        NOW,
    )

    assert [row["line"] for row in rows] == [5.5, 6.5]
    assert [row["over_odds"] for row in rows] == [-110, 120]
    assert [row["quality_flags"] for row in rows] == [["line_conflict"], ["line_conflict"]]


def test_latest_side_snapshot_wins_without_overwriting_first_seen():
    rows = build_current_market_lines(
        [
            _snapshot(1, side="over", odds=-105, observed_at="2026-05-13T18:30:00+00:00"),
            _snapshot(2, side="over", odds=-125, observed_at="2026-05-13T18:58:00+00:00"),
            _snapshot(3, side="under", odds=105, observed_at="2026-05-13T18:40:00+00:00"),
            _snapshot(4, side="under", odds=115, observed_at="2026-05-13T18:59:00+00:00"),
        ],
        [_run()],
        NOW,
    )

    assert rows[0]["over_odds"] == -125
    assert rows[0]["under_odds"] == 115
    assert rows[0]["first_seen_at"] == "2026-05-13T18:30:00+00:00"
    assert rows[0]["last_seen_at"] == "2026-05-13T18:59:00+00:00"


def test_opening_baseline_rows_use_complete_first_seen_lines_only():
    current_rows = build_current_market_lines(
        [
            _snapshot(
                "9dfe50e7-daf8-49f2-a771-37c231f2e143",
                side="over",
                odds=-115,
                observed_at="2026-05-13T18:58:00+00:00",
            ),
            _snapshot(
                "99fcdcd2-e4c9-46fa-adf4-a41042cc6343",
                side="under",
                odds=-105,
                observed_at="2026-05-13T18:59:00+00:00",
            ),
            _snapshot(
                "ba880a1a-98cc-43ff-a389-f96a68ebfd67",
                book="draftkings",
                book_name="DraftKings",
                side="over",
            ),
        ],
        [_run()],
        NOW,
    )

    baseline_rows = build_opening_baseline_rows(current_rows)

    assert baseline_rows == [{
        "slate_date": "2026-05-13",
        "normalized_player_name": "jose berrios",
        "player_name": "Jose Berrios",
        "market_key": "pitcher_strikeouts",
        "book_key": "fanduel",
        "book_name": "FanDuel",
        "line": 5.5,
        "opening_over_odds": -115,
        "opening_under_odds": -105,
        "opening_provider": "boltodds",
        "opening_source": "provider_first_seen",
        "first_seen_at": "2026-05-13T18:58:00+00:00",
        "source_line_id": "9dfe50e7-daf8-49f2-a771-37c231f2e143",
    }]
