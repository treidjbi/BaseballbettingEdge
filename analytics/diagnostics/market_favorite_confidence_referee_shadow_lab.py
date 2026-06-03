"""Shadow lab for market-favorite confidence-referee candidates.

This diagnostic is analysis-only. It must not change live lambda, verdicts,
thresholds, staking, provider order, notifications, calibration, locks, or
dashboard artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_PATH = ROOT / "analytics" / "output" / "market_favorite_confidence_referee_shadow_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}

RUNTIME_SAFE_FIELDS = {
    "side",
    "k_line",
    "line_bucket",
    "american_odds",
    "price_sign",
    "market_favorite_side",
    "favorite_gap_no_vig",
    "model_side",
    "model_market_relationship",
    "projected_ks",
    "edge",
    "ev",
    "adj_ev",
    "verdict",
    "locked_verdict",
    "quality_gate_level",
    "bet_timing_window",
    "opportunity_bucket",
    "leash_risk_bucket",
    "pitcher_archetype_bucket",
}


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def load_jsonl(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tracked(row: dict[str, Any]) -> bool:
    return (
        str(row.get("slate_date") or "") >= CLEAN_WINDOW_START
        and row.get("context_snapshot") == "official_close"
        and row.get("is_tracked_pick") is True
        and row.get("result") in WIN_LOSS_RESULTS
        and _text(row.get("side")) in {"over", "under"}
    )


def _caution_count(row: dict[str, Any]) -> int:
    caution = 0
    if row.get("quality_gate_level") in {"capped", "unknown", None}:
        caution += 1
    if row.get("bet_timing_window") in {"pre_15", "pre_5", "post_start", "unknown"}:
        caution += 1
    if _text(row.get("side")) == "under" and row.get("line_bucket") in {"5.5", "6.5", "7.5+"}:
        caution += 1
    if row.get("leash_risk_bucket") in {"medium", "high"}:
        caution += 1
    return caution


def candidate_flags(row: dict[str, Any]) -> dict[str, bool]:
    side = _text(row.get("side"))
    favorite = _text(row.get("market_favorite_side"))
    model_side = _text(row.get("model_side")) or side
    agrees = side in {"over", "under"} and favorite in {"over", "under"} and model_side == favorite
    fades = side in {"over", "under"} and favorite in {"over", "under"} and model_side != favorite

    return {
        "current_model_tracked": _tracked(row),
        "model_agrees_market_favorite": _tracked(row) and agrees,
        "model_fades_market_favorite": _tracked(row) and fades,
        "over_agrees_market_favorite": _tracked(row) and side == "over" and agrees,
        "under_agrees_market_favorite": _tracked(row) and side == "under" and agrees,
        "market_favorite_referee_candidate": _tracked(row)
        and agrees
        and row.get("quality_gate_level") in {"clean", "capped"}
        and row.get("bet_timing_window") not in {"post_start", "unknown"},
        "market_fade_warning_candidate": _tracked(row) and fades and _caution_count(row) >= 1,
    }


def _pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def tracked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _tracked(row)]


def summarize_candidate(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [row for row in tracked_rows(rows) if candidate_flags(row).get(name, False)]
    wins = sum(1 for row in selected if row.get("result") == "win")
    losses = sum(1 for row in selected if row.get("result") == "loss")
    pnl = round(sum(_pnl(row) for row in selected), 2)
    return {
        "name": name,
        "rows": len(selected),
        "wins": wins,
        "losses": losses,
        "flat_pnl": pnl,
        "flat_roi": round(pnl / len(selected), 3) if selected else None,
    }


def split_holdout_rows(
    rows: list[dict[str, Any]],
    *,
    train_fraction: float = 0.7,
    min_validate_dates: int = 5,
) -> dict[str, Any]:
    dates = sorted({str(row.get("slate_date") or "") for row in rows if row.get("slate_date")})
    if len(dates) <= 1:
        return {"train_dates": dates, "validate_dates": [], "train_rows": list(rows), "validate_rows": []}

    cut_index = int(len(dates) * train_fraction)
    cut_index = max(1, min(cut_index, len(dates) - 1))
    if len(dates) > min_validate_dates:
        cut_index = min(cut_index, len(dates) - min_validate_dates)

    train_dates = dates[:cut_index]
    validate_dates = dates[cut_index:]
    train_set = set(train_dates)
    validate_set = set(validate_dates)
    return {
        "train_dates": train_dates,
        "validate_dates": validate_dates,
        "train_rows": [row for row in rows if str(row.get("slate_date") or "") in train_set],
        "validate_rows": [row for row in rows if str(row.get("slate_date") or "") in validate_set],
    }


CANDIDATES = [
    "current_model_tracked",
    "model_agrees_market_favorite",
    "model_fades_market_favorite",
    "over_agrees_market_favorite",
    "under_agrees_market_favorite",
    "market_favorite_referee_candidate",
    "market_fade_warning_candidate",
]


def _fmt_roi(value: float | None) -> str:
    return "--" if value is None else f"{value:+.1%}"


def _summary_row(summary: dict[str, Any]) -> str:
    return (
        f"| `{summary['name']}` | {summary['rows']} | "
        f"{summary['wins']}-{summary['losses']} | "
        f"{summary['flat_pnl']:+.2f} | {_fmt_roi(summary['flat_roi'])} |"
    )


def summarize_slices(
    candidate_name: str,
    rows: list[dict[str, Any]],
    field: str,
    *,
    min_rows: int = 50,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in tracked_rows(rows):
        if not candidate_flags(row).get(candidate_name, False):
            continue
        grouped.setdefault(str(row.get(field) or "unknown"), []).append(row)

    summaries = []
    for bucket, bucket_rows in sorted(grouped.items()):
        wins = sum(1 for row in bucket_rows if row.get("result") == "win")
        losses = sum(1 for row in bucket_rows if row.get("result") == "loss")
        pnl = round(sum(_pnl(row) for row in bucket_rows), 2)
        summaries.append(
            {
                "bucket": bucket,
                "rows": len(bucket_rows),
                "wins": wins,
                "losses": losses,
                "flat_pnl": pnl,
                "flat_roi": round(pnl / len(bucket_rows), 3) if bucket_rows else None,
                "sample_status": "enough_sample" if len(bucket_rows) >= min_rows else "small_sample",
            }
        )
    return summaries


def _promotion_gate_status(
    *,
    tracked_count: int,
    validate_dates: list[str],
    current: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if tracked_count < 250:
        blockers.append(f"validation tracked rows {tracked_count} < 250")
    if len(validate_dates) < 10:
        blockers.append(f"validation slates {len(validate_dates)} < 10")
    if candidate["rows"] < 100:
        blockers.append(f"candidate rows {candidate['rows']} < 100")

    current_win_rate = current["wins"] / current["rows"] if current["rows"] else 0.0
    candidate_win_rate = candidate["wins"] / candidate["rows"] if candidate["rows"] else 0.0
    if candidate_win_rate - current_win_rate < 0.03:
        blockers.append("side accuracy lift < 3.0 percentage points")
    if candidate["flat_pnl"] <= 0:
        blockers.append("candidate flat PnL is not positive")
    if candidate["flat_pnl"] - current["flat_pnl"] < 5.0:
        blockers.append("candidate flat PnL lift < 5.0 units")

    if blockers:
        return "not_ready", blockers
    return "promotion_plan_candidate", []


def build_report(rows: list[dict[str, Any]]) -> str:
    tracked = tracked_rows(rows)
    split = split_holdout_rows(tracked)
    validation = split["validate_rows"] or tracked
    current_summary = summarize_candidate("current_model_tracked", validation)
    candidate_summary = summarize_candidate("market_favorite_referee_candidate", validation)
    gate_status, blockers = _promotion_gate_status(
        tracked_count=len(tracked_rows(validation)),
        validate_dates=split["validate_dates"],
        current=current_summary,
        candidate=candidate_summary,
    )

    lines = [
        "# Market Favorite Confidence Referee Shadow Lab",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, locks, or dashboard artifacts.",
        "",
        "## Scope",
        "",
        f"- Clean window start: `{CLEAN_WINDOW_START}`",
        f"- Tracked rows: `{len(tracked)}`",
        f"- Training slates: `{len(split['train_dates'])}`",
        f"- Validation slates: `{len(split['validate_dates'])}`",
        "",
        "## Validation Candidate Scoreboard",
        "",
        "| Candidate | Rows | W-L | Flat PnL | Flat ROI |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(_summary_row(summarize_candidate(candidate, validation)) for candidate in CANDIDATES)

    for field in (
        "side",
        "price_sign",
        "line_bucket",
        "quality_gate_level",
        "bet_timing_window",
        "opportunity_bucket",
        "leash_risk_bucket",
        "pitcher_archetype_bucket",
    ):
        lines.extend(
            [
                "",
                f"### market_favorite_referee_candidate By {field}",
                "",
                "| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |",
                "| --- | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        slice_rows = summarize_slices("market_favorite_referee_candidate", validation, field)
        if not slice_rows:
            lines.append("| none | 0 | 0-0 | +0.00 | -- | `small_sample` |")
        for item in slice_rows:
            lines.append(
                f"| `{item['bucket']}` | {item['rows']} | {item['wins']}-{item['losses']} | "
                f"{item['flat_pnl']:+.2f} | {_fmt_roi(item['flat_roi'])} | `{item['sample_status']}` |"
            )

    lines.extend(
        [
            "",
            "## Promotion Discussion Gate",
            "",
            f"- Status: `{gate_status}`",
        ]
    )
    if blockers:
        lines.append(f"- Blockers: `{'; '.join(blockers)}`")
    lines.extend(
        [
            "- This report can only recommend drafting a later production plan.",
            "- A candidate must survive over/under, plus/minus, K-line, quality, timing, opportunity/leash, and pitcher-archetype slices.",
            "- Market-favorite evidence is a referee/selection warning candidate, not a replacement for the model.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    report = build_report(load_jsonl())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
