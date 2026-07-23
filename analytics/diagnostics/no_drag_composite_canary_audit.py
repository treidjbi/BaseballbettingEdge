"""Audit the frozen no-drag composite as post-grading research only.

This diagnostic cannot change live picks, model math, verdicts, staking,
providers, notifications, locks, UI, retention, artifacts, or source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import gate_f_preclose_clv_proxy_lab as preclose_proxy
from analytics.diagnostics import strong_base_decision_lab as strong_base
from market_infra import alternative_pick_selector as alternative_selector
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
CLEAN_WINDOW_START_DATE = date.fromisoformat(CLEAN_WINDOW_START)
HISTORICAL_END_DATE = date.fromisoformat(HISTORICAL_END)
PROSPECTIVE_START_DATE = date.fromisoformat(PROSPECTIVE_START)
CURRENT_PROVIDER_START_DATE = date.fromisoformat(CURRENT_PROVIDER_START)
LOCKED_HISTORICAL = {"rows": 186, "wins": 124, "losses": 62, "pnl": 29.20, "roi": 0.157}
LOCKED_CURRENT_PROVIDER = {"rows": 52, "wins": 36, "losses": 16, "pnl": 9.17, "roi": 0.176}
LOCKED_RECENT_REFERENCE = {"rows": 35, "wins": 24, "losses": 11, "pnl": 5.68, "roi": 0.162}
BASELINE_PNL_TOLERANCE = 0.005
HISTORY_RECOVERED_ARCHIVE_SOURCE = "picks_history_exact"
WIN_LOSS_RESULTS = {"win", "loss"}
VERDICT_FIELDS = (
    "display_verdict",
    "locked_verdict",
    "actionable_verdict",
    "current_verdict",
    "verdict",
)
ADJUSTED_EV_FIELDS = ("locked_adj_ev", "adj_ev", "ev")
CRITICAL_INPUT_GROUPS = (
    ("slate_date",),
    ("normalized_pitcher", "pitcher", "player_name"),
    ("side",),
    ("result",),
    ("pick_history_pnl", "pnl", "theoretical_pnl"),
    VERDICT_FIELDS,
    ("edge",),
    ("locked_adj_ev", "adj_ev", "ev"),
    ("model_market_relationship",),
    ("line_bucket",),
    ("price_sign",),
    ("price_bucket",),
    ("bet_timing_window",),
    ("leash_risk_bucket", "opportunity_bucket"),
    ("pitcher_archetype_bucket",),
    ("model_no_vig_gap",),
    ("quality_gate_level",),
    ("batter_handedness_mode",),
)
NUMERIC_CRITICAL_GROUPS = {
    ("pick_history_pnl", "pnl", "theoretical_pnl"),
    ("edge",),
    ("locked_adj_ev", "adj_ev", "ev"),
    ("model_no_vig_gap",),
}
SLICE_DIMENSIONS = (
    "verdict_family",
    "side",
    "k_line",
    "price_sign",
    "price_bucket",
    "quality",
    "path_b",
    "model_market",
    "workload_leash",
    "market_anchor",
    "market_agreement",
    "preclose_clv_proxy",
    "final_clv",
    "provider_era",
    "provider_attribution",
    "recent_14_slates",
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


@dataclass(frozen=True)
class _AdjustedEvResolution:
    value: float | None
    non_finite_field: str | None
    finite_input_present: bool


def to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def verdict(row: dict[str, Any]) -> str:
    return alternative_selector.display_verdict(row)


def _numeric_candidate(value: Any) -> tuple[str, float | None]:
    if value is None or isinstance(value, bool):
        return "absent_or_unparseable", None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "absent_or_unparseable", None
    if not math.isfinite(number):
        return "non_finite_truthy", None
    if number == 0.0:
        return "finite_zero", number
    return "finite_truthy", number


def _resolve_adjusted_ev(row: dict[str, Any]) -> _AdjustedEvResolution:
    finite_input_present = False
    for field in ADJUSTED_EV_FIELDS:
        state, value = _numeric_candidate(row.get(field))
        if state == "finite_zero":
            finite_input_present = True
            continue
        if state == "non_finite_truthy":
            return _AdjustedEvResolution(
                value=None,
                non_finite_field=field,
                finite_input_present=finite_input_present,
            )
        if state == "finite_truthy":
            return _AdjustedEvResolution(
                value=value,
                non_finite_field=None,
                finite_input_present=True,
            )
    return _AdjustedEvResolution(
        value=None,
        non_finite_field=None,
        finite_input_present=finite_input_present,
    )


def adjusted_ev(row: dict[str, Any]) -> float | None:
    return _resolve_adjusted_ev(row).value


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


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def parse_slate_date(row: dict[str, Any]) -> date | None:
    raw_value = row.get("slate_date")
    if raw_value is None:
        return None
    normalized = str(raw_value).strip()[:10]
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _slate_date(row: dict[str, Any]) -> str:
    parsed = parse_slate_date(row)
    return parsed.isoformat() if parsed is not None else ""


def missing_critical_inputs(row: dict[str, Any]) -> tuple[str, ...]:
    slate_date = parse_slate_date(row)
    if slate_date is None:
        return ("slate_date",)
    if slate_date < PROSPECTIVE_START_DATE:
        return ()
    missing: list[str] = []
    for group in CRITICAL_INPUT_GROUPS:
        if group == ADJUSTED_EV_FIELDS:
            resolution = _resolve_adjusted_ev(row)
            if resolution.non_finite_field is not None:
                missing.append(f"{resolution.non_finite_field}:non_finite")
            elif not resolution.finite_input_present:
                missing.append("|".join(group))
            continue
        if group in NUMERIC_CRITICAL_GROUPS:
            present = any(to_float(row.get(field)) is not None for field in group)
        else:
            present = any(_value_present(row.get(field)) for field in group)
        if not present:
            missing.append("|".join(group))
    raw_selector = row.get("market_anchor_selector")
    selector = _json_object(raw_selector)
    if (
        raw_selector is not None
        and selector
        and "labels" not in selector
        and not _value_present(row.get("market_anchor_selector_labels"))
    ):
        missing.append("market_anchor_selector.labels|market_anchor_selector_labels")
    return tuple(missing)


def evaluate_row(row: dict[str, Any]) -> Evaluation:
    shared = alternative_selector.no_drag_diagnostic_predicate(row)
    return Evaluation(
        qualifies=shared["qualifies"],
        families=shared["families"],
        drag_labels=shared["drag_labels"],
        missing_inputs=missing_critical_inputs(row),
    )


def pick_key(row: dict[str, Any]) -> str:
    slate_date = _slate_date(row)
    pitcher_source = row.get("normalized_pitcher") or row.get("pitcher") or row.get("player_name") or ""
    pitcher = normalize(pitcher_source).strip()
    side = str(row.get("side") or "").strip().lower()
    return "|".join((slate_date, pitcher, side))


def row_pnl(row: dict[str, Any]) -> float | None:
    for field in ("pick_history_pnl", "pnl", "theoretical_pnl"):
        value = to_float(row.get(field))
        if value is not None:
            return value
    return None


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(row.get("result") == "win" for row in rows)
    losses = sum(row.get("result") == "loss" for row in rows)
    pnl = 0.0
    for row in rows:
        pnl = round(pnl + (row_pnl(row) or 0.0), 3)
    count = wins + losses
    return {
        "rows": count,
        "wins": wins,
        "losses": losses,
        "pnl": pnl,
        "roi": round(pnl / count, 4) if count else 0.0,
    }


def _is_tracked(row: dict[str, Any]) -> bool:
    value = row.get("is_tracked_pick")
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _text_or_missing(value: Any) -> str:
    text = str(value or "").strip()
    return text or "missing"


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _slice_bucket(
    dimension: str,
    row: dict[str, Any],
    recent_dates: set[str],
) -> str:
    if dimension == "verdict_family":
        selected = verdict(row)
        if selected.startswith("FIRE"):
            return "FIRE"
        if selected == "LEAN":
            return "LEAN"
        return "other"
    if dimension == "side":
        side = str(row.get("side") or "").strip().lower()
        return side if side in {"over", "under"} else "missing"
    if dimension == "k_line":
        return _text_or_missing(row.get("line_bucket"))
    if dimension == "price_sign":
        return _text_or_missing(row.get("price_sign"))
    if dimension == "price_bucket":
        return _text_or_missing(row.get("price_bucket"))
    if dimension == "quality":
        return _text_or_missing(row.get("quality_gate_level"))
    if dimension == "path_b":
        return strong_base.path_b_coverage_bucket(row)
    if dimension == "model_market":
        return _text_or_missing(row.get("model_market_relationship"))
    if dimension == "workload_leash":
        return _text_or_missing(
            _first_non_empty(row.get("leash_risk_bucket"), row.get("opportunity_bucket"))
        )
    if dimension == "market_anchor":
        labels = market_anchor_labels(row)
        if "market_anchor_strict" in labels:
            return "market_anchor_strict"
        if "market_anchor_core" in labels:
            return "market_anchor_core"
        return "none"
    if dimension == "market_agreement":
        return _text_or_missing(row.get("market_agreement_label"))
    if dimension == "preclose_clv_proxy":
        return preclose_proxy.preclose_clv_proxy_label(row)
    if dimension == "final_clv":
        return strong_base.clv_bucket(row)
    if dimension == "provider_era":
        reporting_row = {**row, "slate_date": _slate_date(row)}
        return strong_base.provider_era(reporting_row)
    if dimension == "provider_attribution":
        return _text_or_missing(
            _first_non_empty(row.get("provider"), row.get("live_display_provider"))
        )
    if dimension == "recent_14_slates":
        return "included" if _slate_date(row) in recent_dates else "outside"
    raise ValueError(f"Unsupported slice dimension: {dimension}")


def _build_slices(
    rows: list[dict[str, Any]],
    recent_dates: set[str],
) -> dict[str, dict[str, dict[str, Any]]]:
    slices: dict[str, dict[str, dict[str, Any]]] = {}
    for dimension in SLICE_DIMENSIONS:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            buckets[_slice_bucket(dimension, row, recent_dates)].append(row)
        slices[dimension] = {
            bucket: score(bucket_rows)
            for bucket, bucket_rows in sorted(buckets.items())
        }
    return slices


def _missing_slice_coverage(
    slices: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, int]:
    return {
        dimension: buckets.get("missing", {}).get("rows", 0)
        for dimension, buckets in slices.items()
    }


def _mandatory_slice_risks(
    slices: dict[str, dict[str, dict[str, dict[str, Any]]]],
    missing_coverage: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    negative: list[dict[str, Any]] = []
    for window, dimensions in slices.items():
        for dimension, buckets in dimensions.items():
            for bucket, bucket_score in buckets.items():
                if bucket_score["rows"] >= 10 and bucket_score["pnl"] < 0:
                    negative.append({
                        "type": "negative_bucket",
                        "window": window,
                        "dimension": dimension,
                        "bucket": bucket,
                        **bucket_score,
                    })
    negative.sort(key=lambda risk: (risk["pnl"], -risk["rows"]))

    missing = [
        {
            "type": "missing_coverage",
            "window": window,
            "dimension": dimension,
            "rows": count,
        }
        for window, dimensions in missing_coverage.items()
        for dimension, count in dimensions.items()
        if count
    ]
    missing.sort(key=lambda risk: (risk["window"], risk["dimension"]))
    return negative + missing


def _baseline_reconciliation(
    observed: dict[str, Any],
    locked: dict[str, Any],
) -> dict[str, Any]:
    pnl_delta = observed["pnl"] - locked["pnl"]
    checks = {
        "rows": observed["rows"] == locked["rows"],
        "wins": observed["wins"] == locked["wins"],
        "losses": observed["losses"] == locked["losses"],
        "pnl": abs(pnl_delta) <= BASELINE_PNL_TOLERANCE,
    }
    return {
        "matches": all(checks.values()),
        "checks": checks,
        "observed": observed,
        "locked": dict(locked),
    }


def build_audit(
    rows: list[dict[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    all_tracked_rows = [
        row
        for row in rows
        if _is_tracked(row) and row.get("result") in WIN_LOSS_RESULTS
    ]
    history_recovered_rows = [
        row
        for row in all_tracked_rows
        if str(row.get("archive_outcome_reconciliation_source") or "").strip()
        == HISTORY_RECOVERED_ARCHIVE_SOURCE
    ]
    tracked_rows = [
        row
        for row in all_tracked_rows
        if str(row.get("archive_outcome_reconciliation_source") or "").strip()
        != HISTORY_RECOVERED_ARCHIVE_SOURCE
    ]
    evaluated = [
        (row, evaluate_row(row), parse_slate_date(row))
        for row in tracked_rows
    ]
    selected_rows = [
        (row, slate_date)
        for row, evaluation, slate_date in evaluated
        if evaluation.qualifies and slate_date is not None
    ]
    historical_selected = [
        (row, slate_date)
        for row, slate_date in selected_rows
        if CLEAN_WINDOW_START_DATE <= slate_date <= HISTORICAL_END_DATE
    ]
    prospective_selected = [
        (row, slate_date)
        for row, slate_date in selected_rows
        if slate_date >= PROSPECTIVE_START_DATE
    ]
    historical_rows = [row for row, _ in historical_selected]
    prospective_rows = [row for row, _ in prospective_selected]
    combined_selected = historical_selected + prospective_selected
    combined_rows = historical_rows + prospective_rows
    current_provider_rows = [
        row
        for row, slate_date in combined_selected
        if slate_date >= CURRENT_PROVIDER_START_DATE
    ]
    current_provider_historical_rows = [
        row
        for row, slate_date in historical_selected
        if slate_date >= CURRENT_PROVIDER_START_DATE
    ]
    recent_date_values = sorted(
        {slate_date for _, slate_date in combined_selected}
    )[-14:]
    recent_dates = [slate_date.isoformat() for slate_date in recent_date_values]
    recent_rows = [
        row
        for row, slate_date in combined_selected
        if slate_date in recent_date_values
    ]

    integrity_rows = [
        row
        for row, _, slate_date in evaluated
        if slate_date is not None and slate_date >= CLEAN_WINDOW_START_DATE
    ]
    key_counts = Counter(pick_key(row) for row in integrity_rows)
    duplicate_keys = sorted(key for key, count in key_counts.items() if count > 1)
    input_gap_evaluations = [
        (row, evaluation)
        for row, evaluation, slate_date in evaluated
        if (slate_date is None or slate_date >= PROSPECTIVE_START_DATE)
        and evaluation.missing_inputs
    ]

    historical_score = score(historical_rows)
    prospective_score = score(prospective_rows)
    historical_reconciliation = _baseline_reconciliation(
        historical_score,
        LOCKED_HISTORICAL,
    )
    current_provider_reconciliation = _baseline_reconciliation(
        score(current_provider_historical_rows),
        LOCKED_CURRENT_PROVIDER,
    )
    current_provider_reconciliation["window"] = {
        "start": CURRENT_PROVIDER_START,
        "end": HISTORICAL_END,
    }
    reconciliation_matches = (
        historical_reconciliation["matches"]
        and current_provider_reconciliation["matches"]
    )
    input_gap_rows = len(input_gap_evaluations)

    if duplicate_keys:
        status = "blocked_duplicate_keys"
    elif not reconciliation_matches:
        status = "blocked_baseline_drift"
    elif input_gap_rows:
        status = "blocked_input_gap"
    elif LOCKED_CURRENT_PROVIDER["rows"] + prospective_score["rows"] >= REVIEW_FLOOR:
        status = "ready_for_review"
    else:
        status = "collecting"

    qualified_rows = 0 if status.startswith("blocked_") else prospective_score["rows"]
    counter_rows = LOCKED_CURRENT_PROVIDER["rows"] + qualified_rows

    recent_date_set = set(recent_dates)
    slices = {
        "historical_rebuild": _build_slices(historical_rows, recent_date_set),
        "prospective": _build_slices(prospective_rows, recent_date_set),
        "combined": _build_slices(combined_rows, recent_date_set),
    }
    slice_missing_coverage = {
        window: _missing_slice_coverage(window_slices)
        for window, window_slices in slices.items()
    }
    if status.startswith("blocked_"):
        callout = "integrity_block"
    elif prospective_score["rows"] == 0:
        callout = "no_prospective_rows"
    elif prospective_score["rows"] < 10:
        callout = "small_sample"
    elif prospective_score["pnl"] > 0 and prospective_score["roi"] >= 0.10:
        callout = "positive_breakout_watch"
    elif prospective_score["pnl"] < 0:
        callout = "deterioration_watch"
    else:
        callout = "neutral_soak"
    mandatory_slice_risks = _mandatory_slice_risks(slices, slice_missing_coverage)

    return {
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "selector": {
            "id": SELECTOR_ID,
            "version": SELECTOR_VERSION,
            "fingerprint": RULE_FINGERPRINT,
            "formula": RULE_SPEC["formula"],
        },
        "status": status,
        "integrity": {
            "duplicate_keys": duplicate_keys,
            "history_recovered_rows_excluded": len(history_recovered_rows),
            "history_recovered_keys_excluded": sorted(
                pick_key(row) for row in history_recovered_rows
            ),
            "input_gap_rows": input_gap_rows,
            "input_gap_keys": [pick_key(row) for row, _ in input_gap_evaluations],
            "input_gaps": {
                pick_key(row): list(evaluation.missing_inputs)
                for row, evaluation in input_gap_evaluations
            },
            "slice_missing_coverage": slice_missing_coverage,
        },
        "locked_baselines": {
            "historical": dict(LOCKED_HISTORICAL),
            "current_provider": dict(LOCKED_CURRENT_PROVIDER),
            "recent_reference": dict(LOCKED_RECENT_REFERENCE),
        },
        "reconciliation": {
            "matches": reconciliation_matches,
            "pnl_tolerance": BASELINE_PNL_TOLERANCE,
            "historical": historical_reconciliation,
            "current_provider": current_provider_reconciliation,
        },
        "windows": {
            "historical_rebuild": historical_score,
            "prospective": prospective_score,
            "combined": score(combined_rows),
            "current_provider": score(current_provider_rows),
            "recent_14_slates": {
                **score(recent_rows),
                "slate_dates": recent_dates,
            },
        },
        "counter": {
            "locked_current_provider_rows": LOCKED_CURRENT_PROVIDER["rows"],
            "prospective_qualified_rows": qualified_rows,
            "rows": counter_rows,
            "floor": REVIEW_FLOOR,
            "remaining": max(REVIEW_FLOOR - counter_rows, 0),
        },
        "callouts": {
            "breakout_or_deterioration": callout,
            "mandatory_slice_risks": mandatory_slice_risks,
        },
        "slices": slices,
        "live_boundary": (
            "This audit cannot change live behavior; promotion requires a separate "
            "Tyler-approved plan."
        ),
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _score_line(label: str, window: dict[str, Any]) -> str:
    return (
        f"- {label}: {window['rows']} rows, {window['wins']}-{window['losses']}, "
        f"{window['pnl']:+.2f}u, {window['roi']:+.1%} ROI"
    )


def render_markdown(summary: dict[str, Any]) -> str:
    selector = summary["selector"]
    counter = summary["counter"]
    reconciliation = summary["reconciliation"]
    historical_reconciliation = reconciliation["historical"]
    current_provider_reconciliation = reconciliation["current_provider"]
    windows = summary["windows"]
    callouts = summary["callouts"]
    risks = callouts["mandatory_slice_risks"]
    lines = [
        "# No-Drag Composite Prospective Canary Audit",
        "",
        "## Executive Read",
        "",
        f"- Status: `{summary['status']}`",
        f"- Selector: `{selector['id']}` (version {selector['version']})",
        f"- Rule fingerprint: `{selector['fingerprint']}`",
        f"- Generated at: `{summary['generated_at']}`",
        "",
        "## Counter",
        "",
        (
            f"- Review counter: **{counter['rows']}/{counter['floor']}**; "
            f"**{counter['remaining']}** rows remaining."
        ),
        f"- Locked current-provider rows: {counter['locked_current_provider_rows']}",
        f"- Qualified prospective rows credited: {counter['prospective_qualified_rows']}",
        "",
        "## Baseline Reconciliation",
        "",
        f"- Both locked baselines reconcile: **{'yes' if reconciliation['matches'] else 'no'}**",
        (
            "- Historical rebuild reconciles: "
            f"**{'yes' if historical_reconciliation['matches'] else 'no'}**"
        ),
        _score_line("Locked historical", historical_reconciliation["locked"]),
        _score_line(
            "Observed historical rebuild",
            historical_reconciliation["observed"],
        ),
        (
            "- Locked current-provider slice reconciles: "
            f"**{'yes' if current_provider_reconciliation['matches'] else 'no'}** "
            f"(`{current_provider_reconciliation['window']['start']}` through "
            f"`{current_provider_reconciliation['window']['end']}`)."
        ),
        _score_line(
            "Locked current-provider historical",
            current_provider_reconciliation["locked"],
        ),
        _score_line(
            "Observed current-provider historical",
            current_provider_reconciliation["observed"],
        ),
        (
            "- History-recovered archive rows excluded from the frozen/prospective "
            f"counter: {summary['integrity']['history_recovered_rows_excluded']}."
        ),
    ]
    if not reconciliation["matches"]:
        lines.append(
            "- The input corpus does not reconcile to both locked baselines; "
            "the prospective counter is held fail-closed."
        )
    lines.extend([
        "",
        "## Prospective Evidence",
        "",
        _score_line("Observed prospective selector rows", windows["prospective"]),
        (
            f"- Input-gap rows: {summary['integrity']['input_gap_rows']}; "
            f"duplicate keys: {len(summary['integrity']['duplicate_keys'])}."
        ),
        "",
        "## Current Provider and Recent",
        "",
        _score_line("Observed current-provider window", windows["current_provider"]),
        _score_line("Latest 14 selected slate dates", windows["recent_14_slates"]),
        "",
        "## Breakout or Deterioration",
        "",
        f"- Descriptive callout: `{callouts['breakout_or_deterioration']}`",
        "- This callout is descriptive only and cannot alter status or counter eligibility.",
        "",
        "## Mandatory Slice Risks",
        "",
    ])
    if risks:
        for risk in risks:
            if risk["type"] == "negative_bucket":
                lines.append(
                    f"- Negative bucket: `{risk['window']}` / `{risk['dimension']}` / "
                    f"`{risk['bucket']}` — {risk['rows']} rows, {risk['pnl']:+.2f}u."
                )
            else:
                lines.append(
                    f"- Missing coverage: `{risk['window']}` / `{risk['dimension']}` — "
                    f"{risk['rows']} rows."
                )
    else:
        lines.append("- None at the current evidence volume.")

    lines.extend(["", "## Slice Audit", ""])
    for window in ("historical_rebuild", "prospective", "combined"):
        dimensions = summary["slices"][window]
        lines.append(f"### {window}")
        lines.append("")
        for dimension in SLICE_DIMENSIONS:
            buckets = dimensions[dimension]
            missing_count = summary["integrity"]["slice_missing_coverage"][window][
                dimension
            ]
            lines.append(f"#### {dimension}")
            lines.append("")
            lines.append(f"- Missing coverage: {missing_count} rows")
            if not buckets:
                lines.append("- No buckets in this window.")
            else:
                for bucket, bucket_score in buckets.items():
                    lines.append(_score_line(f"`{bucket}`", bucket_score))
            lines.append("")
        lines.append("")

    lines.extend([
        "## Live Boundary",
        "",
        f"{summary['live_boundary']}",
        "",
    ])
    return "\n".join(lines)


def write_outputs(
    summary: dict[str, Any],
    md_path: Path,
    json_path: Path,
) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(summary), encoding="utf-8")
    json_path.write_text(
        json.dumps(summary, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit the frozen no-drag composite on post-grading evidence."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    args = parser.parse_args(argv)

    summary = build_audit(load_jsonl(args.input))
    write_outputs(summary, args.output_md, args.output_json)
    print(
        f"No-drag canary audit: status={summary['status']} "
        f"counter={summary['counter']['rows']}/{summary['counter']['floor']}"
    )
    print(f"Markdown: {args.output_md}")
    print(f"JSON: {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
