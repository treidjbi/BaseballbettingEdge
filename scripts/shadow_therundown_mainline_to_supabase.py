"""Write TheRundown mainline pitcher strikeout observations to Supabase.

This script is shadow-only. It must not update today.json, picks_history,
dashboard artifacts, production provider order, model outputs, or notifications.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

from fetch_odds import (  # noqa: E402
    BASE_URL,
    MARKET_ID,
    SPORT_ID,
    TARGET_AFFILIATE_IDS,
    THROTTLE_S,
    _headers,
)
from market_infra.provider_audit import build_provider_coverage_audit  # noqa: E402
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402
from market_infra.therundown_snapshot import (  # noqa: E402
    THERUNDOWN_MARKET_KEY,
    THERUNDOWN_SPORT_KEY,
    THERUNDOWN_TARGET_BOOKS,
    snapshots_from_therundown_events,
)

SCRIPT_PATH = "scripts/shadow_therundown_mainline_to_supabase.py"
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
        _optional_env("THERUNDOWN_MAINLINE_ARTIFACT_URL")
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


def _slate_fetch_dates(slate_date: str) -> list[str]:
    dt = datetime.strptime(slate_date, "%Y-%m-%d")
    return [slate_date, (dt + timedelta(days=1)).strftime("%Y-%m-%d")]


def fetch_therundown_events(
    fetch_date: str,
    *,
    main_line: bool = True,
    hide_closed_markets: bool = True,
) -> dict[str, Any]:
    params: dict[str, str] = {
        "market_ids": str(MARKET_ID),
        "affiliate_ids": ",".join(TARGET_AFFILIATE_IDS),
    }
    if main_line:
        params["main_line"] = "true"
    if hide_closed_markets:
        params["hide_closed_markets"] = "1"

    response = requests.get(
        f"{BASE_URL}/sports/{SPORT_ID}/events/{fetch_date}",
        headers=_headers(),
        params=params,
        timeout=20,
    )
    headers = _tracked_headers(response.headers)
    response.raise_for_status()
    body = response.json()
    return {
        "fetch_date": fetch_date,
        "events": body.get("events", []),
        "datapoints": int(headers.get("X-Datapoints") or 0),
        "headers": headers,
        "params": params,
    }


def _tracked_headers(headers: Any) -> dict[str, str | None]:
    names = [
        "X-Datapoints",
        "X-Datapoints-Used",
        "X-Datapoints-Remaining",
        "X-Datapoints-Limit",
        "X-Datapoints-Period",
        "X-Tier",
        "X-Rate-Limit",
        "X-Data-Delay-Seconds",
        "X-Websocket-Access",
    ]
    return {name: headers.get(name) for name in names}


def _event_rows(
    *,
    slate_date: str,
    events: list[dict[str, Any]],
    observed_at: str,
) -> list[dict[str, Any]]:
    rows = []
    for event in events:
        provider_event_id = str(event.get("event_id") or event.get("id") or "").strip()
        if not provider_event_id:
            continue
        rows.append({
            "provider": "therundown",
            "provider_event_id": provider_event_id,
            "sport_key": THERUNDOWN_SPORT_KEY,
            "slate_date": slate_date,
            "commence_time": event.get("event_date") or event.get("commence_time"),
            "home_team": _team_name(event, "is_home"),
            "away_team": _team_name(event, "is_away"),
            "raw_event": _sanitized_event(event),
            "last_seen_at": observed_at,
        })
    return rows


def _team_name(event: dict[str, Any], marker: str) -> str | None:
    for team in event.get("teams") or []:
        if team.get(marker):
            return team.get("name")
    return None


def _sanitized_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id") or event.get("id"),
        "event_date": event.get("event_date") or event.get("commence_time"),
        "sport_id": event.get("sport_id"),
        "teams": event.get("teams") or [],
    }


def _run_metadata(
    *,
    production_payload: dict | None,
    production_artifact_path: str | None,
    fetch_results: list[dict[str, Any]],
    snapshot_count: int,
    query_mode: str,
    hide_closed_markets: bool,
) -> dict[str, Any]:
    return {
        "script": SCRIPT_PATH,
        "query_mode": query_mode,
        "hide_closed_markets": hide_closed_markets,
        "production_artifact_path": production_artifact_path,
        "production_artifact_date": _payload_slate_date(production_payload),
        "datapoints_total": sum(_integer(result.get("datapoints")) for result in fetch_results),
        "snapshot_rows": snapshot_count,
        "target_affiliate_ids": list(TARGET_AFFILIATE_IDS),
        "fetches": [
            {
                "fetch_date": result.get("fetch_date"),
                "datapoints": _integer(result.get("datapoints")),
                "event_count": len(result.get("events") or []),
                "params": result.get("params"),
                "headers": result.get("headers"),
            }
            for result in fetch_results
        ],
    }


def _coverage_audit_row(
    *,
    run_id: str,
    slate_date: str,
    snapshots: list[dict[str, Any]],
    books_seen: set[str],
    observed_at: str,
    production_payload: dict | None,
    production_artifact_path: str | None,
    fetch_results: list[dict[str, Any]],
    query_mode: str,
    hide_closed_markets: bool,
) -> dict[str, Any]:
    target_books = {
        book_key: title
        for book_key, title in THERUNDOWN_TARGET_BOOKS.values()
    }
    audit = build_provider_coverage_audit(
        snapshots,
        production_payload,
        target_books=target_books,
    )
    metadata = {
        **audit["metadata"],
        "snapshot_rows": len(snapshots),
        "observed_at": observed_at,
        "production_artifact_path": production_artifact_path,
        "books_seen_raw": sorted(books_seen),
        "query_mode": query_mode,
        "hide_closed_markets": hide_closed_markets,
        "datapoints_total": sum(_integer(result.get("datapoints")) for result in fetch_results),
        "fetches": [
            {
                "fetch_date": result.get("fetch_date"),
                "datapoints": _integer(result.get("datapoints")),
                "event_count": len(result.get("events") or []),
                "headers": result.get("headers"),
            }
            for result in fetch_results
        ],
    }

    return {
        "run_id": run_id,
        "slate_date": slate_date,
        "provider": "therundown",
        "target_books": audit["target_books"],
        "books_seen": sorted(books_seen),
        "target_event_count": sum(len(result.get("events") or []) for result in fetch_results),
        "parsed_pitcher_prop_count": audit["parsed_pitcher_prop_count"],
        "complete_pitcher_line_groups": audit["complete_pitcher_line_groups"],
        "same_line_overlap_count": audit["same_line_overlap_count"],
        "line_conflict_count": audit["line_conflict_count"],
        "missing_target_books": audit["missing_target_books"],
        "metadata": metadata,
    }


def poll_therundown_mainline_to_supabase(
    slate_date: str,
    *,
    writer: SupabaseMarketWriter | None = None,
    observed_at: str | None = None,
    hide_closed_markets: bool = True,
    raise_on_error: bool = True,
) -> dict[str, Any]:
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    writer = writer or SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    query_mode = "main_line"

    started_rows = writer.insert_rows("market_provider_runs", [{
        "provider": "therundown",
        "mode": "shadow_poll",
        "slate_date": slate_date,
        "status": "started",
        "metadata": {
            "script": SCRIPT_PATH,
            "query_mode": query_mode,
            "hide_closed_markets": hide_closed_markets,
            "target_affiliate_ids": list(TARGET_AFFILIATE_IDS),
        },
    }])
    run_id = started_rows[0]["id"]

    fetch_results: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    books_seen: set[str] = set()
    production_payload, production_artifact_path = _production_artifact_for_slate(
        slate_date,
        artifact_url=_production_artifact_url_from_env(),
    )
    request_count = 0

    try:
        for fetch_date in _slate_fetch_dates(slate_date):
            request_count += 1
            result = fetch_therundown_events(
                fetch_date,
                main_line=True,
                hide_closed_markets=hide_closed_markets,
            )
            fetch_results.append(result)
            events.extend(result.get("events") or [])
            time.sleep(THROTTLE_S)

        snapshots = snapshots_from_therundown_events(
            events,
            observed_at=observed_at,
            mainline_only=True,
        )
        for row in snapshots:
            row["run_id"] = run_id
            if row.get("bookmaker_key"):
                books_seen.add(str(row["bookmaker_key"]))

        event_rows = _event_rows(
            slate_date=slate_date,
            events=events,
            observed_at=observed_at,
        )
        writer.upsert_rows("market_events", event_rows, on_conflict="provider,provider_event_id")
        writer.upsert_rows("market_snapshots", snapshots, on_conflict="dedupe_key")
        writer.insert_rows("provider_coverage_audits", [
            _coverage_audit_row(
                run_id=run_id,
                slate_date=slate_date,
                snapshots=snapshots,
                books_seen=books_seen,
                observed_at=observed_at,
                production_payload=production_payload,
                production_artifact_path=production_artifact_path,
                fetch_results=fetch_results,
                query_mode=query_mode,
                hide_closed_markets=hide_closed_markets,
            )
        ])
        writer.upsert_rows("market_provider_runs", [{
            "id": run_id,
            "provider": "therundown",
            "mode": "shadow_poll",
            "slate_date": slate_date,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "request_count": request_count,
            "target_event_count": sum(len(result.get("events") or []) for result in fetch_results),
            "parsed_pitcher_prop_count": len({
                (snapshot["normalized_player_name"], snapshot["line"])
                for snapshot in snapshots
            }),
            "books_seen": sorted(books_seen),
            "metadata": _run_metadata(
                production_payload=production_payload,
                production_artifact_path=production_artifact_path,
                fetch_results=fetch_results,
                snapshot_count=len(snapshots),
                query_mode=query_mode,
                hide_closed_markets=hide_closed_markets,
            ),
        }], on_conflict="id")
    except Exception as exc:
        error_message = str(exc)[:1000]
        writer.upsert_rows("market_provider_runs", [{
            "id": run_id,
            "provider": "therundown",
            "mode": "shadow_poll",
            "slate_date": slate_date,
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "request_count": request_count,
            "target_event_count": sum(len(result.get("events") or []) for result in fetch_results),
            "parsed_pitcher_prop_count": len({
                (snapshot["normalized_player_name"], snapshot["line"])
                for snapshot in snapshots
            }),
            "books_seen": sorted(books_seen),
            "error_message": error_message,
            "metadata": _run_metadata(
                production_payload=production_payload,
                production_artifact_path=production_artifact_path,
                fetch_results=fetch_results,
                snapshot_count=len(snapshots),
                query_mode=query_mode,
                hide_closed_markets=hide_closed_markets,
            ),
        }], on_conflict="id")
        if raise_on_error:
            raise
        return {
            "run_id": run_id,
            "status": "failed",
            "request_count": request_count,
            "snapshot_count": len(snapshots),
            "books_seen": sorted(books_seen),
            "datapoints": sum(_integer(result.get("datapoints")) for result in fetch_results),
            "error": error_message,
        }

    return {
        "run_id": run_id,
        "status": "completed",
        "request_count": request_count,
        "target_event_count": sum(len(result.get("events") or []) for result in fetch_results),
        "snapshot_count": len(snapshots),
        "parsed_pitcher_prop_count": len({
            (snapshot["normalized_player_name"], snapshot["line"])
            for snapshot in snapshots
        }),
        "books_seen": sorted(books_seen),
        "datapoints": sum(_integer(result.get("datapoints")) for result in fetch_results),
    }


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("date", help="Slate date in YYYY-MM-DD format.")
    parser.add_argument(
        "--include-closed",
        action="store_true",
        help="Do not send hide_closed_markets=1. Default is live-window mainline only.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    result = poll_therundown_mainline_to_supabase(
        args.date,
        hide_closed_markets=not args.include_closed,
        raise_on_error=_env_flag("THERUNDOWN_MAINLINE_SHADOW_FAIL_ON_ERROR", False),
    )
    if result.get("status") == "failed":
        print(
            f"TheRundown mainline shadow ingest degraded date={args.date} "
            f"error={result.get('error', 'unknown')}",
            file=sys.stderr,
        )
        return 0
    print(
        f"TheRundown mainline shadow ingest date={args.date} "
        f"events={result['target_event_count']} snapshots={result['snapshot_count']} "
        f"parsed={result['parsed_pitcher_prop_count']} "
        f"datapoints={result['datapoints']} "
        f"books={','.join(result['books_seen']) or 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
