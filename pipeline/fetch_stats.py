"""
fetch_stats.py
Fetches pitcher and team stats from the MLB Stats API (free, no key required).
Returns a dict keyed by pitcher name with stats needed for build_features.
"""
import logging
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from name_utils import normalize as _normalize_name

log = logging.getLogger(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"
RECENT_START_LOOKBACK = 10
RECENT_START_COUNT = 5
ET = ZoneInfo("America/New_York")


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
    """Extract aggregate K/9 from one or more MLB stats splits."""
    total_ip = 0.0
    total_so = 0
    for split in splits:
        stat = split.get("stat", {})
        ip   = _parse_ip(stat.get("inningsPitched", 0))
        so   = int(stat.get("strikeOuts", 0) or 0)
        if ip > 0:
            total_ip += ip
            total_so += so
    if total_ip <= 0:
        return None
    return round((total_so / total_ip) * 9, 2)


def _parse_split_date(value) -> datetime | None:
    """Parse an MLB game log date string like 2026-03-29."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return None


def _schedule_game_date_et(game: dict, fallback_date_str: str) -> str:
    """Return the game calendar date in ET for schedule filtering."""
    game_date = game.get("gameDate")
    if game_date:
        try:
            return datetime.fromisoformat(game_date.replace("Z", "+00:00")).astimezone(ET).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return fallback_date_str
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return None


def _is_playable_schedule_game(game: dict) -> bool:
    """Return False for MLB schedule rows that should not produce betting props."""
    status = game.get("status") or {}
    detailed = str(status.get("detailedState") or "").strip().lower()
    abstract = str(status.get("abstractGameState") or "").strip().lower()

    non_playable_tokens = ("postponed", "cancelled", "canceled")
    if any(token in detailed for token in non_playable_tokens):
        return False
    if any(token in abstract for token in non_playable_tokens):
        return False
    return True


def _sort_starts_by_date_desc(starts: list) -> list:
    """Return started game-log rows newest-first when date data exists."""
    return sorted(
        starts,
        key=lambda split: _parse_split_date(split.get("date")) or datetime.min,
        reverse=True,
    )


def _extract_days_since_last_start(target_date: datetime, starts: list) -> int | None:
    """Compute rest days from the latest started game in the game log slice."""
    if not starts:
        return None
    last_start_date = _parse_split_date(starts[0].get("date"))
    if last_start_date is None or last_start_date > target_date:
        return None
    return (target_date - last_start_date).days


def _extract_last_pitch_count(starts: list) -> int | None:
    """Read the pitch count from the latest started game in the game log slice."""
    if not starts:
        return None
    pitch_count = starts[0].get("stat", {}).get("numberOfPitches")
    if pitch_count in (None, ""):
        return None
    try:
        return int(pitch_count)
    except (TypeError, ValueError):
        return None


def fetch_pitch_hand(person_id: int) -> str | None:
    """Fetch a pitcher's throwing hand ('R' or 'L') from /people/{id}.

    The MLB /schedule endpoint with hydrate=probablePitcher,team only returns
    {id, fullName, link} on probablePitcher — pitchHand is NOT hydrated. So we
    fall back to /people/{id}, which always returns pitchHand. Returns 'R' or
    'L' on success, or None on fetch failure / missing data so callers can
    choose their own default.
    """
    try:
        data = _get(f"/people/{person_id}")
    except Exception as e:
        log.warning("fetch_pitch_hand: /people/%s failed: %s", person_id, e)
        return None
    people = data.get("people") or []
    if not people:
        return None
    code = (people[0].get("pitchHand") or {}).get("code")
    if code in ("R", "L"):
        return code
    return None


def fetch_pitcher_stats(person_id: int, season: int, target_date: datetime | None = None) -> dict:
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
        "stats": "gameLog", "group": "pitching", "season": season, "limit": RECENT_START_LOOKBACK
    })
    starts        = (log_data.get("stats") or [{}])[0].get("splits", [])
    starts        = [s for s in starts if int(s.get("stat", {}).get("gamesStarted", 0) or 0) > 0]
    if not starts:
        # Opening Day / early season: fall back to last season's game log
        prior_data = _get(f"/people/{person_id}/stats", {
            "stats": "gameLog", "group": "pitching", "season": season - 1, "limit": RECENT_START_LOOKBACK
        })
        starts     = (prior_data.get("stats") or [{}])[0].get("splits", [])
        starts     = [s for s in starts if int(s.get("stat", {}).get("gamesStarted", 0) or 0) > 0]
    starts        = _sort_starts_by_date_desc(starts)
    starts        = starts[:RECENT_START_COUNT]
    starts_count  = len(starts)
    recent_start_ips = [_parse_ip(s.get("stat", {}).get("inningsPitched", 0)) for s in starts]
    recent_k9     = _k9_from_splits(starts) if starts_count >= 3 else season_k9

    # Average IP per start from last 5 starts — used as expected_innings in calc_lambda.
    # Falls back to 5.5 if fewer than 3 starts (e.g. early season, call-ups).
    if starts_count >= 3:
        avg_ip_last5 = round(sum(recent_start_ips) / len(recent_start_ips), 2)
    else:
        avg_ip_last5 = 5.5

    days_since_last_start = (
        _extract_days_since_last_start(target_date, starts)
        if target_date is not None else None
    )
    last_pitch_count = _extract_last_pitch_count(starts)

    return {
        "season_k9":              season_k9,
        "career_k9":              career_k9,
        "recent_k9":              recent_k9,
        "starts_count":           starts_count,
        "innings_pitched_season": ip,
        "avg_ip_last5":           avg_ip_last5,
        "recent_start_ips":       recent_start_ips,
        "days_since_last_start":  days_since_last_start,
        "last_pitch_count":       last_pitch_count,
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


def fetch_stats(date_str: str, pitcher_names: list) -> tuple[dict, dict]:
    """
    Main entry point.  Returns **(stats_by_name, probables_by_team)**.

    `stats_by_name` — `{pitcher_name: stats_dict}` for pitchers whose
    TheRundown name matches MLB's probable for some scheduled team.
    Unchanged shape from prior versions plus one new field, `probable_name`,
    which is the matched MLB fullName (used by build_features for
    `starter_mismatch`).

    `probables_by_team` — `{team_name: [probable_pitcher_fullName, ...]}`
    captured for **every** scheduled side regardless of whether MLB's
    probable matched a TheRundown pitcher name. A team can appear more
    than once on a slate because of doubleheaders, so values are lists.
    Lets run_pipeline cross-check the odds pitcher against MLB's current
    probables on the team side, which is the only way to flag phantoms —
    when the book keeps the prop market live on a pitcher who got scratched,
    MLB's probable for that team has already swapped but fetch_stats's name
    filter would silently drop the mismatch. (Task A7, 2026-04-23.)

    Fetches schedules for date_str AND date_str+1 to match the UTC-offset
    behaviour of fetch_odds (ET evening games are filed under the next
    UTC day).  Skips pitchers where the confirmed starter cannot be
    found in the schedule.

    Name matching is accent-insensitive: TheRundown may return 'Jose Berrios'
    while the MLB API returns 'José Berríos'. Both normalize to 'jose berrios'
    and match. The original TheRundown name is preserved as the dict key so
    downstream lookups (stats_map.get(odds["pitcher"])) continue to work
    without modification.
    """
    target_date = datetime.strptime(date_str, "%Y-%m-%d")
    season = target_date.year
    next_day = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")

    # Build normalized lookup: stripped/lowercased name → original TheRundown name
    norm_to_orig: dict[str, str] = {}
    for n in pitcher_names:
        key = _normalize_name(n)
        if key not in norm_to_orig:
            norm_to_orig[key] = n

    # Build combined date list for the range query (MLB API supports startDate/endDate)
    schedule = _get("/schedule", {
        "sportId":   1,
        "startDate": date_str,
        "endDate":   next_day,
        "hydrate":   "probablePitcher,team",
    })

    stats_by_name: dict = {}
    probables_by_team: dict = {}
    for date_block in schedule.get("dates", []):
        block_date_str = date_block.get("date") or date_str
        for game in date_block.get("games", []):
            if _schedule_game_date_et(game, block_date_str) != date_str:
                continue
            if not _is_playable_schedule_game(game):
                status = (game.get("status") or {}).get("detailedState") or "non-playable"
                away_name = (
                    game.get("teams", {}).get("away", {}).get("team", {}).get("name", "")
                )
                home_name = (
                    game.get("teams", {}).get("home", {}).get("team", {}).get("name", "")
                )
                log.info(
                    "Skipping %s @ %s on %s: game status is %s",
                    away_name,
                    home_name,
                    date_str,
                    status,
                )
                continue
            game_date = _parse_split_date(block_date_str) or target_date
            for side in ("away", "home"):
                team_data = game.get("teams", {}).get(side, {})
                team_name = team_data.get("team", {}).get("name", "")
                pitcher   = team_data.get("probablePitcher")

                # A7: record MLB's probable per team BEFORE the match filter,
                # so run_pipeline can flag phantom-starter mismatches even
                # when MLB has already swapped away from the odds pitcher.
                if team_name:
                    probable_name = (pitcher or {}).get("fullName")
                    team_probables = probables_by_team.setdefault(team_name, [])
                    if probable_name and probable_name not in team_probables:
                        team_probables.append(probable_name)

                if not pitcher:
                    continue
                mlb_name  = pitcher.get("fullName", "")
                norm_mlb  = _normalize_name(mlb_name)
                if norm_mlb not in norm_to_orig:
                    continue
                # Use the original TheRundown name as the key so run_pipeline's
                # stats_map.get(odds["pitcher"]) resolves correctly.
                name = norm_to_orig[norm_mlb]
                if mlb_name != name:
                    log.info("Name normalised: %r (MLB) → %r (TheRundown)", mlb_name, name)

                pid    = pitcher["id"]
                # The /schedule endpoint with hydrate=probablePitcher,team does
                # not actually hydrate pitchHand — it only returns id/fullName/
                # link. So if the schedule didn't give us a hand, fall back to
                # /people/{id}, which always does. Without this fallback every
                # pitcher in production silently became 'R' (see analytics/
                # diagnostics/a1_pitcher_throws.py for the bug history).
                throws = (pitcher.get("pitchHand") or {}).get("code")
                if throws not in ("R", "L"):
                    throws = fetch_pitch_hand(pid) or "R"
                team_id = team_data.get("team", {}).get("id")

                try:
                    pstats = fetch_pitcher_stats(pid, season, target_date=game_date)
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

                opp_team_name = opp_team.get("name", "")
                park_team_name = team_name if side == "home" else opp_team_name
                stats_by_name[name] = {
                    **pstats,
                    "throws":           throws,
                    "opp_k_rate":       opp_k_rate,
                    "opp_games_played": opp_games_played,
                    "team":             team_name,
                    "opp_team":         opp_team_name,
                    "park_team":        park_team_name,
                    "probable_name":    mlb_name,  # A7: happy-path mirror
                }

    return stats_by_name, probables_by_team
