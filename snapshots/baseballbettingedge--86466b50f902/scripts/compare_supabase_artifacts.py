"""Compare local dashboard artifact hashes with the Supabase artifact mirror.

This command is read-only. It is meant for artifact-exit parity checks before
any dashboard source or scheduler canary.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
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


def parse_supabase_cli_rows(output: str) -> list[dict[str, Any]]:
    payload = json.loads(output)
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("Supabase CLI output did not include a rows array")
    return rows


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def resolve_npx_command() -> str:
    return shutil.which("npx") or shutil.which("npx.cmd") or "npx"


def _fetch_remote_rows_with_cli(artifact_keys: list[str]) -> list[dict[str, Any]]:
    key_list = ", ".join(_sql_literal(key) for key in artifact_keys)
    sql = (
        "select artifact_key, payload_sha256, published_at "
        "from public.published_pipeline_artifacts "
        f"where artifact_key in ({key_list}) "
        "order by artifact_key;"
    )
    result = subprocess.run(
        [resolve_npx_command(), "supabase", "db", "query", "--linked", "-o", "json", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_supabase_cli_rows(result.stdout)


def compare_local_to_remote_rows(
    local_rows: list[dict[str, Any]],
    remote_rows: list[dict[str, Any]],
    *,
    remote_key_prefix: str = "",
) -> list[dict[str, Any]]:
    remote_by_key = {row["artifact_key"]: row for row in remote_rows}
    comparisons = []
    for local in local_rows:
        remote_key = f"{remote_key_prefix}{local['artifact_key']}"
        remote = remote_by_key.get(remote_key)
        comparison = compare_hashes(
            local_sha=local["payload_sha256"],
            remote_sha=(remote or {}).get("payload_sha256"),
        )
        status = "match" if comparison["matches"] else ("missing" if remote is None else "mismatch")
        comparisons.append({
            "artifact_key": local["artifact_key"],
            "remote_artifact_key": remote_key,
            "status": status,
            "published_at": (remote or {}).get("published_at"),
            **comparison,
        })
    return comparisons


def run(
    *,
    root: Path,
    writer: Any,
    slate_date: str,
    remote_key_prefix: str = "",
) -> list[dict[str, Any]]:
    local_rows = collect_artifact_rows(
        root=root,
        slate_date=slate_date,
        source="manual_backfill",
        source_run_id=None,
        source_commit_sha=None,
    )
    remote_rows = [
        row
        for row in (_fetch_remote_row(writer, f"{remote_key_prefix}{local['artifact_key']}") for local in local_rows)
        if row is not None
    ]
    return compare_local_to_remote_rows(local_rows, remote_rows, remote_key_prefix=remote_key_prefix)


def run_with_linked_cli(*, root: Path, slate_date: str, remote_key_prefix: str = "") -> list[dict[str, Any]]:
    local_rows = collect_artifact_rows(
        root=root,
        slate_date=slate_date,
        source="manual_backfill",
        source_run_id=None,
        source_commit_sha=None,
    )
    remote_rows = _fetch_remote_rows_with_cli([f"{remote_key_prefix}{row['artifact_key']}" for row in local_rows])
    return compare_local_to_remote_rows(local_rows, remote_rows, remote_key_prefix=remote_key_prefix)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument(
        "--remote-key-prefix",
        default="",
        help="Optional prefix used by shadow/candidate rows in Supabase.",
    )
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if os.environ.get("SUPABASE_URL", "").strip() and os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip():
        writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
        comparisons = run(root=ROOT, writer=writer, slate_date=args.date, remote_key_prefix=args.remote_key_prefix)
    else:
        comparisons = run_with_linked_cli(root=ROOT, slate_date=args.date, remote_key_prefix=args.remote_key_prefix)
    ok = True
    for row in comparisons:
        if row["status"] != "match":
            ok = False
        print(
            "artifact_parity "
            f"status={row['status']} key={row['artifact_key']} "
            f"remote_key={row['remote_artifact_key']} "
            f"local_sha={row['local_sha']} remote_sha={row['remote_sha']} "
            f"published_at={row['published_at']}"
        )
    return 1 if args.strict and not ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
