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
    time.sleep(THROTTLE_S)
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

            # Best over: highest over odds across all books
            best_over_price = None
            best_book_id    = None
            for book_id, bd in chosen["over"].items():
                if best_over_price is None or bd["price"] > best_over_price:
                    best_over_price = bd["price"]
                    best_book_id    = book_id

            if best_over_price is None or not chosen["under"]:
                continue  # need both sides

            # Under: prefer same book as best over, else take best under odds
            if best_book_id in chosen["under"]:
                best_under_price = chosen["under"][best_book_id]["price"]
                over_delta       = chosen["over"][best_book_id]["delta"]
                under_delta      = chosen["under"][best_book_id]["delta"]
            else:
                best_under_entry = max(chosen["under"].values(), key=lambda bd: bd["price"])
                best_under_price = best_under_entry["price"]
                under_delta      = best_under_entry["delta"]
                over_delta       = chosen["over"][best_book_id]["delta"]

            if best_under_price is None:
                continue

            # Opening odds: price_delta = current - opening → opening = current - delta
            opening_over  = best_over_price  - over_delta
            opening_under = best_under_price - under_delta

            results.append({
                "pitcher":            pitcher_name,
                "team":               away_team,
                "opp_team":           home_team,
                "game_time":          game_time,
                "k_line":             main_val,
                "opening_line":       main_val,
                "best_over_book":     f"Book{best_book_id}",
                "best_over_odds":     best_over_price,
                "best_under_odds":    best_under_price,
                "opening_over_odds":  opening_over,
                "opening_under_odds": opening_under,
            })

    return results


def parse_k_props(data: dict, opening_odds_map: dict = None) -> list:
    """
    Parse a TheRundown events response (new markets format) into K-prop dicts.
    opening_odds_map is accepted for backward-compat but ignored — the API now
    provides price_delta directly in each price entry.
    """
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
