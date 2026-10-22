from __future__ import annotations

from typing import Any


def _normalized_books(books_seen: set[str] | list[str]) -> list[str]:
    return sorted(str(book).strip() for book in books_seen if str(book).strip())


def build_heartbeat_row(
    *,
    provider: str,
    mode: str,
    slate_date: str,
    run_id: str | None,
    observed_at: str,
    event: str,
    books_seen: set[str] | list[str],
    last_message_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "provider": provider,
        "mode": mode,
        "slate_date": slate_date,
        "observed_at": observed_at,
        "books_seen": _normalized_books(books_seen),
        "metadata": {
            "event": event,
            **(metadata or {}),
        },
    }
    if run_id:
        row["run_id"] = run_id
    if last_message_at:
        row["last_message_at"] = last_message_at
    return row


def should_flush_batch(
    *,
    pending_count: int,
    batch_size: int,
    last_flush_monotonic: float,
    now_monotonic: float,
    flush_seconds: float,
) -> bool:
    if pending_count <= 0:
        return False
    if batch_size > 0 and pending_count >= batch_size:
        return True
    if flush_seconds <= 0:
        return False
    return (now_monotonic - last_flush_monotonic) >= flush_seconds


def append_raw_sample(
    samples: list[Any],
    payload: Any,
    *,
    limit: int,
) -> list[Any]:
    if limit <= 0 or len(samples) >= limit:
        return list(samples[: max(limit, 0)])
    return [*samples, payload]
