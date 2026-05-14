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
MARKET_ALIASES = {
    "pitcher_strikeouts": MARKET_KEY,
    "pitcherstrikeouts": MARKET_KEY,
    "pitcher strikeouts": MARKET_KEY,
    "player_strikeouts": MARKET_KEY,
    "playerstrikeouts": MARKET_KEY,
    "player strikeouts": MARKET_KEY,
    "strikeouts": MARKET_KEY,
}

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


def normalize_market_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    compact = re.sub(r"[^a-z0-9]+", "", text)
    return MARKET_ALIASES.get(text) or MARKET_ALIASES.get(compact) or text


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
        market_key = normalize_market_key(snapshot.get("market_key"))
        if market_key != MARKET_KEY:
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

        key = (slate_date, provider, book_key, normalized_player, market_key, line)
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
            "game_time": _game_time(latest_row),
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
            "updated_at": _isoformat(observed_now),
        })

    _flag_line_conflicts(current_rows, stale_after_seconds)
    return current_rows


def build_opening_baseline_rows(current_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in current_rows:
        if not row.get("is_complete"):
            continue
        if row.get("over_odds") is None or row.get("under_odds") is None:
            continue
        rows.append({
            "slate_date": row["slate_date"],
            "normalized_player_name": row["normalized_player_name"],
            "player_name": row["player_name"],
            "market_key": row["market_key"],
            "book_key": row["book_key"],
            "book_name": row["book_name"],
            "line": row["line"],
            "opening_over_odds": row["over_odds"],
            "opening_under_odds": row["under_odds"],
            "opening_provider": row["provider"],
            "opening_source": "provider_first_seen",
            "first_seen_at": row["first_seen_at"],
            "source_line_id": row.get("over_snapshot_id") or row.get("under_snapshot_id"),
        })
    return rows


def _flag_line_conflicts(rows: list[dict[str, Any]], stale_after_seconds: int) -> None:
    by_book_player: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if not row.get("is_complete"):
            continue
        if int(row.get("freshness_seconds") or 0) > stale_after_seconds:
            continue
        key = (
            str(row.get("slate_date") or ""),
            str(row.get("provider") or ""),
            str(row.get("book_key") or ""),
            str(row.get("normalized_player_name") or ""),
            str(row.get("market_key") or ""),
        )
        by_book_player.setdefault(key, []).append(row)

    for conflict_rows in by_book_player.values():
        distinct_lines = {row.get("line") for row in conflict_rows}
        if len(distinct_lines) <= 1:
            continue
        for row in conflict_rows:
            flags = list(row.get("quality_flags") or [])
            if "line_conflict" not in flags:
                flags.append("line_conflict")
                row["quality_flags"] = flags


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


def _game_time(row: dict[str, Any]) -> str | None:
    for field in ("game_time", "commence_time", "event_date", "start_time"):
        value = row.get(field)
        if value:
            return str(value)
    payload = _raw_payload(row)
    if isinstance(payload, dict):
        for field in ("game_time", "commence_time", "event_date", "start_time"):
            value = payload.get(field)
            if value:
                return str(value)
    return None


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
