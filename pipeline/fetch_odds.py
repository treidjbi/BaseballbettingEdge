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
from zoneinfo import ZoneInfo

from name_utils import normalize

log = logging.getLogger(__name__)

BASE_URL   = "https://therundown.io/api/v2"
SPORT_ID   = 3   # MLB
MARKET_ID  = 19  # pitcher_strikeouts
THROTTLE_S = 0.55
_last_call_time: float = 0.0

THE_ODDS_BASE_URL = "https://api.the-odds-api.com/v4"
THE_ODDS_SPORT_KEY = "baseball_mlb"
THE_ODDS_MARKET_KEY = "pitcher_strikeouts"
THE_ODDS_FALLBACK_BOOKMAKERS = ("fanduel", "draftkings")
THE_ODDS_BOOK_KEY_MAP = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
}
PROPLINE_BASE_URL = "https://api.prop-line.com/v1"
PROPLINE_SPORT_KEY = "baseball_mlb"
PROPLINE_MARKET_KEY = "pitcher_strikeouts"
PROPLINE_BOOK_KEY_MAP = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betrivers": "BetRivers",
    "kalshi": "Kalshi",
}
PHOENIX_TZ = ZoneInfo("America/Phoenix")

# TheRundown v2 affiliate IDs. Option B (Task A4 follow-up): only target books
# count; untracked books trigger a skip rather than a fallback, so picks only
# surface when the user can actually place the bet.
TARGET_AFFILIATE_IDS = ("19", "22", "23", "24", "25")
BOOK_ID_MAP = {
    "19": "DraftKings",
    "22": "BetMGM",
    "23": "FanDuel",
    "24": "theScore Bet",
    "25": "Kalshi",
}
# Priority order for picking the reference book on the card. Higher-priority
# books come first; _select_ref_book returns the first match.
REF_BOOK_PRIORITY = ["23", "22", "19", "24", "25"]

# Books tracked in steam.json snapshots (Steam Phase A). Same set as
# BOOK_ID_MAP today; kept as a separate name so steam tracking and ref-book
# selection can diverge later if needed.
TRACKED_BOOKS = {
    "19": "DraftKings",
    "22": "BetMGM",
    "23": "FanDuel",
    "24": "theScore Bet",
    "25": "Kalshi",
}
REF_BOOK_NAME_PRIORITY = ["FanDuel", "BetMGM", "DraftKings", "theScore Bet", "BetRivers", "Kalshi"]
PITCHER_POSITION_MARKERS = {"1", "p", "sp", "rp", "pitcher", "starting pitcher", "relief pitcher"}
MIN_REASONABLE_PITCHER_K_LINE = 1.5


def _select_ref_book_name(book_odds: dict) -> str | None:
    for book_name in REF_BOOK_NAME_PRIORITY:
        if book_name in book_odds:
            return book_name
    return None


def _normalize_position_marker(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _participant_position_markers(participant: dict) -> set[str]:
    markers: set[str] = set()
    position_nodes = [participant]
    for key in ("player", "athlete", "person"):
        node = participant.get(key)
        if isinstance(node, dict):
            position_nodes.append(node)

    for node in position_nodes:
        for key in ("primaryPosition", "position"):
            position = node.get(key)
            if isinstance(position, dict):
                for field in ("abbreviation", "code", "name", "type"):
                    marker = _normalize_position_marker(position.get(field))
                    if marker:
                        markers.add(marker)
            else:
                marker = _normalize_position_marker(position)
                if marker:
                    markers.add(marker)

    return markers


def _is_obvious_non_pitcher_participant(participant: dict) -> bool:
    markers = _participant_position_markers(participant)
    if not markers:
        return False
    return markers.isdisjoint(PITCHER_POSITION_MARKERS)


def _select_ref_book(available_books: dict) -> tuple:
    """
    Select reference book from available_books dict {book_id: price_info}.
    Priority order: FanDuel → BetMGM → DraftKings → theScore Bet → Kalshi.
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
    key = os.environ.get("RUNDOWN_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "RUNDOWN_API_KEY not set. "
            "Set it as a Windows User Environment Variable via sysdm.cpl."
        )
    return {"X-TheRundown-Key": key, "Accept": "application/json"}


def _the_odds_key() -> str:
    return os.environ.get("ODDS_API_KEY", "").strip()


def _propline_key() -> str:
    return os.environ.get("PROPLINE_API_KEY", "").strip()


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


def the_odds_get(path: str, params: dict | None = None) -> tuple[dict | list, dict]:
    key = _the_odds_key()
    if not key:
        raise EnvironmentError("ODDS_API_KEY not set")

    request_params = dict(params or {})
    request_params["apiKey"] = key
    resp = requests.get(
        f"{THE_ODDS_BASE_URL}{path}",
        params=request_params,
        timeout=15,
    )
    resp.raise_for_status()
    quota = {
        "remaining": resp.headers.get("x-requests-remaining"),
        "used": resp.headers.get("x-requests-used"),
        "last": resp.headers.get("x-requests-last"),
    }
    return resp.json(), quota


def propline_get(path: str, params: dict | None = None) -> dict | list:
    key = _propline_key()
    if not key:
        raise EnvironmentError("PROPLINE_API_KEY not set")

    resp = requests.get(
        f"{PROPLINE_BASE_URL}{path}",
        headers={"X-API-Key": key, "Accept": "application/json"},
        params=params or {},
        timeout=15,
    )
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
            if _is_obvious_non_pitcher_participant(participant):
                log.info(
                    "skipping %s: participant metadata marks a non-pitcher (%s)",
                    pitcher_name,
                    sorted(_participant_position_markers(participant)),
                )
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
            if main_val < MIN_REASONABLE_PITCHER_K_LINE:
                log.info(
                    "skipping %s: k_line %.1f is below the starter-only floor of %.1f",
                    pitcher_name,
                    main_val,
                    MIN_REASONABLE_PITCHER_K_LINE,
                )
                continue

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
                "odds_source":        "therundown",
            })

    return results


def _the_odds_event_date_phoenix(event: dict) -> str | None:
    commence_time = event.get("commence_time")
    if not commence_time:
        return None
    try:
        dt = datetime.fromisoformat(str(commence_time).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(PHOENIX_TZ).strftime("%Y-%m-%d")


def _parse_provider_event_props(
    event: dict,
    *,
    book_key_map: dict,
    source: str,
    event_id_field: str,
) -> list:
    grouped: dict = {}
    for bookmaker in event.get("bookmakers", []):
        book_key = bookmaker.get("key")
        book_name = book_key_map.get(book_key)
        if not book_name:
            continue
        for market in bookmaker.get("markets", []):
            if market.get("key") not in (THE_ODDS_MARKET_KEY, PROPLINE_MARKET_KEY):
                continue
            for outcome in market.get("outcomes", []):
                direction = str(outcome.get("name", "")).strip().lower()
                if direction not in ("over", "under"):
                    continue
                pitcher_name = outcome.get("description") or outcome.get("player")
                if not pitcher_name:
                    continue
                try:
                    line_val = float(outcome.get("point"))
                except (TypeError, ValueError):
                    continue
                price = american_odds_from_line(outcome.get("price"))
                if price is None:
                    continue
                pitcher_key = normalize(pitcher_name)
                grouped.setdefault(pitcher_key, {"pitcher": pitcher_name, "lines": {}})
                grouped[pitcher_key]["lines"].setdefault(line_val, {})
                grouped[pitcher_key]["lines"][line_val].setdefault(book_name, {})
                grouped[pitcher_key]["lines"][line_val][book_name][direction] = price

    props = []
    for pitcher_data in grouped.values():
        complete_lines = {}
        for line_val, by_book in pitcher_data["lines"].items():
            complete_books = {
                book_name: odds
                for book_name, odds in by_book.items()
                if "over" in odds and "under" in odds
            }
            if complete_books:
                complete_lines[line_val] = complete_books
        if not complete_lines:
            continue

        def line_score(item):
            _line_val, books = item
            priority_score = max(
                (
                    len(REF_BOOK_NAME_PRIORITY) - idx
                    for idx, book_name in enumerate(REF_BOOK_NAME_PRIORITY)
                    if book_name in books
                ),
                default=0,
            )
            return (priority_score, len(books))

        main_val, book_odds = max(complete_lines.items(), key=line_score)
        if main_val < MIN_REASONABLE_PITCHER_K_LINE:
            continue
        ref_book = _select_ref_book_name(book_odds)
        if ref_book is None:
            continue
        ref_odds = book_odds[ref_book]
        props.append({
            "pitcher": pitcher_data["pitcher"],
            "team": "",
            "opp_team": "",
            "game_time": event.get("commence_time", ""),
            "k_line": main_val,
            "opening_line": main_val,
            "ref_book": ref_book,
            "best_over_book": ref_book,
            "best_under_book": ref_book,
            "best_over_odds": ref_odds["over"],
            "best_under_odds": ref_odds["under"],
            "opening_over_odds": ref_odds["over"],
            "opening_under_odds": ref_odds["under"],
            "opening_odds_source": "first_seen",
            "book_odds": book_odds,
            "odds_source": source,
            event_id_field: event.get("id"),
        })
    return props


def _parse_the_odds_event_props(event: dict) -> list:
    return _parse_provider_event_props(
        event,
        book_key_map=THE_ODDS_BOOK_KEY_MAP,
        source="the_odds",
        event_id_field="the_odds_event_id",
    )


def _parse_propline_event_props(event: dict) -> list:
    return _parse_provider_event_props(
        event,
        book_key_map=PROPLINE_BOOK_KEY_MAP,
        source="propline",
        event_id_field="propline_event_id",
    )


def _fetch_the_odds_fallback_props(date_str: str) -> list:
    log.info(
        "The Odds fallback: fetching %s %s for %s books=%s",
        THE_ODDS_SPORT_KEY,
        THE_ODDS_MARKET_KEY,
        date_str,
        ",".join(THE_ODDS_FALLBACK_BOOKMAKERS),
    )
    events, events_quota = the_odds_get(f"/sports/{THE_ODDS_SPORT_KEY}/events")
    log.info(
        "The Odds fallback: events returned=%d quota_last=%s remaining=%s",
        len(events) if isinstance(events, list) else 0,
        events_quota.get("last"),
        events_quota.get("remaining"),
    )
    if not isinstance(events, list):
        return []

    target_events = [
        event for event in events
        if _the_odds_event_date_phoenix(event) == date_str
    ]
    props = []
    credits_used = 0
    for event in target_events:
        event_id = event.get("id")
        if not event_id:
            continue
        data, quota = the_odds_get(
            f"/sports/{THE_ODDS_SPORT_KEY}/events/{event_id}/odds",
            params={
                "bookmakers": ",".join(THE_ODDS_FALLBACK_BOOKMAKERS),
                "markets": THE_ODDS_MARKET_KEY,
                "oddsFormat": "american",
            },
        )
        try:
            credits_used += int(quota.get("last") or 0)
        except ValueError:
            pass
        if isinstance(data, dict):
            props.extend(_parse_the_odds_event_props(data))

    log.info(
        "The Odds fallback: fetched %d events, parsed %d pitcher props, credits_used=%d",
        len(target_events),
        len(props),
        credits_used,
    )
    return props


def _fetch_propline_fallback_props(date_str: str) -> list:
    log.info(
        "PropLine fallback: fetching %s %s for %s",
        PROPLINE_SPORT_KEY,
        PROPLINE_MARKET_KEY,
        date_str,
    )
    events = propline_get(f"/sports/{PROPLINE_SPORT_KEY}/events")
    log.info(
        "PropLine fallback: events returned=%d",
        len(events) if isinstance(events, list) else 0,
    )
    if not isinstance(events, list):
        return []

    target_events = [
        event for event in events
        if _the_odds_event_date_phoenix(event) == date_str
    ]
    props = []
    books_seen: set[str] = set()
    for event in target_events:
        event_id = event.get("id")
        if not event_id:
            continue
        data = propline_get(
            f"/sports/{PROPLINE_SPORT_KEY}/events/{event_id}/odds",
            params={"markets": PROPLINE_MARKET_KEY},
        )
        if isinstance(data, dict):
            for bookmaker in data.get("bookmakers", []):
                books_seen.add(str(bookmaker.get("key") or bookmaker.get("title") or ""))
            props.extend(_parse_propline_event_props(data))

    log.info(
        "PropLine fallback: fetched %d events, parsed %d pitcher props, raw_books=%s",
        len(target_events),
        len(props),
        ",".join(sorted(b for b in books_seen if b)) or "none",
    )
    return props


def _refresh_ref_from_book_odds(prop: dict, force: bool = False) -> None:
    book_odds = prop.get("book_odds") or {}
    ref_book = _select_ref_book_name(book_odds)
    if not ref_book:
        return
    if not force and prop.get("ref_book") == ref_book:
        return
    ref_odds = book_odds[ref_book]
    prop["ref_book"] = ref_book
    prop["best_over_book"] = ref_book
    prop["best_under_book"] = ref_book
    prop["best_over_odds"] = ref_odds["over"]
    prop["best_under_odds"] = ref_odds["under"]
    prop["opening_over_odds"] = ref_odds["over"]
    prop["opening_under_odds"] = ref_odds["under"]
    prop["opening_odds_source"] = "first_seen"


def _merge_fallback_props(rundown_props: list, fallback_props: list, source_label: str) -> list:
    merged = [dict(prop) for prop in rundown_props]
    by_key = {
        (normalize(prop.get("pitcher", "")), prop.get("k_line")): prop
        for prop in merged
    }
    existing_pitchers = {
        normalize(prop.get("pitcher", ""))
        for prop in merged
    }

    for fallback in fallback_props:
        key = (normalize(fallback.get("pitcher", "")), fallback.get("k_line"))
        existing = by_key.get(key)
        if existing is None:
            if key[0] in existing_pitchers:
                log.info(
                    "%s fallback skipped %s: line %.1f differs from TheRundown line",
                    source_label,
                    fallback.get("pitcher", ""),
                    fallback.get("k_line"),
                )
                continue
            copied = dict(fallback)
            merged.append(copied)
            by_key[key] = copied
            existing_pitchers.add(key[0])
            continue

        existing_book_odds = dict(existing.get("book_odds") or {})
        for book_name, odds in (fallback.get("book_odds") or {}).items():
            existing_book_odds.setdefault(book_name, odds)
        existing["book_odds"] = existing_book_odds or None
        existing_source = existing.get("odds_source") or "therundown"
        fallback_source = fallback.get("odds_source") or source_label.lower()
        source_parts = []
        for part in f"{existing_source}+{fallback_source}".split("+"):
            if part and part not in source_parts:
                source_parts.append(part)
        existing["odds_source"] = "+".join(source_parts)
        for key_name in ("the_odds_event_id", "propline_event_id"):
            if fallback.get(key_name):
                existing[key_name] = fallback.get(key_name)
        _refresh_ref_from_book_odds(existing)

    return merged


def _merge_the_odds_fallback_props(rundown_props: list, fallback_props: list) -> list:
    return _merge_fallback_props(rundown_props, fallback_props, "The Odds")


def _merge_propline_fallback_props(rundown_props: list, fallback_props: list) -> list:
    return _merge_fallback_props(rundown_props, fallback_props, "PropLine")


def _missing_fd_dk_coverage(props: list) -> bool:
    books_seen = {
        book_name
        for prop in props
        for book_name in (prop.get("book_odds") or {})
    }
    return any(book_name not in books_seen for book_name in THE_ODDS_BOOK_KEY_MAP.values())


def _needs_fallback_coverage(props: list) -> bool:
    return not props or _missing_fd_dk_coverage(props)


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
    failures: list[Exception] = []

    for fetch_date in dates_to_fetch:
        log.info("Fetching K props for UTC date %s ...", fetch_date)
        try:
            url  = f"{BASE_URL}/sports/{SPORT_ID}/events/{fetch_date}"
            data = throttled_get(url, params={
                "market_ids": MARKET_ID,
                "affiliate_ids": ",".join(TARGET_AFFILIATE_IDS),
            })
            for event in data.get("events", []):
                eid = event.get("event_id")
                if eid and eid in seen_event_ids:
                    continue
                if eid:
                    seen_event_ids.add(eid)
                all_props.extend(_parse_event_k_props(event))
        except Exception as e:
            failures.append(e)
            log.warning("fetch_odds failed for %s: %s", fetch_date, e)

    if _the_odds_key() and _needs_fallback_coverage(all_props):
        try:
            fallback_props = _fetch_the_odds_fallback_props(date_str)
            if fallback_props:
                all_props = _merge_the_odds_fallback_props(all_props, fallback_props)
        except Exception as e:
            log.warning("The Odds fallback failed for %s: %s", date_str, e)
    elif not _the_odds_key() and _needs_fallback_coverage(all_props):
        log.info("The Odds fallback skipped: ODDS_API_KEY not set")

    if _propline_key() and _needs_fallback_coverage(all_props):
        try:
            fallback_props = _fetch_propline_fallback_props(date_str)
            if fallback_props:
                all_props = _merge_propline_fallback_props(all_props, fallback_props)
        except Exception as e:
            log.warning("PropLine fallback failed for %s: %s", date_str, e)
    elif not _propline_key() and _needs_fallback_coverage(all_props):
        log.info("PropLine fallback skipped: PROPLINE_API_KEY not set")

    if not all_props and failures:
        raise failures[0]

    log.info("Found %d K props", len(all_props))
    return all_props
