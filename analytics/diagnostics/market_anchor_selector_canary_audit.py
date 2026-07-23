"""Post-grading audit for market-anchor selector shadow metadata."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from analytics.diagnostics import gate_f_preclose_clv_proxy_lab as preclose_proxy
from analytics.diagnostics import strong_base_decision_lab as strong_base


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "market_anchor_selector_canary_audit.md"
WIN_LOSS_RESULTS = {"win", "loss"}
SELECTOR_SHADOW_DEPLOY_DATE = date(2026, 6, 16)
CURRENT_PROVIDER_START_DATE = date(2026, 6, 24)
REVIEW_CLEAN_SELECTOR_FLOOR = 150
REVIEW_STRICT_FLOOR = 75
RECENT_SLATE_COUNT = 14
MANDATORY_SLICE_DIMENSIONS = (
    "side",
    "k_line",
    "price_sign",
    "quality",
    "timing",
    "final_clv",
    "preclose_clv_proxy",
    "workload",
    "path_b",
    "provider",
    "provider_era",
    "market_agreement",
    "model_market",
)


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


def _text_or_missing(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or "missing"


def _k_line_bucket(row: dict[str, Any]) -> str:
    existing = str(row.get("line_bucket") or "").strip()
    if existing:
        return existing
    k_line = _to_float(row.get("k_line"))
    if k_line is None:
        return "missing"
    return f"{k_line:g}"


def _price_sign(row: dict[str, Any]) -> str:
    existing = _text_or_missing(row.get("price_sign"))
    if existing != "missing":
        return existing
    odds = _to_float(
        row.get("locked_odds")
        if row.get("locked_odds") is not None
        else row.get("american_odds")
    )
    if odds is None:
        return "missing"
    return "plus" if odds > 0 else "minus"


def _slice_bucket(row: dict[str, Any], dimension: str) -> str:
    if dimension == "side":
        return _text_or_missing(row.get("side"))
    if dimension == "k_line":
        return _k_line_bucket(row)
    if dimension == "price_sign":
        return _price_sign(row)
    if dimension == "quality":
        return _text_or_missing(row.get("quality_gate_level"))
    if dimension == "timing":
        return _text_or_missing(row.get("bet_timing_window"))
    if dimension == "final_clv":
        return strong_base.clv_bucket(row)
    if dimension == "preclose_clv_proxy":
        return _text_or_missing(preclose_proxy.preclose_clv_proxy_label(row))
    if dimension == "workload":
        return _text_or_missing(
            row.get("leash_risk_bucket") or row.get("opportunity_bucket")
        )
    if dimension == "path_b":
        return strong_base.path_b_coverage_bucket(row)
    if dimension == "provider":
        return _text_or_missing(
            row.get("provider")
            or row.get("live_display_provider")
            or row.get("odds_source")
        )
    if dimension == "provider_era":
        return strong_base.provider_era(row)
    if dimension == "market_agreement":
        return _text_or_missing(row.get("market_agreement_label"))
    if dimension == "model_market":
        return _text_or_missing(row.get("model_market_relationship"))
    raise ValueError(f"unsupported slice dimension: {dimension}")


def _slice_scores(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    slices: dict[str, dict[str, dict[str, Any]]] = {}
    for dimension in MANDATORY_SLICE_DIMENSIONS:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            buckets[_slice_bucket(row, dimension)].append(row)
        slices[dimension] = {
            bucket: _score(bucket_rows)
            for bucket, bucket_rows in sorted(buckets.items())
        }
    return slices


def _recent_slate_dates(rows: list[dict[str, Any]]) -> set[date]:
    dates = sorted(
        {
            row_date
            for row in rows
            if (row_date := _row_date(row)) is not None
        }
    )
    return set(dates[-RECENT_SLATE_COUNT:])


def _window_scores(
    rows: list[dict[str, Any]],
    *,
    recent_slate_dates: set[date],
) -> dict[str, dict[str, Any]]:
    return {
        "all": _score(rows),
        "current_provider": _score(
            [
                row
                for row in rows
                if (row_date := _row_date(row)) is not None
                and row_date >= CURRENT_PROVIDER_START_DATE
            ]
        ),
        "recent_14_slates": _score(
            [row for row in rows if _row_date(row) in recent_slate_dates]
        ),
    }


def _leave_one_slate_out(rows: list[dict[str, Any]]) -> dict[str, Any]:
    slate_dates = sorted(
        {
            row_date
            for row in rows
            if (row_date := _row_date(row)) is not None
        }
    )
    cases: list[dict[str, Any]] = []
    for excluded_date in slate_dates:
        case = {
            "excluded_slate_date": excluded_date.isoformat(),
            **_score([row for row in rows if _row_date(row) != excluded_date]),
        }
        cases.append(case)
    empty_case = {"excluded_slate_date": None, **_score([])}
    return {
        "cases": cases,
        "minimum": min(cases, key=lambda item: (item["pnl"], item["roi"]))
        if cases
        else empty_case,
        "maximum": max(cases, key=lambda item: (item["pnl"], item["roi"]))
        if cases
        else empty_case,
    }


def _missing_coverage(
    slices: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, int]:
    return {
        dimension: int((buckets.get("missing") or {}).get("rows", 0))
        for dimension, buckets in slices.items()
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tracked = _tracked(rows)
    with_selector = [row for row in tracked if _selector(row)]
    clean_selector_rows = sum(
        1
        for row in with_selector
        if _text_or_missing(row.get("quality_gate_level")) == "clean"
    )
    fire_rows = [
        row
        for row in with_selector
        if _is_fire(row.get("display_verdict") or row.get("verdict"))
    ]
    strict_fire = [row for row in fire_rows if "market_anchor_strict" in _labels(row)]
    non_strict_fire = [row for row in fire_rows if "market_anchor_strict" not in _labels(row)]
    strict_all = [row for row in with_selector if "market_anchor_strict" in _labels(row)]
    strict_slices = _slice_scores(strict_all)
    strict_fire_slices = _slice_scores(strict_fire)
    recent_slate_dates = _recent_slate_dates(strict_all)
    strict_leave_one_out = _leave_one_slate_out(strict_all)
    strict_fire_leave_one_out = _leave_one_slate_out(strict_fire)
    strict_all_score = _score(strict_all)

    row_dates = sorted(row_date for row in rows if (row_date := _row_date(row)) is not None)
    latest_slate_date = row_dates[-1].isoformat() if row_dates else None
    earliest_slate_date = row_dates[0].isoformat() if row_dates else None
    review_status = (
        "separate_shadow_review_ready"
        if clean_selector_rows >= REVIEW_CLEAN_SELECTOR_FLOOR
        and strict_all_score["rows"] >= REVIEW_STRICT_FLOOR
        and strict_leave_one_out["minimum"]["pnl"] > 0
        else "collecting"
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "earliest_slate_date": earliest_slate_date,
        "latest_slate_date": latest_slate_date,
        "selector_shadow_deploy_date": SELECTOR_SHADOW_DEPLOY_DATE.isoformat(),
        "input_stale_for_selector": bool(row_dates and row_dates[-1] < SELECTOR_SHADOW_DEPLOY_DATE),
        "tracked_rows": len(tracked),
        "selector_rows": len(with_selector),
        "clean_selector_rows": clean_selector_rows,
        "review_status": review_status,
        "fire_rows": _score(fire_rows),
        "strict_fire": _score(strict_fire),
        "non_strict_fire": _score(non_strict_fire),
        "strict_all": strict_all_score,
        "strict_windows": _window_scores(
            strict_all,
            recent_slate_dates=recent_slate_dates,
        ),
        "strict_fire_windows": _window_scores(
            strict_fire,
            recent_slate_dates=recent_slate_dates,
        ),
        "strict_slices": strict_slices,
        "strict_fire_slices": strict_fire_slices,
        "missing_coverage_counts": {
            "strict_all": _missing_coverage(strict_slices),
            "strict_fire": _missing_coverage(strict_fire_slices),
        },
        "leave_one_slate_out": {
            "strict_all": strict_leave_one_out,
            "strict_fire": strict_fire_leave_one_out,
        },
        "strict_fire_all_over": bool(strict_fire)
        and all(_text_or_missing(row.get("side")) == "over" for row in strict_fire),
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


def _window_lines(label: str, windows: dict[str, dict[str, Any]]) -> list[str]:
    lines = [f"### {label}", ""]
    for window in ("all", "current_provider", "recent_14_slates"):
        lines.append(_score_line(window.replace("_", " ").title(), windows[window]))
    return lines


def _slice_lines(
    label: str,
    slices: dict[str, dict[str, dict[str, Any]]],
) -> list[str]:
    lines = [f"### {label}", ""]
    for dimension in MANDATORY_SLICE_DIMENSIONS:
        lines.extend([f"#### {dimension}", ""])
        buckets = slices.get(dimension) or {}
        if not buckets:
            lines.append("- No rows.")
            continue
        for bucket, score in sorted(buckets.items()):
            lines.append(_score_line(f"`{bucket}`", score))
        lines.append("")
    return lines


def _leave_one_out_lines(label: str, result: dict[str, Any]) -> list[str]:
    minimum = result["minimum"]
    maximum = result["maximum"]
    return [
        f"### {label}",
        "",
        _score_line(
            f"Minimum after excluding `{minimum.get('excluded_slate_date') or 'none'}`",
            minimum,
        ),
        _score_line(
            f"Maximum after excluding `{maximum.get('excluded_slate_date') or 'none'}`",
            maximum,
        ),
    ]


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
        f"- Review status: `{summary['review_status']}`.",
        f"- Tracked graded rows: `{summary['tracked_rows']}`",
        f"- Rows with selector metadata: `{summary['selector_rows']}`",
        f"- Clean rows with selector metadata: `{summary['clean_selector_rows']}`",
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
            "## Review Floors And Windows",
            "",
            f"- The raw review floors are `{REVIEW_CLEAN_SELECTOR_FLOOR}` clean selector rows and `{REVIEW_STRICT_FLOOR}` strict rows.",
            "- Clearing raw review floors opens a separate shadow review only; it is not promotion approval.",
        ]
    )
    lines.extend(_window_lines("All Strict Rows", summary["strict_windows"]))
    lines.extend([""])
    lines.extend(
        _window_lines("Strict Displayed FIRE Rows", summary["strict_fire_windows"])
    )
    lines.extend(
        [
            "",
            "## Strict Displayed FIRE Concentration",
            "",
        ]
    )
    if summary.get("strict_fire_all_over"):
        lines.append(
            "- Strict displayed FIRE is all `OVER`; the result is concentrated, not side-balanced."
        )
    else:
        lines.append("- Strict displayed FIRE rows are not all `OVER`.")
    lines.extend(["", "## Mandatory Strict Slices", ""])
    lines.extend(_slice_lines("All Strict Rows", summary["strict_slices"]))
    lines.extend(_slice_lines("Strict Displayed FIRE Rows", summary["strict_fire_slices"]))
    lines.extend(["", "## Leave-One-Slate-Out", ""])
    lines.extend(
        _leave_one_out_lines(
            "All Strict Rows",
            summary["leave_one_slate_out"]["strict_all"],
        )
    )
    lines.extend([""])
    lines.extend(
        _leave_one_out_lines(
            "Strict Displayed FIRE Rows",
            summary["leave_one_slate_out"]["strict_fire"],
        )
    )
    negative_slices: list[str] = []
    for dimension, buckets in summary["strict_slices"].items():
        for bucket, score in buckets.items():
            if score["rows"] and score["pnl"] < 0:
                negative_slices.append(f"{dimension}={bucket}")
    missing_counts = summary["missing_coverage_counts"]["strict_all"]
    missing_labels = [
        f"{dimension}={count}"
        for dimension, count in missing_counts.items()
        if count
    ]
    lines.extend(
        [
            "",
            "## Blocking Evidence",
            "",
            (
                "- Negative strict slices: "
                + (", ".join(f"`{label}`" for label in negative_slices) or "none")
                + "."
            ),
            (
                "- Missing strict coverage: "
                + (", ".join(f"`{label}`" for label in missing_labels) or "none")
                + "."
            ),
            "- Side concentration, negative slices, or missing coverage remain blockers even when raw review floors are met.",
            "",
            "## Promotion Gate",
            "",
            "- `enforce_downside` remains closed; keep `MARKET_ANCHOR_SELECTOR_MODE=shadow`.",
            "- Strict rows must stay positive after excluding one slate and must survive side, K-line, price, quality, timing, CLV, workload, Path B, provider/source, and market-agreement slices.",
            "- Non-strict FIRE rows must remain clearly worse before any downside-only cap can be considered.",
            "- Any narrowed OVER-only candidate requires a new selector id, fingerprint, baseline, plan, and prospective canary.",
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
