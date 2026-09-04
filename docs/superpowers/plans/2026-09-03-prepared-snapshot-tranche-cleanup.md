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
