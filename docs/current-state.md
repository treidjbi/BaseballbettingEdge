# Current State

Last updated: 2026-05-22

## Read Order

For any new work in this repo:

1. Read `AGENTS.md` for the canonical project instructions and architecture notes.
2. Read this file for the current operating state.
3. Read the newest active dated plans that match the task:
   - `docs/superpowers/plans/2026-05-13-boltodds-propline-official-provider-cutover.md`
   - `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
   - `docs/superpowers/plans/2026-05-20-live-market-decision-ui.md`
     for future dashboard UI work that displays BoltOdds/PropLine live-market
     evidence after the operational/provider production switch is approved
   - `docs/superpowers/plans/2026-05-22-github-artifact-exit.md`
     for the post-lock plan to move dashboard artifact serving and scheduled
     pipeline execution off GitHub Actions after strict lock canary validation
   - `docs/superpowers/plans/2026-05-07-bet-conversion-shadow-audit.md`
     only as historical diagnostic context for the first bet-selection audit
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
- Keep candidate ranking changes shadow-only until the clean sample and the
  Gate C / Gate F rules in
  `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
  justify a live behavior plan.
- TheRundown remains the production book-of-record odds source for the scheduled
  pipeline. It renewed through the end of May 2026, so May is now the planned
  overlap window for building and shadow-comparing the BoltOdds + PropLine
  official-provider cutover before any cancellation/removal decision.
- PropLine remains a shadow/fallback/live-movement source. Polling is useful,
  and real signed provider webhooks are now landing with book-level movement
  IDs after PropLine's 2026-05-19 payload fix. The planned provider stack is
  BoltOdds primary with PropLine fallback/DraftKings coverage, but that is not
  official until the cutover gates and environment switch are completed.
- BoltOdds is being tested as a separate shadow-only WebSocket live-market
  sidecar. It must not affect production picks, grading, dashboard artifacts,
  or provider order until the provider cutover plan is implemented and Tyler
  explicitly approves the switch.

## Four-Lane Operating Board

Use this board to keep the active workstreams visible without turning every
new idea into a separate source of truth. The BBE Operations Brief should
summarize these lanes daily and call out only the next decision or blocker for
each lane.

| Lane | Current Source | Current Stage | Next Decision |
| --- | --- | --- | --- |
| Pipeline / infrastructure | `2026-05-19-supabase-operational-foundation.md`, `2026-05-22-github-artifact-exit.md`, `2026-05-13-boltodds-propline-official-provider-cutover.md`, `2026-05-20-live-notification-coordinator.md`, `docs/operational-risk-register.md` | Staged Supabase/BoltOdds/PropLine migration. GitHub + TheRundown remain production source of truth. Supabase lock ledger is in strict/single-writer canary code: GitHub can consume Supabase lock rows while `ENABLE_GITHUB_FALLBACK_LOCKING=false` suppresses its own due-lock fallback, avoiding the dual-writer race. Drifted already-locked ledger rows are now classified in `operational_pick_locks.metadata.consumer_status`. | Audit the strict/single-writer canary for the next lock windows. If clean, proceed toward Supabase artifact mirror; if any lock row is missing or unclassified, fix lock infrastructure before artifact-exit work. |
| Model | `2026-05-12-pitcher-k-outcome-research-dataset.md` | Gate C confidence-referee / compact evidence proof. Gate A and local Gate B are effectively done. | Move from Gate C to Gate D only when collection/storage/reconciliation are routine. Gate E/F are required before any live ranking, threshold, staking, calibration, or formula promotion. |
| UI | `2026-05-20-live-market-decision-ui.md`, `2026-05-20-live-notification-coordinator.md` | Future-state design only. The dashboard should eventually display best price, consensus, movement, urgency, and notification grouping from the new operational base. | Revisit after the operational/provider switch is stable. Keep display work separated from provider promotion and betting-rule changes. |
| Tracking / data collection / history | `docs/research/market-tracker-map.md`, `docs/research/pitcher-k-outcome-dataset.md`, compact outcome outputs, live-market audits | Canonical research row plus existing market/live/provider trackers. Daily brief now keeps a compact Gate C bucket scoreboard and pre/post 2026-04-28 context. | Prefer derived labels on the compact outcome row before adding tables. Promote compact storage or retention only after row-volume/cost proof and Tyler approval. |

Board rule: each lane can advance independently, but live betting behavior only
changes after the controlling lane has passed its own promotion gate and Tyler
explicitly approves the production switch. Operational reliability evidence is
not a model-change approval, and model bucket evidence is not a provider-cutover
approval.

Board maintenance rule: when a session meaningfully changes a lane's stage,
next decision, blocker, promotion status, or controlling plan, update the
controlling dated plan first, this board second, and the BBE Operations Brief
automation memory when the daily brief should carry the update forward. Keep
the board concise; do not duplicate detailed rules from the controlling plans.

## Supabase Operational Foundation Migration

As of 2026-05-19, Tyler approved starting the migration from pure shadow
evidence toward Supabase as the operational control plane. This does not remove
TheRundown or GitHub artifacts yet.

Phase 1 promotes only gated foundations:

- `operational_pick_locks` can store first-seen lock snapshots captured by the
  live layer before first pitch.
- `ENABLE_SUPABASE_LOCK_LEDGER=true` lets Render write lock-intent rows.
- `ENABLE_SUPABASE_LOCK_CONSUMER=true` lets the GitHub pipeline apply those
  lock rows to artifacts/history.
- Both flags default off in code until Tyler explicitly enables them.
- BoltOdds + PropLine provider-source promotion still uses the existing
  `OFFICIAL_MARKET_SOURCE=boltodds_propline` and
  `ENABLE_BOLTODDS_PIPELINE_SOURCE=true` gates.

Operational rollout note, 2026-05-21:

- Hosted Supabase migration `20260519201848 operational_pick_locks` has been
  applied and verified on the active project.
- Render `bbe-live-layer` now has `ENABLE_SUPABASE_LOCK_LEDGER=true` for
  lock-ledger writes.
- GitHub repository variables now have `ENABLE_SUPABASE_LOCK_CONSUMER=true`
  and `SUPABASE_LOCK_CONSUMER_STRICT=false` for a non-strict lock consumer
  canary. If Supabase read/apply fails, the pipeline should warn and fall back
  to the existing GitHub lock path.
- As of 2026-05-23, code support exists for a stricter single-writer lock
  canary: `ENABLE_GITHUB_FALLBACK_LOCKING=false` keeps GitHub publishing and
  grading artifacts but suppresses its own T-30 due-lock fallback in normal and
  lock-only runs. In that posture, due locks must come from
  `operational_pick_locks`; `SUPABASE_LOCK_CONSUMER_STRICT=true` makes
  Supabase consumer failures fail the GitHub run visibly instead of silently
  falling back. This is still not a provider, model, threshold, staking, or
  dashboard-source change.
- First validation on 2026-05-21 used a manual GitHub `mode=lock` dispatch
  after Render wrote four due lock rows. The run applied 4/4 external lock rows
  and committed the locked fields to `today.json`, the dated archive, and
  `picks_history.json`. This proves the consumer path, but the scheduled
  GitHub run did not arrive after Render wrote the rows, so the next speed fix
  is event-driven lock-only dispatch plus a consumed-row marker.
- Code support now exists for that speed fix:
  - GitHub fetches only unconsumed `operational_pick_locks` rows and marks
    represented lock rows with `consumed_at`; rows already correctly locked in
    the artifact DB are idempotently consumable, while unmatched rows stay
    unconsumed for audit.
  - Render live layer dispatches GitHub `pipeline.yml` with `mode=lock` and the
    slate date only when `ENABLE_LOCK_ONLY_WORKFLOW_DISPATCH=true` and new lock
    rows were inserted.
  - Dispatch can use a direct GitHub token (`GITHUB_LOCK_DISPATCH_TOKEN` or
    `GITHUB_PAT`) or the existing Netlify `trigger-pipeline` proxy. The default
    proxy URL is `https://baseballbettingedge.netlify.app/.netlify/functions/trigger-pipeline`.
  - Optional direct-dispatch env: `GITHUB_LOCK_DISPATCH_REPO`,
    `GITHUB_LOCK_DISPATCH_WORKFLOW`, and `GITHUB_LOCK_DISPATCH_REF`.
- Live validation on 2026-05-21 at 19:40 UTC: Render inserted two fresh due
  rows, Cade Cavalli over and David Peterson under, logged
  `dispatch:sent:200`, and triggered GitHub workflow run `26248878102`. That
  run applied 2/6 external rows and committed both locks to artifacts/history.
  Because four earlier manual-canary rows were already locked but still
  unconsumed, the consumer patch now treats already-represented lock rows as
  safe to consume. Follow-up lock run `26249190878` marked all 6/6 represented
  2026-05-21 rows consumed.
  - Render `bbe-live-layer` has `ENABLE_LOCK_ONLY_WORKFLOW_DISPATCH=true` set
    as a service environment variable and has been redeployed on the dispatch
    code. Validate the next due lock batch by checking for
    `dispatch:sent:200` in Render logs and a matching GitHub `mode=lock` run.
- `OFFICIAL_MARKET_SOURCE=boltodds_propline`,
  `ENABLE_BOLTODDS_PIPELINE_SOURCE`, and live webhook processor promotion
  remain off/unset unless Tyler explicitly approves those separate canaries.

Cutover branch infrastructure progress as of 2026-05-14:

- The Supabase cutover tables have been applied for the active project:
  `current_market_lines`, `market_opening_baselines`,
  `official_market_lines`, `provider_arbitration_decisions`,
  `provider_request_usage_daily`, and `compact_market_line_movements`.
- `current_market_lines` and `market_opening_baselines` builders exist as
  shadow derived-market infrastructure. The current-line builder can fill
  missing provider snapshot `game_time` values from same-slate
  `live_pick_state` rows, with provenance recorded under
  `raw_payload.game_time_source`, so official arbitration can still fail closed
  when live-state timing is unavailable.
- `official_market_lines` arbitration exists behind a separate build script and
  remains shadow-only. It fills missing `current_market_lines.game_time` from
  `live_pick_state` or the production artifact before arbitration, then fails
  closed for stale, unsupported, incomplete, legacy-contract, and
  missing-current lines. It does not change production artifacts yet.
- Live Supabase now has write guards on `current_market_lines`,
  `official_market_lines`, and `provider_arbitration_decisions` to suppress
  duplicate high-cadence shadow rewrites, preserve non-null `game_time`, fail
  closed for legacy `["selected"]` official rows, and reduce duplicate
  arbitration-decision inserts. These guards protect Supabase IO only; they do
  not make BoltOdds/PropLine the production provider.
- BoltOdds official-line freshness now treats a fresh current-slate WebSocket
  heartbeat as supporting evidence for unchanged complete BoltOdds lines. This
  prevents normal K-prop price quietness from making otherwise usable rows fail
  stale solely because the exact line did not re-emit. It still fails closed on
  incomplete rows, missing game time, ambiguous mainline ladders, stale/missing
  heartbeats, and unsupported books.
- The live-layer shadow builders now read `market_feed_heartbeats` and apply
  the same BoltOdds unchanged-line freshness concept to `live_market_display_state`
  and `market_pick_evidence` metadata. `shadow_notification_candidates` now
  suppresses stale market evidence unless the provider heartbeat holds it fresh.
  This remains shadow-only and does not enable BoltOdds notification sends.
- A shadow mainline selector now runs before official arbitration so
  same-book BoltOdds alt ladders are not treated as automatic provider outages.
  It keeps raw/current rows for audit, selects complete supported mainline
  candidates only when PropLine/TheRundown overlap or cross-book support makes
  the choice clear, and fails closed on ambiguous ladders. The first May 14
  rehearsal after this change showed raw schedule-first provider coverage at
  21/22 starters, but only 14/22 mainline-ready and 14/22 official-ready, so
  the cutover remains not ready.
- `.github/workflows/shadow-market-infra.yml` now has a shadow-only derived
  line build step. Scheduled runs capture PropLine and rebuild
  `current_market_lines`/`official_market_lines` from existing snapshots; they
  do not run the production pipeline, push artifacts, or change provider order.
  The provider cutover comparison report is manual-only from that workflow.
- Step 7 storage/cost support is implemented on the cutover branch:
  `provider_request_usage_daily` is written from fetched provider runs/snapshots,
  and `scripts/compact_market_snapshots.py` upserts compact
  `compact_market_line_movements` rows after the current/official market-line
  build. This enables storage and request-usage review, but raw snapshot
  deletion/retention is still a separate approval step.
- Supabase upgraded to Pro on 2026-05-21 after the org exceeded the Free
  database-size cap. Baseline CLI read after upgrade showed the linked BBE
  database at `639 MB`; `market_snapshots` was the dominant table at about
  `462 MB` total. Use `scripts/supabase_storage_guardrail.sql` in daily/weekly
  ops reads and keep spend cap on unless Tyler explicitly approves overages.
- The Odds API official arbitration remains behind an explicit emergency flag;
  DraftKings remains PropLine-first until BoltOdds DraftKings coverage is
  explicitly enabled.
- A pipeline adapter for `official_market_lines` exists behind a double opt-in:
  `OFFICIAL_MARKET_SOURCE=boltodds_propline` and
  `ENABLE_BOLTODDS_PIPELINE_SOURCE=true`. Without both, TheRundown remains the
  odds source. Strict provider mode is available for later cutover rehearsal,
  but should not be enabled until the yes/no review.
- `analytics/diagnostics/provider_cutover_shadow_compare.py` exists for the
  fresh-slate rehearsal. Use it to compare TheRundown against provider-mode
  rows and evaluate coverage, FD/DK availability, line conflicts, ref-book
  changes, odds deltas, artifact contract, and usage gates before any cutover
  decision. Its current-line/mainline coverage read uses the same BoltOdds
  heartbeat-held unchanged-line semantics as official arbitration.
- `analytics/diagnostics/executable_market_shadow_audit.py` exists for the
  Monday cutover review. It scores the current model projection against every
  fresh, complete, supported mainline book/line/side from `current_market_lines`
  so cross-book disagreement can be studied as best-executable EV evidence.
  This is shadow-only and must not change official ref-book semantics, live
  thresholds, staking, provider order, notifications, or artifacts.
- The cutover comparison now also fetches MLB probable starters first and
  reports schedule-first provider coverage. This is shadow evidence for the
  intended future provider architecture; the production pipeline still runs
  odds-first until Tyler explicitly approves a promotion.

## Provider Plan Precedence

For provider-production work, use
`docs/superpowers/plans/2026-05-13-boltodds-propline-official-provider-cutover.md`
as the controlling implementation plan.

This newer plan synthesizes or supersedes production-facing parts of these older
plans:

- `2026-05-13-boltodds-production-line-movement.md`: use only for the May 13
  stale-slate diagnosis, worker-rotation implementation detail, and historical
  notification/display thinking. The new cutover plan controls official
  provider source behavior.
- `2026-05-07-boltodds-starter-trial.md`: use as trial setup/history and
  worker-branch context. The new cutover plan controls production promotion.
- `2026-05-06-live-layer-event-system.md`: keep as the live-layer foundation.
  The new cutover plan controls BoltOdds/PropLine notification promotion and
  provider-source changes.
- `2026-05-05-propline-fallback-and-model-signal-plan.md`: historical fallback
  and diagnostic work is complete. The new cutover plan controls PropLine's
  future fallback/DraftKings role and downgrade gates.
- `2026-05-01-propline-supabase-market-infrastructure.md`: historical Supabase
  foundation. Reuse existing trackers and follow
  `docs/research/market-tracker-map.md` before adding tables.

Still independently active:

- `2026-05-07-bet-conversion-shadow-audit.md` for bet-selection-first
  diagnostics.
- `2026-05-12-pitcher-k-outcome-research-dataset.md` for compact outcome rows,
  CLV, process-vs-result, and projection shadow research.
Historical / absorbed:

- `2026-04-28-one-week-evaluation-cadence.md` is stale as an active cadence.
  It was useful for the first post-Phase-C week and it did add quality-gate
  audit checks, but its durable rules now live here and in the newer diagnostic
  plans: keep `2026-04-28+` as the clean evaluation boundary, avoid random
  threshold/staking/formula changes, and use the E1-E5, bet-conversion, outcome
  dataset, and quality-gate diagnostics for current decisions.

The live-layer shadow builders on `main` now read `market_feed_heartbeats` and
apply BoltOdds unchanged-line freshness to `live_market_display_state` and
`market_pick_evidence` metadata. `shadow_notification_candidates` suppresses
stale market evidence unless the provider heartbeat holds it fresh. This is
shadow-only and does not enable BoltOdds notification sends.

After the operational/provider production switch is approved, revisit the live
market decision UI plan:
`docs/superpowers/plans/2026-05-20-live-market-decision-ui.md`. That plan is
display-only and shadow-only until Tyler separately approves implementation and
promotion.

Also revisit the live notification coordinator plan:
`docs/superpowers/plans/2026-05-20-live-notification-coordinator.md`.
That plan captures the future notification product direction after the
operational switch: Supabase `notification_events` should become the primary
durable queue, start-window reminders should be grouped, lock pushes should be
batched, late/post-start betting-action pushes should be suppressed or converted
to system-health alerts, and GitHub `send-notifications` should eventually move
to fallback/artifact-health mode after a clean canary.

After the lock layer is strict-canary clean, use the GitHub artifact-exit plan:
`docs/superpowers/plans/2026-05-22-github-artifact-exit.md`.
That plan covers the missing post-lock phase: mirror dashboard JSON artifacts
into Supabase, serve them through a Netlify artifact API with static fallback,
move scheduled pipeline execution to Render, and only then disable GitHub
scheduled artifact publishing. It is future work until Tyler approves starting
Task 1 after the current lock slate audit.

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
- Render cron service ID: `crn-d7tpb19o3t8c739p3qig`
- Render BoltOdds worker: `bbe-boltodds-shadow-worker`
- Render BoltOdds worker ID: `srv-d7ugabe7r5hc73b36oag`
- Local Windows Render CLI: installed under `%LOCALAPPDATA%\Render\bin`;
  new shells should resolve `render`, while existing Codex shells may need the
  full `render.exe` path until the parent process is restarted.
- Cadence: every 10 minutes
- Source artifact: fresh GitHub raw `today.json`, not the baked Render checkout
- Market source: PropLine polling when `PROPLINE_API_KEY` is present
- Shadow provider-state rebuild: `scripts/build_live_events_to_supabase.py`
  can refresh `current_market_lines`, `official_market_lines`,
  `provider_arbitration_decisions`, `provider_request_usage_daily`, and
  `compact_market_line_movements` from the live feed path. The script
  entrypoint enables this by default with freshness guards, so the Render
  live-layer cron can keep the production-shaped shadow tables current even
  when GitHub scheduled shadow-market runs are delayed. Direct test/helper
  calls to `run()` remain opt-in. This is still shadow-only and does not change
  production provider order or pipeline artifacts.
- Live-layer market-state guardrails:
  - `LIVE_BUILD_MARKET_LINES=false` disables the Render-side rebuild.
  - `LIVE_COMPACT_MARKET_SNAPSHOTS=false` skips compact movement upserts.
  - `LIVE_MARKET_LINE_BUILD_MIN_INTERVAL_SECONDS` defaults to `600`.
  - `LIVE_MARKET_COMPACTION_MIN_INTERVAL_SECONDS` defaults to `1800`.
- Supabase live tables:
  - `market_snapshots`
  - `live_pick_state`
  - `notification_events`
  - `line_movement_events`
  - `market_pick_evidence`
  - `live_market_display_state`
  - `shadow_notification_candidates`
  - `game_reminder_state`
  - `shadow_pipeline_runs`
  - `shadow_pick_lock_observations`
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

`live_market_outcome_audit.py` is the local shadow diagnostic that joins
exported live-market evidence back to graded results in `data/picks_history.json`.
It can read `market_pick_evidence`, `live_market_display_state`, and raw
`market_snapshots`; when raw snapshots are available it rebuilds fixed pregame
checkpoints such as pre-30, pre-15, pre-5, and final pre-start. Use it to learn
which live movement contexts actually win, not to alter live behavior.

`shadow_notification_candidates` is the next evidence layer. It records
would-have-sent market alerts by provider, candidate type, suppression reason,
time window, BetRivers-only status, broad-confirmation status, and
reversal/volatility status. It does not send pushes.

`live_market_display_state` is the app-facing shadow layer for BoltOdds/PropLine
movement display. It summarizes provider snapshots into market consensus, best
actionable book, off-market books, movement sequence, and freshness/actionable
state. It is intentionally not a pick, lock, threshold, staking, provider-order,
or notification-send input.

As of 2026-05-15, BoltOdds rows in `live_market_display_state` and
`market_pick_evidence` can be marked effectively fresh when the same-slate
BoltOdds heartbeat is fresh and the book is present in `books_seen`, even when
the exact K-prop line did not re-emit. This is a shadow freshness interpretation
only; actual `notification_events` still do not use BoltOdds movement.

`shadow_pipeline_runs` and `shadow_pick_lock_observations` are the Render
live-layer timing rehearsal for getting off GitHub Actions for time-sensitive
locks. They record compact per-run freshness/lock-window counts plus deduped
pick/status observations such as `due_now`, `missed_lock`, and
`started_unlocked`. They are shadow-only and must not update dashboard
artifacts, `picks_history.json`, grading, calibration, model outputs, provider
order, or notification sends until Tyler approves a separate promotion.

Current housekeeping:

- `NOTIFY_SECRET` rotation after screenshot exposure was completed on
  2026-05-07. Daily checks should verify sender health and queue counts, not
  keep treating rotation as outstanding.
- Later review whether the older GitHub shadow PropLine polling/market-state
  build can be reduced if Render live polling and guarded market-line rebuilds
  provide the same evidence with less scheduler delay.

## Provider Shadow State

### PropLine

PropLine polling is useful for fallback/partial-provider evidence and live
movement comparison, especially around FanDuel and BetRivers. It should not be
promoted broadly from TheRundown based on current evidence.

Webhook status:

- The receiver path is active and now has real signed `line_movement`
  deliveries in `propline_webhook_deliveries` as of 2026-05-19.
- PropLine confirmed on 2026-05-19 that new `line_movement` and `resolution`
  deliveries include `bookmaker_key`, `bookmaker_title`, `market_id`, and
  `outcome_id`. The IDs match `/odds`, `/odds/history`, and `/results`, so
  webhook movement can be reconciled to polling by ID instead of fuzzy
  player+line+book matching.
- `scripts/process_propline_webhooks.py` can process inbox rows into shadow
  `line_movement_events`; it writes the actual book key and stores
  `bookmaker_title`, `market_id`, and `outcome_id` when present. Legacy rows
  without a book still use `bookmaker_key='propline_webhook'` with
  `metadata.bookmaker_key_missing=true`.
- The live-layer hook is gated by `LIVE_PROCESS_PROPLINE_WEBHOOKS`; leave it
  off until the lock-ledger observation is not at risk. Do not use webhook rows
  for production odds, picks, notifications, or provider promotion without a
  separate review.

### BoltOdds

The BoltOdds Starter trial worker should now deploy from `main`; the old
`codex/boltodds-starter-trial` branch is historical trial context only.

- Branch: `main`
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

As of 2026-05-12, active BoltOdds capture excludes Kalshi so the remaining
trial can prioritize mainstream-book line movement and CLV evidence while
reducing row volume. Kalshi remains shadow-only unless Tyler explicitly
promotes it as an actionable book with a separate source/arbitration decision.

Let the trial collect uptime, heartbeat freshness, normalized book coverage,
row volume, and stale-feed evidence before any provider decision.

May 13 stale-slate diagnosis: the persistent worker could heartbeat on the
wrong slate if it started before GitHub's delayed full run updated `today.json`.
The worker now refreshes the production artifact during the WebSocket loop using
`BOLTODDS_ARTIFACT_REFRESH_SECONDS` and rotates forward only when the artifact
date advances, emitting a `slate_rotated` heartbeat. Render must point at
`main` for this and the provider-runtime hardening fixes to deploy.

## Active Evaluation Stack

The active local diagnostics and tests are:

- `analytics/diagnostics/e1_regime_map.py`
- `analytics/diagnostics/e2_storage_integrity.py`
- `analytics/diagnostics/e3_projection_audit.py`
- `analytics/diagnostics/e4_bet_selection_audit.py`
- `analytics/diagnostics/e5_quality_gate_audit.py`
- `analytics/diagnostics/bet_conversion_shadow_audit.py`
- `analytics/diagnostics/market_price_outcome_audit.py`
- `analytics/diagnostics/live_market_outcome_audit.py`
- `analytics/diagnostics/pitcher_k_outcome_dataset.py`
- `analytics/diagnostics/k_projection_shadow_lab.py`
- `analytics/diagnostics/executable_market_shadow_audit.py`
- `tests/test_e1_regime_map.py`
- `tests/test_e2_storage_integrity.py`
- `tests/test_e3_projection_audit.py`
- `tests/test_e4_bet_selection_audit.py`
- `tests/test_e5_quality_gate_audit.py`
- `tests/test_bet_conversion_shadow_audit.py`
- `tests/test_market_price_outcome_audit.py`
- `tests/test_live_market_outcome_audit.py`
- `tests/test_pitcher_k_outcome_dataset_contract.py`
- `tests/test_pitcher_k_outcome_dataset.py`
- `tests/test_k_projection_shadow_lab.py`
- `tests/test_executable_market_shadow_audit.py`

Current readout from 2026-05-07:

- Clean regime rows are sufficient to choose the next analysis track.
- Global projection residual is close enough to neutral that a broad lambda
  correction is not the first move.
- Bet conversion/ranking is the clearest business problem.
- FIRE 2u sample is still too small for a staking ladder decision.
- Quality gates are live and useful, but not a complete ranking solution.
- Market-price context is now part of the shadow read. The whole-market archive
  audit includes PASS-level pitcher markets and tracks price buckets, over/under
  side outcomes, plus/minus prices, and relative favorite behavior such as
  `-115` versus `-105`. It also tracks model-versus-market-favorite agreement,
  K-line buckets, no-vig market probabilities, miss distance, book-specific
  side/price buckets, and side-specific price movement contexts. Use it to
  question price-sensitive selection patterns, not to change live rules
  directly.
- Live-market outcome context is now a separate shadow read. BoltOdds/PropLine
  evidence can be joined to graded rows by slate, normalized pitcher, and side,
  with special attention to pregame checkpoints rebuilt from raw snapshots. This
  is the correct layer for "market moved with us/against us" outcome testing,
  especially broad-book moves, single-book noise, reversals, over/under splits,
  and plus/minus flips.
- The pitcher K outcome research dataset now has Gate A/B local proof. The
  local diagnostic writes `analytics/output/pitcher_k_outcome_dataset.jsonl`
  and `analytics/output/pitcher_k_outcome_dataset_summary.md` from committed
  archive rows. On the 2026-04-28+ clean window it produced 574 graded side rows
  with zero duplicate keys, zero missing team/opponent, and zero missing odds.
  It reconciled 294/294 clean graded `picks_history.json` rows, including 15
  unique pitcher/side fallback matches where the archived official-close line
  differed from the locked pick-history line. This is still local/shadow-only;
  it does not require a Supabase upgrade unless a later Gate C decision promotes
  compact daily storage.
- The detailed source of truth for this tracker stack now lives in
  `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`.
  That plan owns Gate C confidence-referee scope, runtime-safe versus
  hindsight-only field boundaries, batter-handedness Path A/Path B,
  opportunity/leash evidence, K-projection challenger evidence, and promotion
  gates. Keep this file as a status snapshot, not the detailed rulebook.
- The same dataset now carries compact bet-time/CLV, model-vs-market,
  pitcher-handedness, lineup-shape placeholder, and opportunity/leash tracker
  fields. The 2026-04-28+ local run populated price CLV for all 294 tracked
  picks, with 51 rows beating the official-close price and 10 beating the
  official-close line. Treat this as a weekend evidence tracker for BoltOdds
  timing quality, not as a model-rule change.
- The compact row also carries derived research labels so future work does not
  duplicate storage for questions already answerable from existing fields:
  `clv_type`, `process_outcome_bucket`, `bet_timing_window`,
  `large_edge_skepticism_flag` / reasons, and `pitcher_archetype_bucket`.
  The 2026-04-28+ local run currently shows 61 tracked rows with some CLV edge,
  233 tracked rows with no CLV edge, and 134 model-preferred/actionable rows
  where a large edge also had stacked caution signals. Use these labels to ask
  better review questions, not to change live thresholds.
- The K projection shadow lab now reuses the compact outcome dataset to compare
  transparent challenger projections against the current lambda. The 2026-04-28+
  local run scored 287 official-close market rows: `market_shrink_25` improved
  MAE/RMSE slightly versus the current model, `high_line_temper` improved side
  accuracy slightly, and simple recent/career rate blends were worse. Treat this
  as projection-lab evidence only, not a live model-rule change.
- The best-executable market shadow audit scores over/under EV for each fresh
  supported book line after provider mainline selection. Use it during the
  Monday BoltOdds + PropLine review to separate single-book outliers from
  ref-book-vs-majority conflicts and to see whether disagreement would have
  created better executable candidates. It is not a promotion plan; any live
  best-line selection needs CLV/outcome proof and separate approval.
- Use `docs/research/market-tracker-map.md` as the current tracker inventory
  before adding more BoltOdds/Supabase tracking. It distinguishes existing raw
  evidence tables from the compact long-term research row.
- The weekday `BBE Operations Brief` should now digest the tracker stack daily:
  market-price audit, live-market outcome audit, pitcher K outcome dataset,
  BoltOdds heartbeats/snapshots/coverage, price CLV, line CLV,
  model-versus-market relationship, opportunity/leash buckets, and
  lineup-handedness field availability. The brief should explain what changed
  without promoting live model behavior.
- As of the 2026-05-20 read, keep a compact Gate C bucket scoreboard in the
  daily brief and compare it to the immediate pre-bump window only as context.
  Use 2026-04-08 through 2026-04-27 as the fair pre-bump reference and
  2026-04-28+ as the clean current regime. The important current finding is
  inversion, not rollback: pre-bump FIRE 1u, unders, and high-edge rows were
  strong, while post-bump FIRE 1u, unders, and high-edge rows are weak;
  post-bump FIRE 2u, overs, moderate-edge, beat-close-price, and pre-30 timing
  rows look more promising. This remains shadow-only until the May 12 plan's
  Gate E/F standards justify a separate promotion plan.

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

Use `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
as the controlling plan. Use
`docs/superpowers/plans/2026-05-07-bet-conversion-shadow-audit.md` only as
historical context for the first shadow diagnostic.

The next model-facing work should compare adjusted EV, raw edge, model margin,
side-specific conversion, quality-gate context, opening-source context,
market-price/favorite context, live-market movement context, price/line CLV,
model-versus-market relationship, opportunity/leash context, and K-projection
challenger evidence in shadow. It should also keep batter-handedness and
lineup-shape evidence collection-only until the May 12 plan's Path B checks
pass. Do not promote a live rule from one positive bucket or one slate.
Preserve the rolling pre/post 2026-04-28 bucket comparison as interpretation
context, but let the clean current regime drive Gate E/F candidate thinking.

### Pitcher K Outcome Research Dataset

Use `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`.

The dataset plan is now the concentrated rulebook for Gate C
confidence-referee work, compact storage, daily collection, research readiness,
batter-handedness Path A/Path B, opportunity/leash evidence, and promotion
boundaries. It must stay shadow-only until a separate model/ranking promotion
plan is approved.

### BoltOdds Trial Review

Use `docs/superpowers/plans/2026-05-07-boltodds-starter-trial.md`, and for
official-provider cutover work use the 2026-05-13 cutover plan on
`codex/boltodds-production-plan`.

Review uptime, heartbeat freshness, normalized row coverage by target book,
stale-feed risk, row volume risk, and whether the feed would have changed
timing or notification decisions. Do not buy Pro or promote BoltOdds without a
post-trial decision.

Before raw `market_snapshots` retention is enforced, the cutover branch still
needs compact movement rollups and provider request-usage writes to prove the
storage/cost path is safe.

As of 2026-05-21, Supabase is on Pro. The first surprise-bill guardrail is to
track total database size, top table size, and egress before adding more capture
volume. If the database approaches `6 GB`, egress trends toward the plan
allowance, or `market_snapshots` keeps growing without changing decisions, pause
new capture work and run retention dry-runs before considering overages.

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
