"""
fetch_statcast.py
Fetches pitcher SwStr% (swinging strike rate) from FanGraphs via PyBaseball.
Returns {pitcher_name: swstr_pct} where swstr_pct is a decimal (0.134 = 13.4%).
Falls back to LEAGUE_AVG_SWSTR (neutral multiplier = 1.0) on any failure.
"""
import logging
from pybaseball import pitching_stats

log = logging.getLogger(__name__)

LEAGUE_AVG_SWSTR = 0.110   # FanGraphs historical MLB average


def _parse_swstr(value) -> float:
    """
    Normalize SwStr% to a decimal float.
    PyBaseball returns decimals (0.134) in recent versions.
    Guard against percentage strings ('13.4 %') just in case.
    """
    try:
        s = str(value).strip().replace("%", "").strip()
        v = float(s)
        # If value looks like a percentage (e.g. 13.4) rather than a decimal (0.134)
        if v > 1.0:
            v = v / 100.0
        return v if v > 0 else LEAGUE_AVG_SWSTR
    except (ValueError, TypeError):
        return LEAGUE_AVG_SWSTR


def fetch_swstr(season: int, pitcher_names: list) -> dict:
    """
    Main entry point. Returns {pitcher_name: swstr_pct} for all pitchers.
    Fetches the full FanGraphs pitching stats table once, then filters.
    Falls back to LEAGUE_AVG_SWSTR for any pitcher not found.

    Note: qual=0 includes pitchers with <1 IP — catches openers and early-season starters.
    """
    fallback = {name: LEAGUE_AVG_SWSTR for name in pitcher_names}

    try:
        df = pitching_stats(season, season, qual=0)
    except Exception as e:
        log.warning("fetch_swstr: pitching_stats() failed: %s — using neutral for all", e)
        return fallback

    if df is None or df.empty:
        log.warning("fetch_swstr: empty DataFrame returned — using neutral for all")
        return fallback

    # Normalize column name — PyBaseball uses 'SwStr%'
    swstr_col = next((c for c in df.columns if "SwStr" in c), None)
    if not swstr_col:
        log.warning("fetch_swstr: SwStr%% column not found in DataFrame — using neutral for all")
        return fallback

    result = {}
    for name in pitcher_names:
        # FanGraphs names may differ from MLB API names (accents, suffixes).
        # Try exact match first, then case-insensitive match.
        row = df[df["Name"] == name]
        if row.empty:
            row = df[df["Name"].str.lower() == name.lower()]
        if row.empty:
            log.info("fetch_swstr: '%s' not found in FanGraphs — using neutral", name)
            result[name] = LEAGUE_AVG_SWSTR
            continue

        raw   = row.iloc[0][swstr_col]
        swstr = _parse_swstr(raw)
        log.info("fetch_swstr: %s → SwStr%% %.1f%%", name, swstr * 100)
        result[name] = swstr

    return result
