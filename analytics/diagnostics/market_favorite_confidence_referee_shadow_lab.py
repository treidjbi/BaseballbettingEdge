"""Shadow lab for market-favorite confidence-referee candidates.

This diagnostic is analysis-only. It must not change live lambda, verdicts,
thresholds, staking, provider order, notifications, calibration, locks, or
dashboard artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_PATH = ROOT / "analytics" / "output" / "market_favorite_confidence_referee_shadow_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}

RUNTIME_SAFE_FIELDS = {
    "side",
    "k_line",
    "line_bucket",
    "american_odds",
    "price_sign",
    "market_favorite_side",
    "favorite_gap_no_vig",
    "model_side",
    "model_market_relationship",
    "projected_ks",
    "edge",
    "ev",
    "adj_ev",
    "verdict",
    "locked_verdict",
    "quality_gate_level",
    "bet_timing_window",
    "opportunity_bucket",
    "leash_risk_bucket",
    "pitcher_archetype_bucket",
}


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def load_jsonl(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tracked(row: dict[str, Any]) -> bool:
    return (
        str(row.get("slate_date") or "") >= CLEAN_WINDOW_START
        and row.get("context_snapshot") == "official_close"
        and row.get("is_tracked_pick") is True
        and row.get("result") in WIN_LOSS_RESULTS
        and _text(row.get("side")) in {"over", "under"}
    )


def _caution_count(row: dict[str, Any]) -> int:
    caution = 0
    if row.get("quality_gate_level") in {"capped", "unknown", None}:
        caution += 1
    if row.get("bet_timing_window") in {"pre_15", "pre_5", "post_start", "unknown"}:
        caution += 1
    if _text(row.get("side")) == "under" and row.get("line_bucket") in {"5.5", "6.5", "7.5+"}:
        caution += 1
    if row.get("leash_risk_bucket") in {"medium", "high"}:
        caution += 1
    return caution


def candidate_flags(row: dict[str, Any]) -> dict[str, bool]:
    side = _text(row.get("side"))
    favorite = _text(row.get("market_favorite_side"))
    model_side = _text(row.get("model_side")) or side
    agrees = side in {"over", "under"} and favorite in {"over", "under"} and model_side == favorite
    fades = side in {"over", "under"} and favorite in {"over", "under"} and model_side != favorite

    return {
        "current_model_tracked": _tracked(row),
        "model_agrees_market_favorite": _tracked(row) and agrees,
        "model_fades_market_favorite": _tracked(row) and fades,
        "over_agrees_market_favorite": _tracked(row) and side == "over" and agrees,
        "under_agrees_market_favorite": _tracked(row) and side == "under" and agrees,
        "market_favorite_referee_candidate": _tracked(row)
        and agrees
        and row.get("quality_gate_level") in {"clean", "capped"}
        and row.get("bet_timing_window") not in {"post_start", "unknown"},
        "market_fade_warning_candidate": _tracked(row) and fades and _caution_count(row) >= 1,
    }
