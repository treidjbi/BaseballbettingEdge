"""Build live pick events from the latest dashboard artifact into Supabase."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

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
from market_infra.live_market_display import build_live_market_display_rows  # noqa: E402
from market_infra.market_evidence import build_market_pick_evidence_rows  # noqa: E402
from market_infra.shadow_notification_candidates import (  # noqa: E402
    build_shadow_notification_candidate_rows,
)
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402
from scripts.shadow_propline_to_supabase import poll_propline_to_supabase  # noqa: E402

DEFAULT_ARTIFACT = ROOT / "dashboard" / "data" / "processed" / "today.json"
DEFAULT_ARTIFACT_URL = (
    "https://raw.githubusercontent.com/treidjbi/BaseballBettingEdge/"
    "main/dashboard/data/processed/today.json"
)
LIVE_NOTIFICATION_MOVEMENT_PROVIDERS = {"propline"}


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _optional_env(name: str) -> str:
    return os.environ.get(name, "").strip()


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


def _load_artifact_bytes(artifact_bytes: bytes) -> tuple[dict[str, Any], str]:
    payload = json.loads(artifact_bytes.decode("utf-8"))
    return payload, hashlib.sha256(artifact_bytes).hexdigest()


def _load_artifact(path: Path, artifact_url: str | None = None) -> tuple[dict[str, Any], str, str]:
    if artifact_url:
        try:
            with urlopen(artifact_url, timeout=20) as response:
                payload, artifact_sha = _load_artifact_bytes(response.read())
                return payload, artifact_sha, artifact_url
        except Exception as error:
            print(
                f"Warning: remote artifact fetch failed ({error}); falling back to local {path}",
                file=sys.stderr,
            )

    artifact_bytes = path.read_bytes()
    payload, artifact_sha = _load_artifact_bytes(artifact_bytes)
    return payload, artifact_sha, _source_artifact_path(path)


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


def _live_notification_snapshots(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("provider") or "").strip().lower() in LIVE_NOTIFICATION_MOVEMENT_PROVIDERS
    ]


def run(
    *,
    slate_date: str,
    artifact_path: Path,
    supabase_url: str,
    service_role_key: str,
    poll_propline: bool = False,
    artifact_url: str | None = None,
    artifact_payload: dict[str, Any] | None = None,
    artifact_sha: str | None = None,
    artifact_source: str | None = None,
) -> dict[str, Any]:
    if artifact_payload is None:
        payload, artifact_sha, artifact_source = _load_artifact(Path(artifact_path), artifact_url=artifact_url)
    else:
        payload = artifact_payload
        if not artifact_sha or not artifact_source:
            raise ValueError("artifact_sha and artifact_source are required with artifact_payload")

    writer = SupabaseMarketWriter(supabase_url, service_role_key)
    previous_rows = writer.select_rows("live_pick_state", {"slate_date": f"eq.{slate_date}"})
    observed_at = _now_utc()
    propline_result: dict[str, Any] | None = None

    if poll_propline:
        propline_result = poll_propline_to_supabase(
            slate_date,
            writer=writer,
            observed_at=observed_at.isoformat(),
        )

    pick_notification_rows, state_rows = build_pick_change_events(
        slate_date=slate_date,
        pitchers=payload.get("pitchers") or [],
        previous_state=_previous_state(previous_rows),
        observed_at=observed_at,
        source_artifact_path=artifact_source,
        source_artifact_sha256=artifact_sha,
    )
    missing_notification_rows, missing_state_rows = build_missing_pick_state_events(
        slate_date=slate_date,
        previous_rows=previous_rows,
        current_state_rows=state_rows,
        observed_at=observed_at,
        source_artifact_path=artifact_source,
        source_artifact_sha256=artifact_sha,
    )
    state_rows.extend(missing_state_rows)

    snapshot_rows = writer.select_rows("market_snapshots", {
        "provider": "in.(propline,boltodds)",
        "order": "observed_at.desc",
        "limit": "2500",
    })
    previous_snapshots, current_snapshots = _snapshot_pairs(_live_notification_snapshots(snapshot_rows))
    movement_notification_rows = build_line_movement_events(
        slate_date=slate_date,
        live_picks=state_rows,
        previous_snapshots=previous_snapshots,
        current_snapshots=current_snapshots,
    )
    line_movement_rows = build_line_movement_rows(movement_notification_rows)
    market_pick_evidence_rows = build_market_pick_evidence_rows(
        slate_date=slate_date,
        live_picks=state_rows,
        snapshot_rows=snapshot_rows,
        observed_at=observed_at,
        source_artifact_path=artifact_source,
        source_artifact_sha256=artifact_sha,
    )
    live_market_display_rows = build_live_market_display_rows(
        slate_date=slate_date,
        live_picks=state_rows,
        snapshot_rows=snapshot_rows,
        observed_at=observed_at,
        source_artifact_path=artifact_source,
        source_artifact_sha256=artifact_sha,
    )
    shadow_notification_candidate_rows = build_shadow_notification_candidate_rows(
        market_pick_evidence_rows
    )

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
    writer.upsert_rows(
        "market_pick_evidence",
        market_pick_evidence_rows,
        on_conflict="slate_date,normalized_pitcher,side,provider",
    )
    writer.upsert_rows(
        "live_market_display_state",
        live_market_display_rows,
        on_conflict="slate_date,normalized_pitcher,side,provider",
    )
    writer.upsert_rows(
        "shadow_notification_candidates",
        shadow_notification_candidate_rows,
        on_conflict="dedupe_key",
    )
    writer.upsert_rows("game_reminder_state", reminder_rows, on_conflict="dedupe_key")
    writer.upsert_rows("live_pick_state", state_rows, on_conflict="slate_date,normalized_pitcher,side")
    return {
        "state_rows": state_rows,
        "notification_rows": notification_rows,
        "line_movement_rows": line_movement_rows,
        "market_pick_evidence_rows": market_pick_evidence_rows,
        "live_market_display_rows": live_market_display_rows,
        "shadow_notification_candidate_rows": shadow_notification_candidate_rows,
        "reminder_rows": reminder_rows,
        "live_pick_state": len(state_rows),
        "notification_events": len(notification_rows),
        "line_movement_events": len(line_movement_rows),
        "market_pick_evidence": len(market_pick_evidence_rows),
        "live_market_display_state": len(live_market_display_rows),
        "shadow_notification_candidates": len(shadow_notification_candidate_rows),
        "game_reminders": len(reminder_rows),
        "propline": propline_result or {"skipped": True},
        "artifact_source": artifact_source,
    }


def main() -> int:
    artifact = DEFAULT_ARTIFACT
    artifact_url = ""
    payload = None
    slate_date = sys.argv[1] if len(sys.argv) > 1 else ""
    if not slate_date:
        artifact_url = _optional_env("LIVE_ARTIFACT_URL") or DEFAULT_ARTIFACT_URL
        payload, artifact_sha, artifact_source = _load_artifact(artifact, artifact_url=artifact_url)
        slate_date = str(payload["date"])
    else:
        payload = None
        artifact_sha = None
        artifact_source = _source_artifact_path(artifact)

    result = run(
        slate_date=slate_date,
        artifact_path=artifact,
        supabase_url=_env("SUPABASE_URL"),
        service_role_key=_env("SUPABASE_SERVICE_ROLE_KEY"),
        poll_propline=bool(_optional_env("PROPLINE_API_KEY")),
        artifact_url=artifact_url,
        artifact_payload=payload,
        artifact_sha=artifact_sha,
        artifact_source=artifact_source,
    )
    propline = result["propline"]
    propline_summary = "propline=skipped"
    if not propline.get("skipped"):
        propline_summary = (
            f"propline_events={propline['target_event_count']} "
            f"propline_snapshots={propline['snapshot_count']}"
        )
    print(
        "Live event build "
        f"date={slate_date} state_rows={result['live_pick_state']} "
        f"notification_events={result['notification_events']} "
        f"live_market_display={result.get('live_market_display_state', 0)} "
        f"artifact_source={'remote' if str(result.get('artifact_source', artifact_source)).startswith('http') else 'local'} "
        f"{propline_summary}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
