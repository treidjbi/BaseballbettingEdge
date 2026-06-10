"""Reconstruct postgame pitcher opportunity for Gate C research.

This script reads compact pitcher K outcome rows, fetches MLB schedule and
boxscore data, and writes local shadow artifacts only. The reconstructed fields
are post-result diagnostics and are not runtime availability proof.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from analytics.diagnostics.pitcher_k_outcome_dataset import (  # noqa: E402
    ACTUAL_OPPORTUNITY_BACKFILL,
    OUTPUT_JSONL,
    actual_opportunity_lookup_key,
)
from pipeline.name_utils import normalize  # noqa: E402


MLB_BASE = "https://statsapi.mlb.com/api/v1"
OUTPUT_JSON = ACTUAL_OPPORTUNITY_BACKFILL
OUTPUT_SUMMARY = ROOT / "analytics" / "output" / "actual_opportunity_backfill_summary.md"
HTTP_CACHE = ROOT / "analytics" / "output" / "actual_opportunity_mlb_cache.json"


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


def _parse_mlb_ip(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        whole_text, _, outs_text = text.partition(".")
        whole = int(whole_text or "0")
        outs = int(outs_text or "0")
        if outs not in {0, 1, 2}:
            return None
        return whole + outs / 3.0
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


def extract_pitcher_opportunity(
    boxscore: dict[str, Any],
    side_key: str,
    pitcher_name: Any,
) -> dict[str, Any] | None:
    team_block = ((boxscore.get("teams") or {}).get(side_key) or {})
    pitchers = team_block.get("pitchers") or []
    players = team_block.get("players") or {}
    pitcher_norm = _normalized(pitcher_name)
    if not pitcher_norm:
        return None

    for pitcher_id in pitchers:
        entry = players.get(f"ID{pitcher_id}") or {}
        person = entry.get("person") or {}
        if _normalized(person.get("fullName")) != pitcher_norm:
            continue
        pitching = (entry.get("stats") or {}).get("pitching") or {}
        actual_ip = _parse_mlb_ip(pitching.get("inningsPitched"))
        pitch_count = _to_int(pitching.get("numberOfPitches"))
        batters_faced = _to_int(pitching.get("battersFaced"))
        if actual_ip is None and pitch_count is None and batters_faced is None:
            return None
        return {
            "actual_ip": actual_ip,
            "actual_pitch_count": pitch_count,
            "batters_faced": batters_faced,
            "pitcher_match_type": "normalized_name",
            "boxscore_pitcher_name": person.get("fullName"),
        }
    return None


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


def make_cached_fetchers(
    cache_path: Path = HTTP_CACHE,
    *,
    delay_seconds: float = 0.05,
) -> tuple[ScheduleFetcher, BoxscoreFetcher, Callable[[], None]]:
    cache = _load_http_cache(cache_path)

    def fetch_schedule(date_str: str) -> dict[str, Any] | None:
        schedules = cache.setdefault("schedules", {})
        if date_str in schedules:
            return schedules[date_str]
        response = requests.get(
            f"{MLB_BASE}/schedule",
            params={"sportId": 1, "date": date_str},
            timeout=20,
        )
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


def build_actual_opportunity_backfill(
    rows: list[dict[str, Any]],
    *,
    schedule_fetcher: ScheduleFetcher,
    boxscore_fetcher: BoxscoreFetcher,
) -> dict[str, Any]:
    opportunities: dict[str, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for row in rows:
        key = actual_opportunity_lookup_key(
            row.get("slate_date"),
            row.get("team"),
            row.get("opp_team"),
            row.get("game_time"),
            row.get("pitcher") or row.get("normalized_pitcher"),
        )
        if not key.strip("|") or key in seen_keys:
            continue
        seen_keys.add(key)

        slate_date = str(row.get("slate_date") or "").strip()
        team = row.get("team")
        opp_team = row.get("opp_team")
        pitcher = row.get("pitcher") or row.get("normalized_pitcher")
        if not slate_date or not team or not opp_team or not pitcher:
            unmatched.append({"lookup_key": key, "reason": "missing date/team/opponent/pitcher"})
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

        side_key = _side_for_team(game, team)
        game_pk = game.get("gamePk")
        if side_key is None or game_pk is None:
            unmatched.append({"lookup_key": key, "reason": "pitcher team side not matched"})
            continue

        try:
            boxscore = boxscore_fetcher(int(game_pk))
        except Exception as exc:  # pragma: no cover - network defensive path
            unmatched.append({"lookup_key": key, "reason": f"boxscore fetch failed: {type(exc).__name__}"})
            continue
        if not boxscore:
            unmatched.append({"lookup_key": key, "reason": "boxscore missing"})
            continue

        opportunity = extract_pitcher_opportunity(boxscore, side_key, pitcher)
        if not opportunity:
            unmatched.append({"lookup_key": key, "reason": "pitcher opportunity missing from boxscore"})
            continue

        opportunities[key] = {
            **opportunity,
            "slate_date": slate_date,
            "team": team,
            "opp_team": opp_team,
            "game_time": row.get("game_time"),
            "pitcher": pitcher,
            "game_pk": int(game_pk),
            "side_key": side_key,
            "actual_opportunity_source": "mlb_boxscore_reconstructed",
            "actual_opportunity_runtime_safe": False,
        }

    return {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "mlb_boxscore_reconstructed",
        "runtime_safe": False,
        "opportunities": opportunities,
        "unmatched": unmatched,
        "summary": {
            "dataset_rows": len(rows),
            "unique_opportunity_keys": len(seen_keys),
            "reconstructed_opportunities": len(opportunities),
            "unmatched_opportunities": len(unmatched),
        },
    }


def render_summary(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "# Actual Opportunity Backfill",
        "",
        "Shadow-only: reconstructed MLB boxscore evidence for Gate C research. This is not proof the fields were available at bet time.",
        "",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Dataset rows checked: `{summary.get('dataset_rows', 0)}`",
        f"- Unique opportunity keys: `{summary.get('unique_opportunity_keys', 0)}`",
        f"- Reconstructed opportunities: `{summary.get('reconstructed_opportunities', 0)}`",
        f"- Unmatched opportunities: `{summary.get('unmatched_opportunities', 0)}`",
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
    parser = argparse.ArgumentParser(description="Backfill actual pitcher opportunity from MLB boxscores.")
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
    payload = build_actual_opportunity_backfill(
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
