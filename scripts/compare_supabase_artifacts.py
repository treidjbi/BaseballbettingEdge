"""Compare local dashboard artifact hashes with the Supabase artifact mirror.

This command is read-only. It is meant for artifact-exit parity checks before
any dashboard source or scheduler canary.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402
from scripts.publish_pipeline_artifacts_to_supabase import collect_artifact_rows  # noqa: E402


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def compare_hashes(*, local_sha: str, remote_sha: str | None) -> dict[str, object]:
    return {
        "matches": bool(remote_sha) and local_sha == remote_sha,
        "local_sha": local_sha,
        "remote_sha": remote_sha,
    }


def _fetch_remote_row(writer: Any, artifact_key: str) -> dict[str, Any] | None:
    rows = writer.select_rows(
        "published_pipeline_artifacts",
        {
            "artifact_key": f"eq.{artifact_key}",
            "select": "artifact_key,payload_sha256,published_at",
            "limit": "1",
        },
    )
    return rows[0] if rows else None


def run(
    *,
    root: Path,
    writer: Any,
    slate_date: str,
) -> list[dict[str, Any]]:
    local_rows = collect_artifact_rows(
        root=root,
        slate_date=slate_date,
        source="manual_backfill",
        source_run_id=None,
        source_commit_sha=None,
    )
    comparisons = []
    for local in local_rows:
        remote = _fetch_remote_row(writer, local["artifact_key"])
        comparison = compare_hashes(
            local_sha=local["payload_sha256"],
            remote_sha=(remote or {}).get("payload_sha256"),
        )
        status = "match" if comparison["matches"] else ("missing" if remote is None else "mismatch")
        comparisons.append({
            "artifact_key": local["artifact_key"],
            "status": status,
            "published_at": (remote or {}).get("published_at"),
            **comparison,
        })
    return comparisons


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    comparisons = run(root=ROOT, writer=writer, slate_date=args.date)
    ok = True
    for row in comparisons:
        if row["status"] != "match":
            ok = False
        print(
            "artifact_parity "
            f"status={row['status']} key={row['artifact_key']} "
            f"local_sha={row['local_sha']} remote_sha={row['remote_sha']} "
            f"published_at={row['published_at']}"
        )
    return 1 if args.strict and not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
