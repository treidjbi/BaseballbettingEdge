# Lineup-Aware EV + Manual Trigger + T-30min Line Lock

**Date:** 2026-04-08  
**Status:** Approved  
**Scope:** Phase 2 feature set — individual batter K rates by handedness, dashboard refresh trigger, automatic pre-game line locking

---

## Problem

The model currently uses team-level K% (Bayesian-regressed toward league average) as the opponent strikeout signal. This is coarse — a pitcher facing a lineup stacked with high-K batters vs. a contact-heavy one gets the same `opp_k_rate`. The gap compounds for extreme matchups and is one of the largest remaining sources of systematic EV mispricing.

A secondary problem: the pipeline runs on a fixed schedule (6am, 7pm, 3am PHX time) via GitHub Actions, which has 1-2 hour queue delays. Lineup data isn't available until 1-3 hours before first pitch — too late for a fixed 6am pull to capture. The user actively monitors line movement via Action Network and wants updated EV with lineup data before making betting decisions, but also needs consistent grading that doesn't depend on manual discipline.

---

## Goals

1. Replace team K% with individual batter K rates matched to pitcher handedness.
2. Add a dashboard "Refresh" button that manually triggers the pipeline via GitHub `workflow_dispatch`.
3. Automatically lock each pick's odds, EV, and verdict at T-30min before game time. Grading and calibration always use locked values.
4. On days the user doesn't run the pipeline, the system falls back gracefully: the 3am grading run locks all unlocked picks unconditionally before grading.

## Non-Goals

- Personal P&L tracking (handled by Pikkit).
- Real-time line movement (user uses Action Network for this).
- Moving off GitHub Actions / Netlify infrastructure.
- Phase 3 features (Stuff+, velocity trend, CSW%).

---

## Existing Schema (reference)

The `picks` table is **one row per side** (over OR under). Each row has:
- `side TEXT` — "over" or "under"
- `odds INTEGER` — the best available odds for that side at seed time
- `adj_ev REAL` — movement-adjusted EV for that side
- `verdict TEXT` — LEAN / FIRE 1u / FIRE 2u for that side

This is the foundation for the lock column design: locks mirror the per-row structure.

---

## Architecture

### New files
- `pipeline/fetch_lineups.py` — MLB Stats API projected lineup fetch
- `pipeline/fetch_batter_stats.py` — FanGraphs batter K% splits by handedness
- `netlify/functions/trigger-pipeline.js` — GitHub workflow_dispatch proxy (keeps PAT server-side)
- `netlify.toml` — Netlify functions directory config (create if absent)

### Modified files
- `pipeline/fetch_stats.py` — add `throws` (pitcher handedness) to return dict
- `pipeline/build_features.py` — new `calc_lineup_k_rate()`, updated `build_pitcher_record()` signature, add `lineup_used` to return dict
- `pipeline/fetch_results.py` — add `game_time`, `lineup_used`, and lock columns to schema; add `lock_due_picks()`; update grading to use locked odds; update `export_db_to_history()` and `load_history_into_db()`
- `pipeline/run_pipeline.py` — wire lineup + batter stat fetches; call `lock_due_picks()` + `export_db_to_history()` in all run modes after locking
- `pipeline/calibrate.py` — use `COALESCE(locked_adj_ev, adj_ev)` in `_load_closed_picks()` query
- `dashboard/index.html` — Refresh button + spinner

---

## Component Details

### fetch_stats.py — add `throws`

The MLB Stats API `probablePitcher` object already includes `pitchHand.code` (`"R"` or `"L"`). Add this field to the returned stats dict as `throws`. Default to `"R"` when absent (right-handed majority; safe fallback for split lookup).

Add a test case: `pitchHand` missing in API response → `throws` defaults to `"R"`.

### fetch_lineups.py

Uses the MLB Stats API directly via `requests` (same pattern as existing pipeline). Endpoint:
```
GET https://statsapi.mlb.com/api/v1/schedule
    ?sportId=1&date={YYYY-MM-DD}&hydrate=lineups,probablePitcher
```

Returns:
```python
{
  480123: [  # game_pk integer key
    {"name": "Mookie Betts",     "bats": "R"},
    {"name": "Freddie Freeman",  "bats": "L"},
    ...
  ]
}
```

Returns `{}` when no lineup data is available (normal for morning runs). Silent — callers receive `None` from lineup lookup and fall back to team K%.

`game_pk` for the matching game is resolved by matching `away_team` / `home_team` to the pitcher's `team` field from today.json.

### fetch_batter_stats.py

**Primary approach:** `pybaseball.batting_stats(current_season, qual=0)` returns FanGraphs aggregate batter data including `K%` (aggregate, not split by handedness). This is the reliable fallback.

**Handedness splits:** Attempt `pybaseball.batting_stats_split_seasons()` or equivalent FanGraphs split endpoint. **Important: verify the exact pybaseball function name and signature against the installed library version before implementing.** The function may not exist; if absent, the implementation falls back to aggregate K% for both `vs_R` and `vs_L` splits — the feature still works, just without handedness differentiation.

Wrap the split call in a broad try/except. If it fails for any reason, use aggregate K% for both splits. Log a warning but do not fail the run.

Returns:
```python
{
  "Mookie Betts":    {"vs_R": 0.181, "vs_L": 0.143},
  "Freddie Freeman": {"vs_R": 0.112, "vs_L": 0.098},
}
```

For batters not found: return `{"vs_R": LEAGUE_AVG_K_RATE, "vs_L": LEAGUE_AVG_K_RATE}`. Import `LEAGUE_AVG_K_RATE` from `build_features` — do not redefine.

Cache within a single pipeline run — one FanGraphs pull for all batters, not per-pitcher.

### calc_lineup_k_rate() in build_features.py

```python
def calc_lineup_k_rate(
    lineup: list[dict] | None,   # [{"name": str, "bats": str}, ...], or None
    batter_stats: dict,          # {name: {"vs_R": float, "vs_L": float}}
    pitcher_throws: str,         # "R" or "L"
) -> float | None:
```

Returns `None` when lineup is `None` or empty. The caller uses `None` to decide whether to fall back to team K%.

When lineup is available:
1. For each batter, look up `batter_stats[name][split_key]` where `split_key = "vs_R" if pitcher_throws == "R" else "vs_L"`. Fall back to `LEAGUE_AVG_K_RATE` if batter not in dict.
2. Return the simple mean across all batters — **unregressed**.

**The return value is unregressed.** `calc_lambda()` internally calls `bayesian_opp_k(opp_k_rate, opp_games_played)` which applies Bayesian regression. Passing an already-regressed rate would double-regress. Returning the raw mean preserves the existing regression path in `calc_lambda()` without changes.

**Known limitation (Phase 2):** `opp_games_played` approximates sample size at the team level. Individual batter plate appearances would be more precise but require additional API calls per batter. Accepted for Phase 2; revisit in Phase 3.

### build_pitcher_record() changes

Updated signature (new optional params with safe defaults):
```python
def build_pitcher_record(
    odds: dict,
    stats: dict,                          # now includes `throws` field
    ump_k_adj: float,
    swstr_data: dict | None = None,
    lineup: list[dict] | None = None,     # NEW
    batter_stats: dict | None = None,     # NEW
) -> dict:
```

Logic change for `opp_k_rate` input to `calc_lambda()`:
```python
lineup_rate = None
if lineup is not None and batter_stats is not None:
    lineup_rate = calc_lineup_k_rate(lineup, batter_stats, stats.get("throws", "R"))

effective_opp_k_rate = lineup_rate if lineup_rate is not None else stats["opp_k_rate"]
lineup_used = lineup_rate is not None
```

Pass `effective_opp_k_rate` to `calc_lambda()` as `opp_k_rate`. Pass `opp_games_played` unchanged — `calc_lambda()` applies `bayesian_opp_k()` to whatever rate it receives.

Add `lineup_used` (bool) to the returned pitcher dict. Stored in the DB when seeding.

All existing callers without `lineup`/`batter_stats` params continue to work unchanged — defaults are `None` → falls back to `stats["opp_k_rate"]` as before.

---

## DB Schema Changes — fetch_results.py

### New columns (via ALTER TABLE migrations in `init_db()`)

```sql
-- game context — prerequisite for lock timing
game_time     TEXT    -- ISO UTC timestamp, e.g. "2026-04-09T19:10:00Z"

-- lineup flag
lineup_used   INTEGER -- 1 if individual batter K rates were used, 0 otherwise

-- lock columns (per-row — mirrors one-row-per-side schema)
locked_at      TEXT    -- ISO timestamp when lock was applied, NULL until locked
locked_k_line  REAL    -- k_line at lock time
locked_odds    INTEGER -- odds at lock time (this row's side odds)
locked_adj_ev  REAL    -- adj_ev at lock time (this row's side)
locked_verdict TEXT    -- verdict at lock time (this row's side)
```

Each migration is a separate `ALTER TABLE picks ADD COLUMN ...` wrapped in try/except `OperationalError` (existing pattern in `init_db()`).

`game_time` is populated in `seed_picks()` from `odds["game_time"]` (already present in `today.json`).
`lineup_used` is populated in `seed_picks()` from `p.get("lineup_used", False)`.

### lock_due_picks()

```python
def lock_due_picks(
    conn: sqlite3.Connection,
    now: datetime,                  # must be timezone-aware UTC
    lock_window_minutes: int = 30,
    lock_all_past: bool = False,
) -> int:
    """
    Lock open picks at T-30min before game_time.
    When lock_all_past=True (3am grading run): lock ALL unlocked open picks
    unconditionally — handles missing game_time and yesterday's games.
    Returns count of picks locked.
    """
```

Called at the start of every pipeline run before any seeding or grading.

Lock condition (when `lock_all_past=False`):
- `locked_at IS NULL`
- `result IS NULL` (open pick)
- `game_time IS NOT NULL`
- `datetime.fromisoformat(game_time.replace("Z", "+00:00")) - now <= timedelta(minutes=lock_window_minutes)`

Lock condition (when `lock_all_past=True`):
- `locked_at IS NULL`
- `result IS NULL`
- (game_time check skipped — lock everything remaining)

Lock writes:
```sql
UPDATE picks
SET locked_at = ?, locked_k_line = k_line, locked_odds = odds,
    locked_adj_ev = adj_ev, locked_verdict = verdict
WHERE id = ?
```

Idempotent: rows with `locked_at IS NOT NULL` are never updated.

`now` must be `datetime.now(timezone.utc)` — use the same timezone-aware pattern as `_game_date_et()` in `run_pipeline.py`.

### Grading uses locked odds

In `fetch_results.py` grading logic, use locked odds when available:
```python
graded_odds = row["locked_odds"] if row["locked_odds"] is not None else row["odds"]
```

P&L computed from `graded_odds`. For pre-migration picks (no `locked_at`), behavior is unchanged.

### Calibration uses locked EV

In `calibrate.py` — `_load_closed_picks()` SELECT:
```sql
COALESCE(locked_adj_ev, adj_ev) AS adj_ev
```

This replaces the bare `adj_ev` in the SELECT. No other changes to calibration logic required. Pre-migration picks (no `locked_adj_ev`) fall back to `adj_ev` automatically.

### export_db_to_history() and load_history_into_db()

Both functions use hardcoded column lists and must be updated in tandem. The SELECT column list in `export_db_to_history()` and the `cols` list used in the positional `zip(cols, row)` pattern must be updated together and remain in exactly the same order. New columns added to the end of both lists:

```python
# append to existing cols list:
"game_time", "lineup_used",
"locked_at", "locked_k_line", "locked_odds", "locked_adj_ev", "locked_verdict"
```

This ensures locked values survive GHA runner resets via `picks_history.json`.

`load_history_into_db()` uses dict-keyed access (`p.get(...)`) so order doesn't matter there — add new keys with `None` defaults.

---

## run_pipeline.py wiring

`lock_due_picks()` is called at the start of every run mode (morning/manual, grading, preview) before seeding. The `lock_all_past` argument varies by run mode:

| Run mode | `lock_all_past` | Reason |
|---|---|---|
| Morning (scheduled 6am) | `False` | Only lock picks whose T-30min window has arrived |
| Manual (workflow_dispatch) | `False` | Same — only lock games that are imminent |
| Grading (scheduled 3am) | `True` | Lock everything remaining from yesterday unconditionally |
| Preview (scheduled 7pm) | `False` | Preview builds tomorrow's data; today's picks lock as normal |

After `lock_due_picks()`, call `export_db_to_history()` regardless of how many picks were seeded — if locks were applied, the history file must be updated to persist them. Currently `export_db_to_history()` is only called when `seeded > 0`; this condition must be expanded to `if seeded > 0 or locks_applied > 0`.

Lineup and batter stat fetches run only in morning/manual mode (not in grading or preview modes — no `today.json` is being built). In preview mode (`_run_preview()`), lineups are not fetched (games are not yet scheduled for tomorrow's lineup data).

Note: `game_time` is already present in `today.json` (populated by `build_pitcher_record()` from `odds["game_time"]`). The `seed_picks()` change simply needs to read this existing field into the new DB column.

---

## Netlify Function — trigger-pipeline.js

File: `netlify/functions/trigger-pipeline.js`

Environment variables (configured in Netlify dashboard, never in client code):
- `GITHUB_PAT` — GitHub fine-grained personal access token, `Actions: Write` permission scoped to this repo only
- `GITHUB_REPO` — `owner/repo` string (e.g. `treidjbi/baseballbettingedge`)
- `GITHUB_WORKFLOW` — workflow filename (e.g. `pipeline.yml`)

```javascript
exports.handler = async () => {
  const res = await fetch(
    `https://api.github.com/repos/${process.env.GITHUB_REPO}/actions/workflows/${process.env.GITHUB_WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.GITHUB_PAT}`,
        Accept: "application/vnd.github+json",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );
  if (res.status === 204) return { statusCode: 200, body: '{"status":"triggered"}' };
  return { statusCode: res.status, body: '{"error":"dispatch failed"}' };
};
```

**Known limitation:** The endpoint has no authentication — anyone who knows the Netlify function URL can trigger a GHA run. The PAT is server-side so there is no credential risk; the only risk is unwanted pipeline runs. Accepted for a solo-user tool.

`netlify.toml` in repo root:
```toml
[functions]
  directory = "netlify/functions"
```

Create this file if it doesn't exist. If it already exists, add the `[functions]` block.

### Dashboard Refresh Button

Added to nav bar in `dashboard/index.html` (near date selector).

States:
- **Idle:** "↻ Refresh"
- **Triggered:** spinner + "Running… (~3 min)" — button disabled for 180s
- **Error:** "Refresh failed" — resets after 5s

Calls `POST /api/trigger-pipeline` (Netlify function path, `/.netlify/functions/trigger-pipeline`). No polling of GHA run status — flat 3-minute wait message.

Client-side 3-minute disable is lost on page refresh — accepted limitation.

The `workflow_dispatch` trigger already exists in the current `pipeline.yml`. No change to the workflow file required.

---

## Fallback Behavior (User Doesn't Run Pipeline)

| Scenario | Line used for grading | Lineup data |
|---|---|---|
| Manual run before T-30min | Last manual run's line | Yes, if lineups were posted |
| No manual run — 3am sweep | Morning 6am seeded line | No |
| `game_time` NULL — 3am sweep | Morning 6am seeded line | No |

The 3am grading run always produces a complete grade for every pick from the previous day. No picks are skipped.

---

## Testing

- `test_fetch_stats.py` — add case: `pitchHand` missing in API response → `throws` defaults to `"R"`
- `test_fetch_lineups.py` — mock MLB Stats API; test `{}` fallback when no lineups; test `bats` field parsing; test game_pk team-matching logic
- `test_fetch_batter_stats.py` — mock pybaseball aggregate call; test split lookup, aggregate fallback, unknown batter → `LEAGUE_AVG_K_RATE`; test split call failure (AttributeError) degrades silently to aggregate; confirm `LEAGUE_AVG_K_RATE` imported from `build_features` not redefined
- `test_build_features.py` — add `TestCalcLineupKRate`:
  - `lineup=None` → returns `None`
  - lineup available, pitcher throws R → uses `vs_R` split
  - pitcher throws L → uses `vs_L` split
  - batter not in stats → uses `LEAGUE_AVG_K_RATE`
  - empty list → returns `None`
  - verify return value is unregressed (raw mean, not Bayesian-adjusted)
  - `build_pitcher_record()` with no lineup params → `lineup_used=False`, behavior unchanged
  - `build_pitcher_record()` with lineup → `lineup_used=True`, `effective_opp_k_rate` differs from `stats["opp_k_rate"]`
- `test_fetch_results.py` — add lock logic tests:
  - `lock_due_picks(lock_all_past=False)`: pick due → locked; pick not due → skipped; `game_time=None` → skipped
  - `lock_due_picks(lock_all_past=True)`: all unlocked open picks locked including `game_time=None` rows
  - idempotent: already-locked pick not re-locked
  - grading uses `locked_odds` when not None, falls back to `odds`
  - `_load_closed_picks()` returns `locked_adj_ev` when set, `adj_ev` otherwise
  - `export_db_to_history()` includes all new columns in output
  - `load_history_into_db()` populates new columns including `None` defaults for pre-migration rows
  - fixtures for lock tests must include `game_time` and `lineup_used` fields
- All existing 162 tests must continue to pass; new `build_pitcher_record()` params are optional with `None` defaults

---

## Rollout Notes

- DB migration is backward-compatible: all new columns default to NULL; pre-migration picks grade and calibrate with existing behavior
- `export_db_to_history()` / `load_history_into_db()` updates must ship in the same commit as the lock columns — if the DB has locked values but history export doesn't include them, a GHA runner reset would lose the locks
- Netlify function setup requires one-time env var configuration in Netlify dashboard
- After deploying: monitor whether `locked_odds` differs from morning `odds` on days with manual runs — if they're almost always the same, the lock is correct but confirms the morning line is already the best available baseline
- `pybaseball` split function must be verified against the installed version before `fetch_batter_stats.py` is written; if splits are unavailable, the feature delivers aggregate-only K rates (still a meaningful improvement over team K%)
