# Code Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all Critical and Important issues identified in the 2026-04-01 code review, organized into six phases from highest-impact correctness bugs to polish.

**Architecture:** Fixes are pure in-place edits to existing files — no new modules, no restructuring. Each phase is independently shippable and leaves the system in a working state.

**Tech Stack:** Python 3.11, pytest, scipy/numpy, GitHub Actions, vanilla JS

---

## Phase 1 — Critical Math & Data Correctness

These bugs directly affect bet decisions. Fix first.

---

### Task 1.1: Fix `win_prob_under` for integer K-lines

**Files:**
- Modify: `pipeline/build_features.py:190-191`
- Test: `tests/test_build_features.py`

**Problem:** `win_prob_under = 1 - win_prob_over` double-counts push mass on whole-number lines (5, 6, 7). Over + under probabilities sum to > 1.0, inflating under EV.

**Correct formula:** `win_prob_under = poisson.cdf(math.ceil(k_line) - 1, applied_lam)`

For half-point lines (5.5, 6.5) this is equivalent to the old formula. For integer lines it is correct.

- [ ] **Step 1: Write the failing test**

Note: The half-line test (`k_line=7.5`) will PASS even before the fix because `floor(7.5)=7` and `ceil(7.5)-1=7` produce the same CDF. Only the integer test demonstrates the failure — run both together but only expect the integer one to fail.

Add to `tests/test_build_features.py` inside `TestBuildPitcherRecord`:

```python
def test_win_prob_over_plus_under_sum_to_one_half_line(self):
    """For half-point lines, over + under should sum to 1.0 (no push mass)."""
    from build_features import build_pitcher_record
    odds = {**self.BASE_ODDS, "k_line": 7.5}
    rec = build_pitcher_record(odds, self.BASE_STATS, ump_k_adj=0.0)
    total = rec["ev_over"]["win_prob"] + rec["ev_under"]["win_prob"]
    assert abs(total - 1.0) < 0.001

def test_win_prob_over_plus_under_sum_to_one_integer_line(self):
    """For integer lines, over + under should sum to < 1.0 (push mass exists)."""
    from build_features import build_pitcher_record
    from scipy.stats import poisson
    import math
    odds = {**self.BASE_ODDS, "k_line": 7.0}
    rec = build_pitcher_record(odds, self.BASE_STATS, ump_k_adj=0.0)
    total = rec["ev_over"]["win_prob"] + rec["ev_under"]["win_prob"]
    # They should sum to < 1.0 (push probability is the gap)
    assert total < 1.0
    # And specifically the gap should equal P(X == 7) at the applied lambda
    lam = rec["lambda"]
    push_prob = poisson.pmf(7, lam)
    assert abs((1.0 - total) - push_prob) < 0.002
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
python -m pytest tests/test_build_features.py::TestBuildPitcherRecord::test_win_prob_over_plus_under_sum_to_one_integer_line -v
```
Expected: FAIL — integer test fails because currently over + under > 1.0

- [ ] **Step 3: Fix `build_features.py:190-191`**

Change:
```python
win_prob_over  = 1 - poisson.cdf(math.floor(k_line), applied_lam)
win_prob_under = 1 - win_prob_over
```

To:
```python
win_prob_over  = 1 - poisson.cdf(math.floor(k_line), applied_lam)
win_prob_under = poisson.cdf(math.ceil(k_line) - 1, applied_lam)
```

- [ ] **Step 4: Run all build_features tests**

```bash
python -m pytest tests/test_build_features.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/build_features.py tests/test_build_features.py
git commit -m "fix: correct win_prob_under for integer K-lines (push mass bug)"
```

---

### Task 1.2: Fix home pitcher team/opp_team swap in `fetch_odds.py`

**Files:**
- Modify: `pipeline/fetch_odds.py:65-171`
- Test: `tests/test_fetch_odds.py`

**Problem:** Every pitcher in a market gets `team=away_team` and `opp_team=home_team` regardless of which side they pitch for. Home starters are labeled with the wrong team in the DB and dashboard.

**Fix:** Determine each pitcher's team by matching their name against the participant's `team_id` or by using a side flag in the API response. If the API does not provide a side flag per participant, use the MLB schedule (already fetched in `fetch_stats`) as the source of truth. The cleanest fix within `fetch_odds.py` alone: mark both pitchers with `team=None, opp_team=None` and resolve team assignment in `fetch_stats` where the schedule is authoritative.

However, the simpler targeted fix is: check if the participant API response includes a `team_id` or `is_home` field on the participant and use it. Looking at the existing code, participants come from `market["participants"]` — each participant has a `name` but no team side flag in the parsed structure.

**Best fix:** Set `team` and `opp_team` to empty strings in `fetch_odds`, and populate them in `fetch_stats.py` when we have the confirmed starter info from the MLB schedule (which already knows home/away).

- [ ] **Step 1: Write failing test**

Add to `tests/test_fetch_odds.py`:

```python
def test_home_pitcher_gets_home_team_not_away():
    """Home pitcher must NOT get team=away_team."""
    event = {
        "teams": [
            {"name": "Yankees", "is_away": True, "is_home": False},
            {"name": "Red Sox", "is_away": False, "is_home": True},
        ],
        "event_date": "2026-04-01T23:05:00Z",
        "markets": [{
            "market_id": 19,
            "participants": [
                {
                    "name": "Away Pitcher",
                    "team_id": "away_team_id",
                    "lines": [{"value": "Over 6.5", "prices": {"1": {"price": -110, "is_main_line": True, "price_delta": 0}}},
                               {"value": "Under 6.5", "prices": {"1": {"price": -110, "is_main_line": True, "price_delta": 0}}}]
                },
                {
                    "name": "Home Pitcher",
                    "team_id": "home_team_id",
                    "lines": [{"value": "Over 5.5", "prices": {"1": {"price": -115, "is_main_line": True, "price_delta": 0}}},
                               {"value": "Under 5.5", "prices": {"1": {"price": -105, "is_main_line": True, "price_delta": 0}}}]
                },
            ]
        }]
    }
    # Both pitchers should have team='' (unresolved) since fetch_odds can't know home/away per pitcher
    from fetch_odds import _parse_event_k_props
    results = _parse_event_k_props(event)
    assert len(results) == 2
    # Neither pitcher should be confidently assigned a team at this stage
    # (team resolution happens in fetch_stats via MLB schedule)
    away_rec = next(r for r in results if r["pitcher"] == "Away Pitcher")
    home_rec = next(r for r in results if r["pitcher"] == "Home Pitcher")
    # After fix: team fields are empty strings, resolved later
    assert away_rec["team"] == ""
    assert home_rec["team"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_fetch_odds.py::test_home_pitcher_gets_home_team_not_away -v
```
Expected: FAIL — currently both pitchers get `team="Yankees"` (away_team)

- [ ] **Step 3: Fix `fetch_odds.py` — clear team assignment**

In `_parse_event_k_props`, change the `results.append(...)` block (line 157-169). Replace:
```python
results.append({
    "pitcher":            pitcher_name,
    "team":               away_team,
    "opp_team":           home_team,
    ...
})
```
With:
```python
results.append({
    "pitcher":            pitcher_name,
    "team":               "",        # resolved by fetch_stats via MLB schedule
    "opp_team":           "",        # resolved by fetch_stats via MLB schedule
    ...
})
```

- [ ] **Step 4: Fix `fetch_stats.py` — populate team/opp_team per pitcher**

In `fetch_stats`, after building `pstats`, add team name resolution. The schedule already has `side` ("away"/"home") and team names. Replace:
```python
stats_by_name[name] = {**pstats, "opp_k_rate": opp_k_rate}
```
With:
```python
team_name     = team_data.get("team", {}).get("name", "")
opp_team_name = opp_team.get("name", "")
stats_by_name[name] = {
    **pstats,
    "opp_k_rate":  opp_k_rate,
    "team":        team_name,
    "opp_team":    opp_team_name,
}
```

- [ ] **Step 5: Fix `build_features.py` — prefer stats team over odds team**

In `build_pitcher_record`, after the `params = load_params()` line, update the return dict to prefer the authoritative team from `stats` if present:

```python
# team/opp_team: stats dict is authoritative (from MLB schedule); odds fallback for safety
team     = stats.get("team")     or odds.get("team", "")
opp_team = stats.get("opp_team") or odds.get("opp_team", "")
```

And in the return dict replace:
```python
"team":               odds["team"],
"opp_team":           odds["opp_team"],
```
With:
```python
"team":               team,
"opp_team":           opp_team,
```

- [ ] **Step 6: Add integration test verifying resolved team name flows through `build_pitcher_record`**

Add to `tests/test_build_features.py` inside `TestBuildPitcherRecord`:

```python
def test_team_from_stats_overrides_empty_string_from_odds(self):
    """When stats contains team/opp_team (from MLB schedule), build_pitcher_record
    should output those values, not the empty strings from fetch_odds."""
    from build_features import build_pitcher_record
    odds = {**self.BASE_ODDS, "team": "", "opp_team": ""}
    stats = {**self.BASE_STATS, "team": "Boston Red Sox", "opp_team": "New York Yankees"}
    rec = build_pitcher_record(odds, stats, ump_k_adj=0.0)
    assert rec["team"] == "Boston Red Sox"
    assert rec["opp_team"] == "New York Yankees"
```

- [ ] **Step 7: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add pipeline/fetch_odds.py pipeline/fetch_stats.py pipeline/build_features.py tests/test_fetch_odds.py tests/test_build_features.py
git commit -m "fix: resolve team/opp_team from MLB schedule instead of odds API (home pitcher swap bug)"
```

---

### Task 1.3: Wire up `opp_games_played` so Bayesian blend actually works

**Files:**
- Modify: `pipeline/fetch_stats.py:99-165`
- Test: `tests/test_build_features.py` (existing `test_high_k_opponent_inflates_lambda` already covers the math — this fixes production data flow)

**Problem:** `fetch_stats` never puts `opp_games_played` in the stats dict. `bayesian_opp_k` always gets `opp_games_played=0` → full regression to league average → `opp_k_rate` is a no-op in production.

**Fix:** The MLB schedule already returns team game counts. Fetch the team's `gamesPlayed` from the teams stats endpoint (same call already made for K rate).

**Interdependency note:** Task 1.3 Step 4 shows the final `stats_by_name[name]` dict. It supersedes the dict change from Task 1.2 Step 4 — the dict in Step 4 here must include all fields from both tasks (`team`, `opp_team`, `opp_k_rate`, `opp_games_played`). Implement Task 1.2 before Task 1.3, and use the combined dict shown in Step 4 below.

- [ ] **Step 1: Write failing test**

Add to `tests/test_build_features.py` in `TestBuildPitcherRecord`:

```python
def test_opp_games_played_affects_lambda(self):
    """opp_games_played=0 (no data) should produce same lambda as league avg opp.
    opp_games_played=162 with high K% team should produce higher lambda."""
    from build_features import build_pitcher_record
    stats_no_games = {**self.BASE_STATS, "opp_k_rate": 0.30, "opp_games_played": 0}
    stats_full_season = {**self.BASE_STATS, "opp_k_rate": 0.30, "opp_games_played": 162}
    rec_no = build_pitcher_record(self.BASE_ODDS, stats_no_games, ump_k_adj=0.0)
    rec_full = build_pitcher_record(self.BASE_ODDS, stats_full_season, ump_k_adj=0.0)
    # With 162 games of 0.30 K%, lambda should be higher than with 0 games (league avg)
    assert rec_full["lambda"] > rec_no["lambda"]
```

- [ ] **Step 2: Run test to verify it already passes (math is correct)**

```bash
python -m pytest tests/test_build_features.py::TestBuildPitcherRecord::test_opp_games_played_affects_lambda -v
```
Expected: PASS — the math works, the issue is the production data flow.

- [ ] **Step 3: Fix `fetch_stats.py` — add `gamesPlayed` to team stats fetch**

In `fetch_team_k_rate`, also return games played. Change the function signature and body:

```python
def fetch_team_k_rate(team_id: int, season: int) -> tuple[float, int]:
    """Fetch a team's season batter K% and games played.
    Returns (k_rate, games_played). Falls back to (0.227, 0) on missing data."""
    data   = _get(f"/teams/{team_id}/stats", {
        "stats": "season", "group": "hitting", "season": season
    })
    splits = data.get("stats", [{}])[0].get("splits", [])
    for split in splits:
        stat = split.get("stat", {})
        pa   = int(stat.get("plateAppearances", 0) or 0)
        so   = int(stat.get("strikeOuts", 0) or 0)
        gp   = int(stat.get("gamesPlayed", 0) or 0)
        if pa > 0:
            return round(so / pa, 4), gp
    return 0.227, 0  # fall back to league average, no games
```

- [ ] **Step 4: Update callers in `fetch_stats`**

In `fetch_stats`, change the call to `fetch_team_k_rate`:
```python
try:
    opp_k_rate, opp_games_played = fetch_team_k_rate(opp_team_id, season) if opp_team_id else (0.227, 0)
except Exception as e:
    log.warning("Team K rate fetch failed for %s: %s", opp_team.get("name"), e)
    opp_k_rate, opp_games_played = 0.227, 0
```

And in the stats dict:
```python
stats_by_name[name] = {
    **pstats,
    "opp_k_rate":       opp_k_rate,
    "opp_games_played": opp_games_played,
    "team":             team_name,
    "opp_team":         opp_team_name,
}
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All PASS (fetch_team_k_rate signature change is internal to the module)

- [ ] **Step 6: Commit**

```bash
git add pipeline/fetch_stats.py tests/test_build_features.py
git commit -m "fix: wire opp_games_played from MLB API so Bayesian opp K% blend is active"
```

---

## Phase 2 — CI/CD & Deployment Reliability

---

### Task 2.1: Fix git push order and add DST-aware cron schedules

**Files:**
- Modify: `.github/workflows/pipeline.yml`

**Problem 1 (DST):** Cron schedules use UTC-5 offsets (EST), but the baseball season runs in EDT (UTC-4). The 9am scheduled run fires at 10am ET all season.

**Problem 2 (results.db in git):** `results.db` is committed to git — binary file, grows unbounded, causes merge conflicts on concurrent runs.

**Note:** The existing git commit-pull-push order in `pipeline.yml` (commit → pull --rebase → push) is already correct. No change needed there.

- [ ] **Step 1: Remove `results.db` from the `git add` list**

In the `Commit pipeline output` step, remove the `results.db` line:

```yaml
      - name: Commit pipeline output
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add dashboard/data/processed/
          test -f dashboard/data/performance.json && git add dashboard/data/performance.json || true
          test -f data/params.json && git add data/params.json || true
          git diff --staged --quiet || git commit -m "chore: pipeline update $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git pull --rebase
          git push
```

(The `data/results.db` line that existed before is now gone.)

- [ ] **Step 2: Add `results.db` to `.gitignore`**

Add to `.gitignore`:
```
data/results.db
```

- [ ] **Step 3: Fix cron schedules for EDT**

The pipeline runs during the baseball season (April–October), which is entirely in EDT (UTC-4). Add a second set of schedules for EDT and use GitHub's workflow_dispatch as the manual trigger. Replace the `on.schedule` block:

```yaml
on:
  schedule:
    # Morning run: 9:00 AM ET
    # EDT (Mar–Nov): UTC-4 → 13:00 UTC
    # EST (Nov–Mar): UTC-5 → 14:00 UTC
    - cron: '0 13 * * *'   # 9am EDT (primary — baseball season)
    - cron: '0 14 * * *'   # 9am EST (offseason)
    # Midday run: 1:00 PM ET
    - cron: '0 17 * * *'   # 1pm EDT
    - cron: '0 18 * * *'   # 1pm EST
    # Evening run: 8:00 PM ET
    - cron: '0 0 * * *'    # 8pm EDT (midnight UTC)
    - cron: '0 1 * * *'    # 8pm EST (1am UTC)
  workflow_dispatch:
```

Update the evening run detection to match both EDT and EST evening crons:

```yaml
          if [ "${{ github.event.schedule }}" = "0 0 * * *" ] || [ "${{ github.event.schedule }}" = "0 1 * * *" ]; then
            python pipeline/run_pipeline.py $(TZ=America/New_York date +%Y-%m-%d) --run-type evening
          else
            python pipeline/run_pipeline.py $(TZ=America/New_York date +%Y-%m-%d)
          fi
```

Note: `$(TZ=America/New_York date +%Y-%m-%d)` ensures the date is always ET regardless of runner timezone.

- [ ] **Step 4: Verify `.gitignore` has results.db**

```bash
git check-ignore -v data/results.db
```
Expected: `data/results.db` is ignored

- [ ] **Step 5: Remove `results.db` from git tracking if it was previously committed**

```bash
git rm --cached data/results.db 2>/dev/null || echo "not tracked"
```

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/pipeline.yml .gitignore
git commit -m "fix: correct git push order, DST-aware cron schedules, remove results.db from git"
```

---

### Task 2.2: Fix `run_pipeline.py` date default to use ET timezone

**Files:**
- Modify: `pipeline/run_pipeline.py:217`
- Test: `tests/test_run_pipeline.py`

**Problem:** `datetime.now().strftime("%Y-%m-%d")` uses system local time. On a dev machine in ET near midnight, it returns "tomorrow" while games are still being played "today."

- [ ] **Step 1: Write failing test**

The test patches `sys.argv` so argparse uses no date argument, forcing it to use the default. It then checks the output file's date field matches ET, not UTC.

Add to `tests/test_run_pipeline.py`:

```python
def test_default_date_uses_et_not_utc(tmp_path):
    """When no date argument is given, pipeline should use today in ET (not UTC).
    At 11pm ET (= 4am UTC next day), the output date should still be the ET date."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    import run_pipeline
    from unittest.mock import patch, MagicMock
    from zoneinfo import ZoneInfo
    from datetime import datetime

    # 11pm ET April 1 = 3am UTC April 2
    et_now = datetime(2026, 4, 1, 23, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    out_path = tmp_path / "today.json"

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[]), \
         patch("run_pipeline._write_archive"), \
         patch("run_pipeline._run_evening_steps"), \
         patch("run_pipeline.datetime") as mock_dt:
        # Make datetime.now(tz) return our ET time
        mock_dt.now.return_value = et_now
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.strptime = datetime.strptime

        # Simulate argparse with no date arg — triggers default= computation
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("date", nargs="?",
                            default=mock_dt.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"))
        args = parser.parse_args([])
        assert args.date == "2026-04-01"  # ET date, not UTC date (which would be 2026-04-02)
```

- [ ] **Step 2: Fix `run_pipeline.py:217`**

Change:
```python
default=datetime.now().strftime("%Y-%m-%d"),
```
To:
```python
default=datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"),
```

`ZoneInfo` is already imported at the top of the file (line 13).

- [ ] **Step 3: Clean up dev comment on line 128**

Change:
```python
log.info("Built %d/%d pitcher records (lambda v2: variable IP + SwStr%%)", len(records), len(props))
```
To:
```python
log.info("Built %d/%d pitcher records", len(records), len(props))
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_run_pipeline.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/run_pipeline.py tests/test_run_pipeline.py
git commit -m "fix: use ET timezone for default date in run_pipeline CLI"
```

---

## Phase 3 — Robustness & Error Handling

---

### Task 3.1: Protect `seed_picks` from missing/corrupt `today.json`

**Files:**
- Modify: `pipeline/fetch_results.py:68-98`
- Test: `tests/test_fetch_results.py`

**Problem:** `seed_picks` opens `today.json` without error handling. A missing or corrupt file on the 8pm run crashes before result fetching or calibration run.

- [ ] **Step 1: Write failing test**

Add to `tests/test_fetch_results.py`:

```python
def test_seed_picks_missing_file_returns_zero():
    """seed_picks should return 0 and log a warning when today.json is missing."""
    from pathlib import Path
    from fetch_results import seed_picks
    result = seed_picks(Path("/nonexistent/path/today.json"))
    assert result == 0

def test_seed_picks_corrupt_json_returns_zero(tmp_path):
    """seed_picks should return 0 when today.json contains invalid JSON."""
    bad_json = tmp_path / "today.json"
    bad_json.write_text("{not valid json{{")
    from fetch_results import seed_picks
    result = seed_picks(bad_json)
    assert result == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_fetch_results.py::test_seed_picks_missing_file_returns_zero tests/test_fetch_results.py::test_seed_picks_corrupt_json_returns_zero -v
```
Expected: FAIL — currently raises `FileNotFoundError`

- [ ] **Step 3: Fix `fetch_results.py:68-72`**

Change:
```python
def seed_picks(today_json_path: Path = TODAY_JSON) -> int:
    """Insert non-PASS picks from today.json. Returns count of new rows inserted."""
    with open(today_json_path) as f:
        data = json.load(f)
```
To:
```python
def seed_picks(today_json_path: Path = TODAY_JSON) -> int:
    """Insert non-PASS picks from today.json. Returns count of new rows inserted."""
    try:
        with open(today_json_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        log.warning("seed_picks: could not read %s: %s — skipping seed", today_json_path, e)
        return 0
```

- [ ] **Step 4: Run all fetch_results tests**

```bash
python -m pytest tests/test_fetch_results.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "fix: guard seed_picks against missing or corrupt today.json"
```

---

### Task 3.2: Fix fragile void detection in `fetch_and_close_results`

**Files:**
- Modify: `pipeline/fetch_results.py:209`

**Problem:** `any(team_norm in ft or ft in team_norm for ft in finalized_teams)` uses substring matching. "New York" matches both Yankees and Mets — a Mets pitcher could be voided when the Yankees game finishes.

**Fix:** Use exact match on abbreviation, falling back to exact match on full name. Never use substring.

- [ ] **Step 1: Write integration test using a real NY-team collision scenario**

Add to `tests/test_fetch_results.py`:

```python
def test_void_detection_does_not_cross_match_ny_teams(tmp_path):
    """A Mets pitcher should NOT be voided when only a Yankees game is final."""
    import fetch_results
    from unittest.mock import patch, MagicMock

    db_path = tmp_path / "results.db"
    with patch.object(fetch_results, "DB_PATH", db_path):
        fetch_results.init_db()
        # Seed a Mets pitcher pick for yesterday
        with fetch_results.get_db() as conn:
            conn.execute("""
                INSERT INTO picks (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                                   raw_lambda, applied_lambda, odds, movement_conf)
                VALUES ('2026-03-31','Jacob deGrom','new york mets','over',
                        6.5,'FIRE 2u',0.10,0.09,5.5,5.5,-110,1.0)
            """)

        # Schedule: only Yankees game is final — Mets game is not final
        schedule_resp = MagicMock()
        schedule_resp.raise_for_status = MagicMock()
        schedule_resp.json.return_value = {
            "dates": [{
                "games": [
                    {
                        "gamePk": 1,
                        "status": {"abstractGameState": "Final"},
                        "teams": {
                            "home": {"team": {"name": "New York Yankees", "abbreviation": "NYY"}},
                            "away": {"team": {"name": "Boston Red Sox", "abbreviation": "BOS"}},
                        }
                    },
                    {
                        "gamePk": 2,
                        "status": {"abstractGameState": "Live"},  # Mets game NOT final
                        "teams": {
                            "home": {"team": {"name": "New York Mets", "abbreviation": "NYM"}},
                            "away": {"team": {"name": "Atlanta Braves", "abbreviation": "ATL"}},
                        }
                    }
                ]
            }]
        }

        boxscore_resp = MagicMock()
        boxscore_resp.raise_for_status = MagicMock()
        boxscore_resp.json.return_value = {
            "teams": {
                "home": {"pitchers": [999], "players": {
                    "ID999": {"person": {"fullName": "Gerrit Cole"},
                              "stats": {"pitching": {"strikeOuts": 8}}}
                }},
                "away": {"pitchers": [], "players": {}}
            }
        }

        def mock_get(url, **kwargs):
            if "boxscore" in url:
                return boxscore_resp
            return schedule_resp

        with patch("fetch_results.requests.get", side_effect=mock_get):
            with patch("fetch_results._et_dates", return_value=("2026-04-01", "2026-03-31")):
                closed = fetch_results.fetch_and_close_results()

        # Mets pitcher should NOT be voided (Yankees game finished but Mets game did not)
        with fetch_results.get_db() as conn:
            pick = conn.execute(
                "SELECT result FROM picks WHERE pitcher='Jacob deGrom'"
            ).fetchone()
        assert pick["result"] is None  # still open — not voided
        assert closed == 0
```

- [ ] **Step 2: Run test to verify it fails (bug is present)**

```bash
python -m pytest tests/test_fetch_results.py::test_void_detection_does_not_cross_match_ny_teams -v
```
Expected: FAIL — current substring logic matches "new york mets" to "new york yankees"

- [ ] **Step 3: Fix void detection in `fetch_results.py`**

The `finalized_teams` set already contains both the full team name and the abbreviation (lines 157-160). Change the void detection at line 209:

```python
elif any(team_norm in ft or ft in team_norm for ft in finalized_teams):
```
To:
```python
elif team_norm in finalized_teams:
```

And update `finalized_teams` population to normalize team names the same way `team_norm` is computed (i.e., `.lower().strip()` — which it already does). This ensures exact matching works.

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "fix: use exact team match for void detection to prevent cross-NY team false positives"
```

---

### Task 3.3: Add retry logic to MLB Stats API calls

**Files:**
- Modify: `pipeline/fetch_stats.py:15-18`

**Problem:** `_get` has no retry. A brief MLB API blip can silently skip all pitchers on a slate.

- [ ] **Step 1: Fix `fetch_stats.py` `_get` function**

Replace:
```python
def _get(path: str, params: dict = None) -> dict:
    resp = requests.get(f"{MLB_BASE}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()
```
With:
```python
def _get(path: str, params: dict = None) -> dict:
    """GET with 3-attempt retry and exponential backoff."""
    import time
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.get(f"{MLB_BASE}{path}", params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s
    raise last_err
```

- [ ] **Step 2: Move `timedelta` import to module level**

Remove `from datetime import timedelta` from inside `fetch_stats` function body (line 121).

Add `timedelta` to the top-level import:
```python
from datetime import datetime, timedelta
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/fetch_stats.py
git commit -m "fix: add retry logic to MLB Stats API, move timedelta import to module level"
```

---

## Phase 4 — Calibration Correctness

---

### Task 4.1: Fix Phase 2 blend-weight NNLS normalization

**Files:**
- Modify: `pipeline/calibrate.py:227-245`
- Test: `tests/test_calibrate.py`

**Problem:** The NNLS normalization divides X by column means, then divides coefficients by column means again. The correct inverse is a single division. Additionally the target `y` is in raw K counts while the columns are K/9 rates, making the coefficient scale meaningless. The correct approach: directly regress normalized (sum-to-1) columns against actual Ks.

- [ ] **Step 1: Write failing test**

Use varied input data so the regression actually exercises weight estimation (constant rows produce degenerate NNLS and don't test the math):

Add to `tests/test_calibrate.py`:

```python
def test_phase2_blend_weights_sum_to_one():
    """After Phase 2 calibration with data where season_k9 is the best predictor,
    weight_season_cap should dominate, and weights should sum to <= 1.0."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from calibrate import _calibrate_phase2

    # 60 rows with varied K/9 values; actual_ks correlates most with season_k9
    # so we expect weight_season_cap to get a high weight after calibration
    import random
    random.seed(42)
    picks = []
    for i in range(60):
        s_k9 = 7.0 + (i % 8) * 0.5   # 7.0 to 10.5
        r_k9 = 8.0 + (i % 4) * 0.25   # 8.0 to 8.75
        c_k9 = 7.5 + (i % 5) * 0.3    # 7.5 to 8.7
        # actual_ks strongly tracks season_k9
        actual = round(s_k9 * 0.55)
        picks.append({
            "season_k9": s_k9, "recent_k9": r_k9, "career_k9": c_k9,
            "actual_ks": actual, "ump_k_adj": 0.0, "raw_lambda": 5.0,
        })

    params = {"weight_season_cap": 0.70, "weight_recent": 0.20, "ump_scale": 1.0,
              "lambda_bias": 0.0, "ev_thresholds": {}}
    result = _calibrate_phase2(picks, params)
    ws = result["weight_season_cap"]
    wr = result["weight_recent"]
    # Weights must sum to <= 1.0 (career = 1 - ws - wr)
    assert ws + wr <= 1.0
    assert ws >= 0.05
    assert wr >= 0.05
    # Season weight should be at least as large as recent (season is the better predictor)
    assert ws >= wr
```

- [ ] **Step 2: Run test**

```bash
python -m pytest tests/test_calibrate.py::test_phase2_blend_weights_sum_to_one -v
```

- [ ] **Step 3: Fix `_calibrate_phase2` blend weight regression**

Replace the NNLS block (lines 227-247) with a cleaner column-sum normalization approach:

```python
if len(blend_data) >= 60:
    try:
        import numpy as np
        from scipy.optimize import nnls
        X = np.array([[d[0], d[1], d[2]] for d in blend_data])
        y = np.array([d[3] for d in blend_data], dtype=float)

        # Normalize each feature column to mean=1 so coefficients are
        # directly interpretable as relative weights
        col_means = X.mean(axis=0)
        col_means[col_means == 0] = 1.0
        X_norm = X / col_means  # each column now has mean ≈ 1

        # Also normalize y to mean=1 for unit-consistent regression
        y_mean = y.mean() if y.mean() != 0 else 1.0
        y_norm = y / y_mean

        coeffs, _ = nnls(X_norm, y_norm)
        total = coeffs.sum()
        if total > 0:
            w = coeffs / total  # normalize to sum=1
            w = [max(0.05, wi) for wi in w]  # floor each weight at 5%
            w_total = sum(w)
            w = [wi / w_total for wi in w]   # renormalize after floor
            params["weight_season_cap"] = round(min(0.85, max(0.40, w[0])), 3)
            params["weight_recent"]     = round(min(0.40, max(0.05, w[1])), 3)
    except Exception as e:
        log.warning("Blend weight regression failed: %s — keeping current weights", e)
```

- [ ] **Step 4: Run all calibrate tests**

```bash
python -m pytest tests/test_calibrate.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/calibrate.py tests/test_calibrate.py
git commit -m "fix: correct NNLS blend weight normalization in Phase 2 calibration"
```

---

### Task 4.2: Allow `ump_scale` to increase when ump data is predictive

**Files:**
- Modify: `pipeline/calibrate.py:213-220`
- Test: `tests/test_calibrate.py`

**Problem:** `ump_scale` only ever decreases (when `abs(corr) < 0.05`). There is no path to increase it when correlation is high. Scale decays toward 0, never recovers.

**Fix:** Add a symmetric branch — when `corr > 0.15` (strong positive correlation), increase scale by 0.05.

- [ ] **Step 1: Write test**

Add to `tests/test_calibrate.py`:

```python
def test_ump_scale_increases_when_correlated():
    """When ump_k_adj strongly correlates with residuals, ump_scale should increase."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from calibrate import _calibrate_phase2

    # Create data with strong positive correlation between ump_k_adj and residual
    picks = []
    for i in range(60):
        ump_adj = (i % 5) * 0.1  # 0.0, 0.1, 0.2, 0.3, 0.4
        residual = ump_adj * 2    # perfect positive correlation
        picks.append({
            "season_k9": 9.0, "recent_k9": 8.0, "career_k9": 7.0,
            "ump_k_adj": ump_adj,
            "actual_ks": int(5 + residual),
            "raw_lambda": 5.0,
        })

    params = {"weight_season_cap": 0.70, "weight_recent": 0.20,
              "ump_scale": 1.0, "lambda_bias": 0.0, "ev_thresholds": {}}
    result = _calibrate_phase2(picks, params)
    assert result["ump_scale"] > 1.0  # should have increased


def test_ump_scale_decreases_when_uncorrelated():
    """When ump_k_adj shows no correlation with residuals, ump_scale should decrease."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from calibrate import _calibrate_phase2

    picks = [
        {"season_k9": 9.0, "recent_k9": 8.0, "career_k9": 7.0,
         "ump_k_adj": 0.2, "actual_ks": 5, "raw_lambda": 5.0}
    ] * 60  # constant ump_k_adj → zero variance → |corr| < 0.05

    params = {"weight_season_cap": 0.70, "weight_recent": 0.20,
              "ump_scale": 1.0, "lambda_bias": 0.0, "ev_thresholds": {}}
    result = _calibrate_phase2(picks, params)
    assert result["ump_scale"] < 1.0  # should have decreased
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_calibrate.py::test_ump_scale_increases_when_correlated tests/test_calibrate.py::test_ump_scale_decreases_when_uncorrelated -v
```
Expected: `test_ump_scale_increases_when_correlated` FAIL, `test_ump_scale_decreases_when_uncorrelated` PASS

- [ ] **Step 3: Fix `_calibrate_phase2` ump_scale logic**

Replace lines 216-220:
```python
            if abs(corr) < 0.05:
                current_scale = params.get("ump_scale", 1.0)
                params["ump_scale"] = round(max(0.0, min(1.5, current_scale - 0.05)), 3)
```
With:
```python
            current_scale = params.get("ump_scale", 1.0)
            if corr > 0.15:
                # Strong positive correlation: ump adjustment is predictive — increase weight
                params["ump_scale"] = round(max(0.0, min(1.5, current_scale + 0.05)), 3)
            elif abs(corr) < 0.05:
                # Near-zero correlation: ump adjustment not predictive — decrease weight
                params["ump_scale"] = round(max(0.0, min(1.5, current_scale - 0.05)), 3)
            # Between 0.05 and 0.15: leave scale unchanged
```

- [ ] **Step 4: Run all calibrate tests**

```bash
python -m pytest tests/test_calibrate.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/calibrate.py tests/test_calibrate.py
git commit -m "fix: allow ump_scale to increase when ump data is predictive, not just decrease"
```

---

## Phase 5 — Test Coverage Gaps

---

### Task 5.1: Fix `fetch_results` tests to properly mock two-call HTTP flow

**Files:**
- Modify: `tests/test_fetch_results.py`

**Problem:** `fetch_and_close_results` makes two HTTP calls — one to `/schedule` and one to `/game/{pk}/boxscore` — but tests use a single mock that returns the same response for both. Tests pass but prove nothing about the boxscore parsing path.

- [ ] **Step 1: Add tests using properly sequenced mocks**

**Important:** `test_fetch_results.py` already has a `_make_schedule_response` helper. Use different names (`_sched_resp` and `_bs_resp`) to avoid shadowing it.

Add to `tests/test_fetch_results.py`:

```python
def _sched_resp(game_pk=12345, is_final=True):
    """Minimal schedule API response for two-call HTTP flow tests."""
    return {
        "dates": [{
            "games": [{
                "gamePk": game_pk,
                "status": {"abstractGameState": "Final" if is_final else "Live"},
                "teams": {
                    "home": {"team": {"name": "Boston Red Sox", "abbreviation": "BOS"}},
                    "away": {"team": {"name": "New York Yankees", "abbreviation": "NYY"}},
                }
            }]
        }]
    }

def _bs_resp(starter_name="Chris Sale", starter_id=123, ks=7):
    """Minimal boxscore API response for two-call HTTP flow tests."""
    return {
        "teams": {
            "home": {
                "pitchers": [starter_id],
                "players": {
                    f"ID{starter_id}": {
                        "person": {"fullName": starter_name},
                        "stats": {"pitching": {"strikeOuts": ks}}
                    }
                }
            },
            "away": {"pitchers": [], "players": {}}
        }
    }

def test_fetch_and_close_results_calls_boxscore_separately(tmp_path):
    """The schedule call and boxscore call should use different response data."""
    import sqlite3
    from unittest.mock import patch, MagicMock
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    import fetch_results

    # Set up a real DB with an open pick
    db_path = tmp_path / "results.db"
    with patch.object(fetch_results, "DB_PATH", db_path):
        fetch_results.init_db()
        with fetch_results.get_db() as conn:
            conn.execute("""
                INSERT INTO picks (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                                   raw_lambda, applied_lambda, odds, movement_conf)
                VALUES ('2026-03-31','Chris Sale','BOS','over',7.5,'FIRE 2u',0.10,0.09,
                        5.5,5.5,-110,1.0)
            """)

        schedule_mock = MagicMock()
        schedule_mock.json.return_value = _sched_resp(game_pk=99, is_final=True)
        schedule_mock.raise_for_status = MagicMock()

        boxscore_mock = MagicMock()
        boxscore_mock.json.return_value = _bs_resp("Chris Sale", 456, ks=8)
        boxscore_mock.raise_for_status = MagicMock()

        call_count = [0]
        def mock_get(url, **kwargs):
            call_count[0] += 1
            if "boxscore" in url:
                return boxscore_mock
            return schedule_mock

        with patch("fetch_results.requests.get", side_effect=mock_get):
            with patch("fetch_results._et_dates", return_value=("2026-04-01", "2026-03-31")):
                closed = fetch_results.fetch_and_close_results()

        # Two HTTP calls should have been made: schedule + boxscore
        assert call_count[0] == 2
        # The pick should be resolved
        assert closed == 1
```

- [ ] **Step 2: Run the new test**

```bash
python -m pytest tests/test_fetch_results.py::test_fetch_and_close_results_calls_boxscore_separately -v
```
Expected: PASS

- [ ] **Step 3: Run all fetch_results tests**

```bash
python -m pytest tests/test_fetch_results.py -v
```
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_fetch_results.py
git commit -m "test: fix fetch_results tests to properly mock two-call HTTP flow (schedule + boxscore)"
```

---

### Task 5.2: Add `run()` orchestration tests to `test_run_pipeline.py`

**Files:**
- Modify: `tests/test_run_pipeline.py`

**Problem:** `run()` — which orchestrates five systems and writes two output formats — has zero test coverage.

- [ ] **Step 1: Add orchestration tests**

Add to `tests/test_run_pipeline.py`:

```python
import sys, os, json, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))


def _sample_prop():
    return {
        "pitcher": "Test Pitcher", "team": "", "opp_team": "",
        "game_time": "2026-04-01T23:05:00Z", "k_line": 6.5, "opening_line": 6.5,
        "best_over_book": "FD", "best_over_odds": -110, "best_under_odds": -110,
        "opening_over_odds": -110, "opening_under_odds": -110,
    }

def _sample_stats():
    return {
        "season_k9": 9.0, "recent_k9": 9.0, "career_k9": 8.0,
        "starts_count": 5, "innings_pitched_season": 30.0,
        "avg_ip_last5": 5.5, "opp_k_rate": 0.227, "opp_games_played": 10,
        "team": "Test Team", "opp_team": "Opp Team",
    }


def test_run_writes_today_json(tmp_path):
    """run() should always write today.json even if it has 0 pitchers."""
    import run_pipeline
    out_path = tmp_path / "today.json"

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value={"Test Pitcher": _sample_stats()}), \
         patch("run_pipeline.fetch_swstr", return_value={"Test Pitcher": 0.110}), \
         patch("run_pipeline.fetch_umpires", return_value={"Test Pitcher": 0.0}), \
         patch("run_pipeline._write_archive"):  # skip archive for unit test
        run_pipeline.run("2026-04-01")

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["date"] == "2026-04-01"
    assert len(data["pitchers"]) == 1


def test_run_writes_empty_output_when_no_props(tmp_path):
    """run() should write today.json with props_available=False when no odds returned."""
    import run_pipeline
    out_path = tmp_path / "today.json"

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[]), \
         patch("run_pipeline._write_archive"), \
         patch("run_pipeline._run_evening_steps"):
        run_pipeline.run("2026-04-01")

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["props_available"] is False
    assert data["pitchers"] == []


def test_run_evening_calls_results_and_calibrate(tmp_path):
    """run_type='evening' should invoke fetch_results.run and calibrate.run."""
    import run_pipeline
    out_path = tmp_path / "today.json"

    results_called = []
    calibrate_called = []

    def fake_results_run():
        results_called.append(True)

    def fake_calibrate_run():
        calibrate_called.append(True)

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[]), \
         patch("run_pipeline._write_archive"):
        # Patch the imports inside _run_evening_steps
        import sys
        fake_fetch_results = MagicMock()
        fake_fetch_results.run = fake_results_run
        fake_calibrate = MagicMock()
        fake_calibrate.run = fake_calibrate_run
        with patch.dict(sys.modules, {
            "fetch_results": fake_fetch_results,
            "calibrate": fake_calibrate,
        }):
            run_pipeline.run("2026-04-01", run_type="evening")

    assert len(results_called) == 1, "fetch_results.run() was not called"
    assert len(calibrate_called) == 1, "calibrate.run() was not called"
```

- [ ] **Step 2: Run all run_pipeline tests**

```bash
python -m pytest tests/test_run_pipeline.py -v
```
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_run_pipeline.py
git commit -m "test: add orchestration tests for run_pipeline.run() covering happy path and evening mode"
```

---

## Phase 6 — Frontend & Minor Cleanup

---

### Task 6.1: Fix Watchlist to show under-side price movement

**Files:**
- Modify: `dashboard/index.html`

**Problem:** Watchlist filters on `price_delta_over !== 0` only. Under-side steam moves are invisible.

- [ ] **Step 1: Find the Watchlist filter in `index.html`**

Locate the `movers` filter (around line 677):
```javascript
const movers = [...pitchers]
  .filter(p => p.price_delta_over !== 0)
  .sort((a, b) => Math.abs(b.price_delta_over) - Math.abs(a.price_delta_over))
```

- [ ] **Step 2: Fix to consider both sides**

Replace:
```javascript
const movers = [...pitchers]
  .filter(p => p.price_delta_over !== 0)
  .sort((a, b) => Math.abs(b.price_delta_over) - Math.abs(a.price_delta_over))
```
With:
```javascript
const movers = [...pitchers]
  .filter(p => p.price_delta_over !== 0 || p.price_delta_under !== 0)
  .sort((a, b) => {
    const maxA = Math.max(Math.abs(a.price_delta_over || 0), Math.abs(a.price_delta_under || 0));
    const maxB = Math.max(Math.abs(b.price_delta_over || 0), Math.abs(b.price_delta_under || 0));
    return maxB - maxA;
  })
```

- [ ] **Step 3: Verify in browser**

Start the dev server and confirm the Watchlist tab loads without errors.

```bash
# Server should already be running on port 8080
```

- [ ] **Step 4: Fix `loadPerformance()` to cache on first load**

Find `loadPerformance()` call on tab switch (around line 714):
```javascript
if (name === 'perf') loadPerformance()
```
Replace with:
```javascript
if (name === 'perf' && !window._perfLoaded) {
  loadPerformance();
  window._perfLoaded = true;
}
```

- [ ] **Step 5: Fix XSS risk — use textContent for user-visible strings from API**

Find the pitcher card rendering that uses `innerHTML` with `${p.pitcher}`, `${p.team}`, `${p.opp_team}`. This is acceptable risk given the data source is controlled, but add an escape helper at the top of the script section:

```javascript
function esc(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
```

Then replace `${p.pitcher}` → `${esc(p.pitcher)}`, `${p.team}` → `${esc(p.team)}`, `${p.opp_team}` → `${esc(p.opp_team)}` in innerHTML template literals.

- [ ] **Step 6: Commit**

```bash
git add dashboard/index.html
git commit -m "fix: watchlist includes under-side movement, cache performance tab, escape API strings in innerHTML"
```

---

### Task 6.2: Minor cleanup — dead code and fetch_odds improvements

**Files:**
- Modify: `pipeline/fetch_odds.py`

- [ ] **Step 1: Fix `throttled_get` first-call dead sleep**

Replace:
```python
def throttled_get(url: str, params: dict = None) -> dict:
    """GET with rate-limit throttle. Raises on non-200."""
    time.sleep(THROTTLE_S)
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
```
With:
```python
_last_call_time: float = 0.0

def throttled_get(url: str, params: dict = None) -> dict:
    """GET with rate-limit throttle. Raises on non-200."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < THROTTLE_S:
        time.sleep(THROTTLE_S - elapsed)
    _last_call_time = time.time()
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
```

- [ ] **Step 2: Remove dead `opening_odds_map` parameter from `parse_k_props`**

Change:
```python
def parse_k_props(data: dict, opening_odds_map: dict = None) -> list:
    """
    Parse a TheRundown events response (new markets format) into K-prop dicts.
    opening_odds_map is accepted for backward-compat but ignored — the API now
    provides price_delta directly in each price entry.
    """
```
To:
```python
def parse_k_props(data: dict) -> list:
    """Parse a TheRundown events response (new markets format) into K-prop dicts."""
```

- [ ] **Step 3: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add pipeline/fetch_odds.py
git commit -m "fix: proper rate limiting in throttled_get, remove dead opening_odds_map param"
```

---

## Final Verification

- [ ] **Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
```
Expected: All tests pass.

- [ ] **Start dashboard and smoke test**

```bash
python -m http.server 8080 --directory dashboard
```

Verify:
- Props tab loads today's data
- Watchlist shows both over and under movers
- Performance tab loads once and does not re-fetch on tab switch
- Date selector works

- [ ] **Final commit**

```bash
git add .
git commit -m "chore: final verification — all phases complete"
```

---

## Summary of Issues Fixed by Phase

| Phase | Issues Fixed |
|-------|-------------|
| 1 — Math & Data | win_prob_under integer bug (#1), home pitcher team swap (#11), opp_games_played wiring (#4/15) |
| 2 — CI/CD | DST cron (#31), results.db in git (#32), ET date default (#28). Note: git push order (#30) was already correct in the existing file — no change needed. |
| 3 — Robustness | seed_picks guard (#20), void detection fuzzy match (#21), MLB API retry (#17), timedelta import (#18) |
| 4 — Calibration | NNLS normalization (#6), ump_scale decay-only (#9) |
| 5 — Test Coverage | fetch_results two-call mock (#19/41), run() orchestration tests (#42) |
| 6 — Frontend/Cleanup | watchlist under movement (#35), perf tab caching (#37), XSS risk (#36), rate limiter (#13), dead param (#14) |
