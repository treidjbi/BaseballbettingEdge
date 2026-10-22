# Pipeline Data Completeness Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close eight data gaps in the picks pipeline — store all fields that are already computed but silently dropped, and refresh stats alongside odds on every pipeline run so the model uses the latest data right up to the T-30min lock.

**Architecture:** All changes are confined to `pipeline/fetch_results.py` and `pipeline/build_features.py`. Every new field is already present in `today.json` (produced by `build_pitcher_record`) — the DB schema, `seed_picks`, `export_db_to_history`, and `load_history_into_db` simply need to plumb them through. SQLite `ALTER TABLE` migrations in `init_db` handle live databases with no data loss. Stats that currently freeze at first-insert will now refresh alongside odds until the existing `locked_at IS NULL` gate seals everything 30 minutes before game time.

**Tech Stack:** Python 3.12, SQLite (via stdlib `sqlite3`), pytest, existing project test patterns in `tests/`

---

## Files Changed

| File | What changes |
|------|-------------|
| `pipeline/fetch_results.py` | `init_db` — add 8 new columns + migrations; `seed_picks` — INSERT/UPDATE extended; `export_db_to_history` — SELECT extended; `load_history_into_db` — INSERT extended |
| `pipeline/build_features.py` | `build_pitcher_record` return dict — add `pitcher_throws` |
| `tests/test_fetch_results.py` | `today_json` fixture extended; new test class for new columns; new test for stats-refresh behaviour |
| `tests/test_build_features.py` | One new assertion on `build_pitcher_record` return |

No new files. No schema renames. No changes to `run_pipeline.py`, `fetch_stats.py`, or the dashboard.

---

## New DB Columns Reference

| Column | Type | Source in today.json | Refreshed on update? |
|--------|------|----------------------|----------------------|
| `opp_team` | TEXT | `p["opp_team"]` | no (static per game) |
| `pitcher_throws` | TEXT | `p["pitcher_throws"]` (new) | no (static) |
| `best_over_odds` | INTEGER | `p["best_over_odds"]` | **yes** — odds move |
| `best_under_odds` | INTEGER | `p["best_under_odds"]` | **yes** |
| `opening_over_odds` | INTEGER | `p["opening_over_odds"]` | **yes** — preview lines may update |
| `opening_under_odds` | INTEGER | `p["opening_under_odds"]` | **yes** |
| `swstr_pct` | REAL | `p["swstr_pct"]` | **yes** — ump and lineup arrive later |
| `career_swstr_pct` | REAL | `p["career_swstr_pct"]` | no (career baseline is static) |

**Stats now refreshed on every update** (previously frozen at first insert):
`opp_k_rate`, `swstr_delta_k9`, `raw_lambda`, `ump_k_adj`, `season_k9`, `recent_k9`, `career_k9`, `avg_ip`, `lineup_used`, `swstr_pct`

These all freeze automatically when `locked_at` is set (the existing `WHERE locked_at IS NULL` gate in the UPDATE already handles this — no lock logic changes required).

---

## Task 1: Add `pitcher_throws` to `build_pitcher_record`

**Files:**
- Modify: `pipeline/build_features.py` — `build_pitcher_record` return dict
- Test: `tests/test_build_features.py`

- [ ] **Step 1.1 — Write failing test**

In `tests/test_build_features.py`, add to the existing test class (or as a standalone test at the bottom):

```python
def test_build_pitcher_record_includes_pitcher_throws():
    """pitcher_throws should be present and reflect stats['throws']."""
    from build_features import build_pitcher_record
    odds = {
        "pitcher": "Test Pitcher", "k_line": 5.5,
        "best_over_odds": -115, "best_under_odds": -105,
        "opening_over_odds": -110, "opening_under_odds": -110,
        "best_over_book": "FanDuel", "game_time": "2026-04-15T17:05:00Z",
        "team": "NYY", "opp_team": "BOS",
    }
    stats = {
        "team": "NYY", "opp_team": "BOS", "throws": "L",
        "season_k9": 8.0, "recent_k9": 8.0, "career_k9": 8.0,
        "innings_pitched_season": 30.0, "avg_ip_last5": 5.5,
        "starts_count": 6, "opp_k_rate": 0.227, "opp_games_played": 10,
    }
    rec = build_pitcher_record(odds, stats, ump_k_adj=0.0)
    assert rec["pitcher_throws"] == "L"


def test_build_pitcher_record_throws_defaults_to_R_when_missing():
    from build_features import build_pitcher_record
    odds = {
        "pitcher": "Test Pitcher", "k_line": 5.5,
        "best_over_odds": -115, "best_under_odds": -105,
        "opening_over_odds": -110, "opening_under_odds": -110,
        "best_over_book": "FanDuel", "game_time": "2026-04-15T17:05:00Z",
        "team": "NYY", "opp_team": "BOS",
    }
    stats = {
        "team": "NYY", "opp_team": "BOS",   # no "throws" key
        "season_k9": 8.0, "recent_k9": 8.0, "career_k9": 8.0,
        "innings_pitched_season": 30.0, "avg_ip_last5": 5.5,
        "starts_count": 6, "opp_k_rate": 0.227, "opp_games_played": 10,
    }
    rec = build_pitcher_record(odds, stats, ump_k_adj=0.0)
    assert rec["pitcher_throws"] == "R"
```

- [ ] **Step 1.2 — Run to confirm failure**

```
pytest tests/test_build_features.py::test_build_pitcher_record_includes_pitcher_throws -v
```
Expected: `FAILED` — KeyError or AssertionError on `rec["pitcher_throws"]`

- [ ] **Step 1.3 — Implement**

In `pipeline/build_features.py`, inside `build_pitcher_record`, find the `return {` block (line ~300). Add `"pitcher_throws"` after `"opp_team"`:

```python
    return {
        "pitcher":            odds["pitcher"],
        "team":               team,
        "opp_team":           opp_team,
        "pitcher_throws":     stats.get("throws", "R"),   # ← add this line
        "game_time":          odds["game_time"],
        # ... rest unchanged
    }
```

- [ ] **Step 1.4 — Run tests**

```
pytest tests/test_build_features.py -v
```
Expected: all pass including the two new tests.

- [ ] **Step 1.5 — Commit**

```bash
git add pipeline/build_features.py tests/test_build_features.py
git commit -m "feat: add pitcher_throws to build_pitcher_record output"
```

---

## Task 2: Add new columns to DB schema + migrations

**Files:**
- Modify: `pipeline/fetch_results.py` — `init_db()`
- Test: `tests/test_fetch_results.py`

- [ ] **Step 2.1 — Write failing tests**

Add a new test class to `tests/test_fetch_results.py`:

```python
class TestNewColumns:
    """All new schema columns must exist after init_db()."""

    NEW_COLS = [
        "opp_team", "pitcher_throws",
        "best_over_odds", "best_under_odds",
        "opening_over_odds", "opening_under_odds",
        "swstr_pct", "career_swstr_pct",
    ]

    def test_new_columns_exist_after_init(self, tmp_db):
        db_path, fr = tmp_db
        conn = fr.get_db()
        cols = {row[1] for row in conn.execute("PRAGMA table_info(picks)")}
        conn.close()
        for col in self.NEW_COLS:
            assert col in cols, f"Missing column: {col}"

    def test_migration_adds_columns_to_existing_db(self, tmp_path):
        """init_db on a pre-existing DB without new columns must add them safely."""
        import sqlite3
        db = tmp_path / "old.db"
        # Create a minimal old-schema DB (no new columns)
        with sqlite3.connect(db) as conn:
            conn.execute("""
                CREATE TABLE picks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT, pitcher TEXT, team TEXT, side TEXT,
                    k_line REAL, verdict TEXT, ev REAL, adj_ev REAL,
                    raw_lambda REAL, applied_lambda REAL, odds INTEGER,
                    movement_conf REAL, result TEXT
                )
            """)
            conn.execute("INSERT INTO picks (date,pitcher,team,side,k_line,verdict,ev,adj_ev,raw_lambda,applied_lambda,odds,movement_conf) VALUES ('2026-04-01','P','T','over',5.5,'LEAN',0.02,0.02,5.0,5.0,-115,1.0)")

        with patch("fetch_results.DB_PATH", db):
            import fetch_results
            fetch_results.init_db()
            conn = fetch_results.get_db()
            cols = {row[1] for row in conn.execute("PRAGMA table_info(picks)")}
            conn.close()

        for col in self.NEW_COLS:
            assert col in cols, f"Migration failed to add: {col}"
        # Existing row must still be present
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0] == 1
```

- [ ] **Step 2.2 — Run to confirm failure**

```
pytest tests/test_fetch_results.py::TestNewColumns -v
```
Expected: `FAILED` — columns not found.

- [ ] **Step 2.3 — Implement**

In `pipeline/fetch_results.py`, inside `init_db()`, extend the existing migration loop. Find the block starting with `for col, defn in [` (around line 81) and extend it to include all new columns:

```python
        for col, defn in [
            ("game_time",          "TEXT"),
            ("lineup_used",        "INTEGER NOT NULL DEFAULT 0"),
            ("locked_at",          "TEXT"),
            ("locked_k_line",      "REAL"),
            ("locked_odds",        "INTEGER"),
            ("locked_adj_ev",      "REAL"),
            ("locked_verdict",     "TEXT"),
            # ── New columns ──────────────────────────────────────
            ("opp_team",           "TEXT"),
            ("pitcher_throws",     "TEXT"),
            ("best_over_odds",     "INTEGER"),
            ("best_under_odds",    "INTEGER"),
            ("opening_over_odds",  "INTEGER"),
            ("opening_under_odds", "INTEGER"),
            ("swstr_pct",          "REAL"),
            ("career_swstr_pct",   "REAL"),
        ]:
```

Also add the new columns to the `CREATE TABLE IF NOT EXISTS picks` statement (for fresh DBs), inserting them after `ref_book TEXT`:

```sql
                ref_book        TEXT,
                opp_team        TEXT,
                pitcher_throws  TEXT,
                best_over_odds  INTEGER,
                best_under_odds INTEGER,
                opening_over_odds  INTEGER,
                opening_under_odds INTEGER,
                swstr_pct       REAL,
                career_swstr_pct REAL,
                game_time       TEXT,
```

- [ ] **Step 2.4 — Run tests**

```
pytest tests/test_fetch_results.py::TestNewColumns -v
```
Expected: both pass.

- [ ] **Step 2.5 — Run full suite to check no regressions**

```
pytest tests/ -v
```
Expected: all existing tests pass.

- [ ] **Step 2.6 — Commit**

```bash
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: add 8 new schema columns to picks DB with auto-migration"
```

---

## Task 3: Update `seed_picks` — INSERT and stats-refresh UPDATE

**Files:**
- Modify: `pipeline/fetch_results.py` — `seed_picks()`
- Test: `tests/test_fetch_results.py`

This is the core stats-lock fix. The INSERT stores all new fields on first write. The UPDATE now also refreshes stats (`opp_k_rate`, `swstr_delta_k9`, `raw_lambda`, `ump_k_adj`, `season_k9`, `recent_k9`, `career_k9`, `avg_ip`, `swstr_pct`, `best_over_odds`, `best_under_odds`, `opening_over_odds`, `opening_under_odds`) so they are as fresh as possible at lock time. The existing `WHERE locked_at IS NULL AND result IS NULL` gate already prevents updates after the pick is locked — no lock logic changes needed.

- [ ] **Step 3.1 — Write failing tests**

Add to `tests/test_fetch_results.py`:

```python
class TestSeedPicksNewFields:

    def _make_today_json(self, tmp_path, extra_fields=None):
        """Build a minimal today.json with one FIRE 1u over pick."""
        base = {
            "date": "2026-04-15",
            "props_available": True,
            "pitchers": [{
                "pitcher": "Gerrit Cole", "team": "New York Yankees",
                "opp_team": "Boston Red Sox",
                "pitcher_throws": "R",
                "game_time": "2026-04-15T23:05:00Z",
                "k_line": 7.5,
                "raw_lambda": 7.2, "lambda": 7.2,
                "season_k9": 9.1, "recent_k9": 8.8, "career_k9": 9.0,
                "avg_ip": 5.8, "opp_k_rate": 0.235, "ump_k_adj": 0.2,
                "swstr_delta_k9": 0.15, "swstr_pct": 0.132, "career_swstr_pct": 0.120,
                "best_over_odds": -115, "best_under_odds": -105,
                "opening_over_odds": -110, "opening_under_odds": -110,
                "ref_book": "FanDuel",
                "lineup_used": False,
                "ev_over":  {"ev": 0.05, "adj_ev": 0.05, "verdict": "FIRE 1u",
                             "win_prob": 0.58, "movement_conf": 1.0},
                "ev_under": {"ev": -0.02, "adj_ev": -0.02, "verdict": "PASS",
                             "win_prob": 0.42, "movement_conf": 1.0},
            }],
        }
        if extra_fields:
            base["pitchers"][0].update(extra_fields)
        p = tmp_path / "today.json"
        p.write_text(json.dumps(base))
        return p

    def test_insert_stores_new_fields(self, tmp_db, tmp_path):
        db_path, fr = tmp_db
        today = self._make_today_json(tmp_path)
        fr.seed_picks(today)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT opp_team, pitcher_throws, best_over_odds, best_under_odds, "
            "opening_over_odds, opening_under_odds, swstr_pct, career_swstr_pct "
            "FROM picks WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()

        assert row["opp_team"] == "Boston Red Sox"
        assert row["pitcher_throws"] == "R"
        assert row["best_over_odds"] == -115
        assert row["best_under_odds"] == -105
        assert row["opening_over_odds"] == -110
        assert row["opening_under_odds"] == -110
        assert abs(row["swstr_pct"] - 0.132) < 0.001
        assert abs(row["career_swstr_pct"] - 0.120) < 0.001

    def test_update_refreshes_stats_on_second_run(self, tmp_db, tmp_path):
        """A second seed_picks call with updated data should refresh stats + odds
        on unlocked picks."""
        db_path, fr = tmp_db
        # First insert: original odds and opp_k_rate
        today_v1 = self._make_today_json(tmp_path)
        fr.seed_picks(today_v1)

        # Second run: lineup now available, odds shifted, opp_k_rate updated
        today_v2 = self._make_today_json(tmp_path, extra_fields={
            "best_over_odds": -125,      # odds moved
            "opp_k_rate": 0.248,         # lineup K rate now available
            "swstr_delta_k9": 0.20,      # updated SwStr delta
            "lineup_used": True,
            "lambda": 7.4,               # recomputed lambda
            "ev_over": {"ev": 0.06, "adj_ev": 0.06, "verdict": "FIRE 1u",
                        "win_prob": 0.60, "movement_conf": 1.0},
            "ev_under": {"ev": -0.03, "adj_ev": -0.03, "verdict": "PASS",
                         "win_prob": 0.40, "movement_conf": 1.0},
        })
        fr.seed_picks(today_v2)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT best_over_odds, opp_k_rate, swstr_delta_k9, lineup_used, applied_lambda "
            "FROM picks WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()

        assert row["best_over_odds"] == -125,     "odds should refresh on second run"
        assert abs(row["opp_k_rate"] - 0.248) < 0.001, "opp_k_rate should refresh when lineup arrives"
        assert abs(row["swstr_delta_k9"] - 0.20) < 0.001
        assert row["lineup_used"] == 1
        assert abs(row["applied_lambda"] - 7.4) < 0.01

    def test_locked_pick_stats_not_refreshed(self, tmp_db, tmp_path):
        """Once a pick is locked, stats and odds must not change."""
        db_path, fr = tmp_db
        today_v1 = self._make_today_json(tmp_path)
        fr.seed_picks(today_v1)

        # Lock the pick manually
        conn = fr.get_db()
        conn.execute(
            "UPDATE picks SET locked_at='2026-04-15T22:35:00Z' "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        )
        conn.commit()
        conn.close()

        # Second run with different odds and stats
        today_v2 = self._make_today_json(tmp_path, extra_fields={
            "best_over_odds": -140,
            "opp_k_rate": 0.260,
        })
        fr.seed_picks(today_v2)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT best_over_odds, opp_k_rate FROM picks "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()

        assert row["best_over_odds"] == -115, "locked pick odds must not change"
        assert abs(row["opp_k_rate"] - 0.235) < 0.001, "locked pick stats must not change"
```

- [ ] **Step 3.2 — Run to confirm failures**

```
pytest tests/test_fetch_results.py::TestSeedPicksNewFields -v
```
Expected: all three tests `FAILED`.

- [ ] **Step 3.3 — Implement: extend the INSERT**

In `pipeline/fetch_results.py`, replace the `seed_picks` INSERT block (around lines 117–134) with:

```python
                cur = conn.execute("""
                    INSERT OR IGNORE INTO picks
                    (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                     raw_lambda, applied_lambda, odds, movement_conf,
                     season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                     swstr_delta_k9, ref_book, game_time, lineup_used,
                     opp_team, pitcher_throws,
                     best_over_odds, best_under_odds,
                     opening_over_odds, opening_under_odds,
                     swstr_pct, career_swstr_pct)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    game_date, p["pitcher"], p["team"], side,
                    p["k_line"], ev_data["verdict"], ev_data["ev"], ev_data["adj_ev"],
                    p.get("raw_lambda", p["lambda"]), p["lambda"], odds,
                    ev_data["movement_conf"],
                    p.get("season_k9"), p.get("recent_k9"), p.get("career_k9"),
                    p.get("avg_ip"), p.get("ump_k_adj"), p.get("opp_k_rate"),
                    p.get("swstr_delta_k9"),
                    p.get("ref_book"),
                    p.get("game_time"),
                    int(bool(p.get("lineup_used", False))),
                    p.get("opp_team"),
                    p.get("pitcher_throws"),
                    p.get("best_over_odds"),
                    p.get("best_under_odds"),
                    p.get("opening_over_odds"),
                    p.get("opening_under_odds"),
                    p.get("swstr_pct"),
                    p.get("career_swstr_pct"),
                ))
```

- [ ] **Step 3.4 — Implement: extend the UPDATE (stats-refresh fix)**

Replace the UPDATE block (around lines 139–153) with:

```python
                if cur.rowcount == 0:
                    conn.execute("""
                        UPDATE picks
                        SET verdict = ?, ev = ?, adj_ev = ?, odds = ?,
                            k_line = ?, applied_lambda = ?, movement_conf = ?,
                            lineup_used = ?, game_time = ?,
                            raw_lambda = ?,
                            opp_k_rate = ?, swstr_delta_k9 = ?,
                            season_k9 = ?, recent_k9 = ?, career_k9 = ?,
                            avg_ip = ?, ump_k_adj = ?, swstr_pct = ?,
                            best_over_odds = ?, best_under_odds = ?,
                            opening_over_odds = ?, opening_under_odds = ?
                        WHERE date = ? AND pitcher = ? AND side = ?
                          AND locked_at IS NULL AND result IS NULL
                    """, (
                        ev_data["verdict"], ev_data["ev"], ev_data["adj_ev"], odds,
                        p["k_line"], p["lambda"], ev_data["movement_conf"],
                        int(bool(p.get("lineup_used", False))),
                        p.get("game_time"),
                        p.get("raw_lambda", p["lambda"]),
                        p.get("opp_k_rate"), p.get("swstr_delta_k9"),
                        p.get("season_k9"), p.get("recent_k9"), p.get("career_k9"),
                        p.get("avg_ip"), p.get("ump_k_adj"), p.get("swstr_pct"),
                        p.get("best_over_odds"), p.get("best_under_odds"),
                        p.get("opening_over_odds"), p.get("opening_under_odds"),
                        game_date, p["pitcher"], side,
                    ))
                    updated += conn.execute("SELECT changes()").fetchone()[0]
```

Note: `opp_team`, `pitcher_throws`, and `career_swstr_pct` are intentionally excluded from the UPDATE — these are static per game and correct at insert time.

- [ ] **Step 3.5 — Run tests**

```
pytest tests/test_fetch_results.py::TestSeedPicksNewFields -v
```
Expected: all three pass.

- [ ] **Step 3.6 — Run full suite**

```
pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 3.7 — Commit**

```bash
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: store all computed fields in DB; refresh stats alongside odds until lock"
```

---

## Task 4: Update `export_db_to_history` and `load_history_into_db`

**Files:**
- Modify: `pipeline/fetch_results.py` — `export_db_to_history()` and `load_history_into_db()`
- Test: `tests/test_fetch_results.py`

- [ ] **Step 4.1 — Write failing test**

Add to `tests/test_fetch_results.py`:

```python
class TestExportLoadRoundTrip:
    """New fields survive a full DB → JSON → DB round trip."""

    NEW_FIELD_PICK = {
        "date": "2026-04-15", "pitcher": "Export Test", "team": "NYY",
        "opp_team": "BOS", "pitcher_throws": "L", "side": "over",
        "k_line": 6.5, "verdict": "FIRE 1u", "ev": 0.05, "adj_ev": 0.05,
        "raw_lambda": 6.2, "applied_lambda": 6.2, "odds": -115,
        "movement_conf": 1.0,
        "season_k9": 9.1, "recent_k9": 8.8, "career_k9": 9.0,
        "avg_ip": 5.8, "ump_k_adj": 0.0, "opp_k_rate": 0.235,
        "swstr_delta_k9": 0.12, "swstr_pct": 0.130, "career_swstr_pct": 0.115,
        "best_over_odds": -115, "best_under_odds": -105,
        "opening_over_odds": -110, "opening_under_odds": -110,
        "ref_book": "FanDuel", "game_time": "2026-04-15T23:05:00Z",
        "lineup_used": 0,
        "locked_at": None, "locked_k_line": None, "locked_odds": None,
        "locked_adj_ev": None, "locked_verdict": None,
        "result": "win", "actual_ks": 8, "pnl": 0.87, "fetched_at": "2026-04-16T03:00:00Z",
    }

    def test_new_fields_survive_export_and_reload(self, tmp_db, tmp_path):
        db_path, fr = tmp_db
        history = tmp_path / "history.json"

        # Insert directly so we control all fields
        conn = fr.get_db()
        conn.execute("""
            INSERT INTO picks
            (date, pitcher, team, opp_team, pitcher_throws, side, k_line,
             verdict, ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf,
             season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
             swstr_delta_k9, swstr_pct, career_swstr_pct,
             best_over_odds, best_under_odds, opening_over_odds, opening_under_odds,
             ref_book, game_time, lineup_used, result, actual_ks, pnl, fetched_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "2026-04-15", "Export Test", "NYY", "BOS", "L", "over",
            6.5, "FIRE 1u", 0.05, 0.05, 6.2, 6.2, -115, 1.0,
            9.1, 8.8, 9.0, 5.8, 0.0, 0.235,
            0.12, 0.130, 0.115,
            -115, -105, -110, -110,
            "FanDuel", "2026-04-15T23:05:00Z", 0,
            "win", 8, 0.87, "2026-04-16T03:00:00Z",
        ))
        conn.commit()
        conn.close()

        # Export
        fr.HISTORY_PATH = history
        fr.export_db_to_history(history)

        # Verify JSON contains new fields
        with open(history) as f:
            exported = json.load(f)
        assert len(exported) == 1
        p = exported[0]
        assert p["opp_team"] == "BOS"
        assert p["pitcher_throws"] == "L"
        assert p["best_over_odds"] == -115
        assert p["best_under_odds"] == -105
        assert p["opening_over_odds"] == -110
        assert p["opening_under_odds"] == -110
        assert abs(p["swstr_pct"] - 0.130) < 0.001
        assert abs(p["career_swstr_pct"] - 0.115) < 0.001

        # Reload into a fresh DB and verify
        fresh_db = tmp_path / "fresh.db"
        with patch("fetch_results.DB_PATH", fresh_db):
            fr.init_db()
            fr.load_history_into_db(history)
            conn2 = fr.get_db()
            row = conn2.execute(
                "SELECT opp_team, pitcher_throws, best_over_odds, swstr_pct "
                "FROM picks WHERE pitcher='Export Test'"
            ).fetchone()
            conn2.close()

        assert row["opp_team"] == "BOS"
        assert row["pitcher_throws"] == "L"
        assert row["best_over_odds"] == -115
        assert abs(row["swstr_pct"] - 0.130) < 0.001
```

- [ ] **Step 4.2 — Run to confirm failure**

```
pytest tests/test_fetch_results.py::TestExportLoadRoundTrip -v
```
Expected: `FAILED` — missing keys in exported JSON.

- [ ] **Step 4.3 — Implement: update `export_db_to_history`**

In `pipeline/fetch_results.py`, replace the SELECT and cols list in `export_db_to_history` (around lines 251–268):

```python
        rows = conn.execute("""
            SELECT date, pitcher, team, opp_team, pitcher_throws, side, k_line,
                   verdict, ev, adj_ev,
                   raw_lambda, applied_lambda, odds, movement_conf,
                   season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                   swstr_delta_k9, swstr_pct, career_swstr_pct, ref_book,
                   best_over_odds, best_under_odds,
                   opening_over_odds, opening_under_odds,
                   result, actual_ks, pnl, fetched_at,
                   game_time, lineup_used,
                   locked_at, locked_k_line, locked_odds, locked_adj_ev, locked_verdict
            FROM picks
            ORDER BY date, pitcher, side
        """).fetchall()

    cols = [
        "date", "pitcher", "team", "opp_team", "pitcher_throws", "side", "k_line",
        "verdict", "ev", "adj_ev",
        "raw_lambda", "applied_lambda", "odds", "movement_conf",
        "season_k9", "recent_k9", "career_k9", "avg_ip", "ump_k_adj", "opp_k_rate",
        "swstr_delta_k9", "swstr_pct", "career_swstr_pct", "ref_book",
        "best_over_odds", "best_under_odds",
        "opening_over_odds", "opening_under_odds",
        "result", "actual_ks", "pnl", "fetched_at",
        "game_time", "lineup_used",
        "locked_at", "locked_k_line", "locked_odds", "locked_adj_ev", "locked_verdict",
    ]
    picks = [dict(zip(cols, row)) for row in rows]
```

- [ ] **Step 4.4 — Implement: update `load_history_into_db`**

In `pipeline/fetch_results.py`, replace the INSERT in `load_history_into_db` (around lines 217–237):

```python
            cur = conn.execute("""
                INSERT OR IGNORE INTO picks
                (date, pitcher, team, opp_team, pitcher_throws, side, k_line,
                 verdict, ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf,
                 season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                 swstr_delta_k9, swstr_pct, career_swstr_pct, ref_book,
                 best_over_odds, best_under_odds, opening_over_odds, opening_under_odds,
                 result, actual_ks, pnl, fetched_at, game_time, lineup_used,
                 locked_at, locked_k_line, locked_odds, locked_adj_ev, locked_verdict)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                p.get("date"), p.get("pitcher"), p.get("team"),
                p.get("opp_team"), p.get("pitcher_throws"),
                p.get("side"),
                p.get("k_line"), p.get("verdict"), p.get("ev"), p.get("adj_ev"),
                p.get("raw_lambda"), p.get("applied_lambda"), p.get("odds"),
                p.get("movement_conf"),
                p.get("season_k9"), p.get("recent_k9"), p.get("career_k9"),
                p.get("avg_ip"), p.get("ump_k_adj"), p.get("opp_k_rate"),
                p.get("swstr_delta_k9"), p.get("swstr_pct"), p.get("career_swstr_pct"),
                p.get("ref_book"),
                p.get("best_over_odds"), p.get("best_under_odds"),
                p.get("opening_over_odds"), p.get("opening_under_odds"),
                p.get("result"), p.get("actual_ks"), p.get("pnl"), p.get("fetched_at"),
                p.get("game_time"), int(bool(p.get("lineup_used", False))),
                p.get("locked_at"), p.get("locked_k_line"), p.get("locked_odds"),
                p.get("locked_adj_ev"), p.get("locked_verdict"),
            ))
```

- [ ] **Step 4.5 — Run tests**

```
pytest tests/test_fetch_results.py::TestExportLoadRoundTrip -v
```
Expected: passes.

- [ ] **Step 4.6 — Run full suite**

```
pytest tests/ -v
```
Expected: all pass. If any existing export/load tests fail, update their fixtures to include the new fields (add `p.get("opp_team")` etc. — existing history JSON without these fields will just return `None` which is valid).

- [ ] **Step 4.7 — Update `today_json` fixture in test file**

The `today_json` fixture (around line 24 in `tests/test_fetch_results.py`) needs the new fields so tests that call `seed_picks` with it don't silently store NULLs. `best_over_odds`, `best_under_odds`, and `opp_team` are already in the fixture — do not duplicate them. Add only the truly missing fields to each pitcher dict:

```python
                "pitcher_throws": "R",
                "opening_over_odds": -110,
                "opening_under_odds": -110,
                "swstr_pct": 0.120,
                "career_swstr_pct": 0.110,
                "swstr_delta_k9": 0.05,
```

- [ ] **Step 4.8 — Run full suite one final time**

```
pytest tests/ -v
```
Expected: all pass, 0 failures.

- [ ] **Step 4.9 — Commit**

```bash
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: export and reload all new fields through picks_history.json"
```

---

## Task 5: Push and verify deploy

- [ ] **Step 5.1 — Pull (pipeline may have committed data since last sync)**

```bash
git pull --rebase origin main
```
If conflict on `data/picks_history.json` or `dashboard/data/`: take `--theirs` (pipeline data is always authoritative).

```bash
git checkout --theirs data/picks_history.json
git add data/picks_history.json
git rebase --continue
```

- [ ] **Step 5.2 — Push**

```bash
git push origin main
```

- [ ] **Step 5.3 — Verify next pipeline run**

After the next GitHub Actions run completes, check `data/picks_history.json` for a recent pick and confirm the new fields are populated:

```bash
# Spot-check: find a pick and verify new fields are not all null
python -c "
import json
picks = json.load(open('data/picks_history.json'))
recent = [p for p in picks if p.get('result') is None][:3]
for p in recent:
    print(p['pitcher'], '|', p.get('opp_team'), '|', p.get('pitcher_throws'), '|', p.get('best_over_odds'))
"
```
Expected: `opp_team` populated (e.g. "Boston Red Sox"), `pitcher_throws` is "R" or "L", `best_over_odds` is an integer.

---

## What This Does Not Change

- Lock timing and `lock_due_picks` logic — unchanged. The `WHERE locked_at IS NULL` gate in `seed_picks` UPDATE is what freezes stats; no new lock code needed.
- `run_pipeline.py` — unchanged. It already passes `p.get("opp_team")` etc. through `today.json`; those fields just weren't being written to the DB.
- Dashboard — unchanged. The new fields are in the DB for analytics but not rendered anywhere yet.
- Grading (`fetch_and_close_results`) — unchanged. Grades on locked_odds which is already correctly captured.
- Phase 2 (handedness model, CSW%) — gated at n≥100 picks; `pitcher_throws` being stored now means historical data will be available when the gate opens.
