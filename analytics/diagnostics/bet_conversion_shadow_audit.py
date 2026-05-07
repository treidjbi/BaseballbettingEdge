"""Shadow audit for bet-conversion and selection signals.

This diagnostic is analysis-only. It does not change live projections,
verdicts, thresholds, staking, provider order, or calibration.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
PROJECTION_KEYS = ("applied_lambda", "raw_lambda", "lambda", "projected_ks")


def load_history(path: Path = HISTORY_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clean_win_loss_rows(rows: list[dict]) -> list[dict]:
    return [
        row
        for row in rows
        if str(row.get("date") or "") >= CLEAN_WINDOW_START
        and row.get("result") in WIN_LOSS_RESULTS
    ]


def current_verdict(row: dict) -> str:
    return str(
        row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("verdict")
        or ""
    )


def current_adj_ev(row: dict) -> float | None:
    locked = to_float(row.get("locked_adj_ev"))
    if locked is not None:
        return locked
    return to_float(row.get("adj_ev"))


def current_projection(row: dict) -> float | None:
    for key in PROJECTION_KEYS:
        value = to_float(row.get(key))
        if value is not None:
            return value
    return None


def current_line(row: dict) -> float | None:
    locked = to_float(row.get("locked_k_line"))
    if locked is not None:
        return locked
    value = to_float(row.get("k_line"))
    if value is not None:
        return value
    return to_float(row.get("line"))


def picked_side_model_margin(row: dict) -> float | None:
    projection = current_projection(row)
    line = current_line(row)
    side = str(row.get("side") or "").lower()
    if projection is None or line is None:
        return None
    if side == "over":
        return round(projection - line, 3)
    if side == "under":
        return round(line - projection, 3)
    return None


def _is_current_fire(row: dict) -> bool:
    return current_verdict(row).startswith("FIRE")


def _edge(row: dict) -> float | None:
    return to_float(row.get("edge"))


def summarize_strategy(
    name: str,
    rows: list[dict],
    predicate: Callable[[dict], bool],
) -> dict:
    selected = [row for row in rows if predicate(row)]
    wins = sum(1 for row in selected if row.get("result") == "win")
    losses = sum(1 for row in selected if row.get("result") == "loss")
    flat_pnl = round(sum(float(row.get("pnl") or 0.0) for row in selected), 2)
    flat_units = float(len(selected))
    flat_roi = round(flat_pnl / flat_units, 4) if flat_units else None

    return {
        "name": name,
        "selected": len(selected),
        "wins": wins,
        "losses": losses,
        "flat_units": flat_units,
        "flat_pnl": flat_pnl,
        "flat_roi": flat_roi,
        "current_fire_1u_losses_selected": sum(
            1
            for row in selected
            if current_verdict(row) == "FIRE 1u" and row.get("result") == "loss"
        ),
        "current_fire_2u_wins_selected": sum(
            1
            for row in selected
            if current_verdict(row) == "FIRE 2u" and row.get("result") == "win"
        ),
    }


def _between(value: float | None, lower: float, upper: float) -> bool:
    return value is not None and lower <= value < upper


def _at_least(value: float | None, lower: float) -> bool:
    return value is not None and value >= lower


def default_strategy_predicates() -> list[tuple[str, Callable[[dict], bool]]]:
    return [
        ("current_fire_flat", _is_current_fire),
        (
            "current_fire_over",
            lambda row: _is_current_fire(row) and str(row.get("side") or "").lower() == "over",
        ),
        (
            "current_fire_under",
            lambda row: _is_current_fire(row) and str(row.get("side") or "").lower() == "under",
        ),
        ("adj_ev_6_to_17", lambda row: _between(current_adj_ev(row), 0.06, 0.17)),
        ("adj_ev_17_plus", lambda row: _at_least(current_adj_ev(row), 0.17)),
        ("edge_2_to_4", lambda row: _between(_edge(row), 0.02, 0.04)),
        ("edge_4_to_6", lambda row: _between(_edge(row), 0.04, 0.06)),
        ("edge_6_plus", lambda row: _at_least(_edge(row), 0.06)),
        (
            "model_margin_0_to_0_75",
            lambda row: _between(picked_side_model_margin(row), 0.0, 0.75),
        ),
        (
            "model_margin_0_75_to_1_5",
            lambda row: _between(picked_side_model_margin(row), 0.75, 1.5),
        ),
        (
            "model_margin_1_5_plus",
            lambda row: _at_least(picked_side_model_margin(row), 1.5),
        ),
        (
            "clean_quality_fire",
            lambda row: _is_current_fire(row) and row.get("quality_gate_level") == "clean",
        ),
        (
            "capped_quality_fire",
            lambda row: _is_current_fire(row) and row.get("quality_gate_level") == "capped",
        ),
    ]


def build_strategy_summaries(rows: list[dict]) -> list[dict]:
    clean_rows = clean_win_loss_rows(rows)
    return [
        summarize_strategy(name, clean_rows, predicate)
        for name, predicate in default_strategy_predicates()
    ]


def _format_roi(value: float | None) -> str:
    return "--" if value is None else f"{value:+.1%}"


def _format_strategy_row(summary: dict) -> str:
    return (
        f"| `{summary['name']}` | {summary['selected']} | "
        f"{summary['wins']}-{summary['losses']} | "
        f"{summary['flat_pnl']:+.2f} | {_format_roi(summary['flat_roi'])} | "
        f"{summary['current_fire_1u_losses_selected']} | "
        f"{summary['current_fire_2u_wins_selected']} |"
    )


def build_report(rows: list[dict]) -> str:
    clean_rows = clean_win_loss_rows(rows)
    summaries = build_strategy_summaries(rows)
    current_fire = next(
        row for row in summaries if row["name"] == "current_fire_flat"
    )
    over_fire = next(row for row in summaries if row["name"] == "current_fire_over")
    under_fire = next(row for row in summaries if row["name"] == "current_fire_under")

    lines = [
        "# Bet Conversion Shadow Audit",
        "",
        "This audit is shadow-only. It does not change live lambda, verdicts, thresholds, staking, provider order, pick seeding, or calibration.",
        "",
        "## Scope",
        "",
        f"- Clean window start: `{CLEAN_WINDOW_START}`",
        f"- Clean win/loss rows: `{len(clean_rows)}`",
        f"- Current FIRE flat-selection rows: `{current_fire['selected']}`",
        f"- Current FIRE 1u losses captured by current FIRE selection: `{current_fire['current_fire_1u_losses_selected']}`",
        f"- Current FIRE 2u wins captured by current FIRE selection: `{current_fire['current_fire_2u_wins_selected']}`",
        "",
        "## Strategy Comparison",
        "",
        "All strategy rows use flat 1u shadow accounting so selection quality is not mixed with staking size.",
        "",
        "| Strategy | Selected | W-L | Flat PnL | Flat ROI | FIRE 1u Losses Selected | FIRE 2u Wins Selected |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(_format_strategy_row(summary) for summary in summaries)

    lines.extend(
        [
            "",
            "## Side-Specific Warning",
            "",
            f"- Current FIRE over slice: selected={over_fire['selected']}, W-L={over_fire['wins']}-{over_fire['losses']}, flat_roi={_format_roi(over_fire['flat_roi'])}.",
            f"- Current FIRE under slice: selected={under_fire['selected']}, W-L={under_fire['wins']}-{under_fire['losses']}, flat_roi={_format_roi(under_fire['flat_roi'])}.",
            "- Read this beside E3 residuals. If side residuals and side ROI point the same direction after more rows, side conversion becomes the first live-change candidate.",
            "",
            "## Recommended Next Read",
            "",
            "- Keep this diagnostic shadow-only until Gate C is open.",
            "- Look for a strategy that avoids a meaningful share of current FIRE 1u losses while retaining most current FIRE 2u wins.",
            "- Do not promote a strategy from one positive ROI bucket unless it also makes baseball sense and does not simply cherry-pick a tiny sample.",
            "- If edge or model-margin buckets continue to beat adjusted EV buckets, write the Gate C plan around replacing or tempering adjusted-EV ranking.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    print(build_report(load_history()))


if __name__ == "__main__":
    main()
