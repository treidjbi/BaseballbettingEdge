"""Runtime-safe market favorite confidence referee.

This module is pure and feature-flagged. It must not change projection math,
staking, provider order, notifications, locks, or dashboard source-of-truth
behavior.
"""

from __future__ import annotations

import copy
import os
from typing import Any


VALID_MODES = {"off", "shadow", "enforce"}

VERDICT_ORDER = {
    "PASS": 0,
    "LEAN": 1,
    "FIRE 1u": 2,
    "FIRE 2u": 3,
}
ORDER_VERDICT = {rank: verdict for verdict, rank in VERDICT_ORDER.items()}


def referee_mode() -> str:
    value = os.getenv("MARKET_FAVORITE_REFEREE_MODE", "off").strip().lower()
    return value if value in VALID_MODES else "off"


def american_to_implied(odds: Any) -> float | None:
    if isinstance(odds, bool):
        return None
    try:
        value = int(odds)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    if value > 0:
        return 100.0 / (value + 100.0)
    return abs(value) / (abs(value) + 100.0)


def market_favorite_side(over_odds: Any, under_odds: Any) -> str:
    over_prob = american_to_implied(over_odds)
    under_prob = american_to_implied(under_odds)
    if over_prob is None or under_prob is None:
        return "unknown"
    if abs(over_prob - under_prob) < 0.0001:
        return "tie"
    return "over" if over_prob > under_prob else "under"


def cap_verdict(verdict: str, max_verdict: str) -> str:
    current_order = VERDICT_ORDER.get(verdict, VERDICT_ORDER["PASS"])
    max_order = VERDICT_ORDER.get(max_verdict, VERDICT_ORDER["PASS"])
    return ORDER_VERDICT[min(current_order, max_order)]


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _projection_margin(record: dict[str, Any], side: str) -> float | None:
    lam = _to_float(record.get("lambda"))
    k_line = _to_float(record.get("k_line"))
    if lam is None or k_line is None:
        return None
    if side == "over":
        return round(lam - k_line, 3)
    if side == "under":
        return round(k_line - lam, 3)
    return None


def _price_sign(odds: Any) -> str:
    value = _to_float(odds)
    if value is None:
        return "unknown"
    if value > 0:
        return "plus"
    if value < 0:
        return "minus"
    return "unknown"


def _line_bucket(k_line: Any) -> str:
    value = _to_float(k_line)
    if value is None:
        return "unknown"
    if value >= 7.5:
        return "7.5+"
    return f"{value:.1f}"


def _price_driven_fade_reasons(
    record: dict[str, Any],
    side: str,
    side_data: dict[str, Any],
    selected_odds: Any,
) -> list[str]:
    reasons: list[str] = []
    edge = _to_float(side_data.get("edge"))
    margin = _projection_margin(record, side)

    if _price_sign(selected_odds) == "plus" and (edge is None or edge < 0.04):
        reasons.append("plus_money_thin_edge")
    if margin is None or margin < 0.75:
        reasons.append("thin_projection_margin")
    if side == "under" and _line_bucket(record.get("k_line")) in {"5.5", "6.5", "7.5+"}:
        reasons.append("under_line_bucket_caution")
    if record.get("quality_gate_level") in {"capped", "blocked"}:
        reasons.append("quality_gate_capped_or_blocked")

    return reasons


def apply_referee_to_side(
    record: dict[str, Any],
    side: str,
    side_data: dict[str, Any],
    mode: str | None = None,
) -> dict[str, Any]:
    active_mode = mode or referee_mode()
    if active_mode not in VALID_MODES:
        active_mode = "off"

    updated = copy.deepcopy(side_data)
    if active_mode == "off":
        return updated

    selected_side = side.lower()
    selected_odds = record.get(f"best_{selected_side}_odds")
    favorite_side = market_favorite_side(record.get("best_over_odds"), record.get("best_under_odds"))
    if selected_side == favorite_side:
        relationship = "model_agrees_with_favorite"
    elif favorite_side in {"over", "under"}:
        relationship = "model_fades_favorite"
    else:
        relationship = "unknown"

    current_verdict = updated.get("actionable_verdict") or updated.get("verdict") or "PASS"
    would_cap_to = current_verdict
    reasons: list[str] = []

    if relationship == "model_fades_favorite":
        price_reasons = _price_driven_fade_reasons(record, selected_side, updated, selected_odds)
        if price_reasons:
            would_cap_to = cap_verdict(current_verdict, "LEAN")
            reasons = ["price_driven_market_fade", *price_reasons]
        elif current_verdict == "FIRE 2u":
            would_cap_to = "FIRE 1u"
            reasons = ["market_fade_caps_fire_two"]

    cap_lowers_verdict = VERDICT_ORDER.get(would_cap_to, 0) < VERDICT_ORDER.get(current_verdict, 0)
    applied = active_mode == "enforce" and cap_lowers_verdict

    updated["confidence_referee"] = {
        "mode": active_mode,
        "relationship": relationship,
        "market_favorite_side": favorite_side,
        "selected_side": selected_side,
        "selected_odds": selected_odds,
        "price_sign": _price_sign(selected_odds),
        "projection_margin_ks": _projection_margin(record, selected_side),
        "probability_edge": updated.get("edge"),
        "would_cap_to": would_cap_to,
        "applied": applied,
        "reasons": reasons,
    }

    if applied:
        updated["verdict"] = would_cap_to
        updated["actionable_verdict"] = would_cap_to

    return updated
