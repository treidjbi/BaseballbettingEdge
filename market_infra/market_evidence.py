from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from market_infra.provider_freshness import (
    effective_book_freshness,
    normalize_book_key,
    provider_heartbeat_health,
)
from pipeline.name_utils import normalize


MARKET_EVIDENCE_PROVIDERS = {"propline", "boltodds"}
TRACKED_VERDICTS = {"LEAN", "FIRE 1u", "FIRE 2u"}
DEFAULT_STALE_AFTER_SECONDS = 900


def _numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _matches_line(value: float, target: float) -> bool:
    return abs(value - target) < 0.001


def _parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _isoformat(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _line_market_direction(side: str, previous_line: float, current_line: float) -> str:
    if previous_line == current_line:
        return "neutral"
    if side == "over":
        return "toward_pick" if current_line > previous_line else "away_from_pick"
    return "toward_pick" if current_line < previous_line else "away_from_pick"


def _line_bet_value_direction(side: str, previous_line: float, current_line: float) -> str:
    if previous_line == current_line:
        return "neutral"
    if side == "over":
        return "better_now" if current_line < previous_line else "worse_now"
    return "better_now" if current_line > previous_line else "worse_now"


def _odds_market_direction(odds_delta: int) -> str:
    if odds_delta == 0:
        return "neutral"
    return "away_from_pick" if odds_delta > 0 else "toward_pick"


def _odds_bet_value_direction(odds_delta: int) -> str:
    if odds_delta == 0:
        return "neutral"
    return "better_now" if odds_delta > 0 else "worse_now"


def _direction_summary(
    *,
    side: str,
    first_line: float,
    current_line: float,
    first_odds: int,
    current_odds: int,
) -> tuple[str, str]:
    if not _matches_line(first_line, current_line):
        return (
            _line_market_direction(side, first_line, current_line),
            _line_bet_value_direction(side, first_line, current_line),
        )

    odds_delta = current_odds - first_odds
    return _odds_market_direction(odds_delta), _odds_bet_value_direction(odds_delta)


def _market_reversal_count(side: str, ordered: list[dict[str, Any]]) -> int:
    directions: list[str] = []
    for previous, current in zip(ordered, ordered[1:]):
        market_direction, _ = _direction_summary(
            side=side,
            first_line=float(previous["line"]),
            current_line=float(current["line"]),
            first_odds=int(previous["american_odds"]),
            current_odds=int(current["american_odds"]),
        )
        if market_direction != "neutral":
            directions.append(market_direction)

    if len(directions) < 2:
        return 0
    return sum(
        1
        for previous_direction, current_direction in zip(directions, directions[1:])
        if previous_direction != current_direction
    )


def _consensus(
    *,
    positive_count: int,
    negative_count: int,
    positive_label: str,
    negative_label: str,
) -> str:
    if positive_count and negative_count:
        return "mixed"
    if positive_count:
        return positive_label
    if negative_count:
        return negative_label
    return "none"


def _time_window(observed_at: datetime, game_time: Any) -> tuple[int | None, str]:
    game_time_dt = _parse_datetime(game_time)
    if game_time_dt is None:
        return None, "unknown"

    minutes_to_game = int(round((game_time_dt - observed_at).total_seconds() / 60))
    if minutes_to_game < 0:
        return minutes_to_game, "post_start"
    if minutes_to_game <= 5:
        return minutes_to_game, "pre_5"
    if minutes_to_game <= 15:
        return minutes_to_game, "pre_15"
    if minutes_to_game <= 30:
        return minutes_to_game, "pre_30"
    if minutes_to_game <= 60:
        return minutes_to_game, "pre_60"
    if minutes_to_game <= 120:
        return minutes_to_game, "pre_120"
    return minutes_to_game, "early"


def _group_snapshots(
    snapshot_rows: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str, str], dict[str, list[dict[str, Any]]]] = {}
    for snapshot in snapshot_rows:
        provider = str(snapshot.get("provider") or "").strip().lower()
        if provider not in MARKET_EVIDENCE_PROVIDERS:
            continue
        normalized = str(
            snapshot.get("normalized_player_name") or normalize(snapshot.get("player_name") or "")
        ).strip()
        side = str(snapshot.get("side") or "").strip().lower()
        book = normalize_book_key(snapshot.get("bookmaker_key") or "")
        if not normalized or side not in {"over", "under"} or not book:
            continue
        grouped.setdefault((provider, normalized, side), {}).setdefault(book, []).append(snapshot)
    return grouped


def _book_summary(
    *,
    slate_date: str,
    provider: str,
    side: str,
    pick_line: float,
    book: str,
    snapshots: list[dict[str, Any]],
    observed_at: datetime,
    provider_health: dict[tuple[str, str], dict[str, Any]],
    stale_after_seconds: int,
) -> dict[str, Any] | None:
    valid_snapshots: list[dict[str, Any]] = []
    for snapshot in snapshots:
        line = _numeric(snapshot.get("line"))
        odds = _integer(snapshot.get("american_odds"))
        snapshot_time = _parse_datetime(snapshot.get("observed_at"))
        if line is None or odds is None or snapshot_time is None:
            continue
        valid_snapshots.append({
            **snapshot,
            "line": line,
            "american_odds": odds,
            "_observed_at_dt": snapshot_time,
        })

    if not valid_snapshots:
        return None

    ordered = sorted(valid_snapshots, key=lambda row: row["_observed_at_dt"])
    first = ordered[0]
    current = ordered[-1]
    first_line = float(first["line"])
    current_line = float(current["line"])
    first_odds = int(first["american_odds"])
    current_odds = int(current["american_odds"])
    market_direction, bet_value_direction = _direction_summary(
        side=side,
        first_line=first_line,
        current_line=current_line,
        first_odds=first_odds,
        current_odds=current_odds,
    )
    reversal_count = _market_reversal_count(side, ordered)
    line_freshness_seconds = max(int((observed_at - current["_observed_at_dt"]).total_seconds()), 0)
    freshness = effective_book_freshness(
        provider=provider,
        slate_date=slate_date,
        book_key=book,
        line_freshness_seconds=line_freshness_seconds,
        provider_health=provider_health,
        stale_after_seconds=stale_after_seconds,
    )

    return {
        "bookmaker_key": normalize_book_key(book),
        "snapshot_count": len(ordered),
        "first_snapshot_id": first.get("id"),
        "current_snapshot_id": current.get("id"),
        "first_observed_at": first.get("observed_at"),
        "current_observed_at": current.get("observed_at"),
        "first_line": first_line,
        "current_line": current_line,
        "line_delta": round(current_line - first_line, 3),
        "first_odds": first_odds,
        "current_odds": current_odds,
        "odds_delta": current_odds - first_odds,
        "market_direction": market_direction,
        "bet_value_direction": bet_value_direction,
        "reversal_count": reversal_count,
        "has_reversal": reversal_count > 0,
        "touches_pick_line": any(_matches_line(float(row["line"]), pick_line) for row in ordered),
        "freshness_seconds": freshness["freshness_seconds"],
        "line_freshness_seconds": freshness["line_freshness_seconds"],
        "freshness_status": (
            "fresh" if int(freshness["freshness_seconds"]) <= stale_after_seconds else "stale"
        ),
        "heartbeat_hold": freshness["heartbeat_hold"],
        "heartbeat_freshness_seconds": freshness["heartbeat_freshness_seconds"],
    }


def build_market_pick_evidence_rows(
    *,
    slate_date: str,
    live_picks: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    observed_at: datetime | str,
    source_artifact_path: str,
    source_artifact_sha256: str | None,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    provider_heartbeats: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    observed_at_dt = _parse_datetime(observed_at)
    if observed_at_dt is None:
        return []
    observed_at_iso = _isoformat(observed_at_dt)
    heartbeat_health = provider_heartbeat_health(
        provider_heartbeats or [],
        observed_at_dt,
        stale_after_seconds,
    )
    grouped_snapshots = _group_snapshots(snapshot_rows)
    rows: list[dict[str, Any]] = []

    for pick in live_picks:
        verdict = str(pick.get("current_verdict") or "PASS").strip()
        if verdict not in TRACKED_VERDICTS:
            continue

        pitcher_name = str(pick.get("pitcher") or "").strip()
        normalized_pitcher = str(pick.get("normalized_pitcher") or normalize(pitcher_name)).strip()
        side = str(pick.get("side") or "").strip().lower()
        pick_line = _numeric(pick.get("k_line"))
        if not normalized_pitcher or side not in {"over", "under"} or pick_line is None:
            continue

        minutes_to_game, time_window = _time_window(observed_at_dt, pick.get("game_time"))
        for provider in sorted(MARKET_EVIDENCE_PROVIDERS):
            book_groups = grouped_snapshots.get((provider, normalized_pitcher, side), {})
            if not book_groups:
                continue

            book_summaries = {
                book: summary
                for book, snapshots in sorted(book_groups.items())
                if (
                    summary := _book_summary(
                        slate_date=slate_date,
                        provider=provider,
                        side=side,
                        pick_line=pick_line,
                        book=book,
                        snapshots=snapshots,
                        observed_at=observed_at_dt,
                        provider_health=heartbeat_health,
                        stale_after_seconds=stale_after_seconds,
                    )
                )
                is not None
            }
            if not book_summaries:
                continue

            toward_pick_count = sum(
                1 for summary in book_summaries.values() if summary["market_direction"] == "toward_pick"
            )
            away_from_pick_count = sum(
                1 for summary in book_summaries.values() if summary["market_direction"] == "away_from_pick"
            )
            better_now_count = sum(
                1 for summary in book_summaries.values() if summary["bet_value_direction"] == "better_now"
            )
            worse_now_count = sum(
                1 for summary in book_summaries.values() if summary["bet_value_direction"] == "worse_now"
            )
            touching_pick_line_count = sum(
                1 for summary in book_summaries.values() if summary["touches_pick_line"]
            )
            reversal_book_count = sum(
                1 for summary in book_summaries.values() if int(summary.get("reversal_count") or 0) > 0
            )
            volatile_book_count = reversal_book_count
            latest_snapshot_at = max(
                str(summary["current_observed_at"]) for summary in book_summaries.values()
            )
            freshness_seconds = min(
                int(summary["freshness_seconds"]) for summary in book_summaries.values()
            )
            line_freshness_seconds = min(
                int(summary["line_freshness_seconds"]) for summary in book_summaries.values()
            )
            heartbeat_holds = [
                summary
                for summary in book_summaries.values()
                if summary.get("heartbeat_hold")
            ]
            heartbeat_freshness_seconds = [
                int(summary["heartbeat_freshness_seconds"])
                for summary in heartbeat_holds
                if summary.get("heartbeat_freshness_seconds") is not None
            ]
            snapshot_count = sum(int(summary["snapshot_count"]) for summary in book_summaries.values())
            books_seen = sorted(book_summaries)

            rows.append({
                "slate_date": slate_date,
                "pitcher": pitcher_name,
                "normalized_pitcher": normalized_pitcher,
                "side": side,
                "provider": provider,
                "current_verdict": verdict,
                "k_line": pick_line,
                "current_odds": pick.get("current_odds"),
                "current_book": pick.get("current_book"),
                "game_time": pick.get("game_time"),
                "game_state": pick.get("game_state"),
                "is_fire": bool(pick.get("is_fire")),
                "is_locked": bool(pick.get("is_locked")),
                "observed_at": observed_at_iso,
                "latest_snapshot_at": latest_snapshot_at,
                "snapshot_count": snapshot_count,
                "book_count": len(book_summaries),
                "books_seen": books_seen,
                "toward_pick_count": toward_pick_count,
                "away_from_pick_count": away_from_pick_count,
                "better_now_count": better_now_count,
                "worse_now_count": worse_now_count,
                "touching_pick_line_count": touching_pick_line_count,
                "reversal_book_count": reversal_book_count,
                "volatile_book_count": volatile_book_count,
                "market_consensus": _consensus(
                    positive_count=toward_pick_count,
                    negative_count=away_from_pick_count,
                    positive_label="toward_pick",
                    negative_label="away_from_pick",
                ),
                "bet_value_consensus": _consensus(
                    positive_count=better_now_count,
                    negative_count=worse_now_count,
                    positive_label="better_now",
                    negative_label="worse_now",
                ),
                "minutes_to_game": minutes_to_game,
                "time_window": time_window,
                "source_artifact_path": source_artifact_path,
                "source_artifact_sha256": source_artifact_sha256,
                "dedupe_key": f"{slate_date}:market_evidence:{provider}:{normalized_pitcher}:{side}",
                "metadata": {
                    "book_summaries": book_summaries,
                    "tracked_verdict": verdict,
                    "stale_after_seconds": stale_after_seconds,
                    "freshness_seconds": freshness_seconds,
                    "line_freshness_seconds": line_freshness_seconds,
                    "freshness_status": (
                        "fresh" if freshness_seconds <= stale_after_seconds else "stale"
                    ),
                    "heartbeat_hold": bool(heartbeat_holds),
                    "heartbeat_hold_books": sorted(
                        summary["bookmaker_key"] for summary in heartbeat_holds
                    ),
                    "heartbeat_freshness_seconds": (
                        min(heartbeat_freshness_seconds) if heartbeat_freshness_seconds else None
                    ),
                },
            })

    return rows
