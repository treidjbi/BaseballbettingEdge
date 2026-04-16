# CLAUDE.md — BaseballBettingEdge

## What This Project Does

MLB pitcher strikeout prop betting model. Fetches daily K props from TheRundown API, combines with pitcher stats (MLB Stats API), swinging-strike rates (FanGraphs/PyBaseball), umpire tendencies (ump.news), and opposing lineup K rates to produce a Poisson-based expected strikeout (lambda) for each pitcher. Computes EV against book odds and outputs verdicts (PASS / LEAN / FIRE 1u / FIRE 2u).

Results are displayed on a static dashboard hosted on Netlify with push notification support.

## Architecture

```
pipeline/           Python data pipeline (runs on GitHub Actions)
  run_pipeline.py     Orchestrator — entry point, run types: full | grading | preview | lock
  fetch_odds.py       TheRundown API v2 — K prop lines (market_id=19)
  fetch_stats.py      MLB Stats API — pitcher season/recent/career K/9, avg IP, team data
  fetch_statcast.py   PyBaseball/FanGraphs — swinging strike rates (SwStr%)
  fetch_umpires.py    ump.news — HP umpire K rate adjustments
  fetch_lineups.py    Confirmed lineups
  fetch_batter_stats.py  FanGraphs — batter K% splits (vs L/R)
  build_features.py   Joins all data → computes lambda, Poisson EV, verdicts
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
  preview_lines.json    7pm preview opening lines for next day
  processed/            (gitignored intermediate data)
  umpires/              Umpire data cache

tests/              pytest test suite
```

## Pipeline Schedule (GitHub Actions)

All times America/Phoenix (UTC-7, no DST):
- **7:00 PM** — Preview: fetch next-day opening lines → `preview_lines.json`
- **3:00 AM** — Grading: grade yesterday's picks + calibrate `params.json`
- **6:00 AM** — Full run: finalize today's picks (uses 7pm lines as opening baseline)
- **8 AM–6 PM every 30 min** — Refresh: fetch fresh odds/lineups, update unlocked picks, lock T-30min

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

## Model Overview

1. Blend pitcher K/9: weighted mix of season, recent (last 5 starts), and career K/9
2. SwStr% delta: additive K/9 adjustment based on current vs career swinging strike rate
3. Opponent K%: Bayesian-regressed team/lineup strikeout rate
4. Umpire adjustment: HP umpire career K rate delta
5. Lambda = (adjusted_K/9 × opp_K_factor × innings/9) + ump_adjustment + lambda_bias
6. Poisson CDF → over/under win probabilities → EV vs book odds → verdict

## Calibration

`calibrate.py` runs during the grading step:
- **Phase 1 (n>=30)**: lambda_bias — corrects systematic over/under-prediction
- **Phase 2 (n>=60)**: ump_scale, K/9 blend weights (season_cap, recent), swstr_k9_scale
- Parameters saved to `data/params.json` with calibration notes
- Only uses current-season picks after any `formula_change_date`

## Data Flow

```
TheRundown API → fetch_odds → props[]
MLB Stats API  → fetch_stats → stats_map{}
FanGraphs      → fetch_swstr → swstr_map{}
ump.news       → fetch_umpires → ump_map{}
Lineups API    → fetch_lineups → lineup[]
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

## Important Patterns

- **Locked snapshots**: Once a game starts, its card data is frozen in today.json. Post-start API runs don't overwrite pre-game snapshots.
- **Pick seeding**: `INSERT OR IGNORE` — first-seen line is locked in. Subsequent runs update unlocked picks only.
- **Ephemeral DB**: SQLite DB is rebuilt from `picks_history.json` each run (GitHub Actions runners are stateless).
- **Graceful degradation**: Each data source can fail independently. SwStr%, umpires, lineups all fall back to neutral values. `data_complete` flag excludes degraded picks from calibration.
- **Movement confidence**: Line movement against bet side applies a 0–1 haircut to EV (noise_floor=10pts, full_fade=30pts).

## Testing Notes

- Tests use `unittest.mock` extensively to mock API calls
- `build_features` functions are pure (no I/O) for easy testing
- Test files mirror pipeline modules: `test_build_features.py`, `test_calibrate.py`, etc.
- Run full suite: `python -m pytest tests/ -v`
