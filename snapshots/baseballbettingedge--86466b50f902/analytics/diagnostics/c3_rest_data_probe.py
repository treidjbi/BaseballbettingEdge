"""Read-only probe for C3 rest/workload fields on the MLB Stats API."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

import requests


MLB_BASE = "https://statsapi.mlb.com/api/v1"
DEFAULT_PLAYER_ID = 571927  # Steven Matz
DEFAULT_SEASON = 2026
DEFAULT_LIMIT = 10


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.get(f"{MLB_BASE}{path}", params=params, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SystemExit(f"ERROR: request failed for {path}: {exc}") from exc
    return response.json()


def _extract_start_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    splits = ((payload.get("stats") or [{}])[0]).get("splits") or []
    starts = [
        split for split in splits
        if int(split.get("stat", {}).get("gamesStarted", 0) or 0) > 0
    ]
    return sorted(
        starts,
        key=lambda split: _parse_date(split.get("date")) or datetime.min,
        reverse=True,
    )


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return None


def _summarize_start(split: dict[str, Any]) -> dict[str, Any]:
    stat = split.get("stat", {})
    return {
        "date": split.get("date"),
        "inningsPitched": stat.get("inningsPitched"),
        "strikeOuts": stat.get("strikeOuts"),
        "numberOfPitches": stat.get("numberOfPitches"),
        "gamesStarted": stat.get("gamesStarted"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-id", type=int, default=DEFAULT_PLAYER_ID)
    parser.add_argument("--season", type=int, default=DEFAULT_SEASON)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    payload = _get(
        f"/people/{args.player_id}/stats",
        {
            "stats": "gameLog",
            "group": "pitching",
            "season": args.season,
            "limit": args.limit,
        },
    )
    starts = _extract_start_rows(payload)
    if not starts:
        raise SystemExit(
            f"ERROR: no started gameLog splits found for player_id={args.player_id} season={args.season}"
        )

    first_start = _summarize_start(starts[0])
    if first_start.get("date") in (None, ""):
        raise SystemExit("ERROR: first filtered start is missing top-level split['date']")
    if first_start.get("numberOfPitches") in (None, ""):
        raise SystemExit("ERROR: first filtered start is missing stat['numberOfPitches']")

    print("=== C3 rest/workload probe ===")
    print(f"player_id: {args.player_id}")
    print(f"season: {args.season}")
    print(f"started splits returned: {len(starts)}")
    print("first filtered start:")
    print(json.dumps(first_start, indent=2))
    print("\nfirst five filtered starts:")
    print(json.dumps([_summarize_start(split) for split in starts[:5]], indent=2))


if __name__ == "__main__":
    main()
