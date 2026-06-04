"""Shadow audit for would-have-sent notification candidates.

This diagnostic is analysis-only. It does not send notifications or change
live picks, locks, thresholds, staking, provider order, or calibration.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_rows(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _reasons(row: dict[str, Any]) -> set[str]:
    value = row.get("suppression_reasons")
    if not isinstance(value, list):
        return set()
    return {str(reason) for reason in value}


def _movement_strength_labels(row: dict[str, Any]) -> list[str]:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return []
    value = metadata.get("movement_strength_labels")
    if not isinstance(value, list):
        return []
    return sorted(str(label) for label in value if str(label).strip())


def summarize_candidates(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, int]]:
    buckets: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {
            "rows": 0,
            "would_send_shadow": 0,
            "suppress_shadow": 0,
            "betrivers_only": 0,
            "volatile_or_reversed": 0,
            "number_worse": 0,
            "movement_strength_labels": Counter(),
        }
    )
    for row in rows:
        key = (
            str(row.get("provider") or "unknown"),
            str(row.get("candidate_type") or "unknown"),
        )
        bucket = buckets[key]
        bucket["rows"] += 1
        action = str(row.get("candidate_action") or "")
        if action in {"would_send_shadow", "suppress_shadow"}:
            bucket[action] += 1
        if row.get("betrivers_only"):
            bucket["betrivers_only"] += 1
        reasons = _reasons(row)
        if "volatile_or_reversed" in reasons:
            bucket["volatile_or_reversed"] += 1
        if "number_worse" in reasons:
            bucket["number_worse"] += 1
        for label in _movement_strength_labels(row):
            bucket["movement_strength_labels"][label] += 1

    normalized = {}
    for key, bucket in sorted(buckets.items()):
        normalized[key] = {
            **bucket,
            "movement_strength_labels": dict(sorted(bucket["movement_strength_labels"].items())),
        }
    return normalized


def build_report(rows: list[dict[str, Any]]) -> str:
    summary = summarize_candidates(rows)
    lines = [
        "# Shadow Notification Candidate Audit",
        "",
        "This report is shadow-only. It does not send notifications or change picks, locks, thresholds, staking, provider order, or calibration.",
        "",
        "| Provider | Candidate Type | Rows | Would Send | Suppressed | BetRivers Only | Reversed/Volatile | Number Worse |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if not summary:
        lines.append("| -- | -- | 0 | 0 | 0 | 0 | 0 | 0 |")
    else:
        for (provider, candidate_type), bucket in summary.items():
            lines.append(
                f"| `{provider}` | `{candidate_type}` | {bucket['rows']} | "
                f"{bucket['would_send_shadow']} | {bucket['suppress_shadow']} | "
                f"{bucket['betrivers_only']} | {bucket['volatile_or_reversed']} | "
                f"{bucket['number_worse']} |"
            )
    label_counts: Counter[str] = Counter()
    for bucket in summary.values():
        label_counts.update(bucket.get("movement_strength_labels") or {})
    lines.extend([
        "",
        "## Movement Strength Labels",
        "",
        "| Label | Rows |",
        "| --- | ---: |",
    ])
    if not label_counts:
        lines.append("| -- | 0 |")
    else:
        for label, count in sorted(label_counts.items()):
            lines.append(f"| `{label}` | {count} |")
    lines.extend([
        "",
        "## Promotion Rule",
        "",
        "- Do not promote a provider to live notifications from candidate volume alone.",
        "- First prove low stale/duplicate risk, low BetRivers-only noise, and clean post-grade value.",
    ])
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit shadow notification candidate rows.")
    parser.add_argument("--candidates", type=Path, required=True, help="JSON export of shadow candidates")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(build_report(load_rows(args.candidates)))


if __name__ == "__main__":
    main()
