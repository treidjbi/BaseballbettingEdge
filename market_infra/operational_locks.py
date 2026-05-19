from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pipeline.name_utils import normalize


TRACKED_VERDICT_RANK = {
    "PASS": 0,
    "LEAN": 1,
    "FIRE 1u": 2,
    "FIRE 2u": 3,
}

LOCK_WINDOW_MINUTES = 30
MISSED_LOCK_GRACE_MINUTES = 5


def _parse_datetime(value: Any) -> datetime | None:
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
    return parsed.astimezone(timezone.utc)


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


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


def _tracked_pick_rows(pitcher: dict[str, Any]) -> list[dict[str, Any]]:
    tracked = pitcher.get("tracked_picks")
    if isinstance(tracked, list):
        return [row for row in tracked if isinstance(row, dict)]
    return []


def _pick_verdict(pick: dict[str, Any]) -> str:
    return str(
        pick.get("display_verdict")
        or pick.get("locked_verdict")
        or pick.get("actionable_verdict")
        or pick.get("verdict")
        or "PASS"
    ).strip() or "PASS"


def _capture_status(observed_at: datetime, game_time: datetime) -> tuple[str | None, datetime, float]:
    should_lock_at = game_time - timedelta(minutes=LOCK_WINDOW_MINUTES)
    minutes_until_start = round((game_time - observed_at).total_seconds() / 60.0, 2)
    grace_ends_at = should_lock_at + timedelta(minutes=MISSED_LOCK_GRACE_MINUTES)

    if observed_at >= game_time:
        return None, should_lock_at, minutes_until_start
    if observed_at > grace_ends_at:
        return "missed_lock", should_lock_at, minutes_until_start
    if observed_at >= should_lock_at:
        return "due_now", should_lock_at, minutes_until_start
    return None, should_lock_at, minutes_until_start


def build_operational_lock_rows(
    *,
    slate_date: str,
    pitchers: list[dict[str, Any]],
    observed_at: datetime,
    source_artifact_path: str,
    source_artifact_sha256: str | None,
    artifact_generated_at: str | datetime | None = None,
) -> list[dict[str, Any]]:
    """Build operational lock ledger rows from dashboard tracked picks.

    This is pure shaping logic. It does not write Supabase rows or mutate the
    source artifact.
    """
    observed_utc = _parse_datetime(observed_at)
    if observed_utc is None:
        raise ValueError("observed_at must be parseable")

    artifact_generated = _parse_datetime(artifact_generated_at)
    rows: list[dict[str, Any]] = []

    for pitcher in pitchers:
        pitcher_name = str(pitcher.get("pitcher") or "").strip()
        if not pitcher_name:
            continue
        normalized_pitcher = normalize(pitcher_name)

        for pick in _tracked_pick_rows(pitcher):
            side = str(pick.get("side") or "").strip().lower()
            if side not in {"over", "under"}:
                continue
            if _parse_datetime(pick.get("locked_at")) is not None:
                continue

            verdict = _pick_verdict(pick)
            if TRACKED_VERDICT_RANK.get(verdict, 0) <= TRACKED_VERDICT_RANK["PASS"]:
                continue

            game_time = _parse_datetime(pick.get("game_time") or pitcher.get("game_time"))
            if game_time is None:
                continue

            status, should_lock_at, minutes_until_start = _capture_status(observed_utc, game_time)
            if status is None:
                continue

            line = _numeric(pick.get("display_k_line") or pick.get("locked_k_line") or pick.get("k_line"))
            odds = _integer(pick.get("display_odds") or pick.get("locked_odds") or pick.get("odds"))
            if line is None or odds is None:
                continue

            book = (
                pick.get("book")
                or pick.get("current_book")
                or pitcher.get(f"best_{side}_book")
                or pitcher.get("ref_book")
            )

            rows.append({
                "dedupe_key": f"{slate_date}:{normalized_pitcher}:{side}",
                "slate_date": slate_date,
                "source": "live_layer",
                "status_at_capture": status,
                "observed_at": _isoformat(observed_utc),
                "locked_at": _isoformat(observed_utc),
                "pitcher": str(pick.get("pitcher") or pitcher_name),
                "normalized_pitcher": normalized_pitcher,
                "side": side,
                "locked_verdict": verdict,
                "locked_k_line": line,
                "locked_odds": odds,
                "locked_adj_ev": _numeric(
                    pick.get("display_adj_ev") or pick.get("locked_adj_ev") or pick.get("adj_ev")
                ),
                "locked_book": str(book).strip() if book else None,
                "game_time": _isoformat(game_time),
                "should_lock_at": _isoformat(should_lock_at),
                "minutes_until_start": minutes_until_start,
                "source_artifact_path": source_artifact_path,
                "source_artifact_sha256": source_artifact_sha256,
                "metadata": {
                    "team": pitcher.get("team"),
                    "opp_team": pitcher.get("opp_team"),
                    "artifact_generated_at": _isoformat(artifact_generated),
                    "lock_window_minutes": LOCK_WINDOW_MINUTES,
                    "missed_lock_grace_minutes": MISSED_LOCK_GRACE_MINUTES,
                },
            })

    return rows
