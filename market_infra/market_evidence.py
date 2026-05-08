from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pipeline.name_utils import normalize


MARKET_EVIDENCE_PROVIDERS = {"propline", "boltodds"}
TRACKED_VERDICTS = {"LEAN", "FIRE 1u", "FIRE 2u"}


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
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
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
        book = str(snapshot.get("bookmaker_key") or "").strip().lower()
        if not normalized or side not in {"over", "under"} or not book:
            continue
        grouped.setdefault((provider, normalized, side), {}).setdefault(book, []).append(snapshot)
    return grouped


def _book_summary(
    *,
    side: str,
    pick_line: float,
    book: str,
    snapshots: list[dict[str, Any]],
) -> dict[str, Any] | None:
    valid_snapshots: list[dict[str, Any]] = []
    for snapshot in snapshots:
        line = _numeric(snapshot.get("line"))
        odds = _integer(snapshot.get("american_odds"))
        if line is None or odds is None or not snapshot.get("observed_at"):
            continue
        valid_snapshots.append({**snapshot, "line": line, "american_odds": odds})

    if not valid_snapshots:
        return None

    ordered = sorted(valid_snapshots, key=lambda row: str(row.get("observed_at") or ""))
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

    return {
        "bookmaker_key": book,
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
        "touches_pick_line": any(_matches_line(float(row["line"]), pick_line) for row in ordered),
    }


def build_market_pick_evidence_rows(
    *,
    slate_date: str,
    live_picks: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    observed_at: datetime | str,
    source_artifact_path: str,
    source_artifact_sha256: str | None,
) -> list[dict[str, Any]]:
    observed_at_dt = _parse_datetime(observed_at)
    if observed_at_dt is None:
        return []
    observed_at_iso = _isoformat(observed_at_dt)
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
                        side=side,
                        pick_line=pick_line,
                        book=book,
                        snapshots=snapshots,
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
            latest_snapshot_at = max(
                str(summary["current_observed_at"]) for summary in book_summaries.values()
            )
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
                },
            })

    return rows
