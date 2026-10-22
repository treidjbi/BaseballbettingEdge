from unittest.mock import Mock, patch

from market_infra.boltodds_client import (
    BOLTODDS_DEFAULT_BOOKS,
    BOLTODDS_DEFAULT_MARKET_ALIASES,
    BOLTODDS_REST_BASE,
    build_subscribe_message,
    get_json,
    market_aliases_from_env,
    select_pitcher_strikeout_markets,
    target_books_from_env,
)


def test_target_books_from_env_defaults_to_current_preference_order(monkeypatch):
    monkeypatch.delenv("BOLTODDS_TARGET_BOOKS", raising=False)

    result = target_books_from_env()

    assert result == BOLTODDS_DEFAULT_BOOKS
    assert result is not BOLTODDS_DEFAULT_BOOKS
    assert list(result) == [
        "fanduel",
        "betmgm",
        "betrivers",
        "caesars",
    ]


def test_target_books_from_env_parses_known_unknown_and_blank_keys(monkeypatch):
    monkeypatch.setenv(
        "BOLTODDS_TARGET_BOOKS",
        " FanDuel, , new_book,DRAFTKINGS,Kalshi,espn-bet ",
    )

    assert target_books_from_env() == {
        "fanduel": "FanDuel",
        "new_book": "New Book",
        "draftkings": "DraftKings",
        "kalshi": "Kalshi",
        "espn-bet": "Espn Bet",
    }


def test_market_aliases_from_env_defaults_and_parses_custom_aliases(monkeypatch):
    monkeypatch.delenv("BOLTODDS_MARKET_ALIASES", raising=False)
    default_result = market_aliases_from_env()

    assert default_result == BOLTODDS_DEFAULT_MARKET_ALIASES
    assert default_result is not BOLTODDS_DEFAULT_MARKET_ALIASES

    monkeypatch.setenv(
        "BOLTODDS_MARKET_ALIASES",
        " Pitcher Ks, , Pitcher Strikeouts O/U ",
    )

    assert market_aliases_from_env() == ["Pitcher Ks", "Pitcher Strikeouts O/U"]


def test_build_subscribe_message_uses_supplied_filters():
    assert build_subscribe_message(
        sports=["MLB"],
        sportsbooks=["fanduel", "draftkings"],
        markets=["Pitcher Strikeouts"],
    ) == {
        "action": "subscribe",
        "filters": {
            "sports": ["MLB"],
            "sportsbooks": ["fanduel", "draftkings"],
            "markets": ["Pitcher Strikeouts"],
        },
    }


def test_select_pitcher_strikeout_markets_chooses_one_exact_alias_by_priority():
    payload = {
        "fanduel": {
            "MLB": [
                "Strikeouts",
                "Pitcher Outs",
                "Pitcher Strikeouts O/U",
            ]
        },
        "draftkings": {
            "MLB": [
                "pitcher strikeouts",
                "Player Hits",
            ]
        },
    }

    assert select_pitcher_strikeout_markets(
        payload,
        ["Pitcher Strikeouts", "Strikeouts", "Pitcher Strikeouts O/U"],
    ) == ["pitcher strikeouts"]


def test_select_pitcher_strikeout_markets_chooses_one_deterministic_fallback():
    payload = {
        "fanduel": {
            "MLB": [
                "Away Pitcher Strikeout Total",
                "Pitcher Outs",
                "Batter Strikeouts",
            ]
        },
        "draftkings": {"MLB": ["Home pitcher strikeouts alt line"]},
    }

    assert select_pitcher_strikeout_markets(payload, ["Exact Missing"]) == [
        "Away Pitcher Strikeout Total",
    ]


def test_select_pitcher_strikeout_markets_ignores_non_mlb_markets_by_default():
    payload = {
        "fanduel": {
            "NHL": ["Pitcher Strikeouts"],
            "NFL": ["Pitcher Strikeouts O/U"],
        },
        "draftkings": {"NBA": ["Pitcher Strikeout Total"]},
    }

    assert select_pitcher_strikeout_markets(payload, ["Pitcher Strikeouts"]) == []


def test_select_pitcher_strikeout_markets_ignores_malformed_payload_shapes():
    payload = {
        "fanduel": ["not", "a", "sport-map"],
        "draftkings": {
            "MLB": "Pitcher Strikeouts",
            "NHL": ["Player Shots"],
            "MLB_ALT": ["Pitcher Strikeouts", None, {"market": "Pitcher Ks"}],
        },
        "betmgm": {"MLB": ["Pitcher Strikeouts"]},
    }

    assert select_pitcher_strikeout_markets(
        payload,
        ["Pitcher Strikeouts"],
    ) == ["Pitcher Strikeouts"]
    assert select_pitcher_strikeout_markets("not-a-dict", ["Pitcher Strikeouts"]) == []


def test_get_json_adds_key_param_and_raises_for_status():
    response = Mock()
    response.json.return_value = {"ok": True}
    response.raise_for_status.return_value = None

    with patch("market_infra.boltodds_client.requests.get", return_value=response) as get:
        result = get_json("/markets", "secret-key", params={"sport": "MLB", "key": "old"})

    get.assert_called_once_with(
        f"{BOLTODDS_REST_BASE}/markets",
        params={"sport": "MLB", "key": "secret-key"},
        timeout=20,
    )
    response.raise_for_status.assert_called_once_with()
    assert result == {"ok": True}
