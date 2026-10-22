"""Reconstruct historical opponent lineup handedness for Gate C research.

This script reads the compact pitcher K outcome rows, fetches MLB schedule and
boxscore data, and writes local shadow artifacts only. The reconstructed fields
are useful for model research but are not runtime availability proof.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analytics.diagnostics.pitcher_k_outcome_dataset import (
    OUTPUT_JSONL,
    handedness_matchup_bucket,
    lineup_handedness_lookup_key,
)
from pipeline.name_utils import normalize


MLB_BASE = "https://statsapi.mlb.com/api/v1"
OUTPUT_JSON = ROOT / "analytics" / "output" / "lineup_handedness_backfill.json"
OUTPUT_SUMMARY = ROOT / "analytics" / "output" / "lineup_handedness_backfill_summary.md"
HTTP_CACHE = ROOT / "analytics" / "output" / "lineup_handedness_mlb_cache.json"


ScheduleFetcher = Callable[[str], dict[str, Any] | None]
BoxscoreFetcher = Callable[[int], dict[str, Any] | None]


def _normalized(value: Any) -> str:
    return normalize(str(value or "")).strip()


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def load_dataset_rows(path: Path = OUTPUT_JSONL) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _team_name(game: dict[str, Any], side_key: str) -> str:
    return str(
        (((game.get("teams") or {}).get(side_key) or {}).get("team") or {}).get("name")
        or ""
    )


def _side_for_team(game: dict[str, Any], team_name: Any) -> str | None:
    team = _normalized(team_name)
    if _normalized(_team_name(game, "away")) == team:
        return "away"
    if _normalized(_team_name(game, "home")) == team:
        return "home"
    return None


def _candidate_games(
    schedule: dict[str, Any],
    *,
    team: Any,
    opp_team: Any,
) -> list[dict[str, Any]]:
    team_norm = _normalized(team)
    opp_norm = _normalized(opp_team)
    candidates: list[dict[str, Any]] = []
    for date_entry in schedule.get("dates", []) or []:
        for game in date_entry.get("games", []) or []:
            away = _normalized(_team_name(game, "away"))
            home = _normalized(_team_name(game, "home"))
            if {away, home} == {team_norm, opp_norm}:
                candidates.append(game)
    return candidates


def _select_game(candidates: list[dict[str, Any]], game_time: Any) -> dict[str, Any] | None:
    if not candidates:
        return None
    target = _parse_dt(game_time)
    if target is None:
        return candidates[0] if len(candidates) == 1 else None

    def distance(game: dict[str, Any]) -> float:
        game_dt = _parse_dt(game.get("gameDate"))
        if game_dt is None:
            return float("inf")
        return abs((game_dt - target).total_seconds())

    best = min(candidates, key=distance)
    return best if distance(best) != float("inf") else None


def extract_lineup_handedness(boxscore: dict[str, Any], side_key: str) -> dict[str, Any] | None:
    team_block = ((boxscore.get("teams") or {}).get(side_key) or {})
    order = team_block.get("battingOrder") or []
    players = team_block.get("players") or {}
    if not order:
        return None

    names: list[str] = []
    bats_list: list[str] = []
    hand_counts: Counter[str] = Counter()
    for player_id in order:
        entry = players.get(f"ID{player_id}") or {}
        person = entry.get("person") or {}
        name = person.get("fullName") or "Unknown"
        bats = str(((person.get("batSide") or {}).get("code")) or "R").upper()
        if bats not in {"R", "L", "S"}:
            bats = "R"
        names.append(name)
        bats_list.append(bats)
        hand_counts[bats] += 1

    return {
        "lineup_count": len(bats_list),
        "lineup_right_batters": hand_counts["R"],
        "lineup_left_batters": hand_counts["L"],
        "lineup_switch_batters": hand_counts["S"],
        "lineup_bats": bats_list,
        "lineup_names": names,
    }


def _load_http_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schedules": {}, "boxscores": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schedules": {}, "boxscores": {}}
    if not isinstance(payload, dict):
        return {"schedules": {}, "boxscores": {}}
    payload.setdefault("schedules", {})
    payload.setdefault("boxscores", {})
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def make_cached_fetchers(cache_path: Path = HTTP_CACHE, *, delay_seconds: float = 0.05) -> tuple[ScheduleFetcher, BoxscoreFetcher, Callable[[], None]]:
    cache = _load_http_cache(cache_path)

    def fetch_schedule(date_str: str) -> dict[str, Any] | None:
        schedules = cache.setdefault("schedules", {})
        if date_str in schedules:
            return schedules[date_str]
        response = requests.get(f"{MLB_BASE}/schedule", params={"sportId": 1, "date": date_str}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        schedules[date_str] = payload
        time.sleep(delay_seconds)
        return payload

    def fetch_boxscore(game_pk: int) -> dict[str, Any] | None:
        key = str(game_pk)
        boxscores = cache.setdefault("boxscores", {})
        if key in boxscores:
            return boxscores[key]
        response = requests.get(f"{MLB_BASE}/game/{game_pk}/boxscore", timeout=20)
        response.raise_for_status()
        payload = response.json()
        boxscores[key] = payload
        time.sleep(delay_seconds)
        return payload

    def persist() -> None:
        _write_json(cache_path, cache)

    return fetch_schedule, fetch_boxscore, persist


def build_historical_lineup_backfill(
    rows: list[dict[str, Any]],
    *,
    schedule_fetcher: ScheduleFetcher,
    boxscore_fetcher: BoxscoreFetcher,
) -> dict[str, Any]:
    lineups: dict[str, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    count_mismatches = 0

    for row in rows:
        key = lineup_handedness_lookup_key(
            row.get("slate_date"),
            row.get("team"),
            row.get("opp_team"),
            row.get("game_time"),
        )
        if not key.strip("|") or key in seen_keys:
            continue
        seen_keys.add(key)

        slate_date = str(row.get("slate_date") or "").strip()
        team = row.get("team")
        opp_team = row.get("opp_team")
        if not slate_date or not team or not opp_team:
            unmatched.append({"lookup_key": key, "reason": "missing date/team/opponent"})
            continue

        try:
            schedule = schedule_fetcher(slate_date)
        except Exception as exc:  # pragma: no cover - network defensive path
            unmatched.append({"lookup_key": key, "reason": f"schedule fetch failed: {type(exc).__name__}"})
            continue
        if not schedule:
            unmatched.append({"lookup_key": key, "reason": "schedule missing"})
            continue

        game = _select_game(
            _candidate_games(schedule, team=team, opp_team=opp_team),
            row.get("game_time"),
        )
        if not game:
            unmatched.append({"lookup_key": key, "reason": "game not matched"})
            continue

        side_key = _side_for_team(game, opp_team)
        game_pk = game.get("gamePk")
        if side_key is None or game_pk is None:
            unmatched.append({"lookup_key": key, "reason": "opponent side not matched"})
            continue

        try:
            boxscore = boxscore_fetcher(int(game_pk))
        except Exception as exc:  # pragma: no cover - network defensive path
            unmatched.append({"lookup_key": key, "reason": f"boxscore fetch failed: {type(exc).__name__}"})
            continue
        if not boxscore:
            unmatched.append({"lookup_key": key, "reason": "boxscore missing"})
            continue

        lineup = extract_lineup_handedness(boxscore, side_key)
        if not lineup:
            unmatched.append({"lookup_key": key, "reason": "lineup missing from boxscore"})
            continue

        expected_count = _to_int(row.get("lineup_count"))
        count_matches = expected_count is None or expected_count == lineup["lineup_count"]
        if not count_matches:
            count_mismatches += 1

        lineups[key] = {
            **lineup,
            "slate_date": slate_date,
            "team": team,
            "opp_team": opp_team,
            "game_time": row.get("game_time"),
            "game_pk": int(game_pk),
            "side_key": side_key,
            "lineup_handedness_source": "mlb_boxscore_reconstructed",
            "lineup_handedness_runtime_safe": False,
            "lineup_count_matches_existing": count_matches,
            "handedness_matchup_bucket": handedness_matchup_bucket(
                pitcher_throws=row.get("pitcher_throws"),
                right_batters=lineup["lineup_right_batters"],
                left_batters=lineup["lineup_left_batters"],
                switch_batters=lineup["lineup_switch_batters"],
            ),
        }

    return {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "mlb_boxscore_reconstructed",
        "runtime_safe": False,
        "lineups": lineups,
        "unmatched": unmatched,
        "summary": {
            "dataset_rows": len(rows),
            "unique_lineup_keys": len(seen_keys),
            "reconstructed_lineups": len(lineups),
            "unmatched_lineups": len(unmatched),
            "lineup_count_mismatches": count_mismatches,
        },
    }


def render_summary(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "# Historical Lineup Handedness Backfill",
        "",
        "Shadow-only: reconstructed MLB boxscore evidence for Gate C research. This is not proof the fields were available at bet time.",
        "",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Dataset rows checked: `{summary.get('dataset_rows', 0)}`",
        f"- Unique lineup keys: `{summary.get('unique_lineup_keys', 0)}`",
        f"- Reconstructed lineups: `{summary.get('reconstructed_lineups', 0)}`",
        f"- Unmatched lineups: `{summary.get('unmatched_lineups', 0)}`",
        f"- Existing lineup-count mismatches: `{summary.get('lineup_count_mismatches', 0)}`",
        "- Runtime-safe for live decisions: `no`",
        "",
        "## Unmatched Examples",
        "",
    ]
    unmatched = payload.get("unmatched") or []
    if not unmatched:
        lines.append("- none")
    else:
        for item in unmatched[:10]:
            lines.append(f"- `{item.get('lookup_key')}`: {item.get('reason')}")
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill historical lineup handedness from MLB boxscores.")
    parser.add_argument("--dataset", type=Path, default=OUTPUT_JSONL)
    parser.add_argument("--output", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--summary-output", type=Path, default=OUTPUT_SUMMARY)
    parser.add_argument("--http-cache", type=Path, default=HTTP_CACHE)
    parser.add_argument("--delay-seconds", type=float, default=0.05)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    rows = load_dataset_rows(args.dataset)
    schedule_fetcher, boxscore_fetcher, persist_cache = make_cached_fetchers(
        args.http_cache,
        delay_seconds=args.delay_seconds,
    )
    payload = build_historical_lineup_backfill(
        rows,
        schedule_fetcher=schedule_fetcher,
        boxscore_fetcher=boxscore_fetcher,
    )
    persist_cache()
    _write_json(args.output, payload)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(render_summary(payload), encoding="utf-8")
    print(render_summary(payload))


if __name__ == "__main__":
    main()
