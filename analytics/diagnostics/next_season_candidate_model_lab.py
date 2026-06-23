"""Walk-forward candidate lab for next-season pitcher K model work."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "analytics" / "output" / "season_end_model_rebuild_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "next_season_candidate_model_lab.md"
DEFAULT_TEST_START = "2026-06-01"
HINDSIGHT_FIELD_NAMES = {
    "actual_ks",
    "result",
    "pnl",
    "theoretical_pnl",
    "pick_history_pnl",
    "closing_odds",
    "closing_line",
    "beat_close_price",
    "beat_close_line",
    "price_clv_cents",
    "line_clv_delta",
    "actual_ip",
    "actual_pitch_count",
    "batters_faced",
}


@dataclass(frozen=True)
class Candidate:
    name: str
    runtime_fields: tuple[str, ...]
    selector: Callable[[dict[str, Any]], bool]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def walk_forward_split(
    rows: list[dict[str, Any]], *, test_start: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda row: row.get("slate_date") or "")
    train = [row for row in ordered if (row.get("slate_date") or "") < test_start]
    test = [row for row in ordered if (row.get("slate_date") or "") >= test_start]
    return train, test


def row_pnl(row: dict[str, Any]) -> float:
    labels = row.get("hindsight_labels", {})
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = labels.get(key)
        if value is not None and value != "":
            return float(value)
    return 0.0


def score_candidate(candidate: Candidate, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if any(field in HINDSIGHT_FIELD_NAMES for field in candidate.runtime_fields):
        return {"candidate": candidate.name, "status": "blocked_hindsight_runtime_field", "rows": 0}

    selected = [row for row in rows if candidate.selector(row.get("runtime_features", {}))]
    graded = [row for row in selected if row.get("hindsight_labels", {}).get("result") in {"win", "loss"}]
    wins = sum(1 for row in graded if row["hindsight_labels"]["result"] == "win")
    losses = sum(1 for row in graded if row["hindsight_labels"]["result"] == "loss")
    pnl = round(sum(row_pnl(row) for row in graded), 2)
    status = "review_ready" if len(graded) >= 150 and pnl > 0 else "watch"
    return {
        "candidate": candidate.name,
        "status": status,
        "rows": len(graded),
        "wins": wins,
        "losses": losses,
        "pnl": pnl,
    }


def score_candidate_walk_forward(
    candidate: Candidate, rows: list[dict[str, Any]], *, test_start: str
) -> dict[str, Any]:
    overall = score_candidate(candidate, rows)
    if overall["status"] == "blocked_hindsight_runtime_field":
        return overall

    train_rows, test_rows = walk_forward_split(rows, test_start=test_start)
    train = score_candidate(candidate, train_rows)
    test = score_candidate(candidate, test_rows)
    result = {
        **overall,
        "train_rows": train.get("rows", 0),
        "train_wins": train.get("wins", 0),
        "train_losses": train.get("losses", 0),
        "train_pnl": train.get("pnl", 0.0),
        "test_rows": test.get("rows", 0),
        "test_wins": test.get("wins", 0),
        "test_losses": test.get("losses", 0),
        "test_pnl": test.get("pnl", 0.0),
    }
    if result["rows"] >= 150 and result["pnl"] > 0 and result["test_rows"] >= 30 and result["test_pnl"] > 0:
        result["status"] = "review_ready"
    else:
        result["status"] = "watch"
    return result


def default_candidates() -> list[Candidate]:
    return [
        Candidate(
            name="model_agrees_with_favorite",
            runtime_fields=("model_market_relationship",),
            selector=lambda runtime_features: runtime_features.get("model_market_relationship")
            == "model_agrees_with_favorite",
        ),
        Candidate(
            name="clean_quality_only",
            runtime_fields=("quality_gate_level",),
            selector=lambda runtime_features: runtime_features.get("quality_gate_level") == "clean",
        ),
    ]


def render(results: list[dict[str, Any]], *, test_start: str = DEFAULT_TEST_START) -> str:
    lines = [
        "# Next Season Candidate Model Lab",
        "",
        "Research-only. This report does not change live lambda, thresholds, staking, providers, notifications, locks, retention, calibration, or dashboard source-of-truth.",
        "",
        f"Walk-forward split: train rows before `{test_start}`; test rows on/after `{test_start}`.",
        "PnL preference: `pick_history_pnl`, then `theoretical_pnl`, then legacy `pnl`.",
        "",
        "| Candidate | Status | Rows | W-L | PnL | Train Rows | Train PnL | Test Rows | Test PnL |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in results:
        lines.append(
            f"| `{row['candidate']}` | `{row['status']}` | {row.get('rows', 0)} | "
            f"{row.get('wins', 0)}-{row.get('losses', 0)} | {row.get('pnl', 0)} | "
            f"{row.get('train_rows', 0)} | {row.get('train_pnl', 0)} | "
            f"{row.get('test_rows', 0)} | {row.get('test_pnl', 0)} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--test-start", default=DEFAULT_TEST_START)
    args = parser.parse_args(argv)

    rows = load_jsonl(args.input)
    results = [
        score_candidate_walk_forward(candidate, rows, test_start=args.test_start)
        for candidate in default_candidates()
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(results, test_start=args.test_start), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
