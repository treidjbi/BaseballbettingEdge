"""
backfill_results.py
One-time script to seed historical picks (from processed JSON files) into
results.db and close them against the MLB Stats API.

Run once from the repo root:
    py -3 pipeline/backfill_results.py

Safe to re-run — INSERT OR IGNORE prevents duplicates.
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import pytz
import requests

# Reuse init_db, get_db, _normalize, _calc_pnl from fetch_results
sys.path.insert(0, str(Path(__file__).parent))
from fetch_results import init_db, get_db, _normalize, _calc_pnl

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).parent.parent / "dashboard" / "data" / "processed"
MLB_BASE = "https://statsapi.mlb.com/api/v1"


def _seed_historical(json_path: Path) -> tuple[str, int]:
    """Seed non-PASS picks from a historical processed JSON. Returns (date, inserted_count)."""
    data = json.loads(json_path.read_text())
    game_date = data["date"]
    inserted = 0

    with get_db() as conn:
        for p in data.get("pitchers", []):
            for side in ("over", "under"):
                ev_data = p.get(f"ev_{side}")
                if not ev_data or ev_data.get("verdict") == "PASS":
                    continue
                odds = p.get(f"best_{side}_odds")
                if odds is None:
                    continue
                cur = conn.execute("""
                    INSERT OR IGNORE INTO picks
                    (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                     raw_lambda, applied_lambda, odds, movement_conf,
                     season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    game_date, p["pitcher"], p["team"], side,
                    p["k_line"], ev_data["verdict"], ev_data["ev"], ev_data["adj_ev"],
                    p.get("raw_lambda", p["lambda"]), p["lambda"], odds,
                    ev_data.get("movement_conf", 1.0),
                    p.get("season_k9"), p.get("recent_k9"), p.get("career_k9"),
                    p.get("avg_ip"), p.get("ump_k_adj"), p.get("opp_k_rate"),
                ))
                inserted += cur.rowcount

    return game_date, inserted


def _close_date(date_str: str) -> int:
    """Fetch MLB box scores for date_str and close open picks. Returns resolved count."""
    with get_db() as conn:
        open_picks = conn.execute(
            "SELECT * FROM picks WHERE date=? AND result IS NULL", (date_str,)
        ).fetchall()

    if not open_picks:
        log.info("%s — no open picks to close", date_str)
        return 0

    try:
        resp = requests.get(f"{MLB_BASE}/schedule", params={
            "sportId": 1, "date": date_str,
        }, timeout=30)
        resp.raise_for_status()
        schedule = resp.json()
    except Exception as e:
        log.error("%s — MLB API fetch failed: %s", date_str, e)
        return 0

    ks_by_name: dict[str, int] = {}
    finalized_teams: set[str] = set()

    for date_entry in schedule.get("dates", []):
        for game in date_entry.get("games", []):
            is_final = game.get("status", {}).get("abstractGameState") == "Final"
            game_pk  = game.get("gamePk")

            for ts in ("home", "away"):
                team_info = game.get("teams", {}).get(ts, {}).get("team", {})
                team_keys = {team_info.get("name", "").lower(),
                             team_info.get("abbreviation", "").lower()}
                if is_final:
                    finalized_teams |= team_keys

            if not is_final or not game_pk:
                continue

            try:
                bs_resp = requests.get(f"{MLB_BASE}/game/{game_pk}/boxscore", timeout=30)
                bs_resp.raise_for_status()
                boxscore = bs_resp.json()
            except Exception as e:
                log.warning("%s — boxscore fetch failed for game %s: %s", date_str, game_pk, e)
                continue

            for ts in ("home", "away"):
                players        = boxscore.get("teams", {}).get(ts, {}).get("players", {})
                pitchers_order = boxscore.get("teams", {}).get(ts, {}).get("pitchers", [])
                if not pitchers_order:
                    continue
                starter = players.get(f"ID{pitchers_order[0]}", {})
                name = starter.get("person", {}).get("fullName", "")
                ks   = starter.get("stats", {}).get("pitching", {}).get("strikeOuts")
                if name and ks is not None:
                    ks_by_name[_normalize(name)] = int(ks)

    closed = 0
    now_str = datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_db() as conn:
        for pick in open_picks:
            norm     = _normalize(pick["pitcher"])
            team_norm = pick["team"].lower()

            if norm in ks_by_name:
                actual_ks = ks_by_name[norm]
                k_line    = pick["k_line"]
                side      = pick["side"]
                if actual_ks > k_line:
                    result = "win" if side == "over" else "loss"
                elif actual_ks < k_line:
                    result = "loss" if side == "over" else "win"
                else:
                    result = "push"
                pnl = _calc_pnl(result, pick["odds"])
                conn.execute(
                    "UPDATE picks SET actual_ks=?,result=?,pnl=?,fetched_at=? WHERE id=?",
                    (actual_ks, result, pnl, now_str, pick["id"])
                )
                log.info("  %-25s %s  actual=%d  line=%.1f  → %s",
                         pick["pitcher"], side, actual_ks, k_line, result)
                closed += 1

            elif any(team_norm in ft or ft in team_norm for ft in finalized_teams):
                conn.execute(
                    "UPDATE picks SET result='void',pnl=0.0,fetched_at=? WHERE id=?",
                    (now_str, pick["id"])
                )
                log.info("  %-25s %s  → void (scratched)", pick["pitcher"], pick["side"])
                closed += 1
            else:
                log.warning("  %-25s %s  → no result found (game not final?)", pick["pitcher"], pick["side"])

    return closed


def run() -> None:
    init_db()

    # Collect all historical processed files, excluding today.json and index.json,
    # and excluding dates already fully closed in the DB.
    with get_db() as conn:
        already_closed = {
            r[0] for r in conn.execute(
                "SELECT date FROM picks WHERE result IS NOT NULL GROUP BY date"
            ).fetchall()
        }

    json_files = sorted(
        f for f in PROCESSED_DIR.glob("????-??-??.json")
        if "today" not in f.name and "index" not in f.name
    )

    total_seeded  = 0
    total_closed  = 0

    for json_path in json_files:
        date_str, seeded = _seed_historical(json_path)
        total_seeded += seeded
        if seeded:
            log.info("%s — seeded %d picks", date_str, seeded)

        if date_str in already_closed:
            log.info("%s — already closed, skipping API call", date_str)
            continue

        closed = _close_date(date_str)
        total_closed += closed
        log.info("%s — closed %d picks", date_str, closed)

    log.info("Done. Seeded %d new picks, closed %d results total.", total_seeded, total_closed)

    # Print summary
    with get_db() as conn:
        rows = conn.execute("""
            SELECT date,
                   COUNT(*) as total,
                   SUM(result='win') as wins,
                   SUM(result='loss') as losses,
                   SUM(result='push') as pushes,
                   SUM(result='void') as voids,
                   SUM(result IS NULL) as open
            FROM picks GROUP BY date ORDER BY date
        """).fetchall()

    print("\n-- Results DB Summary ------------------------------------------")
    print(f"{'Date':<12} {'Total':>5} {'W':>4} {'L':>4} {'P':>4} {'Void':>5} {'Open':>5}")
    print("-" * 50)
    for r in rows:
        print(f"{r[0]:<12} {r[1]:>5} {r[2] or 0:>4} {r[3] or 0:>4} {r[4] or 0:>4} {r[5] or 0:>5} {r[6] or 0:>5}")


if __name__ == "__main__":
    run()
