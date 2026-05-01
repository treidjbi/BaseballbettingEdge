from market_infra.prop_snapshot import snapshots_from_propline_event


def test_snapshots_from_propline_event_keeps_target_books_only():
    event = {
        "id": "pl-event-1",
        "sport_key": "baseball_mlb",
        "commence_time": "2026-05-01T23:05:00Z",
        "home_team": "Boston Red Sox",
        "away_team": "New York Yankees",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [{
                    "key": "pitcher_strikeouts",
                    "outcomes": [
                        {"name": "Over", "description": "Gerrit Cole", "price": -120, "point": 7.5},
                        {"name": "Under", "description": "Gerrit Cole", "price": 100, "point": 7.5},
                    ],
                }],
            },
            {
                "key": "bovada",
                "title": "Bovada",
                "markets": [{
                    "key": "pitcher_strikeouts",
                    "outcomes": [
                        {"name": "Over", "description": "Gerrit Cole", "price": -118, "point": 7.5},
                    ],
                }],
            },
        ],
    }

    rows = snapshots_from_propline_event(event, observed_at="2026-05-01T18:00:00Z")

    assert len(rows) == 2
    assert {row["bookmaker_key"] for row in rows} == {"draftkings"}
    assert {row["side"] for row in rows} == {"over", "under"}
    assert rows[0]["provider"] == "propline"
    assert rows[0]["provider_event_id"] == "pl-event-1"
    assert rows[0]["market_key"] == "pitcher_strikeouts"
    assert rows[0]["normalized_player_name"] == "gerrit cole"
    assert rows[0]["dedupe_key"]


def test_snapshots_from_propline_event_dedupe_changes_with_price():
    base = {
        "id": "pl-event-1",
        "bookmakers": [{
            "key": "fanduel",
            "title": "FanDuel",
            "markets": [{
                "key": "pitcher_strikeouts",
                "outcomes": [
                    {"name": "Over", "description": "Gerrit Cole", "price": -120, "point": 7.5},
                ],
            }],
        }],
    }
    changed = {
        **base,
        "bookmakers": [{
            "key": "fanduel",
            "title": "FanDuel",
            "markets": [{
                "key": "pitcher_strikeouts",
                "outcomes": [
                    {"name": "Over", "description": "Gerrit Cole", "price": -130, "point": 7.5},
                ],
            }],
        }],
    }

    first = snapshots_from_propline_event(base, observed_at="2026-05-01T18:00:00Z")[0]
    second = snapshots_from_propline_event(changed, observed_at="2026-05-01T18:00:00Z")[0]

    assert first["dedupe_key"] != second["dedupe_key"]
