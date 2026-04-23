"""
fetch_lineups.py
Fetches projected/confirmed batting lineups from the MLB Stats API for a given
game date. Returns None when the lineup hasn't been posted yet (normal for
morning runs, or for games still in pregame state).

Data source (2026-04-23 cutover — Task A5):
  * Previously hit /schedule?hydrate=lineups and filtered players by
    `battingOrder`. That field does NOT exist on the schedule hydrate's player
    payload — it only lives on /game/{pk}/boxscore. Result: every call returned
    None, and lineup_used was False on 602/602 picks all-time. Mitigated by
    build_features falling back to stats["opp_k_rate"] (team-aggregate), but
    the per-batter signal (handedness, batter-specific K% via fetch_batter_stats)
    was completely dormant.
  * This module now:
      1. GET /schedule to map (date, team_name) -> (gamePk, away|home).
      2. GET /game/{gamePk}/boxscore for the ordered battingOrder list and
         per-player info.
      3. Return 9 batters in batting order with {"name", "bats"} dicts.
  * Both calls hit statsapi.mlb.com with no published rate limit. Two calls
    per team per slate (~30/day in peak season) is negligible.

Graceful-degradation semantics preserved:
  * Any network / HTTP / parse error: return None (no exception bubbles up).
  * Team not on schedule for that date: return None.
  * Boxscore has empty battingOrder (pregame before lineup posted): return None.
"""
import logging
import requests

log = logging.getLogger(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"


def _find_game(schedule_data: dict, team_name: str) -> tuple:
    """Return (game_pk, side_key) for the game `team_name` plays on this slate.

    side_key is "away" or "home" so the caller can index into boxscore.teams.
    Returns (None, None) when the team isn't scheduled.
    Match is case-insensitive.
    """
    team_lower = team_name.lower()
    for date_entry in schedule_data.get("dates", []) or []:
        for game in date_entry.get("games", []) or []:
            teams = game.get("teams") or {}
            away = ((teams.get("away") or {}).get("team") or {}).get("name", "").lower()
            home = ((teams.get("home") or {}).get("team") or {}).get("name", "").lower()
            if team_lower == away:
                return game.get("gamePk"), "away"
            if team_lower == home:
                return game.get("gamePk"), "home"
    return None, None


def _extract_batters(boxscore: dict, side_key: str) -> list:
    """Return [{"name": str, "bats": str}, ...] in battingOrder order.

    Empty list when battingOrder is missing/empty (pregame, lineup not posted).
    Unknown handedness defaults to "R" (matches prior behavior).
    """
    team_block = ((boxscore.get("teams") or {}).get(side_key) or {})
    order = team_block.get("battingOrder") or []
    players = team_block.get("players") or {}

    result = []
    for pid in order:
        entry = players.get(f"ID{pid}") or {}
        person = entry.get("person") or {}
        name = person.get("fullName") or "Unknown"
        bats = ((person.get("batSide") or {}).get("code")) or "R"
        result.append({"name": name, "bats": bats})
    return result


def fetch_lineups(date_str: str, team_name: str) -> list[dict] | None:
    """
    Fetch the batting lineup for `team_name` on `date_str` (YYYY-MM-DD).

    Returns a list of {"name": str, "bats": str} dicts in batting order, or
    None when the lineup isn't available yet / isn't retrievable.

    team_name must match the MLB Stats API team name (e.g. "New York Yankees").
    Matching is case-insensitive on both away and home sides.
    """
    # Step 1: locate the game on the schedule
    try:
        resp = requests.get(
            f"{MLB_BASE}/schedule",
            params={"sportId": 1, "date": date_str},
            timeout=15,
        )
        resp.raise_for_status()
        schedule_data = resp.json()
    except Exception as e:
        log.warning(
            "fetch_lineups: schedule fetch failed for %s on %s: %s",
            team_name, date_str, e,
        )
        return None

    game_pk, side_key = _find_game(schedule_data, team_name)
    if not game_pk:
        log.info("fetch_lineups: no game found for %s on %s", team_name, date_str)
        return None

    # Step 2: boxscore carries battingOrder + per-player handedness
    try:
        resp = requests.get(
            f"{MLB_BASE}/game/{game_pk}/boxscore",
            timeout=15,
        )
        resp.raise_for_status()
        boxscore = resp.json()
    except Exception as e:
        log.warning(
            "fetch_lineups: boxscore fetch failed for %s (pk=%s): %s",
            team_name, game_pk, e,
        )
        return None

    batters = _extract_batters(boxscore, side_key)
    if not batters:
        log.info(
            "fetch_lineups: no battingOrder posted yet for %s on %s (pk=%s)",
            team_name, date_str, game_pk,
        )
        return None

    log.info(
        "fetch_lineups: %s — %d batters from boxscore for %s (pk=%s)",
        date_str, len(batters), team_name, game_pk,
    )
    return batters
