from __future__ import annotations

import hashlib
import json
from typing import Any

from pipeline.name_utils import normalize


THERUNDOWN_TARGET_BOOKS = {
    "19": ("draftkings", "DraftKings"),
    "22": ("betmgm", "BetMGM"),
    "23": ("fanduel", "FanDuel"),
    "24": ("thescore", "theScore Bet"),
    "25": ("kalshi", "Kalshi"),
}
THERUNDOWN_SPORT_KEY = "baseball_mlb"
THERUNDOWN_MARKET_ID = 19
THERUNDOWN_MARKET_KEY = "pitcher_strikeouts"


def snapshots_from_therundown_events(
    events: list[dict[str, Any]],
    *,
    observed_at: str,
    mainline_only: bool = True,
    target_books: dict[str, tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Normalize TheRundown pitcher-K event rows into shadow market snapshots."""
    target_books = target_books or THERUNDOWN_TARGET_BOOKS
    rows: list[dict[str, Any]] = []

    for event in events:
        provider_event_id = str(event.get("event_id") or event.get("id") or "").strip()
        if not provider_event_id:
            continue
        game_time = event.get("event_date") or event.get("commence_time") or event.get("game_time")

        for market in event.get("markets") or []:
            if str(market.get("market_id")) != str(THERUNDOWN_MARKET_ID):
                continue
            for participant in market.get("participants") or []:
                player_name = str(participant.get("name") or "").strip()
                if not player_name:
                    continue
                for line_row in participant.get("lines") or []:
                    parsed = _parse_line_value(line_row.get("value"))
                    if parsed is None:
                        continue
                    side, line = parsed
                    for affiliate_id, price_info in (line_row.get("prices") or {}).items():
                        affiliate_id = str(affiliate_id)
                        if affiliate_id not in target_books:
                            continue
                        if mainline_only and price_info.get("is_main_line") is False:
                            continue
                        american_odds = _american_odds(price_info.get("price"))
                        if american_odds is None:
                            continue

                        bookmaker_key, bookmaker_title = target_books[affiliate_id]
                        normalized = normalize(player_name)
                        source_payload = {
                            "affiliate_id": affiliate_id,
                            "affiliate_title": bookmaker_title,
                            "price": price_info.get("price"),
                            "is_main_line": price_info.get("is_main_line"),
                            "updated_at": price_info.get("updated_at"),
                            "participant_id": participant.get("id"),
                            "market_id": market.get("market_id"),
                        }
                        dedupe_parts = {
                            "provider": "therundown",
                            "provider_event_id": provider_event_id,
                            "market_key": THERUNDOWN_MARKET_KEY,
                            "bookmaker_key": bookmaker_key,
                            "player": normalized,
                            "side": side,
                            "line": line,
                            "price": american_odds,
                            "observed_at": observed_at,
                        }
                        rows.append({
                            "provider": "therundown",
                            "provider_event_id": provider_event_id,
                            "game_time": game_time,
                            "sport_key": THERUNDOWN_SPORT_KEY,
                            "market_key": THERUNDOWN_MARKET_KEY,
                            "bookmaker_key": bookmaker_key,
                            "bookmaker_title": bookmaker_title,
                            "player_name": player_name,
                            "normalized_player_name": normalized,
                            "side": side,
                            "line": line,
                            "american_odds": american_odds,
                            "observed_at": observed_at,
                            "book_updated_at": price_info.get("updated_at"),
                            "source_payload": source_payload,
                            "dedupe_key": _dedupe_key(dedupe_parts),
                        })

    return rows


def _parse_line_value(value: Any) -> tuple[str, float] | None:
    parts = str(value or "").strip().lower().split()
    if len(parts) != 2 or parts[0] not in {"over", "under"}:
        return None
    try:
        return parts[0], float(parts[1])
    except ValueError:
        return None


def _american_odds(value: Any) -> int | None:
    try:
        text = str(value).strip().replace("+", "")
        if not text or text.lower() in {"none", "null", "n/a", "-"}:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _dedupe_key(parts: dict[str, Any]) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
