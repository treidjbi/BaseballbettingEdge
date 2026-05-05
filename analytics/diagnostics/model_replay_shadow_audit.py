"""Shadow comparison between current projections and a simpler prior model."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"
CLEAN_WINDOW_START = "2026-04-28"
GRADED_RESULTS = {"win", "loss"}
CURRENT_PROJECTION_KEYS = (
    "lambda",
    "raw_lambda",
    "applied_lambda",
    "model_lambda",
    "projected_ks",
)


def load_history() -> list[dict]:
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def simple_projection(row: dict) -> float | None:
    season_k9 = _to_float(row.get("season_k9"))
    career_k9 = _to_float(row.get("career_k9"))
    avg_ip = _to_float(row.get("avg_ip"))
    if season_k9 is None or career_k9 is None or avg_ip is None:
        return None

    blended_k9 = (0.60 * season_k9) + (0.40 * career_k9)
    return round((blended_k9 * avg_ip) / 9.0, 3)


def current_projection(row: dict) -> float | None:
    for key in CURRENT_PROJECTION_KEYS:
        projection = _to_float(row.get(key))
        if projection is not None:
            return projection
    return None


def projection_residual(row: dict, projection: float | None) -> float | None:
    actual = _to_float(row.get("actual_ks"))
    if actual is None or projection is None:
        return None
    return round(actual - float(projection), 3)


def _is_clean_graded_row(row: dict) -> bool:
    return str(row.get("date") or "") >= CLEAN_WINDOW_START and row.get("result") in GRADED_RESULTS


def _mean_abs(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(abs(value) for value in values) / len(values), 3)


def _empty_residual_bucket() -> dict:
    return {
        "current_n": 0,
        "current_mean_abs_residual": None,
        "simple_n": 0,
        "simple_mean_abs_residual": None,
    }


def _summarize_residuals(current: list[float], simple: list[float]) -> dict:
    return {
        "current_n": len(current),
        "current_mean_abs_residual": _mean_abs(current),
        "simple_n": len(simple),
        "simple_mean_abs_residual": _mean_abs(simple),
    }


def summarize(rows: list[dict]) -> dict:
    current_residuals: list[float] = []
    simple_residuals: list[float] = []
    side_residuals: dict[str, dict[str, list[float]]] = {}
    eligible_rows = 0

    for row in rows:
        if not _is_clean_graded_row(row):
            continue
        eligible_rows += 1

        side = str(row.get("side") or "unknown")
        side_bucket = side_residuals.setdefault(side, {"current": [], "simple": []})

        current = projection_residual(row, current_projection(row))
        if current is not None:
            current_residuals.append(current)
            side_bucket["current"].append(current)

        simple = projection_residual(row, simple_projection(row))
        if simple is not None:
            simple_residuals.append(simple)
            side_bucket["simple"].append(simple)

    by_side = {}
    for side, residuals in sorted(side_residuals.items()):
        summary = _summarize_residuals(residuals["current"], residuals["simple"])
        if summary != _empty_residual_bucket():
            by_side[side] = summary

    return {
        "eligible_rows": eligible_rows,
        **_summarize_residuals(current_residuals, simple_residuals),
        "by_side": by_side,
    }


def _format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def build_model_replay_report(summary: dict) -> str:
    lines = [
        "# Model Replay Shadow Audit",
        "",
        "This audit is diagnostic only. It does not change live lambda, verdicts, thresholds, staking, or calibration.",
        "",
        "## Clean Window Replay",
        "",
        f"- Eligible clean graded rows (`{CLEAN_WINDOW_START}+`, result win/loss): {summary['eligible_rows']}",
        f"- Current model rows: {summary['current_n']}",
        f"- Current mean absolute residual: {_format_metric(summary['current_mean_abs_residual'])}",
        f"- Simple prior replay rows: {summary['simple_n']}",
        f"- Simple prior replay mean absolute residual: {_format_metric(summary['simple_mean_abs_residual'])}",
        "",
        "## Side Residuals",
        "",
    ]

    if summary["by_side"]:
        for side, row in summary["by_side"].items():
            lines.append(
                f"- `{side}`: current_n={row['current_n']}, current_mae={_format_metric(row['current_mean_abs_residual'])}, "
                f"simple_n={row['simple_n']}, simple_mae={_format_metric(row['simple_mean_abs_residual'])}"
            )
    else:
        lines.append("- No side-level replay rows available yet.")

    lines.extend(
        [
            "",
            "## Decision Rule",
            "",
            "- only consider simplification if same-window replay beats current residuals, including side residuals, on the same `2026-04-28+` rows.",
            "- Do not simplify based on all-history ROI; not if all-history ROI merely looks better.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    print(build_model_replay_report(summarize(load_history())))


if __name__ == "__main__":
    main()
