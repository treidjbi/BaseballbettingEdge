"""
fetch_lineups.py
Fetches projected batting lineups from the MLB Stats API for a given game date.
Returns None when lineups haven't been posted yet (normal for morning runs).
"""
import logging
import requests

log = logging.getLogger(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"


def fetch_lineups(date_str: str, team_name: str) -> list[dict] | None:
    """
    Fetch the projected lineup for a team on a given date.

    Returns a list of {"name": str, "bats": str} dicts (one per batter in order)
    when the lineup is available, or None when not yet posted.

    team_name must match the MLB Stats API team name exactly (e.g. "New York Yankees").
    Matching is case-insensitive on both away and home sides.
    """
    try:
        resp = requests.get(
            f"{MLB_BASE}/schedule",
            params={"sportId": 1, "date": date_str, "hydrate": "lineups"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("fetch_lineups: API error for %s on %s: %s", team_name, date_str, e)
        return None

    team_lower = team_name.lower()
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            teams = game.get("teams", {})
            away_name = teams.get("away", {}).get("team", {}).get("name", "").lower()
            home_name = teams.get("home", {}).get("team", {}).get("name", "").lower()

            if team_lower in (away_name, home_name):
                side_key = "awayPlayers" if team_lower == away_name else "homePlayers"
                players = game.get("lineups", {}).get(side_key, [])

                # Filter to batting order entries only (battingOrder is a string like "100")
                batters = [p for p in players if p.get("battingOrder")]
                batters.sort(key=lambda p: int(p.get("battingOrder", "999")))

                if not batters:
                    log.info("fetch_lineups: no lineup posted for %s on %s", team_name, date_str)
                    return None

                result = []
                for b in batters:
                    name = b.get("person", {}).get("fullName", "Unknown")
                    bats = b.get("person", {}).get("batSide", {}).get("code", "R")
                    result.append({"name": name, "bats": bats})

                log.info("fetch_lineups: %s — %d batters found for %s",
                         date_str, len(result), team_name)
                return result

    log.info("fetch_lineups: no game found for %s on %s", team_name, date_str)
    return None
