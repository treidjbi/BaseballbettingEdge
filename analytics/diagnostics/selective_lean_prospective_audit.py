"""Audit one frozen selective-LEAN candidate as post-grading research only.

This diagnostic reads canonical Gate C rows and writes ignored research
outputs. It cannot change picks, model math, verdicts, thresholds, staking,
providers, notifications, locks, artifacts, UI, retention, or source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import gate_f_preclose_clv_proxy_lab as preclose_proxy  # noqa: E402
from analytics.diagnostics import strong_base_decision_lab as strong_base  # noqa: E402
from pipeline.name_utils import normalize  # noqa: E402


DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT_MD = ROOT / "analytics" / "output" / "selective_lean_prospective_audit.md"
DEFAULT_OUTPUT_JSON = ROOT / "analytics" / "output" / "selective_lean_prospective_audit.json"

SELECTOR_ID = "expand_lean_low_line_capped_model_fade"
SELECTOR_VERSION = 1
CLEAN_WINDOW_START = "2026-04-28"
CURRENT_PROVIDER_START = "2026-06-24"
HISTORICAL_END = "2026-08-12"
FREEZE_GAP_START = "2026-08-13"
PROSPECTIVE_START = "2026-08-15"
REVIEW_FLOOR = 75
UNDER_FLOOR = 20
PLUS_PRICE_FLOOR = 10
MANDATORY_SLICE_FLOOR = 10
BASELINE_PNL_TOLERANCE = 0.005
WIN_LOSS_RESULTS = {"win", "loss"}
HISTORY_RECOVERED_ARCHIVE_SOURCES = {
    "picks_history_exact",
    "picks_history_pitcher_game",
}

CLEAN_WINDOW_START_DATE = date.fromisoformat(CLEAN_WINDOW_START)
CURRENT_PROVIDER_START_DATE = date.fromisoformat(CURRENT_PROVIDER_START)
HISTORICAL_END_DATE = date.fromisoformat(HISTORICAL_END)
FREEZE_GAP_START_DATE = date.fromisoformat(FREEZE_GAP_START)
PROSPECTIVE_START_DATE = date.fromisoformat(PROSPECTIVE_START)

CANDIDATE_DEFINITION = {
    "display_verdict": "LEAN",
    "line_bucket": "2.5-3.5",
    "model_market_relationship": "model_fades_favorite",
    "quality_gate_level": "capped",
}
EXPECTED_RULE_FINGERPRINT = (
    "4e00a180e35fe75dc8889d47065a25c4351cb37ac55664eb42f01b77c07fd13a"
)
RULE_FINGERPRINT = hashlib.sha256(
    json.dumps(CANDIDATE_DEFINITION, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()

LOCKED_HISTORICAL = {
    "rows": 103,
    "wins": 55,
    "losses": 48,
    "pnl": 11.415935,
    "roi": 0.110834,
}
LOCKED_CURRENT_PROVIDER = {
    "rows": 56,
    "wins": 28,
    "losses": 28,
    "pnl": 2.999676,
    "roi": 0.053566,
}

VERDICT_FIELDS = (
    "display_verdict",
    "locked_verdict",
    "actionable_verdict",
    "current_verdict",
    "verdict",
)
LOCK_ID_FIELDS = ("operational_lock_id", "lock_id", "lock_key", "operational_lock_key")
LOCK_CONSUMED_FIELDS = (
    "operational_lock_consumed_at",
    "consumed_at",
    "lock_consumed_at",
)
LOCK_SOURCE_FIELDS = (
    "operational_lock_source_artifact_path",
    "lock_source_artifact_path",
)
PROVIDER_FIELDS = ("provider", "live_display_provider", "odds_source")
MARKET_AGREEMENT_FIELDS = ("market_agreement_label", "market_agreement")
PNL_FIELDS = ("pick_history_pnl", "pnl", "theoretical_pnl")

CRITICAL_INPUT_GROUPS = (
    ("slate_date", "date"),
    ("normalized_pitcher", "pitcher", "player_name"),
    ("side",),
    ("result",),
    PNL_FIELDS,
    VERDICT_FIELDS,
    ("line_bucket", "k_line"),
    ("k_line",),
    ("model_market_relationship",),
    ("quality_gate_level",),
    ("price_sign",),
    ("bet_timing_window",),
    ("bet_time_at", "locked_at"),
    LOCK_ID_FIELDS,
    LOCK_CONSUMED_FIELDS,
    LOCK_SOURCE_FIELDS,
    ("source_artifact_path",),
    PROVIDER_FIELDS,
    MARKET_AGREEMENT_FIELDS,
    ("batter_handedness_mode", "path_b_coverage_bucket"),
    ("leash_risk_bucket", "opportunity_bucket", "workload_bucket"),
    ("preclose_clv_proxy_label", "preclose_clv_proxy"),
    ("clv_type", "clv_bucket", "final_clv_bucket"),
)
NUMERIC_CRITICAL_GROUPS = {PNL_FIELDS, ("k_line",)}

SLICE_DIMENSIONS = (
    "side",
    "price_sign",
    "k_line",
    "quality",
    "timing",
    "model_market",
    "path_b",
    "workload",
    "preclose_clv_proxy",
    "final_clv",
    "provider",
    "market_agreement",
)


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


def _is_true(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def verdict(row: dict[str, Any]) -> str:
    return str(_first_non_empty(row, VERDICT_FIELDS) or "").strip()


def parse_slate_date(row: dict[str, Any]) -> date | None:
    raw = str(row.get("slate_date") or row.get("date") or "").strip()[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def selector_matches(row: dict[str, Any]) -> bool:
    """Apply only the approved pregame selector definition."""

    return (
        verdict(row) == CANDIDATE_DEFINITION["display_verdict"]
        and str(row.get("line_bucket") or "") == CANDIDATE_DEFINITION["line_bucket"]
        and str(row.get("model_market_relationship") or "")
        == CANDIDATE_DEFINITION["model_market_relationship"]
        and str(row.get("quality_gate_level") or "").lower()
        == CANDIDATE_DEFINITION["quality_gate_level"]
    )


def pick_key(row: dict[str, Any]) -> str:
    slate_date = parse_slate_date(row)
    pitcher = row.get("normalized_pitcher") or row.get("pitcher") or row.get("player_name") or ""
    return "|".join(
        (
            slate_date.isoformat() if slate_date else "",
            normalize(pitcher).strip(),
            str(row.get("side") or "").strip().lower(),
        )
    )


def row_pnl(row: dict[str, Any]) -> float | None:
    for field in PNL_FIELDS:
        value = _to_float(row.get(field))
        if value is not None:
            return value
    return None


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    graded = [row for row in rows if row.get("result") in WIN_LOSS_RESULTS]
    wins = sum(row.get("result") == "win" for row in graded)
    losses = sum(row.get("result") == "loss" for row in graded)
    pnl = round(sum(row_pnl(row) or 0.0 for row in graded), 6)
    count = wins + losses
    return {
        "rows": count,
        "wins": wins,
        "losses": losses,
        "pnl": pnl,
        "roi": round(pnl / count, 6) if count else 0.0,
    }


def missing_critical_inputs(row: dict[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    for group in CRITICAL_INPUT_GROUPS:
        if group in NUMERIC_CRITICAL_GROUPS:
            present = any(_to_float(row.get(field)) is not None for field in group)
        else:
            present = any(_value_present(row.get(field)) for field in group)
        if not present:
            missing.append("|".join(group))

    if str(row.get("bet_timing_window") or "").strip().lower() != "pre_30":
        missing.append("bet_timing_window=pre_30")
    if str(row.get("archive_outcome_reconciliation_source") or "").strip() in (
        HISTORY_RECOVERED_ARCHIVE_SOURCES
    ):
        missing.append("history_recovered")
    return tuple(dict.fromkeys(missing))


def _baseline_reconciliation(
    observed: dict[str, Any], locked: dict[str, Any]
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


def _text_bucket(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "missing"


def _slice_bucket(row: dict[str, Any], dimension: str) -> str:
    if dimension == "side":
        return _text_bucket(row.get("side")).lower()
    if dimension == "price_sign":
        return _text_bucket(row.get("price_sign")).lower()
    if dimension == "k_line":
        return _text_bucket(row.get("k_line") or row.get("line_bucket"))
    if dimension == "quality":
        return _text_bucket(row.get("quality_gate_level")).lower()
    if dimension == "timing":
        return _text_bucket(row.get("bet_timing_window")).lower()
    if dimension == "model_market":
        return _text_bucket(row.get("model_market_relationship"))
    if dimension == "path_b":
        return strong_base.path_b_coverage_bucket(row)
    if dimension == "workload":
        return _text_bucket(
            row.get("workload_bucket")
            or row.get("leash_risk_bucket")
            or row.get("opportunity_bucket")
        )
    if dimension == "preclose_clv_proxy":
        return _text_bucket(
            row.get("preclose_clv_proxy_label")
            or row.get("preclose_clv_proxy")
            or preclose_proxy.preclose_clv_proxy_label(row)
        )
    if dimension == "final_clv":
        return _text_bucket(
            row.get("final_clv_bucket")
            or row.get("clv_bucket")
            or row.get("clv_type")
            or strong_base.clv_bucket(row)
        )
    if dimension == "provider":
        return _text_bucket(_first_non_empty(row, PROVIDER_FIELDS))
    if dimension == "market_agreement":
        return _text_bucket(_first_non_empty(row, MARKET_AGREEMENT_FIELDS))
    raise ValueError(f"Unknown slice dimension: {dimension}")


def build_slices(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for dimension in SLICE_DIMENSIONS:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            buckets[_slice_bucket(row, dimension)].append(row)
        result[dimension] = {
            bucket: score(bucket_rows) for bucket, bucket_rows in sorted(buckets.items())
        }
    return result


def _negative_mandatory_slices(
    slices: dict[str, dict[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    return sorted(
        (
            {"dimension": dimension, "bucket": bucket, **bucket_score}
            for dimension, buckets in slices.items()
            for bucket, bucket_score in buckets.items()
            if bucket_score["rows"] >= MANDATORY_SLICE_FLOOR
            and bucket_score["pnl"] < 0
        ),
        key=lambda item: (item["pnl"], -item["rows"], item["dimension"], item["bucket"]),
    )


def _recent_rows(rows: list[dict[str, Any]], slate_count: int = 14) -> tuple[list[dict[str, Any]], list[str]]:
    slate_dates = sorted(
        {
            parsed.isoformat()
            for row in rows
            if (parsed := parse_slate_date(row)) is not None
        }
    )[-slate_count:]
    keep = set(slate_dates)
    return (
        [
            row
            for row in rows
            if (parsed := parse_slate_date(row)) is not None
            and parsed.isoformat() in keep
        ],
        slate_dates,
    )


def _leave_one_slate_out(rows: list[dict[str, Any]]) -> dict[str, Any]:
    slate_dates = sorted(
        {
            parsed.isoformat()
            for row in rows
            if (parsed := parse_slate_date(row)) is not None
        }
    )
    cases = [
        {
            "excluded_slate_date": excluded,
            **score(
                [
                    row
                    for row in rows
                    if (parse_slate_date(row) or date.min).isoformat() != excluded
                ]
            ),
        }
        for excluded in slate_dates
    ]
    return {
        "cases": cases,
        "minimum": min(cases, key=lambda item: item["pnl"])
        if cases
        else {"rows": 0, "wins": 0, "losses": 0, "pnl": 0.0, "roi": 0.0},
    }


def _diversity(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "under_rows": sum(_slice_bucket(row, "side") == "under" for row in rows),
        "plus_price_rows": sum(
            _slice_bucket(row, "price_sign").startswith("plus") for row in rows
        ),
        "provider_attributed_rows": sum(
            _slice_bucket(row, "provider") not in {"missing", "unknown", "none"}
            for row in rows
        ),
        "market_agreement_attributed_rows": sum(
            _slice_bucket(row, "market_agreement")
            not in {"missing", "unknown", "none"}
            for row in rows
        ),
    }


def build_audit(
    rows: list[dict[str, Any]],
    generated_at: str | None = None,
    *,
    enforce_baseline: bool = True,
) -> dict[str, Any]:
    analysis_rows = strong_base.analysis_rows(rows)
    tracked = [row for row in analysis_rows if _is_true(row.get("is_tracked_pick"))]
    candidates = [row for row in tracked if selector_matches(row)]

    historical_rows = [
        row
        for row in candidates
        if (slate := parse_slate_date(row)) is not None
        and CLEAN_WINDOW_START_DATE <= slate <= HISTORICAL_END_DATE
    ]
    current_provider_historical = [
        row
        for row in historical_rows
        if (parse_slate_date(row) or date.min) >= CURRENT_PROVIDER_START_DATE
    ]
    freeze_gap_rows = [
        row
        for row in candidates
        if (slate := parse_slate_date(row)) is not None
        and FREEZE_GAP_START_DATE <= slate < PROSPECTIVE_START_DATE
    ]
    prospective_candidates = [
        row
        for row in candidates
        if (parse_slate_date(row) or date.min) >= PROSPECTIVE_START_DATE
    ]

    key_counts = Counter(pick_key(row) for row in prospective_candidates)
    duplicate_keys = sorted(key for key, count in key_counts.items() if count > 1)
    input_gaps = {
        pick_key(row): list(gaps)
        for row in prospective_candidates
        if (gaps := missing_critical_inputs(row))
    }
    eligible_rows = [
        row
        for row in prospective_candidates
        if pick_key(row) not in duplicate_keys and not missing_critical_inputs(row)
    ]
    eligible_ids = {id(row) for row in eligible_rows}
    blocked_rows = [row for row in prospective_candidates if id(row) not in eligible_ids]

    historical_reconciliation = _baseline_reconciliation(
        score(historical_rows), LOCKED_HISTORICAL
    )
    current_provider_reconciliation = _baseline_reconciliation(
        score(current_provider_historical), LOCKED_CURRENT_PROVIDER
    )
    baseline_matches = (
        historical_reconciliation["matches"]
        and current_provider_reconciliation["matches"]
    )

    prospective_score = score(eligible_rows)
    recent_rows, recent_dates = _recent_rows(eligible_rows)
    recent_score = score(recent_rows)
    slices = build_slices(eligible_rows)
    negative_slices = _negative_mandatory_slices(slices)
    diversity = _diversity(eligible_rows)
    leave_one_slate_out = _leave_one_slate_out(eligible_rows)
    gates = {
        "prospective_floor": prospective_score["rows"] >= REVIEW_FLOOR,
        "under_diversity": diversity["under_rows"] >= UNDER_FLOOR,
        "plus_price_diversity": diversity["plus_price_rows"] >= PLUS_PRICE_FLOOR,
        "prospective_positive": prospective_score["pnl"] > 0,
        "latest_14_positive": recent_score["rows"] > 0 and recent_score["pnl"] > 0,
        "provider_attribution_complete": (
            diversity["provider_attributed_rows"] == prospective_score["rows"]
        ),
        "market_agreement_attribution_complete": (
            diversity["market_agreement_attributed_rows"] == prospective_score["rows"]
        ),
        "mandatory_slices_nonnegative": not negative_slices,
        "leave_one_slate_out_positive": (
            leave_one_slate_out["minimum"]["rows"] > 0
            and leave_one_slate_out["minimum"]["pnl"] > 0
        ),
    }

    rule_matches = RULE_FINGERPRINT == EXPECTED_RULE_FINGERPRINT
    if not rule_matches:
        status = "blocked_rule_drift"
    elif duplicate_keys:
        status = "blocked_duplicate_keys"
    elif enforce_baseline and not baseline_matches:
        status = "blocked_baseline_drift"
    elif input_gaps:
        status = "blocked_input_gap"
    elif all(gates.values()):
        status = "ready_for_review"
    else:
        status = "collecting"

    if status == "ready_for_review":
        decision = "ready_for_separate_shadow_design"
    elif (
        status == "collecting"
        and prospective_score["rows"] >= REVIEW_FLOOR
        and prospective_score["pnl"] <= 0
    ):
        decision = "retire"
    else:
        decision = "continue_research"

    return {
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "status": status,
        "decision": decision,
        "selector": {
            "id": SELECTOR_ID,
            "version": SELECTOR_VERSION,
            "definition": dict(CANDIDATE_DEFINITION),
            "fingerprint": RULE_FINGERPRINT,
            "expected_fingerprint": EXPECTED_RULE_FINGERPRINT,
            "fingerprint_matches": rule_matches,
        },
        "windows": {
            "historical_nomination": score(historical_rows),
            "historical_current_provider": score(current_provider_historical),
            "freeze_gap": score(freeze_gap_rows),
            "prospective_eligible": prospective_score,
            "prospective_blocked": score(blocked_rows),
            "latest_14_slates": {**recent_score, "slate_dates": recent_dates},
        },
        "counter": {
            "rows": prospective_score["rows"],
            "floor": REVIEW_FLOOR,
            "remaining": max(REVIEW_FLOOR - prospective_score["rows"], 0),
        },
        "integrity": {
            "baseline_enforced": enforce_baseline,
            "duplicate_keys": duplicate_keys,
            "input_gap_rows": len(input_gaps),
            "input_gaps": input_gaps,
            "freeze_gap_rows_excluded": len(freeze_gap_rows),
            "history_recovered_prospective_rows_excluded": sum(
                "history_recovered" in missing_critical_inputs(row)
                for row in prospective_candidates
            ),
        },
        "locked_baselines": {
            "historical_nomination": dict(LOCKED_HISTORICAL),
            "historical_current_provider": dict(LOCKED_CURRENT_PROVIDER),
        },
        "reconciliation": {
            "matches": baseline_matches,
            "pnl_tolerance": BASELINE_PNL_TOLERANCE,
            "historical_nomination": historical_reconciliation,
            "historical_current_provider": current_provider_reconciliation,
        },
        "diversity": diversity,
        "gates": gates,
        "negative_mandatory_slices": negative_slices,
        "leave_one_slate_out": leave_one_slate_out,
        "slices": slices,
        "live_boundary": (
            "Research only. Passing opens a separate review; it cannot change "
            "official picks, model math, staking, providers, notifications, locks, "
            "artifacts, UI, retention, or source of truth."
        ),
    }


def _score_line(label: str, value: dict[str, Any]) -> str:
    return (
        f"- {label}: `{value['rows']}` rows, `{value['wins']}-{value['losses']}`, "
        f"`{value['pnl']:+.3f}u`, `{value['roi']:+.1%}` ROI."
    )


def render_report(summary: dict[str, Any]) -> str:
    windows = summary["windows"]
    lines = [
        "# Selective LEAN Prospective Audit",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "## Executive Read",
        "",
        f"- Status: `{summary['status']}`",
        f"- Decision: `{summary['decision']}`",
        f"- Candidate: `{summary['selector']['id']}`",
        f"- Fingerprint: `{summary['selector']['fingerprint']}`",
        (
            f"- Formal prospective counter: `{summary['counter']['rows']}/"
            f"{summary['counter']['floor']}`; starts `{PROSPECTIVE_START}`."
        ),
        _score_line("Locked historical nomination", windows["historical_nomination"]),
        _score_line("Freeze gap (excluded)", windows["freeze_gap"]),
        _score_line("Eligible prospective", windows["prospective_eligible"]),
        _score_line("Blocked prospective", windows["prospective_blocked"]),
        "",
        "## Integrity",
        "",
        f"- Historical baseline reconciles: `{'yes' if summary['reconciliation']['matches'] else 'no'}`.",
        f"- Duplicate candidate keys: `{len(summary['integrity']['duplicate_keys'])}`.",
        f"- Prospective input-gap rows: `{summary['integrity']['input_gap_rows']}`.",
        f"- Freeze-gap rows excluded from credit: `{summary['integrity']['freeze_gap_rows_excluded']}`.",
        "",
        "## Review Gates",
        "",
    ]
    for gate, passed in summary["gates"].items():
        lines.append(f"- `{gate}`: `{'pass' if passed else 'hold'}`")
    lines.extend(
        [
            "",
            "## Diversity",
            "",
            f"- UNDER rows: `{summary['diversity']['under_rows']}/{UNDER_FLOOR}`.",
            f"- Plus-price rows: `{summary['diversity']['plus_price_rows']}/{PLUS_PRICE_FLOOR}`.",
            (
                "- Provider / agreement attributed: "
                f"`{summary['diversity']['provider_attributed_rows']}` / "
                f"`{summary['diversity']['market_agreement_attributed_rows']}`."
            ),
            f"- Negative mandatory slices at {MANDATORY_SLICE_FLOOR}+ rows: `{len(summary['negative_mandatory_slices'])}`.",
            "",
            "## Live Boundary",
            "",
            f"- {summary['live_boundary']}",
            "",
        ]
    )
    return "\n".join(lines)


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


def write_outputs(summary: dict[str, Any], md_path: Path, json_path: Path) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_report(summary), encoding="utf-8")
    json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument(
        "--skip-baseline-reconciliation",
        action="store_true",
        help="Test/fixture use only; production-shaped research runs enforce baselines.",
    )
    args = parser.parse_args(argv)

    summary = build_audit(
        load_jsonl(args.input),
        enforce_baseline=not args.skip_baseline_reconciliation,
    )
    write_outputs(summary, args.output_md, args.output_json)
    print(
        f"status={summary['status']} decision={summary['decision']} "
        f"counter={summary['counter']['rows']}/{summary['counter']['floor']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
