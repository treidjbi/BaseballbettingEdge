"""Probe PropLine MLB pitcher strikeout book coverage for a slate date.

This is a safe diagnostics helper for GitHub Actions: it prints returned
bookmaker keys/titles and complete pitcher-prop counts, never the API key.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

from fetch_odds import (  # noqa: E402
    PROPLINE_MARKET_KEY,
    PROPLINE_SPORT_KEY,
    _parse_propline_event_props,
    _the_odds_event_date_phoenix,
    propline_get,
)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/probe_propline_books.py YYYY-MM-DD", file=sys.stderr)
        return 2

    date_str = sys.argv[1]
    events = propline_get(f"/sports/{PROPLINE_SPORT_KEY}/events")
    if not isinstance(events, list):
        print("PropLine events response was not a list")
        return 1

    target_events = [
        event for event in events
        if _the_odds_event_date_phoenix(event) == date_str
    ]
    print(f"PropLine probe date={date_str} events_returned={len(events)} target_events={len(target_events)}")

    raw_books = Counter()
    complete_props_by_book = Counter()
    parsed_props = 0
    event_rows = []

    for event in target_events:
        event_id = event.get("id")
        if not event_id:
            continue
        odds = propline_get(
            f"/sports/{PROPLINE_SPORT_KEY}/events/{event_id}/odds",
            params={"markets": PROPLINE_MARKET_KEY},
        )
        if not isinstance(odds, dict):
            continue
        event_props = _parse_propline_event_props(odds)
        parsed_props += len(event_props)

        event_book_keys = []
        for bookmaker in odds.get("bookmakers", []):
            key = str(bookmaker.get("key") or "")
            title = str(bookmaker.get("title") or key)
            label = f"{key}:{title}" if key else title
            raw_books[label] += 1
            event_book_keys.append(label)
            for market in bookmaker.get("markets", []):
                if market.get("key") != PROPLINE_MARKET_KEY:
                    continue
                seen_complete = set()
                for outcome in market.get("outcomes", []):
                    player = outcome.get("description") or outcome.get("player")
                    point = outcome.get("point")
                    if player and point is not None:
                        seen_complete.add((player, point))
                complete_props_by_book[label] += len(seen_complete)

        event_rows.append(
            f"- {event.get('away_team')} @ {event.get('home_team')} "
            f"id={event_id} books={','.join(sorted(event_book_keys)) or 'none'} "
            f"parsed_target_props={len(event_props)}"
        )

    print("Raw books returned:")
    for label, count in sorted(raw_books.items()):
        print(f"- {label}: events={count} complete_pitcher_line_groups={complete_props_by_book[label]}")

    print(f"Parsed user-target props={parsed_props}")
    print("Event detail:")
    for row in event_rows:
        print(row)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
