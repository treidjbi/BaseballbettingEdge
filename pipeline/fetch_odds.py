"""
fetch_odds.py
Fetches MLB K prop lines from TheRundown API v2.
Uses market_ids=19 (pitcher_strikeouts) with the markets-based response format.
Fetches both date_str and date_str+1 (UTC) to cover ET evening games.
Auth: X-TheRundown-Key header. Rate limit: 2 req/sec — sleep 0.55s between calls.
"""
import os
import time
import logging
import requests
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

BASE_URL   = "https://therundown.io/api/v2"
SPORT_ID   = 3   # MLB
MARKET_ID  = 19  # pitcher_strikeouts
THROTTLE_S = 0.55
_last_call_time: float = 0.0

# TheRundown v2 book IDs. Verify against live API response if lines are missing.
# To discover available IDs: log list(lines_data[main_val]["over"].keys()) in _parse_event_k_props
# Caesars (20) and Fanatics (38) are best-guess IDs — if a pitcher's ref_book
# shows up as "Book<N>" in picks_history.json for an N not in this map, update
# the map. Option B (Task A4 follow-up): only target books count; untracked
# books now trigger a skip rather than a fallback, so picks only surface when
# the user can actually place the bet.
BOOK_ID_MAP = {
    "23": "FanDuel",
    "22": "BetMGM",
    "19": "DraftKings",
    "30": "BetRivers",
    "20": "Caesars",
    "38": "Fanatics",
}
# Priority order for picking the reference book on the card. Higher-priority
# books come first; _select_ref_book returns the first match.
REF_BOOK_PRIORITY = ["23", "22", "19", "30", "20", "38"]

# Books tracked in steam.json snapshots (Steam Phase A). Same set as
# BOOK_ID_MAP today; kept as a separate name so steam tracking and ref-book
# selection can diverge later if needed.
TRACKED_BOOKS = {
    "23": "FanDuel",
    "22": "BetMGM",
    "19": "DraftKings",
    "30": "BetRivers",
    "20": "Caesars",
    "38": "Fanatics",
}


def _select_ref_book(available_books: dict) -> tuple:
    """
    Select reference book from available_books dict {book_id: price_info}.
    Priority order: FanDuel → BetMGM → DraftKings → BetRivers → Caesars → Fanatics.
    Returns (book_id, human_name) or (None, None) if NO priority book is
    available. This is the Option B behavior: we deliberately do NOT fall back
    to unknown books — a pick the user cannot actually place is worse than no
    pick, so the caller in _parse_event_k_props skips the pitcher entirely.
    """
    for book_id in REF_BOOK_PRIORITY:
        if book_id in available_books:
            return book_id, BOOK_ID_MAP[book_id]
    return None, None


def _headers() -> dict:
    key = os.environ.get("RUNDOWN_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "RUNDOWN_API_KEY not set. "
            "Set it as a Windows User Environment Variable via sysdm.cpl."
        )
    return {"X-TheRundown-Key": key, "Accept": "application/json"}


def throttled_get(url: str, params: dict = None) -> dict:
    """GET with rate-limit throttle. Raises on non-200."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < THROTTLE_S:
        time.sleep(THROTTLE_S - elapsed)
    _last_call_time = time.time()
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def american_odds_from_line(value) -> int | None:
    """Parse an American odds value like '-110', '+130', or 130. Returns None if unparseable."""
    try:
        v = str(value).strip().replace("+", "")
        if not v or v.lower() in ("n/a", "none", "null", "-"):
            return None
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _parse_line_value(value_str: str):
    """
    Parse 'Over 5.5' → ('over', 5.5) or 'Under 6.5' → ('under', 6.5).
    Returns None on parse failure.
    """
    parts = value_str.strip().lower().split()
    if len(parts) == 2 and parts[0] in ("over", "under"):
        try:
            return parts[0], float(parts[1])
        except ValueError:
            pass
    return None


def _parse_event_k_props(event: dict) -> list:
    """
    Parse a single event's markets list into K-prop dicts (one per pitcher).
    Expects market_id=19 (pitcher_strikeouts) entries in event['markets'].
    Returns empty list if no such market is present.
    """
    teams     = event.get("teams", [])
    away_team = next((t["name"] for t in teams if t.get("is_away")), "")
    home_team = next((t["name"] for t in teams if t.get("is_home")), "")
    game_time = event.get("event_date", "")

    results = []
    for market in event.get("markets", []):
        if market.get("market_id") != MARKET_ID:
            continue

        for participant in market.get("participants", []):
            pitcher_name = participant.get("name", "")
            if not pitcher_name:
                continue

            # Collect {line_val: {direction: {book_id: {price, is_main, delta}}}}
            lines_data: dict = {}
            for line in participant.get("lines", []):
                parsed = _parse_line_value(line.get("value", ""))
                if not parsed:
                    continue
                direction, line_val = parsed
                for book_id, price_info in line.get("prices", {}).items():
                    price = american_odds_from_line(price_info.get("price"))
                    if price is None:
                        continue
                    is_main = price_info.get("is_main_line", False)
                    delta   = price_info.get("price_delta", 0) or 0
                    lines_data.setdefault(line_val, {"over": {}, "under": {}})
                    lines_data[line_val][direction][book_id] = {
                        "price":   price,
                        "is_main": is_main,
                        "delta":   delta,
                    }

            if not lines_data:
                continue

            # Prefer the line value where any book marks is_main_line=True
            main_val = None
            for lv, dirs in lines_data.items():
                for direction in ("over", "under"):
                    if any(bd["is_main"] for bd in dirs[direction].values()):
                        main_val = lv
                        break
                if main_val is not None:
                    break

            if main_val is None:
                # No main flag — pick the line val with the most book coverage
                main_val = max(
                    lines_data,
                    key=lambda lv: len(lines_data[lv]["over"]) + len(lines_data[lv]["under"]),
                )

            chosen = lines_data[main_val]

            # Capture per-book odds for steam tracking (tracked books only).
            book_odds: dict = {}
            for book_id, book_name in TRACKED_BOOKS.items():
                if book_id in chosen["over"] and book_id in chosen["under"]:
                    book_odds[book_name] = {
                        "over":  chosen["over"][book_id]["price"],
                        "under": chosen["under"][book_id]["price"],
                    }

            # Select reference book from the priority list. Option B: untracked
            # books trigger a skip so we don't surface picks on books the user
            # can't place. The over and under sides are resolved independently
            # so we accept e.g. FanDuel over / BetMGM under if those are the
            # best priority matches on each side.
            ref_book_id, ref_book_name = _select_ref_book(chosen["over"])
            if ref_book_id is None:
                log.info(
                    "no target book offered an over line for %s — skipping "
                    "(available books: %s)",
                    pitcher_name, sorted(chosen["over"].keys()),
                )
                continue
            if ref_book_id in chosen["under"]:
                ref_over  = chosen["over"][ref_book_id]
                ref_under = chosen["under"][ref_book_id]
                under_book_name = ref_book_name
            else:
                # Ref book has over but not under — pick the next priority book
                # that offers an under. Still priority-only (no fallback).
                under_book_id, under_book_name = _select_ref_book(chosen["under"])
                if under_book_id is None:
                    log.info(
                        "no target book offered an under line for %s — skipping "
                        "(available books: %s)",
                        pitcher_name, sorted(chosen["under"].keys()),
                    )
                    continue
                ref_over  = chosen["over"][ref_book_id]
                ref_under = chosen["under"][under_book_id]

            ref_over_price  = ref_over["price"]
            ref_under_price = ref_under["price"]
            over_delta      = ref_over.get("delta", 0) or 0
            under_delta     = ref_under.get("delta", 0) or 0

            if ref_over_price is None or ref_under_price is None:
                continue

            # Opening odds: price_delta = current - opening → opening = current - delta
            opening_over  = ref_over_price  - over_delta
            opening_under = ref_under_price - under_delta

            results.append({
                "pitcher":            pitcher_name,
                "team":               "",        # resolved by fetch_stats via MLB schedule
                "opp_team":           "",        # resolved by fetch_stats via MLB schedule
                "game_time":          game_time,
                "k_line":             main_val,
                "opening_line":       main_val,
                "ref_book":           ref_book_name,
                "best_over_book":     ref_book_name,
                "best_under_book":    under_book_name,
                "best_over_odds":     ref_over_price,
                "best_under_odds":    ref_under_price,
                "opening_over_odds":  opening_over,
                "opening_under_odds": opening_under,
                # Opening is within-day (TheRundown's price_delta is start-of-current-trading-day).
                # run_pipeline._apply_preview_openings promotes to "preview" when the 7pm
                # overnight baseline is available. Distinct sources have different semantics
                # for movement_conf — see calc_movement_confidence.
                "opening_odds_source": "first_seen",
                "book_odds":          book_odds or None,
            })

    return results


def parse_k_props(data: dict) -> list:
    """Parse a TheRundown events response (new markets format) into K-prop dicts."""
    results = []
    for event in data.get("events", []):
        results.extend(_parse_event_k_props(event))
    return results


def fetch_odds(date_str: str) -> list:
    """
    Main entry point. Returns list of K-prop dicts for date_str (YYYY-MM-DD).
    Fetches both date_str and date_str+1 in UTC to cover ET evening games
    (e.g. a 7 PM ET game on Mar 25 is filed as Mar 26 UTC by TheRundown).
    Returns empty list if no props available.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dates_to_fetch = [date_str, (dt + timedelta(days=1)).strftime("%Y-%m-%d")]

    seen_event_ids: set = set()
    all_props: list = []

    for fetch_date in dates_to_fetch:
        log.info("Fetching K props for UTC date %s ...", fetch_date)
        try:
            url  = f"{BASE_URL}/sports/{SPORT_ID}/events/{fetch_date}"
            data = throttled_get(url, params={"market_ids": MARKET_ID})
            for event in data.get("events", []):
                eid = event.get("event_id")
                if eid and eid in seen_event_ids:
                    continue
                if eid:
                    seen_event_ids.add(eid)
                all_props.extend(_parse_event_k_props(event))
        except Exception as e:
            log.warning("fetch_odds failed for %s: %s", fetch_date, e)

    log.info("Found %d K props", len(all_props))
    return all_props
