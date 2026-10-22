"""Downgrade-only profit rescue audit for FIRE exposure.

This diagnostic reads the compact Gate C pitcher outcome dataset and estimates
what a runtime-safe, downgrade-only canary would have done to flat 1u FIRE
exposure. It does not change live lambda, verdicts, thresholds, staking,
provider order, notifications, locks, retention, calibration, or dashboard
source-of-truth.
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
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "profit_rescue_audit.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}


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


def _is_fire(verdict: Any) -> bool:
    return str(verdict or "").startswith("FIRE")


def _verdict(row: dict[str, Any]) -> str:
    return str(
        row.get("display_verdict")
        or row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("current_verdict")
        or row.get("verdict")
        or ""
    ).strip()


def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def proposed_rescue_decision(row: dict[str, Any]) -> dict[str, Any]:
    current_verdict = _verdict(row)
    proposed_verdict = current_verdict
    side = str(row.get("side") or "").strip().lower()
    relationship = str(row.get("model_market_relationship") or "").strip()
    reasons: list[str] = []

    if current_verdict == "FIRE 2u":
        proposed_verdict = "FIRE 1u"
        reasons.append("cap_fire_two_to_fire_one")

    if side == "under" and _is_fire(proposed_verdict):
        proposed_verdict = "LEAN"
        reasons.append("cap_fire_under_to_lean")

    if relationship == "model_fades_favorite" and _is_fire(current_verdict):
        reasons.append("cap_market_fade_fire_to_lean")
        if _is_fire(proposed_verdict):
            proposed_verdict = "LEAN"

    if not _is_fire(current_verdict):
        action = "keep_non_fire"
    elif proposed_verdict == current_verdict:
        action = "keep_fire"
    elif _is_fire(proposed_verdict):
        action = "downgrade_fire_two_to_fire_one"
    else:
        action = "downgrade_fire_to_lean"

    return {
        "current_verdict": current_verdict,
        "proposed_verdict": proposed_verdict,
        "action": action,
        "reasons": reasons,
    }


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
    return {"rows": 0, "wins": 0, "losses": 0, "pnl": 0.0, "roi": 0.0}


def _add(bucket: dict[str, Any], row: dict[str, Any]) -> None:
    bucket["rows"] += 1
    if row.get("result") == "win":
        bucket["wins"] += 1
    elif row.get("result") == "loss":
        bucket["losses"] += 1
    bucket["pnl"] = round(float(bucket["pnl"]) + _row_pnl(row), 2)
    bucket["roi"] = round(float(bucket["pnl"]) / int(bucket["rows"]), 4) if bucket["rows"] else 0.0


def _window_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    current_fire = _empty_bucket()
    proposed_fire = _empty_bucket()
    downgraded_to_lean = _empty_bucket()

    for row in rows:
        decision = proposed_rescue_decision(row)
        if _is_fire(decision["current_verdict"]):
            _add(current_fire, row)
            if _is_fire(decision["proposed_verdict"]):
                _add(proposed_fire, row)
            else:
                _add(downgraded_to_lean, row)

    return {
        "rows": len(rows),
        "current_fire": current_fire,
        "proposed_fire": proposed_fire,
        "downgraded_to_lean": downgraded_to_lean,
        "fire_pnl_delta": round(float(proposed_fire["pnl"]) - float(current_fire["pnl"]), 2),
    }


def _summarize_by_action(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(_empty_bucket)
    for row in rows:
        _add(buckets[proposed_rescue_decision(row)["action"]], row)
    return dict(sorted(buckets.items()))


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = analysis_rows(rows)
    dates = [parsed for row in selected if (parsed := _parse_date(row.get("slate_date") or row.get("date")))]
    anchor = max(dates) if dates else None
    windows: dict[str, dict[str, Any]] = {"clean_regime": _window_summary(selected)}

    if anchor is not None:
        for days in (7, 14, 21, 30):
            floor = anchor - timedelta(days=days - 1)
            window_rows = [
                row
                for row in selected
                if (row_date := _parse_date(row.get("slate_date") or row.get("date"))) is not None
                and row_date >= floor
            ]
            windows[f"last_{days}_days"] = _window_summary(window_rows)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "analysis_rows": len(selected),
        "anchor_date": anchor.isoformat() if anchor else None,
        "windows": windows,
        "by_action": _summarize_by_action(selected),
    }


def _format_roi(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:+.1%}"


def _bucket_line(label: str, bucket: dict[str, Any]) -> str:
    return (
        f"| `{label}` | {bucket['rows']} | {bucket['wins']}-{bucket['losses']} | "
        f"{float(bucket['pnl']):+.2f} | {_format_roi(bucket.get('roi'))} |"
    )


def _render_window_table(lines: list[str], windows: dict[str, dict[str, Any]]) -> None:
    lines.extend(
        [
            "## FIRE Exposure Windows",
            "",
            "| Window | Rows | Current FIRE | Current FIRE PnL | Proposed FIRE | Proposed FIRE PnL | Downgraded to LEAN | FIRE PnL Delta |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, summary in windows.items():
        current_fire = summary["current_fire"]
        proposed_fire = summary["proposed_fire"]
        downgraded = summary["downgraded_to_lean"]
        lines.append(
            f"| `{name}` | {summary['rows']} | {current_fire['rows']} | {float(current_fire['pnl']):+.2f} | "
            f"{proposed_fire['rows']} | {float(proposed_fire['pnl']):+.2f} | "
            f"{downgraded['rows']} | {float(summary['fire_pnl_delta']):+.2f} |"
        )
    lines.append("")


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Profit Rescue Audit",
        "",
        f"Generated at: `{summary.get('generated_at', 'unknown')}`",
        f"Anchor date: `{summary.get('anchor_date') or 'unknown'}`",
        "",
        "downgrade-only: this report evaluates the `PROFIT_RESCUE_REFEREE_MODE=shadow|enforce` canary policy and does not change lambda, calibration, global EV thresholds, staking, provider order, notifications, locks, retention, or dashboard source-of-truth.",
        "",
        "## Executive Read",
        "",
        f"- Total source rows: `{summary.get('total_rows', 0)}`",
        f"- Clean tracked win/loss rows analyzed: `{summary.get('analysis_rows', 0)}`",
        "- Proposed policy: cap remaining FIRE 2u to FIRE 1u, cap remaining FIRE unders to LEAN, and cap remaining model-fades-market-favorite FIRE rows to LEAN.",
        "- Read this as a risk-off production canary candidate, not proof that any LEAN should become FIRE.",
        "",
    ]
    _render_window_table(lines, summary.get("windows", {}))
    lines.extend(
        [
            "## Action Buckets",
            "",
            "| Action | Rows | W-L | PnL | ROI |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for action, bucket in summary.get("by_action", {}).items():
        lines.append(_bucket_line(action, bucket))
    lines.append("")
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
