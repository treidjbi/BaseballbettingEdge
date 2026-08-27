"""Offline CLV target rows for evaluating future live-safe process proxies."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from analytics.diagnostics import gate_f_preclose_clv_proxy_lab as preclose_proxy
from analytics.diagnostics import market_agreement_tracker
from analytics.diagnostics import strong_base_decision_lab as strong_base
from pipeline.name_utils import normalize


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "analytics" / "output"
CURRENT_PROVIDER_START = "2026-06-24"
CURRENT_PROVIDER_VALUES = {"therundown", "propline", "therundown_propline"}
PROXY_LABELS = (
    "strong_preclose_clv_proxy",
    "medium_preclose_clv_proxy",
    "weak_preclose_clv_proxy",
)
PROXY_FORECASTS = {
    "strong_preclose_clv_proxy": 0.75,
    "medium_preclose_clv_proxy": 0.50,
    "weak_preclose_clv_proxy": 0.25,
}
AGREEMENT_FORECASTS = {
    "market_with_model": 0.75,
    "market_mixed": 0.50,
    "market_no_signal": 0.50,
    "market_against_model": 0.25,
}
LIVE_SAFE_PROXY_FIELDS = (
    "edge",
    "adj_ev",
    "ev",
    "locked_adj_ev",
    "model_no_vig_gap",
    "price_sign",
    "quality_gate_level",
    "bet_timing_window",
    "side_price_movement",
    "toward_pick_count",
    "away_from_pick_count",
    "book_count",
    "books_seen",
    "broad_confirmation",
    "best_is_off_market",
    "reversal_book_count",
    "volatile_book_count",
    "model_market_relationship",
    "market_consensus",
    "market_agreement_label",
    "line_bucket",
    "batter_handedness_mode",
    "lineup_real_split_count",
    "lineup_split_source",
    "lineup_handedness_runtime_safe",
    "leash_risk_bucket",
    "opportunity_bucket",
    "workload_bucket",
    "is_opener",
    "last_pitch_count",
    "recent_start_count",
)


def _timezone_aware_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def load_close_evidence_packet(path: Path) -> list[dict[str, Any]]:
    """Load only the explicit official-close packet; reject movement-rollup shapes."""
    if not path.is_file():
        raise ValueError("close packet is missing or unreadable")
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError("close packet is missing or unreadable") from exc
    if not content:
        return []
    try:
        if path.suffix.lower() == ".json":
            parsed = json.loads(content)
            rows = parsed if isinstance(parsed, list) else [parsed]
        else:
            rows = [json.loads(line) for line in content.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise ValueError("close packet is malformed JSON or JSONL") from exc
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("close packet rows must be objects")
    for row in rows:
        if str(row.get("observation_type") or "").strip().lower() != "official_close":
            raise ValueError("close packet requires official_close observations")
        required_strings = (
            _slate_date(row),
            _normalized_pitcher(row),
            str(row.get("provider") or "").strip().lower(),
            _book(row.get("bookmaker")),
            str(row.get("observation_id") or "").strip(),
            str(row.get("freshness") or "").strip().lower(),
        )
        if not all(required_strings) or _timezone_aware_timestamp(row.get("observed_at")) is None:
            raise ValueError("close packet row is missing required provenance")
        if str(row.get("side") or "").strip().lower() not in {"over", "under"}:
            raise ValueError("close packet row requires over or under side")
        if _number(row.get("line")) is None or _number(row.get("american_odds")) is None:
            raise ValueError("close packet row requires numeric close line and price")
        if not _has_operational_lock_provenance(row):
            raise ValueError("close packet row is missing operational lock provenance")
    return rows


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_operational_lock_provenance(row: dict[str, Any]) -> bool:
    required_strings = (
        str(row.get("official_lock_reference") or "").strip(),
        str(row.get("lock_provider") or "").strip().lower(),
        _book(row.get("lock_book")),
        str(row.get("lock_source_artifact_path") or "").strip(),
        str(row.get("lock_source_artifact_sha256") or "").strip(),
    )
    return (
        all(required_strings)
        and _number(row.get("lock_line")) is not None
        and _number(row.get("lock_odds")) is not None
        and _timezone_aware_timestamp(row.get("lock_observed_at")) is not None
    )


def _book(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _fresh(row: dict[str, Any]) -> bool:
    return str(row.get("freshness") or "").strip().lower() == "fresh"


def _slate_date(row: dict[str, Any]) -> str:
    return str(row.get("slate_date") or row.get("date") or "").strip()


def _normalized_pitcher(row: dict[str, Any]) -> str:
    return normalize(str(row.get("normalized_pitcher") or row.get("pitcher") or row.get("player_name") or ""))


def _event_identity(row: dict[str, Any]) -> str:
    for key in ("provider_event_id", "event_id", "game_id", "game_pk"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _same_identity(lock_row: dict[str, Any], close_row: dict[str, Any]) -> bool:
    lock_date = _slate_date(lock_row)
    close_date = _slate_date(close_row)
    lock_pitcher = _normalized_pitcher(lock_row)
    close_pitcher = _normalized_pitcher(close_row)
    lock_side = str(lock_row.get("side") or "").strip().lower()
    close_side = str(close_row.get("side") or "").strip().lower()
    if not all((lock_date, close_date, lock_pitcher, close_pitcher, lock_side, close_side)):
        return False
    if (lock_date, lock_pitcher, lock_side) != (close_date, close_pitcher, close_side):
        return False
    lock_event = _event_identity(lock_row)
    close_event = _event_identity(close_row)
    return not (lock_event and close_event and lock_event != close_event)


def _same_line(lock_line: float | None, close_line: float | None) -> bool:
    return lock_line is not None and close_line is not None and lock_line == close_line


def classify_final_clv(row: dict[str, Any]) -> str:
    if row.get("close_eligibility") != "eligible":
        return "unknown"

    lock_line = _number(row.get("lock_line"))
    close_line = _number(row.get("close_line"))
    side = str(row.get("side") or "").lower()
    if lock_line is None or close_line is None:
        return "unknown"
    if side == "over" and close_line > lock_line:
        return "beat_close_line"
    if side == "under" and close_line < lock_line:
        return "beat_close_line"
    if lock_line != close_line:
        return "worse_close_line"
    lock_odds = _number(row.get("lock_odds"))
    close_odds = _number(row.get("close_odds"))
    if lock_odds is None or close_odds is None:
        return "unknown"
    if lock_odds > close_odds:
        return "beat_close_price"
    if lock_odds < close_odds:
        return "worse_close_price"
    return "neutral_close"


def build_target_row(gate_c_row: dict[str, Any], market_rows: list[dict[str, Any]]) -> dict[str, Any]:
    slate_date = _slate_date(gate_c_row)
    display_pitcher = str(
        gate_c_row.get("pitcher") or gate_c_row.get("player_name") or gate_c_row.get("normalized_pitcher") or ""
    ).strip()
    normalized_pitcher = _normalized_pitcher(gate_c_row)
    side = str(gate_c_row.get("side") or "").strip().lower()
    gate_c_lock_provider = str(
        gate_c_row.get("lock_provider") or gate_c_row.get("provider") or ""
    ).strip().lower()
    if not gate_c_lock_provider:
        for field in ("official_line_source_provider", "official_odds_source"):
            candidate = str(gate_c_row.get(field) or "").strip().lower()
            if candidate in {"therundown", "propline"}:
                gate_c_lock_provider = candidate
                break
    gate_c_lock_book = str(
        gate_c_row.get("lock_book")
        or gate_c_row.get("bet_time_book")
        or gate_c_row.get("bookmaker_title")
        or gate_c_row.get("bookmaker_key")
        or ""
    ).strip()
    gate_c_lock_line = _number(gate_c_row.get("lock_line"))
    if gate_c_lock_line is None:
        gate_c_lock_line = _number(gate_c_row.get("bet_time_line"))
    if gate_c_lock_line is None:
        gate_c_lock_line = _number(gate_c_row.get("k_line"))
    gate_c_lock_odds = _number(gate_c_row.get("lock_odds"))
    if gate_c_lock_odds is None:
        gate_c_lock_odds = _number(gate_c_row.get("bet_time_odds"))
    if gate_c_lock_odds is None:
        gate_c_lock_odds = _number(gate_c_row.get("american_odds"))
    gate_c_lock_observed_at = gate_c_row.get("locked_at") or gate_c_row.get("bet_time_at")

    close_observations = [
        observation
        for observation in market_rows
        if str(observation.get("observation_type") or "").lower() == "official_close"
    ]
    close_candidates = [observation for observation in close_observations if _same_identity(gate_c_row, observation)]
    operational_candidates = [
        observation
        for observation in close_candidates
        if _has_operational_lock_provenance(observation)
    ]
    uses_operational_lock = bool(operational_candidates)
    if uses_operational_lock:
        close = operational_candidates[0]
        lock_provider = str(close.get("lock_provider") or "").strip().lower()
        lock_book = str(close.get("lock_book") or "").strip()
        lock_line = _number(close.get("lock_line"))
        lock_odds = _number(close.get("lock_odds"))
        lock_observed_at = close.get("lock_observed_at")
        official_lock_reference = close.get("official_lock_reference")
        lock_source_artifact_path = close.get("lock_source_artifact_path")
        lock_source_artifact_sha256 = close.get("lock_source_artifact_sha256")
    else:
        matching_provider = [
            observation
            for observation in close_candidates
            if gate_c_lock_provider
            and _book(gate_c_lock_book)
            and str(observation.get("provider") or "").strip().lower()
            == gate_c_lock_provider
            and _book(observation.get("bookmaker")) == _book(gate_c_lock_book)
        ]
        close_candidates = matching_provider or close_candidates
        close = next(
            (
                observation
                for observation in close_candidates
                if _same_line(gate_c_lock_line, _number(observation.get("line")))
            ),
            None,
        )
        close = close or (close_candidates[0] if close_candidates else None)
        lock_provider = gate_c_lock_provider
        lock_book = gate_c_lock_book
        lock_line = gate_c_lock_line
        lock_odds = gate_c_lock_odds
        lock_observed_at = gate_c_lock_observed_at
        official_lock_reference = gate_c_row.get("official_lock_reference") or gate_c_row.get("dataset_key")
        lock_source_artifact_path = None
        lock_source_artifact_sha256 = None
    close_provider = str(close.get("provider") or "").strip().lower() if close else ""
    close_book = _book(close.get("bookmaker")) if close else ""
    close_line = _number(close.get("line")) if close else None
    lock_timestamp = _timezone_aware_timestamp(lock_observed_at)
    close_timestamp = _timezone_aware_timestamp(close.get("observed_at")) if close else None
    gate_c_timestamp = _timezone_aware_timestamp(gate_c_lock_observed_at)
    gate_c_book_agrees = (
        _book(gate_c_lock_book) == _book(lock_book)
        if _book(gate_c_lock_book) and _book(lock_book)
        else None
    )
    gate_c_line_agrees = (
        gate_c_lock_line == lock_line
        if gate_c_lock_line is not None and lock_line is not None
        else None
    )
    gate_c_odds_agrees = (
        gate_c_lock_odds == lock_odds
        if gate_c_lock_odds is not None and lock_odds is not None
        else None
    )
    gate_c_timestamp_agrees = (
        gate_c_timestamp == lock_timestamp
        if gate_c_timestamp is not None and lock_timestamp is not None
        else None
    )
    eligibility = "identity_mismatch" if close_observations else "missing_close"
    if close:
        if not lock_provider:
            eligibility = "missing_lock_provider"
        elif not close_provider:
            eligibility = "missing_close_provider"
        elif close_provider != lock_provider:
            eligibility = "provider_mismatch"
        elif not _book(lock_book):
            eligibility = "missing_lock_book"
        elif not close_book:
            eligibility = "missing_close_book"
        elif close_book != _book(lock_book):
            eligibility = "book_mismatch"
        elif not lock_observed_at:
            eligibility = "missing_lock_timestamp"
        elif lock_timestamp is None:
            eligibility = "invalid_lock_timestamp"
        elif not close.get("observed_at"):
            eligibility = "missing_close_timestamp"
        elif close_timestamp is None:
            eligibility = "invalid_close_timestamp"
        elif close_timestamp <= lock_timestamp:
            eligibility = "close_not_after_lock"
        elif lock_line is None:
            eligibility = "missing_lock_line"
        elif close_line is None:
            eligibility = "missing_close_line"
        elif close.get("freshness") is None or str(close.get("freshness")).strip() == "":
            eligibility = "missing_close_freshness"
        elif not _fresh(close):
            eligibility = "stale_evidence"
        elif uses_operational_lock and None in (
            gate_c_line_agrees,
            gate_c_odds_agrees,
            gate_c_timestamp_agrees,
        ):
            eligibility = "missing_gate_c_lock_reconciliation"
        elif uses_operational_lock and not gate_c_line_agrees:
            eligibility = "gate_c_lock_line_mismatch"
        elif uses_operational_lock and not gate_c_odds_agrees:
            eligibility = "gate_c_lock_odds_mismatch"
        elif uses_operational_lock and not gate_c_timestamp_agrees:
            eligibility = "gate_c_lock_timestamp_mismatch"
        else:
            eligibility = "eligible"
    row = {
        "target_key": f"{slate_date}:{normalized_pitcher}:{side}",
        "slate_date": slate_date,
        "normalized_pitcher": normalized_pitcher,
        "display_pitcher": display_pitcher,
        "side": side,
        "official_lock_reference": official_lock_reference,
        "lock_observed_at": lock_observed_at,
        "lock_provider": lock_provider or None,
        "lock_book": lock_book or None,
        "lock_line": lock_line,
        "lock_odds": lock_odds,
        "lock_source_artifact_path": lock_source_artifact_path,
        "lock_source_artifact_sha256": lock_source_artifact_sha256,
        "gate_c_bet_time_book": gate_c_lock_book or None,
        "gate_c_book_agrees_with_operational_lock": gate_c_book_agrees,
        "gate_c_line_agrees_with_operational_lock": gate_c_line_agrees,
        "gate_c_odds_agrees_with_operational_lock": gate_c_odds_agrees,
        "gate_c_timestamp_agrees_with_operational_lock": gate_c_timestamp_agrees,
        "close_eligibility": eligibility,
        "close_observation_id": close.get("observation_id") if close else None,
        "close_observed_at": close.get("observed_at") if close else None,
        "close_provider": close.get("provider") if close else None,
        "close_book": close.get("bookmaker") if close else None,
        "close_line": close_line,
        "close_odds": _number(close.get("american_odds")) if close else None,
        "close_freshness": close.get("freshness") if close else None,
        "close_line_match": (
            "same_line"
            if close and _same_line(lock_line, close_line)
            else ("alternate_line" if close and lock_line is not None and close_line is not None else "unknown")
        ),
        # Graded PnL is descriptive report context only. It is deliberately
        # kept outside the explicitly bounded pre-close proxy input surface.
        "pick_history_pnl": _number(gate_c_row.get("pick_history_pnl")),
        "theoretical_pnl": _number(gate_c_row.get("theoretical_pnl")),
        "preclose_proxy_inputs": {
            "side": side,
            **{field: gate_c_row.get(field) for field in LIVE_SAFE_PROXY_FIELDS},
        },
    }
    row["final_clv"] = classify_final_clv(row)
    return row


def classify_proxy(row: dict[str, Any]) -> str:
    """Return the shared pre-close label without reading any outcome fields."""
    return str(preclose_proxy.preclose_clv_proxy_score(_proxy_inputs(row))["label"])


def _proxy_inputs(row: dict[str, Any]) -> dict[str, Any]:
    """Keep the scorer's input surface explicit and free of post-close outcomes."""
    source = row.get("preclose_proxy_inputs")
    if not isinstance(source, dict):
        source = row
    return {
        "side": str(row.get("side") or source.get("side") or "").strip().lower(),
        **{field: source.get(field) for field in LIVE_SAFE_PROXY_FIELDS},
    }


def _target_bucket(row: dict[str, Any]) -> str:
    if row.get("close_eligibility") != "eligible":
        return "unknown"
    label = str(row.get("final_clv") or "unknown")
    if label.startswith("beat_close_"):
        return "beat"
    if label == "neutral_close":
        return "neutral"
    if label.startswith("worse_close_"):
        return "worse"
    return "unknown"


def _agreement_label(row: dict[str, Any]) -> str:
    inputs = _proxy_inputs(row)
    if inputs.get("market_consensus") not in (None, ""):
        return market_agreement_tracker.movement_agreement_label(inputs)
    existing = str(inputs.get("market_agreement_label") or "").strip().lower()
    return existing or "market_no_signal"


def _price_label(row: dict[str, Any]) -> str:
    value = str(_proxy_inputs(row).get("price_sign") or "").strip().lower()
    if value:
        return value
    odds = _number(row.get("lock_odds"))
    return "plus" if odds is not None and odds > 0 else "minus" if odds is not None else "unknown"


def _line_label(row: dict[str, Any]) -> str:
    value = str(_proxy_inputs(row).get("line_bucket") or "").strip()
    if value:
        return value
    line = _number(row.get("lock_line"))
    return f"{line:g}" if line is not None else "unknown"


def _path_b_label(row: dict[str, Any]) -> str:
    return strong_base.path_b_coverage_bucket(_proxy_inputs(row))


def _workload_label(row: dict[str, Any]) -> str:
    inputs = _proxy_inputs(row)
    return str(
        inputs.get("workload_bucket")
        or inputs.get("leash_risk_bucket")
        or inputs.get("opportunity_bucket")
        or "unknown"
    ).strip().lower()


def _provider_label(row: dict[str, Any]) -> str:
    return str(row.get("lock_provider") or row.get("provider") or "unknown").strip().lower() or "unknown"


def _provider_era(row: dict[str, Any]) -> str:
    return strong_base.provider_era({"slate_date": _slate_date(row)})


def _pnl(row: dict[str, Any]) -> float | None:
    for field in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = _number(row.get(field))
        if value is not None:
            return value
    return None


def _is_fully_attributed_current_provider(row: dict[str, Any]) -> bool:
    if _target_bucket(row) == "unknown" or _slate_date(row) < CURRENT_PROVIDER_START:
        return False
    lock_provider = str(row.get("lock_provider") or "").strip().lower()
    close_provider = str(row.get("close_provider") or "").strip().lower()
    lock_book = _book(row.get("lock_book"))
    close_book = _book(row.get("close_book"))
    return (
        lock_provider in CURRENT_PROVIDER_VALUES
        and close_provider == lock_provider
        and bool(lock_book)
        and close_book == lock_book
    )


def _bucket_metrics(
    rows: list[dict[str, Any]],
    *,
    denominator: int,
    base_rate: float | None,
    forecast: float | None,
) -> dict[str, Any]:
    evaluated = [row for row in rows if _target_bucket(row) != "unknown"]
    target_counts = Counter(_target_bucket(row) for row in evaluated)
    evaluated_rows = len(evaluated)
    beat_rows = int(target_counts["beat"])
    precision = round(beat_rows / evaluated_rows, 4) if evaluated_rows else None
    brier = (
        round(
            sum((float(forecast) - (1.0 if _target_bucket(row) == "beat" else 0.0)) ** 2 for row in evaluated)
            / evaluated_rows,
            4,
        )
        if evaluated_rows and forecast is not None
        else None
    )
    # PnL stays a descriptive cross-tab. Unlike the CLV target, it can exist
    # when close evidence is unknown, so retain it without recoding that row.
    pnl_values = [value for row in rows if (value := _pnl(row)) is not None]
    return {
        "rows": len(rows),
        "evaluated_rows": evaluated_rows,
        "coverage": round(evaluated_rows / denominator, 4) if denominator else 0.0,
        "target_counts": {bucket: int(target_counts[bucket]) for bucket in ("beat", "neutral", "worse")},
        "precision": precision,
        "base_rate": base_rate,
        "lift_vs_base_rate": (
            round(precision - base_rate, 4)
            if precision is not None and base_rate is not None
            else None
        ),
        "forecast_probability": forecast,
        "brier_style_score": brier,
        "pnl_rows": len(pnl_values),
        "pnl": round(sum(pnl_values), 2),
        "roi": round(sum(pnl_values) / len(pnl_values), 4) if pnl_values else None,
    }


def _rolling_14_slate_windows(rows: list[dict[str, Any]], base_rate: float | None) -> list[dict[str, Any]]:
    dates = sorted({_slate_date(row) for row in rows if _slate_date(row)})
    if not dates:
        return []
    windows: list[dict[str, Any]] = []
    for start in range(max(0, len(dates) - 28), len(dates), 14):
        window_dates = dates[start : start + 14]
        if not window_dates:
            continue
        window_rows = [row for row in rows if _slate_date(row) in set(window_dates)]
        denominator = len(window_rows)
        eligible = [row for row in window_rows if _target_bucket(row) != "unknown"]
        window_base = len([row for row in eligible if _target_bucket(row) == "beat"]) / len(eligible) if eligible else None
        strong = _bucket_metrics(
            [row for row in window_rows if row.get("proxy_label") == "strong_preclose_clv_proxy"],
            denominator=denominator,
            base_rate=window_base,
            forecast=PROXY_FORECASTS["strong_preclose_clv_proxy"],
        )
        windows.append(
            {
                "start_date": window_dates[0],
                "end_date": window_dates[-1],
                "slates": len(window_dates),
                "base_rate": round(window_base, 4) if window_base is not None else None,
                "strong_lift_vs_base_rate": strong["lift_vs_base_rate"],
                "strong_evaluated_rows": strong["evaluated_rows"],
            }
        )
    return windows


def _slice_value(row: dict[str, Any], name: str) -> str:
    inputs = _proxy_inputs(row)
    if name == "side":
        return str(row.get("side") or "unknown").strip().lower() or "unknown"
    if name == "price":
        return _price_label(row)
    if name == "k_line":
        return _line_label(row)
    if name == "timing":
        return str(inputs.get("bet_timing_window") or "unknown").strip().lower() or "unknown"
    if name == "quality":
        return str(inputs.get("quality_gate_level") or "unknown").strip().lower() or "unknown"
    if name == "path_b":
        return _path_b_label(row)
    if name == "workload":
        return _workload_label(row)
    if name == "provider":
        return _provider_label(row)
    if name == "agreement":
        return str(row.get("market_agreement_label") or _agreement_label(row))
    raise ValueError(f"unsupported CLV process slice: {name}")


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    deduplicated: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        slate_date = _slate_date(row)
        display_pitcher = str(row.get("display_pitcher") or row.get("pitcher") or row.get("normalized_pitcher") or "").strip()
        normalized_pitcher = _normalized_pitcher(row)
        side = str(row.get("side") or "").strip().lower()
        key = (slate_date, normalized_pitcher, side)
        if key in deduplicated:
            continue
        summarized = {**row}
        summarized["slate_date"] = slate_date
        summarized["normalized_pitcher"] = normalized_pitcher
        summarized["display_pitcher"] = display_pitcher
        summarized["preclose_proxy_inputs"] = _proxy_inputs(summarized)
        summarized["proxy_label"] = classify_proxy(summarized)
        summarized["market_agreement_label"] = _agreement_label(summarized)
        summarized["target_bucket"] = _target_bucket(summarized)
        summarized["provider_era"] = _provider_era(summarized)
        summarized["proxy_selector_inputs"] = {
            "lock_provider": summarized.get("lock_provider"),
            "lock_book": summarized.get("lock_book"),
            "lock_line": summarized.get("lock_line"),
            "lock_odds": summarized.get("lock_odds"),
            "lock_observed_at": summarized.get("lock_observed_at"),
        }
        deduplicated[key] = summarized

    target_rows = list(deduplicated.values())
    eligible_rows = [row for row in target_rows if _target_bucket(row) != "unknown"]
    base_rate = (
        round(sum(1 for row in eligible_rows if _target_bucket(row) == "beat") / len(eligible_rows), 4)
        if eligible_rows
        else None
    )
    proxy_buckets = {
        label: _bucket_metrics(
            [row for row in target_rows if row["proxy_label"] == label],
            denominator=len(target_rows),
            base_rate=base_rate,
            forecast=PROXY_FORECASTS[label],
        )
        for label in PROXY_LABELS
    }
    agreement_names = sorted({row["market_agreement_label"] for row in target_rows} | set(AGREEMENT_FORECASTS))
    agreement_buckets = {
        label: _bucket_metrics(
            [row for row in target_rows if row["market_agreement_label"] == label],
            denominator=len(target_rows),
            base_rate=base_rate,
            forecast=AGREEMENT_FORECASTS.get(label),
        )
        for label in agreement_names
    }
    provider_eras = sorted({row["provider_era"] for row in target_rows})
    provider_era_drift = {
        era: _bucket_metrics(
            [row for row in target_rows if row["provider_era"] == era],
            denominator=len(target_rows),
            base_rate=base_rate,
            forecast=None,
        )
        for era in provider_eras
    }
    slice_names = ("side", "price", "k_line", "timing", "quality", "path_b", "workload", "provider", "agreement")
    slices: dict[str, dict[str, dict[str, Any]]] = {}
    for name in slice_names:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in target_rows:
            grouped[_slice_value(row, name)].append(row)
        slices[name] = {
            value: _bucket_metrics(bucket_rows, denominator=len(target_rows), base_rate=base_rate, forecast=None)
            for value, bucket_rows in sorted(grouped.items())
        }
    all_era_rolling_windows = _rolling_14_slate_windows(target_rows, base_rate)
    slices["rolling_14_slates"] = {
        f"{window['start_date']}..{window['end_date']}": window
        for window in all_era_rolling_windows
    }
    pnl_crosstab: dict[str, dict[str, dict[str, Any]]] = {}
    for label in PROXY_LABELS:
        label_rows = [row for row in target_rows if row["proxy_label"] == label]
        pnl_crosstab[label] = {
            target: _bucket_metrics(
                [row for row in label_rows if _target_bucket(row) == target],
                denominator=len(target_rows),
                base_rate=base_rate,
                forecast=None,
            )
            for target in ("beat", "neutral", "worse", "unknown")
    }
    fully_attributed_current = [row for row in target_rows if _is_fully_attributed_current_provider(row)]
    readiness_rolling_windows = _rolling_14_slate_windows(fully_attributed_current, base_rate)
    all_era_positive_windows = [
        window
        for window in all_era_rolling_windows
        if window["slates"] == 14
        and window["strong_evaluated_rows"] > 0
        and (window["strong_lift_vs_base_rate"] or 0.0) > 0
    ]
    positive_windows = [
        window
        for window in readiness_rolling_windows
        if window["slates"] == 14
        and window["strong_evaluated_rows"] > 0
        and (window["strong_lift_vs_base_rate"] or 0.0) > 0
    ]
    readiness_status = (
        "ready_for_proxy_design"
        if len(fully_attributed_current) >= 100 and len(positive_windows) >= 2
        else "keep_as_process_kpi"
    )
    return {
        "input_rows": len(rows),
        "duplicate_rows": len(rows) - len(target_rows),
        "rows": target_rows,
        "final_clv_counts": dict(sorted(Counter(str(row.get("final_clv") or "unknown") for row in target_rows).items())),
        "eligible_target_rows": len(eligible_rows),
        "unknown_target_rows": len(target_rows) - len(eligible_rows),
        "base_beat_rate": base_rate,
        "proxy_buckets": proxy_buckets,
        "agreement_buckets": agreement_buckets,
        "provider_era_drift": provider_era_drift,
        "pnl_crosstab": pnl_crosstab,
        "slices": slices,
        "readiness": {
            "current_provider_start": CURRENT_PROVIDER_START,
            "fully_attributed_current_provider_targets": len(fully_attributed_current),
            "minimum_current_provider_targets": 100,
            "all_era_rolling_14_slate_windows": all_era_rolling_windows,
            "all_era_positive_proxy_lift_windows": len(all_era_positive_windows),
            "readiness_rolling_14_slate_windows": readiness_rolling_windows,
            "rolling_14_slate_windows": readiness_rolling_windows,
            "positive_proxy_lift_windows": len(positive_windows),
            "minimum_positive_windows": 2,
            "status": readiness_status,
        },
    }


def render_report(summary: dict[str, Any]) -> str:
    counts = summary.get("final_clv_counts") or {}
    lines = [
        "# CLV Process Target Validation",
        "",
        "This is an offline process target. It does not create a selector, verdict, or pick action.",
        "",
        "`evidence_clv_supported` (277 rows, 155-122, +19.01u, +6.9%) is a process benchmark only.",
        "The most recent 30 rows were -4.64u, so this report makes no performance claim from CLV support.",
        "Final CLV, closing price/line, results, actual Ks, and actual workload remain outcome fields, never proxy-selector inputs.",
        "",
        "## Coverage",
        "",
        f"- Input rows: `{summary.get('input_rows', 0)}`",
        f"- Deduplicated target rows: `{len(summary.get('rows') or [])}`",
        f"- Duplicate rows removed: `{summary.get('duplicate_rows', 0)}`",
        f"- Fully attributed eligible targets: `{summary.get('eligible_target_rows', 0)}`",
        f"- Unknown/missing-close targets: `{summary.get('unknown_target_rows', 0)}`",
        f"- Base beat-close rate: `{summary.get('base_beat_rate') if summary.get('base_beat_rate') is not None else '--'}`",
        "",
        "## Final CLV Labels",
        "",
    ]
    if counts:
        lines.extend(f"- `{label}`: `{count}`" for label, count in sorted(counts.items()))
    else:
        lines.append("- No target rows")
    lines.extend(
        [
            "",
            "## Live-Safe Proxy Validation",
            "",
            "| Proxy bucket | Evaluated | Coverage | Beat/Neutral/Worse | Precision | Lift vs base | Brier-style |",
            "| --- | ---: | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for label in PROXY_LABELS:
        bucket = (summary.get("proxy_buckets") or {}).get(label, {})
        counts = bucket.get("target_counts") or {}
        lines.append(
            f"| `{label}` | {bucket.get('evaluated_rows', 0)} | {bucket.get('coverage', 0.0):.1%} | "
            f"{counts.get('beat', 0)}/{counts.get('neutral', 0)}/{counts.get('worse', 0)} | "
            f"{_format_rate(bucket.get('precision'))} | {_format_rate(bucket.get('lift_vs_base_rate'))} | "
            f"{_format_number(bucket.get('brier_style_score'))} |"
        )
    lines.extend(["", "## Market-Agreement Validation", "", "| Agreement bucket | Evaluated | Precision | Lift vs base | Brier-style |", "| --- | ---: | ---: | ---: | ---: |"])
    for label, bucket in sorted((summary.get("agreement_buckets") or {}).items()):
        lines.append(
            f"| `{label}` | {bucket.get('evaluated_rows', 0)} | {_format_rate(bucket.get('precision'))} | "
            f"{_format_rate(bucket.get('lift_vs_base_rate'))} | {_format_number(bucket.get('brier_style_score'))} |"
        )
    lines.extend(["", "## Provider-Era Drift", "", "| Era | Evaluated | Precision | Lift vs all-target base |", "| --- | ---: | ---: | ---: |"])
    for era, bucket in sorted((summary.get("provider_era_drift") or {}).items()):
        lines.append(
            f"| `{era}` | {bucket.get('evaluated_rows', 0)} | {_format_rate(bucket.get('precision'))} | "
            f"{_format_rate(bucket.get('lift_vs_base_rate'))} |"
        )
    lines.extend(["", "## Descriptive PnL Cross-Tab", "", "| Proxy bucket | Final CLV bucket | PnL rows | PnL | ROI |", "| --- | --- | ---: | ---: | ---: |"])
    for label, targets in (summary.get("pnl_crosstab") or {}).items():
        for target, bucket in targets.items():
            lines.append(
                f"| `{label}` | `{target}` | {bucket.get('pnl_rows', 0)} | "
                f"{float(bucket.get('pnl', 0.0)):+.2f} | {_format_rate(bucket.get('roi'))} |"
            )
    readiness = summary.get("readiness") or {}
    lines.extend(
        [
            "",
            "## Readiness",
            "",
            f"- Status: `{readiness.get('status', 'keep_as_process_kpi')}`",
            f"- Fully attributed current-provider targets since `{readiness.get('current_provider_start', CURRENT_PROVIDER_START)}`: `{readiness.get('fully_attributed_current_provider_targets', 0)}` / `{readiness.get('minimum_current_provider_targets', 100)}`.",
            f"- Current-provider readiness windows: `{len(readiness.get('readiness_rolling_14_slate_windows') or [])}`; positive strong-proxy lift windows: `{readiness.get('positive_proxy_lift_windows', 0)}` / `{readiness.get('minimum_positive_windows', 2)}` consecutive 14-slate windows.",
            f"- All-era descriptive windows: `{len(readiness.get('all_era_rolling_14_slate_windows') or [])}`; positive all-era windows: `{readiness.get('all_era_positive_proxy_lift_windows', 0)}`. These cannot satisfy readiness.",
            "- Brier-style scoring uses fixed ordinal pre-close forecasts (strong .75, medium .50, weak .25); it is a process calibration diagnostic, not a calibrated probability claim.",
            "- PnL is cross-tabbed with final CLV for context only; it is not causal proof of the other outcome.",
            "- Side, price, K-line, timing, quality, Path B, workload, provider, agreement, and rolling 14-slate slices are included in the JSON for review before any separate design plan.",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_rate(value: Any) -> str:
    number = _number(value)
    return "--" if number is None else f"{number:+.1%}"


def _format_number(value: Any) -> str:
    number = _number(value)
    return "--" if number is None else f"{number:.3f}"


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    if path.suffix.lower() == ".json":
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return [row for row in parsed if isinstance(row, dict)]
        if isinstance(parsed, dict):
            return [parsed]
        return []
    rows: list[dict[str, Any]] = []
    for line in content.splitlines():
        parsed = json.loads(line)
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build offline CLV process target rows.")
    parser.add_argument("--gate-c-input", type=Path, required=True)
    parser.add_argument("--close-evidence-input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    close_rows = load_close_evidence_packet(args.close_evidence_input)
    target_rows = [build_target_row(row, close_rows) for row in _load_json_rows(args.gate_c_input)]
    summary = build_summary(target_rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "clv_process_target_validation.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "clv_process_target_validation.md").write_text(render_report(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
