# BaseballBettingEdge — Design Spec
**Date:** 2026-03-24
**Status:** Approved

---

## Overview

BaseballBettingEdge is a static web dashboard for evaluating MLB pitcher strikeout (K) props using a Poisson probability model. A GitHub Actions pipeline fetches odds, stats, and umpire data twice daily, computes EV-based verdicts, and commits the result as `data/processed/today.json`. A Netlify-hosted static dashboard reads that file and renders pitcher cards with verdicts and juice movement signals.

No user accounts, no backend server, no live API calls from the browser.

---

## Goals

- Surface FIRE / LEAN / PASS verdicts for pitcher K props each game day
- Show intra-day juice movement (price delta) as a signal of sharp action
- Highlight the top 5 juice movers on a Watchlist tab
- Deploy automatically on every pipeline run with no manual steps

## Non-Goals (v1)

- EV calculator (manual override) — removed; user tracks bets via Pikkitt
- Bet tracker / P&L — removed; Pikkitt handles this
- CORS proxy / live odds refresh — deferred to v2
- Left/right handedness splits on opponent K rate
- Pitch count / innings restriction override

---

## Architecture

```
GitHub Actions (9am ET + 1pm ET)
  └─ run_pipeline.py
       ├─ fetch_odds.py      → TheRundown API v2
       ├─ fetch_stats.py     → MLB Stats API (free, no key)
       ├─ fetch_umpires.py   → ump.news scrape + career_k_rates.json
       └─ build_features.py  → calc_lambda() + Poisson EV + price deltas
            └─ writes data/processed/today.json
  └─ git commit + push to main
  └─ Netlify auto-deploys dashboard

Browser
  └─ dashboard/index.html
       └─ fetch("../data/processed/today.json") → render cards
       (no localStorage, no API calls)
```

---

## Repo Structure

```
baseballbettingedge/
├── .github/workflows/pipeline.yml
├── pipeline/
│   ├── run_pipeline.py        ← orchestrator
│   ├── fetch_odds.py          ← TheRundown K prop lines + 7-day history
│   ├── fetch_stats.py         ← MLB API: starters, K/9, team K%
│   ├── fetch_umpires.py       ← ump.news scrape → HP umpire
│   └── build_features.py      ← calc_lambda, Poisson EV, price deltas
├── data/
│   ├── processed/today.json
│   └── umpires/career_k_rates.json   ← 30-umpire static table
├── dashboard/
│   └── index.html             ← single-file static dashboard
├── docs/
│   └── superpowers/specs/
│       └── 2026-03-24-baseballbettingedge-design.md
├── requirements.txt
├── netlify.toml
└── .gitignore
```

---

## Pipeline

### Modules

**`fetch_odds.py`**
- Auth: `X-TheRundown-Key` header from `RUNDOWN_API_KEY` env var
- Base URL: `https://therundown.io/api/v2`
- Fetches today's MLB K props (sport ID 3)
- Fetches 7-day history to extract opening odds for each prop
- Rate-limited: 0.55s sleep between requests (2 req/sec Starter plan limit)
- Returns: `{ pitcher, team, opp_team, game_time, k_line, opening_line, best_over_book, best_over_odds, opening_over_odds, opening_under_odds }`

**`fetch_stats.py`**
- MLB Stats API (no key required)
- Fetches confirmed starting pitcher for each game
- Returns per pitcher: `season_k9`, `recent_k9` (last 5 starts), `career_k9`, `innings_pitched_season`
- Returns per team: `opp_k_rate` (season batter K%)
- Falls back to season K/9 only if recent data is unavailable (<3 starts)

**`fetch_umpires.py`**
- Scrapes ump.news for home plate umpire assignments
- Looks up career K adj from `data/umpires/career_k_rates.json`
- Falls back to `ump_k_adj = 0` if assignment not yet posted or umpire not in table
- Static table covers ~30 umpires with meaningful K rate deltas vs average

**`build_features.py`**
Joins all data sources and computes per pitcher:

```python
# Blended K/9 — weights shift toward season as IP accumulates
w_season = min(innings_pitched / 60, 0.7)   # caps at 70% by ~60 IP
w_recent = 0.2
w_career = 1 - w_season - w_recent

blended_k9 = (w_season * season_k9) + (w_recent * recent_k9) + (w_career * career_k9)

# Lambda (expected Ks)
expected_innings = 5.5   # default; adjustable per pitcher tier
lambda_ = (blended_k9 * expected_innings / 9) \
        * (opp_k_rate / 0.227) \
        + (ump_k_adj * expected_innings / 9)

# Poisson win probability and EV
win_prob_over = 1 - poisson.cdf(k_line, lambda_)   # P(Ks > line)
implied_over  = american_to_implied(best_over_odds)
ev_over       = win_prob_over - implied_over

# Price delta (juice movement signal)
price_delta_over  = best_over_odds - opening_over_odds
price_delta_under = best_under_odds - opening_under_odds

# Verdict thresholds (quarter Kelly sizing)
# PASS:   ev <= 0.01
# LEAN:   0.01 < ev <= 0.03
# FIRE 1u: 0.03 < ev <= 0.06
# FIRE 2u: ev > 0.06
```

**`run_pipeline.py`**
- Orchestrates fetch → build → write in order
- Per-pitcher error isolation: one bad pitcher logs a warning and is skipped; does not crash the run
- Sets `props_available: false` if no K props are returned from TheRundown (too early, props not posted)
- Writes `data/processed/today.json` on completion

### Error Handling

| Failure | Behavior |
|---|---|
| TheRundown returns no props | `props_available: false`, dashboard shows "Props not yet posted" |
| MLB Stats API down | Skip pitcher (omit from output), log warning |
| Ump assignment not posted | `ump_k_adj = 0`, noted in output |
| Pitcher scratched mid-day | 1pm run will not include them if starter confirmed elsewhere |
| Pipeline crashes entirely | Last committed `today.json` remains; dashboard shows stale warning if >6h |

---

## `today.json` Schema

```json
{
  "generated_at": "2026-04-01T18:00:00Z",
  "date": "2026-04-01",
  "props_available": true,
  "pitchers": [
    {
      "pitcher": "Gerrit Cole",
      "team": "NYY",
      "opp_team": "BOS",
      "game_time": "2026-04-01T23:05:00Z",
      "k_line": 7.5,
      "opening_line": 7.5,
      "best_over_book": "FanDuel",
      "best_over_odds": -112,
      "best_under_odds": -108,
      "opening_over_odds": -110,
      "opening_under_odds": -110,
      "price_delta_over": -2,
      "price_delta_under": 2,
      "lambda": 7.21,
      "opp_k_rate": 0.241,
      "ump_k_adj": 0.4,
      "ev_over": { "ev": 0.038, "verdict": "FIRE 1u", "win_prob": 0.572 },
      "ev_under": { "ev": -0.041, "verdict": "PASS", "win_prob": 0.428 }
    }
  ]
}
```

---

## Dashboard

### Visual Design

Scorecard / Press Box aesthetic:
- Background: `#f5f0e8` (parchment)
- Surface: `#ffffff`
- Borders: `#d0c8b8`
- Accent dark: `#1a1a1a`
- Fire/positive: `#c0392b` (red)
- Positive EV: `#27ae60` (green)
- Monospace: used for all numbers and stat values
- Serif: used for headers and pitcher names

### Tabs

**Props tab (default)**
- One full card per pitcher, sorted by `ev_over` descending
- PASS verdicts dimmed and collapsed by default; "Show all" toggle reveals them
- Each card:
  - Dark header bar: `[Pitcher Name · TEAM vs OPP]` + verdict badge
  - Stats row (monospace): Line · λ · EV Over · Best Book
  - Sub-row: adjustment badges (`OPP K% +12%`, `UMP +0.4`) + game time
  - Price delta inline: `7.5 · -112 ↑ juice -25` (red = juice moving to over)

**Watchlist tab**
- Top 5 pitchers by `abs(price_delta_over)`, descending
- Label: "Biggest juice moves today"
- Condensed card: pitcher name, line, opening odds → current odds, delta, verdict
- If `generated_at` is from the 9am window: note "Early run — limited movement data"

### Data Freshness States

| State | UI |
|---|---|
| Fresh (<6h) | Green badge "Updated {HH:MM}" |
| Stale (>6h) | Yellow banner "Data may be outdated — pipeline may have failed" |
| Props not posted | Gray banner "Props not yet posted — check back after 10am ET" |

---

## Deployment

### GitHub Actions (`.github/workflows/pipeline.yml`)

```yaml
on:
  schedule:
    - cron: '0 14 * * *'   # 9am ET
    - cron: '0 18 * * *'   # 1pm ET
  workflow_dispatch:         # manual trigger

env:
  RUNDOWN_API_KEY: ${{ secrets.RUNDOWN_API_KEY }}
```

Pipeline steps: checkout → setup Python → install requirements → run pipeline → commit today.json → push to main.

### Netlify

- `netlify.toml`: `publish = "dashboard"`, `functions = "netlify/functions"` (stub directory, no active functions in v1)
- Auto-deploys on every push to main
- Dashboard live within ~30s of pipeline push

### One-Time Setup

1. Add `RUNDOWN_API_KEY` as a GitHub Actions secret
2. Connect repo to Netlify (auto-deploy on push to main)
3. Test pipeline locally: `python pipeline/run_pipeline.py 2026-04-01` with key in `.env`

---

## Static Data

**`data/umpires/career_k_rates.json`**
Static table of ~30 HP umpires with career K rate delta vs league average. Range: −0.52 (CB Bucknor) to +0.52 (Vic Carapazza). Source: Baseball Savant. Updated manually each offseason.

```json
{
  "Vic Carapazza": 0.52,
  "CB Bucknor": -0.52,
  ...
}
```

---

## Known Limitations (v1)

- 60-second live odds delay on TheRundown Starter plan (noted in dashboard UI)
- Ump assignments from ump.news typically available ~10am ET; 9am run will show neutral adj
- No L/R handedness split on opponent K rate
- No pitch count or innings limit override (uses fixed 5.5 expected innings)
- Price delta meaningful only on 1pm run; 9am run shows `±0` for most pitchers
