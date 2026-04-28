"""Storage-integrity diagnostic foundation for persisted pick history."""

from __future__ import annotations

import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT_DIR / "data" / "picks_history.json"

REGIME_ORDER = [
    "pre_2026_04_08",
    "phase_a_to_pre_swstr_live",
    "swstr_roi_transition",
    "post_roi_clean",
]

PERSISTED_FIELDS = [
    "opp_team",
    "pitcher_throws",
    "swstr_pct",
    "career_swstr_pct",
    "swstr_delta_k9",
    "park_factor",
    "days_since_last_start",
    "last_pitch_count",
    "rest_k9_delta",
    "opening_odds_source",
    "edge",
    "data_complete",
    "locked_k_line",
    "locked_odds",
    "locked_adj_ev",
    "locked_verdict",
]

CRITICAL_MODELING_FIELDS = [
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

FORWARD_ONLY_FIELDS = [
    "pitcher_throws",
    "swstr_pct",
    "career_swstr_pct",
    "swstr_delta_k9",
    "park_factor",
    "days_since_last_start",
    "last_pitch_count",
    "rest_k9_delta",
    "opening_odds_source",
    "data_complete",
]

LOCK_SNAPSHOT_FIELDS = [
    "locked_k_line",
    "locked_odds",
    "locked_adj_ev",
    "locked_verdict",
]


def load_history(path: Path = HISTORY_PATH) -> list[dict]:
    """Return stored pick-history rows."""
    with open(path, encoding="utf-8") as handle:
        rows = json.load(handle)
    if not isinstance(rows, list):
        raise ValueError(f"{path} did not contain a list of history rows")
    return rows


def classify_regime(date_str: str | None) -> str:
    """Map an ISO date string onto the evaluation-era labels from the plan."""
    if not date_str:
        return "unknown"
    if date_str < "2026-04-08":
        return "pre_2026_04_08"
    if date_str <= "2026-04-23":
        return "phase_a_to_pre_swstr_live"
    if date_str <= "2026-04-27":
        return "swstr_roi_transition"
    return "post_roi_clean"


def field_presence_rate(rows: list[dict], field: str) -> float:
    """Return the share of rows where a field is persisted with a non-null value."""
    if not rows:
        return 0.0
    present_count = sum(1 for row in rows if _field_is_present(row, field))
    return present_count / len(rows)


def summarize_field_matrix(
    rows: list[dict],
    fields: list[str] = PERSISTED_FIELDS,
) -> dict[str, dict[str, float]]:
    """Return field-presence rates for each regime."""
    summary: dict[str, dict[str, float]] = {}
    for regime in REGIME_ORDER:
        regime_rows = [row for row in rows if classify_regime(row.get("date")) == regime]
        summary[regime] = {
            field: field_presence_rate(regime_rows, field)
            for field in fields
        }
    return summary


def summarize_locked_vs_unlocked(
    rows: list[dict],
    fields: list[str] = PERSISTED_FIELDS,
) -> dict[str, dict[str, object]]:
    """Compare field population for locked and unlocked rows."""
    groups = {
        "locked": [row for row in rows if row.get("locked_at")],
        "unlocked": [row for row in rows if not row.get("locked_at")],
    }
    summary: dict[str, dict[str, object]] = {}
    for label, group_rows in groups.items():
        summary[label] = {
            "row_count": len(group_rows),
            "field_presence_rates": {
                field: field_presence_rate(group_rows, field)
                for field in fields
            },
        }
    return summary


def summarize_transition_rows(rows: list[dict]) -> dict[str, object]:
    """Call out transition-slate rows that should stay out of clean benchmarking."""
    transition_rows = [
        row for row in rows
        if classify_regime(row.get("date")) == "swstr_roi_transition"
    ]
    if not transition_rows:
        return {
            "row_count": 0,
            "locked_row_count": 0,
            "unlocked_row_count": 0,
            "missing_critical_fields": [],
        }

    missing_fields = [
        field
        for field in CRITICAL_MODELING_FIELDS
        if field_presence_rate(transition_rows, field) < 1.0
    ]
    return {
        "row_count": len(transition_rows),
        "locked_row_count": sum(1 for row in transition_rows if row.get("locked_at")),
        "unlocked_row_count": sum(1 for row in transition_rows if not row.get("locked_at")),
        "missing_critical_fields": missing_fields,
    }


def determine_storage_assessment(rows: list[dict]) -> str:
    """Return the current storage-contract maturity assessment."""
    field_matrix = summarize_field_matrix(rows, CRITICAL_MODELING_FIELDS)
    clean_rates = field_matrix["post_roi_clean"]
    post_clean_ready = all(rate >= 0.95 for rate in clean_rates.values())
    has_transition_rows = any(
        classify_regime(row.get("date")) == "swstr_roi_transition"
        for row in rows
    )
    all_regimes_stable = True
    for regime in REGIME_ORDER:
        regime_rows = [
            row for row in rows
            if classify_regime(row.get("date")) == regime
        ]
        if not regime_rows:
            continue
        regime_rates = field_matrix[regime]
        if not all(rate >= 0.95 for rate in regime_rates.values()):
            all_regimes_stable = False
            break

    if post_clean_ready and has_transition_rows:
        return "good enough for season learning"
    if post_clean_ready and all_regimes_stable:
        return "good enough for multi-season scaling"
    return "ready for a structural split like per-season files or a committed database"


def identify_safe_modeling_fields(rows: list[dict]) -> list[str]:
    """Fields that are fully populated in the clean post-ROI regime."""
    clean_rows = [row for row in rows if classify_regime(row.get("date")) == "post_roi_clean"]
    if not clean_rows:
        return []
    return [
        field
        for field in CRITICAL_MODELING_FIELDS
        if field_presence_rate(clean_rows, field) >= 0.95
    ]


def identify_regime_fragile_fields(rows: list[dict]) -> list[str]:
    """Fields that look reliable now but are historically inconsistent."""
    if not rows:
        return []
    field_matrix = summarize_field_matrix(rows, CRITICAL_MODELING_FIELDS)
    fragile_fields: list[str] = []
    for field in CRITICAL_MODELING_FIELDS:
        rates = [
            field_matrix[regime][field]
            for regime in REGIME_ORDER
            if any(classify_regime(row.get("date")) == regime for row in rows)
        ]
        if rates and max(rates) - min(rates) >= 0.5:
            fragile_fields.append(field)
    return fragile_fields


def build_storage_integrity_report(rows: list[dict]) -> str:
    """Render a markdown storage-integrity memo skeleton."""
    field_matrix = summarize_field_matrix(rows)
    locked_summary = summarize_locked_vs_unlocked(rows)
    transition_summary = summarize_transition_rows(rows)
    safe_fields = identify_safe_modeling_fields(rows)
    fragile_fields = identify_regime_fragile_fields(rows)
    assessment = determine_storage_assessment(rows)

    lines = [
        "# E2 Storage Integrity",
        "",
        f"Current storage model assessment: **{assessment}**.",
        "",
        "This diagnostic checks whether decision-time context is persisted consistently enough to support clean evaluation windows and future modeling.",
        "",
        "## Persisted Field Matrix By Regime",
        "",
    ]
    for regime in REGIME_ORDER:
        lines.append(f"### {regime}")
        rates = field_matrix[regime]
        if not any(rates.values()):
            lines.append("- No rows in this regime.")
            lines.append("")
            continue
        for field, rate in rates.items():
            lines.append(f"- `{field}`: {rate:.0%}")
        lines.append("")

    lines.extend(
        [
            "## Locked Vs Unlocked Field Population Comparison",
            "",
            f"- Locked rows: {locked_summary['locked']['row_count']}",
            f"- Unlocked rows: {locked_summary['unlocked']['row_count']}",
        ]
    )
    for field in LOCK_SNAPSHOT_FIELDS:
        locked_rate = locked_summary["locked"]["field_presence_rates"][field]
        unlocked_rate = locked_summary["unlocked"]["field_presence_rates"][field]
        lines.append(
            f"- `{field}` locked/unlocked presence: {locked_rate:.0%} / {unlocked_rate:.0%}"
        )

    lines.extend(
        [
            "",
            "## Same-Day Transition-Slate Exceptions",
            "",
            f"- Transition rows: {transition_summary['row_count']}",
            f"- Locked transition rows: {transition_summary['locked_row_count']}",
            f"- Unlocked transition rows: {transition_summary['unlocked_row_count']}",
        ]
    )
    if transition_summary["missing_critical_fields"]:
        lines.append(
            "- Critical fields with gaps on the transition slate: "
            + ", ".join(f"`{field}`" for field in transition_summary["missing_critical_fields"])
        )
    else:
        lines.append("- Critical fields with gaps on the transition slate: none detected")

    lines.extend(
        [
            "",
            "## History Fields That Are Safe For Future Modeling",
            "",
        ]
    )
    if safe_fields:
        lines.extend(f"- `{field}`" for field in safe_fields)
    else:
        lines.append("- None yet; clean post-ROI rows are still too sparse.")

    lines.extend(
        [
            "",
            "## History Fields That Are Too Regime-Fragile For Naive Reuse",
            "",
        ]
    )
    if fragile_fields:
        lines.extend(f"- `{field}`" for field in fragile_fields)
    else:
        lines.append("- None detected from the current history sample.")

    lines.extend(
        [
            "",
            "## Forward-Only And Intentionally Sparse Fields",
            "",
        ]
    )
    lines.extend(f"- `{field}`" for field in FORWARD_ONLY_FIELDS)

    lines.extend(
        [
            "",
            "## What This Means",
            "",
            f"- Season learning: {'yes' if assessment == 'good enough for season learning' else 'not yet'}",
            f"- Multi-season scaling: {'yes' if assessment == 'good enough for multi-season scaling' else 'not yet'}",
            "- Structural split needed: "
            + (
                "yes"
                if assessment.startswith("ready for a structural split")
                else "not yet"
            ),
        ]
    )
    return "\n".join(lines)


def main() -> None:
    print(build_storage_integrity_report(load_history()))


def _field_is_present(row: dict, field: str) -> bool:
    value = row.get(field)
    if value is None:
        return False
    if isinstance(value, str) and value == "":
        return False
    return field in row


if __name__ == "__main__":
    main()
