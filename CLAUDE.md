# BaseballBettingEdge

MLB pitcher strikeout (K) prop betting dashboard. Static site + Python pipeline + GitHub Actions.

## Architecture

- **Pipeline:** Python 3.11, runs via GitHub Actions on cron schedule
- **Frontend:** Single-file static HTML dashboard (PWA) at `dashboard/index.html`
- **Hosting:** Netlify (auto-deploy on push to main)
- **Notifications:** Web Push (VAPID) via Netlify Functions + Service Worker
- **Data:** JSON files committed to git + SQLite (`data/results.db`)

## Key Paths

- `pipeline/run_pipeline.py` — orchestrator (fetch odds/stats/umpires/lineups → build features → write JSON)
- `pipeline/build_features.py` — Poisson EV model, verdict logic
- `dashboard/index.html` — full SPA (vanilla JS, no framework)
- `dashboard/sw.js` — service worker for push notifications
- `netlify/functions/send-notifications.mjs` — push notification dispatcher
- `netlify/functions/save-subscription.mjs` — subscription storage
- `.github/workflows/pipeline.yml` — cron schedule + pipeline execution
- `data/picks_history.json` — flattened pick history (seeded/locked/graded)
- `data/params.json` — calibrated model parameters

## Pipeline Schedule (America/Phoenix, UTC-7 no DST)

- 7:00 PM — preview: fetch next-day lines as opening baseline
- 3:00 AM — grading: grade previous day + calibrate
- 6:00 AM — full: finalize today's picks
- 8:00 AM–6:00 PM (every 30 min) — refresh: fresh odds/lineups, update unlocked picks, lock T-30min

## External APIs

### TheRundown (odds)
- **Plan:** Starter ($49/month)
- **Data points:** 2,000,000/month (then $0.002/pt overage)
- **Rate limit:** 2 req/sec
- **Data delay:** 60 seconds
- **Features:** All 15+ bookmakers, all periods & markets, live odds, best lines, 7-day history
- **Not included:** WebSocket streaming, +EV calculations
- **Auth:** `RUNDOWN_API_KEY` env var / GitHub secret
- **Usage:** ~2 API calls per pipeline run (today + tomorrow UTC dates)

### MLB Stats API (stats)
- Free, no key required

### ump.news (umpires)
- Scraped, no key required

### FanGraphs / PyBaseball (SwStr%, batter stats)
- Free, no key required

## Secrets (GitHub Actions + Netlify)

- `RUNDOWN_API_KEY` — TheRundown API key
- `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` — web push keys
- `NOTIFY_SECRET` — shared secret for GitHub Actions → Netlify notification calls
- `NETLIFY_SITE_URL` — base URL of the Netlify site

## Testing

```bash
# Run pipeline locally
python pipeline/run_pipeline.py 2026-04-01

# Run tests
python -m pytest tests/
```

## Conventions

- All times in codebase use America/Phoenix (UTC-7, no DST) — crons never change
- Pipeline has per-pitcher error isolation (one bad pitcher doesn't crash the run)
- Locked snapshots: once a game starts, its card data is frozen
- Verdict thresholds: PASS (EV <= 0.01), LEAN (0.01-0.03), FIRE 1u (0.03-0.06), FIRE 2u (> 0.06)
