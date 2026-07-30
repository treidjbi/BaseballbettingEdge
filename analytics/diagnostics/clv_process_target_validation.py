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


def _slate_date(row: dict[str, Any]) -> str:
    return str(row.get("slate_date") or row.get("date") or "").strip()


def _normalized_pitcher(row: dict[str, Any]) -> str:
    return normalize(str(row.get("normalized_pitcher") or row.get("pitcher") or row.get("player_name") or ""))


def _event_identity(row: dict[str, Any]) -> str:
    for key in ("provider_event_id", "event_id", "game_id", "game_pk"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _same_identity(lock_row: dict[str, Any], close_row: dict[str, Any]) -> bool:
    lock_date = _slate_date(lock_row)
    close_date = _slate_date(close_row)
    lock_pitcher = _normalized_pitcher(lock_row)
    close_pitcher = _normalized_pitcher(close_row)
    lock_side = str(lock_row.get("side") or "").strip().lower()
    close_side = str(close_row.get("side") or "").strip().lower()
    if not all((lock_date, close_date, lock_pitcher, close_pitcher, lock_side, close_side)):
        return False
    if (lock_date, lock_pitcher, lock_side) != (close_date, close_pitcher, close_side):
        return False
    lock_event = _event_identity(lock_row)
    close_event = _event_identity(close_row)
    return not (lock_event and close_event and lock_event != close_event)


def _same_line(lock_line: float | None, close_line: float | None) -> bool:
    return lock_line is not None and close_line is not None and lock_line == close_line


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
    slate_date = _slate_date(gate_c_row)
    display_pitcher = str(
        gate_c_row.get("pitcher") or gate_c_row.get("player_name") or gate_c_row.get("normalized_pitcher") or ""
    ).strip()
    normalized_pitcher = _normalized_pitcher(gate_c_row)
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

    close_observations = [
        observation
        for observation in market_rows
        if str(observation.get("observation_type") or "").lower() == "official_close"
    ]
    close_candidates = [observation for observation in close_observations if _same_identity(gate_c_row, observation)]
    matching_provider = [
        observation
        for observation in close_candidates
        if lock_provider
        and _book(lock_book)
        and str(observation.get("provider") or "").strip().lower() == lock_provider
        and _book(observation.get("bookmaker")) == _book(lock_book)
    ]
    close_candidates = matching_provider or close_candidates
    close = next(
        (observation for observation in close_candidates if _same_line(lock_line, _number(observation.get("line")))),
        None,
    )
    close = close or (close_candidates[0] if close_candidates else None)
    close_provider = str(close.get("provider") or "").strip().lower() if close else ""
    close_book = _book(close.get("bookmaker")) if close else ""
    close_line = _number(close.get("line")) if close else None
    eligibility = "identity_mismatch" if close_observations else "missing_close"
    if close:
        if not lock_provider:
            eligibility = "missing_lock_provider"
        elif not close_provider:
            eligibility = "missing_close_provider"
        elif close_provider != lock_provider:
            eligibility = "provider_mismatch"
        elif not _book(lock_book):
            eligibility = "missing_lock_book"
        elif not close_book:
            eligibility = "missing_close_book"
        elif close_book != _book(lock_book):
            eligibility = "book_mismatch"
        elif not (gate_c_row.get("locked_at") or gate_c_row.get("bet_time_at")):
            eligibility = "missing_lock_timestamp"
        elif not close.get("observed_at"):
            eligibility = "missing_close_timestamp"
        elif lock_line is None:
            eligibility = "missing_lock_line"
        elif close_line is None:
            eligibility = "missing_close_line"
        elif close.get("freshness") is None or str(close.get("freshness")).strip() == "":
            eligibility = "missing_close_freshness"
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
        "close_line": close_line,
        "close_odds": _number(close.get("american_odds")) if close else None,
        "close_freshness": close.get("freshness") if close else None,
        "close_line_match": (
            "same_line"
            if close and _same_line(lock_line, close_line)
            else ("alternate_line" if close and lock_line is not None and close_line is not None else "unknown")
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
        slate_date = _slate_date(row)
        display_pitcher = str(row.get("display_pitcher") or row.get("pitcher") or row.get("normalized_pitcher") or "").strip()
        normalized_pitcher = _normalized_pitcher(row)
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
