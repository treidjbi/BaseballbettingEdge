"""Export bounded compact inputs for shadow-only market-agreement research.

The exporter performs read-only Supabase and production-artifact requests. It
never reads raw market_snapshots and never writes to Supabase or live BBE
artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analytics.diagnostics import pitcher_k_outcome_dataset as dataset  # noqa: E402
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


COMPACT_TABLES = ("market_pick_evidence", "live_market_display_state")
DEFAULT_OUTPUT_DIR = ROOT / "analytics" / "output" / "market_agreement_inputs"
DEFAULT_ARTIFACT_API_URL = dataset.DEFAULT_ARTIFACT_API_URL
DEFAULT_PAGE_SIZE = 1000
PHOENIX_TZ = ZoneInfo("America/Phoenix")
OUTPUT_FILENAMES = (
    "market_pick_evidence.json",
    "live_market_display_state.json",
    "picks_history.json",
    "today.json",
    "manifest.json",
)
TABLE_ORDER = (
    "slate_date.asc,normalized_pitcher.asc,side.asc,"
    "provider.asc,observed_at.asc,id.asc"
)


def _validate_date_range(start_date: str, end_date: str) -> None:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as error:
        raise ValueError("start_date and end_date must use YYYY-MM-DD") from error
    if end < start:
        raise ValueError("end_date must be on or after start_date")


def _date_filter(start_date: str, end_date: str) -> dict[str, str]:
    return {
        "and": f"(slate_date.gte.{start_date},slate_date.lte.{end_date})",
    }


def _table_params(
    start_date: str,
    end_date: str,
    limit: int,
    offset: int,
) -> dict[str, str]:
    return {
        "select": "*",
        **_date_filter(start_date, end_date),
        "order": TABLE_ORDER,
        "limit": str(limit),
        "offset": str(offset),
    }


def _dedupe_identity(row: dict[str, Any]) -> str:
    identity = str(row.get("id") or row.get("dedupe_key") or "").strip()
    if not identity:
        raise ValueError("compact table row is missing id and dedupe_key")
    return identity


def _collect_table_rows(
    *,
    writer: SupabaseMarketWriter,
    table: str,
    start_date: str,
    end_date: str,
    page_size: int,
) -> list[dict[str, Any]]:
    exact_count = writer.count_rows(table, _date_filter(start_date, end_date))
    collected: list[dict[str, Any]] = []
    for offset in range(0, exact_count, page_size):
        page = writer.select_rows(
            table,
            _table_params(start_date, end_date, page_size, offset),
        )
        if not isinstance(page, list):
            raise ValueError(f"{table} returned a non-list page")
        for row in page:
            if not isinstance(row, dict):
                raise ValueError(f"{table} returned a non-object row")
            collected.append(row)

    deduped: dict[str, dict[str, Any]] = {}
    for row in collected:
        identity = _dedupe_identity(row)
        deduped.setdefault(identity, row)
    rows = list(deduped.values())
    if len(rows) != exact_count:
        raise ValueError(
            f"{table} exact count mismatch: expected {exact_count}, fetched {len(rows)}"
        )
    return rows


def _bounded_history_rows(
    payload: Any,
    *,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("picks_history artifact must be a list")
    rows: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            raise ValueError("picks_history artifact contains a non-object row")
        slate_date = str(row.get("date") or row.get("slate_date") or "").strip()
        if start_date <= slate_date <= end_date:
            rows.append(row)
    return rows


def _date_span(rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    dates = sorted(
        {
            str(row.get("slate_date") or row.get("date") or "").strip()
            for row in rows
            if str(row.get("slate_date") or row.get("date") or "").strip()
        }
    )
    return (dates[0], dates[-1]) if dates else (None, None)


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _replace_outputs_atomically(
    *,
    output_dir: Path,
    payloads: dict[str, bytes],
) -> None:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}-staging-",
            dir=output_dir.parent,
        )
    )
    backup_dir = staging_dir / "prior"
    try:
        for filename, payload in payloads.items():
            staged_path = staging_dir / filename
            staged_path.write_bytes(payload)
            if _sha256_bytes(staged_path.read_bytes()) != _sha256_bytes(payload):
                raise OSError(f"staged hash verification failed for {filename}")

        output_dir.mkdir(parents=True, exist_ok=True)
        backup_dir.mkdir()
        prior_files: set[str] = set()
        for filename in payloads:
            final_path = output_dir / filename
            if final_path.exists():
                shutil.copy2(final_path, backup_dir / filename)
                prior_files.add(filename)

        replaced: list[str] = []
        try:
            for filename in payloads:
                (staging_dir / filename).replace(output_dir / filename)
                replaced.append(filename)
        except Exception:
            for filename in replaced:
                final_path = output_dir / filename
                backup_path = backup_dir / filename
                if filename in prior_files:
                    backup_path.replace(final_path)
                elif final_path.exists():
                    final_path.unlink()
            raise
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def export_inputs(
    *,
    writer: SupabaseMarketWriter,
    artifact_loader: Callable[[str], Any],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    start_date: str = dataset.CLEAN_WINDOW_START,
    end_date: str,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    _validate_date_range(start_date, end_date)
    if page_size <= 0 or page_size > 1000:
        raise ValueError("page_size must be between 1 and 1000")

    table_rows = {
        table: _collect_table_rows(
            writer=writer,
            table=table,
            start_date=start_date,
            end_date=end_date,
            page_size=page_size,
        )
        for table in COMPACT_TABLES
    }
    history_rows = _bounded_history_rows(
        artifact_loader("picks_history"),
        start_date=start_date,
        end_date=end_date,
    )
    today_payload = artifact_loader("today")
    if not isinstance(today_payload, dict):
        raise ValueError("today artifact must be an object")

    data_payloads = {
        "market_pick_evidence.json": _json_bytes(table_rows["market_pick_evidence"]),
        "live_market_display_state.json": _json_bytes(
            table_rows["live_market_display_state"]
        ),
        "picks_history.json": _json_bytes(history_rows),
        "today.json": _json_bytes(today_payload),
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    manifest: dict[str, Any] = {
        "artifact": "market_agreement_inputs",
        "generated_at": generated_at,
        "shadow_only": True,
        "start_date": start_date,
        "end_date": end_date,
        "tables": {},
        "artifacts": {
            "picks_history": {"rows": len(history_rows)},
            "today": {"slate_date": today_payload.get("slate_date")},
        },
        "files": {
            filename: {"sha256": _sha256_bytes(payload)}
            for filename, payload in data_payloads.items()
        },
        "guardrails": [
            "read_only",
            "compact_tables_only",
            "no_market_snapshots",
            "no_live_behavior_change",
        ],
    }
    for table, rows in table_rows.items():
        min_date, max_date = _date_span(rows)
        manifest["tables"][table] = {
            "rows": len(rows),
            "min_date": min_date,
            "max_date": max_date,
        }

    _replace_outputs_atomically(
        output_dir=output_dir,
        payloads={
            **data_payloads,
            "manifest.json": _json_bytes(manifest),
        },
    )
    return manifest


def _load_artifact(base_url: str, artifact_type: str) -> Any:
    url = dataset.artifact_api_url(base_url, artifact_type)
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-date", default=dataset.CLEAN_WINDOW_START)
    parser.add_argument(
        "--end-date",
        default=datetime.now(PHOENIX_TZ).date().isoformat(),
    )
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument(
        "--artifact-api-url",
        default=os.environ.get("BBE_ARTIFACT_API_URL", "").strip()
        or DEFAULT_ARTIFACT_API_URL,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    writer = SupabaseMarketWriter(
        _required_env("SUPABASE_URL"),
        _required_env("SUPABASE_SERVICE_ROLE_KEY"),
    )
    manifest = export_inputs(
        writer=writer,
        artifact_loader=lambda artifact_type: _load_artifact(
            args.artifact_api_url,
            artifact_type,
        ),
        output_dir=args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        page_size=args.page_size,
    )
    print(
        "Exported shadow market-agreement inputs: "
        f"market_pick_evidence={manifest['tables']['market_pick_evidence']['rows']} "
        f"live_market_display_state={manifest['tables']['live_market_display_state']['rows']} "
        f"dates={manifest['start_date']}..{manifest['end_date']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
