# Current State

Last updated: 2026-05-07

## Read Order

For any new work in this repo:

1. Read `AGENTS.md` for the canonical project instructions and architecture notes.
2. Read this file for the current operating state.
3. Read the newest active dated plans that match the task:
   - `docs/superpowers/plans/2026-05-07-bet-conversion-shadow-audit.md`
   - `docs/superpowers/plans/2026-05-07-boltodds-starter-trial.md`
   - `docs/superpowers/plans/2026-05-06-live-layer-event-system.md`
   - `docs/superpowers/plans/2026-05-05-propline-fallback-and-model-signal-plan.md`
   - `docs/superpowers/plans/2026-04-28-one-week-evaluation-cadence.md`
4. Read `docs/provider-cost-ledger.md` before recommending new providers,
   upgrades, polling increases, or always-on infrastructure.
5. Read `docs/operational-risk-register.md` before changing provider behavior,
   notification behavior, retention, live workers, or source-of-truth rules.
6. Use older dated plans in `docs/superpowers/plans/` as archive context, not
   as replacements for this file.

## Current Operating Mode

The project is still in a post-Phase-C soak/evaluation period, but the active
question has shifted from "is the projection formula broadly broken?" to "how
do we convert model signal into better betting decisions?"

- Treat `2026-04-28` as the clean post-ROI / post-SwStr-live evaluation
  boundary.
- Do not make ad hoc model, threshold, staking, or `formula_change_date`
  changes unless Tyler explicitly decides to break cadence.
- Current model track: `bet-selection-first`.
- Keep candidate ranking changes shadow-only until the clean sample and Gate C
  justify a live behavior plan.
- TheRundown remains the production book-of-record odds source for the scheduled
  pipeline.
- PropLine remains a shadow/fallback/live-movement source. Polling is useful;
  real provider webhooks are still unproven.
- BoltOdds is being tested as a separate shadow-only WebSocket live-market
  sidecar. It must not affect production picks, grading, dashboard artifacts,
  or provider order without explicit approval.

## Active Production Path

The official app still runs from the GitHub pipeline:

- GitHub Actions preview/full/refresh/grading jobs write `today.json`, dated
  archives, `steam.json`, `performance.json`, `params.json`,
  `preview_lines.json`, and `data/picks_history.json`.
- Netlify serves the static dashboard and notification functions.
- `data/picks_history.json` remains the durable grading/history source.
- `data/results.db` remains ephemeral.

Generated artifacts are user-facing truth. Verify live-slate fixes against the
actual artifacts, not only unit tests.

## Live Notification Layer

The live layer is now separate from the production pipeline.

- Render cron service: `bbe-live-layer`
- Cadence: every 10 minutes
- Source artifact: fresh GitHub raw `today.json`, not the baked Render checkout
- Market source: PropLine polling when `PROPLINE_API_KEY` is present
- Supabase live tables:
  - `market_snapshots`
  - `live_pick_state`
  - `notification_events`
  - `line_movement_events`
  - `market_pick_evidence`
  - `live_market_display_state`
  - `shadow_notification_candidates`
  - `game_reminder_state`
- Netlify scheduled function: `send-live-notifications`
- Manual endpoint: `/api/send-live-notifications-now`

This layer can create live notification events, but it must not update
dashboard artifacts, grading, picks history, calibration, model outputs, or
production provider order.

`market_pick_evidence` is a shadow-only rollup built from live market snapshots
and current pick state. It is meant to answer "model says this, market did
that, outcome was this" after enough graded rows accumulate. It does not change
live picks, line locks, thresholds, staking, provider order, or notification
sends.

`shadow_notification_candidates` is the next evidence layer. It records
would-have-sent market alerts by provider, candidate type, suppression reason,
time window, BetRivers-only status, broad-confirmation status, and
reversal/volatility status. It does not send pushes.

`live_market_display_state` is the app-facing shadow layer for BoltOdds/PropLine
movement display. It summarizes provider snapshots into market consensus, best
actionable book, off-market books, movement sequence, and freshness/actionable
state. It is intentionally not a pick, lock, threshold, staking, provider-order,
or notification-send input.

Current housekeeping:

- `NOTIFY_SECRET` rotation after screenshot exposure was completed on
  2026-05-07. Daily checks should verify sender health and queue counts, not
  keep treating rotation as outstanding.
- Later review whether the older GitHub shadow PropLine polling can be reduced
  if Render live polling creates duplicate provider calls.

## Provider Shadow State

### PropLine

PropLine polling is useful for fallback/partial-provider evidence and live
movement comparison, especially around FanDuel and BetRivers. It should not be
promoted broadly from TheRundown based on current evidence.

Webhook status:

- The receiver path works via the signed synthetic test.
- Real PropLine provider webhook traffic has not been proven yet.
- Do not claim PropLine webhooks are live unless `propline_webhook_deliveries`
  shows real provider deliveries.

### BoltOdds

The BoltOdds Starter trial is running on a separate branch and worker path.

- Branch: `codex/boltodds-starter-trial`
- Render worker: `bbe-boltodds-shadow-worker`
- Purpose: one persistent WebSocket connection for MLB pitcher strikeout market
  evidence.
- Writes: shadow-only Supabase provider runs, feed heartbeats, market snapshots,
  coverage audits, and migration-risk diagnostics.
- Production impact: none.

Starter discovery confirmed enough coverage to test the trial:

- Useful/visible: FanDuel, BetMGM, BetRivers, Kalshi, Caesars
- Weird: DraftKings appears in discovery but returned zero authenticated market
  rows during checks
- Missing: theScore

Let the trial collect uptime, heartbeat freshness, normalized book coverage,
row volume, and stale-feed evidence before any provider decision.

## Active Evaluation Stack

The active local diagnostics and tests are:

- `analytics/diagnostics/e1_regime_map.py`
- `analytics/diagnostics/e2_storage_integrity.py`
- `analytics/diagnostics/e3_projection_audit.py`
- `analytics/diagnostics/e4_bet_selection_audit.py`
- `analytics/diagnostics/e5_quality_gate_audit.py`
- `analytics/diagnostics/bet_conversion_shadow_audit.py`
- `tests/test_e1_regime_map.py`
- `tests/test_e2_storage_integrity.py`
- `tests/test_e3_projection_audit.py`
- `tests/test_e4_bet_selection_audit.py`
- `tests/test_e5_quality_gate_audit.py`
- `tests/test_bet_conversion_shadow_audit.py`

Current readout from 2026-05-07:

- Clean regime rows are sufficient to choose the next analysis track.
- Global projection residual is close enough to neutral that a broad lambda
  correction is not the first move.
- Bet conversion/ranking is the clearest business problem.
- FIRE 2u sample is still too small for a staking ladder decision.
- Quality gates are live and useful, but not a complete ranking solution.

## Next Decision Checkpoints

### Cost / Provider Spend

Use `docs/provider-cost-ledger.md`.

Provider and infrastructure choices should be judged by decision value, not by
technical appeal. Before adding spend, increasing polling, upgrading a plan, or
keeping overlapping feeds, check the cost ledger and state what decision the
cost improves.

### Operational Risk / Source Truth

Use `docs/operational-risk-register.md`.

The risk register tracks trial dates, kill/keep criteria, failure modes,
retention rules, notification guardrails, and source-of-truth hierarchy. Update
it when a trial starts or ends, a provider changes role, or a live-layer failure
mode is discovered.

### Bet Conversion / Gate C

Use `docs/superpowers/plans/2026-05-07-bet-conversion-shadow-audit.md`.

The next model-facing work should compare adjusted EV, raw edge, model margin,
side-specific conversion, quality-gate context, and opening-source context in
shadow. Do not promote a live rule from one positive bucket or one slate.

### BoltOdds Trial Review

Use `docs/superpowers/plans/2026-05-07-boltodds-starter-trial.md`.

Review uptime, heartbeat freshness, normalized row coverage by target book,
stale-feed risk, row volume risk, and whether the feed would have changed
timing or notification decisions. Do not buy Pro or promote BoltOdds without a
post-trial decision.

### June 1 Provider Review

The next broad provider decision checkpoint is **2026-06-01**:

- Review the full May PropLine shadow trial against TheRundown production
  artifacts, Render live-layer evidence, BoltOdds trial evidence, and any real
  PropLine webhook/support updates.
- Summarize coverage by target book, pitcher/line completeness, line conflicts,
  same-line overlap, movement detection, schedule jitter, Supabase shadow-table
  health, and whether movements would have changed decisions.
- Decide whether PropLine remains fallback/shadow, becomes a partial provider
  for specific books, justifies more live infrastructure, or stays shadow-only.
- Do not change production odds-provider behavior without Tyler's approval.

## Historical Context

The dated plan archive is intentionally preserved so future agents can see what
changed, what was tried, and what mistakes to avoid repeating.

Important recent context:

- `docs/superpowers/plans/2026-05-04-post-soak-model-growth-roadmap.md`
- `docs/superpowers/plans/2026-05-01-propline-supabase-market-infrastructure.md`
- `docs/superpowers/plans/2026-04-29-input-quality-gates-and-data-maturity.md`
- `docs/superpowers/plans/2026-04-27-post-phase-c-model-evaluation.md`
- `docs/superpowers/plans/2026-04-27-swstr-signal-repair-and-rebaseline.md`

When historical plans conflict with this file, treat this file plus the newest
active dated plan for the task as current.
