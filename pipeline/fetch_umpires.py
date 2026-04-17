"""
fetch_umpires.py
Fetches HP umpire assignments from the MLB Stats API schedule endpoint
(hydrate=officials). Returns {pitcher_name: ump_k_adj}.
Falls back to ump_k_adj = 0.0 if the assignment is not yet posted or the
umpire is not in the local career_k_rates table.

Data source (2026-04-17 cutover — Task A3):
  * The previous source (www.ump.news) went NXDOMAIN; this module now calls
    https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}&hydrate=officials
    and parses each game's `officials` array for the `officialType == "Home Plate"`
    entry.
  * Completed games: `officials` is populated reliably (100% in spot checks).
  * Pre-game on game-day: `officials` fills in closer to first pitch (same
    timing profile as ump.news was). The 30-min refresh loop catches
    post-post assignments before T-30 lock.
  * Each game has one HP umpire — both the home and away starter face the
    same ump. The returned dict is keyed by away-team abbreviation so the
    downstream _build_game_ump_map / fetch_umpires logic is unchanged.

Known coverage cap (NOT fixed here — separate follow-up task):
  * `data/umpires/career_k_rates.json` has only 30 umpires and includes
    retired names (Angel Hernandez, Ted Barrett, Paul Nauert, Bill Miller).
    Real 2026 match rate vs live MLB assignments is ~21% (62 unique HP umps
    actually working). Most calls still end up at 0.0 until the table is
    expanded. Expansion is tracked as a follow-up.
"""
import json
import logging
import os
import requests

from name_utils import normalize as _normalize

log = logging.getLogger(__name__)

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"

# Maps 3-letter MLB abbreviations to substrings of TheRundown full team names.
# Key = our canonical abbreviation.
# Value = substring that appears in the full team name from TheRundown API
# *and* in the MLB Stats API's `teams.{home,away}.team.name` field (both
# sources use the same "City Nickname" full-name format).
ABBR_TO_NAME_SUBSTR = {
    "ARI": "Arizona",    "ATL": "Atlanta",     "BAL": "Baltimore",
    "BOS": "Boston",     "CHC": "Cubs",        "CWS": "White Sox",
    "CIN": "Cincinnati", "CLE": "Cleveland",   "COL": "Colorado",
    "DET": "Detroit",    "HOU": "Houston",     "KC":  "Kansas City",
    "LAA": "Angels",     "LAD": "Dodgers",     "MIA": "Miami",
    "MIL": "Milwaukee",  "MIN": "Minnesota",   "NYM": "Mets",
    "NYY": "Yankees",    "OAK": "Athletics",   "PHI": "Philadelphia",
    "PIT": "Pittsburgh", "SD":  "San Diego",   "SEA": "Seattle",
    "SF":  "San Francisco", "STL": "St. Louis", "TB": "Tampa",
    "TEX": "Texas",      "TOR": "Toronto",     "WSH": "Washington",
}
CAREER_RATES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "umpires", "career_k_rates.json"
)


def _load_career_rates() -> dict:
    """Return career K adjustments keyed by normalized umpire name.

    Normalizes keys (lower + accent-strip) so lookups tolerate casing or
    diacritical differences between the MLB API ("Jose Garcia") and the
    career rates file ("José García") without silently falling back to 0.0.
    """
    with open(CAREER_RATES_PATH, "r") as f:
        raw = json.load(f)
    return {_normalize(k): v for k, v in raw.items()}


def _abbr_for_team_name(name: str) -> str | None:
    """Reverse-lookup a 3-letter abbreviation from a full team name.

    MLB Stats API returns team names like "Chicago Cubs", "New York Yankees".
    We match by checking which ABBR_TO_NAME_SUBSTR value appears (case-insensitive)
    in the full name and returning the corresponding key. Returns None if no
    entry matches — the caller logs and skips the game.

    Ambiguity note: the substrings in ABBR_TO_NAME_SUBSTR are chosen so that
    each MLB team name matches exactly one entry (e.g. "Chicago Cubs" matches
    only "Cubs", not the "White Sox" substring for CWS). See
    test_abbr_map_values_match_career_rates_team_substrings for the guard.
    """
    if not name:
        return None
    name_lower = name.lower()
    for abbr, substr in ABBR_TO_NAME_SUBSTR.items():
        if substr.lower() in name_lower:
            return abbr
    return None


def fetch_hp_assignments(date_str: str) -> dict:
    """
    Fetches HP umpire assignments for `date_str` (YYYY-MM-DD) from the MLB
    Stats API schedule endpoint with officials hydrate.

    Returns {away_team_abbr: hp_umpire_name}. Empty dict on network/HTTP
    failure or if no games have officials populated yet. Games whose team
    names don't reverse-lookup to a known abbreviation are skipped.
    """
    try:
        resp = requests.get(
            MLB_SCHEDULE_URL,
            params={"sportId": 1, "date": date_str, "hydrate": "officials"},
            timeout=15,
            headers={"User-Agent": "BaseballBettingEdge/1.0"},
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        log.warning(
            "MLB schedule fetch failed for %s: %s — using neutral ump adj",
            date_str, e,
        )
        return {}

    assignments: dict = {}
    dates = payload.get("dates") or []
    for date_block in dates:
        for game in date_block.get("games", []) or []:
            officials = game.get("officials") or []
            hp_name = None
            for off in officials:
                if off.get("officialType") == "Home Plate":
                    hp_name = (off.get("official") or {}).get("fullName")
                    break
            if not hp_name:
                # Partial data is OK — officials fill in closer to game time.
                continue

            teams = game.get("teams") or {}
            away_name = ((teams.get("away") or {}).get("team") or {}).get("name", "")
            home_name = ((teams.get("home") or {}).get("team") or {}).get("name", "")

            away_abbr = _abbr_for_team_name(away_name)
            if away_abbr:
                assignments[away_abbr] = hp_name
            else:
                # Unknown team name — don't crash, just warn once per miss.
                log.warning(
                    "MLB schedule: no ABBR_TO_NAME_SUBSTR match for '%s' (vs '%s'); skipping",
                    away_name, home_name,
                )

    log.info("Fetched %d HP assignments from MLB Stats API for %s",
             len(assignments), date_str)
    return assignments


def _build_game_ump_map(assignments: dict) -> dict:
    """
    Converts {away_abbr: ump_name} into {team_name_substr: ump_name}.
    Each game has one HP umpire — both the away pitcher and home pitcher
    face the same ump.

    Note: keys are the AWAY team's name substring only. fetch_umpires()
    covers the home starter by checking BOTH prop["team"] and
    prop["opp_team"] against these keys (both pitchers face the same HP).
    """
    game_ump = {}
    for abbr, ump_name in assignments.items():
        abbr_upper = abbr.upper()
        substr = ABBR_TO_NAME_SUBSTR.get(abbr_upper)
        if substr:
            game_ump[substr.lower()] = ump_name
    return game_ump


def fetch_umpires(props: list, date_str: str) -> dict:
    """
    Main entry point. Returns {pitcher_name: ump_k_adj} for all pitchers.
    Matches pitcher's team (full name) against ABBR_TO_NAME_SUBSTR lookup.
    Works for both home and away starters. Falls back to 0.0.
    """
    career_rates = _load_career_rates()
    assignments  = fetch_hp_assignments(date_str)
    game_ump     = _build_game_ump_map(assignments)

    result = {}
    for prop in props:
        pitcher  = prop["pitcher"]
        # Check both team and opp_team — either pitcher (home or away) faces the same HP ump
        team_names = [
            prop.get("team", "").lower(),
            prop.get("opp_team", "").lower(),
        ]

        ump_name = None
        for substr, name in game_ump.items():
            if any(substr in t for t in team_names):
                ump_name = name
                break

        ump_key = _normalize(ump_name) if ump_name else None
        if ump_key and ump_key in career_rates:
            adj = career_rates[ump_key]
            log.info("Pitcher %s: ump %s → adj %+.2f", pitcher, ump_name, adj)
            result[pitcher] = adj
        else:
            if ump_name:
                log.info("Umpire '%s' not in career table — using 0 for %s", ump_name, pitcher)
            else:
                log.info("No HP assignment found for %s — using 0", pitcher)
            result[pitcher] = 0.0

    return result
