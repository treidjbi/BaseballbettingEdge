"""Shadow audit for market price, side outcomes, and relative favorite behavior.

This diagnostic is analysis-only. It does not change live projections,
verdicts, thresholds, staking, provider order, pick seeding, or calibration.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = ROOT / "dashboard" / "data" / "processed"
DEFAULT_END_DATE = "9999-12-31"
WINDOWS = [
    ("season_to_date_archive", "2026-03-25"),
    ("post_april_8_context", "2026-04-08"),
    ("clean_post_bump", "2026-04-28"),
]
PRICE_BUCKET_ORDER = [
    "< -200",
    "-150 to -200",
    "-130 to -149",
    "-100 to -129",
    "+100 to +119",
    "+120 to +149",
    "+150+",
]
MOVEMENT_NOISE_CENTS = 10
MOVEMENT_ORDER = ["with_side", "against_side", "unchanged"]
LINE_BUCKET_ORDER = ["2.5-3.5", "4.5", "5.5", "6.5", "7.5+", "other"]
MISS_DISTANCE_ORDER = [
    "won by 0.5",
    "won by 1",
    "won by 2+",
    "won by 3+",
]
MODEL_GAP_ORDER = ["model below market", "0-2%", "2-5%", "5%+"]
NO_VIG_MOVEMENT_ORDER = ["toward_side", "away_from_side", "unchanged"]
TIME_BUCKET_ORDER = ["<2h", "2-6h", "6h+", "unknown"]
VERDICT_RANK = {
    "PASS": 0,
    "LEAN": 1,
    "FIRE 1u": 2,
    "FIRE 2u": 3,
}


def to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def american_implied_probability(odds: int) -> float:
    if odds < 0:
        return abs(odds) / (abs(odds) + 100)
    return 100 / (odds + 100)


def no_vig_probabilities(over_odds: int, under_odds: int) -> tuple[float, float]:
    over_raw = american_implied_probability(over_odds)
    under_raw = american_implied_probability(under_odds)
    total = over_raw + under_raw
    if total <= 0:
        return 0.0, 0.0
    return over_raw / total, under_raw / total


def no_vig_side_probability(over_odds: int, under_odds: int, side: str) -> float | None:
    over_prob, under_prob = no_vig_probabilities(over_odds, under_odds)
    if side == "over":
        return over_prob
    if side == "under":
        return under_prob
    return None


def price_sign(odds: int | None) -> str:
    if odds is None:
        return "unknown"
    if odds > 0:
        return "+ money"
    if odds < 0:
        return "- money"
    return "even"


def price_sign_compact(odds: int | None) -> str:
    if odds is None:
        return "unknown"
    if odds > 0:
        return "+ money"
    if odds < 0:
        return "- money"
    return "even"


def price_bucket(odds: int | None) -> str:
    if odds is None:
        return "unknown"
    if odds < -200:
        return "< -200"
    if -200 <= odds <= -150:
        return "-150 to -200"
    if -150 < odds <= -130:
        return "-130 to -149"
    if -130 < odds < 0:
        return "-100 to -129"
    if 100 <= odds <= 119:
        return "+100 to +119"
    if 120 <= odds <= 149:
        return "+120 to +149"
    if odds >= 150:
        return "+150+"
    return "other"


def line_bucket(k_line: object) -> str:
    line = to_float(k_line)
    if line is None:
        return "other"
    if line <= 3.5:
        return "2.5-3.5"
    if line == 4.5:
        return "4.5"
    if line == 5.5:
        return "5.5"
    if line == 6.5:
        return "6.5"
    if line >= 7.5:
        return "7.5+"
    return "other"


def miss_distance_bucket(
    winning_side_name: str,
    actual_ks: object,
    k_line: object,
) -> str:
    actual = to_float(actual_ks)
    line = to_float(k_line)
    if actual is None or line is None or winning_side_name not in {"over", "under"}:
        return "other"
    margin = abs(actual - line)
    if margin <= 0.5:
        return "won by 0.5"
    if margin <= 1.0:
        return "won by 1"
    if margin < 3.0:
        return "won by 2+"
    return "won by 3+"


def model_market_gap_bucket(gap: float | None) -> str:
    if gap is None:
        return "unknown"
    if gap < 0.0:
        return "model below market"
    if gap < 0.02:
        return "0-2%"
    if gap < 0.05:
        return "2-5%"
    return "5%+"


def no_vig_movement_bucket(
    opening_prob: float | None,
    current_prob: float | None,
    noise_floor: float = 0.01,
) -> str:
    if opening_prob is None or current_prob is None:
        return "unknown"
    delta = current_prob - opening_prob
    if delta > noise_floor:
        return "toward_side"
    if delta < -noise_floor:
        return "away_from_side"
    return "unchanged"


def price_movement_bucket(
    opening_odds: object,
    current_odds: object,
    noise_floor: int = MOVEMENT_NOISE_CENTS,
) -> str:
    opening = to_int(opening_odds)
    current = to_int(current_odds)
    if opening is None or current is None:
        return "unknown"

    delta = current - opening
    if delta < -noise_floor:
        return "with_side"
    if delta > noise_floor:
        return "against_side"
    return "unchanged"


def winning_side(actual_ks: object, k_line: object) -> str:
    actual = to_float(actual_ks)
    line = to_float(k_line)
    if actual is None or line is None:
        return "unknown"
    if actual > line:
        return "over"
    if actual < line:
        return "under"
    return "push"


def market_favorite_side(over_odds: object, under_odds: object) -> str:
    over = to_int(over_odds)
    under = to_int(under_odds)
    if over is None or under is None:
        return "unknown"

    over_implied = american_implied_probability(over)
    under_implied = american_implied_probability(under)
    if over_implied > under_implied:
        return "over"
    if under_implied > over_implied:
        return "under"
    return "tie"


def _ev_score(ev_row: object) -> tuple[int, float]:
    if not isinstance(ev_row, dict):
        return (0, 0.0)
    verdict = str(
        ev_row.get("actionable_verdict")
        or ev_row.get("verdict")
        or ev_row.get("raw_verdict")
        or "PASS"
    )
    rank = VERDICT_RANK.get(verdict, 0)
    adj_ev = to_float(ev_row.get("adj_ev"))
    if adj_ev is None:
        adj_ev = to_float(ev_row.get("ev"))
    return (rank, adj_ev or 0.0)


def _ev_win_prob(row: dict, side: str) -> float | None:
    ev_row = row.get("ev_over") if side == "over" else row.get("ev_under")
    if not isinstance(ev_row, dict):
        return None
    return to_float(ev_row.get("win_prob"))


def infer_model_side(row: dict) -> str:
    if row.get("model_side") in {"over", "under"}:
        return str(row["model_side"])
    over_score = _ev_score(row.get("ev_over"))
    under_score = _ev_score(row.get("ev_under"))
    if over_score > under_score:
        return "over"
    if under_score > over_score:
        return "under"
    return "tie"


def infer_model_win_prob(row: dict, side: str) -> float | None:
    explicit = to_float(row.get("model_win_prob"))
    if explicit is not None:
        return explicit
    return _ev_win_prob(row, side)


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def time_to_game_bucket(generated_at: object, game_time: object) -> str:
    generated = _parse_datetime(generated_at)
    game = _parse_datetime(game_time)
    if generated is None or game is None:
        return "unknown"
    hours = (game - generated).total_seconds() / 3600
    if hours < 2:
        return "<2h"
    if hours < 6:
        return "2-6h"
    return "6h+"


def _side_odds(market: dict, side: str) -> int | None:
    if side == "over":
        return to_int(market.get("over_odds"))
    if side == "under":
        return to_int(market.get("under_odds"))
    return None


def _side_opening_odds(market: dict, side: str) -> int | None:
    if side == "over":
        return to_int(market.get("opening_over_odds"))
    if side == "under":
        return to_int(market.get("opening_under_odds"))
    return None


def load_archived_markets(
    archive_dir: Path = ARCHIVE_DIR,
    start_date: str = "2026-03-25",
    end_date: str = DEFAULT_END_DATE,
) -> list[dict]:
    markets: list[dict] = []
    for path in sorted(archive_dir.glob("2026-*.json")):
        date = path.stem
        if date < start_date or date > end_date:
            continue

        payload = json.loads(path.read_text(encoding="utf-8"))
        generated_at = payload.get("generated_at")
        for row in payload.get("pitchers") or []:
            over_odds = to_int(row.get("best_over_odds"))
            under_odds = to_int(row.get("best_under_odds"))
            actual = to_float(row.get("actual_ks"))
            line = to_float(row.get("k_line"))
            if over_odds is None or under_odds is None or actual is None or line is None:
                continue

            winner = winning_side(actual, line)
            if winner != "over" and winner != "under":
                continue

            markets.append(
                {
                    "date": date,
                    "pitcher": row.get("pitcher") or "",
                    "k_line": line,
                    "actual_ks": actual,
                    "winning_side": winner,
                    "over_odds": over_odds,
                    "under_odds": under_odds,
                    "opening_over_odds": to_int(row.get("opening_over_odds")),
                    "opening_under_odds": to_int(row.get("opening_under_odds")),
                    "ref_book": row.get("ref_book") or "unknown",
                    "model_side": infer_model_side(row),
                    "model_win_prob": infer_model_win_prob(row, infer_model_side(row)),
                    "ev_over": row.get("ev_over"),
                    "ev_under": row.get("ev_under"),
                    "book_odds": row.get("book_odds") or {},
                    "generated_at": generated_at,
                    "game_time": row.get("game_time"),
                    "lineup_used": row.get("lineup_used"),
                }
            )
    return markets


def _empty_summary() -> dict:
    return {
        "markets": 0,
        "wins": 0,
        "losses": 0,
        "implied_total": 0.0,
        "avg_implied": None,
        "win_rate": None,
    }


def _finalize_summary(summary: dict) -> dict:
    markets = int(summary["markets"])
    if markets:
        summary["avg_implied"] = round(summary["implied_total"] / markets, 4)
        summary["win_rate"] = round(summary["wins"] / markets, 4)
    summary.pop("implied_total", None)
    return summary


def summarize_side_price_buckets(markets: list[dict]) -> dict[tuple[str, str], dict]:
    summary: dict[tuple[str, str], dict] = defaultdict(_empty_summary)
    for market in markets:
        for side in ("over", "under"):
            odds = _side_odds(market, side)
            if odds is None:
                continue
            key = (side, price_bucket(odds))
            bucket = summary[key]
            bucket["markets"] += 1
            if market.get("winning_side") == side:
                bucket["wins"] += 1
            else:
                bucket["losses"] += 1
            bucket["implied_total"] += american_implied_probability(odds)
    return {key: _finalize_summary(value) for key, value in summary.items()}


def summarize_side_movement_contexts(markets: list[dict]) -> dict[tuple[str, str, str], dict]:
    summary: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {
            "markets": 0,
            "wins": 0,
            "losses": 0,
            "delta_total": 0.0,
            "avg_delta": None,
        }
    )
    for market in markets:
        for side in ("over", "under"):
            opening = _side_opening_odds(market, side)
            current = _side_odds(market, side)
            if opening is None or current is None:
                continue

            movement = price_movement_bucket(opening, current)
            sign_transition = f"{price_sign_compact(opening)} -> {price_sign_compact(current)}"
            key = (side, movement, sign_transition)
            bucket = summary[key]
            bucket["markets"] += 1
            if market.get("winning_side") == side:
                bucket["wins"] += 1
            else:
                bucket["losses"] += 1
            bucket["delta_total"] += current - opening

    finalized = {}
    for key, row in summary.items():
        if row["markets"]:
            row["avg_delta"] = round(row["delta_total"] / row["markets"], 1)
        row.pop("delta_total", None)
        finalized[key] = row
    return finalized


def _basic_count_summary() -> dict:
    return {"markets": 0, "wins": 0, "losses": 0}


def _record_win_loss(bucket: dict, won: bool) -> None:
    bucket["markets"] += 1
    if won:
        bucket["wins"] += 1
    else:
        bucket["losses"] += 1


def summarize_model_vs_favorite(markets: list[dict]) -> dict[str, dict]:
    summary: dict[str, dict] = defaultdict(_basic_count_summary)
    for market in markets:
        model_side = market.get("model_side")
        favorite = market_favorite_side(market.get("over_odds"), market.get("under_odds"))
        if model_side not in {"over", "under"} or favorite not in {"over", "under"}:
            continue
        key = "model_agrees_with_favorite" if model_side == favorite else "model_fades_favorite"
        _record_win_loss(summary[key], market.get("winning_side") == model_side)
    return dict(summary)


def summarize_model_market_gap(markets: list[dict]) -> dict[str, dict]:
    summary: dict[str, dict] = defaultdict(_basic_count_summary)
    for market in markets:
        model_side = market.get("model_side")
        model_prob = to_float(market.get("model_win_prob"))
        over_odds = to_int(market.get("over_odds"))
        under_odds = to_int(market.get("under_odds"))
        if model_side not in {"over", "under"} or model_prob is None or over_odds is None or under_odds is None:
            continue
        market_prob = no_vig_side_probability(over_odds, under_odds, str(model_side))
        if market_prob is None:
            continue
        key = model_market_gap_bucket(model_prob - market_prob)
        _record_win_loss(summary[key], market.get("winning_side") == model_side)
    return dict(summary)


def summarize_no_vig_movement(markets: list[dict]) -> dict[tuple[str, str], dict]:
    summary: dict[tuple[str, str], dict] = defaultdict(_basic_count_summary)
    for market in markets:
        current_over = to_int(market.get("over_odds"))
        current_under = to_int(market.get("under_odds"))
        opening_over = to_int(market.get("opening_over_odds"))
        opening_under = to_int(market.get("opening_under_odds"))
        if None in {current_over, current_under, opening_over, opening_under}:
            continue
        for side in ("over", "under"):
            opening_prob = no_vig_side_probability(opening_over, opening_under, side)
            current_prob = no_vig_side_probability(current_over, current_under, side)
            key = (side, no_vig_movement_bucket(opening_prob, current_prob))
            _record_win_loss(summary[key], market.get("winning_side") == side)
    return dict(summary)


def summarize_pitcher_repeat_errors(
    markets: list[dict],
    min_markets: int = 3,
) -> dict[str, dict]:
    summary: dict[str, dict] = defaultdict(
        lambda: {"markets": 0, "over_wins": 0, "under_wins": 0, "margin_total": 0.0}
    )
    for market in markets:
        pitcher = str(market.get("pitcher") or "")
        if not pitcher:
            continue
        row = summary[pitcher]
        row["markets"] += 1
        if market.get("winning_side") == "over":
            row["over_wins"] += 1
        elif market.get("winning_side") == "under":
            row["under_wins"] += 1
        actual = to_float(market.get("actual_ks"))
        line = to_float(market.get("k_line"))
        if actual is not None and line is not None:
            row["margin_total"] += actual - line

    finalized = {}
    for pitcher, row in summary.items():
        if row["markets"] < min_markets:
            continue
        row["avg_actual_minus_line"] = round(row["margin_total"] / row["markets"], 2)
        row.pop("margin_total", None)
        finalized[pitcher] = row
    return finalized


def _book_side_odds(market: dict, side: str) -> list[tuple[str, int]]:
    book_odds = market.get("book_odds")
    if not isinstance(book_odds, dict):
        return []
    rows = []
    for book, odds in book_odds.items():
        if not isinstance(odds, dict):
            continue
        value = to_int(odds.get(side))
        if value is not None:
            rows.append((str(book), value))
    return rows


def summarize_book_outliers(
    markets: list[dict],
    min_delta: int = 20,
) -> dict[tuple[str, str, str], dict]:
    summary: dict[tuple[str, str, str], dict] = defaultdict(_basic_count_summary)
    for market in markets:
        ref_book = str(market.get("ref_book") or "unknown")
        for side in ("over", "under"):
            book_rows = _book_side_odds(market, side)
            if len(book_rows) < 3:
                continue
            ref_odds = next((odds for book, odds in book_rows if book == ref_book), None)
            if ref_odds is None:
                continue
            market_median = median(odds for _, odds in book_rows)
            delta = ref_odds - market_median
            if delta <= -min_delta:
                outlier = "ref_more_favored"
            elif delta >= min_delta:
                outlier = "ref_less_favored"
            else:
                continue
            key = (ref_book, side, outlier)
            _record_win_loss(summary[key], market.get("winning_side") == side)
    return dict(summary)


def summarize_game_timing(markets: list[dict]) -> dict[str, dict]:
    summary: dict[str, dict] = defaultdict(_basic_count_summary)
    for market in markets:
        model_side = market.get("model_side")
        if model_side not in {"over", "under"}:
            continue
        key = time_to_game_bucket(market.get("generated_at"), market.get("game_time"))
        _record_win_loss(summary[key], market.get("winning_side") == model_side)
    return dict(summary)


def summarize_lineup_state(markets: list[dict]) -> dict[str, dict]:
    summary: dict[str, dict] = defaultdict(_basic_count_summary)
    for market in markets:
        model_side = market.get("model_side")
        if model_side not in {"over", "under"}:
            continue
        key = "confirmed_lineup" if market.get("lineup_used") is True else "projected_lineup"
        _record_win_loss(summary[key], market.get("winning_side") == model_side)
    return dict(summary)


def summarize_line_side_price_contexts(markets: list[dict]) -> dict[tuple[str, str, str], dict]:
    summary: dict[tuple[str, str, str], dict] = defaultdict(_basic_count_summary)
    for market in markets:
        line_key = line_bucket(market.get("k_line"))
        for side in ("over", "under"):
            odds = _side_odds(market, side)
            if odds is None:
                continue
            key = (side, line_key, price_bucket(odds))
            _record_win_loss(summary[key], market.get("winning_side") == side)
    return dict(summary)


def summarize_line_buckets(markets: list[dict]) -> dict[str, dict]:
    summary: dict[str, dict] = defaultdict(_basic_count_summary)
    for market in markets:
        key = line_bucket(market.get("k_line"))
        bucket = summary[key]
        bucket["markets"] += 1
        # This section reports how often each market resolves over/under at a line.
        if market.get("winning_side") == "over":
            bucket["wins"] += 1
        else:
            bucket["losses"] += 1
    return dict(summary)


def summarize_miss_distance(markets: list[dict]) -> dict[str, dict]:
    summary: dict[str, dict] = defaultdict(_basic_count_summary)
    for market in markets:
        key = miss_distance_bucket(
            str(market.get("winning_side") or ""),
            market.get("actual_ks"),
            market.get("k_line"),
        )
        bucket = summary[key]
        bucket["markets"] += 1
        bucket["wins"] += 1
    return dict(summary)


def summarize_book_side_price_buckets(markets: list[dict]) -> dict[tuple[str, str, str], dict]:
    summary: dict[tuple[str, str, str], dict] = defaultdict(_basic_count_summary)
    for market in markets:
        book = str(market.get("ref_book") or "unknown")
        for side in ("over", "under"):
            odds = _side_odds(market, side)
            if odds is None:
                continue
            key = (book, side, price_bucket(odds))
            _record_win_loss(summary[key], market.get("winning_side") == side)
    return dict(summary)


def summarize_winning_price_signs(markets: list[dict]) -> dict[str, dict]:
    all_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    for market in markets:
        winning_odds = _side_odds(market, str(market.get("winning_side")))
        all_counts[price_sign(winning_odds)] += 1

        signs = {
            price_sign(to_int(market.get("over_odds"))),
            price_sign(to_int(market.get("under_odds"))),
        }
        if signs == {"+ money", "- money"}:
            split_counts[price_sign(winning_odds)] += 1

    return {
        "all_markets": dict(all_counts),
        "one_minus_one_plus": dict(split_counts),
    }


def summarize_favorite_results(markets: list[dict]) -> dict[str, dict]:
    summary = {
        "favorite": {"markets": 0, "wins": 0, "losses": 0},
        "underdog": {"markets": 0, "wins": 0, "losses": 0},
        "tie": {"markets": 0, "wins": 0, "losses": 0},
    }
    for market in markets:
        favorite = market_favorite_side(market.get("over_odds"), market.get("under_odds"))
        winner = market.get("winning_side")
        if favorite == "tie":
            summary["tie"]["markets"] += 1
            summary["tie"]["wins"] += 1
            continue
        if favorite == "unknown":
            continue

        summary["favorite"]["markets"] += 1
        summary["underdog"]["markets"] += 1
        if winner == favorite:
            summary["favorite"]["wins"] += 1
            summary["underdog"]["losses"] += 1
        else:
            summary["favorite"]["losses"] += 1
            summary["underdog"]["wins"] += 1
    return summary


def summarize_favorite_by_side(markets: list[dict]) -> dict[str, dict]:
    summary: dict[str, dict] = defaultdict(lambda: {"markets": 0, "wins": 0, "losses": 0})
    for market in markets:
        favorite = market_favorite_side(market.get("over_odds"), market.get("under_odds"))
        if favorite not in {"over", "under"}:
            continue
        bucket = summary[favorite]
        bucket["markets"] += 1
        if market.get("winning_side") == favorite:
            bucket["wins"] += 1
        else:
            bucket["losses"] += 1
    return dict(summary)


def _format_pct(value: float | None) -> str:
    return "--" if value is None else f"{value:.1%}"


def _rate(wins: int, markets: int) -> str:
    return "--" if markets == 0 else f"{wins / markets:.1%}"


def _count_pct(count: int, total: int) -> str:
    return "--" if total == 0 else f"{count / total:.1%}"


def _render_side_bucket_table(lines: list[str], summary: dict[tuple[str, str], dict]) -> None:
    lines.extend(
        [
            "| Side | Price Bucket | Markets | W-L | Win Rate | Avg Implied |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for side in ("over", "under"):
        for bucket_name in PRICE_BUCKET_ORDER:
            row = summary.get((side, bucket_name))
            if not row:
                continue
            lines.append(
                f"| `{side}` | `{bucket_name}` | {row['markets']} | "
                f"{row['wins']}-{row['losses']} | {_format_pct(row['win_rate'])} | "
                f"{_format_pct(row['avg_implied'])} |"
            )


def _render_movement_context_table(
    lines: list[str],
    summary: dict[tuple[str, str, str], dict],
) -> None:
    lines.extend(
        [
            "| Side | Movement | Opening -> Current | Markets | W-L | Win Rate | Avg Delta |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for side in ("over", "under"):
        for movement in MOVEMENT_ORDER:
            rows = [
                (transition, row)
                for (row_side, row_movement, transition), row in summary.items()
                if row_side == side and row_movement == movement
            ]
            for transition, row in sorted(rows):
                lines.append(
                    f"| `{side}` | `{movement}` | `{transition}` | {row['markets']} | "
                    f"{row['wins']}-{row['losses']} | {_rate(row['wins'], row['markets'])} | "
                    f"{row['avg_delta']:+.1f} |"
                )


def _render_model_vs_favorite(lines: list[str], summary: dict[str, dict]) -> None:
    lines.extend(
        [
            "| Relationship | Markets | W-L | Win Rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for key in ("model_agrees_with_favorite", "model_fades_favorite"):
        row = summary.get(key)
        if not row:
            continue
        lines.append(
            f"| `{key}` | {row['markets']} | {row['wins']}-{row['losses']} | "
            f"{_rate(row['wins'], row['markets'])} |"
        )


def _render_model_market_gap(lines: list[str], summary: dict[str, dict]) -> None:
    lines.extend(
        [
            "| Model Edge Over Market | Markets | W-L | Win Rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for key in MODEL_GAP_ORDER:
        row = summary.get(key)
        if not row:
            continue
        lines.append(
            f"| `{key}` | {row['markets']} | {row['wins']}-{row['losses']} | "
            f"{_rate(row['wins'], row['markets'])} |"
        )


def _render_no_vig_movement(lines: list[str], summary: dict[tuple[str, str], dict]) -> None:
    lines.extend(
        [
            "| Side | No-Vig Movement | Markets | W-L | Win Rate |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for side in ("over", "under"):
        for movement in NO_VIG_MOVEMENT_ORDER:
            row = summary.get((side, movement))
            if not row:
                continue
            lines.append(
                f"| `{side}` | `{movement}` | {row['markets']} | "
                f"{row['wins']}-{row['losses']} | {_rate(row['wins'], row['markets'])} |"
            )


def _render_line_buckets(lines: list[str], summary: dict[str, dict]) -> None:
    lines.extend(
        [
            "| K Line Bucket | Markets | Over-Under Outcomes | Over Rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for key in LINE_BUCKET_ORDER:
        row = summary.get(key)
        if not row:
            continue
        lines.append(
            f"| `{key}` | {row['markets']} | {row['wins']}-{row['losses']} | "
            f"{_rate(row['wins'], row['markets'])} |"
        )


def _render_miss_distance(lines: list[str], summary: dict[str, dict]) -> None:
    lines.extend(
        [
            "| Margin Bucket | Markets | Share |",
            "| --- | ---: | ---: |",
        ]
    )
    total = sum(row["markets"] for row in summary.values())
    for key in MISS_DISTANCE_ORDER:
        row = summary.get(key)
        if not row:
            continue
        lines.append(f"| `{key}` | {row['markets']} | {_count_pct(row['markets'], total)} |")


def _render_pitcher_repeat_tendencies(
    lines: list[str],
    summary: dict[str, dict],
    limit: int = 12,
) -> None:
    lines.extend(
        [
            "| Pitcher | Markets | Over Wins | Under Wins | Avg Actual-Line |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    rows = sorted(
        summary.items(),
        key=lambda item: (abs(item[1]["avg_actual_minus_line"]), item[1]["markets"]),
        reverse=True,
    )
    for pitcher, row in rows[:limit]:
        lines.append(
            f"| `{pitcher}` | {row['markets']} | {row['over_wins']} | "
            f"{row['under_wins']} | {row['avg_actual_minus_line']:+.2f} |"
        )


def _render_book_side_price_buckets(
    lines: list[str],
    summary: dict[tuple[str, str, str], dict],
    min_markets: int = 10,
) -> None:
    lines.extend(
        [
            "| Book | Side | Price Bucket | Markets | W-L | Win Rate |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    rows = [
        (book, side, bucket_name, row)
        for (book, side, bucket_name), row in summary.items()
        if row["markets"] >= min_markets
    ]
    for book, side, bucket_name, row in sorted(rows):
        lines.append(
            f"| `{book}` | `{side}` | `{bucket_name}` | {row['markets']} | "
            f"{row['wins']}-{row['losses']} | {_rate(row['wins'], row['markets'])} |"
        )


def _render_book_outliers(
    lines: list[str],
    summary: dict[tuple[str, str, str], dict],
    min_markets: int = 3,
) -> None:
    lines.extend(
        [
            "| Ref Book | Side | Outlier Type | Markets | W-L | Win Rate |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    rows = [
        (book, side, outlier, row)
        for (book, side, outlier), row in summary.items()
        if row["markets"] >= min_markets
    ]
    for book, side, outlier, row in sorted(rows):
        lines.append(
            f"| `{book}` | `{side}` | `{outlier}` | {row['markets']} | "
            f"{row['wins']}-{row['losses']} | {_rate(row['wins'], row['markets'])} |"
        )


def _render_basic_summary_table(lines: list[str], summary: dict[str, dict], label: str) -> None:
    lines.extend(
        [
            f"| {label} | Markets | W-L | Win Rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for key, row in sorted(summary.items()):
        lines.append(
            f"| `{key}` | {row['markets']} | {row['wins']}-{row['losses']} | "
            f"{_rate(row['wins'], row['markets'])} |"
        )


def _render_line_side_price_contexts(
    lines: list[str],
    summary: dict[tuple[str, str, str], dict],
    min_markets: int = 8,
) -> None:
    lines.extend(
        [
            "| Side | K Line Bucket | Price Bucket | Markets | W-L | Win Rate |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    rows = [
        (side, line_key, price_key, row)
        for (side, line_key, price_key), row in summary.items()
        if row["markets"] >= min_markets
    ]
    order = {value: index for index, value in enumerate(LINE_BUCKET_ORDER)}
    for side, line_key, price_key, row in sorted(
        rows,
        key=lambda item: (item[0], order.get(item[1], 99), item[2]),
    ):
        lines.append(
            f"| `{side}` | `{line_key}` | `{price_key}` | {row['markets']} | "
            f"{row['wins']}-{row['losses']} | {_rate(row['wins'], row['markets'])} |"
        )


def build_report(markets: list[dict], title: str = "Market Price Outcome Audit") -> str:
    sign_summary = summarize_winning_price_signs(markets)
    favorite_summary = summarize_favorite_results(markets)
    favorite_by_side = summarize_favorite_by_side(markets)
    side_bucket_summary = summarize_side_price_buckets(markets)
    movement_context_summary = summarize_side_movement_contexts(markets)
    model_favorite_summary = summarize_model_vs_favorite(markets)
    model_gap_summary = summarize_model_market_gap(markets)
    no_vig_movement_summary = summarize_no_vig_movement(markets)
    line_summary = summarize_line_buckets(markets)
    miss_summary = summarize_miss_distance(markets)
    book_summary = summarize_book_side_price_buckets(markets)
    pitcher_repeat_summary = summarize_pitcher_repeat_errors(markets)
    book_outlier_summary = summarize_book_outliers(markets)
    game_timing_summary = summarize_game_timing(markets)
    lineup_summary = summarize_lineup_state(markets)
    line_side_price_summary = summarize_line_side_price_contexts(markets)
    all_total = sum(sign_summary["all_markets"].values())
    split_total = sum(sign_summary["one_minus_one_plus"].values())

    lines = [
        f"# {title}",
        "",
        "This audit is shadow-only. It does not change live lambda, verdicts, thresholds, staking, provider order, pick seeding, or calibration.",
        "",
        "## Scope",
        "",
        f"- Graded whole-market pitcher rows: `{len(markets)}`",
        "- Source: archived `dashboard/data/processed/YYYY-MM-DD.json` pitcher markets, so PASS-level markets are included.",
        "- Market favorite handles relative pricing, e.g. `-115` vs `-105`, not only plus-money versus minus-money.",
        "",
        "## Winning Side Price Sign",
        "",
        f"- All markets: minus-priced side won `{sign_summary['all_markets'].get('- money', 0)}/{all_total}` ({_count_pct(sign_summary['all_markets'].get('- money', 0), all_total)}); plus-priced side won `{sign_summary['all_markets'].get('+ money', 0)}/{all_total}` ({_count_pct(sign_summary['all_markets'].get('+ money', 0), all_total)}).",
        f"- One-minus/one-plus markets only: minus-priced side won `{sign_summary['one_minus_one_plus'].get('- money', 0)}/{split_total}` ({_count_pct(sign_summary['one_minus_one_plus'].get('- money', 0), split_total)}); plus-priced side won `{sign_summary['one_minus_one_plus'].get('+ money', 0)}/{split_total}` ({_count_pct(sign_summary['one_minus_one_plus'].get('+ money', 0), split_total)}).",
        "",
        "## Market Favorite Results",
        "",
    ]

    favorite = favorite_summary["favorite"]
    underdog = favorite_summary["underdog"]
    lines.extend(
        [
            f"- Favorite side won `{favorite['wins']}/{favorite['markets']}` ({_rate(favorite['wins'], favorite['markets'])}).",
            f"- Underdog side won `{underdog['wins']}/{underdog['markets']}` ({_rate(underdog['wins'], underdog['markets'])}).",
        ]
    )
    for side in ("over", "under"):
        row = favorite_by_side.get(side)
        if row:
            lines.append(
                f"- When `{side}` was the market favorite: `{row['wins']}/{row['markets']}` wins ({_rate(row['wins'], row['markets'])})."
            )

    lines.extend(["", "## Side Price Buckets", ""])
    _render_side_bucket_table(lines, side_bucket_summary)
    lines.extend(["", "## Model Versus Market Favorite", ""])
    _render_model_vs_favorite(lines, model_favorite_summary)
    lines.extend(["", "## Model Edge Over No-Vig Market", ""])
    _render_model_market_gap(lines, model_gap_summary)
    lines.extend(["", "## No-Vig Movement", ""])
    _render_no_vig_movement(lines, no_vig_movement_summary)
    lines.extend(["", "## Line Buckets", ""])
    _render_line_buckets(lines, line_summary)
    lines.extend(["", "## Miss Distance", ""])
    _render_miss_distance(lines, miss_summary)
    lines.extend(["", "## Pitcher Repeat Tendencies", ""])
    _render_pitcher_repeat_tendencies(lines, pitcher_repeat_summary)
    lines.extend(
        [
            "",
            "## Book Side Price Buckets",
            "",
            "Rows with fewer than 10 markets are hidden to reduce noise.",
            "",
        ]
    )
    _render_book_side_price_buckets(lines, book_summary)
    lines.extend(
        [
            "",
            "## Book Outliers",
            "",
            "Rows compare the reference book side price against the median available book price for that side; small rows are hidden.",
            "",
        ]
    )
    _render_book_outliers(lines, book_outlier_summary)
    lines.extend(["", "## Game Timing", ""])
    _render_basic_summary_table(lines, game_timing_summary, "Time To Game")
    lines.extend(["", "## Lineup State", ""])
    _render_basic_summary_table(lines, lineup_summary, "Lineup State")
    lines.extend(
        [
            "",
            "## Line Side Price Contexts",
            "",
            "Rows with fewer than 8 markets are hidden to reduce noise.",
            "",
        ]
    )
    _render_line_side_price_contexts(lines, line_side_price_summary)
    lines.extend(
        [
            "",
            "## Side Price Movement Contexts",
            "",
            "Movement is side-specific: negative delta means that side became more expensive/more favored (`with_side`); positive delta means that side became cheaper (`against_side`).",
            "",
        ]
    )
    _render_movement_context_table(lines, movement_context_summary)
    lines.extend(
        [
            "",
            "## Recommended Next Read",
            "",
            "- Use this as market context beside the bet-conversion audit before changing model selection or staking.",
            "- Watch whether current-regime under buckets stay disconnected from their implied probabilities.",
            "- Treat price/favorite behavior as a shadow guardrail candidate, not a live betting rule, until it survives more slates.",
        ]
    )
    return "\n".join(lines)


def build_multi_window_report(
    archive_dir: Path = ARCHIVE_DIR,
    end_date: str = DEFAULT_END_DATE,
) -> str:
    sections: list[str] = []
    for label, start_date in WINDOWS:
        markets = load_archived_markets(archive_dir, start_date=start_date, end_date=end_date)
        title = f"Market Price Outcome Audit - {label}"
        sections.append(build_report(markets, title=title))
    return "\n\n---\n\n".join(sections)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit whole-market price outcomes.")
    parser.add_argument("--archive-dir", type=Path, default=ARCHIVE_DIR)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(build_multi_window_report(args.archive_dir, end_date=args.end_date))


if __name__ == "__main__":
    main()
