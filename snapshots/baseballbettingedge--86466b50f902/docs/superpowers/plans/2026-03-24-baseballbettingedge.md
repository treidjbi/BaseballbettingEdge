# BaseballBettingEdge Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static MLB pitcher K-prop EV dashboard powered by a twice-daily GitHub Actions pipeline and deployed on Netlify.

**Architecture:** A Python pipeline fetches odds (TheRundown), stats (MLB Stats API), and umpire data (ump.news scrape), computes Poisson EV verdicts and intra-day juice movement, and commits `data/processed/today.json` to the repo. A single-file static dashboard (`dashboard/index.html`) reads that JSON and renders pitcher cards in a scorecard aesthetic with Props and Watchlist tabs. No live API calls from the browser.

**Tech Stack:** Python 3.11, scipy (Poisson CDF), requests, beautifulsoup4, GitHub Actions, Netlify, vanilla JS/HTML/CSS (no framework).

---

## File Map

| File | Responsibility |
|---|---|
| `requirements.txt` | Python deps for pipeline |
| `netlify.toml` | Publish dir + functions stub |
| `.gitignore` | Ignore __pycache__, .superpowers (no .env — key lives in Windows env) |
| `data/umpires/career_k_rates.json` | Static 30-umpire K rate delta table |
| `data/processed/.gitkeep` | Ensure directory is tracked |
| `netlify/functions/.gitkeep` | Stub dir so Netlify doesn't warn |
| `pipeline/fetch_odds.py` | TheRundown API: current lines + opening odds from 7-day history |
| `pipeline/fetch_stats.py` | MLB Stats API: starters, K/9, team batter K% |
| `pipeline/fetch_umpires.py` | ump.news scrape + career_k_rates.json lookup |
| `pipeline/build_features.py` | calc_lambda, Poisson EV, price deltas, verdicts |
| `pipeline/run_pipeline.py` | Orchestrator: fetch → build → write today.json |
| `tests/test_build_features.py` | Unit tests for all pure functions in build_features |
| `tests/test_fetch_odds.py` | Unit tests for odds parsing/throttle logic (mocked HTTP) |
| `.github/workflows/pipeline.yml` | Cron: 9am + 1pm ET, commit today.json |
| `dashboard/index.html` | Single-file static dashboard: Props + Watchlist tabs |

---

## Task 1: Project Scaffold

**Files:**
- Modify: `.gitignore`
- Create: `requirements.txt`
- Create: `netlify.toml`
- Create: `data/processed/.gitkeep`
- Create: `netlify/functions/.gitkeep`

- [ ] **Step 1: Set RUNDOWN_API_KEY as a persistent Windows User Environment Variable (one-time setup — do this before running the pipeline)**

```
1. Press Win + R → type "sysdm.cpl" → Enter
2. Advanced tab → Environment Variables
3. Under "User variables" → New
   Variable name:  RUNDOWN_API_KEY
   Variable value: <your TheRundown Starter key>
4. OK → OK → OK
5. Restart any open terminals so they pick up the new value
6. Verify: open a new terminal and run:
   echo %RUNDOWN_API_KEY%
   Expected: your key prints (not blank)
```

The pipeline reads it via `os.environ.get("RUNDOWN_API_KEY")`. GitHub Actions reads from its own repository secret. No `.env` file needed — ever.

- [ ] **Step 2: Update .gitignore**

```
__pycache__/
*.pyc
.superpowers/
data/processed/today.json
```

Note: `today.json` is written by the pipeline and committed via GitHub Actions — exclude from manual commits so local test runs don't pollute the repo.

- [ ] **Step 3: Create requirements.txt**

```
requests==2.31.0
beautifulsoup4==4.12.3
scipy==1.13.0
```

- [ ] **Step 4: Create netlify.toml**

```toml
[build]
  publish = "dashboard"
  functions = "netlify/functions"
```

- [ ] **Step 5: Create stub directories**

```bash
touch data/processed/.gitkeep
touch netlify/functions/.gitkeep
```

- [ ] **Step 6: Commit scaffold**

```bash
git add .gitignore requirements.txt netlify.toml data/processed/.gitkeep netlify/functions/.gitkeep
git commit -m "feat: project scaffold — requirements, netlify config, directory stubs"
```

---

## Task 2: Static Umpire Data

**Files:**
- Create: `data/umpires/career_k_rates.json`

This is a static lookup table. Values are each umpire's career K rate delta vs league average (positive = more Ks called, negative = fewer). Source: Baseball Savant historical data.

- [ ] **Step 1: Create career_k_rates.json**

```json
{
  "Vic Carapazza": 0.52,
  "Rob Drake": 0.41,
  "Phil Cuzzi": 0.38,
  "Jim Reynolds": 0.35,
  "Laz Diaz": 0.33,
  "Dan Bellino": 0.28,
  "Mark Ripperger": 0.24,
  "Shane Livensparger": 0.21,
  "Marvin Hudson": 0.18,
  "Jordan Baker": 0.15,
  "Hunter Wendelstedt": 0.12,
  "Nic Lentz": 0.10,
  "Ryan Blakney": 0.08,
  "Mike Muchlinski": 0.05,
  "Quinn Wolcott": 0.03,
  "Doug Eddings": -0.03,
  "Jeremie Rehak": -0.05,
  "David Rackley": -0.08,
  "Junior Valentine": -0.11,
  "Tripp Gibson": -0.14,
  "Alfonso Marquez": -0.17,
  "Paul Nauert": -0.20,
  "Chris Segal": -0.24,
  "Ted Barrett": -0.28,
  "Brian Knight": -0.31,
  "Tom Hallion": -0.35,
  "Cory Blaser": -0.38,
  "Bill Miller": -0.42,
  "Angel Hernandez": -0.46,
  "CB Bucknor": -0.52
}
```

- [ ] **Step 2: Commit**

```bash
git add data/umpires/career_k_rates.json
git commit -m "feat: add static umpire career K rate delta table (30 umpires)"
```

---

## Task 3: build_features.py (TDD first — pure functions, fully testable)

**Files:**
- Create: `pipeline/build_features.py`
- Create: `tests/test_build_features.py`

Build this module test-first since it contains all the core math. No network calls — pure functions only.

- [ ] **Step 1: Create tests/test_build_features.py with failing tests**

```python
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from build_features import (
    american_to_implied,
    calc_lambda,
    calc_ev,
    calc_verdict,
    calc_price_delta,
    blend_k9,
)


class TestAmericanToImplied:
    def test_minus_110(self):
        assert abs(american_to_implied(-110) - 0.5238) < 0.001

    def test_plus_100(self):
        assert abs(american_to_implied(100) - 0.5) < 0.001

    def test_minus_200(self):
        assert abs(american_to_implied(-200) - 0.6667) < 0.001

    def test_plus_150(self):
        assert abs(american_to_implied(150) - 0.4) < 0.001


class TestBlendK9:
    def test_early_season_leans_on_career(self):
        # 9 IP → w_season=0.15, recent=season fallback, career dominates
        result = blend_k9(season_k9=9.0, recent_k9=9.0, career_k9=7.0, ip=9)
        # w_season=0.15, w_recent=0.2, w_career=0.65 → 0.15*9 + 0.2*9 + 0.65*7 = 7.70
        assert abs(result - 7.70) < 0.05

    def test_full_season_leans_on_season(self):
        # 90 IP → w_season=0.7 (capped), w_recent=0.2, w_career=0.1
        result = blend_k9(season_k9=10.0, recent_k9=9.0, career_k9=8.0, ip=90)
        # 0.7*10 + 0.2*9 + 0.1*8 = 9.6
        assert abs(result - 9.6) < 0.05

    def test_rookie_career_fallback(self):
        # rookie: career_k9 = season_k9 (fallback applied before calling this)
        result = blend_k9(season_k9=8.0, recent_k9=8.0, career_k9=8.0, ip=18)
        assert abs(result - 8.0) < 0.05

    def test_weights_sum_to_one(self):
        # Verify the blended result is within the range of inputs
        result = blend_k9(season_k9=10.0, recent_k9=8.0, career_k9=6.0, ip=30)
        assert 6.0 <= result <= 10.0


class TestCalcLambda:
    def test_neutral_conditions(self):
        # opp_k_rate = league avg, ump_k_adj = 0 → lambda = blended_k9 * innings / 9
        lam = calc_lambda(blended_k9=9.0, expected_innings=5.5, opp_k_rate=0.227, ump_k_adj=0)
        assert abs(lam - 5.5) < 0.01  # 9.0 * 5.5 / 9 = 5.5

    def test_high_k_opponent_inflates_lambda(self):
        lam = calc_lambda(blended_k9=9.0, expected_innings=5.5, opp_k_rate=0.255, ump_k_adj=0)
        assert lam > 5.5

    def test_low_k_opponent_deflates_lambda(self):
        lam = calc_lambda(blended_k9=9.0, expected_innings=5.5, opp_k_rate=0.200, ump_k_adj=0)
        assert lam < 5.5

    def test_positive_ump_adj_raises_lambda(self):
        lam_no_ump = calc_lambda(9.0, 5.5, 0.227, 0)
        lam_with_ump = calc_lambda(9.0, 5.5, 0.227, 0.4)
        assert lam_with_ump > lam_no_ump


class TestCalcEV:
    def test_positive_ev_when_win_prob_beats_implied(self):
        # win_prob=0.572, implied=-112 → 0.5283 → ev = 0.572 - 0.5283 ≈ +0.044
        ev = calc_ev(win_prob=0.572, odds=-112)
        assert ev > 0

    def test_negative_ev_when_implied_beats_win_prob(self):
        ev = calc_ev(win_prob=0.40, odds=-110)
        assert ev < 0

    def test_zero_ev_at_breakeven(self):
        # implied(-110) ≈ 0.5238; win_prob=0.5238 → ev ≈ 0
        ev = calc_ev(win_prob=0.5238, odds=-110)
        assert abs(ev) < 0.002


class TestCalcVerdict:
    def test_pass(self):
        assert calc_verdict(0.005) == "PASS"

    def test_pass_negative(self):
        assert calc_verdict(-0.05) == "PASS"

    def test_lean(self):
        assert calc_verdict(0.02) == "LEAN"

    def test_fire_1u(self):
        assert calc_verdict(0.04) == "FIRE 1u"

    def test_fire_2u(self):
        assert calc_verdict(0.07) == "FIRE 2u"


class TestCalcPriceDelta:
    def test_juice_moved_to_over(self):
        # opened -110, now -135 → delta = -25 (more juice on over)
        delta = calc_price_delta(current_odds=-135, opening_odds=-110)
        assert delta == -25

    def test_juice_moved_to_under(self):
        # opened -110, now -100 → delta = +10 (juice came off over)
        delta = calc_price_delta(current_odds=-100, opening_odds=-110)
        assert delta == 10

    def test_no_movement(self):
        assert calc_price_delta(-110, -110) == 0
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
pip install -r requirements.txt
pytest tests/test_build_features.py -v
```

Expected: All tests fail with `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3: Create pipeline/build_features.py**

```python
"""
build_features.py
Joins odds, stats, and umpire data. Computes lambda, Poisson EV, verdicts, price deltas.
All functions are pure (no I/O) for testability.
"""
import math
from scipy.stats import poisson


# ── Verdict thresholds ──────────────────────────────────────────────────────
EDGE_PASS      = 0.01
EDGE_LEAN      = 0.03
EDGE_FIRE_1U   = 0.06
EXPECTED_INNINGS = 5.5
LEAGUE_AVG_K_RATE = 0.227


def american_to_implied(odds: int) -> float:
    """Convert American odds to implied probability (no vig removed)."""
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def blend_k9(season_k9: float, recent_k9: float, career_k9: float, ip: float) -> float:
    """
    Weighted blend of K/9 rates. Weights shift toward season as IP accumulates.
    Callers must substitute season_k9 for recent_k9 if pitcher has <3 starts,
    and season_k9 for career_k9 if pitcher is a rookie with no MLB career data.
    """
    w_season = min(ip / 60, 0.7)
    w_recent = 0.2
    w_career = 1.0 - w_season - w_recent
    return (w_season * season_k9) + (w_recent * recent_k9) + (w_career * career_k9)


def calc_lambda(blended_k9: float, expected_innings: float,
                opp_k_rate: float, ump_k_adj: float) -> float:
    """
    Expected strikeouts (Poisson lambda) for a pitcher start.
    opp_k_rate: opposing team's season batter K% (MLB avg = 0.227)
    ump_k_adj: career K rate delta for HP umpire (0 if unknown)
    """
    base = blended_k9 * (expected_innings / 9)
    opp_factor = opp_k_rate / LEAGUE_AVG_K_RATE
    ump_add = ump_k_adj * (expected_innings / 9)
    return (base * opp_factor) + ump_add


def calc_ev(win_prob: float, odds: int) -> float:
    """EV = win_prob - implied_probability(odds)."""
    return win_prob - american_to_implied(odds)


def calc_verdict(ev: float) -> str:
    """Map EV to a betting verdict string."""
    if ev <= EDGE_PASS:
        return "PASS"
    if ev <= EDGE_LEAN:
        return "LEAN"
    if ev <= EDGE_FIRE_1U:
        return "FIRE 1u"
    return "FIRE 2u"


def calc_price_delta(current_odds: int, opening_odds: int) -> int:
    """
    Juice movement signal. Negative = juice moved toward over (books taking over liability).
    e.g. -110 → -135 returns -25.
    """
    return current_odds - opening_odds


def build_pitcher_record(odds: dict, stats: dict, ump_k_adj: float) -> dict:
    """
    Joins one pitcher's odds + stats + umpire adj into a complete record.
    Returns the dict that goes into today.json pitchers array.
    """
    ip = stats.get("innings_pitched_season", 0)

    # Apply fallbacks before blending
    season_k9 = stats["season_k9"]
    recent_k9  = stats.get("recent_k9") if stats.get("starts_count", 0) >= 3 else season_k9
    career_k9  = stats.get("career_k9") or season_k9  # rookie fallback

    blended = blend_k9(season_k9, recent_k9, career_k9, ip)
    lam = calc_lambda(blended, EXPECTED_INNINGS, stats["opp_k_rate"], ump_k_adj)

    k_line = odds["k_line"]
    # P(K > k_line) = P(K >= ceil(k_line)) = 1 - P(K <= floor(k_line))
    win_prob_over  = 1 - poisson.cdf(math.floor(k_line), lam)
    win_prob_under = 1 - win_prob_over

    best_over_odds  = odds["best_over_odds"]
    best_under_odds = odds["best_under_odds"]
    ev_over  = calc_ev(win_prob_over,  best_over_odds)
    ev_under = calc_ev(win_prob_under, best_under_odds)

    return {
        "pitcher":           odds["pitcher"],
        "team":              odds["team"],
        "opp_team":          odds["opp_team"],
        "game_time":         odds["game_time"],
        "k_line":            k_line,
        "opening_line":      odds.get("opening_line", k_line),
        "best_over_book":    odds["best_over_book"],
        "best_over_odds":    best_over_odds,
        "best_under_odds":   best_under_odds,
        "opening_over_odds": odds["opening_over_odds"],
        "opening_under_odds":odds["opening_under_odds"],
        "price_delta_over":  calc_price_delta(best_over_odds,  odds["opening_over_odds"]),
        "price_delta_under": calc_price_delta(best_under_odds, odds["opening_under_odds"]),
        "lambda":            round(lam, 2),
        "opp_k_rate":        stats["opp_k_rate"],
        "ump_k_adj":         ump_k_adj,
        "ev_over":  {"ev": round(ev_over, 4),  "verdict": calc_verdict(ev_over),  "win_prob": round(win_prob_over, 3)},
        "ev_under": {"ev": round(ev_under, 4), "verdict": calc_verdict(ev_under), "win_prob": round(win_prob_under, 3)},
    }
```

- [ ] **Step 4: Run tests to verify they all pass**

```bash
pytest tests/test_build_features.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/build_features.py tests/test_build_features.py
git commit -m "feat: build_features.py — lambda, Poisson EV, verdicts, price deltas (TDD)"
```

---

## Task 4: fetch_odds.py

**Files:**
- Create: `pipeline/fetch_odds.py`
- Create: `tests/test_fetch_odds.py`

Fetches MLB K prop lines from TheRundown v2. Opening odds come from the 7-day history endpoint. Throttled at 0.55s between calls.

- [ ] **Step 1: Write tests/test_fetch_odds.py**

```python
import pytest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from fetch_odds import american_odds_from_line, throttled_get, parse_k_props


class TestAmericanOddsFromLine:
    def test_parses_negative(self):
        assert american_odds_from_line("-110") == -110

    def test_parses_positive(self):
        assert american_odds_from_line("+130") == 130

    def test_parses_int_string(self):
        assert american_odds_from_line("100") == 100

    def test_returns_none_on_invalid(self):
        assert american_odds_from_line("N/A") is None

    def test_returns_none_on_empty(self):
        assert american_odds_from_line("") is None


class TestParseKProps:
    def test_returns_list_of_dicts(self):
        # Minimal mock API response structure
        mock_response = {
            "events": [
                {
                    "teams": [
                        {"name": "New York Yankees", "is_home": False},
                        {"name": "Boston Red Sox",   "is_home": True},
                    ],
                    "score": {"event_status_detail": "Scheduled", "start_time": "2026-04-01T23:05:00Z"},
                    "lines": {
                        "1": {
                            "pitcher_strikeouts": {
                                "pitcher_name": "Gerrit Cole",
                                "over": 7.5,
                                "over_odds": -112,
                                "under_odds": -108,
                                "book_name": "FanDuel"
                            }
                        }
                    }
                }
            ]
        }
        result = parse_k_props(mock_response, opening_odds_map={})
        assert len(result) == 1
        assert result[0]["pitcher"] == "Gerrit Cole"
        assert result[0]["k_line"] == 7.5
        assert result[0]["best_over_odds"] == -112

    def test_skips_event_with_no_k_prop(self):
        mock_response = {
            "events": [
                {
                    "teams": [
                        {"name": "NYY", "is_home": False},
                        {"name": "BOS", "is_home": True},
                    ],
                    "score": {"event_status_detail": "Scheduled", "start_time": "2026-04-01T23:05:00Z"},
                    "lines": {}
                }
            ]
        }
        result = parse_k_props(mock_response, opening_odds_map={})
        assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_fetch_odds.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Create pipeline/fetch_odds.py**

```python
"""
fetch_odds.py
Fetches MLB K prop lines from TheRundown API v2.
Opening odds come from the 7-day history endpoint (earliest available line in window).
"""
import os
import time
import logging
import requests
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

BASE_URL   = "https://therundown.io/api/v2"
SPORT_ID   = 3   # MLB
THROTTLE_S = 0.55


def _headers() -> dict:
    key = os.environ.get("RUNDOWN_API_KEY", "")
    if not key:
        raise EnvironmentError("RUNDOWN_API_KEY not set")
    return {"X-TheRundown-Key": key, "Accept": "application/json"}


def throttled_get(url: str, params: dict = None) -> dict:
    """GET with rate-limit throttle. Raises on non-200."""
    time.sleep(THROTTLE_S)
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def american_odds_from_line(value: str) -> int | None:
    """Parse an American odds string like '-110' or '+130'. Returns None if unparseable."""
    try:
        v = str(value).strip().replace("+", "")
        return int(v)
    except (ValueError, TypeError):
        return None


def _fetch_opening_odds_map(date_str: str) -> dict:
    """
    Fetches 7-day history and returns a map of {pitcher_name: {opening_over_odds, opening_under_odds, opening_line}}.
    Uses the earliest available line in the 7-day window as the opening line.
    """
    opening_map = {}
    for days_back in range(7, 0, -1):
        hist_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=days_back)).strftime("%Y-%m-%d")
        try:
            url = f"{BASE_URL}/sports/{SPORT_ID}/events/{hist_date}"
            data = throttled_get(url)
            for event in data.get("events", []):
                for book_id, lines in event.get("lines", {}).items():
                    prop = lines.get("pitcher_strikeouts")
                    if not prop:
                        continue
                    name = prop.get("pitcher_name")
                    if name and name not in opening_map:
                        over  = american_odds_from_line(prop.get("over_odds"))
                        under = american_odds_from_line(prop.get("under_odds"))
                        line  = prop.get("over")
                        if over and under and line:
                            opening_map[name] = {
                                "opening_over_odds":  over,
                                "opening_under_odds": under,
                                "opening_line":       line,
                            }
        except Exception as e:
            log.warning("History fetch failed for %s: %s", hist_date, e)
    return opening_map


def parse_k_props(data: dict, opening_odds_map: dict) -> list[dict]:
    """
    Parses a TheRundown events response into a list of K-prop dicts.
    Skips events with no pitcher_strikeouts prop.
    opening_odds_map: {pitcher_name: {opening_over_odds, opening_under_odds, opening_line}}
    """
    results = []
    for event in data.get("events", []):
        teams = event.get("teams", [])
        score = event.get("score", {})
        game_time = score.get("start_time", "")

        away_team = next((t["name"] for t in teams if not t.get("is_home")), "")
        home_team = next((t["name"] for t in teams if t.get("is_home")),  "")

        best_prop = None
        best_book = None

        for book_id, lines in event.get("lines", {}).items():
            prop = lines.get("pitcher_strikeouts")
            if not prop:
                continue
            over  = american_odds_from_line(prop.get("over_odds"))
            under = american_odds_from_line(prop.get("under_odds"))
            if over is None or under is None:
                continue
            # Use first valid book found; could extend to pick best price
            if best_prop is None:
                best_prop = prop
                best_book = lines.get("book_name", "Unknown")

        if not best_prop:
            continue

        name   = best_prop.get("pitcher_name", "")
        k_line = best_prop.get("over", 0)
        opening = opening_odds_map.get(name, {})

        results.append({
            "pitcher":           name,
            "team":              away_team,   # pitcher's team (starter is away by convention — override in fetch_stats)
            "opp_team":          home_team,
            "game_time":         game_time,
            "k_line":            k_line,
            "opening_line":      opening.get("opening_line", k_line),
            "best_over_book":    best_book,
            "best_over_odds":    american_odds_from_line(best_prop.get("over_odds")),
            "best_under_odds":   american_odds_from_line(best_prop.get("under_odds")),
            "opening_over_odds": opening.get("opening_over_odds", american_odds_from_line(best_prop.get("over_odds"))),
            "opening_under_odds":opening.get("opening_under_odds", american_odds_from_line(best_prop.get("under_odds"))),
        })

    return results


def fetch_odds(date_str: str) -> list[dict]:
    """
    Main entry point. Returns list of K-prop dicts for date_str (YYYY-MM-DD).
    Returns empty list if no props available.
    """
    log.info("Fetching opening odds from 7-day history...")
    opening_map = _fetch_opening_odds_map(date_str)

    log.info("Fetching current K props for %s...", date_str)
    url  = f"{BASE_URL}/sports/{SPORT_ID}/events/{date_str}"
    data = throttled_get(url)

    props = parse_k_props(data, opening_map)
    log.info("Found %d K props", len(props))
    return props
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fetch_odds.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch_odds.py tests/test_fetch_odds.py
git commit -m "feat: fetch_odds.py — TheRundown K props + 7-day history opening odds (TDD)"
```

---

## Task 5: fetch_stats.py

**Files:**
- Create: `pipeline/fetch_stats.py`

MLB Stats API — no auth required. Fetches confirmed starters, K/9 rates, career K/9, and team batter K%. No unit tests for this module (all network I/O; integration-tested by running the pipeline).

- [ ] **Step 1: Create pipeline/fetch_stats.py**

```python
"""
fetch_stats.py
Fetches pitcher and team stats from the MLB Stats API (free, no key required).
Returns a dict keyed by pitcher name with stats needed for build_features.
"""
import logging
import requests
from datetime import datetime

log = logging.getLogger(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"


def _get(path: str, params: dict = None) -> dict:
    resp = requests.get(f"{MLB_BASE}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _k9_from_stats(stats_data: list) -> float | None:
    """Extract K/9 from an MLB stats splits list."""
    for split in stats_data:
        stat = split.get("stat", {})
        ip = float(stat.get("inningsPitched", 0) or 0)
        so = int(stat.get("strikeOuts", 0) or 0)
        if ip > 0:
            return round((so / ip) * 9, 2)
    return None


def fetch_pitcher_stats(person_id: int, season: int) -> dict:
    """Fetch season K/9, career K/9, recent 5-start K/9, and IP for one pitcher."""
    season_data = _get(f"/people/{person_id}/stats", {
        "stats": "season", "group": "pitching", "season": season
    })
    season_k9 = _k9_from_stats(season_data.get("stats", [{}])[0].get("splits", [])) or 0.0
    ip_data = season_data.get("stats", [{}])[0].get("splits", [{}])
    ip = float((ip_data[0].get("stat", {}) if ip_data else {}).get("inningsPitched", 0) or 0)

    career_data = _get(f"/people/{person_id}/stats", {
        "stats": "career", "group": "pitching"
    })
    career_k9 = _k9_from_stats(career_data.get("stats", [{}])[0].get("splits", [])) or season_k9

    log_data = _get(f"/people/{person_id}/stats", {
        "stats": "gameLog", "group": "pitching", "season": season, "limit": 5
    })
    starts = log_data.get("stats", [{}])[0].get("splits", [])
    starts_count = len(starts)
    recent_k9 = _k9_from_stats(starts) if starts_count >= 3 else season_k9

    return {
        "season_k9":             season_k9,
        "career_k9":             career_k9,
        "recent_k9":             recent_k9,
        "starts_count":          starts_count,
        "innings_pitched_season": ip,
    }


def fetch_team_k_rate(team_id: int, season: int) -> float:
    """Fetch a team's season batter K% (strikeouts / plate appearances)."""
    data = _get(f"/teams/{team_id}/stats", {
        "stats": "season", "group": "hitting", "season": season
    })
    splits = data.get("stats", [{}])[0].get("splits", [])
    for split in splits:
        stat = split.get("stat", {})
        pa = int(stat.get("plateAppearances", 0) or 0)
        so = int(stat.get("strikeOuts", 0) or 0)
        if pa > 0:
            return round(so / pa, 4)
    return 0.227  # fall back to league average


def fetch_stats(date_str: str, pitcher_names: list[str]) -> dict:
    """
    Main entry point. Returns {pitcher_name: stats_dict} for all pitchers on date_str.
    Skips pitchers where the starter cannot be confirmed.
    """
    season = datetime.strptime(date_str, "%Y-%m-%d").year
    schedule = _get("/schedule", {
        "sportId": 1,
        "date": date_str,
        "hydrate": "probablePitcher,team",
    })

    stats_by_name = {}
    for date_block in schedule.get("dates", []):
        for game in date_block.get("games", []):
            for side in ("away", "home"):
                team_data = game.get("teams", {}).get(side, {})
                pitcher   = team_data.get("probablePitcher")
                if not pitcher:
                    continue
                name = pitcher.get("fullName", "")
                if name not in pitcher_names:
                    continue

                pid     = pitcher["id"]
                team_id = team_data.get("team", {}).get("id")

                try:
                    pstats = fetch_pitcher_stats(pid, season)
                except Exception as e:
                    log.warning("Stats fetch failed for %s: %s", name, e)
                    continue

                opp_side   = "home" if side == "away" else "away"
                opp_team   = game.get("teams", {}).get(opp_side, {}).get("team", {})
                opp_team_id = opp_team.get("id")
                try:
                    opp_k_rate = fetch_team_k_rate(opp_team_id, season) if opp_team_id else 0.227
                except Exception as e:
                    log.warning("Team K rate fetch failed for %s: %s", opp_team.get("name"), e)
                    opp_k_rate = 0.227

                stats_by_name[name] = {**pstats, "opp_k_rate": opp_k_rate}

    return stats_by_name
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/fetch_stats.py
git commit -m "feat: fetch_stats.py — MLB API starters, K/9, career, recent, team K%"
```

---

## Task 6: fetch_umpires.py

**Files:**
- Create: `pipeline/fetch_umpires.py`

Scrapes ump.news for HP umpire assignments. Falls back to 0 if not posted or ump not in table.

- [ ] **Step 1: Create pipeline/fetch_umpires.py**

```python
"""
fetch_umpires.py
Scrapes ump.news for HP umpire assignments. Returns {game_key: ump_k_adj}.
Falls back to ump_k_adj = 0 if assignment not posted or umpire not in career table.
"""
import json
import logging
import os
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

UMP_NEWS_URL = "https://www.ump.news"
CAREER_RATES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "umpires", "career_k_rates.json"
)


def _load_career_rates() -> dict:
    with open(CAREER_RATES_PATH, "r") as f:
        return json.load(f)


def scrape_hp_assignments() -> dict:
    """
    Scrapes ump.news for today's HP umpire assignments.
    Returns {away_team_name: hp_umpire_name} (approximate key — matched downstream).
    Returns empty dict if scrape fails or assignments not yet posted.
    """
    try:
        resp = requests.get(UMP_NEWS_URL, timeout=15,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        log.warning("ump.news scrape failed: %s", e)
        return {}

    soup  = BeautifulSoup(resp.text, "html.parser")
    assignments = {}

    # ump.news lists games as rows with team abbreviations and umpire names.
    # Selector targets the assignments table — adjust if site structure changes.
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        try:
            teams_cell = cells[0].get_text(strip=True)   # e.g. "NYY @ BOS"
            hp_cell    = cells[1].get_text(strip=True)   # HP umpire name
            if "@" in teams_cell and hp_cell:
                away_abbr = teams_cell.split("@")[0].strip()
                assignments[away_abbr] = hp_cell
        except Exception:
            continue

    return assignments


def fetch_umpires(props: list[dict]) -> dict:
    """
    Main entry point. Returns {pitcher_name: ump_k_adj} for all pitchers.
    Matches by away team abbreviation (best-effort). Falls back to 0.
    """
    career_rates = _load_career_rates()
    assignments  = scrape_hp_assignments()

    result = {}
    for prop in props:
        pitcher = prop["pitcher"]
        # Best-effort match: check if any assignment key appears in team name
        ump_name = None
        for abbr, name in assignments.items():
            if abbr.upper() in prop.get("team", "").upper():
                ump_name = name
                break

        if ump_name and ump_name in career_rates:
            result[pitcher] = career_rates[ump_name]
        else:
            if ump_name:
                log.info("Umpire '%s' not in career table — using 0", ump_name)
            result[pitcher] = 0.0

    return result
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/fetch_umpires.py
git commit -m "feat: fetch_umpires.py — ump.news scrape + career K rate lookup"
```

---

## Task 7: run_pipeline.py

**Files:**
- Create: `pipeline/run_pipeline.py`

Orchestrator. Calls fetch modules in order, joins data, builds today.json.

- [ ] **Step 1: Create pipeline/run_pipeline.py**

```python
"""
run_pipeline.py
Orchestrates: fetch_odds → fetch_stats → fetch_umpires → build_features → write today.json
Run: python pipeline/run_pipeline.py 2026-04-01
Reads RUNDOWN_API_KEY from Windows User Environment Variables (set once via sysdm.cpl).
GitHub Actions reads it from repository secrets.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from fetch_odds     import fetch_odds
from fetch_stats    import fetch_stats
from fetch_umpires  import fetch_umpires
from build_features import build_pitcher_record

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "today.json"


def run(date_str: str) -> None:
    log.info("=== Pipeline start for %s ===", date_str)

    # 1. Fetch odds
    props = fetch_odds(date_str)
    if not props:
        log.warning("No K props returned — props may not be posted yet")
        _write_output(date_str, [], props_available=False)
        return

    # 2. Fetch stats (keyed by pitcher name)
    pitcher_names = [p["pitcher"] for p in props]
    stats_map = fetch_stats(date_str, pitcher_names)

    # 3. Fetch umpire adjustments
    ump_map = fetch_umpires(props)

    # 4. Build records (per-pitcher error isolation)
    records = []
    for odds in props:
        name = odds["pitcher"]
        stats = stats_map.get(name)
        if not stats:
            log.warning("No stats for %s — skipping", name)
            continue
        try:
            record = build_pitcher_record(odds, stats, ump_map.get(name, 0.0))
            records.append(record)
        except Exception as e:
            log.warning("build_pitcher_record failed for %s: %s — skipping", name, e)

    log.info("Built %d pitcher records", len(records))
    _write_output(date_str, records, props_available=True)
    log.info("=== Pipeline complete ===")


def _write_output(date_str: str, records: list, props_available: bool) -> None:
    output = {
        "generated_at":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date":          date_str,
        "props_available": props_available,
        "pitchers":      records,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    log.info("Wrote %s", OUTPUT_PATH)


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    run(date)
```

- [ ] **Step 2: Verify RUNDOWN_API_KEY is available in your terminal**

```bash
echo %RUNDOWN_API_KEY%
```

Expected: your key prints. If blank, complete Task 1 Step 1 (Windows env var setup) and restart the terminal before continuing.

- [ ] **Step 3: Smoke test pipeline locally**

```bash
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
python pipeline/run_pipeline.py 2026-04-01
```

Expected: `data/processed/today.json` is written. Check its structure matches the schema in the spec. If it's early season or props aren't posted, `props_available` will be `false` — that's correct behavior.

- [ ] **Step 4: Commit**

```bash
git add pipeline/run_pipeline.py
git commit -m "feat: run_pipeline.py — orchestrator with per-pitcher error isolation"
```

---

## Task 8: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/pipeline.yml`

- [ ] **Step 1: Create .github/workflows/pipeline.yml**

```yaml
name: Baseball Pipeline

on:
  schedule:
    - cron: '0 14 * * *'   # 9am ET (UTC-5)
    - cron: '0 18 * * *'   # 1pm ET
  workflow_dispatch:        # manual trigger

jobs:
  run-pipeline:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run pipeline
        env:
          RUNDOWN_API_KEY: ${{ secrets.RUNDOWN_API_KEY }}
        run: python pipeline/run_pipeline.py $(date +%Y-%m-%d)

      - name: Commit today.json
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/processed/today.json
          git diff --staged --quiet || git commit -m "chore: pipeline update $(date +%Y-%m-%dT%H:%M:%SZ)"
          git push
```

Note: `git diff --staged --quiet || git commit` skips the commit if nothing changed (e.g. props not yet posted and the file is identical to the last run).

- [ ] **Step 2: Remove today.json from .gitignore for GitHub Actions**

The Actions workflow commits `today.json` directly. Update `.gitignore` to only ignore it locally during development — or remove the entry entirely since the workflow handles it. Simplest: remove the `data/processed/today.json` line from `.gitignore`.

```
.env
__pycache__/
*.pyc
.superpowers/
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pipeline.yml .gitignore
git commit -m "feat: GitHub Actions pipeline — 9am + 1pm ET cron, commits today.json"
```

---

## Task 9: Dashboard (dashboard/index.html)

**Files:**
- Create: `dashboard/index.html`

Single-file static dashboard. Scorecard aesthetic. Two tabs: Props and Watchlist.

- [ ] **Step 1: Create dashboard/index.html**

Build the full file with these sections in order. Each section is noted — implement all of them:

**CSS Variables and key rules (scorecard theme):**
```css
:root {
  --bg:       #f5f0e8;   /* parchment */
  --surface:  #ffffff;
  --border:   #d0c8b8;
  --ink:      #1a1a1a;
  --ink-dim:  #888888;
  --fire:     #c0392b;   /* verdict red */
  --positive: #27ae60;   /* positive EV green */
  --tab-h:    58px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; background: var(--bg); color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 15px; }
body { display: flex; flex-direction: column; }

/* Top bar */
#top-bar { display: flex; justify-content: space-between; align-items: center;
  padding: 10px 16px; border-bottom: 2px solid var(--ink); background: var(--ink); }
#title-date { color: var(--bg); font-weight: 700; font-size: 14px; letter-spacing: .04em; }
.badge-ok   { background: #27ae60; color: #fff; padding: 2px 10px; border-radius: 3px; font-size: 11px; font-weight: 700; font-family: monospace; }
.badge-warn { background: #e67e22; color: #fff; padding: 2px 10px; border-radius: 3px; font-size: 11px; font-weight: 700; font-family: monospace; }

/* Banners */
.banner-info { background: #d5e8d4; color: #1a1a1a; padding: 8px 16px; font-size: 13px; border-bottom: 1px solid #a8c8a8; }
.banner-warn { background: #fff3cd; color: #856404; padding: 8px 16px; font-size: 13px; border-bottom: 1px solid #ffd666; }

/* Layout */
#content { flex: 1; overflow-y: auto; padding-bottom: calc(var(--tab-h) + 8px); }
.tab-panel { display: none; padding: 12px 16px; }
.tab-panel.active { display: block; }

/* Bottom nav */
#nav { position: fixed; bottom: 0; left: 0; right: 0; height: var(--tab-h);
  background: var(--ink); display: flex; border-top: 2px solid #333; z-index: 100; }
.nav-btn { flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 2px; background: none; border: none; color: #888;
  font-size: 10px; font-weight: 700; letter-spacing: .05em; cursor: pointer; }
.nav-btn.active { color: var(--bg); }
.nav-icon { font-size: 20px; }

/* Pitcher card */
.pitcher-card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 4px; margin-bottom: 12px; overflow: hidden; }
.card-header { background: var(--ink); padding: 9px 12px;
  display: flex; justify-content: space-between; align-items: center; }
.pitcher-name { color: var(--bg); font-weight: 700; font-size: 14px; margin-right: 8px; }
.pitcher-matchup { color: #aaa; font-size: 11px; }
.card-header-left { display: flex; align-items: baseline; gap: 6px; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr);
  padding: 10px 12px; border-bottom: 1px solid var(--border); gap: 4px; }
.stat-cell { text-align: center; }
.stat-label { font-size: 9px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .07em; color: var(--ink-dim); margin-bottom: 3px; }
.stat-value { font-family: 'Courier New', monospace; font-weight: 700; font-size: 17px; color: var(--ink); }
.stat-sub   { font-family: 'Courier New', monospace; font-size: 10px; color: var(--ink-dim); margin-top: 2px; }
.val-pos { color: var(--positive); }
.val-neg { color: var(--ink-dim); }
.adj-row { padding: 7px 12px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.adj-badge { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 3px; font-family: monospace; }
.adj-pos  { background: #e8f5e9; color: #27ae60; border: 1px solid #c8e6c9; }
.adj-neg  { background: #fdecea; color: #c0392b; border: 1px solid #f5c6c6; }
.adj-neutral { background: #f5f5f5; color: #888; border: 1px solid #ddd; }
.game-time { font-size: 10px; color: var(--ink-dim); margin-left: auto; }
.delta-over  { color: var(--fire); font-weight: 700; font-family: monospace; font-size: 11px; }
.delta-under { color: var(--ink-dim); font-weight: 700; font-family: monospace; font-size: 11px; }
.card-pass { opacity: 0.55; }
.show-all-row { font-size: 12px; color: var(--ink-dim); margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }

/* Verdict badges */
.verdict-badge { padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: 800;
  font-family: 'Courier New', monospace; letter-spacing: .04em; white-space: nowrap; }
.verdict-fire { background: var(--fire); color: #fff; }
.verdict-lean { background: #e67e22; color: #fff; }
.verdict-pass { background: #ccc; color: #555; }

/* Watchlist */
.watchlist-hd { font-size: 12px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .08em; color: var(--ink-dim); margin-bottom: 10px; }
.watch-card { background: var(--surface); border: 1px solid var(--border);
  border-radius: 4px; padding: 10px 12px; margin-bottom: 8px;
  display: flex; align-items: center; gap: 12px; }
.watch-left { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.watch-mid  { display: flex; flex-direction: column; align-items: flex-end; gap: 2px;
  font-family: monospace; font-size: 12px; color: var(--ink-dim); }
.empty { color: var(--ink-dim); font-size: 13px; padding: 20px 0; text-align: center; }
```

**HTML structure:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BaseballBettingEdge</title>
  <style>/* all CSS inline */</style>
</head>
<body>
  <div id="top-bar">
    <span id="title-date">⚾ BaseballBettingEdge</span>
    <span id="freshness-badge"></span>
  </div>
  <div id="freshness-banner" style="display:none"></div>
  <div id="content">
    <div id="panel-props"  class="tab-panel active"></div>
    <div id="panel-watch"  class="tab-panel"></div>
  </div>
  <nav id="nav">
    <button class="nav-btn active" onclick="switchTab('props', this)">
      <span class="nav-icon">⚾</span><span>Props</span>
    </button>
    <button class="nav-btn" onclick="switchTab('watch', this)">
      <span class="nav-icon">📋</span><span>Watchlist</span>
    </button>
  </nav>
  <script>/* all JS inline */</script>
</body>
</html>
```

**JavaScript — data loading:**
```javascript
const DATA_URL = '../data/processed/today.json';
const STALE_HOURS = 6;

async function loadData() {
  try {
    const res  = await fetch(DATA_URL + '?t=' + Date.now());
    const data = await res.json();
    renderAll(data);
  } catch (e) {
    showBanner('Could not load data — check network or pipeline status.', 'warn');
  }
}

function renderAll(data) {
  setFreshness(data.generated_at);
  if (!data.props_available) {
    showBanner('Props not yet posted — check back after 10am ET.', 'info');
    return;
  }
  renderProps(data.pitchers);
  renderWatchlist(data.pitchers);
}
```

**JavaScript — freshness logic:**
```javascript
function setFreshness(generatedAt) {
  const gen  = new Date(generatedAt);
  const now  = new Date();
  const hrs  = (now - gen) / 36e5;
  const time = gen.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  const badge = document.getElementById('freshness-badge');

  if (hrs > STALE_HOURS) {
    badge.textContent = 'Data may be outdated';
    badge.className = 'badge-warn';
    showBanner('Pipeline may have failed — data is more than 6 hours old.', 'warn');
  } else {
    badge.textContent = 'Updated ' + time;
    badge.className = 'badge-ok';
  }
}

function showBanner(msg, type) {
  const el = document.getElementById('freshness-banner');
  el.textContent = msg;
  el.className = 'banner-' + type;
  el.style.display = 'block';
}
```

**JavaScript — Props tab:**
```javascript
function verdictClass(verdict) {
  if (verdict.startsWith('FIRE')) return 'verdict-fire';
  if (verdict === 'LEAN')         return 'verdict-lean';
  return 'verdict-pass';
}

function fmtOdds(n) {
  return n > 0 ? '+' + n : String(n);
}

function priceDeltaHtml(delta) {
  if (delta === 0) return '';
  const dir = delta < 0 ? '↑' : '↓';
  const cls = delta < 0 ? 'delta-over' : 'delta-under';
  return `<span class="${cls}">${dir} juice ${delta}</span>`;
}

function renderProps(pitchers) {
  const el = document.getElementById('panel-props');
  // Sort: FIRE 2u → FIRE 1u → LEAN → PASS
  const order = { 'FIRE 2u': 0, 'FIRE 1u': 1, 'LEAN': 2, 'PASS': 3 };
  const sorted = [...pitchers].sort((a, b) =>
    (order[a.ev_over.verdict] ?? 3) - (order[b.ev_over.verdict] ?? 3)
  );

  const hasAction = sorted.some(p => p.ev_over.verdict !== 'PASS');
  let html = '';

  if (hasAction) {
    html += '<div class="show-all-row"><label><input type="checkbox" id="show-all" onchange="togglePassCards()"> Show PASS verdicts</label></div>';
  }

  for (const p of sorted) {
    const isPass = p.ev_over.verdict === 'PASS';
    html += `
    <div class="pitcher-card ${isPass ? 'card-pass' : ''}" ${isPass ? 'data-pass="1"' : ''}>
      <div class="card-header">
        <div class="card-header-left">
          <span class="pitcher-name">${p.pitcher}</span>
          <span class="pitcher-matchup">${p.team} vs ${p.opp_team}</span>
        </div>
        <span class="verdict-badge ${verdictClass(p.ev_over.verdict)}">${p.ev_over.verdict}</span>
      </div>
      <div class="stats-row">
        <div class="stat-cell">
          <div class="stat-label">Line</div>
          <div class="stat-value">${p.k_line}</div>
          <div class="stat-sub">${fmtOdds(p.best_over_odds)} ${priceDeltaHtml(p.price_delta_over)}</div>
        </div>
        <div class="stat-cell">
          <div class="stat-label">λ</div>
          <div class="stat-value">${p.lambda}</div>
          <div class="stat-sub">Poisson</div>
        </div>
        <div class="stat-cell">
          <div class="stat-label">EV Over</div>
          <div class="stat-value ${p.ev_over.ev > 0 ? 'val-pos' : 'val-neg'}">${(p.ev_over.ev * 100).toFixed(1)}%</div>
          <div class="stat-sub">p=${p.ev_over.win_prob}</div>
        </div>
        <div class="stat-cell">
          <div class="stat-label">Book</div>
          <div class="stat-value">${p.best_over_book}</div>
          <div class="stat-sub">${fmtOdds(p.best_over_odds)}</div>
        </div>
      </div>
      <div class="adj-row">
        ${adjBadge('OPP K%', p.opp_k_rate, 0.227)}
        ${p.ump_k_adj !== 0 ? `<span class="adj-badge ${p.ump_k_adj > 0 ? 'adj-pos' : 'adj-neg'}">UMP ${p.ump_k_adj > 0 ? '+' : ''}${p.ump_k_adj}</span>` : ''}
        <span class="game-time">${fmtTime(p.game_time)}</span>
      </div>
    </div>`;
  }

  el.innerHTML = html || '<p class="empty">No props available.</p>';
  if (hasAction) togglePassCards(); // hide PASS by default
}

function adjBadge(label, actual, avg) {
  const pct = ((actual - avg) / avg * 100).toFixed(0);
  const sign = pct > 0 ? '+' : '';
  const cls  = pct > 0 ? 'adj-pos' : (pct < 0 ? 'adj-neg' : 'adj-neutral');
  return `<span class="adj-badge ${cls}">${label} ${sign}${pct}%</span>`;
}

function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
}

function togglePassCards() {
  const show = document.getElementById('show-all')?.checked;
  document.querySelectorAll('[data-pass="1"]').forEach(el => {
    el.style.display = show ? 'block' : 'none';
  });
}
```

**JavaScript — Watchlist tab:**
```javascript
function renderWatchlist(pitchers) {
  const el = document.getElementById('panel-watch');
  const sorted = [...pitchers]
    .filter(p => p.price_delta_over !== 0)
    .sort((a, b) => Math.abs(b.price_delta_over) - Math.abs(a.price_delta_over))
    .slice(0, 5);

  if (!sorted.length) {
    el.innerHTML = '<p class="empty">No juice movement yet — check back after the 1pm ET run.</p>';
    return;
  }

  let html = '<h2 class="watchlist-hd">Biggest juice moves today</h2>';
  for (const p of sorted) {
    const dir = p.price_delta_over < 0 ? '↑' : '↓';
    const cls = p.price_delta_over < 0 ? 'delta-over' : 'delta-under';
    html += `
    <div class="watch-card">
      <div class="watch-left">
        <span class="pitcher-name">${p.pitcher}</span>
        <span class="pitcher-matchup">${p.team} vs ${p.opp_team}</span>
      </div>
      <div class="watch-mid">
        <span class="stat-label">Over</span>
        <span>${fmtOdds(p.opening_over_odds)} → ${fmtOdds(p.best_over_odds)}</span>
        <span class="${cls}">${dir} ${Math.abs(p.price_delta_over)}</span>
      </div>
      <span class="verdict-badge ${verdictClass(p.ev_over.verdict)}">${p.ev_over.verdict}</span>
    </div>`;
  }

  el.innerHTML = html;
}
```

**Initialize:**
```javascript
document.addEventListener('DOMContentLoaded', loadData);
function switchTab(name, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  btn.classList.add('active');
}
```

- [ ] **Step 2: Open dashboard locally to verify layout**

Since today.json may not exist yet, create a minimal test fixture:

```bash
# Create a quick test fixture
cat > data/processed/today.json << 'EOF'
{
  "generated_at": "2026-04-01T18:00:00Z",
  "date": "2026-04-01",
  "props_available": true,
  "pitchers": [
    {
      "pitcher": "Gerrit Cole", "team": "NYY", "opp_team": "BOS",
      "game_time": "2026-04-01T23:05:00Z",
      "k_line": 7.5, "opening_line": 7.5,
      "best_over_book": "FanDuel", "best_over_odds": -112, "best_under_odds": -108,
      "opening_over_odds": -110, "opening_under_odds": -110,
      "price_delta_over": -2, "price_delta_under": 2,
      "lambda": 7.21, "opp_k_rate": 0.241, "ump_k_adj": 0.4,
      "ev_over":  {"ev": 0.038, "verdict": "FIRE 1u", "win_prob": 0.572},
      "ev_under": {"ev": -0.041, "verdict": "PASS",   "win_prob": 0.428}
    },
    {
      "pitcher": "Shohei Ohtani", "team": "LAD", "opp_team": "SD",
      "game_time": "2026-04-02T02:40:00Z",
      "k_line": 8.5, "opening_line": 8.5,
      "best_over_book": "DraftKings", "best_over_odds": -110, "best_under_odds": -110,
      "opening_over_odds": -110, "opening_under_odds": -110,
      "price_delta_over": 0, "price_delta_under": 0,
      "lambda": 8.11, "opp_k_rate": 0.215, "ump_k_adj": 0.0,
      "ev_over":  {"ev": 0.009, "verdict": "PASS", "win_prob": 0.512},
      "ev_under": {"ev": -0.011, "verdict": "PASS", "win_prob": 0.488}
    }
  ]
}
EOF
```

Open `dashboard/index.html` in a browser (drag to browser or use a local server). Verify:
- Props tab shows Cole as FIRE 1u, Ohtani collapsed under "Show PASS verdicts" toggle
- Juice delta `↑ juice -2` shows on Cole's card
- Watchlist shows Cole as the top mover
- Freshness badge shows "Data may be outdated" (fixture is from 2026-04-01)

- [ ] **Step 3: Commit**

```bash
git add dashboard/index.html data/processed/today.json
git commit -m "feat: dashboard — scorecard theme, Props + Watchlist tabs, freshness states"
```

---

## Task 10: End-to-End Wiring + Deploy Setup

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass.

- [ ] **Step 2: Push repo to GitHub**

```bash
git remote add origin https://github.com/treidjbi/baseballbettingedge.git
git branch -M main
git push -u origin main
```

- [ ] **Step 3: Add RUNDOWN_API_KEY secret in GitHub**

Go to: `https://github.com/treidjbi/baseballbettingedge/settings/secrets/actions`
Add secret: `RUNDOWN_API_KEY` = your TheRundown Starter plan key.

- [ ] **Step 4: Connect Netlify**

1. Log in to Netlify → "Add new site" → "Import an existing project"
2. Choose GitHub → select `treidjbi/baseballbettingedge`
3. Build command: *(leave blank — static site)*
4. Publish directory: `dashboard`
5. Deploy → confirm site is live

- [ ] **Step 5: Trigger a manual pipeline run**

Go to: `https://github.com/treidjbi/baseballbettingedge/actions`
Select "Baseball Pipeline" → "Run workflow" → Run.
Confirm `data/processed/today.json` is committed and Netlify deploys within 30s.

- [ ] **Step 6: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "chore: final wiring — remote set, deploy verified"
git push
```
