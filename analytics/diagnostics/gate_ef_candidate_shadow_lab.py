"""Shadow-only Gate E/F candidate labels for runtime-safe diagnostics.

This module is analysis-only. It must not change live model behavior,
pipeline behavior, thresholds, staking, provider order, dashboard artifacts,
notification behavior, or params.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_PATH = ROOT / "analytics" / "output" / "gate_ef_candidate_shadow_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
FIRE_VERDICTS = {"FIRE 1u", "FIRE 2u"}
CANDIDATE_NAMES = (
    "current_fire_flat",
    "current_fire_over",
    "current_fire_under",
    "fire_without_under_skeptic_2plus",
    "fire_without_under_skeptic_3plus",
    "fire_mid_edge",
    "fire_not_high_adj_ev",
    "fire_model_margin_under_1_5",
    "fire_clean_quality",
    "fire_combined_skeptic",
)
RUNTIME_SAFE_FIELDS = {
    "side",
    "line_bucket",
    "price_sign",
    "model_market_relationship",
    "bet_timing_window",
    "quality_gate_level",
    "pitcher_archetype_bucket",
    "opportunity_bucket",
    "locked_verdict",
    "actionable_verdict",
    "verdict",
    "edge",
    "locked_adj_ev",
    "adj_ev",
    "projected_ks",
    "applied_lambda",
    "raw_lambda",
    "lambda",
    "locked_k_line",
    "k_line",
    "line",
}
PROJECTION_KEYS = ("projected_ks", "applied_lambda", "raw_lambda", "lambda")
HIGH_LINE_BUCKETS = {"5.5", "6.5", "7.5+"}


def to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
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


def current_verdict(row: dict[str, Any]) -> str:
    return str(
        row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("verdict")
        or ""
    )


def is_current_fire(row: dict[str, Any]) -> bool:
    return current_verdict(row) in FIRE_VERDICTS


def current_adj_ev(row: dict[str, Any]) -> float | None:
    locked = to_float(row.get("locked_adj_ev"))
    if locked is not None:
        return locked
    return to_float(row.get("adj_ev"))


def current_projection(row: dict[str, Any]) -> float | None:
    for key in PROJECTION_KEYS:
        value = to_float(row.get(key))
        if value is not None:
            return value
    return None


def current_line(row: dict[str, Any]) -> float | None:
    locked = to_float(row.get("locked_k_line"))
    if locked is not None:
        return locked
    value = to_float(row.get("k_line"))
    if value is not None:
        return value
    return to_float(row.get("line"))


def picked_side_model_margin(row: dict[str, Any]) -> float | None:
    projection = current_projection(row)
    line = current_line(row)
    side = str(row.get("side") or "").lower()
    if projection is None or line is None:
        return None
    if side == "over":
        return round(projection - line, 3)
    if side == "under":
        return round(line - projection, 3)
    return None


def under_skeptic_reasons(row: dict[str, Any]) -> list[str]:
    if str(row.get("side") or "").lower() != "under":
        return []

    reasons: list[str] = []
    line_bucket = str(row.get("line_bucket") or "")
    if line_bucket in HIGH_LINE_BUCKETS:
        reasons.append("under_high_line")
    if row.get("price_sign") == "minus":
        reasons.append("under_minus_price")
    if row.get("model_market_relationship") == "model_agrees_with_favorite":
        reasons.append("under_market_favorite_agreement")
    if row.get("bet_timing_window") not in {"pre_120", "pre_60", "pre_30"}:
        reasons.append("under_late_or_unknown_timing")
    if row.get("quality_gate_level") in {None, "", "unknown", "capped", "soft_cap"}:
        reasons.append("under_capped_or_unknown_quality")
    if str(row.get("pitcher_archetype_bucket") or "").startswith("high_k"):
        reasons.append("under_high_k_archetype")
    if row.get("opportunity_bucket") == "deep_starter":
        reasons.append("under_deep_starter_opportunity")
    return reasons


def candidate_flags(row: dict[str, Any]) -> dict[str, bool]:
    current_fire = is_current_fire(row)
    side = str(row.get("side") or "").lower()
    reasons = under_skeptic_reasons(row)
    under_skeptic_2plus = len(reasons) >= 2
    under_skeptic_3plus = len(reasons) >= 3
    edge = to_float(row.get("edge"))
    adj_ev = current_adj_ev(row)
    margin = picked_side_model_margin(row)

    return {
        "current_fire_flat": current_fire,
        "current_fire_over": current_fire and side == "over",
        "current_fire_under": current_fire and side == "under",
        "under_skeptic_2plus": under_skeptic_2plus,
        "under_skeptic_3plus": under_skeptic_3plus,
        "fire_without_under_skeptic_2plus": current_fire and not under_skeptic_2plus,
        "fire_without_under_skeptic_3plus": current_fire and not under_skeptic_3plus,
        "fire_mid_edge": current_fire and edge is not None and 0.02 <= edge < 0.06,
        "fire_not_high_adj_ev": current_fire and adj_ev is not None and adj_ev < 0.17,
        "fire_model_margin_under_1_5": current_fire and margin is not None and margin < 1.5,
        "fire_clean_quality": current_fire and row.get("quality_gate_level") == "clean",
        "fire_combined_skeptic": (
            current_fire
            and not under_skeptic_2plus
            and adj_ev is not None
            and adj_ev < 0.17
            and edge is not None
            and edge < 0.06
        ),
    }


def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def clean_tracked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("slate_date") or "") >= CLEAN_WINDOW_START
        and row.get("result") in WIN_LOSS_RESULTS
        and row.get("is_tracked_pick") is True
    ]


def summarize_candidate(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    clean_rows = clean_tracked_rows(rows)
    current_fire_rows = [
        (index, row)
        for index, row in enumerate(clean_rows)
        if candidate_flags(row)["current_fire_flat"]
    ]
    selected = [
        (index, row)
        for index, row in enumerate(clean_rows)
        if candidate_flags(row).get(name, False)
    ]
    selected_indices = {index for index, _row in selected}
    avoided = [
        row
        for index, row in current_fire_rows
        if index not in selected_indices
    ]
    selected_rows = [row for _index, row in selected]

    wins = sum(1 for row in selected_rows if row.get("result") == "win")
    losses = sum(1 for row in selected_rows if row.get("result") == "loss")
    flat_pnl = round(sum(_row_pnl(row) for row in selected_rows), 2)
    flat_roi = round(flat_pnl / len(selected_rows), 4) if selected_rows else None

    return {
        "name": name,
        "selected": len(selected_rows),
        "wins": wins,
        "losses": losses,
        "flat_pnl": flat_pnl,
        "flat_roi": flat_roi,
        "current_fire_rows": len(current_fire_rows),
        "current_fire_1u_losses_avoided": sum(
            1
            for row in avoided
            if current_verdict(row) == "FIRE 1u" and row.get("result") == "loss"
        ),
        "current_fire_2u_wins_retained": sum(
            1
            for row in selected_rows
            if current_verdict(row) == "FIRE 2u" and row.get("result") == "win"
        ),
    }


def _format_roi(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value * 100:+.1f}%"


def _candidate_row(summary: dict[str, Any]) -> str:
    return (
        f"| {summary['name']} "
        f"| {summary['selected']} "
        f"| {summary['wins']}-{summary['losses']} "
        f"| {summary['flat_pnl']:+.2f} "
        f"| {_format_roi(summary['flat_roi'])} "
        f"| {summary['current_fire_1u_losses_avoided']} "
        f"| {summary['current_fire_2u_wins_retained']} |"
    )


def build_report(
    rows: list[dict[str, Any]],
    input_warning: str | None = None,
) -> str:
    clean_rows = clean_tracked_rows(rows)
    summaries = [summarize_candidate(name, rows) for name in CANDIDATE_NAMES]
    table_rows = "\n".join(_candidate_row(summary) for summary in summaries)
    warning_section = []
    if input_warning:
        warning_section = [
            "## Input Warning",
            "",
            f"**{input_warning}**",
            "",
        ]

    return "\n".join(
        [
            "# Gate E/F Candidate Shadow Lab",
            "",
            "**Shadow-only warning:** This report is analysis-only. It must not change live model behavior, production thresholds, staking, provider order, dashboard artifacts consumed by the app, notifications, or source-of-truth behavior.",
            "",
            *warning_section,
            "## Scope",
            "",
            f"- Clean evaluation window starts at `{CLEAN_WINDOW_START}`.",
            f"- Clean tracked rows included: `{len(clean_rows)}`.",
            "- Candidate labels use runtime-safe fields for shadow diagnostics only.",
            "",
            "## Candidate Scoreboard",
            "",
            "| Candidate | Selected | W-L | Flat PnL | ROI | FIRE 1u losses avoided | FIRE 2u wins retained |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            table_rows,
            "",
            "## Promotion Discussion Check",
            "",
            "- These rows are not production approval.",
            "- A later Tyler-approved production plan is required before any candidate can affect live picks, thresholds, staking, notifications, provider behavior, or dashboard source-of-truth artifacts.",
            "- Promotion discussion should compare this shadow evidence against the current live lambda baseline and the broader Gate E/F evidence package.",
        ]
    )


def main() -> None:
    input_warning = None
    if not DATASET_PATH.exists():
        input_warning = (
            f"Input dataset is missing at `{DATASET_PATH}`. "
            "zero-row output is not decision evidence."
        )
    rows = load_jsonl(DATASET_PATH)
    report = build_report(rows, input_warning=input_warning)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(f"{report}\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
