from __future__ import annotations

from collections import defaultdict
from typing import Any


PROPLINE_HOBBY_DAILY_REQUEST_LIMIT = 5000
PROPLINE_WARNING_FRACTION = 0.70


def _source_for_run(row: dict[str, Any]) -> str:
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        for key in ("script", "worker", "source"):
            value = str(metadata.get(key) or "").strip()
            if value:
                return value
    return str(row.get("mode") or "unknown").strip() or "unknown"


def _usage_date(row: dict[str, Any], fallback: str | None) -> str:
    if fallback:
        return fallback
    slate_date = str(row.get("slate_date") or "").strip()
    if slate_date:
        return slate_date[:10]
    for key in ("started_at", "created_at", "observed_at"):
        value = str(row.get(key) or "").strip()
        if value:
            return value[:10]
    raise ValueError("usage_date is required when rows do not include a date")


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_provider_usage_rows(
    *,
    run_rows: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    usage_date: str | None = None,
) -> list[dict[str, Any]]:
    runs_by_id = {
        str(row.get("id")): row
        for row in run_rows
        if row.get("id")
    }
    usage: dict[tuple[str, str, str], dict[str, Any]] = {}

    def ensure(date: str, provider: str, source: str) -> dict[str, Any]:
        key = (date, provider, source)
        if key not in usage:
            usage[key] = {
                "usage_date": date,
                "provider": provider,
                "source": source,
                "request_count": 0,
                "snapshot_count": 0,
            }
        return usage[key]

    for row in run_rows:
        provider = str(row.get("provider") or "").strip().lower()
        if not provider:
            continue
        date = _usage_date(row, usage_date)
        source = _source_for_run(row)
        ensure(date, provider, source)["request_count"] += _integer(row.get("request_count"))

    for row in snapshot_rows:
        run = runs_by_id.get(str(row.get("run_id") or ""))
        provider = str((run or row).get("provider") or "").strip().lower()
        if not provider:
            continue
        date = _usage_date(run or row, usage_date)
        source = _source_for_run(run or row)
        ensure(date, provider, source)["snapshot_count"] += 1

    return sorted(
        usage.values(),
        key=lambda row: (row["usage_date"], row["provider"], row["source"]),
    )


def propline_budget_warnings(
    usage_rows: list[dict[str, Any]],
    *,
    daily_limit: int = PROPLINE_HOBBY_DAILY_REQUEST_LIMIT,
    warning_fraction: float = PROPLINE_WARNING_FRACTION,
) -> list[str]:
    threshold = daily_limit * warning_fraction
    warnings = []
    for row in usage_rows:
        if row.get("provider") != "propline":
            continue
        request_count = _integer(row.get("request_count"))
        if request_count < threshold:
            continue
        pct = request_count / daily_limit * 100
        warnings.append(
            "PropLine request usage "
            f"{request_count}/{daily_limit} ({pct:.1f}%) "
            f"for {row['usage_date']} source={row['source']}"
        )
    return warnings


def write_provider_usage_rows(
    writer: Any,
    usage_rows: list[dict[str, Any]],
    *,
    enforce_propline_budget: bool = False,
) -> list[dict[str, Any]]:
    usage_rows = _merge_existing_max_counts(writer, usage_rows)
    warnings = propline_budget_warnings(usage_rows)
    if enforce_propline_budget:
        for row in usage_rows:
            if row.get("provider") == "propline" and _integer(row.get("request_count")) > PROPLINE_HOBBY_DAILY_REQUEST_LIMIT:
                raise RuntimeError(f"PropLine daily request budget exceeded for {row['usage_date']}")
    writer.upsert_rows(
        "provider_request_usage_daily",
        usage_rows,
        on_conflict="usage_date,provider,source",
    )
    return [{"warning": warning} for warning in warnings]


def _merge_existing_max_counts(writer: Any, usage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not usage_rows or not hasattr(writer, "select_rows"):
        return usage_rows

    merged_rows = []
    for row in usage_rows:
        merged = dict(row)
        existing_rows = writer.select_rows(
            "provider_request_usage_daily",
            {
                "usage_date": f"eq.{row['usage_date']}",
                "provider": f"eq.{row['provider']}",
                "source": f"eq.{row['source']}",
                "limit": "1",
            },
        )
        if existing_rows:
            existing = existing_rows[0]
            merged["request_count"] = max(
                _integer(existing.get("request_count")),
                _integer(merged.get("request_count")),
            )
            merged["snapshot_count"] = max(
                _integer(existing.get("snapshot_count")),
                _integer(merged.get("snapshot_count")),
            )
        merged_rows.append(merged)
    return merged_rows
