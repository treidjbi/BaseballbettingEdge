# Active Gates And Soak Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate BaseballBettingEdge's active operating plans into one gate index so daily work can tell what is already operational, what is soaking, and what still requires Tyler's explicit promotion approval.

**Architecture:** Keep detailed implementation rules in the existing dated child plans, but use this document as the active gate matrix and sequencing surface. Separate operational/display adoption from production behavior promotion so BoltOdds/PropLine, notifications, UI, and model research can advance without accidentally changing source-of-truth, model math, thresholds, staking, locks, retention, or notification classes.

**Tech Stack:** Documentation-only coordination plan over the existing Python pipeline, Render cron services, Supabase operational tables, Netlify functions, dashboard v2, and analytics diagnostics.

---

Date: 2026-06-09
Owner: Tyler + Codex
Status: Active synthesis plan

## Operating Decision

Tyler approved formalizing the active gates on 2026-06-09 after the June 8/9
operations brief showed the system was healthy but spread across many dated
plans.

This plan does not merge or delete historical plans. It gives future agents one
place to answer:

- Is this already operational?
- Is this only display or shadow evidence?
- Is this soaking with defined pass/fail checks?
- What exact gate must pass before production behavior changes?
- Which child plan controls the implementation details?

## Non-Goals

- Do not change production code or environment variables from this synthesis.
- Do not promote strict provider mode.
- Do not change official source-of-truth rules.
- Do not change lambda, thresholds, staking, calibration, or
  `formula_change_date`.
- Do not enable new notification send classes.
- Do not delete raw Supabase rows.
- Do not remove GitHub manual rollback.
- Do not treat UI display value as provider, model, or notification promotion.

## Plan Hierarchy

Use the docs in this order for active work:

1. `AGENTS.md`
2. `docs/current-state.md`
3. This synthesis plan
4. The controlling child plan for the specific lane:
   - Provider/source: `2026-05-13-boltodds-propline-official-provider-cutover.md`
   - Operational foundation: `2026-05-19-supabase-operational-foundation.md`
   - Artifact exit: `2026-05-22-github-artifact-exit.md`
   - Notifications: `2026-05-20-live-notification-coordinator.md` and
     `2026-06-04-live-notification-digest-coordinator.md`
   - UI display: `2026-05-20-live-market-decision-ui.md`
   - Model/research: `2026-05-12-pitcher-k-outcome-research-dataset.md`
   - Confidence referee: `2026-06-05-market-favorite-confidence-referee-production-canary.md`
   - Path B: `2026-06-07-batter-handedness-path-b-canary.md`
   - Market agreement: `2026-06-07-market-agreement-tracker.md`
   - Projection challengers: `2026-06-03-gate-f-projection-challenger-shadow-plan.md`
   - Workload/no-vig: `2026-06-08-workload-no-vig-k-projection-ev-synthesis.md`

If this synthesis conflicts with a child plan, use `docs/current-state.md` plus
the newest child plan for implementation details, then update this synthesis so
the gate index matches the current decision.

## Duplicate Plan Read

The active plans are not true duplicates, but several now describe the same
operational surface from different angles.

| Cluster | Keep As | Why |
| --- | --- | --- |
| Provider, live market display, notifications | Separate child plans under this synthesis | Provider source-of-truth, UI display, and notification sends have different risk gates. |
| Gate C, confidence referee, Path B, workload/no-vig, Gate F | Separate child plans under the model lane | Each candidate family needs its own evidence and rollback standard. |
| Supabase foundation, artifact exit, lock ledger, storage guardrails | Separate operational child plans | Scheduler, locks, artifacts, and retention fail differently. |
| Market agreement and live-market audits | Tracking child plans | They add labels and reads, not production behavior. |

Do not physically merge these plans into one giant document. Use this plan as
the short control plane and leave the child plans as implementation history and
rulebooks.

## Gate Matrix

### Gate 1: Render/Supabase Artifact Path

**State:** Open and operational.

Render and Supabase are the primary scheduled artifact path. Netlify
`get-artifact` is the dashboard artifact source, with static/GitHub rollback
available through manual `workflow_dispatch`.

Pass checks to keep this gate open:

- Preview, grading, full/refresh, and lock modes publish expected artifact keys.
- `today`, dated slate, `steam`, `performance`, `params`, `preview_lines`,
  `picks_history`, and optional `fangraphs_cache` are fresh when expected.
- Render modes hydrate from Netlify `get-artifact` before publishing so stale
  checkout copies are not republished.
- Manual GitHub rollback remains available.

Failure response:

- Repair only the current approved production path.
- Verify Render/Supabase/Netlify freshness before using GitHub rollback.
- Do not use an artifact incident as provider or model promotion evidence.

### Gate 2: Lock Ledger And Lock Consumer

**State:** Open for non-strict operation; strict escalation closed.

The lock ledger is operational and Render lock mode can replay consumed rows to
repair artifacts. Strict single-writer behavior remains a separate discussion.

Strict-mode discussion can begin only when:

- At least five consecutive active lock slates show no unconsumed due rows.
- `started_unlocked_count = 0`.
- Duplicate/wrong-date risk is absent.
- Render lock failures recover without stale dashboard artifacts.
- GitHub manual rollback remains available.

Still closed:

- `SUPABASE_LOCK_CONSUMER_STRICT=true`
- any lock behavior that removes the current repair/fallback posture

### Gate 3: BoltOdds/PropLine Dashboard Display

**State:** Open and operational as display evidence.

BoltOdds/PropLine data is already powering live market display and book-board
context through sanitized Supabase/Netlify reads. That means it can help Tyler
shop prices and understand market movement.

This gate does not approve:

- official source-of-truth cutover
- strict provider mode
- model/ranking changes
- automatic bet placement
- new notification send classes

Keep-open checks:

- `live_market_display_state` is fresh during active slates.
- Dashboard labels clearly distinguish playable, shop, stale, off-market, same
  line, and different line states.
- PASS cards stay quiet.
- Accepted-bet/live-book selector does not coerce missing line or odds into
  misleading values.

### Gate 4: Official Provider Source

**State:** Closed; non-strict provider-source canary is active.

Render preview/full/refresh may use the BoltOdds + PropLine adapter in
non-strict mode, with TheRundown fallback/rollback still available. This is not
the same as official provider promotion.

Promotion review can begin only when a clean schedule-first sample shows:

- At least 95% probable-starter coverage by usable official market lines.
- FanDuel and DraftKings coverage is reliable; DraftKings may remain PropLine.
- Supported-book attribution is clear in `today`, dated archive, and `steam`.
- Provider conflicts fail closed or fall back predictably.
- Freshness guards catch stale provider state.
- Pick-set differences versus rollback source are explainable.
- No stale artifact or lock regression follows provider-source canary runs.
- Row-volume and request usage remain inside cost guardrails.

Still closed:

- `OFFICIAL_MARKET_STRICT=true`
- removing TheRundown rollback
- canceling fallback before post-cutover proof
- widening provider usage for spend without cost review

### Gate 5: Dynamic Notifications From Provider Evidence

**State:** Grouped notification classes are operational; new movement-action
classes are closed.

`LIVE_NOTIFICATION_COORDINATOR_MODE=grouped` is active for approved grouped
classes:

- start-window reminders
- same-run pick-change digests

Line/price movement remains individual. Provider-driven dynamic notification
classes must start as shadow labels.

Next implementation gate:

- Complete Task 5 from `2026-06-04-live-notification-digest-coordinator.md`:
  movement-strength labels in shadow.

Shadow movement labels should include:

- `single_book`
- `broad_confirmation`
- `propline_polling_confirmed`
- `propline_webhook_confirmed`
- `boltodds_confirmed`
- `provider_conflict`
- `volatile_or_reversed`
- `stale_or_heartbeat_missing`

Promotion review for any new user-facing movement class requires:

- At least two clean active slates of would-have-sent rows.
- No duplicate send rows for the same pitcher/side/action.
- Zero stale post-start betting-action sends.
- Clear evidence that the alert would change Tyler's action: bet now, shop
  price, wait, or ignore.
- Narrow first candidate: active FIRE picks only, pre-lock, fresh provider
  state, and broad or explicit provider confirmation.

Still closed:

- broader BoltOdds/PropLine movement sends
- webhook-derived live sends
- notification classes that change model verdicts or stakes

### Gate 6: Live Market Decision UI

**State:** Open and operational as default-on display.

The market sheet and book selector are default-on for actionable cards, with
`?marketSheet=0` as rollback.

Keep-open checks:

- Mobile scan density is acceptable.
- Stale/live labels are clear.
- Same line versus different line is clear.
- Best/model-ref/playable tags do not imply official provider promotion.
- Accepted-bet selector preserves manual edits and audit metadata.

Open follow-up:

- Finish and push the accepted-bet live-book selector hotfix so null/blank
  book line or odds cannot display or save as misleading zero values.

### Gate 7: Gate C Research Dataset

**State:** Open for baseline durable evidence; refreshed/backfilled for current
research reads.

The durable Gate C artifact is the preferred full-corpus research input.
Runtime canary fields for Path B and the confidence referee are present in the
current rows, while no-vig, workload, and market-agreement reads remain derived
shadow labels from the existing row fields.

2026-06-09 Phoenix update:

- The actual opportunity backfill reconstructed `831/831` unique pitcher-game
  opportunity keys from MLB boxscores.
- Actual IP, pitch count, and batters faced now populate all `1,662` Gate C
  side rows.
- These fields are marked `actual_opportunity_runtime_safe=false`; they are
  postgame explanation labels, not pre-lock model inputs.

Pass criteria:

- Zero duplicate dataset keys.
- Clean reconciliation to `picks_history`.
- No hindsight-only fields used as runtime-safe labels.
- Current-regime rows are clearly separated from older context.

### Gate 8: Workload/No-Vig Task 5

**State:** Implemented as an optional Gate C refresh hook; soaking as
shadow-only explanation evidence.

Scope:

- Wire the workload/no-vig audit into the Gate C refresh path behind an
  explicit CLI flag or documented command.
- Keep the report shadow-only.
- Do not change live lambda, EV, thresholds, staking, provider order,
  notifications, locks, retention, or dashboard source-of-truth.

Pass criteria:

- The report runs from the refreshed Gate C artifact.
- Path B and confidence-referee sections contain real slices instead of only
  readiness placeholders.
- Output states Gate E/F status for workload, no-vig, referee v2, Path B, and
  projection-challenger families.

Current read:

- The refreshed report analyzes `854` clean tracked win/loss rows from `1,662`
  source rows and reconciles `855/855` clean graded picks.
- The actual opportunity backfill improves miss classification after the fact,
  but it does not change the workload/no-vig gate because those labels remain
  pregame-derived unless a separate Gate E/F plan proves a runtime-safe input.

### Gate 9: Confidence Referee

**State:** Open as a production canary; still bounded.

`MARKET_FAVORITE_REFEREE_MODE=enforce` is active. It is verdict-conversion
only: it may lower confidence on runtime-safe market-fade rows while preserving
raw verdict metadata.

Keep-open checks:

- Referee metadata appears on tracked rows.
- Applied caps and would-cap rows are counted daily.
- Capped rows are compared against CLV, no-vig labels, workload labels,
  Path B coverage, and outcome after grading.
- Any surprising behavior can roll back by setting
  `MARKET_FAVORITE_REFEREE_MODE=shadow|off`.

Still closed:

- stricter referee v2 behavior
- raising verdicts
- changing lambda, thresholds, or staking
- using post-start or result fields as runtime inputs

2026-06-09 evidence update:

- `analytics/diagnostics/confidence_referee_canary_audit.py` now reads the
  durable Gate C dataset instead of the stale `picks_history` metadata path.
- Current report read: `1,662` source rows, `164` rows with referee metadata,
  and `14` applied caps (`6` FIRE 1u -> LEAN, `1` FIRE 2u -> FIRE 1u, `7`
  FIRE 2u -> LEAN).
- This fixes the audit surface only; it does not change the live referee,
  threshold, staking, model, provider, lock, notification, retention, or
  dashboard behavior.

### Gate 10: Path B Handedness

**State:** Open as a live input canary; promotion to normal behavior still
needs evidence.

`BATTER_HANDEDNESS_MODE=path_b` is active. It can use live-collected PA-backed
split samples when available and must fall back per batter to Path A when not.

Keep-open checks:

- Every artifact row exposes `batter_handedness_mode`.
- `lineup_split_source`, real split counts, and fallback counts are present.
- Missing or untrusted rows fall back cleanly.
- Historical backfill is not used as a live input.

Promotion discussion can begin only after:

- Several clean full slates show real split coverage, not just mode metadata.
- Path B rows can be sliced against outcome, CLV, workload/no-vig labels, and
  confidence-referee caps.
- No artifact-contract regressions appear.

### Gate 11: Projection, Threshold, And Staking Changes

**State:** Closed.

Gate F projection challengers remain shadow-only. Current reports show
directional signals, but no challenger has passed promotion standards.

Promotion review requires:

- Gate E research readiness for the candidate family.
- Gate F holdout lift.
- Rolling-window support.
- Side, price, K-line, provider, quality, timing, workload, Path B, and CLV
  slice survival.
- No FIRE 2u degradation.
- Runtime-safe inputs only.
- One clear rollback flag.

Still closed:

- `lambda` formula changes
- `params.json` manual changes
- global verdict thresholds
- staking ladder changes
- `formula_change_date` changes

### Gate 12: Market Agreement Tracker

**State:** Open as shadow tracking; promotion behavior closed. The overall
sample is now review-ready, but candidate behavior remains closed.

The market agreement tracker is implemented and should help interpret whether
live market movement confirmed or contradicted the model side.

Sample gates:

- Overall tracker read stays `watch_only` until at least 75 graded rows have
  movement-backed evidence.
- Candidate buckets stay `watch_only` until at least 50 graded rows exist.
- Candidate buckets become `promotion-plan eligible` only when the candidate
  also passes the Gate 12A universal promotion floor below.

Bucket-specific reads:

- `lean_market_with_us`: eligible only as a future "review/playable LEAN"
  candidate when the bucket has at least `50` graded rows, positive ROI,
  non-negative CLV, and survives over/under, K-line, no-vig, workload, Path B,
  provider, and rolling-window slices. It cannot auto-promote LEANs.
- `fire_market_against_us`: eligible only as a future de-risk/referee-v2
  candidate when the bucket has at least `50` graded rows, negative ROI or
  meaningfully worse CLV, and the weakness survives FIRE 1u/FIRE 2u, side,
  K-line, provider, timing, workload, Path B, and rolling-window slices. It
  cannot auto-downgrade FIRE rows without a separate plan.
- `referee_cap_*`: review-ready at `50` total graded cap rows, but individual
  cap sub-buckets remain watch-only until they have at least `20` graded rows
  each. These buckets can only audit whether the referee is too strict or too
  loose; they cannot raise verdicts or override caps automatically.
- `mixed_or_reversed`, `single_book_*`, and `line_half_plus` buckets must be
  treated as volatility/timing labels until they survive provider and stale-row
  checks. A single-book or reversed move is not enough to define behavior.

2026-06-09 evidence update:

- Compact Supabase backfill used `market_pick_evidence` and
  `live_market_display_state`, plus Gate C metadata/result overlay.
- Current report read: `2,482` evidence rows, `2,171` graded rows, and `56`
  graded confidence-referee cap rows.
- The tracker can now support Gate E review of movement agreement buckets, but
  it still cannot promote LEANs, override caps, change notifications, or change
  model/provider behavior.

Still closed:

- auto-promoting LEANs
- overriding confidence-referee caps
- changing model, staking, provider, notification, or dashboard behavior

### Gate 12A: Bet-Selection And Edge Candidate Gates

**State:** Open as Gate E research evidence; production behavior closed.

The bet-selection/edge synthesis report turns the durable Gate C row into
candidate labels for selection quality. It is the place to test whether edge,
adjusted EV, no-vig probability, CLV, model-market relationship, workload, and
postgame opportunity explanations agree or conflict.

Universal floors before any candidate can move beyond watch-only:

- Source rows come from the durable Gate C dataset for the clean `2026-04-28+`
  regime.
- The overall report has at least `500` clean tracked win/loss rows and clean
  reconciliation.
- A candidate bucket has at least `75` graded rows for a narrow single-purpose
  review, or `150` graded rows before it can justify a production-plan draft.
- The candidate is not explained by one slate, one pitcher, one provider, one
  book, or one K-line cluster.
- Required fields are present on at least `90%` of candidate rows:
  `edge`, `adj_ev` or `locked_adj_ev`, `model_no_vig_gap`, CLV fields,
  side, verdict, K line, quality gate, model-market relationship, workload
  labels, and provider/source attribution when available.
- The candidate survives side, over/under, FIRE 1u/FIRE 2u/LEAN, plus/minus
  price, K-line, quality, timing, model-market, no-vig, CLV, workload,
  Path B, provider, market-agreement, and rolling-window slices.
- Hindsight-only fields, including `actual_ip`, `actual_pitch_count`,
  `batters_faced`, result, and PnL, are explanation fields only. They cannot
  define a runtime selector.
- A promotion-plan draft must name the exact runtime-safe input fields, the
  intended behavior change, the feature flag or rollback switch, and the first
  slate/scope of the canary.

Candidate-specific gates:

| Candidate label | Possible future use | Research-ready floor | Promotion-plan floor |
| --- | --- | --- | --- |
| `clv_supported` | Positive-process label; possible LEAN review cue | `75` graded rows, positive ROI, beat-close-price or beat-close-line on most rows, and no negative side/verdict split | `150` graded rows, positive ROI after removing one slate, CLV support survives side, verdict, timing, provider, no-vig, workload, Path B, and market-agreement slices |
| `high_edge_skeptic` | De-risk high raw-edge rows when market/no-vig/workload disagree | `75` graded rows, negative ROI or worse CLV, and weakness not isolated to one slate/provider/K-line | `150` graded rows, negative ROI survives side, FIRE 1u/FIRE 2u, plus/minus price, no-vig, workload, Path B, CLV, market-agreement, and rolling-window slices |
| `fire_under_watch` | Narrow FIRE-under downgrade/referee-v2 candidate | `50` graded rows, negative ROI, and weakness is tied to runtime-safe market/workload/no-vig labels, not postgame opportunity | `100` graded rows, no FIRE 2u degradation risk, negative ROI survives K-line, price, timing, provider, CLV, workload, Path B, and rolling-window slices |
| `moderate_edge_clean_context` | Possible keep/upgrade cue for clean moderate edges | `50` graded rows, positive ROI, confirmed no-vig edge, and non-negative CLV | `100` graded rows, positive ROI survives over/under, LEAN/FIRE, K-line, timing, provider, workload, Path B, and market-agreement slices |
| `baseline_watch` | Control bucket only | Always report as context | Never promotion-eligible by itself |

Current read from `analytics/output/bet_selection_edge_synthesis.md`:

- Overall sample is research-ready: `854` clean tracked win/loss rows.
- `clv_supported` is promising but still needs slice survival:
  `101` rows, `56-45`, `+7.44`, `+7.4% ROI`.
- `high_edge_skeptic` is a de-risk candidate but must survive slices:
  `326` rows, `160-166`, `-20.18`, `-6.2% ROI`.
- `fire_under_watch` is the clearest watch item but remains below the
  production-plan floor: `58` rows, `22-36`, `-10.69`, `-18.4% ROI`.
- `moderate_edge_clean_context` is watch-only: `25` rows and below the
  research-ready floor.

Still closed:

- any automatic LEAN promotion
- any automatic FIRE downgrade
- any global threshold, staking, EV, lambda, or formula change
- any runtime use of postgame opportunity fields
- any provider, notification, lock, retention, or dashboard source-of-truth
  change

### Gate 12B: Profit-Rescue FIRE Exposure Canary

**State:** Active downgrade-only production canary. Tyler approved
`PROFIT_RESCUE_REFEREE_MODE=enforce` on 2026-06-10 after the first audit showed
material downside control in the FIRE bucket.

The 2026-06-10 profit-rescue plan adds
`PROFIT_RESCUE_REFEREE_MODE=off|shadow|enforce` after the quality gate and
market-favorite confidence referee. Default is `off`. `shadow` adds metadata
only. `enforce` can only lower verdicts:

- remaining `FIRE 2u` -> `FIRE 1u`;
- remaining FIRE unders -> `LEAN`;
- remaining model-fades-market-favorite FIRE rows -> `LEAN`.

This is intentionally downside-only. It does not promote LEANs, change lambda,
change global thresholds, change staking, change provider order, change
notifications, change locks, change retention, or change dashboard
source-of-truth.

Current read from `analytics/output/profit_rescue_audit.md`:

- Clean tracked win/loss rows analyzed: `854`.
- Current clean-regime FIRE exposure: `536` rows, `-34.07u`.
- Proposed retained FIRE exposure: `118` rows, `+8.35u`.
- Last 7 days: current FIRE `64` rows, `-15.93u`; proposed retained FIRE `11`
  rows, `-1.84u`.
- Last 30 days: current FIRE `359` rows, `-24.78u`; proposed retained FIRE
  `81` rows, `+2.68u`.

Production activation:

- `PROFIT_RESCUE_REFEREE_MODE=enforce` is active on the seven Render pipeline
  cron services as of commit `c60bd895`.
- Manual Render refresh `job-d8kpc9bbc2fs73cr7uh0` succeeded and published
  `today.json` generated at `2026-06-10T16:52:46Z`.
- Public artifact verification showed `54/54` side payloads in enforce mode,
  seven applied profit-rescue caps, `17` current actionable LEAN sides, and
  zero current FIRE side verdicts.
- Same-day caveat: Carlos Rodon under remains as one top-level locked
  `FIRE 1u` row because it locked at `2026-06-10T16:40:29Z` from the
  pre-reconciliation artifact. Treat it as a stale-lock caveat for June 10, not
  fresh post-canary FIRE evidence.

Next decision:

- Observe the enforce canary against graded outcomes, CLV, provider/source
  attribution, FIRE/LEAN, side, K-line, quality, timing, Path B, workload,
  market agreement, and rolling-window slices.
- Roll back with `PROFIT_RESCUE_REFEREE_MODE=off` if it behaves unexpectedly.

Still closed:

- any LEAN promotion
- any model/lambda/threshold/staking change
- any provider, notification, lock, retention, or dashboard source-of-truth
  change

### Gate 12C: FIRE Re-Entry Selection Lab

**State:** Shadow measurement active; no re-entry production behavior approved.

The 2026-06-10 FIRE re-entry lab changes the Gate F question from only "what
should we cap?" to "which capped or retained FIRE-like rows can earn FIRE back
with enough runtime-safe evidence?"

Current read from `analytics/output/gate_f_fire_reentry_lab.md`:

- Clean tracked win/loss rows analyzed: `854`.
- Historical FIRE-like rows analyzed: `638`.
- Profit-rescue shadow retention: `134` retained FIRE rows and `504`
  capped-to-LEAN rows, or `21.0%` retained.
- Ready-for-plan candidates: none.
- Runtime-safe watch candidates:
  - `moderate_edge_quality_reentry`: `68` rows, `38-30`, `+4.77u`,
    `+7.0% ROI`, but recent PnL was negative and slice risks remain.
  - `retained_fire_control`: `134` rows, `77-57`, `+2.71u`, `+2.0% ROI`,
    but recent PnL and multiple slices are negative.
- `clv_supported_reentry` is a process anchor, not a runtime selector:
  `83` rows, `48-35`, `+15.88u`, `+19.1% ROI`, but CLV is post-close evidence
  and cannot be the live rule by itself.
- `avoid_fire_under_reentry` strongly supports keeping the under brake:
  `348` rows, `164-184`, `-32.77u`, `-9.4% ROI`.

Next decision:

- Keep `PROFIT_RESCUE_REFEREE_MODE=enforce` while collecting graded rows.
- Rerun the re-entry lab after each grading cycle and track whether
  `moderate_edge_quality_reentry` or `retained_fire_control` improves recent
  PnL and survives side, K-line, price, timing, quality, CLV, no-vig, workload,
  Path B, provider, and market-agreement slices.
- Draft a separate production re-entry canary only after one candidate reaches
  `ready_for_plan` with enough retained volume and no major negative slice.

Still closed:

- any FIRE re-entry promotion
- any LEAN promotion
- any model/lambda/threshold/staking change
- any provider, notification, lock, retention, or dashboard source-of-truth
  change

### Gate 13: Storage And Retention

**State:** Closed for deletion; open for dry-run evidence.

Raw `market_snapshots` are high volume. Compact movement rows exist, but raw
retention deletion still needs explicit Tyler approval.

Retention review can begin when:

- Storage guardrail shows material raw snapshot growth.
- Compact movement summaries exist for the candidate deletion window.
- A dry-run reports exact row counts and approximate size.
- The candidate rows no longer affect picks, locks, alerts, UI decisions, CLV,
  provider decisions, or model research.

Still closed:

- `ALLOW_MARKET_SNAPSHOT_DELETE=true`
- any `--execute` retention deletion
- Supabase spend-cap changes

2026-06-09 retention-readiness update:

- Added a read-only linked-CLI report:
  `npx supabase db query --linked --file scripts\supabase_retention_readiness.sql -o json`.
- Added `scripts/backfill_compact_market_movements_via_cli.py` to upsert
  compact summaries through linked Supabase CLI without requiring local
  service-role env vars. It defaults to dry-run and never deletes raw rows.
- Backfilled compact summaries for May 1-26: May 1-10 dry-run/execution covered
  `198,514` raw rows -> `5,603` compact rows; May 11-26 covered `297,922` raw
  rows -> `13,624` compact rows.
- Latest readiness report after backfill: database `1150 MB` (`14.04%` of 8 GB
  Pro allowance); `market_snapshots` about `785 MB`.
- 14-day window: `463,997` raw rows, estimated `517 MB`; bounded sample checked
  `10,000` rows / `1,045` groups, all compact-covered.
- 30-day window: `175,070` raw rows, estimated `195 MB`; bounded sample checked
  `10,000` rows / `756` groups, all compact-covered.
- `coverage_exact=false` and `eligible_for_execute=false` remain by design.
  This report is retention-readiness evidence only, not permission to run
  retention.

Next retention decision, if needed, is whether to build an exact coverage proof
or ask Tyler for a separate execute-retention approval. Execution remains closed
until that separate approval.

## What Counts As Soak

Soak is not waiting indefinitely. A soak has to name what is being observed and
what decision it can unlock.

Use this rule:

- If the gate has pass/fail checks and a next decision, it is a valid soak.
- If the gate only says "keep watching" without a decision, convert it into a
  checklist or close it as operational.
- If the evidence already supports only display or shadow value, mark that
  surface operational and keep the production promotion gate closed.

## Current Next Work

Recommended order:

1. Review Gate 12B first: decide whether the downside-only profit-rescue
   canary should run in `shadow` or `enforce`. Do not bundle that with provider
   strict mode or any lambda/staking/threshold change.
2. Keep Gate 7/Gate 8/Gate 9/Gate 12/Gate 12A/Gate 5 in observation after the
   2026-06-09 implementation push; do not promote provider,
   confidence-referee v2, market-agreement, positive bet-selection, or
   notification behavior from one refreshed report.
3. For Gate 13, keep deletion closed; the bounded compact-coverage sample is
   clear after the May 1-26 backfill, but execution needs exact proof or a
   separate Tyler approval.
4. Keep the provider-source strict cutover, new notification send classes,
   model changes, and retention deletion in soak until their specific gates
   pass.

## Briefing Contract

The BBE Operations Brief should report active gates in four groups:

1. System health: artifact path, Render runs, lock ledger, notification sender,
   storage.
2. Model health: confidence referee, Path B, Gate C/D/E/F, workload/no-vig.
3. Bet-selection health: market agreement, CLV, price/timing, live-market
   decision value.
4. Betting outcome: prior-day W/L, PnL, close losses, large misses, and whether
   they contradict or support the active gates.

Do not confuse a winning slate with a healthy system or a losing slate with a
broken system.

## Update Policy

Update this synthesis when:

- a gate opens, closes, or changes pass/fail criteria;
- Tyler approves an environment-variable promotion;
- a child plan becomes purely historical;
- a new recurring brief checklist is needed;
- storage, provider, notification, or model risk changes materially.

Update the child plan first when implementation details change. Update this
plan second so the gate matrix stays short and current.
