"""Runtime-safe market-anchored selector metadata.

This module is pure and feature-flagged. In shadow mode it only annotates side
payloads. In enforce_downside mode it can only lower current FIRE exposure and
must not change lambda, thresholds, staking, provider order, notifications,
locks, retention, calibration, or dashboard source-of-truth behavior.
"""

from __future__ import annotations

import copy
import math
import os
from typing import Any

from confidence_referee import (
    VERDICT_ORDER,
    american_to_implied,
    cap_verdict,
    market_favorite_side,
)


VALID_MODES = {"off", "shadow", "enforce_downside"}


def market_anchor_mode() -> str:
    value = os.getenv("MARKET_ANCHOR_SELECTOR_MODE", "off").strip().lower()
    return value if value in VALID_MODES else "off"


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _clamp_probability(value: float) -> float:
    return max(0.0001, min(0.9999, value))


def poisson_cdf(k: int, lam: float) -> float:
    if k < 0:
        return 0.0
    lam = max(0.0, lam)
    term = math.exp(-lam)
    total = term
    for idx in range(1, k + 1):
        term *= lam / idx
        total += term
    return max(0.0, min(1.0, total))


def poisson_over_probability(k_line: float, lam: float) -> float:
    return _clamp_probability(1.0 - poisson_cdf(math.floor(k_line), lam))


def market_implied_projection(k_line: float, over_probability: float) -> float:
    target = _clamp_probability(over_probability)
    low = 0.0
    high = max(12.0, k_line + 8.0)
    while poisson_over_probability(k_line, high) < target and high < 40.0:
        high *= 1.5

    for _ in range(72):
        mid = (low + high) / 2.0
        if poisson_over_probability(k_line, mid) < target:
            low = mid
        else:
            high = mid
    return round((low + high) / 2.0, 4)


def no_vig_side_probability(over_odds: Any, under_odds: Any, side: str) -> float | None:
    over = american_to_implied(over_odds)
    under = american_to_implied(under_odds)
    if over is None or under is None or over + under <= 0:
        return None
    side_value = str(side or "").strip().lower()
    if side_value == "over":
        return round(over / (over + under), 4)
    if side_value == "under":
        return round(under / (over + under), 4)
    return None


def _current_verdict(side_data: dict[str, Any]) -> str:
    return str(side_data.get("actionable_verdict") or side_data.get("verdict") or "PASS").strip() or "PASS"


def _is_fire(verdict: Any) -> bool:
    return str(verdict or "").startswith("FIRE")


def _relationship(record: dict[str, Any], selected_side: str) -> tuple[str, str]:
    favorite_side = market_favorite_side(record.get("best_over_odds"), record.get("best_under_odds"))
    if selected_side == favorite_side:
        return "model_agrees_with_favorite", favorite_side
    if favorite_side in {"over", "under"}:
        return "model_fades_favorite", favorite_side
    return "unknown", favorite_side


def _stable_workload(record: dict[str, Any]) -> bool:
    days = _to_float(record.get("days_since_last_start"))
    pitches = _to_float(record.get("last_pitch_count"))
    if days is not None and days < 4:
        return False
    if pitches is not None and pitches > 110:
        return False
    return True


def _line(record: dict[str, Any]) -> float | None:
    return _to_float(record.get("k_line"))


def _selected_side_probability(k_line: float, projection: float, selected_side: str) -> float:
    over_probability = poisson_over_probability(k_line, projection)
    if selected_side == "over":
        return over_probability
    return _clamp_probability(1.0 - over_probability)


def _baseball_blend_weight(record: dict[str, Any], relationship: str) -> float:
    weight = 0.35
    quality = str(record.get("quality_gate_level") or "").strip().lower()
    line = _line(record)

    if quality and quality not in {"clean", "none"}:
        weight -= 0.10
    if relationship == "model_fades_favorite":
        weight -= 0.10
    if not _stable_workload(record):
        weight -= 0.10
    if line is not None and line >= 7.5:
        weight -= 0.05
    return max(0.15, min(0.45, weight))


def _projected_side(k_line: float, projection: float) -> str | None:
    if projection > k_line:
        return "over"
    if projection < k_line:
        return "under"
    return None


def _selector_metadata(
    record: dict[str, Any],
    selected_side: str,
    side_data: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    line = _line(record)
    current_projection = _to_float(record.get("lambda"))
    over_probability = no_vig_side_probability(
        record.get("best_over_odds"),
        record.get("best_under_odds"),
        "over",
    )
    side_probability = no_vig_side_probability(
        record.get("best_over_odds"),
        record.get("best_under_odds"),
        selected_side,
    )
    relationship, favorite_side = _relationship(record, selected_side)

    market_projection = None
    anchor_projection = current_projection
    anchor_side = None
    anchor_edge = None
    labels: list[str] = []

    if line is not None and over_probability is not None:
        market_projection = market_implied_projection(line, over_probability)
        if current_projection is not None:
            weight = _baseball_blend_weight(record, relationship)
            anchor_projection = round(market_projection + ((current_projection - market_projection) * weight), 4)
        else:
            anchor_projection = market_projection

    if line is not None and anchor_projection is not None:
        anchor_side = _projected_side(line, anchor_projection)
        selected_probability = _selected_side_probability(line, anchor_projection, selected_side)
        if side_probability is not None:
            anchor_edge = round(selected_probability - side_probability, 4)

    if anchor_side == selected_side:
        labels.append("market_anchor_side_agrees")
    if anchor_side == selected_side and anchor_edge is not None and 0.005 <= anchor_edge <= 0.12:
        labels.append("market_anchor_core")

    quality = str(record.get("quality_gate_level") or "").strip().lower()
    clean_quality = quality in {"", "clean", "none"}
    stable_line = line is None or line <= 6.5
    stable_timing = str(record.get("opening_odds_source") or "").strip().lower() in {
        "",
        "full_movement",
        "preview",
    }
    if (
        "market_anchor_core" in labels
        and relationship == "model_agrees_with_favorite"
        and selected_side == favorite_side
        and clean_quality
        and _stable_workload(record)
        and stable_line
        and stable_timing
    ):
        labels.append("market_anchor_strict")

    current_verdict = _current_verdict(side_data)
    would_verdict = current_verdict
    reasons: list[str] = []
    if _is_fire(current_verdict) and "market_anchor_strict" not in labels:
        would_verdict = cap_verdict(current_verdict, "LEAN")
        reasons.append("cap_fire_without_market_anchor_strict")

    applied = mode == "enforce_downside" and VERDICT_ORDER.get(would_verdict, 0) < VERDICT_ORDER.get(current_verdict, 0)

    return {
        "mode": mode,
        "selected_side": selected_side,
        "market_favorite_side": favorite_side,
        "relationship": relationship,
        "no_vig_side_probability": side_probability,
        "market_implied_projection": market_projection,
        "market_anchor_projection": anchor_projection,
        "anchor_side": anchor_side,
        "anchor_edge": anchor_edge,
        "labels": labels,
        "current_verdict": current_verdict,
        "would_verdict": would_verdict,
        "would_cap_to": would_verdict,
        "applied": applied,
        "reasons": reasons,
    }


def apply_market_anchor_selector_to_side(
    record: dict[str, Any],
    side: str,
    side_data: dict[str, Any],
    mode: str | None = None,
) -> dict[str, Any]:
    active_mode = mode or market_anchor_mode()
    if active_mode not in VALID_MODES:
        active_mode = "off"

    updated = copy.deepcopy(side_data)
    if active_mode == "off":
        return updated

    selected_side = str(side or "").strip().lower()
    if selected_side not in {"over", "under"}:
        return updated

    metadata = _selector_metadata(record, selected_side, updated, active_mode)
    updated["market_anchor_selector"] = metadata

    if metadata["applied"]:
        updated["verdict"] = metadata["would_verdict"]
        updated["actionable_verdict"] = metadata["would_verdict"]

    return updated
