from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from pipeline.name_utils import normalize


BOLTODDS_DEFAULT_TARGET_BOOKS = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "betrivers": "BetRivers",
    "scorebet": "theScore Bet",
    "caesars": "Caesars",
}

BOLTODDS_SUPPORTED_ACTIONS = {"initial_state", "game_update", "line_update"}
AMERICAN_ODDS_RE = re.compile(r"^[+-]?\d+$")


def _valid_american_odds(odds: int) -> int | None:
    if odds == 0 or abs(odds) < 100:
        return None
    return odds


def _american_odds(value: Any) -> int | None:
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return _valid_american_odds(value)
        if not isinstance(value, str):
            return None

        text = str(value).strip()
        if not text or text.lower() in {"none", "null", "n/a", "-"}:
            return None
        if not AMERICAN_ODDS_RE.match(text):
            return None
        odds = int(text)
        return _valid_american_odds(odds)
    except (TypeError, ValueError, OverflowError):
        return None


def _line(value: Any) -> float | None:
    try:
        if isinstance(value, bool):
            return None
        line = float(value)
        if not math.isfinite(line):
            return None
        return line
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


def _normalized_values(values: set[str]) -> set[str]:
    return {str(value or "").strip().lower() for value in values}


def _market_allowed(value: Any, allowed_markets: set[str]) -> bool:
    return str(value or "").strip().lower() in _normalized_values(allowed_markets)


def _event_id(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    event_id = str(value).strip()
    return event_id or None


def _event_id_from_info(info: dict[str, Any]) -> str | None:
    for key in ("id", "game_id", "universal_id"):
        event_id = _event_id(info.get(key))
        if event_id:
            return event_id
    return None


def snapshots_from_boltodds_message(
    message: dict[str, Any],
    *,
    observed_at: str,
    allowed_markets: set[str],
    target_books: dict[str, str] | None = None,
    allowed_player_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(message, dict):
        return []

    if message.get("action") not in BOLTODDS_SUPPORTED_ACTIONS:
        return []

    data = message.get("data") or {}
    if not isinstance(data, dict):
        return []

    sportsbook = str(data.get("sportsbook") or "").strip().lower()
    target_books = target_books or BOLTODDS_DEFAULT_TARGET_BOOKS
    if sportsbook not in target_books:
        return []
    allowed_players = _normalized_values(allowed_player_names or set())

    info = data.get("info") or {}
    if not isinstance(info, dict):
        return []

    provider_event_id = _event_id_from_info(info)
    if provider_event_id is None:
        return []

    outcomes = data.get("outcomes") or {}
    if not isinstance(outcomes, dict):
        return []

    rows: list[dict[str, Any]] = []
    for outcome_label, outcome in outcomes.items():
        if not isinstance(outcome, dict):
            continue

        market_name = str(outcome.get("outcome_name") or "").strip()
        if not _market_allowed(market_name, allowed_markets):
            continue

        player_raw = outcome.get("outcome_target")
        if not isinstance(player_raw, str):
            continue
        player_name = player_raw.strip()
        side = _side(outcome.get("outcome_over_under"))
        line = _line(outcome.get("outcome_line"))
        price = _american_odds(outcome.get("odds"))
        if not player_name or side is None or line is None or price is None:
            continue

        normalized_player = normalize(player_name)
        if allowed_players and normalized_player not in allowed_players:
            continue
        dedupe_parts = {
            "provider": "boltodds",
            "provider_event_id": provider_event_id,
            "market_key": market_name,
            "bookmaker_key": sportsbook,
            "player": normalized_player,
            "side": side,
            "line": line,
            "price": price,
            "observed_at": observed_at,
        }

        rows.append({
            "provider": "boltodds",
            "provider_event_id": provider_event_id,
            "sport_key": str(data.get("sport") or "MLB"),
            "market_key": market_name,
            "bookmaker_key": sportsbook,
            "bookmaker_title": target_books[sportsbook],
            "player_name": player_name,
            "normalized_player_name": normalized_player,
            "side": side,
            "line": line,
            "american_odds": price,
            "observed_at": observed_at,
            "book_updated_at": message.get("timestamp"),
            "source_payload": {
                "action": message.get("action"),
                "game": data.get("game"),
                "home_team": data.get("home_team"),
                "away_team": data.get("away_team"),
                "outcome_label": outcome_label,
                "outcome": outcome,
            },
            "dedupe_key": _dedupe_key(dedupe_parts),
        })

    return rows
