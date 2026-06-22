"""Feature-flagged market-shrink projection challenger.

Runtime-safe: uses only current model lambda and the posted K line.
"""

from __future__ import annotations

import os
from typing import Any


VALID_MODES = {"off", "shadow", "enforce"}
MARKET_SHRINK_WEIGHTS = {
    "market_shrink_15": 0.15,
    "market_shrink_25": 0.25,
    "market_shrink_35": 0.35,
}
DEFAULT_CANDIDATE = "market_shrink_25"


def projection_challenger_mode(value: str | None = None) -> str:
    raw = (value if value is not None else os.getenv("MARKET_SHRINK_PROJECTION_MODE", "off")).strip().lower()
    return raw if raw in VALID_MODES else "off"


def projection_challenger_candidate(value: str | None = None) -> str:
    raw = (
        value
        if value is not None
        else os.getenv("MARKET_SHRINK_PROJECTION_CANDIDATE", DEFAULT_CANDIDATE)
    ).strip().lower()
    return raw if raw in MARKET_SHRINK_WEIGHTS else DEFAULT_CANDIDATE


def market_shrink_projection(current_lambda: float, k_line: float, candidate: str) -> tuple[float, float]:
    weight = MARKET_SHRINK_WEIGHTS[candidate]
    projected = current_lambda + ((k_line - current_lambda) * weight)
    return round(projected, 3), weight


def apply_projection_challenger(
    current_lambda: float,
    k_line: float,
    *,
    mode: str | None = None,
    candidate: str | None = None,
) -> dict[str, Any]:
    resolved_mode = projection_challenger_mode(mode)
    requested_candidate = (
        candidate
        if candidate is not None
        else os.getenv("MARKET_SHRINK_PROJECTION_CANDIDATE", DEFAULT_CANDIDATE)
    ).strip().lower()
    if requested_candidate not in MARKET_SHRINK_WEIGHTS:
        return {
            "mode": resolved_mode,
            "candidate": requested_candidate,
            "applied": False,
            "current_lambda": round(current_lambda, 3),
            "would_lambda": round(current_lambda, 3),
            "selected_lambda": round(current_lambda, 3),
            "k_line": k_line,
            "weight": None,
            "delta": 0.0,
            "reason": "invalid_candidate",
        }

    would_lambda, weight = market_shrink_projection(current_lambda, k_line, requested_candidate)
    selected_lambda = would_lambda if resolved_mode == "enforce" else round(current_lambda, 3)
    return {
        "mode": resolved_mode,
        "candidate": requested_candidate,
        "applied": resolved_mode == "enforce",
        "current_lambda": round(current_lambda, 3),
        "would_lambda": would_lambda,
        "selected_lambda": selected_lambda,
        "k_line": k_line,
        "weight": weight,
        "delta": round(would_lambda - current_lambda, 3),
        "reason": "enforced" if resolved_mode == "enforce" else "shadow_only" if resolved_mode == "shadow" else "off",
    }
