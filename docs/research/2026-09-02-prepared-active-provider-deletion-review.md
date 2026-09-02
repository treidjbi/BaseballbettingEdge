# Prepared Active-Provider Raw Snapshot Deletion Review

Review date: **2026-09-02**

## Decision

**READY FOR AN EXACT EXECUTION-DESIGN REVIEW; NOT APPROVED FOR DELETION.**

The completed manual compaction interval remains valid for the exact historical
PropLine/TheRundown dates below. Current read-only Supabase counts still match
the compact representation counts, and the candidate is materially large.
No row was deleted, no retention flag was enabled, and the existing broad
age-based executor must not be used for this scope.

## Exact Prepared Scope

Providers are fixed to:

- `propline`
- `therundown`

Slate dates are fixed to:

- `2026-06-12` through `2026-06-30`
- `2026-07-02` through `2026-07-12`
- `2026-07-16` through `2026-07-26`

This is `41` slate dates and `82` provider/date partitions. It is not a rolling
age cutoff and must never expand because time passes.

## Current Read-Only Sizing

| Provider | Raw rows | Logical bytes | Compact groups | Represented rows | Match |
|---|---:|---:|---:|---:|---|
| PropLine | `1,006,737` | `534,532,381` | `15,106` | `1,006,737` | Yes |
| TheRundown | `809,528` | `413,403,504` | `21,401` | `809,528` | Yes |
| **Total** | **`1,816,265`** | **`947,935,885`** | **`36,507`** | **`1,816,265`** | **Yes** |

The candidate is approximately `904.02 MiB` of logical raw-row data. Physical
database-size recovery may be lower or delayed because ordinary row removal
does not shrink relation files. `VACUUM FULL`, reclamation, and maintenance
downtime remain separate decisions.

The sanitized live evidence is stored at
`data/research/retention/prepared-active-provider-deletion-preview-2026-09-02.json`.
The fixed-scope SELECT-only query is
`scripts/supabase_prepared_market_snapshot_deletion_preview.sql` at SHA-256
`561b7033f8ee904076588a969fbe7324c457f56131dfca50804c37064ecdca6c`.

The combined query exceeded the connector transport window once and was not
retried. The evidence packet instead uses the successful raw sizing read, the
successful compact-count read, and the successful 82-partition count read.

## Required Exclusions

The following fail-closed partitions are outside the candidate and must remain:

- PropLine `2026-05-14` through `2026-06-11`
- PropLine `2026-07-01`
- TheRundown `2026-07-15`
- every provider/date after `2026-07-26`
- every `the_odds` and BoltOdds row
- the raw PropLine webhook inbox and every non-`market_snapshots` table

The September 2 exact-coverage failure for August 12-18 concerns a newer,
unprepared interval. It does not invalidate the prepared scope, but it is a
hard reason not to use a rolling 30-day deletion statement.

## Backup and Recovery Gate

A completed physical backup at `2026-08-28T05:45:45.570Z` was newer than the
last historical compact write at `2026-08-27T22:19:39.703533Z`. That satisfied
the documented freshness checkpoint at the time. Supabase currently provides
daily backups for this Pro project, but the latest completed backup must be
reverified immediately before execution. PITR remains disabled, so daily
backup recovery can lose activity after the selected backup.

Backup inventory is not proof of a tested restore. Before execution, record:

1. the latest completed backup timestamp;
2. that it is newer than this packet and the last compact write;
3. the expected recovery point and potential data-loss window; and
4. whether a separate logical export is required for this exact scope.

## Execution Design Required Before Approval

The current `scripts/retire_market_snapshots.py` accepts only
`--older-than-days`. On September 2 that broad predicate would include
fail-closed dates and post-July-26 data, so it is not an acceptable executor for
this packet.

The execution implementation must be reviewed before use and must:

1. hard-code or cryptographically bind the exact providers and 41-date set;
2. process one provider/date partition per transaction;
3. compare every partition's current row count to the approved preview before
   removing anything;
4. fail closed on any new row, missing row, provider mismatch, date mismatch,
   compact mismatch, timeout, or uncertain response;
5. retain resumable progress so a partial run never widens the remaining scope;
6. require both an explicit execute flag and a process-scoped approval token;
7. verify zero remaining target rows and unchanged permanent compact/history
   evidence after each partition; and
8. leave vacuum/reclamation disabled.

## Approval Boundary

This packet asks only whether to implement and review that exact bounded
executor. It is not approval to remove rows. After the executor, current backup
proof, final per-partition preview, and proposed command/hash are visible,
Tyler must separately approve the exact deletion execution.

Retired BoltOdds May 7-June 16 remains a separate candidate and must not be
silently combined with this active-provider tranche.
