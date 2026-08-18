# Current State

Last updated: 2026-08-06

## Read Order

For any new work in this repo:

1. Read `AGENTS.md` for the canonical project instructions and architecture notes.
2. Read this file for the current operating state.
3. Read `docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md`
   for the active gate index and to separate operational/display surfaces from
   still-closed production promotion gates.
4. Read the newest active dated plans that match the task:
   - `docs/superpowers/plans/2026-06-10-profit-rescue-and-strict-provider-readiness.md`
     for the downgrade-only FIRE exposure rescue canary and the read-only
     strict-provider readiness report
   - `docs/superpowers/plans/2026-06-13-market-anchored-k-shadow-rebuild.md`
     for the shadow-only market-anchored K projection/selector rebuild report
   - `docs/superpowers/plans/2026-06-16-market-anchored-v2-selector-shadow-canary.md`
     for the feature-flagged market-anchor selector shadow/canary plan
   - `docs/superpowers/plans/2026-07-23-research-evidence-reconciliation-and-market-anchor-review.md`
     for the exact Gate C outcome-recovery, bounded compact market-agreement
     export, expanded market-anchor review, and gated research-cron rollout
   - `docs/superpowers/plans/2026-07-29-market-anchor-downside-review.md`
     and `docs/research/market-anchor-downside-review-packet.md` for the exact
     paired downside cohort and the current `keep_shadow` decision
   - `docs/superpowers/plans/2026-07-29-strong-base-fire-policy-shadow-matrix.md`
     and `docs/research/strong-base-fire-policy-shortlist.md` for the six
     frozen FIRE policies and the July 30 prospective shortlist
   - `docs/superpowers/plans/2026-05-13-boltodds-propline-official-provider-cutover.md`
     for historical provider-arbitration context only; BoltOdds active runtime
      was retired on 2026-06-17 and the current production posture is
      non-strict TheRundown+PropLine official mode with direct TheRundown
      fallback
   - `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
   - `docs/superpowers/plans/2026-06-05-market-favorite-confidence-referee-production-canary.md`
     for the Tyler-approved market-favorite confidence-referee production
     canary plan
   - `docs/superpowers/plans/2026-06-07-market-agreement-tracker.md`
     for the shadow-only market agreement tracker that evaluates LEAN, FIRE,
     and confidence-referee capped picks against live market movement
   - `docs/superpowers/plans/2026-06-03-market-favorite-confidence-referee-shadow-plan.md`
     for active market-favorite confidence-referee shadow work
   - `docs/superpowers/plans/2026-06-03-gate-f-projection-challenger-shadow-plan.md`
     for active Gate F projection-challenger shadow work
   - `docs/superpowers/plans/2026-06-22-market-shrink-projection-production-canary.md`
     for the active shadow-only market-shrink projection production canary
     after the 2026-06-22 Gate F report marked `market_shrink_15`,
     `market_shrink_25`, and `market_shrink_35` as
     `promotion_plan_candidate`
   - `docs/superpowers/plans/2026-06-08-workload-no-vig-k-projection-ev-synthesis.md`
     for the shadow-only workload, no-vig EV, Path B, and
     confidence-referee interaction synthesis
   - `analytics/diagnostics/bet_selection_edge_synthesis.py`
     (report: `analytics/output/bet_selection_edge_synthesis.md`) for
     shadow-only bet-selection/edge slices from the durable Gate C row
   - `analytics/diagnostics/strong_base_decision_lab.py`
     (report: `analytics/output/strong_base_decision_lab.md`) for the
     shadow-only Strong Base Expansion and Exposure Reduction Lab that
     reconciles positive CLV against mass portfolio losses
   - `analytics/diagnostics/strong_base_portfolio_simulator.py`
     (report: `analytics/output/strong_base_portfolio_simulator.md`) for the
     read-only policy simulator that compares current FIRE staking,
     drag-suppressed tracked picks, strict retained FIRE, selective LEAN
     expansion, PASS expansion, and CLV-confirmed hindsight ceilings
   - `analytics/diagnostics/shadow_signal_synthesis_lab.py`
     (report: `analytics/output/shadow_signal_synthesis_lab.md`) for the
     read-only synthesis that stacks Strong Base, market-anchor,
     market-agreement, and pre-close proxy signals into combined policy-shape
     scoreboards
   - `analytics/diagnostics/market_anchor_downside_counterfactual_audit.py`
     for the exact paired, pre-start, would-change market-anchor downside read
   - `analytics/diagnostics/strong_base_fire_policy_matrix.py`
     for immutable downside-cap and retained-FIRE policy fingerprints,
     incremental value, overlap, slices, and prospective counters
   - `docs/superpowers/plans/2026-07-21-no-drag-composite-prospective-canary.md`
     for the controlling frozen post-grading v1 implementation plan
   - `docs/research/no-drag-composite-prospective-canary-packet.md`
     for the lead operator packet for the no-drag prospective canary
   - `docs/research/2026-07-28-no-drag-strict-runtime-core-review-packet.md`
     for the early-trigger review after no-drag reached `75/75`, including the
     strict-runtime-core comparison and the still-closed promotion gates
   - `docs/research/2026-07-28-artifact-publisher-timeout-resilience-review.md`
     for the scoped diagnosis of recurring lock-publisher PostgREST statement
     timeouts and the separately gated publisher-only resilience options
   - `docs/research/2026-07-29-research-candidate-plan-map.md`
     for the July 29 candidate inventory, the distinction between volume and
     evidence-diversity gates, and links to the six bounded follow-up plans
   - `docs/superpowers/plans/2026-07-29-no-drag-and-strict-runtime-prospective-review.md`
     for the implemented frozen strict-runtime-core audit, its July 30
     prospective boundary, and the still-future August 10 independent review
   - `docs/superpowers/plans/2026-07-29-market-shrink-retirement-decision.md`
     and `docs/research/market-shrink-retirement-review.md` for the decision to
     retain market-shrink as projection-error diagnostics only while closing
     its betting-promotion path
   - `docs/superpowers/plans/2026-07-29-clv-process-target-validation.md`
     and `docs/research/clv-process-target-review.md` for the offline final-CLV
     process target, its bounded compact-input contract, and the current
     `keep_as_process_kpi` decision
   - `docs/research/2026-07-30-umpire-ytd-name-audit.md` for the read-only
     1,627-game name-set audit, the eight active names missing from the live
     cache, and the decision to leave production umpire inputs unchanged until
     a separate prior-smoothed coverage review is approved
   - `docs/superpowers/specs/2026-07-21-pregame-alternative-pick-methodology-design.md`
     for the approved product direction, production rollout contract, and
     first-normal-slate integrity gate for the pregame Alt Picks comparison
     surface; code, migration, isolated record mode, endpoint, and UI are live,
     the first-normal-slate provisional/frozen integrity proof passed on
     2026-07-22, and every official promotion gate remains closed
   - `docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md`
     for Tyler's approved design to replace the v1 global pending veto with
     dependency-aware lane resolution and exact candidate-grain Preclose
     evidence; the test-first implementation plan is
     `docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md`.
     The isolated V2 comparison recorder and versioned Alt Picks UI are live.
     The 2026-07-24 current-artifact linkage repair produced the first healthy
     prospective slate. The next normal `18:37:45Z` refresh then proved the
     endpoint-only bridge on `55a36b3e`: after the V2 recorder wrote 19
     provisional rows at `18:40:44Z`, the endpoint served all 19 by
     `18:41:40Z` with one selected Consensus Core row and one pending row,
     before the later lock republish could normalize the publisher and recorder
     logical hashes. The exact served-body hash still matched the recorder's
     bound byte hash, so the brief full/refresh-to-lock handoff is repaired
     without weakening fail-closed artifact linkage. Official picks, model
     math, staking, providers,
     notifications, locks, accepted bets, artifacts, and history remain
     unchanged and closed to promotion. The first immutable V2 T-30 checkpoint
     then passed on Shane Drohan OVER 5.5: it froze at `19:40:21Z`, 29.64
     minutes before first pitch, matched the exact operational-lock artifact,
     and was consumed at `19:42:23Z`. The row was correctly `not_selected`;
     there are zero duplicate groups, malformed/missing proofs, Alt
     notifications, or Alt accepted-bet writes. Next evidence needed is the
     first selected T-30 freeze and a genuinely prospective graded outcome.
     The selected-freeze gate then passed on Matthew Boyd UNDER 5.5:
     Consensus Core froze at `22:10:36Z`, 29.39 minutes before first pitch,
     and the exact operational lock was consumed at `22:12:34Z` with every
     candidate/artifact linkage field matching. The remaining evidence gate is
     a genuinely prospective graded outcome. Tyler approved the dashboard-only
     recovery repair on 2026-07-24. The Alt tab now fetches immediately, polls
     every 60 seconds only while mounted, prevents overlapping reads, preserves
     the last healthy response through later failures, and cache-busts both
     frontend assets. Netlify deploy `6a63e8d36373af0008e5c6ed` proved those
     assets on exact commit `049276bc`, but Chrome then supplied stronger
     evidence: direct access to the function URL failed
     `ERR_BLOCKED_BY_CLIENT` while the endpoint itself remained healthy.
     The follow-up exact commit `8fba5303` and ready Netlify deploy
     `6a63ea91d4787300084cadc6` add only the neutral same-origin
     `/api/slate-comparison` rewrite and a fresh adapter token. The route
     returned current V2 JSON with 11 frozen rows and two selected at the
     22:43Z checkpoint. Tyler then reproduced the same unavailable state in
     normal Chrome and on his phone, superseding the transport hypothesis.
     Exact live-response validation isolated one client-contract mismatch:
     Matthew Boyd validly selected Consensus Core with Anchor plus Re-entry,
     zero qualifying Preclose observations, and Base already short-circuiting
     composite Preclose to disagreement. The endpoint accepted the proof, but
     the browser incorrectly allowed selected zero-observation rows only when
     the displayed Preclose family stayed pending. Exact commit `31005482` and
     completed Netlify deploy `6a63ed9fd8afa30008e443c8` now permit pending or
     disproved nonessential Preclose while still rejecting zero-observation
     Preclose agreement. The exact live payload normalized with 13 frozen rows
     and two selected, and production Chrome rendered Trevor Rogers, Matthew
     Boyd, and 11 supporting rows. All 173 JavaScript tests and 1,928 Python
     tests passed. No alternate script transport is required or approved; this
     remains comparison-only and changes no model, selector, provider, lock,
     notification, accepted-bet, artifact, history, or source-of-truth behavior
   - `docs/research/strict-runtime-core-selective-lean-canary-packet.md`
     for comparison/control historical context on
     `strict_runtime_core_plus_selective_lean`, not the lead candidate
   - `docs/research/all-star-break-operations-packet.md`
     for the 2026-07-13 break-window checklist, off-day artifact-noise fix
     scope, strict-runtime actual-record read, and cost/row-volume notes
   - `analytics/diagnostics/market_anchored_k_shadow_rebuild.py`
     (report: `analytics/output/market_anchored_k_shadow_rebuild.md`) for
     the shadow-only rebuild experiment that starts from market-implied K
     projection and adds a shrink-adjusted baseball signal
   - `scripts/run_post_grading_shadow_reports.py` for the review-only daily
     post-grading command that rebuilds Gate C/workload/no-vig/market-anchor,
     Strong Base, market-agreement, synthesis, paired downside, and FIRE policy
     matrix reports and prints decision-facing excerpts to scheduler logs
   - `docs/superpowers/plans/2026-06-07-batter-handedness-path-b-canary.md`
     for the Tyler-approved, feature-flagged batter-handedness Path B canary
   - `docs/superpowers/plans/2026-05-20-live-market-decision-ui.md`
     for the default-on, display-only live-market decision UI and accepted-bet
     live-book selector flow
   - `docs/superpowers/plans/2026-06-04-live-notification-digest-coordinator.md`
     for the active notification grouping and movement-strength implementation
     path
   - `docs/superpowers/plans/2026-05-22-github-artifact-exit.md`
     for the Render/Supabase artifact path, Netlify `get-artifact`, and GitHub
     manual rollback posture
   - `docs/superpowers/plans/2026-05-07-bet-conversion-shadow-audit.md`
     only as historical diagnostic context for the first bet-selection audit
5. Read `docs/provider-cost-ledger.md` before recommending new providers,
   upgrades, polling increases, or always-on infrastructure.
6. Read `docs/operational-risk-register.md` before changing provider behavior,
   notification behavior, retention, live workers, or source-of-truth rules.
7. Use older dated plans in `docs/superpowers/plans/` as archive context, not
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
  justify a live behavior plan. On 2026-06-05, Tyler approved drafting a
  feature-flagged market-favorite confidence-referee production canary and
  waived the remaining 16-row validation shortfall; this is documented in
  `docs/superpowers/plans/2026-06-05-market-favorite-confidence-referee-production-canary.md`.
- Active model-facing child plans are now the market-favorite confidence-referee
  production canary plan, the market-favorite confidence-referee shadow plan,
  the Gate F projection-challenger shadow plan, and the market-shrink
  projection production-canary plan. The confidence-referee canary plan is
  verdict-conversion only. Tyler approved activating
  `MARKET_SHRINK_PROJECTION_MODE=shadow` on 2026-06-22; `enforce` still
  requires a separate Tyler decision. Neither plan approves global thresholds,
  staking, provider, notification, lock, retention, or dashboard-source changes.
- On 2026-06-07, Tyler approved promoting `MARKET_FAVORITE_REFEREE_MODE` from
  `shadow` to `enforce` on the Render pipeline cron group and promoting
  `LIVE_NOTIFICATION_COORDINATOR_MODE` from `shadow` to `grouped` on
  `bbe-live-layer`. These are existing feature-flag promotions only. They do
  not change lambda, global thresholds, staking, provider order, locks,
  retention, dashboard source-of-truth, or provider strictness.
- Also on 2026-06-07, Tyler approved a feature-flagged personal-use
  batter-handedness Path B canary. This canary is controlled by
  `BATTER_HANDEDNESS_MODE=path_a|path_b`; it may use live-collected,
  PA-backed split samples from `data/batter_splits_YYYY.json` when available,
  with per-batter Path A fallback. It must not use historical handedness
  backfill as a live input and does not change thresholds, staking, provider
  order, notifications, locks, retention, or dashboard source-of-truth. As of
  2026-06-07, `BATTER_HANDEDNESS_MODE=path_b` is active on the seven Render
  pipeline cron services. The first same-day verification was partial because
  several games had already started before activation.
- As of 2026-06-24, Tyler approved the narrow live official-provider posture
  shift to `OFFICIAL_MARKET_SOURCE=therundown_propline` with
  `ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE=true`,
  `OFFICIAL_MARKET_SOURCE_FALLBACK=therundown`, and
  `OFFICIAL_MARKET_STRICT=false` for live Render preview/full runs only. This is
  a non-strict curated-official-lines path with TheRundown direct fallback, not
  strict provider mode, not a model/staking/threshold change, and not a lock or
  dashboard contract change. The older non-strict BoltOdds + PropLine
  provider-source canary is retired from official artifact runs. GitHub manual
  `workflow_dispatch` remains a TheRundown rollback path unless separately
  changed.
- PropLine is now part of the approved non-strict TheRundown+PropLine official
  provider mode through curated `official_market_lines`; PropLine webhooks
  remain movement/timing evidence only. Webhook evidence processing keeps the
  180-minute inbox window, but webhook movement notifications have a separate
  20-minute queue-eligibility gate so stale webhook rows can be archived without
  creating dead notification rows. The live-alert supported/actionable book
  allow-list is FanDuel, DraftKings, BetMGM, BetRivers, Kalshi, Caesars, and
  theScore/scorebet; the PropLine polling fallback target set remains narrower.
- As of 2026-06-12 evening Phoenix time, the TheRundown mainline shadow canary
  is active in the Render `bbe-live-layer` loop behind
  `LIVE_CAPTURE_THERUNDOWN_MAINLINE=true`.
  The first implementation also remains available in the observation-only
  `shadow-market-infra` workflow for manual dispatch, but scheduled GitHub
  TheRundown capture is off because GitHub delivery proved too sparse for the
  primary 10-minute canary cadence. Both paths write only observation rows to
  existing Supabase market trackers (`market_provider_runs`, `market_events`,
  `market_snapshots`, and `provider_coverage_audits`) with data-point header
  metadata. The first verified scheduled Render run completed at
  `2026-06-13T05:30Z` with `174` TheRundown data points, `120` snapshots, and
  `30` parsed pitcher-line groups. This is not a provider-source switch, not a
  notification source, and not a model/dashboard/artifact change. TheRundown
  mainline polling plus PropLine webhooks is now the leading low-cost
  replacement thesis for BoltOdds. On 2026-06-14, after a clean cost/usage
  read and live webhook proof, Tyler approved moving forward with this
  low-cost path: keep TheRundown as the official source for artifacts and
  high-frequency mainline evidence, allow PropLine supported-book webhook rows to
  drive live line/price movement notifications behind
  `LIVE_SEND_PROPLINE_WEBHOOK_MOVEMENT_NOTIFICATIONS=true`, and retire
  BoltOdds spend before the next renewal. On 2026-06-17, Tyler approved killing
  the active BoltOdds runtime; Render worker `bbe-boltodds-shadow-worker`
  (`srv-d7ugabe7r5hc73b36oag`) was suspended via Render API, and post-suspend
  checks found zero BoltOdds heartbeats or snapshots after
  `2026-06-17T17:22:29Z`. This is not approval for
  `OFFICIAL_MARKET_SOURCE=boltodds_propline`, strict provider mode, model
  changes, staking changes, or dashboard source-of-truth changes.
- BoltOdds is retired from active runtime. Historical rows remain research
  evidence only and must not affect production picks, grading, dashboard
  artifacts, provider order, notifications, or model behavior.
- As of 2026-07-07, the mainline best-price notification policy is live in
  `send` mode on Render `bbe-live-layer` after Tyler explicitly approved
  skipping shadow. Local verification passed:
  `python -m pytest tests/test_mainline_price_notifications.py tests/test_market_infra_live_events.py tests/test_live_layer_worker.py tests/test_live_layer_schema.py -q`
  returned `85` passing tests, `node --test
  tests/test_send_live_notifications_function.mjs` returned `20` passing tests,
  and `git diff --check` returned clean. Supabase migration
  `20260707190000_mainline_price_notification_event_type.sql` is applied and
  the live `notification_events_event_type_check` constraint allows
  `mainline_best_price_changed`. Render deploy
  `dep-d96m057avr4c73a2f85g` is live on commit `8871b3c3`, with
  `LIVE_MAINLINE_PRICE_NOTIFICATION_MODE=send` and
  `LIVE_MAINLINE_PRICE_MIN_CENTS=10`. First verified scheduled run observed at
  `2026-07-07T20:30:29.605579Z` had `mainline_best_price.mode=send`,
  `input_count=38`, `candidate_count=0`, and `notification_count=0`; no
  `mainline_best_price_changed` rows were queued because no qualifying
  transition occurred on that tick. This changes only live notification event
  creation and suppresses the old raw polling/webhook movement notification
  rows in `send` mode; it does not change model math, provider order, official
  artifacts, thresholds, staking, locks, retention, dashboard source-of-truth,
  or grading. Rollback is `LIVE_MAINLINE_PRICE_NOTIFICATION_MODE=off` plus a
  `bbe-live-layer` redeploy.
- As of 2026-07-08, Tyler approved the non-strict combined TheRundown+PropLine
  live-display/main-line best-price path. The live layer still writes
  individual `therundown` and `propline` rows for audit, then adds
  `provider=therundown_propline` combined rows for the app-facing book board
  and best-price notification candidate selection when both providers have the
  same pitcher/side. The combined row dedupes duplicate books and uses only the
  pick's same K line for primary `best_book` / `best_line` / `best_odds`;
  different-line books remain visible as book-board context. This is not strict
  provider mode and does not change official artifacts, model math, thresholds,
  staking, locks, retention, dashboard source-of-truth, or grading.
- As of 2026-06-09, active soaks and promotion gates are formalized in
  `docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md`.
  Treat PropLine and historical BoltOdds dashboard display as operational
  evidence, but keep
  official provider source, strict provider mode, new movement notification
  classes, model/lambda/threshold/staking changes, and retention deletion as
  separate closed gates until their pass criteria are met and Tyler approves.
- As of 2026-06-10, Gate 12A in the active-gates synthesis formalizes
  candidate-specific bet-selection gates for `clv_supported`,
  `high_edge_skeptic`, `fire_under_watch`, `moderate_edge_clean_context`, and
  market-agreement buckets. These are Gate E/F review rules only; they do not
  approve automatic LEAN promotion, FIRE downgrades, thresholds, staking,
  lambda, provider, notification, lock, retention, or dashboard-source changes.
- Also on 2026-06-10, Tyler approved `PROFIT_RESCUE_REFEREE_MODE=enforce` as a
  downgrade-only FIRE exposure canary. All seven Render pipeline cron services
  were updated and redeployed on commit `c60bd895`. `shadow` still adds
  metadata only; `enforce` can only lower remaining FIRE exposure after quality
  and confidence-referee caps. This does not approve LEAN promotion, lambda
  changes, thresholds, staking, provider changes, notifications, locks,
  retention, or dashboard source-of-truth changes.
- As of 2026-06-17, `bbe-gate-c-post-grading-review`
  (`crn-d8mpcb0g4nts73fq5bv0`) runs
  `python scripts/run_post_grading_shadow_reports.py` as the review-only
  post-grading command for the Gate C/workload/no-vig/market-anchored model
  research read plus the active shadow trackers: confidence-referee canary,
  profit-rescue audit, bet-selection edge synthesis, market-agreement tracker,
  Gate F projection challenger report, and optional shadow-notification
  candidate audit when a bounded candidate export is provided. Schedule is
  `7 11 * * *` UTC (`4:07 AM` Phoenix), after
  `bbe-pipeline-grading` at `17 10 * * *` UTC. AutoDeploy is off. One-off
  Render verification job `job-d8mpda1o3t8c73c3lerg` succeeded on
  2026-06-13. This command prints the market-anchor Executive Read and Read
  Rule plus selector input coverage to scheduler logs and does not publish
  dashboard artifacts, update
  calibration, change lambda, change thresholds/staking, change provider
  behavior, change notifications, change locks, or change retention.
  2026-07-09 update: Tyler approved redeploying this read-only cron after the
  shadow signal synthesis work. Render deploy `dep-d97ujla8qa3s73aqa53g` is
  live on commit `6d30632d` (`feat: add shadow signal synthesis packet`), and
  one-off verification job `job-d97ul53tqb8s739hptf0` succeeded with the same
  `python scripts/run_post_grading_shadow_reports.py` start command. Service
  readback stayed unchanged: branch `main`, autoDeploy off, schedule
  `7 11 * * *`, and the same review-only command.

## Four-Lane Operating Board

Use this board to keep the active workstreams visible without turning every
new idea into a separate source of truth. The BBE Operations Brief should
summarize these lanes daily and call out only the next decision or blocker for
each lane.

| Lane | Current Source | Current Stage | Next Decision |
| --- | --- | --- | --- |
| Pipeline / infrastructure | `2026-05-19-supabase-operational-foundation.md`, `2026-05-22-github-artifact-exit.md`, `2026-05-13-boltodds-propline-official-provider-cutover.md`, `2026-05-20-live-notification-coordinator.md`, `2026-06-04-live-notification-digest-coordinator.md`, `2026-06-10-profit-rescue-and-strict-provider-readiness.md`, `2026-06-19-therundown-propline-official-provider-and-webhook-evaluation.md`, `2026-07-07-mainline-best-price-notification-policy.md`, `2026-08-14-supabase-pressure-repairs.md`, `docs/operational-risk-register.md` | Render + Supabase artifact API are the primary scheduler/artifact path as of 2026-05-30. GitHub scheduled triggers are disabled, but manual `workflow_dispatch` remains the rollback path. As of 2026-06-24, Tyler approved the live preview/full wrapper shift to non-strict `OFFICIAL_MARKET_SOURCE=therundown_propline`, `ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE=true`, `OFFICIAL_MARKET_SOURCE_FALLBACK=therundown`, `ENABLE_BOLTODDS_PIPELINE_SOURCE=false`, and `OFFICIAL_MARKET_STRICT=false`; Render lock and grading commands stay unchanged. The older non-strict BoltOdds + PropLine provider-source canary through `official_market_lines` is retired from official artifact runs, and `--provider-rehearsal` now fails closed unless `ALLOW_BOLTODDS_PROVIDER_REHEARSAL=true` is set after a new Tyler-approved provider trial. Render preview, pipeline/full/refresh, and lock modes publish only the artifact keys each mode can actually regenerate; Render grading/full/refresh/lock hydrate from Netlify `get-artifact` before running so stale checkout copies of history, params, performance, preview lines, or the optional FanGraphs last-good cache are not republished. `bbe-pipeline-lock` runs every 10 minutes offset behind the live-layer lock ledger and can replay already-consumed Supabase lock rows if a prior stale artifact publish left the dashboard behind. As of 2026-08-14, lock-scope publication compares canonical payload hashes and skips unchanged artifact payload upserts while preserving the publication-run audit row; the first clean scheduled post-deploy run recorded three candidates, three unchanged, and zero artifact upserts on commit `5bc06334`. The linked PropLine webhook inbox now has a ready/valid partial `received_at` index for unprocessed rows, and the live query shape used it in post-migration proof. Dashboard artifact adapters default to Netlify `get-artifact` with static fallback. As of 2026-06-07, Render `bbe-live-layer` runs `LIVE_NOTIFICATION_COORDINATOR_MODE=grouped` with start-window and pick-change grouping flags enabled; Supabase allows digest event types and user-facing sends are grouped only for those approved classes. As of 2026-07-07, Render `bbe-live-layer` also runs `LIVE_MAINLINE_PRICE_NOTIFICATION_MODE=send` and `LIVE_MAINLINE_PRICE_MIN_CENTS=10` after Tyler explicitly approved skipping shadow. This replaces the old raw book-by-book polling/webhook movement pushes with same-main-line best-price-change alerts when a qualifying transition occurs; raw movement rows remain audit evidence. As of 2026-06-24, PropLine webhook evidence processing keeps the 180-minute inbox window, while webhook movement notification queueing has a separate 20-minute freshness gate; this is still movement-only and not an odds-source switch. FanGraphs SwStr and batter aggregate K% fetches now write/read `data/fangraphs_cache.json`; preview/full/refresh publish it as optional `fangraphs_cache` artifact so future 403s can reuse fresh last-good stats before falling fully neutral. Hosted Supabase allows `fangraphs_cache` in `published_pipeline_artifacts`. Render pipeline cron services keep autoDeploy off; after an approved main push, use `python scripts/deploy_render_pipeline_crons.py --execute` to redeploy preview, grading, full, refresh, and lock as one validated group. | Observe one naturally changed lock cycle to prove required lock artifacts still publish, and watch normal slates for recurrence of REST `57014` pressure failures; do not manufacture a lock or change cadence. Keep the compact/current market snapshot truncation repair in a separate plan. Collect five normal slates of ready-shadow overlap and false-candidate evidence before any ready-to-bet send/suppression review; `LIVE_READY_TO_BET_SHADOW=record` remains record-only. Keep model, staking, thresholds, retention deletion, default dashboard UI, strict provider mode, and `OFFICIAL_MARKET_SOURCE=boltodds_propline` separate. |
| Model | `2026-05-12-pitcher-k-outcome-research-dataset.md`, `2026-07-29-no-drag-and-strict-runtime-prospective-review.md`, `2026-07-29-market-anchor-downside-review.md`, `2026-07-29-strong-base-fire-policy-shadow-matrix.md`, `2026-07-29-market-shrink-retirement-decision.md`, `2026-07-29-clv-process-target-validation.md`, `2026-08-14-selective-lean-prospective-audit.md` | Gate C remains the canonical research input; active canaries remain bounded and do not approve live model, threshold, staking, provider, notification, lock, retention, or dashboard-source changes. No-drag and strict-runtime remain separate controls. Market-anchor remains shadow, Strong Base FIRE policies remain frozen, market-shrink remains diagnostic-only, and final CLV remains a process target with no approved close-packet producer. As of 2026-08-14, `expand_lean_low_line_capped_model_fade` is also frozen as a research-only prospective counter: historical `103`, `55-48`, `+11.416u`; current provider `56`, `28-28`, `+3.000u`; formal prospective `0/75` from 2026-08-15. | Keep all live gates closed. Selective LEAN cannot earn prospective credit until Gate C carries consumed-lock linkage plus complete provider/agreement attribution; then require 75 graded rows, UNDER/plus-price diversity, positive prospective/latest-14 PnL, and complete nonnegative mandatory slices. Treat any passed counter as permission for a separate review only. |
| UI | `2026-05-20-live-market-decision-ui.md`, `2026-05-20-live-notification-coordinator.md`, `2026-06-04-live-notification-digest-coordinator.md` | Phase 2 live market-decision UI is now default-on for actionable cards, with `?marketSheet=0` as the rollback/opt-out. `dashboard/v2-data.js` fetches `/.netlify/functions/live-market-display` by default and attaches sanitized `live_market_display_state` rows; the Netlify function reads with server-side Supabase credentials and returns app-safe allow-listed rows plus sanitized `book_rows` / `movement_events`. `dashboard/v2-app.jsx` keeps PASS cards quiet and shows actionable-card market strips, detail-sheet market panels, a compact book board with Best / Model ref / Same line / Different line / cushion tags, and Log Bet live-book selection that fills the existing line, odds, and book fields. The existing Log Bet modal still records through the existing accepted-bet path, preserves matched push/shadow-review `notification_event_id` / `shadow_candidate_id`, supports same-day review/duplicate warnings and append-only corrections, and keeps manual edits available. This is a UI readout only and does not change provider/source-of-truth, model, threshold, staking, lock, retention, notification, or accepted-bet API behavior. | Verify same-line defaulting and alternate-line context on the next normal slate, including that alternate-line rows remain manually selectable but cannot auto-prefill Log Bet. Retain `?marketSheet=0` as rollback/opt-out and keep provider promotion, betting-rule changes, broader edit/delete audit, and notification behavior separate. |

| Tracking / data collection / history | `docs/research/market-tracker-map.md`, `docs/research/pitcher-k-outcome-dataset.md`, `2026-06-07-market-agreement-tracker.md`, `2026-08-18-season-retention-foundation.md`, `2026-08-18-bounded-retention-audit-design.md`, `2026-08-18-bounded-retention-audit.md`, compact outcome outputs, live-market audits | Canonical research and market/live/provider trackers remain active. Season-retention Phase 1 is complete and merged on local `main` at `c74385a7`; the exact reporter fails closed on contradictory coverage, incomplete provider/runtime equality, stale Phoenix-day evidence, missing decision linkage/pins, and incomplete retired-BoltOdds preservation. Live verification is still blocked: the first monolithic SELECT-only audit failed with PostgreSQL `53100` temporary-file exhaustion, and the separately approved repaired attempt passed local preflight but failed with PostgreSQL `57014` statement timeout after about two minutes. It returned no stdout, generated no reports, changed no data, and was not retried. Latest verified sizing remains approximately 3.866M `market_snapshots` rows / 3,238 MB, so the full-season materialize-and-window-sort shape is not live-viable under the observed hosted limits. Tyler approved the replacement written design; its implementation plan now decomposes serial adaptive chunks, one-date canaries, atomic checkpoints, complete-matrix reconciliation, version 2 reporting, and fixture-only verification into five local review gates. | Choose subagent-driven or inline execution for the local implementation plan. Implementation does not authorize a live Supabase read; request fresh approval after code review for each one-date canary, runtime-boundary read, or capped multi-chunk invocation. Keep Phase 2, Phase 3, backfill, migration, retention activation, deletion, vacuum, provider/model/notification/lock/UI changes, push, and deployment closed. |

### August 14 selective-LEAN prospective-counter overlay

Tyler approved the bounded research implementation, merge, push, and hosted
research-cron deployment. No database, model, provider, notification, lock,
UI, history, artifact, retention, or source-of-truth behavior change is
authorized by this overlay.

| Lane | Confirmed evidence | Next decision |
| --- | --- | --- |
| Model | `expand_lean_low_line_capped_model_fade` is frozen at fingerprint `4e00a180e35fe75dc8889d47065a25c4351cb37ac55664eb42f01b77c07fd13a`. Historical nomination is `103`, `55-48`, `+11.415935u`; current-provider is `56`, `28-28`, `+2.999676u`. Formal prospective evidence begins 2026-08-15 at `0/75`; August 13-14 are explicitly excluded. | Continue research only. Require 75 eligible rows, 20 UNDER, 10 plus-price, positive prospective/latest-14 PnL, complete provider/agreement attribution, nonnegative mandatory slices, and positive leave-one-slate-out evidence before a separate review. |
| Tracking / data collection / history | The post-grading runner now has a frozen selective-LEAN audit and independent skip flag. It writes ignored Markdown/JSON only. The audit fail-closes on missing consumed operational-lock identifier/time/source-artifact proof; current Gate C rows do not yet carry that linkage. Exact code commit `5f3b010c` passed `2,015` tests on both the feature branch and merged `main`, and GitHub `main` matches the full SHA. | Decide separately whether to enrich Gate C from the existing lock ledger. Until then, prospective matches are visible as blocked evidence and receive no credit. Add no table and weaken no proof gate. |
| Pipeline / infrastructure | Only `bbe-gate-c-post-grading-review` was manually targeted for the research release: deploy `dep-d9vkm6ou01pc738c91c0` is live on `5f3b010c`, and verification job `job-d9vkmqflk1mc738bb57g` succeeded at `2026-08-14T17:12:03Z` using the unchanged `python scripts/run_post_grading_shadow_reports.py --refresh-market-agreement-inputs` command. Branch `main`, auto-deploy off, schedule `7 11 * * *`, and service posture are unchanged. The GitHub push also triggered the pre-existing `bbe-live-layer` auto-deploy setting: deploy `dep-d9vklmjl550s73fvr180` reached live on the same commit. No live-layer code or config path changed, and its first post-deploy scheduled run succeeded at `2026-08-14T17:11:21Z`. All pipeline-cron deploys remained on `ad6f7d9b`; BoltOdds remained suspended. | Observe the next natural post-grading research run. Treat the live-layer rebuild as behavior-neutral but keep its auto-deploy posture visible before future docs/research pushes. All live production gates remain closed. |
| UI | Unchanged. | No action. |

### July 30 natural research-run overlay

The scheduled research cron on `e8962820` completed its July 30 natural run
with `3,476` source rows and `1,814` tracked rows. This is research evidence
only: it changes no model, provider, notification, lock, UI, artifact,
retention, or source-of-truth behavior.

| Lane | Current stage | Next decision / blocker |
| --- | --- | --- |
| Model | No-drag is `79/75` and `ready_for_review`, but diversity and mandatory slice gates remain open. Strict-runtime current-provider history is `20/50`, `15-5`, `+5.864u`, with zero UNDER and plus-price rows; prospective review starts July 30. The paired market-anchor downside cohort remains `48`, `27-21`, control `-0.763u`, downside delta `+0.763u`, and `keep_shadow`. Strong Base has frozen `cap_high_raw_edge` and `strict_runtime_core_flat`, both at `0/75` prospective rows. Market-shrink remains `retain_diagnostic_shadow` and its betting-promotion path is closed. | Keep all production gates closed. Collect only diverse prospective evidence, preserve the August 10 review, and let Gate D's deployed reconciliation repair prove ten clean scheduled graded slates rather than adding code. |
| Pipeline / infrastructure | Publisher resilience is production-deployed on `ad6f7d9b` to all seven Render pipeline crons; natural publisher and lock runs succeeded afterward. Render/Supabase/Netlify `get-artifact` remains the primary path; GitHub scheduled workflows remain disabled and manual dispatch is rollback/repair only. | Ordinary observation only; escalate on stale served artifacts, missed due locks, or grading/history divergence. |
| UI | Live-market display remains default-on and display-only; Alt V2 remains comparison-only. | Continue separate soak; neither surface opens a provider, betting-rule, or official-pick promotion. |
| Tracking / data collection / history | Gate D repair is live on the research cron. The July 30 run refreshed canonical research evidence without authorizing new storage, retention, or runtime behavior. | Require ten clean scheduled graded slates; keep the Gasser exception fail-closed and do not infer missing attribution. |

### August 5 Alt V2 optional-telemetry and lock-integrity overlay

Tyler approved the previously local Alt V2 prerequisite fix for push and
production deployment. This overlay records the deployment and the separate
Gabriel Hughes lock-gap diagnosis; it does not approve a model, provider,
notification, strict-lock, dashboard-source, accepted-bet, staking, threshold,
or retention change.

| Lane | Confirmed evidence | Next decision |
| --- | --- | --- |
| Pipeline / infrastructure | Exact commit `cf103127` passed the complete `2,005`-test suite, was pushed to `main`, and is live only on `bbe-live-layer` as Render deploy `dep-d9pmuivlk1mc73eeoak0`. The first scheduled cycle used the remote artifact and logged `alt_picks=rows:17 provisional:17 frozen:0`. Natural T-30 cycles at `17:40:50Z` and `17:50:25Z` each inserted two `due_now` operational locks and two linked V2 frozen rows; the following lock crons applied and consumed all four rows. | Keep normal soak. The exact nested optional-webhook-error path is regression-proven but did not occur naturally in either production checkpoint, so verify it opportunistically if a real optional webhook failure coincides with a future due lock; do not inject an error. |
| Model | Unchanged. Alt V2 remains a comparison-only selector over official non-PASS candidates and changes no lambda, verdict, threshold, staking, or official history rule. | Continue prospective grading separately from official model performance; all live model gates remain closed. |
| UI | Unchanged. No dashboard or endpoint deploy was required. | Continue the existing Alt V2/default-on live-market UI soak. |
| Tracking / data collection / history | Hunter Brown UNDER 5.5 and Jameson Taillon UNDER 4.5 froze as `not_selected` at `29.16` minutes before first pitch. Eric Lauer OVER 3.5 froze `not_selected` and Shota Imanaga OVER 4.5 froze `selected` in `consensus_core` at `29.57` minutes. For all four rows, lock key, artifact hash/path, line, price, book, game time, and observation time match the consumed operational lock. The Gabriel Hughes August 4 gap was not a provider or failed-lock incident: confirmed Tampa Bay lineup data dropped his lambda from `3.99` to `3.59` and current verdict to PASS at `22:07Z`; FanDuel later moved from `+108` to `+112`, and the `00:37` refresh restored LEAN only about two minutes before the `00:40` start, after the last usable live-layer/lock window. | Treat Hughes as a separate late-verdict-reentry/cadence design gap. Any rule that suppresses, freezes, or immediately locks a post-T-30 re-entry needs a separate Tyler-approved plan; make no retrospective lock or Alt freeze. |

### August 6 Bet Ticket validation deployment overlay

The scoped Bet Ticket HTML-pattern repair is deployed and verified. It changes
only client-side accepted-bet form validation; it does not change accepted-bet
storage, model, provider, notification, lock, artifact, staking, threshold,
retention, or source-of-truth behavior.

| Lane | Confirmed evidence | Next decision |
| --- | --- | --- |
| UI | Exact `main` commit `f44a31d8` passed all `59` JavaScript and `2,005` Python tests, was pushed to GitHub, and is live on ready Netlify production deploy `6a74c6f2cbaa4900089d2fb6`. A cache-busted production browser check opened Dylan Cease's live-book Bet Ticket and confirmed the deployed odds pattern is `[+\\-]?[0-9]*`: existing `-126` and test `+120` were valid, while `1.5` failed with `patternMismatch=true`. The prior invalid regular-expression console error did not recur. The ticket was canceled without saving; the only console error was the pre-existing missing `favicon.ico`. | Treat the Bet Ticket validation defect as resolved and continue the existing UI soak. Same-line/alternate-line behavior, same-day duplicate warnings, phone density, and accepted-bet provenance remain observation items; no broader UI or betting-rule promotion follows from this repair. |
| Pipeline / infrastructure | The dashboard-only Netlify publication did not redeploy Render services or alter Supabase, provider, scheduler, lock, notification, or artifact behavior. | Continue ordinary pipeline observation and escalate only for stale served artifacts, missed due locks, grading/history divergence, or notification delivery failures. |

### July 29 strict-runtime implementation and market-shrink decision overlay

Tyler approved executing both bounded research plans and externally activating
the strict audit runner. The implementation is merged and pushed on `main`;
only the read-only post-grading research cron was redeployed. It adds audits,
tests, and operator documentation only; no live model, lambda, verdict,
threshold, staking, provider, notification, lock, artifact, UI, retention,
environment, or source-of-truth behavior changed.

| Lane | Current stage | Next decision / blocker |
| --- | --- | --- |
| Pipeline / infrastructure | The post-grading research runner now invokes a frozen strict-runtime-core audit with an independent skip flag and bounded output. The audit writes ignored research Markdown/JSON only and has no publisher or live-table writer. Exact code commit `e8962820` is live only on `bbe-gate-c-post-grading-review` as deploy `dep-d9l590f10e5c73frlcog`; verification job `job-d9l59dlf1gfc73dijd9g` succeeded at `2026-07-29T19:33:04Z`. Cross-service deploy readback found no other deploy after activation began. The service remains branch `main`, auto-deploy off, schedule `7 11 * * *`, starter plan, and command `python scripts/run_post_grading_shadow_reports.py --refresh-market-agreement-inputs`. Render exposed final deploy/job status but no retained task log body, so bounded excerpt and no-writer behavior remain proven by the committed runner tests. | Treat activation as complete and observe the next scheduled post-grading run. The later handoff-doc commit does not require redeployment. Production pipeline behavior is unchanged. |
| Model | Strict-runtime core is frozen as `strict_runtime_core_flat` with fingerprint `6d07a98031a8b26915ad34fc031def76d26519850dc476db723d37f25a8d9905` and prospective credit starting `2026-07-30`. The current canonical read is `collecting`: historical `96`, `64-32`, `+17.724u`; current provider `20/50`, `15-5`, `+5.864u`; recent `17`, `14-3`, `+7.106u`; UNDER, plus-price, provider-attribution, and agreement-attribution counts are all zero. Market-shrink is `retain_diagnostic_shadow`: `605`, `300-305`, `-42.56u/-7.0%`; current provider `574`, `285-289`, `-39.81u/-6.9%`; recent `255`, `123-132`, `-27.47u/-10.8%`; zero applied rows and zero selected-lambda drift. Its paired `578` unique pitcher-games improved MAE from `1.9472` to `1.8932` (`+0.0540` K), so its projection-error diagnostic remains useful while its betting-promotion path closes. | Accumulate only genuinely prospective, diverse strict-core rows; do not weaken the `50` current-provider, `10` UNDER, `10` plus-price, provider/agreement, slice, rolling-window, and leave-one-slate-out gates. Issue the no-drag/strict packet on August 10 using the then-latest graded slate. Do not draft market-shrink enforce work. Gate C/D/E/F/12E and every live behavior gate remain closed. |
| UI | Unchanged. | Continue Alt V2/default-on live-market UI soak independently. |
| Tracking / data collection / history | The production-shaped hybrid rebuild through July 28 reconciled `3,434` Gate C side rows, `1,793` tracked rows, zero duplicates, and `1,750/1,750` graded picks. Strict history-recovered rows remain historical context only and receive no prospective credit. Market-shrink adds zero provider calls and zero Supabase rows; its JSON footprint is about `25 KB` in `today` and `234 KB` across `picks_history`. | Preserve provenance and existing shadow metadata. If artifact bloat later becomes material, require a separate approved simplification plan; no retirement or retention write is approved now. |

### July 29 publisher implementation and model-evidence overlay

Tyler approved the narrow artifact-publisher resilience implementation. It is
merged and pushed on `main` at `a1019485`; the later approval and verified
production deployment are recorded in the next July 29 overlay. The merged
tree passed `1,911` tests and the publisher dry run collected the expected
seven all-scope artifacts. No model, provider, lock, notification,
source-of-truth, or retention behavior changed.

| Lane | Current stage | Next decision / blocker |
| --- | --- | --- |
| Pipeline / infrastructure | A fifth `published_pipeline_artifacts` `57014` timeout occurred on the July 28 `14:07` Phoenix refresh and recovered on the next scheduled refresh without stale artifacts, missed locks, grading divergence, or betting impact. `main` at `a1019485` changes only this publisher to `return=minimal` plus one retry requiring a transient HTTP status and exact database code `57014`; other writer defaults and all artifact/lock contracts remain unchanged. The merged tree passed `1,911` tests and the publisher dry run passed. | This was the pre-activation read. Tyler subsequently approved deployment; use the next July 29 overlay for verified production state. |
| Model | No-drag is `77/75` and `ready_for_review`; prospective July 21-28 is `25`, `16-9`, `+2.297u/+9.2%`. Strict runtime core is `96`, `64-32`, `+17.72u`; current provider `20`, `15-5`, `+5.86u`; recent `17`, `14-3`, `+7.11u`. The raw count gate is complete for no-drag, but no-drag still lacks plus-price/FIRE 2u diversity and has negative middle-price/K=4.5 slices. Strict current-provider evidence remains concentrated in OVER/minus rows. | Keep the August 10 canonical review. Treat missing UNDER/plus-price/provider-agreement/CLV/rolling-window evidence as the blocker; do not mistake more same-profile picks for gate progress. No live promotion plan yet. |
| UI | No dashboard behavior changed. | Continue Alt V2/default-on live-market UI soak. |
| Tracking / data collection / history | July 29 storage is `3,390 MB` (`41.38%` of 8 GB); exact compact coverage remains false and retention execution remains ineligible. | Keep the August 3 `fix_compaction_first` confirmation and make no deletion. |

### July 29 approved deployment, Gate D repair, and research plan map

Tyler approved the two previously separate actions: deploy the merged
publisher-resilience fix and resolve the named Robert Gasser Gate D exception.
The six new research plans are planning artifacts only; none changes live
model, provider, threshold, staking, notification, lock, UI, retention, or
source-of-truth behavior.

| Lane | Current stage | Next decision / blocker |
| --- | --- | --- |
| Pipeline / infrastructure | All seven Render pipeline cron services are live on publisher commit `ad6f7d9b`. Deploys `dep-d9l2o8favr4c739uc020` through `dep-d9l2q3jl550s73fg5rs0` completed successfully. The first natural post-deploy lock at `2026-07-29T16:42Z` checked out `ad6f7d9b`, consumed five newly represented lock rows, published `today`, `dated_slate:2026-07-29`, and `picks_history`, and finished successfully. Supabase source commit/run metadata and Netlify ETags matched the published hashes. | Observe the next normal preview, grading, full, and refresh runs. Roll back only if minimal-return/retry behavior produces a stale artifact, repeated failure, or contract mismatch. |
| Model | No-drag remains `77/75` and strict runtime core remains the strongest comparison signal. The candidate map creates separate plans for no-drag/strict, market-anchor downside, Strong Base FIRE policy, selective LEAN/pre-close, CLV process validation, and market-shrink retirement. | Follow `docs/research/2026-07-29-research-candidate-plan-map.md`. Keep the August 10 independent review; no plan authorizes activation. |
| UI | No dashboard behavior changed. | Continue Alt V2/default-on live-market UI soak. |
| Tracking / data collection / history | The Gasser exception is repaired with a consensus-only pitcher-game actual-K fallback after exact-line recovery. Production-shaped hybrid verification through July 28 produced `3,434` side rows, `1,793` tracked rows, zero duplicates, `25` recoveries, zero ambiguities, and `1,750/1,750` reconciliation. The archived `4.5` market and official `UNDER 3.5` bet remain distinct; all recovered rows remain excluded from no-drag credit. | Let the next ten scheduled graded slates prove the new path remains boring. Gate D and all model-promotion gates stay closed until that operational proof and candidate-specific slice gates pass. |

The research-only service is also deployed on the repaired code: Render deploy
`dep-d9l3a79t0dsc73fng6t0` is live on `519f099d`, and verification job
`job-d9l3avtf1gfc73dfmmag` succeeded at `2026-07-29T17:20:02Z`. Its canonical
run produced `3,434` Gate C rows, `1,793` tracked rows, zero duplicates,
`1,750/1,750` reconciliation, and no-drag `77/75` with all `25`
history-recovered rows excluded. The service remained branch `main`,
autoDeploy off, schedule `7 11 * * *`, and start command
`python scripts/run_post_grading_shadow_reports.py --refresh-market-agreement-inputs`.

### July 29 market-anchor downside and Strong Base FIRE matrix overlay

Tyler approved executing the two bounded research plans. The implementation
adds post-grading diagnostics and scheduler excerpts only; no live selector,
mode, verdict, threshold, stake, provider, notification, lock, artifact, UI,
retention, environment variable, or source-of-truth behavior changed.

| Lane | Current stage | Next decision / blocker |
| --- | --- | --- |
| Model | The exact market-anchor downside audit covers `743/743` tracked rows since the June 16 selector deployment. One post-start row is excluded. The exact pre-start would-change cohort is `48`, all OVER/FIRE 1u/minus-price, `27-21`, with current displayed PnL `-0.763u` and hypothetical downside value `+0.763u`. Current-provider delta is `+4.632u` on 41; recent delta is `+1.714u` on 24. The decision is `keep_shadow`. The Strong Base matrix reconciles all six locked historical counts and freezes `cap_high_raw_edge` plus `strict_runtime_core_flat` for prospective review starting July 30. | Market-anchor still needs at least two more exact rows, at least 10 UNDER rows, and complete provider/agreement/CLV attribution; do not promote when the count alone reaches 50. Strong Base counters are `0/75`; only diverse post-July-29 graded rows advance them. All live gates remain closed. |
| Pipeline / infrastructure | `scripts/run_post_grading_shadow_reports.py` now invokes both research diagnostics with independent skip flags and bounded excerpts. Generated Markdown/JSON remains under ignored `analytics/output/`. The approved research-only release is live on Render deploy `dep-d9l4fv5aeets73ag2rag` at commit `eb31214f`; the single verification job `job-d9l4gddf1gfc73dhhrs0` succeeded at `2026-07-29T18:39:34Z`, and the focused runner/audit suite passed `20/20` on the same commit. The service remains branch `main`, autoDeploy off, schedule `7 11 * * *`, and start command `python scripts/run_post_grading_shadow_reports.py --refresh-market-agreement-inputs`. Render CLI exposed the successful task status but returned no retained task log body, so bounded excerpt behavior was re-verified through the committed runner tests rather than a live-log capture. | Treat the research release as successful and observe the next scheduled run for refreshed compact attribution. No redeploy, environment change, or live-behavior action is needed now; a successful research run is not a Render variable or live-behavior approval. |
| UI | Unchanged. | Continue the existing Alt V2/default-on live-market UI soak independently. |
| Tracking / data collection / history | The local production-shaped rebuild through July 28 matched the canonical `3,434` side rows, `1,793` tracked rows, zero duplicate keys, and `1,750/1,750` reconciliation. Its available compact market-agreement enrichment ended July 13, so missing provider/agreement fields are treated as blockers. | Use the scheduled `--refresh-market-agreement-inputs` path for the next canonical packet; do not fill missing attribution by inference. |

### July 28 four-action operations follow-through overlay

Tyler approved four read-only follow-ups from the July 28 morning brief. The
review artifacts are documentation and evidence only; they do not approve a
production deploy, model/provider/notification/lock/UI change, or retention
write.

| Lane | Current stage | Next decision / blocker |
| --- | --- | --- |
| Pipeline / infrastructure | A scoped review confirmed four identical `published_pipeline_artifacts` `57014` statement timeouts on lock runs: Jul 23 `02:32`, Jul 25 `11:42`, and Jul 27 `00:32`/`05:32` Phoenix. Each was the same three-artifact bulk upsert and each next 10-minute cycle recovered. No due lock, served artifact, or grading impact was found. The resilience gap is the growing roughly `5.9 MiB` logical response, an `8s` PostgREST statement ceiling, unnecessary `return=representation`, and no transient retry; the table itself is small, recently vacuumed/analyzed, and has no custom triggers. The final natural-refresh check used the served artifact generated at `13:37:53` Phoenix: 30 pitchers, 21 tracked picks, `7` clean / `23` capped, and lineup maturity of 14 confirmed / 16 projected across pitcher rows (10 / 11 among tracked picks). The approved non-strict wrapper selected PropLine for two rows without changing source posture: Cal Quantrill UNDER 2.5 `+126` (confirmed lineup) and Luis Castillo OVER 4.5 `+112` (projected lineup); both remained first-seen-opening-capped LEANs, with TheRundown still primary and cross-book rows present. | No emergency repair or rollback. Review `docs/research/2026-07-28-artifact-publisher-timeout-resilience-review.md`, then separately approve or decline a test-first publisher-only minimal-return/bounded-retry plan. Escalate only if a timeout causes a stale served artifact, missed due lock, or grading/history divergence. Continue natural refresh observation for the remaining projected lineups; the two PropLine selections are normal approved fallback evidence, not a provider-promotion signal. |
| Model | The scheduled July 28 research run reconciled the frozen no-drag baselines/fingerprint and reached `ready_for_review` at `75/75`. Prospective July 21-27 is `23`, `15-8`, `+2.621u/+11.4%`, with positive leave-one-slate-out PnL. Strict runtime core is `95`, `63-32`, `+17.05u`; current provider `19`, `14-5`, `+5.19u`; recent `17`, `14-3`, `+7.19u`. No-drag still has zero plus-price and FIRE 2u prospective rows; strict core's current-provider rows are all OVER at minus money. | Keep the August 10 four-candidate checkpoint and read `docs/research/2026-07-28-no-drag-strict-runtime-core-review-packet.md`. Refresh provider/agreement, side, price, K-line, quality, timing, CLV, Path B, workload, and rolling slices then. No live promotion plan yet; Gate C/D/E/F/12E remain closed. |
| UI | No dashboard behavior changed. The lineup and fallback check was artifact-only and the PropLine rows remain within the approved non-strict fallback contract. | Continue existing Alt V2/default-on live-market UI soak. Do not treat the fallback rows or model breakout as UI/provider promotion. |
| Tracking / data collection / history | The July 28 linked-CLI review reports `3,331 MB` database use (`40.66%` of 8 GB) and `2,374 MB` of `market_snapshots`. The 14-day window has `2,003,860` raw rows / `1,745 MB` / `148` uncovered sampled groups; the 30-day window has `1,303,579` rows / `1,135 MB` / `30` uncovered groups. Exact coverage is false and both windows are ineligible. | Retention remains `NO-GO`; keep spend cap and current rules. August 3 is a confirmation review, not execution. Exact provider/date compact coverage, recoverability, material benefit, the exact statement, and separate Tyler approval are all still required. |

### July 27 operations action overlay

This overlay schedules the two approved governance reviews and records the
normalized pick-identity repair. It does not open any model, provider, strict
lock, notification, UI, source-of-truth, or retention gate.

| Lane | Current stage | Next decision / blocker |
| --- | --- | --- |
| Pipeline / infrastructure | The Martin Perez / Martín Pérez duplicate was traced to exact Unicode display-name uniqueness in history hydration and seeding. The scoped repair now deduplicates by normalized `(date, pitcher, side)`, preserves graded or locked evidence, and retains the current display spelling. Main commit `56f3d25e` passed `1,905` tests and is live on all seven pipeline cron services. The first post-deploy refresh succeeded at `17:08:18Z`; public `today`, dated slate, and history artifacts published at `17:08:07Z` contain one `Martin Pérez` `under 3.5` identity and zero July 27 normalized duplicate groups. All pitcher rows kept `market_source_mode=therundown_propline`, odds sources were only `therundown` or `therundown+propline`, and line-source provider remained TheRundown. Render CLI authentication was refreshed without changing service settings. | Keep observing normal refresh and lock cycles. The repair is complete; do not infer a provider, model, threshold, staking, notification, strict-lock, UI, source-of-truth, or retention change from it. |
| Model | A combined shadow-only checkpoint is scheduled for `2026-08-10` in `docs/research/2026-07-27-shadow-model-review-checkpoint.md`. It keeps market-anchor, market-shrink, moderate-edge/CLV, and no-drag as four separate decisions and records the partial July 26 scheduling baseline. | Rebuild from the full approved production index and enforce all mandatory slices. Default is keep soaking; any survivor needs a separate Tyler-approved plan. |
| UI | Unchanged by these action items. | Continue the existing prospective Alt V2 and default-on live-market UI soak. Do not infer UI or selector promotion from the identity repair. |
| Tracking / data collection / history | The July 27 dry-run reports show a `3,248 MB` database (`39.65%` of 8 GB), `2,314 MB` of `market_snapshots`, `2,003,860` raw rows older than 14 days, and `1,257,858` older than 30 days. Exact compact coverage is false; the bounded samples have `148` and `143` uncovered groups, so both windows remain `eligible_for_execute=false`. The retention yes/no review is scheduled for `2026-08-03` in `docs/research/2026-07-27-retention-decision-checkpoint.md`. | Retention deletion is `NO-GO` unless exact coverage, bounded target, backup/recovery, material benefit, and a separate Tyler approval all exist. Keep spend cap and current retention behavior unchanged. |

### July 23 research evidence repair board overlay

This is the freshest board read for the scoped research repair on
`codex/research-evidence-repair`. It supplements the longer lane rows above and
does not change any live-system approval.

| Lane | Current stage | Next decision / blocker |
| --- | --- | --- |
| Pipeline / infrastructure | The research-only post-grading runner's explicit `--refresh-market-agreement-inputs` mode is deployed only on `bbe-gate-c-post-grading-review`. Deploy `dep-d9h4mvj7uimc73f3n2gg` built `main` commit `0d9b07aa`; the first manual run finished successfully at `17:16:27Z`. Its environment contains only the two required Supabase credentials, and branch, schedule, plan, build command, and auto-deploy posture were preserved. Integrated verification returned `1,867` Python and `99` Node tests. Production isolation passed with zero pipeline-publication, lock, notification, or provider rows attributable to the research run and no other service deploy. | Keep the bounded research cron on ordinary post-grading observation. Preserve the named Robert Gasser `2026-06-03` fail-closed exception. Do not couple this completed research wiring repair to live pipeline, provider, model, notification, lock, UI, artifact, or retention changes. |
| Model | The deployed expanded market-anchor audit confirms the raw separate-review floors with `331` clean selector rows and `131` strict rows. Strict-all is `81-50`, `+6.62u`; current-provider strict is `58-33`, `+8.31u`; leave-one-slate-out minimum remains `+3.68u`. Strict displayed FIRE is `27` rows, `20-7`, `+7.14u`, but every row is `OVER`. Negative K-line, CLV-proxy, workload, provider-era, and market-agreement slices plus substantial missing provider/agreement attribution remain. The frozen no-drag fingerprint is unchanged; after excluding `24` history-recovered archive rows from backfill credit, both baselines reconcile and the counter is `58/75` with `17` remaining. | Market-anchor status is `separate_shadow_review_ready`, not promotion-ready. Keep `MARKET_ANCHOR_SELECTOR_MODE=shadow` and `enforce_downside` closed. Continue the no-drag prospective soak; history-recovered rows never advance its frozen or prospective counter. |
| UI | Unchanged. No dashboard, accepted-bet, live-book selector, or display behavior changed in this repair. | Continue the existing normal-slate UI observation plan; do not couple it to this research work. |
| Tracking / data collection / history | The deployed bounded read-only export produced `3,105` `market_pick_evidence` rows and `3,251` `live_market_display_state` rows through `2026-07-23`; raw `market_snapshots` were not queried. The refreshed tracker produced `6,356` rows. Gate C produced `3,224` side rows, `1,682` tracked rows, zero duplicate keys, `24` unique exact outcome recoveries, and zero ambiguous recoveries. Tyler accepted Robert Gasser as the one named fail-closed historical exception, so the accepted reconciliation result remains `1,647/1,648`. | Keep Gasser unrecovered and visible; do not add a cross-line rule or mutate the dated archive. Continue ordinary scheduled evidence collection, while Gate C/D/E/F/12E model-promotion gates remain closed. |

### July 21 Alt Picks board overlay

The controlling written design is
`docs/superpowers/specs/2026-07-21-pregame-alternative-pick-methodology-design.md`.
Tyler approved the product direction and the staged production rollout: compare
official same-day picks with a pregame alternative methodology in the middle
Alt Picks tab without changing official behavior.

The independently reviewed V1 feature and first-slate repairs are merged
through `f39f438b`. Dependency-aware V2 is now the operational Alt methodology.
Its final reviewed contract-repair tree is `cb2224f1`, released through the
tree-identical `main` control commit `6ab9fcf2`. V1 remains inert compatibility
only. Production recording and display are open only for isolated prospective
comparison state; every official model, verdict, staking, notification, lock,
provider, accepted-bet, artifact, history, and source-of-truth promotion gate
remains closed.

| Lane | Current stage | Next decision |
| --- | --- | --- |
| Pipeline / infrastructure | V2 remains isolated in the existing post-lock `bbe-live-layer` sidecar. The final repair binds raw workload inputs, separates the legacy snapshot suffix from V2-safe rows, uses one newest-101 provider-run read, retains the existing snapshot budget of up to five descending 1,000-row keyset pages, and fails incomplete/ambiguous evidence to pending. Render deploy `dep-d9h8u9sm0tmc738cfmqg` is live on `6ab9fcf2`; its first normal `22:10Z` cycle completed successfully from the remote official artifact. No environment, worker, cadence, schema, provider, notification, lock, or official pipeline path changed. | Observe the first new workload-bound V2 proof and immutable freeze on the next normal slate. Do not reconstruct old proofs. Immediate sidecar stop remains `ALTERNATIVE_PICK_SELECTION_MODE=off` plus a `bbe-live-layer` redeploy; do not change cadence or provider posture. |
| Model | The dependency-aware V2 comparison selector remains live with frozen fingerprint `23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4`. The repair closes proof and ambiguity gaps but does not change the frozen methodology. The post-repair partial slate had no eligible future tracked candidate: its four tracked picks were already locked/started and the two future pitchers were official PASS rows. Old frozen state stayed immutable. The exploratory official-close `148-84`, `+38.585u`, `+16.63%` on `232` remains hindsight-capable research only. | Soak the first new proof through T-30 freeze and graded outcome on a normal slate. This is comparison evidence, not approval for official pick selection, model math, thresholds, staking, providers, notifications, locks, retention, or source truth. |
| UI | **Healthy - soak.** The dashboard-only recovery is live on exact `main` commit `31005482` as completed Netlify deploy `6a63ed9fd8afa30008e443c8`. Immediate plus 60-second non-overlapping reads, last-good retention, the neutral alias, and the `2026-07-24-alt-contract-recovery` adapter token are deployed. The exact live V2 payload normalized with 13 frozen rows and two selected; a cache-busted production Chrome session rendered Trevor Rogers and Matthew Boyd plus 11 supporting rows and remained healthy through the next mounted refresh. The root cause was a narrow browser-contract mismatch for valid zero-observation, dependency-short-circuited Preclose disagreement—not missing data or a product transport gap. Zero-observation Preclose agreement still fails closed. No wager controls or other dashboard-tab behavior changed. | Keep the UI in prospective soak and confirm a normal phone refresh. Do not add a script fallback or infer any model, selector, provider, notification, lock, accepted-bet, artifact, history, or source-of-truth promotion. |
| Tracking / data collection / history | The additive V2 proof schema remains active. Post-deploy controls are zero notification rows, four unique operational locks all consumed, two unique accepted bets, and zero V2 duplicate groups. The Brandon Pfaadt frozen V2 proof remains unchanged at MD5 `efa7e0484981aa26b976b0bd897b7dea`, observed `20:50:12Z`; no historical proof was rewritten. The current official artifact was generated `22:07:47Z`, has eight pitchers, four tracked picks, zero warnings, and TheRundown as every row's line source. | Continue bounded prospective collection. The next normal slate must prove a new workload-bound row; do not backfill missed checkpoints, delete/compact Alt evidence, or let Alt rows enter official history/analytics without separate approval. |

Decision-integrity rollout, 2026-07-20: `main` commit `b7906a44` is live on
Netlify deploy `6a5e5bbef33863243b980d83`; production root and `/v2.html`
returned `200`, the `2026-07-17-same-line-trust` assets were present, and the
deployed bundles contained same-line ranking, `Alt-line context`, explicit
freshness gating, and manual selected-row provenance. Supabase migration
`20260717181500_ready_to_bet_shadow_candidate.sql` was the only pending
migration and was applied. Render off-mode deploy `dep-d9f5onrtqb8s73blj9lg`
produced the `2026-07-20T17:41:03Z` run with `mode=off`, zero candidates, and
the grouped coordinator unchanged. After only
`LIVE_READY_TO_BET_SHADOW=record` was added, deploy
`dep-d9f5sltaeets73cgk1lg` produced the first record run at
`2026-07-20T17:50:32Z`: `60` watching rows, zero candidates, zero recent
notification rows, and zero `ready_to_bet` notification events. This is the
first observation only, not promotion evidence; collect five normal slates.

Model-lane overlay, 2026-07-10 (superseded for lead-candidate purposes): Tyler
approved escalating
`strict_runtime_core_plus_selective_lean` from generic watchlist treatment to a
canary-review candidate after the post-grading refresh through the 2026-07-09
slate. The selector is now `225` rows, `140-85`, `+30.18u`, `+13.4%`, with
`85` retained FIRE rows and `140` selective LEAN rows; current-provider/recent
slice is `44` rows, `29-15`, `+9.55u`. The newest three qualifying rows went
`2-1`, `+0.75u` while the normal tracked slate lost `-2.639u`. Its packet,
`docs/research/strict-runtime-core-selective-lean-canary-packet.md`, is retained
as comparison/control historical context. Current lead-candidate work is the
July 21 no-drag plan and packet:
`docs/superpowers/plans/2026-07-21-no-drag-composite-prospective-canary.md` and
`docs/research/no-drag-composite-prospective-canary-packet.md`. This is still
not a production flip. The superseded overlay's known risk slices were weak
pre-close proxy, price bucket `+100 to +119`, and worse-close-price. No LEAN
promotion, displayed-verdict
change, staking change, lambda change, threshold change, provider behavior
change, notification change, lock change, retention change, dashboard source
change, or `formula_change_date` change is approved from this overlay.

Pipeline-lane overlay, 2026-07-13: the All-Star break packet is
`docs/research/all-star-break-operations-packet.md`. It records the
break-window posture: patch off-day `dated_slate` hydration noise, run a
post-break restart checklist on the first real slate, keep strict-runtime
tracking as actual-record shadow evidence only, and monitor cost/row volume
without cadence or retention changes. The off-day wrapper fix makes pre-run
`dated_slate` hydration optional while keeping required artifacts fail-closed.
Tyler approved merging and deploying that wrapper fix to the Render pipeline
cron group on 2026-07-13.

Pipeline-lane overlay, 2026-06-17: Tyler approved retiring BoltOdds and keeping
the official production path as TheRundown with PropLine fallback/live-movement
sidecar. `bbe-boltodds-shadow-worker` (`srv-d7ugabe7r5hc73b36oag`) is suspended
by user in Render. Morning checks should verify no fresh BoltOdds
`market_feed_heartbeats` or `market_snapshots` appear after
`2026-06-17T17:22:29Z`; any fresh rows are an accidental reactivation, not a
promotion signal. `render.yaml` is now a non-deploying `services: []`
placeholder, and `--provider-rehearsal` requires
`ALLOW_BOLTODDS_PROVIDER_REHEARSAL=true` after a fresh Tyler-approved provider
trial. This supersedes the older board next-decision wording about deploying
the 2026-06-16 provider-wrapper fix or stopping BoltOdds before
renewal; both actions are done.

Pipeline-lane overlay, 2026-06-19: The explicit `therundown_propline` provider
mode support, non-strict TheRundown fallback, provider parity CLI fallback,
PropLine webhook audit, and cross-book line-conflict fail-closed behavior are
on `main`. Render pipeline cron services plus `bbe-live-layer` are live on
`1ec4a726`, and live-layer one-off `job-d8qpj8u7r5hc73dflev0` succeeded after
the Supabase rollup provider constraints were widened for `therundown`. At the
time this was not an official-provider env flip: latest 2026-06-19 parity was
safer but still not ready, with line conflicts excluded (`0.0%`) and provider
coverage down to `22/29` (`75.9%`). The "keep `OFFICIAL_MARKET_SOURCE=therundown`"
decision was superseded by Tyler's 2026-06-24 approval for the non-strict
`therundown_propline` live wrapper flip.

Pipeline-lane overlay, 2026-06-24: Tyler approved the non-strict live
`therundown_propline` wrapper flip after the last-week evidence review. The
next proof step is operational, not analytical: deploy the Render pipeline cron
group from the approved main commit, then verify fresh preview/full artifacts
use `therundown_propline` or direct TheRundown fallback, never
`boltodds_propline`, and that strict mode remains false. Webhook movement
notification queueing now has a separate 20-minute freshness gate while the
180-minute webhook evidence-processing window remains for audit rows.

Pipeline-lane overlay, 2026-07-08: the live-market display path now treats
TheRundown and PropLine as a combined non-strict coverage surface for UI and
main-line best-price notifications. `live_market_display_state` permits
`provider=therundown_propline`; Netlify and `dashboard/v2-data.js` pass through
and prefer that combined row over individual provider rows. Individual provider
rows remain audit evidence, and strict provider/source-of-truth promotion
remains closed.

Branch-hygiene overlay, 2026-06-17: safe merged local branches were deleted,
merged remote branches were deleted where they still existed, and stale
patch-equivalent live-market UI remote-tracking refs were pruned after GitHub
reported the remote refs were already gone. The only remaining non-main local
and remote branches are `codex/artifact-exit-shadow-mirror`,
`codex/boltodds-production-plan`, and
`codex/confidence-referee-shadow-report`; they still contain unique unmerged
commits and should be treated as historical/archive candidates until Tyler
explicitly approves deleting or merging them.

Model-lane overlay, 2026-06-17: refreshed Gate C through the fully graded
2026-06-16 slate with `python scripts/run_post_grading_shadow_reports.py
--artifact-source hybrid --end-date 2026-06-16`. The refreshed durable dataset
has `2020` rows, `1050` tracked rows, `1051/1051` graded pick reconciliations,
and loaded dates through `2026-06-16`. The market-anchor selector canary audit
now has `24` tracked graded rows with selector metadata and `8` strict rows
(`4-4`, `-1.24u`, `-15.5%` ROI). This fixed the stale zero-row audit read, but
`enforce_downside` remains closed because the live selector sample is tiny and
the first strict slice is negative. The post-grading runner now prints selector
audit input coverage so future stale Gate C inputs are visible in logs.

Model-lane overlay, 2026-06-22: after the weekend stale-PASS and archive-index
repair, a refreshed production Gate F report covered slates through
2026-06-21 and marked `market_shrink_15`, `market_shrink_25`, and
`market_shrink_35` as `promotion_plan_candidate` with zero bad slices and no
FIRE 2u degradation. `high_line_temper`, `leash_cap`, and
`handedness_bucket_adjust` remain blocked. The drafted production-canary plan
is `docs/superpowers/plans/2026-06-22-market-shrink-projection-production-canary.md`.
This draft does not approve a live lambda change; any `shadow` or `enforce`
env flip still needs Tyler's explicit approval.

Model-lane overlay, 2026-06-10: Tyler approved
`PROFIT_RESCUE_REFEREE_MODE=enforce`; all seven Render pipeline cron services
were updated and redeployed on commit `c60bd895`. The manual refresh published
`today.json` generated at `2026-06-10T16:52:46Z` with all side payloads in
enforce mode, seven applied profit-rescue caps, zero current FIRE side verdicts,
and one same-day stale-lock caveat for Carlos Rodon under, which locked from
the pre-reconciliation artifact at `2026-06-10T16:40:29Z`.

Gate F selection-progress overlay, 2026-06-10: `analytics/output/gate_f_fire_reentry_lab.md`
now measures FIRE re-entry volume and candidate decision value. It shows `638`
historical FIRE-like rows, `134` retained under the profit-rescue policy, and
`504` capped to LEAN. No candidate is ready for a production plan yet.
Runtime-safe watch candidates are `moderate_edge_quality_reentry` (`68` rows,
`+4.77u`, `+7.0% ROI`) and `retained_fire_control` (`134` rows, `+2.71u`,
`+2.0% ROI`). `clv_supported_reentry` is a strong process anchor (`83` rows,
`+15.88u`, `+19.1% ROI`) but not a live selector because CLV is post-close
evidence.

Gate F CLV-proxy overlay, 2026-06-10: `analytics/output/gate_f_preclose_clv_proxy_lab.md`
keeps CLV as the validation target and tests whether pre-lock fields can
predict it. Gate C now enriches from both
`analytics/output/market_agreement_tracker.jsonl` and
`analytics/output/market_agreement_inputs/live_market_display_state.json`. The
durable dataset has `195` market-agreement rows, `223` live-display rows, `281`
market book-count rows, `42` broad-confirmation rows, and `75` best-off-market
rows. The CLV proxy report has `192/886` tracked rows (`21.7%`) with
toward/away and agreement labels, `278/886` (`31.4%`) with `book_count`, and
`220/886` (`24.8%`) with `best_is_off_market` coverage. The stronger
book-board evidence made the proxy read more conservative, not promotion-ready:
`strong_preclose_clv_proxy` is `294` rows, `162-132`, `+3.54u`, `+1.2% ROI`,
`92` positive-CLV rows (`31.3%`), `121` source-FIRE rows, `-12.33u` recent PnL,
and `13` negative slices. Do not re-enter FIRE from it yet.

Market-anchored rebuild overlay, 2026-06-13:
`analytics/output/market_anchored_k_shadow_rebuild.md` now tests a shadow-only
"start from market, add shrink-adjusted baseball signal" model shape. On
`920` clean official-close markets, market-implied projection beat current
model MAE/RMSE (`1.732`/`2.168` vs. `1.832`/`2.286`) and side accuracy
(`56.9%` vs. `53.9%`); the market-anchored blend was similar (`1.741` MAE,
`2.175` RMSE, `56.9%` side accuracy). On `956` clean tracked rows, current
FIRE was `549` rows, `269-280`, `-39.93u`, `-7.3% ROI`; the market-anchor
core selector was still near breakeven (`485` rows, `269-216`, `-5.48u`,
`-1.1% ROI`); the strict runtime-safe selector was promising (`149` rows,
`90-59`, `+6.41u`, `+4.3% ROI`). This is shadow evidence only. It does not
approve a live v2 selector, lambda change, threshold change, staking change,
provider change, notification change, lock change, retention change, or
dashboard source-of-truth change. The daily review command is
`python scripts/run_post_grading_shadow_reports.py`; it is intended to run
after grading and preserve the decision-facing report excerpt in scheduler
logs.

Market-anchor v2 selector plan overlay, 2026-06-16:
`docs/superpowers/plans/2026-06-16-market-anchored-v2-selector-shadow-canary.md`
is the controlling plan for turning the market-anchored strict selector into
feature-flagged runtime metadata and a post-grading audit. As of 2026-06-16,
branch `codex/market-anchor-selector-shadow` implemented the default-off
metadata plumbing, persistence, Gate C passthrough, and canary audit; it was
merged to `main` at commit `687cf472`. Tyler approved deploying
`MARKET_ANCHOR_SELECTOR_MODE=shadow` on the seven Render pipeline cron
services on 2026-06-16. The first controlled refresh job
`job-d8oqplb7uimc739ivvp0` published `today.json` generated at
`2026-06-16T20:08:07Z` with selector metadata on all `60` side rows and
`selector_applied_rows=0`; provider provenance remained TheRundown
(`odds_source=therundown` on 30 pitcher rows). This is metadata-only and does
not change verdicts. `enforce_downside` remains closed until the audit reaches
its row, slice, CLV, workload, Path B, provider/source, market-agreement, and
rolling-window gates. This plan does not approve LEAN promotion, lambda
changes, threshold changes, staking changes, provider changes, notification
changes, lock changes, retention deletion, or dashboard source-of-truth
changes.

Board rule: each lane can advance independently, but live betting behavior only
changes after the controlling lane has passed its own promotion gate and Tyler
explicitly approves the production switch. Operational reliability evidence is
not a model-change approval, and model bucket evidence is not a provider-cutover
approval.

Gate-index rule: when the question is "are we soaking, operational, or ready to
promote?", start with
`docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md`. Update
that synthesis when a gate opens, closes, or changes pass/fail criteria; keep
the detailed implementation rules in the controlling child plan.

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
- BoltOdds provider-source promotion is retired after the 2026-06-17
  suspension. `OFFICIAL_MARKET_SOURCE=boltodds_propline` and
  `ENABLE_BOLTODDS_PIPELINE_SOURCE=true` remain closed unless Tyler explicitly
  opens a new provider trial.

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
- Render primary-scheduler update, 2026-05-30: after GitHub scheduled triggers
  were disabled and Render became the artifact publisher, `bbe-pipeline-lock`
  now hydrates from Netlify `get-artifact` before lock mode and fetches all
  same-slate `operational_pick_locks`, including rows that already have
  `consumed_at`. This lets lock mode repair an artifact that fell behind a
  consumed lock ledger row without overwriting the original `consumed_at`
  marker. The live layer's automatic GitHub lock dispatch should remain off.
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
  not make any sidecar/provider rehearsal table the production provider.
- Historical BoltOdds official-line freshness can still be tested explicitly,
  but active current-line, official-line, live-display, and market-evidence
  defaults exclude retired BoltOdds rows. The active readers now default to
  TheRundown plus PropLine/the capped emergency Odds API where applicable, so
  stale same-day BoltOdds rows in Supabase cannot become official/live evidence
  unless Tyler opens a fresh provider trial and a new flag/path is added.
- A shadow mainline selector still runs before official arbitration so same-book
  alt ladders are not treated as automatic provider outages. It keeps raw/current
  rows for audit, selects complete supported mainline candidates only when
  provider overlap or cross-book support makes the choice clear, and fails
  closed on ambiguous ladders. The old BoltOdds rehearsal results remain
  history, not a current cutover recommendation.
- `.github/workflows/shadow-market-infra.yml` is manual-only as of 2026-06-17.
  Manual dispatch can capture TheRundown/PropLine sidecar evidence and rebuild
  `current_market_lines`/`official_market_lines` from existing snapshots, but it
  does not run the production pipeline, push artifacts, or change provider
  order. Routine refresh now belongs to Render/live-layer paths, not scheduled
  GitHub shadow polling.
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
- The Odds API official arbitration remains behind an explicit emergency flag.
  DraftKings remains TheRundown/PropLine-priority in active arbitration; retired
  BoltOdds compatibility flags do not promote BoltOdds.
- A historical pipeline adapter for `official_market_lines` exists behind a double opt-in:
  `OFFICIAL_MARKET_SOURCE=boltodds_propline` and
  `ENABLE_BOLTODDS_PIPELINE_SOURCE=true`. After the 2026-06-17 retirement, keep
  both unset/false unless Tyler opens a new provider trial. `--provider-rehearsal`
  also fails closed unless `ALLOW_BOLTODDS_PROVIDER_REHEARSAL=true` is set for
  that explicit trial.
- `analytics/diagnostics/provider_cutover_shadow_compare.py` exists for the
  fresh-slate rehearsal. Use it to compare TheRundown against provider-mode
  rows and evaluate coverage, FD/DK availability, line conflicts, ref-book
  changes, odds deltas, artifact contract, and usage gates before any cutover
  decision. Its old BoltOdds heartbeat-held unchanged-line semantics are
  historical trial context only after retirement.
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

The old BoltOdds + PropLine production cutover plan is now superseded. For any
future provider-production work, start from the current production posture:
TheRundown as official artifact source with PropLine fallback/live-movement
sidecar, BoltOdds retired from active runtime, and strict provider/source
promotion closed unless Tyler explicitly opens a new trial. Use
`docs/superpowers/plans/2026-05-13-boltodds-propline-official-provider-cutover.md`
only as historical provider-arbitration context and lessons learned.

That historical plan synthesized or superseded production-facing parts of these
older plans:

- `2026-05-13-boltodds-production-line-movement.md`: use only for the May 13
  stale-slate diagnosis, worker-rotation implementation detail, and historical
  notification/display thinking. It no longer controls active production
  provider behavior.
- `2026-05-07-boltodds-starter-trial.md`: use as trial setup/history and
  worker-branch context. It no longer controls production promotion.
- `2026-05-06-live-layer-event-system.md`: keep as the live-layer foundation.
  BoltOdds notification/provider-source promotion is closed after retirement;
  PropLine notification behavior stays governed by the live-notification plans
  and explicit Tyler approvals.
- `2026-05-05-propline-fallback-and-model-signal-plan.md`: historical fallback
  and diagnostic work is complete. PropLine's current role is fallback and
  live-movement sidecar unless Tyler explicitly opens a new provider plan.
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

The live market decision UI plan now has a default-on actionable-card readout:
`docs/superpowers/plans/2026-05-20-live-market-decision-ui.md`. It remains
display-only and shadow-only with `?marketSheet=0` as rollback/opt-out; any
provider/model/betting-rule behavior still requires separate Tyler approval.

Also revisit the live notification coordinator plan:
`docs/superpowers/plans/2026-05-20-live-notification-coordinator.md`.
That plan captures the future notification product direction after the
operational switch: Supabase `notification_events` should become the primary
durable queue, start-window reminders should be grouped, lock pushes should be
batched, late/post-start betting-action pushes should be suppressed or converted
to system-health alerts, and GitHub `send-notifications` should eventually move
to fallback/artifact-health mode after a clean canary.

Notification rollout note, 2026-05-23:

- Tyler approved moving user-facing pushes to a single sender while the
  Supabase lock canary is active.
- GitHub `send-notifications` now has a repo-variable kill switch:
  `ENABLE_GITHUB_LEGACY_NOTIFICATIONS=false`. When disabled, GitHub still
  publishes artifacts and grades, but it does not call the old Netlify
  artifact-diff sender.
- The live path is Supabase `notification_events` plus Netlify
  `send-live-notifications`; this should be the only user-facing sender during
  the canary.
- Rollback is `ENABLE_GITHUB_LEGACY_NOTIFICATIONS=true`; leave model, provider,
  artifact, grading, and lock behavior untouched.

Notification sender hardening note, 2026-05-24:

- Netlify live sender dependency packaging was repaired with
  `netlify/functions/package-lock.json`; production deploy
  `6a1380ee17600ff413555a06` rebuilt functions with the cache skipped and
  verified `send-live-notifications` against Supabase.
- `send-live-notifications` now suppresses stale queued events instead of
  sending late betting-action pushes. Default stale TTL is 20 minutes and can
  be adjusted with `LIVE_NOTIFICATION_MAX_EVENT_AGE_MINUTES`.
- Suppressed stale rows stay in `notification_events` for audit with
  `send_attempts=3` and a stale-suppression `last_send_error`; normal fresh
  sends continue to mark `sent_at`.
- `/api/send-live-notifications-now` supports authenticated `smoke_check`
  mode, and `scripts/smoke_live_notifications_sender.mjs` can verify the
  deployed sender can read the queue and load Netlify Blobs/subscribers without
  sending pushes when a real `NOTIFY_SECRET` is available.

After the lock layer is strict-canary clean, use the GitHub artifact-exit plan:
`docs/superpowers/plans/2026-05-22-github-artifact-exit.md`.
That plan covers the missing post-lock phase: mirror dashboard JSON artifacts
into Supabase, serve them through a Netlify artifact API with static fallback,
move scheduled pipeline execution to Render, and only then disable GitHub
scheduled artifact publishing. Tyler approved starting the first shadow-mirror
slice after the strict lock canary; later source/scheduler stages still require
their own parity evidence and approval.

Artifact-exit rollout note, 2026-05-24:

- Tyler approved starting Stage 1 after the strict/single-writer lock canary.
- Task 1 and Task 2 add only the Supabase artifact mirror schema and pure
  artifact-row helpers. They do not publish rows, change dashboard reads, move
  schedules to Render, or alter provider/model/betting behavior.
- Tasks 4-8 added gated GitHub shadow publishing, the Netlify artifact API,
  default-static dashboard adapters, a read-only parity checker, and Render
  runner/risk docs. These remain pre-candidate infrastructure; no dashboard
  source or scheduler switch has been made.
- The hosted `published_pipeline_artifacts` and
  `pipeline_artifact_publication_runs` tables now exist, and repo variable
  `ENABLE_SUPABASE_ARTIFACT_PUBLISH=true` is enabled for shadow rows.
- The shadow publisher is now on `main`. Manual `main` run `26367454166`
  wrote 8 Supabase artifact rows, refreshed `published_at`, recorded artifact
  commit `599f275f`, and passed
  `scripts/compare_supabase_artifacts.py --date 2026-05-24 --strict` with 8/8
  matches.
- First scheduled `main` run `26367602689` also published 8 shadow artifacts,
  and follow-up manual `main` run `26367707782` refreshed all 8 rows at
  `2026-05-24T17:18:04Z`, recorded artifact commit `c37896ea`, and passed
  strict parity with 8/8 matches.
- A controlled one-off Render preview canary ran on
  `bbe-pipeline-shadow-runner-hosted` (`crn-d89jpvdckfvc738nfla0`) with
  `ENABLE_SUPABASE_LOCK_CONSUMER=false`, `SUPABASE_LOCK_CONSUMER_STRICT=false`,
  `OFFICIAL_MARKET_SOURCE=therundown`, and
  `ENABLE_BOLTODDS_PIPELINE_SOURCE=false` inside the job. Render job
  `job-d89jqolckfvc738ngg6g` succeeded at `2026-05-24T18:05:02Z` and
  publication run `render-preview-shadow-20260524T180310Z` wrote 8
  `render_pipeline` rows with source commit `d8686401`.
- That Render write intentionally stayed shadow-only. Because GitHub continued
  refreshing official artifacts during the test, the Render rows did not match
  the latest GitHub commit `f124a44b`; the current Supabase mirror was restored
  with `manual-github-artifact-restore-after-render-canary-20260524T181000Z`.
  REST-backed strict parity then passed 8/8 against the latest GitHub artifacts.
- Netlify `get-artifact` is now configured for the production site after deploy
  `6a13455bb5613060d352d0ba`. The function uses hosted Supabase credentials
  server-side; no service credentials are exposed to the browser.
- The Tyler-only dashboard artifact API canary uses
  `localStorage.bbe_artifact_source=supabase`; the default dashboard source
  remains static JSON. Current 2026-05-24 API parity passed after GitHub
  artifact commit `9c87dfe1` refreshed the slate at `2026-05-24T18:43:00Z`.
- The canary initially found missing prior dated-slate rows for the date
  browser. Manual backfill run
  `manual-dated-archive-backfill-20260524T184546Z` added
  `dated_slate:2026-05-21`, `dated_slate:2026-05-22`, and
  `dated_slate:2026-05-23`; direct API checks and strict parity for
  2026-05-23 now pass 8/8.
- Playwright canary after backfill loaded the current slate and
  `?date=2026-05-23` through Netlify `get-artifact` with 200s for
  `dated_slate`, `performance`, `params`, `index`, and `steam`. The
  performance view loaded in Supabase mode. No `get-artifact` console errors
  remained; only the existing favicon 404 and React DevTools info appeared.
- Two earlier Render runner clones, `bbe-pipeline-shadow-runner`
  (`crn-d89jdge7r5hc73dj8300`) and `bbe-pipeline-shadow-runner-v2`
  (`crn-d89jjq3bc2fs73fa0qr0`), were deleted on 2026-05-25 after confirming
  both were inert annual cron clones. The remaining pipeline runner canary
  service is `bbe-pipeline-shadow-runner-hosted`
  (`crn-d89jpvdckfvc738nfla0`).
- Current recommendation after the 2026-05-25 follow-up: use 2026-05-25 as an
  observation day, not a migration day. Dashboard reads remain static by
  default, GitHub schedules remain official, and Render has not been promoted
  beyond a one-off shadow canary.
- The next BBE Operations Brief should verify that the remaining refresh/lock
  windows kept strict locks clean, every GitHub artifact commit still published
  the expected 8 Supabase rows, strict parity stayed clean, and the
  session-only dashboard API canary showed no current/prior-date
  `get-artifact` errors. Only after that review should Task 11 be discussed as
  a separate Render primary scheduler go/no-go.
- Post-slate review on 2026-05-25 found one canary caveat: `Matthew Liberatore`
  remained in top-level `tracked_picks` after the St. Louis probable changed to
  `Brycen Mautz`, so the final artifact showed 25 active tracked picks but only
  24 lockable pitcher-card picks. Code now splits unmatched, still-unlocked
  tracked history rows into `inactive_tracked_picks` with
  `inactive_reason=starter_replaced` or `missing_pitcher_card`, keeping active
  `tracked_picks` aligned with the lockable pitcher-card set. Treat the
  2026-05-24 canary as good-but-not-perfect evidence; Task 11 should wait for
  one clean slate with active tracked picks, Supabase lock rows, and shadow
  timing counts aligned.
- Same-day artifact follow-up on 2026-05-25 found that the stale current-slate
  artifact incident was a GitHub delayed-grading/source dependency issue, not a
  Render lock failure. Commit `213de1fb` prevents grading runs from enriching,
  staging, or publishing current-slate `today.json`; grading now stages only
  dated archives, `performance.json`, `picks_history.json`, and `params.json`,
  and publishes Supabase artifacts with grading scope against the prior slate.
- The 2026-05-24 Supabase mirror mismatch was repaired with
  `source=manual_backfill`; strict artifact parity for 2026-05-24 now passes
  8/8 including `dated_slate:2026-05-24`.
- This strengthens the case for moving the scheduler/source-of-truth path away
  from delayed GitHub schedules, but Task 11 should still be a controlled Render
  primary-scheduler rehearsal/go-no-go with manual GitHub rollback verified.
- Follow-up on 2026-05-26: the current-day artifact was again stale by the
  morning brief until a manual `workflow_dispatch` repair succeeded. This is
  scheduler/source dependency evidence, not a lock failure. The next approved
  move is to rehearse Render pipeline modes with
  `scripts/run_render_pipeline_mode.py --shadow-prefix --execute`; those rows
  publish under `render_shadow:<publish-date>:` keys so the rehearsal cannot
  overwrite the live Supabase artifact mirror or Tyler-only API canary.
- Same-day scheduler-rehearsal setup on 2026-05-26: commit `4c6d0edc` added the
  Render wrapper and shadow-key parity support, then `bbe-pipeline-shadow-runner-hosted`
  was redeployed on that commit. One-off Render job `job-d8as33j7uimc73ck10og`
  succeeded for May 26 full mode and wrote 8 prefixed rows under
  `render_shadow:2026-05-26:`. Normal live artifact keys still matched
  GitHub/static 8/8 afterward. Three morning-only Render shadow cron services
  are now active for the next slate while GitHub remains official:
  `bbe-pipeline-preview-shadow` (`crn-d8as4l1akrks738ngep0`, `17 7 * * *`),
  `bbe-pipeline-grading-shadow` (`crn-d8as4pdckfvc73dgpme0`, `17 10 * * *`),
  and `bbe-pipeline-full-shadow` (`crn-d8as4r8g4nts73b5f510`, `17 13 * * *`).
  Shadow-prefixed runs force the Supabase lock consumer off and keep
  `OFFICIAL_MARKET_SOURCE=therundown`, so they cannot consume official lock
  rows or accidentally test the BoltOdds/PropLine provider cutover. They must
  be evaluated as shadow evidence only.
- Scheduler-only follow-up later on 2026-05-26: commit `228d67fd` hardened the
  shadow wrapper so all `--shadow-prefix` runs force
  `ENABLE_SUPABASE_LOCK_CONSUMER=false`, `SUPABASE_LOCK_CONSUMER_STRICT=false`,
  `OFFICIAL_MARKET_SOURCE=therundown`, and
  `ENABLE_BOLTODDS_PIPELINE_SOURCE=false` while preserving those settings for
  non-shadow/live-key runs. All existing Render shadow services were redeployed
  on that guarded commit. Three refresh-window shadow cron services were also
  created while GitHub remains official:
  `bbe-pipeline-refresh-shadow-day` (`crn-d8asbonavr4c73drnrhg`,
  `7,37 15-23 * * *`), `bbe-pipeline-refresh-shadow-evening`
  (`crn-d8asbrel51nc73ahmh60`, `7,37 0 * * *`), and
  `bbe-pipeline-refresh-shadow-final` (`crn-d8asbv0jo6nc7381gma0`,
  `7 1 * * *`). One guarded one-off Render job
  `job-d8ascuj7uimc73ckb640` succeeded for May 26 full mode, wrote 8 prefixed
  rows through publication run
  `manual-render-pipeline-2026-05-26-20260526T161330Z`, and left the normal
  live artifact keys on GitHub/static-compatible rows with strict parity 8/8.
  Next evidence needed: today's refresh-shadow windows, then tomorrow's
  preview/grading/full shadow windows, must write expected prefixed rows without
  duplicate/wrong-date artifacts before any Task 11 promotion discussion.
- Provider-rehearsal follow-up later on 2026-05-26: the first refresh-shadow
  cron failure showed the newly created Render cron services were missing both
  TheRundown and Supabase runtime env, so they could not test either scheduler
  parity or the provider adapter. Tyler redirected the same shadow services
  toward the higher-value BoltOdds/PropLine rehearsal instead of TheRundown
  parity. Commit `2b3fb2b6` added an explicit
  `--provider-rehearsal` flag to the Render wrapper. Shadow provider-rehearsal
  runs still force the Supabase lock consumer off, but set
  `OFFICIAL_MARKET_SOURCE=boltodds_propline`,
  `ENABLE_BOLTODDS_PIPELINE_SOURCE=true`, and `OFFICIAL_MARKET_STRICT=true`
  while publishing only under `render_shadow:<date>:` artifact keys. The
  preview/full/refresh shadow cron commands now include that flag, and the
  shadow cron services have the hosted Supabase env needed to read
  `official_market_lines` and publish artifact rows. `bbe-pipeline-refresh-shadow-day`
  then succeeded on its scheduled 18:07 UTC run, read 28 ready
  BoltOdds/PropLine official props, wrote all 8 `render_shadow:2026-05-26:`
  artifact rows, and left normal live artifact keys on GitHub source
  `26466152086`. This is a provider/scheduler rehearsal success, not a
  production source switch. Do not judge these provider-rehearsal rows by
  byte-for-byte parity against TheRundown GitHub artifacts; judge them by
  complete prefixed artifact writes, provider coverage/readiness, no normal-key
  overwrite, and later provider comparison diagnostics.
- Same-day refresh-shadow stability fix on 2026-05-26: Render alert emails for
  `bbe-pipeline-refresh-shadow-day` and `bbe-pipeline-refresh-shadow-evening`
  were 512 MiB out-of-memory failures in the shadow provider-rehearsal cron,
  not production pipeline or live-lock failures. Logs showed both runs died
  after pitcher records were built and before shadow artifact publishing,
  consistent with collection-only batter-split backfill pushing the starter
  cron over memory. Shadow-prefixed Render pipeline runs now force
  `BATTER_SPLIT_COLLECTION_MAX_NEW=0`; this preserves provider/scheduler
  rehearsal value while avoiding memory-heavy research backfill on the small
  cron plan.
- Historical Render separation follow-up on 2026-05-29: after the missed May 28 lock was
  traced to delayed GitHub artifacts, Tyler approved waiting another slate but
  cleaning up Render. The active Task 11 scheduler-shadow services now run
  the TheRundown-equivalent command
  `scripts/run_render_pipeline_mode.py --shadow-prefix --execute` without
  `--provider-rehearsal`; provider-rehearsal remains shadow-only but must be
  evaluated separately because strict BoltOdds/PropLine coverage failures do
  not prove scheduler unreliability. Shadow PropLine scheduled polling now
  records provider failures without failing manual shadow-market dispatch, and
  the old BoltOdds worker retry note is historical only after retirement.
- Current override as of 2026-06-17: BoltOdds is retired, so
  `--provider-rehearsal` is fail-closed unless
  `ALLOW_BOLTODDS_PROVIDER_REHEARSAL=true` is set after Tyler explicitly opens a
  new provider trial. Treat the May provider-rehearsal notes above as history,
  not an active recommendation.
- Render primary-scheduler cutover on 2026-05-30: Tyler approved taking the
  scheduler migration live while keeping the provider source on TheRundown.
  The Render scheduler env gap was fixed, all preview/grading/full/refresh
  services were redeployed on current artifact commit `643b262f`, and a
  normal-mode lock run published live Supabase artifact keys. The old shadow
  services were renamed/repointed to live-key commands without
  `--shadow-prefix`, and new
  `bbe-pipeline-lock` (`crn-d8dgp6q8qa3s739n80s0`) runs lock mode every 10
  minutes at `2,12,22,32,42,52 * * * *`. Render pipeline services explicitly
  set `OFFICIAL_MARKET_SOURCE=therundown`,
  `ENABLE_BOLTODDS_PIPELINE_SOURCE=false`,
  `ENABLE_SUPABASE_LOCK_CONSUMER=true`,
  `SUPABASE_LOCK_CONSUMER_STRICT=false`, and
  `ENABLE_GITHUB_FALLBACK_LOCKING=false`. The live layer now has
  `ENABLE_LOCK_ONLY_WORKFLOW_DISPATCH=false` so new lock rows are consumed by
  Render lock cron instead of GitHub lock-only dispatches. GitHub `pipeline.yml`
  keeps manual dispatch only.

Post-cutover cadence planning note, 2026-05-25:

- The intended migration shape is four loops, not one monolithic
  every-10-minute pipeline.
- The live market/control loop is `bbe-live-layer`: keep the 10-minute cadence
  for live provider reads, market-state rebuilds, lock ledger writes,
  notification candidates/events, and compact evidence. This loop must not
  grade, calibrate, rewrite model outputs, or publish dashboard artifacts unless
  a later plan explicitly promotes that behavior.
- The artifact pipeline loop moved to Render on 2026-05-30 after Tyler's Task
  11 approval. Keep the loops separate and use manual GitHub workflow dispatch
  only as rollback/repair.
  Preview, grading, full, refresh, and lock modes should keep their distinct
  responsibilities. A 10-minute refresh cadence can be considered after Render
  parity, provider cutover, runtime, Supabase IO, and notification-value evidence
  prove it is useful; do not treat Render promotion as approval to run every
  pipeline mode every 10 minutes.
- The provider-source loop should feed `official_market_lines` through BoltOdds
  plus PropLine arbitration. The pipeline should consume those curated rows, not
  scan raw `market_snapshots`, when `OFFICIAL_MARKET_SOURCE=boltodds_propline`
  and `ENABLE_BOLTODDS_PIPELINE_SOURCE=true` are eventually approved.
- The notification/product loop should use the live market/control loop for
  dynamic "when to bet" signals, then promote notification classes one at a time
  through the live notification coordinator plan.
- Follow-up planning now tracks six integration gaps before dynamic alerts
  become production behavior: explicit decision-policy thresholds,
  notification-to-bet attribution, accepted-bet analytics ingestion, same-day
  accepted-bet review/correction, live-market bet-ticket prefill, and
  shadow-to-production alert review.
- Implementation contracts are now expected for the first dynamic-alert build:
  alert/deep-link context, attribution match precedence, decision-label v0
  thresholds, and the daily alert-to-bet review output.

## Active Production Path

The official app now runs from Render-published Supabase artifacts:

- Render preview/full/refresh/grading/lock cron services write `today.json`,
  dated archives, `steam.json`, `performance.json`, `params.json`,
  `preview_lines.json`, and `data/picks_history.json` into Supabase
  `published_pipeline_artifacts` live keys.
- Netlify serves the static dashboard shell and `get-artifact` function.
  Dashboard adapters default to the artifact API and fall back to static JSON
  if the API errors.
- GitHub Actions `pipeline.yml` is manual rollback only; scheduled triggers are
  disabled.
- `data/picks_history.json` remains the durable grading/history source.
- `data/results.db` remains ephemeral.

Generated artifacts are user-facing truth. Verify live-slate fixes against the
actual artifacts, not only unit tests.

## Live Notification Layer

The live layer is now separate from the production pipeline.

- Render cron service: `bbe-live-layer`
- Render cron service ID: `crn-d7tpb19o3t8c739p3qig`
- Retired Render BoltOdds worker: `bbe-boltodds-shadow-worker`
- Render BoltOdds worker ID: `srv-d7ugabe7r5hc73b36oag`
- Local Windows Render CLI: installed under `%LOCALAPPDATA%\Render\bin`;
  new shells should resolve `render`, while existing Codex shells may need the
  full `render.exe` path until the parent process is restarted.
- Cadence: every 10 minutes
- Source artifact: fresh dashboard artifact state; during migration, verify the
  live layer reads the current Supabase/Netlify artifact path rather than a
  stale baked Render checkout or stale GitHub raw artifact.
- Market source: PropLine polling when `PROPLINE_API_KEY` is present; optional
  TheRundown mainline shadow polling when
  `LIVE_CAPTURE_THERUNDOWN_MAINLINE=true`
- Shadow provider-state rebuild: `scripts/build_live_events_to_supabase.py`
  can refresh `current_market_lines`, `official_market_lines`,
  `provider_arbitration_decisions`, `provider_request_usage_daily`, and
  `compact_market_line_movements` from the live feed path. The script
  entrypoint enables this by default with freshness guards, so the Render
  live-layer cron can keep the production-shaped shadow tables current even
  though GitHub shadow-market dispatch is now manual-only. Direct test/helper
  calls to `run()` remain opt-in. This is still shadow-only and does not change
  production provider order or pipeline artifacts.
- Live-layer market-state guardrails:
  - `LIVE_CAPTURE_THERUNDOWN_MAINLINE=true` enables TheRundown mainline
    polling inside the Render live-layer run. It writes provider evidence and
    request/data-point usage rows and is active as of the verified
    `2026-06-13T05:30Z` scheduled run. This does not replace the official
    pipeline's TheRundown artifact path; it keeps 10-minute mainline evidence
    current for live/provider decisions.
  - `LIVE_SEND_PROPLINE_WEBHOOK_MOVEMENT_NOTIFICATIONS=true` allows recent
    supported-book PropLine webhook movement rows to create the same line/price
    movement `notification_events` shape as PropLine polling. This only
    affects live movement alerts for current FIRE picks; it does not change
    official odds, picks, grading, model output, locks, staking, provider
    order, or dashboard artifact truth. Roll back by setting the flag false.
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

`live_market_display_state` is the app-facing shadow layer for live-market
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
- As of 2026-05-24, webhook consumption is approved for shadow-only canary
  processing. The live-layer entrypoint defaults
  `LIVE_PROCESS_PROPLINE_WEBHOOKS=true`, bounded by
  `LIVE_PROCESS_PROPLINE_WEBHOOK_LIMIT=100` and
  `LIVE_PROCESS_PROPLINE_WEBHOOK_MAX_AGE_MINUTES=180`. As of 2026-06-24,
  webhook movement notifications apply a separate queue-eligibility freshness
  gate, `LIVE_PROPLINE_WEBHOOK_NOTIFICATION_MAX_AGE_MINUTES=20`, so older
  webhook rows can still be archived as evidence without creating stale
  notification rows. Roll back processing by setting
  `LIVE_PROCESS_PROPLINE_WEBHOOKS=false`.
- `analytics/diagnostics/mainline_movement_pattern_audit.py` is the read-only
  weekly pattern report for movement notifications. It reads processed
  `line_movement_events`, `notification_events`, `market_pick_evidence`, and
  `compact_market_line_movements` rather than broad raw webhook inbox scans.
  The first 2026-06-24 seven-day report found high raw webhook volume, but the
  reviewed candidate alert patterns were still supported-book mainline polling
  rows. Use it to decide what to observe next; do not treat it as approval for
  new notification classes.
- Direct Supabase verification before the canary found 2,638 valid unprocessed
  deliveries and no current webhook-sourced `line_movement_events`; old
  comparison rows exist but are stale. Keep the canary recent-windowed until
  the current slate proves clean.
- The 2026-05-24 GitHub live-layer proof passes processed the current recent
  slice into 95 webhook-sourced movement rows and 26 unsupported-shape rows,
  with zero unprocessed rows left inside the current 3-hour window and zero
  `notification_events` created by the proof window. Older backlog rows remain
  unprocessed by design.
- Existing PropLine webhook versus BoltOdds snapshot comparison rows in
  `shadow_movement_source_comparisons` are stale as of 2026-05-16; refresh that
  comparison from the new webhook movement rows before using it for timing
  claims.
- Refreshed on 2026-05-24 after the webhook canary. Current webhook movement
  rows were materialized into `shadow_provider_movement_events`, matched to the
  nearest BoltOdds snapshot within 90 minutes using normalized pitcher + side
  and the `pitcher_strikeouts` / `Strikeouts` market-key alias, then upserted
  into `shadow_movement_source_comparisons`. The 95 current rows split:
  42 `propline_webhook_first`, 21 `boltodds_first`, and 32
  `no_boltodds_match`. Treat this as shadow timing evidence only.
- Follow-up on 2026-05-25: the receiver is still accepting signed
  `line_movement` deliveries, but direct Supabase verification showed continuous
  live-layer consumption was not yet proven after the manual proof window:
  latest processed delivery was `2026-05-24T23:24Z`, while newer valid rows were
  pending. The live-layer timing row now records `metadata.propline_webhooks`
  from each run so future checks can distinguish "receiver is filling the inbox"
  from "Render is continuously consuming the inbox." Next webhook action is to
  redeploy/verify `bbe-live-layer` on this code path or run a bounded proof
  dispatch and confirm `processed` advances on new rows.
- Two bounded `live-layer-proof` dispatches on commit `9cee9c6` then processed
  the current 3-hour webhook window: first pass read 100 deliveries and wrote 53
  webhook-sourced movement events, second pass read the remaining 47 and wrote
  35 movement events. Recent pending valid rows were 0 afterward, and
  `shadow_pipeline_runs.metadata.propline_webhooks` records both proof results.
  This proves the processor still works on the new code, but Render continuous
  consumption still needs one scheduled `bbe-live-layer` run observed with the
  same metadata.
- Follow-up on 2026-05-26: `bbe-live-layer` was redeployed to current `main`
  after scheduled rows showed `propline_webhooks=skipped`; the next normal
  23:50 UTC cron processed 8 webhook deliveries into 8 movement rows. Recent
  unsupported webhook rows were not malformed standard lines: they were
  alternate strikeout ladder outcomes such as `9+ Strikeouts` with no
  over/under point. The processor classifies those separately as unsupported
  ladder outcomes and still does not write them as standard movement events.
- As of 2026-06-14, Tyler approved promoting clean supported-book webhook rows to
  live line/price movement notifications only, behind
  `LIVE_SEND_PROPLINE_WEBHOOK_MOVEMENT_NOTIFICATIONS=true`. Do not use webhook
  rows for production odds, picks, provider promotion, model behavior, lock
  behavior, or dashboard source-of-truth without a separate review.

### BoltOdds

BoltOdds is retired from active runtime as of 2026-06-17. The old
`codex/boltodds-starter-trial` branch and the historical `main` worker code are
trial context only.

- Branch: `main`
- Render worker: `bbe-boltodds-shadow-worker`, suspended by user via Render API
  on 2026-06-17.
- Render Blueprint: `render.yaml` is intentionally non-deploying
  (`services: []`) so a Blueprint sync cannot recreate the worker.
- Provider rehearsal: `scripts/run_render_pipeline_mode.py --provider-rehearsal`
  is fail-closed unless `ALLOW_BOLTODDS_PROVIDER_REHEARSAL=true` is set after a
  fresh Tyler-approved provider trial.
- Purpose: historical MLB pitcher strikeout market evidence only.
- Writes: shadow-only Supabase provider runs, feed heartbeats, market snapshots,
  coverage audits, and migration-risk diagnostics.
- Production impact: none. Fresh rows after `2026-06-17T17:22:29Z` should be
  treated as accidental reactivation unless Tyler explicitly reopens BoltOdds.

Starter discovery confirmed enough coverage to test the trial:

- Useful/visible: FanDuel, BetMGM, BetRivers, Kalshi, Caesars
- Weird: DraftKings appears in discovery but returned zero authenticated market
  rows during checks
- Missing: theScore

As of 2026-05-12, active BoltOdds capture excludes Kalshi so the remaining
trial can prioritize mainstream-book line movement and CLV evidence while
reducing row volume. Kalshi remains shadow-only unless Tyler explicitly
promotes it as an actionable book with a separate source/arbitration decision.

Do not restart the trial to collect more rows without a new decision.

May 13 stale-slate diagnosis: the persistent worker could heartbeat on the
wrong slate if it started before GitHub's delayed full run updated `today.json`.
The worker now refreshes the production artifact during the WebSocket loop using
`BOLTODDS_ARTIFACT_REFRESH_SECONDS` and rotates forward only when the artifact
date advances, emitting a `slate_rotated` heartbeat. Render must point at
`main` for this and the provider-runtime hardening fixes to deploy.

2026-06-01 follow-up: after the Render/Supabase artifact cutover, the BoltOdds
worker was still defaulting to raw GitHub `today.json` and a stale 2026-05-30
slate. Commit `eea0e51f` changes the normal worker default to the Netlify
`get-artifact?type=today` API while keeping manual `SLATE_DATE` replay local
unless an artifact URL env var is explicitly supplied. Render deploy
`dep-d8evpud9j78s73flambg` started on commit `eea0e51f`; the first attempt hit
BoltOdds Starter's one-connection policy while the old stale socket drained,
then retry run `24327701-59a9-4f6d-a2bf-3331eaeab456` started/ready on
2026-06-01 with the Netlify artifact path and no error as of 21:53Z. Next brief
should confirm fresh books_seen/message/snapshot rows and no revived
2026-05-30 heartbeats before using BoltOdds evidence in any provider review.
Same-day follow-up at 2026-06-02 00:33Z confirmed that retry run was active on
slate_date 2026-06-01, had fresh heartbeats with FanDuel, BetMGM, BetRivers,
and Caesars, had 4,339 messages by the latest heartbeat, and had written 3,318
snapshot rows through 2026-06-02 00:32:59Z. Keep BoltOdds shadow-only, but the
stale-slate artifact-source issue is no longer the active blocker.

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
- `analytics/diagnostics/market_anchored_k_shadow_rebuild.py`
- `analytics/diagnostics/gate_c_holdout_shadow_lab.py`
- `analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py`
- `analytics/diagnostics/gate_f_projection_challenger_shadow_report.py`
- `analytics/diagnostics/batter_handedness_shadow_audit.py`
- `analytics/diagnostics/historical_lineup_handedness_backfill.py`
- `analytics/diagnostics/pre_post_428_model_review.py`
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
- `tests/test_market_anchored_k_shadow_rebuild.py`
- `tests/test_gate_c_holdout_shadow_lab.py`
- `tests/test_market_favorite_confidence_referee_shadow_lab.py`
- `tests/test_gate_f_projection_challenger_shadow_report.py`
- `tests/test_batter_handedness_shadow_audit.py`
- `tests/test_historical_lineup_handedness_backfill.py`
- `tests/test_pre_post_428_model_review.py`
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
- Live-market outcome context is now a separate shadow read. PropLine and
  historical BoltOdds evidence can be joined to graded rows by slate, normalized pitcher, and side,
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
  supported book line after provider mainline selection. Use it during PropLine
  review to separate single-book outliers from
  ref-book-vs-majority conflicts and to see whether disagreement would have
  created better executable candidates. It is not a promotion plan; any live
  best-line selection needs CLV/outcome proof and separate approval.
- Use `docs/research/market-tracker-map.md` as the current tracker inventory
  before adding more PropLine/Supabase tracking. It distinguishes existing raw
  evidence tables from the compact long-term research row.
- The weekday `BBE Operations Brief` should now digest the tracker stack daily:
  market-price audit, live-market outcome audit, pitcher K outcome dataset,
  PropLine and historical BoltOdds movement evidence, price CLV, line CLV,
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
- The 2026-05-26 hard review added
  `analytics/diagnostics/pre_post_428_model_review.py` and
  `analytics/diagnostics/batter_handedness_shadow_audit.py`. The fair immediate
  pre-bump window had 428 tracked picks across 20 slates, 21.40 picks/slate,
  +12.63u / +2.9% flat ROI, and +7.64u / +1.2% staked ROI. The 2026-04-28+
  window had 603 tracked picks across 28 slates, 21.54 picks/slate, -15.68u /
  -2.6% flat ROI, and -17.30u / -2.5% staked ROI. Whole-market
  projection quality did not get worse: MAE improved from 1.862 to 1.804,
  RMSE improved from 2.394 to 2.287, and side accuracy stayed roughly flat
  at 54.6% to 54.2%. The issue is selection/regime inversion, not a broad
  projection collapse: unders flipped from +9.2% ROI pre-bump to -9.2%
  post-bump, overs flipped from -8.9% to +6.0%, and FIRE 1u flipped from
  +14.5% to -5.1%.
- The same 2026-05-26 refresh expanded the compact outcome proof to 1,174
  clean graded rows and 603 tracked picks with zero duplicate dataset keys,
  zero missing results, zero missing team/opponent, and zero missing book odds.
  The confidence-referee report is useful as a Gate C diagnosis surface, but
  not as a live rule: `wait_for_late_data` was positive, while
  `bet_late_if_still_available` was poor and should be treated as a warning
  label until rewritten and retested.
- Path B batter-handedness moved from "missing compact fields" to "ready for a
  deeper shadow audit" after
  `analytics/diagnostics/historical_lineup_handedness_backfill.py` rebuilt
  opponent lineup hand counts from MLB boxscores. The 2026-05-26 run checked
  1,174 compact rows, 587 unique lineup keys, reconstructed 587/587 lineups,
  and had 0 unmatched lineups and 0 existing lineup-count mismatches. The
  compact dataset now has 1,174/1,174 R/L/S hand-count rows and 1,174/1,174
  matchup buckets, all marked `mlb_boxscore_reconstructed` and not runtime-safe.
  Early tracked-outcome read: same-hand-heavy rows were 440, 229-211, -5.05u,
  -1.1% ROI; opposite-hand-heavy rows were 163, 81-82, -10.63u, -6.5% ROI.
  Handedness context is useful enough for a Path B holdout comparison, but it
  does not by itself solve the post-bump under problem or justify live lambda
  changes.
- `analytics/diagnostics/gate_c_holdout_shadow_lab.py` now runs the first
  train/validation Gate C holdout. On 587 official-close markets it trained on
  2026-04-28 through 2026-05-16 and validated on 2026-05-17 through
  2026-05-25. Validation did not support discarding lambda: `current_model`
  side accuracy was 110-80 / 57.9%, while `over_only` was 98-92 / 51.6% and
  `market_favorite_only` was 97-88 / 52.4%. `market_shrink_25` slightly
  improved validation MAE (1.801 vs 1.820), while `high_line_temper` and
  `handedness_bucket_adjust` slightly improved side accuracy (111-79 / 58.4%).
  Treat those as Gate F candidates to study, not live model changes.

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

2026-06-01 follow-up: `analytics/diagnostics/pitcher_k_outcome_dataset.py` now
has an explicit `--artifact-source production` mode that reads Netlify
`get-artifact` `index`, `dated_slate`, and `picks_history` artifacts instead of
stale committed local files. Current production dated-slate coverage starts at
2026-05-21; older clean-window dates listed in `index` return 404 and are
skipped with a warning. A fresh production-backed run produced 372
official-close side rows and 188 tracked rows, with 0 duplicate keys, 0 missing
results/team/opponent/odds/model fields, and 188/188 tracked rows reconciled
for loaded dates. Treat this as a fresh partial production read; full
2026-04-28+ clean-window reporting still needs historical dated-slate backfill
or a clearly-labeled hybrid local-plus-production analysis. This remains
shadow-only and does not change live lambda, thresholds, staking, verdicts,
provider order, notifications, or dashboard behavior.

2026-06-03 follow-up: Gate C now has a committed durable research artifact
under `data/research/gate_c/`, built by
`scripts/build_pitcher_k_outcome_dataset.py` in `hybrid` mode. Hybrid mode uses
local committed archive rows as the broad historical base and fills graded
dates that are missing or incomplete locally from production `get-artifact`
dated slates and `picks_history`. The current artifact covers 2026-04-28
through 2026-06-02 with 1,470 official-close side rows, 757 tracked rows, 0
duplicate dataset keys, 0 missing results/team/opponent/odds, and 757/757
tracked rows reconciled. This is the preferred full-corpus Gate C read for
briefing and research; production `get-artifact` alone remains useful for
freshness checks but can be partial when the published index or historical
mirror is incomplete.

### BoltOdds Retirement Review

Use `docs/superpowers/plans/2026-05-07-boltodds-starter-trial.md` only as
historical trial context. After the 2026-06-17 suspension, the operational
check is whether fresh BoltOdds heartbeats or snapshots reappear accidentally;
do not buy Pro, restart the worker, or promote BoltOdds without a new Tyler
decision.

Before raw `market_snapshots` retention is enforced, the cutover branch still
needs compact movement rollups and provider request-usage writes to prove the
storage/cost path is safe.

As of 2026-05-21, Supabase is on Pro. The first surprise-bill guardrail is to
track total database size, top table size, and egress before adding more capture
volume. If the database approaches `6 GB`, egress trends toward the plan
allowance, or `market_snapshots` keeps growing without changing decisions, pause
new capture work and run retention dry-runs before considering overages.

2026-06-09 retention-readiness update: added
`scripts/supabase_retention_readiness.sql` as a read-only linked-CLI report for
raw `market_snapshots` age/size and bounded compact-coverage sampling:

```powershell
npx supabase db query --linked --file scripts\supabase_retention_readiness.sql -o json
```

Added `scripts/backfill_compact_market_movements_via_cli.py` for linked-CLI
compact backfills without local service-role env vars. It defaults to dry-run
and never deletes raw rows. The 2026-06-09 May 1-26 compact backfill upserted
`19,227` compact rows from `496,436` raw rows.

Latest post-backfill readiness run: database `1150 MB` (`14.04%` of 8 GB Pro
allowance); `market_snapshots` about `785 MB`; 14-day raw rows `463,997` /
estimated `517 MB`; 30-day raw rows `175,070` / estimated `195 MB`. The bounded
provider-indexed compact-coverage samples were clear in both windows
(`uncovered_snapshot_groups=0`). `coverage_exact=false` and
`eligible_for_execute=false` remain by design; retention execution remains
closed until Tyler separately approves an execute step or we add an exact
coverage proof.

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

2026-06-02 provider rehearsal follow-up:

- GitHub shadow-market run `26833112223` succeeded after the cutover comparison
  diagnostic was updated to read `provider_request_usage_daily` automatically.
  PropLine usage gate passed at 336 requests, about 6.7% of the 5,000/day Hobby
  budget. Schedule-first coverage passed: 28/29 probable starters covered,
  28/29 with FanDuel or DraftKings, 25/29 with DraftKings, and 28/29
  official-ready. The older raw TheRundown-prop denominator still reported
  27/32 covered and should be treated as overlap evidence, not the sole
  official-starter gate.
- Render provider-mode shadow artifact rehearsal
  `job-d8fg8ql53gjs73a586ng` succeeded on the idle shadow-runner after deploy
  `dep-d8fg7tmrnols73b5ktu0`. It wrote only
  `render_shadow:2026-06-02:` artifact keys. Shadow `today` had 28 pitcher rows,
  16 tracked picks, all `odds_source=boltodds+propline`, all with
  `official_market_line_id`, and all with `book_odds`.
- Do not promote provider source yet. The shadow artifact was not a no-op
  replacement for production: it matched 15 tracked picks exactly, dropped live
  LEANs for Connor Prielipp and Nathan Eovaldi, and added a provider-only LEAN
  for Kyle Harrison. The next decision is whether Tyler wants a controlled
  morning provider-source canary that accepts pick-set differences, or another
  shadow slate to understand why those differences occurred.

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
