from __future__ import annotations

from datetime import datetime
from typing import Any

from pipeline.name_utils import normalize


VERDICT_RANK = {
    "PASS": 0,
    "LEAN": 1,
    "FIRE 1u": 2,
    "FIRE 2u": 3,
}

LOCKED_GAME_STATES = {"locked", "in_progress", "final", "completed", "postponed"}
PROPLINE_WEBHOOK_NOTIFICATION_BOOKS = {
    "betmgm",
    "betrivers",
    "caesars",
    "draftkings",
    "fanduel",
    "kalshi",
    "scorebet",
    "thescore",
}
MAX_LINE_MOVEMENT_NOTIFICATION_DELTA = 1.0


def _isoformat(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _is_fire(verdict: str | None) -> bool:
    return VERDICT_RANK.get(verdict or "PASS", 0) >= VERDICT_RANK["FIRE 1u"]


def _is_locked(pitcher: dict[str, Any]) -> bool:
    game_state = str(pitcher.get("game_state") or "").strip().lower()
    return bool(pitcher.get("locked_at")) or game_state in LOCKED_GAME_STATES


def _is_locked_state_row(row: dict[str, Any]) -> bool:
    game_state = str(row.get("game_state") or "").strip().lower()
    return bool(row.get("is_locked")) or bool(row.get("locked_at")) or game_state in LOCKED_GAME_STATES


def _k_line(value: Any) -> float | None:
    try:
        line = float(value)
    except (TypeError, ValueError):
        return None
    return line


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


def _snapshot_movement_key(snapshot: dict[str, Any]) -> tuple[str, str, str, str] | None:
    provider_event_id = str(snapshot.get("provider_event_id") or "").strip()
    book = str(snapshot.get("bookmaker_key") or "").strip()
    normalized = str(
        snapshot.get("normalized_player_name")
        or normalize(snapshot.get("player_name") or "")
    ).strip()
    side = str(snapshot.get("side") or "").strip().lower()
    if provider_event_id and book and normalized and side in {"over", "under"}:
        return provider_event_id, book, normalized, side
    return None


def _format_odds(value: int) -> str:
    return f"{value:+d}"


def _movement_body(
    *,
    pitcher_name: str,
    side: str,
    movement_kind: str,
    previous_line: float,
    current_line: float,
    previous_odds: int,
    current_odds: int,
    book: str,
    market_direction: str,
    bet_value_direction: str,
) -> str:
    side_label = side.upper()
    market_label = "market toward pick" if market_direction == "toward_pick" else "market away from pick"
    value_label = "better" if bet_value_direction == "better_now" else "worse"
    if movement_kind == "odds":
        return (
            f"{pitcher_name} {side_label} {current_line:g} odds "
            f"{_format_odds(previous_odds)}->{_format_odds(current_odds)} at {book}; "
            f"{market_label}, price {value_label}"
        )
    return (
        f"{pitcher_name} {side_label} {previous_line:g}->{current_line:g} at {book}; "
        f"{market_label}, current line {value_label}"
    )


def _line_bet_value_direction(side: str, previous_line: float, current_line: float) -> str:
    if side == "over":
        return "better_now" if current_line < previous_line else "worse_now"
    return "better_now" if current_line > previous_line else "worse_now"


def _line_market_direction(side: str, previous_line: float, current_line: float) -> str:
    if side == "over":
        return "toward_pick" if current_line > previous_line else "away_from_pick"
    return "toward_pick" if current_line < previous_line else "away_from_pick"


def _odds_bet_value_direction(odds_delta: int) -> str:
    return "better_now" if odds_delta > 0 else "worse_now"


def _odds_market_direction(odds_delta: int) -> str:
    return "away_from_pick" if odds_delta > 0 else "toward_pick"


def _parse_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _is_post_start_pick(pick: dict[str, Any], observed_at: Any) -> bool:
    game_time = pick.get("game_time")
    if not game_time or not observed_at:
        return False
    try:
        return _parse_datetime(observed_at) >= _parse_datetime(game_time)
    except (TypeError, ValueError):
        return False


def _reminder_dedupe_keys(existing_reminders: Any) -> set[str]:
    keys: set[str] = set()
    for reminder in existing_reminders or []:
        if isinstance(reminder, dict):
            key = reminder.get("dedupe_key")
            if key:
                keys.add(str(key))
        else:
            keys.add(str(reminder))
    return keys


def _previous_row(
    previous_state: dict[Any, Any],
    *,
    slate_date: str,
    normalized_pitcher: str,
    side: str,
) -> dict[str, Any] | None:
    tuple_key = (slate_date, normalized_pitcher, side)
    if tuple_key in previous_state:
        row = previous_state[tuple_key]
        return row if isinstance(row, dict) else {"current_verdict": row}

    string_key = f"{slate_date}:{normalized_pitcher}:{side}"
    if string_key in previous_state:
        row = previous_state[string_key]
        return row if isinstance(row, dict) else {"current_verdict": row}

    return None


def _side_rows(pitcher: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for side in ("over", "under"):
        ev = pitcher.get(f"ev_{side}")
        if not isinstance(ev, dict):
            continue
        verdict = str(ev.get("verdict") or "PASS").strip() or "PASS"
        rows.append({
            "side": side,
            "verdict": verdict,
            "odds": pitcher.get(f"best_{side}_odds"),
            "book": pitcher.get(f"best_{side}_book"),
            "ev": ev,
        })
    return rows


def _state_row(
    *,
    slate_date: str,
    pitcher: dict[str, Any],
    side_row: dict[str, Any],
    previous_verdict: str | None,
    k_line: float,
    observed_at: str,
    source_artifact_path: str,
    source_artifact_sha256: str | None,
) -> dict[str, Any]:
    pitcher_name = str(pitcher.get("pitcher") or "").strip()
    current_verdict = side_row["verdict"]

    return {
        "slate_date": slate_date,
        "pitcher": pitcher_name,
        "normalized_pitcher": normalize(pitcher_name),
        "side": side_row["side"],
        "current_verdict": current_verdict,
        "previous_verdict": previous_verdict,
        "k_line": k_line,
        "current_odds": side_row["odds"],
        "current_book": side_row["book"],
        "game_time": pitcher.get("game_time"),
        "game_state": pitcher.get("game_state"),
        "is_fire": _is_fire(current_verdict),
        "is_locked": _is_locked(pitcher),
        "source_artifact_path": source_artifact_path,
        "source_artifact_sha256": source_artifact_sha256,
        "last_model_seen_at": observed_at,
        "metadata": {
            "team": pitcher.get("team"),
            "opp_team": pitcher.get("opp_team"),
            "adj_ev": side_row["ev"].get("adj_ev"),
            "edge": side_row["ev"].get("edge"),
        },
    }


def _event(
    *,
    slate_date: str,
    event_type: str,
    pitcher_name: str,
    normalized_pitcher: str,
    side: str,
    previous_verdict: str | None,
    verdict: str,
    k_line: float,
    book: Any,
    odds: Any,
    observed_at: str,
) -> dict[str, Any]:
    side_label = side.upper()
    titles = {
        "new_fire_pick": "New FIRE Pick",
        "pick_upgraded": "Pick Upgraded",
        "pick_downgraded": "Pick Downgraded",
    }
    title = titles.get(event_type, "Pick Changed")
    body = f"{pitcher_name} {verdict} {side_label} {k_line} Ks"
    if book:
        body = f"{body} at {book}"

    return {
        "slate_date": slate_date,
        "event_type": event_type,
        "severity": "action",
        "title": title,
        "body": body,
        "url": "/",
        "dedupe_key": f"{slate_date}:{event_type}:{normalized_pitcher}:{side}:{verdict}:{k_line}",
        "payload": {
            "pitcher": pitcher_name,
            "side": side,
            "previous_verdict": previous_verdict,
            "verdict": verdict,
            "k_line": k_line,
            "book": book,
            "odds": odds,
        },
        "occurred_at": observed_at,
    }


def build_pick_change_events(
    slate_date: str,
    pitchers: list[dict[str, Any]],
    previous_state: dict[Any, Any],
    observed_at: datetime | str,
    source_artifact_path: str,
    source_artifact_sha256: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observed_at_iso = _isoformat(observed_at)
    events: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []

    for pitcher in pitchers:
        pitcher_name = str(pitcher.get("pitcher") or "").strip()
        if not pitcher_name:
            continue
        normalized_pitcher = normalize(pitcher_name)
        k_line = _k_line(pitcher.get("k_line"))
        if k_line is None:
            continue

        for side_row in _side_rows(pitcher):
            previous = _previous_row(
                previous_state,
                slate_date=slate_date,
                normalized_pitcher=normalized_pitcher,
                side=side_row["side"],
            )
            previous_verdict = None if previous is None else previous.get("current_verdict")
            state_row = _state_row(
                slate_date=slate_date,
                pitcher=pitcher,
                side_row=side_row,
                previous_verdict=previous_verdict,
                k_line=k_line,
                observed_at=observed_at_iso,
                source_artifact_path=source_artifact_path,
                source_artifact_sha256=source_artifact_sha256,
            )
            state_rows.append(state_row)

            current_verdict = side_row["verdict"]
            if state_row["is_locked"]:
                continue

            event_type = None
            if previous_verdict is None:
                if _is_fire(current_verdict):
                    event_type = "new_fire_pick"
            elif VERDICT_RANK.get(current_verdict, 0) > VERDICT_RANK.get(previous_verdict, 0):
                if _is_fire(current_verdict):
                    event_type = "pick_upgraded"
            elif _is_fire(previous_verdict) and VERDICT_RANK.get(current_verdict, 0) < VERDICT_RANK.get(previous_verdict, 0):
                event_type = "pick_downgraded"

            if event_type is None:
                continue

            events.append(_event(
                slate_date=slate_date,
                event_type=event_type,
                pitcher_name=pitcher_name,
                normalized_pitcher=normalized_pitcher,
                side=side_row["side"],
                previous_verdict=previous_verdict,
                verdict=current_verdict,
                k_line=k_line,
                book=side_row["book"],
                odds=side_row["odds"],
                observed_at=observed_at_iso,
            ))

    return events, state_rows


def build_missing_pick_state_events(
    *,
    slate_date: str,
    previous_rows: list[dict[str, Any]],
    current_state_rows: list[dict[str, Any]] | None = None,
    current_keys: set[tuple[str, str, str]] | None = None,
    observed_at: datetime | str,
    source_artifact_path: str,
    source_artifact_sha256: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observed_at_iso = _isoformat(observed_at)
    seen = set(current_keys or set())
    for row in current_state_rows or []:
        row_slate = str(row.get("slate_date") or "").strip()
        normalized_pitcher = str(row.get("normalized_pitcher") or "").strip()
        side = str(row.get("side") or "").strip().lower()
        if row_slate and normalized_pitcher and side:
            seen.add((row_slate, normalized_pitcher, side))

    events: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []

    for previous in previous_rows:
        row_slate = str(previous.get("slate_date") or "").strip()
        if row_slate != slate_date:
            continue
        pitcher_name = str(previous.get("pitcher") or "").strip()
        normalized_pitcher = str(previous.get("normalized_pitcher") or normalize(pitcher_name)).strip()
        side = str(previous.get("side") or "").strip().lower()
        if not normalized_pitcher or side not in {"over", "under"}:
            continue
        if (slate_date, normalized_pitcher, side) in seen:
            continue
        if _is_locked_state_row(previous):
            continue

        previous_verdict = str(previous.get("current_verdict") or "PASS").strip() or "PASS"
        k_line = _k_line(previous.get("k_line"))
        if k_line is None:
            continue

        state_row = {
            "slate_date": slate_date,
            "pitcher": pitcher_name,
            "normalized_pitcher": normalized_pitcher,
            "side": side,
            "current_verdict": "PASS",
            "previous_verdict": previous_verdict,
            "k_line": k_line,
            "current_odds": previous.get("current_odds"),
            "current_book": previous.get("current_book"),
            "game_time": previous.get("game_time"),
            "game_state": previous.get("game_state"),
            "is_fire": False,
            "is_locked": _is_locked_state_row(previous),
            "source_artifact_path": source_artifact_path,
            "source_artifact_sha256": source_artifact_sha256,
            "last_model_seen_at": observed_at_iso,
            "metadata": {"stale_reason": "absent_from_artifact"},
        }
        state_rows.append(state_row)

        if _is_fire(previous_verdict):
            events.append(_event(
                slate_date=slate_date,
                event_type="pick_downgraded",
                pitcher_name=pitcher_name,
                normalized_pitcher=normalized_pitcher,
                side=side,
                previous_verdict=previous_verdict,
                verdict="PASS",
                k_line=k_line,
                book=previous.get("current_book"),
                odds=previous.get("current_odds"),
                observed_at=observed_at_iso,
            ))

    return events, state_rows


def build_line_movement_events(
    slate_date: str,
    live_picks: list[dict[str, Any]],
    previous_snapshots: list[dict[str, Any]],
    current_snapshots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actionable: dict[tuple[str, str], dict[str, Any]] = {}
    for pick in live_picks:
        if not _is_fire(pick.get("current_verdict")):
            continue
        if _is_locked_state_row(pick):
            continue
        pitcher_name = str(pick.get("pitcher") or "").strip()
        normalized_pitcher = str(pick.get("normalized_pitcher") or normalize(pitcher_name)).strip()
        side = str(pick.get("side") or "").strip().lower()
        if normalized_pitcher and side in {"over", "under"}:
            actionable[(normalized_pitcher, side)] = pick

    previous_by_provider_book_player_side_line: dict[tuple[str, str, str, str, float], dict[str, Any]] = {}
    previous_lines_by_provider_book_player_side: dict[tuple[str, str, str, str], set[float]] = {}
    previous_single_snapshot_by_provider_book_player_side: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for snapshot in previous_snapshots:
        movement_key = _snapshot_movement_key(snapshot)
        line = _numeric(snapshot.get("line"))
        if movement_key is None or line is None:
            continue
        previous_by_provider_book_player_side_line[(*movement_key, line)] = snapshot
        previous_lines_by_provider_book_player_side.setdefault(movement_key, set()).add(line)
        previous_single_snapshot_by_provider_book_player_side[movement_key] = snapshot

    current_lines_by_provider_book_player_side: dict[tuple[str, str, str, str], set[float]] = {}
    for snapshot in current_snapshots:
        movement_key = _snapshot_movement_key(snapshot)
        line = _numeric(snapshot.get("line"))
        if movement_key is not None and line is not None:
            current_lines_by_provider_book_player_side.setdefault(movement_key, set()).add(line)

    events: list[dict[str, Any]] = []
    for snapshot in current_snapshots:
        movement_key = _snapshot_movement_key(snapshot)
        current_line = _numeric(snapshot.get("line"))
        if movement_key is None or current_line is None:
            continue
        provider_event_id, book, normalized, side = movement_key
        previous = previous_by_provider_book_player_side_line.get((*movement_key, current_line))
        if previous is None:
            previous_lines = previous_lines_by_provider_book_player_side.get(movement_key, set())
            current_lines = current_lines_by_provider_book_player_side.get(movement_key, set())
            if len(previous_lines) == 1 and len(current_lines) == 1:
                previous = previous_single_snapshot_by_provider_book_player_side.get(movement_key)
        if previous is None:
            continue
        pick = actionable.get((normalized, side))
        if pick is None:
            continue
        if _is_post_start_pick(pick, snapshot.get("observed_at")):
            continue

        previous_line = _numeric(previous.get("line"))
        previous_odds = _integer(previous.get("american_odds"))
        current_odds = _integer(snapshot.get("american_odds"))
        if None in {previous_line, current_line, previous_odds, current_odds}:
            continue

        line_changed = previous_line != current_line
        if line_changed and abs(current_line - previous_line) > MAX_LINE_MOVEMENT_NOTIFICATION_DELTA:
            continue
        pick_line = _numeric(pick.get("k_line"))
        if pick_line is not None:
            if line_changed and not (
                _matches_line(previous_line, pick_line) or _matches_line(current_line, pick_line)
            ):
                continue
            if not line_changed and not _matches_line(current_line, pick_line):
                continue

        odds_delta = current_odds - previous_odds
        if not line_changed and abs(odds_delta) < 10:
            continue

        if line_changed and previous_odds != current_odds:
            movement_kind = "line_and_odds"
        elif line_changed:
            movement_kind = "line"
        else:
            movement_kind = "odds"

        if line_changed:
            bet_value_direction = _line_bet_value_direction(side, previous_line, current_line)
            market_direction = _line_market_direction(side, previous_line, current_line)
        else:
            bet_value_direction = _odds_bet_value_direction(odds_delta)
            market_direction = _odds_market_direction(odds_delta)

        # Keep the old event_type/movement_direction names for compatibility;
        # they describe the current bet value, not market confirmation.
        with_model = bet_value_direction == "better_now"
        movement_direction = "with_model" if with_model else "against_model"
        event_type = "line_moved_with_us" if with_model else "line_moved_against_us"
        title_noun = "Price" if movement_kind == "odds" else "Line"
        title_direction = "Better" if with_model else "Worse"
        pitcher_name = str(pick.get("pitcher") or snapshot.get("player_name") or "").strip()
        dedupe_key = (
            f"{slate_date}:line:{provider_event_id}:{book}:{normalized}:{side}:"
            f"{previous_line:g}:{previous_odds}:{current_line:g}:{current_odds}"
        )

        events.append({
            "slate_date": slate_date,
            "event_type": event_type,
            "severity": "watch" if with_model else "action",
            "title": f"{title_noun} {title_direction} Now",
            "body": _movement_body(
                pitcher_name=pitcher_name,
                side=side,
                movement_kind=movement_kind,
                previous_line=previous_line,
                current_line=current_line,
                previous_odds=previous_odds,
                current_odds=current_odds,
                book=book,
                market_direction=market_direction,
                bet_value_direction=bet_value_direction,
            ),
            "url": "/",
            "dedupe_key": dedupe_key,
            "payload": {
                "pitcher": pitcher_name,
                "normalized_pitcher": normalized,
                "side": side,
                "provider_event_id": provider_event_id,
                "bookmaker_key": book,
                "previous_line": previous_line,
                "current_line": current_line,
                "previous_odds": previous_odds,
                "current_odds": current_odds,
                "movement_direction": movement_direction,
                "market_direction": market_direction,
                "bet_value_direction": bet_value_direction,
                "movement_kind": movement_kind,
                "source_snapshot_id": snapshot.get("id"),
                "game_time": pick.get("game_time"),
                "game_state": pick.get("game_state"),
                "is_locked": pick.get("is_locked"),
            },
            "occurred_at": snapshot.get("observed_at"),
        })

    return events


def build_propline_webhook_movement_notification_events(
    slate_date: str,
    live_picks: list[dict[str, Any]],
    webhook_movement_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actionable: dict[tuple[str, str], dict[str, Any]] = {}
    for pick in live_picks:
        if not _is_fire(pick.get("current_verdict")):
            continue
        if _is_locked_state_row(pick):
            continue
        pitcher_name = str(pick.get("pitcher") or "").strip()
        normalized_pitcher = str(pick.get("normalized_pitcher") or normalize(pitcher_name)).strip()
        side = str(pick.get("side") or "").strip().lower()
        if normalized_pitcher and side in {"over", "under"}:
            actionable[(normalized_pitcher, side)] = pick

    events: list[dict[str, Any]] = []
    for row in webhook_movement_rows:
        if str(row.get("slate_date") or "") != slate_date:
            continue
        metadata = row.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        if metadata.get("source") != "propline_webhook":
            continue
        if metadata.get("bookmaker_key_missing"):
            continue

        normalized = str(row.get("normalized_pitcher") or normalize(row.get("pitcher") or "")).strip()
        side = str(row.get("side") or "").strip().lower()
        book = str(row.get("bookmaker_key") or "").strip().lower()
        pick = actionable.get((normalized, side))
        if pick is None or side not in {"over", "under"} or book not in PROPLINE_WEBHOOK_NOTIFICATION_BOOKS:
            continue
        if _is_post_start_pick(pick, row.get("observed_at")):
            continue

        previous_line = _numeric(row.get("previous_line"))
        current_line = _numeric(row.get("current_line"))
        previous_odds = _integer(row.get("previous_odds"))
        current_odds = _integer(row.get("current_odds"))
        if None in {previous_line, current_line, previous_odds, current_odds}:
            continue

        line_changed = previous_line != current_line
        if line_changed and abs(current_line - previous_line) > MAX_LINE_MOVEMENT_NOTIFICATION_DELTA:
            continue
        pick_line = _numeric(pick.get("k_line"))
        if pick_line is not None:
            if line_changed and not (
                _matches_line(previous_line, pick_line) or _matches_line(current_line, pick_line)
            ):
                continue
            if not line_changed and not _matches_line(current_line, pick_line):
                continue

        odds_delta = current_odds - previous_odds
        if not line_changed and abs(odds_delta) < 10:
            continue

        if line_changed and previous_odds != current_odds:
            movement_kind = "line_and_odds"
        elif line_changed:
            movement_kind = "line"
        else:
            movement_kind = "odds"

        if line_changed:
            bet_value_direction = _line_bet_value_direction(side, previous_line, current_line)
            market_direction = _line_market_direction(side, previous_line, current_line)
        else:
            bet_value_direction = _odds_bet_value_direction(odds_delta)
            market_direction = _odds_market_direction(odds_delta)

        with_model = bet_value_direction == "better_now"
        event_type = "line_moved_with_us" if with_model else "line_moved_against_us"
        title_noun = "Price" if movement_kind == "odds" else "Line"
        title_direction = "Better" if with_model else "Worse"
        pitcher_name = str(pick.get("pitcher") or row.get("pitcher") or "").strip()
        provider_event_id = str(
            metadata.get("prop_line_event_id")
            or metadata.get("provider_event_id")
            or ""
        ).strip()
        if not provider_event_id:
            continue
        dedupe_key = (
            f"{slate_date}:line:{provider_event_id}:{book}:{normalized}:{side}:"
            f"{previous_line:g}:{previous_odds}:{current_line:g}:{current_odds}"
        )

        events.append({
            "slate_date": slate_date,
            "event_type": event_type,
            "severity": "watch" if with_model else "action",
            "title": f"{title_noun} {title_direction} Now",
            "body": _movement_body(
                pitcher_name=pitcher_name,
                side=side,
                movement_kind=movement_kind,
                previous_line=previous_line,
                current_line=current_line,
                previous_odds=previous_odds,
                current_odds=current_odds,
                book=book,
                market_direction=market_direction,
                bet_value_direction=bet_value_direction,
            ),
            "url": "/",
            "dedupe_key": dedupe_key,
            "payload": {
                "pitcher": pitcher_name,
                "normalized_pitcher": normalized,
                "side": side,
                "provider_event_id": provider_event_id,
                "bookmaker_key": book,
                "previous_line": previous_line,
                "current_line": current_line,
                "previous_odds": previous_odds,
                "current_odds": current_odds,
                "movement_direction": "with_model" if with_model else "against_model",
                "market_direction": market_direction,
                "bet_value_direction": bet_value_direction,
                "movement_kind": movement_kind,
                "source": "propline_webhook",
                "source_line_movement_dedupe_key": row.get("dedupe_key"),
                "prop_line_delivery_id": metadata.get("prop_line_delivery_id"),
                "game_time": pick.get("game_time"),
                "game_state": pick.get("game_state"),
                "is_locked": pick.get("is_locked"),
            },
            "occurred_at": row.get("observed_at"),
        })

    return events


def build_line_movement_rows(movement_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in movement_events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue

        row = {
            "slate_date": event.get("slate_date"),
            "normalized_pitcher": payload.get("normalized_pitcher"),
            "pitcher": payload.get("pitcher"),
            "side": payload.get("side"),
            "bookmaker_key": payload.get("bookmaker_key"),
            "previous_line": payload.get("previous_line"),
            "current_line": payload.get("current_line"),
            "previous_odds": payload.get("previous_odds"),
            "current_odds": payload.get("current_odds"),
            "movement_direction": payload.get("movement_direction"),
            "movement_kind": payload.get("movement_kind"),
            "observed_at": event.get("occurred_at"),
            "dedupe_key": event.get("dedupe_key"),
            "source_snapshot_id": payload.get("source_snapshot_id"),
            "metadata": {
                "bet_value_direction": payload.get("bet_value_direction"),
                "event_type": event.get("event_type"),
                "market_direction": payload.get("market_direction"),
                "provider_event_id": payload.get("provider_event_id"),
                "severity": event.get("severity"),
            },
        }
        required = [
            "slate_date",
            "normalized_pitcher",
            "pitcher",
            "side",
            "bookmaker_key",
            "current_line",
            "current_odds",
            "movement_direction",
            "movement_kind",
            "observed_at",
            "dedupe_key",
        ]
        if all(row.get(key) is not None for key in required):
            rows.append(row)

    return rows


def build_reminder_events(
    slate_date: str,
    live_picks: list[dict[str, Any]],
    existing_reminders: Any,
    observed_at: datetime | str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observed_at_dt = _parse_datetime(observed_at)
    observed_at_iso = observed_at_dt.isoformat()
    seen_reminders = _reminder_dedupe_keys(existing_reminders)
    windows = {
        "FIRE 2u": [("45_min", 45), ("10_min", 10)],
        "FIRE 1u": [("25_min", 25)],
    }
    events: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for pick in live_picks:
        if pick.get("is_locked") or pick.get("locked_at") or not pick.get("game_time"):
            continue

        verdict = str(pick.get("current_verdict") or "PASS").strip()
        if verdict not in windows:
            continue

        game_time = _parse_datetime(pick["game_time"])
        minutes_to_game = (game_time - observed_at_dt).total_seconds() / 60
        pitcher_name = str(pick.get("pitcher") or "").strip()
        normalized_pitcher = str(pick.get("normalized_pitcher") or normalize(pitcher_name)).strip()
        side = str(pick.get("side") or "").strip().lower()
        if not normalized_pitcher or side not in {"over", "under"}:
            continue

        for window_name, minutes in windows[verdict]:
            if minutes_to_game < 0 or minutes_to_game > minutes:
                continue
            if minutes_to_game < max(0, minutes - 10):
                continue

            dedupe_key = f"{slate_date}:reminder:{window_name}:{normalized_pitcher}:{side}"
            if dedupe_key in seen_reminders:
                continue

            row = {
                "slate_date": slate_date,
                "normalized_pitcher": normalized_pitcher,
                "side": side,
                "reminder_window": window_name,
                "game_time": game_time.isoformat(),
                "due_at": observed_at_iso,
                "fired_at": observed_at_iso,
                "dedupe_key": dedupe_key,
                "metadata": {
                    "verdict": verdict,
                    "pitcher": pitcher_name,
                },
            }
            rows.append(row)
            events.append({
                "slate_date": slate_date,
                "event_type": "game_reminder_due",
                "severity": "action",
                "title": "Pick Starts Soon",
                "body": f"{pitcher_name} {verdict} {side.upper()} {pick.get('k_line')} Ks",
                "url": "/",
                "dedupe_key": dedupe_key,
                "payload": {
                    "pitcher": pitcher_name,
                    "side": side,
                    "verdict": verdict,
                    "k_line": pick.get("k_line"),
                    "game_time": game_time.isoformat(),
                    "reminder_window": window_name,
                },
                "occurred_at": observed_at_iso,
            })
            seen_reminders.add(dedupe_key)

    return events, rows
