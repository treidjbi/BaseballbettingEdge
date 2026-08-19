# Bounded Season-Retention Audit

**Date:** 2026-08-18

**Status:** Approved 2026-08-18

**Scope:** Local, read-only replacement for the live verification step of the
Season Retention Foundation

## Purpose

Produce exact, season-long raw-to-compact retention evidence without repeating
the full-season PostgreSQL operation that exhausted temporary storage and then
timed out. The audit must preserve the evidence needed to explain season
results while keeping retention execution, database writes, production changes,
and deletion closed.

This specification changes how the existing Phase 1 audit is read and
assembled. The 2026-08-19 preserved-lineage amendment below narrows one anomaly
classification without weakening preservation: a historical cross-date row is
informational only when an exact compact group proves its source ID and time
range; any unpreserved cross-date row still blocks readiness.

## Business Outcome

At season end, BaseballBettingEdge should retain enough durable evidence to
answer:

- what the official model selected and how each pick performed;
- what Tyler actually bet, at which book, price, stake, and time;
- whether projection, opportunity, price, timing, market disagreement, data
  quality, or ordinary variance best explains an outcome;
- whether alerts, locks, provider coverage, or live-market evidence changed an
  actual decision;
- which research and shadow candidates worked prospectively; and
- which raw records can be removed because a smaller durable record proves the
  same season-review facts.

The objective is not minimum possible storage. It is a defensible evidence
floor: retain decision and outcome value, then remove redundant operational
volume only after exact proof and a separate approval.

## Trigger and Rejected Query Shape

The implemented monolithic SELECT-only audit was safe from mutation but not
viable on the hosted database:

1. The first attempt failed with PostgreSQL `53100` temporary-file exhaustion.
2. A narrowed, separately approved second attempt passed local preflight but
   failed with PostgreSQL `57014` statement timeout after about two minutes.
3. Neither attempt returned a usable envelope, generated a report, changed
   data, or authorized a retry.

The replacement must not materialize or sort the full candidate season in one
database statement. Raising the statement timeout, adding a database helper,
creating an index, or writing a summary table is outside this phase.

## Approaches Considered

### 1. Adaptive bounded historical chunks — selected

Read one provider across one, three, or at most seven historical slate dates,
checkpoint the aggregate result locally, and assemble the season envelope only
after the complete date/provider matrix is present.

This preserves exact reconciliation while placing a hard ceiling on each
database operation. It also gives the operator a resumable path without
automatic retries or database-side state.

### 2. One provider-date per query — safe fallback

This is the smallest database workload but would require more than one hundred
manual calls for the current season. The selected design starts here as a
canary and returns here automatically when a larger successful unit becomes
slow.

### 3. Database summary table, helper function, or new index — rejected here

Database-side materialization could be faster over time, but it would require a
migration or write path before the evidence contract is proven. That mixes
audit verification with schema/storage decisions and is not authorized.

## Scope Boundaries

### Candidate historical scope

The audit uses Phoenix calendar dates and includes:

- `start_date`: fixed at `2026-04-28`, the clean evaluation-regime boundary;
- `end_date`: `as_of_date - raw_retention_days`, inclusive;
- `raw_retention_days`: fixed at `30` for this verification design; and
- `providers`: `boltodds`, `propline`, `the_odds`, and `therundown`.

Every calendar date/provider combination in this scope is expected, including
combinations with zero rows. Zero rows are evidence only when the query returns
the explicit zero record; absence of a record is incomplete coverage.

### Protected recent scope

Dates after `end_date` are recorded in `protected_scope` and are never read by
the exact raw-to-compact chunk queries. Current provider freshness is checked
separately through narrow indexed runtime-boundary reads.

### Explicit non-goals

This design does not:

- write, update, upsert, backfill, delete, truncate, vacuum, reindex, or migrate
  Supabase data;
- generate executable retention or cleanup SQL;
- change a retention rule, spend cap, provider flag, provider order, polling
  cadence, source of truth, notification, lock, dashboard, model, threshold,
  formula, staking, or artifact;
- query a provider API;
- raise a database timeout or add a database object;
- change `scripts/retire_market_snapshots.py` or
  `scripts/backfill_compact_market_movements_via_cli.py`;
- push, deploy, schedule, or activate the audit; or
- make `ready_for_retention_review` equivalent to deletion approval.

## Approved Architecture

### Components

The future implementation is limited to:

- `scripts/retention_bounded_sql.py` — pure, deterministic SQL builder with
  ISO-date validation and an exact provider allowlist;
- `scripts/bounded_retention_audit.py` — local CLI orchestration, cadence,
  subprocess handling, atomic checkpoints, resume validation, and final
  assembly;
- `scripts/build_season_retention_readiness.py` — extend the existing reporter
  to validate and consume audit envelope version 2;
- `tests/test_retention_bounded_sql.py` — static query-shape and input tests;
- `tests/test_bounded_retention_audit.py` — cadence, checkpoint, subprocess,
  assembly, and fail-closed tests; and
- focused additions to `tests/test_build_season_retention_readiness.py` for the
  version 2 contract.

No migration, dependency, service, scheduled job, dashboard asset, or
production artifact is added.

### Data flow

1. The operator supplies `as_of_date` and, for live use, explicitly authorizes
   a bounded validation invocation.
2. The local CLI calculates the candidate and protected scopes.
3. It reads and validates existing checkpoints for the exact query hash and
   scope.
4. It selects the next missing provider/date chunk, beginning with a one-date
   canary.
5. It renders one validated SELECT-only statement and runs it serially through
   `npx supabase db query --linked -o json`.
6. It validates the returned JSON and writes one atomic local checkpoint.
7. It stops by default. A separately explicit multi-chunk invocation may
   continue within the cadence and chunk-count caps.
8. After all expected chunks exist, the assembler validates the complete
   matrix, joins separately bounded anomaly and runtime-boundary aggregates,
   and creates one sanitized version 2 envelope.
9. Only a complete, reconciled envelope may be passed to the existing
   readiness and BoltOdds closure reporters.

Generated checkpoints and reports remain under the already ignored
`analytics/output/retention/` directory. Checkpoints are local working state,
not durable season evidence or production artifacts. A small sanitized final
manifest or report may be proposed for durable storage in a separate review.

## Database Read Contract

### Indexed chunk boundary

Each chunk covers one provider and an inclusive range of one, three, or seven
slate dates. The query must:

1. select target `market_provider_runs` by the indexed `slate_date` boundary
   and exact provider;
2. join `market_snapshots` through indexed `run_id` access;
3. read `compact_market_line_movements` through its slate-date/provider/book/
   normalized-player boundary; and
4. normalize grouping fields only after the indexed date/run boundary is
   established.

### Preserved historical cross-date lineage

The audit must keep the original `slate_date_mismatch_rows` count visible and
split it into two exhaustive counters:

- `preserved_slate_date_mismatch_rows`; and
- `unpreserved_slate_date_mismatch_rows`.

Their sum must equal `slate_date_mismatch_rows` in every chunk and in the final
provider aggregate. A cross-date row is preserved only when a compact row keyed
to the provider run's original `run_slate_date` and normalized market group:

1. contains the raw snapshot ID in `source_snapshot_ids`; and
2. covers the raw `observed_at` inside its `first_seen_at` / `last_seen_at`
   bounds.

The total and preserved counters are informational. A nonzero unpreserved
counter is a hard completeness blocker. Missing run linkage, missing group
keys, provider/run disagreement, unknown providers, and all compact-coverage
mismatches remain hard blockers. Version 1 behavior is unchanged.

Index-driving predicates must not wrap date, provider, or run identifiers in
`lower`, `trim`, casts, or other functions. The SQL may normalize fields in a
bounded downstream projection.

### Exact grouping contract

The canonical movement key remains:

`slate_date, provider, book_key, normalized_player_name, market_key, side, line`

Within a chunk, first, last, and movement evidence use one ascending ordering
of `observed_at, id`. The query must not add a reverse-order full-partition
sort. It projects only required scalar fields and `pg_column_size(ms)`; `ms.*`,
source payloads, authorization values, and individual raw rows are prohibited
from output.

### Per-partition output

The query emits exactly one aggregate row for every requested provider/date,
including explicit zero rows. Each row includes:

- raw snapshot rows and logical bytes;
- raw movement groups and compact movement groups;
- exact, missing, unexpected, mismatched, and duplicate group counts;
- mismatch subtypes for first/last timestamps, first/last/min/max odds,
  movement count, and snapshot count;
- earliest and latest raw and compact timestamps;
- invalid-key or normalization counts; and
- a derived `coverage_exact` flag.

`coverage_exact` is never accepted as an independent assertion. The assembler
recomputes it from the emitted equations and blocker counts.

### Bounded anomaly reads

Rows that cannot be attributed safely through the target-run path must remain
visible. A separate SELECT-only anomaly query may inspect the same bounded date
window for:

- missing `run_id`;
- orphaned `run_id`;
- run/snapshot provider mismatch;
- run/snapshot slate-date mismatch; and
- an unknown provider.

The anomaly query returns aggregate counts only. It must use a bounded
`observed_at` interval derived from the chunk dates and may not scan the full
season. Any non-zero unattributed anomaly blocks readiness.

### Runtime-boundary reads

Current/latest evidence is intentionally separate from the historical
candidate scope. Narrow indexed reads report, by provider:

- latest provider run and snapshot;
- latest heartbeat and message timestamp where applicable;
- latest candidate-scope run and snapshot; and
- retired BoltOdds maximum run, snapshot, heartbeat, and message boundaries.

These rows do not change candidate totals. BoltOdds evidence after
`2026-06-17T17:22:29Z` is an operational exception and blocks its closure.

## Cadence and Load Guardrails

The local runner enforces all of these rules:

- first live unit: one provider and one historical date;
- adaptive ladder: `1 -> 3 -> 7` dates;
- hard maximum: seven dates per query;
- execution: strictly serial, never parallel;
- cooldown: at least 30 seconds between successful queries;
- automatic retries: zero;
- default invocation cap: one chunk;
- hard invocation cap: five chunks; and
- multi-chunk execution: requires an explicit CLI flag and separate operator
  approval for that live invocation.

A structurally valid chunk completing in 30 seconds or less may promote the
next missing chunk by one ladder rung. A valid chunk taking more than 30
seconds is saved, then the invocation stops; the next invocation returns to the
previous smaller rung. No success may jump directly from one to seven dates.

The runner stops immediately, writes no checkpoint for the failed unit, and
does not retry when it sees:

- a non-zero subprocess exit;
- a timeout;
- empty stdout or malformed/truncated JSON;
- PostgreSQL `53100` or `57014`;
- pooler `ECIRCUITBREAKER`;
- an authentication retry/error; or
- any validation or aggregate contradiction.

The operator must review the failure before another invocation. The runner may
resume only from prior validated checkpoints.

## Checkpoint and Resume Contract

Each successful chunk produces one atomic JSON checkpoint. The runner writes a
temporary file in the output directory, flushes and closes it, then replaces
the target path. An interrupted or malformed temporary file is never treated
as completed work.

Every checkpoint records:

- `audit_version`;
- requested provider and inclusive date range;
- `as_of_date`, candidate cutoff, and protected-window metadata;
- exact ordered provider allowlist;
- SQL/query SHA-256;
- runner version and Supabase CLI version;
- start, finish, and elapsed seconds;
- returned partition count and validation result;
- coverage aggregates and anomaly aggregates; and
- a sanitized error state, which must be null for a resumable checkpoint.

Resume skips a chunk only when the file parses and all scope, version, hash,
cutoff, provider, date, partition-count, and aggregate checks match the current
invocation. A mismatch invalidates the checkpoint and fails closed; it does not
silently rerun or merge mixed contracts.

The runner sanitizes stderr and exceptions before persistence or display. It
must never print or store database passwords, service-role keys, access tokens,
authorization headers, connection strings, project references, or provider
keys.

## Version 2 Audit Envelope

The assembler produces this top-level contract:

- `audit_version: 2`;
- `audit_generated_at`;
- `as_of_date` and `timezone: America/Phoenix`;
- `candidate_scope` with start, inclusive end, retention days, and providers;
- `protected_scope` with first protected date and reason;
- `execution` with query hash, runner/CLI versions, cadence contract, expected
  and completed chunk ranges, and `complete`;
- `coverage` with exactly one record per expected provider/date;
- `source_anomalies` limited to the candidate scope;
- `candidate_runtime` whose provider totals equal the coverage candidate scope;
- `runtime_boundary` for current/latest and retired-provider checks;
- the existing `season_evidence` and `pins` inputs;
- `complete`;
- `retention_execution_closed: true`; and
- `deletion_approved: false`.

`as_of_date` is current operator context. The historical candidate cutoff is a
separate immutable field. The reporter must not reject a valid historical
candidate matrix merely because current runtime evidence falls after the
cutoff; it validates current freshness through `runtime_boundary` instead.

Version 2 is an explicit contract, not an imitation of version 1. The reporter
may continue accepting validated version 1 fixtures for regression coverage,
but live bounded output must identify itself as version 2.

## Final Assembly and Completeness Rules

The assembler may emit a final envelope only when all of these are true:

1. Every expected date/provider combination is present exactly once.
2. Chunk ranges have no gaps or overlaps.
3. Every checkpoint has one query hash, provider allowlist, cutoff, timezone,
   runner version, and CLI contract.
4. All partition count equations are internally consistent.
5. Raw row and logical-byte totals reconcile exactly between coverage and
   `candidate_runtime`.
6. Missing, unexpected, mismatch, duplicate, and anomaly totals reconcile to
   their subtypes.
7. `coverage_exact` recomputes from blocker counts for every partition.
8. No provider/date mismatch or unattributed anomaly remains.
9. Phoenix `as_of_date` and runtime-boundary freshness are valid.
10. BoltOdds has no run, snapshot, heartbeat, or message after its documented
    suspension boundary.
11. Gate C season evidence covers the applicable audited dates.
12. Every positive decision-linked class has its required outcome/timing
    evidence and preserved pin.

If any check fails, the tool writes no complete readiness report. It may write
a sanitized local diagnostic manifest marked `complete: false`,
`retention_execution_closed: true`, and `deletion_approved: false`. The final
operator posture remains `blocked/no-go`.

## Durable Season Evidence Contract

These evidence classes remain full-season or permanent:

- official picks, grades, results, history, parameters, and model metadata;
- the Gate C compact outcome dataset and manifests;
- accepted bets and append-only corrections;
- official opening, checkpoint, pre-close, close, CLV, and compact movement
  evidence;
- sent notifications and outcome-linked alert evidence;
- consumed operational locks and their source-artifact links;
- frozen Alt V2 decisions and genuine prospective results;
- provider provenance, request usage, coverage, reliability, and cost summaries;
- incident, accepted-bet, notification, unusual-loss, provider-transition, and
  model-review pins; and
- a sanitized aggregate BoltOdds closure record.

Raw snapshots, repeated operational rows, and raw webhook payloads are only
cleanup candidates after their durable records exist and the exact applicable
partition reconciles. The audit reports candidates; it never executes cleanup.

## Testing Contract

### Static SQL tests

Tests prove that every generated statement:

- is one SELECT-only statement;
- contains explicit bounded start/end predicates;
- reaches snapshots through target runs and `run_id`;
- reaches compact rows through bounded date/provider predicates;
- uses only one ascending within-group ordering;
- contains no full-season materialization, reverse full-partition sort, `ms.*`,
  or source payload output; and
- contains no mutation, DDL, maintenance, or executable cleanup token.

### Chunk and envelope fixtures

Fixtures cover:

- one-, three-, and seven-date chunks;
- explicit zero-row provider/dates;
- ordinary active providers and retired BoltOdds;
- missing and orphaned run IDs;
- provider and slate-date mismatches;
- duplicate, missing, unexpected, and mismatched compact groups;
- missing partitions, overlaps, and gaps;
- mixed query hashes, scopes, cutoffs, versions, and CLI contracts;
- malformed, empty, and truncated JSON;
- stale audit/runtime dates; and
- every aggregate-count contradiction.

### Cadence and subprocess tests

Tests use mocked subprocesses and clocks to prove:

- the first live unit is a one-date canary;
- promotion happens only after a valid result at or below 30 seconds;
- seven dates is a hard maximum;
- a successful slow chunk is saved and stops/de-escalates;
- the 30-second cooldown is enforced;
- the default cap is one and hard cap is five chunks;
- resume skips only exact validated checkpoints;
- every listed error stops with no retry;
- dates/providers are validated before shell construction;
- argument injection cannot alter the command; and
- secrets and raw envelopes are not printed.

### Reporter and regression tests

Version 2 tests prove full-matrix validation, current-versus-candidate date
separation, runtime equality, BoltOdds closure, decision linkage, pins,
redaction, exit codes, and closed deletion posture. The complete repository
test suite must pass on the exact implementation commit.

## Live Validation Gate

Implementation does not authorize live validation. After code review and a
separate Tyler approval, validation proceeds in this order:

1. one old, low-volume provider/date;
2. one high-volume retired-BoltOdds provider/date;
3. review of query plans, elapsed time, aggregate integrity, and checkpoint
   contents; and
4. only after another explicit approval, a capped multi-chunk invocation.

No step may backfill, delete, vacuum, change a timeout, create a database
object, or activate retention.

## Success Criteria

The bounded audit design is implemented successfully only when:

1. all local static, fixture, cadence, reporter, and full-repository tests pass;
2. the runner cannot issue writes, parallel queries, automatic retries, or
   unbounded reads;
3. the final assembler rejects every incomplete or mixed-contract matrix;
4. approved live canaries complete without `53100`, `57014`, pooler, or auth
   failures;
5. the completed version 2 report reproduces provider/date coverage and known
   blockers without exposing raw payloads or secrets; and
6. all production, provider, model, notification, lock, UI, source-of-truth,
   retention, deletion, push, and deployment gates remain closed.

## Decisions Reserved for Later Approval

After the written specification and a future implementation are reviewed,
Tyler must still separately decide whether to approve:

1. the first live one-date canary;
2. the retired-BoltOdds stress canary;
3. any capped multi-chunk historical audit;
4. Phase 2 exact durable-evidence finalization or backfill;
5. precise table- and provider-specific retention windows;
6. a Phase 3 partition-specific deletion proposal; and
7. any storage-reclamation operation after deletion.
