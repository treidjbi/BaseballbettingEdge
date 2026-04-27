"""
fetch_statcast.py
Fetches pitcher SwStr% from FanGraphs leaderboard JSON - current season and career average.
Returns {pitcher_name: {"swstr_pct": float, "career_swstr_pct": float | None}} where
swstr_pct values are decimals (0.134 = 13.4%).

Career average is the 3-season average prior to the current season. Used in
build_features.calc_swstr_delta_k9() to compute a career-relative delta (additive K/9
adjustment) instead of a raw-vs-league-average multiplier, which double-counted the
pitcher's swing-and-miss ability already embedded in their K/9 rates.

Falls back to {"swstr_pct": LEAGUE_AVG_SWSTR, "career_swstr_pct": None} on any failure.
"""
import html
import logging
import re

import requests

from name_utils import normalize as _norm

log = logging.getLogger(__name__)

LEAGUE_AVG_SWSTR = 0.110   # FanGraphs historical MLB average
FANGRAPHS_LEADERBOARD_URL = "https://www.fangraphs.com/api/leaders/major-league/data"
FANGRAPHS_TIMEOUT_SECONDS = 30
FANGRAPHS_PAGE_SIZE = 5000
FANGRAPHS_MAX_RETRIES = 3


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


def _strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def _extract_player_name(row: dict) -> str:
    return str(row.get("PlayerName") or _strip_html(str(row.get("Name", "")))).strip()


def _build_swstr_lookup(rows: list[dict]) -> dict:
    """Build {normalized_name: swstr_pct} from FanGraphs leaderboard rows.
    Keys are accent-stripped + lowercased via name_utils.normalize so that
    FanGraphs names (e.g. 'Shota Imanaga') match TheRundown names ('Shota Imanaga')."""
    lookup = {}
    for row in rows:
        name = _extract_player_name(row)
        if not name:
            continue
        lookup[_norm(name)] = _parse_swstr(row.get("SwStr%"))
    return lookup


def _leaderboard_params(start_season: int, end_season: int, page_num: int | None = None) -> dict:
    params = {
        "pos": "all",
        "stats": "pit",
        "lg": "all",
        "qual": "0",
        "type": "8",
        "season": str(end_season),
        "season1": str(start_season),
        "ind": "0",
        "month": "0",
        "pageitems": str(FANGRAPHS_PAGE_SIZE),
        "startdate": "",
        "enddate": "",
    }
    if page_num and page_num > 1:
        params["pagenum"] = str(page_num)
    return params


def _validate_rows(rows, start_season: int, end_season: int, page_num: int) -> list[dict] | None:
    if not isinstance(rows, list):
        log.info(
            "fetch_swstr: FanGraphs data rows malformed for %s-%s page %s",
            start_season,
            end_season,
            page_num,
        )
        return None

    if any(not isinstance(row, dict) for row in rows):
        log.info(
            "fetch_swstr: FanGraphs row entries malformed for %s-%s page %s",
            start_season,
            end_season,
            page_num,
        )
        return None

    return rows


def _parse_total_count(payload: dict, row_count: int, start_season: int, end_season: int, page_num: int) -> int | None:
    raw_total_count = payload.get("totalCount", row_count)
    try:
        total_count = int(raw_total_count)
    except (TypeError, ValueError):
        log.info(
            "fetch_swstr: FanGraphs totalCount malformed for %s-%s page %s",
            start_season,
            end_season,
            page_num,
        )
        return None

    if total_count < row_count:
        log.info(
            "fetch_swstr: FanGraphs totalCount smaller than rows returned for %s-%s page %s",
            start_season,
            end_season,
            page_num,
        )
        return None

    return total_count


def _fetch_swstr_page(start_season: int, end_season: int, page_num: int) -> tuple[list[dict], int] | None:
    last_error = None

    for attempt in range(1, FANGRAPHS_MAX_RETRIES + 1):
        try:
            response = requests.get(
                FANGRAPHS_LEADERBOARD_URL,
                params=_leaderboard_params(start_season, end_season, page_num),
                timeout=FANGRAPHS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as e:
            last_error = e
            log.info(
                "fetch_swstr: FanGraphs request attempt %s/%s failed for %s-%s page %s: %s",
                attempt,
                FANGRAPHS_MAX_RETRIES,
                start_season,
                end_season,
                page_num,
                e,
            )
            continue

        if not isinstance(payload, dict):
            last_error = ValueError("payload was not a dict")
            log.info(
                "fetch_swstr: FanGraphs payload malformed for %s-%s page %s on attempt %s/%s",
                start_season,
                end_season,
                page_num,
                attempt,
                FANGRAPHS_MAX_RETRIES,
            )
            continue

        rows = _validate_rows(payload.get("data"), start_season, end_season, page_num)
        if rows is None:
            last_error = ValueError("payload data malformed")
            continue

        total_count = _parse_total_count(payload, len(rows), start_season, end_season, page_num)
        if total_count is None:
            last_error = ValueError("payload totalCount malformed")
            continue

        return rows, total_count

    log.info(
        "fetch_swstr: FanGraphs window unusable for %s-%s page %s after retries: %s",
        start_season,
        end_season,
        page_num,
        last_error,
    )
    return None


def _fetch_swstr_lookup_result_for_window(start_season: int, end_season: int) -> tuple[dict, bool]:
    """Fetch one FanGraphs window and return ({normalized_name: swstr_pct}, usable)."""
    first_page = _fetch_swstr_page(start_season, end_season, page_num=1)
    if first_page is None:
        return {}, False

    rows, total_count = first_page
    if not rows:
        return {}, True

    all_rows = list(rows)
    next_page_num = 2
    while len(all_rows) < total_count:
        page_result = _fetch_swstr_page(start_season, end_season, page_num=next_page_num)
        if page_result is None:
            log.info(
                "fetch_swstr: FanGraphs window incomplete for %s-%s because page %s was unusable",
                start_season,
                end_season,
                next_page_num,
            )
            return {}, False

        page_rows, page_total_count = page_result
        if page_total_count != total_count:
            log.info(
                "fetch_swstr: FanGraphs totalCount changed mid-fetch for %s-%s (%s -> %s)",
                start_season,
                end_season,
                total_count,
                page_total_count,
            )
            return {}, False
        if not page_rows:
            log.info(
                "fetch_swstr: FanGraphs pagination truncated for %s-%s at page %s (%s/%s rows)",
                start_season,
                end_season,
                next_page_num,
                len(all_rows),
                total_count,
            )
            return {}, False

        all_rows.extend(page_rows)
        next_page_num += 1

    return _build_swstr_lookup(all_rows), True


def _fetch_swstr_lookup_for_window(start_season: int, end_season: int) -> dict:
    """Fetch one FanGraphs window and return {normalized_name: swstr_pct}."""
    lookup, _ = _fetch_swstr_lookup_result_for_window(start_season, end_season)
    return lookup


def _fetch_career_swstr_lookup_result(season: int) -> tuple[dict, bool]:
    """Return (3-year pre-season SwStr averages keyed by name, usable flag)."""
    sums = {}
    counts = {}

    for yr in range(season - 3, season):
        lookup, usable = _fetch_swstr_lookup_result_for_window(yr, yr)
        if not usable:
            log.info(
                "fetch_swstr: career baseline unavailable because %s season fetch was unusable",
                yr,
            )
            return {}, False
        for name, swstr in lookup.items():
            sums[name] = sums.get(name, 0.0) + swstr
            counts[name] = counts.get(name, 0) + 1

    return {name: sums[name] / counts[name] for name in sums if counts[name] > 0}, True


def _fallback_result(pitcher_names: list, *, current_usable: bool, career_usable: bool) -> dict:
    result = {
        name: {"swstr_pct": LEAGUE_AVG_SWSTR, "career_swstr_pct": None}
        for name in pitcher_names
    }
    result["__meta__"] = {
        "current_usable": current_usable,
        "career_usable": career_usable,
    }
    return result


def fetch_swstr(season: int, pitcher_names: list) -> dict:
    """
    Main entry point. Returns {pitcher_name: {"swstr_pct": float, "career_swstr_pct": float | None}}.

    - swstr_pct:        current season SwStr% (decimal). Falls back to LEAGUE_AVG_SWSTR.
    - career_swstr_pct: average SwStr% over the 3 seasons prior to `season`.
                        None if unavailable (rookie, or API failure).

    qual=0 includes pitchers with <1 IP - catches openers and early-season starters.
    """
    current_lookup, current_usable = _fetch_swstr_lookup_result_for_window(season, season)
    if not current_usable or not current_lookup:
        log.warning(
            "fetch_swstr: current-season lookup empty for %s - using neutral for all",
            season,
        )
        return _fallback_result(
            pitcher_names,
            current_usable=False,
            career_usable=False,
        )

    career_lookup, career_usable = _fetch_career_swstr_lookup_result(season)
    if career_usable and not career_lookup:
        log.info(
            "fetch_swstr: career baseline fetched cleanly for %s but no prior-season rows matched",
            season,
        )
    elif not career_usable:
        log.warning(
            "fetch_swstr: career baseline unavailable for %s - SwStr deltas will be neutral",
            season,
        )

    result = {}
    for name in pitcher_names:
        key = _norm(name)
        current = current_lookup.get(key)
        if current is None:
            log.info("fetch_swstr: '%s' not found in FanGraphs current season - using neutral", name)
            current = LEAGUE_AVG_SWSTR

        career = career_lookup.get(key)

        log.info(
            "fetch_swstr: %s -> SwStr%% %.1f%% (career: %s)",
            name,
            current * 100,
            f"{career * 100:.1f}%" if career is not None else "n/a",
        )
        result[name] = {"swstr_pct": current, "career_swstr_pct": career}

    result["__meta__"] = {
        "current_usable": True,
        "career_usable": career_usable,
    }
    return result
