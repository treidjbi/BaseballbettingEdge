"""Read-only portfolio simulator for Strong Base decision policies.

This diagnostic compares current staking, strict FIRE retention, selective
LEAN expansion, and price-confirmed hindsight ceilings. It does not change live
lambda, verdicts, thresholds, staking, provider order, notifications, locks,
retention, calibration, dashboard artifacts, or source-of-truth behavior.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import strong_base_decision_lab as strong_base


DEFAULT_INPUT = strong_base.DEFAULT_INPUT
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "strong_base_portfolio_simulator.md"


@dataclass(frozen=True)
class PortfolioPolicy:
    name: str
    description: str
    runtime_safe: bool
    uses_hindsight: bool
    stake_mode: str
    selector: Callable[[dict[str, Any]], bool]
    stake_fn: Callable[[dict[str, Any]], float]


def _verdict_units(row: dict[str, Any]) -> float:
    verdict = strong_base._verdict(row)
    if verdict == "FIRE 2u":
        return 2.0
    if verdict == "FIRE 1u":
        return 1.0
    return 0.0


def _flat_unit(row: dict[str, Any]) -> float:
    return 1.0


def _tracked_win_loss(row: dict[str, Any]) -> bool:
    return strong_base._tracked_win_loss(row)


def _nontracked_positive_pass(row: dict[str, Any]) -> bool:
    return strong_base._nontracked_pass(row) and strong_base._positive_edge_ev(row)


def _labels(row: dict[str, Any]) -> set[str]:
    return strong_base.candidate_labels(row)


def _has_lane(row: dict[str, Any], lane: str) -> bool:
    definitions = {definition.name: definition for definition in strong_base.candidate_definitions()}
    return any(definitions[label].policy_lane == lane for label in _labels(row) if label in definitions)


def _has_any(row: dict[str, Any], labels: set[str]) -> bool:
    return bool(_labels(row) & labels)


def _strict_fire_core(row: dict[str, Any]) -> bool:
    drag_labels = {"cap_high_raw_edge", "cap_market_fade", "cap_fire_under_market_fade"}
    return _tracked_win_loss(row) and _has_lane(row, "keep_fire") and not _has_any(row, drag_labels)


def _selective_lean_candidate(row: dict[str, Any]) -> bool:
    drag_labels = {"cap_high_raw_edge", "cap_fire_under_market_fade"}
    return _tracked_win_loss(row) and _has_lane(row, "expand_lean") and not _has_any(row, drag_labels)


def _drag_suppressed_tracked(row: dict[str, Any]) -> bool:
    drag_labels = {"cap_high_raw_edge", "cap_market_fade", "cap_fire_under_market_fade"}
    return _tracked_win_loss(row) and not _has_any(row, drag_labels)


def portfolio_policies() -> tuple[PortfolioPolicy, ...]:
    return (
        PortfolioPolicy(
            name="current_staked_fire",
            description="Current staked FIRE exposure: FIRE 1u risks 1u, FIRE 2u risks 2u, LEAN risks 0u.",
            runtime_safe=True,
            uses_hindsight=False,
            stake_mode="verdict_units",
            selector=lambda row: _tracked_win_loss(row) and strong_base._is_fire(row),
            stake_fn=_verdict_units,
        ),
        PortfolioPolicy(
            name="current_tracked_flat",
            description="Flat 1u quality read on every tracked non-PASS pick, including LEAN rows.",
            runtime_safe=True,
            uses_hindsight=False,
            stake_mode="flat_1u",
            selector=_tracked_win_loss,
            stake_fn=_flat_unit,
        ),
        PortfolioPolicy(
            name="drag_suppressed_tracked_flat",
            description="Flat 1u tracked portfolio after suppressing high-edge, market-fade, and FIRE-under-fade drag rows.",
            runtime_safe=True,
            uses_hindsight=False,
            stake_mode="flat_1u",
            selector=_drag_suppressed_tracked,
            stake_fn=_flat_unit,
        ),
        PortfolioPolicy(
            name="strict_runtime_core_flat",
            description="Flat 1u retained FIRE core: keep-FIRE candidates only, with high-edge and market-fade drag caps removed.",
            runtime_safe=True,
            uses_hindsight=False,
            stake_mode="flat_1u",
            selector=_strict_fire_core,
            stake_fn=_flat_unit,
        ),
        PortfolioPolicy(
            name="strict_plus_selective_lean_flat",
            description="Flat 1u strict retained FIRE core plus selective LEAN candidate expansion buckets.",
            runtime_safe=True,
            uses_hindsight=False,
            stake_mode="flat_1u",
            selector=lambda row: _strict_fire_core(row) or _selective_lean_candidate(row),
            stake_fn=_flat_unit,
        ),
        PortfolioPolicy(
            name="positive_edge_pass_expansion_flat",
            description="Flat 1u check on nontracked PASS sides with positive edge and EV. This tests broad extra-volume temptation.",
            runtime_safe=True,
            uses_hindsight=False,
            stake_mode="flat_1u",
            selector=_nontracked_positive_pass,
            stake_fn=_flat_unit,
        ),
        PortfolioPolicy(
            name="price_confirmed_hindsight_ceiling",
            description="Flat 1u ceiling on tracked rows that beat closing price or line. This is process evidence, not a live rule.",
            runtime_safe=False,
            uses_hindsight=True,
            stake_mode="flat_1u",
            selector=lambda row: _tracked_win_loss(row) and "evidence_clv_supported" in _labels(row),
            stake_fn=_flat_unit,
        ),
    )


def _empty_stats(policy: PortfolioPolicy | None = None) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "units": 0.0,
        "pnl": 0.0,
        "roi": 0.0,
        "fire_rows": 0,
        "lean_rows": 0,
    }
    if policy is not None:
        stats.update({
            "name": policy.name,
            "description": policy.description,
            "runtime_safe": policy.runtime_safe,
            "uses_hindsight": policy.uses_hindsight,
            "stake_mode": policy.stake_mode,
        })
    return stats


def _policy_rows(rows: list[dict[str, Any]], policy: PortfolioPolicy) -> list[tuple[dict[str, Any], float]]:
    selected: list[tuple[dict[str, Any], float]] = []
    for row in rows:
        if not policy.selector(row):
            continue
        units = policy.stake_fn(row)
        if units <= 0:
            continue
        selected.append((row, units))
    return selected


def _stats_from_weighted_rows(
    weighted_rows: list[tuple[dict[str, Any], float]],
    policy: PortfolioPolicy | None = None,
) -> dict[str, Any]:
    stats = _empty_stats(policy)
    for row, units in weighted_rows:
        stats["rows"] += 1
        if row.get("result") == "win":
            stats["wins"] += 1
        if row.get("result") == "loss":
            stats["losses"] += 1
        if strong_base._is_fire(row):
            stats["fire_rows"] += 1
        if strong_base._is_lean(row):
            stats["lean_rows"] += 1
        stats["units"] = round(float(stats["units"]) + units, 3)
        stats["pnl"] = round(float(stats["pnl"]) + strong_base._row_pnl(row) * units, 3)
    if stats["units"]:
        stats["roi"] = round(float(stats["pnl"]) / float(stats["units"]), 4)
    return stats


def _recent_weighted_rows(weighted_rows: list[tuple[dict[str, Any], float]], *, slate_count: int = 14) -> list[tuple[dict[str, Any], float]]:
    dates = sorted({str(row.get("slate_date") or row.get("date") or "") for row, _ in weighted_rows if row.get("slate_date") or row.get("date")})
    if not dates:
        return []
    keep = set(dates[-slate_count:])
    return [(row, units) for row, units in weighted_rows if str(row.get("slate_date") or row.get("date") or "") in keep]


def _slice_risks(weighted_rows: list[tuple[dict[str, Any], float]]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for field, label_fn in strong_base.MANDATORY_SLICE_FIELDS:
        buckets: dict[str, list[tuple[dict[str, Any], float]]] = {}
        for row, units in weighted_rows:
            buckets.setdefault(label_fn(row), []).append((row, units))
        for bucket, bucket_rows in buckets.items():
            stats = _stats_from_weighted_rows(bucket_rows)
            if int(stats["rows"]) >= 10 and float(stats["pnl"]) < 0:
                risks.append({"field": field, "bucket": bucket, **stats})
    return sorted(risks, key=lambda item: (float(item["pnl"]), -int(item["rows"])))[:8]


def _readiness(policy: PortfolioPolicy, stats: dict[str, Any], recent: dict[str, Any], current_provider: dict[str, Any], risks: list[dict[str, Any]]) -> str:
    if policy.name.startswith("current_"):
        return "baseline"
    if policy.uses_hindsight:
        return "hindsight_ceiling"
    if int(stats["rows"]) < 45:
        return "watch_more"
    if float(stats["pnl"]) <= 0:
        return "not_ready"
    if int(current_provider["rows"]) < 25:
        return "watch_more"
    if int(recent["rows"]) >= 10 and float(recent["pnl"]) <= 0:
        return "watch_more"
    if risks:
        return "watch_more"
    return "promotion_plan_candidate"


def _policy_summary(rows: list[dict[str, Any]], policy: PortfolioPolicy) -> dict[str, Any]:
    weighted_rows = _policy_rows(rows, policy)
    stats = _stats_from_weighted_rows(weighted_rows, policy)
    recent = _stats_from_weighted_rows(_recent_weighted_rows(weighted_rows))
    current_provider = _stats_from_weighted_rows([
        (row, units)
        for row, units in weighted_rows
        if strong_base.provider_era(row) == "official_therundown_propline"
    ])
    risks = _slice_risks(weighted_rows)
    stats["recent"] = recent
    stats["current_provider"] = current_provider
    stats["negative_slices"] = risks
    stats["readiness"] = _readiness(policy, stats, recent, current_provider, risks)
    return stats


def build_portfolio_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = strong_base.analysis_rows(rows)
    policies = {
        policy.name: _policy_summary(selected, policy)
        for policy in portfolio_policies()
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "analysis_rows": len(selected),
        "policies": policies,
    }


def _format_roi(value: Any) -> str:
    number = strong_base._to_float(value)
    if number is None:
        return "--"
    return f"{number:+.1%}"


def _format_stats(stats: dict[str, Any]) -> str:
    return (
        f"{stats.get('rows', 0)} "
        f"({stats.get('wins', 0)}-{stats.get('losses', 0)}), "
        f"{float(stats.get('pnl', 0.0)):+.2f}u / "
        f"{float(stats.get('units', 0.0)):.1f}u risked, "
        f"{_format_roi(stats.get('roi'))}"
    )


def _render_policy_table(lines: list[str], policies: dict[str, dict[str, Any]]) -> None:
    lines.append("## Policy Comparison")
    lines.append("")
    lines.append("| Policy | Mode | Result | Current provider | Recent | Hindsight | Readiness |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- | --- |")
    ordered_names = [
        "current_staked_fire",
        "current_tracked_flat",
        "drag_suppressed_tracked_flat",
        "strict_runtime_core_flat",
        "strict_plus_selective_lean_flat",
        "positive_edge_pass_expansion_flat",
        "price_confirmed_hindsight_ceiling",
    ]
    for name in ordered_names:
        item = policies[name]
        lines.append(
            f"| `{name}` | `{item['stake_mode']}` | {_format_stats(item)} | "
            f"{_format_stats(item['current_provider'])} | {_format_stats(item['recent'])} | "
            f"{item['uses_hindsight']} | `{item['readiness']}` |"
        )
    lines.append("")


def _render_slice_risks(lines: list[str], policies: dict[str, dict[str, Any]]) -> None:
    lines.append("## Policy Slice Risks")
    lines.append("")
    lines.append("| Policy | Negative mandatory slices |")
    lines.append("| --- | --- |")
    for name, item in policies.items():
        if name.startswith("current_"):
            continue
        risks = item.get("negative_slices") or []
        if not risks:
            lines.append(f"| `{name}` | none above the 10-row threshold |")
            continue
        rendered = "; ".join(
            f"{risk['field']}={risk['bucket']} ({_format_stats(risk)})"
            for risk in risks[:4]
        )
        lines.append(f"| `{name}` | {rendered} |")
    lines.append("")


def render_report(summary: dict[str, Any]) -> str:
    policies = summary["policies"]
    strict = policies["strict_runtime_core_flat"]
    expansion = policies["strict_plus_selective_lean_flat"]
    current_fire = policies["current_staked_fire"]
    price_ceiling = policies["price_confirmed_hindsight_ceiling"]
    pass_check = policies["positive_edge_pass_expansion_flat"]
    lines = [
        "# Strong Base Portfolio Simulator",
        "",
        f"Generated at: `{summary.get('generated_at', 'unknown')}`",
        "",
        "read-only: No live behavior changes. This simulator does not change model math, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.",
        "",
        "## Executive Read",
        "",
        f"- Current staked FIRE baseline: `{_format_stats(current_fire)}`.",
        f"- Strict runtime core: `{_format_stats(strict)}`. This is the cleanest no-hindsight retained-FIRE policy shape.",
        f"- Strict plus selective LEAN expansion: `{_format_stats(expansion)}`. Treat as a watch policy unless current-provider and recent slices survive.",
        f"- Positive-edge PASS expansion check: `{_format_stats(pass_check)}`. Broad extra PASS volume remains closed if this is weak.",
        f"- Price-confirmed hindsight ceiling: `{_format_stats(price_ceiling)}`. This is the process target, not a live selector.",
        "",
    ]
    _render_policy_table(lines, policies)
    _render_slice_risks(lines, policies)
    lines.extend([
        "## Next Decision",
        "",
        "- Draft a live promotion plan only for a runtime-safe policy marked `promotion_plan_candidate`.",
        "- If every runtime-safe policy is `watch_more` or `not_ready`, keep current live caps and continue collecting mainline-best-price evidence.",
        "- Never promote the `price_confirmed_hindsight_ceiling` directly; convert it into pre-close or best-main-line price rules first.",
        "",
    ])
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    rows = strong_base.load_rows(args.input)
    report = render_report(build_portfolio_summary(rows))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output} ({len(rows)} source rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
