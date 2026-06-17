"""Post-grading audit for market-anchor selector shadow metadata."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "market_anchor_selector_canary_audit.md"
WIN_LOSS_RESULTS = {"win", "loss"}
SELECTOR_SHADOW_DEPLOY_DATE = date(2026, 6, 16)


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _selector(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("market_anchor_selector")
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _labels(row: dict[str, Any]) -> set[str]:
    raw = _selector(row).get("labels") or row.get("market_anchor_selector_labels") or []
    if isinstance(raw, str):
        raw = [raw]
    return {str(label) for label in raw if str(label or "").strip()}


def _is_fire(value: Any) -> bool:
    return str(value or "").startswith("FIRE")


def _row_date(row: dict[str, Any]) -> date | None:
    value = row.get("slate_date") or row.get("game_date") or row.get("date")
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _row_pnl(row: dict[str, Any]) -> float:
    return _to_float(row.get("pick_history_pnl")) or _to_float(row.get("pnl")) or 0.0


def _score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    score = {"rows": 0, "wins": 0, "losses": 0, "pnl": 0.0, "roi": 0.0}
    for row in rows:
        if row.get("result") not in WIN_LOSS_RESULTS:
            continue
        score["rows"] += 1
        if row.get("result") == "win":
            score["wins"] += 1
        else:
            score["losses"] += 1
        score["pnl"] = round(score["pnl"] + _row_pnl(row), 3)
    if score["rows"]:
        score["roi"] = round(score["pnl"] / score["rows"], 4)
    return score


def _tracked(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("is_tracked_pick") is True and row.get("result") in WIN_LOSS_RESULTS
    ]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tracked = _tracked(rows)
    with_selector = [row for row in tracked if _selector(row)]
    fire_rows = [row for row in with_selector if _is_fire(row.get("display_verdict") or row.get("verdict"))]
    strict_fire = [row for row in fire_rows if "market_anchor_strict" in _labels(row)]
    non_strict_fire = [row for row in fire_rows if "market_anchor_strict" not in _labels(row)]
    strict_all = [row for row in with_selector if "market_anchor_strict" in _labels(row)]

    slices: dict[str, dict[str, Any]] = {}
    for field in ("side", "line_bucket", "price_sign", "quality_gate_level", "model_market_relationship"):
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in strict_all:
            buckets[str(row.get(field) or "unknown")].append(row)
        for bucket, bucket_rows in buckets.items():
            if len(bucket_rows) >= 5:
                slices[f"{field}={bucket}"] = _score(bucket_rows)

    row_dates = sorted(row_date for row in rows if (row_date := _row_date(row)) is not None)
    latest_slate_date = row_dates[-1].isoformat() if row_dates else None
    earliest_slate_date = row_dates[0].isoformat() if row_dates else None

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "earliest_slate_date": earliest_slate_date,
        "latest_slate_date": latest_slate_date,
        "selector_shadow_deploy_date": SELECTOR_SHADOW_DEPLOY_DATE.isoformat(),
        "input_stale_for_selector": bool(row_dates and row_dates[-1] < SELECTOR_SHADOW_DEPLOY_DATE),
        "tracked_rows": len(tracked),
        "selector_rows": len(with_selector),
        "fire_rows": _score(fire_rows),
        "strict_fire": _score(strict_fire),
        "non_strict_fire": _score(non_strict_fire),
        "strict_all": _score(strict_all),
        "strict_slices": slices,
    }


def _format_pnl(value: Any) -> str:
    return f"{(_to_float(value) or 0.0):+.2f}"


def _format_roi(value: Any) -> str:
    number = _to_float(value)
    return "--" if number is None else f"{number:+.1%}"


def _score_line(label: str, score: dict[str, Any]) -> str:
    return (
        f"- {label}: `{score['rows']}` rows, `{score['wins']}-{score['losses']}`, "
        f"`{_format_pnl(score['pnl'])}`, `{_format_roi(score['roi'])}` ROI."
    )


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Market Anchor Selector Canary Audit",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.",
        "",
        "## Executive Read",
        "",
        f"- Tracked graded rows: `{summary['tracked_rows']}`",
        f"- Rows with selector metadata: `{summary['selector_rows']}`",
        _score_line("Displayed FIRE with selector metadata", summary["fire_rows"]),
        _score_line("Market-anchor strict displayed FIRE", summary["strict_fire"]),
        _score_line("Non-strict displayed FIRE", summary["non_strict_fire"]),
        _score_line("All market-anchor strict tracked rows", summary["strict_all"]),
        "",
        "## Input Coverage",
        "",
        f"- Slate date range: `{summary.get('earliest_slate_date') or 'unknown'}` to `{summary.get('latest_slate_date') or 'unknown'}`",
        f"- Selector shadow deployment date: `{summary['selector_shadow_deploy_date']}`",
    ]
    if summary.get("input_stale_for_selector"):
        lines.extend(
            [
                "- Warning: Input ends before selector shadow deployment. Refresh the Gate C dataset before interpreting selector rows.",
            ]
        )
    lines.extend(
        [
            "",
            "## Strict Slice Check",
            "",
        ]
    )
    slices = summary.get("strict_slices") or {}
    if not slices:
        lines.append("- No strict slices met the minimum display threshold.")
    else:
        for label, score in sorted(slices.items()):
            lines.append(_score_line(label, score))
    lines.extend(
        [
            "",
            "## Promotion Gate",
            "",
            "- Do not enable `MARKET_ANCHOR_SELECTOR_MODE=enforce_downside` from this report alone.",
            "- A promotion review requires at least `150` clean tracked rows with selector metadata and at least `75` strict rows.",
            "- Strict rows must stay positive after excluding one slate and must survive side, K-line, price, quality, timing, CLV, workload, Path B, provider/source, and market-agreement slices.",
            "- Non-strict FIRE rows must remain clearly worse before any downside-only cap can be considered.",
            "",
        ]
    )
    return "\n".join(lines)


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    report = render_report(summarize(load_rows(args.input)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
