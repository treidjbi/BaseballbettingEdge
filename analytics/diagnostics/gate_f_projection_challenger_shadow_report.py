"""Gate F projection challenger decision report.

Shadow-only. This module summarizes whether a projection challenger deserves a
later production implementation plan. It must not change live lambda, verdicts,
thresholds, staking, provider order, notifications, calibration, or dashboard
artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import gate_c_holdout_shadow_lab as holdout_lab
from analytics.diagnostics import k_projection_shadow_lab as k_lab

DATASET_PATH = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_PATH = ROOT / "analytics" / "output" / "gate_f_projection_challenger_shadow_report.md"
PROJECTION_CANDIDATES = [
    "market_shrink_15",
    "market_shrink_25",
    "market_shrink_35",
    "high_line_temper",
    "leash_cap",
    "handedness_bucket_adjust",
]
RUNTIME_SAFE = {
    "market_shrink_15": True,
    "market_shrink_25": True,
    "market_shrink_35": True,
    "high_line_temper": True,
    "leash_cap": True,
    "handedness_bucket_adjust": False,
}
SLICE_FIELDS = (
    "side",
    "price_sign",
    "line_bucket",
    "quality_gate_level",
    "model_market_relationship",
    "bet_timing_window",
    "opportunity_bucket",
    "leash_risk_bucket",
    "pitcher_archetype_bucket",
)


def load_jsonl(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _winning_side(row: dict[str, Any]) -> str | None:
    actual = k_lab.to_float(row.get("actual_ks"))
    line = k_lab.to_float(row.get("k_line"))
    if actual is None or line is None:
        return None
    if actual > line:
        return "over"
    if actual < line:
        return "under"
    return None


def _candidate_projection(
    row: dict[str, Any],
    candidate: str,
    *,
    adjustments: dict[str, dict[str, Any]] | None = None,
) -> float | None:
    if candidate in k_lab.CHALLENGERS:
        return k_lab.challenger_projection(row, candidate)
    if candidate == "handedness_bucket_adjust":
        return holdout_lab.candidate_projection(row, candidate, adjustments=adjustments)
    return None


def _candidate_side(
    row: dict[str, Any],
    candidate: str,
    *,
    adjustments: dict[str, dict[str, Any]] | None = None,
) -> str | None:
    projection = _candidate_projection(row, candidate, adjustments=adjustments)
    line = k_lab.to_float(row.get("k_line"))
    if projection is None or line is None:
        return None
    if projection > line:
        return "over"
    if projection < line:
        return "under"
    return None


def summarize_projection_candidate(
    candidate: str,
    rows: list[dict[str, Any]],
    *,
    adjustments: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[float] = []
    side_wins = 0
    side_losses = 0
    usable_rows = 0
    for row in rows:
        projection = _candidate_projection(row, candidate, adjustments=adjustments)
        actual = k_lab.to_float(row.get("actual_ks"))
        if projection is None or actual is None:
            continue

        usable_rows += 1
        errors.append(actual - projection)
        candidate_side = _candidate_side(row, candidate, adjustments=adjustments)
        winning_side = row.get("winning_side") or _winning_side(row)
        if candidate_side and winning_side:
            if candidate_side == winning_side:
                side_wins += 1
            else:
                side_losses += 1

    side_total = side_wins + side_losses
    return {
        "name": candidate,
        "rows": usable_rows,
        "mean_error": round(sum(errors) / len(errors), 3) if errors else None,
        "mae": round(sum(abs(error) for error in errors) / len(errors), 3) if errors else None,
        "rmse": round((sum(error * error for error in errors) / len(errors)) ** 0.5, 3) if errors else None,
        "side_wins": side_wins,
        "side_losses": side_losses,
        "side_accuracy": round(side_wins / side_total, 3) if side_total else None,
    }


def _delta(candidate_value: float | None, current_value: float | None) -> float:
    if candidate_value is None or current_value is None:
        return 0.0
    return round(candidate_value - current_value, 3)


def _slice_failure_count(
    candidate: str,
    rows: list[dict[str, Any]],
    *,
    adjustments: dict[str, dict[str, Any]] | None,
    min_rows: int = 25,
) -> int:
    failures = 0
    for field in SLICE_FIELDS:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row.get(field) or "unknown")].append(row)
        for bucket_rows in grouped.values():
            if len(bucket_rows) < min_rows:
                continue
            current = summarize_projection_candidate("current_model", bucket_rows, adjustments=adjustments)
            challenger = summarize_projection_candidate(candidate, bucket_rows, adjustments=adjustments)
            mae_delta = _delta(challenger["mae"], current["mae"])
            side_delta = _delta(challenger["side_accuracy"], current["side_accuracy"])
            if mae_delta > 0.05 or side_delta < -0.02:
                failures += 1
    return failures


def _aligned_wins(
    candidate: str,
    rows: list[dict[str, Any]],
    *,
    adjustments: dict[str, dict[str, Any]] | None,
) -> int:
    wins = 0
    for row in rows:
        if _candidate_side(row, candidate, adjustments=adjustments) == row.get("side") and row.get("result") == "win":
            wins += 1
    return wins


def _fire_2u_degradation(
    candidate: str,
    rows: list[dict[str, Any]],
    *,
    adjustments: dict[str, dict[str, Any]] | None,
) -> bool:
    fire_2u_rows = [
        row
        for row in rows
        if row.get("is_tracked_pick") is True
        and str(row.get("locked_verdict") or row.get("verdict") or "") == "FIRE 2u"
    ]
    return _aligned_wins(candidate, fire_2u_rows, adjustments=adjustments) < _aligned_wins(
        "current_model",
        fire_2u_rows,
        adjustments=adjustments,
    )


def _positive_rolling_windows(
    candidate: str,
    windows: list[dict[str, Any]],
    *,
    adjustments: dict[str, dict[str, Any]] | None,
) -> int:
    positive = 0
    for window in windows:
        current = summarize_projection_candidate("current_model", window["validate_rows"], adjustments=adjustments)
        challenger = summarize_projection_candidate(candidate, window["validate_rows"], adjustments=adjustments)
        if challenger["mae"] is None or current["mae"] is None:
            continue
        mae_ok = challenger["mae"] <= current["mae"]
        side_ok = _delta(challenger["side_accuracy"], current["side_accuracy"]) >= -0.005
        if mae_ok and side_ok:
            positive += 1
    return positive


def gate_f_decision(candidate: dict[str, Any]) -> dict[str, Any]:
    if not candidate.get("runtime_safe", False):
        return {"name": candidate["name"], "status": "blocked_hindsight_only", "reason": "candidate uses hindsight-only inputs"}
    if candidate.get("holdout_mae_delta", 0.0) > -0.025:
        return {"name": candidate["name"], "status": "blocked_mae_lift_too_small", "reason": "holdout MAE lift < 0.025"}
    if candidate.get("holdout_rmse_delta", 0.0) > 0.010:
        return {"name": candidate["name"], "status": "blocked_rmse_degradation", "reason": "holdout RMSE degraded > 0.010"}
    if candidate.get("side_accuracy_delta", 0.0) < -0.005:
        return {
            "name": candidate["name"],
            "status": "blocked_side_accuracy_degradation",
            "reason": "side accuracy degraded > 0.5 percentage points",
        }
    if candidate.get("bad_slice_count", 0) > 0:
        return {"name": candidate["name"], "status": "blocked_slice_failure", "reason": "one or more core slices failed"}
    if candidate.get("fire_2u_degradation", False):
        return {"name": candidate["name"], "status": "blocked_fire_2u_degradation", "reason": "FIRE 2u wins degraded"}
    if candidate.get("positive_rolling_windows", 0) < 2:
        return {
            "name": candidate["name"],
            "status": "blocked_not_rolling_stable",
            "reason": "fewer than two positive rolling windows",
        }
    return {"name": candidate["name"], "status": "promotion_plan_candidate", "reason": "Gate F shadow standards passed"}


def evaluate_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    markets = holdout_lab.market_rows(rows)
    tracked = holdout_lab.tracked_side_rows(rows)
    market_split = holdout_lab.split_holdout_rows(markets)
    tracked_split = holdout_lab.split_holdout_rows(tracked)
    adjustments = holdout_lab.fit_handedness_adjustments(market_split["train_rows"])
    rolling_windows = holdout_lab.rolling_validation_windows(markets)
    current = summarize_projection_candidate("current_model", market_split["validate_rows"], adjustments=adjustments)

    evaluations: list[dict[str, Any]] = []
    for candidate in PROJECTION_CANDIDATES:
        summary = summarize_projection_candidate(candidate, market_split["validate_rows"], adjustments=adjustments)
        item = {
            "name": candidate,
            "rows": summary["rows"],
            "holdout_mae_delta": _delta(summary["mae"], current["mae"]),
            "holdout_rmse_delta": _delta(summary["rmse"], current["rmse"]),
            "side_accuracy_delta": _delta(summary["side_accuracy"], current["side_accuracy"]),
            "bad_slice_count": _slice_failure_count(
                candidate,
                market_split["validate_rows"],
                adjustments=adjustments,
            ),
            "fire_2u_degradation": _fire_2u_degradation(
                candidate,
                tracked_split["validate_rows"],
                adjustments=adjustments,
            ),
            "positive_rolling_windows": _positive_rolling_windows(
                candidate,
                rolling_windows,
                adjustments=adjustments,
            ),
            "runtime_safe": RUNTIME_SAFE[candidate],
        }
        item.update(gate_f_decision(item))
        evaluations.append(item)
    return evaluations


def _fmt_delta(value: float) -> str:
    return f"{value:+.3f}"


def _decision_row(item: dict[str, Any]) -> str:
    return (
        f"| `{item['name']}` | `{item['status']}` | {item['reason']} | "
        f"{item['rows']} | {_fmt_delta(item['holdout_mae_delta'])} | "
        f"{_fmt_delta(item['holdout_rmse_delta'])} | {_fmt_delta(item['side_accuracy_delta'])} | "
        f"{item['positive_rolling_windows']} | {item['bad_slice_count']} | "
        f"{'yes' if item['fire_2u_degradation'] else 'no'} |"
    )


def build_report(rows: list[dict[str, Any]]) -> str:
    evaluations = evaluate_candidates(rows)
    lines = [
        "# Gate F Projection Challenger Shadow Report",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, locks, or dashboard artifacts.",
        "",
        "## Decision Summary",
        "",
        "| Candidate | Status | Reason | Rows | MAE Delta | RMSE Delta | Side Accuracy Delta | Positive Rolling Windows | Bad Slices | FIRE 2u Degradation |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    lines.extend(_decision_row(item) for item in evaluations)
    lines.extend(
        [
            "",
            "## Read Rule",
            "",
            "- `promotion_plan_candidate` means draft a later production plan; it does not approve live lambda.",
            "- `blocked_hindsight_only` candidates can stay in research but cannot drive pre-lock behavior.",
            "- Slice failures and FIRE 2u degradation block production-plan discussion even when aggregate MAE improves.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Gate F projection challenger shadow report.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    report = build_report(load_jsonl(args.dataset))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
