"""Paired, research-only audit of market-anchor downside counterfactuals.

The audit consumes the selector metadata captured before games.  It never
recomputes the selector from outcomes and does not change live behavior.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import strong_base_decision_lab as strong_base  # noqa: E402


DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT_MD = ROOT / "analytics" / "output" / "market_anchor_downside_counterfactual_audit.md"
DEFAULT_OUTPUT_JSON = ROOT / "analytics" / "output" / "market_anchor_downside_counterfactual_audit.json"
WIN_LOSS = {"win", "loss"}
SELECTOR_SHADOW_DEPLOY_DATE = "2026-06-16"
VERDICT_RANK = {"PASS": 0, "LEAN": 1, "FIRE 1u": 2, "FIRE 2u": 3}
CRITICAL_DIMENSIONS = ("provider", "agreement", "clv_proxy")


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


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


def _tracked(row: dict[str, Any]) -> bool:
    if row.get("result") not in WIN_LOSS:
        return False
    if "is_tracked_pick" in row:
        return _truthy(row.get("is_tracked_pick"))
    return _verdict(row) not in {"", "PASS"}


def _row_key(row: dict[str, Any]) -> str:
    pitcher = " ".join(str(row.get("pitcher") or row.get("pitcher_name") or "").lower().split())
    return "|".join(
        (
            str(row.get("slate_date") or row.get("date") or ""),
            pitcher,
            str(row.get("side") or "").lower(),
        )
    )


def _is_post_start(row: dict[str, Any]) -> bool:
    timing = str(
        row.get("bet_timing_window")
        or row.get("timing_bucket")
        or row.get("capture_timing")
        or ""
    ).lower()
    return timing in {"post_start", "in_game", "post_game", "started"} or _truthy(row.get("game_started"))


def _layer_applied(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if _truthy(value.get("applied")) or _truthy(value.get("capped")):
        return True
    current = str(value.get("current_verdict") or "")
    would = str(value.get("would_verdict") or value.get("final_verdict") or "")
    return bool(current and would and current != would)


def _earlier_layers(row: dict[str, Any]) -> list[str]:
    aliases = (
        ("quality_gate", ("quality_gate", "quality_gate_metadata")),
        ("confidence_referee", ("confidence_referee", "market_favorite_confidence_referee")),
        ("profit_rescue", ("profit_rescue_referee", "profit_rescue")),
    )
    found: list[str] = []
    for label, keys in aliases:
        if any(_layer_applied(row.get(key)) for key in keys):
            found.append(label)
    return found


def candidate_action(row: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable selector action recorded on one Gate C row."""

    selector = row.get("market_anchor_selector")
    raw_verdict = _raw_verdict(row)
    display_verdict = _verdict(row)
    base = {
        "row_key": _row_key(row),
        "slate_date": str(row.get("slate_date") or row.get("date") or ""),
        "pitcher": str(row.get("pitcher") or row.get("pitcher_name") or ""),
        "side": str(row.get("side") or "").lower(),
        "raw_verdict": raw_verdict,
        "display_verdict": display_verdict,
        "final_verdict": str(row.get("verdict") or display_verdict),
        "selector_current_verdict": None,
        "hypothetical_verdict": None,
        "selector_mode": None,
        "selector_reasons": [],
        "earlier_cap_reasons": list(row.get("cap_reasons") or []),
        "earlier_cap_layers": _earlier_layers(row),
        "applied": False,
        "would_change": False,
        "cap_depth": 0,
        "exact": True,
    }
    if _is_post_start(row):
        return {**base, "classification": "post_start_excluded", "exact": False}
    if not isinstance(selector, dict):
        return {**base, "classification": "missing_metadata", "exact": False}

    current = str(selector.get("current_verdict") or "").strip()
    hypothetical = str(selector.get("would_verdict") or selector.get("would_cap_to") or "").strip()
    selected_side = str(selector.get("selected_side") or row.get("side") or "").lower()
    base.update(
        {
            "selector_current_verdict": current or None,
            "hypothetical_verdict": hypothetical or None,
            "selector_mode": str(selector.get("mode") or ""),
            "selector_reasons": list(selector.get("reasons") or []),
            "applied": _truthy(selector.get("applied")),
        }
    )
    if not current or not hypothetical or selected_side != base["side"]:
        return {**base, "classification": "invalid_metadata", "exact": False}

    current_rank = VERDICT_RANK.get(current)
    hypothetical_rank = VERDICT_RANK.get(hypothetical)
    if current_rank is None or hypothetical_rank is None:
        return {**base, "classification": "invalid_metadata", "exact": False}

    base["cap_depth"] = max(0, current_rank - hypothetical_rank)
    if raw_verdict.startswith("FIRE") and not current.startswith("FIRE"):
        return {**base, "classification": "already_capped"}
    if current.startswith("FIRE") and hypothetical_rank < current_rank:
        return {**base, "classification": "would_change", "would_change": True}
    return {**base, "classification": "unchanged"}


def paired_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paired: list[dict[str, Any]] = []
    for row in rows:
        if not _tracked(row):
            continue
        if str(row.get("slate_date") or row.get("date") or "") < SELECTOR_SHADOW_DEPLOY_DATE:
            continue
        action = candidate_action(row)
        if action["classification"] == "would_change" and action["exact"]:
            paired.append({**action, "source_row": row})
    return sorted(paired, key=lambda item: (item["slate_date"], item["row_key"]))


def _pnl(row: dict[str, Any]) -> float:
    return round(strong_base._row_pnl(row), 4)


def _stake(verdict: str) -> float:
    if verdict == "FIRE 2u":
        return 2.0
    if verdict == "FIRE 1u":
        return 1.0
    return 0.0


def _score(items: list[dict[str, Any]]) -> dict[str, Any]:
    avoided = 0.0
    foregone = 0.0
    control_pnl = 0.0
    wins = losses = 0
    by_slate: dict[str, float] = defaultdict(float)
    for item in items:
        row = item["source_row"]
        pnl = _pnl(row) * _stake(str(item["selector_current_verdict"]))
        control_pnl += pnl
        if row.get("result") == "win":
            wins += 1
            foregone += max(0.0, pnl)
        else:
            losses += 1
            avoided += max(0.0, -pnl)
        by_slate[item["slate_date"]] += -pnl
    delta = avoided - foregone
    max_contribution = max(by_slate.values(), default=0.0)
    return {
        "rows": len(items),
        "wins": wins,
        "losses": losses,
        "control_pnl": round(control_pnl, 3),
        "hypothetical_pnl": 0.0,
        "avoided_losses": losses,
        "avoided_loss_units": round(avoided, 3),
        "foregone_wins": wins,
        "foregone_win_units": round(foregone, 3),
        "net_unit_delta": round(delta, 3),
        "max_one_slate_contribution": round(max_contribution, 3),
    }


def _explicit_clv(row: dict[str, Any]) -> str:
    if row.get("clv_bucket"):
        return str(row["clv_bucket"])
    keys = ("price_clv_cents", "line_clv_delta", "beat_close_price", "beat_close_line")
    if not any(key in row and row.get(key) is not None for key in keys):
        return "missing"
    return strong_base.clv_bucket(row)


def _provider(row: dict[str, Any]) -> str:
    for key in ("provider_era", "odds_source", "market_source_mode", "market_provider"):
        if row.get(key):
            return str(row[key])
    return "missing"


def _agreement(row: dict[str, Any]) -> str:
    return str(row.get("market_agreement_label") or row.get("market_agreement_signal") or "missing")


def _path_b(row: dict[str, Any]) -> str:
    return str(row.get("path_b_coverage_bucket") or strong_base.path_b_coverage_bucket(row))


def _workload(row: dict[str, Any]) -> str:
    return str(row.get("workload_bucket") or row.get("leash_risk_bucket") or row.get("opportunity_bucket") or "missing")


SLICE_DIMENSIONS: tuple[tuple[str, Callable[[dict[str, Any]], str]], ...] = (
    ("side", lambda row: str(row.get("side") or "missing").lower()),
    ("k_line", lambda row: str(row.get("line_bucket") or row.get("line") or "missing")),
    ("price", lambda row: str(row.get("price_sign") or "missing")),
    ("fire_level", lambda row: _verdict(row) or "missing"),
    ("quality", lambda row: str(row.get("quality_gate_level") or "missing")),
    ("timing", lambda row: str(row.get("bet_timing_window") or "missing")),
    ("model_market", lambda row: str(row.get("model_market_relationship") or "missing")),
    ("path_b", _path_b),
    ("workload", _workload),
    ("clv_proxy", _explicit_clv),
    ("provider", _provider),
    ("agreement", _agreement),
)


def _slice_scores(items: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for dimension, bucket_fn in SLICE_DIMENSIONS:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            buckets[bucket_fn(item["source_row"])].append(item)
        result[dimension] = {bucket: _score(bucket_items) for bucket, bucket_items in sorted(buckets.items())}
    return result


def _recent(items: list[dict[str, Any]], slate_count: int = 14) -> list[dict[str, Any]]:
    dates = sorted({item["slate_date"] for item in items if item["slate_date"]})
    keep = set(dates[-slate_count:])
    return [item for item in items if item["slate_date"] in keep]


def _leave_one_out(items: list[dict[str, Any]]) -> dict[str, Any]:
    dates = sorted({item["slate_date"] for item in items if item["slate_date"]})
    cases = [
        {"excluded_slate_date": date, **_score([item for item in items if item["slate_date"] != date])}
        for date in dates
    ]
    return {
        "cases": cases,
        "minimum": min(cases, key=lambda case: case["net_unit_delta"]) if cases else {"net_unit_delta": 0.0},
    }


def _public_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if key != "source_row"}


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tracked = [row for row in rows if _tracked(row)]
    audit_window = [
        row
        for row in tracked
        if str(row.get("slate_date") or row.get("date") or "") >= SELECTOR_SHADOW_DEPLOY_DATE
    ]
    actions = [candidate_action(row) for row in audit_window]
    candidates = paired_rows(rows)
    candidate_keys = [item["row_key"] for item in candidates]
    duplicate_keys = sum(1 for count in Counter(candidate_keys).values() if count > 1)
    missing_fire_metadata = sum(
        1
        for row, action in zip(audit_window, actions)
        if (_raw_verdict(row).startswith("FIRE") or _verdict(row).startswith("FIRE"))
        and action["classification"] in {"missing_metadata", "invalid_metadata"}
    )
    exact = duplicate_keys == 0 and missing_fire_metadata == 0
    cohort = _score(candidates)
    slices = _slice_scores(candidates)
    missing_critical = {
        dimension: int((slices.get(dimension, {}).get("missing") or {}).get("rows", 0))
        for dimension in CRITICAL_DIMENSIONS
    }
    side_counts = Counter(item["side"] for item in candidates)
    current_provider = [
        item
        for item in candidates
        if "therundown_propline" in _provider(item["source_row"]).lower()
        or item["slate_date"] >= strong_base.CURRENT_PROVIDER_START
    ]
    recent = _recent(candidates)
    gates = {
        "exact_reconstruction": exact,
        "would_change_floor_50": len(candidates) >= 50,
        "side_floor_10_each": side_counts.get("over", 0) >= 10 and side_counts.get("under", 0) >= 10,
        "current_provider_non_negative": _score(current_provider)["net_unit_delta"] >= 0,
        "latest_14_non_negative": _score(recent)["net_unit_delta"] >= 0,
        "critical_attribution_complete": all(value == 0 for value in missing_critical.values()),
    }
    if all(gates.values()) and cohort["net_unit_delta"] > 0:
        decision = "draft_separate_canary"
    elif exact and len(candidates) >= 50 and cohort["net_unit_delta"] <= 0:
        decision = "retire_downside_path"
    else:
        decision = "keep_shadow"
    counts = Counter(action["classification"] for action in actions)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "selector_shadow_deploy_date": SELECTOR_SHADOW_DEPLOY_DATE,
        "tracked_rows": len(tracked),
        "audit_window_rows": len(audit_window),
        "metadata_rows": sum(1 for row in audit_window if isinstance(row.get("market_anchor_selector"), dict)),
        "classification_counts": dict(sorted(counts.items())),
        "would_change_rows": len(candidates),
        "applied_rows": sum(1 for action in actions if action["applied"]),
        "cap_depth_counts": dict(sorted(Counter(str(item["cap_depth"]) for item in candidates).items())),
        "duplicate_keys": duplicate_keys,
        "missing_fire_metadata": missing_fire_metadata,
        "post_start_excluded_rows": int(counts.get("post_start_excluded", 0)),
        "exact_reconstruction": exact,
        "cohort": cohort,
        "current_provider": _score(current_provider),
        "latest_14_slates": _score(recent),
        "slices": slices,
        "rolling_windows": {"latest_14_slates": _score(recent)},
        "leave_one_slate_out": _leave_one_out(candidates),
        "missing_critical_attribution": missing_critical,
        "gates": gates,
        "decision": decision,
        "paired_rows": [_public_item(item) for item in candidates],
    }


def _score_line(label: str, score: dict[str, Any]) -> str:
    return (
        f"- {label}: `{score['rows']}` rows, `{score['wins']}-{score['losses']}`, "
        f"control `{score['control_pnl']:+.3f}u`, downside delta `{score['net_unit_delta']:+.3f}u`."
    )


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Market-Anchor Downside Counterfactual Audit",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "Research-only. The selector remains shadow; this audit does not change verdicts, staking, providers, notifications, locks, artifacts, UI, or source-of-truth behavior.",
        "",
        "## Executive Read",
        "",
        f"- Decision: `{summary['decision']}`.",
        f"- Exact paired reconstruction: `{str(summary['exact_reconstruction']).lower()}`.",
        f"- Selector audit window: `{summary['selector_shadow_deploy_date']}` onward; `{summary['audit_window_rows']}` tracked graded rows.",
        f"- Stored selector metadata: `{summary['metadata_rows']}/{summary['audit_window_rows']}` audit-window rows.",
        f"- Exact would-change cohort: `{summary['would_change_rows']}`; applied live: `{summary['applied_rows']}`.",
        _score_line("Paired cohort", summary["cohort"]),
        f"- Avoided loss: `{summary['cohort']['avoided_loss_units']:+.3f}u`; foregone wins: `{summary['cohort']['foregone_win_units']:+.3f}u`.",
        f"- Maximum one-slate contribution: `{summary['cohort']['max_one_slate_contribution']:+.3f}u`.",
        "",
        "## Cohort Integrity",
        "",
        f"- Duplicate candidate keys: `{summary['duplicate_keys']}`.",
        f"- FIRE rows missing exact pre-start metadata: `{summary['missing_fire_metadata']}`.",
        f"- Explicit post-start exclusions: `{summary['post_start_excluded_rows']}`.",
        f"- Classification counts: `{json.dumps(summary['classification_counts'], sort_keys=True)}`.",
        f"- Cap-depth counts: `{json.dumps(summary['cap_depth_counts'], sort_keys=True)}`.",
        "",
        "## Review Gates",
        "",
    ]
    for gate, passed in summary["gates"].items():
        lines.append(f"- `{gate}`: `{'pass' if passed else 'closed'}`")
    lines.extend(
        [
            "",
            _score_line("Current-provider cohort", summary["current_provider"]),
            _score_line("Latest 14 slates", summary["latest_14_slates"]),
            f"- Missing critical attribution: `{json.dumps(summary['missing_critical_attribution'], sort_keys=True)}`.",
            "",
            "## Mandatory Slices",
            "",
            "| Dimension | Bucket | Rows | W-L | Downside delta |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for dimension, buckets in summary["slices"].items():
        for bucket, score in buckets.items():
            lines.append(
                f"| `{dimension}` | `{bucket}` | {score['rows']} | {score['wins']}-{score['losses']} | {score['net_unit_delta']:+.3f}u |"
            )
    lines.extend(
        [
            "",
            "## Decision Rule",
            "",
            "- `draft_separate_canary` requires 50 exact would-change rows, 10 per side, non-negative current-provider and latest-14 deltas, complete provider/agreement/CLV attribution, and positive paired value.",
            "- Any live activation remains a separate Tyler-approved plan.",
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

    summary = build_summary(load_rows(args.input))
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(render_report(summary), encoding="utf-8")
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_md}")
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
