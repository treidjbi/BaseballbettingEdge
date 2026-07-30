"""Offline CLV target rows for evaluating future live-safe process proxies."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.name_utils import normalize


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "analytics" / "output"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _book(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _fresh(row: dict[str, Any]) -> bool:
    return str(row.get("freshness") or "").strip().lower() == "fresh"


def classify_final_clv(row: dict[str, Any]) -> str:
    if row.get("close_eligibility") != "eligible":
        return "unknown"

    lock_line = _number(row.get("lock_line"))
    close_line = _number(row.get("close_line"))
    side = str(row.get("side") or "").lower()
    if lock_line is None or close_line is None:
        return "unknown"
    if side == "over" and close_line > lock_line:
        return "beat_close_line"
    if side == "under" and close_line < lock_line:
        return "beat_close_line"
    if lock_line != close_line:
        return "worse_close_line"
    lock_odds = _number(row.get("lock_odds"))
    close_odds = _number(row.get("close_odds"))
    if lock_odds is None or close_odds is None:
        return "unknown"
    if lock_odds > close_odds:
        return "beat_close_price"
    if lock_odds < close_odds:
        return "worse_close_price"
    return "neutral_close"


def build_target_row(gate_c_row: dict[str, Any], market_rows: list[dict[str, Any]]) -> dict[str, Any]:
    slate_date = str(gate_c_row.get("slate_date") or gate_c_row.get("date") or "").strip()
    display_pitcher = str(gate_c_row.get("pitcher") or gate_c_row.get("player_name") or "").strip()
    normalized_pitcher = str(gate_c_row.get("normalized_pitcher") or normalize(display_pitcher)).strip()
    side = str(gate_c_row.get("side") or "").strip().lower()
    lock_provider = str(gate_c_row.get("lock_provider") or gate_c_row.get("provider") or "").strip().lower()
    lock_book = str(
        gate_c_row.get("lock_book")
        or gate_c_row.get("bet_time_book")
        or gate_c_row.get("bookmaker_title")
        or gate_c_row.get("bookmaker_key")
        or ""
    ).strip()
    lock_line = _number(gate_c_row.get("lock_line"))
    if lock_line is None:
        lock_line = _number(gate_c_row.get("bet_time_line"))
    if lock_line is None:
        lock_line = _number(gate_c_row.get("k_line"))
    lock_odds = _number(gate_c_row.get("lock_odds"))
    if lock_odds is None:
        lock_odds = _number(gate_c_row.get("bet_time_odds"))
    if lock_odds is None:
        lock_odds = _number(gate_c_row.get("american_odds"))

    close_candidates = [
        observation
        for observation in market_rows
        if str(observation.get("observation_type") or "").lower() == "official_close"
        and str(observation.get("side") or "").strip().lower() == side
    ]
    matching_provider = [
        observation
        for observation in close_candidates
        if str(observation.get("provider") or "").strip().lower() == lock_provider
        and _book(observation.get("bookmaker")) == _book(lock_book)
    ]
    close_candidates = matching_provider or close_candidates
    close = next((observation for observation in close_candidates if _number(observation.get("line")) == lock_line), None)
    close = close or (close_candidates[0] if close_candidates else None)
    close_provider = str(close.get("provider") or "").strip().lower() if close else ""
    close_book = _book(close.get("bookmaker")) if close else ""
    eligibility = "missing_close"
    if close:
        if close_provider != lock_provider:
            eligibility = "provider_mismatch"
        elif close_book != _book(lock_book):
            eligibility = "book_mismatch"
        elif not _fresh(close):
            eligibility = "stale_evidence"
        else:
            eligibility = "eligible"
    row = {
        "target_key": f"{slate_date}:{normalized_pitcher}:{side}",
        "slate_date": slate_date,
        "normalized_pitcher": normalized_pitcher,
        "display_pitcher": display_pitcher,
        "side": side,
        "official_lock_reference": gate_c_row.get("official_lock_reference") or gate_c_row.get("dataset_key"),
        "lock_observed_at": gate_c_row.get("locked_at") or gate_c_row.get("bet_time_at"),
        "lock_provider": lock_provider or None,
        "lock_book": lock_book or None,
        "lock_line": lock_line,
        "lock_odds": lock_odds,
        "close_eligibility": eligibility,
        "close_observation_id": close.get("observation_id") if close else None,
        "close_observed_at": close.get("observed_at") if close else None,
        "close_provider": close.get("provider") if close else None,
        "close_book": close.get("bookmaker") if close else None,
        "close_line": _number(close.get("line")) if close else None,
        "close_odds": _number(close.get("american_odds")) if close else None,
        "close_line_match": (
            "same_line"
            if close and _number(close.get("line")) == lock_line
            else ("alternate_line" if close else "unknown")
        ),
    }
    row["final_clv"] = classify_final_clv(row)
    return row


def classify_proxy(row: dict[str, Any]) -> str:
    """Reserve proxy labels for Task 2; Task 1 has no live-safe selector."""
    return "not_evaluated_task_1"


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    deduplicated: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        slate_date = str(row.get("slate_date") or row.get("date") or "").strip()
        display_pitcher = str(row.get("display_pitcher") or row.get("pitcher") or "").strip()
        normalized_pitcher = str(row.get("normalized_pitcher") or normalize(display_pitcher)).strip()
        side = str(row.get("side") or "").strip().lower()
        key = (slate_date, normalized_pitcher, side)
        if key in deduplicated:
            continue
        summarized = {**row}
        summarized["slate_date"] = slate_date
        summarized["normalized_pitcher"] = normalized_pitcher
        summarized["display_pitcher"] = display_pitcher
        summarized["proxy_label"] = classify_proxy(summarized)
        summarized["proxy_selector_inputs"] = {
            "lock_provider": summarized.get("lock_provider"),
            "lock_book": summarized.get("lock_book"),
            "lock_line": summarized.get("lock_line"),
            "lock_odds": summarized.get("lock_odds"),
            "lock_observed_at": summarized.get("lock_observed_at"),
        }
        deduplicated[key] = summarized

    target_rows = list(deduplicated.values())
    return {
        "input_rows": len(rows),
        "duplicate_rows": len(rows) - len(target_rows),
        "rows": target_rows,
        "final_clv_counts": dict(sorted(Counter(str(row.get("final_clv") or "unknown") for row in target_rows).items())),
    }


def render_report(summary: dict[str, Any]) -> str:
    counts = summary.get("final_clv_counts") or {}
    lines = [
        "# CLV Process Target Validation",
        "",
        "This is an offline process target. It does not create a selector, verdict, or pick action.",
        "",
        "`evidence_clv_supported` (277 rows, 155-122, +19.01u, +6.9%) is a process benchmark only.",
        "The most recent 30 rows were -4.64u, so this report makes no performance claim from CLV support.",
        "Final CLV, closing price/line, results, actual Ks, and actual workload remain outcome fields, never proxy-selector inputs.",
        "",
        "## Coverage",
        "",
        f"- Input rows: `{summary.get('input_rows', 0)}`",
        f"- Deduplicated target rows: `{len(summary.get('rows') or [])}`",
        f"- Duplicate rows removed: `{summary.get('duplicate_rows', 0)}`",
        "",
        "## Final CLV Labels",
        "",
    ]
    if counts:
        lines.extend(f"- `{label}`: `{count}`" for label, count in sorted(counts.items()))
    else:
        lines.append("- No target rows")
    return "\n".join(lines) + "\n"


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    if path.suffix.lower() == ".json":
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [row for row in parsed if isinstance(row, dict)]
        if isinstance(parsed, dict):
            return [parsed]
        return []
    rows: list[dict[str, Any]] = []
    for line in content.splitlines():
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build offline CLV process target rows.")
    parser.add_argument("--gate-c-input", type=Path, required=True)
    parser.add_argument("--market-input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    target_rows = [build_target_row(row, _load_json_rows(args.market_input)) for row in _load_json_rows(args.gate_c_input)]
    summary = build_summary(target_rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "clv_process_target_validation.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "clv_process_target_validation.md").write_text(render_report(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
