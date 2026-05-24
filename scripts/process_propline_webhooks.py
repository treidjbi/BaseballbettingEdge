"""Process PropLine webhook inbox rows into shadow movement facts.

This script is observation-only. It must not update production artifacts,
provider order, picks, grading, calibration, or notification sends.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402
from pipeline.name_utils import normalize  # noqa: E402


PHOENIX_TZ = timezone(timedelta(hours=-7), "America/Phoenix")
DEFAULT_LIMIT = 100
DEFAULT_MAX_AGE_MINUTES = 180


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _env_int(name: str, *, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise EnvironmentError(f"{name} must be an integer") from exc


def _side(value: Any) -> str | None:
    side = str(value or "").strip().lower()
    if side in {"over", "under"}:
        return side
    return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip().replace("+", "")))
    except (TypeError, ValueError):
        return None


def _present_value(*values: Any) -> Any:
    for value in values:
        if value is not None and str(value).strip() != "":
            return value
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _phoenix_slate_date(*values: Any) -> str | None:
    for value in values:
        parsed = _parse_timestamp(value)
        if parsed is not None:
            return parsed.astimezone(PHOENIX_TZ).date().isoformat()
    return None


def _movement_kind(
    *,
    previous_line: float,
    current_line: float,
    previous_odds: int,
    current_odds: int,
) -> str | None:
    line_changed = previous_line != current_line
    odds_changed = previous_odds != current_odds
    if line_changed and odds_changed:
        return "line_and_odds"
    if line_changed:
        return "line"
    if odds_changed:
        return "odds"
    return None


def _line_movement_row(delivery: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    payload = delivery.get("payload")
    if not isinstance(payload, dict):
        return None, "unsupported_payload_shape"

    event_type = str(payload.get("event_type") or delivery.get("prop_line_event") or "").strip()
    if event_type != "line_movement":
        return None, "unsupported_event_type"

    event = payload.get("event")
    current = payload.get("current")
    previous = payload.get("previous")
    if not isinstance(event, dict) or not isinstance(current, dict) or not isinstance(previous, dict):
        return None, "unsupported_payload_shape"

    player_name = str(payload.get("player_name") or "").strip()
    side = _side(payload.get("outcome_name"))
    previous_line = _float(previous.get("point"))
    current_line = _float(current.get("point"))
    previous_odds = _int(previous.get("price_american"))
    current_odds = _int(current.get("price_american"))
    observed_at = (
        payload.get("timestamp")
        or delivery.get("prop_line_timestamp")
        or delivery.get("received_at")
    )
    observed_at_dt = _parse_timestamp(observed_at)
    slate_date = _phoenix_slate_date(
        event.get("commence_time"),
        observed_at_dt,
        delivery.get("received_at"),
    )
    if (
        not player_name
        or side is None
        or previous_line is None
        or current_line is None
        or previous_odds is None
        or current_odds is None
        or observed_at_dt is None
        or not slate_date
    ):
        return None, "unsupported_payload_shape"

    movement_kind = _movement_kind(
        previous_line=previous_line,
        current_line=current_line,
        previous_odds=previous_odds,
        current_odds=current_odds,
    )
    if movement_kind is None:
        return None, "no_movement"

    delivery_id = str(delivery.get("prop_line_delivery_id") or delivery.get("id") or "").strip()
    if not delivery_id:
        return None, "missing_delivery_id"

    bookmaker_key = str(_present_value(
        payload.get("bookmaker_key"),
        current.get("bookmaker_key"),
        previous.get("bookmaker_key"),
        payload.get("bookmaker"),
        payload.get("book"),
    ) or "").strip().lower()
    bookmaker_key_missing = False
    if not bookmaker_key:
        bookmaker_key = "propline_webhook"
        bookmaker_key_missing = True
    bookmaker_title = _present_value(
        payload.get("bookmaker_title"),
        current.get("bookmaker_title"),
        previous.get("bookmaker_title"),
    )
    market_id = _present_value(
        payload.get("market_id"),
        current.get("market_id"),
        previous.get("market_id"),
    )
    outcome_id = _present_value(
        payload.get("outcome_id"),
        current.get("outcome_id"),
        previous.get("outcome_id"),
    )

    provider_event_id = str(event.get("external_id") or event.get("id") or "").strip()
    metadata = {
        "bookmaker_key_missing": bookmaker_key_missing,
        "event_type": event_type,
        "market_key": payload.get("market_key"),
        "price_change_pct": _float(payload.get("price_change_pct")),
        "prop_line_delivery_id": delivery_id,
        "prop_line_event_id": event.get("id"),
        "provider_event_id": provider_event_id or None,
        "source": "propline_webhook",
        "sport_key": payload.get("sport_key"),
        "teams": {
            "away": event.get("away_team"),
            "home": event.get("home_team"),
        },
    }
    if bookmaker_title is not None:
        metadata["bookmaker_title"] = bookmaker_title
    if market_id is not None:
        metadata["market_id"] = market_id
    if outcome_id is not None:
        metadata["outcome_id"] = outcome_id

    row = {
        "slate_date": slate_date,
        "normalized_pitcher": normalize(player_name),
        "pitcher": player_name,
        "side": side,
        "bookmaker_key": bookmaker_key,
        "previous_line": previous_line,
        "current_line": current_line,
        "previous_odds": previous_odds,
        "current_odds": current_odds,
        "movement_direction": "neutral",
        "movement_kind": movement_kind,
        "observed_at": observed_at_dt.isoformat(),
        "dedupe_key": f"{slate_date}:propline_webhook:{delivery_id}",
        "source_snapshot_id": None,
        "metadata": metadata,
    }
    return row, None


def run(
    *,
    supabase_url: str,
    service_role_key: str,
    limit: int = DEFAULT_LIMIT,
    received_after: datetime | None = None,
) -> dict[str, Any]:
    writer = SupabaseMarketWriter(supabase_url, service_role_key)
    query = {
        "processed": "eq.false",
        "order": "received_at.asc",
        "limit": str(max(1, limit)),
    }
    if received_after is not None:
        cutoff = received_after.astimezone(timezone.utc)
        query["received_at"] = f"gte.{cutoff.isoformat()}"
    deliveries = writer.select_rows(
        "propline_webhook_deliveries",
        query,
    )

    movement_rows: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    processed = 0
    unsupported = 0

    for delivery in deliveries:
        delivery_id = delivery.get("id")
        if not delivery_id:
            unsupported += 1
            continue

        if not delivery.get("signature_valid"):
            unsupported += 1
            updates.append({
                "id": delivery_id,
                "processed": True,
                "processing_error": "invalid_signature",
            })
            continue

        movement_row, error = _line_movement_row(delivery)
        if error is not None:
            unsupported += 1
            updates.append({
                "id": delivery_id,
                "processed": True,
                "processing_error": error,
            })
            continue

        if movement_row is not None:
            movement_rows.append(movement_row)
            processed += 1
        updates.append({
            "id": delivery_id,
            "processed": True,
            "processing_error": None,
        })

    if movement_rows:
        writer.upsert_rows("line_movement_events", movement_rows, on_conflict="dedupe_key")
    if updates:
        writer.upsert_rows("propline_webhook_deliveries", updates, on_conflict="id")

    return {
        "deliveries": len(deliveries),
        "processed": processed,
        "line_movement_events": len(movement_rows),
        "unsupported": unsupported,
        "received_after": (
            received_after.astimezone(timezone.utc).isoformat()
            if received_after is not None
            else None
        ),
    }


def main() -> int:
    max_age_minutes = _env_int(
        "LIVE_PROCESS_PROPLINE_WEBHOOK_MAX_AGE_MINUTES",
        default=DEFAULT_MAX_AGE_MINUTES,
    )
    received_after = None
    if max_age_minutes > 0:
        received_after = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    result = run(
        supabase_url=_env("SUPABASE_URL"),
        service_role_key=_env("SUPABASE_SERVICE_ROLE_KEY"),
        limit=_env_int("LIVE_PROCESS_PROPLINE_WEBHOOK_LIMIT", default=DEFAULT_LIMIT),
        received_after=received_after,
    )
    print(
        "PropLine webhook processing "
        f"deliveries={result['deliveries']} "
        f"processed={result['processed']} "
        f"line_movement_events={result['line_movement_events']} "
        f"unsupported={result['unsupported']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
