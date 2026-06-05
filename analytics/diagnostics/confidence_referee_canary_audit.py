"""Audit confidence-referee metadata persisted to picks history."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"
OUTPUT_PATH = ROOT / "analytics" / "output" / "confidence_referee_canary_audit.md"


def load_history(path: Path = HISTORY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _label(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    return str(value)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mode_counts: Counter[str] = Counter()
    relationship_counts: Counter[str] = Counter()
    cap_transition_counts: Counter[str] = Counter()
    rows_with_referee_metadata = 0
    applied_caps = 0

    for row in rows:
        meta = row.get("confidence_referee")
        if not isinstance(meta, dict):
            continue

        rows_with_referee_metadata += 1
        mode_counts[_label(meta.get("mode"))] += 1
        relationship_counts[_label(meta.get("relationship"))] += 1

        if meta.get("applied") is True:
            applied_caps += 1
            raw_verdict = _label(row.get("raw_verdict"))
            final_verdict = _label(row.get("verdict"))
            cap_transition_counts[f"{raw_verdict} -> {final_verdict}"] += 1

    return {
        "total_rows": len(rows),
        "rows_with_referee_metadata": rows_with_referee_metadata,
        "applied_caps": applied_caps,
        "mode_counts": dict(sorted(mode_counts.items())),
        "relationship_counts": dict(sorted(relationship_counts.items())),
        "cap_transition_counts": dict(sorted(cap_transition_counts.items())),
    }


def _counter_lines(title: str, counts: dict[str, int]) -> list[str]:
    lines = [f"## {title}", ""]
    if not counts:
        return lines + ["- None", ""]
    return lines + [f"- `{key}`: `{value}`" for key, value in counts.items()] + [""]


def build_report(rows: list[dict[str, Any]]) -> str:
    summary = summarize(rows)
    lines = [
        "# Confidence Referee Canary Audit",
        "",
        "This is feature-flag audit evidence for confidence_referee metadata in picks_history rows.",
        "",
        "## Summary",
        "",
        f"- Total rows: `{summary['total_rows']}`",
        f"- Rows with referee metadata: `{summary['rows_with_referee_metadata']}`",
        f"- Applied caps: `{summary['applied_caps']}`",
        "",
    ]
    lines.extend(_counter_lines("Mode Counts", summary["mode_counts"]))
    lines.extend(_counter_lines("Relationship Counts", summary["relationship_counts"]))
    lines.extend(_counter_lines("Applied Cap Transitions", summary["cap_transition_counts"]))
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_report(load_history()), encoding="utf-8")


if __name__ == "__main__":
    main()
