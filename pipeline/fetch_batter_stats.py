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
from build_features import LEAGUE_AVG_K_RATE
from name_utils import normalize as _norm

log = logging.getLogger(__name__)


def _fetch_aggregate(season: int):
    """Fetch aggregate batter stats from FanGraphs. Returns DataFrame."""
    from pybaseball import batting_stats
    return batting_stats(season, qual=0)


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
