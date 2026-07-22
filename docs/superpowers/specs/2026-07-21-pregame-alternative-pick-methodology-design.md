# Pregame Alternative Pick Methodology Design

**Date:** 2026-07-21
**Status:** Tasks 1-6 review-clean and merged at `3a7fe7c5`; isolated record mode and Alt Picks UI deployed, first-normal-slate row/freeze proof pending
**Bundle ID:** `pregame_alternative_pick_methodology_v1`

## Executive decision

Add a same-day **Alt Picks** view to the middle dashboard tab so Tyler can
compare the official mainline picks with a separate, promising alternative
selection methodology before games begin.

The alternative methodology has two deliberately disjoint lanes:

1. **Consensus Core** selects a no-drag pick only when at least two distinct
   evidence families support it.
2. **Re-entry Expansion** selects a moderate-edge quality re-entry only when it
   is outside the no-drag population.

The official Picks tab, official artifact, displayed verdicts, grading,
staking, notifications, locks, provider order, and accepted-bet flow remain
unchanged. Alt Picks is a prospective comparison surface, not a production
model promotion.

## Production rollout handoff (2026-07-21 Phoenix)

Tasks 1-6 are independently review-clean and merged to `main` at `3a7fe7c5`.
The frozen selector manifest fingerprint is
`f8f7ccf652b8eda4860d07798bc4673920b0b9d727552bc7e2e6547d478b4579`.
Migration `supabase/migrations/20260721222627_alternative_pick_selection_state.sql`
is applied with RLS, browser-role denial, uniqueness, and both frozen-row
triggers directly verified. The code default remains `off`; Tyler-approved
`record` mode is live only on `bbe-live-layer` deploy
`dep-d9g2nsmrnols739u3h8g`. Netlify deploy
`6a602de17d040836c1641df0` serves the sanitized endpoint and Alt Picks UI.

The first record-mode tick at `2026-07-22T02:40:39Z` correctly produced no rows
because no unstarted games remained. No prospective production sample is
claimed until a normal slate produces valid exact-lock frozen rows. Nothing in
this rollout changes official picks, model math, thresholds, staking,
notifications, operational locks, provider order, source-of-truth rules, or
accepted-bet behavior.

The final review found and fixed five edge contracts: valid literal-null
no-lane supporting rows had been suppressed; absent `best_is_off_market`
could default to a qualifying value; PASS/ineligible rows could reach
persistence; pending-only rows could receive healthy-empty copy; and blank or
missing no-lane identity could be coerced into null.

## Product intent

The view should answer three questions quickly:

- Which official same-day opportunities does the alternative methodology
  select?
- Which distinct, de-duplicated evidence families agree or disagree on each
  selection?
- Was the selection still provisional, or was it frozen before first pitch?

This is intentionally more useful than another historical report. Historical
analysis continues in the research workflow; the app shows only today's
prospective alternative choices and their evidence.

## Exploratory official-close baselines

The locked research corpus was rescored with the source-compatible incremental
three-decimal unit ledger. These Gate C rows are `official_close` research
rows. Preclose and large-edge fields may therefore include market information
observed after T-30. That is timing leakage rather than result leakage, but it
means these totals are not checkpoint-equivalent T-30 performance.

| Portfolio | Full clean sample | Full PnL / ROI | Current-provider sample | Current-provider PnL / ROI |
| --- | ---: | ---: | ---: | ---: |
| Consensus Core | 106-46 on 152 | +32.603u / +21.45% | 33-9 on 42 | +14.191u / +33.79% |
| Re-entry Expansion | 42-38 on 80 | +5.982u / +7.48% | 14-8 on 22 | +7.235u / +32.89% |
| Combined, disjoint | 148-84 on 232 | +38.585u / +16.63% | 47-17 on 64 | +21.426u / +33.48% |

Displayed totals round only after the machine ledger is complete: `+32.60u`,
`+5.98u`, `+38.59u`, `+14.19u`, `+7.24u`, and `+21.43u`. The machine values
above are offline official-close parity anchors so a future one-cent display
difference is not mistaken for scoring drift. They are not prospective
performance promises, promotion gates, or the starting T-30 record. The T-30
record starts at zero when frozen prospective collection is activated and is
never backfilled from these rows.

## Versioned selector contracts

The alternative bundle gets new identities. It must not mutate the frozen
no-drag v1 selector, fingerprints, baselines, or prospective counter.

- Bundle: `pregame_alternative_pick_methodology_v1`
- Consensus selector: `no_drag_distinct_family_consensus_core_v1`
- Expansion selector: `moderate_edge_quality_reentry_expansion_v1`

Implementation should expose the predicates through a small pure, tested
module shared by the prospective evaluator and the research diagnostics. The
runtime path must not maintain a second, subtly different copy of the selector
logic.

### Frozen field and fingerprint manifest

Before implementation can write a prospective row, v1 must include a
machine-readable selector manifest and golden truth table. The manifest freezes
field precedence, normalization, thresholds, null behavior, formulas, and
canonical fingerprint serialization.

| Contract | Required prospective inputs |
| --- | --- |
| Candidate identity | Phoenix slate date, game identity/time, normalized pitcher, side, official model K line, supported provider posture, tracked status, current artifact path/SHA, and evaluation time |
| Base and drag | Display-verdict precedence; side; line bucket; edge; adjusted EV; model/market relationship; no-vig gap; quality level; timing bucket derived at evaluation; runtime-derived leash/opportunity and pitcher-archetype buckets |
| Market anchor | Exact `market_anchor_selector.labels` from the official artifact, including explicit absence versus missing metadata |
| Preclose | Base inputs plus price sign, movement direction or toward/away counts, book count, broad confirmation, off-market flag, reversal count, volatility count, snapshot identities, first/last observation times, and evidence freshness |
| Re-entry | Source-FIRE verdict precedence, side, model/market relationship, quality level, edge, adjusted EV, no-vig gap, and large-edge-skepticism flag |

Display verdict precedence is `display_verdict`, `locked_verdict`,
`actionable_verdict`, `current_verdict`, then `verdict`. Source-FIRE precedence
is a FIRE-valued `raw_verdict`, then FIRE-valued
`quality_actionable_verdict`, then the display precedence. V1 adjusted-EV
precedence must reproduce the legacy source-compatible truthy-or contract
across `locked_adj_ev`, `adj_ev`, and `ev`; any later cleanup requires a new
selector version and new offline parity anchors.

`result`, win/loss, PnL, final CLV, closing price/line, and actual postgame
opportunity are forbidden selector inputs. Historical result/tracked fields
may filter the offline scoring population only; they are not part of any live
family predicate.

Missing required values return `pending` before any legacy scorer is called.
In particular, missing reversal or volatility counts must not be coerced to
zero and awarded a low-volatility point.

The fingerprint is SHA-256 of UTF-8 canonical JSON with sorted keys, compact
separators, explicit nulls, normalized lowercase enums, and decimal thresholds
stored as strings. Its payload includes the bundle and selector IDs, complete
field precedence/null rules, family predicates, portfolio formulas, and timing
contract.

## Eligible universe

An alternative candidate must be an exact current-day official-artifact pick
that satisfies all of the following:

- the canonical artifact date is today's Phoenix slate date;
- the official row is tracked and its current displayed verdict is not `PASS`;
- pitcher, side, K line, game, and source-artifact hash match the canonical
  artifact exactly;
- the game has not started;
- all inputs used for an affirmative family vote were observed no later than
  the evaluation checkpoint; and
- provider evidence is TheRundown official state plus approved PropLine
  fallback/live-movement sidecar evidence only.

The evaluator must not search PASS rows, alternate lines, opposite sides, or
retired BoltOdds rows for new bets. It selects from the same official
opportunity universe so the comparison remains understandable.

## Distinct evidence families

One family can cast at most one vote. Correlated labels inside a family are not
extra votes. "Distinct" is an implementation de-duplication rule, not a claim
of statistical independence: Base, Anchor, Preclose, and Re-entry still share
some model and market inputs. The family count is an interpretable selection
contract, not six or seven independent model votes.

### 1. Base selection

`base_support` is the source-compatible result of
`strong_base_strict_plus_selective` for the row.

Strict runtime core and selective LEAN are alternate branches of the same base
family. They never count as two votes.

### 2. Market anchor

`anchor_support` is true when either:

- `market_anchor_strict` is true; or
- `base_support` and `market_anchor_core` are both true.

Strict and core anchor labels are one market-anchor family. They never count as
two votes.

### 3. Preclose market confirmation

`preclose_support` is true only when `base_support` is true and the existing
runtime-safe `preclose_strong` contract is satisfied by current, pregame
market evidence.

At least two valid observations associated with the current candidate identity
are required before this family can agree. Raw market snapshots do not carry an
artifact SHA, so a derived row's later-applied SHA is not sufficient proof.

The enforceable association contract is:

- exact Phoenix slate/game, normalized pitcher, side, official model line, and
  supported-provider identity;
- two distinct snapshot IDs/timestamps observed after that exact candidate
  identity first became current and no later than the checkpoint;
- reset the evidence window if side, model line, game, or pitcher identity
  changes;
- require the last observation to pass the existing freshness policy; and
- store the bounded observation IDs/count plus first/last observation times in
  the alternative row.

Until that contract is satisfied, Preclose is `pending`, not `disagree`.

### 4. Moderate-edge quality re-entry

`reentry_support` is true when the existing Gate F FIRE re-entry contract
includes the `moderate_edge_quality_reentry` label using only fields available
at the checkpoint.

Any research-only or postgame field is forbidden from prospective evaluation.
If runtime parity cannot be proved for a required input, the family is
`pending` and cannot qualify a pick.

## Portfolio membership

The source-compatible no-drag predicate is:

```text
no_drag = (base_support OR market_anchor_strict) AND NOT drag_core
```

The distinct-family count is:

```text
family_count = count_true(
  base_support,
  anchor_support,
  preclose_support,
  reentry_support
)
```

The two lane predicates are:

```text
consensus_core = no_drag AND family_count >= 2
reentry_expansion = reentry_support AND NOT no_drag
```

Because the expansion lane requires `NOT no_drag`, a pick cannot appear in
both lanes. If required no-drag inputs are missing, the evaluator cannot prove
that an expansion is outside no-drag; that candidate remains `pending`.

## Evidence states

Each family returns one of three states:

- `agree`: all required runtime-safe inputs exist and the predicate is true;
- `disagree`: all required runtime-safe inputs exist and the predicate is
  false; or
- `pending`: evidence is missing, stale, mismatched, or not yet mature.

The UI must never render `pending` as model disagreement. The stored row keeps
both the normalized state and compact reason codes so data-quality issues can
be distinguished from genuine negative evidence.

Selection identity is explicit. `selected` requires an approved lane and its
matching selector. `not_selected` requires the literal pair `lane: null` and
`selector_id: null`; `pending` may carry either that literal pair or a valid
lane/selector pair. Blank, whitespace, missing, or mixed pairs are invalid and
suppressed rather than coerced. PASS or otherwise ineligible candidates remain
outside the persisted universe.

Preclose can resolve only when exact, fresh, same-cycle live-display evidence
for the candidate supplies a real boolean `best_is_off_market`. Missing or
mismatched evidence leaves preclose `pending`; it never defaults to safe or
qualifying. A pending-only UI state likewise never claims evidence is healthy.

## Pregame timing and freeze

The evaluator runs at the end of each existing `bbe-live-layer` cycle, after
the approved notification and operational-lock steps in that cycle.

This means **after T-30 processing, not after the slate**:

1. Before the T-30 checkpoint, the evaluator may upsert a `provisional` row as
   the official artifact and market evidence change. A provisional row must
   match the latest canonical artifact SHA exactly.
2. The first pregame cycle that writes or observes the immutable operational
   lock row freezes the alternative selection from the same artifact and input
   snapshot used in that cycle.
3. `status_at_capture=due_now` is an on-time freeze. Because a 10-minute cycle
   can skip the five-minute operational grace window,
   `status_at_capture=missed_lock` may also freeze while the game is still
   pregame, but it is stored and displayed as a late checkpoint.
4. The row stores `should_lock_at`, actual `frozen_at`,
   `minutes_until_start`, lock status, lock dedupe key, and the lock/artifact
   SHA. UI copy uses `Frozen T-28` or `Frozen T-21 (late)`, not a blanket
   `Frozen T-30` label.
5. Selection and provenance columns on a frozen row are immutable and remain
   visible before first pitch. Later artifact publication does not invalidate
   a correctly linked frozen row.
6. Post-slate research joins outcomes to the frozen identity outside this
   table. Grading never mutates or reconstructs the frozen choice.

At the exact current-cycle lock, incomplete or immature evidence is frozen as
`pending` with its reason codes rather than guessed into a selection. That
pending capture is just as immutable as a selected frozen row. The evaluator
never reconstructs a missed freeze later in pregame or after start.

A freeze is valid only when the artifact used by that evaluator cycle, the
operational lock row, and the market-evidence window agree on slate/game,
pitcher, side, model line, and the lock row's source-artifact SHA. If the
sidecar misses that first valid lock cycle, it does not reconstruct a frozen
selection from a later artifact. If no valid pregame freeze is observed, the
evaluator records a missed-freeze reason and never backfills after game start.

## Architecture

### Pure evaluator

A pure evaluator accepts:

- the canonical official pick row;
- the exact official artifact SHA-256;
- normalized live market evidence carrying the bounded candidate-identity
  observation window;
- the Phoenix evaluation timestamp and scheduled start time; and
- relevant operational-lock evidence.

It returns family states, lane membership, compact reason codes, checkpoint
state, and a deterministic selector fingerprint. It performs no database or
network writes.

### Optional live-layer sidecar

The existing live-layer entrypoint invokes the evaluator only after its current
notification, market-state, and lock-ledger responsibilities complete.

- Feature flag: `ALTERNATIVE_PICK_SELECTION_MODE=off|record`
- Default: `off`
- Any exception is caught, logged without secrets, and treated as a no-op.
- The sidecar uses inputs already built in the cycle, performs no new provider
  call, has a five-second total wall-clock budget with no retry, and trips a
  per-cycle circuit breaker after its first failure or timeout.
- Failure cannot roll back or alter notifications, locks, official artifacts,
  or the live-market display state.
- No new Render service or paid worker is introduced.

This placement gives the evaluator the freshest approved pregame evidence at
the lowest operational cost while preserving a fail-safe boundary.

The implemented recorder remains inactive under its default. In `record` it
starts only after the existing notification, live-state, operational-lock,
timing, and shadow-market work has succeeded. Its five-second total sidecar
budget has no retry; its first timeout/read/evaluation/write failure ends only
the alternative work for that cycle and leaves the normal process successful.

### Isolated Supabase state

Create a small additive table, proposed as
`alternative_pick_selection_state`, with one row per pick/checkpoint rather
than one row per family.

Minimum identity and provenance fields:

- `slate_date`
- normalized pitcher/game/side/line identity
- `bundle_id`, `selector_id`, and selector fingerprint
- `checkpoint` (`provisional` or `frozen_pregame`)
- lane membership and family-state JSON
- official verdict, odds, book, and display-safe matchup fields
- `source_artifact_path`, `source_artifact_sha256`, and artifact generation time
- operational lock dedupe key, lock status, scheduled/actual freeze timestamps,
  minutes until start, and compact reason codes
- bounded evidence observation IDs/count plus first/last timestamps

Uniqueness:

```text
(slate_date, game_identity, normalized_pitcher, side, bundle_id, checkpoint)
```

`provisional` may be updated before freeze. `frozen_pregame` is insert-once and
all of its columns are immutable; conflicts do nothing. The expected ceiling is
two rows per eligible pick per day. Row Level Security is enabled, direct
anonymous browser reads are denied, and no retention deletion is approved by
this design.

The additive migration is
`20260721222627_alternative_pick_selection_state.sql`; it is applied to
Supabase with its RLS and trigger contract verified. It deliberately keeps two hash domains: canonical-payload
`source_artifact_sha256` proves a provisional row matches the published
artifact, while exact fetched-byte `lock_artifact_sha256` / lock source hash
proves the frozen operational-lock link. Neither domain is interchangeable.

### Sanitized Netlify endpoint

A server-side Netlify function reads only the current Phoenix slate and
returns an explicit display allow-list. Provisional rows must match the latest
canonical artifact SHA. Frozen rows instead must match an existing immutable
operational-lock row on lock dedupe key, slate/game, pitcher, side, line, and
the lock row's source-artifact SHA. A later refresh SHA may differ without
hiding the frozen selection; the response marks that the artifact advanced
after freeze.

The browser never receives service-role credentials, internal error payloads,
or unrelated historical state. The existing official artifact adapter and
live-market endpoint remain unchanged.

The deployed endpoint reads current-Phoenix-slate state only with server-side
service-role credentials, validates the exact `today`
artifact key and approved provider/publication posture, and returns a strict
sanitized allow-list. Invalid, stale, malformed, foreign-selector, or
unlinked rows are suppressed; missing configuration or read failures return a
stable unavailable response without internal details.

### Dashboard adapter

The Alt Picks fetch is isolated and fail-open with respect to the rest of the
dashboard. If it fails, the official Picks and Results tabs continue normally.
No alternative state is merged into official pitcher objects or accepted-bet
records.

## Alt Picks UI

Replace the middle **History** navigation item with **Alt Picks**. Keep the
left **Picks** tab and right **Results** tab unchanged.

The Alt Picks view contains:

1. a compact header with slate date, last refresh, prospective-only labeling,
   and provisional/frozen counts;
2. a **Consensus Core** group first;
3. a **Re-entry Expansion** group second; and
4. a collapsed summary of not-selected and pending candidates.

Each selected card shows:

- pitcher and matchup;
- the official side, line, odds, and book;
- the official mainline verdict for direct comparison;
- the alternative lane;
- Base, Anchor, Preclose, and Re-entry chips in `agree`, `disagree`, or
  `pending` state;
- `Provisional`, actual `Frozen T-N`, or `Frozen T-N (late)` status; and
- evidence/artifact freshness.

Visual treatment is neutral blue/teal. Do not use FIRE red, stake units,
`Bet now`, `Log Bet`, or push-notification controls. On a 390-pixel mobile
viewport, identity, official pick, lane, and freeze status remain above the
fold; evidence chips wrap and supporting detail moves into the existing detail
sheet pattern.

Historical PnL and prior slates are intentionally absent from this tab.

The deployed UI is comparison-only: it does not
merge alternative rows into official pitcher or accepted-bet state and exposes
no wager, Log Bet, units/stake, PnL/history, or notification controls. The
legacy `?tab=history` route canonically redirects to `?tab=alt`; Picks and
Results remain separate.

## Failure and empty states

- Endpoint/evaluator unavailable: **Alternative methodology unavailable. Main
  picks are unaffected.**
- Current artifact has no matching provisional evidence: **Waiting for
  current-slate evidence.** Suppress the stale provisional row. A frozen row
  remains eligible only through its exact immutable operational-lock link.
- No qualifiers with zero pending rows: show a healthy empty state and
  candidate counts; do not imply a pipeline failure.
- Pending-only supporting rows: say the alternative evaluation is still
  pending; never call the evidence healthy.
- Family evidence incomplete: show `pending` with a short reason.
- Freeze missed: show the provisional audit state as missed/unfrozen; do not
  synthesize a frozen choice later.

## Testing strategy

### Selector and ledger tests

- Golden rows for each family and both lane predicates.
- Family de-duplication tests.
- Missing-input tests that prove `pending` cannot qualify a pick.
- Disjoint-lane property tests.
- Offline official-close parity anchors using the source-compatible
  incremental three-decimal scorer, clearly separated from the empty
  prospective T-30 ledger.
- Field-level manifest, canonical fingerprint, and prospective checkpoint
  golden fixtures.
- Selector and fingerprint regression tests proving no-drag v1 is unchanged.

### Timing and persistence tests

- Provisional upsert before T-30.
- Provisional exact-current-artifact-hash rejection.
- Current-line snapshot association, two-observation maturity, identity-reset,
  and missing-field completeness tests.
- On-time `due_now` and late `missed_lock` pregame freezes with actual timing.
- Frozen-row immutability and idempotent retries.
- Later artifact refresh preserves only an exactly lock-linked frozen row.
- No post-start freeze or postgame backfill.
- Sidecar exception and timeout tests leave notification, lock, and
  live-display writes and process success intact.
- Row-volume ceiling of two state rows per eligible pick/day.

### Endpoint and UI tests

- RLS denies direct anonymous table reads.
- Endpoint returns only allow-listed current-slate fields.
- Endpoint suppresses stale provisional hashes and invalid frozen lock links,
  while preserving a valid frozen row after a later artifact refresh.
- Official Picks and Results remain functional when Alt Picks fails.
- Desktop and 390-pixel visual checks for selected, pending, empty, stale, and
  unavailable states.
- No betting actions, stakes, historical PnL, or notification controls appear
  in Alt Picks.

### Completed local verification

Focused task verification was review-clean: Task 1 finished with 132 focused
tests passing; Task 2 with 24; Task 3 with 136 plus 14 targeted regressions;
Task 4 with the 14-test endpoint/live-market suite; and Task 5 with 38 Node
and 115 Python tests, syntax/diff/build parity. The one-cent regression locks
display formatting at `38.585 -> +38.59u`; it rounds only the displayed value
and does not change the three-decimal scoring ledger or selector math.

Browser QA covered selected, pending, healthy-empty, waiting/stale-suppressed,
and unavailable states, the read-only detail sheet, the legacy route, and
Picks/Results at `1280x900` and `390x844`. Mobile `scrollWidth` equaled `390`,
with identity, official pick, lane, and freeze state before supporting detail.

The final candidate verification was:

```powershell
python -m pytest tests/ -q
node --test dashboard/*.test.mjs tests/*.mjs
node --check dashboard/v2-app.js
git diff --check
git diff origin/main...HEAD -- render.yaml netlify.toml .github/workflows data/params.json pipeline dashboard/data data/picks_history.json
git grep -n "ALTERNATIVE_PICK_SELECTION_MODE" -- . ':!docs'
```

Results: `1568 passed` Python tests and `98` Node tests passed. JavaScript
syntax, diff, prohibited-path, and default-off checks were clean; the runtime
mode helper defaults invalid/missing values to `off`. An independent Babel
compilation from JSX produced a byte-identical `dashboard/v2-app.js` hash.

## Rollout sequence

Each state-changing step remains separately approval-gated.

1. [x] Implement the pure evaluator, migration, endpoint, and UI with
   `ALTERNATIVE_PICK_SELECTION_MODE=off`.
2. [x] Prove the local test suite, official-close parity anchors, prospective
   checkpoint fixtures, and frozen manifest fingerprint. This is local proof,
   not a prospective production sample.
3. [x] Apply the additive RLS migration only after Tyler approves that production
   database step; verify policies and uniqueness directly.
4. [x] Deploy the live-layer code with the mode still `off`; verify existing
   notifications, locks, and live-market UI are unchanged.
5. [x] After separate Tyler approval, set the mode to `record` and redeploy the
   existing live layer.
6. [ ] Verify current-artifact provisional rows, bounded row volume, and no impact
   on existing live-layer writes. The late-slate zero-candidate/no-write cycle
   passed; real provisional-row proof waits for the next normal slate.
7. [ ] Verify immutable on-time/late pregame frozen rows on a normal slate and
   confirm later refreshes do not hide valid lock-linked rows.
8. [x] Deploy the Netlify endpoint/UI and smoke-test desktop plus 390-pixel mobile.
   The empty/waiting production state passed; selected/pending/frozen row QA
   remains part of Steps 6-7 on the next normal slate.

Rollback is `ALTERNATIVE_PICK_SELECTION_MODE=off` plus the prior Netlify
deploy. No table deletion, history rewrite, or retention action is required.

## Review cadence

- **First slate:** integrity review only—hashes, timing, missing inputs,
  immutability, and UI clarity.
- **Five slates:** coverage and disagreement review by family and lane.
- **25 frozen picks:** early directional read, explicitly too small for a
  model or staking decision.
- **75 frozen picks or season end:** formal paired comparison with the mainline
  picks across side, K line, price sign, official verdict, provider era,
  Path B, workload, quality, timing, model/market, CLV, and rolling windows.

No sample size automatically promotes the methodology. Any official verdict,
model, threshold, staking, notification, lock, provider, or source-of-truth
change requires a separate reviewed plan and Tyler approval.

## Non-goals

This design does not authorize:

- changing the official model, lambda, thresholds, formula date, or staking;
- altering official picks, verdicts, locks, grading, params, or history;
- sending alternative-pick notifications;
- creating automatic accepted bets or a Log Bet path;
- changing provider priority or dashboard artifact source;
- using BoltOdds in active runtime;
- adding a Render service or increasing polling cadence;
- deleting or compacting production data; or
- showing historical research PnL in the app.

## Acceptance criteria

The design is correctly implemented only when:

1. Tyler can compare same-day official Picks with prospective Alt Picks before
   games begin.
2. Consensus Core and Re-entry Expansion match the versioned pure predicates
   and remain disjoint.
3. Every affirmative vote is based only on pregame, runtime-safe inputs with a
   current provisional artifact or exact frozen lock/artifact provenance.
4. Provisional choices can evolve before T-30, while the first valid on-time or
   explicitly late post-lock pregame choice is immutable.
5. Missing or stale evidence appears as pending/unavailable, never as invented
   disagreement or a stale selection.
6. A failure anywhere in the alternative path leaves official artifacts,
   picks, notifications, locks, live-market display, grading, and accepted bets
   unchanged.
7. The alternative path adds no worker cost and no unbounded row growth.
8. The app clearly communicates comparison and agreement without implying an
   official promotion or betting instruction.
