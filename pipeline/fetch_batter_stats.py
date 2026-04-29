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
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
import warnings

import pandas as pd
import requests
from bs4 import MarkupResemblesLocatorWarning
from pybaseball import get_splits, playerid_reverse_lookup

from build_features import LEAGUE_AVG_K_RATE
from name_utils import normalize as _norm

log = logging.getLogger(__name__)
FANGRAPHS_LEADERBOARD_URL = "https://www.fangraphs.com/api/leaders/major-league/data"
FANGRAPHS_TIMEOUT_SECONDS = 30
FANGRAPHS_PAGE_SIZE = 5000
BATTER_SPLIT_CACHE_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_SPLIT_COLLECTION_MAX_NEW = int(os.environ.get("BATTER_SPLIT_COLLECTION_MAX_NEW", "4"))


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


def _extract_bref_platoon_split_rates(table: pd.DataFrame) -> dict:
    """Extract K% collection fields from pybaseball/baseball-reference splits."""
    result = {}
    for split_name, output_key in (("vs RHP", "vs_R"), ("vs LHP", "vs_L")):
        try:
            row = table.loc[("Platoon Splits", split_name)]
        except KeyError:
            continue
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        try:
            pa = int(row.get("PA") or 0)
            so = int(row.get("SO") or 0)
        except (TypeError, ValueError):
            continue
        if pa <= 0:
            continue
        result[output_key] = {
            "pa": pa,
            "so": so,
            "k_rate": round(so / pa, 4),
        }
    return result


def _fetch_bref_platoon_split_rates(bbref_id: str, season: int) -> dict:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)
        table = get_splits(bbref_id, season)
    return _extract_bref_platoon_split_rates(table)


def _load_split_cache(cache_path: Path, season: int) -> dict:
    try:
        payload = json.loads(cache_path.read_text())
    except Exception:
        payload = {}
    if payload.get("season") != season:
        payload = {}
    payload.setdefault("season", season)
    payload.setdefault("source", "baseball-reference via pybaseball.get_splits")
    payload.setdefault("projection_status", "collection_only")
    payload.setdefault("batters", {})
    return payload


def _flatten_lineup_batter_candidates(lineups: list[list[dict] | None]) -> dict[int, dict]:
    candidates: dict[int, dict] = {}
    for lineup in lineups:
        if not lineup:
            continue
        for batter in lineup:
            mlbam_id = batter.get("mlbam_id")
            if mlbam_id is None:
                continue
            try:
                parsed_id = int(mlbam_id)
            except (TypeError, ValueError):
                continue
            candidates.setdefault(
                parsed_id,
                {
                    "name": batter.get("name", ""),
                    "bats": batter.get("bats", ""),
                    "mlbam_id": parsed_id,
                },
            )
    return candidates


def _reverse_lookup_bbref_ids(mlbam_ids: list[int]) -> dict[int, str]:
    if not mlbam_ids:
        return {}
    lookup = playerid_reverse_lookup(mlbam_ids, key_type="mlbam")
    result: dict[int, str] = {}
    for _, row in lookup.iterrows():
        mlbam_id = row.get("key_mlbam")
        bbref_id = row.get("key_bbref")
        if pd.isna(mlbam_id) or pd.isna(bbref_id) or not bbref_id:
            continue
        result[int(mlbam_id)] = str(bbref_id)
    return result


def collect_batter_split_samples(
    lineups: list[list[dict] | None],
    season: int,
    *,
    cache_path: Path | None = None,
    max_new: int = DEFAULT_SPLIT_COLLECTION_MAX_NEW,
) -> dict:
    """Collect real batter vs-RHP/vs-LHP split samples without using them in projection.

    This is intentionally collection-only during the soak period. The projection
    caller continues to consume aggregate FanGraphs K% plus league platoon deltas
    until the collected split cache is audited and explicitly promoted.
    """
    cache_path = cache_path or (BATTER_SPLIT_CACHE_DIR / f"batter_splits_{season}.json")
    cache = _load_split_cache(cache_path, season)
    batters = cache.setdefault("batters", {})
    candidates = _flatten_lineup_batter_candidates(lineups)
    if not candidates:
        return {
            "projection_status": "collection_only",
            "requested_batters": 0,
            "already_cached": 0,
            "attempted": 0,
            "collected": 0,
            "failed": 0,
            "queued_not_attempted": 0,
            "cache_size": len(batters),
            "errors": [],
        }
    uncached = [
        candidate
        for mlbam_id, candidate in candidates.items()
        if f"mlbam:{mlbam_id}" not in batters
    ]
    missing = uncached[:max(0, max_new)]

    summary = {
        "projection_status": "collection_only",
        "requested_batters": len(candidates),
        "already_cached": len(candidates) - len(uncached),
        "attempted": len(missing),
        "collected": 0,
        "failed": 0,
        "queued_not_attempted": max(0, len(uncached) - len(missing)),
        "cache_size": len(batters),
        "errors": [],
    }

    if missing:
        bbref_by_mlbam = _reverse_lookup_bbref_ids([b["mlbam_id"] for b in missing])
        for batter in missing:
            mlbam_id = batter["mlbam_id"]
            bbref_id = bbref_by_mlbam.get(mlbam_id)
            if not bbref_id:
                summary["failed"] += 1
                if len(summary["errors"]) < 5:
                    summary["errors"].append(f"{batter.get('name')}: no bbref id")
                continue
            try:
                splits = _fetch_bref_platoon_split_rates(bbref_id, season)
            except Exception as exc:
                summary["failed"] += 1
                if len(summary["errors"]) < 5:
                    summary["errors"].append(f"{batter.get('name')}: {type(exc).__name__}: {exc}")
                continue
            if not splits:
                summary["failed"] += 1
                if len(summary["errors"]) < 5:
                    summary["errors"].append(f"{batter.get('name')}: no platoon split rows")
                continue
            batters[f"mlbam:{mlbam_id}"] = {
                "name": batter.get("name", ""),
                "bats": batter.get("bats", ""),
                "mlbam_id": mlbam_id,
                "bbref_id": bbref_id,
                "season": season,
                **splits,
            }
            summary["collected"] += 1

    summary["cache_size"] = len(batters)
    summary["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cache["updated_at"] = summary["updated_at"]
    cache["last_run"] = summary
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2))
    return summary


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
