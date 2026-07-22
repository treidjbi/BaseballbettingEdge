# Alt Picks Dependency-Aware V2 Design

**Date:** 2026-07-22

**Status:** Approved by Tyler; implementation plan drafted, implementation not started

**Approved bundle:** `pregame_alternative_pick_methodology_v2`

## Executive decision

Create a versioned v2 of the comparison-only Alt Picks methodology so a
nonessential pending family does not veto a lane whose result is already
provable. Keep every affirmative family vote strict, preserve the v1 ledger and
immutable frozen rows, and continue leaving official Picks, model behavior,
staking, notifications, locks, providers, artifacts, and accepted bets
unchanged.

V2 also replaces the current Preclose cross-check against a broad market
tracker with an exact candidate-bound evidence calculation. This fixes the
grain mismatch without adding a provider call, worker, table, or paid service.
One additive JSONB column is required on the existing state table so every V2
decision and provider binding remains auditable after the source artifact
advances. This is intentionally preferred to hiding provenance inside family
reason strings.

## Why v2 is required

The first normal slate proved that the deployed v1 sidecar is isolated and can
bind exact observations, but it also exposed two structural bottlenecks:

1. the evaluator makes the whole candidate pending whenever any one of Base,
   Anchor, Preclose, or Re-entry is pending, even when that family cannot change
   the relevant lane result; and
2. exact game/line/window observations are compared with
   `market_pick_evidence`, whose normal rollup spans a broader
   provider/pitcher/side window and can include other lines or events.

At the 2026-07-22 18:31Z checkpoint, the active artifact had 15 provisional
candidates. All 15 had Preclose pending, despite 12 carrying mature bound
observations. Eight rows had `provider_observations_missing`, eight had
`provider_evidence_conflict`, and one had both. The UI therefore showed zero
selected candidates.

A read-only replay of the preserved research corpus reproduced the documented
official-close anchors:

| Lane | Record | PnL / ROI |
| --- | ---: | ---: |
| Consensus Core | 106-46 on 152 | +32.603u / +21.45% |
| Re-entry Expansion | 42-38 on 80 | +5.982u / +7.48% |
| Combined, disjoint | 148-84 on 232 | +38.585u / +16.63% |

That historical construction did not require all four families to be complete.
Of 152 Consensus Core rows, 121 lacked reversal or volatility fields and 77 of
those already had two non-Preclose affirmative families. Of 80 Re-entry rows,
74 lacked those fields even though Preclose is not an input to the Re-entry
lane.

The historical totals remain exploratory official-close evidence. V2 must not
restore the historical scorer's optimistic missing-value defaults, claim those
totals as prospective performance, or backfill a T-30 record.

## Alternatives considered

1. Keep V1 unchanged and continue waiting. This preserves the strictest
   posture but knowingly leaves conclusively provable Consensus and Re-entry
   lanes hidden whenever an unrelated family is pending.
2. Coerce missing evidence to false/zero or remove provider checks. This would
   surface more rows quickly, but it recreates optimistic historical defaults
   and makes affirmative Preclose evidence unauditable. Rejected.
3. Create dependency-aware V2 with exact evidence and a separate prospective
   ledger. Chosen: it surfaces only logically proven lanes, keeps unresolved
   relevant inputs pending, and preserves V1 as an immutable control.

For persistence, a compact proof column on the existing bounded table is
preferred over a second table or encoded reason strings. It adds one small
migration while keeping the decision independently auditable and the runtime
simple.

## Scope and hard boundaries

V2 remains a read-only comparison surface.

- It selects only tracked, non-PASS opportunities already present in the exact
  current official artifact.
- It cannot select PASS rows, alternate lines, opposite sides, or new
  pitchers. Alternate lines from the same proven event may appear only as
  off-market context in the ephemeral evidence ladder.
- It does not change official verdicts, displayed Picks, lambda, EV, thresholds,
  staking, grading, calibration, notifications, operational locks, accepted
  bets, provider order, artifact source, dashboard source of truth, or
  retention.
- It uses only TheRundown official state and approved PropLine fallback or
  live-movement evidence. BoltOdds remains excluded.
- It adds no provider request, Render service, polling cadence, table, or paid
  infrastructure.
- `ALTERNATIVE_PICK_SELECTION_MODE=off` remains the code default and emergency
  stop.
- A separate `ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION` gate accepts only
  `v1` or `v2`. Unset or blank defaults to `v1`; an explicitly invalid value
  skips the isolated recorder cycle instead of silently selecting a version.
  Deploying V2-capable code alone therefore cannot create V2 rows while
  production remains in `record` mode.

## Version identities

V1 identities and fingerprint remain frozen forever:

- bundle: `pregame_alternative_pick_methodology_v1`
- Consensus: `no_drag_distinct_family_consensus_core_v1`
- Re-entry: `moderate_edge_quality_reentry_expansion_v1`
- fingerprint:
  `f8f7ccf652b8eda4860d07798bc4673920b0b9d727552bc7e2e6547d478b4579`

V2 receives new identities and a new manifest fingerprint:

- bundle: `pregame_alternative_pick_methodology_v2`
- Consensus: `no_drag_distinct_family_consensus_core_v2`
- Re-entry: `moderate_edge_quality_reentry_expansion_v2`
- fingerprint: calculated from the reviewed v2 manifest and frozen before any
  production row is written

Existing v1 rows remain in Supabase. V2 never updates, deletes, reconstructs,
or relabels them. V2 starts a new prospective record at zero.

The runtime bundle-version gate and public endpoint each select one explicit
version. They must not infer the active version from whichever rows happen to
exist most recently.

## Evidence-family contract

Base, Anchor, Preclose, and Re-entry continue to return exactly one state:

- `agree`: every required runtime-safe input exists and the predicate is true;
- `disagree`: every required runtime-safe input exists and the predicate is
  false; or
- `pending`: required evidence is missing, stale, immature, malformed, or
  mismatched.

Pending never becomes an affirmative vote. V2 changes only whether a pending
family is relevant to proving a lane result.

The family predicates and thresholds remain unchanged:

- Base: `strong_base_strict_plus_selective`
- Anchor: `market_anchor_strict OR (base_support AND market_anchor_core)`
- Preclose: `base_support AND strong_preclose_clv_proxy` using exact mature
  candidate evidence
- Re-entry: source FIRE plus `moderate_edge_quality_reentry`

### Primitive and composite truth rules

Every primitive is three-valued before families are composed. A missing,
malformed, stale, or unknown required input produces `pending`; ordinary
comparisons against missing values must never silently produce `false`.

- `base_support` is the unchanged Base family predicate.
- `market_anchor_strict` and `market_anchor_core` are evaluated independently
  from a valid parsed anchor-label payload. A present valid label list makes
  each primitive true or false; an absent or malformed required payload makes
  the affected primitive pending.
- `drag_high_edge` requires numeric edge,
  `drag_market_fade` requires a known model/market relationship, and
  `drag_fire_under_fade` requires known official verdict, side, and
  relationship. `drag_core` is their three-valued OR: true when any clause is
  true, false only when every clause is false, and pending otherwise. Within
  the FIRE-under-fade AND clause, any definitively false operand short-circuits
  that clause to false.

Anchor remains:

```text
anchor = market_anchor_strict OR (base_support AND market_anchor_core)
```

using normal three-valued short circuits. Strict agreement proves Anchor even
if Base or Core is pending. A proven Base-plus-Core agreement also proves it.
If strict is false and either Base or Core is definitively false, the Core
branch is false; Anchor is then false unless another unresolved clause can
still make it true. In particular, Base disagreement plus strict disagreement
proves Anchor disagreement even if Core is pending.

Preclose remains:

```text
preclose = base_support AND strong_preclose_clv_proxy
```

Base disagreement or a definitively non-strong Preclose predicate proves the
family false even if the other operand is pending. Both operands must
explicitly agree to produce agreement; every other unresolved combination is
pending.

## Dependency-aware three-valued logic

### No-drag

The Boolean formula remains:

```text
support = base_support OR market_anchor_strict
no_drag = support AND NOT drag_core
```

V2 evaluates it with short-circuiting three-valued logic:

- known `drag_core=true` makes `no_drag=false`;
- known `support=false` makes `no_drag=false`;
- known `support=true` plus known `drag_core=false` makes `no_drag=true`;
- otherwise `no_drag=pending`.

Here `support` is the three-valued OR of Base support and the strict Anchor
primitive. A Core-with-Base Anchor agreement is not strict support. Support is
false only when both inputs are definitively false. The explicit primitive
rules above govern missing inputs for both `support` and `drag_core`.

An Anchor agreement caused only by `market_anchor_core_with_base` is not
silently promoted into `market_anchor_strict` for this formula.

### Consensus Core

```text
consensus_core = no_drag AND family_count >= 2
```

- Select when `no_drag=true` and at least two families explicitly agree.
- Do not require remaining families to resolve once two affirmative votes make
  the lane true.
- Return not selected when `no_drag=false`, or whenever the maximum possible
  count after all pending families resolve is still below two, even if
  `no_drag` itself is pending.
- Otherwise remain pending.

### Re-entry Expansion

```text
reentry_expansion = reentry_support AND NOT no_drag
```

- Select when Re-entry explicitly agrees and `no_drag=false`.
- Preclose is not a dependency of this lane and may remain visibly pending.
- Return not selected when Re-entry explicitly disagrees or `no_drag=true`.
- Otherwise remain pending.

The lanes remain disjoint because Re-entry requires `no_drag=false` while
Consensus requires `no_drag=true`.

### Overall status

- `selected`: exactly one lane is proven true;
- `not_selected`: both lanes are proven false; or
- `pending`: neither lane is true and at least one could still become true when
  relevant evidence resolves.

Selected rows may therefore contain a pending chip for a nonessential family.
The UI must say which families confirmed the selection and must not render a
pending chip as disagreement or confirmation.

## Exact Preclose evidence

V2 derives Preclose inputs from the bounded observations already associated
with the exact candidate. The general-purpose `market_pick_evidence` rollup
remains useful for market-agreement research, but it is not an equality oracle
for the narrower Alt Picks window.

V2 Preclose does not read `market_pick_evidence` for counts, provider presence,
completeness, freshness, disagreement, reversal, volatility, or any other
decision input. The broad tracker may continue to be written for its existing
research consumers, but it cannot veto or affirm V2.

An observation may enter the V2 Preclose window only when it matches:

- Phoenix slate date;
- normalized pitcher;
- side;
- the tracked candidate's displayed official model K line and game time from
  the canonical artifact, replaced by the exact locked values only at freeze;
- canonical game identity, with exact game time unless an explicit
  artifact-declared source-line or source-snapshot ID maps the provider row to
  that canonical candidate;
- current candidate artifact identity, artifact `line_source_provider`, and
  verified provider-event/current-line binding through that explicit source
  mapping;
- an approved provider and supported book;
- a timestamp at or after `candidate_became_current_at` and no later than the
  evaluation checkpoint; and
- the existing native freshness policy.

The window resets if pitcher, game, side, model line, or artifact candidate
identity changes. A change to the official `line_source_provider`, its verified
provider event, or its official current-line binding also resets the candidate
window. Adding an optional sidecar binding does not reset official evidence;
changing that sidecar event discards only that provider's observations and
starts its provider-local window at the new binding time. The main live-state
card is never the canonical V2 line/time source. A new artifact payload/byte
SHA alone does not reset the window when the canonical candidate identity and
official binding are unchanged; both hashes are still recorded as provenance
for that evaluation cycle.

Raw provider snapshots do not carry an artifact SHA. V2 must therefore seed the
association from artifact-declared `source_current_market_line_ids`,
`source_snapshot_ids`, or provider event IDs to the underlying provider event.
After that event is proven, later snapshots may enter only with the same
provider event ID and exact pitcher/side/line semantics. V2 must not stamp the
current SHA onto an otherwise unbound semantic match after the fact. A
provider-reported start-time skew may be tolerated only through that explicit
event binding; without it, game-time mismatch remains pending.

The provider-specific movement key is:

```text
(provider, provider_event_id, normalized_pitcher, side,
 official_model_line, normalized_book)
```

Snapshot identities are provider-qualified `(provider, id)` tokens and are
deduplicated before evaluation. The same qualified ID with conflicting content
is malformed and leaves Preclose pending. Rows are ordered by
`(observed_at, id)`; the official line-source provider needs at least two
distinct observation IDs at two distinct timestamps, with at least one book
having two checkpoints. At a fixed line, decreasing American odds is movement
toward the selected side, increasing odds is movement away, and no change is
neutral, reusing the existing runtime odds-direction helpers. A reversal book
is a book whose consecutive non-neutral step directions change at least once;
`volatile_book_count` retains the current runtime definition equal to the
number of reversal books. These are definition-preserving calculations, not
new thresholds.

Provider/book rows are first calculated independently. The same normalized
book reported by both providers counts once after reconciliation. Matching
direction collapses to one contribution; contradictory direction for the same
book, or opposing provider-level majorities at the same checkpoint, is actual
provider disagreement and leaves Preclose pending. “At the same checkpoint”
means each participating provider's latest fresh observation under the native
freshness policy at or before the single V2 evaluation time; future rows are
excluded and a provider outside the native freshness limit is not treated as
current disagreement. Optional-provider absence is not disagreement.

The live layer already loads provider heartbeats for the broad market builders.
V2 receives those same in-memory heartbeat rows and reuses
`provider_heartbeat_health` / `effective_book_freshness` plus the existing
stale threshold. It performs no additional query or provider call. Under the
current native policy, fresh TheRundown and PropLine snapshots qualify by line
age; heartbeat-based freshness extension remains limited to providers already
recognized by the helper. V2 does not broaden that policy, the heartbeat
schema, or heartbeat writers. Missing or stale evidence from the artifact's
exact `line_source_provider` under that native policy leaves Preclose pending;
the official provider must never be inferred from the combined
`therundown_propline` posture label.

Preclose may resolve only when:

- at least two exact-line movement observations with distinct IDs and
  timestamps exist;
- the artifact's explicit `line_source_provider` has mature exact-event
  evidence that is fresh under the native policy, including heartbeat
  qualification only where the existing helper supports it;
- additional approved sidecar-provider evidence is included only when it has
  a verified exact-event binding and a mature fresh window; a bound-but-
  immature sidecar remains diagnostic and is not mandatory merely because the
  artifact posture is `therundown_propline`;
- any mature present provider disagreement, as defined above, is handled
  fail-closed;
- reversal and volatility counts are derived from the exact bounded window;
- a separate exact-event book-ladder view, built in memory from the same
  candidate-bound provider rows, supplies a real Boolean
  `best_is_off_market`; and
- the last observation is fresh and pregame.

Missing official line-source-provider evidence, conflicting mature providers,
malformed counts, stale exact-event evidence, or an identity mismatch leaves
Preclose pending. Missing values are never coerced to zero.

The exact-line movement window and exact-event book-ladder view are deliberately
different grains: movement/reversal counts use only the official model line,
while off-market detection may inspect other line points for the same exact
event, pitcher, side, and checkpoint. Neither may include another event or a
row that is only broadly matched by pitcher and side. The existing persisted
`live_market_display_state` remains the dashboard display source; V2's exact
book-ladder view is ephemeral selector evidence and does not change that UI.
The ephemeral ladder reuses the existing main-line, off-market-book, and
best-actionable helpers on that exact-event slice and must produce an explicit
Boolean; it never imports the broader persisted row as truth.

## Runtime and persistence flow

The existing live-layer placement remains unchanged:

1. fetch the canonical remote `today` artifact;
2. finish approved notification coordination;
3. finish live-market display and evidence writes;
4. finish operational lock processing and other existing shadow work;
5. run the optional Alt Picks sidecar within its existing five-second,
   no-retry, fail-open budget;
6. pass the already-loaded provider heartbeats and build the ephemeral
   exact-line and exact-event evidence views from the artifact plus
   already-fetched market rows;
7. evaluate V2 from those views; and
8. upsert only isolated V2 comparison state.

The existing `alternative_pick_selection_state` table can hold V1 and V2
because its uniqueness includes `bundle_id`. Add one bounded
`evaluation_proof jsonb` column to that table; do not add a new table. Every V2
row stores a schema-versioned compact proof containing:

- the official `line_source_provider` and canonical displayed/locked line and
  time;
- provider event IDs, current-line IDs, seed snapshot IDs, and exact movement
  and ladder observation IDs used;
- heartbeat freshness decisions for participating providers;
- the bounded normalized artifact inputs needed to recompute Base, Anchor,
  Re-entry, support, and drag: official/source verdicts, side, edge, adjusted
  EV status/value, no-vig gap, model/market relationship, line bucket, official
  odds/book, price sign, quality/timing, opportunity/leash/archetype,
  large-edge skepticism, and validated anchor labels;
- the decisive Preclose aggregates and score inputs: reconciled book count,
  toward/away counts, reversal/volatility counts, side-price direction,
  `best_is_off_market`, score, label, and score reasons;
- the primitive `support`, `drag_core`, and `no_drag` states;
- both lane tri-state results and the decisive family names; and
- the selector fingerprint and source artifact hashes already represented by
  the row.

The proof is application-bounded to 32 KiB. It stores provider-qualified seed,
first, last, direction-change-pivot, and latest-ladder observation tokens plus
counts and a SHA-256 of the full ordered qualifying token list; it does not
duplicate every unchanged polling row. `evidence_observation_ids` uses the
same provider-qualified decisive tokens, while `evidence_observation_count`
records the full qualifying count. An invalid or oversized proof leaves the V2
row pending instead of truncating decision evidence.

V1 rows may retain an empty proof. Because the existing V1 PostgREST upsert
omits the new column, the migration includes a narrow V1-only null-to-`{}`
compatibility trigger; it must not default a missing V2 proof or change shared
writer headers. V2 writes and the V2 endpoint fail closed if the proof is
missing, malformed, mixed-version, or inconsistent with the row.
The endpoint exposes only the sanitized decision summary needed by the UI, not
raw provider identifiers. Frozen V2 rows retain their proof immutably.

Only the explicitly gated bundle writes. After V2 activation, the ceiling
remains one provisional and one frozen row per eligible pick for V2; V1 rows
remain audit-only. Code deployment with the bundle gate left at its default V1
must create zero V2 rows. The public endpoint returns V2 only after V2 rows pass
production verification.

## Freeze and no-backfill rules

- V2 provisional rows may evolve before the exact operational lock.
- The first valid due-now or pregame missed-lock cycle freezes V2 from that
  exact artifact and checkpoint.
- A selected V2 row may freeze with a nonessential pending family.
- An unresolved relevant dependency freezes as pending.
- V1 frozen rows and games whose valid V2 freeze was missed are never
  reconstructed or converted.
- Activating V2 mid-slate does not create retroactive V2 picks for already
  locked or started games.
- Production activation occurs before the first relevant T-30 lock or is
  deferred to the next Phoenix slate; a legitimate no-candidate or partial
  no-backfill cycle is not mislabeled as infrastructure failure and cannot
  unlock the V2 UI. The exact official artifact, not V1 state coverage, is the
  source for candidate eligibility and T-30 preflight.

## UI behavior

The existing isolated Alt Picks tab remains the surface. No wager controls are
added.

For a selected row, the card shows:

- lane and provisional/frozen state;
- official pitcher, side, line, odds, book, and verdict;
- family chips with `agree`, `disagree`, or `pending`;
- confirmed-family count;
- exact checkpoint and evidence freshness; and
- comparison-only copy stating that official Picks are unchanged.

When a selected row has a pending nonessential family, copy must make the
distinction explicit, for example: `Selected with 2 confirmed families;
Preclose still pending.`

The page must not show stakes, units, PnL, Log Bet, Save Bet, notification
controls, FIRE-red styling, or language implying a recommended wager.

The endpoint uses an explicit version request. A request without a version
continues to serve V1 for backward compatibility; V2 is served only for
`bundle_version=v2`. Both responses include top-level `bundle_id` and
`selector_fingerprint`. The V2 browser adapter always requests V2 and accepts
the response only when both fields match its reviewed constants; otherwise the
entire comparison surface is unavailable, never partially rendered. Thus an
old cached client continues to request V1 from a new endpoint, while a new
client receiving V1 from an old endpoint rejects it. Browser validation must
allow a proven selected lane with zero Preclose observations when its persisted
decision proof shows that Preclose was a nonessential pending family.

## Failure handling

- Any V2 exception remains a sidecar-only no-op for that cycle.
- No fallback may synthesize a family agreement.
- An endpoint/version mismatch returns unavailable comparison state; it cannot
  retain partial counts or affect Picks or Results.
- Duplicate, malformed, mixed-version, wrong-fingerprint, or provenance-invalid
  rows are suppressed from the endpoint.
- `ALTERNATIVE_PICK_SELECTION_MODE=off` plus a live-layer redeploy remains the
  immediate recorder rollback. The previous reviewed Render and Netlify
  deploys remain available for full V1 surface rollback.

## Verification strategy

### Pure truth-table tests

- Consensus selects with Base and Anchor agreeing while Preclose is pending.
- Consensus remains pending with one agreement when another pending family
  could supply the second vote.
- Consensus is not selected when even all pending families cannot reach two,
  including when `no_drag` is pending.
- Re-entry selects with Re-entry agreeing, no-drag false, and Preclose pending.
- Re-entry remains pending when no-drag is unresolved.
- `drag_core=true` and `support=false` short-circuit no-drag correctly.
- Strict Anchor agreement short-circuits pending Base/Core; Base disagreement
  plus disproven strict/core branches proves Anchor disagreement.
- Base disagreement or raw Preclose disagreement short-circuits the composite
  Preclose family to disagreement.
- Missing primitive inputs stay pending and never become optimistic false.
- Pending never increases `family_count` or becomes an affirmative vote.
- The two lanes remain disjoint for every truth-table combination.

### Evidence tests

- An unrelated alternate line or adjacent event cannot contaminate exact
  candidate movement evidence; alternate lines from the same exact event may
  appear only in the book-ladder view.
- Broad `market_pick_evidence` books/counts do not veto a valid exact window.
- Broad `market_pick_evidence` is never read for V2 Preclose presence,
  freshness, completeness, conflict, or scoring.
- The official line-source provider must be represented.
- Absence of an optional fallback/sidecar provider does not by itself block an
  exact official-provider window.
- Provider start-time skew is accepted only with explicit artifact source-ID
  binding; an unbound time mismatch remains pending.
- Present provider disagreement, stale evidence, game-time mismatch,
  post-checkpoint observations, missing exact-event off-market Boolean, and
  malformed reversal/volatility fields all leave Preclose pending.
- Duplicate snapshot IDs with conflicting content, two providers disagreeing
  for the same normalized book, an adjacent event, and an alternate-line row
  entering the movement window each fail closed. A valid alternate line may
  enter only the exact-event ladder.
- Heartbeat freshness is taken from the already-loaded native provider-health
  input, not the broad tracker and not a new query.

### Version, persistence, endpoint, and UI tests

- V1 IDs and fingerprint remain byte-for-byte unchanged.
- V2 has a new canonical manifest and frozen fingerprint.
- V1 and V2 uniqueness cannot collide.
- V1 frozen rows remain immutable and are never backfilled into V2.
- V2 rows persist a valid evaluation proof, and frozen decision proof remains
  reconstructable after the source artifact advances.
- The endpoint returns only reviewed V2 rows after activation and suppresses
  mixed/unknown versions.
- Top-level bundle/fingerprint mismatches and old/new client combinations fail
  closed without partial cards or counts.
- Selected rows with a pending nonessential family render accurate chips and
  copy.
- A selected Base-plus-Anchor row with zero Preclose observations survives
  browser validation when its dependency proof is valid.
- Picks, Results, accepted bets, notifications, and operational locks remain
  unchanged when V2 succeeds, fails, or is off.

### Historical and captured-slate checks

- Reproduce the official-close `106-46`, `42-38`, and `148-84` legacy Boolean
  research anchors as comparator parity while keeping them clearly separate
  from V2 prospective results. The incomplete historical rows are not expected
  to pass V2's stricter affirmative-evidence rules.
- The originally planned 2026-07-22 18:31Z fixture is unavailable: the V1
  state preserved seven canonical and byte-hash pairs, but no matching raw
  artifact survived in `artifact_snapshots`, `published_pipeline_artifacts`,
  the repository, or local archives. Do not reconstruct it from the 5,259
  broad tracker rows, later mutable lines, close data, or later artifacts.
- Commit a synthetic golden fixture with mature exact official-provider
  movement and ladder evidence that affirmatively resolves Preclose, so the
  exact evidence path is tested independently of live captured rows.
- Before Production Gate A, commit a sanitized fixture from the next clean
  prospective normal slate. Capture the official `get-artifact` bytes while
  the artifact is current and before every eligible candidate's T-30, verify
  both raw-byte and canonical-payload SHA-256 against the contemporaneous
  published artifact row, and retain only artifact-declared snapshot/current-
  line IDs whose own timestamps do not exceed the checkpoint. The manifest
  must bind the raw fixture hash, official artifact hashes, capture timestamp,
  maximum source timestamp, and expected V2 outputs. If exact retention or
  binding fails, defer to another slate.
- Do not alter, reconstruct, or backfill any already-frozen V1 row. The future
  captured fixture starts the V2 prospective ledger at zero and contains no
  result, actual Ks, PnL, CLV outcome, accepted-bet, notification, or post-start
  input.

The synthetic fixture and future captured rows are deterministic regression
evidence, not current wagering advice or a promised production count after
later artifacts.

## Staged rollout

1. Add and review the bounded proof-column migration separately.
2. Apply the migration and verify the new column/default plus existing RLS,
   browser denial, service-role access, uniqueness, V1 writes, and frozen-row
   immutability before deploying any V2-capable runtime.
3. Implement the explicit bundle-version gate, V2 evaluator, endpoint
   handshake, and browser adapter with the bundle gate still defaulted to V1.
4. Run focused selector/evidence tests, full Python and Node suites, protected
   behavior checks, historical parity, and the synthetic exact-evidence replay.
5. Before applying the proof migration or merging either reviewed branch,
   capture and independently review the next clean prospective exact fixture
   under the gate above. Until it passes, all production steps remain closed.
6. Merge and deploy the live-layer code without changing official services or
   provider configuration; prove that deployment alone writes zero V2 rows.
7. Before the first relevant T-30 lock, change only
   `ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION` to `v2` through a full-list,
   cursor-paginated preserve-and-verify environment update, record whether the
   key was originally present or absent, redeploy the existing live-layer, and
   wait for a clean scheduled cycle. Defer to the next slate if any relevant
   lock has already occurred.
8. Verify bounded V2 provisional rows, expected lane decisions, zero duplicate
   keys, zero alternative notification events, and unchanged lock timing.
9. Deploy the backward-compatible endpoint handshake and V2 browser request
   only after the V2 rows pass that check. Unversioned requests must continue
   serving V1.
10. Verify desktop and mobile cards, selected-with-pending copy, and continued
   isolation of Picks, Results, and accepted bets.

Rollback reverses the gates in dependency order: restore the bundle key to its
exact pre-activation state (absent or V1), or set the recorder `off` for an immediate stop, obtain one clean V1
cycle with zero new V2 writes, and verify current-slate V1 coverage before
restoring the V1 UI. V1 rows missed while V2 was active are never reconstructed;
if current-slate V1 coverage is incomplete, the Alt comparison surface remains
unavailable until the next clean slate rather than presenting partial V1 as
complete. The backward-compatible endpoint may remain deployed because
unversioned requests serve the validated V1 handshake; a full endpoint rollback
remains available if that contract itself fails.

No step authorizes an official model, staking, provider, notification, lock,
artifact, or retention change.

## Acceptance criteria

The V2 design is complete only when:

1. a nonessential pending family cannot veto a conclusively proven lane;
2. unresolved evidence that could change a lane still keeps it pending;
3. every affirmative vote remains complete, runtime-safe, pregame, and exact;
4. Preclose uses exact candidate-bound observations rather than a mismatched
   broad-rollup equality check;
5. V1 identities and frozen rows remain unchanged and V2 starts at zero;
6. the Alt Picks tab can show prospective selections before games without
   altering official behavior; and
7. deployment evidence proves bounded state, no unexpected notifications or
   locks, and a clean rollback path.

## Non-goals

- promoting V2 into official Picks;
- changing model math, thresholds, staking, or units;
- adding betting actions or historical PnL to the Alt Picks tab;
- treating the `+38.585u` research anchor as guaranteed prospective
  performance;
- backfilling V1 or missed V2 checkpoints;
- changing provider order, strict mode, polling cadence, notification classes,
  lock behavior, artifact source, retention, or dashboard source of truth; or
- reviving BoltOdds.
