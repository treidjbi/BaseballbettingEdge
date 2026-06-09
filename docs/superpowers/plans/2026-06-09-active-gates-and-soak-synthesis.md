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

**State:** Open for baseline durable evidence; needs refresh/backfill for new
runtime labels.

The durable Gate C artifact is the preferred full-corpus research input, but
the current committed rows do not yet carry all live canary labels needed for
the newest reads.

Next implementation gate:

- Backfill or refresh Gate C rows with:
  - `batter_handedness_mode`
  - `lineup_split_source`
  - `lineup_real_split_count`
  - `lineup_path_a_fallback_count`
  - confidence-referee mode, relationship, would-cap, and applied-cap fields
  - no-vig EV labels
  - workload sensitivity labels
  - market-agreement labels when exported evidence exists

Pass criteria:

- Zero duplicate dataset keys.
- Clean reconciliation to `picks_history`.
- No hindsight-only fields used as runtime-safe labels.
- Current-regime rows are clearly separated from older context.

### Gate 8: Workload/No-Vig Task 5

**State:** Next docs-approved implementation after Gate C refresh/backfill.

Task 5 from `2026-06-08-workload-no-vig-k-projection-ev-synthesis.md` should
be done after the Gate C row refresh carries the fields listed in Gate 7.

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

**State:** Open as shadow tracking; promotion behavior closed.

The market agreement tracker is implemented and should help interpret whether
live market movement confirmed or contradicted the model side.

Sample gates:

- Overall tracker read stays `watch_only` until at least 75 graded rows have
  movement-backed evidence.
- Candidate buckets stay `watch_only` until at least 50 graded rows exist.

Still closed:

- auto-promoting LEANs
- overriding confidence-referee caps
- changing model, staking, provider, notification, or dashboard behavior

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
- Latest report: database `1127 MB` (`13.76%` of 8 GB Pro allowance);
  `market_snapshots` about `785 MB`.
- 14-day window: `463,345` raw rows, estimated `516 MB`; bounded provider-
  indexed sample checked `10,000` rows / `1,043` groups, with `490` compact-
  covered groups and `553` uncovered groups.
- 30-day window: `169,323` raw rows, estimated `189 MB`; bounded sample checked
  `10,000` rows / `733` groups, with `0` compact-covered groups because older
  raw rows predate current compact coverage.
- `coverage_exact=false` and `eligible_for_execute=false` by design. This
  report is retention-readiness evidence only, not permission to run retention.

Next retention work is compact/backfill coverage for older May raw windows, then
rerun the readiness report. Execution remains a separate Tyler approval.

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

1. Keep Gate 7/Gate 8/Gate 5 in observation after the 2026-06-09 implementation
   push; do not promote model, provider, or notification behavior from one
   refreshed report.
2. For Gate 13, compact/backfill coverage for older May raw market windows, then
   rerun `scripts\supabase_retention_readiness.sql`.
3. Keep the provider-source strict cutover, new notification send classes,
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
