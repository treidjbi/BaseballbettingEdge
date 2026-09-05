# Bounded forward-capture proposal

Date: September 4, 2026. **Proposal prepared; no collector, sink or activation
implemented.** The paired proof-format repair is accepted on the feature branch
at `b08284fd`; [acceptance evidence](../../research/2026-09-04-signed-score-implementation.md)
does not authorize deployment. The [frozen contract](../specs/2026-09-04-forward-pregame-evidence-contract.md)
continues to control eligibility, timing, baselines and every research gate.

## Decision

Next implement a standalone **offline feasibility prototype** that consumes
explicit supplied artifact/lock/market/seed receipts, validates one bounded slate
and writes a new local packet. Do not start by adding a scheduled collector or
hosted sink. First prove that the unchanged frozen decision can be reproduced
from by-lock inputs and that an original ungraded seed can be affirmatively
witnessed. If no eligible opportunities survive, report zero and stop; do not
relax timing, substitute snapshots or widen provider polling.

The proposed prototype sink is a new directory under
`analytics/output/forward_capture_feasibility/<run-id>/`, using exclusive creation
and atomic completion. Outputs include the complete opportunity inventory,
input hashes, every exclusion, validation result, byte counts and timings. Inputs
are read-only files; source URLs are descriptive and must never be fetched by
this prototype. Local or retrospectively assembled files establish internal
consistency only, not trusted live acquisition or formal prospective credit.

## Exact source mapping and unresolved proof

| Envelope need | Current source/code | Required witness or gap |
| --- | --- | --- |
| Official artifact and Path B | `_load_artifact` / supplied artifact in `scripts/build_live_events_to_supabase.py`; exact `pitchers`/`tracked_picks` fields | Preserve fetched body bytes and actual successful acquisition time, generated time and both hashes. Current return values include payload/hash/source, not an acquisition receipt. Never relabel a later read as earlier availability |
| Lock and frozen decision | `operational_pick_locks`; `record_alternative_pick_selection_v2` and `alternative_pick_selection_state` | Exact game/book/side/line/odds/hash and original full immutable proof, lock insertion acknowledgment and freeze completion before start. Preserve conflicts and unconsumed rows as excluded |
| Raw market and provenance | `_fetch_live_market_snapshot_rows`, provider runs, `current_market_lines`, heartbeats, candidate/provider window state | Reuse bounded inputs already read; retain actual read start/end and completeness. The current result exposes window/status/rows, not authenticated per-source acquisition receipts |
| Snapshot availability | `market_snapshots.observed_at` and schema-default `created_at` | `observed_at` can be stamped before a poll. A default `created_at` alone is not proof of enforced append-only receipt provenance or transaction commit time; verify write semantics before treating it as ingestion proof |
| Original history seed | `pipeline/fetch_results.py:seed_picks`, `export_db_to_history`; `pipeline/run_pipeline.py` seed/lock/export block | `fetched_at`, a later exported history row, or absent recovery flags do not prove original seeding. Need an affirmative ordinary-run, result-null, pregame per-row seed/locked-quote witness with run identity; distinguish new insert from hydrated/recovered/update-only rows |
| Consumption, settlement, final CLV | Existing consumption acknowledgment and later exact history/close records | Append separate attachments; preserve actual recorded PnL and cost missingness. No outcome field may enter the pregame envelope. Do not repair Kumar or mutate history |

The important sequencing issue is concrete: the live layer sets `observed_at`
after loading the artifact but **before** provider polling, heartbeat reads and
snapshot reads. It later uses that shared time for lock/evidence work. A callback
at the end cannot stamp the inputs' acquisition times with the earlier value.
For each candidate, the prototype must test exact replay using only authenticated
by-lock receipts. A same-cycle late snapshot cannot replace missing by-lock data,
even when its provider/event timestamp appears early. If the resulting proof
differs from the actual frozen proof, keep the candidate excluded.

Do not move the operational lock timestamp, change which snapshot the current
proof consumes, modify production sampling, or redefine the frozen contract to
make this pass. If unchanged runtime cannot yield a feasible cohort, bring that
specific result back for a separate decision before building hosted infrastructure.

## Proposed limits and resource evidence

These are proposed prototype/pilot stop limits, not production settings or a
change to selection thresholds:

- One explicitly supplied slate, all tracked opportunities inventoried before
  selection; at most 32 candidates. If the slate exceeds the cap, mark the whole
  attempt incomplete rather than cherry-picking a subset.
- Reuse the current snapshot reader ceiling of five 1,000-row pages and its
  provenance/freshness rules. Complete coverage must include every required
  candidate/provider window start. A full last page, missing provider-run page,
  unknown cutoff, duplicate key or truncated window remains incomplete. No
  automatic page-limit increase or raw/webhook rescan.
- At most 4 MiB serialized per envelope, 64 MiB total input and 64 MiB total
  output for one attempt. Measure before writes; exceedance emits an inventory
  failure, never a silently shortened envelope. Preserve exact bytes; share
  identical artifact/receipt objects by content hash in a future storage layer.
- No provider calls, Supabase writes, pipeline invocation or scheduled work in
  the prototype. Measure local bytes and validation time; keep every formal
  credit and real activation field zero/null.

The [new measured packet](../../research/evidence/2026-09-04-signed-score-implementation/run/acceptance.json)
contains synthetic envelopes of **14,455–16,881 bytes** with only two/four snapshot
receipts. Artifact receipt objects are 2,258–2,762 bytes. Those small fixtures are
not production capacity evidence. Canonical reserialization of 21 previously
captured historical artifact payloads ranges **85,520–991,748 bytes**, total
5,177,969 bytes; this is explicitly a decoded-payload size proxy, not original
wire bytes or a live acquisition benchmark. Base64, proofs, source windows,
deduplication, database indexes and replication can change actual storage use.

Before a hosted pilot, measure representative source rows/bytes, compression,
read/page count, validation time, write/ack latency and total storage. Prove the
whole pregame envelope is acknowledged before game start. No current invoice,
server latency, storage projection or incremental dollar cost is established
here. Reuse the provider cost ledger and operational risk register; no new paid
service, provider request, cadence or retention change is proposed for execution.

## Conditional hosted design, not selected runtime configuration

If the offline feasibility gate passes, the concrete hosted candidate is a
separate append-only research store in the existing Supabase project, with
proposed objects `research_capture_objects`, `research_capture_envelopes` and
`research_capture_attachments`. These names reserve no resources today. A future
migration must specify exact columns/constraints, server timestamps, immutable
content addressing, unique evidence-version/candidate keys, insert-only writer
permissions, no public access and no update/delete path. Do not use production
artifact keys, notification tables or an existing freeze as mutable storage.

Identical retries must resolve to the same content and acknowledgment; conflicting
bytes must fail closed and remain visible. Receipt authentication must bind raw
bytes, actual acquisition/commit times, source/run identity and implementation
revision. A caller-written timestamp or checksum alone is insufficient. Schema
and local PostgreSQL behavior tests must run before a migration review; current
missing local binaries are not permission to skip that acceptance later.

Any live capture must be failure-isolated and disabled by default. It may observe
already available buffers and ordinary seed/consumption events only through a
separately reviewed instrumentation path. It must never gate official picks,
locking, grading, artifacts, calibration or notifications. A failed/late capture
records exclusion; it does not retry by changing a lock or writing history.
No automatic backfill after failure. Pause on cap breaches, source/manifest drift,
missing original-seed provenance, missed persistence deadline or runtime impact.

Rollback disables only the approved capture instrumentation/writer, restores the
reviewed paired-reader revision if needed, and leaves all research evidence
intact. No cleanup/deletion/retention change is bundled with rollback. A future
activation needs a new committed manifest, sink/read-bound approval and first
fully unobserved slate; both real activation fields remain unset now.

## Acceptance and next revisit

Prototype acceptance must include late receipt versus early event timestamp,
missing original seed, recovery, exact-quote conflict, complete/capped read,
snapshot replay mismatch, identical/conflicting retry, output-cap failure and
crash-before-completion cases, plus valid weak/neutral/fallback evidence. Report
the entire inventory and zero-credit conclusion. Reuse existing validators and
trackers; do not create a competing selection formula or count agreement and
Preclose as independent corroboration.

Revisit capture feasibility when those tests and measured source coverage exist.
Revisit hosted pilot approval only after acquisition/seed provenance, immutable
write behavior, budget and failure isolation pass. Revisit predictive promotion
only at the original sample/diversity/after-cost gates; this engineering work
creates no new predictive result. Routine signed-score repair probes can now
stop except for regression or source drift.
