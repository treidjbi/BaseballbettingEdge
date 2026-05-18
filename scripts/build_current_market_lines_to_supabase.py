"""Build current supported-book market lines from Supabase snapshots."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.current_market_lines import (  # noqa: E402
    build_current_market_lines,
    build_opening_baseline_rows,
)
from market_infra.provider_usage import (  # noqa: E402
    build_provider_usage_rows,
    write_provider_usage_rows,
)
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402
from pipeline.name_utils import normalize  # noqa: E402

DEFAULT_ARTIFACT_URL = (
    "https://raw.githubusercontent.com/treidjbi/BaseballBettingEdge/"
    "main/dashboard/data/processed/today.json"
)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _run_id_filter(run_rows: list[dict[str, Any]]) -> str:
    run_ids = [str(row.get("id")) for row in run_rows if row.get("id")]
    return f"in.({','.join(run_ids)})"


def _run_id_filter_from_ids(run_ids: list[str]) -> str:
    return f"in.({','.join(run_ids)})"


def _fetch_inputs(
    writer: SupabaseMarketWriter,
    slate_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    run_rows = writer.select_rows(
        "market_provider_runs",
        {
            "slate_date": f"eq.{slate_date}",
            "provider": "in.(boltodds,propline,the_odds,therundown)",
            "order": "created_at.desc",
            "limit": "250",
        },
    )
    run_rows = _merge_heartbeat_run_rows(writer, slate_date, run_rows)
    if not run_rows:
        return [], []

    snapshot_rows = _fetch_snapshot_pages(writer, run_rows)
    return snapshot_rows, run_rows


def _merge_heartbeat_run_rows(
    writer: SupabaseMarketWriter,
    slate_date: str,
    run_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Include rotated worker runs whose heartbeats advanced before run rows did."""
    rows_by_id = {
        str(row.get("id")): dict(row)
        for row in run_rows
        if row.get("id")
    }
    heartbeat_rows = writer.select_rows(
        "market_feed_heartbeats",
        {
            "slate_date": f"eq.{slate_date}",
            "provider": "in.(boltodds,propline,the_odds,therundown)",
            "order": "observed_at.desc",
            "limit": "250",
        },
    )
    heartbeat_run_ids = []
    for row in heartbeat_rows:
        run_id = str(row.get("run_id") or "")
        if run_id and run_id not in rows_by_id and run_id not in heartbeat_run_ids:
            heartbeat_run_ids.append(run_id)

    if heartbeat_run_ids:
        extra_rows = writer.select_rows(
            "market_provider_runs",
            {
                "id": _run_id_filter_from_ids(heartbeat_run_ids),
                "order": "created_at.desc",
                "limit": str(len(heartbeat_run_ids)),
            },
        )
        for row in extra_rows:
            run_id = str(row.get("id") or "")
            if not run_id:
                continue
            normalized = dict(row)
            normalized["slate_date"] = slate_date
            rows_by_id[run_id] = normalized

    return list(rows_by_id.values())


def _fetch_snapshot_pages(
    writer: SupabaseMarketWriter,
    run_rows: list[dict[str, Any]],
    *,
    page_size: int = 1000,
    max_pages: int = 20,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    run_filter = _run_id_filter(run_rows)
    for page in range(max_pages):
        page_rows = writer.select_rows(
            "market_snapshots",
            {
                "run_id": run_filter,
                "order": "observed_at.desc",
                "limit": str(page_size),
                "offset": str(page * page_size),
            },
        )
        rows.extend(page_rows)
        if len(page_rows) < page_size:
            break
    return rows


def _fetch_live_pick_state_rows(
    writer: SupabaseMarketWriter,
    slate_date: str,
) -> list[dict[str, Any]]:
    return writer.select_rows(
        "live_pick_state",
        {
            "slate_date": f"eq.{slate_date}",
            "order": "updated_at.desc",
            "limit": "1000",
        },
    )


def _load_artifact_payload_for_game_times(
    slate_date: str,
    *,
    artifact_url: str | None = None,
    root: Path = ROOT,
) -> tuple[dict[str, Any] | None, str | None]:
    if artifact_url:
        try:
            with urlopen(artifact_url, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if str(payload.get("date") or "").strip() == slate_date:
                return payload, artifact_url
        except Exception as error:
            print(
                f"Warning: market-line artifact fetch failed ({error}); falling back to local artifact",
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
        if str(payload.get("date") or "").strip() != slate_date:
            continue
        return payload, relative_path.as_posix()
    return None, None


def _enrich_game_times_from_live_pick_state(
    current_rows: list[dict[str, Any]],
    live_pick_state_rows: list[dict[str, Any]],
) -> int:
    game_times_by_pitcher: dict[str, dict[str, Any]] = {}
    for row in live_pick_state_rows:
        game_time = row.get("game_time")
        if not game_time:
            continue
        normalized_pitcher = str(row.get("normalized_pitcher") or "").strip()
        if not normalized_pitcher:
            normalized_pitcher = normalize(row.get("pitcher") or "")
        if not normalized_pitcher:
            continue
        game_times_by_pitcher.setdefault(normalized_pitcher, {
            "game_time": str(game_time),
            "source_artifact_path": row.get("source_artifact_path"),
        })

    enriched = 0
    for row in current_rows:
        if row.get("game_time"):
            continue
        normalized_player = str(row.get("normalized_player_name") or "").strip()
        game_time_info = game_times_by_pitcher.get(normalized_player)
        if not game_time_info:
            continue
        row["game_time"] = game_time_info["game_time"]
        raw_payload = row.get("raw_payload")
        if not isinstance(raw_payload, dict):
            raw_payload = {}
            row["raw_payload"] = raw_payload
        raw_payload["game_time_source"] = {
            "source": "live_pick_state",
            "source_artifact_path": game_time_info.get("source_artifact_path"),
        }
        enriched += 1
    return enriched


def _enrich_game_times_from_artifact(
    current_rows: list[dict[str, Any]],
    artifact_payload: dict[str, Any] | None,
    *,
    source_artifact_path: str | None,
) -> int:
    game_times_by_pitcher: dict[str, dict[str, Any]] = {}
    for pitcher in (artifact_payload or {}).get("pitchers") or []:
        if not isinstance(pitcher, dict):
            continue
        game_time = pitcher.get("game_time")
        if not game_time:
            continue
        normalized_pitcher = normalize(pitcher.get("pitcher") or "")
        if not normalized_pitcher:
            continue
        game_times_by_pitcher.setdefault(normalized_pitcher, {
            "game_time": str(game_time),
            "source_artifact_path": source_artifact_path,
        })

    enriched = 0
    for row in current_rows:
        if row.get("game_time"):
            continue
        normalized_player = str(row.get("normalized_player_name") or "").strip()
        game_time_info = game_times_by_pitcher.get(normalized_player)
        if not game_time_info:
            continue
        row["game_time"] = game_time_info["game_time"]
        raw_payload = row.get("raw_payload")
        if not isinstance(raw_payload, dict):
            raw_payload = {}
            row["raw_payload"] = raw_payload
        raw_payload["game_time_source"] = {
            "source": "production_artifact",
            "source_artifact_path": game_time_info.get("source_artifact_path"),
        }
        enriched += 1
    return enriched


def run(
    *,
    slate_date: str,
    writer: SupabaseMarketWriter,
    dry_run: bool,
    now_utc: datetime | None = None,
    stale_after_seconds: int = 900,
    artifact_payload: dict[str, Any] | None = None,
    artifact_source: str | None = None,
    artifact_url: str | None = None,
) -> dict[str, Any]:
    snapshot_rows, run_rows = _fetch_inputs(writer, slate_date)
    current_rows = build_current_market_lines(
        snapshot_rows=snapshot_rows,
        run_rows=run_rows,
        now_utc=now_utc or _now_utc(),
        stale_after_seconds=stale_after_seconds,
    )
    live_pick_state_rows = _fetch_live_pick_state_rows(writer, slate_date)
    live_state_enriched = _enrich_game_times_from_live_pick_state(current_rows, live_pick_state_rows)
    if artifact_payload is None:
        env_artifact_url = (
            artifact_url
            or os.environ.get("MARKET_LINE_ARTIFACT_URL", "").strip()
            or os.environ.get("LIVE_ARTIFACT_URL", "").strip()
        )
        artifact_payload, artifact_source = _load_artifact_payload_for_game_times(
            slate_date,
            artifact_url=env_artifact_url or None,
        )
    artifact_enriched = _enrich_game_times_from_artifact(
        current_rows,
        artifact_payload,
        source_artifact_path=artifact_source,
    )
    game_time_enriched = live_state_enriched + artifact_enriched
    complete_rows = [row for row in current_rows if row["is_complete"]]
    stale_rows = [row for row in current_rows if "stale" in row["quality_flags"]]
    baseline_rows = build_opening_baseline_rows(current_rows)
    provider_usage_rows = build_provider_usage_rows(
        run_rows=run_rows,
        snapshot_rows=snapshot_rows,
        usage_date=slate_date,
    )

    written_rows: list[dict[str, Any]] = []
    written_baselines: list[dict[str, Any]] = []
    written_usage_rows: list[dict[str, Any]] = []
    if not dry_run:
        written_rows = writer.upsert_rows(
            "current_market_lines",
            current_rows,
            on_conflict="slate_date,provider,book_key,normalized_player_name,market_key,line",
        )
        written_baselines = writer.insert_ignore_rows(
            "market_opening_baselines",
            baseline_rows,
            on_conflict="slate_date,normalized_player_name,market_key,book_key,line",
        )
        written_usage_rows = write_provider_usage_rows(
            writer,
            provider_usage_rows,
            enforce_propline_budget=(
                os.environ.get("ENFORCE_PROPLINE_DAILY_BUDGET", "false").strip().lower()
                in {"1", "true", "yes", "on"}
            ),
        )

    return {
        "slate_date": slate_date,
        "snapshot_rows": len(snapshot_rows),
        "provider_runs": len(run_rows),
        "current_market_lines": len(current_rows),
        "complete_rows": len(complete_rows),
        "stale_rows": len(stale_rows),
        "game_time_enriched": game_time_enriched,
        "game_time_live_state_enriched": live_state_enriched,
        "game_time_artifact_enriched": artifact_enriched,
        "game_time_artifact_source": artifact_source,
        "opening_baselines": len(baseline_rows),
        "provider_usage_rows": len(provider_usage_rows),
        "provider_usage_warnings": len(written_usage_rows),
        "written_rows": len(written_rows),
        "written_baselines": len(written_baselines),
        "dry_run": dry_run,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Slate date in YYYY-MM-DD format.")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing rows.")
    parser.add_argument(
        "--stale-after-seconds",
        type=int,
        default=900,
        help="Freshness threshold for stale quality flags.",
    )
    parser.add_argument(
        "--artifact-url",
        default=os.environ.get("MARKET_LINE_ARTIFACT_URL", "").strip() or DEFAULT_ARTIFACT_URL,
        help="Optional current today.json URL used to fill provider rows missing game_time.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    result = run(
        slate_date=args.date,
        writer=writer,
        dry_run=args.dry_run,
        stale_after_seconds=args.stale_after_seconds,
        artifact_url=args.artifact_url or None,
    )
    action = "dry_run" if args.dry_run else "upsert"
    print(
        "Current market line build "
        f"action={action} date={result['slate_date']} "
        f"provider_runs={result['provider_runs']} "
        f"snapshots={result['snapshot_rows']} "
        f"lines={result['current_market_lines']} "
        f"complete={result['complete_rows']} "
        f"stale={result['stale_rows']} "
        f"game_time_enriched={result['game_time_enriched']} "
        f"game_time_artifact_enriched={result['game_time_artifact_enriched']} "
        f"opening_baselines={result['opening_baselines']} "
        f"provider_usage={result['provider_usage_rows']} "
        f"written={result['written_rows']}"
        f" written_baselines={result['written_baselines']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
