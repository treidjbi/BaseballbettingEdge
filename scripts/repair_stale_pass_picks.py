"""Repair stale unlocked picks that became PASS before lock.

This is a narrow data-repair utility for cases where an earlier same-day
non-PASS row survived in picks_history after a later pregame artifact made that
same pitcher/side PASS. It does not manufacture locks; it marks those stale
rows as PASS so grading, performance, and archive tracked-pick views stop
treating them as active picks.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

DEFAULT_ARTIFACT_API_URL = "https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact"
HISTORY_PATH = ROOT / "data" / "picks_history.json"
ARCHIVE_DIR = ROOT / "dashboard" / "data" / "processed"


def _artifact_url(base: str, artifact_type: str, date: str | None = None) -> str:
    params = {"type": artifact_type}
    if date:
        params["date"] = date
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{urlencode(params)}"


def _fetch_json(url: str) -> Any:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def hydrate_artifacts(*, dates: list[str], artifact_api_url: str) -> dict[str, dict]:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    history = _fetch_json(_artifact_url(artifact_api_url, "picks_history"))
    HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")

    archives: dict[str, dict] = {}
    for date in dates:
        archive = _fetch_json(_artifact_url(artifact_api_url, "dated_slate", date))
        (ARCHIVE_DIR / f"{date}.json").write_text(json.dumps(archive, indent=2), encoding="utf-8")
        archives[date] = archive

    for artifact_type, relative in [
        ("performance", Path("dashboard/data/performance.json")),
        ("params", Path("data/params.json")),
    ]:
        payload = _fetch_json(_artifact_url(artifact_api_url, artifact_type))
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return archives


def _effective_verdict(side_data: dict[str, Any]) -> str:
    return str(
        side_data.get("actionable_verdict")
        or side_data.get("verdict")
        or "PASS"
    ).strip() or "PASS"


def _pitcher_lookup(archive: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("pitcher") or "").strip().lower(): row
        for row in archive.get("pitchers", [])
        if isinstance(row, dict) and str(row.get("pitcher") or "").strip()
    }


def _side_key(side: str) -> str | None:
    side_value = str(side or "").strip().lower()
    if side_value == "over":
        return "ev_over"
    if side_value == "under":
        return "ev_under"
    return None


def _side_odds(pitcher_row: dict[str, Any], side: str) -> Any:
    return pitcher_row.get("best_over_odds" if side == "over" else "best_under_odds")


def _clear_archive_results(archives: dict[str, dict], dates: list[str]) -> None:
    for date in dates:
        archive = archives.get(date)
        if not archive:
            continue
        for pitcher in archive.get("pitchers", []):
            if not isinstance(pitcher, dict):
                continue
            pitcher.pop("result", None)
            for side_key in ("ev_over", "ev_under"):
                side_data = pitcher.get(side_key)
                if isinstance(side_data, dict):
                    side_data.pop("result", None)


def repair_history_against_archives(
    history: list[dict[str, Any]],
    archives: dict[str, dict],
    dates: list[str],
) -> list[dict[str, str]]:
    date_set = set(dates)
    archive_lookup = {date: _pitcher_lookup(archive) for date, archive in archives.items()}
    repaired: list[dict[str, str]] = []

    for pick in history:
        date = str(pick.get("date") or "")
        if date not in date_set:
            continue
        if pick.get("locked_at") or pick.get("verdict") == "PASS":
            continue

        side = str(pick.get("side") or "").strip().lower()
        side_field = _side_key(side)
        if not side_field:
            continue

        pitcher = str(pick.get("pitcher") or "").strip()
        pitcher_row = archive_lookup.get(date, {}).get(pitcher.lower())
        side_data = pitcher_row.get(side_field) if isinstance(pitcher_row, dict) else None
        if not isinstance(side_data, dict) or _effective_verdict(side_data) != "PASS":
            continue

        previous_verdict = str(pick.get("verdict") or "")
        pick["verdict"] = "PASS"
        pick["raw_verdict"] = side_data.get("raw_verdict") or side_data.get("verdict") or "PASS"
        pick["actionable_verdict"] = side_data.get("actionable_verdict") or "PASS"
        pick["edge"] = side_data.get("edge")
        pick["ev"] = side_data.get("ev")
        pick["adj_ev"] = side_data.get("adj_ev")
        pick["raw_adj_ev"] = side_data.get("raw_adj_ev", side_data.get("adj_ev"))
        pick["k_line"] = pitcher_row.get("k_line", pick.get("k_line"))
        pick["odds"] = _side_odds(pitcher_row, side)
        pick["result"] = None
        pick["actual_ks"] = None
        pick["pnl"] = None
        pick["fetched_at"] = None

        repaired.append(
            {
                "date": date,
                "pitcher": pitcher,
                "side": side,
                "previous_verdict": previous_verdict,
            }
        )

    if repaired:
        _clear_archive_results(archives, dates)
    return repaired


def _write_repaired_files(history: list[dict[str, Any]], archives: dict[str, dict]) -> None:
    HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")
    for date, archive in archives.items():
        (ARCHIVE_DIR / f"{date}.json").write_text(json.dumps(archive, indent=2), encoding="utf-8")


def _rebuild_derived_artifacts(*, include_dates: list[str]) -> None:
    import calibrate
    import fetch_results
    import run_pipeline

    fetch_results.reset_db()
    fetch_results.init_db()
    fetch_results.load_history_into_db(HISTORY_PATH)
    calibrate.run()
    run_pipeline._enrich_archives_with_results()
    run_pipeline._enrich_archives_with_tracked_picks(include_today=False)
    run_pipeline._refresh_index_json()


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _source_commit_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _publish_repaired_artifacts(*, dates: list[str], source_run_id: str) -> None:
    from market_infra.supabase_writer import SupabaseMarketWriter
    from scripts.publish_pipeline_artifacts_to_supabase import run as publish_artifacts

    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    previous = os.environ.get("PIPELINE_RUN_TYPE")
    os.environ["PIPELINE_RUN_TYPE"] = "grading"
    try:
        for date in dates:
            publish_artifacts(
                root=ROOT,
                writer=writer,
                slate_date=date,
                source="render_pipeline",
                source_run_id=f"{source_run_id}-{date}",
                source_commit_sha=_source_commit_sha(),
                execute=True,
                scope="grading",
            )
    finally:
        if previous is None:
            os.environ.pop("PIPELINE_RUN_TYPE", None)
        else:
            os.environ["PIPELINE_RUN_TYPE"] = previous


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dates", nargs="+", required=True)
    parser.add_argument("--artifact-api-url", default=DEFAULT_ARTIFACT_API_URL)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--source-run-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    dates = sorted(set(args.dates))
    archives = hydrate_artifacts(dates=dates, artifact_api_url=args.artifact_api_url)
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    repaired = repair_history_against_archives(history, archives, dates)
    _write_repaired_files(history, archives)
    _rebuild_derived_artifacts(include_dates=dates)

    source_run_id = args.source_run_id or f"manual-stale-pass-repair-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    if args.publish:
        _publish_repaired_artifacts(dates=dates, source_run_id=source_run_id)

    print(
        "stale_pass_repair "
        f"dates={','.join(dates)} repaired={len(repaired)} publish={str(args.publish).lower()} "
        f"source_run_id={source_run_id}"
    )
    for row in repaired:
        print(
            "stale_pass_repair_row "
            f"date={row['date']} pitcher={row['pitcher']} side={row['side']} "
            f"previous_verdict={row['previous_verdict']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
