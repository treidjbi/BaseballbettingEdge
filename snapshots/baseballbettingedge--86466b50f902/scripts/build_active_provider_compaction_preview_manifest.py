"""Build one aggregate-only active-provider compaction preview from audit checkpoints."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable


DEFAULT_PROVIDERS = ("propline", "therundown")


def _strict_nonnegative_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a nonnegative integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a nonnegative integer") from error
    if parsed < 0 or parsed != value:
        raise ValueError(f"{label} must be a nonnegative integer")
    return parsed


def _contiguous_dates(start: str, end: str) -> list[str]:
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if end_date < start_date:
        raise ValueError("checkpoint date range is reversed")
    result = []
    current = start_date
    while current <= end_date:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def _load_coverage(
    checkpoint_dir: Path,
    *,
    providers: tuple[str, ...],
) -> tuple[dict[tuple[str, str], dict[str, Any]], str, str]:
    requested = set(providers)
    rows_by_partition: dict[tuple[str, str], dict[str, Any]] = {}
    contract_hashes: set[str] = set()
    audit_dates: set[str] = set()
    checkpoint_count = 0

    for path in sorted(checkpoint_dir.glob("checkpoint-*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        checkpoint_provider = str(document.get("provider") or "").strip().lower()
        if checkpoint_provider not in requested:
            continue
        checkpoint_count += 1
        payload = document.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(f"checkpoint payload is missing: {path.name}")
        if (
            document.get("status") != "completed"
            or document.get("complete") is not True
            or document.get("validation") != "passed"
        ):
            raise ValueError(f"checkpoint is not complete: {path.name}")
        if payload.get("complete") is not True:
            raise ValueError(f"checkpoint payload is not complete: {path.name}")
        contract_hash = str(document.get("query_contract_sha256") or "").strip()
        audit_date = str(document.get("as_of_date") or "").strip()
        if not contract_hash or not audit_date:
            raise ValueError(f"checkpoint identity is incomplete: {path.name}")
        date.fromisoformat(audit_date)
        contract_hashes.add(contract_hash)
        audit_dates.add(audit_date)

        coverage = payload.get("coverage")
        if not isinstance(coverage, list):
            raise ValueError(f"checkpoint coverage is missing: {path.name}")
        for raw_row in coverage:
            if not isinstance(raw_row, dict):
                raise ValueError(f"checkpoint coverage row is invalid: {path.name}")
            row = dict(raw_row)
            provider = str(row.get("provider") or "").strip().lower()
            slate_date = str(row.get("slate_date") or "").strip()
            if provider != checkpoint_provider:
                raise ValueError(f"checkpoint provider drift: {path.name}")
            date.fromisoformat(slate_date)
            key = (provider, slate_date)
            if key in rows_by_partition:
                raise ValueError(f"duplicate provider/date checkpoint coverage: {key}")
            rows_by_partition[key] = row

    if checkpoint_count == 0:
        raise ValueError("no active-provider checkpoint files found")
    if len(contract_hashes) != 1:
        raise ValueError("active-provider checkpoints must share one query-contract hash")
    if len(audit_dates) != 1:
        raise ValueError("active-provider checkpoints must share one audit date")
    return rows_by_partition, contract_hashes.pop(), audit_dates.pop()


def _validate_shared_contiguous_dates(
    rows_by_partition: dict[tuple[str, str], dict[str, Any]],
    *,
    providers: tuple[str, ...],
) -> list[str]:
    dates_by_provider = {
        provider: sorted(
            slate_date
            for row_provider, slate_date in rows_by_partition
            if row_provider == provider
        )
        for provider in providers
    }
    if any(not dates for dates in dates_by_provider.values()):
        raise ValueError("active providers must have the same contiguous date coverage")
    first_dates = dates_by_provider[providers[0]]
    if any(dates != first_dates for dates in dates_by_provider.values()):
        raise ValueError("active providers must have the same contiguous date coverage")
    expected = _contiguous_dates(first_dates[0], first_dates[-1])
    if first_dates != expected:
        raise ValueError("active providers must have the same contiguous date coverage")
    return expected


def _partition_summary(row: dict[str, Any]) -> dict[str, Any]:
    missing = _strict_nonnegative_int(
        row.get("missing_compact_group_count"),
        label="missing_compact_group_count",
    )
    mismatched = _strict_nonnegative_int(
        row.get("mismatched_group_count"),
        label="mismatched_group_count",
    )
    return {
        "provider": str(row["provider"]).strip().lower(),
        "slate_date": str(row["slate_date"]).strip(),
        "raw_snapshot_rows": _strict_nonnegative_int(
            row.get("raw_snapshot_rows"), label="raw_snapshot_rows",
        ),
        "raw_group_count": _strict_nonnegative_int(
            row.get("raw_group_count"), label="raw_group_count",
        ),
        "compact_group_count": _strict_nonnegative_int(
            row.get("compact_group_count"), label="compact_group_count",
        ),
        "missing_compact_group_count": missing,
        "mismatched_group_count": mismatched,
        "rows_to_upsert_count": missing + mismatched,
        "unexpected_compact_group_count": _strict_nonnegative_int(
            row.get("unexpected_compact_group_count"),
            label="unexpected_compact_group_count",
        ),
        "unpreserved_unexpected_compact_group_count": _strict_nonnegative_int(
            row.get("unpreserved_unexpected_compact_group_count"),
            label="unpreserved_unexpected_compact_group_count",
        ),
        "first_raw_seen_at": row.get("first_raw_seen_at"),
        "last_raw_seen_at": row.get("last_raw_seen_at"),
        "requires_exact_partition_finalizer": True,
    }


def build_manifest(
    checkpoint_dir: str | Path,
    *,
    providers: Iterable[str] = DEFAULT_PROVIDERS,
) -> dict[str, Any]:
    root = Path(checkpoint_dir)
    normalized_providers = tuple(str(provider).strip().lower() for provider in providers)
    if normalized_providers != DEFAULT_PROVIDERS:
        raise ValueError("manifest scope is fixed to propline and therundown")
    if not root.is_dir():
        raise ValueError("checkpoint directory does not exist")

    rows_by_partition, contract_hash, audit_date = _load_coverage(
        root,
        providers=normalized_providers,
    )
    shared_dates = _validate_shared_contiguous_dates(
        rows_by_partition,
        providers=normalized_providers,
    )
    summaries = [
        _partition_summary(rows_by_partition[(provider, slate_date)])
        for provider in normalized_providers
        for slate_date in shared_dates
    ]
    repair_partitions = [
        summary for summary in summaries if summary["rows_to_upsert_count"] > 0
    ]
    preservation_only = [
        {
            "provider": summary["provider"],
            "slate_date": summary["slate_date"],
            "unexpected_compact_group_count": summary[
                "unexpected_compact_group_count"
            ],
            "unpreserved_unexpected_compact_group_count": summary[
                "unpreserved_unexpected_compact_group_count"
            ],
        }
        for summary in summaries
        if summary["rows_to_upsert_count"] == 0
        and summary["unpreserved_unexpected_compact_group_count"] > 0
    ]
    provider_totals = {}
    for provider in normalized_providers:
        provider_rows = [row for row in summaries if row["provider"] == provider]
        provider_repairs = [
            row for row in repair_partitions if row["provider"] == provider
        ]
        provider_totals[provider] = {
            "reviewed_partition_count": len(provider_rows),
            "repair_partition_count": len(provider_repairs),
            "rows_to_upsert_count": sum(
                row["rows_to_upsert_count"] for row in provider_repairs
            ),
            "raw_snapshot_rows": sum(row["raw_snapshot_rows"] for row in provider_rows),
            "raw_group_count": sum(row["raw_group_count"] for row in provider_rows),
            "compact_group_count": sum(
                row["compact_group_count"] for row in provider_rows
            ),
        }

    return {
        "report_type": "active_provider_compaction_preview_manifest",
        "source_audit_date": audit_date,
        "source_query_contract_sha256": contract_hash,
        "providers": list(normalized_providers),
        "date_range": {
            "start_date": shared_dates[0],
            "end_date": shared_dates[-1],
            "dates_per_provider": len(shared_dates),
        },
        "reviewed_partition_count": len(summaries),
        "repair_partition_count": len(repair_partitions),
        "rows_to_upsert_count": sum(
            row["rows_to_upsert_count"] for row in repair_partitions
        ),
        "provider_totals": provider_totals,
        "repair_partitions": repair_partitions,
        "preservation_only_partitions": preservation_only,
        "database_write_performed": False,
        "deletion_approved": False,
        "retention_execution_closed": True,
    }


def write_manifest(output: str | Path, report: dict[str, Any]) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as error:
        raise FileExistsError(f"refusing to overwrite existing evidence: {path}") from error


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-dir", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    report = build_manifest(args.checkpoint_dir)
    write_manifest(args.output, report)
    print(
        "Active-provider compaction preview "
        f"repairs={report['repair_partition_count']} "
        f"rows_to_upsert={report['rows_to_upsert_count']} "
        "database_write_performed=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
