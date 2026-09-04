# Prepared Snapshot Controlled-Tranche Cleanup Plan

Date: **2026-09-03**

## Authorization and Hard Gate

Tyler approved continuing through planning, implementation, tests, backup
checks, and SELECT-only previews without pausing. This approval does not cover
another database deletion, vacuum, reclamation, or any provider/date outside
the previously prepared scope.

The next hard gate is approval of one exact tranche packet after its current
backup evidence, partition counts, preview tokens, packet token, packet hash,
and five proposed commands are visible. No command in a tranche may run before
that approval.

## Fixed Remaining Queue

The original prepared scope remains the 82 PropLine/TheRundown provider/date
partitions for June 12-30, July 2-12, and July 16-26, 2026. The confirmed
PropLine June 12 deletion is complete and excluded. The remaining queue is
therefore exactly 81 partitions.

Queue order is deterministic: slate date ascending, then PropLine before
TheRundown. The completed PropLine June 12 partition is omitted, making
TheRundown June 12 the first pending partition. The queue must never expand
because time passes.

## Tranche Contract

- Maximum tranche size: five provider/date partitions.
- Maximum live-preview size: `250,000` raw rows and `150 MiB` of logical raw
  bytes. A larger tranche fails before any packet file is written.
- Each partition keeps its own exact preview report, 24-hour token, source
  state, delete SQL hash, and immutable result path.
- The tranche packet binds the ordered partition list, each preview-file hash,
  each preview token, aggregate rows/bytes/groups, backup timestamp, proposed
  commands, and expiry into one packet token.
- The packet builder is SELECT-only and exposes no execute subcommand.
- After approval, an operator runs the five existing single-partition commands
  manually and sequentially.
- After every command, inspect its immutable result before proceeding.
- Stop immediately on source drift, validation failure, timeout, uncertain
  mutation, malformed result, or failed postcheck. Never retry an uncertain
  write automatically.
- Existing exclusions remain: every unprepared date/provider, webhooks,
  BoltOdds, The Odds API, post-July-26 rows, vacuum, and reclamation.

## First Tranche

The first deterministic tranche is:

1. TheRundown `2026-06-12`
2. PropLine `2026-06-13`
3. TheRundown `2026-06-13`
4. PropLine `2026-06-14`
5. TheRundown `2026-06-14`

Prepare all five exact previews only after reconfirming the latest completed
physical backup. Query all five before writing any packet files so a read
failure leaves no partial approval packet. A successful packet remains
`deletion_approved=false` and `retention_execution_closed=true` until Tyler
approves the exact packet and embedded commands.

## Verification

- Use red-green TDD for the packet builder.
- Prove the fixed queue has 81 unique partitions and 17 bounded tranches.
- Prove the completed first partition is excluded.
- Prove every query is read-only and all queries finish before files are
  written.
- Prove unknown tranches, stale backups, expired/tampered reports, duplicate
  partitions, changed files, existing output directories, and incomplete
  acknowledgements fail closed.
- Run the focused retention suite, JSON validation, `git diff --check`, and a
  staged credential scan before committing.

## First-Tranche Preparation Record

Implementation and the authorized SELECT-only preparation completed on
September 3 Phoenix time (September 4 UTC).

- The fixed remaining queue contains `81` unique partitions in `17` tranches.
  Its canonical queue hash is
  `e8f8cd9ccfedabe8c60542239c91648df0e1edc14daa1ab3f875ba9e5a62df87`.
- The read-only packet builder is
  `scripts/prepare_prepared_market_snapshot_tranche.py`. It has no execute
  subcommand and cannot mutate the database.
- The first packet is
  `data/research/retention/prepared-tranche-001-2026-09-04/tranche-report.json`
  at SHA-256
  `7915ab4e5280b392d59404f44d166087036615870a1d17255c650ea3df47be38`.
- The packet covers `57,232` raw rows / `28,436,544` logical bytes (about
  `27.12 MiB`) and `1,790` exact compact groups.
- TheRundown June 13 and June 14 expose `5,522` and `7,306` cross-date rows.
  All `12,828` are individually preserved by compact lineage; unpreserved
  rows and every other blocking anomaly are zero. The executor now follows
  the controlling v2 audit rule that preserved cross-date lineage is visible
  but informational, while any unpreserved lineage remains a hard blocker.
- The packet is bound to the completed physical backup at
  `2026-09-03T05:43:13.129000+00:00`; PITR remains disabled. The packet token
  is `9c607b896349aac403869efe25c4e701bbe2adb71f5233aea554f35c48445636`
  and expires at `2026-09-05T04:30:19.830245+00:00`.
- The focused retention suite passed `251` tests. Packet validation passed,
  both deletion environment variables remained unset, no result file exists,
  and zero rows were deleted during tranche preparation.

The next action is the hard gate: Tyler must approve or reject this exact
tranche token and its five embedded commands. If it expires, recheck the
backup and rebuild the packet. Approval must still be executed sequentially,
with each immutable result inspected before the next command.

## First-Tranche Execution Stop

Tyler approved the exact tranche token. Execution began sequentially on
September 3 Phoenix time (September 4 UTC).

1. TheRundown June 12 confirmed deletion of exactly `10,104` raw rows /
   `5,163,024` logical bytes. Its postcheck retained `456` compact groups
   representing all `10,104` observations.
2. PropLine June 13 confirmed deletion of exactly `8,866` raw rows /
   `4,028,458` logical bytes. Its postcheck retained `192` compact groups
   representing all `8,866` observations.
3. TheRundown June 13 stopped before mutation because its mandatory fresh
   preview no longer exactly matched the approved report. Target rows, bytes,
   and compact groups were unchanged at `23,731`, `12,119,175`, and `612`,
   but the informational cross-date counters changed from `5,522` preserved
   mismatches to zero after the approved TheRundown June 12 rows were removed.

The third command wrote no result because it failed before the mutation path.
A fresh SELECT confirmed all `23,731` target rows still exist. Commands four
and five were not attempted. No command was retried and no vacuum ran. The
two confirmed results removed `18,970` rows / `9,191,482` logical bytes (about
`8.77 MiB`) while preserving `648` compact groups. The sanitized stop record
is `data/research/retention/prepared-tranche-001-2026-09-04/tranche-execution-stop.json`
at SHA-256
`7efe6957cb7e2c29f0872cb3f54f1db5312d97ef8b5cadb7c5f00e7acffd44e9`.

The root cause is an interaction between chronological execution and the
date-scoped informational anomaly counters: deleting one run date can remove
cross-date observations counted on the following observed date, invalidating
a later precomputed token even though that later target partition is intact.
Do not retry tranche 001 or run commands four or five. Before further deletion,
review and test a replacement ordering/packet contract, generate fresh exact
previews, and obtain approval for the replacement token.

## Approved Descending-Queue Replacement

Tyler approved the reversible redesign after the tranche 001 stop. A bounded
linked SELECT over every remaining prepared provider/run row proved the
dependency direction:

- `1,785,407` raw rows remain in the prepared scope;
- `1,579,245` were observed on their provider run date;
- `206,162` were observed exactly one day after their run date; and
- zero were observed before their run date or more than one day after it.

The proof query is
`scripts/supabase_prepared_snapshot_ordering_proof.sql`. Its sanitized output
is
`data/research/retention/prepared-snapshot-descending-order-proof-2026-09-04.json`
at SHA-256
`0432ab48bec69875f5e67a6a645899cef378340d93bcc425c9ce6448c0e14584`.
Because deletions can change only the same or following observed date,
processing run dates newest-first prevents a deletion from changing any later
precomputed preview in the queue.

Queue v2 excludes all three confirmed partitions and contains `79` remaining
partitions in `16` tranches. It orders slate dates descending and retains
PropLine before TheRundown on the same date. Its canonical queue hash is
`896e11ecad59b1b3fb217583bbaace0c1878c6527efffce435776d700c4cf2e7`;
the queue artifact is
`data/research/retention/prepared-snapshot-remaining-queue-v2-2026-09-04.json`.
Queue v1 and tranche 001 remain immutable stopped history and must not be
resumed.

The latest completed physical backup was reconfirmed at
`2026-09-03T05:43:13.129000+00:00`; PITR remains disabled. Replacement packet
`tranche-v2-001` passed all five exact linked previews:

1. PropLine July 26: `28,554` rows / `15,430,914` bytes / `658` groups.
2. TheRundown July 26: `19,248` rows / `9,842,584` bytes / `668` groups.
3. PropLine July 25: `38,092` rows / `20,410,532` bytes / `590` groups.
4. TheRundown July 25: `26,155` rows / `13,362,471` bytes / `753` groups.
5. PropLine July 24: `45,790` rows / `24,634,086` bytes / `624` groups.

The packet totals `157,839` rows / `83,680,587` logical bytes (about
`79.80 MiB`) / `3,293` exact compact groups. All hard anomalies are zero; the
TheRundown July 26 and July 25 informational cross-date counts (`8,425` and
`7,902`) are fully preserved. The packet report SHA-256 is
`11749a7820747e37e4b9762fb56fdfeb5c56bef8efc4f34a7810328262bdc051`,
its approval token is
`180cc86f27f621ddc5b31adf15d2473f99976251eea55db102517f10abaa46d0`,
and it expires at `2026-09-05T04:58:55.853993+00:00`.

No result file exists, both deletion environment gates remained unset, and no
row was deleted during the redesign or replacement preview. The next action is
the new hard gate: approve or reject this exact v2 packet and its five embedded
commands. Execution must remain sequential and stop on any unexpected state.

## Approved Descending Tranche v2-001 Execution

Tyler approved exact packet token
`180cc86f27f621ddc5b31adf15d2473f99976251eea55db102517f10abaa46d0`
and directed execution to continue through the packet while every result stayed
exact. All five commands ran once, sequentially, in the approved order:

1. PropLine July 26 confirmed `28,554` deleted rows / `658` groups.
2. TheRundown July 26 confirmed `19,248` deleted rows / `668` groups.
3. PropLine July 25 confirmed `38,092` deleted rows / `590` groups.
4. TheRundown July 25 confirmed `26,155` deleted rows / `753` groups.
5. PropLine July 24 confirmed `45,790` deleted rows / `624` groups.

The packet therefore removed exactly `157,839` raw rows / `83,680,587`
logical bytes while retaining all `3,293` compact groups representing all
`157,839` observations. Every immutable result has `status=confirmed`, zero
target raw rows, no mutation or postcheck error, no automatic retry, and no
vacuum. The aggregate execution record is
`data/research/retention/prepared-tranche-v2-001-2026-09-04/tranche-execution-result.json`.
The independent SELECT-only query
`scripts/supabase_prepared_tranche_v2_001_postcheck.sql` also returned
`all_confirmed=true`. One earlier independent ad hoc SELECT exhausted temporary
CLI login retries without executing; the durable file-based SELECT then
authenticated and passed, so there was no uncertain write or repeated deletion.

The post-execution physical read was `6,092,729,491` database bytes (`70.93%`
of the included 8 GiB) and `4,153,589,760` bytes for `market_snapshots`.
Ongoing writes and MVCC mean DELETE did not immediately reduce physical files;
vacuum and reclamation remain unapproved.

Reversible preparation then produced `tranche-v2-002`, covering TheRundown July
24 and both providers July 23-22. Its five exact previews bind `106,972` rows /
`55,918,412` logical bytes / `2,494` compact groups. All hard anomalies are
zero, and all `16,887` informational cross-date rows are preserved. The packet
report SHA-256 is
`3cd26eeb65759a4d9a82b85c88421660028ddcf420f9a8cb56297c42c3527982`,
its exact approval token is
`0173b9ee8a99a7d073256a30b283f66a37b21fe05c3f49973774ab4abf9bf328`,
and it expires at `2026-09-05T05:24:57.679806+00:00`. No v2-002 result file
exists and no v2-002 command ran. The full retention-focused Python 3.11 suite
passes `597` tests. This exact packet is the next hard gate;
later tranches, webhooks, BoltOdds, post-July-26 rows, vacuum, and reclamation
remain closed.
