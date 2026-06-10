"""Shadow-only Gate F FIRE re-entry selection lab.

This diagnostic asks which rows could earn FIRE status back after the active
profit-rescue canary. It reads historical Gate C rows and does not change live
lambda, verdicts, thresholds, staking, provider order, notifications, locks,
retention, calibration, or dashboard source-of-truth behavior.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "gate_f_fire_reentry_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
FIRE_VERDICTS = {"FIRE 1u", "FIRE 2u"}
CANDIDATE_NAMES = (
    "clv_supported_reentry",
    "market_aligned_reentry",
    "moderate_edge_quality_reentry",
    "retained_fire_control",
    "avoid_fire_under_reentry",
)
CANDIDATE_KINDS = {
    "clv_supported_reentry": "process_anchor",
    "market_aligned_reentry": "runtime_selector",
    "moderate_edge_quality_reentry": "runtime_selector",
    "retained_fire_control": "runtime_selector",
    "avoid_fire_under_reentry": "avoidance_rule",
}
SLICE_FIELDS = (
    "side",
    "display_verdict",
    "line_bucket",
    "price_sign",
    "quality_gate_level",
    "model_market_relationship",
    "bet_timing_window",
    "no_vig_label",
    "clv_label",
    "leash_risk_bucket",
    "path_b_coverage_bucket",
    "provider",
    "market_agreement_label",
)


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def _is_fire(verdict: Any) -> bool:
    return str(verdict or "").startswith("FIRE")


def current_verdict(row: dict[str, Any]) -> str:
    return str(
        row.get("display_verdict")
        or row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("current_verdict")
        or row.get("verdict")
        or ""
    ).strip()


def source_fire_verdict(row: dict[str, Any]) -> str:
    """Return the FIRE-like source verdict before profit-rescue capping.

    Historical rows usually only have display/locked verdicts. Future
    post-canary rows may preserve a raw FIRE verdict while displaying LEAN.
    """
    for key in ("raw_verdict", "quality_actionable_verdict"):
        value = str(row.get(key) or "").strip()
        if _is_fire(value):
            return value
    return current_verdict(row)


def no_vig_label(row: dict[str, Any]) -> str:
    gap = _to_float(row.get("model_no_vig_gap"))
    if gap is None:
        return "no_vig_unknown"
    if gap >= 0.04:
        return "no_vig_confirmed_edge"
    if gap >= 0.02:
        return "no_vig_thin_edge"
    if gap > 0:
        return "no_vig_price_only_edge"
    return "no_vig_no_edge"


def clv_label(row: dict[str, Any]) -> str:
    price_clv = _to_float(row.get("price_clv_cents"))
    line_clv = _to_float(row.get("line_clv_delta"))
    if _is_true(row.get("beat_close_price")) or (price_clv is not None and price_clv > 0):
        return "beat_close_price"
    if _is_true(row.get("beat_close_line")) or (line_clv is not None and line_clv > 0):
        return "beat_close_line"
    if price_clv is not None and price_clv < 0:
        return "worse_than_close_price"
    if line_clv is not None and line_clv < 0:
        return "worse_than_close_line"
    return "clv_neutral_or_unknown"


def clv_supported(row: dict[str, Any]) -> bool:
    return clv_label(row) in {"beat_close_price", "beat_close_line"}


def profit_rescue_shadow_decision(row: dict[str, Any]) -> dict[str, Any]:
    current = source_fire_verdict(row)
    proposed = current
    side = str(row.get("side") or "").strip().lower()
    relationship = str(row.get("model_market_relationship") or "").strip()
    reasons: list[str] = []

    if current == "FIRE 2u":
        proposed = "FIRE 1u"
        reasons.append("cap_fire_two_to_fire_one")

    if side == "under" and _is_fire(proposed):
        proposed = "LEAN"
        reasons.append("cap_fire_under_to_lean")

    if relationship == "model_fades_favorite" and _is_fire(current):
        reasons.append("cap_market_fade_fire_to_lean")
        if _is_fire(proposed):
            proposed = "LEAN"

    if not _is_fire(current):
        action = "keep_non_fire"
    elif proposed == current:
        action = "keep_fire"
    elif _is_fire(proposed):
        action = "downgrade_fire_two_to_fire_one"
    else:
        action = "downgrade_fire_to_lean"

    return {
        "current_verdict": current,
        "proposed_verdict": proposed,
        "action": action,
        "reasons": reasons,
    }


def candidate_labels(row: dict[str, Any]) -> set[str]:
    verdict = source_fire_verdict(row)
    if not _is_fire(verdict):
        return set()

    labels: set[str] = set()
    decision = profit_rescue_shadow_decision(row)
    side = str(row.get("side") or "").strip().lower()
    relationship = str(row.get("model_market_relationship") or "").strip()
    quality = str(row.get("quality_gate_level") or "").strip().lower()
    edge = _to_float(row.get("edge"))
    adj_ev = _to_float(row.get("locked_adj_ev"))
    if adj_ev is None:
        adj_ev = _to_float(row.get("adj_ev"))
    no_vig_gap = _to_float(row.get("model_no_vig_gap"))
    workload = str(row.get("leash_risk_bucket") or row.get("opportunity_bucket") or "").strip().lower()

    if _is_fire(decision["proposed_verdict"]):
        labels.add("retained_fire_control")

    if clv_supported(row):
        labels.add("clv_supported_reentry")

    if relationship == "model_agrees_with_favorite" and no_vig_gap is not None and no_vig_gap >= 0.04:
        labels.add("market_aligned_reentry")

    if (
        edge is not None
        and 0.02 <= edge < 0.06
        and adj_ev is not None
        and adj_ev < 0.17
        and no_vig_gap is not None
        and no_vig_gap >= 0.04
        and quality in {"", "clean", "none"}
        and not _is_true(row.get("large_edge_skepticism_flag"))
    ):
        labels.add("moderate_edge_quality_reentry")

    if side == "under" and (
        not clv_supported(row)
        or (no_vig_gap is not None and no_vig_gap < 0.02)
        or relationship == "model_fades_favorite"
        or workload in {"high", "medium", "short_leash"}
    ):
        labels.add("avoid_fire_under_reentry")

    return labels


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
        if "is_tracked_pick" in row and not _is_true(row.get("is_tracked_pick")):
            continue
        selected.append(row)
    return selected


def _empty_bucket() -> dict[str, Any]:
    return {
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "pnl": 0.0,
        "roi": 0.0,
        "retained_fire_rows": 0,
        "capped_to_lean_rows": 0,
        "clv_support_rows": 0,
        "clv_support_rate": 0.0,
    }


def _add_row(bucket: dict[str, Any], row: dict[str, Any]) -> None:
    bucket["rows"] += 1
    if row.get("result") == "win":
        bucket["wins"] += 1
    elif row.get("result") == "loss":
        bucket["losses"] += 1
    bucket["pnl"] = round(float(bucket["pnl"]) + _row_pnl(row), 2)
    bucket["roi"] = round(float(bucket["pnl"]) / int(bucket["rows"]), 4)
    decision = profit_rescue_shadow_decision(row)
    if _is_fire(decision["proposed_verdict"]):
        bucket["retained_fire_rows"] += 1
    elif _is_fire(decision["current_verdict"]):
        bucket["capped_to_lean_rows"] += 1
    if clv_supported(row):
        bucket["clv_support_rows"] += 1
    bucket["clv_support_rate"] = round(
        float(bucket["clv_support_rows"]) / int(bucket["rows"]),
        4,
    )


def _slice_value(row: dict[str, Any], field: str) -> str:
    if field == "no_vig_label":
        return no_vig_label(row)
    if field == "clv_label":
        return clv_label(row)
    return str(row.get(field) or "unknown")


def _summarize_slice(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(_empty_bucket)
    for row in rows:
        _add_row(buckets[_slice_value(row, field)], row)
    return dict(sorted(buckets.items()))


def _negative_slices(rows: list[dict[str, Any]], *, min_rows: int = 10) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for field in SLICE_FIELDS:
        for bucket, summary in _summarize_slice(rows, field).items():
            if summary["rows"] >= min_rows and summary["pnl"] < 0:
                risks.append(
                    {
                        "field": field,
                        "bucket": bucket,
                        "rows": summary["rows"],
                        "pnl": summary["pnl"],
                        "roi": summary["roi"],
                    }
                )
    risks.sort(key=lambda item: (float(item["pnl"]), -int(item["rows"])))
    return risks


def _recent_rows(rows: list[dict[str, Any]], *, days: int = 14) -> list[dict[str, Any]]:
    dates = [parsed for row in rows if (parsed := _parse_date(row.get("slate_date") or row.get("date")))]
    if not dates:
        return rows
    floor = max(dates) - timedelta(days=days - 1)
    return [
        row
        for row in rows
        if (row_date := _parse_date(row.get("slate_date") or row.get("date"))) is not None
        and row_date >= floor
    ]


def _score_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bucket = _empty_bucket()
    for row in rows:
        _add_row(bucket, row)
    return bucket


def _readiness(summary: dict[str, Any]) -> str:
    kind = str(summary.get("kind") or "")
    if kind == "process_anchor":
        return "process_anchor"
    if kind == "avoidance_rule":
        return "avoidance_rule"

    rows = int(summary["rows"])
    roi = float(summary["roi"])
    clv_rate = float(summary["clv_support_rate"])
    recent_pnl = float(summary["recent"]["pnl"])
    has_negative_slice = bool(summary["negative_slices"])
    if rows >= 100 and roi > 0 and clv_rate >= 0.4 and recent_pnl >= 0 and not has_negative_slice:
        return "ready_for_plan"
    if rows >= 50 and roi > 0:
        return "watch_more"
    return "not_ready"


def summarize_candidate(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [row for row in rows if name in candidate_labels(row)]
    summary = _score_rows(selected)
    recent = _score_rows(_recent_rows(selected))
    negative_slices = _negative_slices(selected)
    summary.update(
        {
            "name": name,
            "kind": CANDIDATE_KINDS.get(name, "runtime_selector"),
            "recent": recent,
            "negative_slices": negative_slices,
            "slice_tables": {field: _summarize_slice(selected, field) for field in SLICE_FIELDS},
        }
    )
    summary["readiness"] = _readiness(summary)
    return summary


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = analysis_rows(rows)
    source_fire_rows = [row for row in selected if _is_fire(source_fire_verdict(row))]
    rescue_summary = _score_rows(source_fire_rows)
    candidates = {
        name: summarize_candidate(name, selected)
        for name in CANDIDATE_NAMES
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "analysis_rows": len(selected),
        "source_fire_rows": len(source_fire_rows),
        "rescue_summary": rescue_summary,
        "candidates": candidates,
    }


def _format_roi(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:+.1%}"


def _format_pnl(value: Any) -> str:
    number = _to_float(value) or 0.0
    return f"{number:+.2f}"


def _render_scoreboard(lines: list[str], candidates: dict[str, dict[str, Any]]) -> None:
    lines.extend(
        [
            "## Candidate Scoreboard",
            "",
            "| Candidate | Kind | Readiness | Rows | W-L | PnL | ROI | Retained FIRE | Capped to LEAN | CLV support | Recent PnL | Slice risks |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    ordered = sorted(
        candidates.values(),
        key=lambda item: (
            {
                "ready_for_plan": 5,
                "watch_more": 4,
                "process_anchor": 3,
                "avoidance_rule": 2,
                "not_ready": 1,
            }.get(str(item["readiness"]), 0),
            float(item["pnl"]),
            int(item["rows"]),
        ),
        reverse=True,
    )
    for item in ordered:
        lines.append(
            f"| `{item['name']}` | `{item.get('kind', 'runtime_selector')}` | `{item['readiness']}` | {item['rows']} | "
            f"{item['wins']}-{item['losses']} | {_format_pnl(item['pnl'])} | {_format_roi(item['roi'])} | "
            f"{item['retained_fire_rows']} | {item['capped_to_lean_rows']} | "
            f"{item['clv_support_rows']} ({_format_roi(item['clv_support_rate'])}) | "
            f"{_format_pnl(item['recent']['pnl'])} | {len(item['negative_slices'])} |"
        )
    lines.append("")


def _render_top_risks(lines: list[str], candidates: dict[str, dict[str, Any]]) -> None:
    lines.extend(["## Top Slice Risks", ""])
    for name, item in candidates.items():
        risks = item.get("negative_slices", [])[:5]
        if not risks:
            lines.append(f"- `{name}`: no negative slices above the minimum sample floor.")
            continue
        risk_text = "; ".join(
            f"{risk['field']}={risk['bucket']} ({risk['rows']} rows, {_format_pnl(risk['pnl'])})"
            for risk in risks
        )
        lines.append(f"- `{name}`: {risk_text}.")
    lines.append("")


def render_report(summary: dict[str, Any]) -> str:
    candidates = summary.get("candidates", {})
    ready = [name for name, item in candidates.items() if item.get("readiness") == "ready_for_plan"]
    watch = [name for name, item in candidates.items() if item.get("readiness") == "watch_more"]
    process = [name for name, item in candidates.items() if item.get("readiness") == "process_anchor"]
    rescue = summary.get("rescue_summary", {})
    retained = int(rescue.get("retained_fire_rows", 0))
    capped = int(rescue.get("capped_to_lean_rows", 0))
    total_fire = int(summary.get("source_fire_rows", 0))
    retained_rate = retained / total_fire if total_fire else 0.0

    lines = [
        "# Gate F FIRE Re-Entry Selection Lab",
        "",
        f"Generated at: `{summary.get('generated_at', 'unknown')}`",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.",
        "",
        "## Executive Read",
        "",
        f"- Total source rows: `{summary.get('total_rows', 0)}`",
        f"- Clean tracked win/loss rows analyzed: `{summary.get('analysis_rows', 0)}`",
        f"- Historical FIRE-like rows analyzed: `{total_fire}`",
        f"- Profit-rescue shadow retention: `{retained}` retained FIRE rows and `{capped}` capped-to-LEAN rows (`{retained_rate:.1%}` retained).",
        "- This lab exists to prevent a permanent zero-FIRE product by finding evidence-backed re-entry candidates.",
        f"- Ready-for-plan candidates: `{', '.join(ready) if ready else 'none'}`",
        f"- Watch-more candidates: `{', '.join(watch) if watch else 'none'}`",
        f"- Process anchors, not runtime selectors: `{', '.join(process) if process else 'none'}`",
        "",
        "## Gate Read",
        "",
        "- Gate F is now measuring FIRE re-entry volume and decision value, not just FIRE avoidance.",
        "- A ready candidate still needs a Tyler-approved production plan and feature flag before it can affect live picks.",
        "- Hindsight-only result, PnL, CLV, and actual workload fields are used for scoring/process support only, never as the sole live selector.",
        "",
    ]
    _render_scoreboard(lines, candidates)
    _render_top_risks(lines, candidates)
    lines.extend(
        [
            "## Recommendation",
            "",
            "- If no candidate is `ready_for_plan`, keep `PROFIT_RESCUE_REFEREE_MODE=enforce` and collect the next graded slates.",
            "- If a candidate is `ready_for_plan`, draft a separate re-entry canary that restores FIRE only for that candidate family while preserving a one-env-var rollback.",
            "- Do not change projection math from this report; projection challengers stay in the separate Gate F lambda lane.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    summary = build_summary(load_rows(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(summary), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    write_report(args.input, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
