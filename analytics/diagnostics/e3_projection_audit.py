"""Projection-audit helpers for clean-window residual analysis."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics.e1_regime_map import classify_regime

SIDE_ORDER = ["over", "under"]


def load_history() -> list[dict]:
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def residual(row: dict) -> float | None:
    actual = row.get("actual_ks")
    if actual is None:
        return None

    projection = row.get("lambda")
    if projection is None:
        projection = row.get("applied_lambda")
    if projection is None:
        return None

    return float(actual) - float(projection)


def filter_rows(
    rows: list[dict],
    *,
    clean_only: bool = False,
    graded_only: bool = False,
) -> list[dict]:
    filtered: list[dict] = []
    for row in rows:
        if clean_only and classify_regime(row.get("date")) != "post_roi_clean":
            continue
        if graded_only and row.get("actual_ks") is None:
            continue
        filtered.append(row)
    return filtered


def _bucket_for_lambda(value: float | int | None) -> str | None:
    if value is None:
        return None
    value = float(value)
    lower = int(value)
    upper = lower + 0.9
    return f"{lower:.1f}-{upper:.1f}"


def _summarize_group(label: str, values: list[float], key: str) -> dict:
    return {
        key: label,
        "count": len(values),
        "mean_residual": round(mean(values), 1),
        "median_residual": round(median(values), 1),
    }


def summarize_residuals_by_lambda_bucket(
    rows: list[dict],
    *,
    clean_only: bool = False,
) -> list[dict]:
    grouped: dict[str, list[float]] = {}
    for row in filter_rows(rows, clean_only=clean_only, graded_only=True):
        bucket = _bucket_for_lambda(row.get("applied_lambda", row.get("lambda")))
        value = residual(row)
        if bucket is None or value is None:
            continue
        grouped.setdefault(bucket, []).append(value)

    def _bucket_sort_key(label: str) -> float:
        return float(label.split("-")[0])

    return [
        _summarize_group(bucket, grouped[bucket], "bucket")
        for bucket in sorted(grouped, key=_bucket_sort_key)
    ]


def summarize_residuals_by_side(
    rows: list[dict],
    *,
    clean_only: bool = False,
) -> list[dict]:
    grouped: dict[str, list[float]] = {}
    for row in filter_rows(rows, clean_only=clean_only, graded_only=True):
        side = row.get("side")
        value = residual(row)
        if side not in SIDE_ORDER or value is None:
            continue
        grouped.setdefault(side, []).append(value)

    return [
        _summarize_group(side, grouped[side], "side")
        for side in SIDE_ORDER
        if side in grouped
    ]


def summarize_pitcher_extremes(rows: list[dict], *, clean_only: bool = False, min_n: int = 2) -> dict:
    grouped: dict[str, list[float]] = {}
    for row in filter_rows(rows, clean_only=clean_only, graded_only=True):
        pitcher = row.get("pitcher")
        value = residual(row)
        if not pitcher or value is None:
            continue
        grouped.setdefault(str(pitcher), []).append(value)

    aggregates = [
        {
            "pitcher": pitcher,
            "count": len(values),
            "mean_residual": round(mean(values), 2),
        }
        for pitcher, values in grouped.items()
        if len(values) >= min_n
    ]
    ordered = sorted(aggregates, key=lambda item: item["mean_residual"])
    return {
        "most_over_predicted": ordered[:5],
        "most_under_predicted": list(reversed(ordered[-5:])),
    }


def build_projection_audit_report(rows: list[dict]) -> str:
    clean_rows = filter_rows(rows, clean_only=True, graded_only=True)
    side_summary = summarize_residuals_by_side(rows, clean_only=True)
    bucket_summary = summarize_residuals_by_lambda_bucket(rows, clean_only=True)
    pitcher_extremes = summarize_pitcher_extremes(rows, clean_only=True)

    if clean_rows:
        overall_values = [value for value in (residual(row) for row in clean_rows) if value is not None]
        overall_mean = round(mean(overall_values), 2) if overall_values else 0.0
        overall_median = round(median(overall_values), 2) if overall_values else 0.0
    else:
        overall_mean = 0.0
        overall_median = 0.0

    lines = [
        "# E3 Projection Audit",
        "",
        "This audit uses the clean post-ROI window (`2026-04-28+`) so residuals do not mix dead-SwStr or transition-era rows.",
        "",
        "## Clean Window Snapshot",
        "",
        f"- Clean graded rows: {len(clean_rows)}",
        f"- Mean residual (`actual_ks - projection`): {overall_mean:+.2f}",
        f"- Median residual (`actual_ks - projection`): {overall_median:+.2f}",
        "",
        "## Residuals By Side",
        "",
    ]
    if side_summary:
        for row in side_summary:
            lines.append(
                f"- `{row['side']}`: n={row['count']}, mean={row['mean_residual']:+.1f}, median={row['median_residual']:+.1f}"
            )
    else:
        lines.append("- No clean graded rows yet.")

    lines.extend(
        [
            "",
            "## Residuals By Lambda Bucket",
            "",
        ]
    )
    if bucket_summary:
        for row in bucket_summary:
            lines.append(
                f"- `{row['bucket']}`: n={row['count']}, mean={row['mean_residual']:+.1f}, median={row['median_residual']:+.1f}"
            )
    else:
        lines.append("- No clean graded rows yet.")

    lines.extend(
        [
            "",
            "## Pitcher Extremes",
            "",
            "### Most Over-Predicted",
        ]
    )
    if pitcher_extremes["most_over_predicted"]:
        for row in pitcher_extremes["most_over_predicted"]:
            lines.append(
                f"- `{row['pitcher']}`: n={row['count']}, mean residual={row['mean_residual']:+.2f}"
            )
    else:
        lines.append("- Not enough repeat pitcher samples yet.")

    lines.append("")
    lines.append("### Most Under-Predicted")
    if pitcher_extremes["most_under_predicted"]:
        for row in pitcher_extremes["most_under_predicted"]:
            lines.append(
                f"- `{row['pitcher']}`: n={row['count']}, mean residual={row['mean_residual']:+.2f}"
            )
    else:
        lines.append("- Not enough repeat pitcher samples yet.")

    lines.extend(
        [
            "",
            "## Decision Framing",
            "",
            "- If the high-lambda buckets stay materially negative, the next implementation plan should prioritize lambda-shape correction before more feature add-ons.",
            "- If over/under asymmetry stays large, the next implementation plan should treat side conversion and price handling as first-class suspects, not just pitcher inputs.",
            "- If pitcher extremes cluster by archetype or team context, that is evidence for opponent/environment structure work instead of global lambda nudges.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    print(build_projection_audit_report(load_history()))


if __name__ == "__main__":
    main()
