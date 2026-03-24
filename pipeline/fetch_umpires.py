"""
fetch_umpires.py
Scrapes ump.news for HP umpire assignments. Returns {pitcher_name: ump_k_adj}.
Falls back to ump_k_adj = 0.0 if assignment not posted or umpire not in career table.
Note: Assignments typically posted ~10am ET — 9am pipeline run may return all zeros.
"""
import json
import logging
import os
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

UMP_NEWS_URL      = "https://www.ump.news"
CAREER_RATES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "umpires", "career_k_rates.json"
)


def _load_career_rates() -> dict:
    with open(CAREER_RATES_PATH, "r") as f:
        return json.load(f)


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


def fetch_umpires(props: list) -> dict:
    """
    Main entry point. Returns {pitcher_name: ump_k_adj} for all pitchers.
    Matches by away team abbreviation (best-effort). Falls back to 0.0.
    """
    career_rates = _load_career_rates()
    assignments  = scrape_hp_assignments()

    result = {}
    for prop in props:
        pitcher  = prop["pitcher"]
        team_str = prop.get("team", "").upper()

        # Best-effort match: check if any scraped abbreviation appears in the team name
        ump_name = None
        for abbr, name in assignments.items():
            if abbr in team_str or team_str.startswith(abbr):
                ump_name = name
                break

        if ump_name and ump_name in career_rates:
            adj = career_rates[ump_name]
            log.info("Pitcher %s: ump %s → adj %+.2f", pitcher, ump_name, adj)
            result[pitcher] = adj
        else:
            if ump_name:
                log.info(
                    "Umpire '%s' not in career table — using 0 for %s", ump_name, pitcher
                )
            else:
                log.info("No HP assignment found for %s — using 0", pitcher)
            result[pitcher] = 0.0

    return result
