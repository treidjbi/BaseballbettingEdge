"""Build the Gate C confidence-referee shadow report.

This diagnostic reads the compact pitcher K outcome dataset and writes a local
report only. It must not change live picks, locks, thresholds, staking,
provider order, notifications, projection math, or calibration.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_PATH = ROOT / "analytics" / "output" / "confidence_referee_shadow_report.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
BUCKET_ORDER = [
    "bet_late_if_still_available",
    "wait_for_late_data",
    "skip_or_demand_better_price",
    "monitor_only",
]


def load_jsonl(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _is_fire(row: dict[str, Any]) -> bool:
    return str(row.get("verdict") or "").startswith("FIRE")


def _pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl"):
        value = row.get(key)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _has_clv_edge(row: dict[str, Any]) -> bool:
    return _is_true(row.get("beat_close_price")) or _is_true(row.get("beat_close_line"))


def _runtime_caution_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if _is_true(row.get("large_edge_skepticism_flag")):
        reasons.append("large_edge_skepticism")
    if row.get("model_market_relationship") == "model_fades_favorite":
        reasons.append("model_fades_market_favorite")
    if row.get("leash_risk_bucket") == "high":
        reasons.append("high_leash_risk")
    if row.get("opportunity_bucket") == "short_leash":
        reasons.append("short_leash_opportunity")
    if row.get("quality_gate_level") in {"capped", "soft_cap"}:
        reasons.append("quality_gate_capped")
    return reasons


def referee_bucket(row: dict[str, Any]) -> str:
    """Assign a shadow referee bucket from runtime-safe fields only."""

    timing = str(row.get("bet_timing_window") or "unknown")
    if timing == "post_start":
        return "monitor_only"

    if not _is_fire(row):
        return "monitor_only"

    if _runtime_caution_reasons(row):
        return "skip_or_demand_better_price"

    if timing in {"pre_15", "pre_5"}:
        return "bet_late_if_still_available"

    if timing in {"pre_120", "pre_60", "pre_30", "unknown"}:
        return "wait_for_late_data"

    return "monitor_only"


def clean_official_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("slate_date") or "") >= CLEAN_WINDOW_START
        and row.get("context_snapshot") == "official_close"
        and row.get("result") in WIN_LOSS_RESULTS
    ]


def tracked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in clean_official_rows(rows) if _is_true(row.get("is_tracked_pick"))]


def _blank_summary() -> dict[str, Any]:
    return {
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "pnl": 0.0,
        "roi": None,
        "clv_edge_rows": 0,
        "good_process": 0,
        "weak_process": 0,
    }


def summarize_buckets(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary = {bucket: _blank_summary() for bucket in BUCKET_ORDER}

    for row in rows:
        if row.get("result") not in WIN_LOSS_RESULTS:
            continue

        bucket = referee_bucket(row)
        item = summary[bucket]
        item["rows"] += 1
        if row.get("result") == "win":
            item["wins"] += 1
        else:
            item["losses"] += 1

        item["pnl"] += _pnl(row)
        if _has_clv_edge(row):
            item["clv_edge_rows"] += 1

        process_bucket = str(row.get("process_outcome_bucket") or "")
        if process_bucket.startswith("good_process"):
            item["good_process"] += 1
        elif process_bucket.startswith("weak_process"):
            item["weak_process"] += 1

    for item in summary.values():
        item["pnl"] = round(item["pnl"], 2)
        if item["rows"]:
            item["roi"] = round(item["pnl"] / item["rows"], 4)

    return summary


def _counter_line(title: str, counter: Counter) -> str:
    parts = [f"`{key}` {value}" for key, value in counter.most_common()]
    return f"- {title}: " + (", ".join(parts) if parts else "none")


def _format_roi(value: float | None) -> str:
    return "--" if value is None else f"{value:+.1%}"


def _format_bucket_row(bucket: str, item: dict[str, Any]) -> str:
    return (
        f"| `{bucket}` | {item['rows']} | {item['wins']}-{item['losses']} | "
        f"{item['pnl']:+.2f} | {_format_roi(item['roi'])} | "
        f"{item['clv_edge_rows']} | {item['good_process']} | {item['weak_process']} |"
    )


def build_report(rows: list[dict[str, Any]]) -> str:
    clean_rows = clean_official_rows(rows)
    tracked = tracked_rows(rows)
    bucket_summary = summarize_buckets(tracked)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    duplicate_keys = len(clean_rows) - len({row.get("dataset_key") for row in clean_rows})
    missing_team_or_opponent = sum(
        1 for row in clean_rows if not row.get("team") or not row.get("opp_team")
    )
    missing_book_odds = sum(1 for row in clean_rows if row.get("american_odds") is None)
    missing_model_fields = sum(
        1
        for row in clean_rows
        if row.get("model_win_prob") is None or row.get("model_side") is None
    )

    relationship_counts = Counter(row.get("model_market_relationship") or "unknown" for row in clean_rows)
    edge_counts = Counter(row.get("model_edge_bucket") or "unknown" for row in clean_rows)
    opportunity_counts = Counter(row.get("opportunity_bucket") or "unknown" for row in clean_rows)
    leash_counts = Counter(row.get("leash_risk_bucket") or "unknown" for row in clean_rows)
    timing_counts = Counter(row.get("bet_timing_window") or "unknown" for row in tracked)

    clv_rows = sum(1 for row in tracked if row.get("price_clv_cents") is not None)
    beat_close_price = sum(1 for row in tracked if _is_true(row.get("beat_close_price")))
    beat_close_line = sum(1 for row in tracked if _is_true(row.get("beat_close_line")))
    large_edge_rows = sum(1 for row in tracked if _is_true(row.get("large_edge_skepticism_flag")))
    tracked_pnl = round(sum(_pnl(row) for row in tracked), 2)
    tracked_roi = round(tracked_pnl / len(tracked), 4) if tracked else None

    lines = [
        "# Confidence Referee Shadow Report",
        "",
        "Shadow-only: this report does not change live picks, locks, thresholds, staking, provider order, notifications, projection math, or calibration.",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Clean window start: `{CLEAN_WINDOW_START}`",
        "",
        "## Evidence Boundary",
        "",
        "- Runtime-safe label inputs: verdict, timing window, model-vs-market relationship, quality gate, leash/opportunity buckets, and pregame caution flags.",
        "- Hindsight validation fields: result, PnL, beat-close price, beat-close line, and process-outcome buckets.",
        "",
        "## System Health",
        "",
        f"- Clean graded dataset rows: `{len(clean_rows)}`",
        f"- Tracked pick rows: `{len(tracked)}`",
        f"- Duplicate dataset keys: `{duplicate_keys}`",
        f"- Missing team/opponent rows: `{missing_team_or_opponent}`",
        f"- Missing book odds rows: `{missing_book_odds}`",
        f"- Missing model fields rows: `{missing_model_fields}`",
        "",
        "## Model Health",
        "",
        _counter_line("Model vs market relationship", relationship_counts),
        _counter_line("Model edge buckets", edge_counts),
        _counter_line("Opportunity buckets", opportunity_counts),
        _counter_line("Leash risk buckets", leash_counts),
        "",
        "## Bet-Selection Health",
        "",
        f"- Rows with price CLV available: `{clv_rows}`",
        f"- Beat close price rows: `{beat_close_price}`",
        f"- Beat close line rows: `{beat_close_line}`",
        f"- Large-edge skepticism rows: `{large_edge_rows}`",
        _counter_line("Bet timing windows", timing_counts),
        "",
        "| Referee Bucket | Rows | W-L | PnL | ROI | CLV Edge Rows | Good Process | Weak Process |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(_format_bucket_row(bucket, bucket_summary[bucket]) for bucket in BUCKET_ORDER)

    process_counts = Counter(row.get("process_outcome_bucket") or "unknown" for row in tracked)
    lines.extend(
        [
            "",
            "## Betting Outcome",
            "",
            f"- Tracked-pick PnL in referee rows: `{tracked_pnl:+.2f}`",
            f"- Tracked-pick ROI in referee rows: `{_format_roi(tracked_roi)}`",
            _counter_line("Process outcome buckets", process_counts),
            "",
            "## Referee Read",
            "",
            "- `bet_late_if_still_available` is the clean late-window FIRE bucket. It should only become actionable if it keeps validating across side, price, and line buckets.",
            "- `wait_for_late_data` is the patience bucket: the model liked the pick, but the row was not yet in the late lock window.",
            "- `skip_or_demand_better_price` is the skepticism bucket: runtime-safe caution says the number needs to improve or the pick should stay shadow-only.",
            "- `monitor_only` means the row is non-FIRE, post-start, incomplete, or not useful enough for a betting decision.",
            "",
            "## Next Action",
            "",
            "- Keep this report beside bet-conversion, market-price, live-market, and pitcher-outcome diagnostics.",
            "- Do not promote any bucket directly into alerts or betting rules until Gate E/F and a separate Tyler-approved promotion plan.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = build_report(load_jsonl(args.input))
    print(report)
    if not args.no_write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
