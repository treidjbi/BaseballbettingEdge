from __future__ import annotations

import hashlib
import json
from typing import Any

from pipeline.name_utils import normalize

PROPLINE_TARGET_BOOKS = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betrivers": "BetRivers",
    "kalshi": "Kalshi",
}

PROPLINE_SPORT_KEY = "baseball_mlb"
PROPLINE_MARKET_KEY = "pitcher_strikeouts"


def _american_odds(value: Any) -> int | None:
    try:
        text = str(value).strip().replace("+", "")
        if not text or text.lower() in {"none", "null", "n/a", "-"}:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _side(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"over", "under"}:
        return text
    return None


def _dedupe_key(parts: dict[str, Any]) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshots_from_propline_event(event: dict[str, Any], observed_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    provider_event_id = str(event.get("id") or "")
    if not provider_event_id:
        return rows

    for bookmaker in event.get("bookmakers") or []:
        bookmaker_key = str(bookmaker.get("key") or "").strip().lower()
        if bookmaker_key not in PROPLINE_TARGET_BOOKS:
            continue
        bookmaker_title = str(bookmaker.get("title") or PROPLINE_TARGET_BOOKS[bookmaker_key])

        for market in bookmaker.get("markets") or []:
            if market.get("key") != PROPLINE_MARKET_KEY:
                continue
            for outcome in market.get("outcomes") or []:
                side = _side(outcome.get("name"))
                player_name = str(outcome.get("description") or outcome.get("player") or "").strip()
                price = _american_odds(outcome.get("price"))
                point = outcome.get("point")
                if side is None or not player_name or price is None or point is None:
                    continue
                try:
                    line = float(point)
                except (TypeError, ValueError):
                    continue

                dedupe_parts = {
                    "provider": "propline",
                    "provider_event_id": provider_event_id,
                    "market_key": PROPLINE_MARKET_KEY,
                    "bookmaker_key": bookmaker_key,
                    "player": normalize(player_name),
                    "side": side,
                    "line": line,
                    "price": price,
                    "observed_at": observed_at,
                }

                rows.append({
                    "provider": "propline",
                    "provider_event_id": provider_event_id,
                    "sport_key": event.get("sport_key") or PROPLINE_SPORT_KEY,
                    "market_key": PROPLINE_MARKET_KEY,
                    "bookmaker_key": bookmaker_key,
                    "bookmaker_title": bookmaker_title,
                    "player_name": player_name,
                    "normalized_player_name": normalize(player_name),
                    "side": side,
                    "line": line,
                    "american_odds": price,
                    "observed_at": observed_at,
                    "book_updated_at": outcome.get("book_updated_at"),
                    "source_payload": outcome,
                    "dedupe_key": _dedupe_key(dedupe_parts),
                })

    return rows
