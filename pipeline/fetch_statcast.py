"""
fetch_statcast.py
Fetches pitcher SwStr% from FanGraphs via PyBaseball — current season and career average.
Returns {pitcher_name: {"swstr_pct": float, "career_swstr_pct": float | None}} where
swstr_pct values are decimals (0.134 = 13.4%).

Career average is the 3-season average prior to the current season. Used in
build_features.calc_swstr_delta_k9() to compute a career-relative delta (additive K/9
adjustment) instead of a raw-vs-league-average multiplier, which double-counted the
pitcher's swing-and-miss ability already embedded in their K/9 rates.

Falls back to {"swstr_pct": LEAGUE_AVG_SWSTR, "career_swstr_pct": None} on any failure.
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


def _build_swstr_lookup(df, swstr_col: str) -> dict:
    """Build {normalized_name: swstr_pct} from a FanGraphs DataFrame."""
    lookup = {}
    for _, row in df.iterrows():
        name = row.get("Name", "")
        if not name:
            continue
        lookup[name] = _parse_swstr(row[swstr_col])
        lookup[name.lower()] = lookup[name]   # case-insensitive key
    return lookup


def _get_swstr_col(df) -> str | None:
    return next((c for c in df.columns if "SwStr" in c), None)


def fetch_swstr(season: int, pitcher_names: list) -> dict:
    """
    Main entry point. Returns {pitcher_name: {"swstr_pct": float, "career_swstr_pct": float | None}}.

    - swstr_pct:        current season SwStr% (decimal). Falls back to LEAGUE_AVG_SWSTR.
    - career_swstr_pct: average SwStr% over the 3 seasons prior to `season`.
                        None if unavailable (rookie, or API failure).

    Fetches two FanGraphs tables: current season and a 3-year career window.
    qual=0 includes pitchers with <1 IP — catches openers and early-season starters.
    """
    fallback = {name: {"swstr_pct": LEAGUE_AVG_SWSTR, "career_swstr_pct": None}
                for name in pitcher_names}

    # ── Current season ────────────────────────────────────────────────────────
    try:
        df_current = pitching_stats(season, season, qual=0)
    except Exception as e:
        log.warning("fetch_swstr: current-season pitching_stats() failed: %s — using neutral for all", e)
        return fallback

    if df_current is None or df_current.empty:
        log.warning("fetch_swstr: empty current-season DataFrame — using neutral for all")
        return fallback

    swstr_col = _get_swstr_col(df_current)
    if not swstr_col:
        log.warning("fetch_swstr: SwStr%% column not found in current DataFrame — using neutral for all")
        return fallback

    current_lookup = _build_swstr_lookup(df_current, swstr_col)

    # ── Career (last 3 complete seasons) ──────────────────────────────────────
    career_lookup: dict = {}
    try:
        career_start = season - 3
        career_end   = season - 1
        df_career = pitching_stats(career_start, career_end, qual=0)
        if df_career is not None and not df_career.empty:
            c_col = _get_swstr_col(df_career)
            if c_col:
                career_lookup = _build_swstr_lookup(df_career, c_col)
            else:
                log.info("fetch_swstr: SwStr%% column not found in career DataFrame — career baseline unavailable")
        else:
            log.info("fetch_swstr: empty career DataFrame — career baseline unavailable")
    except Exception as e:
        log.info("fetch_swstr: career pitching_stats() failed: %s — career baseline unavailable", e)

    # ── Assemble results ──────────────────────────────────────────────────────
    result = {}
    for name in pitcher_names:
        current = current_lookup.get(name) or current_lookup.get(name.lower())
        if current is None:
            log.info("fetch_swstr: '%s' not found in FanGraphs current season — using neutral", name)
            current = LEAGUE_AVG_SWSTR

        career = career_lookup.get(name) or career_lookup.get(name.lower())
        # career is None for rookies or when the career fetch failed — handled gracefully downstream

        log.info("fetch_swstr: %s → SwStr%% %.1f%% (career: %s)",
                 name, current * 100,
                 f"{career * 100:.1f}%" if career is not None else "n/a")
        result[name] = {"swstr_pct": current, "career_swstr_pct": career}

    return result
