"""Shadow-only bet-selection and edge synthesis for Gate E/F review.

This diagnostic reads the compact Gate C pitcher outcome dataset. It does not
change live lambda, verdicts, thresholds, staking, provider order,
notifications, locks, retention, calibration, or dashboard source-of-truth.
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
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "bet_selection_edge_synthesis.md"
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


def _first_float(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return None


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


def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def edge_bucket(row: dict[str, Any]) -> str:
    edge = _first_float(row, ("edge", "model_no_vig_gap"))
    if edge is None:
        return "edge_unknown"
    if edge < 0.02:
        return "edge_lt_2"
    if edge < 0.04:
        return "edge_2_to_4"
    if edge < 0.06:
        return "edge_4_to_6"
    return "edge_6_plus"


def ev_bucket(row: dict[str, Any]) -> str:
    ev = _first_float(row, ("locked_adj_ev", "adj_ev", "ev"))
    if ev is None:
        return "adj_ev_unknown"
    if ev < 0.06:
        return "adj_ev_lt_6"
    if ev < 0.17:
        return "adj_ev_6_to_17"
    return "adj_ev_17_plus"


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


def actual_outing_bucket(row: dict[str, Any]) -> str:
    actual_ip = _to_float(row.get("actual_ip"))
    expected_ip = _first_float(row, ("avg_ip", "projected_ip", "expected_ip"))
    if actual_ip is None or expected_ip is None:
        return "actual_outing_unknown"
    delta = actual_ip - expected_ip
    if delta <= -1.0:
        return "short_outing"
    if delta >= 1.0:
        return "deep_outing"
    return "normal_outing"


def candidate_label(row: dict[str, Any]) -> str:
    edge = _first_float(row, ("edge", "model_no_vig_gap")) or 0.0
    no_vig_gap = _to_float(row.get("model_no_vig_gap"))
    relationship = str(row.get("model_market_relationship") or "").strip()
    side = str(row.get("side") or "").lower()
    quality = str(row.get("quality_gate_level") or "").lower()
    workload = str(row.get("leash_risk_bucket") or row.get("opportunity_bucket") or "").lower()
    large_skeptic = _is_true(row.get("large_edge_skepticism_flag"))

    if edge >= 0.06 and (large_skeptic or relationship == "model_fades_favorite"):
        return "high_edge_skeptic"
    if side == "under" and _is_fire(row) and (
        workload in {"high", "medium", "short_leash"} or relationship == "model_fades_favorite"
    ):
        return "fire_under_watch"
    if 0.04 <= edge < 0.06 and no_vig_gap is not None and no_vig_gap >= 0.04:
        if quality in {"clean", "none", ""} and relationship == "model_agrees_with_favorite" and not large_skeptic:
            return "moderate_edge_clean_context"
    if clv_label(row) in {"beat_close_price", "beat_close_line"}:
        return "clv_supported"
    return "baseline_watch"


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


def analysis_rows(
    rows: list[dict[str, Any]],
    *,
    start_date: str = CLEAN_WINDOW_START,
) -> list[dict[str, Any]]:
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


def _empty_bucket() -> dict[str, float | int]:
    return {
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "fire_rows": 0,
        "lean_rows": 0,
        "pnl": 0.0,
        "roi": 0.0,
        "beat_close_price_rows": 0,
        "beat_close_line_rows": 0,
    }


def _add_result(bucket: dict[str, float | int], row: dict[str, Any]) -> None:
    bucket["rows"] += 1
    if row.get("result") == "win":
        bucket["wins"] += 1
    elif row.get("result") == "loss":
        bucket["losses"] += 1
    if _is_fire(row):
        bucket["fire_rows"] += 1
    if _verdict(row) == "LEAN":
        bucket["lean_rows"] += 1
    bucket["pnl"] = round(float(bucket["pnl"]) + _row_pnl(row), 3)
    bucket["roi"] = round(float(bucket["pnl"]) / int(bucket["rows"]), 4)
    if _is_true(row.get("beat_close_price")):
        bucket["beat_close_price_rows"] += 1
    if _is_true(row.get("beat_close_line")):
        bucket["beat_close_line_rows"] += 1


def _summarize_by(
    rows: list[dict[str, Any]],
    label_fn: Callable[[dict[str, Any]], str],
) -> dict[str, dict[str, float | int]]:
    buckets: dict[str, dict[str, float | int]] = defaultdict(_empty_bucket)
    for row in rows:
        _add_result(buckets[label_fn(row)], row)
    return dict(sorted(buckets.items()))


def _combined_label(
    row: dict[str, Any],
    left_fn: Callable[[dict[str, Any]], str],
    right_fn: Callable[[dict[str, Any]], str],
) -> str:
    return f"{left_fn(row)} | {right_fn(row)}"


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = analysis_rows(rows)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "analysis_rows": len(selected),
        "by_verdict": _summarize_by(selected, lambda row: _verdict(row) or "unknown"),
        "by_side": _summarize_by(selected, lambda row: str(row.get("side") or "unknown").lower()),
        "by_edge_bucket": _summarize_by(selected, edge_bucket),
        "by_ev_bucket": _summarize_by(selected, ev_bucket),
        "by_edge_ev": _summarize_by(selected, lambda row: _combined_label(row, edge_bucket, ev_bucket)),
        "by_candidate_label": _summarize_by(selected, candidate_label),
        "by_model_market": _summarize_by(
            selected,
            lambda row: str(row.get("model_market_relationship") or "unknown"),
        ),
        "by_no_vig": _summarize_by(selected, no_vig_label),
        "by_clv": _summarize_by(selected, clv_label),
        "by_opportunity_actual": _summarize_by(
            selected,
            lambda row: f"{row.get('opportunity_bucket') or 'unknown'} | {actual_outing_bucket(row)}",
        ),
    }


def _format_roi(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:+.1%}"


def _render_bucket_table(
    lines: list[str],
    title: str,
    buckets: dict[str, dict[str, float | int]],
    *,
    max_rows: int = 25,
) -> None:
    lines.append(f"## {title}")
    lines.append("")
    lines.append("| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    if not buckets:
        lines.append("| -- | 0 | 0 | 0 | 0-0 | +0.00 | -- | 0 | 0 |")
        lines.append("")
        return

    ordered = sorted(
        buckets.items(),
        key=lambda item: (int(item[1]["rows"]), float(item[1]["pnl"])),
        reverse=True,
    )
    for label, bucket in ordered[:max_rows]:
        pnl = float(bucket["pnl"])
        lines.append(
            f"| `{label}` | {bucket['rows']} | {bucket['fire_rows']} | {bucket['lean_rows']} | "
            f"{bucket['wins']}-{bucket['losses']} | {pnl:+.2f} | {_format_roi(bucket.get('roi'))} | "
            f"{bucket['beat_close_price_rows']} | {bucket['beat_close_line_rows']} |"
        )
    lines.append("")


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Bet Selection And Edge Synthesis",
        "",
        f"Generated at: `{summary.get('generated_at', 'unknown')}`",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.",
        "",
        "## Executive Read",
        "",
        f"- Total source rows: `{summary.get('total_rows', 0)}`",
        f"- Clean tracked win/loss rows analyzed: `{summary.get('analysis_rows', 0)}`",
        "- Useful next decision: use this as Gate E research evidence for which bet-selection contexts deserve deeper Gate F challenger testing.",
        "- Bill James-style component thinking is reflected here as a diagnostic frame: do not judge edge from ERA/surface outcomes; compare strikeout skill, workload, market price, no-vig gap, CLV, and postgame opportunity separately.",
        "",
        "## Gate Read",
        "",
        "- Gate E remains the research-readiness gate for candidate labels and bet-selection slices.",
        "- Gate F remains the promotion-candidate gate; no slice in this report can change live selection without holdout, rolling-window, side, K-line, FIRE/LEAN, CLV, workload, Path B, and market-agreement review.",
        "",
    ]
    _render_bucket_table(lines, "Verdict", summary.get("by_verdict", {}))
    _render_bucket_table(lines, "Side", summary.get("by_side", {}))
    _render_bucket_table(lines, "Edge Buckets", summary.get("by_edge_bucket", {}))
    _render_bucket_table(lines, "EV Buckets", summary.get("by_ev_bucket", {}))
    _render_bucket_table(lines, "Edge By EV", summary.get("by_edge_ev", {}))
    _render_bucket_table(lines, "Candidate Labels", summary.get("by_candidate_label", {}))
    _render_bucket_table(lines, "Model Market Relationship", summary.get("by_model_market", {}))
    _render_bucket_table(lines, "No-Vig Labels", summary.get("by_no_vig", {}))
    _render_bucket_table(lines, "CLV Labels", summary.get("by_clv", {}))
    _render_bucket_table(lines, "Opportunity By Actual Outing", summary.get("by_opportunity_actual", {}))
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
