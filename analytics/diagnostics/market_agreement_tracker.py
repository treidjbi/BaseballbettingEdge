"""Derived market-agreement tracker for Gate C review.

This diagnostic is analysis-only. It does not change live picks, locks,
thresholds, staking, provider order, notification sends, or calibration.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analytics.diagnostics.live_market_outcome_audit import (  # noqa: E402
    DEFAULT_CHECKPOINTS_MINUTES,
    build_rows_from_inputs,
    load_json_rows,
)
from pipeline.name_utils import normalize  # noqa: E402


HISTORY_PATH = ROOT / "data" / "picks_history.json"
OUTPUT_MD_PATH = ROOT / "analytics" / "output" / "market_agreement_tracker.md"
OUTPUT_JSONL_PATH = ROOT / "analytics" / "output" / "market_agreement_tracker.jsonl"
OVERALL_GRADED_MIN_ROWS = 75
BUCKET_GRADED_MIN_ROWS = 50


def _to_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def _normalized_pitcher(row: dict[str, Any]) -> str:
    return str(
        row.get("normalized_pitcher")
        or row.get("normalized_player_name")
        or normalize(row.get("pitcher") or row.get("player_name") or "")
    ).strip()


def _pick_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("slate_date") or row.get("date") or "").strip(),
        _normalized_pitcher(row),
        str(row.get("side") or "").strip().lower(),
    )


def _current_verdict(row: dict[str, Any]) -> str:
    return str(
        row.get("current_verdict")
        or row.get("display_verdict")
        or row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("verdict")
        or ""
    ).strip()


def _raw_verdict(row: dict[str, Any]) -> str:
    return str(row.get("raw_verdict") or "").strip()


def _is_fire_verdict(verdict: str) -> bool:
    return verdict.startswith("FIRE")


def _is_lean_verdict(verdict: str) -> bool:
    return verdict == "LEAN"


def _confidence_referee(row: dict[str, Any]) -> dict[str, Any]:
    return _json_object(row.get("confidence_referee"))


def movement_agreement_label(row: dict[str, Any]) -> str:
    consensus = str(row.get("market_consensus") or "").strip().lower()
    if consensus == "toward_pick":
        return "market_with_model"
    if consensus == "away_from_pick":
        return "market_against_model"
    if consensus == "mixed":
        return "market_mixed"
    return "market_no_signal"


def movement_value_label(row: dict[str, Any]) -> str:
    consensus = str(row.get("bet_value_consensus") or "").strip().lower()
    if consensus == "better_now":
        return "number_better_now"
    if consensus == "worse_now":
        return "number_worse_now"
    if consensus == "mixed":
        return "value_mixed"
    return "value_no_signal"


def movement_strength_label(row: dict[str, Any]) -> str:
    market_consensus = str(row.get("market_consensus") or "").strip().lower()
    toward_count = _to_int(row.get("toward_pick_count")) or 0
    away_count = _to_int(row.get("away_from_pick_count")) or 0
    reversal_count = _to_int(row.get("reversal_book_count") or row.get("volatile_book_count")) or 0

    if market_consensus == "mixed" or reversal_count > 0 or (toward_count > 0 and away_count > 0):
        return "mixed_or_reversed"
    if row.get("broad_confirmation") is True or toward_count >= 2:
        return "broad_with_model"
    if away_count >= 2:
        return "broad_against_model"
    if toward_count == 1 or market_consensus == "toward_pick":
        return "single_book_with_model"
    if away_count == 1 or market_consensus == "away_from_pick":
        return "single_book_against_model"
    return "no_movement_signal"


def _book_summaries(row: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = _json_object(row.get("metadata"))
    raw_summaries = metadata.get("book_summaries")
    if isinstance(raw_summaries, dict):
        return [summary for summary in raw_summaries.values() if isinstance(summary, dict)]
    if isinstance(raw_summaries, list):
        return [summary for summary in raw_summaries if isinstance(summary, dict)]
    return []


def _max_abs_movement(row: dict[str, Any]) -> tuple[float, int]:
    max_line_delta = abs(_to_float(row.get("line_delta")) or 0.0)
    max_odds_delta = abs(_to_int(row.get("odds_delta")) or 0)

    for summary in _book_summaries(row):
        line_delta = abs(_to_float(summary.get("line_delta")) or 0.0)
        odds_delta = abs(_to_int(summary.get("odds_delta")) or 0)
        max_line_delta = max(max_line_delta, line_delta)
        max_odds_delta = max(max_odds_delta, odds_delta)

    return round(max_line_delta, 3), max_odds_delta


def movement_magnitude_bucket(row: dict[str, Any]) -> str:
    max_line_delta, max_odds_delta = _max_abs_movement(row)
    if max_line_delta >= 0.5:
        return "line_half_plus"
    if max_odds_delta >= 20:
        return "odds_20c_plus"
    if max_odds_delta >= 10:
        return "odds_10_19c"
    return "small_or_none"


def _tracker_bucket(row: dict[str, Any]) -> str:
    agreement = row.get("movement_agreement_label") or movement_agreement_label(row)
    current_verdict = _current_verdict(row)
    referee_meta = _confidence_referee(row)
    referee_applied = referee_meta.get("applied") is True

    suffix_by_agreement = {
        "market_with_model": "market_with_us",
        "market_against_model": "market_against_us",
        "market_mixed": "mixed",
        "market_no_signal": "no_signal",
    }
    suffix = suffix_by_agreement.get(str(agreement), "no_signal")

    if referee_applied:
        return f"referee_cap_{suffix}"
    if _is_lean_verdict(current_verdict):
        return f"lean_{suffix}"
    if _is_fire_verdict(current_verdict):
        return f"fire_{suffix}"
    return f"other_{suffix}"


def annotate_row(row: dict[str, Any]) -> dict[str, Any]:
    annotated = {**row}
    metadata = _json_object(annotated.get("metadata"))
    referee_meta = _confidence_referee(annotated)
    current_verdict = _current_verdict(annotated)
    raw_verdict = _raw_verdict(annotated)
    max_line_delta, max_odds_delta = _max_abs_movement(annotated)

    annotated["metadata"] = metadata
    annotated["normalized_pitcher"] = _normalized_pitcher(annotated)
    annotated["current_verdict"] = current_verdict
    annotated["raw_verdict"] = raw_verdict or None
    annotated["final_verdict"] = current_verdict
    annotated["is_fire"] = _is_fire_verdict(current_verdict)
    annotated["is_lean"] = _is_lean_verdict(current_verdict)
    annotated["confidence_referee"] = referee_meta or None
    annotated["confidence_referee_mode"] = referee_meta.get("mode") or "none"
    annotated["confidence_referee_applied"] = referee_meta.get("applied") is True
    annotated["confidence_referee_relationship"] = referee_meta.get("relationship") or "unknown"
    annotated["confidence_referee_would_cap_to"] = referee_meta.get("would_cap_to")
    annotated["movement_agreement_label"] = movement_agreement_label(annotated)
    annotated["movement_value_label"] = movement_value_label(annotated)
    annotated["movement_strength_label"] = movement_strength_label(annotated)
    annotated["max_abs_line_delta"] = max_line_delta
    annotated["max_abs_odds_delta"] = max_odds_delta
    annotated["movement_magnitude_bucket"] = movement_magnitude_bucket(annotated)
    annotated["tracker_bucket"] = _tracker_bucket(annotated)
    return annotated


def extract_current_pick_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []

    rows: list[dict[str, Any]] = []
    if isinstance(payload.get("tracked_picks"), list):
        rows.extend(row for row in payload["tracked_picks"] if isinstance(row, dict))

    for pitcher in payload.get("pitchers") or []:
        if not isinstance(pitcher, dict) or not isinstance(pitcher.get("tracked_picks"), list):
            continue
        rows.extend(row for row in pitcher["tracked_picks"] if isinstance(row, dict))

    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = _pick_key(row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def load_json_payload(path: Path | None) -> Any:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _overlay_current_pick_metadata(
    rows: list[dict[str, Any]],
    current_pick_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    current_by_key = {_pick_key(row): row for row in current_pick_rows}
    merged_rows: list[dict[str, Any]] = []
    overlay_fields = (
        "raw_verdict",
        "actionable_verdict",
        "locked_verdict",
        "quality_gate_level",
        "confidence_referee",
        "verdict_cap_reason",
        "data_maturity",
    )

    for row in rows:
        merged = {**row}
        current = current_by_key.get(_pick_key(row), {})
        for field in overlay_fields:
            if _is_missing(merged.get(field)) and not _is_missing(current.get(field)):
                merged[field] = current.get(field)
        if _is_missing(merged.get("current_verdict")):
            merged["current_verdict"] = (
                current.get("current_verdict")
                or current.get("display_verdict")
                or current.get("locked_verdict")
                or current.get("actionable_verdict")
                or current.get("verdict")
            )
        merged_rows.append(merged)

    return merged_rows


def build_tracker_rows(
    *,
    market_pick_evidence_rows: list[dict[str, Any]],
    live_market_display_rows: list[dict[str, Any]],
    market_snapshot_rows: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
    current_pick_rows: list[dict[str, Any]] | None = None,
    checkpoints_minutes: list[int] | tuple[int, ...] = DEFAULT_CHECKPOINTS_MINUTES,
) -> list[dict[str, Any]]:
    rows = build_rows_from_inputs(
        market_pick_evidence_rows=market_pick_evidence_rows,
        live_market_display_rows=live_market_display_rows,
        market_snapshot_rows=market_snapshot_rows,
        history_rows=history_rows,
        checkpoints_minutes=checkpoints_minutes,
    )
    if current_pick_rows:
        rows = _overlay_current_pick_metadata(rows, current_pick_rows)
    return [annotate_row(row) for row in rows]


def summarize_buckets(
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> dict[tuple[Any, ...], dict[str, Any]]:
    buckets: dict[tuple[Any, ...], dict[str, Any]] = defaultdict(
        lambda: {
            "rows": 0,
            "fire_rows": 0,
            "lean_rows": 0,
            "referee_caps": 0,
            "graded": 0,
            "wins": 0,
            "losses": 0,
            "pnl": 0.0,
            "roi": None,
        }
    )

    for row in rows:
        key = tuple(row.get(field) or "unknown" for field in fields)
        bucket = buckets[key]
        bucket["rows"] += 1
        if row.get("is_fire") is True:
            bucket["fire_rows"] += 1
        if row.get("is_lean") is True:
            bucket["lean_rows"] += 1
        if row.get("confidence_referee_applied") is True:
            bucket["referee_caps"] += 1

        result = row.get("result")
        if result not in {"win", "loss"}:
            continue
        bucket["graded"] += 1
        if result == "win":
            bucket["wins"] += 1
        else:
            bucket["losses"] += 1
        bucket["pnl"] += float(row.get("pnl") or 0.0)

    for bucket in buckets.values():
        bucket["pnl"] = round(bucket["pnl"], 2)
        bucket["roi"] = round(bucket["pnl"] / bucket["graded"], 4) if bucket["graded"] else None

    return dict(sorted(buckets.items()))


def sample_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    graded_rows = [row for row in rows if row.get("result") in {"win", "loss"}]
    bucket_counts: dict[str, int] = defaultdict(int)
    for row in graded_rows:
        bucket_counts[str(row.get("tracker_bucket") or "unknown")] += 1

    bucket_statuses = {
        bucket: {
            "graded_rows": count,
            "status": "review_ready" if count >= BUCKET_GRADED_MIN_ROWS else "watch_only",
        }
        for bucket, count in sorted(bucket_counts.items())
    }

    return {
        "graded_rows": len(graded_rows),
        "overall_min_rows": OVERALL_GRADED_MIN_ROWS,
        "bucket_min_rows": BUCKET_GRADED_MIN_ROWS,
        "overall_status": "review_ready"
        if len(graded_rows) >= OVERALL_GRADED_MIN_ROWS
        else "watch_only",
        "bucket_statuses": bucket_statuses,
    }


def _format_roi(value: float | None) -> str:
    return "--" if value is None else f"{value:+.1%}"


def _render_table(
    lines: list[str],
    *,
    summary: dict[tuple[Any, ...], dict[str, Any]],
    headers: tuple[str, ...],
    max_rows: int = 30,
) -> None:
    lines.append(
        "| "
        + " | ".join(headers)
        + " | Rows | FIRE | LEAN | Ref Caps | Graded | W-L | PnL | ROI |"
    )
    lines.append(
        "| "
        + " | ".join(["---"] * len(headers))
        + " | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    if not summary:
        lines.append(
            "| "
            + " | ".join(["--"] * len(headers))
            + " | 0 | 0 | 0 | 0 | 0 | 0-0 | +0.00 | -- |"
        )
        return

    sorted_rows = sorted(
        summary.items(),
        key=lambda item: (item[1]["graded"], item[1]["rows"]),
        reverse=True,
    )
    for key, bucket in sorted_rows[:max_rows]:
        key_values = [f"`{value}`" for value in key]
        lines.append(
            "| "
            + " | ".join(key_values)
            + f" | {bucket['rows']} | {bucket['fire_rows']} | {bucket['lean_rows']} | "
            + f"{bucket['referee_caps']} | {bucket['graded']} | "
            + f"{bucket['wins']}-{bucket['losses']} | {bucket['pnl']:+.2f} | "
            + f"{_format_roi(bucket['roi'])} |"
        )


def build_report(rows: list[dict[str, Any]], title: str = "Market Agreement Tracker") -> str:
    annotated_rows = [annotate_row(row) for row in rows]
    gate = sample_gate(annotated_rows)
    graded = sum(1 for row in annotated_rows if row.get("result") in {"win", "loss"})
    fire_rows = sum(1 for row in annotated_rows if row.get("is_fire") is True)
    lean_rows = sum(1 for row in annotated_rows if row.get("is_lean") is True)
    referee_caps = sum(1 for row in annotated_rows if row.get("confidence_referee_applied") is True)

    agreement_summary = summarize_buckets(
        annotated_rows,
        (
            "tracker_bucket",
            "movement_agreement_label",
            "movement_strength_label",
            "movement_magnitude_bucket",
        ),
    )
    lean_summary = summarize_buckets(
        [row for row in annotated_rows if row.get("is_lean") is True],
        ("tracker_bucket", "movement_strength_label", "movement_magnitude_bucket"),
    )
    referee_summary = summarize_buckets(
        [row for row in annotated_rows if row.get("confidence_referee_applied") is True],
        (
            "tracker_bucket",
            "confidence_referee_relationship",
            "movement_strength_label",
            "movement_magnitude_bucket",
        ),
    )

    lines = [
        f"# {title}",
        "",
        "Shadow-only: this report does not change picks, locks, thresholds, staking, provider order, notifications, or calibration.",
        "",
        "## Summary",
        "",
        f"- Evidence rows: `{len(annotated_rows)}`",
        f"- FIRE rows: `{fire_rows}`",
        f"- LEAN rows: `{lean_rows}`",
        f"- Confidence-referee applied caps: `{referee_caps}`",
        f"- Graded rows: `{graded}`",
        "",
        "## Sample Gate",
        "",
        f"- Overall status: `{gate['overall_status']}`",
        f"- Movement-backed graded rows: `{gate['graded_rows']}`",
        f"- Minimum overall graded rows: `{gate['overall_min_rows']}`",
        f"- Minimum bucket graded rows: `{gate['bucket_min_rows']}`",
        "- Buckets below the minimum are watch-only even when their PnL looks attractive.",
        "",
        "## Agreement Buckets",
        "",
    ]
    _render_table(
        lines,
        summary=agreement_summary,
        headers=("Tracker Bucket", "Agreement", "Strength", "Magnitude"),
    )

    lines.extend(["", "## LEAN Buckets", ""])
    _render_table(
        lines,
        summary=lean_summary,
        headers=("Tracker Bucket", "Strength", "Magnitude"),
    )

    lines.extend(["", "## Referee Cap Buckets", ""])
    _render_table(
        lines,
        summary=referee_summary,
        headers=("Tracker Bucket", "Referee Relationship", "Strength", "Magnitude"),
    )

    lines.extend([
        "",
        "## Read Rule",
        "",
        "- `movement_agreement_label` asks whether live market movement moved with or against the model side.",
        "- `movement_strength_label` separates broad multi-book support from single-book or reversed noise.",
        "- `movement_magnitude_bucket` separates line moves from small price-only moves.",
        "- Referee-cap buckets are review flags. They do not override the referee or promote LEANs automatically.",
        "- Wait for enough graded slates before treating any bucket as a decision rule.",
    ])
    return "\n".join(lines).rstrip() + "\n"


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _parse_checkpoints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Track market agreement against BBE picks and referee caps."
    )
    parser.add_argument("--history", type=Path, default=HISTORY_PATH)
    parser.add_argument("--market-pick-evidence", type=Path)
    parser.add_argument("--live-market-display", type=Path)
    parser.add_argument("--market-snapshots", type=Path)
    parser.add_argument("--current-artifact", type=Path)
    parser.add_argument("--checkpoints", default="120,60,30,15,5,0")
    parser.add_argument("--output-md", type=Path, default=OUTPUT_MD_PATH)
    parser.add_argument("--output-jsonl", type=Path, default=OUTPUT_JSONL_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    current_payload = load_json_payload(args.current_artifact)
    rows = build_tracker_rows(
        market_pick_evidence_rows=load_json_rows(args.market_pick_evidence),
        live_market_display_rows=load_json_rows(args.live_market_display),
        market_snapshot_rows=load_json_rows(args.market_snapshots),
        history_rows=load_json_rows(args.history),
        current_pick_rows=extract_current_pick_rows(current_payload),
        checkpoints_minutes=_parse_checkpoints(args.checkpoints),
    )
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(build_report(rows), encoding="utf-8")
    write_jsonl(rows, args.output_jsonl)
    print(f"Wrote {args.output_md} and {args.output_jsonl} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
