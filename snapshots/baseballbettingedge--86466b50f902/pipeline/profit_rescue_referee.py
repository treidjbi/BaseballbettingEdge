"""Runtime-safe FIRE exposure reducer.

This module is pure and feature-flagged. It can only lower FIRE exposure and
must not change projection math, staking, provider order, notifications, locks,
retention, calibration, or dashboard source-of-truth behavior.
"""

from __future__ import annotations

import copy
import os
from typing import Any

from confidence_referee import VERDICT_ORDER, cap_verdict, market_favorite_side


VALID_MODES = {"off", "shadow", "enforce"}


def profit_rescue_mode() -> str:
    value = os.getenv("PROFIT_RESCUE_REFEREE_MODE", "off").strip().lower()
    return value if value in VALID_MODES else "off"


def _is_fire(verdict: Any) -> bool:
    return str(verdict or "").startswith("FIRE")


def _relationship(record: dict[str, Any], selected_side: str) -> tuple[str, str]:
    favorite_side = market_favorite_side(record.get("best_over_odds"), record.get("best_under_odds"))
    if selected_side == favorite_side:
        return "model_agrees_with_favorite", favorite_side
    if favorite_side in {"over", "under"}:
        return "model_fades_favorite", favorite_side
    return "unknown", favorite_side


def apply_profit_rescue_to_side(
    record: dict[str, Any],
    side: str,
    side_data: dict[str, Any],
    mode: str | None = None,
) -> dict[str, Any]:
    active_mode = mode or profit_rescue_mode()
    if active_mode not in VALID_MODES:
        active_mode = "off"

    updated = copy.deepcopy(side_data)
    if active_mode == "off":
        return updated

    selected_side = side.lower()
    relationship, favorite_side = _relationship(record, selected_side)
    current_verdict = updated.get("actionable_verdict") or updated.get("verdict") or "PASS"
    would_cap_to = current_verdict
    reasons: list[str] = []

    if current_verdict == "FIRE 2u":
        would_cap_to = cap_verdict(would_cap_to, "FIRE 1u")
        reasons.append("cap_fire_two_to_fire_one")

    if selected_side == "under" and _is_fire(would_cap_to):
        would_cap_to = cap_verdict(would_cap_to, "LEAN")
        reasons.append("cap_fire_under_to_lean")

    if relationship == "model_fades_favorite" and _is_fire(current_verdict):
        reasons.append("cap_market_fade_fire_to_lean")
        if _is_fire(would_cap_to):
            would_cap_to = cap_verdict(would_cap_to, "LEAN")

    cap_lowers_verdict = VERDICT_ORDER.get(would_cap_to, 0) < VERDICT_ORDER.get(current_verdict, 0)
    applied = active_mode == "enforce" and cap_lowers_verdict

    updated["profit_rescue_referee"] = {
        "mode": active_mode,
        "relationship": relationship,
        "market_favorite_side": favorite_side,
        "selected_side": selected_side,
        "would_cap_to": would_cap_to,
        "applied": applied,
        "reasons": reasons,
    }

    if applied:
        updated["verdict"] = would_cap_to
        updated["actionable_verdict"] = would_cap_to

    return updated
