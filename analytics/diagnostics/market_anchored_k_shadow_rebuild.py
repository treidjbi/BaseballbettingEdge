"""Shadow-only market-anchored pitcher K rebuild diagnostic.

This report tests a from-scratch model shape where the market-implied K
projection is the prior and the current baseball projection is a shrink-adjusted
input. It does not change live lambda, verdicts, thresholds, staking, provider
order, notifications, locks, retention, calibration, dashboard artifacts, or
source-of-truth behavior.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "market_anchored_k_shadow_rebuild.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
PROJECTION_NAMES = ("current_model", "market_implied", "market_anchor")
SELECTOR_NAMES = (
    "current_action_fire",
    "market_price_only_favorite",
    "market_anchor_side_agrees",
    "market_anchor_core",
    "market_anchor_strict",
)


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _clamp_probability(value: float) -> float:
    return max(0.0001, min(0.9999, value))


def poisson_cdf(k: int, lam: float) -> float:
    """Return P(X <= k) for a Poisson random variable."""

    if k < 0:
        return 0.0
    lam = max(0.0, lam)
    term = math.exp(-lam)
    total = term
    for idx in range(1, k + 1):
        term *= lam / idx
        total += term
    return max(0.0, min(1.0, total))


def poisson_over_probability(k_line: float, lam: float) -> float:
    """Return the probability of clearing a half-run K line."""

    under_max = math.floor(k_line)
    return _clamp_probability(1.0 - poisson_cdf(under_max, lam))


def market_implied_projection(k_line: float, over_probability: float) -> float:
    """Invert a no-vig over probability into a Poisson K projection."""

    target = _clamp_probability(over_probability)
    low = 0.0
    high = max(12.0, k_line + 8.0)
    while poisson_over_probability(k_line, high) < target and high < 40.0:
        high *= 1.5

    for _ in range(72):
        mid = (low + high) / 2.0
        if poisson_over_probability(k_line, mid) < target:
            low = mid
        else:
            high = mid
    return round((low + high) / 2.0, 4)


def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def _verdict(row: dict[str, Any]) -> str:
    return str(
        row.get("display_verdict")
        or row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("current_verdict")
        or row.get("verdict")
        or ""
    ).strip()


def _is_fire(row: dict[str, Any]) -> bool:
    return _verdict(row).startswith("FIRE")


def current_projection(row: dict[str, Any]) -> float | None:
    for key in ("projected_ks", "applied_lambda", "raw_lambda", "lambda"):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return None


def _line(row: dict[str, Any]) -> float | None:
    return _to_float(row.get("k_line") or row.get("locked_k_line"))


def _side(row: dict[str, Any]) -> str:
    return str(row.get("side") or "").strip().lower()


def _market_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    line = _line(row)
    line_text = "unknown" if line is None else f"{line:.1f}"
    return (
        str(row.get("slate_date") or row.get("date") or ""),
        str(row.get("context_snapshot") or "official_close"),
        str(row.get("normalized_pitcher") or row.get("pitcher") or "").strip().lower(),
        line_text,
    )


def _over_probability_from_row(row: dict[str, Any]) -> float | None:
    probability = _to_float(row.get("no_vig_side_probability"))
    if probability is None:
        return None
    if _side(row) == "over":
        return _clamp_probability(probability)
    if _side(row) == "under":
        return _clamp_probability(1.0 - probability)
    return None


def market_over_probability(row: dict[str, Any]) -> float | None:
    return _over_probability_from_row(row)


def market_projection_for_row(row: dict[str, Any]) -> float | None:
    line = _line(row)
    over_probability = market_over_probability(row)
    if line is None or over_probability is None:
        return None
    return market_implied_projection(line, over_probability)


def baseball_blend_weight(row: dict[str, Any]) -> float:
    """Return how much current baseball projection to retain over market prior."""

    weight = 0.35
    quality = str(row.get("quality_gate_level") or "").strip().lower()
    relationship = str(row.get("model_market_relationship") or "").strip()
    opportunity = str(row.get("opportunity_bucket") or "").strip().lower()
    leash = str(row.get("leash_risk_bucket") or "").strip().lower()
    line = _line(row)

    if quality and quality != "clean":
        weight -= 0.10
    if relationship == "model_fades_favorite":
        weight -= 0.10
    if opportunity == "short_leash" or leash in {"high", "medium"}:
        weight -= 0.10
    if line is not None and line >= 7.5:
        weight -= 0.05

    return max(0.15, min(0.45, weight))


def market_anchor_projection(row: dict[str, Any]) -> float | None:
    market_projection = market_projection_for_row(row)
    current = current_projection(row)
    if market_projection is None:
        return None if current is None else round(current, 4)
    if current is None:
        return round(market_projection, 4)

    weight = baseball_blend_weight(row)
    return round(market_projection + ((current - market_projection) * weight), 4)


def _side_probability(row: dict[str, Any], projection: float | None) -> float | None:
    line = _line(row)
    if projection is None or line is None:
        return None
    over_probability = poisson_over_probability(line, projection)
    if _side(row) == "over":
        return over_probability
    if _side(row) == "under":
        return _clamp_probability(1.0 - over_probability)
    return None


def anchored_edge(row: dict[str, Any]) -> float | None:
    probability = _side_probability(row, market_anchor_projection(row))
    market_probability = _to_float(row.get("no_vig_side_probability"))
    if probability is None or market_probability is None:
        return None
    return round(probability - market_probability, 4)


def _projected_side(row: dict[str, Any], projection: float | None) -> str | None:
    line = _line(row)
    if projection is None or line is None:
        return None
    if projection > line:
        return "over"
    if projection < line:
        return "under"
    return None


def selector_labels(row: dict[str, Any]) -> set[str]:
    labels: set[str] = set()
    side = _side(row)
    market_favorite = str(row.get("market_favorite_side") or "").strip().lower()
    relationship = str(row.get("model_market_relationship") or "").strip()
    quality = str(row.get("quality_gate_level") or "").strip().lower()
    opportunity = str(row.get("opportunity_bucket") or "").strip().lower()
    leash = str(row.get("leash_risk_bucket") or "").strip().lower()
    timing = str(row.get("bet_timing_window") or "").strip().lower()
    line = _line(row)
    no_vig_gap = _to_float(row.get("model_no_vig_gap"))
    edge = anchored_edge(row)
    anchored_side = _projected_side(row, market_anchor_projection(row))

    if _is_fire(row):
        labels.add("current_action_fire")
    if side and side == market_favorite:
        labels.add("market_price_only_favorite")
    if anchored_side == side:
        labels.add("market_anchor_side_agrees")

    if anchored_side == side and edge is not None and 0.005 <= edge <= 0.12:
        if no_vig_gap is None or no_vig_gap >= 0.0:
            labels.add("market_anchor_core")

    stable_workload = opportunity != "short_leash" and leash not in {"high", "medium"}
    stable_line = line is None or line <= 6.5
    stable_timing = timing not in {"post_start", "pre_5"}
    clean_quality = quality in {"", "clean", "none"}
    if (
        "market_anchor_core" in labels
        and relationship == "model_agrees_with_favorite"
        and side
        and side == market_favorite
        and clean_quality
        and stable_workload
        and stable_line
        and stable_timing
    ):
        labels.add("market_anchor_strict")

    return labels


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
        if _line(row) is None:
            continue
        if _to_float(row.get("actual_ks")) is None:
            continue
        selected.append(row)
    return selected


def tracked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _is_true(row.get("is_tracked_pick"))]


def build_markets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = _market_key(row)
        market = grouped.setdefault(
            key,
            {
                "key": key,
                "rows": [],
                "over_row": None,
                "under_row": None,
                "over_probability": None,
            },
        )
        market["rows"].append(row)
        if _side(row) == "over" and market["over_row"] is None:
            market["over_row"] = row
        if _side(row) == "under" and market["under_row"] is None:
            market["under_row"] = row

    markets: list[dict[str, Any]] = []
    for market in grouped.values():
        over_row = market.get("over_row")
        under_row = market.get("under_row")
        over_probability = None
        if isinstance(over_row, dict):
            over_probability = _over_probability_from_row(over_row)
        if over_probability is None and isinstance(under_row, dict):
            over_probability = _over_probability_from_row(under_row)
        market["over_probability"] = over_probability
        markets.append(market)

    return sorted(markets, key=lambda market: market["key"])


def _market_reference_row(market: dict[str, Any]) -> dict[str, Any] | None:
    over_row = market.get("over_row")
    if isinstance(over_row, dict):
        return over_row
    under_row = market.get("under_row")
    if isinstance(under_row, dict):
        return under_row
    rows = market.get("rows") or []
    return rows[0] if rows else None


def _winning_side(row: dict[str, Any]) -> str | None:
    actual = _to_float(row.get("actual_ks"))
    line = _line(row)
    if actual is None or line is None:
        return None
    if actual > line:
        return "over"
    if actual < line:
        return "under"
    return None


def _projection_for_market(name: str, market: dict[str, Any]) -> float | None:
    row = _market_reference_row(market)
    if row is None:
        return None
    if name == "current_model":
        return current_projection(row)
    if name == "market_implied":
        over_probability = market.get("over_probability")
        line = _line(row)
        if over_probability is None or line is None:
            return None
        return market_implied_projection(line, float(over_probability))
    if name == "market_anchor":
        return market_anchor_projection(row)
    raise ValueError(f"unknown projection: {name}")


def _empty_score() -> dict[str, Any]:
    return {
        "rows": 0,
        "wins": 0,
        "losses": 0,
        "pnl": 0.0,
        "roi": 0.0,
        "mae": None,
        "rmse": None,
        "mean_error": None,
        "side_wins": 0,
        "side_losses": 0,
        "side_accuracy": None,
    }


def _score_selector_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    score = _empty_score()
    for row in rows:
        score["rows"] += 1
        if row.get("result") == "win":
            score["wins"] += 1
        elif row.get("result") == "loss":
            score["losses"] += 1
        score["pnl"] = round(score["pnl"] + _row_pnl(row), 3)
    if score["rows"]:
        score["roi"] = round(score["pnl"] / score["rows"], 4)
    return score


def _projection_score(name: str, markets: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[float] = []
    side_wins = 0
    side_losses = 0
    for market in markets:
        row = _market_reference_row(market)
        if row is None:
            continue
        projection = _projection_for_market(name, market)
        actual = _to_float(row.get("actual_ks"))
        if projection is None or actual is None:
            continue
        errors.append(actual - projection)
        projected_side = _projected_side(row, projection)
        winning_side = _winning_side(row)
        if projected_side and winning_side:
            if projected_side == winning_side:
                side_wins += 1
            else:
                side_losses += 1

    score = _empty_score()
    score["rows"] = len(errors)
    score["side_wins"] = side_wins
    score["side_losses"] = side_losses
    side_total = side_wins + side_losses
    if errors:
        score["mean_error"] = round(sum(errors) / len(errors), 3)
        score["mae"] = round(sum(abs(error) for error in errors) / len(errors), 3)
        score["rmse"] = round(math.sqrt(sum(error * error for error in errors) / len(errors)), 3)
    if side_total:
        score["side_accuracy"] = round(side_wins / side_total, 4)
    return score


def _selector_scoreboard(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in SELECTOR_NAMES}
    for row in rows:
        labels = selector_labels(row)
        for label in labels:
            if label in buckets:
                buckets[label].append(row)
    return {name: _score_selector_rows(bucket_rows) for name, bucket_rows in buckets.items()}


def _slice_risks(rows: list[dict[str, Any]], selector: str, *, min_rows: int = 10) -> list[dict[str, Any]]:
    selected = [row for row in rows if selector in selector_labels(row)]
    risks: list[dict[str, Any]] = []
    for field in ("side", "line_bucket", "price_sign", "quality_gate_level", "model_market_relationship"):
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in selected:
            grouped[str(row.get(field) or "unknown")].append(row)
        for bucket, bucket_rows in grouped.items():
            score = _score_selector_rows(bucket_rows)
            if score["rows"] >= min_rows and score["pnl"] < 0:
                risks.append(
                    {
                        "selector": selector,
                        "field": field,
                        "bucket": bucket,
                        "rows": score["rows"],
                        "pnl": score["pnl"],
                        "roi": score["roi"],
                    }
                )
    risks.sort(key=lambda item: (float(item["pnl"]), -int(item["rows"])))
    return risks


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = analysis_rows(rows)
    tracked = tracked_rows(selected)
    markets = build_markets(selected)
    tracked_markets = build_markets(tracked)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "analysis_rows": len(selected),
        "tracked_rows": len(tracked),
        "market_count": len(markets),
        "tracked_market_count": len(tracked_markets),
        "projection_scoreboard": {name: _projection_score(name, markets) for name in PROJECTION_NAMES},
        "tracked_projection_scoreboard": {
            name: _projection_score(name, tracked_markets) for name in PROJECTION_NAMES
        },
        "tracked_selector_scoreboard": _selector_scoreboard(tracked),
        "official_close_selector_scoreboard": _selector_scoreboard(selected),
        "market_anchor_core_risks": _slice_risks(tracked, "market_anchor_core"),
        "market_anchor_strict_risks": _slice_risks(tracked, "market_anchor_strict", min_rows=5),
    }


def _format_number(value: Any, digits: int = 3) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:.{digits}f}"


def _format_percent(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:+.1%}"


def _format_pnl(value: Any) -> str:
    number = _to_float(value) or 0.0
    return f"{number:+.2f}"


def _render_projection_table(lines: list[str], title: str, scoreboard: dict[str, dict[str, Any]]) -> None:
    lines.extend(
        [
            f"## {title}",
            "",
            "| Projection | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in PROJECTION_NAMES:
        score = scoreboard.get(name, _empty_score())
        lines.append(
            f"| `{name}` | {score['rows']} | {_format_number(score['mean_error'])} | "
            f"{_format_number(score['mae'])} | {_format_number(score['rmse'])} | "
            f"{score['side_wins']}-{score['side_losses']} | {_format_percent(score['side_accuracy'])} |"
        )
    lines.append("")


def _render_selector_table(lines: list[str], title: str, scoreboard: dict[str, dict[str, Any]]) -> None:
    lines.extend(
        [
            f"## {title}",
            "",
            "| Selector | Rows | W-L | PnL | ROI |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in SELECTOR_NAMES:
        score = scoreboard.get(name, _empty_score())
        lines.append(
            f"| `{name}` | {score['rows']} | {score['wins']}-{score['losses']} | "
            f"{_format_pnl(score['pnl'])} | {_format_percent(score['roi'])} |"
        )
    lines.append("")


def _render_risks(lines: list[str], title: str, risks: list[dict[str, Any]]) -> None:
    lines.extend([f"## {title}", ""])
    if not risks:
        lines.append("- No negative tracked slices above the minimum sample floor.")
        lines.append("")
        return
    for risk in risks[:8]:
        lines.append(
            f"- `{risk['selector']}` `{risk['field']}={risk['bucket']}`: "
            f"{risk['rows']} rows, {_format_pnl(risk['pnl'])}, {_format_percent(risk['roi'])} ROI."
        )
    lines.append("")


def render_report(summary: dict[str, Any]) -> str:
    projection = summary.get("projection_scoreboard", {})
    tracked_selectors = summary.get("tracked_selector_scoreboard", {})
    strict_score = tracked_selectors.get("market_anchor_strict", _empty_score())
    core_score = tracked_selectors.get("market_anchor_core", _empty_score())
    current_fire = tracked_selectors.get("current_action_fire", _empty_score())

    lines = [
        "# Market Anchored K Shadow Rebuild",
        "",
        f"Generated at: `{summary.get('generated_at', 'unknown')}`",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.",
        "",
        "## Executive Read",
        "",
        f"- Total source rows: `{summary.get('total_rows', 0)}`",
        f"- Clean official-close side rows analyzed: `{summary.get('analysis_rows', 0)}`",
        f"- Clean tracked rows analyzed: `{summary.get('tracked_rows', 0)}`",
        f"- Official-close market count: `{summary.get('market_count', 0)}`",
        f"- Current FIRE tracked selector: `{current_fire['rows']}` rows, `{current_fire['wins']}-{current_fire['losses']}`, `{_format_pnl(current_fire['pnl'])}`, `{_format_percent(current_fire['roi'])}` ROI.",
        f"- Market-anchor core tracked selector: `{core_score['rows']}` rows, `{core_score['wins']}-{core_score['losses']}`, `{_format_pnl(core_score['pnl'])}`, `{_format_percent(core_score['roi'])}` ROI.",
        f"- Market-anchor strict tracked selector: `{strict_score['rows']}` rows, `{strict_score['wins']}-{strict_score['losses']}`, `{_format_pnl(strict_score['pnl'])}`, `{_format_percent(strict_score['roi'])}` ROI.",
        "",
        "## Rebuild Shape",
        "",
        "- Start from no-vig market probability and K line to infer a market-implied Poisson projection.",
        "- Add only a shrink-adjusted share of the current baseball projection back into that market prior.",
        "- Reduce the baseball share when quality, workload, high-line, or market-fade context says the raw model should be trusted less.",
        "- Score selection with runtime-safe labels first; use results, CLV, and actual opportunity only for validation and explanation.",
        "",
    ]

    _render_projection_table(lines, "Projection Scoreboard", projection)
    _render_projection_table(
        lines,
        "Tracked-Market Projection Scoreboard",
        summary.get("tracked_projection_scoreboard", {}),
    )
    _render_selector_table(lines, "Tracked-Pick Selector Scoreboard", tracked_selectors)
    _render_selector_table(
        lines,
        "Theoretical Official-Close Selector Scoreboard",
        summary.get("official_close_selector_scoreboard", {}),
    )
    _render_risks(lines, "Market-Anchor Core Slice Risks", summary.get("market_anchor_core_risks", []))
    _render_risks(lines, "Market-Anchor Strict Slice Risks", summary.get("market_anchor_strict_risks", []))
    lines.extend(
        [
            "## Read Rule",
            "",
            "- This is a shadow rebuild diagnostic, not a production model proposal.",
            "- Prefer the market-anchored shape only if it beats current FIRE selection and does not simply select a tiny, one-slate, one-side bucket.",
            "- The theoretical official-close table can suggest direction, but tracked-pick performance is the cleaner first decision read.",
            "- A live v2 selector would still need a separate plan, a feature flag, rollback path, and side/K-line/price/provider/CLV/workload/Path B/rolling-window survival.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_report(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    summary = build_summary(load_rows(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(summary), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    summary = write_report(args.input, args.output)
    print(
        f"Wrote {args.output} "
        f"({summary['analysis_rows']} clean rows, {summary['tracked_rows']} tracked rows)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
