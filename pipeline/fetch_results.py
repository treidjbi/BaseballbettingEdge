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
    with open(today_json_path) as f:
        data = json.load(f)

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
