"""Audit the frozen no-drag composite as post-grading research only.

This diagnostic cannot change live picks, model math, verdicts, staking,
providers, notifications, locks, UI, retention, artifacts, or source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import gate_f_preclose_clv_proxy_lab as preclose_proxy
from analytics.diagnostics import strong_base_decision_lab as strong_base
from pipeline.name_utils import normalize

DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT_MD = ROOT / "analytics" / "output" / "no_drag_composite_canary_audit.md"
DEFAULT_OUTPUT_JSON = ROOT / "analytics" / "output" / "no_drag_composite_canary_audit.json"
SELECTOR_ID = "combined_runtime_broad_no_hindsight_no_drag_v1"
SELECTOR_VERSION = 1
CLEAN_WINDOW_START = "2026-04-28"
HISTORICAL_END = "2026-07-20"
PROSPECTIVE_START = "2026-07-21"
CURRENT_PROVIDER_START = "2026-06-24"
REVIEW_FLOOR = 75
LOCKED_HISTORICAL = {"rows": 186, "wins": 124, "losses": 62, "pnl": 29.20, "roi": 0.157}
LOCKED_CURRENT_PROVIDER = {"rows": 52, "wins": 36, "losses": 16, "pnl": 9.17, "roi": 0.176}
LOCKED_RECENT_REFERENCE = {"rows": 35, "wins": 24, "losses": 11, "pnl": 5.68, "roi": 0.162}
BASELINE_PNL_TOLERANCE = 0.005
WIN_LOSS_RESULTS = {"win", "loss"}
VERDICT_FIELDS = (
    "display_verdict",
    "locked_verdict",
    "actionable_verdict",
    "current_verdict",
    "verdict",
)

RULE_SPEC = {
    "selector_id": SELECTOR_ID,
    "version": SELECTOR_VERSION,
    "prospective_start": PROSPECTIVE_START,
    "verdict_precedence": list(VERDICT_FIELDS),
    "adjusted_ev": {
        "precedence": ["locked_adj_ev", "adj_ev", "ev"],
        "join": "python_truthy_or",
        "buckets": [
            {"label": "ev_negative", "min": None, "max_exclusive": 0.0},
            {"label": "ev_0_to_6", "min": 0.0, "max_exclusive": 0.06},
            {"label": "ev_6_to_17", "min": 0.06, "max_exclusive": 0.17},
            {"label": "ev_17_plus", "min": 0.17, "max_exclusive": None},
        ],
    },
    "keep_fire": {
        "keep_fire_market_agreed_moderate_ev": {
            "verdict": "FIRE*",
            "model_market_relationship": "model_agrees_with_favorite",
            "adjusted_ev_bucket": "ev_6_to_17",
            "bet_timing_window": "pre_30",
        },
        "keep_fire_over_moderate_ev_normal_leash": {
            "verdict": "FIRE*",
            "side": "over",
            "adjusted_ev_bucket": "ev_6_to_17",
            "leash_or_opportunity_bucket": "normal",
        },
    },
    "expand_lean": {
        "expand_lean_45_low_ev_normal_leash": {
            "verdict": "LEAN",
            "line_bucket": "4.5",
            "adjusted_ev_bucket": "ev_0_to_6",
            "leash_or_opportunity_bucket": "normal",
        },
        "expand_lean_low_k_standard_no_vig": {
            "verdict": "LEAN",
            "pitcher_archetype_bucket": "low_k_standard",
            "model_no_vig_gap_min": 0.02,
        },
        "expand_lean_low_line_capped_model_fade": {
            "verdict": "LEAN",
            "line_bucket": "2.5-3.5",
            "model_market_relationship": "model_fades_favorite",
            "quality_gate_level": "capped",
        },
    },
    "market_anchor": {
        "label": "market_anchor_strict",
        "sources": ["market_anchor_selector.labels", "market_anchor_selector_labels"],
    },
    "drag": {
        "cap_high_raw_edge": {"edge_min": 0.06},
        "cap_market_fade": {"model_market_relationship": "model_fades_favorite"},
        "cap_fire_under_market_fade": {
            "verdict": "FIRE*",
            "side": "under",
            "model_market_relationship": "model_fades_favorite",
        },
    },
    "formula": "(strict_runtime_core OR selective_lean OR market_anchor_strict) AND NOT drag_core",
}
RULE_FINGERPRINT = hashlib.sha256(
    json.dumps(RULE_SPEC, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class Evaluation:
    qualifies: bool
    families: tuple[str, ...]
    drag_labels: tuple[str, ...]
    missing_inputs: tuple[str, ...]


def to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def verdict(row: dict[str, Any]) -> str:
    return str(next((row.get(field) for field in VERDICT_FIELDS if row.get(field)), "")).strip()


def adjusted_ev(row: dict[str, Any]) -> float | None:
    return to_float(row.get("locked_adj_ev")) or to_float(row.get("adj_ev")) or to_float(row.get("ev"))


def ev_bucket(row: dict[str, Any]) -> str:
    value = adjusted_ev(row)
    if value is None:
        return "ev_unknown"
    if value < 0:
        return "ev_negative"
    if value < 0.06:
        return "ev_0_to_6"
    if value < 0.17:
        return "ev_6_to_17"
    return "ev_17_plus"


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def market_anchor_labels(row: dict[str, Any]) -> set[str]:
    nested = _json_object(row.get("market_anchor_selector")).get("labels") or []
    flat = row.get("market_anchor_selector_labels") or []

    def values(value: Any) -> list[Any]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return []

    return {
        str(label).strip()
        for label in values(nested) + values(flat)
        if str(label or "").strip()
    }


def evaluate_row(row: dict[str, Any]) -> Evaluation:
    selected_verdict = verdict(row)
    is_fire = selected_verdict.startswith("FIRE")
    is_lean = selected_verdict == "LEAN"
    side = str(row.get("side") or "").strip().lower()
    relationship = str(row.get("model_market_relationship") or "").strip()
    line_bucket = str(row.get("line_bucket") or "").strip()
    leash = str(row.get("leash_risk_bucket") or row.get("opportunity_bucket") or "").strip().lower()
    quality = str(row.get("quality_gate_level") or "").strip().lower()
    timing = str(row.get("bet_timing_window") or "").strip()
    archetype = str(row.get("pitcher_archetype_bucket") or "").strip()
    no_vig_gap = to_float(row.get("model_no_vig_gap"))
    families: list[str] = []
    drag_labels: list[str] = []

    edge = to_float(row.get("edge"))
    if edge is not None and edge >= 0.06:
        drag_labels.append("cap_high_raw_edge")
    if relationship == "model_fades_favorite":
        drag_labels.append("cap_market_fade")
    if is_fire and side == "under" and relationship == "model_fades_favorite":
        drag_labels.append("cap_fire_under_market_fade")

    keep_fire = is_fire and (
        (
            relationship == "model_agrees_with_favorite"
            and ev_bucket(row) == "ev_6_to_17"
            and timing == "pre_30"
        )
        or (
            side == "over"
            and ev_bucket(row) == "ev_6_to_17"
            and leash == "normal"
        )
    )
    if keep_fire and not drag_labels:
        families.append("strong_base_strict_runtime_core")

    selective_lean = is_lean and (
        (
            line_bucket == "4.5"
            and ev_bucket(row) == "ev_0_to_6"
            and leash == "normal"
        )
        or (
            archetype == "low_k_standard"
            and no_vig_gap is not None
            and no_vig_gap >= 0.02
        )
        or (
            line_bucket == "2.5-3.5"
            and relationship == "model_fades_favorite"
            and quality == "capped"
        )
    )
    if selective_lean and not {
        "cap_high_raw_edge",
        "cap_fire_under_market_fade",
    }.intersection(drag_labels):
        families.append("strong_base_selective_lean")

    if "market_anchor_strict" in market_anchor_labels(row):
        families.append("market_anchor_strict")

    return Evaluation(
        qualifies=bool(families) and not drag_labels,
        families=tuple(families),
        drag_labels=tuple(drag_labels),
        missing_inputs=(),
    )
