"""Shadow audit for monthly pitcher strikeout environment in app history."""

from __future__ import annotations

import json
import argparse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"


def month_bucket(date_str: str) -> str:
    return str(date_str)[:7]


def summarize_by_month(rows: list[dict]) -> dict:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("result") not in {"win", "loss"}:
            continue
        if row.get("actual_ks") is None:
            continue

        buckets[month_bucket(row.get("date"))].append(float(row["actual_ks"]))

    return {
        month: {
            "n": len(values),
            "avg_actual_ks": round(sum(values) / len(values), 3),
        }
        for month, values in sorted(buckets.items())
        if values
    }


def render(summary: dict) -> str:
    lines = [
        "# Seasonal K Environment Audit",
        "",
        "This is a shadow read. Do not apply month constants directly to live lambda.",
        "",
        "Warning: app picks are selection-biased; validate against MLB-wide starter K/start before any live prior.",
        "",
        "## Monthly Actual K Snapshot",
    ]

    if summary:
        for month, row in summary.items():
            lines.append(f"- `{month}`: n={row['n']}, avg_actual_ks={row['avg_actual_ks']}")
    else:
        lines.append("- No graded win/loss rows with actual_ks found.")

    lines.extend(
        [
            "",
            "## Decision Rule",
            "",
            "- If a month/week environment signal is real, implement it as a shrunk prior or calibration feature, not a hard-coded calendar bump.",
            "- Do not change lambda, verdict thresholds, staking, or formula_change_date from this audit alone.",
        ]
    )
    return "\n".join(lines)


def load_history(path: Path = HISTORY_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit monthly K environment from pick history.")
    parser.add_argument("--history", type=Path, default=HISTORY_PATH, help="Path to picks_history.json")
    args = parser.parse_args(argv)
    rows = load_history(args.history)
    print(render(summarize_by_month(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
