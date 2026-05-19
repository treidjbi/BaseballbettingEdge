"""Read-only monitor for Supabase operational lock-ledger rollout."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.operational_locks import build_operational_lock_rows  # noqa: E402
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


DEFAULT_ARTIFACT_URL = (
    "https://raw.githubusercontent.com/treidjbi/BaseballBettingEdge/"
    "main/dashboard/data/processed/today.json"
)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _row_key(row: dict[str, Any]) -> str:
    return str(
        row.get("dedupe_key")
        or f"{row.get('slate_date')}:{row.get('normalized_pitcher')}:{row.get('side')}"
    )


def _load_json(source: str) -> dict[str, Any]:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _fetch_ledger_rows(writer: SupabaseMarketWriter, slate_date: str) -> list[dict[str, Any]]:
    return writer.select_rows(
        "operational_pick_locks",
        {
            "select": (
                "dedupe_key,slate_date,normalized_pitcher,side,status_at_capture,"
                "observed_at,locked_at,game_time,should_lock_at,source_artifact_path,inserted_at"
            ),
            "slate_date": f"eq.{slate_date}",
            "order": "inserted_at.desc",
        },
    )


def _fetch_shadow_runs(writer: SupabaseMarketWriter, slate_date: str) -> list[dict[str, Any]]:
    return writer.select_rows(
        "shadow_pipeline_runs",
        {
            "select": (
                "slate_date,artifact_generated_at,observed_at,tracked_pick_count,"
                "artifact_locked_pick_count,due_now_count,missed_lock_count,"
                "started_unlocked_count,missing_game_time_count,source_artifact_path"
            ),
            "slate_date": f"eq.{slate_date}",
            "order": "observed_at.desc",
            "limit": "3",
        },
    )


def summarize(
    *,
    slate_date: str,
    observed_at: datetime,
    artifact_generated_at: str | None,
    expected_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    shadow_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_keys = {_row_key(row) for row in expected_rows}
    ledger_keys = {_row_key(row) for row in ledger_rows}
    missing_keys = sorted(expected_keys - ledger_keys)
    latest_shadow_run = shadow_runs[0] if shadow_runs else None

    if expected_keys and missing_keys:
        status = "gap"
    elif expected_keys:
        status = "ok"
    else:
        status = "waiting"

    return {
        "status": status,
        "slate_date": slate_date,
        "observed_at": observed_at.astimezone(timezone.utc).isoformat(),
        "artifact_generated_at": artifact_generated_at,
        "expected_lock_rows": len(expected_rows),
        "ledger_rows": len(ledger_rows),
        "matched_expected_rows": len(expected_keys & ledger_keys),
        "missing_expected_keys": missing_keys,
        "latest_shadow_run": latest_shadow_run,
        "expected_rows": expected_rows,
        "ledger_rows_detail": ledger_rows,
    }


def run_monitor(
    *,
    writer: SupabaseMarketWriter,
    artifact: dict[str, Any],
    slate_date: str,
    observed_at: datetime,
    artifact_source: str,
) -> dict[str, Any]:
    expected_rows = build_operational_lock_rows(
        slate_date=slate_date,
        pitchers=artifact.get("pitchers") or [],
        observed_at=observed_at,
        source_artifact_path=artifact_source,
        source_artifact_sha256=None,
        artifact_generated_at=artifact.get("generated_at"),
    )
    ledger_rows = _fetch_ledger_rows(writer, slate_date)
    shadow_runs = _fetch_shadow_runs(writer, slate_date)
    return summarize(
        slate_date=slate_date,
        observed_at=observed_at,
        artifact_generated_at=artifact.get("generated_at"),
        expected_rows=expected_rows,
        ledger_rows=ledger_rows,
        shadow_runs=shadow_runs,
    )


def render_summary(summary: dict[str, Any]) -> str:
    latest_shadow = summary.get("latest_shadow_run") or {}
    lines = [
        (
            "lock_ledger_monitor "
            f"status={summary['status']} "
            f"date={summary['slate_date']} "
            f"observed_at={summary['observed_at']}"
        ),
        (
            "counts "
            f"expected={summary['expected_lock_rows']} "
            f"ledger={summary['ledger_rows']} "
            f"matched={summary['matched_expected_rows']} "
            f"missing={len(summary['missing_expected_keys'])}"
        ),
    ]
    if latest_shadow:
        lines.append(
            "latest_shadow "
            f"observed_at={latest_shadow.get('observed_at')} "
            f"tracked={latest_shadow.get('tracked_pick_count')} "
            f"locked={latest_shadow.get('artifact_locked_pick_count')} "
            f"due_now={latest_shadow.get('due_now_count')} "
            f"missed={latest_shadow.get('missed_lock_count')} "
            f"started_unlocked={latest_shadow.get('started_unlocked_count')}"
        )
    if summary["missing_expected_keys"]:
        lines.append("missing_expected_keys=" + ",".join(summary["missing_expected_keys"]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Slate date; defaults to artifact date")
    parser.add_argument("--artifact-url", default=DEFAULT_ARTIFACT_URL)
    parser.add_argument("--observed-at", help="UTC ISO timestamp; defaults to now")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if due rows are missing")
    args = parser.parse_args(argv)

    artifact = _load_json(args.artifact_url)
    slate_date = args.date or str(artifact["date"])
    observed_at = _parse_datetime(args.observed_at)
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    summary = run_monitor(
        writer=writer,
        artifact=artifact,
        slate_date=slate_date,
        observed_at=observed_at,
        artifact_source=args.artifact_url,
    )
    print(render_summary(summary))
    if args.strict and summary["status"] == "gap":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
