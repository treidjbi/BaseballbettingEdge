# BoltOdds Retention Closure Preflight — August 21, 2026

## Executive Summary

**Status: WATCH — deletion is NO-GO.** The retired BoltOdds raw slice is a real
cleanup candidate: `611,972` raw rows contain `461,536,160` logical bytes,
about `440 MiB`, while `26,726` compact rows preserve the movement summary in
`28,600,016` logical bytes. Compact coverage is exact and there are zero raw
BoltOdds rows after the documented suspension boundary.

The database is not under immediate capacity pressure. It is about `4.70 GiB`,
or `58.75%` of the included 8 GiB. Deleting the retired raw slice would make
space reusable inside PostgreSQL, but ordinary deletion would not guarantee an
immediate reduction in the physical database size.

Deletion is blocked by season-evaluation and recovery gaps, not by compact
integrity. June 3 is missing from Gate C despite material accepted-bet,
notification, and lock activity; explicit provider metadata is missing on most
tracked BoltOdds-era rows; the normalized evidence and pin manifests do not
exist; the full checkpoint envelope is not assembled locally; and the newest
completed physical backup predates the repair.

## Verified Cleanup Opportunity

| Measure | Verified value | Decision meaning |
|---|---:|---|
| Current database size | `5,046,348,947` bytes (`4.70 GiB`) | `58.75%` of included 8 GiB; no emergency cleanup |
| `market_snapshots` total size | `3,513,262,080` bytes | Largest reviewed storage surface |
| Retired BoltOdds raw candidate | `611,972` rows / `461,536,160` logical bytes | About `440 MiB` eligible for a future bounded proposal |
| Preserved compact evidence | `26,726` rows / `28,600,016` logical bytes | Permanent season/provider evidence layer |
| Rows after suspension boundary | `0` | No accidental BoltOdds reactivation detected |

The candidate window runs from May 7 through June 16, 2026. The retired worker
had no snapshot rows after `2026-06-17T17:22:29Z`. The June 16 repair is exact
at `107/107` groups, and the July 10-22 follow-up partitions are exact zero
rows/runtime/anomalies.

## Evidence That Must Remain Permanent

The end-of-season question is what worked, what did not, and why. The cleanup
rule must therefore preserve:

- official picks, grades, PnL, parameters, and the Gate C outcome dataset;
- accepted-bet timing and results;
- consumed operational locks and opening/checkpoint/close/CLV evidence;
- compact market-movement summaries and provider closure summaries;
- sent notification outcomes and the prospective Alt V2 record;
- incidents, provider transitions, model-review pins, and hashes that connect
  those records to the raw period.

The proposed candidate is only retired BoltOdds raw `market_snapshots` after
these permanent records and their linkages pass the readiness contract. No
other table, provider, model, notification, lock, UI, or artifact behavior is
in scope.

## Why Deletion Is Still Blocked

| Gate | Current evidence | Status |
|---|---|---|
| Compact coverage | June 16 `107/107` exact; later partitions exact zero | Pass |
| Retired-runtime boundary | Zero raw BoltOdds rows after suspension | Pass |
| Gate C date coverage | `40/41` BoltOdds-era dates; June 3 missing | Blocked |
| Provider attribution | `652/844` tracked rows lack explicit provider metadata | Blocked |
| Season evidence and pins | No normalized manifests in the repository | Blocked |
| Canonical checkpoint envelope | Earlier files documented but not assembled locally | Blocked |
| Recovery point | Latest completed physical backup predates repair; PITR disabled | Blocked |

June 3 is the highest-signal gap. It contains `13,801` raw BoltOdds rows,
`627` exact compact rows, `278` completed provider runs, `14` accepted bets,
`73` sent notifications, and `24` consumed locks. Removing its raw rows before
the season evidence is repaired or explicitly pinned would weaken the final
season review even though compaction itself is healthy.

Provider attribution is the broader quality issue. Only `192/844` tracked
BoltOdds-era rows carry explicit provider metadata (`22.75%`). The missing
`652` rows must be enriched when supported by durable evidence or explicitly
recorded as unknown; they must not be guessed.

## Recovery Posture

The current Supabase inventory reports completed physical backups through
August 21, 2026 at `05:32:59Z`, but that backup predates the historical repair.
PITR is not enabled. A new completed daily backup after the repair is the next
minimum recovery gate. Backup availability is not the same as a tested restore,
and no restore was attempted during this read-only preflight.

A second raw export would preserve roughly the same `440 MiB` that cleanup is
intended to remove. It should not be the default answer unless the closure
review finds evidence that cannot be represented in the permanent compact and
season layers.

## Next Decision Sequence

1. Rebuild or explicitly pin June 3 in Gate C without changing live model
   behavior, grades, thresholds, staking, or source-of-truth rules.
2. Enrich supported provider attribution and preserve unknowns explicitly; do
   not infer provider labels.
3. Generate aggregate-only season-evidence and pin manifests. Keep accepted-bet
   details and notification bodies out of the public repository.
4. Recover or regenerate the canonical checkpoint envelope without weakening
   the generic multi-provider contract.
5. Verify the first completed physical backup after the repair.
6. Draft an exact date/provider-bounded deletion statement and dry-run report.
   Tyler must separately approve the deletion statement before execution.
7. If approved, delete only the verified BoltOdds raw candidate, verify the
   permanent layers again, and use ordinary maintenance only as separately
   justified. Do not default to `VACUUM FULL` or another blocking rewrite.

## Evidence And Privacy Boundary

The repository is public. This closure package records aggregate counts,
dates, hashes, and source references only. It does not commit accepted-bet
details, notification bodies, credentials, or access tokens. The underlying
accepted-bet, notification, and lock records remain untouched in Supabase.

Key local evidence fingerprints:

- sizing query SHA-256:
  `ed83774953eb0e2c7148bebd2bdf93460438210828de5d1cb6615a4204e81519`;
- sizing evidence SHA-256:
  `e91942fb81b27a306c4e027d6132fea91900a27e6ad7cd811250ee077b23fe05`;
- repaired June 16 checkpoint SHA-256:
  `150734f5db762d083885d9faec93431e433ced47695211797326f81ecbc6330b`;
- July 10-16 checkpoint SHA-256:
  `25655f8eec984018dbe54184b2e828ca7a0bf80a830b9033073596d72dc0124e`;
- July 17-22 checkpoint SHA-256:
  `c13ed95d79b3f52751f63617e64869738883c3fc5ef97e22da4c2bfe2b652f77`;
- Gate C manifest SHA-256:
  `db66cc7a830ae0951a040894490a40ea6b345b73efacca78f6599526906e1ccf`.

Supabase backup behavior and retention options are documented in
[Database Backups](https://supabase.com/docs/guides/platform/backups). This
preflight performed no database write, deletion, restore, vacuum, provider
change, deployment, or production behavior change.
