"""
fetch_umpires.py
Scrapes ump.news for HP umpire assignments. Returns {pitcher_name: ump_k_adj}.
Falls back to ump_k_adj = 0.0 if assignment not posted or umpire not in career table.

Known data-source issues (2026-04-17, Task A3 audit — analytics/diagnostics/a3_ump_adj.py):
  * The `www.ump.news` domain currently does not resolve from public DNS
    (8.8.8.8, 1.1.1.1 all return NXDOMAIN). As a consequence, every scrape
    attempt fails with a requests exception, scrape_hp_assignments() returns
    an empty dict, and fetch_umpires() returns 0.0 for every pitcher.
  * This matches what we see in picks_history.json: 447/447 rows (100%) have
    ump_k_adj == 0.0 exactly. There are no null / non-zero historical values.
  * The failure is logged at WARNING level by scrape_hp_assignments but the
    pipeline is built to degrade gracefully — an all-zero ump signal is
    equivalent to "no umpire effect modeled" and does not corrupt lambda.
  * Secondary (legacy) concern: even when the domain worked, assignments
    were typically posted ~10am ET, AFTER the 6am PT (9am ET) full-run
    finalization, so staked picks tended to lock with ump_k_adj=0 anyway.
    The 30-min refresh loop could in theory catch the post-10am update
    before T-30 lock, but this is best-effort.

Recovery options (out of scope for Task A3 — user decision):
  - Find a replacement data source (e.g. umpscorecards.com, MLB's own
    officials endpoint, Baseball Savant).
  - Drop ump_k_adj from the model entirely and rebalance lambda_bias.
  - Keep the current graceful-degradation behavior and treat ump effects
    as neutral unless/until a live source is restored.
"""
import json
import logging
import os
import requests
from bs4 import BeautifulSoup

from name_utils import normalize as _normalize

log = logging.getLogger(__name__)

UMP_NEWS_URL = "https://www.ump.news"

# Maps ump.news abbreviations to substrings of TheRundown full team names.
# Key = abbreviation as scraped from ump.news (upper-cased).
# Value = substring that appears in the full team name from TheRundown API.
ABBR_TO_NAME_SUBSTR = {
    "ARI": "Arizona",    "ATL": "Atlanta",     "BAL": "Baltimore",
    "BOS": "Boston",     "CHC": "Cubs",        "CWS": "White Sox",
    "CIN": "Cincinnati", "CLE": "Cleveland",   "COL": "Colorado",
    "DET": "Detroit",    "HOU": "Houston",     "KC":  "Kansas City",
    "LAA": "Angels",     "LAD": "Dodgers",     "MIA": "Miami",
    "MIL": "Milwaukee",  "MIN": "Minnesota",   "NYM": "Mets",
    "NYY": "Yankees",    "OAK": "Oakland",     "PHI": "Philadelphia",
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
    diacritical differences between ump.news ("Jose Garcia") and the career
    rates file ("José García") without silently falling back to 0.0.
    """
    with open(CAREER_RATES_PATH, "r") as f:
        raw = json.load(f)
    return {_normalize(k): v for k, v in raw.items()}


def scrape_hp_assignments() -> dict:
    """
    Scrapes ump.news for today's HP umpire assignments.
    Returns {away_team_abbr: hp_umpire_name}.
    Returns empty dict if scrape fails or assignments not yet posted.
    """
    try:
        resp = requests.get(
            UMP_NEWS_URL, timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BaseballBettingEdge/1.0)"}
        )
        resp.raise_for_status()
    except Exception as e:
        log.warning("ump.news scrape failed: %s — using neutral ump adj", e)
        return {}

    soup        = BeautifulSoup(resp.text, "html.parser")
    assignments = {}

    # ump.news lists games as rows with matchup and umpire columns.
    # Selector targets the main assignments table — adjust if site structure changes.
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        try:
            teams_cell = cells[0].get_text(strip=True)   # e.g. "NYY @ BOS"
            hp_cell    = cells[1].get_text(strip=True)   # HP umpire name
            if "@" in teams_cell and hp_cell:
                away_abbr = teams_cell.split("@")[0].strip().upper()
                if away_abbr:
                    assignments[away_abbr] = hp_cell
        except Exception:
            continue

    log.info("Scraped %d HP assignments from ump.news", len(assignments))
    return assignments


def _build_game_ump_map(assignments: dict) -> dict:
    """
    Converts {away_abbr: ump_name} from ump.news into
    {team_name_substr: ump_name} for both teams in the game.
    Each game has one HP umpire — both the away pitcher and home pitcher face the same ump.
    """
    game_ump = {}
    for abbr, ump_name in assignments.items():
        abbr_upper = abbr.upper()
        substr = ABBR_TO_NAME_SUBSTR.get(abbr_upper)
        if substr:
            game_ump[substr.lower()] = ump_name
    return game_ump


def fetch_umpires(props: list) -> dict:
    """
    Main entry point. Returns {pitcher_name: ump_k_adj} for all pitchers.
    Matches pitcher's team (full name) against ABBR_TO_NAME_SUBSTR lookup.
    Works for both home and away starters. Falls back to 0.0.
    """
    career_rates = _load_career_rates()
    assignments  = scrape_hp_assignments()
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
