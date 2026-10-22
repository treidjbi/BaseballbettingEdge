"""Shadow-only Strong Base decision lab for bet-selection policy review.

This diagnostic reads the compact Gate C pitcher outcome dataset and drafts a
candidate policy scoreboard. It does not change live lambda, verdicts,
thresholds, staking, provider order, notifications, locks, retention,
calibration, dashboard artifacts, or source-of-truth behavior.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "strong_base_decision_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
CURRENT_PROVIDER_START = "2026-06-24"
POST_BOLTODDS_RETIREMENT = "2026-06-17"
WIN_LOSS_RESULTS = {"win", "loss"}
MANDATORY_SLICE_FIELDS: tuple[tuple[str, Callable[[dict[str, Any]], str]], ...] = (
    ("side", lambda row: str(row.get("side") or "unknown").lower()),
    ("k_line", lambda row: str(row.get("line_bucket") or "unknown")),
    ("price", lambda row: str(row.get("price_sign") or "unknown")),
    ("model_market", lambda row: str(row.get("model_market_relationship") or "unknown")),
    ("clv", lambda row: clv_bucket(row)),
    ("quality", lambda row: str(row.get("quality_gate_level") or "unknown")),
    ("path_b", lambda row: path_b_coverage_bucket(row)),
    ("provider_era", lambda row: provider_era(row)),
    ("market_agreement", lambda row: str(row.get("market_agreement_label") or "missing")),
)


@dataclass(frozen=True)
class CandidateDefinition:
    name: str
    policy_lane: str
    kind: str
    runtime_safe: bool
    recommendation: str
    rule: Callable[[dict[str, Any]], bool]


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _verdict(row: dict[str, Any]) -> str:
    return str(
        row.get("display_verdict")
        or row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("current_verdict")
        or row.get("verdict")
        or ""
    ).strip()


def _is_fire(row: dict[str, Any]) -> bool:
    return _verdict(row).startswith("FIRE")


def _is_lean(row: dict[str, Any]) -> bool:
    return _verdict(row) == "LEAN"


def _is_pass(row: dict[str, Any]) -> bool:
    return _verdict(row) == "PASS"


def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def _edge(row: dict[str, Any]) -> float | None:
    return _to_float(row.get("edge"))


def _adj_ev(row: dict[str, Any]) -> float | None:
    return _to_float(row.get("locked_adj_ev")) or _to_float(row.get("adj_ev")) or _to_float(row.get("ev"))


def edge_bucket(row: dict[str, Any]) -> str:
    edge = _edge(row)
    if edge is None:
        return "edge_unknown"
    if edge < 0:
        return "edge_negative"
    if edge < 0.02:
        return "edge_0_to_2"
    if edge < 0.04:
        return "edge_2_to_4"
    if edge < 0.06:
        return "edge_4_to_6"
    return "edge_6_plus"


def ev_bucket(row: dict[str, Any]) -> str:
    ev = _adj_ev(row)
    if ev is None:
        return "ev_unknown"
    if ev < 0:
        return "ev_negative"
    if ev < 0.06:
        return "ev_0_to_6"
    if ev < 0.17:
        return "ev_6_to_17"
    return "ev_17_plus"


def no_vig_positive(row: dict[str, Any]) -> bool:
    gap = _to_float(row.get("model_no_vig_gap"))
    return gap is not None and gap >= 0.02


def clv_bucket(row: dict[str, Any]) -> str:
    price_clv = _to_float(row.get("price_clv_cents"))
    line_clv = _to_float(row.get("line_clv_delta"))
    if _is_true(row.get("beat_close_price")) or (price_clv is not None and price_clv > 0):
        return "beat_close_price"
    if _is_true(row.get("beat_close_line")) or (line_clv is not None and line_clv > 0):
        return "beat_close_line"
    if price_clv is not None and price_clv < 0:
        return "worse_close_price"
    if line_clv is not None and line_clv < 0:
        return "worse_close_line"
    return "neutral_or_unknown"


def provider_era(row: dict[str, Any]) -> str:
    slate_date = str(row.get("slate_date") or row.get("date") or "")
    if slate_date >= CURRENT_PROVIDER_START:
        return "official_therundown_propline"
    if slate_date >= POST_BOLTODDS_RETIREMENT:
        return "post_boltodds_retirement"
    return "pre_current_provider"


def path_b_coverage_bucket(row: dict[str, Any]) -> str:
    real_split_count = _to_float(row.get("lineup_real_split_count"))
    split_source = str(row.get("lineup_split_source") or "").lower()
    mode = str(row.get("batter_handedness_mode") or "").lower()
    if (real_split_count is not None and real_split_count > 0) or split_source in {"real", "mixed"}:
        return "path_b_real_or_mixed"
    if mode == "path_b":
        return "path_b_no_real_splits"
    return "path_a_or_unknown"


def _tracked_win_loss(row: dict[str, Any]) -> bool:
    return _is_true(row.get("is_tracked_pick")) and row.get("result") in WIN_LOSS_RESULTS


def _nontracked_pass(row: dict[str, Any]) -> bool:
    return not _is_true(row.get("is_tracked_pick")) and _is_pass(row) and row.get("result") in WIN_LOSS_RESULTS


def _positive_edge_ev(row: dict[str, Any]) -> bool:
    edge = _edge(row)
    ev = _adj_ev(row)
    return edge is not None and edge > 0 and ev is not None and ev > 0


def _line_bucket(row: dict[str, Any]) -> str:
    return str(row.get("line_bucket") or "")


def _model_market(row: dict[str, Any]) -> str:
    return str(row.get("model_market_relationship") or "")


def _quality(row: dict[str, Any]) -> str:
    return str(row.get("quality_gate_level") or "").lower()


def _leash(row: dict[str, Any]) -> str:
    return str(row.get("leash_risk_bucket") or row.get("opportunity_bucket") or "").lower()


def candidate_definitions() -> tuple[CandidateDefinition, ...]:
    return (
        CandidateDefinition(
            name="keep_fire_market_agreed_moderate_ev",
            policy_lane="keep_fire",
            kind="runtime_selector",
            runtime_safe=True,
            recommendation="Keep FIRE only if it survives current-provider, side, price, CLV-proxy, and rolling-window slices.",
            rule=lambda row: _is_fire(row)
            and _model_market(row) == "model_agrees_with_favorite"
            and ev_bucket(row) == "ev_6_to_17"
            and str(row.get("bet_timing_window") or "") == "pre_30",
        ),
        CandidateDefinition(
            name="keep_fire_over_moderate_ev_normal_leash",
            policy_lane="keep_fire",
            kind="runtime_selector",
            runtime_safe=True,
            recommendation="Watch as a retained-FIRE profile; do not use it to reopen broad FIRE exposure.",
            rule=lambda row: _is_fire(row)
            and str(row.get("side") or "").lower() == "over"
            and ev_bucket(row) == "ev_6_to_17"
            and _leash(row) == "normal",
        ),
        CandidateDefinition(
            name="expand_lean_45_low_ev_normal_leash",
            policy_lane="expand_lean",
            kind="runtime_selector",
            runtime_safe=True,
            recommendation="Candidate for stronger-base LEAN betting only after provider-era and CLV-proxy survival.",
            rule=lambda row: _is_lean(row)
            and _line_bucket(row) == "4.5"
            and ev_bucket(row) == "ev_0_to_6"
            and _leash(row) == "normal",
        ),
        CandidateDefinition(
            name="expand_lean_low_k_standard_no_vig",
            policy_lane="expand_lean",
            kind="runtime_selector",
            runtime_safe=True,
            recommendation="Low-K-standard LEAN watch bucket; likely needs strict K-line and market-signal filters.",
            rule=lambda row: _is_lean(row)
            and str(row.get("pitcher_archetype_bucket") or "") == "low_k_standard"
            and no_vig_positive(row),
        ),
        CandidateDefinition(
            name="expand_lean_low_line_capped_model_fade",
            policy_lane="expand_lean",
            kind="runtime_selector",
            runtime_safe=True,
            recommendation="Odd but positive historical bucket; keep on watch until market-agreement and current-provider slices mature.",
            rule=lambda row: _is_lean(row)
            and _line_bucket(row) == "2.5-3.5"
            and _model_market(row) == "model_fades_favorite"
            and _quality(row) == "capped",
        ),
        CandidateDefinition(
            name="cap_high_raw_edge",
            policy_lane="cap_or_suppress",
            kind="drag_reducer",
            runtime_safe=True,
            recommendation="Treat high raw edge as suspicion, not automatic confidence.",
            rule=lambda row: edge_bucket(row) == "edge_6_plus",
        ),
        CandidateDefinition(
            name="cap_market_fade",
            policy_lane="cap_or_suppress",
            kind="drag_reducer",
            runtime_safe=True,
            recommendation="Keep market-fade caps active unless a narrow counter-slice earns a separate plan.",
            rule=lambda row: _model_market(row) == "model_fades_favorite",
        ),
        CandidateDefinition(
            name="cap_fire_under_market_fade",
            policy_lane="cap_or_suppress",
            kind="drag_reducer",
            runtime_safe=True,
            recommendation="Do not re-open FIRE under exposure without a separate re-entry proof.",
            rule=lambda row: _is_fire(row)
            and str(row.get("side") or "").lower() == "under"
            and _model_market(row) == "model_fades_favorite",
        ),
        CandidateDefinition(
            name="avoid_no_or_worse_price_clv_mass",
            policy_lane="cap_or_suppress",
            kind="process_drag",
            runtime_safe=False,
            recommendation="Use as validation target for pre-close/mainline-best-price proxies, not as a live final-CLV rule.",
            rule=lambda row: clv_bucket(row) in {"neutral_or_unknown", "worse_close_price", "worse_close_line"},
        ),
        CandidateDefinition(
            name="evidence_clv_supported",
            policy_lane="evidence_only",
            kind="process_anchor",
            runtime_safe=False,
            recommendation="Positive process anchor; convert into pre-close timing rules before considering live behavior.",
            rule=lambda row: clv_bucket(row) in {"beat_close_price", "beat_close_line"},
        ),
    )


def candidate_labels(row: dict[str, Any]) -> set[str]:
    if not _tracked_win_loss(row):
        return set()
    return {definition.name for definition in candidate_definitions() if definition.rule(row)}


def load_rows(path: Path = DEFAULT_INPUT) -> list[dict[str, Any]]:
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


def analysis_rows(rows: list[dict[str, Any]], *, start_date: str = CLEAN_WINDOW_START) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        slate_date = str(row.get("slate_date") or row.get("date") or "")
        if slate_date and slate_date < start_date:
            continue
        if row.get("result") not in WIN_LOSS_RESULTS:
            continue
        selected.append(row)
    return selected


def _empty_stats() -> dict[str, float | int]:
    return {
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "pnl": 0.0,
        "roi": 0.0,
        "fire_rows": 0,
        "lean_rows": 0,
        "beat_close_price_rows": 0,
        "beat_close_line_rows": 0,
    }


def _stats(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    stats = _empty_stats()
    for row in rows:
        stats["rows"] += 1
        if row.get("result") == "win":
            stats["wins"] += 1
        if row.get("result") == "loss":
            stats["losses"] += 1
        if _is_fire(row):
            stats["fire_rows"] += 1
        if _is_lean(row):
            stats["lean_rows"] += 1
        stats["pnl"] = round(float(stats["pnl"]) + _row_pnl(row), 3)
        if clv_bucket(row) == "beat_close_price":
            stats["beat_close_price_rows"] += 1
        if clv_bucket(row) == "beat_close_line":
            stats["beat_close_line_rows"] += 1
    if stats["rows"]:
        stats["roi"] = round(float(stats["pnl"]) / int(stats["rows"]), 4)
    return stats


def _group_stats(
    rows: list[dict[str, Any]],
    label_fn: Callable[[dict[str, Any]], str],
) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[label_fn(row)].append(row)
    return {label: _stats(group) for label, group in sorted(groups.items())}


def _recent_rows(rows: list[dict[str, Any]], *, slate_count: int = 14) -> list[dict[str, Any]]:
    dates = sorted({str(row.get("slate_date") or row.get("date") or "") for row in rows if row.get("slate_date") or row.get("date")})
    if not dates:
        return []
    keep = set(dates[-slate_count:])
    return [row for row in rows if str(row.get("slate_date") or row.get("date") or "") in keep]


def _slice_risks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for field, label_fn in MANDATORY_SLICE_FIELDS:
        grouped = _group_stats(rows, label_fn)
        for bucket, stats in grouped.items():
            if int(stats["rows"]) >= 10 and float(stats["pnl"]) < 0:
                risks.append({
                    "field": field,
                    "bucket": bucket,
                    **stats,
                })
    return sorted(risks, key=lambda item: (float(item["pnl"]), -int(item["rows"])))[:8]


def _readiness(definition: CandidateDefinition, rows: list[dict[str, Any]], risks: list[dict[str, Any]]) -> str:
    stats = _stats(rows)
    current_provider_stats = _stats([row for row in rows if provider_era(row) == "official_therundown_propline"])
    recent_stats = _stats(_recent_rows(rows))

    if definition.kind == "process_anchor":
        return "process_anchor"
    if definition.kind in {"drag_reducer", "process_drag"}:
        if int(stats["rows"]) >= 75 and float(stats["pnl"]) < 0:
            return "cap_or_suppress_watch"
        return "watch_more"
    if int(stats["rows"]) < 45:
        return "watch_more"
    if float(stats["pnl"]) <= 0:
        return "not_ready"
    if int(current_provider_stats["rows"]) < 25:
        return "watch_more"
    if int(recent_stats["rows"]) >= 10 and float(recent_stats["pnl"]) <= 0:
        return "watch_more"
    if risks:
        return "watch_more"
    return "ready_for_plan"


def _candidate_summary(definition: CandidateDefinition, rows: list[dict[str, Any]]) -> dict[str, Any]:
    matched = [row for row in rows if definition.rule(row)]
    risks = _slice_risks(matched)
    stats = _stats(matched)
    clv_rows = int(stats["beat_close_price_rows"]) + int(stats["beat_close_line_rows"])
    return {
        "name": definition.name,
        "policy_lane": definition.policy_lane,
        "kind": definition.kind,
        "runtime_safe": definition.runtime_safe,
        "recommendation": definition.recommendation,
        **stats,
        "clv_support_rate": round(clv_rows / int(stats["rows"]), 4) if int(stats["rows"]) else 0.0,
        "current_provider": _stats([row for row in matched if provider_era(row) == "official_therundown_propline"]),
        "post_boltodds": _stats([row for row in matched if provider_era(row) != "pre_current_provider"]),
        "recent": _stats(_recent_rows(matched)),
        "negative_slices": risks,
        "readiness": _readiness(definition, matched, risks),
    }


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = analysis_rows(rows)
    tracked = [row for row in selected if _tracked_win_loss(row)]
    nontracked_pass = [row for row in selected if _nontracked_pass(row)]
    positive_pass = [row for row in nontracked_pass if _positive_edge_ev(row)]
    candidates = {
        definition.name: _candidate_summary(definition, tracked)
        for definition in candidate_definitions()
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "analysis_rows": len(selected),
        "tracked": _stats(tracked),
        "verdict": _group_stats(tracked, lambda row: _verdict(row) or "unknown"),
        "side": _group_stats(tracked, lambda row: str(row.get("side") or "unknown").lower()),
        "edge": _group_stats(tracked, edge_bucket),
        "ev": _group_stats(tracked, ev_bucket),
        "model_market": _group_stats(tracked, lambda row: str(row.get("model_market_relationship") or "unknown")),
        "clv": {
            "beat_close_price": _stats([row for row in tracked if clv_bucket(row) == "beat_close_price"]),
            "beat_close_line": _stats([row for row in tracked if clv_bucket(row) == "beat_close_line"]),
            "no_or_worse_price_clv": _stats([row for row in tracked if clv_bucket(row) not in {"beat_close_price", "beat_close_line"}]),
        },
        "pass_expansion": {
            "all_nontracked_pass": _stats(nontracked_pass),
            "positive_edge_ev": _stats(positive_pass),
        },
        "candidates": candidates,
    }


def _format_roi(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:+.1%}"


def _format_stats(stats: dict[str, Any]) -> str:
    return (
        f"{stats.get('rows', 0)} "
        f"({stats.get('wins', 0)}-{stats.get('losses', 0)}), "
        f"{float(stats.get('pnl', 0.0)):+.2f}u, "
        f"{_format_roi(stats.get('roi'))}"
    )


def _render_candidate_table(lines: list[str], candidates: dict[str, dict[str, Any]]) -> None:
    lines.append("## Candidate Policy Draft")
    lines.append("")
    lines.append("| Candidate | Lane | Runtime-safe | Result | Current provider | Recent | CLV support | Readiness |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | --- |")
    ordered = sorted(
        candidates.values(),
        key=lambda item: (
            item["policy_lane"],
            {"ready_for_plan": 0, "watch_more": 1, "cap_or_suppress_watch": 2, "process_anchor": 3, "not_ready": 4}.get(str(item["readiness"]), 9),
            -abs(float(item["pnl"])),
        ),
    )
    for item in ordered:
        lines.append(
            f"| `{item['name']}` | `{item['policy_lane']}` | {item['runtime_safe']} | "
            f"{_format_stats(item)} | {_format_stats(item['current_provider'])} | "
            f"{_format_stats(item['recent'])} | {item['clv_support_rate']:.1%} | `{item['readiness']}` |"
        )
    lines.append("")


def _render_drag_table(lines: list[str], summary: dict[str, Any]) -> None:
    lines.append("## Positive CLV vs Mass Losses")
    lines.append("")
    lines.append("| Bucket | Result |")
    lines.append("| --- | ---: |")
    lines.append(f"| All tracked | {_format_stats(summary['tracked'])} |")
    for label, stats in summary.get("clv", {}).items():
        lines.append(f"| `{label}` | {_format_stats(stats)} |")
    for label, stats in summary.get("edge", {}).items():
        if label == "edge_6_plus":
            lines.append(f"| `{label}` | {_format_stats(stats)} |")
    for label, stats in summary.get("model_market", {}).items():
        if label == "model_fades_favorite":
            lines.append(f"| `{label}` | {_format_stats(stats)} |")
    lines.append("")


def _render_slice_risks(lines: list[str], candidates: dict[str, dict[str, Any]]) -> None:
    lines.append("## Slice Risks")
    lines.append("")
    lines.append("| Candidate | Negative mandatory slices |")
    lines.append("| --- | --- |")
    for item in candidates.values():
        risks = item.get("negative_slices") or []
        if not risks:
            lines.append(f"| `{item['name']}` | none above the 10-row threshold |")
            continue
        rendered = "; ".join(
            f"{risk['field']}={risk['bucket']} ({_format_stats(risk)})"
            for risk in risks[:4]
        )
        lines.append(f"| `{item['name']}` | {rendered} |")
    lines.append("")


def render_report(summary: dict[str, Any]) -> str:
    pass_positive = summary["pass_expansion"]["positive_edge_ev"]
    lines = [
        "# Strong Base Decision Lab",
        "",
        f"Generated at: `{summary.get('generated_at', 'unknown')}`",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.",
        "",
        "## Executive Read",
        "",
        f"- Total source rows: `{summary.get('total_rows', 0)}`; clean analyzed rows: `{summary.get('analysis_rows', 0)}`.",
        f"- Tracked post-bump portfolio: `{_format_stats(summary['tracked'])}`.",
        "- Working answer: positive CLV is real process evidence, but broad pick volume is still losing; the lab should preserve price/timing-confirmed contexts and cut high-edge, market-faded, CLV-neutral mass.",
        f"- Nontracked PASS expansion check: `{_format_stats(pass_positive)}` positive-edge/EV PASS sides. Generic PASS expansion stays closed.",
        "- Readiness rule: a runtime candidate is not plan-ready unless it has enough rows, positive PnL, current-provider support, positive recent form, and no meaningful negative mandatory slice.",
        "",
    ]
    _render_drag_table(lines, summary)
    _render_candidate_table(lines, summary.get("candidates", {}))
    _render_slice_risks(lines, summary.get("candidates", {}))
    lines.extend([
        "## Next Gate",
        "",
        "- Draft a separate promotion plan only for candidates marked `ready_for_plan`; everything else stays watch-only or process-anchor evidence.",
        "- For `process_anchor` CLV rows, use mainline-best-price and pre-close proxy evidence before converting the signal into a live rule.",
        "- Keep model math, thresholds, staking, provider order, notification classes, locks, retention, and dashboard source-of-truth unchanged until Tyler approves a separate implementation plan.",
        "",
    ])
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    rows = load_rows(args.input)
    report = render_report(build_summary(rows))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output} ({len(rows)} source rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
