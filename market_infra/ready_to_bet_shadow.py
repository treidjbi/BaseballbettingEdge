from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pipeline.name_utils import normalize


ACTIVE_PROVIDERS = {"therundown_propline", "therundown", "propline"}
PROVIDER_RANK = {"therundown_propline": 3, "therundown": 2, "propline": 1}
FRESH_STATUSES = {"fresh", "held_fresh", "heartbeat_held"}
SUPPORTED_BOOKS = {
    "fanduel",
    "draftkings",
    "betmgm",
    "betrivers",
    "caesars",
    "kalshi",
    "thescore",
}
BOOK_ALIASES = {"scorebet": "thescore", "thescorebet": "thescore"}
STARTED_STATES = {"in_progress", "final", "completed"}
LOCKED_STATES = {"locked", "postponed"}


@dataclass(frozen=True)
class ReadyToBetResult:
    state_rows: list[dict[str, Any]]
    candidate_rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_key(row: dict[str, Any]) -> tuple[str, str] | None:
    normalized_pitcher = str(
        row.get("normalized_pitcher") or normalize(str(row.get("pitcher") or ""))
    ).strip()
    side = str(row.get("side") or "").strip().lower()
    if not normalized_pitcher or side not in {"over", "under"}:
        return None
    return normalized_pitcher, side


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return value if isinstance(value, dict) else {}


def _quality_level(pitcher: dict[str, Any], side: str) -> str:
    side_data = pitcher.get(f"ev_{side}")
    if not isinstance(side_data, dict):
        side_data = {}
    return str(
        side_data.get("quality_gate_level")
        or pitcher.get("quality_gate_level")
        or "missing"
    ).strip().lower()


def _book_key(value: Any) -> str:
    normalized = "".join(
        character for character in str(value or "").casefold() if character.isalnum()
    )
    return BOOK_ALIASES.get(normalized, normalized)


def _same_line_market(row: dict[str, Any], target_line: float) -> bool:
    provider = str(row.get("provider") or "").strip().lower()
    freshness = str(row.get("freshness_status") or "").strip().lower()
    best_book = _book_key(row.get("best_book"))
    best_line = _numeric(row.get("best_line"))
    return (
        provider in ACTIVE_PROVIDERS
        and freshness in FRESH_STATUSES
        and best_line is not None
        and abs(best_line - target_line) < 0.001
        and best_book in SUPPORTED_BOOKS
        and _numeric(row.get("best_odds")) is not None
    )


def _preferred_market(
    rows: list[dict[str, Any]], target_line: float
) -> dict[str, Any] | None:
    candidates = [row for row in rows if _same_line_market(row, target_line)]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            PROVIDER_RANK.get(str(row.get("provider") or "").lower(), 0),
            str(row.get("observed_at") or ""),
        ),
    )


def _minutes_and_window(
    game_time: Any, observed_at: datetime
) -> tuple[int | None, str]:
    parsed = _parse_datetime(game_time)
    if parsed is None:
        return None, "unknown"
    minutes = int(round((parsed - observed_at).total_seconds() / 60.0))
    if minutes <= 0:
        return minutes, "post_start"
    if minutes <= 5:
        return minutes, "pre_5"
    if minutes <= 15:
        return minutes, "pre_15"
    if minutes <= 30:
        return minutes, "pre_30"
    if minutes <= 60:
        return minutes, "pre_60"
    if minutes <= 120:
        return minutes, "pre_120"
    return minutes, "early"


def _notification_types(
    notification_rows: list[dict[str, Any]], key: tuple[str, str]
) -> list[str]:
    values = set()
    for row in notification_rows:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        row_key = _row_key({**row, **payload})
        if row_key == key:
            values.add(str(row.get("event_type") or ""))
    return sorted(value for value in values if value)


def build_ready_to_bet_shadow(
    *,
    slate_date: str,
    pitchers: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
    previous_state_rows: list[dict[str, Any]],
    live_market_rows: list[dict[str, Any]],
    accepted_bets: list[dict[str, Any]],
    accepted_bets_available: bool,
    notification_rows: list[dict[str, Any]],
    observed_at: datetime | str,
    mode: str,
) -> ReadyToBetResult:
    normalized_mode = str(mode or "off").strip().lower()
    if normalized_mode != "record":
        return ReadyToBetResult(
            state_rows,
            [],
            {"mode": "off", "state_counts": {}, "candidate_count": 0},
        )

    observed = _parse_datetime(observed_at)
    if observed is None:
        raise ValueError("observed_at must be parseable")

    pitchers_by_name = {
        normalize(str(row.get("pitcher") or "")): row
        for row in pitchers
        if str(row.get("pitcher") or "").strip()
    }
    previous_by_key = {
        key: row for row in previous_state_rows if (key := _row_key(row))
    }
    market_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in live_market_rows:
        key = _row_key(row)
        if key:
            market_by_key.setdefault(key, []).append(row)
    accepted_keys = {key for row in accepted_bets if (key := _row_key(row))}

    state_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    output_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for source in state_rows:
        row = dict(source)
        key = _row_key(row)
        if key is None:
            output_rows.append(row)
            continue
        normalized_pitcher, side = key
        pitcher = pitchers_by_name.get(normalized_pitcher, {})
        game_state = str(
            row.get("game_state") or pitcher.get("game_state") or ""
        ).strip().lower()
        game_time = _parse_datetime(row.get("game_time") or pitcher.get("game_time"))
        timestamp_started = game_time is not None and observed >= game_time
        target_line = _numeric(row.get("k_line"))
        market = (
            None
            if target_line is None
            else _preferred_market(market_by_key.get(key, []), target_line)
        )
        quality_level = _quality_level(pitcher, side)
        reasons: list[str] = []

        if game_state in STARTED_STATES:
            decision_state = "started"
            reasons.append("game_started")
        elif game_state in LOCKED_STATES:
            decision_state = "locked"
            reasons.append("pick_locked")
        elif game_time is None:
            decision_state = "watching"
            reasons.append("game_time_unavailable")
        elif timestamp_started:
            decision_state = "started"
            reasons.append("game_started")
        elif bool(row.get("is_locked")):
            decision_state = "locked"
            reasons.append("pick_locked")
        elif accepted_bets_available and key in accepted_keys:
            decision_state = "logged"
            reasons.append("accepted_bet_logged")
        else:
            if not accepted_bets_available:
                reasons.append("accepted_bet_state_unavailable")
            if not str(row.get("current_verdict") or "").startswith("FIRE"):
                reasons.append("not_fire")
            if quality_level != "clean":
                reasons.append("quality_not_clean")
            if market is None:
                reasons.append("same_line_market_unavailable")
            decision_state = "ready" if not reasons else "watching"

        state_counts[decision_state] += 1
        reason_counts.update(reasons)
        metadata = dict(_metadata(row))
        metadata.update(
            {
                "decision_state": decision_state,
                "decision_reasons": reasons,
                "decision_state_observed_at": observed.isoformat(),
                "ready_to_bet_shadow_mode": normalized_mode,
            }
        )
        row["metadata"] = metadata
        output_rows.append(row)

        previous_state = str(
            _metadata(previous_by_key.get(key, {})).get("decision_state") or ""
        )
        if decision_state != "ready" or previous_state == "ready" or market is None:
            continue

        minutes_to_game, time_window = _minutes_and_window(
            row.get("game_time") or pitcher.get("game_time"), observed
        )
        books_seen = sorted(
            str(book).strip().lower()
            for book in market.get("books_seen") or []
            if str(book).strip()
        )
        candidate_rows.append(
            {
                "slate_date": slate_date,
                "pitcher": row.get("pitcher"),
                "normalized_pitcher": normalized_pitcher,
                "side": side,
                "provider": market.get("provider"),
                "current_verdict": row.get("current_verdict"),
                "k_line": target_line,
                "candidate_type": "ready_to_bet",
                "candidate_action": "would_send_shadow",
                "playable_state": "playable_now",
                "market_consensus": (
                    market.get("market_consensus")
                    if market.get("market_consensus")
                    in {"toward_pick", "away_from_pick", "mixed", "none"}
                    else "none"
                ),
                "bet_value_consensus": (
                    market.get("bet_value_consensus")
                    if market.get("bet_value_consensus")
                    in {"better_now", "worse_now", "mixed", "none"}
                    else "none"
                ),
                "time_window": time_window,
                "minutes_to_game": minutes_to_game,
                "book_count": int(market.get("book_count") or len(books_seen)),
                "books_seen": books_seen,
                "broad_confirmation": market.get("broad_confirmation") is True,
                "single_book": len(books_seen) == 1,
                "betrivers_only": books_seen == ["betrivers"],
                "reversal_book_count": 0,
                "volatile_book_count": 0,
                "suppression_reasons": [],
                "evidence_dedupe_key": market.get("dedupe_key"),
                "occurred_at": observed.isoformat(),
                "dedupe_key": (
                    f"{slate_date}:ready_to_bet:{normalized_pitcher}:{side}"
                ),
                "metadata": {
                    "decision_state": "ready",
                    "previous_decision_state": previous_state or None,
                    "quality_gate_level": quality_level,
                    "best_book": market.get("best_book"),
                    "best_line": market.get("best_line"),
                    "best_odds": market.get("best_odds"),
                    "freshness_status": market.get("freshness_status"),
                    "same_run_notification_types": _notification_types(
                        notification_rows, key
                    ),
                },
            }
        )

    return ReadyToBetResult(
        state_rows=output_rows,
        candidate_rows=candidate_rows,
        summary={
            "mode": normalized_mode,
            "state_counts": dict(sorted(state_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
            "candidate_count": len(candidate_rows),
            "accepted_bets_available": accepted_bets_available,
        },
    )
