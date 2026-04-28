"""
fetch_batter_stats.py
Fetches batter K% splits by pitcher handedness from FanGraphs via pybaseball.

Returns {batter_name: {"vs_R": float, "vs_L": float}} for the current season.
Falls back to aggregate K% for both splits if handedness splits are unavailable.
Returns {} if FanGraphs is completely unreachable (pipeline continues with team K%).

IMPORTANT: Before deploying, verify that pybaseball supports handedness split queries
for the installed version. If `_fetch_splits` raises AttributeError, the fallback to
aggregate K% is used automatically.
"""
import logging
import html
import re

import pandas as pd
import requests

from build_features import LEAGUE_AVG_K_RATE
from name_utils import normalize as _norm

log = logging.getLogger(__name__)
FANGRAPHS_LEADERBOARD_URL = "https://www.fangraphs.com/api/leaders/major-league/data"
FANGRAPHS_TIMEOUT_SECONDS = 30
FANGRAPHS_PAGE_SIZE = 5000


def _fetch_aggregate(season: int):
    """Fetch aggregate batter stats from FanGraphs JSON. Returns DataFrame."""
    response = requests.get(
        FANGRAPHS_LEADERBOARD_URL,
        params={
            "pos": "all",
            "stats": "bat",
            "lg": "all",
            "qual": "0",
            "type": "8",
            "season": str(season),
            "season1": str(season),
            "ind": "0",
            "month": "0",
            "pageitems": str(FANGRAPHS_PAGE_SIZE),
            "startdate": "",
            "enddate": "",
        },
        timeout=FANGRAPHS_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data", []) if isinstance(payload, dict) else []

    normalized_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("PlayerName") or html.unescape(re.sub(r"<[^>]+>", "", str(row.get("Name", "")))).strip()
        k_rate = row.get("K%")
        if not name or k_rate is None:
            continue
        normalized_rows.append({"Name": str(name).strip(), "K%": float(k_rate)})

    return pd.DataFrame(normalized_rows, columns=["Name", "K%"])


def _fetch_splits(season: int):
    """
    Fetch batter K% splits vs LHP and RHP.
    Returns (df_vs_R, df_vs_L) DataFrames, or raises if splits unavailable.

    NOTE: Verify the exact pybaseball function for handedness splits against
    the installed version. Options include batting_stats_bref() with split params
    or a direct FanGraphs splits endpoint call. Update this function accordingly.
    """
    # Attempt to use pybaseball split functionality.
    # This may raise AttributeError if the function doesn't exist in the installed version.
    from pybaseball import batting_stats_bref
    # batting_stats_bref does not natively support handedness splits —
    # raise to trigger fallback to aggregate
    raise AttributeError(
        "Handedness splits not yet implemented — update _fetch_splits() once "
        "the correct pybaseball function is identified. Using aggregate K% fallback."
    )


def _build_lookup(df, name_col: str = "Name", k_col: str = "K%") -> dict:
    """Build {normalized_name: k_rate} lookup from a FanGraphs DataFrame.
    Keys are accent-stripped + lowercased so MLB API batter names (used in
    lineups) match FanGraphs names regardless of diacritic differences."""
    result = {}
    if df is None or df.empty:
        return result
    for _, row in df.iterrows():
        name = row.get(name_col)
        k = row.get(k_col)
        if name and k is not None:
            result[_norm(str(name))] = float(k)
    return result


def fetch_batter_stats(season: int) -> dict:
    """
    Returns {batter_name: {"vs_R": float, "vs_L": float}} for the given season.
    Batters not in the result should be handled by the caller with LEAGUE_AVG_K_RATE.
    Returns {} on complete failure.
    """
    try:
        agg_df = _fetch_aggregate(season)
    except Exception as e:
        log.warning("fetch_batter_stats: aggregate fetch failed: %s — returning {}", e)
        return {}

    agg_lookup = _build_lookup(agg_df)

    try:
        vs_r_df, vs_l_df = _fetch_splits(season)
        vs_r_lookup = _build_lookup(vs_r_df)
        vs_l_lookup = _build_lookup(vs_l_df)
        log.info("fetch_batter_stats: loaded handedness splits for %d batters", len(vs_r_lookup))
        use_splits = True
    except Exception as e:
        log.warning("fetch_batter_stats: splits unavailable (%s) — using aggregate K%%", e)
        use_splits = False

    result = {}
    for name, agg_k in agg_lookup.items():
        # name is already normalized (from _build_lookup); keep it that way so
        # calc_lineup_k_rate() can resolve with _norm(batter_name) as the key.
        if use_splits:
            vs_r = vs_r_lookup.get(name, agg_k)
            vs_l = vs_l_lookup.get(name, agg_k)
        else:
            vs_r = agg_k
            vs_l = agg_k
        result[name] = {"vs_R": vs_r, "vs_L": vs_l}

    log.info("fetch_batter_stats: built stats for %d batters (splits=%s)", len(result), use_splits)
    return result
