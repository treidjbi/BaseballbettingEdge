"""Research-only policy matrix for frozen Strong Base FIRE policies.

The six selectors use pregame fields only. Historical outcomes describe the
frozen baselines; only rows on or after 2026-07-30 advance prospective review.
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
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import strong_base_decision_lab as strong_base  # noqa: E402


DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT_MD = ROOT / "analytics" / "output" / "strong_base_fire_policy_matrix.md"
DEFAULT_OUTPUT_JSON = ROOT / "analytics" / "output" / "strong_base_fire_policy_matrix.json"
PROSPECTIVE_START = "2026-07-30"
REVIEW_FLOOR = 75
WIN_LOSS = {"win", "loss"}
HISTORICAL_BASELINES = {
    "cap_high_raw_edge": {"rows": 926, "pnl": -122.20},
    "cap_market_fade": {"rows": 872, "pnl": -94.37},
    "keep_fire_over_moderate_ev_normal_leash": {"rows": 198, "pnl": 21.25},
    "keep_fire_market_agreed_moderate_ev": {"rows": 170, "pnl": 20.05},
    "strict_runtime_core_flat": {"rows": 96, "pnl": 17.72},
    "keep_fire_if_strong_base_or_market_anchor_strict": {"rows": 112, "pnl": 20.52},
}
FROZEN_SHORTLIST = {
    "downside_cap": "cap_high_raw_edge",
    "retained_fire": "strict_runtime_core_flat",
}


@dataclass(frozen=True)
class PolicySpec:
    id: str
    family: str
    selector: Callable[[dict[str, Any]], bool]
    fingerprint_fields: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            {"id": self.id, "family": self.family, "fields": self.fingerprint_fields},
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _verdict(row: dict[str, Any]) -> str:
    return str(
        row.get("display_verdict")
        or row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("verdict")
        or ""
    ).strip()


def _raw_verdict(row: dict[str, Any]) -> str:
    return str(row.get("raw_verdict") or row.get("original_verdict") or _verdict(row)).strip()


def _is_fire(row: dict[str, Any]) -> bool:
    return _verdict(row).startswith("FIRE")


def _edge(row: dict[str, Any]) -> float | None:
    return _float(row.get("edge"))


def _ev(row: dict[str, Any]) -> float | None:
    for key in ("locked_adj_ev", "adj_ev", "adj_ev_roi", "ev"):
        value = _float(row.get(key))
        if value is not None:
            return value
    return None


def _moderate_ev(row: dict[str, Any]) -> bool:
    value = _ev(row)
    return value is not None and 0.06 <= value < 0.17


def _market_agreed(row: dict[str, Any]) -> bool:
    return str(row.get("model_market_relationship") or "") == "model_agrees_with_favorite"


def _market_fade(row: dict[str, Any]) -> bool:
    return str(row.get("model_market_relationship") or "") == "model_fades_favorite"


def _normal_leash(row: dict[str, Any]) -> bool:
    return str(row.get("leash_risk_bucket") or row.get("opportunity_bucket") or "").lower() == "normal"


def _keep_over(row: dict[str, Any]) -> bool:
    return _is_fire(row) and str(row.get("side") or "").lower() == "over" and _moderate_ev(row) and _normal_leash(row)


def _keep_agreed(row: dict[str, Any]) -> bool:
    return (
        _is_fire(row)
        and _market_agreed(row)
        and _moderate_ev(row)
        and str(row.get("bet_timing_window") or "") == "pre_30"
    )


def _strict_core(row: dict[str, Any]) -> bool:
    edge = _edge(row)
    return (_keep_over(row) or _keep_agreed(row)) and edge is not None and edge < 0.06 and not _market_fade(row)


def _market_anchor_strict(row: dict[str, Any]) -> bool:
    selector = row.get("market_anchor_selector")
    if not isinstance(selector, dict):
        return False
    return "market_anchor_strict" in {str(label) for label in selector.get("labels") or []}


def policy_specs() -> tuple[PolicySpec, ...]:
    specs = (
        PolicySpec(
            "cap_high_raw_edge",
            "downside_cap",
            lambda row: (_edge(row) is not None and _edge(row) >= 0.06),
            ("edge>=0.06",),
        ),
        PolicySpec(
            "cap_market_fade",
            "downside_cap",
            _market_fade,
            ("model_market_relationship=model_fades_favorite",),
        ),
        PolicySpec(
            "keep_fire_over_moderate_ev_normal_leash",
            "retained_fire",
            _keep_over,
            ("display_verdict=FIRE", "side=over", "0.06<=adj_ev<0.17", "leash=normal"),
        ),
        PolicySpec(
            "keep_fire_market_agreed_moderate_ev",
            "retained_fire",
            _keep_agreed,
            (
                "display_verdict=FIRE",
                "model_market_relationship=model_agrees_with_favorite",
                "0.06<=adj_ev<0.17",
                "bet_timing_window=pre_30",
            ),
        ),
        PolicySpec(
            "strict_runtime_core_flat",
            "retained_fire",
            _strict_core,
            (
                "keep_fire_over_moderate_ev_normal_leash OR keep_fire_market_agreed_moderate_ev",
                "edge<0.06",
                "not model_fades_favorite",
            ),
        ),
        PolicySpec(
            "keep_fire_if_strong_base_or_market_anchor_strict",
            "retained_fire",
            lambda row: _is_fire(row) and (_strict_core(row) or _market_anchor_strict(row)),
            ("display_verdict=FIRE", "strict_runtime_core_flat OR stored market_anchor_strict label"),
        ),
    )
    ids = [spec.id for spec in specs]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate Strong Base policy ids are not allowed")
    if any(spec.family not in {"downside_cap", "retained_fire"} for spec in specs):
        raise ValueError("Unsupported Strong Base policy family")
    return specs


def evaluate_policy(row: dict[str, Any], spec: PolicySpec) -> dict[str, Any]:
    """Evaluate one policy without reading outcomes or postgame measurements."""

    if spec.family == "retained_fire" and not _is_fire(row):
        return {"selected": False, "action": "excluded_non_fire"}
    selected = bool(spec.selector(row))
    if not selected:
        return {"selected": False, "action": "not_selected"}
    if spec.family == "retained_fire":
        return {"selected": True, "action": "retained_fire"}
    if _raw_verdict(row).startswith("FIRE") and not _is_fire(row):
        return {"selected": True, "action": "already_capped"}
    if _is_fire(row):
        return {"selected": True, "action": "incremental_would_cap"}
    return {"selected": True, "action": "no_fire_exposure"}


def _row_key(row: dict[str, Any]) -> str:
    pitcher = " ".join(str(row.get("pitcher") or row.get("pitcher_name") or "").lower().split())
    return "|".join(
        (
            str(row.get("slate_date") or row.get("date") or ""),
            pitcher,
            str(row.get("side") or "").lower(),
        )
    )


def _tracked(row: dict[str, Any]) -> bool:
    if row.get("result") not in WIN_LOSS:
        return False
    if "is_tracked_pick" in row:
        value = row.get("is_tracked_pick")
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes"}
        return bool(value)
    return _verdict(row) not in {"", "PASS"}


def _stake(row: dict[str, Any]) -> float:
    return 2.0 if _verdict(row) == "FIRE 2u" else 1.0


def _policy_value(row: dict[str, Any], family: str) -> float:
    pnl = strong_base._row_pnl(row)
    if family == "downside_cap":
        return -pnl * _stake(row)
    return pnl


def _score(rows: list[dict[str, Any]], family: str) -> dict[str, Any]:
    wins = sum(1 for row in rows if row.get("result") == "win")
    losses = sum(1 for row in rows if row.get("result") == "loss")
    pnl = sum(strong_base._row_pnl(row) for row in rows)
    value = sum(_policy_value(row, family) for row in rows)
    return {
        "rows": len(rows),
        "wins": wins,
        "losses": losses,
        "pnl": round(pnl, 3),
        "policy_value": round(value, 3),
        "roi": round(pnl / len(rows), 4) if rows else 0.0,
    }


def _provider(row: dict[str, Any]) -> str:
    for key in ("provider_era", "odds_source", "market_source_mode", "market_provider"):
        if row.get(key):
            return str(row[key])
    return "missing"


def _agreement(row: dict[str, Any]) -> str:
    return str(row.get("market_agreement_label") or row.get("market_agreement_signal") or "missing")


def _clv(row: dict[str, Any]) -> str:
    if row.get("clv_bucket"):
        return str(row["clv_bucket"])
    keys = ("price_clv_cents", "line_clv_delta", "beat_close_price", "beat_close_line")
    if not any(key in row and row.get(key) is not None for key in keys):
        return "missing"
    return strong_base.clv_bucket(row)


def _path_b(row: dict[str, Any]) -> str:
    return str(row.get("path_b_coverage_bucket") or strong_base.path_b_coverage_bucket(row))


def _workload(row: dict[str, Any]) -> str:
    return str(row.get("workload_bucket") or row.get("leash_risk_bucket") or row.get("opportunity_bucket") or "missing")


SLICE_DIMENSIONS: tuple[tuple[str, Callable[[dict[str, Any]], str]], ...] = (
    ("side", lambda row: str(row.get("side") or "missing").lower()),
    ("price", lambda row: str(row.get("price_sign") or "missing")),
    ("k_line", lambda row: str(row.get("line_bucket") or row.get("line") or "missing")),
    ("fire_level", lambda row: _verdict(row) or "missing"),
    ("quality", lambda row: str(row.get("quality_gate_level") or "missing")),
    ("timing", lambda row: str(row.get("bet_timing_window") or "missing")),
    ("model_market", lambda row: str(row.get("model_market_relationship") or "missing")),
    ("path_b", _path_b),
    ("workload", _workload),
    ("clv_proxy", _clv),
    ("provider", _provider),
    ("agreement", _agreement),
)


def _slice_scores(rows: list[dict[str, Any]], family: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for dimension, bucket_fn in SLICE_DIMENSIONS:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            buckets[bucket_fn(row)].append(row)
        result[dimension] = {bucket: _score(bucket_rows, family) for bucket, bucket_rows in sorted(buckets.items())}
    return result


def _recent(rows: list[dict[str, Any]], slate_count: int = 14) -> list[dict[str, Any]]:
    dates = sorted({str(row.get("slate_date") or row.get("date") or "") for row in rows})
    keep = set(dates[-slate_count:])
    return [row for row in rows if str(row.get("slate_date") or row.get("date") or "") in keep]


def _leave_one_out(rows: list[dict[str, Any]], family: str) -> dict[str, Any]:
    dates = sorted({str(row.get("slate_date") or row.get("date") or "") for row in rows})
    cases = [
        {
            "excluded_slate_date": date,
            **_score([row for row in rows if str(row.get("slate_date") or row.get("date") or "") != date], family),
        }
        for date in dates
    ]
    return {
        "cases": cases,
        "minimum": min(cases, key=lambda case: case["policy_value"]) if cases else {"policy_value": 0.0},
    }


def _critical_missing(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "provider": sum(1 for row in rows if _provider(row) == "missing"),
        "agreement": sum(1 for row in rows if _agreement(row) == "missing"),
        "clv_proxy": sum(1 for row in rows if _clv(row) == "missing"),
    }


def _effect_rows(rows: list[dict[str, Any]], spec: PolicySpec) -> tuple[list[dict[str, Any]], Counter]:
    actions: Counter = Counter()
    effect: list[dict[str, Any]] = []
    target = "incremental_would_cap" if spec.family == "downside_cap" else "retained_fire"
    for row in rows:
        evaluated = evaluate_policy(row, spec)
        actions[evaluated["action"]] += 1
        if evaluated["action"] == target:
            effect.append(row)
    return effect, actions


def _policy_summary(rows: list[dict[str, Any]], spec: PolicySpec) -> tuple[dict[str, Any], set[str]]:
    effect, actions = _effect_rows(rows, spec)
    prospective = [row for row in effect if str(row.get("slate_date") or row.get("date") or "") >= PROSPECTIVE_START]
    current_provider = [
        row
        for row in effect
        if "therundown_propline" in _provider(row).lower()
        or str(row.get("slate_date") or row.get("date") or "") >= strong_base.CURRENT_PROVIDER_START
    ]
    recent = _recent(effect)
    slices = _slice_scores(prospective, spec.family)
    missing = _critical_missing(prospective)
    negative_slices = [
        {"dimension": dimension, "bucket": bucket, **score}
        for dimension, buckets in slices.items()
        for bucket, score in buckets.items()
        if score["rows"] >= 10 and score["policy_value"] < 0
    ]
    loo = _leave_one_out(prospective, spec.family)
    floor_met = len(prospective) >= REVIEW_FLOOR
    gates = {
        "prospective_floor_75": floor_met,
        "current_provider_positive": _score(current_provider, spec.family)["policy_value"] > 0,
        "latest_14_positive": _score(recent, spec.family)["policy_value"] > 0,
        "leave_one_slate_out_positive": loo["minimum"]["policy_value"] > 0,
        "critical_attribution_complete": all(value == 0 for value in missing.values()),
        "mandatory_slices_non_negative": not negative_slices,
    }
    if all(gates.values()):
        readiness = "ready_for_separate_review"
    elif floor_met and not gates["critical_attribution_complete"]:
        readiness = "blocked_missing_attribution"
    elif floor_met:
        readiness = "hold_failed_slices"
    else:
        readiness = "collecting"
    summary = {
        "id": spec.id,
        "family": spec.family,
        "fingerprint": spec.fingerprint,
        "fingerprint_fields": list(spec.fingerprint_fields),
        "historical_locked_baseline": HISTORICAL_BASELINES[spec.id],
        "selector_match_rows": (
            int(actions.get("incremental_would_cap", 0))
            + int(actions.get("already_capped", 0))
            + int(actions.get("no_fire_exposure", 0))
            if spec.family == "downside_cap"
            else int(actions.get("retained_fire", 0))
        ),
        "selected_effect_rows": len(effect),
        "incremental_would_cap_rows": int(actions.get("incremental_would_cap", 0)),
        "already_capped_rows": int(actions.get("already_capped", 0)),
        "retained_fire_rows": int(actions.get("retained_fire", 0)),
        "action_counts": dict(sorted(actions.items())),
        "all_available": _score(effect, spec.family),
        "prospective": _score(prospective, spec.family),
        "current_provider": _score(current_provider, spec.family),
        "latest_14_slates": _score(recent, spec.family),
        "leave_one_slate_out": loo,
        "slices": slices,
        "missing_critical_attribution": missing,
        "negative_mandatory_slices": negative_slices,
        "gates": gates,
        "readiness": readiness,
        "shortlist_role": (
            "prospective_candidate"
            if FROZEN_SHORTLIST.get(spec.family) == spec.id
            else "control"
        ),
    }
    return summary, {_row_key(row) for row in effect}


def _overlap(policy_sets: dict[str, set[str]], policy_values: dict[str, float]) -> list[dict[str, Any]]:
    ids = list(policy_sets)
    rows: list[dict[str, Any]] = []
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            left_set = policy_sets[left]
            right_set = policy_sets[right]
            union = left_set | right_set
            intersection = left_set & right_set
            rows.append(
                {
                    "left": left,
                    "right": right,
                    "overlap_rows": len(intersection),
                    "jaccard": round(len(intersection) / len(union), 4) if union else 0.0,
                    "left_unique_rows": len(left_set - right_set),
                    "right_unique_rows": len(right_set - left_set),
                    "paired_unit_delta": round(policy_values[left] - policy_values[right], 3),
                    "prefer_simpler_if_over_80pct": bool(union and len(intersection) / len(union) > 0.8),
                }
            )
    return rows


def build_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tracked = [row for row in rows if _tracked(row)]
    policies: list[dict[str, Any]] = []
    policy_sets: dict[str, set[str]] = {}
    policy_values: dict[str, float] = {}
    for spec in policy_specs():
        summary, selected_keys = _policy_summary(tracked, spec)
        policies.append(summary)
        policy_sets[spec.id] = selected_keys
        policy_values[spec.id] = float(summary["all_available"]["policy_value"])
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "prospective_start": PROSPECTIVE_START,
        "review_floor": REVIEW_FLOOR,
        "tracked_graded_rows": len(tracked),
        "duplicate_row_keys": sum(1 for count in Counter(_row_key(row) for row in tracked).values() if count > 1),
        "frozen_shortlist": FROZEN_SHORTLIST,
        "policies": policies,
        "overlap": _overlap(policy_sets, policy_values),
        "live_behavior_changed": False,
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Strong Base FIRE Policy Shadow Matrix",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "Research-only. These policies do not change live verdicts, thresholds, stakes, providers, notifications, locks, artifacts, UI, retention, or environment variables.",
        "",
        "## Executive Read",
        "",
        f"- Prospective freeze date: `{summary['prospective_start']}`; review floor: `{summary['review_floor']}` graded policy rows.",
        f"- Frozen downside candidate: `{summary['frozen_shortlist']['downside_cap']}`.",
        f"- Frozen retained-FIRE candidate: `{summary['frozen_shortlist']['retained_fire']}`.",
        "- All other policies remain controls. Tyler approval is required before any behavior-changing canary is drafted.",
        "",
        "## Policy Matrix",
        "",
        "| Policy | Family | Locked history | Prospective | Current provider | Latest 14 | Readiness |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for policy in summary["policies"]:
        locked = policy["historical_locked_baseline"]
        prospective = policy["prospective"]
        lines.append(
            f"| `{policy['id']}` | `{policy['family']}` | {locked['rows']} / {locked['pnl']:+.2f}u | "
            f"{prospective['rows']} / {prospective['policy_value']:+.3f}u | "
            f"{policy['current_provider']['policy_value']:+.3f}u | {policy['latest_14_slates']['policy_value']:+.3f}u | `{policy['readiness']}` |"
        )
    lines.extend(
        [
            "",
            "## Incremental Accounting",
            "",
            "| Policy | Selector matches | Incremental caps | Already capped | Retained FIRE | Missing provider/agreement/CLV |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for policy in summary["policies"]:
        lines.append(
            f"| `{policy['id']}` | {policy['selector_match_rows']} | {policy['incremental_would_cap_rows']} | {policy['already_capped_rows']} | "
            f"{policy['retained_fire_rows']} | `{json.dumps(policy['missing_critical_attribution'], sort_keys=True)}` |"
        )
    lines.extend(
        [
            "",
            "## Pairwise Overlap",
            "",
            "| Left | Right | Overlap | Jaccard | Left unique | Right unique | Unit delta |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in summary["overlap"]:
        lines.append(
            f"| `{item['left']}` | `{item['right']}` | {item['overlap_rows']} | {item['jaccard']:.1%} | "
            f"{item['left_unique_rows']} | {item['right_unique_rows']} | {item['paired_unit_delta']:+.3f}u |"
        )
    lines.extend(
        [
            "",
            "## Read Rule",
            "",
            "- Historical results identify the frozen policies but do not advance the prospective counter.",
            "- Readiness requires 75 prospective rows, positive current-provider/latest-14/leave-one-slate-out value, complete attribution, and no negative mandatory slice with at least 10 rows.",
            "- When overlap exceeds 80%, prefer the simpler policy unless the complex policy has material paired value.",
            "",
        ]
    )
    return "\n".join(lines)


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    args = parser.parse_args(argv)

    summary = build_matrix(load_rows(args.input))
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_report(summary), encoding="utf-8")
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
