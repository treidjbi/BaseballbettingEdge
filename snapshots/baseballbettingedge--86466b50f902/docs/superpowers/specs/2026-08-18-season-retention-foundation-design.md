# Season Retention Foundation

**Date:** 2026-08-18

**Status:** Approved 2026-08-18

**Scope:** Phase 1 only — local, read-only evidence tooling and retention-readiness reports

## Purpose

Build a defensible end-of-season retention foundation that preserves the evidence needed to explain what worked, what did not, and why, while identifying raw operational data that can eventually be removed safely.

This phase does not delete, backfill, migrate, schedule, or change production behavior. It establishes the proof required before those actions can be proposed separately.

## Business Outcome

At the end of the season, BaseballBettingEdge should retain enough durable evidence to answer:

- Which official picks, accepted bets, model lanes, and market contexts were profitable?
- Did a miss look like projection error, price/timing error, opportunity/leash error, market disagreement, data quality, or ordinary variance?
- Did provider coverage, alerts, locks, or live-market evidence change an actual decision?
- Can high-volume raw data be reproduced by smaller compact or outcome-linked records before it is removed?

The immediate capacity objective is to stop database growth from becoming an emergency without sacrificing season-review evidence.

## Current Evidence

The 2026-08-18 read-only sizing audit found:

- The database is approximately 4,609 MB, or 56.26% of the 8 GB included allowance.
- `market_snapshots` is approximately 3,238 MB and about 70% of the database, with roughly 3.866 million rows.
- Approximately 3.054 million snapshot rows are older than 14 days; approximately 2.182 million are older than 30 days.
- Retired BoltOdds accounts for 611,972 snapshot rows, all outside the active runtime period.
- `propline_webhook_deliveries` is approximately 365 MB; much of its row size is raw payload data.
- Index and table inspection found some reusable space, but ordinary bloat is not the primary capacity driver. Retained raw evidence is.

Existing compaction is not exact enough to authorize deletion:

| Provider slice | Raw groups | Exact groups | Missing compact groups | Mismatched groups |
|---|---:|---:|---:|---:|
| BoltOdds, all retained dates | 26,188 | 23,900 | 345 | 1,943 |
| PropLine, older than 30 days | 16,842 | 5,321 | 304 | 11,217 |
| TheRundown, older than 30 days | 16,909 | 1,654 | 7,425 | 7,830 |

The existing readiness evidence correctly reports `coverage_exact=false` and `eligible_for_execute=false`. That remains the controlling deletion posture.

## Approved Architecture

The approved long-term architecture is a post-slate exact finalizer:

1. Keep intraday production behavior unchanged.
2. After a slate is complete, rebuild compact movement evidence with exact server-side aggregation.
3. Materialize the existing Gate C checkpoint, pre-close, close, and CLV fields needed for season analysis.
4. Reconcile raw and durable evidence exactly by provider and slate date.
5. Mark only fully proven provider-date partitions as retention-ready.

This design is divided into three independently approved phases because proof generation, production materialization, and deletion have different risks.

### Phase 1 — Read-only retention foundation

This specification controls Phase 1:

- exact raw-to-compact reconciliation queries;
- provider/date retention-readiness reporting;
- a BoltOdds retirement closure package generator;
- fixture-driven tests and a documented evidence contract;
- local generated outputs for review.

Phase 1 may read the linked Supabase database through the CLI. It must not issue any database write, mutation, DDL, vacuum, backfill, retention, or provider API request.

### Phase 2 — Post-slate evidence finalization

Phase 2 requires a new written specification and Tyler approval. It would cover:

- exact post-slate compaction/backfill;
- final checkpoint, closing-line, and CLV materialization;
- schema or migration needs;
- production scheduling and observability;
- historical backfill boundaries.

Phase 2 would still not authorize raw-data deletion.

### Phase 3 — Retention activation and deletion

Phase 3 requires a separate, date- and table-specific approval after Phase 2 evidence is verified. It would cover:

- the exact eligible partitions and estimated recovery;
- an export or recovery artifact where required;
- dry-run counts repeated immediately before execution;
- bounded deletion statements;
- post-delete reconciliation and storage reclamation;
- rollback limitations and incident handling.

## Phase 1 Components

### Planned file layout

Phase 1 will add only these implementation files:

- `scripts/supabase_retention_exact_coverage.sql` — read-only inventory and exact raw-to-compact reconciliation;
- `scripts/build_season_retention_readiness.py` — pure-standard-library CLI with `readiness` and `boltodds-closure` report modes;
- `tests/test_build_season_retention_readiness.py` — fixture-driven decision, validation, redaction, and rendering tests.

Generated reports will default to `analytics/output/retention/`, which is local analytical output and is not a dashboard or production artifact source. The implementation will not add generated live database extracts to Git. A reviewed, sanitized BoltOdds closure package may be proposed for durable storage in a later commit, but that is not automatic Phase 1 behavior.

### 1. Read-only exact coverage query

A dedicated SQL file will calculate raw-versus-compact coverage by provider and baseball slate date. It will use server-side aggregation so results are not truncated by REST pagination limits.

The canonical movement key will match the existing server-side backfill contract exactly:

`slate_date, provider, book_key, normalized_player_name, market_key, side, line`

Ordering for first/last values will be `observed_at, id`, ascending for first values and descending for last values. Provider, book, side, and market normalization will match `scripts/backfill_compact_market_movements_via_cli.py`; the new query will import no alternative grouping rule.

For each provider-date partition, the query will report:

- raw row count and raw logical bytes;
- distinct raw movement-group count;
- compact group count;
- missing and unexpected compact groups;
- mismatch counts for first seen, last seen, first odds, last odds, minimum odds, maximum odds, movement count, and snapshot count;
- the first and last observed timestamps;
- whether exact compact coverage is proven.

The query must be deterministic and read-only. It must not use temporary persistent tables, stored procedures, or database extensions.

### 2. Retention-readiness reporter

A small Python CLI will consume JSON produced by the linked Supabase CLI or a saved fixture. It will create local JSON and Markdown reports without adding dependencies.

The SQL will return one JSON envelope so the CLI can detect partial output. The composed CLI input contract will contain:

- `audit_generated_at` and the requested provider/date range;
- a `coverage` array containing the SQL reconciliation fields;
- a `season_evidence` object derived from the current Gate C manifest plus an explicitly supplied normalized season-evidence file;
- a `pins` array from an explicitly supplied pin manifest containing provider/date/reason/preserved-artifact records;
- a `provider_runtime` object containing last-run, heartbeat, and snapshot boundaries.

For Phase 1 live use, the CLI will read the current committed Gate C manifest at `data/research/gate_c/pitcher_k_outcome_dataset_manifest.json` unless an explicit alternate path is supplied. Its loaded dates, hashes, reconciliation counts, and checkpoint/CLV summary counts will be recorded in the generated report. A manifest that does not cover the audited retention date is blocking evidence, not permission to infer coverage. Missing normalized season-evidence or pin inputs will produce `blocked_outcome_evidence` or `blocked_pinned_evidence`; an omitted input is never treated as an empty, satisfied set.

A provider-date partition is decision-linked when the normalized season evidence identifies an official tracked pick, accepted bet, sent notification, consumed operational lock, frozen Alt V2 row, model-review pin, or operator incident for that slate. Decision-linked partitions require their applicable result and timing/market evidence to be materialized. A partition proven to have no decision-linked rows does not require synthetic outcome rows, but it still requires exact compact coverage and completed pin reconciliation.

Each provider-date record will receive one of these fail-closed decisions:

- `blocked_compaction`: compact movement evidence is missing or mismatched;
- `blocked_outcome_evidence`: compact evidence is exact but required checkpoint, close, CLV, or outcome-linked evidence is incomplete;
- `blocked_pinned_evidence`: the partition contains an incident, accepted bet, sent alert, provider transition, promotion review, or other pinned record that has not been preserved separately;
- `ready_for_retention_review`: all automated checks pass, but deletion still requires a separate Phase 3 approval;
- `not_in_policy_window`: the partition is too recent for the proposed retention window.

The report must never emit an executable deletion statement or equate `ready_for_retention_review` with approved deletion.

The CLI exit contract will be:

- `0`: report produced and all requested partitions reached `ready_for_retention_review` or `not_in_policy_window`;
- `2`: report produced with one or more blocked partitions;
- `3`: input validation failed and no trustworthy readiness decision could be produced.

Exit code `0` still does not authorize deletion.

### 3. BoltOdds retirement closure package

A local generator will produce a compact, durable record of the retired BoltOdds trial before any BoltOdds raw evidence is proposed for removal. The package will contain:

- runtime and suspension dates, last heartbeat, and last snapshot;
- books and coverage observed during the trial;
- raw rows and logical bytes by date;
- compact coverage, missing groups, and mismatch counts;
- connection/reconnect or provider-run evidence available in retained operational summaries;
- known production-decision impact, including an explicit statement that BoltOdds is retired and is not an active source or promotion candidate;
- any outcome-linked or market-movement findings worth preserving;
- unresolved evidence gaps and a retention recommendation;
- a declaration that the package itself does not authorize deletion or runtime reactivation.

The package must exclude secrets, credentials, authorization headers, and unnecessary raw provider payloads.

### 4. Evidence-contract configuration

The Phase 1 reporter will encode the evidence classes needed for season review. The initial contract is:

| Evidence class | Proposed durable posture | Reason |
|---|---|---|
| Official picks, grades, params history, and Gate C outcomes | Full season/permanent | Core model and results analysis |
| Accepted bets, price, book, stake, and timing | Full season/permanent | Actual betting outcome and decision analysis |
| Operational locks and consumed source artifacts | Full season/permanent | Proves which state governed a pick |
| Opening, official, checkpoint, pre-close, close, and CLV summaries | Full season/permanent | Explains price and timing performance |
| Compact first/last/min/max/count movement summaries | Full season/permanent | Preserves movement signal at low volume |
| Actual sent notifications and outcome-linked alert candidates | Full season/permanent | Measures decision value and alert quality |
| Frozen Alt V2 selections and prospective results | Full season/permanent | Preserves genuine prospective research record |
| Provider usage, coverage, reliability, and daily summaries | Full season/permanent | Supports cost and provider decisions |
| Active-provider raw market snapshots | Candidate: 30 days | Removable only after exact compaction and outcome evidence |
| Raw webhook payloads | Candidate: 30 days | Retain thin delivery ledger and parsed fields longer |
| Repeated operational provider rows | Candidate: 14–30 days | Retain daily/slate summaries and pinned incidents |
| Unsaved shadow movement and notification candidates | Candidate: 60 days | Remove only after outcome linkage/materialization |
| Retired-provider raw data | Provider closure review | Requires a complete closure package and exact reconciliation |

These windows are proposed review rules, not active retention settings.

### 5. Pinned-evidence rules

Age-based eligibility must be overridden when a record or partition is needed to explain:

- an accepted bet or official tracked pick;
- a sent notification or operator action;
- a material provider/source transition;
- a lock or artifact incident;
- a model promotion, rejection, or breakout review;
- an unusual win, loss, price move, or data-quality event;
- a disputed grade, CLV value, or decision outcome;
- the prospective Alt V2 record.

Phase 1 may report that a partition is pinned. It may not decide that a business-relevant event is safe to discard.

## Data Flow

1. An operator runs the read-only SQL through `npx supabase db query --linked -o json` from the repository root.
2. The resulting single-envelope JSON is passed to the local reporter or saved as a test/audit input outside production artifacts.
3. The reporter validates the envelope schema, requested date range, query timestamp, and completeness markers.
4. It loads the Gate C manifest, the explicit normalized season-evidence file, and the explicit pin manifest.
5. It evaluates each provider-date partition using exact coverage, decision-linked evidence, provider runtime, and pin preservation.
6. It writes local JSON and Markdown evidence reports.
7. Any missing, partial, or contradictory input produces a blocked decision and non-zero process exit.

The reporter will not connect directly with service-role credentials. This keeps the CLI's linked, read-only operator path explicit and prevents secrets from entering generated output or tests.

## Failure and Safety Behavior

The tooling must fail closed when:

- the query result is empty, truncated, malformed, or missing required columns;
- a provider-date partition has raw evidence but no corresponding compact evidence;
- any exact aggregate differs;
- checkpoint, close, CLV, or outcome evidence required by the contract is absent;
- the slate date or provider cannot be resolved unambiguously;
- the database reports a new or unknown provider;
- pinned evidence has not been preserved in a durable record;
- the BoltOdds closure interval extends beyond the documented suspension date;
- input freshness is insufficient for the stated audit time.

The CLI must print aggregate evidence only and must redact values matching known secret/key field names.

## Testing and Verification

Phase 1 tests will be local and fixture-driven:

- exact coverage succeeds when every raw aggregate equals its compact aggregate;
- each individual mismatch field blocks readiness;
- missing and unexpected compact groups block readiness;
- incomplete checkpoint, close, CLV, or outcome coverage blocks readiness;
- policy-window age alone cannot produce approval;
- pinned evidence blocks automated readiness;
- retired BoltOdds rows after the suspension boundary are surfaced as an operational exception;
- malformed, incomplete, and empty Supabase output fails closed;
- generated Markdown and JSON contain no secret-like fields or executable deletion SQL;
- the BoltOdds closure package preserves required trial facts and declares no production authority.

Live verification will rerun the read-only query and confirm that the report reproduces the known 2026-08-18 mismatch totals. No test or verification command may mutate Supabase.

## Phase 1 Success Criteria

Phase 1 is complete only when:

1. The exact coverage query reproduces live provider/date inventory without pagination loss.
2. Fixture tests cover every blocking decision and pass locally.
3. The live read-only report reproduces the current provider-level mismatch totals.
4. The BoltOdds closure package identifies all unresolved compaction gaps and confirms no fresh post-retirement runtime evidence.
5. No production code path, environment variable, provider flag, scheduled job, artifact, model input, notification, lock, or retention rule changes.
6. No database write, backfill, deletion, vacuum, deployment, merge, or push occurs.
7. The resulting evidence is sufficient to write a separate Phase 2 post-slate-finalizer specification.

## Explicit Non-Goals

Phase 1 will not:

- change TheRundown or PropLine source posture;
- reactivate or promote BoltOdds;
- change polling, webhook, notification, lock, dashboard, model, threshold, staking, or calibration behavior;
- modify `formula_change_date` or historical results;
- add a Supabase migration, scheduled function, trigger, or retention policy;
- backfill compact tables or Gate C fields;
- delete, archive, vacuum, or reclaim database storage;
- publish generated reports to production artifacts;
- merge or push the feature branch without separate approval.

## Decisions Reserved for Later Review

After Phase 1 evidence is reviewed, Tyler will separately decide whether to authorize:

1. a Phase 2 post-slate finalizer and bounded historical backfill;
2. the precise active-provider raw retention window;
3. the precise webhook and operational-table retention windows;
4. the BoltOdds closure package as sufficient historical evidence;
5. a Phase 3 deletion proposal for exact named partitions;
6. any storage-reclamation operation after deletion.
