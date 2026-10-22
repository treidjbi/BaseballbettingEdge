"""Read-only synthesis of active shadow bet-selection signals.

This diagnostic combines market-anchor selector metadata, Strong Base policy
labels, pre-close proxy labels, and optional market-agreement tracker exports.
It does not change live lambda, verdicts, thresholds, staking, provider order,
notifications, locks, retention, calibration, dashboard artifacts, or
source-of-truth behavior.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import gate_f_preclose_clv_proxy_lab as preclose_proxy
from analytics.diagnostics import strong_base_decision_lab as strong_base
from pipeline.name_utils import normalize


DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "shadow_signal_synthesis_lab.md"
CURRENT_PROVIDER_START = "2026-06-24"
WIN_LOSS_RESULTS = {"win", "loss"}


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


def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "pnl", "theoretical_pnl"):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def _slate_date(row: dict[str, Any]) -> str:
    return str(row.get("slate_date") or row.get("date") or "")[:10]


def _normalized_pitcher(row: dict[str, Any]) -> str:
    return str(
        row.get("normalized_pitcher")
        or row.get("normalized_player_name")
        or normalize(row.get("pitcher") or row.get("player_name") or "")
    ).strip()


def _pick_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _slate_date(row),
        _normalized_pitcher(row),
        str(row.get("side") or "").strip().lower(),
    )


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


def _tracked_win_loss(row: dict[str, Any]) -> bool:
    return _is_true(row.get("is_tracked_pick")) and row.get("result") in WIN_LOSS_RESULTS


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


def _market_anchor_selector(row: dict[str, Any]) -> dict[str, Any]:
    return _json_object(row.get("market_anchor_selector"))


def _market_anchor_labels(row: dict[str, Any]) -> set[str]:
    raw = _market_anchor_selector(row).get("labels") or row.get("market_anchor_selector_labels") or []
    if isinstance(raw, str):
        raw = [raw]
    return {str(label) for label in raw if str(label or "").strip()}


def _market_anchor_core(row: dict[str, Any]) -> bool:
    return "market_anchor_core" in _market_anchor_labels(row)


def _market_anchor_strict(row: dict[str, Any]) -> bool:
    return "market_anchor_strict" in _market_anchor_labels(row)


def _candidate_labels(row: dict[str, Any]) -> set[str]:
    return strong_base.candidate_labels(row)


def _has_lane(row: dict[str, Any], lane: str) -> bool:
    definitions = {definition.name: definition for definition in strong_base.candidate_definitions()}
    return any(definitions[label].policy_lane == lane for label in _candidate_labels(row) if label in definitions)


def _has_any(row: dict[str, Any], labels: set[str]) -> bool:
    return bool(_candidate_labels(row) & labels)


DRAG_LABELS = {"cap_high_raw_edge", "cap_market_fade", "cap_fire_under_market_fade"}


def _drag_core(row: dict[str, Any]) -> bool:
    return _has_any(row, DRAG_LABELS)


def _strong_base_keep_fire(row: dict[str, Any]) -> bool:
    return _has_lane(row, "keep_fire")


def _strong_base_expand_lean(row: dict[str, Any]) -> bool:
    return _has_lane(row, "expand_lean")


def _strong_base_strict_runtime_core(row: dict[str, Any]) -> bool:
    return _is_fire(row) and _strong_base_keep_fire(row) and not _drag_core(row)


def _selective_lean_candidate(row: dict[str, Any]) -> bool:
    return (
        _is_lean(row)
        and _strong_base_expand_lean(row)
        and not _has_any(row, {"cap_high_raw_edge", "cap_fire_under_market_fade"})
    )


def _strong_base_strict_plus_selective(row: dict[str, Any]) -> bool:
    return _strong_base_strict_runtime_core(row) or _selective_lean_candidate(row)


def _preclose_strong(row: dict[str, Any]) -> bool:
    return preclose_proxy.preclose_clv_proxy_label(row) == "strong_preclose_clv_proxy"


def _current_provider(row: dict[str, Any]) -> bool:
    return _slate_date(row) >= CURRENT_PROVIDER_START


def _recent_rows(rows: list[dict[str, Any]], *, slate_count: int = 14) -> list[dict[str, Any]]:
    dates = sorted({_slate_date(row) for row in rows if _slate_date(row)})
    if not dates:
        return []
    keep = set(dates[-slate_count:])
    return [row for row in rows if _slate_date(row) in keep]


def _score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    score = {
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "pnl": 0.0,
        "roi": 0.0,
        "fire_rows": 0,
        "lean_rows": 0,
    }
    for row in rows:
        if row.get("result") not in WIN_LOSS_RESULTS:
            continue
        score["rows"] += 1
        if row.get("result") == "win":
            score["wins"] += 1
        else:
            score["losses"] += 1
        if _is_fire(row):
            score["fire_rows"] += 1
        if _is_lean(row):
            score["lean_rows"] += 1
        score["pnl"] = round(float(score["pnl"]) + _row_pnl(row), 3)
    if score["rows"]:
        score["roi"] = round(float(score["pnl"]) / int(score["rows"]), 4)
    return score


def _summary_score(rows: list[dict[str, Any]], selector: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    selected = [row for row in rows if selector(row)]
    score = _score(selected)
    score["current_provider"] = _score([row for row in selected if _current_provider(row)])
    score["recent"] = _score(_recent_rows(selected))
    return score


def _agreement_signal(rows: list[dict[str, Any]]) -> str:
    labels = {str(row.get("movement_agreement_label") or "").strip() for row in rows}
    labels.discard("")
    has_with = "market_with_model" in labels
    has_against = "market_against_model" in labels
    has_mixed = "market_mixed" in labels
    if has_mixed or (has_with and has_against):
        return "market_mixed_or_conflicting"
    if has_with:
        return "market_with_model"
    if has_against:
        return "market_against_model"
    return "market_no_signal"


def _agreement_strength(rows: list[dict[str, Any]]) -> str:
    strengths = {str(row.get("movement_strength_label") or "").strip() for row in rows}
    if "broad_with_model" in strengths:
        return "broad_with_model"
    if "broad_against_model" in strengths:
        return "broad_against_model"
    if "mixed_or_reversed" in strengths:
        return "mixed_or_reversed"
    if "single_book_with_model" in strengths:
        return "single_book_with_model"
    if "single_book_against_model" in strengths:
        return "single_book_against_model"
    return "no_movement_signal"


def _agreement_magnitude(rows: list[dict[str, Any]]) -> str:
    magnitudes = {str(row.get("movement_magnitude_bucket") or "").strip() for row in rows}
    if "line_half_plus" in magnitudes:
        return "line_half_plus"
    if "odds_20c_plus" in magnitudes:
        return "odds_20c_plus"
    if "odds_10_19c" in magnitudes:
        return "odds_10_19c"
    return "small_or_none"


def overlay_market_agreement(
    rows: list[dict[str, Any]],
    market_agreement_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in market_agreement_rows:
        by_key[_pick_key(row)].append(row)

    enriched: list[dict[str, Any]] = []
    for row in rows:
        matches = by_key.get(_pick_key(row), [])
        if not matches:
            enriched.append({
                **row,
                "market_agreement_signal": "missing",
                "market_agreement_strength": "missing",
                "market_agreement_magnitude": "missing",
            })
            continue
        enriched.append({
            **row,
            "market_agreement_signal": _agreement_signal(matches),
            "market_agreement_strength": _agreement_strength(matches),
            "market_agreement_magnitude": _agreement_magnitude(matches),
        })
    return enriched


def _market_agreement_summary(enriched_rows: list[dict[str, Any]], raw_rows: list[dict[str, Any]]) -> dict[str, Any]:
    covered = [row for row in enriched_rows if row.get("market_agreement_signal") != "missing"]
    return {
        "rows": len(raw_rows),
        "covered_picks": len(covered),
        "graded_rows": len(covered),
        "signal_counts": dict(sorted({
            signal: sum(1 for row in covered if row.get("market_agreement_signal") == signal)
            for signal in {row.get("market_agreement_signal") for row in covered}
        }.items())),
    }


def _individual_signals() -> dict[str, Callable[[dict[str, Any]], bool]]:
    return {
        "current_fire_only": _is_fire,
        "market_anchor_core_all": _market_anchor_core,
        "market_anchor_strict_all": _market_anchor_strict,
        "market_anchor_strict_fire": lambda row: _market_anchor_strict(row) and _is_fire(row),
        "market_anchor_non_strict_fire": lambda row: bool(_market_anchor_selector(row))
        and _is_fire(row)
        and not _market_anchor_strict(row),
        "strong_base_keep_fire_lane": _strong_base_keep_fire,
        "strong_base_expand_lean_lane": _strong_base_expand_lean,
        "strong_base_strict_runtime_core": _strong_base_strict_runtime_core,
        "strong_base_strict_plus_selective": _strong_base_strict_plus_selective,
        "drag_suppressed_tracked": lambda row: not _drag_core(row),
        "preclose_strong_proxy": _preclose_strong,
        "market_agreement_with_model": lambda row: row.get("market_agreement_signal") == "market_with_model",
        "market_agreement_against_model": lambda row: row.get("market_agreement_signal") == "market_against_model",
    }


def _composite_policies() -> dict[str, Callable[[dict[str, Any]], bool]]:
    return {
        "baseline_current_fire_flat": _is_fire,
        "cap_drag_only_keep_remaining_fire": lambda row: _is_fire(row) and not _drag_core(row),
        "keep_fire_if_strong_base_or_market_anchor_strict": lambda row: _is_fire(row)
        and (_strong_base_strict_runtime_core(row) or _market_anchor_strict(row)),
        "keep_fire_if_strong_base_and_market_anchor_strict": lambda row: _is_fire(row)
        and _strong_base_strict_runtime_core(row)
        and _market_anchor_strict(row),
        "strict_runtime_core_plus_selective_lean": _strong_base_strict_plus_selective,
        "strict_runtime_core_plus_selective_lean_and_ma_core": lambda row: _strong_base_strict_plus_selective(row)
        and _market_anchor_core(row),
        "strict_runtime_core_plus_selective_lean_and_preclose_strong": lambda row: _strong_base_strict_plus_selective(row)
        and _preclose_strong(row),
        "combined_runtime_broad_no_hindsight": lambda row: _strong_base_strict_plus_selective(row)
        or _market_anchor_strict(row),
        "combined_runtime_broad_no_hindsight_no_drag": lambda row: (
            _strong_base_strict_plus_selective(row) or _market_anchor_strict(row)
        )
        and not _drag_core(row),
        "combined_positive_runtime_watch": lambda row: (
            _is_fire(row)
            and (_strong_base_strict_runtime_core(row) or _market_anchor_strict(row))
            and not _drag_core(row)
            and str(row.get("price_bucket")) != "-100 to -129"
            and str(row.get("line_bucket")) not in {"4.5", "6.5"}
        )
        or (
            _is_lean(row)
            and _selective_lean_candidate(row)
            and (_market_anchor_core(row) or _preclose_strong(row))
        ),
    }


def _slice_bucket(row: dict[str, Any], field: str) -> str:
    if field == "provider_era":
        return strong_base.provider_era(row)
    if field == "clv":
        return strong_base.clv_bucket(row)
    if field == "path_b":
        return strong_base.path_b_coverage_bucket(row)
    if field == "preclose_proxy":
        return preclose_proxy.preclose_clv_proxy_label(row)
    if field == "market_agreement":
        return str(row.get("market_agreement_signal") or "missing")
    if field == "market_anchor":
        if _market_anchor_strict(row):
            return "market_anchor_strict"
        if _market_anchor_core(row):
            return "market_anchor_core"
        return "no_market_anchor"
    return str(row.get(field) if row.get(field) not in (None, "") else "missing")


def _negative_slices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for field in (
        "side",
        "line_bucket",
        "price_bucket",
        "clv",
        "provider_era",
        "path_b",
        "model_market_relationship",
        "quality_gate_level",
        "market_agreement",
        "market_anchor",
        "preclose_proxy",
    ):
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            buckets[_slice_bucket(row, field)].append(row)
        for bucket, bucket_rows in buckets.items():
            stats = _score(bucket_rows)
            if stats["rows"] >= 10 and stats["pnl"] < 0:
                risks.append({"field": field, "bucket": bucket, **stats})
    return sorted(risks, key=lambda risk: (risk["pnl"], -risk["rows"]))[:8]


def build_summary(
    rows: list[dict[str, Any]],
    *,
    market_agreement_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    tracked = [row for row in rows if _tracked_win_loss(row)]
    enriched = overlay_market_agreement(tracked, market_agreement_rows or [])
    individual = {
        name: _summary_score(enriched, selector)
        for name, selector in _individual_signals().items()
    }
    composites = {
        name: _summary_score(enriched, selector)
        for name, selector in _composite_policies().items()
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_source_rows": len(rows),
        "tracked_rows": len(tracked),
        "tracked": _score(enriched),
        "market_agreement": _market_agreement_summary(enriched, market_agreement_rows or []),
        "individual_signals": individual,
        "composite_policies": composites,
        "negative_slices": {
            name: _negative_slices([row for row in enriched if selector(row)])
            for name, selector in _composite_policies().items()
        },
    }


def _format_roi(value: Any) -> str:
    number = _to_float(value)
    return "--" if number is None else f"{number:+.1%}"


def _format_stats(stats: dict[str, Any]) -> str:
    return (
        f"{stats.get('rows', 0)} ({stats.get('wins', 0)}-{stats.get('losses', 0)}), "
        f"{float(stats.get('pnl', 0.0)):+.2f}u, {_format_roi(stats.get('roi'))}"
    )


def _render_score_table(lines: list[str], title: str, rows: dict[str, dict[str, Any]]) -> None:
    lines.extend([f"## {title}", ""])
    lines.append("| Signal | Result | Current provider | Recent | FIRE | LEAN |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for name, stats in rows.items():
        lines.append(
            f"| `{name}` | {_format_stats(stats)} | {_format_stats(stats['current_provider'])} | "
            f"{_format_stats(stats['recent'])} | {stats['fire_rows']} | {stats['lean_rows']} |"
        )
    lines.append("")


def _render_unit_accumulation_candidate(lines: list[str], summary: dict[str, Any]) -> None:
    candidate_name = "strict_runtime_core_plus_selective_lean"
    candidate = summary["composite_policies"][candidate_name]
    lines.extend(
        [
            "## Unit Accumulation Candidate",
            "",
            f"- Preferred aggressive candidate: `{candidate_name}`.",
            f"- Full clean-window record: `{_format_stats(candidate)}`.",
            f"- Current-provider slice: `{_format_stats(candidate['current_provider'])}`.",
            f"- Recent slice: `{_format_stats(candidate['recent'])}`.",
            f"- Mix: `{candidate['fire_rows']}` retained FIRE rows and `{candidate['lean_rows']}` selective LEAN rows.",
            "- Selection rule: primary lens is total units and seasonal volume; ROI is a guardrail for downside, not the only ranking criterion.",
            "- Canary posture: track the full aggressive candidate first, then mark weak pre-close, worse-close-price, plus-price, market-agreement-against, side, K-line, quality, Path B, and provider-era slices as review flags.",
            "",
        ]
    )


def _render_risks(lines: list[str], summary: dict[str, Any]) -> None:
    lines.extend(["## Composite Slice Risks", ""])
    for name in (
        "combined_runtime_broad_no_hindsight",
        "combined_runtime_broad_no_hindsight_no_drag",
        "combined_positive_runtime_watch",
        "strict_runtime_core_plus_selective_lean",
    ):
        risks = summary["negative_slices"].get(name) or []
        if not risks:
            lines.append(f"- `{name}`: no negative mandatory slices above the 10-row floor.")
            continue
        rendered = "; ".join(
            f"{risk['field']}={risk['bucket']} ({_format_stats(risk)})" for risk in risks[:4]
        )
        lines.append(f"- `{name}`: {rendered}.")
    lines.append("")


def render_report(summary: dict[str, Any]) -> str:
    market = summary["market_agreement"]
    lines = [
        "# Shadow Signal Synthesis Lab",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.",
        "",
        "## Executive Read",
        "",
        f"- Source rows: `{summary['total_source_rows']}`; tracked graded rows: `{summary['tracked_rows']}`.",
        f"- Current tracked baseline: `{_format_stats(summary['tracked'])}`.",
        f"- Best broad no-hindsight composite: `combined_runtime_broad_no_hindsight_no_drag` at `{_format_stats(summary['composite_policies']['combined_runtime_broad_no_hindsight_no_drag'])}`.",
        f"- Higher-conviction watch composite: `combined_positive_runtime_watch` at `{_format_stats(summary['composite_policies']['combined_positive_runtime_watch'])}`.",
        "- Read rule: treat this as a policy-shape scout. A live canary still needs a separate Tyler approval, feature flag, rollback, and slice review.",
        "",
    ]
    _render_unit_accumulation_candidate(lines, summary)
    lines.extend([
        "## Market Agreement Input",
        "",
        f"- Raw market-agreement rows: `{market['rows']}`.",
        f"- Tracked picks with market-agreement coverage: `{market['covered_picks']}`.",
        f"- Graded covered picks: `{market['graded_rows']}`.",
        f"- Signal counts: `{json.dumps(market['signal_counts'], sort_keys=True)}`.",
        "",
    ])
    _render_score_table(lines, "Individual Signal Scoreboard", summary["individual_signals"])
    _render_score_table(lines, "Composite Policy Shapes", summary["composite_policies"])
    _render_risks(lines, summary)
    lines.extend(
        [
            "## Next Gate",
            "",
            "- Do not promote a model, threshold, staking, provider, notification, lock, retention, or source-of-truth change from this report.",
            "- Use this report to choose the smallest separate canary plan: likely retained FIRE plus selective LEAN review, with explicit drag suppression and market-agreement checks.",
            "",
        ]
    )
    return "\n".join(lines)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def load_json_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
        return rows
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "items", "result"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--market-agreement", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    report = render_report(
        build_summary(
            load_jsonl(args.input),
            market_agreement_rows=load_json_rows(args.market_agreement),
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report if report.endswith("\n") else f"{report}\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
