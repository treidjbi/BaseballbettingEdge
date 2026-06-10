"""Audit confidence-referee metadata persisted to Gate C research rows.

This diagnostic is analysis-only. It does not change live picks, locks,
thresholds, staking, provider order, notifications, calibration, or dashboard
source-of-truth.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_PATH = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
LEGACY_HISTORY_PATH = ROOT / "data" / "picks_history.json"
OUTPUT_PATH = ROOT / "analytics" / "output" / "confidence_referee_canary_audit.md"


def load_rows(path: Path = DEFAULT_INPUT_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
        return rows

    payload = json.loads(text)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "items", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def load_history(path: Path = LEGACY_HISTORY_PATH) -> list[dict[str, Any]]:
    return load_rows(path)


def _label(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    return str(value)


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _final_verdict(row: dict[str, Any]) -> str:
    return _label(
        row.get("display_verdict")
        or row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("current_verdict")
        or row.get("verdict")
    )


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mode_counts: Counter[str] = Counter()
    relationship_counts: Counter[str] = Counter()
    cap_transition_counts: Counter[str] = Counter()
    rows_with_referee_metadata = 0
    applied_caps = 0

    for row in rows:
        meta = _json_object(row.get("confidence_referee"))
        if not meta:
            continue

        rows_with_referee_metadata += 1
        mode_counts[_label(meta.get("mode"))] += 1
        relationship_counts[_label(meta.get("relationship"))] += 1

        if meta.get("applied") is True:
            applied_caps += 1
            raw_verdict = _label(row.get("raw_verdict"))
            final_verdict = _final_verdict(row)
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
        "This is feature-flag audit evidence for `confidence_referee` metadata in the Gate C pitcher outcome dataset. The legacy picks_history-only read is retired because it does not carry current referee metadata.",
        "",
        "Shadow-only: this report does not change live picks, locks, thresholds, staking, provider order, notifications, calibration, or dashboard source-of-truth.",
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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = load_rows(args.input)
    args.output.write_text(build_report(rows), encoding="utf-8")
    print(f"Wrote {args.output} ({len(rows)} source rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
