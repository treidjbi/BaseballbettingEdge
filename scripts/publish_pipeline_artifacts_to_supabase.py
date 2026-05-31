"""Publish dashboard JSON artifacts into the Supabase artifact mirror.

This is the Stage 1 artifact-exit publisher. It is dry-run by default and does
not change dashboard reads, GitHub artifact commits, or pipeline behavior.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_infra.published_artifacts import ARTIFACT_PATHS, build_artifact_row  # noqa: E402
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402

GRADING_ARTIFACT_PATHS = [
    Path("dashboard/data/performance.json"),
    Path("data/params.json"),
    Path("data/picks_history.json"),
]

PIPELINE_ARTIFACT_PATHS = [
    Path("dashboard/data/processed/today.json"),
    Path("dashboard/data/processed/index.json"),
    Path("dashboard/data/processed/steam.json"),
    Path("data/picks_history.json"),
]

PREVIEW_ARTIFACT_PATHS = [
    Path("dashboard/data/processed/index.json"),
    Path("data/preview_lines.json"),
]

LOCK_ARTIFACT_PATHS = [
    Path("dashboard/data/processed/today.json"),
    Path("data/picks_history.json"),
]


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def collect_artifact_rows(
    *,
    root: Path,
    slate_date: str,
    source: str,
    source_run_id: str | None,
    source_commit_sha: str | None,
    scope: str = "all",
    artifact_key_prefix: str = "",
) -> list[dict[str, Any]]:
    if scope == "all":
        paths = list(ARTIFACT_PATHS)
    elif scope == "pipeline":
        paths = list(PIPELINE_ARTIFACT_PATHS)
    elif scope == "grading":
        paths = list(GRADING_ARTIFACT_PATHS)
    elif scope == "preview":
        paths = list(PREVIEW_ARTIFACT_PATHS)
    elif scope == "lock":
        paths = list(LOCK_ARTIFACT_PATHS)
    else:
        raise ValueError(f"Unsupported artifact publish scope: {scope}")
    paths.append(Path("dashboard/data/processed") / f"{slate_date}.json")
    rows: list[dict[str, Any]] = []
    for relative in paths:
        path = root / relative
        if not path.exists():
            continue
        row = build_artifact_row(
            root=root,
            path=path,
            source=source,
            source_run_id=source_run_id,
            source_commit_sha=source_commit_sha,
        )
        if artifact_key_prefix:
            base_artifact_key = row["artifact_key"]
            row = {
                **row,
                "artifact_key": f"{artifact_key_prefix}{base_artifact_key}",
                "metadata": {
                    **row.get("metadata", {}),
                    "base_artifact_key": base_artifact_key,
                    "artifact_key_prefix": artifact_key_prefix,
                },
            }
        rows.append(row)
    return rows


def run(
    *,
    root: Path,
    writer,
    slate_date: str,
    source: str,
    source_run_id: str | None,
    source_commit_sha: str | None,
    execute: bool,
    scope: str = "all",
    artifact_key_prefix: str = "",
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    rows = collect_artifact_rows(
        root=root,
        slate_date=slate_date,
        source=source,
        source_run_id=source_run_id,
        source_commit_sha=source_commit_sha,
        scope=scope,
        artifact_key_prefix=artifact_key_prefix,
    )
    if execute:
        if writer is None:
            raise EnvironmentError("Supabase writer is required when --execute is set")
        published_at = datetime.now(timezone.utc).isoformat()
        rows_to_publish = [{**row, "published_at": published_at} for row in rows]
        writer.upsert_rows("published_pipeline_artifacts", rows_to_publish, on_conflict="artifact_key")
        completed_at = datetime.now(timezone.utc).isoformat()
        run_row = {
            "run_id": source_run_id or f"{source}:{slate_date}:{completed_at}",
            "source": source,
            "run_type": os.environ.get("PIPELINE_RUN_TYPE", "full"),
            "slate_date": slate_date,
            "status": "completed",
            "artifact_count": len(rows),
            "started_at": started_at,
            "completed_at": completed_at,
            "metadata": {
                "source_commit_sha": source_commit_sha,
                "artifact_key_prefix": artifact_key_prefix or None,
            },
        }
        writer.insert_rows("pipeline_artifact_publication_runs", [run_row])
    return {"artifact_count": len(rows), "execute": execute}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--source", default="github_actions")
    parser.add_argument("--source-run-id")
    parser.add_argument("--source-commit-sha")
    parser.add_argument("--scope", choices=("all", "pipeline", "grading", "preview", "lock"), default="all")
    parser.add_argument(
        "--artifact-key-prefix",
        default="",
        help="Optional prefix for shadow/candidate artifact keys.",
    )
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    writer = None
    if args.execute:
        writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    result = run(
        root=ROOT,
        writer=writer,
        slate_date=args.date,
        source=args.source,
        source_run_id=args.source_run_id,
        source_commit_sha=args.source_commit_sha,
        execute=args.execute,
        scope=args.scope,
        artifact_key_prefix=args.artifact_key_prefix,
    )
    mode = "execute" if args.execute else "dry_run"
    print(f"artifact_publish mode={mode} date={args.date} artifacts={result['artifact_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
