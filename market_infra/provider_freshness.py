from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


WEBSOCKET_HOLD_PROVIDERS = {"boltodds"}
UNKNOWN_FRESHNESS_SECONDS = 1_000_000_000


def normalize_book_key(value: Any) -> str:
    return str(value or "").strip().casefold().replace(" ", "").replace("-", "")


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def heartbeat_books(row: dict[str, Any], metadata: dict[str, Any] | None = None) -> set[str]:
    metadata = metadata or {}
    raw_books = row.get("books_seen")
    if not raw_books:
        raw_books = metadata.get("target_books") or metadata.get("books_seen")
    if isinstance(raw_books, str):
        text = raw_books.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = []
            raw_books = parsed
        elif text.startswith("{") and text.endswith("}"):
            raw_books = [item.strip() for item in text[1:-1].split(",")]
        else:
            raw_books = [item.strip() for item in text.split(",")]
    if not isinstance(raw_books, list):
        return set()
    return {normalize_book_key(book) for book in raw_books if str(book).strip()}


def provider_heartbeat_health(
    rows: list[dict[str, Any]],
    observed_now: datetime,
    stale_after_seconds: int,
) -> dict[tuple[str, str], dict[str, Any]]:
    health: dict[tuple[str, str], dict[str, Any]] = {}
    observed_now_dt = parse_datetime(observed_now)
    if observed_now_dt is None:
        return health

    for row in rows:
        provider = str(row.get("provider") or "").strip().lower()
        slate_date = str(row.get("slate_date") or "").strip()
        if provider not in WEBSOCKET_HOLD_PROVIDERS or not slate_date:
            continue

        metadata = json_object(row.get("metadata"))
        if str(metadata.get("event") or "").strip().lower() in {"failed", "completed"}:
            continue

        observed_at = parse_datetime(row.get("observed_at"))
        last_message_at = parse_datetime(row.get("last_message_at"))
        if observed_at is None or last_message_at is None:
            continue

        observed_age = max(int((observed_now_dt - observed_at).total_seconds()), 0)
        message_age = max(int((observed_now_dt - last_message_at).total_seconds()), 0)
        freshness_seconds = max(observed_age, message_age)
        if freshness_seconds > stale_after_seconds:
            continue

        books_seen = heartbeat_books(row, metadata)
        if not books_seen:
            continue

        key = (provider, slate_date)
        existing = health.get(key)
        if existing is None or freshness_seconds < int(
            existing.get("freshness_seconds") or UNKNOWN_FRESHNESS_SECONDS
        ):
            health[key] = {
                "freshness_seconds": freshness_seconds,
                "observed_age_seconds": observed_age,
                "message_age_seconds": message_age,
                "books_seen": books_seen,
            }
    return health


def effective_book_freshness(
    *,
    provider: str,
    slate_date: str,
    book_key: str,
    line_freshness_seconds: int,
    provider_health: dict[tuple[str, str], dict[str, Any]],
    stale_after_seconds: int,
) -> dict[str, Any]:
    if line_freshness_seconds <= stale_after_seconds:
        return {
            "freshness_seconds": line_freshness_seconds,
            "line_freshness_seconds": line_freshness_seconds,
            "heartbeat_hold": False,
            "heartbeat_freshness_seconds": None,
        }

    provider_key = str(provider or "").strip().lower()
    if provider_key not in WEBSOCKET_HOLD_PROVIDERS:
        return {
            "freshness_seconds": line_freshness_seconds,
            "line_freshness_seconds": line_freshness_seconds,
            "heartbeat_hold": False,
            "heartbeat_freshness_seconds": None,
        }

    health = provider_health.get((provider_key, str(slate_date or "").strip()))
    if not health:
        return {
            "freshness_seconds": line_freshness_seconds,
            "line_freshness_seconds": line_freshness_seconds,
            "heartbeat_hold": False,
            "heartbeat_freshness_seconds": None,
        }

    if normalize_book_key(book_key) not in set(health.get("books_seen") or []):
        return {
            "freshness_seconds": line_freshness_seconds,
            "line_freshness_seconds": line_freshness_seconds,
            "heartbeat_hold": False,
            "heartbeat_freshness_seconds": None,
        }

    try:
        heartbeat_freshness = int(health.get("freshness_seconds"))
    except (TypeError, ValueError):
        return {
            "freshness_seconds": line_freshness_seconds,
            "line_freshness_seconds": line_freshness_seconds,
            "heartbeat_hold": False,
            "heartbeat_freshness_seconds": None,
        }

    if heartbeat_freshness > stale_after_seconds:
        return {
            "freshness_seconds": line_freshness_seconds,
            "line_freshness_seconds": line_freshness_seconds,
            "heartbeat_hold": False,
            "heartbeat_freshness_seconds": None,
        }

    return {
        "freshness_seconds": heartbeat_freshness,
        "line_freshness_seconds": line_freshness_seconds,
        "heartbeat_hold": True,
        "heartbeat_freshness_seconds": heartbeat_freshness,
    }
