"""Gate C holdout lab for lambda, market, over-only, and handedness challengers.

This diagnostic is shadow-only. It reads the compact pitcher K outcome dataset
and writes a local report only. It must not change live lambda, verdicts,
thresholds, staking, provider order, notifications, calibration, or dashboard
artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_PATH = ROOT / "analytics" / "output" / "gate_c_holdout_shadow_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
PROJECTION_CANDIDATES = [
    "current_model",
    "market_shrink_25",
    "high_line_temper",
    "handedness_bucket_adjust",
]
SIDE_BASELINE_CANDIDATES = [
    "market_favorite_only",
    "over_only",
    "under_only",
]
CANDIDATES = PROJECTION_CANDIDATES + SIDE_BASELINE_CANDIDATES


def to_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def load_jsonl(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def current_projection(row: dict[str, Any]) -> float | None:
    for key in ("projected_ks", "applied_lambda", "raw_lambda", "lambda"):
        value = to_float(row.get(key))
        if value is not None:
            return value
    return None


def _line_text(value: Any) -> str:
    line = to_float(value)
    return "unknown" if line is None else f"{line:.1f}"


def _market_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("slate_date") or ""),
        str(row.get("context_snapshot") or ""),
        str(row.get("normalized_pitcher") or row.get("pitcher") or "").lower(),
        _line_text(row.get("k_line")),
    )


def _winning_side(row: dict[str, Any]) -> str | None:
    actual = to_float(row.get("actual_ks"))
    line = to_float(row.get("k_line"))
    if actual is None or line is None:
        return None
    if actual > line:
        return "over"
    if actual < line:
        return "under"
    return None


def market_rows(
    rows: list[dict[str, Any]],
    *,
    start_date: str = CLEAN_WINDOW_START,
) -> list[dict[str, Any]]:
    """Return one clean official-close row per pitcher/line market."""

    markets: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        if str(row.get("slate_date") or "") < start_date:
            continue
        if row.get("context_snapshot") != "official_close":
            continue
        if row.get("result") not in WIN_LOSS_RESULTS:
            continue
        if current_projection(row) is None:
            continue
        if to_float(row.get("actual_ks")) is None or to_float(row.get("k_line")) is None:
            continue

        key = _market_key(row)
        if key not in markets:
            next_row = dict(row)
            next_row["winning_side"] = _winning_side(row)
            markets[key] = next_row

    return sorted(markets.values(), key=_market_key)


def tracked_side_rows(
    rows: list[dict[str, Any]],
    *,
    start_date: str = CLEAN_WINDOW_START,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("slate_date") or "") >= start_date
        and row.get("context_snapshot") == "official_close"
        and row.get("result") in WIN_LOSS_RESULTS
        and row.get("is_tracked_pick") is True
        and row.get("side") in {"over", "under"}
    ]


def split_holdout_rows(
    rows: list[dict[str, Any]],
    *,
    train_fraction: float = 0.7,
    min_validate_dates: int = 5,
) -> dict[str, Any]:
    dates = sorted({str(row.get("slate_date") or "") for row in rows if row.get("slate_date")})
    if len(dates) <= 1:
        return {
            "train_dates": dates,
            "validate_dates": [],
            "train_rows": list(rows),
            "validate_rows": [],
        }

    cut_index = int(len(dates) * train_fraction)
    cut_index = max(1, min(cut_index, len(dates) - 1))
    if len(dates) > min_validate_dates:
        cut_index = min(cut_index, len(dates) - min_validate_dates)

    train_dates = dates[:cut_index]
    validate_dates = dates[cut_index:]
    train_set = set(train_dates)
    validate_set = set(validate_dates)
    return {
        "train_dates": train_dates,
        "validate_dates": validate_dates,
        "train_rows": [row for row in rows if str(row.get("slate_date") or "") in train_set],
        "validate_rows": [row for row in rows if str(row.get("slate_date") or "") in validate_set],
    }


def rolling_validation_windows(
    rows: list[dict[str, Any]],
    *,
    train_dates: int = 20,
    validate_dates: int = 5,
    step_dates: int = 5,
) -> list[dict[str, Any]]:
    dates = sorted({str(row.get("slate_date") or "") for row in rows if row.get("slate_date")})
    windows = []
    start = 0
    while start + train_dates + validate_dates <= len(dates):
        train = dates[start : start + train_dates]
        validate = dates[start + train_dates : start + train_dates + validate_dates]
        train_set = set(train)
        validate_set = set(validate)
        windows.append(
            {
                "train_dates": train,
                "validate_dates": validate,
                "train_rows": [row for row in rows if str(row.get("slate_date") or "") in train_set],
                "validate_rows": [row for row in rows if str(row.get("slate_date") or "") in validate_set],
            }
        )
        start += step_dates
    return windows


def fit_handedness_adjustments(
    rows: list[dict[str, Any]],
    *,
    min_rows: int = 20,
    shrink_base: int = 50,
    max_abs_delta: float = 0.5,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        bucket = str(row.get("handedness_matchup_bucket") or "")
        projection = current_projection(row)
        actual = to_float(row.get("actual_ks"))
        if not bucket or projection is None or actual is None:
            continue
        grouped[bucket].append(actual - projection)

    adjustments: dict[str, dict[str, Any]] = {}
    for bucket, residuals in sorted(grouped.items()):
        if len(residuals) < min_rows:
            continue
        raw_delta = sum(residuals) / len(residuals)
        shrink = 1.0 if shrink_base <= 0 else len(residuals) / (len(residuals) + shrink_base)
        delta = max(-max_abs_delta, min(max_abs_delta, raw_delta * shrink))
        adjustments[bucket] = {
            "rows": len(residuals),
            "raw_delta": round(raw_delta, 3),
            "delta": round(delta, 3),
        }
    return adjustments


def candidate_projection(
    row: dict[str, Any],
    candidate: str,
    *,
    adjustments: dict[str, dict[str, Any]] | None = None,
) -> float | None:
    current = current_projection(row)
    line = to_float(row.get("k_line"))
    if current is None:
        return None

    if candidate == "current_model":
        return round(current, 3)

    if candidate == "market_shrink_25":
        if line is None:
            return round(current, 3)
        return round(current + ((line - current) * 0.25), 3)

    if candidate == "high_line_temper":
        if line is not None and line >= 7.5 and current > line:
            return round(max(0.0, current - 0.55), 3)
        return round(current, 3)

    if candidate == "handedness_bucket_adjust":
        bucket = str(row.get("handedness_matchup_bucket") or "")
        delta = 0.0
        if adjustments and bucket in adjustments:
            delta = to_float(adjustments[bucket].get("delta")) or 0.0
        return round(max(0.0, current + delta), 3)

    return None


def _side_from_projection(projection: float | None, line: float | None) -> str | None:
    if projection is None or line is None:
        return None
    if projection > line:
        return "over"
    if projection < line:
        return "under"
    return None


def candidate_side(
    row: dict[str, Any],
    candidate: str,
    *,
    adjustments: dict[str, dict[str, Any]] | None = None,
) -> str | None:
    if candidate == "market_favorite_only":
        side = str(row.get("market_favorite_side") or "").strip().lower()
        return side if side in {"over", "under"} else None
    if candidate == "over_only":
        return "over"
    if candidate == "under_only":
        return "under"

    return _side_from_projection(
        candidate_projection(row, candidate, adjustments=adjustments),
        to_float(row.get("k_line")),
    )


def summarize_candidate(
    candidate: str,
    rows: list[dict[str, Any]],
    *,
    adjustments: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[float] = []
    side_wins = 0
    side_losses = 0

    for row in rows:
        actual = to_float(row.get("actual_ks"))
        projection = candidate_projection(row, candidate, adjustments=adjustments)
        if actual is not None and projection is not None:
            errors.append(actual - projection)

        side = candidate_side(row, candidate, adjustments=adjustments)
        winning_side = row.get("winning_side") or _winning_side(row)
        if side and winning_side:
            if side == winning_side:
                side_wins += 1
            else:
                side_losses += 1

    side_total = side_wins + side_losses
    return {
        "name": candidate,
        "rows": len(rows),
        "mean_error": round(sum(errors) / len(errors), 3) if errors else None,
        "mae": round(sum(abs(error) for error in errors) / len(errors), 3) if errors else None,
        "rmse": round(math.sqrt(sum(error * error for error in errors) / len(errors)), 3) if errors else None,
        "side_wins": side_wins,
        "side_losses": side_losses,
        "side_accuracy": round(side_wins / side_total, 3) if side_total else None,
    }


def summarize_tracked_alignment(
    candidate: str,
    rows: list[dict[str, Any]],
    *,
    adjustments: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    aligned = []
    for row in rows:
        side = candidate_side(row, candidate, adjustments=adjustments)
        if side == row.get("side"):
            aligned.append(row)

    wins = sum(1 for row in aligned if row.get("result") == "win")
    losses = sum(1 for row in aligned if row.get("result") == "loss")
    pnl = round(
        sum(to_float(row.get("pick_history_pnl")) or to_float(row.get("theoretical_pnl")) or 0.0 for row in aligned),
        2,
    )
    return {
        "name": candidate,
        "tracked_rows": len(rows),
        "aligned_rows": len(aligned),
        "wins": wins,
        "losses": losses,
        "flat_pnl": pnl,
        "flat_roi": round(pnl / len(aligned), 3) if aligned else None,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _pct(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:.1%}"


def _projection_row(summary: dict[str, Any]) -> str:
    return (
        f"| `{summary['name']}` | {summary['rows']} | "
        f"{_fmt(summary['mean_error'])} | {_fmt(summary['mae'])} | {_fmt(summary['rmse'])} | "
        f"{summary['side_wins']}-{summary['side_losses']} | {_pct(summary['side_accuracy'])} |"
    )


def _tracked_row(summary: dict[str, Any]) -> str:
    return (
        f"| `{summary['name']}` | {summary['tracked_rows']} | {summary['aligned_rows']} | "
        f"{summary['wins']}-{summary['losses']} | {summary['flat_pnl']:+.2f} | "
        f"{_pct(summary['flat_roi'])} |"
    )


def _rolling_row(index: int, candidate: str, window: dict[str, Any]) -> str:
    summary = summarize_candidate(candidate, window["validate_rows"])
    train_dates = window["train_dates"]
    validate_dates = window["validate_dates"]
    train_range = f"{train_dates[0]} to {train_dates[-1]}" if train_dates else "none"
    validate_range = f"{validate_dates[0]} to {validate_dates[-1]}" if validate_dates else "none"
    return (
        f"| {index} | `{candidate}` | `{train_range}` | `{validate_range}` | "
        f"{summary['rows']} | {_fmt(summary['mae'])} | {_fmt(summary['rmse'])} | "
        f"{summary['side_wins']}-{summary['side_losses']} | {_pct(summary['side_accuracy'])} |"
    )


def _adjustment_rows(adjustments: dict[str, dict[str, Any]]) -> list[str]:
    if not adjustments:
        return ["| none | 0 | -- | -- |"]
    return [
        f"| `{bucket}` | {item['rows']} | {_fmt(item['raw_delta'])} | {_fmt(item['delta'])} |"
        for bucket, item in sorted(adjustments.items())
    ]


def _best_by(summaries: list[dict[str, Any]], metric: str, *, lower_is_better: bool) -> dict[str, Any] | None:
    usable = [summary for summary in summaries if summary.get(metric) is not None]
    if not usable:
        return None
    return sorted(usable, key=lambda item: item[metric], reverse=not lower_is_better)[0]


def _takeaway(validation_summaries: list[dict[str, Any]]) -> list[str]:
    current = next((item for item in validation_summaries if item["name"] == "current_model"), None)
    best_mae = _best_by(
        [item for item in validation_summaries if item["name"] in PROJECTION_CANDIDATES],
        "mae",
        lower_is_better=True,
    )
    best_side = _best_by(validation_summaries, "side_accuracy", lower_is_better=False)

    lines = [
        "- Do not discard lambda from this report alone; side baselines have no projection-error metric and can be regime-chasing.",
    ]
    if current and best_mae and best_mae["name"] != "current_model":
        lines.append(
            f"- `{best_mae['name']}` beat current lambda on validation MAE "
            f"({_fmt(best_mae['mae'])} vs {_fmt(current['mae'])}), so it is a Gate F candidate, not a live change."
        )
    elif current and best_mae:
        lines.append("- Current lambda still holds the best validation MAE among projection candidates.")

    if current and best_side and best_side["name"] != "current_model":
        lines.append(
            f"- `{best_side['name']}` had the best validation side accuracy "
            f"({_pct(best_side['side_accuracy'])} vs current {_pct(current['side_accuracy'])}); treat that as a referee/selection warning."
        )
    elif current and best_side:
        lines.append("- Current lambda also led validation side accuracy in this split.")

    lines.append("- Any live model change still needs Gate E/F proof across side, price, K-line, quality, and provider slices.")
    return lines


def build_report(rows: list[dict[str, Any]]) -> str:
    markets = market_rows(rows)
    tracked = tracked_side_rows(rows)
    market_split = split_holdout_rows(markets)
    tracked_split = split_holdout_rows(tracked)
    adjustments = fit_handedness_adjustments(market_split["train_rows"])

    train_summaries = [
        summarize_candidate(candidate, market_split["train_rows"], adjustments=adjustments)
        for candidate in CANDIDATES
    ]
    validation_summaries = [
        summarize_candidate(candidate, market_split["validate_rows"], adjustments=adjustments)
        for candidate in CANDIDATES
    ]
    tracked_validation_summaries = [
        summarize_tracked_alignment(candidate, tracked_split["validate_rows"], adjustments=adjustments)
        for candidate in CANDIDATES
    ]
    rolling_windows = rolling_validation_windows(markets)

    lines = [
        "# Gate C Holdout Shadow Lab",
        "",
        "This report is shadow-only. It does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, or dashboard artifacts.",
        "",
        f"- Generated at: `{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}`",
        f"- Clean window start: `{CLEAN_WINDOW_START}`",
        f"- Official-close market rows: `{len(markets)}`",
        f"- Tracked pick side rows: `{len(tracked)}`",
        f"- Training slates: `{len(market_split['train_dates'])}` ({market_split['train_dates'][0] if market_split['train_dates'] else 'none'} to {market_split['train_dates'][-1] if market_split['train_dates'] else 'none'})",
        f"- Validation slates: `{len(market_split['validate_dates'])}` ({market_split['validate_dates'][0] if market_split['validate_dates'] else 'none'} to {market_split['validate_dates'][-1] if market_split['validate_dates'] else 'none'})",
        "",
        "## Training Fit",
        "",
        "Handedness adjustments are learned only from training rows. The reconstructed lineup fields remain hindsight-only until future runtime capture proves them prelock-safe.",
        "",
        "| Bucket | Train Rows | Raw Residual Delta | Applied Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines.extend(_adjustment_rows(adjustments))

    lines.extend(
        [
            "",
            "## Training Scoreboard",
            "",
            "Error is `actual Ks - projected Ks`; negative means the projection was too high. Side-only baselines intentionally have no MAE/RMSE.",
            "",
            "| Candidate | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_projection_row(summary) for summary in train_summaries)

    lines.extend(
        [
            "",
            "## Validation Holdout",
            "",
            "| Candidate | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_projection_row(summary) for summary in validation_summaries)

    lines.extend(
        [
            "",
            "## Validation Tracked-Pick Alignment",
            "",
            "This checks whether a candidate would still point to the side Tyler actually tracked inside the validation window. It is not a replacement betting rule.",
            "",
            "| Candidate | Tracked Rows | Aligned Rows | W-L | Flat PnL | Flat ROI |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_tracked_row(summary) for summary in tracked_validation_summaries)

    lines.extend(
        [
            "",
            "## Rolling Validation Windows",
            "",
            "Rolling windows reduce dependence on one train/validation split. They are still shadow-only.",
            "",
            "| Window | Candidate | Training Dates | Validation Dates | Rows | MAE | RMSE | Side W-L | Side Accuracy |",
            "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    if not rolling_windows:
        lines.append("| 0 | none | none | none | 0 | -- | -- | 0-0 | -- |")
    for index, window in enumerate(rolling_windows, start=1):
        for candidate in ("current_model", "market_shrink_25", "high_line_temper"):
            lines.append(_rolling_row(index, candidate, window))

    lines.extend(["", "## Read Rule", ""])
    lines.extend(_takeaway(validation_summaries))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Gate C holdout shadow lab report.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = build_report(load_jsonl(args.dataset))
    if not args.no_write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
