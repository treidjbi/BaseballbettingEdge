"""Map picks-history rows into evaluation regimes and summarize field coverage."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HISTORY_PATH = ROOT / "data" / "picks_history.json"

REGIME_ORDER = [
    "pre_2026_04_08",
    "phase_a_to_pre_swstr_live",
    "swstr_roi_transition",
    "post_roi_clean",
]

REGIME_LABELS = {
    "pre_2026_04_08": "Pre-2026-04-08",
    "phase_a_to_pre_swstr_live": "2026-04-08 through 2026-04-23",
    "swstr_roi_transition": "2026-04-24 through 2026-04-27",
    "post_roi_clean": "2026-04-28+",
}

FIELD_PRESENCE_KEYS = [
    "pitcher_throws",
    "career_swstr_pct",
    "swstr_delta_k9",
    "park_factor",
    "days_since_last_start",
    "last_pitch_count",
    "rest_k9_delta",
    "opening_odds_source",
    "edge",
]


def classify_regime(date_str: str) -> str:
    """Return the evaluation regime for an ISO date string."""
    parsed_date = date.fromisoformat(date_str)

    if parsed_date < date(2026, 4, 8):
        return "pre_2026_04_08"
    if parsed_date <= date(2026, 4, 23):
        return "phase_a_to_pre_swstr_live"
    if parsed_date <= date(2026, 4, 27):
        return "swstr_roi_transition"
    return "post_roi_clean"


def load_history() -> list[dict]:
    """Load picks history from the canonical JSON file."""
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def summarize_regimes(rows: list[dict]) -> dict:
    """Aggregate counts and presence rates by evaluation regime."""
    summary = {
        regime: {
            "row_count": 0,
            "graded_row_count": 0,
            "locked_row_count": 0,
            "data_complete_count": 0,
            "data_complete_rate": 0.0,
            "field_presence_counts": {field: 0 for field in FIELD_PRESENCE_KEYS},
            "field_presence_rates": {field: 0.0 for field in FIELD_PRESENCE_KEYS},
        }
        for regime in REGIME_ORDER
    }

    for row in rows:
        raw_date = row.get("date")
        if raw_date in (None, ""):
            continue

        regime = classify_regime(raw_date)
        bucket = summary[regime]
        bucket["row_count"] += 1

        if row.get("actual_ks") is not None:
            bucket["graded_row_count"] += 1
        if row.get("locked_at") not in (None, ""):
            bucket["locked_row_count"] += 1
        if bool(row.get("data_complete")):
            bucket["data_complete_count"] += 1

        for field in FIELD_PRESENCE_KEYS:
            if field in row and row[field] is not None:
                bucket["field_presence_counts"][field] += 1

    for regime in REGIME_ORDER:
        bucket = summary[regime]
        row_count = bucket["row_count"]
        if row_count == 0:
            continue

        bucket["data_complete_rate"] = bucket["data_complete_count"] / row_count
        bucket["field_presence_rates"] = {
            field: count / row_count
            for field, count in bucket["field_presence_counts"].items()
        }

    return summary


def _format_pct(value: float) -> str:
    return f"{value:.1%}"


def _build_summary_table(summary: dict) -> list[str]:
    lines = [
        "| Regime | Window | Rows | Graded | Locked | Data complete |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for regime in REGIME_ORDER:
        bucket = summary[regime]
        lines.append(
            "| {regime} | {window} | {rows} | {graded} | {locked} | {complete} |".format(
                regime=regime,
                window=REGIME_LABELS[regime],
                rows=bucket["row_count"],
                graded=bucket["graded_row_count"],
                locked=bucket["locked_row_count"],
                complete=_format_pct(bucket["data_complete_rate"]),
            )
        )
    return lines


def _build_presence_table(summary: dict) -> list[str]:
    lines = [
        "| Field | " + " | ".join(REGIME_ORDER) + " |",
        "| --- | " + " | ".join(["---:"] * len(REGIME_ORDER)) + " |",
    ]
    for field in FIELD_PRESENCE_KEYS:
        rates = " | ".join(
            _format_pct(summary[regime]["field_presence_rates"][field])
            for regime in REGIME_ORDER
        )
        lines.append(f"| {field} | {rates} |")
    return lines


def render_report(rows: list[dict]) -> str:
    """Render a markdown report for later evaluation tasks."""
    summary = summarize_regimes(rows)
    safe_windows = [
        "- `post_roi_clean` is the first clean post-ROI / post-SwStr-live window.",
        "- `swstr_roi_transition` should stay labeled as a transition era and not be mixed into clean benchmarking.",
        "- Earlier regimes remain useful for context and storage audits, but not as like-for-like evaluation baselines.",
    ]

    parts = [
        "# E1 Regime Map",
        "",
        "## Safe Evaluation Windows",
        *safe_windows,
        "",
        "## Regime Summary",
        *_build_summary_table(summary),
        "",
        "## Field Presence Rates",
        *_build_presence_table(summary),
    ]
    return "\n".join(parts)


def main() -> None:
    print(render_report(load_history()))


if __name__ == "__main__":
    main()
