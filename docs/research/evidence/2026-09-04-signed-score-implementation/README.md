# Paired implementation evidence

This is a new packet for implementation `b08284fd`; earlier evidence is preserved.
`run/inactive-reference-manifest.json` has null activation fields.
`run/acceptance.json` pins both reader hashes and the implementation commit.
Every input in `run/synthetic-inputs.json.gz` is synthetic; no case earns formal
credit. Fake September 6 dates and fixture activation declarations activate nothing.

From the repository root with project dependencies and Node installed:

```bash
python docs/research/evidence/2026-09-04-signed-score-implementation/reproduce.py
python -m pytest tests/test_alternative_pick*.py tests/test_signed_score_proof_roundtrip.py tests/test_forward_pregame_evidence_validator.py tests/test_decision_time_research_adapter.py tests/test_pitcher_k_outcome_dataset.py tests/test_selective_lean_prospective_audit.py tests/test_repair_missing_locked_picks.py -q
node --test --test-reporter=tap tests/test_alternative_picks_function.mjs
```

The reproducer is read-only by default; `--create` refuses an existing `run`
directory. It needs Git history containing `2129a9a7` and `b08284fd`. It verifies
new source hashes, old evidence bytes, frozen history, manifest drift and exact
saved results. Tests used Python 3.11 with temporary dependencies outside the
repo. Results: 539 Python passes, 27 local PostgreSQL tests skipped for missing
binaries, and 124 Node passes. No deployed endpoint/database test is implied.

Old reproducers are source-version specific. Use the original revision `2129a9a7`
in a separate checkout to reproduce that review; do not change an old packet
to match today's implementation. New source drift likewise needs a new packet.

Resource measurements are JSON serialization bytes: synthetic envelopes contain
only two/four snapshot receipts. The historical artifact size proxy reserializes
decoded payloads from 21 preserved records; it is neither original wire-byte
measurement nor a prospective capture benchmark. Request, database, latency and
billing measurements remain required before any hosted capture pilot.
