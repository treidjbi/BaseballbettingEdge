# Daily Active-Provider Compaction Finalizer Design

**Date:** 2026-08-26
**Status:** Approved by Tyler on 2026-08-26; implementation plan written,
execution not started
**Scope:** A separate low-frequency Render cron and its local implementation;
no production creation, activation, database write, or deletion is authorized
by this document

## Decision

Add a new isolated daily job, `bbe-market-compaction-finalizer`, for complete
exact compaction of the prior Phoenix slate. The job will initially run in
read-only preview mode. It will not share the frequent `bbe-live-layer`
execution path and will not raise that path's 20,000-row safety ceiling.

The finalizer will consider exactly two active providers in fixed order:

1. `propline`
2. `therundown`

It will derive yesterday's Phoenix date internally, preflight both provider
partitions, and emit aggregate proof only. Three consecutive clean natural
preview runs are required before proposing a separately approved compact-only
execute mode.

This design does not authorize the known historical active-provider backlog,
raw-row deletion, webhook deletion, retention activation, vacuum/reclamation,
or any production behavior change outside compact-market maintenance.

## Problem And Current Evidence

The frequent live compactor is deliberately limited to 20 pages of 1,000 raw
snapshots. Its new fail-closed guard correctly refuses to publish a truncated
prefix when all 20 pages are full. The first natural production exercise of
that guard proved two things:

- no partial compact publication occurred; and
- compaction can exceed the live job's safe read budget while unrelated Alt
  capture continues normally after the approved failure isolation.

The completed active-provider audit found `105` incomplete historical
provider/date partitions representing `34,861` aggregate compact upserts:

- PropLine: `63` partitions and `15,387` upserts;
- TheRundown: `42` partitions and `19,474` upserts.

The largest observed exact partition was about `55,232` raw rows. The existing
exact partition reader has a 75-page ceiling, deterministic keyset paging, and
source-state binding suitable for a slower bounded job. Active-provider write
execution remains intentionally blocked in that historical repair utility.

Current database evidence also shows why this is worth solving without
rushing deletion: `market_snapshots` is the dominant storage table, while the
compact representation is materially smaller. Complete daily compaction is a
prerequisite to a future retention proposal, not deletion authority by itself.

## Goals

1. Complete an exact read of yesterday's PropLine and TheRundown partitions
   once per day without burdening the 10-minute live layer.
2. Prove whether each rebuilt compact partition exactly matches current
   compact state and identify the bounded upserts that would be needed.
3. Fail closed on truncation, source drift, incomplete evidence, unexpected
   compact rows, or deadline exhaustion.
4. Establish an observable three-day preview soak before any write-mode
   discussion.
5. Make a future compact-only execution idempotent and recoverable without
   opening historical repair or retention deletion.

## Non-Goals

The finalizer will not:

- change the official artifact source, provider order, provider flags,
  polling cadence, provider usage accounting, or source-of-truth rules;
- change model inputs, formulas, thresholds, verdicts, staking, Alt selection,
  accepted bets, grading, history, locks, notifications, or UI behavior;
- process BoltOdds or The Odds API;
- accept an arbitrary provider or date from its scheduled command;
- repair the known `105` historical partitions automatically;
- delete raw snapshots, webhook deliveries, or any other row;
- activate retention, vacuum tables, or claim reclaimed storage;
- create a new notification class; or
- write credentials, raw payloads, source IDs, players, books, or market
  records to logs.

## Architecture

### Isolated Render cron

The new service is a separate Render cron named
`bbe-market-compaction-finalizer`. It does not run inside
`bbe-live-layer`, and a failure cannot suppress live-market state, Alt V2,
locks, or notifications.

The proposed schedule is `12:47 UTC` daily, which is `5:47 AM` in
America/Phoenix. This places the finalizer after the expected 3:17 AM grading
cycle and before the 6:17 AM full pipeline run. Scheduler delay is acceptable;
the target is derived from Phoenix calendar time when the process starts.

The job has an eight-minute wall-clock budget. Once the deadline is reached,
it performs no new write and exits nonzero. The daily cadence and 75-page
ceiling bound a preview source read to 75,000 rows per provider, or 150,000
rows across the two providers. A future execute run may perform the required
second source-state read, for a maximum of 300,000 raw rows plus compact-state
reads, while remaining subject to the same deadline.

`render.yaml` remains unchanged with `services: []` so Blueprint activity
cannot recreate the retired BoltOdds worker. A future approved deployment will
create this cron directly in Render and will reuse only the minimum existing
Supabase connection settings needed for the finalizer. Creation, command
changes, and environment changes remain separate production approvals.

### Date and provider boundary

The production entrypoint computes:

`target_slate_date = Phoenix calendar date at process start - 1 day`

The scheduled entrypoint exposes no arbitrary `--date` or `--provider`
argument. Clock injection is allowed only as an internal test seam. The
provider tuple is a code constant in the order `propline`, then `therundown`.

The finalizer treats a missing provider run, zero raw rows, zero rebuilt compact
groups, an out-of-window source, or a cross-date relationship not already
accepted by the exact partition contract as incomplete evidence. It emits an
aggregate failure and exits nonzero. Such a run does not count toward the
three-run soak. A legitimate no-slate day can be reviewed operationally but is
not silently converted into a clean compaction proof.

### Exact partition engine

The existing deterministic exact provider/date reader remains the foundation.
Its reusable preview primitive will be made public so callers do not depend on
a private implementation detail. That primitive must preserve:

- `(observed_at, id)` keyset paging;
- the 75-page, 1,000-row-per-page ceiling;
- complete source-ID validation and duplicate conflict checks;
- the reviewed Phoenix-date and prior-day carryover rules;
- deterministic compact rebuilding;
- exact comparison of rebuilt versus stored compact groups; and
- a source-state fingerprint that binds a later write to the exact read.

Making the preview primitive reusable must not widen the historical repair
utility's execution allowlist. PropLine and TheRundown remain blocked from that
utility's write path.

### Daily orchestrator

A new script, `scripts/run_daily_active_provider_compaction_finalizer.py`,
owns date selection, provider ordering, preflight coordination, mode gating,
deadline enforcement, and the final aggregate result.

Its default and deployed initial mode is `preview`. A future execute mode must
require both:

- an explicit execute command; and
- a finalizer-specific environment gate with the exact approved value.

Changing either production control requires Tyler's separate approval. The
orchestrator does not call the historical repair executor and does not inherit
its date allowlist.

## Data Flow

### Preview mode

1. Resolve current Phoenix date and derive D-1.
2. Exact-read and rebuild the PropLine D-1 partition.
3. Exact-read and rebuild the TheRundown D-1 partition.
4. Verify both complete before considering the overall preflight clean.
5. Compare each rebuilt partition with current compact rows.
6. Emit one aggregate finalizer summary and exit success only if both source
   reads and rebuilds are complete, deterministic, and within all limits.

Missing or mismatched stored compact groups are the expected `would-upsert`
output of a successful preview; they do not make the read proof fail. An
unexpected compact-only group does fail because the finalizer cannot safely
explain or overwrite it.

Preview mode performs no upsert, provider-usage write, audit-table write,
deletion, or other mutation. The summary contains only:

- target slate date and mode;
- provider status in fixed order;
- raw-row, rebuilt-group, exact-match, missing, mismatched, unexpected, and
  would-upsert counts;
- first and last aggregate source timestamps;
- source-state fingerprints;
- elapsed time and deadline status; and
- `database_write_performed=false` and `deletion_performed=false`.

No source IDs or raw market dimensions appear in stdout, stderr, or exception
messages.

### Future execute mode

Execute mode is designed now so preview evidence tests the same logic, but it
is not activated by this design.

1. Preflight both providers completely before the first upsert.
2. If either preflight fails, perform zero writes and exit nonzero.
3. Immediately before each provider write, re-read its exact source state and
   require the fingerprint to match its preflight fingerprint.
4. If stored compact state is already exact, record an idempotent no-op.
5. Otherwise, upsert only the rebuilt compact rows for that provider/date.
6. Use one write attempt. Do not automatically replay an ambiguous request.
7. Re-read compact state and require an exact post-write match before marking
   that provider successful.
8. Continue to the second provider only after the first provider's exact
   post-state is proven.

The two providers are not presented as one database transaction. If PropLine
succeeds and TheRundown fails, the job exits nonzero and reports that bounded
partial state. A retry is safe: PropLine becomes an exact no-op and TheRundown
is attempted only after a fresh complete preflight. An ambiguous write counts
as successful only when the exact post-state proves it.

Execute mode still never deletes raw rows and never writes provider usage.

## Failure And Recovery Contract

The finalizer exits nonzero on any of these conditions:

- the 75-page ceiling is exhausted with another full page possible;
- a source page is incomplete, non-monotonic, duplicated inconsistently, or
  otherwise violates the exact reader contract;
- a required provider run, raw row set, or rebuilt compact set is missing;
- source evidence falls outside the bounded provider/date contract;
- an unexpected compact-only group exists;
- a source-state fingerprint changes between preflight and write;
- a compact upsert fails or its exact post-write verification fails;
- the wall-clock deadline is reached; or
- either provider fails, even if the other provider is exact.

There are no automatic retries. Render's failure state and aggregate logs are
the operational evidence. The BBE Operations Brief may report the outcome,
but the finalizer does not send a push notification or create a notification
event.

Recovery is an ordinary rerun after the cause is understood. Idempotent exact
comparisons prevent an already-complete partition from being rewritten.

## Historical Backlog Boundary

The daily finalizer processes only D-1. It does not iterate over the existing
105-partition manifest and does not add active providers to the historical
repair utility's hard-coded execution allowlist.

After the daily preview and approved execute path are proven, historical work
requires a separate design and approval. That later proposal must use the
reviewed aggregate manifest, bind each batch to exact source fingerprints,
limit batch size, verify every post-state, and stop on the first contradiction.
It must not be smuggled into routine daily execution.

## Retention And Deletion Boundary

Complete compact coverage is necessary but insufficient for deletion. The
finalizer never deletes. A later raw-snapshot retention proposal remains
closed until all of these gates pass with fresh evidence:

1. exact active-provider compact coverage, including the historical backlog;
2. preservation of the season-evaluation evidence and pinned exceptions;
3. a current completed backup plus tested recovery/export proof;
4. a bounded retention dry run showing the exact rows and dates eligible;
5. no source-of-truth, lock, notification, UI, accepted-bet, grading, or
   research dependency on the proposed raw rows; and
6. Tyler's separate approval of the exact deletion scope.

Only then may a retained raw window, expected to be evaluated in the 14-30 day
range, be proposed. This design does not select the final window.

Webhook inbox cleanup, table vacuuming, and physical storage reclamation remain
separate gates even after a future raw-snapshot deletion.

## Security, Cost, And Operational Footprint

- The service receives only the minimum Supabase credentials required through
  service-scoped Render environment settings; no database password, service
  key, provider key, or token is printed.
- Logs contain aggregate counts, timestamps, status values, and hashes only.
- The MVP creates no new Supabase table and no persistent audit payload.
- Natural Render logs plus the daily operations brief are sufficient for the
  three-run preview gate.
- Before implementation or deployment, current Supabase client/CLI behavior
  and relevant platform changes must be checked against official guidance.
- [Render documents](https://render.com/docs/cronjobs) a $1 monthly minimum
  per cron job plus active compute usage. The expected footprint is one
  bounded run per day, and the final production proposal must restate the
  current cost before creation.

## Files In Scope For A Later Implementation

- Create: `scripts/run_daily_active_provider_compaction_finalizer.py`
- Create: `tests/test_daily_active_provider_compaction_finalizer.py`
- Modify: `scripts/repair_compact_market_snapshot_partition.py`
- Modify: `tests/test_repair_compact_market_snapshot_partition.py`
- Update after local verification:
  `docs/superpowers/plans/2026-08-25-active-provider-compaction-finalizer.md`
- Update after a meaningful lane change: `docs/current-state.md`
- Update after a production posture change: BBE Operations Brief automation
  memory

No migration, dependency, dashboard file, Netlify function, provider adapter,
model file, notification sender, lock consumer, retention executor, or
`render.yaml` change is in scope.

## Testing Strategy

Implementation will follow red-green TDD. Tests must prove:

- Phoenix D-1 date selection across UTC date boundaries;
- fixed provider scope and ordering with no arbitrary production date/provider
  override;
- preview as the default and zero writes in every preview outcome;
- both providers are preflighted before any execute-mode upsert;
- exact partitions become idempotent no-ops;
- incomplete reads, page-ceiling exhaustion, missing evidence, unexpected
  compact rows, source drift, and deadline exhaustion fail closed;
- execute mode requires both independent gates;
- one write attempt and exact post-write verification;
- safe recovery when provider one is exact and provider two previously failed;
- no provider-usage or deletion write;
- no raw dimensions, IDs, or credentials in logs and errors;
- existing historical execution allowlists remain unchanged;
- existing live compactor behavior and 20,000-row ceiling remain unchanged;
  and
- focused and complete repository suites pass on the exact implementation
  commit.

Tests use fakes and an injected clock. They do not connect to Supabase or
Render. Any later live preview is a separate read-only deployment gate.

## Rollout And Promotion Gates

1. Approve this written design.
2. Create and approve a detailed TDD implementation plan.
3. Implement locally on an isolated branch and complete code review and full
   verification.
4. Separately approve merge of the behavior-disabled code.
5. Separately approve direct Render cron creation in preview mode only.
6. Observe three consecutive clean natural D-1 previews. Each must cover both
   providers and produce no write.
7. Review read volume, runtime, failure quality, and current Render cost.
8. Only then draft a separate compact-only execute activation proposal.
9. After daily execute soak, address the historical backlog under its own
   bounded plan.
10. Consider retention only after the independent backup, recovery, season-
    evidence, dry-run, and deletion-approval gates pass.

Progress at any gate does not authorize a later gate.

## Acceptance Criteria

The design is implemented successfully only when:

- a separate daily service targets exactly the prior Phoenix slate;
- only PropLine and TheRundown are considered, in fixed order;
- the live layer keeps its existing bound and remains operationally isolated;
- preview mode proves complete exact reads while performing no database write;
- all ambiguous, incomplete, truncated, stale, drifted, or unexpected states
  fail closed;
- three clean natural previews are recorded before execute is proposed;
- execute remains compact-only, idempotent, source-bound, and separately
  approved;
- historical backlog repair and every deletion remain closed; and
- no model, provider, artifact, Alt, notification, lock, UI, history, grading,
  accepted-bet, or source-of-truth behavior changes.
