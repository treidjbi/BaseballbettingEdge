# AGENTS.md — BaseballBettingEdge

## Source Of Truth

This file is the canonical agent entrypoint for the repo.

For new work, read files in this order:

1. `AGENTS.md`
2. `docs/current-state.md`
3. the active dated plan referenced there

`CLAUDE.md` may exist for compatibility, but `AGENTS.md` is the source of truth
going forward.

## Current State

As of 2026-04-28, the repo is in a soak and evaluation period after the recent
grading and post-Phase-C changes.

- Treat `2026-04-28+` as the clean evaluation regime.
- Use the evaluation diagnostics in `analytics/diagnostics/e1` through `e4`
  and the matching `tests/test_e1` through `test_e4` files.
- Use `docs/superpowers/plans/2026-04-28-one-week-evaluation-cadence.md` as
  the active short-term decision cadence.
- Preserve the dated plans in `docs/superpowers/plans/` as historical context
  so future work does not repeat earlier mistakes.

## What This Project Does

MLB pitcher strikeout prop betting model. Fetches daily K props from TheRundown API, combines with pitcher stats (MLB Stats API), swinging-strike rates (FanGraphs/PyBaseball), umpire tendencies (MLB officials + cached career rates), and opposing lineup K rates to produce a Poisson-based expected strikeout (lambda) for each pitcher. Computes probability edge plus expected ROI against book odds and outputs verdicts (PASS / LEAN / FIRE 1u / FIRE 2u).

Results are displayed on a static dashboard hosted on Netlify with push notification support.

## Architecture

```
pipeline/           Python data pipeline (runs on GitHub Actions)
  run_pipeline.py     Orchestrator — entry point, run types: full | grading | preview | lock
  fetch_odds.py       TheRundown API v2 — K prop lines (market_id=19)
  fetch_stats.py      MLB Stats API — pitcher season/recent/career K/9, avg IP, team data
  fetch_statcast.py   PyBaseball/FanGraphs — swinging strike rates (SwStr%)
  fetch_umpires.py    MLB Stats API officials + cached career rates — HP umpire K rate adjustments
  fetch_lineups.py    Confirmed lineups
  fetch_batter_stats.py  FanGraphs — batter K% splits (vs L/R)
  build_features.py   Joins all data → computes lambda, edge, EV ROI, verdicts
  calibrate.py        Auto-calibrates params (lambda_bias, ump_scale, blend weights, swstr_k9_scale)
  fetch_results.py    Seeds picks into SQLite, fetches box scores, grades results
  backfill_results.py Backfill historical results
  name_utils.py       Pitcher/batter name normalization (accent stripping)

dashboard/          Static frontend (single index.html, deployed to Netlify)
  index.html          Full SPA — pitcher cards, performance tab, dark mode, PWA
  sw.js               Service worker for push notifications
  manifest.json       PWA manifest
  data/processed/     Pipeline output (today.json, YYYY-MM-DD.json archives, index.json)

netlify/functions/  Serverless functions
  send-notifications.mjs   Push notification dispatch + game-time reminders
  save-subscription.mjs    Save push subscription endpoints
  trigger-pipeline.js      Manual pipeline trigger

data/               Shared data files
  params.json           Calibrated model parameters (lambda_bias, weights, etc.)
  picks_history.json    All picks with results (JSON, committed by pipeline)
  preview_lines.json    Midnight preview opening lines for the upcoming game day
  processed/            (gitignored intermediate data)
  umpires/              Umpire data cache

tests/              pytest test suite
```

## Pipeline Schedule (GitHub Actions)

All times America/Phoenix (UTC-7, no DST):
- **12:17 AM** — Preview: fetch current-day opening lines → `preview_lines.json`.
  At midnight we've just rolled into the game day, so the run uses TODAY's
  date. Later start time (vs. the prior 7 PM) gives more pitchers time to
  be announced, which improves coverage. The `:17` minute avoids GitHub's
  top-of-hour schedule queue.
- **3:17 AM** — Grading: grade yesterday's picks + calibrate `params.json`
- **6:17 AM** — Full run: finalize today's picks (uses preview lines as opening baseline)
- **8:07 AM–6:07 PM every 30 min** — Refresh: fetch fresh odds/lineups, update unlocked picks, lock T-30min

## Key Commands

```bash
# Install dependencies
pip install -r pipeline/requirements.txt

# Run pipeline (requires RUNDOWN_API_KEY env var)
python pipeline/run_pipeline.py 2026-04-15
python pipeline/run_pipeline.py 2026-04-15 --run-type grading
python pipeline/run_pipeline.py 2026-04-16 --run-type preview

# Run tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_build_features.py -v
```

## Environment Variables / Secrets

- `RUNDOWN_API_KEY` — TheRundown API key (required for fetch_odds)
- `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` — Web Push keys
- `NOTIFY_SECRET` — Push notification auth secret (Netlify function)
- `NETLIFY_SITE_URL` — Netlify site URL for notification endpoint

## TheRundown API (Odds Provider)

- **Plan**: Starter ($49/mo)
- **Quota**: 2,000,000 data points/month, then $0.002/pt overage
- **Rate limit**: 2 req/sec, 60-second data delay
- **Coverage**: All 15+ bookmakers, all periods & markets, best lines, 7-day odds history
- **Not included**: WebSocket streaming, +EV calculations
- **Auth**: `X-TheRundown-Key` header
- Pipeline throttles at 0.55s between calls to stay under 2 req/sec

## Tech Stack

- **Python 3.11** — pipeline
- **Libraries**: requests, beautifulsoup4, scipy (Poisson), pybaseball, pytz, numpy
- **SQLite** — ephemeral results DB (`data/results.db`, gitignored), rebuilt each run from `picks_history.json`
- **GitHub Actions** — scheduled pipeline runs (pip cached for fast installs)
- **Netlify** — static dashboard hosting + serverless functions
- **Single-file HTML dashboard** — vanilla JS, no build step, IBM Plex Mono + Oswald fonts

## API Wiring Notes

These are the API-shape details that have caused real bugs in this repo.
Read this before debugging any data-source issue.

### TheRundown v2 (`pipeline/fetch_odds.py`)

- Response shape is `events[] -> markets[] -> participants[] -> lines[] -> prices{book_id}`.
- Pitcher strikeout props live at `market_id=19`.
- `fetch_odds` intentionally leaves `team=""` and `opp_team=""`. TheRundown
  does not provide a per-prop team mapping we trust enough to stamp those
  fields directly, so `fetch_stats` resolves them later against MLB probables.
- `line["value"]` is a string like `"Over 7.5"` / `"Under 7.5"` and is parsed
  into `(direction, line_val)`.
- `price_delta` means `current - opening`, so reconstructed opening odds are
  `current - price_delta`.
- Ref-book selection is **priority-based**, not best-price-based. Current
  priority is FanDuel -> BetMGM -> DraftKings -> Kalshi -> BetRivers -> Caesars -> Fanatics.
- Option B is live: if no target book exists, the prop is skipped rather than
  falling back to an unknown book.
- `book_odds` is the tracked per-book snapshot used for `steam.json`.
- `opening_odds_source` starts as `"first_seen"` in `fetch_odds`; promotion to
  `"preview"` only happens later in `run_pipeline._apply_preview_openings()`.

### MLB Stats API probable starters (`pipeline/fetch_stats.py`)

- `fetch_stats(date_str, pitcher_names)` returns a **2-tuple**:
  `(stats_by_name, probables_by_team)`.
- `stats_by_name` is keyed by the original TheRundown pitcher name so
  `stats_map.get(odds["pitcher"])` still works after normalization.
- `probables_by_team` exists to catch scratch / phantom cases where MLB's
  current probable no longer matches the odds pitcher (`starter_mismatch`).
- `/schedule?hydrate=probablePitcher,team` does **not** reliably include
  `pitchHand`. When it is missing, the code must fall back to `/people/{id}`.
- `recent_start_ips` comes from pitcher `gameLog`, but it is **not** the raw
  last 5 appearances. The fetch widens the lookback, filters to
  `gamesStarted > 0`, then keeps the last 5 true starts so mixed relief usage
  does not poison opener detection.
- Started game logs should be sorted newest-first by split date before the
  recent-start slice is taken. Do not trust the raw MLB API row order.
- `recent_k9` is the aggregate K/9 across that recent true-start slice, not the
  first game-log row's K/9.
- `park_team` is the venue breadcrumb used for park-factor lookup. For home
  starters it is their own team name; for away starters it is the opponent's
  home team name.
- Name matching between TheRundown and MLB must stay accent-insensitive.
  `name_utils.normalize()` is load-bearing here.

### MLB Stats API lineups (`pipeline/fetch_lineups.py`)

- The lineup flow is a **two-call** flow:
  1. `/schedule` to find `gamePk` and whether the requested team is `away` or `home`
  2. `/game/{gamePk}/boxscore` to get the actual ordered lineup
- Do **not** expect usable batting-order data from schedule hydrate.
  `battingOrder` lives on `boxscore.teams.{away|home}.battingOrder`.
- Batter details live under `boxscore.teams.{away|home}.players["ID{player_id}"]`.
- Returned lineup shape is `[{"name": ..., "bats": ...}, ...]` in batting order.
- Empty `battingOrder` is a normal pregame state and should return `None`.

### MLB Stats API officials / umpires (`pipeline/fetch_umpires.py`)

- `ump.news` is dead. Live source is now
  `/schedule?sportId=1&date=YYYY-MM-DD&hydrate=officials`.
- Home-plate umpire is found by scanning each game's `officials[]` for
  `officialType == "Home Plate"`.
- The assignment map is built from the away-team abbreviation, then later
  matched back to props using both `team` and `opp_team` because both starters
  face the same HP umpire.
- `career_k_rates.json` is the second half of the umpire signal. Missing ump in
  that file still resolves to `0.0`, even if officials were fetched correctly.
- `today.json` distinguishes confirmed-but-unrated umpires from true TBA via
  per-record `umpire` and `umpire_has_rating`. Confirmed-but-unrated umpires
  stay neutral (`ump_k_adj=0.0`) and show up under
  `ump_diagnostics.missing_career_rate_umpires`.
- Team-name reverse lookup is substring-based through `ABBR_TO_NAME_SUBSTR`;
  if a team-name format changes, ump matching can silently die.

### FanGraphs / PyBaseball batter K data (`pipeline/fetch_batter_stats.py`)

- Aggregate batter K% is live.
- True handedness splits are in **collection-only** mode. The pipeline can
  cache Baseball-Reference platoon split samples in
  `data/batter_splits_YYYY.json`, but projection still uses aggregate K% for
  both `vs_R` and `vs_L` plus the league-average platoon adjustment in
  `build_features.calc_lineup_k_rate`.
- Current caller contract is:
  `{normalized_batter_name: {"vs_R": float, "vs_L": float}}`
- Do not promote collected real splits into `vs_R` / `vs_L` projection inputs
  until the soak review confirms coverage and adds Bayesian split regression.

### FanGraphs / PyBaseball SwStr (`pipeline/fetch_statcast.py`)

- Current-season SwStr% comes from the FanGraphs leaderboard JSON endpoint
  (`https://www.fangraphs.com/api/leaders/major-league/data`), not the old
  legacy `pitching_stats()` scrape path.
- Career baseline is the 3-season window before the current season.
- That baseline is the mean of the three prior seasons fetched
  season-by-season, not one combined multi-year scrape.
- Values are normalized to decimals (`0.134`, not `13.4`).
- Missing pitcher or source failure should degrade to league-average
  `LEAGUE_AVG_SWSTR`, not break the pipeline.
- If `career_swstr_pct` suddenly goes null across the board, check
  `pipeline/fetch_statcast.py` before trusting Phase B bias slices.
- Live production confirmation: the repaired transport was verified end-to-end
  on 2026-04-27. Fresh workflow-stored rows from that date forward are the
  first post-fix SwStr-live calibration era.

### Park factors (`data/park_factors.json`, `pipeline/team_codes.py`)

- Park factors live in `data/park_factors.json` under a nested `factors` dict.
  Metadata at the file root is part of the contract; do not flatten it.
- The pipeline stores full MLB team names in the live stats payload, so
  `pipeline/team_codes.py` is the canonical name→code mapping for park-factor
  resolution.
- `TEAM_NAME_TO_CODE` intentionally includes a few historical / alias names
  (`Oakland Athletics`, `Anaheim Angels`, etc.) so upstream label drift
  degrades to the right code instead of silently defaulting to neutral.
- `run_pipeline._resolve_park_factor()` must fail safe to `1.0` when a venue
  name is missing, unknown, or mapped to an invalid factor (missing, non-finite,
  or <= 0). Log a warning and keep the run alive.
- Current provenance note: FanGraphs research is recorded in the file; the
  planned Baseball Savant cross-check is still pending and should be treated as
  a data-refresh follow-up, not as a live-run blocker.

## Model Overview

1. Blend pitcher K/9: weighted mix of season, recent (last 5 starts), and career K/9
2. SwStr% delta: additive K/9 adjustment based on current vs career swinging strike rate
3. Opponent K%: Bayesian-regressed team/lineup strikeout rate
4. Umpire adjustment: HP umpire career K rate delta
5. Lambda = (adjusted_K/9 × opp_K_factor × innings/9) + ump_adjustment + lambda_bias
6. Poisson CDF → over/under win probabilities → probability edge + EV ROI vs book odds → verdict

### Opener handling

- `build_features.is_opener()` flags likely opener / bullpen games when the
  recent-start IP sample averages below `2.5` innings across at least `2`
  starts.
- Openers are forward-only metadata in `today.json` via `is_opener` and
  `opener_note`.
- When opener is true, both sides are forced to `PASS` and adjusted EV is
  zeroed so verdict-driven and adj-EV-driven UI paths stay neutral.
- Raw EV / win probability still remain on the record for inspection; the
  actionable suppression happens through verdict + adjusted EV.

### Park-factor handling

- `calc_lambda(..., park_factor=1.0)` applies park factor multiplicatively to
  the rate-driven portion of lambda before the additive umpire term.
- Park factor is a forward-only signal. Do not backfill historical rows with it.
- Unknown venues should show up as `park_factor=1.0` plus a warning, not as a
  hard pipeline failure.

### Rest / workload handling

- `fetch_stats.py` now exposes `days_since_last_start` and `last_pitch_count`
  from the latest true start in the MLB game log.
- Rest for UTC-shifted games must be computed from the actual schedule block
  date, not blindly from the original `date_str` request.
- `calc_rest_k9_delta()` is intentionally conservative:
  - `<4` days since last start => `-0.3` K/9
  - `>110` pitches in the last start => `-0.2` K/9
  - penalties stack
  - missing data stays neutral
- `rest_k9_delta` is forward-only metadata in the record output and is applied
  to the blended K/9 before lambda.

### Data warnings / degraded-source visibility

- `today.json` now includes a top-level `data_warnings` array. Empty array means
  clean run; the dashboard should hide the warning UI in that case.
- `run_pipeline.collect_data_warnings()` is the pure warning contract. Prefer
  testing there instead of broad orchestration mocks when changing warning text
  or counting logic.
- Units matter:
  - HP ump coverage warnings are counted in scheduled `games`
  - lineup and batter-split warnings are counted in opposing `lineups`
- Lineup warning denominators should only count pitchers that actually reached
  the lineup-fetch path. Do not blame a dropped `fetch_stats` row on
  `fetch_lineups`.
- SwStr warnings should distinguish partial degradation from a full neutral
  fallback. Losing only the career baseline means the current SwStr value is
  still live and only the delta is zeroed.

### EV / Edge Semantics

- `ev_*["edge"]` is the probability gap: model win probability minus implied probability.
- `ev_*["ev"]` is expected ROI on a 1.0u risked stake.
- `ev_*["adj_ev"]` is the movement-confidence-adjusted EV ROI used for ranking and verdict display.

### Verdict Thresholds

Thresholds live in `pipeline/build_features.py` (`EDGE_PASS`, `EDGE_LEAN`, `EDGE_FIRE_1U`):

- **PASS** — EV ROI < 2% (no bet)
- **LEAN** — EV ROI 2–6% (tracked, not staked)
- **FIRE 1u** — EV ROI 6–17% (1-unit play)
- **FIRE 2u** — EV ROI ≥ 17% (2-unit play, truly elite edge)

### Input quality gates

The implementation plan is
`docs/superpowers/plans/2026-04-29-input-quality-gates-and-data-maturity.md`.

Contract:

- Add per-pitcher `input_quality_flags`, `projection_safe`,
  `quality_gate_level`, `quality_gate_reasons`, `verdict_cap_reason`, and
  `data_maturity`.
- Preserve raw model output via side-level `raw_verdict` and `raw_adj_ev`.
- Treat side-level `verdict` as the actionable betting decision after gates.
- Severe flags force actionable PASS while preserving the raw projection for
  audit. Severe flags include opener, starter mismatch, unresolved probable,
  missing game time, missing pitcher K profile, malformed line/odds, invalid
  lambda inputs, and missing team/opponent mapping.
- Soft flags cap conviction. One meaningful soft flag caps at `FIRE 1u`; two
  or more cap at `LEAN`. Soft flags include projected/partial lineup, unrated
  or thin-sample umpire, missing career SwStr baseline, neutral park fallback,
  first-seen opening, thin recent-start sample, and partial movement history.
- `FIRE 2u` should require clean major data, not just a large EV number.
- New pitchers, umpires, lineups, and market feeds graduate through explicit
  maturity states instead of being trusted all at once.
- The quality-gate audit lives at
  `analytics/diagnostics/e5_quality_gate_audit.py` and should be included in
  the weekly review.

## Calibration

`calibrate.py` runs during the grading step:
- **Phase 1 (n>=30)**: lambda_bias — corrects systematic over/under-prediction
- **Phase 2 (n>=60)**: ump_scale, K/9 blend weights (season_cap, recent), swstr_k9_scale
- Parameters saved to `data/params.json` with calibration notes
- Only uses current-season picks after any `formula_change_date`
- Current live boundary: `formula_change_date = 2026-04-28` marks the first
  clean post-ROI / post-SwStr-live calibration era. This preserves historical
  picks/results for analysis while preventing calibration from learning across
  the dead-SwStr window and the 2026-04-27 EV-semantics transition slate.

## Data Flow

```
TheRundown API → fetch_odds → props[]
MLB Stats API  → fetch_stats → (stats_map{}, probables_by_team{})
FanGraphs      → fetch_swstr → swstr_map{}
MLB Stats API  → fetch_umpires (hydrate=officials) → ump_map{}
MLB Stats API  → fetch_lineups (/schedule → /game/{pk}/boxscore) → lineup[]
FanGraphs      → fetch_batter_stats → batter_stats{}
                    ↓
              build_features.build_pitcher_record()
                    ↓
              today.json + YYYY-MM-DD.json archives
                    ↓
              seed_picks → SQLite → picks_history.json
                    ↓
              fetch_results (box scores) → grade → calibrate
```

## Dashboard Status Override (2026-04-24)

The v2 rollout is complete. Treat the older "In-Flight Work: V2 Dashboard UI"
section below as historical rollout context, not current status.

- **v2 is the default UI** via `/` and `dashboard/v2.html`
- **v1 is the legacy fallback** via `/legacy` and `dashboard/index.html`
- The compatibility warning still matters: `today.json` must remain backward-
  compatible with both dashboards unless the legacy path is intentionally retired

## In-Flight Work: V2 Dashboard UI

A v2 dashboard UI landed on main 2026-04-17 (commit `4bb54a8`) and is being
rewired live. It coexists with the v1 dashboard:

- **v1 (default):** `dashboard/index.html` — still the default URL, still served
  as the fallback through every phase of the v2 rollout. Do **not** break it.
- **v2 (preview):** `dashboard/v2.html` + `dashboard/v2-app.jsx` +
  `dashboard/v2-data.js` — served at `/v2.html`. The adapter `v2-data.js` reads
  a specific field list from `today.json` (see the rollout plan below).

**Constraint on any pipeline change:** `today.json` / per-pitcher record schema
must stay backward-compatible with BOTH v1 and v2 through the full rollout.
The v2 adapter reads (non-exhaustive): `pitcher, team, opp_team,
pitcher_throws, game_time, k_line, opening_line, best_over_odds,
best_under_odds, opening_over_odds, opening_under_odds, lambda, avg_ip,
opp_k_rate, ump_k_adj, season_k9, recent_k9, career_k9, ev_over, ev_under,
game_state, best_over_book, swstr_pct, swstr_delta_k9, data_complete`. Renaming
or removing any of these = breaking v2. Adding new nullable fields is safe.

**Where to look before changing pipeline output:**
- Rollout plan: [docs/superpowers/plans/2026-04-17-v2-ui-rollout.md](docs/superpowers/plans/2026-04-17-v2-ui-rollout.md)
- Deferred pipeline wishlist (things v2 would like but doesn't block on):
  [docs/ui-redesign/deferred-pipeline-work.md](docs/ui-redesign/deferred-pipeline-work.md)
- V2 adapter source of truth for field dependencies: [dashboard/v2-data.js](dashboard/v2-data.js)

If a pipeline change you're making adds, renames, or changes the semantics of
any of the listed fields — stop and cross-reference the rollout plan + adapter
before shipping.

## Important Patterns

- **Locked snapshots**: Once a game starts, its card data is frozen in today.json. Post-start API runs don't overwrite pre-game snapshots.
- **Pick seeding**: `INSERT OR IGNORE` — first-seen line is locked in. Subsequent runs update unlocked picks only.
- **Ephemeral DB**: SQLite DB is rebuilt from `picks_history.json` each run (GitHub Actions runners are stateless).
- **Graceful degradation**: Each data source can fail independently. SwStr%, umpires, lineups all fall back to neutral values. `data_complete` now reflects pitcher-level completeness (not just slate-level success) and excludes degraded picks from calibration.
- **User-visible degradation**: silent failures should also surface in
  `today.json.data_warnings` so the dashboard can warn without requiring a CI-log read.
- **Movement confidence**: Line movement against bet side applies a 0–1 haircut to EV (noise_floor=10pts, full_fade=30pts).

**Additional pattern notes (2026-04-24):**

- `opening_*_odds` and `opening_odds_source` are not interchangeable.
  `"preview"` means overnight baseline from `preview_lines.json`;
  `"first_seen"` means reconstructed within-day opening from TheRundown
  `price_delta`.
- `lineup_used`, `data_complete`, `opp_k_rate`, `swstr_delta_k9`, current odds,
  and similar fields should refresh on unlocked rows. Once `locked_at` is set,
  they freeze.
- `tracked_picks` in `today.json` / dated archives is the dashboard-facing
  mirror of `picks_history.json`. V2 pick counts and grading summaries should
  prefer these tracked/locked rows over recomputing actionable picks from the
  latest pitcher-card verdicts.
- If a module uses `/schedule` plus a second MLB endpoint (`/people/{id}`,
  `/game/{pk}/boxscore`), that is usually because the first endpoint looked
  sufficient but omitted a load-bearing field in production.

## Data Caveats (historical data quirks)

Before slicing `data/picks_history.json` or writing analytics that recompute
features from stored inputs, check [docs/data-caveats.md](docs/data-caveats.md).
Known windows where stored fields do not match what a clean rerun would produce:

- **2026-04-11 → 2026-04-17 — `pitcher_throws` bug window.** MLB `/schedule`
  hydrate silently failed to return `pitchHand`, so every pitcher at decision
  time was treated as RHP. The stored `pitcher_throws` field has since been
  corrected for the full history (commits `0407846`, `517f473`, `8463f8e`),
  but `lambda` for picks in this window was computed with the R-assumption and
  was **not** recomputed. Calibration is unaffected (residuals use stored
  lambda, not pitcher_throws). Handedness-sliced analytics can treat the full
  dataset uniformly; input-replay analytics should note the discrepancy.

See `docs/data-caveats.md` for the full remediation trail and guidance per
analysis type.

## Data-Volume Reminders

Check these whenever you read this file and compare the trigger to current state
(`data/params.json` `sample_size`, today's date, etc). If a trigger has been met,
surface the reminder to the user as a suggested next step.

### Batter Handedness — Upgrade from Path A to Path B

**Current state (as of 2026-04-16):** Path A is live. `build_features.calc_lineup_k_rate`
applies a league-average platoon K% delta per batter (`PLATOON_K_DELTA` table) based
on the `(batter_hand, pitcher_throws)` matchup. Switch-hitters are modeled as batting
opposite the pitcher's hand. Per-batter vs-L / vs-R splits are **not** yet wired —
`fetch_batter_stats._fetch_splits` is still stubbed (it raises `AttributeError` and
falls back to aggregate K%).

**Trigger to upgrade (Path B):** When `params.json.sample_size >= 400` **OR** the
current date is on/after **2026-05-25** (~50+ PA per split for most regulars),
remind the user we can upgrade to real per-batter handedness splits:

1. Implement `_fetch_splits()` in [pipeline/fetch_batter_stats.py](pipeline/fetch_batter_stats.py)
   using pybaseball's `splits_leaderboards` or a direct FanGraphs splits URL to
   return real `vs_R` / `vs_L` K% per batter.
2. In [pipeline/build_features.py](pipeline/build_features.py), remove the
   `+ platoon_k_delta(...)` adjustment from `calc_lineup_k_rate` (per-batter splits
   already encode the platoon effect). Keep `PLATOON_K_DELTA` / `platoon_k_delta()`
   around as a fallback for batters missing from the splits lookup.
3. Apply Bayesian regression of each batter's vs-L / vs-R K% toward the
   league-wide same-hand or opposite-hand average, weighted by per-split PA, to
   handle thin samples.
4. Bump `formula_change_date` in `params.json` to the deploy date so calibration
   resets `lambda_bias` cleanly under the new formula.

Related tests: `TestCalcLineupKRate`, `TestPlatoonKDelta` in
[tests/test_build_features.py](tests/test_build_features.py).

### Umpire career_k_rates — Periodic Re-seed

**Current state (as of 2026-04-21):** `data/umpires/career_k_rates.json` holds
per-umpire K-per-game deltas vs. league average for ~87 HP umpires (up from
30 after Task A3b expansion on 2026-04-20, ~94% post-4/8 sample match). The
seed script [scripts/seed_umpire_career_rates.py](scripts/seed_umpire_career_rates.py)
derives deltas empirically from MLB Stats API boxscores (schedule + boxscore
per game, aggregated per umpire, subtracted from league mean). `fetch_umpires.py`
reads the cached JSON at pipeline time.

These deltas drift slowly — a single season of calls adds maybe ±0.1 K/game
to a veteran umpire's career average — but they do drift, and new umpires
appear in-season.

**Trigger to re-seed:** Whenever **any** of the following is true:

- The current month is **May**, **July**, or **September** (quarterly cadence
  roughly aligned with calls-per-year turnover)
- A pipeline log shows a run matched <85% of umpires in the last 30 days
  (analytics: check `ump_k_adj == 0` rate on staked-only picks)
- A new season has started and career_k_rates was last seeded in the prior
  season (check `data/umpires/career_k_rates.json` mtime)

**How to re-seed (background, resumable):**

The seeder is **replace-semantics**, not additive — it re-derives deltas from
scratch for the given window. To pick up drift safely, you must run a wide
multi-season window so each ump has hundreds of games.

```bash
# ✅ RIGHT: wide multi-season window captures 2026 games additively
#    (when run during/after the 2026 season with a 3-year window):
python scripts/seed_umpire_career_rates.py \
    --start 2024-03-28 --end $(date +%F) --output data/umpires/career_k_rates.json

# ❌ WRONG: short YTD-only window produces sample noise, not drift
#    (validated 2026-04-21: median |shift| = 1.76 K/game on a 32-day run —
#    pure small-sample variance, not real career drift)
```

- Wide windows run in hours; resumable via `analytics/output/seed_progress.json`
- Safe to run in the background — no pipeline side effects, writes a single
  JSON at the end
- After completion, diff the JSON vs. the prior version. Commit the update
  if any career K/game delta shifted by **≥0.1** or if new umpires were added.
  Shifts below that threshold are below the noise floor of `ump_scale` and
  not worth a commit.
- For new / thin-sample umpires surfaced by
  `ump_diagnostics.missing_career_rate_umpires`, track the name immediately but
  keep the model adjustment neutral until a wide-window seed can include enough
  games. Do not promote short-window YTD deltas straight into production.
- For a quick "is there a new ump in the pool" check without re-running a
  multi-hour seed, write to a side-file (e.g. `analytics/output/seeds/*.json`)
  and diff name sets only — but **don't** use a short-window file to update
  career deltas.

**Do NOT bump `formula_change_date`** — career_k_rates updates do not change
the model formula; `lambda_bias` self-heals through normal calibration.

### End-of-Season Infrastructure Review (prep for 2027+)

**Trigger:** When the current season is over (roughly October or whenever
`params.json.updated_at` has gone 30+ days without change), remind the user
to do an infrastructure/scale review before the 2027 season starts.

**Topics to walk through:**

1. **`picks_history.json` size.** At end of season, compare size vs repo
   comfort. If > ~10 MB and still growing, evaluate: (a) split by season
   (`data/picks_history_2026.json`, `..._2027.json`) or (b) migrate to a
   committed SQLite or Parquet file (faster load, smaller diff).
2. **Per-day archive directory.** `dashboard/data/processed/YYYY-MM-DD.json`
   will have ~180 files per season. Evaluate whether to gzip archives, move
   old seasons to a subfolder, or serve from an object store.
3. **Pipeline runtime.** Measure typical full-run wall time. If GitHub
   Actions minutes or TheRundown API quota are getting tight, consider
   caching unchanged data between the 30-min refreshes or batching fetches.
4. **Park-factor provenance.** Refresh `data/park_factors.json`, confirm team
   aliases still match live upstream names, and finish or refresh the Savant
   cross-check before the next season.
5. **Calibration window.** Re-evaluate whether `formula_change_date`-based
   filtering is still the right approach, or whether multi-season rolling
   calibration would be more stable.
6. **Line shopping / book coverage.** Check if TheRundown's best-line data
   is still sufficient vs. pulling per-book explicitly for EV optimization.
7. **Notifications / PWA.** Audit subscription counts and delivery rates
   via Netlify function logs — clean up dead endpoints.
8. **Dashboard.** Decide if the single-file HTML is still the right call
   or if a build step (Vite/Astro) is worth the complexity for next season.

Goal: spend a deliberate day planning scale improvements while there's no
active season pressure, rather than patching mid-season.

## Local analytics deep-dive

`analytics/performance.py` is a standalone local tool for slicing
`picks_history.json` beyond the dashboard's performance tab. Not part of
the pipeline. Setup: `pip install -r analytics/requirements.txt`. Run:
`python analytics/performance.py` (optional `--since YYYY-MM-DD` /
`--min-ev 0.06`). Prints tables to the console and saves plots to the
gitignored `analytics/output/`. See [analytics/README.md](analytics/README.md).

## Testing Notes

- Tests use `unittest.mock` extensively to mock API calls
- `build_features` functions are pure (no I/O) for easy testing
- Test files mirror pipeline modules: `test_build_features.py`, `test_calibrate.py`, etc.
- For external data bugs, the tests are often the clearest payload-contract
  reference. Check `tests/test_fetch_odds.py`, `tests/test_fetch_stats.py`,
  `tests/test_fetch_lineups.py`, `tests/test_fetch_umpires.py`, and
  `tests/test_fetch_batter_stats.py` before assuming an endpoint works the way
  its docs suggest.
- Run full suite: `python -m pytest tests/ -v`

## End-of-Season Evaluation Notes

### Lambda Bias Architecture (evaluate after 2026 season)

The current `lambda_bias` is a single calibrated offset that tries to handle both systematic model error and in-season K rate drift. A more durable long-term fix would be separating these into two distinct corrections:

- **Static bias offset** — calibrated annually from the prior season's aggregate model error. Set once before Opening Day and held fixed.
- **Dynamic seasonal adjustment** — follows actual league K/9 trends week over week (e.g. a rolling delta vs. the season-opening baseline). Captures real shifts in run environment, umpire squeeze trends, or rule changes mid-season.

Splitting them would make calibration more interpretable and reduce the risk of the dynamic signal contaminating the static correction (or vice versa).
