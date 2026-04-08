"""
fetch_stats.py
Fetches pitcher and team stats from the MLB Stats API (free, no key required).
Returns a dict keyed by pitcher name with stats needed for build_features.
"""
import logging
import requests
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"


def _get(path: str, params: dict = None) -> dict:
    """GET with 3-attempt retry and exponential backoff."""
    import time
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.get(f"{MLB_BASE}{path}", params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s
    raise last_err


def _parse_ip(value) -> float:
    """
    Convert MLB's fractional IP string to decimal innings.
    MLB uses "12.1" to mean 12 full innings + 1 out (= 12.333...), not 12.1 decimal.
    The digit after the decimal is the out count (0, 1, or 2).
    """
    try:
        s     = str(value or "0").strip()
        parts = s.split(".")
        full  = int(parts[0])
        outs  = int(parts[1]) if len(parts) > 1 else 0
        return full + outs / 3.0
    except (ValueError, IndexError):
        return 0.0


def _k9_from_splits(splits: list) -> float | None:
    """Extract K/9 from an MLB stats splits list."""
    for split in splits:
        stat = split.get("stat", {})
        ip   = _parse_ip(stat.get("inningsPitched", 0))
        so   = int(stat.get("strikeOuts", 0) or 0)
        if ip > 0:
            return round((so / ip) * 9, 2)
    return None


def fetch_pitcher_stats(person_id: int, season: int) -> dict:
    """Fetch season K/9, career K/9, recent 5-start K/9, and IP for one pitcher."""
    # Season stats — API returns {"stats": []} when no starts yet (e.g. Opening Day)
    season_data   = _get(f"/people/{person_id}/stats", {
        "stats": "season", "group": "pitching", "season": season
    })
    season_splits = (season_data.get("stats") or [{}])[0].get("splits", [])
    season_k9     = _k9_from_splits(season_splits) or 0.0
    ip            = _parse_ip(
        (season_splits[0].get("stat", {}) if season_splits else {}).get("inningsPitched", 0)
    )

    # Career stats
    career_data   = _get(f"/people/{person_id}/stats", {
        "stats": "career", "group": "pitching"
    })
    career_splits = (career_data.get("stats") or [{}])[0].get("splits", [])
    career_k9     = _k9_from_splits(career_splits) or season_k9

    # Recent game log — also try prior season if current season is empty
    log_data      = _get(f"/people/{person_id}/stats", {
        "stats": "gameLog", "group": "pitching", "season": season, "limit": 5
    })
    starts        = (log_data.get("stats") or [{}])[0].get("splits", [])
    if not starts:
        # Opening Day / early season: fall back to last season's game log
        prior_data = _get(f"/people/{person_id}/stats", {
            "stats": "gameLog", "group": "pitching", "season": season - 1, "limit": 5
        })
        starts     = (prior_data.get("stats") or [{}])[0].get("splits", [])
    starts_count  = len(starts)
    recent_k9     = _k9_from_splits(starts) if starts_count >= 3 else season_k9

    # Average IP per start from last 5 starts — used as expected_innings in calc_lambda.
    # Falls back to 5.5 if fewer than 3 starts (e.g. early season, call-ups).
    if starts_count >= 3:
        ip_values    = [_parse_ip(s.get("stat", {}).get("inningsPitched", 0)) for s in starts]
        avg_ip_last5 = round(sum(ip_values) / len(ip_values), 2)
    else:
        avg_ip_last5 = 5.5

    return {
        "season_k9":              season_k9,
        "career_k9":              career_k9,
        "recent_k9":              recent_k9,
        "starts_count":           starts_count,
        "innings_pitched_season": ip,
        "avg_ip_last5":           avg_ip_last5,
    }


def fetch_team_k_rate(team_id: int, season: int) -> tuple[float, int]:
    """Fetch a team's season batter K% and games played.
    Returns (k_rate, games_played). Falls back to (0.227, 0) on missing data."""
    data   = _get(f"/teams/{team_id}/stats", {
        "stats": "season", "group": "hitting", "season": season
    })
    splits = data.get("stats", [{}])[0].get("splits", [])
    for split in splits:
        stat = split.get("stat", {})
        pa   = int(stat.get("plateAppearances", 0) or 0)
        so   = int(stat.get("strikeOuts", 0) or 0)
        gp   = int(stat.get("gamesPlayed", 0) or 0)
        if pa > 0:
            return round(so / pa, 4), gp
    return 0.227, 0  # fall back to league average, no games


def fetch_stats(date_str: str, pitcher_names: list) -> dict:
    """
    Main entry point. Returns {pitcher_name: stats_dict} for all pitchers on date_str.
    Fetches schedules for date_str AND date_str+1 to match the UTC-offset behaviour
    of fetch_odds (ET evening games are filed under the next UTC day).
    Skips pitchers where the confirmed starter cannot be found in the schedule.
    """
    season   = datetime.strptime(date_str, "%Y-%m-%d").year
    next_day = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    # Build combined date list for the range query (MLB API supports startDate/endDate)
    schedule = _get("/schedule", {
        "sportId":   1,
        "startDate": date_str,
        "endDate":   next_day,
        "hydrate":   "probablePitcher,team",
    })

    stats_by_name = {}
    for date_block in schedule.get("dates", []):
        for game in date_block.get("games", []):
            for side in ("away", "home"):
                team_data = game.get("teams", {}).get(side, {})
                pitcher   = team_data.get("probablePitcher")
                if not pitcher:
                    continue
                name = pitcher.get("fullName", "")
                if name not in pitcher_names:
                    continue

                pid    = pitcher["id"]
                throws = pitcher.get("pitchHand", {}).get("code", "R")
                team_id = team_data.get("team", {}).get("id")

                try:
                    pstats = fetch_pitcher_stats(pid, season)
                except Exception as e:
                    log.warning("Stats fetch failed for %s: %s", name, e)
                    continue

                opp_side    = "home" if side == "away" else "away"
                opp_team    = game.get("teams", {}).get(opp_side, {}).get("team", {})
                opp_team_id = opp_team.get("id")
                try:
                    opp_k_rate, opp_games_played = fetch_team_k_rate(opp_team_id, season) if opp_team_id else (0.227, 0)
                except Exception as e:
                    log.warning("Team K rate fetch failed for %s: %s", opp_team.get("name"), e)
                    opp_k_rate, opp_games_played = 0.227, 0

                team_name     = team_data.get("team", {}).get("name", "")
                opp_team_name = opp_team.get("name", "")
                stats_by_name[name] = {
                    **pstats,
                    "throws":           throws,
                    "opp_k_rate":       opp_k_rate,
                    "opp_games_played": opp_games_played,
                    "team":             team_name,
                    "opp_team":         opp_team_name,
                }

    return stats_by_name
