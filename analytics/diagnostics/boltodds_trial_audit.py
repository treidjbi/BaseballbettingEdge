"""Summarize BoltOdds provider coverage audit rows for trial review."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _add_counts(counter: Counter, counts: dict | None) -> None:
    if not isinstance(counts, dict):
        return
    for key, value in counts.items():
        counter[str(key)] += _as_int(value)


def _row_timestamp(row: dict) -> str:
    for key in ("created_at", "updated_at", "completed_at"):
        value = row.get(key)
        if value:
            return str(value)
    return ""


def _snapshot_count(row: dict) -> int:
    metadata = row.get("metadata") or {}
    if isinstance(metadata, dict):
        return _as_int(metadata.get("snapshot_rows"))
    return 0


def _filter_provider_rows(rows: list[dict], provider: str) -> list[dict]:
    filtered = []
    for row in rows:
        row_provider = row.get("provider")
        if row_provider is None:
            continue
        if str(row_provider).casefold() != provider.casefold():
            continue
        filtered.append(row)
    return filtered


def _dedupe_rows_by_slate(rows: list[dict]) -> list[dict]:
    """Keep one best review row per slate to avoid repeated-batch inflation."""
    best_by_slate: dict[str, tuple[tuple[str, int, int], dict]] = {}
    for index, row in enumerate(rows):
        slate_date = str(row.get("slate_date") or f"row-{index}")
        key = (_row_timestamp(row), _snapshot_count(row), index)
        current = best_by_slate.get(slate_date)
        if current is None or key > current[0]:
            best_by_slate[slate_date] = (key, row)
    return [row for _, row in sorted(best_by_slate.values(), key=lambda item: item[0])]


def _summarize_rows(rows: list[dict]) -> dict:
    """Summarize provider_coverage_audits rows for BoltOdds trial review."""
    slate_dates = set()
    missing_by_slate: dict[str, set[str]] = defaultdict(set)
    target_book_counts: Counter = Counter()
    production_book_counts: Counter = Counter()
    fillable_missing_counts: Counter = Counter()
    non_target_books_seen = set()

    total_complete_groups = 0
    total_same_line_overlap = 0
    total_line_conflicts = 0

    for row in rows:
        slate_date = row.get("slate_date")
        if slate_date:
            slate_dates.add(str(slate_date))
            missing_by_slate[str(slate_date)].update(
                str(book) for book in _as_list(row.get("missing_target_books"))
            )

        total_complete_groups += _as_int(row.get("complete_pitcher_line_groups"))
        total_same_line_overlap += _as_int(row.get("same_line_overlap_count"))
        total_line_conflicts += _as_int(row.get("line_conflict_count"))

        metadata = row.get("metadata") or {}
        _add_counts(target_book_counts, metadata.get("target_book_group_counts"))
        _add_counts(production_book_counts, metadata.get("production_book_group_counts"))
        _add_counts(fillable_missing_counts, metadata.get("fillable_missing_book_counts"))
        non_target_books_seen.update(
            str(book) for book in _as_list(metadata.get("non_target_books_seen"))
        )

    return {
        "slates": len(slate_dates),
        "complete_pitcher_line_groups": total_complete_groups,
        "same_line_overlap_count": total_same_line_overlap,
        "line_conflict_count": total_line_conflicts,
        "missing_target_books_by_slate": {
            slate_date: sorted(books)
            for slate_date, books in sorted(missing_by_slate.items())
        },
        "target_book_group_counts": dict(sorted(target_book_counts.items())),
        "production_book_group_counts": dict(sorted(production_book_counts.items())),
        "fillable_missing_book_counts": dict(sorted(fillable_missing_counts.items())),
        "non_target_books_seen": sorted(non_target_books_seen),
    }


def summarize_provider_audits(rows: list[dict], provider: str = "boltodds") -> dict:
    """Summarize provider_coverage_audits rows for BoltOdds trial review."""
    provider_rows = _filter_provider_rows(rows, provider)
    deduped_rows = _dedupe_rows_by_slate(provider_rows)
    deduped_summary = _summarize_rows(deduped_rows)
    row_counted_summary = _summarize_rows(provider_rows)

    return {
        "provider": provider,
        "input_rows": len(rows),
        "provider_rows": len(provider_rows),
        "deduped_rows": len(deduped_rows),
        "slates": deduped_summary["slates"],
        "total_complete_pitcher_line_groups": deduped_summary[
            "complete_pitcher_line_groups"
        ],
        "total_same_line_overlap_count": deduped_summary["same_line_overlap_count"],
        "total_line_conflict_count": deduped_summary["line_conflict_count"],
        "missing_target_books_by_slate": deduped_summary["missing_target_books_by_slate"],
        "target_book_group_counts": deduped_summary["target_book_group_counts"],
        "production_book_group_counts": deduped_summary["production_book_group_counts"],
        "fillable_missing_book_counts": deduped_summary["fillable_missing_book_counts"],
        "non_target_books_seen": deduped_summary["non_target_books_seen"],
        "row_counted_totals": {
            "complete_pitcher_line_groups": row_counted_summary[
                "complete_pitcher_line_groups"
            ],
            "same_line_overlap_count": row_counted_summary["same_line_overlap_count"],
            "line_conflict_count": row_counted_summary["line_conflict_count"],
        },
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize BoltOdds provider coverage audit rows."
    )
    parser.add_argument("--input", type=Path, required=True, help="JSON file containing audit rows")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    rows = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(summarize_provider_audits(rows), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
