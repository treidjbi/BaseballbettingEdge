from market_infra.therundown_snapshot import snapshots_from_therundown_events


def _event():
    return {
        "event_id": "tr-evt-1",
        "event_date": "2026-06-12T23:05:00Z",
        "sport_id": 3,
        "teams": [
            {"name": "Away", "is_away": True},
            {"name": "Home", "is_home": True},
        ],
        "markets": [
            {
                "market_id": 19,
                "participants": [
                    {
                        "id": "p-1",
                        "name": "Gerrit Cole",
                        "lines": [
                            {
                                "value": "Over 7.5",
                                "prices": {
                                    "23": {
                                        "price": -115,
                                        "is_main_line": True,
                                        "updated_at": "2026-06-12T15:02:00Z",
                                    },
                                    "2": {
                                        "price": -120,
                                        "is_main_line": True,
                                    },
                                },
                            },
                            {
                                "value": "Under 7.5",
                                "prices": {
                                    "23": {
                                        "price": -105,
                                        "is_main_line": True,
                                        "updated_at": "2026-06-12T15:02:00Z",
                                    },
                                    "2": {
                                        "price": 100,
                                        "is_main_line": True,
                                    },
                                },
                            },
                            {
                                "value": "Over 8.5",
                                "prices": {
                                    "23": {
                                        "price": 135,
                                        "is_main_line": False,
                                    },
                                },
                            },
                            {
                                "value": "Under 8.5",
                                "prices": {
                                    "23": {
                                        "price": -160,
                                        "is_main_line": False,
                                    },
                                },
                            },
                        ],
                    }
                ],
            }
        ],
    }


def test_snapshots_from_therundown_events_keep_only_target_mainline_prices():
    rows = snapshots_from_therundown_events([_event()], observed_at="2026-06-12T15:03:00+00:00")

    assert len(rows) == 2
    assert {row["side"] for row in rows} == {"over", "under"}
    assert {row["line"] for row in rows} == {7.5}
    assert {row["american_odds"] for row in rows} == {-115, -105}
    assert {row["bookmaker_key"] for row in rows} == {"fanduel"}
    assert rows[0]["provider"] == "therundown"
    assert rows[0]["market_key"] == "pitcher_strikeouts"
    assert rows[0]["provider_event_id"] == "tr-evt-1"
    assert rows[0]["player_name"] == "Gerrit Cole"
    assert rows[0]["normalized_player_name"] == "gerrit cole"
    assert rows[0]["game_time"] == "2026-06-12T23:05:00Z"
    assert rows[0]["book_updated_at"] == "2026-06-12T15:02:00Z"
    assert rows[0]["source_payload"]["affiliate_id"] == "23"


def test_snapshots_from_therundown_events_can_include_non_mainline_when_explicit():
    rows = snapshots_from_therundown_events(
        [_event()],
        observed_at="2026-06-12T15:03:00+00:00",
        mainline_only=False,
    )

    assert {row["line"] for row in rows} == {7.5, 8.5}
    assert len(rows) == 4
