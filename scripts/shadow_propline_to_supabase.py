"""Write PropLine pitcher strikeout observations to Supabase sidecar tables.

This script is observation-only. It must not update today.json, picks_history,
dashboard artifacts, or production pipeline outputs.
"""
from __future__ import annotations

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

from fetch_odds import (  # noqa: E402
    PROPLINE_MARKET_KEY,
    PROPLINE_SPORT_KEY,
    _the_odds_event_date_phoenix,
    propline_get,
)
from market_infra.provider_audit import (  # noqa: E402
    TARGET_BOOKS,
    build_provider_coverage_audit,
)
from market_infra.prop_snapshot import snapshots_from_propline_event  # noqa: E402
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402

DEFAULT_PRODUCTION_ARTIFACT_URL = (
    "https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact?type=today"
)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _optional_env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _production_artifact_url_from_env() -> str:
    return (
        _optional_env("PROPLINE_ARTIFACT_URL")
        or _optional_env("PROPLINE_PRODUCTION_ARTIFACT_URL")
        or _optional_env("LIVE_ARTIFACT_URL")
        or DEFAULT_PRODUCTION_ARTIFACT_URL
    )


def _payload_slate_date(payload: dict | None) -> str:
    if not payload:
        return ""
    return str(payload.get("date") or payload.get("slate_date") or "").strip()


def _artifact_matches_slate(payload: dict | None, slate_date: str, source: str) -> bool:
    payload_date = _payload_slate_date(payload)
    if not payload_date or payload_date == slate_date:
        return True
    print(
        f"Warning: production artifact {source} has date={payload_date}; "
        f"expected slate_date={slate_date}; ignoring it",
        file=sys.stderr,
    )
    return False


def _production_artifact_for_slate(
    slate_date: str,
    root: Path = ROOT,
    artifact_url: str | None = None,
) -> tuple[dict | None, str | None]:
    if artifact_url:
        try:
            with urlopen(artifact_url, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if _artifact_matches_slate(payload, slate_date, artifact_url):
                return payload, artifact_url
        except Exception as error:
            print(
                f"Warning: remote production artifact fetch failed ({error}); "
                "falling back to local artifact",
                file=sys.stderr,
            )

    candidates = [
        Path("dashboard") / "data" / "processed" / f"{slate_date}.json",
        Path("dashboard") / "data" / "processed" / "today.json",
    ]
    for relative_path in candidates:
        path = root / relative_path
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        source = relative_path.as_posix()
        if _artifact_matches_slate(payload, slate_date, source):
            return payload, source
    return None, None


def _coverage_audit_row(
    *,
    run_id: str,
    slate_date: str,
    snapshots: list[dict],
    books_seen: set[str],
    target_event_count: int,
    observed_at: str,
    production_payload: dict | None,
    production_artifact_path: str | None,
) -> dict:
    audit = build_provider_coverage_audit(snapshots, production_payload)
    books_seen_raw = sorted(book for book in books_seen if book)
    non_target_books = sorted(
        book for book in books_seen_raw
        if book.strip().lower() not in TARGET_BOOKS
    )
    metadata = {
        **audit["metadata"],
        "snapshot_rows": len(snapshots),
        "observed_at": observed_at,
        "production_artifact_path": production_artifact_path,
        "books_seen_raw": books_seen_raw,
        "non_target_books_seen": non_target_books,
    }

    return {
        "run_id": run_id,
        "slate_date": slate_date,
        "provider": "propline",
        "target_books": audit["target_books"],
        "books_seen": books_seen_raw,
        "target_event_count": target_event_count,
        "parsed_pitcher_prop_count": audit["parsed_pitcher_prop_count"],
        "complete_pitcher_line_groups": audit["complete_pitcher_line_groups"],
        "same_line_overlap_count": audit["same_line_overlap_count"],
        "line_conflict_count": audit["line_conflict_count"],
        "missing_target_books": audit["missing_target_books"],
        "metadata": metadata,
    }


def poll_propline_to_supabase(
    slate_date: str,
    *,
    writer: SupabaseMarketWriter | None = None,
    observed_at: str | None = None,
    raise_on_error: bool = True,
) -> dict[str, Any]:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    writer = writer or SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))

    run_rows = writer.insert_rows("market_provider_runs", [{
        "provider": "propline",
        "mode": "shadow_poll",
        "slate_date": slate_date,
        "status": "started",
        "metadata": {"script": "scripts/shadow_propline_to_supabase.py"},
    }])
    run_id = run_rows[0]["id"]

    request_count = 1
    books_seen: set[str] = set()
    event_rows: list[dict] = []
    snapshots: list[dict] = []
    target_events = []
    production_payload, production_artifact_path = _production_artifact_for_slate(
        slate_date,
        artifact_url=_production_artifact_url_from_env(),
    )

    try:
        events = propline_get(f"/sports/{PROPLINE_SPORT_KEY}/events")
        if not isinstance(events, list):
            events = []
        target_events = [
            event for event in events
            if _the_odds_event_date_phoenix(event) == slate_date
        ]

        for event in target_events:
            event_id = event.get("id")
            if not event_id:
                continue
            event_rows.append({
                "provider": "propline",
                "provider_event_id": str(event_id),
                "sport_key": event.get("sport_key") or PROPLINE_SPORT_KEY,
                "slate_date": slate_date,
                "commence_time": event.get("commence_time"),
                "home_team": event.get("home_team"),
                "away_team": event.get("away_team"),
                "raw_event": event,
                "last_seen_at": observed_at,
            })
            request_count += 1
            odds = propline_get(
                f"/sports/{PROPLINE_SPORT_KEY}/events/{event_id}/odds",
                params={"markets": PROPLINE_MARKET_KEY},
            )
            if not isinstance(odds, dict):
                continue
            for bookmaker in odds.get("bookmakers", []):
                if bookmaker.get("key"):
                    books_seen.add(str(bookmaker["key"]))
            for row in snapshots_from_propline_event(odds, observed_at=observed_at):
                row["run_id"] = run_id
                snapshots.append(row)

        writer.upsert_rows("market_events", event_rows, on_conflict="provider,provider_event_id")
        writer.upsert_rows("market_snapshots", snapshots, on_conflict="dedupe_key")
        writer.insert_rows("provider_coverage_audits", [
            _coverage_audit_row(
                run_id=run_id,
                slate_date=slate_date,
                snapshots=snapshots,
                books_seen=books_seen,
                target_event_count=len(target_events),
                observed_at=observed_at,
                production_payload=production_payload,
                production_artifact_path=production_artifact_path,
            )
        ])
        writer.upsert_rows("market_provider_runs", [{
            "id": run_id,
            "provider": "propline",
            "mode": "shadow_poll",
            "slate_date": slate_date,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "request_count": request_count,
            "target_event_count": len(target_events),
            "parsed_pitcher_prop_count": len({
                (s["normalized_player_name"], s["line"]) for s in snapshots
            }),
            "books_seen": sorted(books_seen),
        }], on_conflict="id")
    except Exception as exc:
        error_message = str(exc)[:1000]
        writer.upsert_rows("market_provider_runs", [{
            "id": run_id,
            "provider": "propline",
            "mode": "shadow_poll",
            "slate_date": slate_date,
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "request_count": request_count,
            "target_event_count": len(target_events),
            "parsed_pitcher_prop_count": len({
                (s["normalized_player_name"], s["line"]) for s in snapshots
            }),
            "books_seen": sorted(books_seen),
            "error_message": error_message,
        }], on_conflict="id")
        if raise_on_error:
            raise
        return {
            "run_id": run_id,
            "status": "failed",
            "target_event_count": len(target_events),
            "snapshot_count": len(snapshots),
            "books_seen": sorted(books_seen),
            "request_count": request_count,
            "error": error_message,
        }

    return {
        "run_id": run_id,
        "target_event_count": len(target_events),
        "snapshot_count": len(snapshots),
        "books_seen": sorted(books_seen),
        "request_count": request_count,
    }


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/shadow_propline_to_supabase.py YYYY-MM-DD", file=sys.stderr)
        return 2

    slate_date = sys.argv[1]
    result = poll_propline_to_supabase(
        slate_date,
        raise_on_error=_env_flag("PROPLINE_SHADOW_FAIL_ON_ERROR", False),
    )
    if result.get("status") == "failed":
        print(
            f"PropLine shadow ingest degraded date={slate_date} "
            f"error={result.get('error', 'unknown')}",
            file=sys.stderr,
        )
        return 0
    print(
        f"PropLine shadow ingest date={slate_date} "
        f"events={result['target_event_count']} snapshots={result['snapshot_count']} "
        f"books={','.join(result['books_seen']) or 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
