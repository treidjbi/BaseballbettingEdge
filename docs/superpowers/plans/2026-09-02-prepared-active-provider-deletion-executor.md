# Prepared Active-Provider Raw Snapshot Deletion Executor Plan

Date: **2026-09-02**

## Authorization and Boundary

Tyler approved implementation of a dormant bounded executor after reviewing
`docs/research/2026-09-02-prepared-active-provider-deletion-review.md`.
This approval covers local code, tests, documentation, and non-mutating
validation only. It does not approve a production preview, deletion, retention
activation, vacuum, reclamation, provider change, notification change, or any
other database write.

Actual deletion requires a later approval that names the exact preview token
and command after current backup evidence is recorded.

## Fixed Scope

The executor accepts exactly one provider and one slate date per invocation.

- Providers: `propline`, `therundown`
- Dates: June 12-30, July 2-12, and July 16-26, 2026
- Table that may eventually be changed: `public.market_snapshots`

It must reject ranges, rolling age cutoffs, BoltOdds, The Odds API, excluded
dates, post-July-26 rows, webhooks, and every other table.

## Preview Contract

Preview is the default operational phase and remains SELECT-only. It must:

1. run the existing exact one-provider/one-date bounded retention query;
2. validate the full query payload using the existing audit contract;
3. require exact compact coverage, complete retention preservation, positive
   raw rows, and zero blocking source anomalies;
4. require a user-supplied completed-backup timestamp newer than both the
   review packet and final historical compact write;
5. bind provider, date, raw counts/bytes, compact counts, timestamps, SQL
   hashes, and backup timestamp into a short-lived approval token;
6. write only a sanitized local preview report; and
7. keep `deletion_approved=false` and `retention_execution_closed=true`.

## Execution Contract

Execution is dormant until separately approved. It must require all of:

- the `execute` subcommand;
- `--execute`;
- `--run-linked-delete`;
- an unexpired validated preview report;
- `ALLOW_MARKET_SNAPSHOT_DELETE=true`; and
- `APPROVED_PREPARED_MARKET_SNAPSHOT_DELETE_TOKEN` exactly equal to the
  preview token.

Immediately before the write, the executor must rerun the exact SELECT-only
preview and prove the source state is unchanged. The write SQL must then:

1. select run-linked rows for only the approved provider/date;
2. gate on approved raw row count, logical bytes, first/last timestamp, compact
   group count, and represented snapshot count;
3. remove one provider/date partition in one database statement/transaction;
4. return aggregate-only counts; and
5. become a zero-row no-op if any gate differs.

After the statement, a separate SELECT-only check must require zero target raw
rows and the unchanged compact row/representation counts. Any transport error
or contradictory result is reported as uncertain and must not be retried
automatically.

## Implementation Files

- Create `scripts/retire_prepared_market_snapshots.py`.
- Create `tests/test_retire_prepared_market_snapshots.py`.
- Update `docs/operational-risk-register.md` with the new exact path while
  retaining the old broad path as ineligible for this packet.
- Update `docs/current-state.md` after local verification.

## Verification

- Use red-green TDD for all new behavior.
- Use fake query runners for mutation tests.
- Never call the production execute path during implementation verification.
- `--help`, invalid-scope checks, local preview construction, and SQL contract
  tests are allowed.
- Run the focused retention suite, JSON validation, `git diff --check`, and a
  staged secret scan before committing.

## Completion Record

Implementation and local verification completed on **2026-09-02**.

- Executor: `scripts/retire_prepared_market_snapshots.py`
- Executor SHA-256:
  `95ae71e9e69f218832ec58e889a32148294453a5b7010912a576f546272323e6`
- New executor tests: `21` passed
- Focused retention suite: `239` passed
- Linked production previews during implementation: `0`
- Production mutations during implementation: `0`
- Rows deleted: `0`

The implementation remains dormant. The next authorized step is not deletion;
it is a separately approved exact SELECT-only preview after the latest completed
backup has been verified and its timestamp recorded. The resulting provider,
date, token, source state, and exact command must be shown to Tyler before any
execution gate is opened.

## First Preview Authorization and Backup Blocker

At **2026-09-02T23:37:39Z**, Tyler approved the first exact SELECT-only preview,
using the first prepared partition: PropLine on `2026-06-12`. The backup check
ran before the partition query. Supabase reported the latest completed physical
backup at `2026-09-02T05:42:14.276Z`, while this review packet was generated at
`2026-09-02T17:56:49Z`. PITR remains disabled.

Because the backup predates the packet, the preview gate failed closed. No
partition query ran, no preview report or token was generated, no execution
environment value was set, and no row was deleted. The sanitized check is in
`data/research/retention/prepared-delete-backup-check-2026-09-02.json`.

The approval may be retried only after a later physical backup reports
`COMPLETED`. Recheck the backup inventory first; do not assume the next scheduled
backup completed. Then rerun only the same PropLine `2026-06-12` SELECT-only
preview. Deletion remains separately gated.

## First Successful Exact Preview

At **2026-09-04T01:36:27.853637Z**, the separately approved SELECT-only preview
completed for PropLine `2026-06-12`. Supabase first reconfirmed the completed
physical backup at `2026-09-03T05:43:13.129Z`; it is newer than the review
packet. PITR remains disabled.

Two attempts through the local linked-CLI boundary returned code `1` with the
generic `subprocess_failed` classification and produced no report. They were not
looped. The documented Supabase connected-SQL fallback then ran the exact same
generated SELECT-only SQL and returned a complete payload. The executor's
existing validator accepted it and wrote:

`data/research/retention/prepared-delete-propline-2026-06-12-2026-09-03.json`

The immutable preview evidence is:

- raw snapshots: `11,888`
- logical raw bytes: `5,111,272`
- raw groups / exact compact groups: `218 / 218`
- mismatched, missing, unexpected, and duplicate groups: `0`
- every source-anomaly count: `0`
- preview SQL SHA-256:
  `dd6a38b3a62012b4c13365978a38d663e584cdae13af37e9e57bd7f8fa0f8e6c`
- delete SQL SHA-256:
  `cc424e6ac576c37513aff421cfe5d97a3b2d833f2ff6e9b20d813b39435a9676`
- preview report SHA-256:
  `2f9016da53968ca397e83af0e7a082ae06ed3b6d7a8c81b64f0b3b96f433d436`
- approval token:
  `feba1b620c4ed27fded9cb62e486da9cf55d6d9241e5c3375571a016f274b09b`
- token expiration: `2026-09-05T01:36:27.853637Z`

The report still states `deletion_approved=false` and
`retention_execution_closed=true`. No environment gate was set and zero rows
were deleted.

The exact proposed command, not executed, is:

```bash
ALLOW_MARKET_SNAPSHOT_DELETE=true \
APPROVED_PREPARED_MARKET_SNAPSHOT_DELETE_TOKEN=feba1b620c4ed27fded9cb62e486da9cf55d6d9241e5c3375571a016f274b09b \
python3 scripts/retire_prepared_market_snapshots.py execute \
  --preview-report data/research/retention/prepared-delete-propline-2026-06-12-2026-09-03.json \
  --output data/research/retention/prepared-delete-result-propline-2026-06-12-2026-09-03.json \
  --execute \
  --run-linked-delete
```

Do not run it without Tyler's separate approval of this provider, date, token,
and command. If the token expires, discard the proposed command and generate a
new exact preview after rechecking backup status.
