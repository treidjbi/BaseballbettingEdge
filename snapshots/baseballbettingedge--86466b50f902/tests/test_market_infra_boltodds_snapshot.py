from market_infra.boltodds_snapshot import (
    BOLTODDS_DEFAULT_TARGET_BOOKS,
    snapshots_from_boltodds_message,
)


OBSERVED_AT = "2026-05-07T20:15:31+00:00"


def _message(action="line_update"):
    return {
        "timestamp": "2026-05-07T20:15:30+00:00",
        "action": action,
        "data": {
            "sport": "MLB",
            "sportsbook": "fanduel",
            "game": "New York Yankees vs Boston Red Sox, 2026-05-07, 07",
            "home_team": "Boston Red Sox",
            "away_team": "New York Yankees",
            "info": {
                "id": 12345,
                "game": "New York Yankees vs Boston Red Sox, 2026-05-07, 07",
                "when": "2026-05-07, 07:10 PM",
                "link": "https://example.test/event/12345",
            },
            "outcomes": {
                "Gerrit Cole Over 6.5 Strikeouts": {
                    "odds": "-118",
                    "link": "https://example.test/betslip",
                    "outcome_name": "Pitcher Strikeouts",
                    "outcome_line": "6.5",
                    "outcome_over_under": "Over",
                    "outcome_target": "Gerrit Cole",
                },
                "Gerrit Cole Under 6.5 Strikeouts": {
                    "odds": "+102",
                    "link": "https://example.test/betslip",
                    "outcome_name": "Pitcher Strikeouts",
                    "outcome_line": "6.5",
                    "outcome_over_under": "Under",
                    "outcome_target": "Gerrit Cole",
                },
            },
        },
    }


def _snapshots(message, **kwargs):
    return snapshots_from_boltodds_message(
        message,
        observed_at=kwargs.get("observed_at", OBSERVED_AT),
        allowed_markets=kwargs.get("allowed_markets", {"pitcher strikeouts"}),
        target_books=kwargs.get("target_books", {"fanduel": "FanDuel"}),
    )


def test_default_target_books_include_current_preference_order():
    assert list(BOLTODDS_DEFAULT_TARGET_BOOKS) == [
        "fanduel",
        "draftkings",
        "betmgm",
        "betrivers",
        "scorebet",
        "caesars",
    ]


def test_default_target_books_exclude_kalshi_from_active_capture():
    message = _message()
    message["data"]["sportsbook"] = "kalshi"

    rows = snapshots_from_boltodds_message(
        message,
        observed_at=OBSERVED_AT,
        allowed_markets={"pitcher strikeouts"},
    )

    assert rows == []


def test_snapshots_from_boltodds_line_update_normalizes_pitcher_strikeouts():
    rows = _snapshots(_message())

    assert len(rows) == 2
    assert rows[0]["provider"] == "boltodds"
    assert rows[0]["provider_event_id"] == "12345"
    assert rows[0]["sport_key"] == "MLB"
    assert rows[0]["market_key"] == "Pitcher Strikeouts"
    assert rows[0]["bookmaker_key"] == "fanduel"
    assert rows[0]["bookmaker_title"] == "FanDuel"
    assert rows[0]["player_name"] == "Gerrit Cole"
    assert rows[0]["normalized_player_name"] == "gerrit cole"
    assert rows[0]["side"] == "over"
    assert rows[0]["line"] == 6.5
    assert rows[0]["american_odds"] == -118
    assert rows[0]["observed_at"] == OBSERVED_AT
    assert rows[0]["book_updated_at"] == "2026-05-07T20:15:30+00:00"
    assert rows[0]["source_payload"]["action"] == "line_update"
    assert rows[0]["source_payload"]["outcome_label"] == "Gerrit Cole Over 6.5 Strikeouts"
    assert rows[0]["source_payload"]["outcome"]["odds"] == "-118"
    assert rows[0]["dedupe_key"]

    assert rows[1]["side"] == "under"
    assert rows[1]["american_odds"] == 102


def test_snapshots_from_boltodds_accepts_integer_odds_values():
    message = _message()
    message["data"]["outcomes"] = {
        "Gerrit Cole Over 6.5 Strikeouts": {
            "odds": -118,
            "outcome_name": "Pitcher Strikeouts",
            "outcome_line": "6.5",
            "outcome_over_under": "Over",
            "outcome_target": "Gerrit Cole",
        },
        "Gerrit Cole Under 6.5 Strikeouts": {
            "odds": "+102",
            "outcome_name": "Pitcher Strikeouts",
            "outcome_line": "6.5",
            "outcome_over_under": "Under",
            "outcome_target": "Gerrit Cole",
        },
    }

    rows = _snapshots(message)

    assert [row["american_odds"] for row in rows] == [-118, 102]


def test_snapshots_from_boltodds_accepts_plus_minus_100_odds():
    message = _message()
    message["data"]["outcomes"] = {
        "Gerrit Cole Over 6.5 Strikeouts": {
            "odds": 100,
            "outcome_name": "Pitcher Strikeouts",
            "outcome_line": "6.5",
            "outcome_over_under": "Over",
            "outcome_target": "Gerrit Cole",
        },
        "Gerrit Cole Under 6.5 Strikeouts": {
            "odds": "-100",
            "outcome_name": "Pitcher Strikeouts",
            "outcome_line": "6.5",
            "outcome_over_under": "Under",
            "outcome_target": "Gerrit Cole",
        },
    }

    rows = _snapshots(message)

    assert [row["american_odds"] for row in rows] == [100, -100]


def test_snapshots_from_boltodds_accepts_game_id_when_book_omits_info_id():
    message = _message()
    message["data"]["info"].pop("id")
    message["data"]["info"]["game_id"] = "35577687"
    message["data"]["info"]["universal_id"] = "6be5cfd183a3"

    rows = _snapshots(message)

    assert len(rows) == 2
    assert {row["provider_event_id"] for row in rows} == {"35577687"}


def test_snapshots_from_boltodds_handles_initial_state_and_game_update():
    initial_rows = _snapshots(_message(action="initial_state"))
    game_rows = _snapshots(_message(action="game_update"))

    assert len(initial_rows) == 2
    assert len(game_rows) == 2


def test_snapshots_from_boltodds_ignores_wrong_action_book_and_market():
    assert _snapshots(_message(action="ping")) == []

    wrong_book = _message()
    wrong_book["data"]["sportsbook"] = "bovada"
    assert _snapshots(wrong_book) == []

    wrong_market = _message()
    wrong_market["data"]["outcomes"]["Gerrit Cole Over 6.5 Strikeouts"][
        "outcome_name"
    ] = "Pitcher Outs"
    wrong_market["data"]["outcomes"]["Gerrit Cole Under 6.5 Strikeouts"][
        "outcome_name"
    ] = "Pitcher Outs"
    assert _snapshots(wrong_market) == []


def test_snapshots_from_boltodds_filters_to_allowed_player_names():
    message = _message()
    message["data"]["outcomes"]["Riley Greene Over 1.5 Strikeouts"] = {
        "odds": "+155",
        "outcome_name": "Strikeouts",
        "outcome_line": "1.5",
        "outcome_over_under": "Over",
        "outcome_target": "Riley Greene",
    }

    rows = snapshots_from_boltodds_message(
        message,
        observed_at=OBSERVED_AT,
        allowed_markets={"pitcher strikeouts", "strikeouts"},
        target_books={"fanduel": "FanDuel"},
        allowed_player_names={"gerrit cole"},
    )

    assert {row["normalized_player_name"] for row in rows} == {"gerrit cole"}


def test_snapshots_from_boltodds_ignores_malformed_required_fields():
    for field, value in [
        ("outcome_over_under", "Both"),
        ("outcome_line", "six and a half"),
        ("odds", "evenish"),
        ("outcome_target", ""),
    ]:
        message = _message()
        message["data"]["outcomes"] = {
            "bad": {
                "odds": "-118",
                "outcome_name": "Pitcher Strikeouts",
                "outcome_line": "6.5",
                "outcome_over_under": "Over",
                "outcome_target": "Gerrit Cole",
                field: value,
            }
        }

        assert _snapshots(message) == []

    missing_event = _message()
    missing_event["data"]["info"]["id"] = ""
    missing_event["data"]["game"] = ""
    assert _snapshots(missing_event) == []


def test_snapshots_from_boltodds_ignores_malformed_envelopes():
    for malformed_data in ["not-a-dict", ["not", "a", "dict"], 123]:
        message = _message()
        message["data"] = malformed_data

        assert _snapshots(message) == []

    for malformed_info in ["not-a-dict", ["not", "a", "dict"], 123]:
        message = _message()
        message["data"]["info"] = malformed_info

        assert _snapshots(message) == []

    assert _snapshots("not-a-dict") == []

    message = _message()
    message["data"]["outcomes"] = {"bad": "not-a-dict"}
    assert _snapshots(message) == []


def test_snapshots_from_boltodds_ignores_non_scalar_event_ids():
    for event_id in [{"id": 12345}, ["12345"]]:
        message = _message()
        message["data"]["info"]["id"] = event_id

        assert _snapshots(message) == []


def test_snapshots_from_boltodds_ignores_non_string_player_names():
    for player_name in [{"name": "Gerrit Cole"}, ["Gerrit Cole"]]:
        message = _message()
        message["data"]["outcomes"] = {
            "bad": {
                "odds": "-118",
                "outcome_name": "Pitcher Strikeouts",
                "outcome_line": "6.5",
                "outcome_over_under": "Over",
                "outcome_target": player_name,
            }
        }

        assert _snapshots(message) == []


def test_snapshots_from_boltodds_ignores_non_finite_lines():
    for line_value in ["NaN", "Infinity", "-Infinity"]:
        message = _message()
        message["data"]["outcomes"] = {
            "bad": {
                "odds": "-118",
                "outcome_name": "Pitcher Strikeouts",
                "outcome_line": line_value,
                "outcome_over_under": "Over",
                "outcome_target": "Gerrit Cole",
            }
        }

        assert _snapshots(message) == []


def test_snapshots_from_boltodds_ignores_bool_lines():
    for line_value in [True, False]:
        message = _message()
        message["data"]["outcomes"] = {
            "bad": {
                "odds": "-118",
                "outcome_name": "Pitcher Strikeouts",
                "outcome_line": line_value,
                "outcome_over_under": "Over",
                "outcome_target": "Gerrit Cole",
            }
        }

        assert _snapshots(message) == []


def test_snapshots_from_boltodds_ignores_non_finite_odds():
    for odds_value in ["NaN", "Infinity", "-Infinity"]:
        message = _message()
        message["data"]["outcomes"] = {
            "bad": {
                "odds": odds_value,
                "outcome_name": "Pitcher Strikeouts",
                "outcome_line": "6.5",
                "outcome_over_under": "Over",
                "outcome_target": "Gerrit Cole",
            }
        }

        assert _snapshots(message) == []


def test_snapshots_from_boltodds_ignores_decimal_and_zero_odds():
    for odds_value in ["1.91", "99.9", "-118.8", "0", 99, "-99", "50", -50]:
        message = _message()
        message["data"]["outcomes"] = {
            "bad": {
                "odds": odds_value,
                "outcome_name": "Pitcher Strikeouts",
                "outcome_line": "6.5",
                "outcome_over_under": "Over",
                "outcome_target": "Gerrit Cole",
            }
        }

        assert _snapshots(message) == []


def test_snapshots_from_boltodds_dedupe_changes_with_price_line_and_observed_at():
    base = _snapshots(_message())[0]

    price_message = _message()
    price_message["data"]["outcomes"]["Gerrit Cole Over 6.5 Strikeouts"]["odds"] = "-125"
    price_changed = _snapshots(price_message)[0]

    line_message = _message()
    line_message["data"]["outcomes"]["Gerrit Cole Over 6.5 Strikeouts"][
        "outcome_line"
    ] = "7.5"
    line_changed = _snapshots(line_message)[0]

    observed_changed = _snapshots(
        _message(),
        observed_at="2026-05-07T20:16:31+00:00",
    )[0]

    assert base["dedupe_key"] != price_changed["dedupe_key"]
    assert base["dedupe_key"] != line_changed["dedupe_key"]
    assert base["dedupe_key"] != observed_changed["dedupe_key"]
