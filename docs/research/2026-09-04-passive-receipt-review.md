# Passive receipt instrumentation review

September 4, 2026. Source baseline: feature branch `9a1c81c1`, pulled and clean
before review. This is a static code review with synthetic validator checks;
it does not verify the currently deployed revision or refresh live health.

**Decision: defer instrumentation implementation and keep hosted capture closed.**
End-of-cycle receipts would document a known timing exclusion. They cannot make
the current market reads available before the clock used for the official lock.
Two useful hooks are feasible—artifact bytes and affirmative seed lineage—but
neither resolves that barrier. No additional collector is justified now.

The [controlling plan](../superpowers/plans/2026-09-04-bounded-forward-capture-proposal.md)
records the stop/revisit decision. The [frozen contract](../superpowers/specs/2026-09-04-forward-pregame-evidence-contract.md)
and all earlier evidence remain unchanged. Formal prospective credit is zero.

## Operational reliability

The reviewed source sequence is coherent as an operational workflow: load the
artifact, timestamp the cycle, obtain market evidence, write locks, freeze shadow
proofs, then consume locks in the separate pipeline. It does not establish that
every research input existed at the earlier cycle timestamp. Those are different
claims. This review finds no new basis to change official locks or report an outage.
The last captured health assessment remains **Watch**, not freshly reverified here.

| Source sequence | What a passive hook could establish | Limitation and disposition |
| --- | --- | --- |
| `_load_artifact` reads and hashes bytes before `run` assigns `observed_at` | Preserve the exact already-fetched body, actual read completion, source and separate byte/logical hashes | Feasible for the normal loader; caller-supplied payloads need their own receipt. A local fallback is not proof of remote freshness. Defer implementation until the full evidence path is feasible |
| `run` sets `observed_at` before polling, heartbeat and snapshot reads; locks use that same value | Actual call/response times would show inputs arriving after `L` | Do not backdate receipts. Same-cycle polling is one cause; later database reads remain even with polling disabled |
| V2 recorder reads current lines and prior window state after the lock write | Preserve the exact buffers and completion times | Current-line and window receipt requirements also remain unsatisfied by end-of-cycle capture |
| Lock and freeze insert calls return later than `L` | Separate insertion acknowledgment and completion before game time `G` | The contract permits `L <= completion < G`; later completion does not permit later input acquisition |
| `seed_picks` exposes `cur.rowcount` and updates unlocked rows | Distinguish an actual new local insert from ignored/hydrated/update-only rows | Capture after successful transaction commit, with result-null state and source/run identity. New local insertion alone does not prove complete prior history hydration or absence of recovery |
| `_apply_supabase_operational_locks` marks represented rows consumed, then the caller exports history | Witness the exact ungraded locked quote after successful acknowledgment, linked to the original seed | `consumed_at` means represented in the consumer, not published history. Do not infer original seeding from a missing recovery flag |
| Render wrapper hydrates, invokes the pipeline subprocess, then publishes | Separate source hydration and final artifact publication acknowledgments | Lock-only mode hydrates history and does not call `seed_picks`. Earlier seed provenance must survive across runs; a later export cannot recreate it |

These are proposed hook locations, not applied code. A future implementation
would need authenticated immutable receipts, explicit run identity across the
wrapper/subprocess, transaction success and conflicting-retry handling. It must
fail independently of official work and measure its overhead. No latency, storage,
provider spend or operating cost is measured by this static review.

## Predictive or selection value

Passive instrumentation supplies no new prediction or selection result. The
selective-LEAN hypothesis, sample/diversity gates and after-cost requirements
remain in the [original assessment](2026-09-04-operating-and-research-assessment.md).
No fees, slippage, new PnL or independent attribution evidence were added here.
Alt V2 promotion paths remain retired; its frozen controls are unchanged.

The stronger barrier is in the implemented forward validator. It requires every
snapshot, current-line, heartbeat, window and completed-read receipt by `L`.
The read must describe complete coverage with `window_end == L`. A completed
read after `L` fails even if every snapshot event timestamp is earlier. An
earlier cycle's receipt does not by itself establish complete coverage through
a later cutoff. Its exact contents and provenance would have to satisfy every
gate without relabeling its completion time or window end.

Using only earlier snapshots is not automatically the same decision. The V2
proof binds movement observation IDs, ordered observations, latest ladder tokens,
a ladder digest, windows and freshness. The validator requires equality of the
entire reconstructed proof. Removing a contributing late token changes that
proof even if the final score or verdict happens to remain the same. This is not
a claim that every new row necessarily uses a late snapshot: the later completed
read is independently sufficient to block the current receipt path.

`market_snapshots.created_at` is not an alternative authenticated witness in
this review. The checked polling writer uses an upsert with merge-on-conflict;
the default timestamp alone does not attest immutable payload bytes, per-version
availability or transaction acknowledgment. No live schema/permission audit was
performed, and no undocumented database protection is assumed either way.

## Evidence boundaries and verification

| Evidence class | Result | Justified interpretation |
| --- | --- | --- |
| Static source at `9a1c81c1` | Fourteen source/contract/fixture files pinned by SHA-256, with line anchors | Establishes the reviewed implementation sequence, not deployed health or live capacity |
| Eight new synthetic cases | One internally complete control; five individually late receipt families rejected; missing and recovered seed cases rejected | The existing validator enforces each independent barrier; all eight have zero formal credit and unset activation |
| Historical September 3 packet, unchanged | Previously captured 12 opportunities, zero complete inputs; 12 locks record consumption | Historical provenance failure, not 12 consumption incidents; this review does not rerun or backfill it |
| Prospective capture | Inactive; no live observations collected | No eligibility count, profit claim or promotion follows from the synthetic control |

The synthetic timing cases change only one receipt acquisition time, leaving its
event time, bytes and frozen proof intact. They isolate why an early event time
cannot rescue a late read. Seed cases use the existing fixture and validator;
they do not exercise actual SQLite transactions, production persistence or a
live provenance service. No new production tests or runtime changes were needed.

Run from the repository root:

```sh
.venv/bin/python docs/research/evidence/2026-09-04-passive-receipt-review/reproduce.py
```

The [reproducer](evidence/2026-09-04-passive-receipt-review/reproduce.py) verifies
source bytes against the reviewed commit and the saved
[eight-case result and source anchors](evidence/2026-09-04-passive-receipt-review/review.json).
It uses local fixtures only and refuses source drift. It is a review reference,
not a new recurring job. Its explicit `--create` mode refuses an existing result.

## Next decision and work to stop

Retain the adapter, validators, signed-score repair and feasibility packets for
regression/source-change review. Pause repeated historical eligibility readouts,
end-of-cycle receipt implementation, additional hosted designs and resource
benchmarking for a path that currently fails its input timing gate. Ordinary
operational checks and already-running collection remain unchanged.

Reopen this lane only when a material source correction provides authenticated,
complete by-lock evidence capable of exact replay plus original seed continuity,
or Tyler explicitly commissions a separate runtime/evidence-version redesign.
The latter is a new scope decision: it must disclose any change to cutoff,
decision inputs or eligible population and define a future holdout. It is not an
automatic next implementation task. Do not move the lock, silently weaken receipt
requirements, relabel restored rows as original, or activate historical matches.
