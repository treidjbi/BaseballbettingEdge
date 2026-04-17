"""A3b spike: identify the cheapest data source for an expanded career_k_rates.json.

Current state (2026-04-17):
  data/umpires/career_k_rates.json has 30 hand-curated entries. Measured
  match rate against the 2026 HP umpire pool is ~22% (11/51 unique umps seen
  in 2026-04-14..17). Target: >=75%. We need roughly 70-80 active umps
  seeded with plausible K-rate deltas (signed K per game vs league average).

Sources investigated (2026-04-17):

  1. umpscorecards.com /api/umpires  (EVALUATED - not viable for K rate)
     - 139 umps, rich JSON, no auth
     - Best-looking fields: total_run_impact_mean, accuracy_above_x_wmean
     - total_run_impact_mean is UNSIGNED (all positive, 0.92 to 2.38) - magnitude
       of runs impacted by bad calls, not directional. Not a K proxy.
     - accuracy_above_x_wmean is signed, but cross-checking against our own
       hand-curated umps gave anti-correlation with K-delta:
         Vic Carapazza  (our +0.52 K) has usc +0.668 (more accurate)
         Rob Drake      (our +0.41 K) has usc -1.227 (less accurate)
       These diverge in sign - umpscorecards measures accuracy, not zone size.
     - CONCLUSION: umpscorecards is not a K-rate data source.

  2. pybaseball statcast (EVALUATED - dead end)
     - Has an 'umpire' column in statcast pitch data
     - Column is always NaN (dtype Int64, 0/3434 non-null in a sample day).
     - Baseball Savant deprecated this field years ago.
     - CONCLUSION: no umpire info via statcast.

  3. baseball-reference, FanGraphs, Baseball Savant leaderboards (EVALUATED)
     - All return 403 (anti-bot) or 404 (no such page) for umpire data.
     - CONCLUSION: not accessible programmatically.

  4. MLB Stats API game boxscores (VIABLE - chosen path)
     - /api/v1/schedule?sportId=1&date=D&hydrate=officials gives one call
       per day returning all games with HP umpire attached.
     - /api/v1/game/{gamePk}/boxscore gives per-game strikeOuts totals
       (home + away batting).strikeOuts per game.
     - Aggregating (sum_Ks / n_games) per ump minus league mean gives a
       clean directional K-rate delta in the same units as our existing
       career_k_rates.json (K per game vs league average).
     - Cost: ~180 schedule calls + ~4860 boxscore calls for 2 seasons
       (2024 + 2025). At 0.55s throttle ~= 45 minutes one-time seed job.
     - CONCLUSION: this is the right source. Implemented in
       scripts/seed_umpire_career_rates.py (see A3b.1 when written).

Decision:
  Proceed with the MLB Stats API approach. Use 2024 + 2025 regular season
  games (~4,860 games). For each game, key the HP umpire -> sum total Ks.
  delta = mean_ks_per_game[ump] - league_mean_ks_per_game.

  Bayesian regression: optional. With ~80-250 games per active ump across
  2 seasons, the deltas are stable without regression. Can add later if a
  few umps have small samples.

Run this spike to see the empirical output for the first handful of
umps + the time breakdown (schedule vs boxscore). Useful for estimating
how long the real seed job will take.
"""
import time
from collections import defaultdict

import requests

API = "https://statsapi.mlb.com/api/v1"
HEADERS = {"User-Agent": "BaseballBettingEdge/A3b-spike"}
THROTTLE = 0.55


def get_schedule(date_str: str) -> list[dict]:
    """Return list of game dicts with gamePk + HP ump attached."""
    r = requests.get(
        f"{API}/schedule",
        params={"sportId": 1, "date": date_str, "hydrate": "officials", "gameType": "R"},
        headers=HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    j = r.json()
    games = []
    for date_block in j.get("dates", []):
        for g in date_block.get("games", []):
            hp = next(
                (o["official"]["fullName"] for o in g.get("officials", [])
                 if o.get("officialType") == "Home Plate"),
                None,
            )
            if hp and g.get("status", {}).get("detailedState") == "Final":
                games.append({"gamePk": g["gamePk"], "hp_ump": hp})
    return games


def get_boxscore_ks(game_pk: int) -> int | None:
    """Return total strikeouts (home + away batting) for a game, or None on failure."""
    r = requests.get(f"{API}/game/{game_pk}/boxscore", headers=HEADERS, timeout=15)
    r.raise_for_status()
    j = r.json()
    try:
        h = j["teams"]["home"]["teamStats"]["batting"]["strikeOuts"]
        a = j["teams"]["away"]["teamStats"]["batting"]["strikeOuts"]
        return int(h) + int(a)
    except (KeyError, TypeError):
        return None


def main():
    print("A3b spike: measure time cost + sample output")
    print("=" * 70)
    # Use 1 week of 2025 regular-season data as a sanity check
    # (enough to confirm aggregation works; real seeder runs 2 full seasons)
    test_dates = ["2025-06-15", "2025-06-16", "2025-06-17"]

    all_games = []
    t0 = time.time()
    for d in test_dates:
        games = get_schedule(d)
        print(f"  {d}: {len(games)} final games")
        all_games.extend(games)
        time.sleep(THROTTLE)
    t_sched = time.time() - t0
    print(f"\nSchedule fetch: {len(all_games)} games in {t_sched:.1f}s "
          f"({len(test_dates)} calls)")

    by_ump = defaultdict(list)
    t0 = time.time()
    for i, g in enumerate(all_games, 1):
        ks = get_boxscore_ks(g["gamePk"])
        if ks is not None:
            by_ump[g["hp_ump"]].append(ks)
        if i % 10 == 0:
            print(f"  progress: {i}/{len(all_games)} games")
        time.sleep(THROTTLE)
    t_box = time.time() - t0
    print(f"\nBoxscore fetch: {len(all_games)} games in {t_box:.1f}s")

    print()
    print("Aggregated K-per-game by HP umpire (sample window):")
    all_ks = [k for ks in by_ump.values() for k in ks]
    league_mean = sum(all_ks) / len(all_ks) if all_ks else 0
    print(f"League mean K/game across sample: {league_mean:.2f}")
    print()
    for ump, ks in sorted(by_ump.items(), key=lambda x: -len(x[1])):
        mean = sum(ks) / len(ks)
        delta = mean - league_mean
        print(f"  {ump:30} n={len(ks):<2} mean={mean:.2f} delta={delta:+.3f}")

    # Extrapolate: 2 full seasons = ~4860 games + ~365 schedule calls
    est_sched = 365 * THROTTLE
    # Game count per day in the sample
    avg_games_per_day = len(all_games) / len(test_dates)
    est_games = int(avg_games_per_day * 180 * 2)  # ~180 game days per season, 2 seasons
    est_box = est_games * THROTTLE
    print()
    print(f"Extrapolation for 2024+2025 regular seasons:")
    print(f"  est schedule calls: ~365 days = {est_sched/60:.1f} min")
    print(f"  est games: {est_games} boxscore calls = {est_box/60:.1f} min")
    print(f"  TOTAL: ~{(est_sched+est_box)/60:.1f} min one-time seed job")


if __name__ == "__main__":
    main()
