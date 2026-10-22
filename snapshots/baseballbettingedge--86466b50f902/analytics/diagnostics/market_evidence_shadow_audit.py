"""Shadow audit for model-vs-market evidence.

This diagnostic is analysis-only. It does not change live picks, locks,
thresholds, staking, provider order, notification sends, or calibration.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _evidence_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("slate_date") or row.get("date") or ""),
        str(row.get("normalized_pitcher") or "").strip(),
        str(row.get("side") or "").strip().lower(),
    )


def join_evidence_to_results(
    evidence_rows: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results_by_key = {
        _evidence_key(row): row
        for row in history_rows
        if row.get("result") in {"win", "loss"}
    }
    joined: list[dict[str, Any]] = []
    for row in evidence_rows:
        result_row = results_by_key.get(_evidence_key(row), {})
        joined.append({
            **row,
            "result": result_row.get("result"),
            "pnl": result_row.get("pnl"),
        })
    return joined


def _is_fire(row: dict[str, Any]) -> bool:
    return str(row.get("current_verdict") or "").startswith("FIRE")


def summarize_evidence(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "rows": 0,
            "fire_rows": 0,
            "graded": 0,
            "wins": 0,
            "losses": 0,
            "pnl": 0.0,
            "roi": None,
        }
    )

    for row in rows:
        key = (
            str(row.get("provider") or "unknown"),
            str(row.get("market_consensus") or "none"),
            str(row.get("bet_value_consensus") or "none"),
        )
        bucket = buckets[key]
        bucket["rows"] += 1
        if _is_fire(row):
            bucket["fire_rows"] += 1

        result = row.get("result")
        if result not in {"win", "loss"}:
            continue
        bucket["graded"] += 1
        if result == "win":
            bucket["wins"] += 1
        else:
            bucket["losses"] += 1
        bucket["pnl"] += float(row.get("pnl") or 0.0)

    for bucket in buckets.values():
        bucket["pnl"] = round(bucket["pnl"], 2)
        bucket["roi"] = round(bucket["pnl"] / bucket["graded"], 4) if bucket["graded"] else None

    return dict(sorted(buckets.items()))


def _format_roi(value: float | None) -> str:
    return "--" if value is None else f"{value:+.1%}"


def build_report(rows: list[dict[str, Any]]) -> str:
    summary = summarize_evidence(rows)
    lines = [
        "# Market Evidence Shadow Audit",
        "",
        "This report is shadow-only. It does not change picks, locks, thresholds, staking, provider order, or notifications.",
        "",
        "## Buckets",
        "",
        "| Provider | Market Consensus | Bet Value Consensus | Rows | FIRE Rows | Graded | W-L | PnL | ROI |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    if not summary:
        lines.append("| -- | -- | -- | 0 | 0 | 0 | 0-0 | +0.00 | -- |")
    else:
        for (provider, market_consensus, bet_value_consensus), bucket in summary.items():
            lines.append(
                f"| `{provider}` | `{market_consensus}` | `{bet_value_consensus}` | "
                f"{bucket['rows']} | {bucket['fire_rows']} | {bucket['graded']} | "
                f"{bucket['wins']}-{bucket['losses']} | {bucket['pnl']:+.2f} | "
                f"{_format_roi(bucket['roi'])} |"
            )

    lines.extend([
        "",
        "## Read Rule",
        "",
        "- `market_consensus` says whether market movement generally moved toward or away from the pick.",
        "- `bet_value_consensus` says whether the current number got better or worse to bet now.",
        "- Wait for enough graded rows before treating any bucket as a decision rule.",
    ])
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit shadow market evidence against graded history.")
    parser.add_argument(
        "--evidence",
        type=Path,
        required=True,
        help="JSON export of market_pick_evidence rows from Supabase.",
    )
    parser.add_argument("--history", type=Path, default=HISTORY_PATH, help="Path to picks_history.json")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    evidence = load_json_rows(args.evidence)
    history = load_json_rows(args.history)
    print(build_report(join_evidence_to_results(evidence, history)))


if __name__ == "__main__":
    main()
