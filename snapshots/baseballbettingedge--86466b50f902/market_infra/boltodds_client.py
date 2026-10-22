from __future__ import annotations

import os
from typing import Any

import requests


BOLTODDS_REST_BASE = "https://spro.agency/api"
BOLTODDS_WS_URL = "wss://spro.agency/api"
BOLTODDS_DEFAULT_BOOKS = {
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "betrivers": "BetRivers",
    "caesars": "Caesars",
}
BOLTODDS_KNOWN_BOOK_TITLES = {
    **BOLTODDS_DEFAULT_BOOKS,
    "draftkings": "DraftKings",
    "kalshi": "Kalshi",
    "scorebet": "theScore Bet",
}
BOLTODDS_DEFAULT_MARKET_ALIASES = [
    "Pitcher Strikeouts",
    "Strikeouts",
    "Pitcher Strikeouts O/U",
]


def _title_for_unknown_book(key: str) -> str:
    return key.replace("_", " ").replace("-", " ").title()


def target_books_from_env() -> dict[str, str]:
    raw_value = os.getenv("BOLTODDS_TARGET_BOOKS", "")
    if not raw_value.strip():
        return dict(BOLTODDS_DEFAULT_BOOKS)

    books: dict[str, str] = {}
    for raw_key in raw_value.split(","):
        key = raw_key.strip().lower()
        if not key:
            continue
        books[key] = BOLTODDS_KNOWN_BOOK_TITLES.get(key, _title_for_unknown_book(key))
    return books


def market_aliases_from_env() -> list[str]:
    raw_value = os.getenv("BOLTODDS_MARKET_ALIASES", "")
    if not raw_value.strip():
        return list(BOLTODDS_DEFAULT_MARKET_ALIASES)

    return [alias.strip() for alias in raw_value.split(",") if alias.strip()]


def build_subscribe_message(
    sports: list[str],
    sportsbooks: list[str],
    markets: list[str],
) -> dict[str, Any]:
    return {
        "action": "subscribe",
        "filters": {
            "sports": sports,
            "sportsbooks": sportsbooks,
            "markets": markets,
        },
    }


def _sorted_market_names(names: list[str]) -> list[str]:
    return sorted(set(names), key=lambda name: (name.casefold(), name))


def _market_names(markets: Any, sport: str = "MLB") -> list[str]:
    if not isinstance(markets, dict):
        return []

    names: list[str] = []
    for sports in markets.values():
        if not isinstance(sports, dict):
            continue
        for sport_name, market_list in sports.items():
            if str(sport_name).strip().casefold() != sport.casefold():
                continue
            if isinstance(market_list, list):
                names.extend(market for market in market_list if isinstance(market, str))
    return _sorted_market_names(names)


def select_pitcher_strikeout_markets(
    markets: Any,
    aliases: list[str],
) -> list[str]:
    names = _market_names(markets)
    for alias in aliases:
        normalized_alias = alias.strip().casefold()
        if not normalized_alias:
            continue
        exact_matches = [
            market_name
            for market_name in names
            if market_name.strip().casefold() == normalized_alias
        ]
        if exact_matches:
            return [exact_matches[0]]

    fallback_matches = [
        market_name
        for market_name in names
        if "pitcher" in market_name.casefold()
        and "strikeout" in market_name.casefold()
    ]
    return fallback_matches[:1]


def get_json(
    path: str,
    api_key: str,
    params: dict[str, Any] | None = None,
) -> Any:
    response = requests.get(
        f"{BOLTODDS_REST_BASE}/{path.lstrip('/')}",
        params={**(params or {}), "key": api_key},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
