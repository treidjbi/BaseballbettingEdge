# Performance Tab Fix + Reference Book Standardization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the blank performance tab by persisting closed picks in `data/picks_history.json` (committed to git), and standardize all odds/lines to a reference book (FanDuel → BetMGM → DraftKings → any fallback) for consistent grading.

**Architecture:** The SQLite `results.db` remains ephemeral (gitignored) — each evening pipeline run loads history from `picks_history.json` into a fresh DB, runs its work, then exports all closed picks back to the JSON. `fetch_odds.py` selects a reference book per pitcher using a priority list; all downstream fields (`k_line`, `best_over_odds`, `best_under_odds`, opening odds) become the ref book's values. No changes needed to `build_features.py` or the dashboard.

**Tech Stack:** Python 3.11, SQLite3, pytest, GitHub Actions, JSON

---

## File Map

| File | Change |
|---|---|
| `data/picks_history.json` | **Create** — bootstrapped from old DB (119 closed picks) |
| `pipeline/fetch_odds.py` | **Modify** — add `REF_BOOK_PRIORITY`, `_select_ref_book()`, ref_book field in output |
| `pipeline/fetch_results.py` | **Modify** — add `HISTORY_PATH`, `ref_book` DB column, `load_history_into_db()`, `export_db_to_history()`, update `seed_picks()` and `run()` |
| `.github/workflows/pipeline.yml` | **Modify** — add `git add data/picks_history.json` to commit step |
| `tests/test_fetch_results.py` | **Modify** — add tests for history load/export, ref_book column |
| `tests/test_fetch_odds.py` | **Modify** — add tests for `_select_ref_book()` priority and fallback |

`build_features.py`, `calibrate.py`, `dashboard/index.html` — **no changes needed**.

---

## Task 1: Bootstrap picks_history.json from old DB

No test needed — this is a one-time data migration.

**Files:**
- Create: `data/picks_history.json`

- [ ] **Step 1: Extract closed picks from the old DB commit**

Run this script from the project root:

```bash
git show 9bed791:data/results.db > /tmp/bootstrap_results.db
```

Then run:

```python
# run as: py -3 bootstrap_history.py  (from project root)
import sqlite3, json
from pathlib import Path

conn = sqlite3.connect('/tmp/bootstrap_results.db')
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT * FROM picks WHERE result IN ('win','loss','push','cancelled')"
).fetchall()
conn.close()

picks = []
for r in rows:
    d = dict(r)
    d.pop("id", None)          # strip auto-increment id
    d["ref_book"] = None       # not tracked in old DB
    picks.append(d)

Path("data/picks_history.json").write_text(json.dumps(picks, indent=2))
print(f"Wrote {len(picks)} picks to data/picks_history.json")
```

Expected output: `Wrote 119 picks to data/picks_history.json`

- [ ] **Step 2: Verify the file**

```bash
py -3 -c "import json; d=json.load(open('data/picks_history.json')); print(len(d), 'picks'); print(d[0])"
```

Expected: 119 picks, first pick has keys: date, pitcher, team, side, k_line, verdict, ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf, season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate, result, actual_ks, pnl, fetched_at, ref_book

- [ ] **Step 3: Commit**

```bash
git add data/picks_history.json
git commit -m "chore: bootstrap picks_history.json with 119 historical closed picks"
```

---

## Task 2: fetch_results.py — history persistence + ref_book column

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `tests/test_fetch_results.py`

### 2a: DB schema — add ref_book column

- [ ] **Step 1: Write the failing test**

Add to `tests/test_fetch_results.py` inside `class TestInitDb`:

```python
def test_ref_book_column_exists(self, tmp_db):
    """picks table should have a ref_book column."""
    db_path, fr = tmp_db
    conn = sqlite3.connect(db_path)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(picks)").fetchall()]
    conn.close()
    assert "ref_book" in cols
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
py -3 -m pytest tests/test_fetch_results.py::TestInitDb::test_ref_book_column_exists -v
```

Expected: FAIL — `ref_book` not in cols

- [ ] **Step 3: Add ref_book to init_db() in fetch_results.py**

In `pipeline/fetch_results.py`, find the `CREATE TABLE IF NOT EXISTS picks` block (line ~35). Add `ref_book TEXT` after the `opp_k_rate` line:

```python
                opp_k_rate      REAL,
                ref_book        TEXT,
                result          TEXT,
```

- [ ] **Step 4: Run test to verify it passes**

```bash
py -3 -m pytest tests/test_fetch_results.py::TestInitDb::test_ref_book_column_exists -v
```

Expected: PASS

### 2b: seed_picks() — store ref_book

- [ ] **Step 5: Write the failing test**

Add to `tests/test_fetch_results.py`. First update the `today_json` fixture to include `ref_book` in both pitchers:

```python
# In the today_json fixture, add "ref_book": "FanDuel" to both pitcher dicts
# e.g. after "best_under_odds": -105, add "ref_book": "FanDuel",
```

Then add a new test inside `class TestSeedPicks`:

```python
def test_seeds_ref_book(self, tmp_db, today_json):
    """seed_picks stores ref_book from today.json."""
    db_path, fr = tmp_db
    p, _ = today_json
    fr.seed_picks(p)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT ref_book FROM picks WHERE pitcher='Gerrit Cole'").fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "FanDuel"
```

- [ ] **Step 6: Run test to verify it fails**

```bash
py -3 -m pytest tests/test_fetch_results.py::TestSeedPicks::test_seeds_ref_book -v
```

Expected: FAIL — ref_book column not populated

- [ ] **Step 7: Update seed_picks() to store ref_book**

In `pipeline/fetch_results.py`, find the `seed_picks` function. Update the INSERT statement to include `ref_book`:

Change the column list from:
```python
                    INSERT OR IGNORE INTO picks
                    (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                     raw_lambda, applied_lambda, odds, movement_conf,
                     season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
```

To:
```python
                    INSERT OR IGNORE INTO picks
                    (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                     raw_lambda, applied_lambda, odds, movement_conf,
                     season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                     ref_book)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
```

And update the values tuple to add `p.get("ref_book")` as the last element:

```python
                ), (
                    game_date, p["pitcher"], p["team"], side,
                    p["k_line"], ev_data["verdict"], ev_data["ev"], ev_data["adj_ev"],
                    p.get("raw_lambda", p["lambda"]), p["lambda"], odds, ev_data["movement_conf"],
                    p.get("season_k9"), p.get("recent_k9"), p.get("career_k9"),
                    p.get("avg_ip"), p.get("ump_k_adj"), p.get("opp_k_rate"),
                    p.get("ref_book"),
                ))
```

- [ ] **Step 8: Run test to verify it passes**

```bash
py -3 -m pytest tests/test_fetch_results.py::TestSeedPicks::test_seeds_ref_book -v
```

Expected: PASS

### 2c: load_history_into_db()

- [ ] **Step 9: Write the failing test**

Add to `tests/test_fetch_results.py` as a new top-level class:

```python
class TestLoadHistoryIntoDb:
    def test_loads_closed_picks_into_db(self, tmp_db, tmp_path):
        """load_history_into_db inserts history records into the DB."""
        db_path, fr = tmp_db
        history = [
            {
                "date": "2026-03-31", "pitcher": "Max Fried", "team": "NYY",
                "side": "over", "k_line": 5.5, "verdict": "FIRE 2u",
                "ev": 0.08, "adj_ev": 0.08, "raw_lambda": 6.1, "applied_lambda": 6.1,
                "odds": -110, "movement_conf": 1.0,
                "season_k9": 9.0, "recent_k9": 8.5, "career_k9": 9.2,
                "avg_ip": 5.5, "ump_k_adj": 0.1, "opp_k_rate": 0.23,
                "result": "win", "actual_ks": 7, "pnl": 0.909,
                "fetched_at": "2026-04-01T03:00:00Z", "ref_book": "FanDuel",
            }
        ]
        history_path = tmp_path / "picks_history.json"
        history_path.write_text(json.dumps(history))

        fr.load_history_into_db(history_path)

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT pitcher, result FROM picks").fetchall()
        conn.close()
        assert ("Max Fried", "win") in rows

    def test_ignores_duplicate_on_reload(self, tmp_db, tmp_path):
        """Calling load_history_into_db twice doesn't duplicate records."""
        db_path, fr = tmp_db
        history = [
            {
                "date": "2026-03-31", "pitcher": "Max Fried", "team": "NYY",
                "side": "over", "k_line": 5.5, "verdict": "FIRE 2u",
                "ev": 0.08, "adj_ev": 0.08, "raw_lambda": 6.1, "applied_lambda": 6.1,
                "odds": -110, "movement_conf": 1.0,
                "season_k9": 9.0, "recent_k9": 8.5, "career_k9": 9.2,
                "avg_ip": 5.5, "ump_k_adj": 0.1, "opp_k_rate": 0.23,
                "result": "win", "actual_ks": 7, "pnl": 0.909,
                "fetched_at": "2026-04-01T03:00:00Z", "ref_book": "FanDuel",
            }
        ]
        history_path = tmp_path / "picks_history.json"
        history_path.write_text(json.dumps(history))

        fr.load_history_into_db(history_path)
        fr.load_history_into_db(history_path)

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
        conn.close()
        assert count == 1

    def test_returns_zero_if_file_missing(self, tmp_db, tmp_path):
        """load_history_into_db returns 0 when history file doesn't exist."""
        db_path, fr = tmp_db
        result = fr.load_history_into_db(tmp_path / "nonexistent.json")
        assert result == 0
```

- [ ] **Step 10: Run tests to verify they fail**

```bash
py -3 -m pytest tests/test_fetch_results.py::TestLoadHistoryIntoDb -v
```

Expected: FAIL — `load_history_into_db` not defined

- [ ] **Step 11: Implement load_history_into_db() in fetch_results.py**

Add after the `HISTORY_PATH` constant (add that too at top of file, after `TODAY_JSON`):

```python
HISTORY_PATH = Path(__file__).parent.parent / "data" / "picks_history.json"
```

Then add the function after `seed_picks()`:

```python
def load_history_into_db(history_path: Path = HISTORY_PATH) -> int:
    """Load closed picks from picks_history.json into DB. Returns count inserted."""
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
                 ref_book, result, actual_ks, pnl, fetched_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                p.get("date"), p.get("pitcher"), p.get("team"), p.get("side"),
                p.get("k_line"), p.get("verdict"), p.get("ev"), p.get("adj_ev"),
                p.get("raw_lambda"), p.get("applied_lambda"), p.get("odds"),
                p.get("movement_conf"), p.get("season_k9"), p.get("recent_k9"),
                p.get("career_k9"), p.get("avg_ip"), p.get("ump_k_adj"),
                p.get("opp_k_rate"), p.get("ref_book"), p.get("result"),
                p.get("actual_ks"), p.get("pnl"), p.get("fetched_at"),
            ))
            inserted += cur.rowcount

    log.info("load_history_into_db: inserted %d picks from history", inserted)
    return inserted
```

- [ ] **Step 12: Run tests to verify they pass**

```bash
py -3 -m pytest tests/test_fetch_results.py::TestLoadHistoryIntoDb -v
```

Expected: all 3 PASS

### 2d: export_db_to_history()

- [ ] **Step 13: Write the failing test**

Add to `tests/test_fetch_results.py` as a new top-level class:

```python
class TestExportDbToHistory:
    def test_writes_closed_picks_to_json(self, tmp_db, tmp_path):
        """export_db_to_history writes all closed picks to JSON."""
        db_path, fr = tmp_db
        # Insert one open and one closed pick directly
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT INTO picks (date, pitcher, team, side, k_line, verdict,
                  ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf,
                  result, actual_ks, pnl)
                VALUES ('2026-04-01','Zack Wheeler','PHI','over',6.5,'FIRE 2u',
                  0.09,0.09,7.1,7.1,-108,1.0,'win',8,0.926)
            """)
            conn.execute("""
                INSERT INTO picks (date, pitcher, team, side, k_line, verdict,
                  ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf,
                  result)
                VALUES ('2026-04-02','Dylan Cease','SDP','over',5.5,'FIRE 1u',
                  0.05,0.05,6.0,6.0,-110,1.0, NULL)
            """)

        history_path = tmp_path / "picks_history.json"
        fr.export_db_to_history(history_path)

        written = json.loads(history_path.read_text())
        pitchers = [r["pitcher"] for r in written]
        assert "Zack Wheeler" in pitchers
        assert "Dylan Cease" not in pitchers  # open pick excluded

    def test_overwrites_existing_file(self, tmp_db, tmp_path):
        """export_db_to_history replaces existing history file."""
        db_path, fr = tmp_db
        history_path = tmp_path / "picks_history.json"
        history_path.write_text('[{"stale": true}]')

        fr.export_db_to_history(history_path)

        written = json.loads(history_path.read_text())
        assert written == []  # empty DB → empty array, stale content gone
```

- [ ] **Step 14: Run tests to verify they fail**

```bash
py -3 -m pytest tests/test_fetch_results.py::TestExportDbToHistory -v
```

Expected: FAIL — `export_db_to_history` not defined

- [ ] **Step 15: Implement export_db_to_history() in fetch_results.py**

Add after `load_history_into_db()`:

```python
def export_db_to_history(history_path: Path = HISTORY_PATH) -> int:
    """Export all closed picks from DB to picks_history.json. Returns count written."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                   raw_lambda, applied_lambda, odds, movement_conf,
                   season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
                   ref_book, result, actual_ks, pnl, fetched_at
            FROM picks
            WHERE result IS NOT NULL
            ORDER BY date, pitcher, side
        """).fetchall()

    picks = [dict(zip(
        ["date","pitcher","team","side","k_line","verdict","ev","adj_ev",
         "raw_lambda","applied_lambda","odds","movement_conf",
         "season_k9","recent_k9","career_k9","avg_ip","ump_k_adj","opp_k_rate",
         "ref_book","result","actual_ks","pnl","fetched_at"],
        row
    )) for row in rows]

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with open(history_path, "w") as f:
        json.dump(picks, f, indent=2)

    log.info("export_db_to_history: wrote %d closed picks", len(picks))
    return len(picks)
```

- [ ] **Step 16: Run tests to verify they pass**

```bash
py -3 -m pytest tests/test_fetch_results.py::TestExportDbToHistory -v
```

Expected: both PASS

### 2e: Update run() to use history

- [ ] **Step 17: Update run() in fetch_results.py**

Find `def run()` (line ~242) and update it to:

```python
def run() -> None:
    """Main entry point for the 8pm pipeline run."""
    init_db()
    loaded = load_history_into_db()
    log.info("Loaded %d picks from history into DB", loaded)
    seeded = seed_picks()
    log.info("Seeded %d picks for today", seeded)
    closed = fetch_and_close_results()
    log.info("Closed %d results for yesterday", closed)
    cancelled = close_orphans()
    log.info("Cancelled %d orphan picks", cancelled)
    exported = export_db_to_history()
    log.info("Exported %d closed picks to history", exported)
```

- [ ] **Step 18: Run the full test suite to verify nothing broke**

```bash
py -3 -m pytest tests/ -v
```

Expected: all existing tests pass + new tests pass

- [ ] **Step 19: Commit**

```bash
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: persist closed picks in picks_history.json, add ref_book column"
```

---

## Task 3: pipeline.yml — commit picks_history.json

**Files:**
- Modify: `.github/workflows/pipeline.yml`

- [ ] **Step 1: Add picks_history.json to the commit step**

In `.github/workflows/pipeline.yml`, find the `Commit pipeline output` step. After the line:

```yaml
          test -f dashboard/data/performance.json && git add dashboard/data/performance.json || true
```

Add:

```yaml
          test -f data/picks_history.json && git add data/picks_history.json || true
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/pipeline.yml
git commit -m "feat: commit picks_history.json in evening pipeline run"
```

---

## Task 4: fetch_odds.py — reference book selection

**Files:**
- Modify: `pipeline/fetch_odds.py`
- Modify: `tests/test_fetch_odds.py`

### 4a: Discover TheRundown book IDs

> **Important:** TheRundown v2 uses numeric string book IDs. The IDs below are the correct values per TheRundown's published book list, but verify against a live API response before deploying.

- [ ] **Step 1: Add BOOK_ID_MAP constant to fetch_odds.py**

Add after the module-level constants (after `THROTTLE_S`):

```python
# TheRundown v2 book IDs. Verify against live API response if lines are missing.
# To discover available IDs: log `list(lines_data[main_val]["over"].keys())` in _parse_event_k_props
BOOK_ID_MAP = {
    "11":  "FanDuel",
    "3":   "DraftKings",
    "6":   "BetMGM",
}
REF_BOOK_PRIORITY = ["11", "6", "3"]   # FanDuel → BetMGM → DraftKings
```

> **Note on book IDs:** Current live data shows all picks coming from book ID "25". If FanDuel, BetMGM, and DraftKings are not ID 11/6/3 in this API version, the fallback to "any available book" will fire. To identify the correct IDs, temporarily add `log.info("Available book IDs for %s: %s", pitcher_name, list(lines_data[main_val]["over"].keys()))` inside `_parse_event_k_props` and run the pipeline once. Update `BOOK_ID_MAP` and `REF_BOOK_PRIORITY` with the correct IDs.

### 4b: Update existing best-over test (breaking change)

The existing `test_selects_best_over_book` test asserts that when two unknown books are available, the one with the best over price wins. After Task 4's change, the code selects by ref-book priority instead. This test must be updated **before** implementing the ref-book logic so the failure reason is intentional.

- [ ] **Step 2: Update test_selects_best_over_book in tests/test_fetch_odds.py**

Replace the existing `test_selects_best_over_book` method (lines ~193–231) with:

```python
def test_selects_ref_book_by_priority(self):
    """Selects FanDuel (book 11) over a better-priced unknown book."""
    event = {
        "event_id": "evt-refbook",
        "event_date": "2026-04-01T23:05:00Z",
        "teams": [
            {"name": "NYY", "is_away": True,  "is_home": False},
            {"name": "BOS", "is_away": False, "is_home": True},
        ],
        "markets": [{
            "market_id": 19,
            "name": "pitcher_strikeouts",
            "participants": [{
                "name": "Gerrit Cole",
                "lines": [
                    {
                        "value": "Over 7.5",
                        "prices": {
                            "25": {"price": -105, "is_main_line": True, "price_delta": 0},
                            "11": {"price": -115, "is_main_line": True, "price_delta": 0},
                        },
                    },
                    {
                        "value": "Under 7.5",
                        "prices": {
                            "25": {"price": -115, "is_main_line": True, "price_delta": 0},
                            "11": {"price": -105, "is_main_line": True, "price_delta": 0},
                        },
                    },
                ],
            }],
        }],
    }
    result = parse_k_props({"events": [event]})
    assert result[0]["best_over_odds"] == -115   # FanDuel (11) wins over Book25 (-105)
    assert result[0]["ref_book"] == "FanDuel"

def test_falls_back_to_any_book_when_no_priority_book(self):
    """Uses first available book when no priority book is present."""
    event = {
        "event_id": "evt-fallback",
        "event_date": "2026-04-01T23:05:00Z",
        "teams": [
            {"name": "NYY", "is_away": True,  "is_home": False},
            {"name": "BOS", "is_away": False, "is_home": True},
        ],
        "markets": [{
            "market_id": 19,
            "name": "pitcher_strikeouts",
            "participants": [{
                "name": "Gerrit Cole",
                "lines": [
                    {
                        "value": "Over 7.5",
                        "prices": {"25": {"price": -110, "is_main_line": True, "price_delta": 0}},
                    },
                    {
                        "value": "Under 7.5",
                        "prices": {"25": {"price": -110, "is_main_line": True, "price_delta": 0}},
                    },
                ],
            }],
        }],
    }
    result = parse_k_props({"events": [event]})
    assert len(result) == 1
    assert result[0]["ref_book"] == "Book25"
```

- [ ] **Step 3: Run the updated test to verify it fails (ref_book key missing)**

```bash
py -3 -m pytest tests/test_fetch_odds.py::TestParseKProps::test_selects_ref_book_by_priority -v
```

Expected: FAIL — `ref_book` key not in result

### 4c: _select_ref_book() helper

- [ ] **Step 4: Write the failing test**

Add to `tests/test_fetch_odds.py`:

```python
from fetch_odds import _select_ref_book, REF_BOOK_PRIORITY

class TestSelectRefBook:
    def test_prefers_fanduel(self):
        """Returns FanDuel when available."""
        books = {
            "11": {"price": -110, "is_main": True, "delta": 0},
            "3":  {"price": -108, "is_main": True, "delta": 0},
        }
        book_id, name = _select_ref_book(books)
        assert book_id == "11"
        assert name == "FanDuel"

    def test_falls_back_to_betmgm(self):
        """Falls back to BetMGM when FanDuel unavailable."""
        books = {
            "6": {"price": -112, "is_main": True, "delta": 0},
            "3": {"price": -108, "is_main": True, "delta": 0},
        }
        book_id, name = _select_ref_book(books)
        assert book_id == "6"
        assert name == "BetMGM"

    def test_falls_back_to_draftkings(self):
        """Falls back to DraftKings when FanDuel and BetMGM unavailable."""
        books = {"3": {"price": -108, "is_main": True, "delta": 0}}
        book_id, name = _select_ref_book(books)
        assert book_id == "3"
        assert name == "DraftKings"

    def test_falls_back_to_any_book(self):
        """Falls back to first available book when none in priority list."""
        books = {"25": {"price": -110, "is_main": True, "delta": 0}}
        book_id, name = _select_ref_book(books)
        assert book_id == "25"
        assert name == "Book25"

    def test_returns_none_for_empty_books(self):
        """Returns (None, None) when no books available."""
        book_id, name = _select_ref_book({})
        assert book_id is None
        assert name is None
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
py -3 -m pytest tests/test_fetch_odds.py::TestSelectRefBook -v
```

Expected: FAIL — `_select_ref_book` not defined

- [ ] **Step 4: Implement _select_ref_book() in fetch_odds.py**

Add after the `BOOK_ID_MAP` / `REF_BOOK_PRIORITY` constants:

```python
def _select_ref_book(available_books: dict) -> tuple[str | None, str | None]:
    """
    Select reference book from available_books dict {book_id: price_info}.
    Priority: FanDuel → BetMGM → DraftKings → any available.
    Returns (book_id, human_name) or (None, None) if no books available.
    """
    for book_id in REF_BOOK_PRIORITY:
        if book_id in available_books:
            return book_id, BOOK_ID_MAP[book_id]
    # Fallback: any available book
    if available_books:
        book_id = next(iter(available_books))
        return book_id, BOOK_ID_MAP.get(book_id, f"Book{book_id}")
    return None, None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
py -3 -m pytest tests/test_fetch_odds.py::TestSelectRefBook -v
```

Expected: all 5 PASS

### 4c: Use ref book in _parse_event_k_props()

- [ ] **Step 6: Write the failing test for ref_book field in parse output**

Add to `tests/test_fetch_odds.py`:

```python
def test_parse_k_props_includes_ref_book():
    """Parsed props include ref_book field."""
    event = _make_event("Gerrit Cole", 6.5, -110, -110, is_main=True)
    # Override book ID to a known ref book (FanDuel = "11")
    event["markets"][0]["participants"][0]["lines"][0]["prices"] = {
        "11": {"price": -110, "price_delta": 0, "is_main_line": True}
    }
    event["markets"][0]["participants"][0]["lines"][1]["prices"] = {
        "11": {"price": -110, "price_delta": 0, "is_main_line": True}
    }
    from fetch_odds import parse_k_props
    results = parse_k_props({"events": [event]})
    assert len(results) == 1
    assert results[0]["ref_book"] == "FanDuel"
    assert results[0]["best_over_book"] == "FanDuel"
```

- [ ] **Step 7: Run test to verify it fails**

```bash
py -3 -m pytest tests/test_fetch_odds.py::test_parse_k_props_includes_ref_book -v
```

Expected: FAIL — `ref_book` key missing

- [ ] **Step 8: Update _parse_event_k_props() to use ref book**

In `pipeline/fetch_odds.py`, find the section after `chosen = lines_data[main_val]` (around line 131). Replace the "Best over" block through the end of `results.append(...)` with:

```python
            chosen = lines_data[main_val]

            # Select reference book (FanDuel → BetMGM → DraftKings → any)
            ref_book_id, ref_book_name = _select_ref_book(chosen["over"])
            if ref_book_id is None:
                continue
            if ref_book_id in chosen["under"]:
                ref_over  = chosen["over"][ref_book_id]
                ref_under = chosen["under"][ref_book_id]
            else:
                # Ref book has over but not under — use ref book for over, best available for under
                under_book_id, _ = _select_ref_book(chosen["under"])
                if under_book_id is None:
                    continue
                ref_over  = chosen["over"][ref_book_id]
                ref_under = chosen["under"][under_book_id]

            ref_over_price  = ref_over["price"]
            ref_under_price = ref_under["price"]
            over_delta      = ref_over["delta"]
            under_delta     = ref_under["delta"]

            if ref_over_price is None or ref_under_price is None:
                continue

            # Opening odds: current - delta = opening
            opening_over  = ref_over_price  - over_delta
            opening_under = ref_under_price - under_delta

            results.append({
                "pitcher":            pitcher_name,
                "team":               "",
                "opp_team":           "",
                "game_time":          game_time,
                "k_line":             main_val,
                "opening_line":       main_val,
                "ref_book":           ref_book_name,
                "best_over_book":     ref_book_name,
                "best_over_odds":     ref_over_price,
                "best_under_odds":    ref_under_price,
                "opening_over_odds":  opening_over,
                "opening_under_odds": opening_under,
            })
```

- [ ] **Step 9: Run all fetch_odds tests to verify they pass**

```bash
py -3 -m pytest tests/test_fetch_odds.py -v
```

Expected: all tests PASS (including existing ones)

- [ ] **Step 10: Commit**

```bash
git add pipeline/fetch_odds.py tests/test_fetch_odds.py
git commit -m "feat: select reference book (FanDuel→BetMGM→DraftKings→any) for consistent odds/grading"
```

---

## Task 5: Run full test suite + verify

- [ ] **Step 1: Run all 146+ tests**

```bash
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
py -3 -m pytest tests/ -v
```

Expected: all tests PASS (146 original + ~12 new = ~158 total)

- [ ] **Step 2: Verify picks_history.json is not gitignored**

```bash
git check-ignore -v data/picks_history.json
```

Expected: no output (file is NOT ignored)

- [ ] **Step 3: Confirm performance.json restores on next evening run**

The next evening pipeline run (cron `0 0 * * *` or `0 1 * * *`) will:
1. Load 119 historical picks from `picks_history.json` into a fresh DB
2. Seed today's picks
3. Close yesterday's results
4. Export the updated history back
5. Write `performance.json` with real pick counts again

To manually test locally (requires `RUNDOWN_API_KEY` set):

```bash
py -3 pipeline/run_pipeline.py 2026-04-03 --run-type evening
```

Then verify:
```bash
py -3 -c "import json; d=json.load(open('dashboard/data/performance.json')); print('total_picks:', d['total_picks'])"
```

Expected: `total_picks: 119+` (historical picks loaded)

- [ ] **Step 4: Final commit if any cleanup needed**

```bash
git add -A
git status  # verify only expected files changed
git commit -m "fix: restore performance tab via picks_history.json persistence"
```
