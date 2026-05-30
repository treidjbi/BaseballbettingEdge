"""Shadow-only Gate E/F candidate labels for runtime-safe diagnostics.

This module is analysis-only. It must not change live model behavior,
pipeline behavior, thresholds, staking, provider order, dashboard artifacts,
notification behavior, or params.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_PATH = ROOT / "analytics" / "output" / "gate_ef_candidate_shadow_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
FIRE_VERDICTS = {"FIRE 1u", "FIRE 2u"}
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
