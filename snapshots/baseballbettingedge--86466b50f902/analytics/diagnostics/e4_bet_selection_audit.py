"""Bet-selection audit helpers for verdict, EV ROI, and edge analysis."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics.e1_regime_map import classify_regime

CLEAN_REGIME = "post_roi_clean"

VERDICT_UNITS = {
    "LEAN": 0.0,
    "FIRE 1u": 1.0,
    "FIRE 2u": 2.0,
}

VERDICT_ORDER = ["PASS", "LEAN", "FIRE 1u", "FIRE 2u", "other"]
ADJ_EV_ORDER = ["<2%", "2-6%", "6-17%", "17%+", "unknown"]
EDGE_ORDER = ["<0%", "0-2%", "2-4%", "4-6%", "6%+", "unknown"]


def load_history() -> list[dict]:
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def stake_units(verdict: str | None) -> float:
    return VERDICT_UNITS.get(verdict or "", 0.0)


def adj_ev_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    value = float(value)
    if value < 0.02:
        return "<2%"
    if value < 0.06:
        return "2-6%"
    if value < 0.17:
        return "6-17%"
    return "17%+"


def edge_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    value = float(value)
    if value < 0.0:
        return "<0%"
    if value < 0.02:
        return "0-2%"
    if value < 0.04:
        return "2-4%"
    if value < 0.06:
        return "4-6%"
    return "6%+"


def verdict_bucket(value: str | None) -> str:
    if value in {"PASS", "LEAN", "FIRE 1u", "FIRE 2u"}:
        return str(value)
    return "other"


def _chosen_verdict(row: dict) -> str | None:
    return row.get("locked_verdict") or row.get("verdict")


def _chosen_adj_ev(row: dict) -> float | None:
    value = row.get("locked_adj_ev")
    if value is None:
        value = row.get("adj_ev")
    return None if value is None else float(value)


def _graded_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("result") in {"win", "loss"}]


def is_clean_window_row(row: dict) -> bool:
    raw_date = row.get("date")
    if raw_date in (None, ""):
        return False
    try:
        return classify_regime(str(raw_date)) == CLEAN_REGIME
    except ValueError:
        return False


def clean_window_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if is_clean_window_row(row)]


def _init_metrics() -> dict[str, float | int | None]:
    return {
        "rows": 0,
        "graded_rows": 0,
        "wins": 0,
        "losses": 0,
        "units_risked": 0.0,
        "weighted_pnl": 0.0,
        "roi": None,
    }


def _summarize(rows: list[dict], bucket_fn) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for row in _graded_rows(rows):
        bucket = bucket_fn(row)
        entry = summary.setdefault(bucket, _init_metrics())
        entry["rows"] += 1
        entry["graded_rows"] += 1
        if row.get("result") == "win":
            entry["wins"] += 1
        elif row.get("result") == "loss":
            entry["losses"] += 1

        units = stake_units(_chosen_verdict(row))
        pnl = float(row.get("pnl") or 0.0) * units
        entry["units_risked"] += units
        entry["weighted_pnl"] += pnl

    for entry in summary.values():
        if entry["units_risked"] > 0:
            entry["roi"] = entry["weighted_pnl"] / entry["units_risked"]
        entry["units_risked"] = round(entry["units_risked"], 2)
        entry["weighted_pnl"] = round(entry["weighted_pnl"], 2)
        if entry["roi"] is not None:
            entry["roi"] = round(entry["roi"], 4)
    return summary


def summarize_by_verdict(rows: list[dict]) -> dict[str, dict]:
    return _summarize(rows, lambda row: verdict_bucket(_chosen_verdict(row)))


def summarize_by_adj_ev_bucket(rows: list[dict]) -> dict[str, dict]:
    return _summarize(rows, lambda row: adj_ev_bucket(_chosen_adj_ev(row)))


def summarize_by_edge_bucket(rows: list[dict]) -> dict[str, dict]:
    return _summarize(rows, lambda row: edge_bucket(
        None if row.get("edge") is None else float(row.get("edge"))
    ))


def _render_summary_group(lines: list[str], rows: list[dict]) -> None:
    if not _graded_rows(rows):
        lines.append("- No graded rows in this section yet.")
        return

    verdict_summary = summarize_by_verdict(rows)
    adj_ev_summary = summarize_by_adj_ev_bucket(rows)
    edge_summary = summarize_by_edge_bucket(rows)

    lines.extend(["", "### By Verdict", ""])
    for bucket in VERDICT_ORDER:
        if bucket not in verdict_summary:
            continue
        row = verdict_summary[bucket]
        roi = "--" if row["roi"] is None else f"{row['roi']:+.2%}"
        lines.append(
            f"- `{bucket}`: graded={row['graded_rows']}, wins={row['wins']}, losses={row['losses']}, units={row['units_risked']:.1f}, weighted_pnl={row['weighted_pnl']:+.2f}, roi={roi}"
        )

    lines.extend(["", "### By Adjusted EV ROI Bucket", ""])
    for bucket in ADJ_EV_ORDER:
        if bucket not in adj_ev_summary:
            continue
        row = adj_ev_summary[bucket]
        roi = "--" if row["roi"] is None else f"{row['roi']:+.2%}"
        lines.append(
            f"- `{bucket}`: graded={row['graded_rows']}, wins={row['wins']}, losses={row['losses']}, units={row['units_risked']:.1f}, weighted_pnl={row['weighted_pnl']:+.2f}, roi={roi}"
        )

    lines.extend(["", "### By Edge Bucket", ""])
    for bucket in EDGE_ORDER:
        if bucket not in edge_summary:
            continue
        row = edge_summary[bucket]
        roi = "--" if row["roi"] is None else f"{row['roi']:+.2%}"
        lines.append(
            f"- `{bucket}`: graded={row['graded_rows']}, wins={row['wins']}, losses={row['losses']}, units={row['units_risked']:.1f}, weighted_pnl={row['weighted_pnl']:+.2f}, roi={roi}"
        )


def build_bet_selection_report(rows: list[dict]) -> str:
    clean_rows = clean_window_rows(rows)

    lines = [
        "# E4 Bet Selection Audit",
        "",
        "This audit keeps projection quality separate from bet conversion. It asks whether verdicts, EV ROI tiers, and edge tiers are turning into the right staked decisions.",
        "",
        "## Clean Post-ROI Window (2026-04-28+)",
        "",
        "Current decision reads use only rows classified as `post_roi_clean` by E1.",
    ]
    _render_summary_group(lines, clean_rows)

    lines.extend(
        [
            "",
            "## All-History Context",
            "",
            "This section keeps older and transition regimes visible as context, but it should not drive current clean-window decisions.",
        ]
    )
    _render_summary_group(lines, rows)

    lines.extend(
        [
            "",
            "## Decision Framing",
            "",
            "- If higher adjusted EV ROI buckets are not earning better realized ROI, the ranking/staking conversion is not trustworthy yet.",
            "- If edge buckets separate better than adjusted EV ROI buckets, probability-gap ranking may still be more informative than current ROI conversion.",
            "- If `FIRE 2u` does not clearly outperform `FIRE 1u`, the stake ladder should be reconsidered before more threshold tweaking.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    print(build_bet_selection_report(load_history()))


if __name__ == "__main__":
    main()
