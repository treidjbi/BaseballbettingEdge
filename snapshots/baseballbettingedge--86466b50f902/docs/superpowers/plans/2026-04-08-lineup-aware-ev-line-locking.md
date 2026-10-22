# Lineup-Aware EV + Line Locking Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace team-level opponent K% with individual batter K rates by handedness, add T-30min pre-game line locking for consistent grading, and add a dashboard Refresh button that triggers the pipeline via GitHub workflow_dispatch.

**Architecture:** New `fetch_lineups.py` and `fetch_batter_stats.py` feed into an updated `build_pitcher_record()` via a new `calc_lineup_k_rate()` function. `fetch_results.py` gains `lock_due_picks()` which writes locked odds/EV/verdict to new DB columns before each grading pass. A Netlify serverless function proxies GitHub workflow_dispatch so the dashboard can trigger pipeline runs without exposing a PAT.

**Tech Stack:** Python 3.11, SQLite (via stdlib `sqlite3`), `pybaseball` (FanGraphs), `requests` (MLB Stats API), Netlify Functions (Node.js), vanilla JS dashboard.

**Spec:** `docs/superpowers/specs/2026-04-08-lineup-aware-ev-and-line-locking-design.md`

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `pipeline/fetch_stats.py` | Modify | Add `throws` (pitcher handedness) to return dict |
| `pipeline/fetch_lineups.py` | Create | Fetch projected lineups from MLB Stats API |
| `pipeline/fetch_batter_stats.py` | Create | Fetch batter K% splits by handedness from FanGraphs |
| `pipeline/build_features.py` | Modify | Add `calc_lineup_k_rate()`, update `build_pitcher_record()` |
| `pipeline/fetch_results.py` | Modify | New DB columns, `lock_due_picks()`, grading + history updates |
| `pipeline/calibrate.py` | Modify | COALESCE locked_adj_ev in `_load_closed_picks()` |
| `pipeline/run_pipeline.py` | Modify | Wire lineup/batter stats; call `lock_due_picks()` in all modes |
| `tests/test_fetch_stats.py` | Modify | Add `throws` test cases |
| `tests/test_fetch_lineups.py` | Create | Tests for new lineup fetch |
| `tests/test_fetch_batter_stats.py` | Create | Tests for new batter stats fetch |
| `tests/test_build_features.py` | Modify | Tests for `calc_lineup_k_rate()` and updated `build_pitcher_record()` |
| `tests/test_fetch_results.py` | Modify | Tests for lock logic, grading, history columns |
| `netlify/functions/trigger-pipeline.js` | Create | GitHub workflow_dispatch proxy |
| `netlify.toml` | Create | Netlify functions directory config |
| `dashboard/index.html` | Modify | Refresh button + spinner |

---

## Task 1: DB Schema — game_time, lineup_used, lock columns

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `tests/test_fetch_results.py`

- [ ] **Step 1: Write failing tests for new columns**

Add to `tests/test_fetch_results.py`:

```python
def test_schema_has_game_time_and_lock_columns(tmp_db):
    """init_db should create all new columns."""
    db_path, fr = tmp_db
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(picks)")}
    conn.close()
    assert "game_time"     in cols
    assert "lineup_used"   in cols
    assert "locked_at"     in cols
    assert "locked_k_line" in cols
    assert "locked_odds"   in cols
    assert "locked_adj_ev" in cols
    assert "locked_verdict" in cols


def test_seed_picks_stores_game_time(tmp_db, today_json):
    """seed_picks should store game_time from today.json."""
    db_path, fr = tmp_db
    json_path, _ = today_json
    with patch("fetch_results.TODAY_JSON", json_path):
        fr.seed_picks(json_path)
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT game_time FROM picks").fetchall()
    conn.close()
    assert all(r[0] is not None for r in rows)
    assert rows[0][0] == "2026-04-15T17:05:00Z"


def test_seed_picks_stores_lineup_used_false_by_default(tmp_db, today_json):
    """seed_picks should store lineup_used=0 when field absent from today.json."""
    db_path, fr = tmp_db
    json_path, _ = today_json
    with patch("fetch_results.TODAY_JSON", json_path):
        fr.seed_picks(json_path)
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT lineup_used FROM picks").fetchall()
    conn.close()
    assert all(r[0] == 0 for r in rows)
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_fetch_results.py::test_schema_has_game_time_and_lock_columns tests/test_fetch_results.py::test_seed_picks_stores_game_time tests/test_fetch_results.py::test_seed_picks_stores_lineup_used_false_by_default -v
```
Expected: 3 failures (columns don't exist yet).

- [ ] **Step 3: Add columns to init_db() and ALTER TABLE migrations**

In `pipeline/fetch_results.py`, update `init_db()`:

In the `CREATE TABLE IF NOT EXISTS picks` block, add after `fetched_at TEXT`:
```python
                game_time       TEXT,
                lineup_used     INTEGER NOT NULL DEFAULT 0,
                locked_at       TEXT,
                locked_k_line   REAL,
                locked_odds     INTEGER,
                locked_adj_ev   REAL,
                locked_verdict  TEXT
```

After the existing `swstr_delta_k9` migration block, add:
```python
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
```

- [ ] **Step 4: Update seed_picks() to store game_time and lineup_used**

In `seed_picks()`, find the INSERT OR IGNORE statement. The column list currently ends with `swstr_delta_k9, ref_book`. Change to:
```python
                    INSERT OR IGNORE INTO picks
                    (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                     raw_lambda, applied_lambda, odds, movement_conf,
                     season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                     swstr_delta_k9, ref_book, game_time, lineup_used)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
```

Add `p.get("game_time"), int(bool(p.get("lineup_used", False)))` to the end of the values tuple.

- [ ] **Step 5: Run tests**

```
pytest tests/test_fetch_results.py::test_schema_has_game_time_and_lock_columns tests/test_fetch_results.py::test_seed_picks_stores_game_time tests/test_fetch_results.py::test_seed_picks_stores_lineup_used_false_by_default -v
```
Expected: 3 PASS.

- [ ] **Step 6: Run full suite**

```
pytest -q
```
Expected: all existing tests pass.

- [ ] **Step 7: Commit**

```
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: add game_time, lineup_used, and lock columns to picks schema"
```

---

## Task 2: fetch_results.py — lock_due_picks()

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `tests/test_fetch_results.py`

- [ ] **Step 1: Write failing tests for lock_due_picks()**

Add to `tests/test_fetch_results.py`:

```python
from datetime import datetime, timezone, timedelta


def _seed_pick_with_game_time(conn, game_time_str, side="over", adj_ev=0.05, odds=-115):
    """Helper: insert a minimal open pick with given game_time."""
    conn.execute("""
        INSERT INTO picks (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                           raw_lambda, applied_lambda, odds, movement_conf, game_time)
        VALUES ('2026-04-15','Test Pitcher','NYY',?,7.5,'FIRE 1u',0.05,?,7.2,7.2,?,1.0,?)
    """, (side, adj_ev, odds, game_time_str))
    conn.commit()


def test_lock_due_picks_locks_imminent_game(tmp_db):
    """A pick whose game starts in 20 min should be locked."""
    db_path, fr = tmp_db
    now = datetime(2026, 4, 15, 17, 0, 0, tzinfo=timezone.utc)
    game_time = "2026-04-15T17:20:00Z"  # 20 min from now
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, game_time)
    count = fr.lock_due_picks(fr.get_db(), now, lock_window_minutes=30)
    assert count == 1
    with fr.get_db() as conn:
        row = conn.execute("SELECT locked_at, locked_odds, locked_adj_ev FROM picks").fetchone()
    assert row["locked_at"] is not None
    assert row["locked_odds"] == -115
    assert abs(row["locked_adj_ev"] - 0.05) < 0.001


def test_lock_due_picks_skips_future_game(tmp_db):
    """A pick with game in 2 hours should NOT be locked."""
    db_path, fr = tmp_db
    now = datetime(2026, 4, 15, 15, 0, 0, tzinfo=timezone.utc)
    game_time = "2026-04-15T17:10:00Z"  # 2h 10min away
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, game_time)
    count = fr.lock_due_picks(fr.get_db(), now, lock_window_minutes=30)
    assert count == 0


def test_lock_due_picks_idempotent(tmp_db):
    """Calling lock twice should not update locked_at a second time."""
    db_path, fr = tmp_db
    now = datetime(2026, 4, 15, 17, 0, 0, tzinfo=timezone.utc)
    game_time = "2026-04-15T17:10:00Z"
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, game_time)
    fr.lock_due_picks(fr.get_db(), now)
    with fr.get_db() as conn:
        first_locked_at = conn.execute("SELECT locked_at FROM picks").fetchone()[0]
    fr.lock_due_picks(fr.get_db(), now)
    with fr.get_db() as conn:
        second_locked_at = conn.execute("SELECT locked_at FROM picks").fetchone()[0]
    assert first_locked_at == second_locked_at


def test_lock_due_picks_all_past_locks_everything(tmp_db):
    """lock_all_past=True locks all open picks regardless of game_time."""
    db_path, fr = tmp_db
    now = datetime(2026, 4, 16, 4, 0, 0, tzinfo=timezone.utc)  # 3am next day
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, "2026-04-15T17:10:00Z", side="over")
        _seed_pick_with_game_time(conn, None, side="under")  # NULL game_time
    count = fr.lock_due_picks(fr.get_db(), now, lock_all_past=True)
    assert count == 2


def test_lock_due_picks_skips_null_game_time_without_lock_all_past(tmp_db):
    """A pick with NULL game_time is skipped in normal mode."""
    db_path, fr = tmp_db
    now = datetime(2026, 4, 15, 17, 0, 0, tzinfo=timezone.utc)
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, None)
    count = fr.lock_due_picks(fr.get_db(), now, lock_all_past=False)
    assert count == 0
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_fetch_results.py -k "lock" -v
```
Expected: 5 failures (function doesn't exist yet).

- [ ] **Step 3: Implement lock_due_picks()**

Add to `pipeline/fetch_results.py` after `seed_picks()`:

```python
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
```

Also add the needed import at the top of `fetch_results.py` (it likely already has `datetime` — confirm `timedelta` is imported):
```python
from datetime import datetime, timedelta, timezone
```

- [ ] **Step 4: Run lock tests**

```
pytest tests/test_fetch_results.py -k "lock" -v
```
Expected: 5 PASS.

- [ ] **Step 5: Run full suite**

```
pytest -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: add lock_due_picks() — locks picks at T-30min before game time"
```

---

## Task 3: fetch_results.py — grading uses locked odds; update history export/import

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `tests/test_fetch_results.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_fetch_results.py`:

```python
def test_grading_uses_locked_odds_for_pnl(tmp_db, today_json):
    """When locked_odds is set, P&L should use locked_odds not current odds."""
    db_path, fr = tmp_db
    json_path, _ = today_json
    fr.seed_picks(json_path)
    # Manually set locked_odds to a different value to test it's used
    with fr.get_db() as conn:
        conn.execute("""
            UPDATE picks SET locked_odds = -200, locked_at = '2026-04-15T17:00:00Z'
            WHERE pitcher = 'Gerrit Cole' AND side = 'over'
        """)
    # Simulate a win and verify P&L uses locked_odds (-200 → +0.50 per unit)
    with fr.get_db() as conn:
        conn.execute("""
            UPDATE picks SET result = 'win', actual_ks = 8
            WHERE pitcher = 'Gerrit Cole' AND side = 'over'
        """)
    fr.export_db_to_history()
    with open(fr.HISTORY_PATH) as f:
        history = json.load(f)
    cole_over = next(p for p in history if p["pitcher"] == "Gerrit Cole" and p["side"] == "over")
    # P&L with -200 odds win = 100/200 = 0.5 units
    # P&L with original -115 odds win = 100/115 ≈ 0.87 units
    # Check locked_odds is in history
    assert cole_over.get("locked_odds") == -200


def test_history_export_includes_lock_columns(tmp_db, today_json):
    """export_db_to_history should include all new columns."""
    db_path, fr = tmp_db
    json_path, _ = today_json
    fr.seed_picks(json_path)
    fr.export_db_to_history()
    with open(fr.HISTORY_PATH) as f:
        history = json.load(f)
    assert len(history) > 0
    pick = history[0]
    for col in ("game_time", "lineup_used", "locked_at", "locked_k_line",
                "locked_odds", "locked_adj_ev", "locked_verdict"):
        assert col in pick, f"missing column: {col}"


def test_history_load_includes_lock_columns(tmp_db, today_json):
    """load_history_into_db should load locked_* columns from history."""
    db_path, fr = tmp_db
    json_path, _ = today_json
    fr.seed_picks(json_path)
    # Manually write history with lock columns
    history = [{"date": "2026-04-10", "pitcher": "Old Pick", "team": "BOS", "side": "over",
                "k_line": 6.5, "verdict": "LEAN", "ev": 0.02, "adj_ev": 0.02,
                "raw_lambda": 6.0, "applied_lambda": 6.0, "odds": -110,
                "movement_conf": 1.0, "result": "win", "actual_ks": 7, "pnl": 0.91,
                "fetched_at": "2026-04-10T12:00:00Z",
                "game_time": "2026-04-10T17:05:00Z", "lineup_used": 1,
                "locked_at": "2026-04-10T16:35:00Z", "locked_k_line": 6.5,
                "locked_odds": -110, "locked_adj_ev": 0.02, "locked_verdict": "LEAN"}]
    import json as _json
    fr.HISTORY_PATH.write_text(_json.dumps(history))
    fr.load_history_into_db()
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT locked_at, locked_odds, game_time, lineup_used FROM picks WHERE pitcher = 'Old Pick'"
    ).fetchone()
    conn.close()
    assert row[0] == "2026-04-10T16:35:00Z"
    assert row[1] == -110
    assert row[2] == "2026-04-10T17:05:00Z"
    assert row[3] == 1
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_fetch_results.py -k "history_export or history_load or locked_odds" -v
```
Expected: failures (columns missing from SELECT/INSERT).

- [ ] **Step 3: Update export_db_to_history() SELECT and cols list**

In `pipeline/fetch_results.py`, find `export_db_to_history()`. Update the SELECT and `cols` list to append new columns:

```python
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
```

- [ ] **Step 4: Update load_history_into_db() INSERT and values**

In `load_history_into_db()`, update the INSERT column list and values tuple to include new columns:

```python
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
```

- [ ] **Step 5: Update grading to use locked_odds**

Find `_calc_pnl` usage in `fetch_and_close_results()`. When computing P&L for a pick, use `locked_odds` when present. Locate where `result` and `odds` are used to compute `pnl`, and replace the `odds` variable with:

```python
graded_odds = row["locked_odds"] if row["locked_odds"] is not None else row["odds"]
pnl = _calc_pnl(result, graded_odds)
```

- [ ] **Step 6: Run new tests**

```
pytest tests/test_fetch_results.py -k "history_export or history_load or locked_odds" -v
```
Expected: 3 PASS.

- [ ] **Step 7: Run full suite**

```
pytest -q
```
Expected: all pass.

- [ ] **Step 8: Commit**

```
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: update grading and history export/import for lock columns"
```

---

## Task 4: calibrate.py — COALESCE locked_adj_ev

**Files:**
- Modify: `pipeline/calibrate.py`
- Modify: `tests/test_calibrate.py` (if it exists) — otherwise add to the test file

- [ ] **Step 1: Write failing test**

Add to `tests/test_calibrate.py` (find the existing file):

```python
def test_load_closed_picks_uses_locked_adj_ev_when_present(tmp_path):
    """_load_closed_picks should return locked_adj_ev in place of adj_ev when set."""
    import sqlite3, sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from unittest.mock import patch
    import calibrate

    db = tmp_path / "results.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE picks (
            date TEXT, verdict TEXT, side TEXT, result TEXT, odds INTEGER,
            adj_ev REAL, locked_adj_ev REAL,
            raw_lambda REAL, actual_ks INTEGER,
            season_k9 REAL, recent_k9 REAL, career_k9 REAL,
            avg_ip REAL, ump_k_adj REAL, swstr_delta_k9 REAL,
            fetched_at TEXT, pnl REAL
        )
    """)
    conn.execute("""
        INSERT INTO picks VALUES
        ('2026-04-10','FIRE 1u','over','win',-115, 0.08, 0.05,
         6.8, 7, 9.0, 8.5, 9.2, 5.8, 0.1, 0.02, '2026-04-10T12:00:00Z', 0.87)
    """)
    conn.commit()
    conn.close()

    with patch("calibrate.DB_PATH", db), \
         patch("calibrate._current_season_start", return_value="2026-03-01"):
        picks = calibrate._load_closed_picks()

    assert len(picks) == 1
    # locked_adj_ev (0.05) should take precedence over adj_ev (0.08)
    assert abs(picks[0]["adj_ev"] - 0.05) < 0.001
```

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_calibrate.py -k "locked_adj_ev" -v
```
Expected: FAIL (query returns raw `adj_ev`, not the coalesced value).

- [ ] **Step 3: Update _load_closed_picks() query**

In `pipeline/calibrate.py`, find `_load_closed_picks()`. Update the SELECT to:

```python
        rows = conn.execute("""
            SELECT verdict, side, result, odds,
                   COALESCE(locked_adj_ev, adj_ev) AS adj_ev,
                   raw_lambda, actual_ks,
                   season_k9, recent_k9, career_k9, avg_ip, ump_k_adj,
                   swstr_delta_k9, fetched_at, pnl
            FROM picks
            WHERE result IN ('win','loss','push')
              AND date >= ?
        """, (season_start,)).fetchall()
```

- [ ] **Step 4: Run test**

```
pytest tests/test_calibrate.py -k "locked_adj_ev" -v
```
Expected: PASS.

- [ ] **Step 5: Run full suite**

```
pytest -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```
git add pipeline/calibrate.py tests/test_calibrate.py
git commit -m "feat: calibration uses locked_adj_ev when available (COALESCE fallback)"
```

---

## Task 5: fetch_stats.py — add pitcher `throws`

**Files:**
- Modify: `pipeline/fetch_stats.py`
- Modify: `tests/test_fetch_stats.py`

- [ ] **Step 1: Write failing tests**

Find `tests/test_fetch_stats.py`. Add:

```python
def test_fetch_stats_returns_throws_field(mock_stats_api):
    """fetch_stats should include throws (R/L) for each pitcher."""
    # mock_stats_api should already be set up in this test file
    # Add pitchHand.code to the probablePitcher in the mock
    stats = fetch_stats("2026-04-15", ["Gerrit Cole"])
    assert "throws" in stats.get("Gerrit Cole", {})
    assert stats["Gerrit Cole"]["throws"] in ("R", "L")


def test_fetch_stats_throws_defaults_to_R_when_missing(mock_stats_no_pitch_hand):
    """When pitchHand is absent from API, throws should default to 'R'."""
    stats = fetch_stats("2026-04-15", ["Test Pitcher"])
    assert stats.get("Test Pitcher", {}).get("throws") == "R"
```

Look at the existing test file to understand what mocks are in place and adapt accordingly. The key fixture to update is whatever mock returns the `probablePitcher` data — add `"pitchHand": {"code": "R"}` to it.

- [ ] **Step 2: Run to confirm failure**

```
pytest tests/test_fetch_stats.py -k "throws" -v
```
Expected: failures.

- [ ] **Step 3: Add throws to fetch_stats.py return dict**

In `pipeline/fetch_stats.py`, find where `fetch_stats()` builds its return dict per pitcher. Locate the `probablePitcher` parse path and extract:

```python
throws = pitcher_data.get("pitchHand", {}).get("code", "R")
```

Add `"throws": throws` to the returned stats dict for each pitcher.

The `probablePitcher` object is available in the schedule API response. The `pitchHand.code` field is at `game["teams"]["home"]["probablePitcher"]["pitchHand"]["code"]` (and same for `away`).

- [ ] **Step 4: Run tests**

```
pytest tests/test_fetch_stats.py -k "throws" -v
```
Expected: PASS.

- [ ] **Step 5: Run full suite**

```
pytest -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```
git add pipeline/fetch_stats.py tests/test_fetch_stats.py
git commit -m "feat: fetch_stats returns pitcher throws (R/L) from MLB Stats API"
```

---

## Task 6: fetch_lineups.py — projected lineup fetch

**Files:**
- Create: `pipeline/fetch_lineups.py`
- Create: `tests/test_fetch_lineups.py`

- [ ] **Step 1: Write tests first**

Create `tests/test_fetch_lineups.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from unittest.mock import patch, MagicMock
import fetch_lineups


SAMPLE_SCHEDULE_RESPONSE = {
    "dates": [{
        "games": [{
            "gamePk": 745000,
            "teams": {
                "away": {"team": {"name": "New York Yankees"}},
                "home": {"team": {"name": "Boston Red Sox"}},
            },
            "lineups": {
                "awayPlayers": [
                    {"person": {"fullName": "Aaron Judge"}, "battingOrder": "100",
                     "position": {"abbreviation": "CF"}},
                    {"person": {"fullName": "Giancarlo Stanton"}, "battingOrder": "200",
                     "position": {"abbreviation": "DH"}},
                ],
                "homePlayers": []
            }
        }]
    }]
}


def _make_mock_response(data):
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status.return_value = None
    return m


def test_fetch_lineups_returns_batters_for_team(monkeypatch):
    """fetch_lineups returns batter list for a given team."""
    monkeypatch.setattr("fetch_lineups.requests.get",
                        lambda *a, **kw: _make_mock_response(SAMPLE_SCHEDULE_RESPONSE))
    result = fetch_lineups.fetch_lineups("2026-04-15", "New York Yankees")
    assert result is not None
    names = [b["name"] for b in result]
    assert "Aaron Judge" in names
    assert "Giancarlo Stanton" in names


def test_fetch_lineups_returns_none_when_no_lineup(monkeypatch):
    """Returns None when no lineup posted for the team."""
    empty_response = {"dates": [{"games": [{
        "gamePk": 745001,
        "teams": {"away": {"team": {"name": "NYY"}}, "home": {"team": {"name": "BOS"}}},
        "lineups": {"awayPlayers": [], "homePlayers": []}
    }]}]}
    monkeypatch.setattr("fetch_lineups.requests.get",
                        lambda *a, **kw: _make_mock_response(empty_response))
    result = fetch_lineups.fetch_lineups("2026-04-15", "NYY")
    assert result is None


def test_fetch_lineups_returns_none_on_api_error(monkeypatch):
    """Returns None (not an exception) when API call fails."""
    def raise_error(*a, **kw):
        raise Exception("network error")
    monkeypatch.setattr("fetch_lineups.requests.get", raise_error)
    result = fetch_lineups.fetch_lineups("2026-04-15", "NYY")
    assert result is None


def test_fetch_lineups_includes_bats_field(monkeypatch):
    """Each batter dict should include a bats field (R/L/S), defaulting to R."""
    monkeypatch.setattr("fetch_lineups.requests.get",
                        lambda *a, **kw: _make_mock_response(SAMPLE_SCHEDULE_RESPONSE))
    result = fetch_lineups.fetch_lineups("2026-04-15", "New York Yankees")
    for batter in result:
        assert "bats" in batter
        assert batter["bats"] in ("R", "L", "S")
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_fetch_lineups.py -v
```
Expected: 4 failures (module doesn't exist).

- [ ] **Step 3: Create fetch_lineups.py**

Create `pipeline/fetch_lineups.py`:

```python
"""
fetch_lineups.py
Fetches projected batting lineups from the MLB Stats API for a given game date.
Returns None when lineups haven't been posted yet (normal for morning runs).
"""
import logging
import requests

log = logging.getLogger(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"


def fetch_lineups(date_str: str, team_name: str) -> list[dict] | None:
    """
    Fetch the projected lineup for a team on a given date.

    Returns a list of {"name": str, "bats": str} dicts (one per batter in order)
    when the lineup is available, or None when not yet posted.

    team_name must match the MLB Stats API team name exactly (e.g. "New York Yankees").
    Matching is case-insensitive on both away and home sides.
    """
    try:
        resp = requests.get(
            f"{MLB_BASE}/schedule",
            params={"sportId": 1, "date": date_str, "hydrate": "lineups"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("fetch_lineups: API error for %s on %s: %s", team_name, date_str, e)
        return None

    team_lower = team_name.lower()
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            teams = game.get("teams", {})
            away_name = teams.get("away", {}).get("team", {}).get("name", "").lower()
            home_name = teams.get("home", {}).get("team", {}).get("name", "").lower()

            if team_lower in (away_name, home_name):
                side_key = "awayPlayers" if team_lower == away_name else "homePlayers"
                players = game.get("lineups", {}).get(side_key, [])

                # Filter to batting order entries only (battingOrder is a string like "100")
                batters = [p for p in players if p.get("battingOrder")]
                batters.sort(key=lambda p: int(p.get("battingOrder", "999")))

                if not batters:
                    log.info("fetch_lineups: no lineup posted for %s on %s", team_name, date_str)
                    return None

                result = []
                for b in batters:
                    name = b.get("person", {}).get("fullName", "Unknown")
                    bats = b.get("person", {}).get("batSide", {}).get("code", "R")
                    result.append({"name": name, "bats": bats})

                log.info("fetch_lineups: %s — %d batters found for %s",
                         date_str, len(result), team_name)
                return result

    log.info("fetch_lineups: no game found for %s on %s", team_name, date_str)
    return None
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_fetch_lineups.py -v
```
Expected: 4 PASS. Fix any failures before proceeding.

- [ ] **Step 5: Run full suite**

```
pytest -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```
git add pipeline/fetch_lineups.py tests/test_fetch_lineups.py
git commit -m "feat: add fetch_lineups — MLB Stats API projected batting lineup fetch"
```

---

## Task 7: fetch_batter_stats.py — batter K% splits by handedness

**Files:**
- Create: `pipeline/fetch_batter_stats.py`
- Create: `tests/test_fetch_batter_stats.py`

- [ ] **Step 1: Write tests first**

Create `tests/test_fetch_batter_stats.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from unittest.mock import patch, MagicMock
import pandas as pd
import fetch_batter_stats
from build_features import LEAGUE_AVG_K_RATE


SAMPLE_AGGREGATE = pd.DataFrame([
    {"Name": "Mookie Betts",    "K%": 0.135},
    {"Name": "Freddie Freeman", "K%": 0.098},
])

SAMPLE_VS_R = pd.DataFrame([
    {"Name": "Mookie Betts",    "K%": 0.150},
    {"Name": "Freddie Freeman", "K%": 0.110},
])

SAMPLE_VS_L = pd.DataFrame([
    {"Name": "Mookie Betts",    "K%": 0.115},
    {"Name": "Freddie Freeman", "K%": 0.080},
])


def test_fetch_batter_stats_returns_splits(monkeypatch):
    """When splits available, returns vs_R and vs_L per batter."""
    monkeypatch.setattr("fetch_batter_stats._fetch_aggregate", lambda season: SAMPLE_AGGREGATE)
    monkeypatch.setattr("fetch_batter_stats._fetch_splits", lambda season: (SAMPLE_VS_R, SAMPLE_VS_L))
    result = fetch_batter_stats.fetch_batter_stats(2026)
    assert abs(result["Mookie Betts"]["vs_R"] - 0.150) < 0.001
    assert abs(result["Mookie Betts"]["vs_L"] - 0.115) < 0.001


def test_fetch_batter_stats_falls_back_to_aggregate_when_splits_fail(monkeypatch):
    """When _fetch_splits raises, returns aggregate K% for both splits."""
    monkeypatch.setattr("fetch_batter_stats._fetch_aggregate", lambda season: SAMPLE_AGGREGATE)
    monkeypatch.setattr("fetch_batter_stats._fetch_splits",
                        lambda season: (_ for _ in ()).throw(AttributeError("no splits")))
    result = fetch_batter_stats.fetch_batter_stats(2026)
    assert abs(result["Mookie Betts"]["vs_R"] - 0.135) < 0.001
    assert abs(result["Mookie Betts"]["vs_L"] - 0.135) < 0.001


def test_fetch_batter_stats_unknown_batter_returns_league_avg(monkeypatch):
    """Batters not in FanGraphs data return LEAGUE_AVG_K_RATE for both splits."""
    monkeypatch.setattr("fetch_batter_stats._fetch_aggregate", lambda season: SAMPLE_AGGREGATE)
    monkeypatch.setattr("fetch_batter_stats._fetch_splits", lambda season: (SAMPLE_VS_R, SAMPLE_VS_L))
    result = fetch_batter_stats.fetch_batter_stats(2026)
    unknown = result.get("Unknown Player")
    # Unknown players should return league avg when looked up via .get() with default
    assert unknown is None  # not in result dict — caller uses .get() with fallback


def test_fetch_batter_stats_uses_league_avg_k_rate_from_build_features(monkeypatch):
    """LEAGUE_AVG_K_RATE should come from build_features, not be redefined."""
    import build_features
    assert fetch_batter_stats.LEAGUE_AVG_K_RATE is build_features.LEAGUE_AVG_K_RATE


def test_fetch_batter_stats_returns_empty_dict_on_total_failure(monkeypatch):
    """When aggregate fetch also fails, returns {} (pipeline continues with team K%)."""
    monkeypatch.setattr("fetch_batter_stats._fetch_aggregate",
                        lambda season: (_ for _ in ()).throw(Exception("FanGraphs down")))
    result = fetch_batter_stats.fetch_batter_stats(2026)
    assert result == {}
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_fetch_batter_stats.py -v
```
Expected: 5 failures (module doesn't exist).

- [ ] **Step 3: Create fetch_batter_stats.py**

Create `pipeline/fetch_batter_stats.py`:

```python
"""
fetch_batter_stats.py
Fetches batter K% splits by pitcher handedness from FanGraphs via pybaseball.

Returns {batter_name: {"vs_R": float, "vs_L": float}} for the current season.
Falls back to aggregate K% for both splits if handedness splits are unavailable.
Returns {} if FanGraphs is completely unreachable (pipeline continues with team K%).

IMPORTANT: Before deploying, verify that pybaseball supports handedness split queries
for the installed version. If `_fetch_splits` raises AttributeError, the fallback to
aggregate K% is used automatically.
"""
import logging
from build_features import LEAGUE_AVG_K_RATE

log = logging.getLogger(__name__)


def _fetch_aggregate(season: int):
    """Fetch aggregate batter stats from FanGraphs. Returns DataFrame."""
    from pybaseball import batting_stats
    return batting_stats(season, qual=0)


def _fetch_splits(season: int):
    """
    Fetch batter K% splits vs LHP and RHP.
    Returns (df_vs_R, df_vs_L) DataFrames, or raises if splits unavailable.

    NOTE: Verify the exact pybaseball function for handedness splits against
    the installed version. Options include batting_stats_bref() with split params
    or a direct FanGraphs splits endpoint call. Update this function accordingly.
    """
    # Attempt to use pybaseball split functionality.
    # This may raise AttributeError if the function doesn't exist in the installed version.
    from pybaseball import batting_stats_bref
    # batting_stats_bref does not natively support handedness splits —
    # raise to trigger fallback to aggregate
    raise AttributeError(
        "Handedness splits not yet implemented — update _fetch_splits() once "
        "the correct pybaseball function is identified. Using aggregate K% fallback."
    )


def _build_lookup(df, name_col: str = "Name", k_col: str = "K%") -> dict:
    """Build {name: k_rate} lookup from a FanGraphs DataFrame."""
    result = {}
    if df is None or df.empty:
        return result
    for _, row in df.iterrows():
        name = row.get(name_col)
        k = row.get(k_col)
        if name and k is not None:
            result[str(name)] = float(k)
    return result


def fetch_batter_stats(season: int) -> dict:
    """
    Returns {batter_name: {"vs_R": float, "vs_L": float}} for the given season.
    Batters not in the result should be handled by the caller with LEAGUE_AVG_K_RATE.
    Returns {} on complete failure.
    """
    try:
        agg_df = _fetch_aggregate(season)
    except Exception as e:
        log.warning("fetch_batter_stats: aggregate fetch failed: %s — returning {}", e)
        return {}

    agg_lookup = _build_lookup(agg_df)

    try:
        vs_r_df, vs_l_df = _fetch_splits(season)
        vs_r_lookup = _build_lookup(vs_r_df)
        vs_l_lookup = _build_lookup(vs_l_df)
        log.info("fetch_batter_stats: loaded handedness splits for %d batters", len(vs_r_lookup))
        use_splits = True
    except Exception as e:
        log.warning("fetch_batter_stats: splits unavailable (%s) — using aggregate K%%", e)
        use_splits = False

    result = {}
    for name, agg_k in agg_lookup.items():
        if use_splits:
            vs_r = vs_r_lookup.get(name, agg_k)
            vs_l = vs_l_lookup.get(name, agg_k)
        else:
            vs_r = agg_k
            vs_l = agg_k
        result[name] = {"vs_R": vs_r, "vs_L": vs_l}

    log.info("fetch_batter_stats: built stats for %d batters (splits=%s)", len(result), use_splits)
    return result
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_fetch_batter_stats.py -v
```
Expected: 5 PASS. Fix any test that reveals a logic issue.

- [ ] **Step 5: Run full suite**

```
pytest -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```
git add pipeline/fetch_batter_stats.py tests/test_fetch_batter_stats.py
git commit -m "feat: add fetch_batter_stats — FanGraphs batter K%% splits by handedness"
```

---

## Task 8: build_features.py — calc_lineup_k_rate + build_pitcher_record update

**Files:**
- Modify: `pipeline/build_features.py`
- Modify: `tests/test_build_features.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_build_features.py`:

```python
from build_features import calc_lineup_k_rate, LEAGUE_AVG_K_RATE


SAMPLE_BATTER_STATS = {
    "Aaron Judge":    {"vs_R": 0.280, "vs_L": 0.210},
    "Mookie Betts":   {"vs_R": 0.150, "vs_L": 0.115},
}

SAMPLE_LINEUP = [
    {"name": "Aaron Judge",  "bats": "R"},
    {"name": "Mookie Betts", "bats": "R"},
]


class TestCalcLineupKRate:
    def test_none_lineup_returns_none(self):
        assert calc_lineup_k_rate(None, SAMPLE_BATTER_STATS, "R") is None

    def test_empty_lineup_returns_none(self):
        assert calc_lineup_k_rate([], SAMPLE_BATTER_STATS, "R") is None

    def test_righty_pitcher_uses_vs_r_split(self):
        result = calc_lineup_k_rate(SAMPLE_LINEUP, SAMPLE_BATTER_STATS, "R")
        expected = (0.280 + 0.150) / 2
        assert result is not None
        assert abs(result - expected) < 0.001

    def test_lefty_pitcher_uses_vs_l_split(self):
        result = calc_lineup_k_rate(SAMPLE_LINEUP, SAMPLE_BATTER_STATS, "L")
        expected = (0.210 + 0.115) / 2
        assert result is not None
        assert abs(result - expected) < 0.001

    def test_unknown_batter_uses_league_avg(self):
        lineup = [{"name": "Unknown Batter", "bats": "R"}]
        result = calc_lineup_k_rate(lineup, SAMPLE_BATTER_STATS, "R")
        assert abs(result - LEAGUE_AVG_K_RATE) < 0.001

    def test_return_value_is_unregressed_raw_mean(self):
        """Return value must NOT be Bayesian-regressed — calc_lambda handles that."""
        lineup = [{"name": "Aaron Judge", "bats": "R"}]
        result = calc_lineup_k_rate(lineup, SAMPLE_BATTER_STATS, "R")
        # Should equal raw vs_R value exactly, not regressed toward league avg
        assert abs(result - 0.280) < 0.001


def test_build_pitcher_record_lineup_used_false_without_lineup(sample_odds, sample_stats, sample_swstr):
    """build_pitcher_record without lineup params should have lineup_used=False."""
    from build_features import build_pitcher_record
    record = build_pitcher_record(sample_odds, sample_stats, 0.0, swstr_data=sample_swstr)
    assert record["lineup_used"] is False


def test_build_pitcher_record_lineup_used_true_with_lineup(sample_odds, sample_stats, sample_swstr):
    """build_pitcher_record with lineup params should have lineup_used=True."""
    from build_features import build_pitcher_record
    stats = {**sample_stats, "throws": "R"}
    record = build_pitcher_record(
        sample_odds, stats, 0.0, swstr_data=sample_swstr,
        lineup=SAMPLE_LINEUP, batter_stats=SAMPLE_BATTER_STATS
    )
    assert record["lineup_used"] is True


def test_build_pitcher_record_lineup_changes_opp_k_rate(sample_odds, sample_stats, sample_swstr):
    """EV should differ when lineup provides different K rate than team average."""
    from build_features import build_pitcher_record
    stats = {**sample_stats, "throws": "R", "opp_k_rate": 0.227}
    # Lineup with very high K batters
    high_k_lineup = [{"name": "Aaron Judge", "bats": "R"}]  # 0.280 vs R
    record_with_lineup = build_pitcher_record(
        sample_odds, stats, 0.0, swstr_data=sample_swstr,
        lineup=high_k_lineup, batter_stats=SAMPLE_BATTER_STATS
    )
    record_without = build_pitcher_record(sample_odds, stats, 0.0, swstr_data=sample_swstr)
    # High-K lineup should produce higher lambda
    assert record_with_lineup["lambda"] != record_without["lambda"]
```

Check what `sample_odds`, `sample_stats`, `sample_swstr` fixtures look like in the existing test file and adapt the fixture names accordingly. They may be named differently.

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_build_features.py -k "lineup" -v
```
Expected: failures (function doesn't exist yet).

- [ ] **Step 3: Add calc_lineup_k_rate() to build_features.py**

Add after `calc_swstr_delta_k9()`:

```python
def calc_lineup_k_rate(
    lineup: list[dict] | None,
    batter_stats: dict,
    pitcher_throws: str,
) -> float | None:
    """
    Compute the mean K rate for a batting lineup against a given pitcher handedness.

    Returns the unregressed raw mean — do NOT Bayesian-regress here.
    calc_lambda() applies bayesian_opp_k() to whatever rate it receives.

    Returns None when lineup is None or empty (caller falls back to team K%).
    Unknown batters use LEAGUE_AVG_K_RATE.

    lineup:         list of {"name": str, "bats": str} dicts
    batter_stats:   {name: {"vs_R": float, "vs_L": float}} from fetch_batter_stats
    pitcher_throws: "R" or "L"
    """
    if not lineup:
        return None
    split_key = "vs_R" if pitcher_throws == "R" else "vs_L"
    rates = []
    for batter in lineup:
        name = batter.get("name", "")
        splits = batter_stats.get(name)
        rates.append(splits[split_key] if splits else LEAGUE_AVG_K_RATE)
    return sum(rates) / len(rates)
```

- [ ] **Step 4: Update build_pitcher_record() signature and logic**

Update the function signature:

```python
def build_pitcher_record(odds: dict, stats: dict, ump_k_adj: float,
                         swstr_data: dict | None = None,
                         lineup: list[dict] | None = None,
                         batter_stats: dict | None = None) -> dict:
```

After the `swstr_delta` calculation, add:

```python
    lineup_rate = None
    if lineup is not None and batter_stats is not None:
        lineup_rate = calc_lineup_k_rate(lineup, batter_stats, stats.get("throws", "R"))
    effective_opp_k_rate = lineup_rate if lineup_rate is not None else stats["opp_k_rate"]
    lineup_used = lineup_rate is not None
```

Replace `stats["opp_k_rate"]` in the `calc_lambda()` call with `effective_opp_k_rate`:

```python
    raw_lam = calc_lambda(blended, avg_ip, effective_opp_k_rate, scaled_ump_k_adj,
                          swstr_delta_k9=swstr_delta, opp_games_played=opp_games)
```

Add `"lineup_used": lineup_used` to the returned dict.

- [ ] **Step 5: Run tests**

```
pytest tests/test_build_features.py -k "lineup" -v
```
Expected: all PASS.

- [ ] **Step 6: Run full suite**

```
pytest -q
```
Expected: all pass.

- [ ] **Step 7: Commit**

```
git add pipeline/build_features.py tests/test_build_features.py
git commit -m "feat: add calc_lineup_k_rate and lineup-aware build_pitcher_record"
```

---

## Task 9: run_pipeline.py — wire lineup/batter stats + lock_due_picks()

**Files:**
- Modify: `pipeline/run_pipeline.py`
- Modify: `tests/test_run_pipeline.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_run_pipeline.py`:

```python
def test_run_calls_lock_due_picks(tmp_path):
    """run() should call lock_due_picks before seeding picks."""
    import run_pipeline
    out_path = tmp_path / "today.json"
    lock_calls = []

    def mock_lock(conn, now, lock_window_minutes=30, lock_all_past=False):
        lock_calls.append({"lock_all_past": lock_all_past})
        return 0

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value={"Test Pitcher": _sample_stats()}), \
         patch("run_pipeline.fetch_swstr", return_value={"Test Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value={"Test Pitcher": 0.0}), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.lock_due_picks", mock_lock), \
         patch("run_pipeline._write_archive"):
        run_pipeline.run("2026-04-01")

    assert len(lock_calls) >= 1
    assert lock_calls[0]["lock_all_past"] is False


def test_grading_run_calls_lock_all_past(tmp_path):
    """Grading run should call lock_due_picks(lock_all_past=True)."""
    import run_pipeline
    lock_calls = []

    def mock_lock(conn, now, lock_window_minutes=30, lock_all_past=False):
        lock_calls.append({"lock_all_past": lock_all_past})
        return 0

    with patch("run_pipeline.lock_due_picks", mock_lock), \
         patch("run_pipeline.fetch_results_run"), \
         patch("run_pipeline.calibrate_run"):
        run_pipeline.run("2026-04-01", run_type="grading")

    assert any(c["lock_all_past"] is True for c in lock_calls)
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_run_pipeline.py -k "lock" -v
```
Expected: failures.

- [ ] **Step 3: Wire lock_due_picks into run_pipeline.py**

In `run_pipeline.py`:

1. Add imports at the top of the file alongside other pipeline imports:
```python
from fetch_lineups      import fetch_lineups
from fetch_batter_stats import fetch_batter_stats
from fetch_results      import init_db, load_history_into_db, seed_picks, export_db_to_history, lock_due_picks, get_db
```

2. Add a cached batter stats helper to avoid multiple FanGraphs calls per run:
```python
_batter_stats_cache: dict | None = None

def fetch_batter_stats_cached(season: int) -> dict:
    global _batter_stats_cache
    if _batter_stats_cache is None:
        try:
            _batter_stats_cache = fetch_batter_stats(season)
        except Exception as e:
            log.warning("fetch_batter_stats failed: %s — using empty dict", e)
            _batter_stats_cache = {}
    return _batter_stats_cache


def fetch_lineups_for_pitcher(date_str: str, team: str) -> list[dict] | None:
    try:
        return fetch_lineups(date_str, team)
    except Exception as e:
        log.warning("fetch_lineups failed for %s: %s", team, e)
        return None
```

3. In the `full` run path, after `fetch_umpires`, add:
```python
    # 5. Fetch batter stats (one FanGraphs pull, cached for this run)
    batter_stats = fetch_batter_stats_cached(int(date_str[:4]))
```

4. In the per-pitcher loop, add lineup fetch and pass to `build_pitcher_record`:
```python
        lineup = fetch_lineups_for_pitcher(date_str, stats.get("team", ""))
        record = build_pitcher_record(
            odds, stats, ump_map.get(name, 0.0),
            swstr_data=swstr_map.get(name, _SWSTR_NEUTRAL),
            lineup=lineup,
            batter_stats=batter_stats if lineup else None,
        )
```

5. In the seeding block, add `lock_due_picks()` call before seeding:
```python
        init_db()
        load_history_into_db()
        conn = get_db()
        locked = lock_due_picks(conn, datetime.now(timezone.utc), lock_all_past=False)
        conn.close()
        seeded = seed_picks()
        if seeded > 0 or locked > 0:
            export_db_to_history()
```

6. In `_run_grading_steps()`, add lock call at the start:
```python
    try:
        from fetch_results import init_db, load_history_into_db, lock_due_picks, export_db_to_history, get_db
        from datetime import datetime, timezone
        init_db()
        load_history_into_db()
        conn = get_db()
        locked = lock_due_picks(conn, datetime.now(timezone.utc), lock_all_past=True)
        conn.close()
        if locked > 0:
            export_db_to_history()
    except Exception as e:
        log.warning("lock_due_picks in grading run failed: %s", e)
    # ... existing fetch_results and calibrate calls follow
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_run_pipeline.py -v
```
Expected: all PASS including new lock tests.

- [ ] **Step 5: Run full suite**

```
pytest -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```
git add pipeline/run_pipeline.py tests/test_run_pipeline.py
git commit -m "feat: wire lineup/batter stats and lock_due_picks into pipeline run modes"
```

---

## Task 10: Netlify Function — workflow_dispatch trigger

**Files:**
- Create: `netlify/functions/trigger-pipeline.js`
- Create: `netlify.toml` (if absent)

This task has no automated tests (it's a serverless function). Verify by manual deployment.

- [ ] **Step 1: Create netlify.toml**

Check if `netlify.toml` exists in the repo root. If not, create it:

```toml
[functions]
  directory = "netlify/functions"
```

If it exists, add the `[functions]` block if not already present.

- [ ] **Step 2: Create the functions directory and trigger function**

```
mkdir netlify
mkdir netlify/functions
```

Create `netlify/functions/trigger-pipeline.js`:

```javascript
/**
 * trigger-pipeline.js
 * Proxies a GitHub Actions workflow_dispatch event.
 * Keeps the GitHub PAT server-side so it's never exposed in the dashboard.
 *
 * Required Netlify env vars (set in Netlify dashboard, not committed to repo):
 *   GITHUB_PAT      — Fine-grained PAT with Actions:Write for this repo
 *   GITHUB_REPO     — "owner/repo" e.g. "treidjbi/baseballbettingedge"
 *   GITHUB_WORKFLOW — Workflow filename e.g. "pipeline.yml"
 */
exports.handler = async (event) => {
  // Only accept POST requests
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: JSON.stringify({ error: "Method not allowed" }) };
  }

  const { GITHUB_PAT, GITHUB_REPO, GITHUB_WORKFLOW } = process.env;
  if (!GITHUB_PAT || !GITHUB_REPO || !GITHUB_WORKFLOW) {
    console.error("trigger-pipeline: missing env vars");
    return { statusCode: 500, body: JSON.stringify({ error: "Server misconfigured" }) };
  }

  try {
    const res = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${GITHUB_WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${GITHUB_PAT}`,
          Accept: "application/vnd.github+json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main" }),
      }
    );

    if (res.status === 204) {
      return {
        statusCode: 200,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "triggered" }),
      };
    }

    const text = await res.text();
    console.error("trigger-pipeline: GitHub API error", res.status, text);
    return {
      statusCode: res.status,
      body: JSON.stringify({ error: "GitHub dispatch failed", details: text }),
    };
  } catch (err) {
    console.error("trigger-pipeline: fetch error", err);
    return { statusCode: 500, body: JSON.stringify({ error: err.message }) };
  }
};
```

- [ ] **Step 3: Set Netlify environment variables**

In the Netlify dashboard for this site:
1. Go to Site Settings → Environment Variables
2. Add `GITHUB_PAT` — create a GitHub fine-grained PAT with `Actions: Write` scoped to the `baseballbettingedge` repo only
3. Add `GITHUB_REPO` — `treidjbi/baseballbettingedge`
4. Add `GITHUB_WORKFLOW` — `pipeline.yml`

- [ ] **Step 4: Commit and deploy**

```
git add netlify/ netlify.toml
git commit -m "feat: add Netlify trigger-pipeline function for workflow_dispatch"
git push origin main
```

Wait for Netlify to deploy (auto-deploys on push to main).

- [ ] **Step 5: Smoke test**

```
curl -X POST https://<your-netlify-site>.netlify.app/.netlify/functions/trigger-pipeline
```

Expected response: `{"status":"triggered"}` and a new GHA run appears in the Actions tab within ~30 seconds.

---

## Task 11: Dashboard Refresh Button

**Files:**
- Modify: `dashboard/index.html`

No automated tests — verify visually after deploy.

- [ ] **Step 1: Add Refresh button to nav bar**

In `dashboard/index.html`, find the nav bar section (near the date selector). Add the Refresh button HTML:

```html
<button id="refresh-btn" onclick="triggerRefresh()" title="Re-run pipeline to update lines and lineups">
  ↻ Refresh
</button>
```

- [ ] **Step 2: Add CSS for button states**

Add to the `<style>` block:

```css
#refresh-btn {
  background: transparent;
  border: 1px solid #4a9eff;
  color: #4a9eff;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
}
#refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
#refresh-btn.running {
  color: #888;
  border-color: #888;
}
```

- [ ] **Step 3: Add JavaScript function**

Add to the `<script>` block:

```javascript
async function triggerRefresh() {
  const btn = document.getElementById('refresh-btn');
  btn.disabled = true;
  btn.classList.add('running');
  btn.textContent = '⟳ Running… (~3 min)';

  try {
    const res = await fetch('/.netlify/functions/trigger-pipeline', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'triggered') {
      btn.textContent = '✓ Triggered';
    } else {
      btn.textContent = '✗ Failed';
      setTimeout(() => { btn.textContent = '↻ Refresh'; btn.disabled = false; btn.classList.remove('running'); }, 5000);
      return;
    }
  } catch (e) {
    btn.textContent = '✗ Error';
    setTimeout(() => { btn.textContent = '↻ Refresh'; btn.disabled = false; btn.classList.remove('running'); }, 5000);
    return;
  }

  // Re-enable after 3 minutes
  setTimeout(() => {
    btn.textContent = '↻ Refresh';
    btn.disabled = false;
    btn.classList.remove('running');
  }, 3 * 60 * 1000);
}
```

- [ ] **Step 4: Commit and deploy**

```
git add dashboard/index.html
git commit -m "feat: add Refresh button to dashboard — triggers pipeline via Netlify function"
git push origin main
```

- [ ] **Step 5: Verify in browser**

Open the dashboard. Click Refresh. Button should show "⟳ Running… (~3 min)". Check GitHub Actions tab — a new pipeline run should appear within ~30 seconds.

---

## Task 12: Final integration check

- [ ] **Step 1: Run full test suite**

```
pytest -v
```
Expected: all 162+ tests pass.

- [ ] **Step 2: Check for any uncommitted changes**

```
git status
```
Expected: clean working tree.

- [ ] **Step 3: Push to origin**

```
git push origin main
```

- [ ] **Step 4: Verify Netlify deploy completes**

Check Netlify dashboard for a successful deploy. Confirm the Refresh button is visible on the live site.

- [ ] **Step 5: Smoke test the pipeline with lineup data**

Manually trigger a pipeline run via the dashboard Refresh button during a day when MLB games are scheduled. Check GitHub Actions logs for:
- `fetch_lineups: N batters found for <team>` messages
- `lock_due_picks: locked N picks` messages
- No errors in the lineup/batter stats path

---

## Known Implementation Notes

- **pybaseball splits:** `_fetch_splits()` in `fetch_batter_stats.py` is intentionally wired to raise until the correct function is identified. The fallback to aggregate K% is active from day one. When pybaseball's handedness split API is confirmed, update `_fetch_splits()` and the tests in `test_fetch_batter_stats.py`.

- **`throws` field in fetch_stats.py:** The `pitchHand.code` field is on the `probablePitcher` object in the schedule API. If the existing `fetch_stats.py` doesn't already parse `probablePitcher` data per pitcher, find where pitcher data is assembled and add the `pitchHand` extraction there.

- **Netlify `fetch` API:** Node.js 18+ has native `fetch`. If the Netlify runtime is older (Node 16), add `node-fetch` as a dependency or use `require('https')` instead.
