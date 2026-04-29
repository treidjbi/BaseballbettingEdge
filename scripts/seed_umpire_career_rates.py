"""Seed data/umpires/career_k_rates.json from MLB Stats API game boxscores.

WHY:
  After A3-fix replaced ump.news with MLB Stats API (2026-04-17), the live
  HP-umpire-per-game lookup works correctly. But the hand-curated
  career_k_rates.json has only 30 umpires (some retired). Measured match
  rate against the 2026 active pool is ~22%. This script derives career
  K-rate deltas for every umpire empirically from real boxscore data.

HOW:
  For each day in the target season window:
    1. /api/v1/schedule?date=D&hydrate=officials&gameType=R
         -> list of (gamePk, HP_umpire_name) for Final games
    2. /api/v1/game/{gamePk}/boxscore
         -> home.batting.strikeOuts + away.batting.strikeOuts
  Aggregate per umpire:
    mean_ks[ump] = sum(game_Ks) / n_games
  League mean:
    league_mean = sum(all game Ks) / total games
  Write:
    career_k_rates.json = { ump_name: mean_ks[ump] - league_mean }

RESUMABILITY:
  Intermediate progress is cached to analytics/output/seed_progress.json
  after each day. Re-running picks up where it left off. Individual game
  boxscore failures are logged but don't stop the run.

USAGE:
  python scripts/seed_umpire_career_rates.py \
      --start 2024-03-28 --end 2025-10-01

  python scripts/seed_umpire_career_rates.py --start 2025-06-01 --end 2025-06-07
      # small-window dry run

OUTPUT FILE FORMAT:
  { "Umpire Name": {"delta": delta_K_per_game_vs_league_avg, "hp_games": n}, ... }
  Deltas are signed, unit = K per game. e.g., -0.50 = ump suppresses Ks,
  +0.70 = ump produces more Ks than average. fetch_umpires.py still accepts
  the legacy numeric format for existing files.

OPTIONS:
  --min-games N    only include umps with >= N games (default: 10)
                   smaller samples give unstable estimates
  --output PATH    output JSON path (default: data/umpires/career_k_rates.json)
  --no-write       skip writing the output file (print only)
"""
import argparse
import json
import logging
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CAREER_RATES_FILE = ROOT / "data" / "umpires" / "career_k_rates.json"
PROGRESS_FILE = ROOT / "analytics" / "output" / "seed_progress.json"
LOG_FILE = ROOT / "analytics" / "output" / "seed_umpire_career_rates.log"

API = "https://statsapi.mlb.com/api/v1"
HEADERS = {"User-Agent": "BaseballBettingEdge/seed-umpire-career-rates"}
THROTTLE = 0.55  # 2 req/sec budget - stay under

log = logging.getLogger("seed_umpire_career_rates")


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def load_progress() -> dict:
    """Return {'completed_dates': [str], 'games': [(gamePk, ump, ks)]}."""
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"completed_dates": [], "games": []}


def save_progress(progress: dict) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


def get_final_games_with_hp(date_str: str, max_retries: int = 3) -> list[tuple[int, str]]:
    """Return [(gamePk, HP_ump_fullName), ...] for all Final regular-season games on date_str."""
    for attempt in range(max_retries):
        try:
            r = requests.get(
                f"{API}/schedule",
                params={"sportId": 1, "date": date_str, "hydrate": "officials", "gameType": "R"},
                headers=HEADERS,
                timeout=20,
            )
            r.raise_for_status()
            j = r.json()
            out = []
            for date_block in j.get("dates", []):
                for g in date_block.get("games", []):
                    if g.get("status", {}).get("detailedState") != "Final":
                        continue
                    hp = next(
                        (o["official"]["fullName"] for o in g.get("officials", [])
                         if o.get("officialType") == "Home Plate"),
                        None,
                    )
                    if hp:
                        out.append((g["gamePk"], hp))
            return out
        except Exception as exc:
            log.warning("schedule %s attempt %d failed: %r", date_str, attempt + 1, exc)
            time.sleep(2 ** attempt)
    log.error("schedule %s failed after %d attempts - skipping day", date_str, max_retries)
    return []


def get_boxscore_ks(game_pk: int, max_retries: int = 3) -> int | None:
    """Return total batting strikeouts (home + away) for a game, or None on failure."""
    for attempt in range(max_retries):
        try:
            r = requests.get(f"{API}/game/{game_pk}/boxscore", headers=HEADERS, timeout=20)
            r.raise_for_status()
            j = r.json()
            h = j["teams"]["home"]["teamStats"]["batting"]["strikeOuts"]
            a = j["teams"]["away"]["teamStats"]["batting"]["strikeOuts"]
            return int(h) + int(a)
        except KeyError:
            # Final-but-no-boxscore - rare, skip
            return None
        except Exception as exc:
            log.warning("boxscore %d attempt %d failed: %r", game_pk, attempt + 1, exc)
            time.sleep(2 ** attempt)
    log.error("boxscore %d failed after %d attempts - skipping game", game_pk, max_retries)
    return None


def aggregate(games: list[tuple[int, str, int]]) -> dict:
    """games: [(gamePk, ump, total_ks)] -> {ump: (n, sum_ks, mean_ks, delta_vs_league)}."""
    by_ump = defaultdict(list)
    for _, ump, ks in games:
        by_ump[ump].append(ks)
    all_ks = [ks for _, _, ks in games]
    league_mean = sum(all_ks) / len(all_ks) if all_ks else 0
    return {
        ump: {
            "n": len(v),
            "sum_ks": sum(v),
            "mean_ks": sum(v) / len(v),
            "delta": sum(v) / len(v) - league_mean,
        }
        for ump, v in by_ump.items()
    }, league_mean


def write_output(agg: dict, min_games: int, output_path: Path) -> dict:
    """Write {ump: {delta, hp_games}} JSON sorted by name. Filter by min_games."""
    kept = {
        ump: {"delta": round(d["delta"], 3), "hp_games": int(d["n"])}
        for ump, d in agg.items()
        if d["n"] >= min_games
    }
    # Sort alphabetically for stable diffs; JSON preserves insertion order.
    ordered = {k: kept[k] for k in sorted(kept.keys())}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n")
    return ordered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--min-games", type=int, default=10,
                        help="minimum games an ump must have to be included (default 10)")
    parser.add_argument("--output", type=Path, default=CAREER_RATES_FILE)
    parser.add_argument("--no-write", action="store_true",
                        help="don't write output file, just print")
    parser.add_argument("--fresh", action="store_true",
                        help="ignore seed_progress.json and start over")
    args = parser.parse_args()

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
    )

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    progress = {"completed_dates": [], "games": []} if args.fresh else load_progress()
    done_set = set(progress["completed_dates"])
    # games list is [(gamePk, ump, ks)]
    games = [tuple(g) for g in progress["games"]]

    all_dates = list(daterange(start, end))
    todo = [d for d in all_dates if d.isoformat() not in done_set]
    log.info("Date window: %s to %s (%d total days, %d already completed, %d remaining)",
             start, end, len(all_dates), len(all_dates) - len(todo), len(todo))
    log.info("Resumed from progress file: %d games collected so far", len(games))

    for i, d in enumerate(todo, 1):
        date_str = d.isoformat()
        pairs = get_final_games_with_hp(date_str)
        time.sleep(THROTTLE)
        day_games = 0
        for game_pk, ump in pairs:
            ks = get_boxscore_ks(game_pk)
            if ks is not None:
                games.append((game_pk, ump, ks))
                day_games += 1
            time.sleep(THROTTLE)
        progress["completed_dates"].append(date_str)
        progress["games"] = games
        save_progress(progress)
        log.info("  day %d/%d  %s  %d games  total_games=%d",
                 i, len(todo), date_str, day_games, len(games))

    log.info("Total games collected: %d", len(games))
    agg, league_mean = aggregate(games)
    log.info("League mean K/game: %.3f", league_mean)
    log.info("Umpires seen: %d (all samples); with n>=%d: %d",
             len(agg), args.min_games, sum(1 for v in agg.values() if v["n"] >= args.min_games))

    # Summary: highest / lowest deltas
    ranked = sorted(agg.items(), key=lambda x: x[1]["delta"])
    ranked_enough = [r for r in ranked if r[1]["n"] >= args.min_games]
    log.info("10 LOWEST delta umps (>= min_games):")
    for ump, d in ranked_enough[:10]:
        log.info("  %-30s n=%3d mean=%.2f delta=%+.3f", ump, d["n"], d["mean_ks"], d["delta"])
    log.info("10 HIGHEST delta umps (>= min_games):")
    for ump, d in ranked_enough[-10:]:
        log.info("  %-30s n=%3d mean=%.2f delta=%+.3f", ump, d["n"], d["mean_ks"], d["delta"])

    if not args.no_write:
        written = write_output(agg, args.min_games, args.output)
        log.info("Wrote %d umpires to %s", len(written), args.output)


if __name__ == "__main__":
    main()
