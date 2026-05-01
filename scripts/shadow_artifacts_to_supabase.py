"""Write selected JSON artifacts to Supabase sidecar tables.

This script is observation-only. It preserves raw JSON copies for audit/replay
and must not update production dashboard or pipeline outputs.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.artifact_snapshot import artifact_snapshot_row  # noqa: E402
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402

DEFAULT_ARTIFACTS = [
    "dashboard/data/processed/today.json",
    "dashboard/data/processed/steam.json",
    "dashboard/data/performance.json",
    "data/picks_history.json",
    "data/preview_lines.json",
    "data/params.json",
]


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _source_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _artifact_paths(args: list[str]) -> list[Path]:
    if args:
        return [ROOT / arg for arg in args]
    return [ROOT / arg for arg in DEFAULT_ARTIFACTS]


def main() -> int:
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    source_commit = _source_commit()
    rows = []

    for path in _artifact_paths(sys.argv[1:]):
        if not path.exists():
            continue
        rows.append(
            artifact_snapshot_row(
                path,
                repo_root=ROOT,
                source_commit=source_commit,
                metadata={"script": "scripts/shadow_artifacts_to_supabase.py"},
            )
        )

    writer.upsert_rows("artifact_snapshots", rows, on_conflict="artifact_path,content_sha256")
    print(f"Artifact shadow ingest snapshots={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
