import pytest

from market_infra.market_snapshot_compaction import compact_snapshot_rows


def _same_time_row(snapshot_id, odds):
    return {
        "slate_date": "2026-05-17",
        "provider": "boltodds",
        "bookmaker_key": "fanduel",
        "player_name": "Example Pitcher",
        "normalized_player_name": "example pitcher",
        "market_key": "pitcher_strikeouts",
        "side": "over",
        "line": 5.5,
        "american_odds": odds,
        "observed_at": "2026-05-17T18:00:00Z",
        "id": snapshot_id,
    }


def test_compaction_tie_breaks_equal_timestamps_by_source_id():
    compact = compact_snapshot_rows([
        _same_time_row("b", -120),
        _same_time_row("c", -130),
        _same_time_row("a", -110),
    ])[0]

    assert compact["first_odds"] == -110
    assert compact["last_odds"] == -130
    assert compact["odds_move_count"] == 2
    assert compact["source_snapshot_ids"] == ["a", "b", "c"]


def test_compaction_collapses_identical_duplicate_source_ids():
    first = _same_time_row("a", -110)

    compact = compact_snapshot_rows([first, dict(first), _same_time_row("b", -120)])[0]

    assert compact["snapshot_count"] == 2
    assert compact["source_snapshot_ids"] == ["a", "b"]


def test_compaction_rejects_conflicting_duplicate_source_ids():
    first = _same_time_row("a", -110)
    conflict = {**first, "american_odds": -125}

    with pytest.raises(ValueError, match="conflicting duplicate snapshot id: a"):
        compact_snapshot_rows([first, conflict])


def test_compaction_rejects_missing_source_id():
    row = _same_time_row("a", -110)
    row.pop("id")

    with pytest.raises(ValueError, match="snapshot id is required"):
        compact_snapshot_rows([row])


def test_compacts_raw_snapshots_without_losing_movement_path():
    rows = compact_snapshot_rows([
        {
            "slate_date": "2026-05-13",
            "provider": "boltodds",
            "bookmaker_key": "fanduel",
            "player_name": "Example Pitcher",
            "normalized_player_name": "example pitcher",
            "market_key": "pitcher_strikeouts",
            "side": "over",
            "line": 5.5,
            "american_odds": -110,
            "observed_at": "2026-05-13T18:00:00Z",
            "id": 1,
        },
        {
            "slate_date": "2026-05-13",
            "provider": "boltodds",
            "bookmaker_key": "fanduel",
            "player_name": "Example Pitcher",
            "normalized_player_name": "example pitcher",
            "market_key": "pitcher_strikeouts",
            "side": "over",
            "line": 5.5,
            "american_odds": -125,
            "observed_at": "2026-05-13T18:05:00Z",
            "id": 2,
        },
    ])

    assert rows == [{
        "slate_date": "2026-05-13",
        "provider": "boltodds",
        "book_key": "fanduel",
        "normalized_player_name": "example pitcher",
        "player_name": "Example Pitcher",
        "market_key": "pitcher_strikeouts",
        "side": "over",
        "line": 5.5,
        "first_seen_at": "2026-05-13T18:00:00+00:00",
        "last_seen_at": "2026-05-13T18:05:00+00:00",
        "first_odds": -110,
        "last_odds": -125,
        "min_odds": -125,
        "max_odds": -110,
        "odds_move_count": 1,
        "snapshot_count": 2,
        "source_snapshot_ids": [1, 2],
    }]


def test_compaction_separates_lines_sides_and_books():
    rows = compact_snapshot_rows([
        {
            "slate_date": "2026-05-13",
            "provider": "propline",
            "bookmaker_key": "draftkings",
            "player_name": "Example Pitcher",
            "side": "over",
            "line": 4.5,
            "american_odds": -110,
            "observed_at": "2026-05-13T18:00:00Z",
            "id": "a",
        },
        {
            "slate_date": "2026-05-13",
            "provider": "propline",
            "bookmaker_key": "draftkings",
            "player_name": "Example Pitcher",
            "side": "under",
            "line": 4.5,
            "american_odds": -110,
            "observed_at": "2026-05-13T18:00:00Z",
            "id": "b",
        },
        {
            "slate_date": "2026-05-13",
            "provider": "propline",
            "bookmaker_key": "draftkings",
            "player_name": "Example Pitcher",
            "side": "over",
            "line": 5.5,
            "american_odds": 120,
            "observed_at": "2026-05-13T18:01:00Z",
            "id": "c",
        },
    ])

    keys = {(row["side"], row["line"]) for row in rows}
    assert keys == {("over", 4.5), ("under", 4.5), ("over", 5.5)}
