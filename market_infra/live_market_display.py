from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from statistics import median
from typing import Any

from market_infra.provider_freshness import (
    effective_book_freshness,
    normalize_book_key,
    provider_heartbeat_health,
)
from pipeline.name_utils import normalize


MAIN_BOOKS = ("fanduel", "draftkings", "betmgm", "betrivers", "caesars")
TRACKED_VERDICTS = {"LEAN", "FIRE 1u", "FIRE 2u"}
OFF_MARKET_ODDS_CENTS = 10
DEFAULT_STALE_AFTER_SECONDS = 900


def _book(value: Any) -> str:
    return normalize_book_key(value)


def _numeric(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _consensus(
    *,
    values: list[str],
    positive_label: str,
    negative_label: str,
) -> str:
    counts = Counter(value for value in values if value != "neutral")
    if counts[positive_label] >= 2 and counts[negative_label] >= 2:
        return "mixed"
    if counts[positive_label] >= 2:
        return positive_label
    if counts[negative_label] >= 2:
        return negative_label
    if counts[positive_label] and counts[negative_label]:
        return "mixed"
    return "none"


def _market_status(market_consensus: str, bet_value_consensus: str) -> str:
    if market_consensus == "toward_pick" and bet_value_consensus == "worse_now":
        return "market_confirmed_worse_number"
    if market_consensus == "toward_pick":
        return "market_confirmed_playable"
    if market_consensus == "away_from_pick" and bet_value_consensus == "better_now":
        return "better_number_market_fade"
    if market_consensus == "mixed" or bet_value_consensus == "mixed":
        return "mixed_market"
    return "no_clear_signal"


def _is_better_line(side: str, candidate_line: float, reference_line: float) -> bool:
    if side == "over":
        return candidate_line < reference_line
    return candidate_line > reference_line


def _is_playable_line(side: str, candidate_line: float, pick_line: float) -> bool:
    return candidate_line == pick_line or _is_better_line(side, candidate_line, pick_line)


def _line_rank(side: str, line: float) -> float:
    return line if side == "over" else -line


def _book_row(
    *,
    slate_date: str,
    provider: str,
    side: str,
    book: str,
    snapshots: list[dict[str, Any]],
    observed_at: datetime,
    provider_health: dict[tuple[str, str], dict[str, Any]],
    stale_after_seconds: int,
) -> dict[str, Any] | None:
    valid: list[dict[str, Any]] = []
    for snapshot in snapshots:
        line = _numeric(snapshot.get("line"))
        odds = _integer(snapshot.get("american_odds"))
        snapshot_time = _parse_datetime(snapshot.get("observed_at"))
        if line is None or odds is None or snapshot_time is None:
            continue
        valid.append({
            **snapshot,
            "bookmaker_key": book,
            "line": line,
            "american_odds": odds,
            "_observed_at_dt": snapshot_time,
        })
    if not valid:
        return None

    ordered = sorted(valid, key=lambda row: row["_observed_at_dt"])
    first = ordered[0]
    current = ordered[-1]
    line_delta = round(float(current["line"]) - float(first["line"]), 3)
    odds_delta = int(current["american_odds"]) - int(first["american_odds"])
    if line_delta:
        market_direction = _line_market_direction(side, first["line"], current["line"])
        bet_value_direction = _line_bet_value_direction(side, first["line"], current["line"])
    elif abs(odds_delta) < OFF_MARKET_ODDS_CENTS:
        market_direction = "neutral"
        bet_value_direction = "neutral"
    else:
        market_direction = _odds_market_direction(odds_delta)
        bet_value_direction = _odds_bet_value_direction(odds_delta)

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
        "book": book,
        "line": current["line"],
        "odds": current["american_odds"],
        "first_line": first["line"],
        "first_odds": first["american_odds"],
        "line_delta": line_delta,
        "odds_delta": odds_delta,
        "market_direction": market_direction,
        "bet_value_direction": bet_value_direction,
        "last_seen_at": _isoformat(current["_observed_at_dt"]),
        "freshness_seconds": freshness["freshness_seconds"],
        "line_freshness_seconds": freshness["line_freshness_seconds"],
        "heartbeat_hold": freshness["heartbeat_hold"],
        "heartbeat_freshness_seconds": freshness["heartbeat_freshness_seconds"],
        "snapshot_count": len(ordered),
    }


def _movement_events(
    *,
    side: str,
    book: str,
    snapshots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    valid = []
    for snapshot in snapshots:
        line = _numeric(snapshot.get("line"))
        odds = _integer(snapshot.get("american_odds"))
        snapshot_time = _parse_datetime(snapshot.get("observed_at"))
        if line is None or odds is None or snapshot_time is None:
            continue
        valid.append({**snapshot, "line": line, "american_odds": odds, "_observed_at_dt": snapshot_time})
    ordered = sorted(valid, key=lambda row: row["_observed_at_dt"])

    events: list[dict[str, Any]] = []
    for previous, current in zip(ordered, ordered[1:]):
        previous_line = float(previous["line"])
        current_line = float(current["line"])
        previous_odds = int(previous["american_odds"])
        current_odds = int(current["american_odds"])
        odds_delta = current_odds - previous_odds
        if previous_line != current_line:
            event_kind = "main_line_moved"
        elif abs(odds_delta) >= OFF_MARKET_ODDS_CENTS:
            event_kind = "price_moved"
        else:
            continue

        if previous_line != current_line:
            bet_value_direction = _line_bet_value_direction(side, previous_line, current_line)
        else:
            bet_value_direction = _odds_bet_value_direction(odds_delta)
        events.append({
            "observed_at": _isoformat(current["_observed_at_dt"]),
            "book": book,
            "event_kind": event_kind,
            "from_line": previous_line,
            "to_line": current_line,
            "from_odds": previous_odds,
            "to_odds": current_odds,
            "bet_value_direction": bet_value_direction,
        })
    return events


def _main_line(book_rows: list[dict[str, Any]]) -> tuple[float | None, list[str]]:
    if not book_rows:
        return None, []
    counts = Counter(row["line"] for row in book_rows)
    main_line, _ = counts.most_common(1)[0]
    books = sorted(row["book"] for row in book_rows if row["line"] == main_line)
    return float(main_line), books


def _off_market_books(
    *,
    side: str,
    main_line: float | None,
    book_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if main_line is None:
        return []
    same_line_odds = [row["odds"] for row in book_rows if row["line"] == main_line]
    consensus_odds = median(same_line_odds) if same_line_odds else None
    rows: list[dict[str, Any]] = []
    for row in book_rows:
        reason = ""
        if _is_better_line(side, float(row["line"]), main_line):
            reason = "better_line"
        elif (
            consensus_odds is not None
            and row["line"] == main_line
            and int(row["odds"]) >= int(consensus_odds) + OFF_MARKET_ODDS_CENTS
        ):
            reason = "better_price"
        if reason:
            rows.append({
                "book": row["book"],
                "line": row["line"],
                "odds": row["odds"],
                "reason": reason,
            })
    return sorted(rows, key=lambda row: (_line_rank(side, float(row["line"])), -int(row["odds"])))


def _best_actionable(
    *,
    side: str,
    pick_line: float,
    book_rows: list[dict[str, Any]],
    freshness_status: str,
) -> dict[str, Any] | None:
    if freshness_status != "fresh":
        return None
    playable = [
        row for row in book_rows
        if _is_playable_line(side, float(row["line"]), pick_line)
    ]
    if not playable:
        return None
    selected = sorted(
        playable,
        key=lambda row: (_line_rank(side, float(row["line"])), -int(row["odds"])),
    )[0]
    return {
        "book": selected["book"],
        "line": selected["line"],
        "odds": selected["odds"],
    }


def _actionable_state(
    *,
    market_status: str,
    freshness_status: str,
    best_actionable: dict[str, Any] | None,
    best_is_off_market: bool,
) -> str:
    if freshness_status != "fresh":
        return "stale"
    if market_status == "market_confirmed_worse_number":
        return "playable_now" if best_actionable else "number_worse"
    if market_status == "better_number_market_fade":
        return "market_fade"
    if market_status == "mixed_market":
        return "mixed"
    if best_is_off_market:
        return "off_market"
    if best_actionable and market_status == "market_confirmed_playable":
        return "playable_now"
    return "monitor"


def _snapshot_groups(
    snapshot_rows: list[dict[str, Any]],
    provider: str,
) -> dict[tuple[str, str], dict[str, list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
    for snapshot in snapshot_rows:
        if str(snapshot.get("provider") or "").strip().lower() != provider:
            continue
        book = _book(snapshot.get("bookmaker_key") or snapshot.get("bookmaker_title"))
        if book not in MAIN_BOOKS:
            continue
        side = str(snapshot.get("side") or "").strip().lower()
        if side not in {"over", "under"}:
            continue
        normalized = str(
            snapshot.get("normalized_player_name")
            or normalize(snapshot.get("player_name") or "")
        ).strip()
        if not normalized:
            continue
        grouped.setdefault((normalized, side), {}).setdefault(book, []).append(snapshot)
    return grouped


def build_live_market_display_rows(
    *,
    slate_date: str,
    live_picks: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    observed_at: datetime | str,
    source_artifact_path: str,
    source_artifact_sha256: str | None,
    provider: str | None = None,
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
    providers = [provider.strip().lower()] if provider else sorted({
        str(row.get("provider") or "").strip().lower()
        for row in snapshot_rows
        if str(row.get("provider") or "").strip().lower() in {"propline", "boltodds"}
    })

    rows: list[dict[str, Any]] = []
    for provider_key in providers:
        grouped_snapshots = _snapshot_groups(snapshot_rows, provider_key)
        for pick in live_picks:
            verdict = str(pick.get("current_verdict") or "PASS").strip()
            if verdict not in TRACKED_VERDICTS:
                continue
            pitcher = str(pick.get("pitcher") or "").strip()
            normalized = str(pick.get("normalized_pitcher") or normalize(pitcher)).strip()
            side = str(pick.get("side") or "").strip().lower()
            pick_line = _numeric(pick.get("k_line"))
            if not normalized or side not in {"over", "under"} or pick_line is None:
                continue

            book_groups = grouped_snapshots.get((normalized, side), {})
            book_rows = [
                row
                for book, snapshots in sorted(book_groups.items())
                if (row := _book_row(
                    slate_date=slate_date,
                    provider=provider_key,
                    side=side,
                    book=book,
                    snapshots=snapshots,
                    observed_at=observed_at_dt,
                    provider_health=heartbeat_health,
                    stale_after_seconds=stale_after_seconds,
                )) is not None
            ]
            if not book_rows:
                continue

            latest_age = min(int(row["freshness_seconds"]) for row in book_rows)
            line_latest_age = min(int(row["line_freshness_seconds"]) for row in book_rows)
            heartbeat_holds = [row for row in book_rows if row.get("heartbeat_hold")]
            heartbeat_freshness_seconds = [
                int(row["heartbeat_freshness_seconds"])
                for row in heartbeat_holds
                if row.get("heartbeat_freshness_seconds") is not None
            ]
            freshness_status = "fresh" if latest_age <= stale_after_seconds else "stale"
            main_line, main_line_books = _main_line(book_rows)
            off_market_books = _off_market_books(
                side=side,
                main_line=main_line,
                book_rows=book_rows,
            )
            best_actionable = _best_actionable(
                side=side,
                pick_line=float(pick_line),
                book_rows=book_rows,
                freshness_status=freshness_status,
            )
            best_is_off_market = bool(
                best_actionable
                and any(
                    row["book"] == best_actionable["book"]
                    and row["line"] == best_actionable["line"]
                    and row["odds"] == best_actionable["odds"]
                    for row in off_market_books
                )
            )
            market_consensus = _consensus(
                values=[row["market_direction"] for row in book_rows],
                positive_label="toward_pick",
                negative_label="away_from_pick",
            )
            bet_value_consensus = _consensus(
                values=[row["bet_value_direction"] for row in book_rows],
                positive_label="better_now",
                negative_label="worse_now",
            )
            market_status = _market_status(market_consensus, bet_value_consensus)
            movement_events = []
            for book, snapshots in book_groups.items():
                movement_events.extend(_movement_events(side=side, book=book, snapshots=snapshots))
            movement_events = sorted(
                movement_events,
                key=lambda row: str(row.get("observed_at") or ""),
                reverse=True,
            )[:12]

            rows.append({
                "slate_date": slate_date,
                "pitcher": pitcher,
                "normalized_pitcher": normalized,
                "side": side,
                "provider": provider_key,
                "current_verdict": verdict,
                "k_line": pick_line,
                "current_odds": pick.get("current_odds"),
                "current_book": pick.get("current_book"),
                "game_time": pick.get("game_time"),
                "game_state": pick.get("game_state"),
                "is_fire": verdict.startswith("FIRE"),
                "is_locked": bool(pick.get("is_locked")),
                "observed_at": observed_at_iso,
                "market_status": market_status,
                "actionable_state": _actionable_state(
                    market_status=market_status,
                    freshness_status=freshness_status,
                    best_actionable=best_actionable,
                    best_is_off_market=best_is_off_market,
                ),
                "market_consensus": market_consensus,
                "bet_value_consensus": bet_value_consensus,
                "main_line": main_line,
                "main_line_books": main_line_books,
                "best_book": best_actionable["book"] if best_actionable else None,
                "best_line": best_actionable["line"] if best_actionable else None,
                "best_odds": best_actionable["odds"] if best_actionable else None,
                "best_is_off_market": best_is_off_market,
                "off_market_books": off_market_books,
                "book_count": len(book_rows),
                "books_seen": sorted(row["book"] for row in book_rows),
                "book_rows": book_rows,
                "movement_events": movement_events,
                "latest_snapshot_at": max(row["last_seen_at"] for row in book_rows),
                "freshness_seconds": latest_age,
                "freshness_status": freshness_status,
                "broad_confirmation": (
                    sum(1 for row in book_rows if row["market_direction"] == "toward_pick") >= 2
                ),
                "source_artifact_path": source_artifact_path,
                "source_artifact_sha256": source_artifact_sha256,
                "dedupe_key": f"{slate_date}:live_market_display:{provider_key}:{normalized}:{side}",
                "metadata": {
                    "stale_after_seconds": stale_after_seconds,
                    "main_books": list(MAIN_BOOKS),
                    "line_freshness_seconds": line_latest_age,
                    "heartbeat_hold": bool(heartbeat_holds),
                    "heartbeat_hold_books": sorted(row["book"] for row in heartbeat_holds),
                    "heartbeat_freshness_seconds": (
                        min(heartbeat_freshness_seconds) if heartbeat_freshness_seconds else None
                    ),
                },
                "updated_at": observed_at_iso,
            })

    return rows
