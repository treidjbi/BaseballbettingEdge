"""Build current supported-book market lines from raw provider snapshots."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pipeline.name_utils import normalize

SUPPORTED_BOOK_NAMES = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "betrivers": "BetRivers",
    "caesars": "Caesars",
}
SUPPORTED_BOOK_KEYS = frozenset(SUPPORTED_BOOK_NAMES)
MARKET_KEY = "pitcher_strikeouts"

_BOOK_ALIASES = {
    "fd": "fanduel",
    "fanduel": "fanduel",
    "fanduelsportsbook": "fanduel",
    "dk": "draftkings",
    "draftking": "draftkings",
    "draftkings": "draftkings",
    "draftkingssportsbook": "draftkings",
    "betmgm": "betmgm",
    "betmgmsportsbook": "betmgm",
    "betrivers": "betrivers",
    "bet_rivers": "betrivers",
    "bet-rivers": "betrivers",
    "betriverssportsbook": "betrivers",
    "caesars": "caesars",
    "caesarssportsbook": "caesars",
    "caesarspalace": "caesars",
}


def normalize_book_key(value: Any) -> str:
    """Return the supported-book key from common raw bookmaker shapes."""
    if isinstance(value, dict):
        for field in ("bookmaker_key", "book_key", "bookmaker_title", "book_name", "book"):
            normalized = normalize_book_key(value.get(field))
            if normalized:
                return normalized
        return ""

    text = str(value or "").strip().lower()
    if not text:
        return ""
    compact = re.sub(r"[^a-z0-9]+", "", text)
    return _BOOK_ALIASES.get(text) or _BOOK_ALIASES.get(compact) or compact


def build_current_market_lines(
    snapshot_rows: list[dict[str, Any]],
    run_rows: list[dict[str, Any]],
    now_utc: datetime,
    stale_after_seconds: int = 900,
) -> list[dict[str, Any]]:
    """Build one current line row per slate/provider/book/player/market/line."""
    observed_now = _ensure_utc(now_utc)
    run_by_id = {str(row.get("id")): row for row in run_rows if row.get("id")}
    grouped: dict[tuple[str, str, str, str, str, float], list[dict[str, Any]]] = {}

    for snapshot in snapshot_rows:
        run_id = str(snapshot.get("run_id") or "")
        run = run_by_id.get(run_id)
        if not run:
            continue
        if str(snapshot.get("market_key") or "").strip() != MARKET_KEY:
            continue

        book_key = normalize_book_key(snapshot)
        if book_key not in SUPPORTED_BOOK_KEYS:
            continue

        player_name = str(snapshot.get("player_name") or "").strip()
        normalized_player = normalize(player_name)
        line = _float_or_none(snapshot.get("line"))
        provider = str(snapshot.get("provider") or run.get("provider") or "").strip().lower()
        slate_date = str(run.get("slate_date") or snapshot.get("slate_date") or "").strip()
        if not all([provider, slate_date, normalized_player]) or line is None:
            continue

        key = (slate_date, provider, book_key, normalized_player, MARKET_KEY, line)
        grouped.setdefault(key, []).append(snapshot)

    current_rows: list[dict[str, Any]] = []
    for key in sorted(grouped):
        rows = grouped[key]
        slate_date, provider, book_key, normalized_player, market_key, line = key
        over = _latest_side(rows, "over")
        under = _latest_side(rows, "under")
        timed_rows = [(row, _snapshot_time(row)) for row in rows]
        valid_times = [timestamp for _, timestamp in timed_rows if timestamp is not None]
        if not valid_times:
            continue

        first_seen = min(valid_times)
        last_seen = max(valid_times)
        freshness_seconds = max(int((observed_now - last_seen).total_seconds()), 0)
        quality_flags = _quality_flags(over, under, freshness_seconds, stale_after_seconds)
        latest_row = max(
            timed_rows,
            key=lambda item: item[1] or datetime.min.replace(tzinfo=timezone.utc),
        )[0]

        current_rows.append({
            "slate_date": slate_date,
            "provider": provider,
            "book_key": book_key,
            "book_name": _book_name(book_key, latest_row),
            "event_id": latest_row.get("event_id"),
            "provider_event_id": latest_row.get("provider_event_id"),
            "player_name": str(latest_row.get("player_name") or "").strip(),
            "normalized_player_name": normalized_player,
            "market_key": market_key,
            "line": line,
            "over_odds": _american_odds(over) if over else None,
            "under_odds": _american_odds(under) if under else None,
            "over_snapshot_id": over.get("id") if over else None,
            "under_snapshot_id": under.get("id") if under else None,
            "first_seen_at": _isoformat(first_seen),
            "last_seen_at": _isoformat(last_seen),
            "source_run_id": latest_row.get("run_id"),
            "is_complete": bool(over and under),
            "freshness_seconds": freshness_seconds,
            "quality_flags": quality_flags,
            "raw_payload": {
                "over": _raw_payload(over) if over else None,
                "under": _raw_payload(under) if under else None,
            },
        })

    return current_rows


def _latest_side(rows: list[dict[str, Any]], side: str) -> dict[str, Any] | None:
    candidates = [
        row for row in rows
        if str(row.get("side") or row.get("outcome_name") or "").strip().lower() == side
        and _snapshot_time(row) is not None
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            _snapshot_time(row) or datetime.min.replace(tzinfo=timezone.utc),
            str(row.get("id") or ""),
        ),
    )


def _quality_flags(
    over: dict[str, Any] | None,
    under: dict[str, Any] | None,
    freshness_seconds: int,
    stale_after_seconds: int,
) -> list[str]:
    flags: list[str] = []
    if over is None:
        flags.append("missing_over")
    if under is None:
        flags.append("missing_under")
    if freshness_seconds > stale_after_seconds:
        flags.append("stale")
    return flags


def _book_name(book_key: str, row: dict[str, Any]) -> str:
    raw_name = str(row.get("bookmaker_title") or row.get("book_name") or "").strip()
    return raw_name or SUPPORTED_BOOK_NAMES.get(book_key, book_key)


def _raw_payload(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    payload = row.get("raw_payload") or row.get("source_payload")
    if isinstance(payload, dict):
        return payload
    return row


def _american_odds(row: dict[str, Any] | None) -> int | None:
    if row is None:
        return None
    value = row.get("american_odds", row.get("odds"))
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _snapshot_time(row: dict[str, Any]) -> datetime | None:
    for field in ("observed_at", "captured_at", "last_seen_at", "created_at"):
        parsed = _parse_datetime(row.get(field))
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _ensure_utc(value)
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return _ensure_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat(value: datetime) -> str:
    return _ensure_utc(value).isoformat()


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
