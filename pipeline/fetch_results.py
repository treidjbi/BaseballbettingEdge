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

DB_PATH      = Path(__file__).parent.parent / "data" / "results.db"
TODAY_JSON   = Path(__file__).parent.parent / "dashboard" / "data" / "processed" / "today.json"
HISTORY_PATH = Path(__file__).parent.parent / "data" / "picks_history.json"


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
                swstr_delta_k9  REAL,
                ref_book        TEXT,
                game_time       TEXT,
                lineup_used     INTEGER NOT NULL DEFAULT 0,
                locked_at       TEXT,
                locked_k_line   REAL,
                locked_odds     INTEGER,
                locked_adj_ev   REAL,
                locked_verdict  TEXT,
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
        # Migrate existing DBs: add swstr_delta_k9 if not present
        try:
            conn.execute("ALTER TABLE picks ADD COLUMN swstr_delta_k9 REAL")
        except sqlite3.OperationalError:
            pass  # column already exists
        for col, defn in [
            ("game_time",      "TEXT"),
            ("lineup_used",    "INTEGER NOT NULL DEFAULT 0"),
            ("locked_at",      "TEXT"),
            ("locked_k_line",  "REAL"),
            ("locked_odds",    "INTEGER"),
            ("locked_adj_ev",  "REAL"),
            ("locked_verdict", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE picks ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass  # column already exists


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
                     season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                     swstr_delta_k9, ref_book, game_time, lineup_used)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    game_date, p["pitcher"], p["team"], side,
                    p["k_line"], ev_data["verdict"], ev_data["ev"], ev_data["adj_ev"],
                    p.get("raw_lambda", p["lambda"]), p["lambda"], odds, ev_data["movement_conf"],
                    p.get("season_k9"), p.get("recent_k9"), p.get("career_k9"),
                    p.get("avg_ip"), p.get("ump_k_adj"), p.get("opp_k_rate"),
                    p.get("swstr_delta_k9"),
                    p.get("ref_book"),
                    p.get("game_time"),
                    int(bool(p.get("lineup_used", False))),
                ))
                inserted += cur.rowcount

    return inserted


def lock_due_picks(conn: sqlite3.Connection, now: datetime,
                   lock_window_minutes: int = 30,
                   lock_all_past: bool = False) -> int:
    """
    Lock open picks at T-{lock_window_minutes}min before game_time.
    lock_all_past=True: lock ALL unlocked open picks (used by 3am grading run).
    Returns count of picks locked.
    """
    locked_at_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    cutoff = now + timedelta(minutes=lock_window_minutes)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    if lock_all_past:
        rows = conn.execute("""
            SELECT id, k_line, odds, adj_ev, verdict
            FROM picks
            WHERE locked_at IS NULL AND result IS NULL
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, k_line, odds, adj_ev, verdict
            FROM picks
            WHERE locked_at IS NULL
              AND result IS NULL
              AND game_time IS NOT NULL
              AND game_time <= ?
        """, (cutoff_str,)).fetchall()

    count = 0
    for row in rows:
        conn.execute("""
            UPDATE picks
            SET locked_at = ?, locked_k_line = ?, locked_odds = ?,
                locked_adj_ev = ?, locked_verdict = ?
            WHERE id = ? AND locked_at IS NULL
        """, (locked_at_str, row["k_line"], row["odds"],
              row["adj_ev"], row["verdict"], row["id"]))
        count += conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    log.info("lock_due_picks: locked %d picks (lock_all_past=%s)", count, lock_all_past)
    return count


def load_history_into_db(history_path: Path = None) -> int:
    """Load closed picks from picks_history.json into DB. Returns count inserted."""
    if history_path is None:
        history_path = HISTORY_PATH
    try:
        with open(history_path) as f:
            picks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        log.warning("load_history_into_db: could not read %s: %s — skipping", history_path, e)
        return 0

    inserted = 0
    with get_db() as conn:
        for p in picks:
            cur = conn.execute("""
                INSERT OR IGNORE INTO picks
                (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                 raw_lambda, applied_lambda, odds, movement_conf,
                 season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                 swstr_delta_k9, ref_book, result, actual_ks, pnl, fetched_at,
                 game_time, lineup_used,
                 locked_at, locked_k_line, locked_odds, locked_adj_ev, locked_verdict)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                p.get("date"), p.get("pitcher"), p.get("team"), p.get("side"),
                p.get("k_line"), p.get("verdict"), p.get("ev"), p.get("adj_ev"),
                p.get("raw_lambda"), p.get("applied_lambda"), p.get("odds"),
                p.get("movement_conf"), p.get("season_k9"), p.get("recent_k9"),
                p.get("career_k9"), p.get("avg_ip"), p.get("ump_k_adj"),
                p.get("opp_k_rate"), p.get("swstr_delta_k9"), p.get("ref_book"),
                p.get("result"), p.get("actual_ks"), p.get("pnl"), p.get("fetched_at"),
                p.get("game_time"), int(bool(p.get("lineup_used", False))),
                p.get("locked_at"), p.get("locked_k_line"), p.get("locked_odds"),
                p.get("locked_adj_ev"), p.get("locked_verdict"),
            ))
            inserted += cur.rowcount

    log.info("load_history_into_db: inserted %d picks from history", inserted)
    return inserted


def export_db_to_history(history_path: Path = None) -> int:
    """Export all picks (open and closed) from DB to picks_history.json.
    Open picks (result IS NULL) are included so they survive across ephemeral
    GitHub Actions runners and can be graded by the next run."""
    if history_path is None:
        history_path = HISTORY_PATH
    with get_db() as conn:
        rows = conn.execute("""
            SELECT date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                   raw_lambda, applied_lambda, odds, movement_conf,
                   season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                   swstr_delta_k9, ref_book, result, actual_ks, pnl, fetched_at,
                   game_time, lineup_used,
                   locked_at, locked_k_line, locked_odds, locked_adj_ev, locked_verdict
            FROM picks
            ORDER BY date, pitcher, side
        """).fetchall()

    cols = ["date", "pitcher", "team", "side", "k_line", "verdict", "ev", "adj_ev",
            "raw_lambda", "applied_lambda", "odds", "movement_conf",
            "season_k9", "recent_k9", "career_k9", "avg_ip", "ump_k_adj", "opp_k_rate",
            "swstr_delta_k9", "ref_book", "result", "actual_ks", "pnl", "fetched_at",
            "game_time", "lineup_used",
            "locked_at", "locked_k_line", "locked_odds", "locked_adj_ev", "locked_verdict"]
    picks = [dict(zip(cols, row)) for row in rows]

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "w") as f:
        json.dump(picks, f, indent=2)

    log.info("export_db_to_history: wrote %d closed picks", len(picks))
    return len(picks)


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
                graded_odds = pick["locked_odds"] if pick["locked_odds"] is not None else pick["odds"]
                pnl = _calc_pnl(result, graded_odds)
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
    """Main entry point for grading runs (evening and 3am). Does NOT seed picks —
    seeding is handled by run_pipeline.py at every run to lock in the earliest-seen line."""
    init_db()
    loaded = load_history_into_db()
    log.info("Loaded %d picks from history into DB", loaded)
    closed = fetch_and_close_results()
    log.info("Closed %d results for yesterday", closed)
    cancelled = close_orphans()
    log.info("Cancelled %d orphan picks", cancelled)
    exported = export_db_to_history()
    log.info("Exported %d closed picks to history", exported)
