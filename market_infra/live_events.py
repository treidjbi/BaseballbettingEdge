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


def _isoformat(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _is_fire(verdict: str | None) -> bool:
    return VERDICT_RANK.get(verdict or "PASS", 0) >= VERDICT_RANK["FIRE 1u"]


def _is_locked(pitcher: dict[str, Any]) -> bool:
    game_state = str(pitcher.get("game_state") or "").strip().lower()
    return bool(pitcher.get("locked_at")) or game_state in LOCKED_GAME_STATES


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


def _parse_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


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
    title = "New FIRE Pick" if event_type == "new_fire_pick" else "Pick Upgraded"
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
            if state_row["is_locked"] or not _is_fire(current_verdict):
                continue

            event_type = None
            if previous_verdict is None:
                event_type = "new_fire_pick"
            elif VERDICT_RANK.get(current_verdict, 0) > VERDICT_RANK.get(previous_verdict, 0):
                event_type = "pick_upgraded"

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
        pitcher_name = str(pick.get("pitcher") or "").strip()
        normalized_pitcher = str(pick.get("normalized_pitcher") or normalize(pitcher_name)).strip()
        side = str(pick.get("side") or "").strip().lower()
        if normalized_pitcher and side in {"over", "under"}:
            actionable[(normalized_pitcher, side)] = pick

    previous_by_book_player_side: dict[tuple[str, str, str], dict[str, Any]] = {}
    for snapshot in previous_snapshots:
        book = str(snapshot.get("bookmaker_key") or "").strip()
        normalized = str(snapshot.get("normalized_player_name") or "").strip()
        side = str(snapshot.get("side") or "").strip().lower()
        if book and normalized and side in {"over", "under"}:
            previous_by_book_player_side[(book, normalized, side)] = snapshot

    events: list[dict[str, Any]] = []
    for snapshot in current_snapshots:
        book = str(snapshot.get("bookmaker_key") or "").strip()
        normalized = str(snapshot.get("normalized_player_name") or normalize(snapshot.get("player_name") or "")).strip()
        side = str(snapshot.get("side") or "").strip().lower()
        if not book or not normalized or side not in {"over", "under"}:
            continue
        previous = previous_by_book_player_side.get((book, normalized, side))
        if previous is None:
            continue
        pick = actionable.get((normalized, side))
        if pick is None:
            continue

        previous_line = _numeric(previous.get("line"))
        current_line = _numeric(snapshot.get("line"))
        previous_odds = _integer(previous.get("american_odds"))
        current_odds = _integer(snapshot.get("american_odds"))
        if None in {previous_line, current_line, previous_odds, current_odds}:
            continue

        line_changed = previous_line != current_line
        odds_delta = current_odds - previous_odds
        if not line_changed and abs(odds_delta) < 10:
            continue

        if line_changed and previous_odds != current_odds:
            movement_kind = "line_and_odds"
        elif line_changed:
            movement_kind = "line"
        else:
            movement_kind = "odds"

        if side == "over":
            with_model = current_line < previous_line or (not line_changed and odds_delta > 0)
        else:
            with_model = current_line > previous_line or (not line_changed and odds_delta > 0)

        movement_direction = "with_model" if with_model else "against_model"
        event_type = "line_moved_with_us" if with_model else "line_moved_against_us"
        pitcher_name = str(pick.get("pitcher") or snapshot.get("player_name") or "").strip()
        dedupe_key = (
            f"{slate_date}:line:{book}:{normalized}:{side}:"
            f"{previous_line:g}:{previous_odds}:{current_line:g}:{current_odds}"
        )

        events.append({
            "slate_date": slate_date,
            "event_type": event_type,
            "severity": "watch" if with_model else "action",
            "title": "Line Moved With Us" if with_model else "Line Moved Against Us",
            "body": f"{pitcher_name} {side.upper()} moved {previous_line:g} to {current_line:g} at {book}",
            "url": "/",
            "dedupe_key": dedupe_key,
            "payload": {
                "pitcher": pitcher_name,
                "side": side,
                "bookmaker_key": book,
                "previous_line": previous_line,
                "current_line": current_line,
                "previous_odds": previous_odds,
                "current_odds": current_odds,
                "movement_direction": movement_direction,
                "movement_kind": movement_kind,
                "source_snapshot_id": snapshot.get("id"),
            },
            "occurred_at": snapshot.get("observed_at"),
        })

    return events


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
