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
        ev = pitcher.get(f"ev_{side}") or {}
        if not isinstance(ev, dict):
            continue
        verdict = str(ev.get("verdict") or "PASS").strip() or "PASS"
        if VERDICT_RANK.get(verdict, 0) <= VERDICT_RANK["PASS"]:
            continue
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
        "k_line": pitcher.get("k_line"),
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
    k_line: Any,
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
                k_line=pitcher.get("k_line"),
                book=side_row["book"],
                odds=side_row["odds"],
                observed_at=observed_at_iso,
            ))

    return events, state_rows
