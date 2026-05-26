"""Compare model and betting performance before and after the 2026-04-28 bump.

This diagnostic is shadow-only. It writes a review report and does not change
live projections, verdicts, thresholds, staking, provider order, notifications,
dashboard artifacts, or calibration.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"
ARCHIVE_DIR = ROOT / "dashboard" / "data" / "processed"
OUTPUT_PATH = ROOT / "analytics" / "output" / "pre_post_428_model_review.md"
PRE_START = "2026-04-08"
PRE_END = "2026-04-27"
POST_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}


def load_history(path: Path = HISTORY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def load_archive_market_rows(archive_dir: Path = ARCHIVE_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(archive_dir.glob("20*.json")):
        date_str = path.stem
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        pitchers = payload.get("pitchers") if isinstance(payload, dict) else None
        if not isinstance(pitchers, list):
            continue
        for pitcher in pitchers:
            if isinstance(pitcher, dict):
                row = dict(pitcher)
                row["date"] = date_str
                rows.append(row)
    return rows


def to_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _projection(row: dict[str, Any]) -> float | None:
    for key in ("applied_lambda", "lambda", "projected_ks", "raw_lambda"):
        value = to_float(row.get(key))
        if value is not None:
            return value
    return None


def _line(row: dict[str, Any]) -> float | None:
    for key in ("locked_k_line", "k_line", "line"):
        value = to_float(row.get(key))
        if value is not None:
            return value
    return None


def _actual(row: dict[str, Any]) -> float | None:
    return to_float(row.get("actual_ks"))


def _date(row: dict[str, Any]) -> str:
    return str(row.get("date") or row.get("slate_date") or "")


def _in_window(row: dict[str, Any], start: str, end: str | None) -> bool:
    date_str = _date(row)
    if not date_str or date_str < start:
        return False
    return end is None or date_str <= end


def _winning_side(row: dict[str, Any]) -> str | None:
    actual = _actual(row)
    line = _line(row)
    if actual is None or line is None:
        return None
    if actual > line:
        return "over"
    if actual < line:
        return "under"
    return None


def _projected_side(row: dict[str, Any]) -> str | None:
    projection = _projection(row)
    line = _line(row)
    if projection is None or line is None:
        return None
    if projection > line:
        return "over"
    if projection < line:
        return "under"
    return None


def _pnl(row: dict[str, Any]) -> float:
    return to_float(row.get("pnl")) or 0.0


def _stake_units(row: dict[str, Any]) -> float:
    explicit = to_float(row.get("stake")) or to_float(row.get("units"))
    if explicit is not None and explicit > 0:
        return explicit
    verdict = _verdict(row).lower()
    return 2.0 if "2u" in verdict else 1.0


def _verdict(row: dict[str, Any]) -> str:
    return str(row.get("locked_verdict") or row.get("actionable_verdict") or row.get("verdict") or "unknown")


def _blank_summary() -> dict[str, Any]:
    return {
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "flat_pnl": 0.0,
        "flat_roi": None,
        "stake_units": 0.0,
        "staked_pnl": 0.0,
        "staked_roi": None,
    }


def _add_pick(summary: dict[str, Any], row: dict[str, Any]) -> None:
    summary["rows"] += 1
    if row.get("result") == "win":
        summary["wins"] += 1
    elif row.get("result") == "loss":
        summary["losses"] += 1
    flat_pnl = _pnl(row)
    stake_units = _stake_units(row)
    summary["flat_pnl"] += flat_pnl
    summary["stake_units"] += stake_units
    summary["staked_pnl"] += flat_pnl * stake_units


def _finish_pick_summary(summary: dict[str, Any]) -> dict[str, Any]:
    summary["flat_pnl"] = round(summary["flat_pnl"], 2)
    summary["stake_units"] = round(summary["stake_units"], 2)
    summary["staked_pnl"] = round(summary["staked_pnl"], 2)
    summary["flat_roi"] = round(summary["flat_pnl"] / summary["rows"], 4) if summary["rows"] else None
    summary["staked_roi"] = (
        round(summary["staked_pnl"] / summary["stake_units"], 4) if summary["stake_units"] else None
    )
    return summary


def _projection_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[float] = []
    side_wins = 0
    side_losses = 0
    by_projected_side: dict[str, dict[str, Any]] = defaultdict(_blank_summary)

    for row in rows:
        projection = _projection(row)
        actual = _actual(row)
        if projection is None or actual is None:
            continue
        errors.append(actual - projection)

        projected_side = _projected_side(row)
        winning_side = _winning_side(row)
        if projected_side and winning_side:
            bucket = by_projected_side[projected_side]
            bucket["rows"] += 1
            if projected_side == winning_side:
                side_wins += 1
                bucket["wins"] += 1
            else:
                side_losses += 1
                bucket["losses"] += 1

    for bucket in by_projected_side.values():
        bucket["roi"] = round(bucket["wins"] / bucket["rows"], 4) if bucket["rows"] else None

    if not errors:
        return {
            "projection_rows": 0,
            "mean_error": None,
            "mae": None,
            "rmse": None,
            "side_wins": 0,
            "side_losses": 0,
            "side_accuracy": None,
            "by_projected_side": dict(by_projected_side),
        }

    side_total = side_wins + side_losses
    return {
        "projection_rows": len(errors),
        "mean_error": round(sum(errors) / len(errors), 3),
        "mae": round(sum(abs(error) for error in errors) / len(errors), 3),
        "rmse": round(math.sqrt(sum(error * error for error in errors) / len(errors)), 3),
        "side_wins": side_wins,
        "side_losses": side_losses,
        "side_accuracy": round(side_wins / side_total, 4) if side_total else None,
        "by_projected_side": dict(by_projected_side),
    }


def summarize_tracked_window(
    history_rows: list[dict[str, Any]],
    start: str,
    end: str | None,
) -> dict[str, Any]:
    rows = [
        row
        for row in history_rows
        if _in_window(row, start, end) and row.get("result") in WIN_LOSS_RESULTS
    ]
    summary = _blank_summary()
    by_side: dict[str, dict[str, Any]] = defaultdict(_blank_summary)
    by_verdict: dict[str, dict[str, Any]] = defaultdict(_blank_summary)
    by_quality: dict[str, dict[str, Any]] = defaultdict(_blank_summary)

    for row in rows:
        _add_pick(summary, row)
        _add_pick(by_side[str(row.get("side") or "unknown").lower()], row)
        _add_pick(by_verdict[_verdict(row)], row)
        _add_pick(by_quality[str(row.get("quality_gate_level") or "unknown")], row)

    _finish_pick_summary(summary)
    for grouped in (by_side, by_verdict, by_quality):
        for item in grouped.values():
            _finish_pick_summary(item)

    projection = _projection_summary(rows)
    summary.update(projection)
    slate_count = len({_date(row) for row in rows if _date(row)})
    summary["slates"] = slate_count
    summary["picks_per_slate"] = round(summary["rows"] / slate_count, 2) if slate_count else None
    summary["by_side"] = dict(by_side)
    summary["by_verdict"] = dict(by_verdict)
    summary["by_quality"] = dict(by_quality)
    return summary


def _market_key(row: dict[str, Any]) -> tuple[str, str, str]:
    line = _line(row)
    return (
        _date(row),
        str(row.get("pitcher") or "").lower(),
        "unknown" if line is None else f"{line:.1f}",
    )


def summarize_market_projection_window(
    market_rows: list[dict[str, Any]],
    start: str,
    end: str | None,
) -> dict[str, Any]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in market_rows:
        if not _in_window(row, start, end):
            continue
        if _projection(row) is None or _actual(row) is None or _line(row) is None:
            continue
        deduped.setdefault(_market_key(row), row)

    rows = list(deduped.values())
    summary = _projection_summary(rows)
    summary["rows"] = len(rows)
    summary["slates"] = len({_date(row) for row in rows if _date(row)})
    summary["markets_per_slate"] = round(summary["rows"] / summary["slates"], 2) if summary["slates"] else None
    return summary


def _fmt_number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "--"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _fmt_roi(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):+.1%}"


def _fmt_error(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):+.3f}"


def _pick_summary_row(label: str, summary: dict[str, Any]) -> str:
    return (
        f"| {label} | {summary['slates']} | {summary['rows']} | "
        f"{_fmt_number(summary['picks_per_slate'])} | {summary['wins']}-{summary['losses']} | "
        f"{summary['flat_pnl']:+.2f} | {_fmt_roi(summary['flat_roi'])} | "
        f"{summary['stake_units']:.0f} | {summary['staked_pnl']:+.2f} | {_fmt_roi(summary['staked_roi'])} | "
        f"{_fmt_error(summary['mean_error'])} | {_fmt_number(summary['mae'], 3)} | "
        f"{_fmt_number(summary['rmse'], 3)} | {_fmt_roi(summary['side_accuracy'])} |"
    )


def _market_summary_row(label: str, summary: dict[str, Any]) -> str:
    return (
        f"| {label} | {summary['slates']} | {summary['rows']} | "
        f"{_fmt_number(summary['markets_per_slate'])} | {_fmt_error(summary['mean_error'])} | "
        f"{_fmt_number(summary['mae'], 3)} | {_fmt_number(summary['rmse'], 3)} | "
        f"{summary['side_wins']}-{summary['side_losses']} | {_fmt_roi(summary['side_accuracy'])} |"
    )


def _group_rows(grouped: dict[str, dict[str, Any]], *, min_rows: int = 1) -> list[str]:
    lines = [
        "| Bucket | Rows | W-L | Flat PnL | Flat ROI | Staked Units | Staked PnL | Staked ROI |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, item in sorted(grouped.items(), key=lambda kv: (-kv[1]["rows"], kv[0])):
        if item["rows"] < min_rows:
            continue
        lines.append(
            f"| `{key}` | {item['rows']} | {item['wins']}-{item['losses']} | "
            f"{item['flat_pnl']:+.2f} | {_fmt_roi(item['flat_roi'])} | "
            f"{item['stake_units']:.0f} | {item['staked_pnl']:+.2f} | {_fmt_roi(item['staked_roi'])} |"
        )
    return lines


def _delta(a: Any, b: Any) -> float | None:
    if a is None or b is None:
        return None
    return round(float(b) - float(a), 4)


def _hard_read(pre_tracked: dict[str, Any], post_tracked: dict[str, Any], pre_market: dict[str, Any], post_market: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    roi_delta = _delta(pre_tracked.get("flat_roi"), post_tracked.get("flat_roi"))
    staked_roi_delta = _delta(pre_tracked.get("staked_roi"), post_tracked.get("staked_roi"))
    mae_delta = _delta(pre_market.get("mae"), post_market.get("mae"))
    side_delta = _delta(pre_market.get("side_accuracy"), post_market.get("side_accuracy"))

    if roi_delta is not None:
        if roi_delta < -0.03:
            lines.append("- Flat selection outcome got materially worse post-bump.")
        elif roi_delta > 0.03:
            lines.append("- Flat selection outcome improved post-bump.")
        else:
            lines.append("- Flat selection outcome is roughly flat post-bump.")
    if staked_roi_delta is not None:
        if staked_roi_delta < -0.03:
            lines.append("- Staked ROI also got materially worse post-bump.")
        elif staked_roi_delta > 0.03:
            lines.append("- Staked ROI improved post-bump.")
        else:
            lines.append("- Staked ROI is roughly flat post-bump.")
    if mae_delta is not None:
        if mae_delta < -0.05:
            lines.append("- Whole-market projection MAE improved post-bump.")
        elif mae_delta > 0.05:
            lines.append("- Whole-market projection MAE worsened post-bump.")
        else:
            lines.append("- Whole-market projection MAE is roughly similar pre/post.")
    if side_delta is not None:
        if side_delta < -0.03:
            lines.append("- Projection side accuracy declined post-bump.")
        elif side_delta > 0.03:
            lines.append("- Projection side accuracy improved post-bump.")
        else:
            lines.append("- Projection side accuracy is roughly similar pre/post.")

    pre_under = pre_tracked.get("by_side", {}).get("under", {})
    post_under = post_tracked.get("by_side", {}).get("under", {})
    pre_over = pre_tracked.get("by_side", {}).get("over", {})
    post_over = post_tracked.get("by_side", {}).get("over", {})
    if pre_under and post_under:
        lines.append(
            f"- Under flat ROI moved from {_fmt_roi(pre_under.get('flat_roi'))} pre-bump to {_fmt_roi(post_under.get('flat_roi'))} post-bump."
        )
    if pre_over and post_over:
        lines.append(
            f"- Over flat ROI moved from {_fmt_roi(pre_over.get('flat_roi'))} pre-bump to {_fmt_roi(post_over.get('flat_roi'))} post-bump."
        )
    return lines


def build_report(
    history_rows: list[dict[str, Any]],
    market_rows: list[dict[str, Any]],
    *,
    post_end: str | None = None,
) -> str:
    pre_tracked = summarize_tracked_window(history_rows, PRE_START, PRE_END)
    post_tracked = summarize_tracked_window(history_rows, POST_START, post_end)
    pre_market = summarize_market_projection_window(market_rows, PRE_START, PRE_END)
    post_market = summarize_market_projection_window(market_rows, POST_START, post_end)

    lines = [
        "# Pre/Post 2026-04-28 Model Review",
        "",
        "Shadow-only: this report does not change live picks, locks, thresholds, staking, provider order, notifications, dashboard artifacts, or calibration.",
        "",
        f"- Generated at: `{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}`",
        f"- Immediate pre-bump window: `{PRE_START}` through `{PRE_END}`",
        f"- Post-bump clean window: `{POST_START}` through `{post_end or 'latest graded'}`",
        "",
        "## Tracked Pick Outcome And Projection",
        "",
        "| Window | Slates | Picks | Picks/Slate | W-L | Flat PnL | Flat ROI | Staked Units | Staked PnL | Staked ROI | Mean Error | MAE | RMSE | Projection Side Accuracy |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        _pick_summary_row("Immediate pre-bump", pre_tracked),
        _pick_summary_row("Post-bump clean", post_tracked),
        "",
        "## Projection Quality",
        "",
        "Whole-market rows use one archived pitcher market per date/pitcher/line, so this reads projection shape separately from which bets were tracked.",
        "",
        "| Window | Slates | Markets | Markets/Slate | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        _market_summary_row("Immediate pre-bump", pre_market),
        _market_summary_row("Post-bump clean", post_market),
        "",
        "## Bet Selection",
        "",
        "### Immediate Pre-Bump By Side",
        "",
        *_group_rows(pre_tracked["by_side"]),
        "",
        "### Post-Bump By Side",
        "",
        *_group_rows(post_tracked["by_side"]),
        "",
        "### Immediate Pre-Bump By Verdict",
        "",
        *_group_rows(pre_tracked["by_verdict"]),
        "",
        "### Post-Bump By Verdict",
        "",
        *_group_rows(post_tracked["by_verdict"]),
        "",
        "## Hard Read",
        "",
        *_hard_read(pre_tracked, post_tracked, pre_market, post_market),
        "",
        "## Decision Boundary",
        "",
        "- No live threshold, staking, calibration, provider, or dashboard behavior changes are made by this report.",
        "- Use this to decide which Gate C/F candidate deserves a separate promotion plan.",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare pre/post 2026-04-28 model performance.")
    parser.add_argument("--history", default=str(HISTORY_PATH))
    parser.add_argument("--archive-dir", default=str(ARCHIVE_DIR))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--post-end")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = build_report(
        load_history(Path(args.history)),
        load_archive_market_rows(Path(args.archive_dir)),
        post_end=args.post_end,
    )
    if not args.no_write:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
