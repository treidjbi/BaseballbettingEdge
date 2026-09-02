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
