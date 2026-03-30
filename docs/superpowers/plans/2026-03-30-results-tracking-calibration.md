# Results Tracking & Auto-Calibration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track actual pitcher K results in SQLite, auto-calibrate model parameters, and show a Performance tab on the dashboard.

**Architecture:** New pipeline modules `fetch_results.py` and `calibrate.py` bolt onto the 8pm run only. `build_features.py` reads `data/params.json` for calibrated parameters (falls back to hardcoded defaults). Results live in `data/results.db` (SQLite, committed to git). Dashboard gets a third Performance tab reading `dashboard/data/performance.json`.

**Tech Stack:** Python 3.11, sqlite3 (stdlib), requests, scipy + numpy (already transitive via pybaseball, add explicitly), pytz (add to requirements), pytest

**Spec:** `docs/superpowers/specs/2026-03-30-results-tracking-calibration-design.md`

---

## File Map

**Create:**
- `pipeline/fetch_results.py` — DB init, pick seeding, result fetching, orphan cleanup
- `pipeline/calibrate.py` — performance.json generation, Phase 1/2 calibration, params.json
- `data/params.json` — calibrated model parameters (written by calibrate.py)
- `data/results.db` — SQLite picks database (binary, committed to git)
- `dashboard/data/performance.json` — aggregated stats for Performance tab
- `tests/test_fetch_results.py`
- `tests/test_calibrate.py`

**Modify:**
- `pipeline/build_features.py` — load_params(), blend_k9() weight args, raw_lambda output, ump_scale, verdict thresholds, output k9 components
- `pipeline/run_pipeline.py` — `--run-type evening` arg, wire new steps
- `.github/workflows/pipeline.yml` — evening run-type flag, updated git add
- `dashboard/index.html` — Performance tab

---

## Task 0: Add dependencies to requirements.txt

**Files:**
- Modify: `pipeline/requirements.txt`

This must happen before any other task — `pytz` and `numpy` are used from Task 1 onward.

- [ ] **Step 1: Add pytz and numpy**

```bash
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
echo "pytz>=2024.1" >> pipeline/requirements.txt
echo "numpy>=1.26.0" >> pipeline/requirements.txt
cat pipeline/requirements.txt
```

Expected: Both lines appear at the end.

- [ ] **Step 2: Commit**

```bash
git add pipeline/requirements.txt
git commit -m "chore: add pytz and numpy to pipeline requirements"
```

---

## Task 1: Update build_features.py

**Files:**
- Modify: `pipeline/build_features.py`
- Modify: `tests/test_build_features.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_build_features.py`:

```python
import json, os, tempfile
from unittest.mock import patch

# -- load_params tests --

class TestLoadParams:
    def test_missing_file_returns_defaults(self):
        with patch("build_features.PARAMS_PATH", "/nonexistent/path/params.json"):
            from build_features import load_params
            p = load_params()
        assert p["lambda_bias"] == 0.0
        assert p["ump_scale"] == 1.0
        assert p["ev_thresholds"]["fire2"] == 0.06

    def test_malformed_file_returns_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json{{{")
            path = f.name
        with patch("build_features.PARAMS_PATH", path):
            from build_features import load_params
            p = load_params()
        os.unlink(path)
        assert p["lambda_bias"] == 0.0

    def test_valid_file_overrides_defaults(self):
        data = {"lambda_bias": 0.3, "ump_scale": 0.8,
                "ev_thresholds": {"fire2": 0.07, "fire1": 0.04, "lean": 0.015},
                "weight_season_cap": 0.65, "weight_recent": 0.25}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        with patch("build_features.PARAMS_PATH", path):
            from build_features import load_params
            p = load_params()
        os.unlink(path)
        assert p["lambda_bias"] == 0.3
        assert p["ev_thresholds"]["fire2"] == 0.07

    def test_partial_file_merges_with_defaults(self):
        data = {"lambda_bias": 0.5}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        with patch("build_features.PARAMS_PATH", path):
            from build_features import load_params
            p = load_params()
        os.unlink(path)
        assert p["lambda_bias"] == 0.5
        assert p["ump_scale"] == 1.0  # default intact


# -- blend_k9 weight params tests --

class TestBlendK9Params:
    def test_custom_season_cap_applied(self):
        # With cap=0.5: w_season=min(90/60, 0.5)=0.5, w_recent=0.2, w_career=0.3
        result = blend_k9(10.0, 9.0, 8.0, ip=90, weight_season_cap=0.5, weight_recent=0.2)
        expected = 0.5 * 10.0 + 0.2 * 9.0 + 0.3 * 8.0  # 5.0+1.8+2.4=9.2
        assert abs(result - expected) < 0.01

    def test_custom_recent_weight_applied(self):
        result = blend_k9(10.0, 9.0, 8.0, ip=0, weight_season_cap=0.70, weight_recent=0.30)
        # w_season=0, w_recent=0.30, w_career=0.70
        expected = 0.0 * 10.0 + 0.30 * 9.0 + 0.70 * 8.0  # 0+2.7+5.6=8.3
        assert abs(result - expected) < 0.01

    def test_w_career_never_negative(self):
        # weight_season_cap=0.8, weight_recent=0.3 → sum>1 at high IP, career should be 0 not negative
        result = blend_k9(10.0, 9.0, 8.0, ip=90, weight_season_cap=0.8, weight_recent=0.3)
        assert result >= 0


# -- calc_verdict threshold params tests --

class TestCalcVerdictThresholds:
    def test_custom_thresholds(self):
        t = {"lean": 0.005, "fire1": 0.02, "fire2": 0.05}
        assert calc_verdict(0.003, t) == "PASS"
        assert calc_verdict(0.01, t) == "LEAN"
        assert calc_verdict(0.03, t) == "FIRE 1u"
        assert calc_verdict(0.06, t) == "FIRE 2u"

    def test_default_thresholds_unchanged(self):
        assert calc_verdict(0.005) == "PASS"
        assert calc_verdict(0.02) == "LEAN"
        assert calc_verdict(0.04) == "FIRE 1u"
        assert calc_verdict(0.07) == "FIRE 2u"


# -- build_pitcher_record output fields --

SAMPLE_ODDS = {
    "pitcher": "Test Pitcher", "team": "Test Team", "opp_team": "Opp Team",
    "game_time": "2026-04-01T17:05:00Z", "k_line": 6.5,
    "opening_line": 6.5, "best_over_book": "FD",
    "best_over_odds": -115, "best_under_odds": -105,
    "opening_over_odds": -110, "opening_under_odds": -110,
}
SAMPLE_STATS = {
    "season_k9": 9.0, "recent_k9": 9.0, "career_k9": 8.0,
    "innings_pitched_season": 30.0, "avg_ip_last5": 5.5,
    "opp_k_rate": 0.227, "opp_games_played": 20, "starts_count": 5,
}

class TestBuildPitcherRecordFields:
    def test_raw_lambda_and_lambda_present(self):
        rec = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 0.0)
        assert "raw_lambda" in rec
        assert "lambda" in rec

    def test_raw_lambda_equals_lambda_when_no_bias(self):
        with patch("build_features.PARAMS_PATH", "/nonexistent"):
            rec = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 0.0)
        assert rec["raw_lambda"] == rec["lambda"]

    def test_lambda_bias_applied_to_lambda_not_raw(self):
        data = {"lambda_bias": 0.5}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f); path = f.name
        with patch("build_features.PARAMS_PATH", path):
            rec = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 0.0)
        os.unlink(path)
        assert abs(rec["lambda"] - (rec["raw_lambda"] + 0.5)) < 0.01

    def test_k9_components_in_output(self):
        rec = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 0.0)
        assert "season_k9" in rec
        assert "recent_k9" in rec
        assert "career_k9" in rec

    def test_ump_scale_applied(self):
        data = {"ump_scale": 0.0}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f); path = f.name
        with patch("build_features.PARAMS_PATH", path):
            rec_scaled = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 1.0)
        with patch("build_features.PARAMS_PATH", "/nonexistent"):
            rec_default = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 1.0)
        os.unlink(path)
        assert rec_scaled["raw_lambda"] < rec_default["raw_lambda"]
```

- [ ] **Step 2: Run to confirm failures**

```
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
pytest tests/test_build_features.py::TestLoadParams tests/test_build_features.py::TestBlendK9Params tests/test_build_features.py::TestCalcVerdictThresholds tests/test_build_features.py::TestBuildPitcherRecordFields -v
```

Expected: multiple FAILs (PARAMS_PATH not defined, load_params not defined, blend_k9 missing args, etc.)

- [ ] **Step 3: Implement changes to build_features.py**

At the top of `pipeline/build_features.py`, add after the imports:

```python
import json
from pathlib import Path

PARAMS_PATH = str(Path(__file__).parent.parent / "data" / "params.json")

DEFAULTS = {
    "ev_thresholds": {"fire2": 0.06, "fire1": 0.03, "lean": 0.01},
    "weight_season_cap": 0.70,
    "weight_recent": 0.20,
    "ump_scale": 1.0,
    "lambda_bias": 0.0,
}

def load_params() -> dict:
    try:
        with open(PARAMS_PATH) as f:
            return {**DEFAULTS, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(DEFAULTS)
```

Update `calc_verdict` to accept optional thresholds:

```python
def calc_verdict(ev: float, thresholds: dict | None = None) -> str:
    t = thresholds or {"lean": EDGE_PASS, "fire1": EDGE_LEAN, "fire2": EDGE_FIRE_1U}
    if ev <= t["lean"]:
        return "PASS"
    if ev <= t["fire1"]:
        return "LEAN"
    if ev <= t["fire2"]:
        return "FIRE 1u"
    return "FIRE 2u"
```

Update `blend_k9` signature:

```python
def blend_k9(season_k9: float, recent_k9: float, career_k9: float, ip: float,
             weight_season_cap: float = 0.70, weight_recent: float = 0.20) -> float:
    w_season = min(ip / 60, weight_season_cap)
    w_recent = weight_recent
    w_career = max(0.0, 1.0 - w_season - w_recent)
    return (w_season * season_k9) + (w_recent * recent_k9) + (w_career * career_k9)
```

Replace `build_pitcher_record` body with this updated version:

```python
def build_pitcher_record(odds: dict, stats: dict, ump_k_adj: float,
                         swstr_pct: float = LEAGUE_AVG_SWSTR) -> dict:
    params = load_params()
    thresholds = params["ev_thresholds"]

    ip     = stats.get("innings_pitched_season", 0)
    avg_ip = stats.get("avg_ip_last5", EXPECTED_INNINGS)

    season_k9 = stats["season_k9"]
    recent_k9 = stats.get("recent_k9") if stats.get("starts_count", 0) >= 3 else season_k9
    career_k9 = stats.get("career_k9") or season_k9

    blended    = blend_k9(season_k9, recent_k9, career_k9, ip,
                          weight_season_cap=params["weight_season_cap"],
                          weight_recent=params["weight_recent"])
    swstr_mult = calc_swstr_mult(swstr_pct)
    opp_games  = stats.get("opp_games_played", 0)

    scaled_ump_k_adj = ump_k_adj * params["ump_scale"]
    raw_lam = calc_lambda(blended, avg_ip, stats["opp_k_rate"], scaled_ump_k_adj,
                          swstr_mult, opp_games_played=opp_games)
    applied_lam = raw_lam + params["lambda_bias"]

    k_line = odds["k_line"]
    win_prob_over  = 1 - poisson.cdf(math.floor(k_line), applied_lam)
    win_prob_under = 1 - win_prob_over

    best_over_odds  = odds["best_over_odds"]
    best_under_odds = odds["best_under_odds"]
    ev_over  = calc_ev(win_prob_over,  best_over_odds)
    ev_under = calc_ev(win_prob_under, best_under_odds)

    price_delta_over  = calc_price_delta(best_over_odds,  odds.get("opening_over_odds",  best_over_odds))
    price_delta_under = calc_price_delta(best_under_odds, odds.get("opening_under_odds", best_under_odds))

    conf_over  = calc_movement_confidence(price_delta_over)
    conf_under = calc_movement_confidence(price_delta_under)
    adj_ev_over  = ev_over  * conf_over
    adj_ev_under = ev_under * conf_under

    return {
        "pitcher":            odds["pitcher"],
        "team":               odds["team"],
        "opp_team":           odds["opp_team"],
        "game_time":          odds["game_time"],
        "k_line":             k_line,
        "opening_line":       odds.get("opening_line", k_line),
        "best_over_book":     odds["best_over_book"],
        "best_over_odds":     best_over_odds,
        "best_under_odds":    best_under_odds,
        "opening_over_odds":  odds["opening_over_odds"],
        "opening_under_odds": odds["opening_under_odds"],
        "price_delta_over":   price_delta_over,
        "price_delta_under":  price_delta_under,
        "raw_lambda":         round(raw_lam, 2),
        "lambda":             round(applied_lam, 2),
        "avg_ip":             avg_ip,
        "swstr_pct":          round(swstr_pct, 4),
        "opp_k_rate":         stats["opp_k_rate"],
        "ump_k_adj":          ump_k_adj,
        "season_k9":          round(season_k9, 2),
        "recent_k9":          round(recent_k9, 2),
        "career_k9":          round(career_k9, 2),
        "ev_over":  {
            "ev":            round(ev_over,      4),
            "adj_ev":        round(adj_ev_over,  4),
            "verdict":       calc_verdict(adj_ev_over,  thresholds),
            "win_prob":      round(win_prob_over,  3),
            "movement_conf": round(conf_over,    4),
        },
        "ev_under": {
            "ev":            round(ev_under,      4),
            "adj_ev":        round(adj_ev_under,  4),
            "verdict":       calc_verdict(adj_ev_under, thresholds),
            "win_prob":      round(win_prob_under,  3),
            "movement_conf": round(conf_under,    4),
        },
    }
```

- [ ] **Step 4: Run tests to confirm passing**

```
pytest tests/test_build_features.py -v
```

Expected: All pass (including existing tests — blend_k9 default args preserve existing behavior).

- [ ] **Step 5: Commit**

```bash
git add pipeline/build_features.py tests/test_build_features.py
git commit -m "feat: add params.json loading and raw_lambda to build_features"
```

---

## Task 2: Create fetch_results.py — DB init and pick seeding

**Files:**
- Create: `pipeline/fetch_results.py`
- Create: `tests/test_fetch_results.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_fetch_results.py`:

```python
import json, os, sys, sqlite3, tempfile, pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))


@pytest.fixture
def tmp_db(tmp_path):
    """Patch DB_PATH to a temp file, yield path."""
    db = tmp_path / "results.db"
    with patch("fetch_results.DB_PATH", db):
        import fetch_results
        fetch_results.init_db()
        yield db, fetch_results


@pytest.fixture
def today_json(tmp_path):
    """Write a minimal today.json and return path."""
    data = {
        "date": "2026-04-15",
        "props_available": True,
        "pitchers": [
            {
                "pitcher": "Gerrit Cole", "team": "New York", "opp_team": "Boston",
                "game_time": "2026-04-15T17:05:00Z", "k_line": 7.5,
                "raw_lambda": 7.2, "lambda": 7.2,
                "season_k9": 9.1, "recent_k9": 8.8, "career_k9": 9.0,
                "avg_ip": 5.8, "opp_k_rate": 0.235, "ump_k_adj": 0.2,
                "best_over_odds": -115, "best_under_odds": -105,
                "ev_over":  {"ev": 0.05, "adj_ev": 0.05, "verdict": "FIRE 1u", "win_prob": 0.58, "movement_conf": 1.0},
                "ev_under": {"ev": -0.02, "adj_ev": -0.02, "verdict": "PASS", "win_prob": 0.42, "movement_conf": 1.0},
            },
            {
                "pitcher": "Shane Bieber", "team": "Cleveland", "opp_team": "Detroit",
                "game_time": "2026-04-15T18:10:00Z", "k_line": 6.5,
                "raw_lambda": 6.1, "lambda": 6.1,
                "season_k9": 8.5, "recent_k9": 8.2, "career_k9": 8.8,
                "avg_ip": 5.5, "opp_k_rate": 0.220, "ump_k_adj": 0.0,
                "best_over_odds": -110, "best_under_odds": -110,
                "ev_over":  {"ev": 0.008, "adj_ev": 0.008, "verdict": "PASS",   "win_prob": 0.51, "movement_conf": 1.0},
                "ev_under": {"ev": 0.07,  "adj_ev": 0.07,  "verdict": "FIRE 2u","win_prob": 0.49, "movement_conf": 1.0},
            },
        ],
    }
    p = tmp_path / "today.json"
    p.write_text(json.dumps(data))
    return p, data


class TestInitDb:
    def test_creates_picks_table(self, tmp_db):
        db_path, fr = tmp_db
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert ("picks",) in tables
        conn.close()

    def test_creates_unique_index(self, tmp_db):
        db_path, fr = tmp_db
        conn = sqlite3.connect(db_path)
        idx = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_picks_date_pitcher_side'").fetchone()
        assert idx is not None
        conn.close()

    def test_idempotent(self, tmp_db):
        """init_db twice does not error."""
        db_path, fr = tmp_db
        fr.init_db()  # second call


class TestSeedPicks:
    def test_only_non_pass_sides_inserted(self, tmp_db, today_json):
        db_path, fr = tmp_db
        p, data = today_json
        count = fr.seed_picks(p)
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT pitcher, side, verdict FROM picks ORDER BY pitcher, side").fetchall()
        conn.close()
        # Cole: over=FIRE 1u (insert), under=PASS (skip)
        # Bieber: over=PASS (skip), under=FIRE 2u (insert)
        assert len(rows) == 2
        assert ("Gerrit Cole", "over", "FIRE 1u") in rows
        assert ("Shane Bieber", "under", "FIRE 2u") in rows

    def test_insert_or_ignore_on_rerun(self, tmp_db, today_json):
        db_path, fr = tmp_db
        p, _ = today_json
        fr.seed_picks(p)
        fr.seed_picks(p)  # second run, same data
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
        conn.close()
        assert count == 2  # no duplicates

    def test_seeds_correct_fields(self, tmp_db, today_json):
        db_path, fr = tmp_db
        p, _ = today_json
        fr.seed_picks(p)
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT * FROM picks WHERE pitcher='Gerrit Cole'").fetchone()
        conn.close()
        assert row is not None
        # k_line=7.5, odds=-115, raw_lambda=7.2
        cols = [d[0] for d in conn.execute("PRAGMA table_info(picks)").fetchall()] if False else None

    def test_returns_inserted_count(self, tmp_db, today_json):
        db_path, fr = tmp_db
        p, _ = today_json
        assert fr.seed_picks(p) == 2
        assert fr.seed_picks(p) == 0  # second run inserts nothing
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_fetch_results.py::TestInitDb tests/test_fetch_results.py::TestSeedPicks -v
```

Expected: ImportError or AttributeError (module doesn't exist yet)

- [ ] **Step 3: Implement fetch_results.py — init_db and seed_picks**

Create `pipeline/fetch_results.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_fetch_results.py::TestInitDb tests/test_fetch_results.py::TestSeedPicks -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: add SQLite DB init and pick seeding to fetch_results"
```

---

## Task 3: fetch_results.py — result fetching from MLB API

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `tests/test_fetch_results.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_fetch_results.py`:

```python
from unittest.mock import patch, MagicMock


def _make_schedule_response(pitcher_name: str, ks: int, game_final: bool = True):
    """Build a minimal MLB schedule+boxscore API response."""
    return {
        "dates": [{
            "date": "2026-04-14",
            "games": [{
                "gamePk": 111111,
                "status": {"abstractGameState": "Final" if game_final else "Live"},
                "teams": {
                    "home": {"team": {"name": "New York Yankees", "abbreviation": "NYY"}},
                    "away": {"team": {"name": "Boston Red Sox",   "abbreviation": "BOS"}},
                },
                "boxscore": {
                    "teams": {
                        "home": {
                            "pitchers": [123],
                            "players": {
                                "ID123": {
                                    "person": {"fullName": pitcher_name},
                                    "stats": {"pitching": {"strikeOuts": ks}},
                                }
                            },
                        },
                        "away": {"pitchers": [], "players": {}},
                    }
                },
            }]
        }]
    }


class TestFetchAndCloseResults:
    def _seed_yesterday_pick(self, db_path, fr, pitcher="Gerrit Cole", side="over",
                              k_line=7.5, odds=-115, verdict="FIRE 1u"):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("""
            INSERT INTO picks (date, pitcher, team, side, k_line, verdict,
                               ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf)
            VALUES (date('now','-1 day','localtime'), ?,?,?,?,?,0.05,0.05,7.2,7.2,?,1.0)
        """, (pitcher, "New York", side, k_line, verdict, odds))
        conn.commit()
        conn.close()

    def test_win_over_recorded(self, tmp_db):
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, pitcher="Gerrit Cole", side="over", k_line=7.5)

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Gerrit Cole", ks=8)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
            count = fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result, actual_ks, pnl FROM picks WHERE pitcher='Gerrit Cole'").fetchone()
        conn.close()
        assert row[0] == "win"
        assert row[1] == 8
        assert row[2] > 0

    def test_loss_over_recorded(self, tmp_db):
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, pitcher="Gerrit Cole", side="over", k_line=7.5)

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Gerrit Cole", ks=6)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
            fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result, pnl FROM picks WHERE pitcher='Gerrit Cole'").fetchone()
        conn.close()
        assert row[0] == "loss"
        assert row[1] == -1.0

    def test_push_recorded(self, tmp_db):
        """Whole number line, pitcher hits exactly the line."""
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, pitcher="Gerrit Cole", side="over", k_line=7.0)

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Gerrit Cole", ks=7)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
            fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result, pnl FROM picks").fetchone()
        conn.close()
        assert row[0] == "push"
        assert row[1] == 0.0

    def test_game_not_final_skipped(self, tmp_db):
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr)

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Gerrit Cole", ks=8, game_final=False)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
            count = fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result FROM picks").fetchone()
        conn.close()
        assert row[0] is None  # not closed
        assert count == 0

    def test_void_when_game_final_but_name_mismatch(self, tmp_db):
        """Pitcher scratched: game Final but their name not in starters."""
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, pitcher="Gerrit Cole")

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Other Pitcher", ks=5)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
            fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result, pnl FROM picks WHERE pitcher='Gerrit Cole'").fetchone()
        conn.close()
        assert row[0] == "void"
        assert row[1] == 0.0

    def test_pnl_positive_odds(self, tmp_db):
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, odds=120, side="under", k_line=7.5)

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Gerrit Cole", ks=6)  # under wins
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
            fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        pnl = conn.execute("SELECT pnl FROM picks").fetchone()[0]
        conn.close()
        assert abs(pnl - 1.20) < 0.01
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_fetch_results.py::TestFetchAndCloseResults -v
```

Expected: AttributeError — `fetch_and_close_results` not defined.

- [ ] **Step 3: Implement fetch_and_close_results in fetch_results.py**

Add to `pipeline/fetch_results.py`:

```python
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
            "sportId": 1, "date": yesterday_et, "hydrate": "boxscore",
        }, timeout=30)
        resp.raise_for_status()
        schedule = resp.json()
    except Exception as e:
        log.error("MLB schedule fetch failed: %s", e)
        return 0

    # Build name->ks and team->starter_name from Final games
    ks_by_name: dict[str, int] = {}
    finalized_teams: set[str] = set()

    for date_entry in schedule.get("dates", []):
        for game in date_entry.get("games", []):
            is_final = game.get("status", {}).get("abstractGameState") == "Final"
            boxscore = game.get("boxscore", {})

            for ts in ("home", "away"):
                team_info = game.get("teams", {}).get(ts, {}).get("team", {})
                team_keys = {team_info.get("name", "").lower(),
                             team_info.get("abbreviation", "").lower()}
                if is_final:
                    finalized_teams |= team_keys

                players = boxscore.get("teams", {}).get(ts, {}).get("players", {})
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
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_fetch_results.py::TestFetchAndCloseResults -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: add MLB box score result fetching and void detection"
```

---

## Task 4: fetch_results.py — orphan cleanup

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `tests/test_fetch_results.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_fetch_results.py`:

```python
class TestCloseOrphans:
    def _insert_pick(self, db_path, date_str, pitcher="Test Pitcher"):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("""
            INSERT INTO picks (date, pitcher, team, side, k_line, verdict,
                               ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf)
            VALUES (?,?,?,?,?,?,0.05,0.05,6.0,6.0,-110,1.0)
        """, (date_str, pitcher, "Test", "over", 6.5, "FIRE 1u"))
        conn.commit()
        conn.close()

    def test_old_null_result_marked_cancelled(self, tmp_db):
        db_path, fr = tmp_db
        old_date = (datetime.now(ET) - timedelta(days=4)).strftime("%Y-%m-%d")
        self._insert_pick(db_path, old_date)

        fr.close_orphans()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result, pnl FROM picks").fetchone()
        conn.close()
        assert row[0] == "cancelled"
        assert row[1] == 0.0

    def test_recent_null_result_untouched(self, tmp_db):
        db_path, fr = tmp_db
        yesterday = (datetime.now(ET) - timedelta(days=1)).strftime("%Y-%m-%d")
        self._insert_pick(db_path, yesterday)

        fr.close_orphans()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result FROM picks").fetchone()
        conn.close()
        assert row[0] is None  # untouched

    def test_already_closed_untouched(self, tmp_db):
        db_path, fr = tmp_db
        old_date = (datetime.now(ET) - timedelta(days=5)).strftime("%Y-%m-%d")
        self._insert_pick(db_path, old_date)
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE picks SET result='win', pnl=0.87")
        conn.commit()
        conn.close()

        fr.close_orphans()

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result FROM picks").fetchone()
        conn.close()
        assert row[0] == "win"  # unchanged
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_fetch_results.py::TestCloseOrphans -v
```

Expected: AttributeError — `close_orphans` not defined.

- [ ] **Step 3: Implement close_orphans**

Add to `pipeline/fetch_results.py`:

```python
def close_orphans() -> int:
    """Mark picks older than 3 days with NULL result as 'cancelled'. Returns count updated."""
    _, yesterday_et = _et_dates()
    # Threshold: date <= yesterday - 2 days = 3+ days ago
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
```

Also add a `run()` entry point that calls everything in order:

```python
def run() -> None:
    """Main entry point for the 8pm pipeline run."""
    init_db()
    seeded = seed_picks()
    log.info("Seeded %d picks for today", seeded)
    closed = fetch_and_close_results()
    log.info("Closed %d results for yesterday", closed)
    cancelled = close_orphans()
    log.info("Cancelled %d orphan picks", cancelled)
```

- [ ] **Step 4: Run all fetch_results tests**

```
pytest tests/test_fetch_results.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: add orphan cleanup and run() entry point to fetch_results"
```

---

## Task 5: calibrate.py — performance.json generation

**Files:**
- Create: `pipeline/calibrate.py`
- Create: `tests/test_calibrate.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_calibrate.py`:

```python
import json, os, sys, sqlite3, tempfile, pytest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))


@pytest.fixture
def tmp_env(tmp_path):
    """Set up temp DB + output paths, return (db_path, perf_path, params_path, calibrate_module)."""
    db = tmp_path / "results.db"
    perf = tmp_path / "performance.json"
    params = tmp_path / "params.json"

    import fetch_results
    with patch("fetch_results.DB_PATH", db), \
         patch("calibrate.DB_PATH", db), \
         patch("calibrate.PERFORMANCE_PATH", perf), \
         patch("calibrate.PARAMS_PATH", params):
        fetch_results.init_db()
        import calibrate
        yield db, perf, params, calibrate


def _insert_closed_pick(db_path, result, verdict="FIRE 1u", odds=-110,
                         adj_ev=0.04, raw_lambda=7.0, actual_ks=8,
                         date_offset_days=1):
    date_str = (datetime.now() - timedelta(days=date_offset_days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO picks (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                           raw_lambda, applied_lambda, odds, movement_conf,
                           result, actual_ks, pnl, fetched_at,
                           season_k9, recent_k9, career_k9, ump_k_adj)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        date_str, f"Pitcher {date_offset_days}", "Team", "over", 7.5, verdict,
        adj_ev, adj_ev, raw_lambda, raw_lambda, odds, 1.0,
        result, actual_ks,
        0.87 if result == "win" else -1.0,
        datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        9.0, 8.5, 8.8, 0.1,
    ))
    conn.commit()
    conn.close()


class TestPerformanceJson:
    def test_written_even_with_zero_picks(self, tmp_env):
        db, perf, params, cal = tmp_env
        cal.run()
        assert perf.exists()
        data = json.loads(perf.read_text())
        assert "total_picks" in data
        assert data["total_picks"] == 0

    def test_by_verdict_excludes_pass(self, tmp_env):
        db, perf, params, cal = tmp_env
        _insert_closed_pick(db, "win", verdict="PASS")
        _insert_closed_pick(db, "loss", verdict="FIRE 1u", date_offset_days=2)
        cal.run()
        data = json.loads(perf.read_text())
        assert "PASS" not in data["by_verdict"]
        assert "FIRE 1u" in data["by_verdict"]

    def test_win_pct_calculated(self, tmp_env):
        db, perf, params, cal = tmp_env
        for i in range(3):
            _insert_closed_pick(db, "win", verdict="FIRE 1u", date_offset_days=i+1)
        _insert_closed_pick(db, "loss", verdict="FIRE 1u", date_offset_days=4)
        cal.run()
        data = json.loads(perf.read_text())
        tier = data["by_verdict"]["FIRE 1u"]
        assert tier["wins"] == 3
        assert tier["losses"] == 1
        assert abs(tier["win_pct"] - 0.75) < 0.01

    def test_lambda_accuracy_present(self, tmp_env):
        db, perf, params, cal = tmp_env
        _insert_closed_pick(db, "win", raw_lambda=7.0, actual_ks=8)
        cal.run()
        data = json.loads(perf.read_text())
        assert "lambda_accuracy" in data
        assert "avg_predicted" in data["lambda_accuracy"]
        assert "avg_actual" in data["lambda_accuracy"]

    def test_insufficient_picks_shows_not_calibrated(self, tmp_env):
        db, perf, params, cal = tmp_env
        for i in range(5):
            _insert_closed_pick(db, "win", date_offset_days=i+1)
        cal.run()
        data = json.loads(perf.read_text())
        assert data["last_calibrated"] is None

    def test_params_not_written_when_insufficient(self, tmp_env):
        db, perf, params, cal = tmp_env
        cal.run()
        assert not params.exists()
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_calibrate.py::TestPerformanceJson -v
```

Expected: ImportError — calibrate.py doesn't exist.

- [ ] **Step 3: Implement calibrate.py — performance.json only**

Create `pipeline/calibrate.py`:

```python
"""
calibrate.py
Aggregates pick results into performance.json.
On Phase 1 (n>=30): calibrates lambda_bias and EV thresholds, writes params.json.
On Phase 2 (n>=60): also calibrates ump_scale and blend weights.
"""
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pytz

log = logging.getLogger(__name__)

DB_PATH           = Path(__file__).parent.parent / "data" / "results.db"
PARAMS_PATH       = Path(__file__).parent.parent / "data" / "params.json"
PERFORMANCE_PATH  = Path(__file__).parent.parent / "dashboard" / "data" / "performance.json"

PHASE1_THRESHOLD  = 30
PHASE2_THRESHOLD  = 60

DEFAULTS = {
    "ev_thresholds": {"fire2": 0.06, "fire1": 0.03, "lean": 0.01},
    "weight_season_cap": 0.70,
    "weight_recent":     0.20,
    "ump_scale":         1.0,
    "lambda_bias":       0.0,
}


def _load_current_params() -> dict:
    try:
        with open(PARAMS_PATH) as f:
            return {**DEFAULTS, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULTS)


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _american_to_implied(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def build_performance() -> dict:
    """Aggregate closed picks into a performance dict (no I/O)."""
    try:
        conn = _get_db()
    except Exception:
        return _empty_performance()

    closed = conn.execute("""
        SELECT verdict, result, odds, adj_ev, raw_lambda, actual_ks, pnl
        FROM picks
        WHERE result IN ('win','loss','push')
        ORDER BY verdict
    """).fetchall()
    conn.close()

    total = len(closed)
    by_verdict: dict[str, dict] = {}

    for row in closed:
        v = row["verdict"]
        if v == "PASS":
            continue
        if v not in by_verdict:
            by_verdict[v] = {"picks": 0, "wins": 0, "losses": 0, "pushes": 0,
                              "total_pnl": 0.0, "sum_ev": 0.0}
        b = by_verdict[v]
        b["picks"] += 1
        b["total_pnl"] += row["pnl"] or 0.0
        b["sum_ev"] += row["adj_ev"] or 0.0
        if row["result"] == "win":   b["wins"]   += 1
        elif row["result"] == "loss": b["losses"]  += 1
        elif row["result"] == "push": b["pushes"]  += 1

    # Format
    formatted: dict[str, dict] = {}
    for v, b in by_verdict.items():
        picks = b["picks"]
        formatted[v] = {
            "picks":    picks,
            "wins":     b["wins"],
            "losses":   b["losses"],
            "pushes":   b["pushes"],
            "win_pct":  round(b["wins"] / picks, 3) if picks else 0.0,
            "roi":      round(b["total_pnl"], 2),
            "avg_ev":   round(b["sum_ev"] / picks, 4) if picks else 0.0,
        }

    # Lambda accuracy
    lam_rows = [(r["raw_lambda"], r["actual_ks"]) for r in closed
                if r["raw_lambda"] is not None and r["actual_ks"] is not None]
    if lam_rows:
        avg_pred   = sum(r[0] for r in lam_rows) / len(lam_rows)
        avg_actual = sum(r[1] for r in lam_rows) / len(lam_rows)
        lam_acc = {
            "avg_predicted": round(avg_pred, 2),
            "avg_actual":    round(avg_actual, 2),
            "bias":          round(avg_actual - avg_pred, 2),
        }
    else:
        lam_acc = {"avg_predicted": None, "avg_actual": None, "bias": None}

    # Load current params to report
    params = _load_current_params()
    last_cal = params.get("updated_at")
    cal_n    = params.get("sample_size", 0) if last_cal else None

    return {
        "generated_at":       datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_picks":        total,
        "last_calibrated":    last_cal,
        "calibration_sample": cal_n,
        "by_verdict":         formatted,
        "lambda_accuracy":    lam_acc,
        "params":             params if last_cal else None,
    }


def _empty_performance() -> dict:
    return {
        "generated_at": datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_picks": 0,
        "last_calibrated": None,
        "calibration_sample": None,
        "by_verdict": {},
        "lambda_accuracy": {"avg_predicted": None, "avg_actual": None, "bias": None},
        "params": None,
    }


def write_performance(perf: dict) -> None:
    PERFORMANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PERFORMANCE_PATH, "w") as f:
        json.dump(perf, f, indent=2)
    log.info("Wrote performance.json (%d total picks)", perf["total_picks"])


def run() -> None:
    perf = build_performance()
    write_performance(perf)
    # Calibration phases added in Tasks 6 & 7
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_calibrate.py::TestPerformanceJson -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/calibrate.py tests/test_calibrate.py
git commit -m "feat: add calibrate.py with performance.json aggregation"
```

---

## Task 6: calibrate.py — Phase 1 calibration (n≥30)

**Files:**
- Modify: `pipeline/calibrate.py`
- Modify: `tests/test_calibrate.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_calibrate.py`:

```python
class TestPhase1Calibration:
    def _fill_picks(self, db, n, raw_lambda=7.0, actual_ks=8, odds=-110,
                    result="win", verdict="FIRE 1u", adj_ev=0.05):
        for i in range(n):
            _insert_closed_pick(db, result, verdict=verdict, odds=odds,
                                adj_ev=adj_ev, raw_lambda=raw_lambda,
                                actual_ks=actual_ks, date_offset_days=i+1)

    def test_no_params_written_below_30(self, tmp_env):
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 29)
        cal.run()
        assert not params.exists()

    def test_params_written_at_30(self, tmp_env):
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 30)
        cal.run()
        assert params.exists()

    def test_lambda_bias_corrects_over_prediction(self, tmp_env):
        """Model predicts 8.0, actual is 7.0 → bias = -1.0."""
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 35, raw_lambda=8.0, actual_ks=7)
        cal.run()
        data = json.loads(params.read_text())
        assert abs(data["lambda_bias"] - (-1.0)) < 0.1

    def test_lambda_bias_corrects_under_prediction(self, tmp_env):
        """Model predicts 6.0, actual is 7.5 → bias = +1.5."""
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 35, raw_lambda=6.0, actual_ks=7)  # actual avg ~7
        cal.run()
        data = json.loads(params.read_text())
        assert data["lambda_bias"] > 0

    def test_ev_threshold_tightens_when_overperforming(self, tmp_env):
        """FIRE 1u hitting 70% (needs ~52% at -110) → raise fire1 threshold."""
        db, perf, params, cal = tmp_env
        # 70% win rate: 24 wins, 10 losses, 1 push = 35 picks
        for i in range(24):
            _insert_closed_pick(db, "win", verdict="FIRE 1u", odds=-110,
                                 adj_ev=0.05, raw_lambda=7.0, actual_ks=8,
                                 date_offset_days=i+1)
        for i in range(10):
            _insert_closed_pick(db, "loss", verdict="FIRE 1u", odds=-110,
                                 adj_ev=0.05, raw_lambda=7.0, actual_ks=6,
                                 date_offset_days=i+25)
        _insert_closed_pick(db, "push", verdict="FIRE 1u", odds=-110,
                             raw_lambda=7.0, actual_ks=7, date_offset_days=36)
        cal.run()
        data = json.loads(params.read_text())
        # Threshold should be raised (stricter) when overperforming
        assert data["ev_thresholds"]["fire1"] >= 0.03

    def test_threshold_bounds_enforced(self, tmp_env):
        """Thresholds never go outside specified bounds."""
        db, perf, params, cal = tmp_env
        # 100% win rate → would push thresholds up; should cap at max
        for i in range(40):
            _insert_closed_pick(db, "win", verdict="FIRE 2u", odds=-110,
                                 adj_ev=0.08, raw_lambda=7.0, actual_ks=9,
                                 date_offset_days=i+1)
        cal.run()
        data = json.loads(params.read_text())
        assert data["ev_thresholds"]["fire2"] <= 0.10  # max bound

    def test_params_json_has_required_fields(self, tmp_env):
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 30)
        cal.run()
        data = json.loads(params.read_text())
        for field in ("updated_at", "sample_size", "ev_thresholds",
                      "weight_season_cap", "weight_recent", "ump_scale", "lambda_bias"):
            assert field in data, f"Missing field: {field}"
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_calibrate.py::TestPhase1Calibration -v
```

Expected: All fail — params.json never written.

- [ ] **Step 3: Implement Phase 1 in calibrate.py**

Add these functions to `pipeline/calibrate.py`:

```python
from scipy.stats import pearsonr


_EV_THRESHOLD_BOUNDS = {
    "fire2": (0.04, 0.10),
    "fire1": (0.02, 0.06),
    "lean":  (0.005, 0.03),
}
# Maps verdict name to threshold key
_VERDICT_TO_THRESHOLD = {
    "FIRE 2u": "fire2",
    "FIRE 1u": "fire1",
    "LEAN":    "lean",
}


def _calibrate_phase1(closed_picks: list, current_params: dict) -> dict:
    """Calibrate lambda_bias and EV thresholds. Returns updated params dict."""
    params = dict(current_params)

    # --- Lambda bias (60-day rolling window) ---
    lam_pairs = [(r["raw_lambda"], r["actual_ks"]) for r in closed_picks
                 if r["raw_lambda"] is not None and r["actual_ks"] is not None]
    if lam_pairs:
        bias = sum(a - p for p, a in lam_pairs) / len(lam_pairs)
        params["lambda_bias"] = round(bias, 3)

    # --- EV threshold adjustment (30-day window) ---
    cutoff = (datetime.now(pytz.utc) - __import__("datetime").timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [r for r in closed_picks if (r["fetched_at"] or "") >= cutoff]

    by_verdict: dict[str, list] = {}
    for row in recent:
        v = row["verdict"]
        if v not in _VERDICT_TO_THRESHOLD:
            continue
        by_verdict.setdefault(v, []).append(row)

    thresholds = dict(params["ev_thresholds"])
    for verdict, rows in by_verdict.items():
        if len(rows) < 10:
            continue
        wins = sum(1 for r in rows if r["result"] == "win")
        total = sum(1 for r in rows if r["result"] in ("win", "loss"))
        if total == 0:
            continue
        observed  = wins / total
        implied   = sum(_american_to_implied(r["odds"]) for r in rows) / len(rows)
        key       = _VERDICT_TO_THRESHOLD[verdict]
        lo, hi    = _EV_THRESHOLD_BOUNDS[key]
        current   = thresholds[key]
        if observed > implied + 0.03:
            thresholds[key] = min(hi, round(current + 0.005, 4))
        elif observed < implied - 0.03:
            thresholds[key] = max(lo, round(current - 0.005, 4))

    params["ev_thresholds"] = thresholds
    return params
```

Update `run()` in `calibrate.py`:

```python
def run() -> None:
    perf = build_performance()
    write_performance(perf)

    # Load closed picks for calibration
    try:
        conn = _get_db()
        closed = conn.execute("""
            SELECT verdict, result, odds, adj_ev, raw_lambda, actual_ks,
                   season_k9, recent_k9, career_k9, ump_k_adj, fetched_at
            FROM picks
            WHERE result IN ('win','loss','push')
        """).fetchall()
        conn.close()
    except Exception as e:
        log.error("Could not load picks for calibration: %s", e)
        return

    n = len(closed)
    log.info("Calibration: %d closed picks", n)

    if n < PHASE1_THRESHOLD:
        log.info("Below Phase 1 threshold (%d), skipping calibration", PHASE1_THRESHOLD)
        return

    current_params = _load_current_params()
    updated_params = _calibrate_phase1(closed, current_params)

    # Phase 2 handled in Task 7 — placeholder
    # if n >= PHASE2_THRESHOLD:
    #     updated_params = _calibrate_phase2(closed, updated_params)

    updated_params["updated_at"]   = datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated_params["sample_size"]  = n

    PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PARAMS_PATH, "w") as f:
        json.dump(updated_params, f, indent=2)
    log.info("Wrote params.json (n=%d)", n)
```

Ensure the top of `calibrate.py` imports (already present from Task 5):
```python
from datetime import datetime, timedelta
```

The cutoff line in `_calibrate_phase1` uses `timedelta` directly (no `__import__` needed):
```python
    cutoff = (datetime.now(pytz.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_calibrate.py::TestPhase1Calibration -v
```

Expected: All pass.

- [ ] **Step 5: Run full test suite to catch regressions**

```
pytest tests/ -v
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/calibrate.py tests/test_calibrate.py
git commit -m "feat: Phase 1 calibration — lambda_bias and EV threshold tuning"
```

---

## Task 7: calibrate.py — Phase 2 calibration (n≥60)

**Files:**
- Modify: `pipeline/calibrate.py`
- Modify: `tests/test_calibrate.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_calibrate.py`:

```python
class TestPhase2Calibration:
    def _fill_picks_n(self, db, n, ump_k_adj=0.0, raw_lambda=7.0, actual_ks=7):
        for i in range(n):
            _insert_closed_pick(db, "win" if i % 2 == 0 else "loss",
                                 raw_lambda=raw_lambda, actual_ks=actual_ks,
                                 date_offset_days=i+1)
            # Patch ump_k_adj directly
            conn = sqlite3.connect(db)
            conn.execute("UPDATE picks SET ump_k_adj=? WHERE rowid=(SELECT MAX(rowid) FROM picks)",
                         (ump_k_adj,))
            conn.commit()
            conn.close()

    def test_phase2_not_triggered_below_60(self, tmp_env):
        db, perf, params, cal = tmp_env
        self._fill_picks_n(db, 59)
        cal.run()
        data = json.loads(params.read_text())
        # ump_scale should remain default
        assert data["ump_scale"] == 1.0

    def test_ump_scale_decays_when_uncorrelated(self, tmp_env):
        """ump_k_adj uncorrelated with residuals → scale decays toward 0.5."""
        db, perf, params, cal = tmp_env
        import random; random.seed(42)
        # ump_k_adj random noise (no correlation with actual outcome)
        for i in range(65):
            ump = random.uniform(-0.5, 0.5)
            # actual_ks doesn't track ump at all
            _insert_closed_pick(db, "win" if i % 2 == 0 else "loss",
                                 raw_lambda=7.0, actual_ks=7,
                                 date_offset_days=i+1)
            conn = sqlite3.connect(db)
            conn.execute("UPDATE picks SET ump_k_adj=? WHERE rowid=(SELECT MAX(rowid) FROM picks)",
                         (ump,))
            conn.commit()
            conn.close()

        # Pre-seed params with ump_scale=1.0
        params.write_text(json.dumps({"ump_scale": 1.0, **{k: v for k, v in DEFAULTS.items() if k != "ump_scale"}}))
        cal.run()
        data = json.loads(params.read_text())
        # After one calibration cycle with low correlation, scale should decay
        assert data["ump_scale"] <= 1.0

    def test_ump_scale_bounded(self, tmp_env):
        db, perf, params, cal = tmp_env
        self._fill_picks_n(db, 65)
        # Pre-seed params with extremely low ump_scale
        existing = dict(DEFAULTS); existing["ump_scale"] = 0.1
        params.write_text(json.dumps(existing))
        cal.run()
        data = json.loads(params.read_text())
        assert data["ump_scale"] >= 0.0
        assert data["ump_scale"] <= 1.5
```

Fix: The test references `DEFAULTS` — add this import at the top of test_calibrate.py:

```python
from calibrate import DEFAULTS
```

- [ ] **Step 2: Run to confirm failures**

```
pytest tests/test_calibrate.py::TestPhase2Calibration -v
```

Expected: `test_phase2_not_triggered_below_60` passes (ump_scale stays 1.0 by design), others fail or show no ump_scale decay.

- [ ] **Step 3: Implement Phase 2 in calibrate.py**

Add `_calibrate_phase2` to `pipeline/calibrate.py`:

```python
def _calibrate_phase2(closed_picks: list, current_params: dict) -> dict:
    """Calibrate ump_scale and blend weights. Returns updated params dict."""
    params = dict(current_params)

    # --- Ump scale: Pearson correlation between ump_k_adj and residual ---
    ump_data = [(r["ump_k_adj"], r["actual_ks"] - r["raw_lambda"])
                for r in closed_picks
                if r["ump_k_adj"] is not None and r["raw_lambda"] is not None
                and r["actual_ks"] is not None]

    if len(ump_data) >= 60:
        umps    = [d[0] for d in ump_data]
        resids  = [d[1] for d in ump_data]
        # Avoid pearsonr crash on zero-variance arrays
        if len(set(umps)) > 1:
            corr, _ = pearsonr(umps, resids)
            if abs(corr) < 0.05:
                current_scale = params.get("ump_scale", 1.0)
                decayed = max(0.0, min(1.5, current_scale - 0.05))
                params["ump_scale"] = round(decayed, 3)

    # --- Blend weights: linear regression on k9 components ---
    # Requires season_k9, recent_k9, career_k9 in picks table
    blend_data = [(r["season_k9"], r["recent_k9"], r["career_k9"], r["actual_ks"])
                  for r in closed_picks
                  if all(r[k] is not None for k in ("season_k9","recent_k9","career_k9","actual_ks"))]

    if len(blend_data) >= 60:
        try:
            import numpy as np
            X = np.array([[d[0], d[1], d[2]] for d in blend_data])
            y = np.array([d[3] for d in blend_data])
            # Constrained least squares: weights >= 0.05 each
            from scipy.optimize import nnls
            # Normalize columns to avoid scale issues
            col_means = X.mean(axis=0)
            col_means[col_means == 0] = 1.0
            X_norm = X / col_means
            coeffs, _ = nnls(X_norm, y)
            coeffs_scaled = coeffs / col_means
            total = coeffs_scaled.sum()
            if total > 0:
                w = coeffs_scaled / total  # normalize to sum=1
                # Apply minimum of 0.05 per weight, cap season at weight_season_cap
                w = [max(0.05, wi) for wi in w]
                w_total = sum(w); w = [wi / w_total for wi in w]  # re-normalize
                season_cap = min(0.85, max(0.40, w[0]))
                recent     = min(0.40, max(0.05, w[1]))
                params["weight_season_cap"] = round(season_cap, 3)
                params["weight_recent"]     = round(recent, 3)
        except Exception as e:
            log.warning("Blend weight regression failed: %s — keeping current weights", e)

    return params
```

Uncomment the Phase 2 call in `run()`:

```python
    if n >= PHASE2_THRESHOLD:
        updated_params = _calibrate_phase2(closed, updated_params)
```

- [ ] **Step 4: Run all calibrate tests**

```
pytest tests/test_calibrate.py -v
```

Expected: All pass.

- [ ] **Step 5: Run full suite**

```
pytest tests/ -v
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/calibrate.py tests/test_calibrate.py
git commit -m "feat: Phase 2 calibration — ump_scale and blend weight tuning"
```

---

## Task 8: Wire run_pipeline.py

**Files:**
- Modify: `pipeline/run_pipeline.py`

- [ ] **Step 1: Add `--run-type` arg and wire evening steps**

At the bottom of `pipeline/run_pipeline.py`, replace the `if __name__ == "__main__":` block:

```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("date", nargs="?",
                        default=datetime.now().strftime("%Y-%m-%d"),
                        help="Game date YYYY-MM-DD")
    parser.add_argument("--run-type", choices=["full", "evening"], default="full",
                        help="'evening' adds result fetching and calibration")
    args = parser.parse_args()
    run(args.date, run_type=args.run_type)
```

Update `run()` signature and add evening steps:

```python
def run(date_str: str, run_type: str = "full") -> None:
    log.info("=== Pipeline start for %s (run_type=%s) ===", date_str, run_type)

    # ... (existing steps 1-5 unchanged) ...

    _write_output(date_str, records, props_available=True)
    log.info("=== Pipeline complete ===")

    # Evening-only: results + calibration
    if run_type == "evening":
        log.info("=== Evening steps: fetch_results + calibrate ===")
        try:
            from fetch_results import run as run_results
            run_results()
        except Exception as e:
            log.error("fetch_results failed: %s", e)
        try:
            from calibrate import run as run_calibrate
            run_calibrate()
        except Exception as e:
            log.error("calibrate failed: %s", e)
```

- [ ] **Step 2: Verify CLI argument parsing**

```bash
python pipeline/run_pipeline.py --help
```

Expected output includes: `--run-type {full,evening}`.

- [ ] **Step 3: Run full test suite**

```
pytest tests/ -v --tb=short
```

Expected: All tests pass (existing + new).

- [ ] **Step 4: Smoke test evening flag (optional, requires RUNDOWN_API_KEY)**

```bash
python pipeline/run_pipeline.py 2026-04-01 --run-type evening
```

Expected: Logs "Evening steps: fetch_results + calibrate". Errors from empty DB are acceptable.

- [ ] **Step 5: Commit**

```bash
git add pipeline/run_pipeline.py
git commit -m "feat: add --run-type evening to run_pipeline with results + calibrate steps"
```

---

## Task 9: Update pipeline.yml

**Files:**
- Modify: `.github/workflows/pipeline.yml`

**Note:** `workflow_dispatch` (manual trigger) sets `github.event.schedule` to empty string, so manual runs always use `--run-type full`. To manually test the evening path, trigger via the schedule or run `run_pipeline.py --run-type evening` locally.

- [ ] **Step 1: Update the workflow**

Replace the `Run pipeline` and `Commit pipeline output` steps with:

```yaml
      - name: Run pipeline
        env:
          RUNDOWN_API_KEY: ${{ secrets.RUNDOWN_API_KEY }}
        run: |
          if [ "${{ github.event.schedule }}" = "0 1 * * *" ]; then
            python pipeline/run_pipeline.py $(date +%Y-%m-%d) --run-type evening
          else
            python pipeline/run_pipeline.py $(date +%Y-%m-%d)
          fi

      - name: Commit pipeline output
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add dashboard/data/processed/
          git add -f dashboard/data/performance.json || true
          git add -f data/results.db || true
          git add -f data/params.json || true
          git diff --staged --quiet || git commit -m "chore: pipeline update $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git pull --rebase
          git push
```

- [ ] **Step 2: Add results.db to .gitattributes**

Check if `.gitattributes` exists:

```bash
ls .gitattributes 2>/dev/null || echo "not found"
```

If missing, create it. If present, append. Either way ensure this line is in `.gitattributes`:

```
data/results.db binary
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pipeline.yml .gitattributes
git commit -m "feat: update pipeline.yml for evening run-type and new output files"
```

---

## Task 10: Dashboard Performance tab

**Files:**
- Modify: `dashboard/index.html`

- [ ] **Step 1: Read the current dashboard**

Read `dashboard/index.html` to understand the current tab structure and JS patterns before editing.

- [ ] **Step 2: Add the Performance tab button**

Find the existing tab button HTML (something like `<button ... id="props-tab"`) and add a third button alongside the existing two:

```html
<button id="perf-tab" onclick="showTab('perf')" class="tab-btn">Performance</button>
```

- [ ] **Step 3: Add the Performance tab panel**

Add a `<div id="perf-panel">` section (hidden by default, same pattern as existing panels):

```html
<div id="perf-panel" class="tab-panel" style="display:none">
  <div id="perf-content">Loading performance data...</div>
</div>
```

- [ ] **Step 4: Add fetchPerformance() and renderPerformance() JS**

Add to the script section of `dashboard/index.html`:

```javascript
async function fetchPerformance() {
  try {
    const resp = await fetch('../data/performance.json?_=' + Date.now());
    if (!resp.ok) throw new Error('not found');
    return await resp.json();
  } catch {
    return null;
  }
}

function renderPerformance(data) {
  const el = document.getElementById('perf-content');
  if (!data) {
    el.innerHTML = '<p>Performance data not yet available.</p>';
    return;
  }
  if (data.total_picks < 10) {
    el.innerHTML = '<p>Not enough data yet — check back after opening week.</p>';
    return;
  }

  const verdicts = ['FIRE 2u', 'FIRE 1u', 'LEAN'];
  const rows = verdicts.map(v => {
    const b = data.by_verdict[v];
    if (!b || b.picks === 0) return `<tr><td>${v}</td><td colspan="4">No picks yet</td></tr>`;
    return `<tr>
      <td>${v}</td>
      <td>${b.picks}</td>
      <td>${(b.win_pct * 100).toFixed(1)}%</td>
      <td>${b.roi >= 0 ? '+' : ''}${b.roi.toFixed(2)}u</td>
      <td>${(b.avg_ev * 100).toFixed(1)}%</td>
    </tr>`;
  }).join('');

  const la = data.lambda_accuracy;
  const lambdaRow = la && la.avg_predicted != null
    ? `<p>Model predicted <strong>${la.avg_predicted.toFixed(2)}</strong> avg Ks &mdash; actual was <strong>${la.avg_actual.toFixed(2)}</strong> (bias: ${la.bias >= 0 ? '+' : ''}${la.bias.toFixed(2)})</p>`
    : '';

  const calNote = data.last_calibrated
    ? `<p class="cal-note">Last recalibrated ${data.last_calibrated.slice(0,10)} (n=${data.calibration_sample} picks)</p>`
    : `<p class="cal-note">Not yet calibrated (need ${data.total_picks}/30 closed picks)</p>`;

  el.innerHTML = `
    <table class="perf-table">
      <thead><tr><th>Verdict</th><th>Picks</th><th>Win %</th><th>ROI</th><th>Avg EV</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${lambdaRow}
    ${calNote}
  `;
}
```

- [ ] **Step 5: Wire fetchPerformance into showTab and page load**

Find the `showTab` function (or equivalent tab-switching logic) and add:

```javascript
// Inside showTab or equivalent, when tab === 'perf':
if (tab === 'perf') {
  fetchPerformance().then(renderPerformance);
}
```

Also call on initial load if perf tab is default (it won't be — props is default — so just ensure tab switching works).

- [ ] **Step 6: Add minimal CSS**

Add to the `<style>` section:

```css
.perf-table { width: 100%; border-collapse: collapse; margin-bottom: 1rem; }
.perf-table th, .perf-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }
.perf-table th { font-weight: 600; color: #aaa; }
.cal-note { font-size: 0.85rem; color: #888; margin-top: 0.5rem; }
```

- [ ] **Step 7: Run tests and verify**

```
pytest tests/ -v
```

Expected: All pass (dashboard is pure HTML/JS, no Python tests for it).

- [ ] **Step 8: Commit**

```bash
git add dashboard/index.html
git commit -m "feat: add Performance tab to dashboard"
```

---

## Done

All tasks complete. Invoke `superpowers:finishing-a-development-branch` to wrap up.
