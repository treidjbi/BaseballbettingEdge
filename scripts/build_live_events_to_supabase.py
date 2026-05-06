"""Build live pick events from the latest dashboard artifact into Supabase."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

from market_infra.live_events import (  # noqa: E402
    build_line_movement_events,
    build_line_movement_rows,
    build_missing_pick_state_events,
    build_pick_change_events,
    build_reminder_events,
)
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402

DEFAULT_ARTIFACT = ROOT / "dashboard" / "data" / "processed" / "today.json"


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _source_artifact_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _previous_state(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    previous: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        slate_date = row.get("slate_date")
        normalized_pitcher = row.get("normalized_pitcher")
        side = row.get("side")
        if slate_date and normalized_pitcher and side:
            previous[(str(slate_date), str(normalized_pitcher), str(side))] = row
    return previous


def _load_artifact(path: Path) -> tuple[dict[str, Any], str]:
    artifact_bytes = path.read_bytes()
    payload = json.loads(artifact_bytes.decode("utf-8"))
    return payload, hashlib.sha256(artifact_bytes).hexdigest()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _snapshot_pairs(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        provider_event_id = str(row.get("provider_event_id") or "").strip()
        book = str(row.get("bookmaker_key") or "").strip()
        normalized = str(row.get("normalized_player_name") or "").strip()
        side = str(row.get("side") or "").strip().lower()
        if provider_event_id and book and normalized and side in {"over", "under"}:
            by_key.setdefault((provider_event_id, book, normalized, side), []).append(row)

    previous: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for snapshots in by_key.values():
        ordered = sorted(snapshots, key=lambda row: str(row.get("observed_at") or ""))
        if len(ordered) < 2:
            continue
        previous.append(ordered[-2])
        current.append(ordered[-1])

    return previous, current


def run(
    *,
    slate_date: str,
    artifact_path: Path,
    supabase_url: str,
    service_role_key: str,
) -> dict[str, Any]:
    payload, artifact_sha = _load_artifact(Path(artifact_path))
    writer = SupabaseMarketWriter(supabase_url, service_role_key)
    previous_rows = writer.select_rows("live_pick_state", {"slate_date": f"eq.{slate_date}"})
    observed_at = _now_utc()

    pick_notification_rows, state_rows = build_pick_change_events(
        slate_date=slate_date,
        pitchers=payload.get("pitchers") or [],
        previous_state=_previous_state(previous_rows),
        observed_at=observed_at,
        source_artifact_path=_source_artifact_path(Path(artifact_path)),
        source_artifact_sha256=artifact_sha,
    )
    missing_notification_rows, missing_state_rows = build_missing_pick_state_events(
        slate_date=slate_date,
        previous_rows=previous_rows,
        current_state_rows=state_rows,
        observed_at=observed_at,
        source_artifact_path=_source_artifact_path(Path(artifact_path)),
        source_artifact_sha256=artifact_sha,
    )
    state_rows.extend(missing_state_rows)

    snapshot_rows = writer.select_rows("market_snapshots", {
        "order": "observed_at.desc",
        "limit": "500",
    })
    previous_snapshots, current_snapshots = _snapshot_pairs(snapshot_rows)
    movement_notification_rows = build_line_movement_events(
        slate_date=slate_date,
        live_picks=state_rows,
        previous_snapshots=previous_snapshots,
        current_snapshots=current_snapshots,
    )
    line_movement_rows = build_line_movement_rows(movement_notification_rows)

    existing_reminders = writer.select_rows("game_reminder_state", {"slate_date": f"eq.{slate_date}"})
    reminder_notification_rows, reminder_rows = build_reminder_events(
        slate_date=slate_date,
        live_picks=state_rows,
        existing_reminders=existing_reminders,
        observed_at=observed_at,
    )

    notification_rows = [
        *pick_notification_rows,
        *missing_notification_rows,
        *movement_notification_rows,
        *reminder_notification_rows,
    ]
    writer.upsert_rows("notification_events", notification_rows, on_conflict="dedupe_key")
    writer.upsert_rows("line_movement_events", line_movement_rows, on_conflict="dedupe_key")
    writer.upsert_rows("game_reminder_state", reminder_rows, on_conflict="dedupe_key")
    writer.upsert_rows("live_pick_state", state_rows, on_conflict="slate_date,normalized_pitcher,side")
    return {
        "state_rows": state_rows,
        "notification_rows": notification_rows,
        "line_movement_rows": line_movement_rows,
        "reminder_rows": reminder_rows,
        "live_pick_state": len(state_rows),
        "notification_events": len(notification_rows),
        "line_movement_events": len(line_movement_rows),
        "game_reminders": len(reminder_rows),
    }


def main() -> int:
    artifact = DEFAULT_ARTIFACT
    payload = None
    slate_date = sys.argv[1] if len(sys.argv) > 1 else ""
    if not slate_date:
        payload, _ = _load_artifact(artifact)
        slate_date = str(payload["date"])

    result = run(
        slate_date=slate_date,
        artifact_path=artifact,
        supabase_url=_env("SUPABASE_URL"),
        service_role_key=_env("SUPABASE_SERVICE_ROLE_KEY"),
    )
    print(
        "Live event build "
        f"date={slate_date} state_rows={result['live_pick_state']} "
        f"notification_events={result['notification_events']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
