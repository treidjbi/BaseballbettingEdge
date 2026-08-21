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

Deletion remains blocked by season-evaluation and recovery gaps, not by compact
integrity. The June 3 Gate C gap is now repaired, but explicit provider metadata
is missing on most tracked BoltOdds-era rows; the normalized evidence and pin
manifests do not exist; the full checkpoint envelope is not assembled locally;
and the newest completed physical backup predates the repair.

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
| Gate C date coverage | All `41/41` BoltOdds-era dates; canonical clean window `50/50` | Pass |
| Provider attribution | `652/844` tracked rows lack explicit provider metadata | Blocked |
| Season evidence and pins | No normalized manifests in the repository | Blocked |
| Canonical checkpoint envelope | Earlier files documented but not assembled locally | Blocked |
| Recovery point | Latest completed physical backup predates repair; PITR disabled | Blocked |

June 3 was the highest-signal gap. It contains `13,801` raw BoltOdds rows,
`627` exact compact rows, `278` completed provider runs, `14` accepted bets,
`73` sent notifications, and `24` consumed locks. The canonical Gate C rebuild
now preserves that slate and its graded outcome evidence, but the remaining
provider/pin/envelope/recovery gates still prohibit raw deletion.

Provider attribution is the broader quality issue. Only `192/844` tracked
BoltOdds-era rows carry explicit provider metadata (`22.75%`). The missing
`652` rows must be enriched when supported by durable evidence or explicitly
recorded as unknown; they must not be guessed.

### June 3 transport diagnosis

The June 3 evidence is preserved. The production dated slate contains Robert
Gasser at a `4.5` line with no embedded result, while the live Supabase
`picks_history` artifact contains his official `UNDER 3.5` loss and `5` actual
strikeouts. The existing pitcher-game reconciliation rule can join those facts.

The failure was that the public unfiltered `picks_history` response exceeded
the Netlify function's response-size ceiling, while the committed local history
ended before June 3. The bounded transport was merged and pushed on `main` at
`016f0676` and deployed to Netlify production as deploy
`6a88b9462f9c4a8071b3d91f`. Production returned `24` June 3 history rows in
`33,196` bytes, rejected a reversed window with HTTP `400`, and preserved the
normal `today` artifact.

The canonical April 28-June 16 rebuild now contains all `50` dates, `2,070`
rows, `1,075` tracked rows, zero duplicate keys, and `1,075/1,075`
reconciliation. Gasser retains the archived `4.5` market, the official UNDER
loss, `5` actual strikeouts, and the `picks_history_pitcher_game` recovery
source. The June 3 Gate C blocker is closed.

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

1. Enrich supported provider attribution and preserve unknowns explicitly; do
   not infer provider labels.
2. Generate aggregate-only season-evidence and pin manifests. Keep accepted-bet
   details and notification bodies out of the public repository.
3. Recover or regenerate the canonical checkpoint envelope without weakening
   the generic multi-provider contract.
4. Verify the first completed physical backup after the repair.
5. Draft an exact date/provider-bounded deletion statement and dry-run report.
   Tyler must separately approve the deletion statement before execution.
6. If approved, delete only the verified BoltOdds raw candidate, verify the
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
  `b6f1c9d414fa4330ce70f9cfcddc70c9cadc8239f9010ca5c60d0e607e9ed845`;
- Gate C JSONL SHA-256:
  `317e8a3134f5e43093728dd06d45b8f3ef717f998c4403a084bf654a118c3f61`;
- Gate C summary SHA-256:
  `7abac6a879df881469be4b4e8eb6369293f1604db79c760e0dc930adfede43e6`.

Supabase backup behavior and retention options are documented in
[Database Backups](https://supabase.com/docs/guides/platform/backups). This
retention preflight and Gate C rebuild performed no database write, deletion,
restore, vacuum, provider change, model change, or source-of-truth change. The
separately approved Netlify deployment changed only the bounded history-read
transport.
