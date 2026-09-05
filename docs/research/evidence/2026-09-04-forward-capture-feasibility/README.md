# Offline source profile and feasibility packet

The source profile is `forward_capture_sources_v1`. It does not activate or
replace `forward_pregame_evidence_v1`. All real activation fields must be null.
The prototype has no HTTP/SQL/provider calls and never dereferences receipt URLs.

## Input profile

The exact root fields are `schema`, `slate_date`, `evidence_kind`, `manifest`,
`source_scope`, `frozen_rows`, `lock_rows`, `captures`, and `attachments`.
`evidence_kind` is `synthetic`, `historical` or `captured_unverified`; none means
externally authenticated. The manifest is the current inactive forward reference.
`source_scope` declares `complete`, `frozen_count`, and `lock_count`; counts must
match supplied rows. The inventory uses the union of all freeze, lock and capture
identities, rather than only successful captures or selected candidates. Duplicate
source IDs fail closed. Declaration of completeness is not external attestation.

Each capture has exact `identity`, `frozen_id`, `lock_id`, `artifact_proof`,
`market_proof`, `decision_time`, `agreement`, `preclose`, `path_b` and `provenance`.
Use the existing forward profile's field/receipt values; extra capture fields
are rejected. The prototype copies values into a new envelope, adds the manifest
binding and digest, and verifies exact frozen replay. It never fills a timestamp,
normalizes a missing value to neutral, modifies a source proof or refreshes odds.

The market read receipt additionally requires `page_size=1000`, a nonempty
`page_row_counts` list of at most five pages, and affirmative
`provider_run_read_complete`. Counts must equal the supplied snapshot receipt
count; intermediate pages must be full and the last must prove exhaustion by
being short. This prototype profile represents a supplied complete candidate
window, not a claim that an arbitrary filtered subset of a whole-slate query
has independent pagination provenance. Any future collector must supply the
actual bounded read/projection lineage; page metadata cannot be fabricated from
the length of an incomplete export.

Each attachment has exact `identity`, `kind`, `receipt`. Kind is consumption,
seed, settlement or close. The pregame feasibility check requires only consumption
and seed, checks exact lock quote/identity, pregame event/acquisition times,
affirmative `recovery_status=original`, explicit `result=null`, `source_run_id`,
and `source_event_type=ordinary_ungraded_lock_witness`. That event must occur
after consumption. These explicit assertions still need external authentication
before trusted capture. Outcomes cannot substitute for a seed witness, affect
the pregame count or enter the decision envelope. Later lifecycle validation
remains the separate existing validator/audit's responsibility.

## Commands and evidence

```bash
python -m analytics.diagnostics.forward_capture_feasibility \
  --input /absolute/path/source-bundle.json.gz \
  --output-dir analytics/output/forward_capture_feasibility/new-run
python docs/research/evidence/2026-09-04-forward-capture-feasibility/reproduce.py
python -m pytest tests/test_forward_capture_feasibility.py tests/test_forward_pregame_evidence_validator.py tests/test_decision_time_research_adapter.py tests/test_signed_score_proof_roundtrip.py -q
```

Input is plain/gzip JSON bounded at 64 MiB uncompressed. Limits are 32 candidates,
4 MiB per envelope and 64 MiB total output, with space reserved for the completion
manifest. The whole attempt fails completeness on cap breach; no shortened
envelope or chosen subset is emitted. Output inside the repo must be a new child
of `analytics/output/forward_capture_feasibility`; external new temporary paths
are accepted for tests. Existing destinations are refused, including incomplete
runs. Completion is atomic and hashes every output; `read_completed` verifies
it. The local files remain editable by their owner and are not a trusted hosted
receipt system. Failed attempts do not get automatic retries or cleanup.

`run/source-bundles.json.gz` contains 16 synthetic scenarios and the one historical
September 3 bundle. `run/assembled-packets.json.gz` holds the newly constructed
diagnostic packets; historical missingness is not filled. `run/acceptance.json`
records independent inventory, exclusions, code hashes and old-file preservation.
`run/measurements.json` records initial local bytes/time; elapsed time is not
expected to reproduce exactly. `tests.txt` preserves 207 passing combined tests.

Normal reproduction regenerates inputs and results, exercises local temporary
output completion, checks exact deterministic equality, and revalidates the
prior signed-score/adapter evidence without editing it. `--create` is one-time
construction and refuses an existing `run` directory. The old Git revisions must
be available to verify preservation. No source is fetched, regraded or backfilled.

Historical `missing_consumption` means no affirmative pregame receipt was supplied.
All 12 preserved lock rows actually contain a recorded consumption timestamp.
All input/seed/persistence assertions remain untrusted local evidence: seven
synthetic internal passes and zero historical passes establish **zero** live
feasibility or prospective credit.
