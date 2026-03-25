"""
fetch_odds.py
Fetches MLB K prop lines from TheRundown API v2.
Opening odds come from the 7-day history endpoint (earliest available line in window).
Auth: X-TheRundown-Key header. Rate limit: 2 req/sec — sleep 0.55s between calls.
"""
import os
import time
import logging
import requests
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

BASE_URL   = "https://therundown.io/api/v2"
SPORT_ID   = 3   # MLB
THROTTLE_S = 0.55


def _headers() -> dict:
    key = os.environ.get("RUNDOWN_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "RUNDOWN_API_KEY not set. "
            "Set it as a Windows User Environment Variable via sysdm.cpl."
        )
    return {"X-TheRundown-Key": key, "Accept": "application/json"}


def throttled_get(url: str, params: dict = None) -> dict:
    """GET with rate-limit throttle. Raises on non-200."""
    time.sleep(THROTTLE_S)
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def american_odds_from_line(value) -> int | None:
    """Parse an American odds value like '-110', '+130', or 130. Returns None if unparseable."""
    try:
        v = str(value).strip().replace("+", "")
        if not v or v.lower() in ("n/a", "none", "null", "-"):
            return None
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _fetch_opening_odds_map(date_str: str) -> dict:
    """
    Fetches 7-day history and returns a map of
    {pitcher_name: {opening_over_odds, opening_under_odds, opening_line}}.
    Uses the earliest available line in the 7-day window as the opening line.
    """
    opening_map = {}
    for days_back in range(7, 0, -1):
        hist_date = (
            datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=days_back)
        ).strftime("%Y-%m-%d")
        try:
            url  = f"{BASE_URL}/sports/{SPORT_ID}/events/{hist_date}"
            data = throttled_get(url)
            for event in data.get("events", []):
                for book_id, lines in event.get("lines", {}).items():
                    prop = lines.get("pitcher_strikeouts")
                    if not prop:
                        continue
                    name = prop.get("pitcher_name")
                    if name and name not in opening_map:
                        over  = american_odds_from_line(prop.get("over_odds"))
                        under = american_odds_from_line(prop.get("under_odds"))
                        line  = prop.get("over")
                        if over and under and line:
                            opening_map[name] = {
                                "opening_over_odds":  over,
                                "opening_under_odds": under,
                                "opening_line":       line,
                            }
        except Exception as e:
            log.warning("History fetch failed for %s: %s", hist_date, e)
    return opening_map


def parse_k_props(data: dict, opening_odds_map: dict) -> list:
    """
    Parses a TheRundown events response into a list of K-prop dicts.
    Skips events with no pitcher_strikeouts prop.
    opening_odds_map: {pitcher_name: {opening_over_odds, opening_under_odds, opening_line}}
    """
    results = []
    for event in data.get("events", []):
        teams     = event.get("teams", [])
        score     = event.get("score", {})
        game_time = score.get("start_time", "")

        away_team = next((t["name"] for t in teams if not t.get("is_home")), "")
        home_team = next((t["name"] for t in teams if t.get("is_home")),  "")

        best_prop     = None
        best_book     = None
        best_over_val = None

        for book_id, lines in event.get("lines", {}).items():
            prop = lines.get("pitcher_strikeouts")
            if not prop:
                continue
            over  = american_odds_from_line(prop.get("over_odds"))
            under = american_odds_from_line(prop.get("under_odds"))
            if over is None or under is None:
                continue
            # Select the book with the highest (most favorable) over odds
            if best_prop is None or over > best_over_val:
                best_prop     = prop
                best_book     = lines.get("book_name", "Unknown")
                best_over_val = over

        if not best_prop:
            continue

        name    = best_prop.get("pitcher_name", "")
        k_line  = best_prop.get("over", 0)
        opening = opening_odds_map.get(name, {})

        curr_over  = american_odds_from_line(best_prop.get("over_odds"))
        curr_under = american_odds_from_line(best_prop.get("under_odds"))

        results.append({
            "pitcher":            name,
            "team":               away_team,
            "opp_team":           home_team,
            "game_time":          game_time,
            "k_line":             k_line,
            "opening_line":       opening.get("opening_line", k_line),
            "best_over_book":     best_book,
            "best_over_odds":     curr_over,
            "best_under_odds":    curr_under,
            "opening_over_odds":  opening.get("opening_over_odds", curr_over),
            "opening_under_odds": opening.get("opening_under_odds", curr_under),
        })

    return results


def fetch_odds(date_str: str) -> list:
    """
    Main entry point. Returns list of K-prop dicts for date_str (YYYY-MM-DD).
    Returns empty list if no props available.
    """
    log.info("Fetching opening odds from 7-day history...")
    opening_map = _fetch_opening_odds_map(date_str)

    log.info("Fetching current K props for %s...", date_str)
    url  = f"{BASE_URL}/sports/{SPORT_ID}/events/{date_str}"
    data = throttled_get(url)

    props = parse_k_props(data, opening_map)
    log.info("Found %d K props", len(props))
    return props
