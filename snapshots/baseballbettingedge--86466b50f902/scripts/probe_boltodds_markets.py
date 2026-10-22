from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.boltodds_client import (
    get_json,
    market_aliases_from_env,
    select_pitcher_strikeout_markets,
    target_books_from_env,
)


PRIORITY_BOOKS = {"fanduel"}
SECONDARY_BOOKS = {"betmgm", "betrivers"}


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _lowered_values(values: object) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value).strip().lower() for value in values if str(value).strip()}


def _mlb_markets_for_book(markets: object, book_key: str) -> set[str]:
    if not isinstance(markets, dict):
        return set()

    book_payload = None
    for raw_book_key, raw_book_payload in markets.items():
        if str(raw_book_key).strip().lower() == book_key.lower():
            book_payload = raw_book_payload
            break

    if not isinstance(book_payload, dict):
        return set()

    for sport_name, market_list in book_payload.items():
        if str(sport_name).strip().lower() != "mlb":
            continue
        if not isinstance(market_list, list):
            return set()
        return {
            str(market_name).strip().lower()
            for market_name in market_list
            if str(market_name).strip()
        }
    return set()


def _books_with_selected_market(
    markets: object,
    target_books: dict[str, str],
    selected_markets: list[str],
) -> list[str]:
    selected_market_names = {
        market_name.strip().lower()
        for market_name in selected_markets
        if market_name.strip()
    }
    if not selected_market_names:
        return []

    books: list[str] = []
    for book_key in target_books:
        book_markets = _mlb_markets_for_book(markets, book_key)
        if selected_market_names.intersection(book_markets):
            books.append(book_key)
    return books


def build_probe_summary(
    info: dict,
    markets: dict,
    target_books: dict[str, str],
    aliases: list[str],
) -> dict:
    selected_markets = select_pitcher_strikeout_markets(markets, aliases)
    books_with_selected_market = _books_with_selected_market(
        markets,
        target_books,
        selected_markets,
    )
    selected_market_book_set = set(books_with_selected_market)
    available_books = _lowered_values(info.get("sportsbooks", []))
    available_target_books = [
        book_key for book_key in target_books if book_key.lower() in available_books
    ]
    missing_books = [
        book_key for book_key in target_books if book_key.lower() not in available_books
    ]

    blocking_reasons: list[str] = []
    sports = _lowered_values(info.get("sports", []))
    if "mlb" not in sports:
        blocking_reasons.append("MLB is not listed in BoltOdds get_info sports")
    if not selected_markets:
        blocking_reasons.append(
            "No MLB pitcher strikeout market matched configured aliases"
        )
    elif not PRIORITY_BOOKS.issubset(selected_market_book_set):
        blocking_reasons.append(
            "FanDuel must expose the selected pitcher strikeout market"
        )
    if selected_markets and not SECONDARY_BOOKS.intersection(selected_market_book_set):
        blocking_reasons.append(
            "At least one of BetMGM or BetRivers must expose the selected pitcher strikeout market"
        )
    if not PRIORITY_BOOKS.issubset(available_books):
        blocking_reasons.append("FanDuel is a required priority book")
    if not SECONDARY_BOOKS.intersection(available_books):
        blocking_reasons.append(
            "At least one of BetMGM or BetRivers must be available"
        )

    return {
        "starter_ready": not blocking_reasons,
        "selected_markets": selected_markets,
        "missing_books": missing_books,
        "available_target_books": available_target_books,
        "books_with_selected_market": books_with_selected_market,
        "blocking_reasons": blocking_reasons,
    }


def main() -> int:
    api_key = _env("BOLTODDS_API_KEY")
    target_books = target_books_from_env()
    aliases = market_aliases_from_env()

    info = get_json("get_info", api_key=api_key)
    markets = get_json(
        "get_markets",
        api_key=api_key,
        params={
            "sports": "MLB",
            "sportsbooks": ",".join(target_books),
        },
    )

    summary = build_probe_summary(info, markets, target_books, aliases)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["starter_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
