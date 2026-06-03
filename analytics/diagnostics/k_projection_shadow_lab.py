"""Shadow lab for testing alternate pitcher K projections.

This diagnostic is analysis-only. It reuses the compact pitcher K outcome
dataset and does not change live projections, verdicts, thresholds, staking,
provider order, notifications, or calibration.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_PATH = ROOT / "analytics" / "output" / "k_projection_shadow_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
CHALLENGERS = [
    "current_model",
    "market_shrink_15",
    "market_shrink_25",
    "market_shrink_35",
    "high_line_temper",
    "leash_cap",
    "recent_rate_blend",
    "career_rate_blend",
]


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


def _market_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    line = to_float(row.get("k_line"))
    line_text = "unknown" if line is None else f"{line:.1f}"
    return (
        str(row.get("slate_date") or ""),
        str(row.get("context_snapshot") or ""),
        str(row.get("normalized_pitcher") or row.get("pitcher") or "").lower(),
        line_text,
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


def current_projection(row: dict[str, Any]) -> float | None:
    for key in ("projected_ks", "applied_lambda", "raw_lambda", "lambda"):
        value = to_float(row.get(key))
        if value is not None:
            return value
    return None


def market_projection_rows(
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
            markets[key] = dict(row)
            markets[key]["winning_side"] = _winning_side(row)

    return sorted(markets.values(), key=lambda row: _market_key(row))


def _rate_projection(row: dict[str, Any], weights: dict[str, float]) -> float | None:
    avg_ip = to_float(row.get("avg_ip"))
    if avg_ip is None or avg_ip <= 0:
        return None

    total_weight = 0.0
    weighted_k9 = 0.0
    for field, weight in weights.items():
        value = to_float(row.get(field))
        if value is None:
            continue
        weighted_k9 += value * weight
        total_weight += weight

    if total_weight <= 0:
        return None

    rest_delta = to_float(row.get("rest_k9_delta")) or 0.0
    ump_adj = to_float(row.get("ump_k_adj")) or 0.0
    rate_projection = ((weighted_k9 / total_weight) + rest_delta) * avg_ip / 9.0
    return round(max(0.0, rate_projection + ump_adj), 3)


def _market_shrink_projection(current: float, line: float | None, weight: float) -> float:
    if line is None:
        return round(current, 3)
    return round(current + ((line - current) * weight), 3)


def challenger_projection(row: dict[str, Any], challenger: str) -> float | None:
    current = current_projection(row)
    line = to_float(row.get("k_line"))
    if current is None:
        return None

    if challenger == "current_model":
        return round(current, 3)

    if challenger == "market_shrink_15":
        return _market_shrink_projection(current, line, 0.15)

    if challenger == "market_shrink_25":
        return _market_shrink_projection(current, line, 0.25)

    if challenger == "market_shrink_35":
        return _market_shrink_projection(current, line, 0.35)

    if challenger == "high_line_temper":
        if line is not None and line >= 7.5 and current > line:
            return round(max(0.0, current - 0.55), 3)
        return round(current, 3)

    if challenger == "leash_cap":
        if (
            row.get("leash_risk_bucket") == "high"
            or row.get("opportunity_bucket") == "short_leash"
            or row.get("pitcher_archetype_bucket") == "short_leash"
        ):
            return round(max(0.0, current - 0.55), 3)
        if row.get("leash_risk_bucket") == "medium":
            return round(max(0.0, current - 0.25), 3)
        return round(current, 3)

    if challenger == "recent_rate_blend":
        rate = _rate_projection(
            row,
            {"recent_k9": 0.5, "season_k9": 0.3, "career_k9": 0.2},
        )
        if rate is None:
            return round(current, 3)
        return round((current * 0.75) + (rate * 0.25), 3)

    if challenger == "career_rate_blend":
        rate = _rate_projection(
            row,
            {"career_k9": 0.5, "season_k9": 0.3, "recent_k9": 0.2},
        )
        if rate is None:
            return round(current, 3)
        return round((current * 0.75) + (rate * 0.25), 3)

    raise ValueError(f"unknown challenger: {challenger}")


def _projected_side(projection: float | None, line: float | None) -> str | None:
    if projection is None or line is None:
        return None
    if projection > line:
        return "over"
    if projection < line:
        return "under"
    return None


def summarize_projection(
    challenger: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    errors: list[float] = []
    side_wins = 0
    side_losses = 0
    usable_rows = 0

    for row in rows:
        projection = challenger_projection(row, challenger)
        actual = to_float(row.get("actual_ks"))
        line = to_float(row.get("k_line"))
        if projection is None or actual is None:
            continue

        usable_rows += 1
        error = actual - projection
        errors.append(error)

        projected_side = _projected_side(projection, line)
        winning_side = row.get("winning_side") or _winning_side(row)
        if projected_side and winning_side:
            if projected_side == winning_side:
                side_wins += 1
            else:
                side_losses += 1

    if not errors:
        return {
            "name": challenger,
            "rows": 0,
            "mean_error": None,
            "mae": None,
            "rmse": None,
            "side_wins": 0,
            "side_losses": 0,
            "side_accuracy": None,
        }

    side_total = side_wins + side_losses
    return {
        "name": challenger,
        "rows": usable_rows,
        "mean_error": round(sum(errors) / len(errors), 3),
        "mae": round(sum(abs(error) for error in errors) / len(errors), 3),
        "rmse": round(math.sqrt(sum(error * error for error in errors) / len(errors)), 3),
        "side_wins": side_wins,
        "side_losses": side_losses,
        "side_accuracy": round(side_wins / side_total, 3) if side_total else None,
    }


def summarize_by_bucket(
    challenger: str,
    rows: list[dict[str, Any]],
    field: str,
    *,
    min_rows: int = 10,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)

    summaries = []
    for bucket, bucket_rows in sorted(grouped.items()):
        if len(bucket_rows) < min_rows:
            continue
        summary = summarize_projection(challenger, bucket_rows)
        summary["bucket"] = bucket
        summaries.append(summary)
    return summaries


def summarize_challenger_slices(
    challenger: str,
    rows: list[dict[str, Any]],
    field: str,
    *,
    min_rows: int = 25,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)

    output = []
    for bucket, bucket_rows in sorted(grouped.items()):
        summary = summarize_projection(challenger, bucket_rows)
        summary["bucket"] = bucket
        summary["sample_status"] = "enough_sample" if summary["rows"] >= min_rows else "small_sample"
        output.append(summary)
    return output


def summarize_tracked_pick_alignment(
    challenger: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    tracked = [row for row in rows if row.get("is_tracked_pick") is True]
    aligned = []
    for row in tracked:
        projection = challenger_projection(row, challenger)
        projected_side = _projected_side(projection, to_float(row.get("k_line")))
        if projected_side == row.get("side"):
            aligned.append(row)

    wins = sum(1 for row in aligned if row.get("result") == "win")
    losses = sum(1 for row in aligned if row.get("result") == "loss")
    pnl = round(sum(to_float(row.get("theoretical_pnl")) or 0.0 for row in aligned), 2)
    roi = round(pnl / len(aligned), 3) if aligned else None

    return {
        "name": challenger,
        "tracked_rows": len(tracked),
        "aligned_rows": len(aligned),
        "wins": wins,
        "losses": losses,
        "flat_pnl": pnl,
        "flat_roi": roi,
    }


def _format_number(value: Any) -> str:
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _format_percent(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:.1%}"


def _projection_row(summary: dict[str, Any]) -> str:
    return (
        f"| `{summary['name']}` | {summary['rows']} | "
        f"{_format_number(summary['mean_error'])} | "
        f"{_format_number(summary['mae'])} | "
        f"{_format_number(summary['rmse'])} | "
        f"{summary['side_wins']}-{summary['side_losses']} | "
        f"{_format_percent(summary['side_accuracy'])} |"
    )


def _tracked_row(summary: dict[str, Any]) -> str:
    return (
        f"| `{summary['name']}` | {summary['tracked_rows']} | "
        f"{summary['aligned_rows']} | {summary['wins']}-{summary['losses']} | "
        f"{summary['flat_pnl']:+.2f} | {_format_percent(summary['flat_roi'])} |"
    )


def _bucket_row(summary: dict[str, Any]) -> str:
    return (
        f"| `{summary['bucket']}` | {summary['rows']} | "
        f"{_format_number(summary['mean_error'])} | "
        f"{_format_number(summary['mae'])} | "
        f"{summary['side_wins']}-{summary['side_losses']} | "
        f"{_format_percent(summary['side_accuracy'])} |"
    )


def _slice_row(summary: dict[str, Any]) -> str:
    return (
        f"| `{summary['bucket']}` | {summary['rows']} | "
        f"{_format_number(summary['mae'])} | "
        f"{_format_number(summary['rmse'])} | "
        f"{summary['side_wins']}-{summary['side_losses']} | "
        f"{_format_percent(summary['side_accuracy'])} | "
        f"`{summary['sample_status']}` |"
    )


def build_report(rows: list[dict[str, Any]]) -> str:
    markets = market_projection_rows(rows)
    projection_summaries = [
        summarize_projection(challenger, markets)
        for challenger in CHALLENGERS
    ]
    tracked_summaries = [
        summarize_tracked_pick_alignment(challenger, markets)
        for challenger in CHALLENGERS
    ]

    lines = [
        "# K Projection Shadow Lab",
        "",
        "This report is shadow-only. It does not change live lambda, verdicts, thresholds, staking, provider order, notifications, or calibration.",
        "",
        "## Scope",
        "",
        f"- Clean window start: `{CLEAN_WINDOW_START}`",
        f"- Official-close market rows: `{len(markets)}`",
        f"- Challenger projections: `{', '.join(CHALLENGERS)}`",
        "",
        "## Projection Accuracy",
        "",
        "Error is `actual Ks - projected Ks`; negative means the projection was too high.",
        "",
        "| Challenger | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(_projection_row(summary) for summary in projection_summaries)

    lines.extend(
        [
            "",
            "## Tracked Pick Alignment",
            "",
            "This checks whether a challenger would still point to the side Tyler actually tracked. It is not a replacement betting rule.",
            "",
            "| Challenger | Tracked Rows | Aligned Rows | W-L | Flat PnL | Flat ROI |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_tracked_row(summary) for summary in tracked_summaries)

    lines.extend(["", "## Challenger Slice Checks"])
    for challenger in ("market_shrink_25", "high_line_temper"):
        for field in (
            "side",
            "price_sign",
            "line_bucket",
            "quality_gate_level",
            "model_market_relationship",
            "bet_timing_window",
            "opportunity_bucket",
            "leash_risk_bucket",
            "pitcher_archetype_bucket",
        ):
            lines.extend(
                [
                    "",
                    f"### {challenger} By {field}",
                    "",
                    "| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
                ]
            )
            lines.extend(_slice_row(summary) for summary in summarize_challenger_slices(challenger, markets, field))

    current_bucket_rows = summarize_by_bucket("current_model", markets, "line_bucket")
    lines.extend(
        [
            "",
            "## Current Model By K-Line Bucket",
            "",
            "| K-Line Bucket | Rows | Mean Error | MAE | Side W-L | Side Accuracy |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_bucket_row(summary) for summary in current_bucket_rows)

    archetype_rows = summarize_by_bucket("current_model", markets, "pitcher_archetype_bucket")
    lines.extend(
        [
            "",
            "## Current Model By Pitcher Archetype",
            "",
            "| Archetype | Rows | Mean Error | MAE | Side W-L | Side Accuracy |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(_bucket_row(summary) for summary in archetype_rows)

    lines.extend(
        [
            "",
            "## Read Rule",
            "",
            "- Treat this as a challenger-projection scoreboard, not a production recommendation.",
            "- Prefer challengers that improve MAE/RMSE and side accuracy without depending on post-start data.",
            "- Do not promote a projection adjustment unless it survives later slates and side, price, line, and provider slices.",
            "- If a simple challenger keeps improving, the next step is a Gate C/F promotion plan with a rollback switch.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the K projection shadow lab report.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = build_report(load_jsonl(args.dataset))
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)


if __name__ == "__main__":
    main()
