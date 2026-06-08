"""Shadow-only workload and no-vig EV audit for pitcher K picks.

This diagnostic reads the compact Gate C pitcher outcome dataset and writes a
local report only. It must not change live lambda, verdicts, thresholds,
staking, provider order, notifications, locks, retention, calibration, or
dashboard source-of-truth.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "workload_no_vig_ev_audit.md"
CLEAN_WINDOW_START = "2026-04-28"
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


def no_vig_edge_label(row: dict[str, Any]) -> str:
    gap = _to_float(row.get("model_no_vig_gap"))
    ev = _first_float(row, ("ev", "adj_ev", "locked_adj_ev"))
    if gap is None:
        return "unknown"
    if _referee_applied(row):
        if gap >= 0.04 or _has_clv_support(row):
            return "no_vig_referee_disagrees"
        return "no_vig_referee_agrees"
    if row.get("model_market_relationship") == "model_fades_favorite" and gap < 0.04:
        return "no_vig_market_disagrees"
    if gap >= 0.04:
        return "no_vig_confirmed_edge"
    if gap >= 0.02:
        return "no_vig_thin_edge"
    if ev is not None and ev > 0:
        return "no_vig_price_only_edge"
    return "no_vig_no_edge"


def workload_sensitivity_label(row: dict[str, Any]) -> str:
    margin = _to_float(row.get("k_margin_to_line"))
    if margin is None:
        return "unknown"
    margin = abs(margin)
    if margin < 0.5:
        return "workload_sensitivity_half_k"
    if margin < 1.0:
        return "workload_sensitivity_one_k"
    return "workload_stable_margin"


def workload_risk_label(row: dict[str, Any]) -> str:
    leash = str(row.get("leash_risk_bucket") or "").lower()
    opportunity = str(row.get("opportunity_bucket") or "").lower()
    gate = str(row.get("quality_gate_level") or "").lower()
    archetype = str(row.get("pitcher_archetype_bucket") or "").lower()
    recent_start_count = _to_float(row.get("recent_start_count"))
    last_pitch_count = _to_float(row.get("last_pitch_count"))

    if leash in {"high", "medium"}:
        return "workload_fragile"
    if opportunity == "short_leash" or archetype == "short_leash":
        return "workload_fragile"
    if _is_true(row.get("is_opener")):
        return "workload_fragile"
    if recent_start_count is not None and recent_start_count < 2:
        return "workload_fragile"
    if last_pitch_count is not None and last_pitch_count <= 75:
        return "workload_fragile"
    if gate in {"capped", "blocked", "soft_cap"}:
        return "workload_watch"
    return "workload_stable"


def path_b_coverage_bucket(row: dict[str, Any]) -> str:
    mode = str(row.get("batter_handedness_mode") or "").lower()
    runtime_safe = _is_true(row.get("lineup_handedness_runtime_safe"))
    if mode != "path_b" and not runtime_safe:
        return "path_a_or_unknown"

    count = _lineup_real_split_count(row)
    if count <= 0:
        return "path_b_zero_real_splits"
    if count <= 4:
        return "path_b_1_4_real_splits"
    if count <= 8:
        return "path_b_5_8_real_splits"
    return "path_b_9_real_splits"


def referee_interaction_label(row: dict[str, Any]) -> str:
    applied = _referee_applied(row)
    no_vig = no_vig_edge_label(row)
    workload = workload_risk_label(row)
    has_warning = (
        no_vig
        in {
            "no_vig_price_only_edge",
            "no_vig_no_edge",
            "no_vig_market_disagrees",
            "no_vig_referee_agrees",
        }
        or workload == "workload_fragile"
    )
    has_confirmed_edge = no_vig in {"no_vig_confirmed_edge", "no_vig_referee_disagrees"}

    if applied and has_confirmed_edge and workload != "workload_fragile":
        return "referee_cap_contradicted_by_no_vig"
    if applied and has_warning:
        return "referee_cap_supported_by_no_vig_or_workload"
    if not applied and has_warning:
        return "uncapped_row_with_shadow_warning"
    return "referee_neutral"


def load_rows(path: Path = DEFAULT_INPUT) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def analysis_rows(
    rows: list[dict[str, Any]],
    *,
    start_date: str = CLEAN_WINDOW_START,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        slate_date = str(row.get("slate_date") or "")
        if slate_date and slate_date < start_date:
            continue
        if row.get("result") not in WIN_LOSS_RESULTS:
            continue
        if "is_tracked_pick" in row and not _is_true(row.get("is_tracked_pick")):
            continue
        selected.append(row)
    return selected


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = analysis_rows(rows)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "analysis_rows": len(selected),
        "no_vig_labels": _summarize_by(selected, no_vig_edge_label),
        "workload_risk_labels": _summarize_by(selected, workload_risk_label),
        "workload_sensitivity_labels": _summarize_by(selected, workload_sensitivity_label),
        "path_b_coverage_buckets": _summarize_by(selected, path_b_coverage_bucket),
        "referee_interaction_labels": _summarize_by(selected, referee_interaction_label),
        "path_b_no_vig_labels": _summarize_by(
            selected,
            lambda row: _combined_label(row, path_b_coverage_bucket, no_vig_edge_label),
        ),
        "path_b_referee_interaction_labels": _summarize_by(
            selected,
            lambda row: _combined_label(row, path_b_coverage_bucket, referee_interaction_label),
        ),
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Workload And No-Vig EV Audit",
        "",
        f"Generated at: `{summary.get('generated_at', 'unknown')}`",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.",
        "",
        "## Executive Read",
        "",
        f"- Total source rows: `{summary.get('total_rows', 0)}`",
        f"- Clean tracked win/loss rows analyzed: `{summary.get('analysis_rows', 0)}`",
        "- Useful next decision: compare workload/no-vig warnings against confidence-referee caps, Path B coverage, CLV, and Gate F projection challenger output before drafting any live behavior change.",
        "",
        "## Gate Read",
        "",
        "- Gate E remains the research-readiness gate for each candidate family.",
        "- Gate F remains the promotion-candidate gate; no bucket from this report can promote without holdout, slices, and a rollback plan.",
        "",
    ]
    _render_bucket_table(lines, "No-Vig Labels", summary.get("no_vig_labels", {}))
    _render_bucket_table(lines, "Workload Risk Labels", summary.get("workload_risk_labels", {}))
    _render_bucket_table(lines, "Workload Sensitivity Labels", summary.get("workload_sensitivity_labels", {}))
    _render_bucket_table(lines, "Path B Coverage Buckets", summary.get("path_b_coverage_buckets", {}))
    _render_bucket_table(lines, "Referee Interaction Labels", summary.get("referee_interaction_labels", {}))
    _render_bucket_table(lines, "Path B By No-Vig Label", summary.get("path_b_no_vig_labels", {}))
    _render_bucket_table(
        lines,
        "Path B By Referee Interaction",
        summary.get("path_b_referee_interaction_labels", {}),
    )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    rows = load_rows(Path(args.input))
    report = render_report(build_summary(rows))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"Wrote {output} ({len(rows)} source rows)")
    return 0


def _first_float(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key in row:
            value = _to_float(row.get(key))
            if value is not None:
                return value
    return None


def _lineup_real_split_count(row: dict[str, Any]) -> int:
    direct = _to_float(
        row.get("lineup_real_split_count")
        or row.get("lineup_split_count")
        or row.get("lineup_handedness_real_split_count")
    )
    if direct is not None:
        return max(0, int(direct))

    total = 0
    found = False
    for key in ("lineup_right_batters", "lineup_left_batters", "lineup_switch_batters"):
        value = _to_float(row.get(key))
        if value is not None:
            found = True
            total += int(value)
    return max(0, total) if found else 0


def _referee_applied(row: dict[str, Any]) -> bool:
    referee = row.get("confidence_referee")
    if isinstance(referee, dict) and _is_true(referee.get("applied")):
        return True

    for key in (
        "confidence_referee_applied",
        "market_favorite_referee_applied",
        "referee_applied",
        "referee_cap_applied",
        "verdict_capped_by_referee",
    ):
        if _is_true(row.get(key)):
            return True

    action = str(row.get("confidence_referee_action") or row.get("referee_action") or "").lower()
    return "cap" in action or "suppress" in action


def _has_clv_support(row: dict[str, Any]) -> bool:
    return _is_true(row.get("beat_close_price")) or _is_true(row.get("beat_close_line"))


def _combined_label(
    row: dict[str, Any],
    left_fn: Callable[[dict[str, Any]], str],
    right_fn: Callable[[dict[str, Any]], str],
) -> str:
    return f"{left_fn(row)} | {right_fn(row)}"


def _empty_bucket() -> dict[str, float | int]:
    return {
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "pnl": 0.0,
        "roi": 0.0,
        "beat_close_price_rows": 0,
        "beat_close_line_rows": 0,
    }


def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def _add_result(bucket: dict[str, float | int], row: dict[str, Any]) -> None:
    bucket["rows"] += 1
    if row.get("result") == "win":
        bucket["wins"] += 1
    elif row.get("result") == "loss":
        bucket["losses"] += 1
    bucket["pnl"] = round(float(bucket["pnl"]) + _row_pnl(row), 3)
    if _is_true(row.get("beat_close_price")):
        bucket["beat_close_price_rows"] += 1
    if _is_true(row.get("beat_close_line")):
        bucket["beat_close_line_rows"] += 1
    bucket["roi"] = round(float(bucket["pnl"]) / int(bucket["rows"]), 4)


def _summarize_by(
    rows: list[dict[str, Any]],
    label_fn: Callable[[dict[str, Any]], str],
) -> dict[str, dict[str, float | int]]:
    buckets: dict[str, dict[str, float | int]] = defaultdict(_empty_bucket)
    for row in rows:
        _add_result(buckets[label_fn(row)], row)
    return dict(sorted(buckets.items()))


def _format_roi(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:+.1%}"


def _render_bucket_table(
    lines: list[str],
    title: str,
    buckets: dict[str, dict[str, float | int]],
) -> None:
    lines.append(f"## {title}")
    lines.append("")
    lines.append("| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    if not buckets:
        lines.append("| -- | 0 | 0-0 | +0.00 | -- | 0 | 0 |")
        lines.append("")
        return

    for label, bucket in buckets.items():
        pnl = float(bucket["pnl"])
        lines.append(
            f"| `{label}` | {bucket['rows']} | {bucket['wins']}-{bucket['losses']} | "
            f"{pnl:+.2f} | {_format_roi(bucket.get('roi'))} | "
            f"{bucket['beat_close_price_rows']} | {bucket['beat_close_line_rows']} |"
        )
    lines.append("")


if __name__ == "__main__":
    raise SystemExit(main())
