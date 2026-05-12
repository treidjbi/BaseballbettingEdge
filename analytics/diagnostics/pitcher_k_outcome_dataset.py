"""Build a shadow-only pitcher K outcome research dataset.

This diagnostic reads committed production artifacts and writes local research
outputs only. It must not change live picks, thresholds, staking, provider
order, notifications, or calibration.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analytics.diagnostics.market_price_outcome_audit import (  # noqa: E402
    american_implied_probability,
    infer_model_side,
    infer_model_win_prob,
    market_favorite_side,
    no_vig_side_probability,
    price_bucket,
    winning_side,
)
from pipeline.name_utils import normalize  # noqa: E402


ARCHIVE_DIR = ROOT / "dashboard" / "data" / "processed"
PICKS_HISTORY = ROOT / "data" / "picks_history.json"
OUTPUT_JSONL = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_SUMMARY = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset_summary.md"
CLEAN_WINDOW_START = "2026-04-28"

APPROVED_CONTEXT_SNAPSHOTS = {
    "official_close",
    "opening",
    "pre_120",
    "pre_60",
    "pre_30",
    "pre_15",
    "pre_5",
    "final_pre_start",
}

REQUIRED_DATASET_FIELDS = {
    "dataset_key",
    "slate_date",
    "context_snapshot",
    "pitcher",
    "normalized_pitcher",
    "side",
    "k_line",
    "bookmaker_key",
    "american_odds",
    "price_sign",
    "price_bucket",
    "market_favorite_side",
    "model_side",
    "model_win_prob",
    "model_no_vig_gap",
    "projected_ks",
    "k_margin_to_line",
    "verdict",
    "quality_gate_level",
    "actual_ks",
    "result",
    "theoretical_pnl",
    "home_away",
    "opp_team",
    "lineup_used",
    "provider",
    "market_consensus",
    "bet_value_consensus",
    "broad_confirmation",
    "source_artifact_path",
    "is_tracked_pick",
    "bet_time_line",
    "bet_time_odds",
    "bet_time_book",
    "closing_line",
    "price_clv_cents",
    "line_clv_delta",
    "beat_close_price",
    "beat_close_line",
    "model_market_relationship",
    "model_edge_bucket",
    "projection_margin_bucket",
    "pitcher_throws",
    "lineup_count",
    "lineup_right_batters",
    "lineup_left_batters",
    "lineup_switch_batters",
    "handedness_matchup_bucket",
    "avg_ip",
    "recent_start_count",
    "opportunity_bucket",
    "leash_risk_bucket",
    "actual_ip",
    "actual_pitch_count",
    "batters_faced",
}


def _to_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalized(value: Any) -> str:
    return normalize(str(value or "")).strip()


def _line_text(value: Any) -> str:
    line = _to_float(value)
    if line is None:
        return "unknown"
    return f"{line:.1f}"


def build_dataset_key(
    *,
    slate_date: str,
    context_snapshot: str,
    normalized_pitcher: str,
    side: str,
    k_line: Any,
) -> str:
    return ":".join(
        [
            str(slate_date),
            str(context_snapshot),
            _normalized(normalized_pitcher),
            str(side).strip().lower(),
            _line_text(k_line),
        ]
    )


def validate_dataset_row(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in sorted(REQUIRED_DATASET_FIELDS):
        if field not in row:
            errors.append(f"missing required field: {field}")

    if row.get("context_snapshot") not in APPROVED_CONTEXT_SNAPSHOTS:
        errors.append("context_snapshot must be one of approved pregame/official values")

    if row.get("side") not in {"over", "under"}:
        errors.append("side must be over or under")

    expected_key = build_dataset_key(
        slate_date=str(row.get("slate_date") or ""),
        context_snapshot=str(row.get("context_snapshot") or ""),
        normalized_pitcher=str(row.get("normalized_pitcher") or ""),
        side=str(row.get("side") or ""),
        k_line=row.get("k_line"),
    )
    if row.get("dataset_key") and row.get("dataset_key") != expected_key:
        errors.append("dataset_key does not match canonical key fields")

    return errors


def theoretical_pnl(result: Any, odds: Any) -> float | None:
    odds_int = _to_int(odds)
    if result not in {"win", "loss"} or odds_int is None:
        return None
    if result == "loss":
        return -1.0
    if odds_int > 0:
        return round(odds_int / 100.0, 2)
    return round(100.0 / abs(odds_int), 2)


def _side_odds(market: dict[str, Any], side: str) -> int | None:
    return _to_int(market.get(f"{side}_odds"))


def _side_opening_odds(market: dict[str, Any], side: str) -> int | None:
    return _to_int(market.get(f"opening_{side}_odds"))


def _research_price_sign(odds: int | None) -> str:
    if odds is None:
        return "unknown"
    if odds < 0:
        return "minus"
    if odds > 0:
        return "plus"
    return "unknown"


def _ev_row(market: dict[str, Any], side: str) -> dict[str, Any]:
    value = market.get(f"ev_{side}")
    return value if isinstance(value, dict) else {}


def _projection(market: dict[str, Any]) -> float | None:
    for field in ("applied_lambda", "raw_lambda", "lambda", "projected_ks"):
        value = _to_float(market.get(field))
        if value is not None:
            return value

    line = _to_float(market.get("k_line"))
    model_side = infer_model_side(market)
    if line is None or model_side not in {"over", "under"}:
        return None
    return line


def _margin_to_line(market: dict[str, Any], side: str) -> float | None:
    line = _to_float(market.get("k_line"))
    projection = _projection(market)
    if line is None or projection is None:
        return None
    margin = projection - line if side == "over" else line - projection
    return round(margin, 3)


def _abs_bucket(value: float | None, buckets: tuple[tuple[float, str], ...], default: str = "unknown") -> str:
    if value is None:
        return default
    absolute = abs(value)
    for limit, label in buckets:
        if absolute < limit:
            return label
    return buckets[-1][1] if buckets else default


def _model_edge_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    absolute = abs(value)
    if absolute < 0.02:
        return "0-2%"
    if absolute < 0.05:
        return "2-5%"
    return "5%+"


def _projection_margin_bucket(value: float | None) -> str:
    return _abs_bucket(
        value,
        (
            (0.5, "0-0.5"),
            (1.0, "0.5-1.0"),
            (1.5, "1.0-1.5"),
            (999.0, "1.5+"),
        ),
    )


def _opportunity_bucket(avg_ip: float | None, recent_start_count: int | None) -> str:
    if avg_ip is None:
        return "unknown"
    if avg_ip < 4.5:
        return "short_leash"
    if avg_ip >= 6.2 and (recent_start_count or 0) >= 3:
        return "deep_starter"
    return "normal"


def _leash_risk_bucket(
    *,
    is_opener: Any,
    starter_mismatch: Any,
    avg_ip: float | None,
    last_pitch_count: int | None,
    days_since_last_start: int | None,
) -> str:
    if bool(is_opener) or bool(starter_mismatch):
        return "high"
    if avg_ip is not None and avg_ip < 4.5:
        return "high"
    if last_pitch_count is not None and last_pitch_count >= 105:
        return "medium"
    if days_since_last_start is not None and days_since_last_start < 4:
        return "medium"
    return "normal"


def _model_market_relationship(model_side: str, market_favorite: str) -> str:
    if model_side not in {"over", "under"} or market_favorite not in {"over", "under"}:
        return "unknown"
    if model_side == market_favorite:
        return "model_agrees_with_favorite"
    return "model_fades_favorite"


def _result_for_side(winning_side: Any, side: str) -> str | None:
    if winning_side not in {"over", "under"}:
        return None
    return "win" if winning_side == side else "loss"


def _home_away(market: dict[str, Any]) -> str | None:
    value = str(market.get("home_away") or market.get("homeAway") or "").strip().lower()
    if value in {"home", "away"}:
        return value
    return None


def _source_path(market: dict[str, Any]) -> str:
    return str(
        market.get("source_artifact_path")
        or f"dashboard/data/processed/{market.get('date')}.json"
    )


def load_archived_markets_for_dataset(
    archive_dir: Path = ARCHIVE_DIR,
    *,
    start_date: str = CLEAN_WINDOW_START,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    markets: list[dict[str, Any]] = []
    end = end_date or "9999-12-31"
    for path in sorted(archive_dir.glob("*.json")):
        date = path.stem
        if date == "index" or date < start_date or date > end:
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        for record in payload.get("pitchers") or []:
            if not isinstance(record, dict):
                continue

            k_line = _to_float(record.get("k_line"))
            actual = _to_float(record.get("actual_ks"))
            over_odds = _to_int(record.get("best_over_odds") or record.get("over_odds"))
            under_odds = _to_int(record.get("best_under_odds") or record.get("under_odds"))
            winner = winning_side(actual, k_line)
            if k_line is None or actual is None or winner not in {"over", "under"}:
                continue
            if over_odds is None or under_odds is None:
                continue

            market = dict(record)
            market.update(
                {
                    "date": date,
                    "normalized_pitcher": _normalized(record.get("pitcher")),
                    "actual_ks": actual,
                    "k_line": k_line,
                    "winning_side": winner,
                    "over_odds": over_odds,
                    "under_odds": under_odds,
                    "opening_over_odds": _to_int(record.get("opening_over_odds")),
                    "opening_under_odds": _to_int(record.get("opening_under_odds")),
                    "source_artifact_path": f"dashboard/data/processed/{date}.json",
                    "generated_at": payload.get("generated_at"),
                }
            )
            markets.append(market)
    return markets


def build_official_close_rows(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for market in markets:
        slate_date = str(market.get("date") or "").strip()
        pitcher = str(market.get("pitcher") or "").strip()
        normalized_pitcher = str(market.get("normalized_pitcher") or _normalized(pitcher)).strip()
        k_line = _to_float(market.get("k_line"))
        if not slate_date or not pitcher or not normalized_pitcher or k_line is None:
            continue

        favorite = market_favorite_side(market.get("over_odds"), market.get("under_odds"))
        model_side = infer_model_side(market)
        source_artifact_path = _source_path(market)
        for side in ("over", "under"):
            odds = _side_odds(market, side)
            opening_odds = _side_opening_odds(market, side)
            result = _result_for_side(market.get("winning_side"), side)
            ev = _ev_row(market, side)
            model_win_prob = infer_model_win_prob(market, side)
            market_prob = None
            if _to_int(market.get("over_odds")) is not None and _to_int(market.get("under_odds")) is not None:
                market_prob = no_vig_side_probability(
                    int(market["over_odds"]),
                    int(market["under_odds"]),
                    side,
                )
            model_no_vig_gap = (
                round(model_win_prob - market_prob, 4)
                if model_win_prob is not None and market_prob is not None
                else None
            )
            margin_to_line = _margin_to_line(market, side)
            avg_ip = _to_float(market.get("avg_ip"))
            recent_start_count = _to_int(market.get("recent_start_count"))
            last_pitch_count = _to_int(market.get("last_pitch_count"))
            days_since_last_start = _to_int(market.get("days_since_last_start"))

            row = {
                "dataset_key": build_dataset_key(
                    slate_date=slate_date,
                    context_snapshot="official_close",
                    normalized_pitcher=normalized_pitcher,
                    side=side,
                    k_line=k_line,
                ),
                "slate_date": slate_date,
                "context_snapshot": "official_close",
                "pitcher": pitcher,
                "normalized_pitcher": normalized_pitcher,
                "side": side,
                "k_line": k_line,
                "bookmaker_key": str(market.get("ref_book") or "").strip() or None,
                "bookmaker_title": str(market.get("ref_book") or "").strip() or None,
                "american_odds": odds,
                "opening_odds": opening_odds,
                "closing_odds": odds,
                "closing_line": k_line,
                "price_sign": _research_price_sign(odds),
                "price_bucket": price_bucket(odds),
                "market_favorite_side": favorite,
                "favorite_gap_no_vig": _favorite_gap(market),
                "no_vig_side_probability": round(market_prob, 4) if market_prob is not None else None,
                "side_price_movement": _side_price_movement(opening_odds, odds),
                "line_movement": None,
                "minus_to_plus_or_plus_to_minus": _sign_transition(opening_odds, odds),
                "model_side": model_side,
                "model_win_prob": round(model_win_prob, 4) if model_win_prob is not None else None,
                "model_no_vig_gap": model_no_vig_gap,
                "model_market_relationship": _model_market_relationship(model_side, favorite),
                "model_edge_bucket": _model_edge_bucket(model_no_vig_gap),
                "projected_ks": _projection(market),
                "k_margin_to_line": margin_to_line,
                "projection_margin_bucket": _projection_margin_bucket(margin_to_line),
                "edge": _to_float(ev.get("edge")),
                "ev": _to_float(ev.get("ev")),
                "adj_ev": _to_float(ev.get("adj_ev")),
                "verdict": ev.get("verdict") or ev.get("raw_verdict"),
                "raw_verdict": ev.get("raw_verdict"),
                "quality_gate_level": market.get("quality_gate_level"),
                "quality_gate_reasons": market.get("quality_gate_reasons"),
                "data_maturity": market.get("data_maturity"),
                "actual_ks": _to_int(market.get("actual_ks")),
                "result": result,
                "theoretical_pnl": theoretical_pnl(result, odds),
                "miss_distance": _miss_distance(market),
                "miss_distance_bucket": _miss_distance_bucket(market),
                "line_bucket": _line_bucket(k_line),
                "team": market.get("team"),
                "opp_team": market.get("opp_team"),
                "pitcher_throws": market.get("pitcher_throws"),
                "home_away": _home_away(market),
                "park_team": market.get("park_team"),
                "game_time": market.get("game_time"),
                "provider_event_id": market.get("provider_event_id"),
                "pitcher_mlb_id": market.get("pitcher_mlb_id"),
                "is_home_start": _home_away(market) == "home" if _home_away(market) else None,
                "is_opener": market.get("is_opener"),
                "starter_mismatch": market.get("starter_mismatch"),
                "lineup_used": market.get("lineup_used"),
                "lineup_count": _to_int(market.get("lineup_count")),
                "lineup_right_batters": _to_int(market.get("lineup_right_batters")),
                "lineup_left_batters": _to_int(market.get("lineup_left_batters")),
                "lineup_switch_batters": _to_int(market.get("lineup_switch_batters")),
                "handedness_matchup_bucket": market.get("handedness_matchup_bucket"),
                "opp_k_rate": _to_float(market.get("opp_k_rate")),
                "umpire": market.get("umpire"),
                "umpire_has_rating": market.get("umpire_has_rating"),
                "ump_k_adj": _to_float(market.get("ump_k_adj")),
                "park_factor": _to_float(market.get("park_factor")),
                "days_since_last_start": days_since_last_start,
                "last_pitch_count": last_pitch_count,
                "avg_ip": avg_ip,
                "recent_start_count": recent_start_count,
                "opportunity_bucket": _opportunity_bucket(avg_ip, recent_start_count),
                "leash_risk_bucket": _leash_risk_bucket(
                    is_opener=market.get("is_opener"),
                    starter_mismatch=market.get("starter_mismatch"),
                    avg_ip=avg_ip,
                    last_pitch_count=last_pitch_count,
                    days_since_last_start=days_since_last_start,
                ),
                "rest_k9_delta": _to_float(market.get("rest_k9_delta")),
                "season_k9": _to_float(market.get("season_k9")),
                "recent_k9": _to_float(market.get("recent_k9")),
                "career_k9": _to_float(market.get("career_k9")),
                "current_swstr_pct": _to_float(
                    market.get("current_swstr_pct") or market.get("swstr_pct")
                ),
                "career_swstr_pct": _to_float(market.get("career_swstr_pct")),
                "provider": None,
                "checkpoint_minutes_to_game": None,
                "book_count": None,
                "books_seen": None,
                "toward_pick_count": None,
                "away_from_pick_count": None,
                "better_now_count": None,
                "worse_now_count": None,
                "market_consensus": None,
                "bet_value_consensus": None,
                "broad_confirmation": False,
                "reversal_book_count": None,
                "volatile_book_count": None,
                "best_book": None,
                "best_line": None,
                "best_odds": None,
                "best_is_off_market": None,
                "is_tracked_pick": False,
                "pick_history_match_type": None,
                "bet_time_line": None,
                "bet_time_odds": None,
                "bet_time_book": None,
                "bet_time_at": None,
                "price_clv_cents": None,
                "line_clv_delta": None,
                "beat_close_price": None,
                "beat_close_line": None,
                "pick_history_pnl": None,
                "actual_ip": _to_float(market.get("actual_ip")),
                "actual_pitch_count": _to_int(market.get("actual_pitch_count")),
                "batters_faced": _to_int(market.get("batters_faced")),
                "source_artifact_path": source_artifact_path,
            }
            rows.append(row)
    return rows


def _favorite_gap(market: dict[str, Any]) -> float | None:
    over = _to_int(market.get("over_odds"))
    under = _to_int(market.get("under_odds"))
    if over is None or under is None:
        return None
    over_prob = american_implied_probability(over)
    under_prob = american_implied_probability(under)
    total = over_prob + under_prob
    if total == 0:
        return None
    return round(abs((over_prob / total) - (under_prob / total)), 4)


def _side_price_movement(opening: int | None, closing: int | None) -> str | None:
    if opening is None or closing is None:
        return None
    if abs(closing - opening) < 10:
        return "unchanged"
    return "with_side" if closing < opening else "against_side"


def _sign_transition(opening: int | None, closing: int | None) -> str | None:
    if opening is None or closing is None:
        return None
    return f"{_research_price_sign(opening)}_to_{_research_price_sign(closing)}"


def _miss_distance(market: dict[str, Any]) -> float | None:
    actual = _to_float(market.get("actual_ks"))
    line = _to_float(market.get("k_line"))
    if actual is None or line is None:
        return None
    return round(actual - line, 3)


def _miss_distance_bucket(market: dict[str, Any]) -> str | None:
    distance = _miss_distance(market)
    if distance is None:
        return None
    abs_distance = abs(distance)
    if abs_distance <= 0.5:
        return "0.5"
    if abs_distance <= 1.5:
        return "1.0-1.5"
    if abs_distance <= 2.5:
        return "2.0-2.5"
    return "3+"


def _line_bucket(k_line: float | None) -> str:
    if k_line is None:
        return "unknown"
    if k_line <= 3.5:
        return "2.5-3.5"
    if k_line == 4.5:
        return "4.5"
    if k_line == 5.5:
        return "5.5"
    if k_line == 6.5:
        return "6.5"
    return "7.5+"


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    key_counts = Counter(str(row.get("dataset_key")) for row in rows)
    context_counts = Counter(str(row.get("context_snapshot") or "unknown") for row in rows)
    model_market_counts = Counter(str(row.get("model_market_relationship") or "unknown") for row in rows)
    opportunity_counts = Counter(str(row.get("opportunity_bucket") or "unknown") for row in rows)
    leash_counts = Counter(str(row.get("leash_risk_bucket") or "unknown") for row in rows)
    clean_rows = [row for row in rows if str(row.get("slate_date") or "") >= CLEAN_WINDOW_START]
    return {
        "total_rows": len(rows),
        "clean_window_rows": len(clean_rows),
        "graded_rows": sum(1 for row in rows if row.get("result") in {"win", "loss"}),
        "rows_missing_result": sum(1 for row in rows if row.get("result") not in {"win", "loss"}),
        "missing_team_or_opponent": sum(
            1 for row in rows if not row.get("team") or not row.get("opp_team")
        ),
        "missing_book_odds": sum(1 for row in rows if row.get("american_odds") is None),
        "missing_model_fields": sum(
            1 for row in rows if row.get("model_win_prob") is None or row.get("model_side") not in {"over", "under"}
        ),
        "duplicate_dataset_keys": sum(count - 1 for count in key_counts.values() if count > 1),
        "context_snapshot_counts": dict(sorted(context_counts.items())),
        "tracked_pick_rows": sum(1 for row in rows if row.get("is_tracked_pick") is True),
        "rows_with_price_clv": sum(1 for row in rows if row.get("price_clv_cents") is not None),
        "beat_close_price_rows": sum(1 for row in rows if row.get("beat_close_price") is True),
        "beat_close_line_rows": sum(1 for row in rows if row.get("beat_close_line") is True),
        "model_market_relationship_counts": dict(sorted(model_market_counts.items())),
        "opportunity_bucket_counts": dict(sorted(opportunity_counts.items())),
        "leash_risk_bucket_counts": dict(sorted(leash_counts.items())),
    }


def reconcile_picks_history(
    rows: list[dict[str, Any]],
    *,
    history_path: Path = PICKS_HISTORY,
    start_date: str = CLEAN_WINDOW_START,
) -> dict[str, Any]:
    row_keys = {str(row.get("dataset_key") or "") for row in rows}
    side_index: dict[tuple[str, str, str], list[str]] = {}
    for row in rows:
        side_key = (
            str(row.get("slate_date") or "").strip(),
            _normalized(row.get("normalized_pitcher") or row.get("pitcher")),
            str(row.get("side") or "").strip().lower(),
        )
        side_index.setdefault(side_key, []).append(str(row.get("dataset_key") or ""))
    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = []

    graded_pick_rows = 0
    matched_pick_rows = 0
    unique_side_fallback_matches = 0
    unmatched_examples: list[dict[str, Any]] = []
    for pick in payload if isinstance(payload, list) else []:
        if not isinstance(pick, dict):
            continue
        slate_date = str(pick.get("date") or pick.get("slate_date") or "").strip()
        side = str(pick.get("side") or "").strip().lower()
        result = str(pick.get("result") or "").strip().lower()
        if slate_date < start_date or side not in {"over", "under"} or result not in {"win", "loss"}:
            continue

        graded_pick_rows += 1
        dataset_key = build_dataset_key(
            slate_date=slate_date,
            context_snapshot="official_close",
            normalized_pitcher=_normalized(pick.get("pitcher")),
            side=side,
            k_line=pick.get("k_line"),
        )
        if dataset_key in row_keys:
            matched_pick_rows += 1
            continue

        fallback_key = (slate_date, _normalized(pick.get("pitcher")), side)
        candidates = [candidate for candidate in side_index.get(fallback_key, []) if candidate]
        if len(candidates) == 1:
            matched_pick_rows += 1
            unique_side_fallback_matches += 1
            continue

        if len(unmatched_examples) < 5:
            unmatched_examples.append(
                {
                    "date": slate_date,
                    "pitcher": pick.get("pitcher"),
                    "side": side,
                    "k_line": pick.get("k_line"),
                    "dataset_key": dataset_key,
                }
            )

    return {
        "graded_pick_rows": graded_pick_rows,
        "matched_pick_rows": matched_pick_rows,
        "unique_side_fallback_matches": unique_side_fallback_matches,
        "unmatched_pick_rows": graded_pick_rows - matched_pick_rows,
        "unmatched_examples": unmatched_examples,
    }


def _load_picks_history(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def _history_indexes(
    history_rows: list[dict[str, Any]],
    start_date: str,
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str, str], list[dict[str, Any]]]]:
    exact: dict[str, dict[str, Any]] = {}
    side: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for pick in history_rows:
        slate_date = str(pick.get("date") or pick.get("slate_date") or "").strip()
        pick_side = str(pick.get("side") or "").strip().lower()
        if slate_date < start_date or pick_side not in {"over", "under"}:
            continue
        key = build_dataset_key(
            slate_date=slate_date,
            context_snapshot="official_close",
            normalized_pitcher=_normalized(pick.get("pitcher")),
            side=pick_side,
            k_line=pick.get("locked_k_line") or pick.get("k_line"),
        )
        exact[key] = pick
        side_key = (slate_date, _normalized(pick.get("pitcher")), pick_side)
        side.setdefault(side_key, []).append(pick)
    return exact, side


def _pick_for_row(
    row: dict[str, Any],
    exact: dict[str, dict[str, Any]],
    side_index: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str | None]:
    dataset_key = str(row.get("dataset_key") or "")
    if dataset_key in exact:
        return exact[dataset_key], "exact_line"
    side_key = (
        str(row.get("slate_date") or "").strip(),
        _normalized(row.get("normalized_pitcher") or row.get("pitcher")),
        str(row.get("side") or "").strip().lower(),
    )
    candidates = side_index.get(side_key, [])
    if len(candidates) == 1:
        return candidates[0], "unique_pitcher_side"
    return None, None


def _line_clv_delta(side: str, bet_line: float | None, closing_line: float | None) -> float | None:
    if bet_line is None or closing_line is None:
        return None
    raw_delta = closing_line - bet_line
    return round(raw_delta if side == "over" else -raw_delta, 3)


def enrich_rows_with_pick_history(
    rows: list[dict[str, Any]],
    *,
    history_path: Path = PICKS_HISTORY,
    start_date: str = CLEAN_WINDOW_START,
) -> list[dict[str, Any]]:
    history_rows = _load_picks_history(history_path)
    exact, side_index = _history_indexes(history_rows, start_date)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        pick, match_type = _pick_for_row(row, exact, side_index)
        next_row = dict(row)
        next_row.setdefault("is_tracked_pick", False)
        next_row.setdefault("pick_history_match_type", None)
        next_row.setdefault("bet_time_line", None)
        next_row.setdefault("bet_time_odds", None)
        next_row.setdefault("bet_time_book", None)
        next_row.setdefault("bet_time_at", None)
        next_row.setdefault("price_clv_cents", None)
        next_row.setdefault("line_clv_delta", None)
        next_row.setdefault("beat_close_price", None)
        next_row.setdefault("beat_close_line", None)
        next_row.setdefault("pick_history_pnl", None)
        if pick is not None:
            bet_line = _to_float(pick.get("locked_k_line") or pick.get("k_line"))
            bet_odds = _to_int(pick.get("locked_odds") or pick.get("odds"))
            closing_odds = _to_int(next_row.get("closing_odds") or next_row.get("american_odds"))
            closing_line = _to_float(next_row.get("closing_line") or next_row.get("k_line"))
            line_clv_delta = _line_clv_delta(str(next_row.get("side") or ""), bet_line, closing_line)
            price_clv_cents = (
                bet_odds - closing_odds
                if bet_odds is not None and closing_odds is not None
                else None
            )
            next_row.update(
                {
                    "is_tracked_pick": True,
                    "pick_history_match_type": match_type,
                    "bet_time_line": bet_line,
                    "bet_time_odds": bet_odds,
                    "bet_time_book": pick.get("locked_book") or pick.get("ref_book") or next_row.get("bookmaker_key"),
                    "bet_time_at": pick.get("locked_at"),
                    "price_clv_cents": price_clv_cents,
                    "line_clv_delta": line_clv_delta,
                    "beat_close_price": price_clv_cents > 0 if price_clv_cents is not None else None,
                    "beat_close_line": line_clv_delta > 0 if line_clv_delta is not None else None,
                    "pick_history_pnl": _to_float(pick.get("pnl")),
                }
            )
        enriched.append(next_row)
    return enriched


def render_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Pitcher K Outcome Dataset Summary",
        "",
        "Shadow-only: this dataset does not change live picks, locks, thresholds, staking, provider order, notifications, or calibration.",
        "",
        f"- Total rows: `{summary['total_rows']}`",
        f"- Clean-window rows: `{summary['clean_window_rows']}`",
        f"- Graded rows: `{summary['graded_rows']}`",
        f"- Rows missing result: `{summary['rows_missing_result']}`",
        f"- Duplicate dataset keys: `{summary['duplicate_dataset_keys']}`",
        f"- Missing team/opponent: `{summary['missing_team_or_opponent']}`",
        f"- Missing book odds: `{summary['missing_book_odds']}`",
        f"- Missing model fields: `{summary['missing_model_fields']}`",
        f"- Tracked pick rows: `{summary.get('tracked_pick_rows', 0)}`",
        f"- Rows with price CLV: `{summary.get('rows_with_price_clv', 0)}`",
        f"- Beat-close price rows: `{summary.get('beat_close_price_rows', 0)}`",
        f"- Beat-close line rows: `{summary.get('beat_close_line_rows', 0)}`",
        f"- Clean graded picks reconciled: `{summary.get('matched_pick_rows', 0)}/{summary.get('graded_pick_rows', 0)}`",
        f"- Unique side fallback reconciliations: `{summary.get('unique_side_fallback_matches', 0)}`",
        f"- Unmatched clean graded picks: `{summary.get('unmatched_pick_rows', 0)}`",
        "",
        "## Context Snapshots",
        "",
    ]
    for context, count in summary["context_snapshot_counts"].items():
        lines.append(f"- `{context}`: `{count}`")
    for title, key in (
        ("Model Vs Market Relationship", "model_market_relationship_counts"),
        ("Opportunity Buckets", "opportunity_bucket_counts"),
        ("Leash Risk Buckets", "leash_risk_bucket_counts"),
    ):
        lines.extend(["", f"## {title}", ""])
        for value, count in (summary.get(key) or {}).items():
            lines.append(f"- `{value}`: `{count}`")
    unmatched = summary.get("unmatched_examples") or []
    if unmatched:
        lines.extend(["", "## Unmatched Pick Examples", ""])
        for item in unmatched:
            lines.append(
                "- `{date}` `{pitcher}` `{side}` `{k_line}`".format(
                    date=item.get("date"),
                    pitcher=item.get("pitcher"),
                    side=item.get("side"),
                    k_line=item.get("k_line"),
                )
            )
    return "\n".join(lines)


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def build_dataset(
    *,
    archive_dir: Path = ARCHIVE_DIR,
    start_date: str = CLEAN_WINDOW_START,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    markets = load_archived_markets_for_dataset(
        archive_dir,
        start_date=start_date,
        end_date=end_date,
    )
    rows = build_official_close_rows(markets)
    return enrich_rows_with_pick_history(rows, start_date=start_date)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the shadow pitcher K outcome dataset.")
    parser.add_argument("--start-date", default=CLEAN_WINDOW_START)
    parser.add_argument("--end-date")
    parser.add_argument("--jsonl-output", type=Path, default=OUTPUT_JSONL)
    parser.add_argument("--summary-output", type=Path, default=OUTPUT_SUMMARY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    rows = build_dataset(start_date=args.start_date, end_date=args.end_date)
    validation_errors = [
        (row.get("dataset_key"), errors)
        for row in rows
        if (errors := validate_dataset_row(row))
    ]
    if validation_errors:
        preview = validation_errors[:5]
        raise SystemExit(f"Dataset validation failed: {preview}")

    summary = build_summary(rows)
    summary.update(reconcile_picks_history(rows, start_date=args.start_date))
    write_jsonl(rows, args.jsonl_output)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(render_summary(summary), encoding="utf-8")
    print(render_summary(summary))


if __name__ == "__main__":
    main()
