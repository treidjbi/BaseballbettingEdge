"""Audit the frozen strict-runtime-core FIRE selector as research only.

This diagnostic reads canonical Gate C rows and writes ignored research
outputs. It cannot change picks, model math, verdicts, thresholds, stakes,
providers, notifications, locks, artifacts, UI, retention, or environment
variables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import strong_base_decision_lab as strong_base  # noqa: E402
from pipeline.name_utils import normalize  # noqa: E402


DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT_MD = ROOT / "analytics" / "output" / "strict_runtime_core_canary_audit.md"
DEFAULT_OUTPUT_JSON = ROOT / "analytics" / "output" / "strict_runtime_core_canary_audit.json"

SELECTOR_ID = "strict_runtime_core_flat"
SELECTOR_VERSION = 1
CLEAN_WINDOW_START = "2026-04-28"
CURRENT_PROVIDER_START = "2026-06-24"
HISTORICAL_END = "2026-07-29"
PROSPECTIVE_START = "2026-07-30"
CURRENT_PROVIDER_REVIEW_FLOOR = 50
DIVERSITY_FLOOR = 10
BASELINE_PNL_TOLERANCE = 0.005
WIN_LOSS_RESULTS = {"win", "loss"}
HISTORY_RECOVERED_ARCHIVE_SOURCES = {
    "picks_history_exact",
    "picks_history_pitcher_game",
}

CLEAN_WINDOW_START_DATE = date.fromisoformat(CLEAN_WINDOW_START)
CURRENT_PROVIDER_START_DATE = date.fromisoformat(CURRENT_PROVIDER_START)
HISTORICAL_END_DATE = date.fromisoformat(HISTORICAL_END)
PROSPECTIVE_START_DATE = date.fromisoformat(PROSPECTIVE_START)

LOCKED_HISTORICAL = {
    "rows": 96,
    "wins": 64,
    "losses": 32,
    "pnl": 17.727,
    "roi": 0.1847,
}
LOCKED_CURRENT_PROVIDER = {
    "rows": 20,
    "wins": 15,
    "losses": 5,
    "pnl": 5.864,
    "roi": 0.2932,
}

VERDICT_FIELDS = (
    "display_verdict",
    "locked_verdict",
    "actionable_verdict",
    "current_verdict",
    "verdict",
)
ADJUSTED_EV_FIELDS = ("adj_ev_roi", "locked_adj_ev", "adj_ev", "ev")
CRITICAL_INPUT_GROUPS = (
    ("slate_date",),
    ("normalized_pitcher", "pitcher", "player_name"),
    ("side",),
    VERDICT_FIELDS,
    ("edge",),
    ADJUSTED_EV_FIELDS,
    ("model_market_relationship",),
    ("line_bucket", "k_line"),
    ("price_sign",),
    ("price_bucket", "price_sign"),
    ("quality_gate_level",),
    ("bet_timing_window",),
    ("leash_risk_bucket", "opportunity_bucket"),
    ("batter_handedness_mode", "path_b_coverage_bucket"),
    ("provider", "live_display_provider", "odds_source"),
    ("market_agreement_label", "market_agreement"),
    ("preclose_clv_proxy_label", "preclose_clv_proxy"),
)
NUMERIC_CRITICAL_GROUPS = {
    ("edge",),
    ADJUSTED_EV_FIELDS,
}

RULE_SPEC = {
    "selector_id": SELECTOR_ID,
    "version": SELECTOR_VERSION,
    "prospective_start": PROSPECTIVE_START,
    "verdict": "FIRE*",
    "keep_labels": [
        "keep_fire_market_agreed_moderate_ev",
        "keep_fire_over_moderate_ev_normal_leash",
    ],
    "drag_labels": [
        "cap_fire_under_market_fade",
        "cap_high_raw_edge",
        "cap_market_fade",
    ],
    "post_start_policy": "exclude",
    "outcome_fields_used": [],
    "formula": (
        "FIRE AND (keep_fire_market_agreed_moderate_ev OR "
        "keep_fire_over_moderate_ev_normal_leash) AND NOT "
        "(cap_high_raw_edge OR cap_market_fade OR "
        "cap_fire_under_market_fade)"
    ),
}
RULE_FINGERPRINT = hashlib.sha256(
    json.dumps(RULE_SPEC, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class Evaluation:
    qualifies: bool
    keep_labels: tuple[str, ...]
    drag_labels: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    post_start_leakage: bool


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _first_non_empty(row: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        value = row.get(field)
        if _value_present(value):
            return value
    return None


def verdict(row: dict[str, Any]) -> str:
    return str(_first_non_empty(row, VERDICT_FIELDS) or "").strip()


def parse_slate_date(row: dict[str, Any]) -> date | None:
    value = str(row.get("slate_date") or row.get("date") or "").strip()[:10]
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _runtime_labels(row: dict[str, Any]) -> set[str]:
    """Evaluate only Strong Base runtime-safe labels without outcome leakage."""

    label_row = dict(row)
    # candidate_labels is a research-row labeler whose outer wrapper requires a
    # tracked result. The two keep labels and three drag labels themselves use
    # only pregame inputs, so a fixed sentinel unlocks those rules without
    # reading the row's real result or PnL.
    label_row["is_tracked_pick"] = True
    label_row["result"] = "win"
    return strong_base.candidate_labels(label_row)


def missing_critical_inputs(row: dict[str, Any]) -> tuple[str, ...]:
    slate_date = parse_slate_date(row)
    if slate_date is None:
        return ("slate_date",)
    if slate_date < PROSPECTIVE_START_DATE:
        return ()
    missing: list[str] = []
    for group in CRITICAL_INPUT_GROUPS:
        if group in NUMERIC_CRITICAL_GROUPS:
            present = any(_to_float(row.get(field)) is not None for field in group)
        else:
            present = any(_value_present(row.get(field)) for field in group)
        if not present:
            missing.append("|".join(group))
    return tuple(missing)


def evaluate_row(row: dict[str, Any]) -> Evaluation:
    labels = _runtime_labels(row)
    keep_labels = tuple(label for label in RULE_SPEC["keep_labels"] if label in labels)
    drag_labels = tuple(label for label in RULE_SPEC["drag_labels"] if label in labels)
    is_fire = verdict(row).upper().startswith("FIRE")
    timing = str(row.get("bet_timing_window") or "").strip().lower()
    would_qualify = is_fire and bool(keep_labels) and not drag_labels
    post_start_leakage = would_qualify and timing in {
        "post_start",
        "in_progress",
        "started",
        "postgame",
    }
    missing = missing_critical_inputs(row)
    return Evaluation(
        qualifies=would_qualify and not missing and not post_start_leakage,
        keep_labels=keep_labels,
        drag_labels=drag_labels,
        missing_inputs=missing,
        post_start_leakage=post_start_leakage,
    )


def pick_key(row: dict[str, Any]) -> str:
    slate_date = parse_slate_date(row)
    pitcher_value = (
        row.get("normalized_pitcher")
        or row.get("pitcher")
        or row.get("player_name")
        or ""
    )
    return "|".join(
        (
            slate_date.isoformat() if slate_date else "",
            normalize(pitcher_value).strip(),
            str(row.get("side") or "").strip().lower(),
        )
    )


def row_pnl(row: dict[str, Any]) -> float | None:
    for field in ("pick_history_pnl", "pnl", "theoretical_pnl"):
        value = _to_float(row.get(field))
        if value is not None:
            return value
    return None


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    graded = [row for row in rows if row.get("result") in WIN_LOSS_RESULTS]
    wins = sum(row.get("result") == "win" for row in graded)
    losses = sum(row.get("result") == "loss" for row in graded)
    pnl = 0.0
    for row in graded:
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
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _baseline_reconciliation(
    observed: dict[str, Any],
    locked: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "rows": observed["rows"] == locked["rows"],
        "wins": observed["wins"] == locked["wins"],
        "losses": observed["losses"] == locked["losses"],
        "pnl": abs(observed["pnl"] - locked["pnl"]) <= BASELINE_PNL_TOLERANCE,
    }
    return {
        "matches": all(checks.values()),
        "checks": checks,
        "observed": observed,
        "locked": dict(locked),
    }


def _audit_input_gaps(row: dict[str, Any], evaluation: Evaluation) -> tuple[str, ...]:
    missing = list(evaluation.missing_inputs)
    if row.get("result") not in WIN_LOSS_RESULTS:
        missing.append("result")
    if row_pnl(row) is None:
        missing.append("pick_history_pnl|pnl|theoretical_pnl")
    return tuple(missing)


def build_audit(
    rows: list[dict[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    all_tracked = [
        row
        for row in rows
        if _is_tracked(row) and row.get("result") in WIN_LOSS_RESULTS
    ]
    history_recovered = [
        row
        for row in all_tracked
        if str(row.get("archive_outcome_reconciliation_source") or "").strip()
        in HISTORY_RECOVERED_ARCHIVE_SOURCES
    ]
    tracked = [row for row in all_tracked if row not in history_recovered]
    evaluated = [(row, evaluate_row(row), parse_slate_date(row)) for row in tracked]

    selected = [
        (row, slate_date)
        for row, evaluation, slate_date in evaluated
        if evaluation.qualifies and slate_date is not None
    ]
    historical_selected = [
        (row, slate_date)
        for row, slate_date in selected
        if CLEAN_WINDOW_START_DATE <= slate_date <= HISTORICAL_END_DATE
    ]
    prospective_selected = [
        (row, slate_date)
        for row, slate_date in selected
        if slate_date >= PROSPECTIVE_START_DATE
    ]
    combined_selected = historical_selected + prospective_selected
    current_provider_selected = [
        (row, slate_date)
        for row, slate_date in combined_selected
        if slate_date >= CURRENT_PROVIDER_START_DATE
    ]
    current_provider_historical = [
        row
        for row, slate_date in historical_selected
        if slate_date >= CURRENT_PROVIDER_START_DATE
    ]

    integrity_rows = [
        row
        for row in tracked
        if (parse_slate_date(row) or date.min) >= CLEAN_WINDOW_START_DATE
    ]
    key_counts = Counter(pick_key(row) for row in integrity_rows)
    duplicate_keys = sorted(key for key, count in key_counts.items() if count > 1)
    prospective_evaluated = [
        (row, evaluation)
        for row, evaluation, slate_date in evaluated
        if slate_date is None or slate_date >= PROSPECTIVE_START_DATE
    ]
    input_gap_evaluations = [
        (row, gaps)
        for row, evaluation in prospective_evaluated
        if (gaps := _audit_input_gaps(row, evaluation))
    ]
    post_start_rows = [
        row
        for row, evaluation in prospective_evaluated
        if evaluation.post_start_leakage
    ]

    historical_rows = [row for row, _ in historical_selected]
    prospective_rows = [row for row, _ in prospective_selected]
    combined_rows = historical_rows + prospective_rows
    current_provider_rows = [row for row, _ in current_provider_selected]
    recent_dates = sorted({slate_date for _, slate_date in combined_selected})[-14:]
    recent_rows = [
        row
        for row, slate_date in combined_selected
        if slate_date in set(recent_dates)
    ]

    historical_reconciliation = _baseline_reconciliation(
        score(historical_rows),
        LOCKED_HISTORICAL,
    )
    current_provider_reconciliation = _baseline_reconciliation(
        score(current_provider_historical),
        LOCKED_CURRENT_PROVIDER,
    )
    reconciliation_matches = (
        historical_reconciliation["matches"]
        and current_provider_reconciliation["matches"]
    )

    if duplicate_keys:
        status = "blocked_duplicate_keys"
    elif not reconciliation_matches:
        status = "blocked_baseline_drift"
    elif input_gap_evaluations:
        status = "blocked_input_gap"
    elif post_start_rows:
        status = "blocked_post_start_leakage"
    else:
        status = "collecting"

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
            "history_recovered_rows_excluded": len(history_recovered),
            "input_gap_rows": len(input_gap_evaluations),
            "input_gap_keys": [pick_key(row) for row, _ in input_gap_evaluations],
            "input_gaps": {
                pick_key(row): list(gaps)
                for row, gaps in input_gap_evaluations
            },
            "post_start_leakage_rows": len(post_start_rows),
            "post_start_leakage_keys": [pick_key(row) for row in post_start_rows],
        },
        "locked_baselines": {
            "historical": dict(LOCKED_HISTORICAL),
            "current_provider": dict(LOCKED_CURRENT_PROVIDER),
        },
        "reconciliation": {
            "matches": reconciliation_matches,
            "pnl_tolerance": BASELINE_PNL_TOLERANCE,
            "historical": historical_reconciliation,
            "current_provider": current_provider_reconciliation,
        },
        "windows": {
            "historical_rebuild": score(historical_rows),
            "prospective": score(prospective_rows),
            "combined": score(combined_rows),
            "current_provider": score(current_provider_rows),
            "recent_14_slates": {
                **score(recent_rows),
                "slate_dates": [value.isoformat() for value in recent_dates],
            },
        },
        "counter": {
            "rows": score(current_provider_rows)["rows"],
            "floor": CURRENT_PROVIDER_REVIEW_FLOOR,
            "remaining": max(
                CURRENT_PROVIDER_REVIEW_FLOOR - score(current_provider_rows)["rows"],
                0,
            ),
        },
        "live_boundary": (
            "Research only. A separate Tyler-approved plan is required before "
            "any runtime or environment change."
        ),
    }


def render_report(summary: dict[str, Any]) -> str:
    current = summary["windows"]["current_provider"]
    recent = summary["windows"]["recent_14_slates"]
    return "\n".join(
        [
            "# Strict Runtime Core Prospective Canary Audit",
            "",
            f"Generated at: `{summary['generated_at']}`",
            "",
            "## Executive Read",
            "",
            f"- Status: `{summary['status']}`",
            f"- Selector: `{summary['selector']['id']}`",
            f"- Fingerprint: `{summary['selector']['fingerprint']}`",
            (
                f"- Current-provider counter: `{summary['counter']['rows']}/"
                f"{summary['counter']['floor']}`."
            ),
            (
                f"- Current provider: `{current['rows']}` rows, "
                f"`{current['wins']}-{current['losses']}`, `{current['pnl']:+.3f}u`."
            ),
            (
                f"- Latest 14 selected slates: `{recent['rows']}` rows, "
                f"`{recent['wins']}-{recent['losses']}`, `{recent['pnl']:+.3f}u`."
            ),
            "",
            "## Live Boundary",
            "",
            f"- {summary['live_boundary']}",
            "",
        ]
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        parsed
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        if isinstance((parsed := json.loads(line)), dict)
    ]


def write_outputs(summary: dict[str, Any], md_path: Path, json_path: Path) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_report(summary), encoding="utf-8")
    json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    args = parser.parse_args(argv)

    summary = build_audit(load_jsonl(args.input))
    write_outputs(summary, args.output_md, args.output_json)
    print(
        f"status={summary['status']} "
        f"counter={summary['counter']['rows']}/{summary['counter']['floor']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
