# Offline capture feasibility result

September 4, 2026. **Prototype complete; stop before hosted capture.** The
preserved September 3 source accounts for 12 opportunities, one known frozen
selective-LEAN rule match, and **zero internally complete capture inputs**.
No trusted live feasibility or formal prospective credit is established.

The [prototype](../../analytics/diagnostics/forward_capture_feasibility.py) reads
explicit files, builds an independent inventory from supplied lock and freeze
exports, assembles a separate envelope without changing source values, and
reuses the existing frozen-proof and pregame replay validators. It validates
ordinary seed/consumption witnesses before requiring any settled result. It
cannot authenticate local assertions about acquisition, persistence or seeding.

## Evidence classes and outcome

| Evidence | Inventory / result | Justified interpretation |
| --- | --- | --- |
| Synthetic acceptance | 16 scenarios; seven pass internal pregame/seed checks, including weak negative, neutral, against, fallback and no-lineup cases | Software accepts complete unfavorable evidence; no selective collection or new positive filter |
| Synthetic exclusions | Nine scenarios remain incomplete, including late receipt, recovery, missing seed/capture, page cap, exact replay mismatch, conflicting retry, byte cap and 33-candidate cap | Missingness and bounded-work failures stay visible; no shortened favorable subset |
| Preserved September 3 exports | 12 frozen rows and 12 locks become 12 inventory rows; all Preclose-pending, all missing capture, consumption-receipt and original-seed evidence | Historical implementation check only; zero complete inputs, zero prospective credit |
| Recorded operational consumption | All 12 exported locks contain `consumed_at` | `missing_consumption` in this prototype means missing the required pregame receipt, **not** 12 unconsumed operational locks |
| Previous acceptance | Signed-score 20-scenario packet remains nine synthetic input candidates at its source revision; adapter and 327 captured proofs remain unchanged | No old credit is created; all 41 checked historical evidence files are byte-preserved |

The frozen export was captured September 4 at 22:48:48Z; the lock export at
22:25:16Z. The prototype filters those existing complete exports to the latest
completed slate, September 3. It does not fetch live data, reconstruct receipts
from those later exports, relabel timestamps or modify a freeze. The source-scope
counts prove conservation within the supplied files; they do not independently
authenticate a complete live collection process.

## Validation and local resource use

**35 focused tests and 207 combined tests pass.** Cases cover acquisition after
lock despite an early event time, original-seed run provenance, recovered/missing
seed, quote and replay mismatch, source/manifest drift, ambiguous IDs, identical
and conflicting retries, full-page exclusion, complete 33-row inventory, byte
caps, unknown fields, attachment identity, interrupted writes, digest mismatch,
forbidden output paths and no network access. The combined suite includes the
forward validator, adapter and signed-score round-trip regressions.

The historical source bundle is 99,654 uncompressed bytes; its completed local
output is 12,654 bytes. The initial run spent approximately 5.3 ms parsing and
validating it. Successful synthetic outputs are at most 24,207 bytes. These are
one-run local measurements, not hosted request cost, storage capacity, latency
or durability evidence. The largest synthetic case deliberately exceeds the
4 MiB envelope cap and is rejected before writing that envelope.

The sink requires a new directory and exclusive files. Payloads are flushed,
renamed and directory-synced; `COMPLETED.json` is written last with file hashes.
An interrupted write leaves no completed marker and cannot be overwritten by
retrying the same directory. A completed assessment can report failure: the
marker confirms output integrity, not a feasible capture. If the output budget
cannot hold all envelopes, only the complete failure inventory is written;
if even that cannot fit, the command fails before creating the destination.

The new prototype does not change the existing forward validator, proof readers,
scoring, staking, thresholds, providers, notifications, retention or production
configuration. No scheduler, collector, migration, hosted sink, deployment or
activation was added. All real activation fields remain null. The prior negative
score repair remains a separate feature-branch change, not a deployed release.

## Decision and next useful evidence

**Pause hosted capture work and repetitive historical feasibility runs.** The
prototype has demonstrated the software contract and the current source gaps.
Another run of these same files cannot establish by-lock acquisition or original
seed provenance. Alt V2 remains retired; selective LEAN stays research-only at
zero formal credit; Kumar remains excluded. No predictive-value conclusion or
fully costed return changes.

The next meaningful decision is whether a separately reviewed passive receipt
instrumentation design can preserve actual acquisition and original ungraded
seed witnesses while leaving official picks, lock timestamps and production
behavior intact. Current `observed_at` is set before polling/reads; it cannot
be substituted for actual receipt time. If an unchanged frozen proof cannot
be replayed from inputs demonstrably available by its lock, report exclusion
and stop rather than moving the lock or importing later snapshots.

Revisit only when new source evidence or an explicit instrumentation proposal
resolves those gaps. A hosted pilot additionally requires verified immutable
storage/permissions, original-seed and acquisition provenance, complete bounded
reads, measured live resource use and rollback. No prototype result grants that
approval. The [controlling plan](../superpowers/plans/2026-09-04-bounded-forward-capture-proposal.md)
retains the exact gates; other lanes keep the triggers in the
[operating brief](../operating-brief.md).

[Results and source hashes](evidence/2026-09-04-forward-capture-feasibility/run/acceptance.json)
· [Measured bytes/time](evidence/2026-09-04-forward-capture-feasibility/run/measurements.json)
· [Input profile and reproduction](evidence/2026-09-04-forward-capture-feasibility/README.md)
