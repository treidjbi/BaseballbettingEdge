# Forward-only pregame research evidence contract

Date: September 4, 2026. Owner: Tyler + Codex.
Status: **Contract defined; capture inactive; prospective activation unset.**
Tyler approved defining this contract after the standalone adapter review.
This document does not implement a collector, validator, integration or release.

## Decision and controlling rules

Use a separate, immutable research envelope to preserve the official decision,
exact pregame market evidence and lineup attribution before outcomes exist.
Reuse existing artifact, lock and V2 evidence machinery. Do not modify V2
proofs, the canonical Gate C corpus or an old freeze to populate new fields.

This contract serves `expand_lean_low_line_capped_model_fade` only. The
[August 14 design](2026-08-14-selective-lean-prospective-audit-design.md)
continues to control its four-field rule, fingerprint, baselines, scoring and
review gates. The [September 4 adapter plan](../plans/2026-09-04-decision-time-research-adapter.md)
controls existing offline linkage. This document controls availability and
provenance for a future evidence version, `forward_pregame_evidence_v1`.
It does not reopen Alt V2's retired promotion paths or count agreement and
Preclose, which share observations, as independent corroboration.

The candidate remains exactly LEAN, line bucket `2.5-3.5`, relationship
`model_fades_favorite`, quality `capped`; fingerprint
`4e00a180e35fe75dc8889d47065a25c4351cb37ac55664eb42f01b77c07fd13a`.
Do not require favorable agreement, strong Preclose, or real Path B splits
to select a row. Those are attribution slices, not extra winning filters.
Weak/against/neutral/known-fallback examples must remain represented.

## Current evidence and the actual gap

The [captured adapter verification](../../research/evidence/2026-09-04-decision-time-adapter/verification.json)
contains 352 identities, 309 complete links and 19 linked frozen rule matches.
All 327 captured Preclose proofs are pending; formal credit is zero. These
are August 15–September 3 historical implementation checks, not an activated
sample. [The executed checks](../../research/evidence/2026-09-04-decision-time-adapter/checks.ipynb)
and [review](../../research/2026-09-04-decision-time-adapter-review.md) remain
the evidence; this contract makes no new live-health or predictive claim.

| Field family | Existing source and reuse | Missing proof this version must supply |
| --- | --- | --- |
| Decision and quote | Full immutable V2 `normalized_inputs`, official binding and consumed operational lock | Separate evidence-version ID and activation manifest; exact game/quote/lock and artifact-byte binding |
| Market agreement | Existing exact V2 Preclose counts and ordered observations; existing consensus/label semantics | Complete pre-decision acquisition window; distinguish observed neutral from missing evidence |
| Preclose proxy | Existing exact evidence builder, frozen proof and semantic validator | Mature official binding, complete bounded read, no late-arrival substitution; no optimistic scorer fallback |
| Path B | Exact official artifact pitcher fields emitted by `build_features.py` | Preserve those fields from the same decision artifact, instead of reading later dated archives |
| Workload | Frozen normalized inputs, including input status and risk buckets | Known pregame values with missingness retained, rather than actual postgame IP/pitch count |
| History and final CLV | Consumed lock, ordinary history seed, later exact history/close | Affirmative original-seed witness and separately versioned result/close attachment |

Critical risks are temporal leakage and identity substitution. High risks are
unknown-as-neutral/default coverage and changing the evaluated population
through missingness. Exact links alone address neither. Evidence completeness
must be reported for all frozen rule matches, including exclusions and losses.

## Time, identity and activation

All timestamps are explicit timezone-aware UTC instants. Slate date uses the
existing schedule's date, not a date inferred from UTC midnight. Let `L` be
the exact operational `locked_at`, `G` its recorded `game_time` and `F` the
research envelope's completion/persistence time.

- Require `L < G`, freeze checkpoint equal to `L`, and `L <= F < G`.
  Inputs, provider heartbeat evidence and snapshot acquisition receipts must
  be available by `L`; recording a deterministic calculation shortly after
  `L` does not permit inputs learned during that delay.
- For each observation retain source event time, trustworthy ingestion or
  acquisition time, source ID and payload digest. Require both event and
  availability times `<= L`. A vendor timestamp alone proves no availability.
  If a source lacks ingestion time, a preserved read receipt completed by
  `L` can prove availability. An export captured after the game cannot.
- Artifact generation and its acquisition receipt must be `<= L`. Preserve
  raw served bytes or an immutable byte-addressed copy, the byte SHA-256,
  issuer logical hash and representation separately. Never hash SQL JSONB
  serialization as if it were the served response. Tie the lock byte hash to
  those exact bytes and the full frozen proof.
- Candidate identity is evidence version + slate date + normalized pitcher
  + side, bound to game identity/time, line, odds, book, official provider,
  lock ID and byte hash. Conflicting games, duplicate tuple identities or
  source IDs reused across candidates quarantine all affected records.
  No latest/first winner, fuzzy pitcher, cross-line or best-price substitution.
- Timing must recompute to the existing `timing_bucket` value and agree with
  the frozen value. `pre_30` means **more than 15 and at most 30 minutes**
  before recorded game time; it is not any pregame or nominal T-30 job.
  Preserve later schedule corrections separately; do not retrospectively
  reclassify eligibility using a more convenient start time.

Activation needs a committed manifest containing this contract's digest,
selector fingerprint, implementation commit and dependency digests, reviewed
capture sink/read bounds, acceptance evidence, activation time and the first
fully unobserved slate date. **Both activation fields are currently null.**
No default of today, tomorrow, or August 15 is allowed.

Keep four separately labeled periods: original nomination through August 12;
August 13–14 freeze gap; original August 15+ audit/blocked history; and the
new evidence version's post-activation cohort. The existing audit date constant
does not change. The new cohort cannot include old adapter matches, pilots
already inspected for outcomes, recovered rows, or late backfills. Do not erase
earlier failures or silently pool acquisition regimes. A restart or material
contract change gets a new version, not a rewritten activation date.

## Envelope and immutable lifecycle

These are required logical fields for the future schema, not a new table or
an instruction to write a production artifact. Unknown values are null with
reason codes; zero and false require affirmative evidence. Reject non-finite
numbers, malformed enum values, invalid numeric types and mismatched quote values.

| Object | Required content |
| --- | --- |
| `manifest_ref` | Contract/evidence version, manifest digest, selector fingerprint, implementation and schema digests |
| `identity` | Tuple identity above, exact game identity/time, freeze time and lock ID |
| `decision_time` | Validated frozen selector inputs, price sign, timing, workload inputs/status/buckets; explicit official quote provider/book/line/odds/verdict |
| `artifact_proof` | Source path, generation/acquisition timestamps, immutable bytes reference, byte SHA-256, separate logical hash/representation |
| `market_proof` | Official and sidecar bindings, candidate/provider window starts, read bounds/completeness, acquisition receipts, observation IDs/digests/times, ordered-token digest, exact ladder and freshness evidence |
| `agreement` | Known/pending/invalid status, label or null, exact toward/away/book counts, contributing proof digest, mapping version |
| `preclose` | Known/pending/invalid status, original score/label/reasons, complete V2 proof and validation result; no replacement defaults |
| `path_b` | Known/pending/invalid status, mode, lineup-used flag/count, split source, real/fallback counts, derived coverage bucket and source-artifact digest |
| `provenance` | Completion/persistence receipt, capture run ID, recovery status/reasons, content digest |
| `research_status` | Selector match independent of outcomes; pregame completeness and all exclusion reasons; credit remains false before activation and later audit acceptance |

Store every tracked locked opportunity in the bounded capture, including
rule nonmatches, pending cases and failures; do not collect only selected or
profitable cases. Record a per-slate expected/observed/failed capture manifest
so missing rows cannot vanish from the denominator. Candidate-level failure
does not block official picks, grading or notifications.

Freeze the decision envelope once. Retries may return the identical content
digest; differing content for the same key is a conflict, never an upsert.
Lock consumption, original seed, settlement and close arrive as separate
append-only attachments referencing the frozen digest. They cannot mutate
the decision or cure missing pregame inputs. Capture after first pitch stays
diagnostic even if all values look plausible.

## Exact market agreement and Preclose

Use the existing exact V2 builder and proof validator at the fixed cutoff.
Require the recorded official provider binding to be mature: at least two
distinct qualifying IDs at distinct times, including a book observed at two
distinct times. Repeated transport deliveries are not independent evidence.
Preserve existing freshness, exact ladder, side/line/book/event, ambiguity,
reversal and conflict checks. The current builder defaults to 900 seconds
and its current recorder does not override that value; record the actual
configuration/code digest, and reject drift rather than changing this limit.

Full candidate/provider window coverage and completed pagination are required.
`snapshot_page_cap_reached`, truncation, missing window, immature official
provider, ambiguous alternate lines, stale evidence or unresolved provider
conflicts stay pending/invalid. Do not lift a cap, extend a lookback, increase
polling, or remove an ambiguity guard under this contract. A diagnostic can
identify the reason; collection changes need their own reviewed scope.

Only after exact evidence is valid, apply the existing consensus semantics
to its same-candidate counts and map through the tracker vocabulary:

| Known toward count | Known away count | Consensus / agreement |
| --- | --- | --- |
| Positive | Positive | `mixed` / `market_mixed`, even if counts differ |
| Positive | Zero | `toward_pick` / `market_with_model` |
| Zero | Positive | `away_from_pick` / `market_against_model` |
| Zero | Zero | `none` / `market_no_signal`, only with mature complete observed coverage |
| Missing or invalid | Any | Null label; pending/invalid, never `market_no_signal` |

This is a versioned mapping of existing logic to exact evidence, not a call
to the broad post-grading tracker with history overlays. Preserve the count
inputs so the mapping is independently reproducible. Agreement and Preclose
reference the same market-proof digest and are explicitly dependent.

Accept all valid Preclose labels: `strong_preclose_clv_proxy`,
`medium_preclose_clv_proxy`, `weak_preclose_clv_proxy`. Reuse existing scoring
math and weights; require all inputs that prevent missing-to-zero/clean
defaults. Never run the permissive historical scorer on incomplete final
archives to supply a frozen label. An unchanged score is not proof of an
unchanged input window. Final CLV is never a pregame input.

## Path B, workload and official provider

Read Path B from the exact decision artifact: `batter_handedness_mode`,
`lineup_used`, `lineup_count`, `lineup_split_source`,
`lineup_real_split_count`, `lineup_path_a_fallback_count`. Bind its pitcher to
the frozen candidate and byte hash. Mode alone is insufficient attribution.
Counts are nonnegative integers. When a lineup is used, real plus fallback
must equal lineup count; source must agree with counts. With no lineup used,
the explicit no-lineup state and zero counts are known missing-lineup context,
not missing fields and not claimed real-split coverage.

Reuse `path_b_coverage_bucket` after checking completeness: known real/mixed
coverage maps to `path_b_real_or_mixed`; known Path B without real splits to
`path_b_no_real_splits`; known Path A to `path_a_or_unknown` while retaining
`status=known` and its explicit mode. Unknown mode/counts remain pending, even
though the legacy helper returns that same last bucket. Preserve all valid
fallback states; do not promote only real-split rows.

Use frozen workload status, last pitch count, rest, opener/starter-mismatch
flags and opportunity/leash buckets. Preserve the approved helper's buckets;
unknown required fields remain pending. Actual IP, batters faced and pitch
count from a box score belong only in the later outcome attachment.

Official provider comes from the exact validated quote binding. A composite
posture such as `therundown+propline` is not a quote provider. Sidecar identity
and contributing books stay separate. Current allowed production sources and
fallback order are unchanged; retired BoltOdds is never admitted by this
contract. An unexpected source remains excluded pending review.

## Consumption, recovery, settlement and costs

Consumption proof must reference the exact lock and its capture time; no
consumption timestamp is invented. To affirm an ordinary original seed,
preserve a receipt of the exact ungraded history row, available before game,
linked to the consumed lock and immutable artifact bytes. This is research
provenance only; it does not add a field to or rewrite official history.
Missing original-seed witness means `recovery_status=unknown`; a documented
repair/recovery means `recovered`. Neither earns formal credit. Absence of a
recovery flag is not `original`. Kumar's old unconsumed lock remains excluded.

After grading, attach exact ordinary history result/P&L, history artifact
digest, capture time and source/recovery classification. Allow win/loss into
the existing formal counter only; pushes/voids remain visible outside its
75-row win/loss floor. Attach final-CLV context with explicit close provenance
and the existing bucket definition, independently of selection. Missing or
conflicting close attribution blocks the corresponding required evidence;
it must not relabel the bet-time quote or its provider/book.

Preserve official recorded stake/P&L separately from fixed-rule research unit
returns. The existing audit's score and frozen baselines are unchanged.
Recorded odds include the quoted payout terms, but are not measured fill
slippage, exchange fees or allocated operating costs. Report those cost fields
as unknown unless independently documented. No fully costed profit claim is
permitted without that evidence; no new hypothetical fee or staking policy is
silently incorporated into the existing promotion statistic.

## Readiness, acceptance and bounded next work

The August 14 gates remain: 75 eligible graded rows, 20 UNDER, 10 plus-price,
positive prospective and latest-14-slate P&L, complete provider/agreement
attribution, no negative mandatory slice of at least 10 rows, and positive
leave-one-slate-out minimum P&L. Preserve both nomination baselines and all
listed slices. Do not borrow counts from Alt V2 or another selector. Report
the actual dates in the existing latest-14 calculation; do not imply a full
14-slate window when fewer dates exist. Readiness permits review only.

The next bounded deliverable is an **offline envelope validator and synthetic
acceptance packet**, reusing captured sources for negative cases. No network,
writer, runner import, schema migration or live collector is needed for that
step. Implementing it and connecting a pregame capture are separate from this
documentation change. Required acceptance cases:

| Case | Expected result |
| --- | --- |
| Complete, activated, unique pre_30 envelope; later ordinary result/close | Eligible-input candidate, subject to unchanged selector, baseline and audit gates |
| Known against/mixed/neutral agreement; weak proxy; known Path A/no-real-split context | Retained as valid attribution; no positivity filtering |
| Valid pilot before activation; missing activation fields | Diagnostic only; zero credit |
| Old 19 linked matches or old 327 pending proofs | Zero credit; no retroactive activation or filled labels |
| Source event pre-lock but receipt post-lock; future artifact; completion post-start | Temporal exclusion |
| 15-minute or 30-minute-plus timing boundary | Excluded from pre_30; test 15/30 exactly and just either side |
| Missing counts defaulted to no-signal, missing Path B mode/counts, negative/mismatched lineup counts | Attribution exclusion |
| Duplicate observation deliveries, insufficient distinct times, capped pages, stale heartbeat or provider conflict | Pending/invalid with original reason; no maturity fabricated |
| Wrong quote/book/game/provider, logical-versus-byte hash substitution, duplicate/reused identity | Quarantine; no nearest or newest match |
| Mutating result/P&L/final-CLV/archived features | Frozen selector result, pregame completeness and digest unchanged |
| Seed provenance unknown/recovered; unconsumed lock | No formal credit even with an official box score |
| Retry identical envelope, then retry different body at same key | Identical accepted idempotently; different quarantined; original preserved |
| Rule, baseline, helper/config digest or source-schema drift | Block readiness; explicit version/review required |

Only after offline acceptance should a capture integration packet name its
exact sink, immutable-write behavior, read bounds, measured bytes/rows/time,
error isolation, reuse of existing fetched inputs, release/rollback steps and
activation manifest. Reuse the existing per-cycle artifact/snapshot/heartbeat
inputs and candidate windows; a second broad raw market collector is not the
default. No new provider requests, higher cadence, paid service or retention
change is authorized. Cap-hit diagnosis must precede any proposed read change.

Use a new research evidence directory for offline packets. Do not add fields
to the strict V2 proof schema or repurpose its immutable ledger. The physical
hosted sink is deliberately not activated or selected by this contract;
integration must justify it against the existing tracker map and cost/risk
register. A missing sink is not permission to write the production artifact.

Retain operational/integrity deltas, the adapter and frozen controls. Pause
repetitive promotion scoreboards as an attention recommendation while these
structural gaps persist. Revisit after offline acceptance and a bounded capture
proposal, or a documented evidence correction—not merely count growth.

## Implementation references inspected

Source inspection is pinned to repository commit `2ea6fe87`:

- [Selective audit constants, critical fields and gates](../../../analytics/diagnostics/selective_lean_prospective_audit.py)
- [Exact V2 market windows, maturity and evidence](../../../market_infra/alternative_pick_preclose_v2.py)
- [Existing recorder inputs and default freshness call](../../../market_infra/alternative_pick_recording_v2.py)
- [V2 full proof validator](../../../market_infra/alternative_pick_evaluation_proof_v2.py)
- [Consensus semantics](../../../market_infra/market_evidence.py)
  and [agreement labels](../../../analytics/diagnostics/market_agreement_tracker.py)
- [Timing and proxy helpers](../../../market_infra/alternative_pick_selector.py)
- [Official lineup fields/count semantics](../../../pipeline/build_features.py)
  and [Path B slice helper](../../../analytics/diagnostics/strong_base_decision_lab.py)
- [Existing tracker map](../../research/market-tracker-map.md),
  [cost ledger](../../provider-cost-ledger.md),
  [risk register](../../operational-risk-register.md)

Only documentation changes accompany this contract. No test results are
claimed for its future validator or collector. The adapter's 185 passing tests
remain the separate prior implementation result. During this contract review,
the saved adapter packet was rebuilt in memory and matched exactly, including
its source-file hashes and zero formal credit. Contract/brief/plan links and
the documentation diff were checked; no historical evidence was rewritten.
