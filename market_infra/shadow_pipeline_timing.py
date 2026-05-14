from __future__ import annotations

import hashlib
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


def _tracked_pick_rows(pitcher: dict[str, Any]) -> list[dict[str, Any]]:
    tracked = pitcher.get("tracked_picks")
    if isinstance(tracked, list):
        return [row for row in tracked if isinstance(row, dict)]

    rows: list[dict[str, Any]] = []
    for side in ("over", "under"):
        ev = pitcher.get(f"ev_{side}")
        if not isinstance(ev, dict):
            continue
        verdict = str(ev.get("actionable_verdict") or ev.get("verdict") or "PASS").strip() or "PASS"
        if TRACKED_VERDICT_RANK.get(verdict, 0) <= TRACKED_VERDICT_RANK["PASS"]:
            continue
        rows.append({
            "pitcher": pitcher.get("pitcher"),
            "side": side,
            "display_verdict": verdict,
            "display_k_line": pitcher.get("k_line"),
            "display_odds": pitcher.get(f"best_{side}_odds"),
            "locked_at": pitcher.get("locked_at"),
            "game_time": pitcher.get("game_time"),
        })
    return rows


def _pick_verdict(pick: dict[str, Any]) -> str:
    return str(
        pick.get("display_verdict")
        or pick.get("locked_verdict")
        or pick.get("actionable_verdict")
        or pick.get("verdict")
        or "PASS"
    ).strip() or "PASS"


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


def _run_key(*, slate_date: str, observed_at: datetime, source_artifact_sha256: str | None) -> str:
    raw = f"{slate_date}|live_layer_shadow_timing|{observed_at.isoformat()}|{source_artifact_sha256 or ''}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{slate_date}:live_layer_shadow_timing:{digest}"


def _status(
    *,
    observed_at: datetime,
    game_time: datetime | None,
    locked_at: datetime | None,
) -> tuple[str, datetime | None, float | None]:
    if locked_at is not None:
        return "artifact_locked", None if game_time is None else game_time - timedelta(minutes=LOCK_WINDOW_MINUTES), None

    if game_time is None:
        return "missing_game_time", None, None

    should_lock_at = game_time - timedelta(minutes=LOCK_WINDOW_MINUTES)
    minutes_until_start = round((game_time - observed_at).total_seconds() / 60.0, 2)

    if observed_at >= game_time:
        return "started_unlocked", should_lock_at, minutes_until_start
    if observed_at >= should_lock_at + timedelta(minutes=MISSED_LOCK_GRACE_MINUTES):
        return "missed_lock", should_lock_at, minutes_until_start
    if observed_at >= should_lock_at:
        return "due_now", should_lock_at, minutes_until_start
    return "not_due", should_lock_at, minutes_until_start


def build_shadow_pipeline_timing_rows(
    *,
    slate_date: str,
    pitchers: list[dict[str, Any]],
    observed_at: datetime,
    source_artifact_path: str,
    source_artifact_sha256: str | None,
    artifact_generated_at: str | datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build compact shadow timing rows for Render-vs-GitHub lock evaluation.

    The observation table is deduped by pick/status so it records state
    transitions without storing every pick on every Render cron tick.
    """
    observed_utc = _parse_datetime(observed_at)
    if observed_utc is None:
        raise ValueError("observed_at must be parseable")

    artifact_generated = _parse_datetime(artifact_generated_at)
    run_key = _run_key(
        slate_date=slate_date,
        observed_at=observed_utc,
        source_artifact_sha256=source_artifact_sha256,
    )

    counts = {
        "tracked_pick_count": 0,
        "artifact_locked_pick_count": 0,
        "due_now_count": 0,
        "missed_lock_count": 0,
        "started_unlocked_count": 0,
        "missing_game_time_count": 0,
    }
    observation_rows: list[dict[str, Any]] = []

    for pitcher in pitchers:
        pitcher_name = str(pitcher.get("pitcher") or "").strip()
        if not pitcher_name:
            continue
        normalized_pitcher = normalize(pitcher_name)
        game_state = str(pitcher.get("game_state") or "").strip() or None

        for pick in _tracked_pick_rows(pitcher):
            side = str(pick.get("side") or "").strip().lower()
            if side not in {"over", "under"}:
                continue
            verdict = _pick_verdict(pick)
            if TRACKED_VERDICT_RANK.get(verdict, 0) <= TRACKED_VERDICT_RANK["PASS"]:
                continue

            counts["tracked_pick_count"] += 1

            game_time = _parse_datetime(pick.get("game_time") or pitcher.get("game_time"))
            locked_at = _parse_datetime(pick.get("locked_at"))
            status, should_lock_at, minutes_until_start = _status(
                observed_at=observed_utc,
                game_time=game_time,
                locked_at=locked_at,
            )

            if status == "artifact_locked":
                counts["artifact_locked_pick_count"] += 1
            elif status == "due_now":
                counts["due_now_count"] += 1
            elif status == "missed_lock":
                counts["missed_lock_count"] += 1
            elif status == "started_unlocked":
                counts["started_unlocked_count"] += 1
            elif status == "missing_game_time":
                counts["missing_game_time_count"] += 1

            line = _numeric(pick.get("display_k_line") or pick.get("locked_k_line") or pick.get("k_line"))
            odds = _integer(pick.get("display_odds") or pick.get("locked_odds") or pick.get("odds"))
            book = (
                pick.get("book")
                or pick.get("current_book")
                or pitcher.get(f"best_{side}_book")
                or pitcher.get("ref_book")
            )

            observation_rows.append({
                "dedupe_key": f"{slate_date}:{normalized_pitcher}:{side}:{status}",
                "slate_date": slate_date,
                "source_run_key": run_key,
                "status": status,
                "observed_at": _isoformat(observed_utc),
                "pitcher": str(pick.get("pitcher") or pitcher_name),
                "normalized_pitcher": normalized_pitcher,
                "side": side,
                "current_verdict": verdict,
                "k_line": line,
                "current_odds": odds,
                "current_book": str(book).strip() if book else None,
                "game_time": _isoformat(game_time),
                "should_lock_at": _isoformat(should_lock_at),
                "artifact_locked_at": _isoformat(locked_at),
                "game_state": game_state,
                "minutes_until_start": minutes_until_start,
                "source_artifact_path": source_artifact_path,
                "source_artifact_sha256": source_artifact_sha256,
                "metadata": {
                    "team": pitcher.get("team"),
                    "opp_team": pitcher.get("opp_team"),
                    "display_status": pick.get("status"),
                    "locked_verdict": pick.get("locked_verdict"),
                    "locked_k_line": pick.get("locked_k_line"),
                    "locked_odds": pick.get("locked_odds"),
                },
            })

    run_row = {
        "run_key": run_key,
        "slate_date": slate_date,
        "run_source": "live_layer_shadow_timing",
        "observed_at": _isoformat(observed_utc),
        "artifact_generated_at": _isoformat(artifact_generated),
        "source_artifact_path": source_artifact_path,
        "source_artifact_sha256": source_artifact_sha256,
        "artifact_pitcher_count": len(pitchers),
        **counts,
        "metadata": {
            "artifact_staleness_seconds": None
            if artifact_generated is None
            else int((observed_utc - artifact_generated).total_seconds()),
            "lock_window_minutes": LOCK_WINDOW_MINUTES,
            "missed_lock_grace_minutes": MISSED_LOCK_GRACE_MINUTES,
        },
    }
    return run_row, observation_rows
