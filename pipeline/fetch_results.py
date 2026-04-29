"""
fetch_results.py
Seeds today's non-PASS picks into SQLite, then fetches yesterday's box scores
from the MLB Stats API to close out results.
Run as part of the 8pm pipeline run only.
"""
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from name_utils import normalize as _normalize

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
MLB_BASE = "https://statsapi.mlb.com/api/v1"

DB_PATH      = Path(__file__).parent.parent / "data" / "results.db"
TODAY_JSON   = Path(__file__).parent.parent / "dashboard" / "data" / "processed" / "today.json"
HISTORY_PATH = Path(__file__).parent.parent / "data" / "picks_history.json"


def _json_or_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def _json_load_or_none(value):
    if value in (None, ""):
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _effective_verdict(ev_data: dict) -> str:
    return ev_data.get("actionable_verdict") or ev_data.get("verdict") or "PASS"


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def reset_db() -> None:
    """Remove the local SQLite cache so history is the run's source of truth."""
    try:
        DB_PATH.unlink()
    except FileNotFoundError:
        pass


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
                raw_verdict     TEXT,
                actionable_verdict TEXT,
                edge            REAL,
                ev              REAL NOT NULL,
                adj_ev          REAL NOT NULL,
                raw_adj_ev      REAL,
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
                opp_team        TEXT,
                pitcher_throws  TEXT,
                best_over_odds  INTEGER,
                best_under_odds INTEGER,
                opening_over_odds  INTEGER,
                opening_under_odds INTEGER,
                opening_odds_source TEXT,
                swstr_pct       REAL,
                career_swstr_pct REAL,
                is_opener      INTEGER NOT NULL DEFAULT 0,
                opener_note    TEXT,
                days_since_last_start INTEGER,
                last_pitch_count INTEGER,
                rest_k9_delta  REAL,
                park_factor    REAL,
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
                fetched_at      TEXT,
                quality_gate_level TEXT,
                input_quality_flags_json TEXT,
                verdict_cap_reason TEXT,
                data_maturity_json TEXT
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
            ("game_time",          "TEXT"),
            ("lineup_used",        "INTEGER NOT NULL DEFAULT 0"),
            ("locked_at",          "TEXT"),
            ("locked_k_line",      "REAL"),
            ("locked_odds",        "INTEGER"),
            ("locked_adj_ev",      "REAL"),
            ("locked_verdict",     "TEXT"),
            ("edge",               "REAL"),
            ("raw_verdict",        "TEXT"),
            ("actionable_verdict", "TEXT"),
            ("raw_adj_ev",         "REAL"),
            ("quality_gate_level", "TEXT"),
            ("input_quality_flags_json", "TEXT"),
            ("verdict_cap_reason", "TEXT"),
            ("data_maturity_json", "TEXT"),
            # New columns
            ("opp_team",           "TEXT"),
            ("pitcher_throws",     "TEXT"),
            ("best_over_odds",     "INTEGER"),
            ("best_under_odds",    "INTEGER"),
            ("opening_over_odds",  "INTEGER"),
            ("opening_under_odds", "INTEGER"),
            ("opening_odds_source", "TEXT"),
            ("swstr_pct",          "REAL"),
            ("career_swstr_pct",   "REAL"),
            ("is_opener",          "INTEGER NOT NULL DEFAULT 0"),
            ("opener_note",        "TEXT"),
            ("days_since_last_start", "INTEGER"),
            ("last_pitch_count",   "INTEGER"),
            ("rest_k9_delta",      "REAL"),
            ("park_factor",        "REAL"),
            # Tracks whether all external data APIs (SwStr%, umpire) returned
            # real data for this pick.  0 = at least one API fell back to a
            # neutral synthetic value.  Calibration excludes incomplete picks so
            # a bad-data run doesn't bias lambda_bias / ump_scale / swstr_k9_scale.
            ("data_complete",      "INTEGER NOT NULL DEFAULT 1"),
        ]:
            try:
                conn.execute(f"ALTER TABLE picks ADD COLUMN {col} {defn}")
            except sqlite3.OperationalError:
                pass  # column already exists


def seed_picks(today_json_path: Path = TODAY_JSON) -> int:
    """Insert non-PASS picks from today.json and refresh unlocked picks with
    latest verdict/odds/edge/EV.  Returns count of new rows inserted."""
    try:
        with open(today_json_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        log.warning("seed_picks: could not read %s: %s — skipping seed", today_json_path, e)
        return 0

    game_date = data["date"]
    inserted = 0
    updated = 0

    with get_db() as conn:
        for p in data.get("pitchers", []):
            for side in ("over", "under"):
                ev_data = p[f"ev_{side}"]
                verdict = _effective_verdict(ev_data)
                if verdict == "PASS":
                    continue
                odds = p[f"best_{side}_odds"]
                raw_verdict = ev_data.get("raw_verdict") or ev_data.get("verdict")
                actionable_verdict = ev_data.get("actionable_verdict") or verdict
                raw_adj_ev = ev_data.get("raw_adj_ev", ev_data.get("adj_ev"))
                quality_gate_level = ev_data.get("quality_gate_level") or p.get("quality_gate_level")
                quality_gate_reasons = ev_data.get("quality_gate_reasons") or p.get("quality_gate_reasons")
                verdict_cap_reason = p.get("verdict_cap_reason")
                if not verdict_cap_reason and quality_gate_reasons:
                    verdict_cap_reason = "; ".join(str(r) for r in quality_gate_reasons)
                input_quality_flags_json = _json_or_none(p.get("input_quality_flags"))
                data_maturity_json = _json_or_none(p.get("data_maturity"))
                cur = conn.execute("""
                    INSERT OR IGNORE INTO picks
                    (date, pitcher, team, side, k_line, verdict,
                     raw_verdict, actionable_verdict,
                     edge, ev, adj_ev, raw_adj_ev,
                     raw_lambda, applied_lambda, odds, movement_conf,
                     season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                     swstr_delta_k9, ref_book, game_time, lineup_used,
                     is_opener, opener_note, days_since_last_start, last_pitch_count,
                     rest_k9_delta, park_factor,
                     opp_team, pitcher_throws,
                     best_over_odds, best_under_odds,
                     opening_over_odds, opening_under_odds, opening_odds_source,
                     swstr_pct, career_swstr_pct, data_complete,
                     quality_gate_level, input_quality_flags_json, verdict_cap_reason,
                     data_maturity_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    game_date, p["pitcher"], p["team"], side,
                    p["k_line"], verdict,
                    raw_verdict, actionable_verdict,
                    ev_data.get("edge", ev_data["ev"]),
                    ev_data["ev"], ev_data["adj_ev"], raw_adj_ev,
                    p.get("raw_lambda", p["lambda"]), p["lambda"], odds, ev_data["movement_conf"],
                    p.get("season_k9"), p.get("recent_k9"), p.get("career_k9"),
                    p.get("avg_ip"), p.get("ump_k_adj"), p.get("opp_k_rate"),
                    p.get("swstr_delta_k9"),
                    p.get("ref_book"),
                    p.get("game_time"),
                    int(bool(p.get("lineup_used", False))),
                    int(bool(p.get("is_opener", False))),
                    p.get("opener_note"),
                    p.get("days_since_last_start"),
                    p.get("last_pitch_count"),
                    p.get("rest_k9_delta"),
                    p.get("park_factor"),
                    p.get("opp_team"),
                    p.get("pitcher_throws"),
                    p.get("best_over_odds"),
                    p.get("best_under_odds"),
                    p.get("opening_over_odds"),
                    p.get("opening_under_odds"),
                    p.get("opening_odds_source"),
                    p.get("swstr_pct"),
                    p.get("career_swstr_pct"),
                    # Default True for picks from old today.json files that predate this field
                    int(bool(p.get("data_complete", True))),
                    quality_gate_level,
                    input_quality_flags_json,
                    verdict_cap_reason,
                    data_maturity_json,
                ))
                inserted += cur.rowcount

                # Refresh unlocked picks with latest data (odds, lineup, verdict, and stats).
                # NOTE: opening_over_odds / opening_under_odds are intentionally NOT updated —
                # they're captured only on INSERT so the original opening line stays frozen
                # for CLV / line-movement tracking. Overwriting them on every refresh
                # silently erased the real opening line and broke movement_conf.
                # COALESCE guards legacy rows where opening is NULL: fills on first refresh
                # after this fix, then never touches it again.
                # opening_odds_source follows the same rule: once captured on INSERT it stays
                # frozen. A later refresh may arrive with source='first_seen' (preview merge
                # didn't fire that run) but we don't want to downgrade an existing 'preview'
                # tag — same invariant as opening_*_odds.
                # Note: we deliberately do NOT COALESCE-fill source for legacy rows whose
                # opening_*_odds just got back-filled above. Per policy P1 (no retroactive
                # labeling), a legacy row with back-filled odds must stay source=NULL — the
                # odds it now holds are current-fetch values, not a real opening baseline,
                # and calc_movement_confidence treats NULL source as no-haircut (correct).
                if cur.rowcount == 0:
                    # data_complete is refreshed on every update: the 6am full
                    # run often inserts with ump_ok=False (HPs not posted yet),
                    # but the 30-min refresh runs later in the day typically
                    # fill in real ump + SwStr data.  Before this fix, the flag
                    # was frozen at insert-time, so a clean-data slate could
                    # silently stay data_complete=0 all day — excluding the
                    # entire slate from calibration and from the dashboard
                    # performance rollup.  Taking the latest flag matches the
                    # latest state of the pick's underlying inputs.
                    conn.execute("""
                        UPDATE picks
                        SET verdict = ?, raw_verdict = ?, actionable_verdict = ?,
                            edge = ?, ev = ?, adj_ev = ?, raw_adj_ev = ?, odds = ?,
                            k_line = ?, applied_lambda = ?, movement_conf = ?,
                            lineup_used = ?, game_time = ?,
                            raw_lambda = ?,
                            opp_k_rate = ?, swstr_delta_k9 = ?,
                            season_k9 = ?, recent_k9 = ?, career_k9 = ?,
                            avg_ip = ?, ump_k_adj = ?, swstr_pct = ?,
                            is_opener = ?, opener_note = ?,
                            days_since_last_start = ?, last_pitch_count = ?,
                            rest_k9_delta = ?, park_factor = ?,
                            best_over_odds = ?, best_under_odds = ?,
                            opening_over_odds = COALESCE(opening_over_odds, ?),
                            opening_under_odds = COALESCE(opening_under_odds, ?),
                            data_complete = ?,
                            quality_gate_level = ?,
                            input_quality_flags_json = ?,
                            verdict_cap_reason = ?,
                            data_maturity_json = ?
                        WHERE date = ? AND pitcher = ? AND side = ?
                          AND locked_at IS NULL AND result IS NULL
                    """, (
                        verdict,
                        raw_verdict,
                        actionable_verdict,
                        ev_data.get("edge", ev_data["ev"]),
                        ev_data["ev"], ev_data["adj_ev"], raw_adj_ev, odds,
                        p["k_line"], p["lambda"], ev_data["movement_conf"],
                        int(bool(p.get("lineup_used", False))),
                        p.get("game_time"),
                        p.get("raw_lambda", p["lambda"]),
                        p.get("opp_k_rate"), p.get("swstr_delta_k9"),
                        p.get("season_k9"), p.get("recent_k9"), p.get("career_k9"),
                        p.get("avg_ip"), p.get("ump_k_adj"), p.get("swstr_pct"),
                        int(bool(p.get("is_opener", False))),
                        p.get("opener_note"),
                        p.get("days_since_last_start"),
                        p.get("last_pitch_count"),
                        p.get("rest_k9_delta"),
                        p.get("park_factor"),
                        p.get("best_over_odds"), p.get("best_under_odds"),
                        p.get("opening_over_odds"), p.get("opening_under_odds"),
                        int(bool(p.get("data_complete", True))),
                        quality_gate_level,
                        input_quality_flags_json,
                        verdict_cap_reason,
                        data_maturity_json,
                        game_date, p["pitcher"], side,
                    ))
                    updated += conn.execute("SELECT changes()").fetchone()[0]

    if updated > 0:
        log.info("seed_picks: updated %d unlocked picks with fresh data", updated)
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
                (date, pitcher, team, opp_team, pitcher_throws, side, k_line,
                 verdict, raw_verdict, actionable_verdict, edge, ev, adj_ev, raw_adj_ev,
                 raw_lambda, applied_lambda, odds, movement_conf,
                 season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                 swstr_delta_k9, swstr_pct, career_swstr_pct, ref_book,
                 best_over_odds, best_under_odds, opening_over_odds, opening_under_odds,
                 opening_odds_source, is_opener, opener_note,
                 days_since_last_start, last_pitch_count, rest_k9_delta, park_factor,
                 result, actual_ks, pnl, fetched_at, game_time, lineup_used,
                 locked_at, locked_k_line, locked_odds, locked_adj_ev, locked_verdict,
                 data_complete, quality_gate_level, input_quality_flags_json,
                 verdict_cap_reason, data_maturity_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                p.get("date"), p.get("pitcher"), p.get("team"),
                p.get("opp_team"), p.get("pitcher_throws"),
                p.get("side"),
                p.get("k_line"), p.get("verdict"),
                p.get("raw_verdict"), p.get("actionable_verdict"),
                p.get("edge", p.get("ev")),
                p.get("ev"), p.get("adj_ev"), p.get("raw_adj_ev"),
                p.get("raw_lambda"), p.get("applied_lambda"), p.get("odds"),
                p.get("movement_conf"),
                p.get("season_k9"), p.get("recent_k9"), p.get("career_k9"),
                p.get("avg_ip"), p.get("ump_k_adj"), p.get("opp_k_rate"),
                p.get("swstr_delta_k9"), p.get("swstr_pct"), p.get("career_swstr_pct"),
                p.get("ref_book"),
                p.get("best_over_odds"), p.get("best_under_odds"),
                p.get("opening_over_odds"), p.get("opening_under_odds"),
                # Legacy rows predate this field — p.get() returns None, which
                # lands as SQL NULL (distinct from "first_seen").  Do NOT
                # retroactively label (Task A2 policy P1).
                p.get("opening_odds_source"),
                int(bool(p.get("is_opener", False))),
                p.get("opener_note"),
                p.get("days_since_last_start"),
                p.get("last_pitch_count"),
                p.get("rest_k9_delta"),
                p.get("park_factor"),
                p.get("result"), p.get("actual_ks"), p.get("pnl"), p.get("fetched_at"),
                p.get("game_time"), int(bool(p.get("lineup_used", False))),
                p.get("locked_at"), p.get("locked_k_line"), p.get("locked_odds"),
                p.get("locked_adj_ev"), p.get("locked_verdict"),
                # Default True: old history entries predate this field and had real data
                int(bool(p.get("data_complete", True))),
                p.get("quality_gate_level"),
                _json_or_none(p.get("input_quality_flags")),
                p.get("verdict_cap_reason"),
                _json_or_none(p.get("data_maturity")),
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
            SELECT date, pitcher, team, opp_team, pitcher_throws, side, k_line,
                   verdict, raw_verdict, actionable_verdict, edge, ev, adj_ev, raw_adj_ev,
                   raw_lambda, applied_lambda, odds, movement_conf,
                   season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                   swstr_delta_k9, swstr_pct, career_swstr_pct, ref_book,
                   best_over_odds, best_under_odds,
                   opening_over_odds, opening_under_odds, opening_odds_source,
                   is_opener, opener_note, days_since_last_start, last_pitch_count,
                   rest_k9_delta, park_factor,
                   result, actual_ks, pnl, fetched_at,
                   game_time, lineup_used,
                   locked_at, locked_k_line, locked_odds, locked_adj_ev, locked_verdict,
                   data_complete, quality_gate_level, input_quality_flags_json,
                   verdict_cap_reason, data_maturity_json
            FROM picks
            ORDER BY date, pitcher, side
        """).fetchall()

    cols = [
        "date", "pitcher", "team", "opp_team", "pitcher_throws", "side", "k_line",
        "verdict", "raw_verdict", "actionable_verdict", "edge", "ev", "adj_ev", "raw_adj_ev",
        "raw_lambda", "applied_lambda", "odds", "movement_conf",
        "season_k9", "recent_k9", "career_k9", "avg_ip", "ump_k_adj", "opp_k_rate",
        "swstr_delta_k9", "swstr_pct", "career_swstr_pct", "ref_book",
        "best_over_odds", "best_under_odds",
        "opening_over_odds", "opening_under_odds", "opening_odds_source",
        "is_opener", "opener_note", "days_since_last_start", "last_pitch_count",
        "rest_k9_delta", "park_factor",
        "result", "actual_ks", "pnl", "fetched_at",
        "game_time", "lineup_used",
        "locked_at", "locked_k_line", "locked_odds", "locked_adj_ev", "locked_verdict",
        "data_complete", "quality_gate_level", "input_quality_flags_json",
        "verdict_cap_reason", "data_maturity_json",
    ]
    picks = [dict(zip(cols, row)) for row in rows]
    for pick in picks:
        pick["input_quality_flags"] = _json_load_or_none(pick.pop("input_quality_flags_json", None))
        pick["data_maturity"] = _json_load_or_none(pick.pop("data_maturity_json", None))

    history_path.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically: dump to a temp file in the same directory, then rename.
    # os.replace() is atomic on POSIX — a crash or disk-full during the write
    # leaves the original picks_history.json intact instead of corrupting it.
    tmp_path = str(history_path) + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(picks, f, indent=2)
        os.replace(tmp_path, history_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    log.info("export_db_to_history: wrote %d picks", len(picks))
    return len(picks)


def _et_dates() -> tuple[str, str]:
    now_et = datetime.now(ET)
    return (
        now_et.strftime("%Y-%m-%d"),
        (now_et - timedelta(days=1)).strftime("%Y-%m-%d"),
    )


def _calc_pnl(result: str, odds: int) -> float:
    if result == "win":
        return odds / 100.0 if odds > 0 else 100.0 / abs(odds)
    if result == "loss":
        return -1.0
    return 0.0  # push, void, cancelled


def _grade_picks_for_date(grade_date: str, date_picks: list) -> int:
    """Fetch MLB results for grade_date and close the given open picks. Returns count resolved."""
    try:
        resp = requests.get(f"{MLB_BASE}/schedule", params={
            "sportId": 1, "date": grade_date,
        }, timeout=30)
        resp.raise_for_status()
        schedule = resp.json()
    except Exception as e:
        log.error("MLB schedule fetch failed for %s: %s", grade_date, e)
        return 0

    # Build name->ks and track which teams have finalized games.
    # Fetch each game's boxscore directly — hydrate=boxscore returns empty data.
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
    now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    with get_db() as conn:
        for pick in date_picks:
            norm      = _normalize(pick["pitcher"])
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

    log.info("Closed %d picks for %s", closed, grade_date)
    return closed


def fetch_and_close_results() -> int:
    """Close out open picks for all past dates. Returns count of picks resolved.

    Grades every date that has open picks before today, not just yesterday.
    This makes grading resilient to missed runs: if the grading job is skipped
    or the MLB API is briefly unavailable on a given night, the next successful
    run will pick up and grade all outstanding open picks automatically.
    """
    today_et, _ = _et_dates()

    with get_db() as conn:
        open_picks = conn.execute(
            "SELECT * FROM picks WHERE date<? AND result IS NULL", (today_et,)
        ).fetchall()

    if not open_picks:
        log.info("No open picks to grade")
        return 0

    # Group by date and grade each past date separately so each gets its own
    # MLB schedule + boxscore fetch.
    from collections import defaultdict
    picks_by_date: dict[str, list] = defaultdict(list)
    for pick in open_picks:
        picks_by_date[pick["date"]].append(pick)

    dates = sorted(picks_by_date.keys())
    log.info("Grading open picks across %d date(s): %s", len(dates), dates)

    total_closed = 0
    for grade_date in dates:
        total_closed += _grade_picks_for_date(grade_date, picks_by_date[grade_date])

    return total_closed


def close_orphans() -> int:
    """Mark picks older than 7 days with NULL result as 'cancelled'. Returns count updated.

    7 days (up from 3) gives enough runway for the MLB Stats API to recover from
    an extended outage without permanently cancelling picks that could still be
    graded.  fetch_and_close_results() always runs first and will grade anything
    it can, so orphan-cancellation is only a last resort for truly missing data.
    """
    threshold = (datetime.now(ET) - timedelta(days=7)).strftime("%Y-%m-%d")
    now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

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
    reset_db()
    init_db()
    loaded = load_history_into_db()
    log.info("Loaded %d picks from history into DB", loaded)
    closed = fetch_and_close_results()
    log.info("Closed %d results for yesterday", closed)
    cancelled = close_orphans()
    log.info("Cancelled %d orphan picks", cancelled)
    exported = export_db_to_history()
    log.info("Exported %d closed picks to history", exported)
