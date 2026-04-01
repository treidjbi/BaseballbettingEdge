"""
fetch_results.py
Seeds today's non-PASS picks into SQLite, then fetches yesterday's box scores
from the MLB Stats API to close out results.
Run as part of the 8pm pipeline run only.
"""
import json
import logging
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import pytz
import requests

log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")
MLB_BASE = "https://statsapi.mlb.com/api/v1"

DB_PATH = Path(__file__).parent.parent / "data" / "results.db"
TODAY_JSON = Path(__file__).parent.parent / "dashboard" / "data" / "processed" / "today.json"


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS picks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT NOT NULL,
                pitcher         TEXT NOT NULL,
                team            TEXT NOT NULL,
                side            TEXT NOT NULL,
                k_line          REAL NOT NULL,
                verdict         TEXT NOT NULL,
                ev              REAL NOT NULL,
                adj_ev          REAL NOT NULL,
                raw_lambda      REAL NOT NULL,
                applied_lambda  REAL NOT NULL,
                odds            INTEGER NOT NULL,
                movement_conf   REAL NOT NULL,
                season_k9       REAL,
                recent_k9       REAL,
                career_k9       REAL,
                avg_ip          REAL,
                ump_k_adj       REAL,
                opp_k_rate      REAL,
                result          TEXT,
                actual_ks       INTEGER,
                pnl             REAL,
                fetched_at      TEXT
            )
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_picks_date_pitcher_side
            ON picks (date, pitcher, side)
        """)


def seed_picks(today_json_path: Path = TODAY_JSON) -> int:
    """Insert non-PASS picks from today.json. Returns count of new rows inserted."""
    try:
        with open(today_json_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        log.warning("seed_picks: could not read %s: %s — skipping seed", today_json_path, e)
        return 0

    game_date = data["date"]
    inserted = 0

    with get_db() as conn:
        for p in data.get("pitchers", []):
            for side in ("over", "under"):
                ev_data = p[f"ev_{side}"]
                if ev_data["verdict"] == "PASS":
                    continue
                odds = p[f"best_{side}_odds"]
                cur = conn.execute("""
                    INSERT OR IGNORE INTO picks
                    (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                     raw_lambda, applied_lambda, odds, movement_conf,
                     season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    game_date, p["pitcher"], p["team"], side,
                    p["k_line"], ev_data["verdict"], ev_data["ev"], ev_data["adj_ev"],
                    p.get("raw_lambda", p["lambda"]), p["lambda"], odds, ev_data["movement_conf"],
                    p.get("season_k9"), p.get("recent_k9"), p.get("career_k9"),
                    p.get("avg_ip"), p.get("ump_k_adj"), p.get("opp_k_rate"),
                ))
                inserted += cur.rowcount

    return inserted


def _et_dates() -> tuple[str, str]:
    now_et = datetime.now(ET)
    return (
        now_et.strftime("%Y-%m-%d"),
        (now_et - timedelta(days=1)).strftime("%Y-%m-%d"),
    )


def _normalize(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _calc_pnl(result: str, odds: int) -> float:
    if result == "win":
        return odds / 100.0 if odds > 0 else 100.0 / abs(odds)
    if result == "loss":
        return -1.0
    return 0.0  # push, void, cancelled


def fetch_and_close_results() -> int:
    """Close out open picks for yesterday ET. Returns count of picks resolved."""
    _, yesterday_et = _et_dates()

    with get_db() as conn:
        open_picks = conn.execute(
            "SELECT * FROM picks WHERE date=? AND result IS NULL", (yesterday_et,)
        ).fetchall()

    if not open_picks:
        log.info("No open picks for %s", yesterday_et)
        return 0

    try:
        resp = requests.get(f"{MLB_BASE}/schedule", params={
            "sportId": 1, "date": yesterday_et,
        }, timeout=30)
        resp.raise_for_status()
        schedule = resp.json()
    except Exception as e:
        log.error("MLB schedule fetch failed: %s", e)
        return 0

    # Build name->ks and track which teams have finalized games
    # Fetch each game's boxscore directly — hydrate=boxscore returns empty data
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
                log.warning("Boxscore fetch failed for game %s: %s", game_pk, e)
                continue

            for ts in ("home", "away"):
                players       = boxscore.get("teams", {}).get(ts, {}).get("players", {})
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
            norm = _normalize(pick["pitcher"])
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
                closed += 1

            elif team_norm in finalized_teams:
                # Game finished but pitcher not in starters → scratched
                conn.execute(
                    "UPDATE picks SET result='void',pnl=0.0,fetched_at=? WHERE id=?",
                    (now_str, pick["id"])
                )
                closed += 1

    log.info("Closed %d picks for %s", closed, yesterday_et)
    return closed


def close_orphans() -> int:
    """Mark picks older than 3 days with NULL result as 'cancelled'. Returns count updated."""
    threshold = (datetime.now(ET) - timedelta(days=3)).strftime("%Y-%m-%d")
    now_str = datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_db() as conn:
        cur = conn.execute("""
            UPDATE picks SET result='cancelled', pnl=0.0, fetched_at=?
            WHERE result IS NULL AND date <= ?
        """, (now_str, threshold))
        count = cur.rowcount

    if count:
        log.info("Marked %d orphan picks as cancelled (threshold: %s)", count, threshold)
    return count


def run() -> None:
    """Main entry point for the 8pm pipeline run."""
    init_db()
    seeded = seed_picks()
    log.info("Seeded %d picks for today", seeded)
    closed = fetch_and_close_results()
    log.info("Closed %d results for yesterday", closed)
    cancelled = close_orphans()
    log.info("Cancelled %d orphan picks", cancelled)
