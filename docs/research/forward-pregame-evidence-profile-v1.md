# Offline serialization profile: forward_pregame_evidence_v1

This profile makes the [logical contract](../superpowers/specs/2026-09-04-forward-pregame-evidence-contract.md)
inspectable as local JSON. It is implemented by
[forward_pregame_evidence_validator.py](../../analytics/diagnostics/forward_pregame_evidence_validator.py).
It creates no table, service or runtime configuration. The
[synthetic factory](../../tests/forward_evidence_factory.py) supplies complete
examples; the [acceptance packet](evidence/2026-09-04-forward-evidence-validator/run/synthetic-inputs.json.gz)
is generated solely from that factory.

## Packet and digest boundary

Top-level fields are `manifest`, inclusive `start_date`/`end_date`, `envelopes`,
`attachments`, and `inventory`. Every envelope must have exactly the field set
exported as `ENVELOPE_FIELDS`. Unknown envelope fields, including outcome
fields, are rejected. A prior packet containing `records`/`rows` is explicitly
reported as legacy-schema evidence and receives zero credit.

An envelope contains `schema`, `evidence_kind` (`synthetic` or `captured`),
`manifest_sha256`, `identity`, `frozen`, `lock`, `artifact_proof`,
`market_proof`, `decision_time`, `agreement`, `preclose`, `path_b`,
`provenance` and `content_sha256`. `frozen` is the complete original V2 row;
`lock` is its exact operational-lock capture, independent of later consumption.
`identity` carries slate, normalized pitcher, side, game time/identity and lock
ID. This profile requires explicit artifact `tracked_picks` display quote,
verdict, pitcher and game fields; older alternate shapes fail closed.

Digest serialization is UTF-8 JSON, sorted keys, compact separators,
`ensure_ascii=False`, `allow_nan=False`. `content_sha256` hashes the entire
envelope excluding that one digest field. `manifest_sha256` hashes the entire
manifest. Receipt byte hashes are **not** hashes of reserialized decoded JSON.
Duplicate JSON object keys, malformed encodings and nonfinite values fail.
The CLI limits decompressed input to 64 MiB as a local file safety bound; this
does not alter any provider query cap or polling setting.

## Receipt and source bodies

A receipt includes `receipt_id`, `source_path`, `source_event_at`,
`acquired_at`, `body_base64` and `byte_sha256`. The body preserves the exact
enclosed source/witness bytes. Source paths are descriptive references; the
validator never dereferences them. Availability and event times must be
timezone-aware and consistent. The independent authentication of those
receipts belongs to the future capture implementation, not this local file
format. No declaration in a JSON file is proof of external persistence.

`artifact_proof` is a receipt containing the exact official artifact body.
The validator finds the unique candidate in its `pitchers`/`tracked_picks`,
checks the locked quote and game, checks Path B fields against that same
pitcher, and replays frozen normalized inputs from the explicit tracked-quote
overlay. Its byte hash must match the operational and frozen byte hashes;
the proof's separate logical hash is checked with the existing canonical
payload helper. The operational source path must match the acquisition path;
the V2 proof keeps its separate canonical logical artifact path.

`market_proof` has:

| Field | Receipt body and validation |
| --- | --- |
| `snapshots` | List of individual receipts of original normalized snapshot rows. Require distinct provider/ID pairs, exact event/receipt times and valid odds; repeated delivery cannot add maturity. |
| `current_lines` | Receipt of an ID-keyed object of existing current-line rows. Resolve official bindings against the artifact and snapshots with the unchanged helper. |
| `heartbeats` | Receipt of the supplied heartbeat list; preserve existing freshness semantics. Empty lists do not manufacture a heartbeat; active polling evidence still follows the existing builder's row-freshness rules. |
| `windows` | Receipt of candidate/provider starts, candidate identity, official binding key and sidecar keys. Require those bindings to match the replay. |
| `read` | Receipt of `complete`, `reason_codes`, `window_start`, `window_end`, `expected_count`, `returned_count`. Require complete, no cap/error reasons, exact count conservation, cutoff equal to lock, and coverage from all provider/candidate window starts. |

All market receipts must be acquired by the lock. Exact replay uses the
unchanged V2 market builder with its existing 900-second default, then the
pure V2 evaluator and full proof builder. The regenerated proof must equal
the persisted proof. This catches mismatched counts, windows, scores, labels,
provider bindings, normalized features, observations and token hashes.

`agreement` is exactly `{status: known, label: ...}` and `preclose` is exactly
`{status: known, label: ..., score: ...}` for complete input acceptance. Values
must equal replay; their common source is `market_proof` and its enclosing
content digest. Incomplete states remain excluded with reasons, not default
neutral values. Mapping version is this schema plus the pinned code digest.
`decision_time` must equal the complete validated normalized-input object.

`path_b` contains the six fields listed by `PATH_FIELDS`, `status=known`, and
`source_artifact_sha256`. It must equal the artifact's fields, with valid
mode/boolean/count/source relationships. Coverage bucket is computed by the
existing helper; known fallback or known no-lineup states are retained.
`provenance` contains `completed_at`, `persisted_at` and `capture_run_id`;
original frozen insertion must precede completion and persistence before game.

## Manifest and later lifecycle

`reference_manifest()` returns an **inactive** local reference: schema/mode,
contract-file digest, original selector fingerprint/baselines, exact dependency
file digests, unchanged freshness configuration and null activation fields.
It reads only fixed repository files. The activation object contains
`activated_at`, `first_unobserved_slate`, `capture_sink`, `review_ref` and
`implementation_commit`. A populated declaration is validated for internal
consistency and forward boundaries only. It never activates capture or
establishes that the referenced approval actually occurred.

Each attachment is `{kind, envelope_sha256, identity, receipt}`. Kinds are
`consumption`, `seed`, `settlement`, `close`. Its receipt body contains the exact
locked quote/identity fields (`slate_date`, `normalized_pitcher`, `side`,
`game_time`, `locked_at`, `locked_k_line`, `locked_odds`, `locked_book`,
`locked_verdict`) and:

- Consumption: lock ID and consumption timestamp before game.
- Seed: explicit `result=null` and `recovery_status=original`; receipt after
  consumption and before game. Missing or contradictory recovery evidence fails.
- Settlement: result, recorded P&L and affirmative original provenance,
  acquired after game start. Win/loss can satisfy input candidacy; push/void
  remain visible and uncounted. No result is graded or repaired here.
- Close: close line, odds, provider/book, observed time and original CLV type;
  observation pregame and receipt after game start. Require the same quote
  source/book and reproduce the existing Gate C CLV bucket. Preserve the actual
  existing `price_and_line` spelling; no new bucket math is introduced.

These are typed research witnesses. A future capture proposal must prove its
exact mappings from ordinary published history/lock/close sources and preserve
the underlying immutable source evidence. Synthetic witness bodies and their
declared times do not establish that mapping for live data.

`inventory` contains each expected identity once with status and any failure
reasons. Missing captures remain visible; inconsistent inventory, conflicting
attachments and reused source IDs block candidacy. Identical retries coalesce;
differing content at the same identity is quarantined. Orphan attachments are
reported and block packet candidacy.

## Output meaning

`pregame_valid` is independent of settlement; `selector_match` can stay true
when a known frozen match lacks another required input. `eligible_input_candidate`
requires the pregame checks, declared forward activation, the unchanged rule,
and valid later attachments. It is **not** the formal audit counter and proves
none of the baseline reconciliation, sample/diversity or profitability gates.
Every result has `formal_prospective_credit=false`; the packet total is zero.

See the [implementation review](2026-09-04-forward-evidence-validator-review.md)
for the preserved negative-score V2 proof limitation and the next decision.
