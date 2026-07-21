"""Shadow-only Gate F pre-close CLV proxy lab.

CLV is post-close evidence. This diagnostic keeps CLV as the validation target
and tests whether runtime-safe pre-lock fields can identify the rows that later
beat close. It does not change live lambda, verdicts, thresholds, staking,
provider order, notifications, locks, retention, calibration, or dashboard
source-of-truth behavior.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from market_infra import alternative_pick_selector as alternative_selector


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "gate_f_preclose_clv_proxy_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
FIRE_VERDICTS = {"FIRE 1u", "FIRE 2u"}
PROXY_LABELS = (
    "strong_preclose_clv_proxy",
    "medium_preclose_clv_proxy",
    "weak_preclose_clv_proxy",
)
SLICE_FIELDS = (
    "side",
    "line_bucket",
    "price_sign",
    "bet_timing_window",
    "quality_gate_level",
    "model_market_relationship",
    "side_price_movement",
    "no_vig_label",
    "proxy_label",
)
RICH_PROXY_FIELDS = (
    "toward_pick_count",
    "away_from_pick_count",
    "better_now_count",
    "worse_now_count",
    "book_count",
    "broad_confirmation",
    "best_is_off_market",
    "reversal_book_count",
    "volatile_book_count",
    "provider",
    "market_agreement_label",
)


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


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    if number is None:
        return None
    return int(number)


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def _is_fire(verdict: Any) -> bool:
    return str(verdict or "").startswith("FIRE")


def current_verdict(row: dict[str, Any]) -> str:
    return alternative_selector.display_verdict(row)


def source_fire_verdict(row: dict[str, Any]) -> str:
    return alternative_selector.source_fire_verdict(row)


def no_vig_label(row: dict[str, Any]) -> str:
    gap = _to_float(row.get("model_no_vig_gap"))
    if gap is None:
        return "no_vig_unknown"
    if gap >= 0.04:
        return "no_vig_confirmed_edge"
    if gap >= 0.02:
        return "no_vig_thin_edge"
    if gap > 0:
        return "no_vig_price_only_edge"
    return "no_vig_no_edge"


def positive_clv_target(row: dict[str, Any]) -> bool:
    price_clv = _to_float(row.get("price_clv_cents"))
    line_clv = _to_float(row.get("line_clv_delta"))
    return (
        _is_true(row.get("beat_close_price"))
        or _is_true(row.get("beat_close_line"))
        or (price_clv is not None and price_clv > 0)
        or (line_clv is not None and line_clv > 0)
    )


def profit_rescue_shadow_decision(row: dict[str, Any]) -> dict[str, Any]:
    current = source_fire_verdict(row)
    proposed = current
    side = str(row.get("side") or "").strip().lower()
    relationship = str(row.get("model_market_relationship") or "").strip()
    reasons: list[str] = []

    if current == "FIRE 2u":
        proposed = "FIRE 1u"
        reasons.append("cap_fire_two_to_fire_one")
    if side == "under" and _is_fire(proposed):
        proposed = "LEAN"
        reasons.append("cap_fire_under_to_lean")
    if relationship == "model_fades_favorite" and _is_fire(current):
        reasons.append("cap_market_fade_fire_to_lean")
        if _is_fire(proposed):
            proposed = "LEAN"

    return {
        "current_verdict": current,
        "proposed_verdict": proposed,
        "reasons": reasons,
    }


def _movement_with_pick(row: dict[str, Any]) -> bool:
    side_movement = str(row.get("side_price_movement") or "").strip()
    toward = _to_int(row.get("toward_pick_count"))
    away = _to_int(row.get("away_from_pick_count"))
    return side_movement == "with_side" or (
        toward is not None and away is not None and toward > away
    )


def _movement_against_pick(row: dict[str, Any]) -> bool:
    side_movement = str(row.get("side_price_movement") or "").strip()
    toward = _to_int(row.get("toward_pick_count"))
    away = _to_int(row.get("away_from_pick_count"))
    return side_movement == "against_side" or (
        toward is not None and away is not None and away > toward
    )


def _book_count(row: dict[str, Any]) -> int:
    count = _to_int(row.get("book_count"))
    if count is not None:
        return count
    books_seen = row.get("books_seen")
    if isinstance(books_seen, list):
        return len(books_seen)
    if isinstance(books_seen, str) and books_seen.strip():
        return len([part for part in books_seen.split(",") if part.strip()])
    return 0


def preclose_clv_proxy_score(row: dict[str, Any]) -> dict[str, Any]:
    """Score runtime-safe pre-close evidence for likely positive CLV.

    This function intentionally never reads beat-close or CLV fields.
    """
    score = 0
    positive: list[str] = []
    risks: list[str] = []
    no_vig_gap = _to_float(row.get("model_no_vig_gap"))
    quality = str(row.get("quality_gate_level") or "").strip().lower()
    timing = str(row.get("bet_timing_window") or "").strip()
    side = str(row.get("side") or "").strip().lower()
    relationship = str(row.get("model_market_relationship") or "").strip()
    edge = _to_float(row.get("edge"))
    adj_ev = _to_float(row.get("locked_adj_ev"))
    if adj_ev is None:
        adj_ev = _to_float(row.get("adj_ev"))
    book_count = _book_count(row)
    reversal_count = _to_int(row.get("reversal_book_count")) or 0
    volatile_count = _to_int(row.get("volatile_book_count")) or 0

    if _movement_with_pick(row):
        score += 3
        positive.append("movement_toward_pick")
    if _movement_against_pick(row):
        score -= 2
        risks.append("movement_against_pick")

    if edge is not None and edge < 0.02:
        score += 3
        positive.append("low_edge_market_validation")
    elif edge is not None and edge < 0.04:
        score += 2
        positive.append("moderate_low_edge_market_validation")
    elif edge is not None and edge < 0.06:
        score += 1
        positive.append("moderate_edge_market_validation")
    elif edge is not None and edge >= 0.06:
        score -= 2
        risks.append("high_edge_clv_risk")

    if adj_ev is not None and adj_ev < 0.06:
        score += 2
        positive.append("low_ev_market_validation")
    elif adj_ev is not None and adj_ev < 0.17:
        score += 1
        positive.append("moderate_ev_market_validation")
    elif adj_ev is not None and adj_ev >= 0.17:
        score -= 1
        risks.append("high_ev_clv_risk")

    if no_vig_gap is not None and 0 < no_vig_gap < 0.04:
        score += 1
        positive.append("thin_or_price_only_no_vig_gap")
    elif no_vig_gap is not None and no_vig_gap >= 0.04:
        score -= 1
        risks.append("model_edge_not_clv_proxy")

    if str(row.get("price_sign") or "").strip() == "minus":
        score += 1
        positive.append("minus_price_market_support")
    elif str(row.get("price_sign") or "").strip() == "plus":
        score -= 1
        risks.append("plus_price_clv_risk")

    if quality in {"", "clean", "none"}:
        score += 1
        positive.append("clean_quality")
    elif quality in {"blocked", "severe"}:
        score -= 2
        risks.append("blocked_quality")

    if timing in {"pre_120", "pre_60", "pre_30"}:
        score += 1
        positive.append("early_lock_window")
    elif timing in {"pre_5", "post_start"}:
        score -= 1
        risks.append("late_timing")

    if _is_true(row.get("broad_confirmation")) or book_count >= 3:
        score += 1
        positive.append("multi_book_support")
    elif book_count == 1:
        score -= 1
        risks.append("single_book_support")

    if _is_true(row.get("best_is_off_market")):
        score -= 2
        risks.append("off_market_best_book")

    if reversal_count > 0 or volatile_count > 1:
        score -= 2
        risks.append("reversal_or_volatility")
    elif reversal_count == 0 and volatile_count == 0:
        score += 1
        positive.append("low_volatility")

    if side == "under" and relationship == "model_fades_favorite":
        score -= 1
        risks.append("under_market_fade")

    if score >= 5:
        label = "strong_preclose_clv_proxy"
    elif score >= 3:
        label = "medium_preclose_clv_proxy"
    else:
        label = "weak_preclose_clv_proxy"

    return {
        "score": score,
        "label": label,
        "positive_reasons": positive,
        "risk_reasons": risks,
    }


def preclose_clv_proxy_label(row: dict[str, Any]) -> str:
    return str(preclose_clv_proxy_score(row)["label"])


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
    return {
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "pnl": 0.0,
        "roi": 0.0,
        "positive_clv_rows": 0,
        "positive_clv_rate": 0.0,
        "source_fire_rows": 0,
        "retained_fire_rows": 0,
        "capped_to_lean_rows": 0,
    }


def _add_row(bucket: dict[str, Any], row: dict[str, Any]) -> None:
    bucket["rows"] += 1
    if row.get("result") == "win":
        bucket["wins"] += 1
    elif row.get("result") == "loss":
        bucket["losses"] += 1
    bucket["pnl"] = round(float(bucket["pnl"]) + _row_pnl(row), 2)
    bucket["roi"] = round(float(bucket["pnl"]) / int(bucket["rows"]), 4)
    if positive_clv_target(row):
        bucket["positive_clv_rows"] += 1
    bucket["positive_clv_rate"] = round(
        float(bucket["positive_clv_rows"]) / int(bucket["rows"]),
        4,
    )
    decision = profit_rescue_shadow_decision(row)
    if _is_fire(decision["current_verdict"]):
        bucket["source_fire_rows"] += 1
        if _is_fire(decision["proposed_verdict"]):
            bucket["retained_fire_rows"] += 1
        else:
            bucket["capped_to_lean_rows"] += 1


def _recent_rows(rows: list[dict[str, Any]], *, days: int = 14) -> list[dict[str, Any]]:
    dates = [parsed for row in rows if (parsed := _parse_date(row.get("slate_date") or row.get("date")))]
    if not dates:
        return rows
    floor = max(dates) - timedelta(days=days - 1)
    return [
        row
        for row in rows
        if (row_date := _parse_date(row.get("slate_date") or row.get("date"))) is not None
        and row_date >= floor
    ]


def _score_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bucket = _empty_bucket()
    for row in rows:
        _add_row(bucket, row)
    return bucket


def _slice_value(row: dict[str, Any], field: str) -> str:
    if field == "no_vig_label":
        return no_vig_label(row)
    if field == "proxy_label":
        return preclose_clv_proxy_label(row)
    return str(row.get(field) or "unknown")


def _summarize_slice(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(_empty_bucket)
    for row in rows:
        _add_row(buckets[_slice_value(row, field)], row)
    return dict(sorted(buckets.items()))


def _negative_slices(rows: list[dict[str, Any]], *, min_rows: int = 10) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    for field in SLICE_FIELDS:
        for bucket, summary in _summarize_slice(rows, field).items():
            if summary["rows"] >= min_rows and summary["pnl"] < 0:
                risks.append(
                    {
                        "field": field,
                        "bucket": bucket,
                        "rows": summary["rows"],
                        "pnl": summary["pnl"],
                        "roi": summary["roi"],
                    }
                )
    risks.sort(key=lambda item: (float(item["pnl"]), -int(item["rows"])))
    return risks


def _candidate_readiness(bucket: dict[str, Any], negative_slices: list[dict[str, Any]]) -> str:
    rows = int(bucket["rows"])
    pnl = float(bucket["pnl"])
    positive_clv_rate = float(bucket["positive_clv_rate"])
    recent_pnl = float(bucket.get("recent", {}).get("pnl", 0.0))
    if rows >= 100 and pnl > 0 and positive_clv_rate >= 0.25 and recent_pnl >= 0 and not negative_slices:
        return "ready_for_plan"
    if rows >= 50 and pnl > 0 and positive_clv_rate >= 0.15:
        return "watch_more"
    return "not_ready"


def _available_field_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field in RICH_PROXY_FIELDS:
        counts[field] = sum(1 for row in rows if row.get(field) not in (None, "", [], {}))
    return counts


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = analysis_rows(rows)
    proxy_buckets: dict[str, dict[str, Any]] = {}
    for label in PROXY_LABELS:
        bucket_rows = [row for row in selected if preclose_clv_proxy_label(row) == label]
        bucket = _score_rows(bucket_rows)
        bucket["recent"] = _score_rows(_recent_rows(bucket_rows))
        bucket["negative_slices"] = _negative_slices(bucket_rows)
        bucket["candidate_readiness"] = _candidate_readiness(bucket, bucket["negative_slices"])
        proxy_buckets[label] = bucket

    source_fire_rows = [row for row in selected if _is_fire(source_fire_verdict(row))]
    strong_rows = [
        row for row in selected if preclose_clv_proxy_label(row) == "strong_preclose_clv_proxy"
    ]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "analysis_rows": len(selected),
        "source_fire_rows": len(source_fire_rows),
        "positive_clv_rows": sum(1 for row in selected if positive_clv_target(row)),
        "proxy_buckets": proxy_buckets,
        "available_field_counts": _available_field_counts(selected),
        "strong_proxy_slice_tables": {
            field: _summarize_slice(strong_rows, field)
            for field in SLICE_FIELDS
        },
    }


def _format_roi(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:+.1%}"


def _format_pnl(value: Any) -> str:
    number = _to_float(value) or 0.0
    return f"{number:+.2f}"


def _render_proxy_scoreboard(lines: list[str], proxy_buckets: dict[str, dict[str, Any]]) -> None:
    lines.extend(
        [
            "## Proxy Scoreboard",
            "",
            "| Proxy bucket | Readiness | Rows | W-L | PnL | ROI | Positive CLV | Source FIRE | Retained FIRE | Capped to LEAN | Recent PnL | Slice risks |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for label in PROXY_LABELS:
        bucket = proxy_buckets.get(label, _empty_bucket())
        lines.append(
            f"| `{label}` | `{bucket.get('candidate_readiness', 'not_ready')}` | {bucket['rows']} | "
            f"{bucket['wins']}-{bucket['losses']} | {_format_pnl(bucket['pnl'])} | {_format_roi(bucket['roi'])} | "
            f"{bucket['positive_clv_rows']} ({_format_roi(bucket['positive_clv_rate'])}) | "
            f"{bucket['source_fire_rows']} | {bucket['retained_fire_rows']} | {bucket['capped_to_lean_rows']} | "
            f"{_format_pnl(bucket.get('recent', {}).get('pnl', 0.0))} | {len(bucket.get('negative_slices', []))} |"
        )
    lines.append("")


def _render_field_availability(lines: list[str], summary: dict[str, Any]) -> None:
    counts = summary.get("available_field_counts", {})
    total = int(summary.get("analysis_rows", 0))
    lines.extend(
        [
            "## Runtime Field Availability",
            "",
            "| Field | Non-null rows | Coverage |",
            "| --- | ---: | ---: |",
        ]
    )
    for field in RICH_PROXY_FIELDS:
        count = int(counts.get(field, 0))
        coverage = count / total if total else 0.0
        lines.append(f"| `{field}` | {count} | {coverage:.1%} |")
    lines.append("")


def _render_top_risks(lines: list[str], proxy_buckets: dict[str, dict[str, Any]]) -> None:
    lines.extend(["## Strong Proxy Slice Risks", ""])
    risks = proxy_buckets.get("strong_preclose_clv_proxy", {}).get("negative_slices", [])[:8]
    if not risks:
        lines.append("- No negative strong-proxy slices above the minimum sample floor.")
    else:
        for risk in risks:
            lines.append(
                f"- `{risk['field']}={risk['bucket']}`: {risk['rows']} rows, "
                f"{_format_pnl(risk['pnl'])}, {_format_roi(risk['roi'])}."
            )
    lines.append("")


def render_report(summary: dict[str, Any]) -> str:
    proxy_buckets = summary.get("proxy_buckets", {})
    strong = proxy_buckets.get("strong_preclose_clv_proxy", _empty_bucket())
    ready = [
        label
        for label, bucket in proxy_buckets.items()
        if bucket.get("candidate_readiness") == "ready_for_plan"
    ]
    watch = [
        label
        for label, bucket in proxy_buckets.items()
        if bucket.get("candidate_readiness") == "watch_more"
    ]

    lines = [
        "# Gate F Pre-Close CLV Proxy Lab",
        "",
        f"Generated at: `{summary.get('generated_at', 'unknown')}`",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.",
        "",
        "## Executive Read",
        "",
        f"- Total source rows: `{summary.get('total_rows', 0)}`",
        f"- Clean tracked win/loss rows analyzed: `{summary.get('analysis_rows', 0)}`",
        f"- Positive CLV target rows: `{summary.get('positive_clv_rows', 0)}`",
        f"- Strong pre-close proxy rows: `{strong.get('rows', 0)}`, positive CLV capture `{strong.get('positive_clv_rows', 0)}` (`{_format_roi(strong.get('positive_clv_rate', 0.0))}`), PnL `{_format_pnl(strong.get('pnl', 0.0))}`.",
        f"- Ready-for-plan proxy buckets: `{', '.join(ready) if ready else 'none'}`",
        f"- Watch-more proxy buckets: `{', '.join(watch) if watch else 'none'}`",
        "",
        "## Boundary",
        "",
        "- CLV is the validation target, not a live selector.",
        "- The proxy score uses pre-close fields only; changing CLV outcome fields does not change proxy membership.",
        "- Current Gate C rows have limited rich live-market coverage, so this lab should improve as market-agreement and book-count fields fill in.",
        "",
    ]
    _render_proxy_scoreboard(lines, proxy_buckets)
    _render_field_availability(lines, summary)
    _render_top_risks(lines, proxy_buckets)
    lines.extend(
        [
            "## Recommendation",
            "",
            "- Do not promote a FIRE re-entry rule from CLV alone.",
            "- Use `strong_preclose_clv_proxy` as the first live-safe candidate only if it holds profit, positive CLV capture, and slice stability after more graded rows and richer market fields.",
            "- Keep `PROFIT_RESCUE_REFEREE_MODE=enforce` until a proxy bucket reaches `ready_for_plan` and Tyler approves a separate canary.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    summary = build_summary(load_rows(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(summary), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    write_report(args.input, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
