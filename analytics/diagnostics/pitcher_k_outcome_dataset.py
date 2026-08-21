"""Build a shadow-only pitcher K outcome research dataset.

This diagnostic reads committed production artifacts and writes local research
outputs only. It must not change live picks, thresholds, staking, provider
order, notifications, or calibration.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen


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
from market_infra import alternative_pick_selector as alternative_selector  # noqa: E402


ARCHIVE_DIR = ROOT / "dashboard" / "data" / "processed"
PICKS_HISTORY = ROOT / "data" / "picks_history.json"
OUTPUT_JSONL = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_SUMMARY = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset_summary.md"
MARKET_AGREEMENT_TRACKER = ROOT / "analytics" / "output" / "market_agreement_tracker.jsonl"
LIVE_MARKET_DISPLAY = ROOT / "analytics" / "output" / "market_agreement_inputs" / "live_market_display_state.json"
LINEUP_HANDEDNESS_BACKFILL = ROOT / "analytics" / "output" / "lineup_handedness_backfill.json"
ACTUAL_OPPORTUNITY_BACKFILL = ROOT / "analytics" / "output" / "actual_opportunity_backfill.json"
CLEAN_WINDOW_START = "2026-04-28"
DEFAULT_ARTIFACT_API_URL = "https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact"

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
    "live_display_provider",
    "live_display_state",
    "live_display_latest_snapshot_at",
    "market_agreement_checkpoint",
    "market_agreement_label",
    "movement_strength_label",
    "movement_value_label",
    "movement_magnitude_bucket",
    "market_agreement_tracker_bucket",
    "book_count",
    "books_seen",
    "toward_pick_count",
    "away_from_pick_count",
    "better_now_count",
    "worse_now_count",
    "market_consensus",
    "bet_value_consensus",
    "broad_confirmation",
    "reversal_book_count",
    "volatile_book_count",
    "best_is_off_market",
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
    "clv_type",
    "process_outcome_bucket",
    "bet_timing_window",
    "model_market_relationship",
    "model_edge_bucket",
    "projection_margin_bucket",
    "large_edge_skepticism_flag",
    "large_edge_skepticism_reasons",
    "pitcher_archetype_bucket",
    "pitcher_throws",
    "lineup_count",
    "lineup_right_batters",
    "lineup_left_batters",
    "lineup_switch_batters",
    "handedness_matchup_bucket",
    "lineup_handedness_source",
    "lineup_handedness_runtime_safe",
    "lineup_handedness_game_pk",
    "lineup_handedness_count_matches_existing",
    "batter_handedness_mode",
    "lineup_split_source",
    "lineup_real_split_count",
    "lineup_path_a_fallback_count",
    "confidence_referee",
    "locked_verdict",
    "display_verdict",
    "actionable_verdict",
    "locked_adj_ev",
    "verdict_cap_reason",
    "avg_ip",
    "recent_start_count",
    "opportunity_bucket",
    "leash_risk_bucket",
    "actual_ip",
    "actual_pitch_count",
    "batters_faced",
    "actual_opportunity_source",
    "actual_opportunity_runtime_safe",
    "actual_opportunity_game_pk",
    "actual_opportunity_pitcher_match_type",
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


def lineup_handedness_lookup_key(
    slate_date: Any,
    team: Any,
    opp_team: Any,
    game_time: Any,
) -> str:
    return "|".join(
        [
            str(slate_date or "").strip(),
            _normalized(team),
            _normalized(opp_team),
            str(game_time or "").strip(),
        ]
    )


def actual_opportunity_lookup_key(
    slate_date: Any,
    team: Any,
    opp_team: Any,
    game_time: Any,
    pitcher: Any,
) -> str:
    return "|".join(
        [
            str(slate_date or "").strip(),
            _normalized(team),
            _normalized(opp_team),
            str(game_time or "").strip(),
            _normalized(pitcher),
        ]
    )


def handedness_matchup_bucket(
    *,
    pitcher_throws: Any,
    right_batters: Any,
    left_batters: Any,
    switch_batters: Any,
) -> str | None:
    pitcher_hand = str(pitcher_throws or "").strip().upper()
    right = _to_int(right_batters)
    left = _to_int(left_batters)
    switch = _to_int(switch_batters)
    if pitcher_hand not in {"R", "L"} or right is None or left is None or switch is None:
        return None

    if pitcher_hand == "R":
        same_hand = right
        opposite_hand = left + switch
    else:
        same_hand = left
        opposite_hand = right + switch

    if switch >= 3:
        return "switch_heavy"
    if same_hand >= 6:
        return "same_hand_heavy"
    if opposite_hand >= 6:
        return "opposite_hand_heavy"
    if same_hand - opposite_hand >= 2:
        return "same_hand_lean"
    if opposite_hand - same_hand >= 2:
        return "opposite_hand_lean"
    return "balanced"


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
    return alternative_selector.runtime_opportunity_bucket(avg_ip, recent_start_count)


def _leash_risk_bucket(
    *,
    is_opener: Any,
    starter_mismatch: Any,
    avg_ip: float | None,
    last_pitch_count: int | None,
    days_since_last_start: int | None,
) -> str:
    return alternative_selector.runtime_leash_risk_bucket(
        is_opener=is_opener,
        starter_mismatch=starter_mismatch,
        avg_ip=avg_ip,
        last_pitch_count=last_pitch_count,
        days_since_last_start=days_since_last_start,
    )


def _model_market_relationship(model_side: str, market_favorite: str) -> str:
    return alternative_selector.runtime_model_market_relationship(model_side, market_favorite)


def _list_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in (None, "", []):
        return []
    return [value]


def _clv_type(is_tracked: bool, price_clv_cents: float | int | None, line_clv_delta: float | None) -> str:
    if not is_tracked:
        return "not_tracked"
    if price_clv_cents is None and line_clv_delta is None:
        return "unknown"

    price_edge = price_clv_cents is not None and price_clv_cents > 0
    line_edge = line_clv_delta is not None and line_clv_delta > 0
    if price_edge and line_edge:
        return "price_and_line"
    if price_edge:
        return "price_only"
    if line_edge:
        return "line_only"
    return "no_clv_edge"


def _process_outcome_bucket(result: Any, clv_type: str) -> str:
    if result not in {"win", "loss"} or clv_type in {"unknown", "not_tracked"}:
        return "unknown"
    good_process = clv_type in {"price_and_line", "price_only", "line_only"}
    if good_process and result == "win":
        return "good_process_win"
    if good_process and result == "loss":
        return "good_process_loss"
    if result == "win":
        return "weak_process_win"
    return "weak_process_loss"


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _bet_timing_window(bet_time_at: Any, game_time: Any) -> str:
    return alternative_selector.timing_bucket(bet_time_at, game_time)


def _large_edge_skepticism_reasons(
    *,
    side: str,
    model_side: str,
    verdict: Any,
    model_edge_bucket: str,
    model_market_relationship: str,
    quality_gate_level: Any,
    quality_gate_reasons: Any,
    side_price_movement: str | None,
    leash_risk_bucket: str,
    opportunity_bucket: str,
) -> list[str]:
    if model_edge_bucket != "5%+":
        return []
    verdict_text = str(verdict or "").strip().upper()
    if side != model_side and not (verdict_text.startswith("LEAN") or verdict_text.startswith("FIRE")):
        return []

    reasons: list[str] = []
    if model_market_relationship == "model_fades_favorite":
        reasons.append("model_fades_market_favorite")

    gate = str(quality_gate_level or "").strip().lower()
    if gate and gate not in {"clean", "none"}:
        reasons.append(f"quality_gate_{gate}")

    if _list_values(quality_gate_reasons):
        reasons.append("lineup_or_quality_gate_reason")

    if side_price_movement == "against_side":
        reasons.append("market_moved_against_side")

    if leash_risk_bucket in {"medium", "high"}:
        reasons.append(f"leash_risk_{leash_risk_bucket}")

    if opportunity_bucket == "short_leash":
        reasons.append("short_leash_opportunity")

    return reasons if len(reasons) >= 2 else []


def _pitcher_archetype_bucket(
    *,
    is_opener: Any,
    starter_mismatch: Any,
    opportunity_bucket: str,
    season_k9: float | None,
    recent_k9: float | None,
    career_k9: float | None,
) -> str:
    return alternative_selector.runtime_pitcher_archetype_bucket(
        is_opener=is_opener,
        starter_mismatch=starter_mismatch,
        opportunity_bucket=opportunity_bucket,
        season_k9=season_k9,
        recent_k9=recent_k9,
        career_k9=career_k9,
    )


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


def _json_rows_from_path(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not text:
        return []

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
        return rows
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "items", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _market_agreement_checkpoint(row: dict[str, Any]) -> str:
    return str(row.get("checkpoint") or row.get("time_window") or "").strip()


def _market_agreement_checkpoint_minutes(row: dict[str, Any]) -> int | None:
    checkpoint = _market_agreement_checkpoint(row)
    if checkpoint == "final_pre_start":
        return 0
    if checkpoint.startswith("pre_"):
        return _to_int(checkpoint.replace("pre_", "", 1))
    raw_minutes = row.get("checkpoint_minutes")
    if raw_minutes is None:
        raw_minutes = row.get("minutes_to_game")
    minutes = _to_int(raw_minutes)
    return minutes if minutes is not None and minutes >= 0 else None


def _is_pre_start_market_agreement_row(row: dict[str, Any]) -> bool:
    if _market_agreement_checkpoint(row) == "post_start":
        return False
    return _market_agreement_checkpoint_minutes(row) is not None


def _market_agreement_exact_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("slate_date") or row.get("date") or "").strip(),
        _normalized(row.get("normalized_pitcher") or row.get("pitcher")),
        str(row.get("side") or "").strip().lower(),
        _line_text(row.get("k_line")),
    )


def _market_agreement_side_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return _market_agreement_exact_key(row)[:3]


def _market_provider_rank(provider: Any) -> int:
    return {
        "boltodds": 0,
        "propline": 1,
    }.get(str(provider or "").strip().lower(), 9)


def _market_agreement_sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    minutes = _market_agreement_checkpoint_minutes(row)
    return (
        minutes if minutes is not None else 9999,
        -(_to_int(row.get("book_count")) or 0),
        -(_to_int(row.get("snapshot_count")) or 0),
        _market_provider_rank(row.get("provider")),
        str(row.get("provider") or ""),
    )


def _market_agreement_indexes(
    tracker_rows: list[dict[str, Any]],
) -> tuple[
    dict[tuple[str, str, str, str], list[dict[str, Any]]],
    dict[tuple[str, str, str], list[dict[str, Any]]],
]:
    exact: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    side: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in tracker_rows:
        if not _is_pre_start_market_agreement_row(row):
            continue
        exact.setdefault(_market_agreement_exact_key(row), []).append(row)
        side.setdefault(_market_agreement_side_key(row), []).append(row)
    return exact, side


def _best_market_agreement_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(rows, key=_market_agreement_sort_key)[0]


def _market_agreement_row_for_dataset_row(
    row: dict[str, Any],
    exact_index: dict[tuple[str, str, str, str], list[dict[str, Any]]],
    side_index: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> dict[str, Any] | None:
    exact_match = _best_market_agreement_row(exact_index.get(_market_agreement_exact_key(row), []))
    if exact_match is not None:
        return exact_match
    return _best_market_agreement_row(side_index.get(_market_agreement_side_key(row), []))


def enrich_rows_with_market_agreement(
    rows: list[dict[str, Any]],
    *,
    tracker_path: Path | None = MARKET_AGREEMENT_TRACKER,
) -> list[dict[str, Any]]:
    tracker_rows = _json_rows_from_path(tracker_path)
    exact_index, side_index = _market_agreement_indexes(tracker_rows)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        next_row = dict(row)
        selected = _market_agreement_row_for_dataset_row(next_row, exact_index, side_index)
        if selected:
            next_row.update(
                {
                    "provider": selected.get("provider") or next_row.get("provider"),
                    "market_agreement_checkpoint": _market_agreement_checkpoint(selected) or None,
                    "checkpoint_minutes_to_game": _market_agreement_checkpoint_minutes(selected),
                    "market_agreement_label": selected.get("movement_agreement_label")
                    or selected.get("market_agreement_label"),
                    "movement_strength_label": selected.get("movement_strength_label"),
                    "movement_value_label": selected.get("movement_value_label"),
                    "movement_magnitude_bucket": selected.get("movement_magnitude_bucket"),
                    "market_agreement_tracker_bucket": selected.get("tracker_bucket"),
                    "book_count": _to_int(selected.get("book_count")),
                    "books_seen": selected.get("books_seen"),
                    "toward_pick_count": _to_int(selected.get("toward_pick_count")),
                    "away_from_pick_count": _to_int(selected.get("away_from_pick_count")),
                    "better_now_count": _to_int(selected.get("better_now_count")),
                    "worse_now_count": _to_int(selected.get("worse_now_count")),
                    "market_consensus": selected.get("market_consensus"),
                    "bet_value_consensus": selected.get("bet_value_consensus"),
                    "broad_confirmation": selected.get("broad_confirmation") is True,
                    "reversal_book_count": _to_int(selected.get("reversal_book_count")),
                    "volatile_book_count": _to_int(selected.get("volatile_book_count")),
                    "best_book": selected.get("best_book") or next_row.get("best_book"),
                    "best_line": _to_float(selected.get("best_line")) or next_row.get("best_line"),
                    "best_odds": _to_int(selected.get("best_odds")) or next_row.get("best_odds"),
                    "best_is_off_market": selected.get("best_is_off_market")
                    if selected.get("best_is_off_market") is not None
                    else next_row.get("best_is_off_market"),
                }
            )
        enriched.append(next_row)
    return enriched


def _is_pre_start_live_display_row(row: dict[str, Any]) -> bool:
    if str(row.get("game_state") or "").strip().lower() != "pregame":
        return False
    game_time = _parse_datetime(row.get("game_time"))
    latest_snapshot = _parse_datetime(row.get("latest_snapshot_at"))
    if game_time is None or latest_snapshot is None:
        return False
    return latest_snapshot <= game_time


def _live_display_sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, int, str]:
    latest_snapshot = _parse_datetime(row.get("latest_snapshot_at"))
    timestamp = int(latest_snapshot.timestamp()) if latest_snapshot is not None else 0
    is_off_market = row.get("best_is_off_market") is True or str(
        row.get("actionable_state") or ""
    ).strip().lower() == "off_market"
    return (
        -timestamp,
        -(1 if row.get("broad_confirmation") is True else 0),
        -(1 if is_off_market else 0),
        -(_to_int(row.get("book_count")) or 0),
        _market_provider_rank(row.get("provider")),
        str(row.get("provider") or ""),
    )


def _live_display_indexes(
    display_rows: list[dict[str, Any]],
) -> tuple[
    dict[tuple[str, str, str, str], list[dict[str, Any]]],
    dict[tuple[str, str, str], list[dict[str, Any]]],
]:
    exact: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    side: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in display_rows:
        if not _is_pre_start_live_display_row(row):
            continue
        exact.setdefault(_market_agreement_exact_key(row), []).append(row)
        side.setdefault(_market_agreement_side_key(row), []).append(row)
    return exact, side


def _live_display_rows_for_dataset_row(
    row: dict[str, Any],
    exact_index: dict[tuple[str, str, str, str], list[dict[str, Any]]],
    side_index: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    exact_rows = exact_index.get(_market_agreement_exact_key(row), [])
    if exact_rows:
        return exact_rows
    return side_index.get(_market_agreement_side_key(row), [])


def _merged_books_seen(existing: Any, display_rows: list[dict[str, Any]]) -> list[str] | None:
    books: set[str] = set()
    if isinstance(existing, list):
        books.update(str(book) for book in existing if str(book or "").strip())
    for row in display_rows:
        raw_books = row.get("books_seen")
        if isinstance(raw_books, list):
            books.update(str(book) for book in raw_books if str(book or "").strip())
    return sorted(books) if books else None


def _best_display_book_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    off_market_rows = [
        row
        for row in rows
        if row.get("best_is_off_market") is True
        or str(row.get("actionable_state") or "").strip().lower() == "off_market"
    ]
    candidates = off_market_rows or rows
    if not candidates:
        return None
    return sorted(candidates, key=_live_display_sort_key)[0]


def enrich_rows_with_live_market_display(
    rows: list[dict[str, Any]],
    *,
    live_market_display_path: Path | None = LIVE_MARKET_DISPLAY,
) -> list[dict[str, Any]]:
    display_rows = _json_rows_from_path(live_market_display_path)
    exact_index, side_index = _live_display_indexes(display_rows)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        next_row = dict(row)
        candidates = _live_display_rows_for_dataset_row(next_row, exact_index, side_index)
        selected = _best_display_book_row(candidates)
        if selected:
            display_book_count = max((_to_int(item.get("book_count")) or 0) for item in candidates)
            existing_book_count = _to_int(next_row.get("book_count")) or 0
            next_row.update(
                {
                    "live_display_provider": selected.get("provider"),
                    "live_display_state": selected.get("actionable_state"),
                    "live_display_latest_snapshot_at": selected.get("latest_snapshot_at"),
                    "book_count": max(existing_book_count, display_book_count) or next_row.get("book_count"),
                    "books_seen": _merged_books_seen(next_row.get("books_seen"), candidates),
                    "broad_confirmation": next_row.get("broad_confirmation") is True
                    or any(item.get("broad_confirmation") is True for item in candidates),
                    "best_is_off_market": (
                        True
                        if any(
                            item.get("best_is_off_market") is True
                            or str(item.get("actionable_state") or "").strip().lower() == "off_market"
                            for item in candidates
                        )
                        else False
                    ),
                    "best_book": selected.get("best_book") or next_row.get("best_book"),
                    "best_line": _to_float(selected.get("best_line")) or next_row.get("best_line"),
                    "best_odds": _to_int(selected.get("best_odds")) or next_row.get("best_odds"),
                }
            )
            if not next_row.get("market_consensus"):
                next_row["market_consensus"] = selected.get("market_consensus")
            if not next_row.get("bet_value_consensus"):
                next_row["bet_value_consensus"] = selected.get("bet_value_consensus")
        enriched.append(next_row)
    return enriched


def artifact_api_url(base_url: str, artifact_type: str, date: str | None = None) -> str:
    params = {"type": artifact_type}
    if date:
        params["date"] = date
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"


def _load_remote_json(url: str) -> Any:
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _artifact_dates_from_index(
    payload: Any,
    *,
    start_date: str,
    end_date: str | None,
) -> list[str]:
    end = end_date or "9999-12-31"
    dates: set[str] = set()
    rows = payload.get("dates") if isinstance(payload, dict) else []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        date = str(row.get("date") or "").strip()
        if date and start_date <= date <= end:
            dates.add(date)
    return sorted(dates)


def _requested_date_range(start_date: str, end_date: str | None) -> list[str]:
    if not end_date:
        return []
    try:
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()
    except ValueError:
        return []
    if end < start:
        return []
    dates: list[str] = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def build_archive_outcome_index(
    history_rows: list[dict[str, Any]],
    *,
    start_date: str = CLEAN_WINDOW_START,
) -> dict[tuple[str, str, float], list[dict[str, Any]]]:
    index: dict[tuple[str, str, float], list[dict[str, Any]]] = {}
    for pick in history_rows:
        slate_date = str(pick.get("date") or pick.get("slate_date") or "").strip()
        line = _to_float(
            pick.get("locked_k_line")
            if pick.get("locked_k_line") is not None
            else pick.get("k_line")
        )
        result = str(pick.get("result") or "").strip().lower()
        actual = _to_float(pick.get("actual_ks"))
        normalized_pitcher = _normalized(pick.get("pitcher"))
        if (
            slate_date < start_date
            or not normalized_pitcher
            or line is None
            or result not in {"win", "loss"}
            or actual is None
        ):
            continue
        index.setdefault((slate_date, normalized_pitcher, line), []).append(pick)
    return index


def build_pitcher_game_outcome_index(
    history_rows: list[dict[str, Any]],
    *,
    start_date: str = CLEAN_WINDOW_START,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for pick in history_rows:
        slate_date = str(pick.get("date") or pick.get("slate_date") or "").strip()
        result = str(pick.get("result") or "").strip().lower()
        actual = _to_float(pick.get("actual_ks"))
        normalized_pitcher = _normalized(pick.get("pitcher"))
        if (
            slate_date < start_date
            or not normalized_pitcher
            or result not in {"win", "loss"}
            or actual is None
        ):
            continue
        index.setdefault((slate_date, normalized_pitcher), []).append(pick)
    return index


def _initialize_archive_outcome_stats(stats: dict[str, int]) -> None:
    stats.setdefault("recovered_markets", 0)
    stats.setdefault("ambiguous_markets", 0)


def _markets_from_archive_payload(
    payload: dict[str, Any],
    *,
    date: str,
    source_artifact_path: str,
    outcome_index: dict[tuple[str, str, float], list[dict[str, Any]]] | None = None,
    pitcher_game_outcome_index: dict[tuple[str, str], list[dict[str, Any]]]
    | None = None,
    outcome_reconciliation_stats: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    stats = outcome_reconciliation_stats
    if stats is not None:
        _initialize_archive_outcome_stats(stats)
    markets: list[dict[str, Any]] = []
    for record in payload.get("pitchers") or []:
        if not isinstance(record, dict):
            continue

        k_line = _to_float(record.get("k_line"))
        actual = _to_float(record.get("actual_ks"))
        outcome_source = "archive" if actual is not None else None
        if actual is None and k_line is not None and outcome_index is not None:
            candidates = outcome_index.get(
                (date, _normalized(record.get("pitcher")), k_line),
                [],
            )
            if len(candidates) == 1:
                actual = _to_float(candidates[0].get("actual_ks"))
                outcome_source = "picks_history_exact"
                if stats is not None:
                    stats["recovered_markets"] += 1
            elif len(candidates) > 1:
                if stats is not None:
                    stats["ambiguous_markets"] += 1
            elif pitcher_game_outcome_index is not None:
                pitcher_game_candidates = pitcher_game_outcome_index.get(
                    (date, _normalized(record.get("pitcher"))),
                    [],
                )
                actual_values = {
                    value
                    for candidate in pitcher_game_candidates
                    if (value := _to_float(candidate.get("actual_ks"))) is not None
                }
                if len(actual_values) == 1:
                    actual = next(iter(actual_values))
                    outcome_source = "picks_history_pitcher_game"
                    if stats is not None:
                        stats["recovered_markets"] += 1
                elif len(actual_values) > 1 and stats is not None:
                    stats["ambiguous_markets"] += 1
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
                "archive_outcome_reconciliation_source": outcome_source,
                "source_artifact_path": source_artifact_path,
                "generated_at": payload.get("generated_at"),
            }
        )
        markets.append(market)
    return markets


def _load_remote_archived_markets_for_dataset(
    *,
    artifact_api_url_base: str,
    start_date: str,
    end_date: str | None,
    outcome_index: dict[tuple[str, str, float], list[dict[str, Any]]] | None = None,
    pitcher_game_outcome_index: dict[tuple[str, str], list[dict[str, Any]]]
    | None = None,
    outcome_reconciliation_stats: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    index_payload = _load_remote_json(artifact_api_url(artifact_api_url_base, "index"))
    dates = _artifact_dates_from_index(
        index_payload,
        start_date=start_date,
        end_date=end_date,
    )
    dates = sorted(set(dates) | set(_requested_date_range(start_date, end_date)))
    markets: list[dict[str, Any]] = []
    skipped_missing: list[str] = []
    for date in dates:
        url = artifact_api_url(artifact_api_url_base, "dated_slate", date)
        try:
            payload = _load_remote_json(url)
        except HTTPError as error:
            if error.code == 404:
                skipped_missing.append(date)
                continue
            raise
        if not isinstance(payload, dict):
            continue
        markets.extend(
            _markets_from_archive_payload(
                payload,
                date=date,
                source_artifact_path=url,
                outcome_index=outcome_index,
                pitcher_game_outcome_index=pitcher_game_outcome_index,
                outcome_reconciliation_stats=outcome_reconciliation_stats,
            )
        )
    if skipped_missing:
        preview = ", ".join(skipped_missing[:5])
        suffix = "" if len(skipped_missing) <= 5 else f", ... ({len(skipped_missing)} total)"
        print(
            f"Warning: skipped missing production dated_slate artifacts: {preview}{suffix}",
            file=sys.stderr,
        )
    return markets


def load_archived_markets_for_dataset(
    archive_dir: Path = ARCHIVE_DIR,
    *,
    start_date: str = CLEAN_WINDOW_START,
    end_date: str | None = None,
    artifact_api_url: str | None = None,
    outcome_history_rows: list[dict[str, Any]] | None = None,
    outcome_reconciliation_stats: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    if outcome_reconciliation_stats is not None:
        _initialize_archive_outcome_stats(outcome_reconciliation_stats)
    outcome_index = (
        build_archive_outcome_index(outcome_history_rows, start_date=start_date)
        if outcome_history_rows is not None
        else None
    )
    pitcher_game_outcome_index = (
        build_pitcher_game_outcome_index(
            outcome_history_rows,
            start_date=start_date,
        )
        if outcome_history_rows is not None
        else None
    )
    if artifact_api_url:
        return _load_remote_archived_markets_for_dataset(
            artifact_api_url_base=artifact_api_url,
            start_date=start_date,
            end_date=end_date,
            outcome_index=outcome_index,
            pitcher_game_outcome_index=pitcher_game_outcome_index,
            outcome_reconciliation_stats=outcome_reconciliation_stats,
        )

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

        markets.extend(
            _markets_from_archive_payload(
                payload,
                date=date,
                source_artifact_path=f"dashboard/data/processed/{date}.json",
                outcome_index=outcome_index,
                pitcher_game_outcome_index=pitcher_game_outcome_index,
                outcome_reconciliation_stats=outcome_reconciliation_stats,
            )
        )
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
            side_price_movement = _side_price_movement(opening_odds, odds)
            opportunity_bucket = _opportunity_bucket(avg_ip, recent_start_count)
            leash_risk_bucket = _leash_risk_bucket(
                is_opener=market.get("is_opener"),
                starter_mismatch=market.get("starter_mismatch"),
                avg_ip=avg_ip,
                last_pitch_count=last_pitch_count,
                days_since_last_start=days_since_last_start,
            )
            relationship = _model_market_relationship(model_side, favorite)
            edge_bucket = _model_edge_bucket(model_no_vig_gap)
            verdict = ev.get("verdict") or ev.get("raw_verdict")
            skepticism_reasons = _large_edge_skepticism_reasons(
                side=side,
                model_side=model_side,
                verdict=verdict,
                model_edge_bucket=edge_bucket,
                model_market_relationship=relationship,
                quality_gate_level=market.get("quality_gate_level"),
                quality_gate_reasons=market.get("quality_gate_reasons"),
                side_price_movement=side_price_movement,
                leash_risk_bucket=leash_risk_bucket,
                opportunity_bucket=opportunity_bucket,
            )
            season_k9 = _to_float(market.get("season_k9"))
            recent_k9 = _to_float(market.get("recent_k9"))
            career_k9 = _to_float(market.get("career_k9"))
            market_anchor_selector = ev.get("market_anchor_selector") or market.get("market_anchor_selector")
            selector_dict = market_anchor_selector if isinstance(market_anchor_selector, dict) else None
            projection_challenger = ev.get("projection_challenger") or market.get("projection_challenger")

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
                "side_price_movement": side_price_movement,
                "line_movement": None,
                "minus_to_plus_or_plus_to_minus": _sign_transition(opening_odds, odds),
                "model_side": model_side,
                "model_win_prob": round(model_win_prob, 4) if model_win_prob is not None else None,
                "model_no_vig_gap": model_no_vig_gap,
                "model_market_relationship": relationship,
                "model_edge_bucket": edge_bucket,
                "projected_ks": _projection(market),
                "k_margin_to_line": margin_to_line,
                "projection_margin_bucket": _projection_margin_bucket(margin_to_line),
                "large_edge_skepticism_flag": bool(skepticism_reasons),
                "large_edge_skepticism_reasons": skepticism_reasons,
                "edge": _to_float(ev.get("edge")),
                "ev": _to_float(ev.get("ev")),
                "adj_ev": _to_float(ev.get("adj_ev")),
                "verdict": verdict,
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
                "batter_handedness_mode": market.get("batter_handedness_mode"),
                "lineup_split_source": market.get("lineup_split_source"),
                "lineup_real_split_count": _to_int(market.get("lineup_real_split_count")),
                "lineup_path_a_fallback_count": _to_int(
                    market.get("lineup_path_a_fallback_count")
                ),
                "lineup_right_batters": _to_int(market.get("lineup_right_batters")),
                "lineup_left_batters": _to_int(market.get("lineup_left_batters")),
                "lineup_switch_batters": _to_int(market.get("lineup_switch_batters")),
                "handedness_matchup_bucket": market.get("handedness_matchup_bucket"),
                "lineup_handedness_source": None,
                "lineup_handedness_runtime_safe": None,
                "lineup_handedness_game_pk": None,
                "lineup_handedness_count_matches_existing": None,
                "opp_k_rate": _to_float(market.get("opp_k_rate")),
                "umpire": market.get("umpire"),
                "umpire_has_rating": market.get("umpire_has_rating"),
                "ump_k_adj": _to_float(market.get("ump_k_adj")),
                "park_factor": _to_float(market.get("park_factor")),
                "days_since_last_start": days_since_last_start,
                "last_pitch_count": last_pitch_count,
                "avg_ip": avg_ip,
                "recent_start_count": recent_start_count,
                "opportunity_bucket": opportunity_bucket,
                "leash_risk_bucket": leash_risk_bucket,
                "rest_k9_delta": _to_float(market.get("rest_k9_delta")),
                "season_k9": season_k9,
                "recent_k9": recent_k9,
                "career_k9": career_k9,
                "pitcher_archetype_bucket": _pitcher_archetype_bucket(
                    is_opener=market.get("is_opener"),
                    starter_mismatch=market.get("starter_mismatch"),
                    opportunity_bucket=opportunity_bucket,
                    season_k9=season_k9,
                    recent_k9=recent_k9,
                    career_k9=career_k9,
                ),
                "current_swstr_pct": _to_float(
                    market.get("current_swstr_pct") or market.get("swstr_pct")
                ),
                "career_swstr_pct": _to_float(market.get("career_swstr_pct")),
                "provider": None,
                "live_display_provider": None,
                "live_display_state": None,
                "live_display_latest_snapshot_at": None,
                "market_agreement_checkpoint": None,
                "market_agreement_label": None,
                "movement_strength_label": None,
                "movement_value_label": None,
                "movement_magnitude_bucket": None,
                "market_agreement_tracker_bucket": None,
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
                "confidence_referee": ev.get("confidence_referee") or market.get("confidence_referee"),
                "market_anchor_selector": market_anchor_selector,
                "market_anchor_selector_mode": selector_dict.get("mode") if selector_dict else None,
                "market_anchor_selector_labels": selector_dict.get("labels") if selector_dict else None,
                "market_anchor_selector_applied": selector_dict.get("applied") if selector_dict else None,
                "projection_challenger": projection_challenger,
                "locked_verdict": ev.get("locked_verdict") or market.get("locked_verdict"),
                "display_verdict": ev.get("display_verdict") or market.get("display_verdict"),
                "actionable_verdict": ev.get("actionable_verdict") or market.get("actionable_verdict"),
                "locked_adj_ev": _to_float(ev.get("locked_adj_ev") or market.get("locked_adj_ev")),
                "verdict_cap_reason": ev.get("verdict_cap_reason") or market.get("verdict_cap_reason"),
                "bet_time_line": None,
                "bet_time_odds": None,
                "bet_time_book": None,
                "bet_time_at": None,
                "price_clv_cents": None,
                "line_clv_delta": None,
                "beat_close_price": None,
                "beat_close_line": None,
                "clv_type": "not_tracked",
                "process_outcome_bucket": "unknown",
                "bet_timing_window": "unknown",
                "pick_history_pnl": None,
                "actual_ip": _to_float(market.get("actual_ip")),
                "actual_pitch_count": _to_int(market.get("actual_pitch_count")),
                "batters_faced": _to_int(market.get("batters_faced")),
                "actual_opportunity_source": None,
                "actual_opportunity_runtime_safe": None,
                "actual_opportunity_game_pk": None,
                "actual_opportunity_pitcher_match_type": None,
                "archive_outcome_reconciliation_source": market.get(
                    "archive_outcome_reconciliation_source"
                ),
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
    return alternative_selector.line_bucket(k_line)


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    key_counts = Counter(str(row.get("dataset_key")) for row in rows)
    context_counts = Counter(str(row.get("context_snapshot") or "unknown") for row in rows)
    model_market_counts = Counter(str(row.get("model_market_relationship") or "unknown") for row in rows)
    opportunity_counts = Counter(str(row.get("opportunity_bucket") or "unknown") for row in rows)
    leash_counts = Counter(str(row.get("leash_risk_bucket") or "unknown") for row in rows)
    clv_type_counts = Counter(str(row.get("clv_type") or "unknown") for row in rows)
    process_counts = Counter(str(row.get("process_outcome_bucket") or "unknown") for row in rows)
    timing_counts = Counter(str(row.get("bet_timing_window") or "unknown") for row in rows)
    archetype_counts = Counter(str(row.get("pitcher_archetype_bucket") or "unknown") for row in rows)
    lineup_handedness_source_counts = Counter(
        str(row.get("lineup_handedness_source") or "missing") for row in rows
    )
    actual_opportunity_source_counts = Counter(
        str(row.get("actual_opportunity_source") or "missing") for row in rows
    )
    market_agreement_label_counts = Counter(
        str(row.get("market_agreement_label") or "missing") for row in rows
    )
    movement_strength_counts = Counter(
        str(row.get("movement_strength_label") or "missing") for row in rows
    )
    live_display_state_counts = Counter(
        str(row.get("live_display_state") or "missing") for row in rows
    )
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
        "lineup_hand_count_rows": sum(
            1
            for row in rows
            if row.get("lineup_right_batters") is not None
            and row.get("lineup_left_batters") is not None
            and row.get("lineup_switch_batters") is not None
        ),
        "lineup_handedness_source_counts": dict(sorted(lineup_handedness_source_counts.items())),
        "actual_opportunity_rows": sum(1 for row in rows if row.get("actual_ip") is not None),
        "actual_pitch_count_rows": sum(
            1 for row in rows if row.get("actual_pitch_count") is not None
        ),
        "batters_faced_rows": sum(1 for row in rows if row.get("batters_faced") is not None),
        "actual_opportunity_source_counts": dict(sorted(actual_opportunity_source_counts.items())),
        "market_agreement_rows": sum(1 for row in rows if row.get("market_agreement_label")),
        "market_book_count_rows": sum(1 for row in rows if row.get("book_count") is not None),
        "toward_away_count_rows": sum(
            1
            for row in rows
            if row.get("toward_pick_count") is not None
            and row.get("away_from_pick_count") is not None
        ),
        "market_broad_confirmation_rows": sum(
            1 for row in rows if row.get("broad_confirmation") is True
        ),
        "live_display_rows": sum(1 for row in rows if row.get("live_display_provider")),
        "best_off_market_rows": sum(1 for row in rows if row.get("best_is_off_market") is True),
        "market_agreement_label_counts": dict(sorted(market_agreement_label_counts.items())),
        "movement_strength_label_counts": dict(sorted(movement_strength_counts.items())),
        "live_display_state_counts": dict(sorted(live_display_state_counts.items())),
        "large_edge_skepticism_rows": sum(1 for row in rows if row.get("large_edge_skepticism_flag") is True),
        "model_market_relationship_counts": dict(sorted(model_market_counts.items())),
        "opportunity_bucket_counts": dict(sorted(opportunity_counts.items())),
        "leash_risk_bucket_counts": dict(sorted(leash_counts.items())),
        "clv_type_counts": dict(sorted(clv_type_counts.items())),
        "process_outcome_bucket_counts": dict(sorted(process_counts.items())),
        "bet_timing_window_counts": dict(sorted(timing_counts.items())),
        "pitcher_archetype_bucket_counts": dict(sorted(archetype_counts.items())),
    }


def reconcile_picks_history(
    rows: list[dict[str, Any]],
    *,
    history_path: Path = PICKS_HISTORY,
    start_date: str = CLEAN_WINDOW_START,
    artifact_api_url: str | None = None,
    included_slate_dates: set[str] | None = None,
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
    payload = _load_picks_history_payload(
        history_path=history_path,
        artifact_api_url_base=artifact_api_url,
    )

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
        if included_slate_dates is not None and slate_date not in included_slate_dates:
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


def _load_picks_history_payload(
    *,
    history_path: Path,
    artifact_api_url_base: str | None = None,
) -> Any:
    if artifact_api_url_base:
        return _load_remote_json(artifact_api_url(artifact_api_url_base, "picks_history"))
    try:
        return json.loads(history_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _load_picks_history(path: Path, artifact_api_url_base: str | None = None) -> list[dict[str, Any]]:
    payload = _load_picks_history_payload(
        history_path=path,
        artifact_api_url_base=artifact_api_url_base,
    )
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
    artifact_api_url: str | None = None,
    history_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    loaded_history_rows = (
        history_rows
        if history_rows is not None
        else _load_picks_history(history_path, artifact_api_url)
    )
    exact, side_index = _history_indexes(loaded_history_rows, start_date)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        pick, match_type = _pick_for_row(row, exact, side_index)
        next_row = dict(row)
        next_row.setdefault("is_tracked_pick", False)
        next_row.setdefault("pick_history_match_type", None)
        next_row.setdefault("confidence_referee", None)
        next_row.setdefault("market_anchor_selector", None)
        next_row.setdefault("market_anchor_selector_mode", None)
        next_row.setdefault("market_anchor_selector_labels", None)
        next_row.setdefault("market_anchor_selector_applied", None)
        next_row.setdefault("projection_challenger", None)
        next_row.setdefault("locked_verdict", None)
        next_row.setdefault("display_verdict", None)
        next_row.setdefault("actionable_verdict", None)
        next_row.setdefault("locked_adj_ev", None)
        next_row.setdefault("verdict_cap_reason", None)
        next_row.setdefault("bet_time_line", None)
        next_row.setdefault("bet_time_odds", None)
        next_row.setdefault("bet_time_book", None)
        next_row.setdefault("bet_time_at", None)
        next_row.setdefault("price_clv_cents", None)
        next_row.setdefault("line_clv_delta", None)
        next_row.setdefault("beat_close_price", None)
        next_row.setdefault("beat_close_line", None)
        next_row.setdefault("clv_type", "not_tracked")
        next_row.setdefault("process_outcome_bucket", "unknown")
        next_row.setdefault("bet_timing_window", "unknown")
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
                    "confidence_referee": pick.get("confidence_referee")
                    if pick.get("confidence_referee") is not None
                    else next_row.get("confidence_referee"),
                    "market_anchor_selector": pick.get("market_anchor_selector")
                    if pick.get("market_anchor_selector") is not None
                    else next_row.get("market_anchor_selector"),
                    "projection_challenger": pick.get("projection_challenger")
                    if pick.get("projection_challenger") is not None
                    else next_row.get("projection_challenger"),
                    "locked_verdict": pick.get("locked_verdict")
                    if pick.get("locked_verdict") is not None
                    else next_row.get("locked_verdict"),
                    "display_verdict": pick.get("display_verdict")
                    if pick.get("display_verdict") is not None
                    else (
                        pick.get("locked_verdict")
                        or pick.get("verdict")
                        or next_row.get("display_verdict")
                    ),
                    "actionable_verdict": pick.get("actionable_verdict")
                    if pick.get("actionable_verdict") is not None
                    else next_row.get("actionable_verdict"),
                    "raw_verdict": pick.get("raw_verdict")
                    if pick.get("raw_verdict") is not None
                    else next_row.get("raw_verdict"),
                    "locked_adj_ev": _to_float(pick.get("locked_adj_ev"))
                    if pick.get("locked_adj_ev") is not None
                    else next_row.get("locked_adj_ev"),
                    "verdict_cap_reason": pick.get("verdict_cap_reason")
                    if pick.get("verdict_cap_reason") is not None
                    else next_row.get("verdict_cap_reason"),
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
            selector = next_row.get("market_anchor_selector")
            if isinstance(selector, dict):
                next_row["market_anchor_selector_mode"] = selector.get("mode")
                next_row["market_anchor_selector_labels"] = selector.get("labels")
                next_row["market_anchor_selector_applied"] = selector.get("applied")
            clv_type = _clv_type(True, price_clv_cents, line_clv_delta)
            next_row.update(
                {
                    "clv_type": clv_type,
                    "process_outcome_bucket": _process_outcome_bucket(next_row.get("result"), clv_type),
                    "bet_timing_window": _bet_timing_window(
                        next_row.get("bet_time_at"),
                        next_row.get("game_time") or pick.get("game_time"),
                    ),
                }
            )
        enriched.append(next_row)
    return enriched


def _load_lineup_handedness_backfill(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    lineups = payload.get("lineups") if isinstance(payload, dict) else None
    return {str(key): value for key, value in lineups.items() if isinstance(value, dict)} if isinstance(lineups, dict) else {}


def _load_actual_opportunity_backfill(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    opportunities = payload.get("opportunities") if isinstance(payload, dict) else None
    return (
        {str(key): value for key, value in opportunities.items() if isinstance(value, dict)}
        if isinstance(opportunities, dict)
        else {}
    )


def enrich_rows_with_lineup_handedness(
    rows: list[dict[str, Any]],
    *,
    backfill_path: Path = LINEUP_HANDEDNESS_BACKFILL,
) -> list[dict[str, Any]]:
    lineups = _load_lineup_handedness_backfill(backfill_path)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        next_row = dict(row)
        next_row.setdefault("lineup_handedness_source", None)
        next_row.setdefault("lineup_handedness_runtime_safe", None)
        next_row.setdefault("lineup_handedness_game_pk", None)
        next_row.setdefault("lineup_handedness_count_matches_existing", None)

        key = lineup_handedness_lookup_key(
            next_row.get("slate_date"),
            next_row.get("team"),
            next_row.get("opp_team"),
            next_row.get("game_time"),
        )
        lineup = lineups.get(key)
        if lineup:
            right = _to_int(lineup.get("lineup_right_batters"))
            left = _to_int(lineup.get("lineup_left_batters"))
            switch = _to_int(lineup.get("lineup_switch_batters"))
            reconstructed_count = _to_int(lineup.get("lineup_count"))
            existing_count = _to_int(next_row.get("lineup_count"))
            next_row.update(
                {
                    "lineup_right_batters": right,
                    "lineup_left_batters": left,
                    "lineup_switch_batters": switch,
                    "lineup_handedness_source": lineup.get("lineup_handedness_source"),
                    "lineup_handedness_runtime_safe": lineup.get("lineup_handedness_runtime_safe"),
                    "lineup_handedness_game_pk": lineup.get("game_pk"),
                    "lineup_handedness_count_matches_existing": (
                        existing_count == reconstructed_count
                        if existing_count is not None and reconstructed_count is not None
                        else None
                    ),
                }
            )
            if reconstructed_count is not None and existing_count is None:
                next_row["lineup_count"] = reconstructed_count
            next_row["handedness_matchup_bucket"] = handedness_matchup_bucket(
                pitcher_throws=next_row.get("pitcher_throws"),
                right_batters=right,
                left_batters=left,
                switch_batters=switch,
            )
        enriched.append(next_row)
    return enriched


def enrich_rows_with_actual_opportunity(
    rows: list[dict[str, Any]],
    *,
    backfill_path: Path = ACTUAL_OPPORTUNITY_BACKFILL,
) -> list[dict[str, Any]]:
    opportunities = _load_actual_opportunity_backfill(backfill_path)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        next_row = dict(row)
        next_row.setdefault("actual_ip", None)
        next_row.setdefault("actual_pitch_count", None)
        next_row.setdefault("batters_faced", None)
        next_row.setdefault("actual_opportunity_source", None)
        next_row.setdefault("actual_opportunity_runtime_safe", None)
        next_row.setdefault("actual_opportunity_game_pk", None)
        next_row.setdefault("actual_opportunity_pitcher_match_type", None)

        key = actual_opportunity_lookup_key(
            next_row.get("slate_date"),
            next_row.get("team"),
            next_row.get("opp_team"),
            next_row.get("game_time"),
            next_row.get("pitcher") or next_row.get("normalized_pitcher"),
        )
        opportunity = opportunities.get(key)
        if opportunity:
            next_row.update(
                {
                    "actual_ip": _to_float(opportunity.get("actual_ip")),
                    "actual_pitch_count": _to_int(opportunity.get("actual_pitch_count")),
                    "batters_faced": _to_int(opportunity.get("batters_faced")),
                    "actual_opportunity_source": opportunity.get("actual_opportunity_source"),
                    "actual_opportunity_runtime_safe": opportunity.get(
                        "actual_opportunity_runtime_safe"
                    ),
                    "actual_opportunity_game_pk": opportunity.get("game_pk"),
                    "actual_opportunity_pitcher_match_type": opportunity.get(
                        "pitcher_match_type"
                    ),
                }
            )
        enriched.append(next_row)
    return enriched


def render_summary(summary: dict[str, Any]) -> str:
    archive_reconciliation = summary.get("archive_outcome_reconciliation") or {}
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
        f"- Rows with lineup hand counts: `{summary.get('lineup_hand_count_rows', 0)}`",
        f"- Rows with actual IP: `{summary.get('actual_opportunity_rows', 0)}`",
        f"- Rows with actual pitch count: `{summary.get('actual_pitch_count_rows', 0)}`",
        f"- Rows with batters faced: `{summary.get('batters_faced_rows', 0)}`",
        f"- Rows with market agreement labels: `{summary.get('market_agreement_rows', 0)}`",
        f"- Rows with market book counts: `{summary.get('market_book_count_rows', 0)}`",
        f"- Rows with toward/away counts: `{summary.get('toward_away_count_rows', 0)}`",
        f"- Rows with live display book-board fields: `{summary.get('live_display_rows', 0)}`",
        f"- Broad market confirmation rows: `{summary.get('market_broad_confirmation_rows', 0)}`",
        f"- Best off-market rows: `{summary.get('best_off_market_rows', 0)}`",
        f"- Large-edge skepticism rows: `{summary.get('large_edge_skepticism_rows', 0)}`",
        f"- Clean graded picks reconciled: `{summary.get('matched_pick_rows', 0)}/{summary.get('graded_pick_rows', 0)}`",
        f"- Unique side fallback reconciliations: `{summary.get('unique_side_fallback_matches', 0)}`",
        f"- Unmatched clean graded picks: `{summary.get('unmatched_pick_rows', 0)}`",
        f"- Archive outcomes recovered from one exact graded history row: `{archive_reconciliation.get('recovered_markets', 0)}`",
        f"- Ambiguous archive outcome matches left excluded: `{archive_reconciliation.get('ambiguous_markets', 0)}`",
        "",
        "## Context Snapshots",
        "",
    ]
    for context, count in summary["context_snapshot_counts"].items():
        lines.append(f"- `{context}`: `{count}`")
    for title, key in (
        ("Model Vs Market Relationship", "model_market_relationship_counts"),
        ("CLV Types", "clv_type_counts"),
        ("Process Outcome Buckets", "process_outcome_bucket_counts"),
        ("Bet Timing Windows", "bet_timing_window_counts"),
        ("Opportunity Buckets", "opportunity_bucket_counts"),
        ("Leash Risk Buckets", "leash_risk_bucket_counts"),
        ("Pitcher Archetype Buckets", "pitcher_archetype_bucket_counts"),
        ("Lineup Handedness Sources", "lineup_handedness_source_counts"),
        ("Actual Opportunity Sources", "actual_opportunity_source_counts"),
        ("Market Agreement Labels", "market_agreement_label_counts"),
        ("Movement Strength Labels", "movement_strength_label_counts"),
        ("Live Display States", "live_display_state_counts"),
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
    lineup_handedness_backfill_path: Path = LINEUP_HANDEDNESS_BACKFILL,
    actual_opportunity_backfill_path: Path = ACTUAL_OPPORTUNITY_BACKFILL,
    market_agreement_tracker_path: Path | None = MARKET_AGREEMENT_TRACKER,
    live_market_display_path: Path | None = LIVE_MARKET_DISPLAY,
    artifact_api_url: str | None = None,
    picks_history_path: Path | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    history_rows = _load_picks_history(
        picks_history_path or PICKS_HISTORY,
        None if picks_history_path is not None else artifact_api_url,
    )
    archive_outcome_stats: dict[str, int] = {}
    markets = load_archived_markets_for_dataset(
        archive_dir,
        start_date=start_date,
        end_date=end_date,
        artifact_api_url=artifact_api_url,
        outcome_history_rows=history_rows,
        outcome_reconciliation_stats=archive_outcome_stats,
    )
    if diagnostics is not None:
        diagnostics["archive_outcome_reconciliation"] = dict(archive_outcome_stats)
    rows = build_official_close_rows(markets)
    rows = enrich_rows_with_lineup_handedness(
        rows,
        backfill_path=lineup_handedness_backfill_path,
    )
    rows = enrich_rows_with_actual_opportunity(
        rows,
        backfill_path=actual_opportunity_backfill_path,
    )
    rows = enrich_rows_with_pick_history(
        rows,
        start_date=start_date,
        history_rows=history_rows,
    )
    rows = enrich_rows_with_market_agreement(
        rows,
        tracker_path=market_agreement_tracker_path,
    )
    return enrich_rows_with_live_market_display(
        rows,
        live_market_display_path=live_market_display_path,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the shadow pitcher K outcome dataset.")
    parser.add_argument("--start-date", default=CLEAN_WINDOW_START)
    parser.add_argument("--end-date")
    parser.add_argument("--jsonl-output", type=Path, default=OUTPUT_JSONL)
    parser.add_argument("--summary-output", type=Path, default=OUTPUT_SUMMARY)
    parser.add_argument("--lineup-handedness-backfill", type=Path, default=LINEUP_HANDEDNESS_BACKFILL)
    parser.add_argument("--actual-opportunity-backfill", type=Path, default=ACTUAL_OPPORTUNITY_BACKFILL)
    parser.add_argument("--market-agreement-tracker", type=Path, default=MARKET_AGREEMENT_TRACKER)
    parser.add_argument("--live-market-display", type=Path, default=LIVE_MARKET_DISPLAY)
    parser.add_argument(
        "--artifact-source",
        choices=("local", "production"),
        default="local",
        help="Use committed local artifacts or the production Netlify artifact API.",
    )
    parser.add_argument(
        "--artifact-api-url",
        default=os.environ.get("BBE_ARTIFACT_API_URL", "").strip() or DEFAULT_ARTIFACT_API_URL,
        help="Base get-artifact URL used when --artifact-source=production.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    artifact_api_url_base = args.artifact_api_url if args.artifact_source == "production" else None
    rows = build_dataset(
        start_date=args.start_date,
        end_date=args.end_date,
        lineup_handedness_backfill_path=args.lineup_handedness_backfill,
        actual_opportunity_backfill_path=args.actual_opportunity_backfill,
        market_agreement_tracker_path=args.market_agreement_tracker,
        live_market_display_path=args.live_market_display,
        artifact_api_url=artifact_api_url_base,
    )
    validation_errors = [
        (row.get("dataset_key"), errors)
        for row in rows
        if (errors := validate_dataset_row(row))
    ]
    if validation_errors:
        preview = validation_errors[:5]
        raise SystemExit(f"Dataset validation failed: {preview}")

    summary = build_summary(rows)
    summary.update(
        reconcile_picks_history(
            rows,
            start_date=args.start_date,
            artifact_api_url=artifact_api_url_base,
            included_slate_dates=(
                {str(row.get("slate_date") or "").strip() for row in rows if row.get("slate_date")}
                if artifact_api_url_base
                else None
            ),
        )
    )
    write_jsonl(rows, args.jsonl_output)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(render_summary(summary), encoding="utf-8")
    print(render_summary(summary))


if __name__ == "__main__":
    main()
