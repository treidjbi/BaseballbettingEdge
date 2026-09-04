# Prepared Active-Provider Raw Snapshot Deletion Review

Review date: **2026-09-02**

## Decision

**FIRST EXACT SELECT-ONLY PREVIEW PASSED; DELETION NOT APPROVED.**

The completed manual compaction interval remains valid for the exact historical
PropLine/TheRundown dates below. Current read-only Supabase counts still match
the compact representation counts, and the candidate is materially large.
No row was deleted, no linked production preview was run during implementation,
no retention flag was enabled, and the existing broad age-based executor must
not be used for this scope.

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

## Implemented Dormant Executor

The current `scripts/retire_market_snapshots.py` accepts only
`--older-than-days`. On September 2 that broad predicate would include
fail-closed dates and post-July-26 data, so it is not an acceptable executor for
this packet.

The implementation at `scripts/retire_prepared_market_snapshots.py` satisfies
the following reviewed design:

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

It has SHA-256
`95ae71e9e69f218832ec58e889a32148294453a5b7010912a576f546272323e6`.
The focused retention safety suite passes `239` tests, including `21` executor
tests that use fake query runners for every mutation case. No production read
or write was used to prove execution behavior.

The future preview shape is intentionally one partition and SELECT-only:

```bash
python scripts/retire_prepared_market_snapshots.py preview \
  --provider propline \
  --slate-date 2026-06-12 \
  --backup-completed-at '<verified-completed-backup-timestamp>' \
  --output data/research/retention/prepared-delete-propline-2026-06-12.json \
  --run-linked-read
```

That command has not been run. The supplied backup timestamp must first be
verified against the current Supabase backup inventory. A successful report
still contains `deletion_approved=false`; it only creates a 24-hour token that
can be presented with the exact proposed delete command for Tyler's separate
approval.

A later execution would additionally require the exact report token in
`APPROVED_PREPARED_MARKET_SNAPSHOT_DELETE_TOKEN`,
`ALLOW_MARKET_SNAPSHOT_DELETE=true`, `execute`, `--execute`, and
`--run-linked-delete`. Do not populate those gates until Tyler approves that
specific provider, date, token, and command.

## Approval Boundary

Tyler's initial approval covered only implementation and local verification of
the exact bounded executor, not a production query or row removal. The next gate
was current backup proof plus one exact SELECT-only partition preview. After a
successful preview and its proposed command/hash are visible, Tyler must still
separately approve the exact deletion execution.

Tyler subsequently approved the first exact SELECT-only preview for PropLine
`2026-06-12`. At `2026-09-02T23:37:39Z`, the latest completed physical backup
was `2026-09-02T05:42:14.276Z`, older than this packet's
`2026-09-02T17:56:49Z` generation time, and PITR remained disabled. The backup
gate therefore failed closed before the partition query. No preview report or
token was generated and no deletion gate opened. Retry only after a later
physical backup is confirmed `COMPLETED`; do not infer completion from the
daily schedule.

On September 3 Phoenix time, a later physical backup was confirmed `COMPLETED`
at `2026-09-03T05:43:13.129Z`. Tyler then approved the same PropLine
`2026-06-12` preview. The local CLI boundary returned two code-1 failures and
no report, so it was not retried again. The connected Supabase SQL fallback ran
the same SELECT-only query, and the executor validator accepted a complete,
exact payload: `11,888` raw rows / `5,111,272` logical bytes represented by
`218` exact compact groups, with zero coverage blockers and zero source
anomalies.

The validated report is
`data/research/retention/prepared-delete-propline-2026-06-12-2026-09-03.json`
at SHA-256
`2f9016da53968ca397e83af0e7a082ae06ed3b6d7a8c81b64f0b3b96f433d436`.
Its approval token is
`feba1b620c4ed27fded9cb62e486da9cf55d6d9241e5c3375571a016f274b09b`,
its delete SQL hash is
`cc424e6ac576c37513aff421cfe5d97a3b2d833f2ff6e9b20d813b39435a9676`,
and it expires at `2026-09-05T01:36:27.853637Z`. The report retains
`deletion_approved=false` and `retention_execution_closed=true`. Zero rows were
deleted. Tyler must separately approve the exact token and command before any
write.

Retired BoltOdds May 7-June 16 remains a separate candidate and must not be
silently combined with this active-provider tranche.
