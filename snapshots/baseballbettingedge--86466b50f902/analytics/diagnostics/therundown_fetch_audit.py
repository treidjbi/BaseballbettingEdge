"""Compare TheRundown query shapes before changing production odds intake.

This is an operator diagnostic, not part of the daily pipeline. It helps answer:
- how many raw market participants did TheRundown return?
- how many parsed as usable pitcher K props?
- how many resolved to MLB probable starters?
- which sportsbook affiliate IDs were present?
- how many data points did each query consume?
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import requests

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = ROOT / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from fetch_odds import BASE_URL, MARKET_ID, SPORT_ID, THROTTLE_S, _headers, parse_k_props
from fetch_stats import fetch_stats


STARTER_AFFILIATE_IDS = ["19", "22", "23", "25"]
EXPERIMENTAL_AFFILIATE_IDS = ["19", "22", "23", "25", "30", "20", "38"]


def build_query_modes() -> dict[str, dict[str, str]]:
    """Return stable query params for side-by-side TheRundown audits."""
    return {
        "current": {"market_ids": str(MARKET_ID)},
        "offset": {"market_ids": str(MARKET_ID), "offset": "300"},
        "offset_affiliates": {
            "market_ids": str(MARKET_ID),
            "offset": "300",
            "affiliate_ids": ",".join(STARTER_AFFILIATE_IDS),
        },
        "offset_experimental_affiliates": {
            "market_ids": str(MARKET_ID),
            "offset": "300",
            "affiliate_ids": ",".join(EXPERIMENTAL_AFFILIATE_IDS),
        },
        "offset_affiliates_main_line": {
            "market_ids": str(MARKET_ID),
            "offset": "300",
            "affiliate_ids": ",".join(STARTER_AFFILIATE_IDS),
            "main_line": "true",
        },
    }


def _market_participants(events: Iterable[dict]) -> list[dict]:
    participants: list[dict] = []
    for event in events:
        for market in event.get("markets", []):
            if market.get("market_id") != MARKET_ID:
                continue
            participants.extend(market.get("participants", []))
    return participants


def _books_seen(events: Iterable[dict]) -> list[str]:
    books: set[str] = set()
    for participant in _market_participants(events):
        for line in participant.get("lines", []):
            books.update((line.get("prices") or {}).keys())
    return sorted(books, key=lambda value: int(value) if str(value).isdigit() else str(value))


def summarize_mode(
    mode_name: str,
    events: list[dict],
    datapoints: int = 0,
    resolved_pitcher_names: set[str] | None = None,
) -> dict:
    """Summarize one TheRundown response shape for coverage and noise."""
    resolved_pitcher_names = resolved_pitcher_names or set()
    raw_participants = _market_participants(events)
    props = parse_k_props({"events": events})
    parsed_names = [prop["pitcher"] for prop in props]
    resolved_names = [name for name in parsed_names if name in resolved_pitcher_names]
    unresolved_names = [name for name in parsed_names if name not in resolved_pitcher_names]

    return {
        "mode": mode_name,
        "events": len(events),
        "datapoints": datapoints,
        "raw_participants": len(raw_participants),
        "parsed_props": len(props),
        "resolved_pitchers": len(resolved_names),
        "pre_probable_noise": max(0, len(raw_participants) - len(props)),
        "books_seen": _books_seen(events),
        "sample_raw_names": [
            (participant.get("name") or "")
            for participant in raw_participants[:8]
            if participant.get("name")
        ],
        "sample_parsed_names": parsed_names[:8],
        "sample_unresolved_names": unresolved_names[:8],
    }


def _dates_for_mode(date_str: str, mode_name: str) -> list[str]:
    if mode_name == "current":
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return [date_str, (dt + timedelta(days=1)).strftime("%Y-%m-%d")]
    return [date_str]


def _get_events(date_str: str, params: dict[str, str]) -> tuple[list[dict], int]:
    url = f"{BASE_URL}/sports/{SPORT_ID}/events/{date_str}"
    response = requests.get(url, headers=_headers(), params=params, timeout=20)
    response.raise_for_status()
    datapoints = int(response.headers.get("X-Datapoints") or 0)
    return response.json().get("events", []), datapoints


def run_audit(date_str: str, resolve_probables: bool = True) -> list[dict]:
    """Fetch all query modes and return their summaries."""
    mode_events: dict[str, list[dict]] = {}
    mode_datapoints: dict[str, int] = {}
    all_parsed_names: set[str] = set()

    for mode_name, params in build_query_modes().items():
        events: list[dict] = []
        datapoints = 0
        for fetch_date in _dates_for_mode(date_str, mode_name):
            fetched_events, fetched_datapoints = _get_events(fetch_date, params)
            events.extend(fetched_events)
            datapoints += fetched_datapoints
            time.sleep(THROTTLE_S)

        mode_events[mode_name] = events
        mode_datapoints[mode_name] = datapoints
        all_parsed_names.update(prop["pitcher"] for prop in parse_k_props({"events": events}))

    resolved_names: set[str] = set()
    if resolve_probables and all_parsed_names:
        stats_map, _ = fetch_stats(date_str, sorted(all_parsed_names))
        resolved_names = set(stats_map.keys())

    summaries: list[dict] = []
    for mode_name in build_query_modes():
        summaries.append(
            summarize_mode(
                mode_name=mode_name,
                events=mode_events[mode_name],
                datapoints=mode_datapoints[mode_name],
                resolved_pitcher_names=resolved_names,
            )
        )
    return summaries


def _print_table(summaries: list[dict]) -> None:
    columns = [
        "mode",
        "datapoints",
        "events",
        "raw_participants",
        "parsed_props",
        "resolved_pitchers",
        "pre_probable_noise",
        "books_seen",
    ]
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in summaries))
        for column in columns
    }
    print(" | ".join(column.ljust(widths[column]) for column in columns))
    print(" | ".join("-" * widths[column] for column in columns))
    for row in summaries:
        values = {**row, "books_seen": ",".join(row.get("books_seen") or [])}
        print(" | ".join(str(values.get(column, "")).ljust(widths[column]) for column in columns))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit TheRundown MLB pitcher K query shapes.")
    parser.add_argument("date", help="Slate date in YYYY-MM-DD format")
    parser.add_argument(
        "--no-resolve-probables",
        action="store_true",
        help="Skip MLB probable-starter resolution and report parse-only coverage.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table.")
    args = parser.parse_args(argv)

    summaries = run_audit(args.date, resolve_probables=not args.no_resolve_probables)
    if args.json:
        print(json.dumps(summaries, indent=2, sort_keys=True))
    else:
        _print_table(summaries)
        for row in summaries:
            unresolved = row.get("sample_unresolved_names") or []
            if unresolved:
                print(f"\n{row['mode']} unresolved sample: {', '.join(unresolved)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
