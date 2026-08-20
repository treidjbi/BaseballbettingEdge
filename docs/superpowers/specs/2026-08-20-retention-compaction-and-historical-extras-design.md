# Retention Compaction Hardening and Historical Extras Design

**Date:** 2026-08-20
**Status:** Implemented locally; merge review pending
**Scope:** Local code and tests only; no live Supabase read or mutation

## Objective

Prevent future market-snapshot compaction from producing unstable movement
paths or duplicate source IDs, then extend the bounded retention audit so the
known May 17-18 BoltOdds extras can be classified as redundant only when the
canonical correct-date evidence is proven exact.

This design supports a later deletion review. It does not authorize deletion,
retention activation, database repair, vacuum, storage reclamation, live
validation, push, or deployment.

## Evidence Behind the Change

The approved 2026-08-19 aggregate equivalence read found:

- `855` unexpected compact groups across BoltOdds May 17-18;
- only `703/855` extras reproduce every listed-source invariant;
- `117` May 17 extras differ only on `odds_move_count`;
- `35` May 18 extras contain duplicate listed source IDs;
- all `855/855` underlying correct-date groups have exact compact matches;
- those canonical groups contain `25,220` raw snapshots; and
- all `21,761/21,761` source IDs listed by the extras map to canonical groups.

The current code orders REST pages by non-unique `observed_at`, sorts movement
rows only by `observed_at`, and has no duplicate-ID contract. The retention SQL
already defines canonical movement order as `(observed_at, id)`.

## Approaches Considered

### 1. Harden future compaction and add a proof-based historical class — selected

Use the same deterministic ordering in the fetcher, Python compactor, and
retention SQL. Keep the unexpected-group total visible, but distinguish
preserved historical extras from unpreserved extras using exact source and
correct-date compact proof.

This addresses recurrence and provides a safe future retention-review path
without rewriting history.

### 2. Harden future compaction only

This is smaller, but the existing `855` extras would continue to block the
bounded audit even though the canonical evidence is exact. It prevents new
damage but does not advance the cleanup goal.

### 3. Repair or delete the historical extras

This could restore literal one-to-one coverage, but it mutates historical
evidence before the classification contract exists. It is rejected for this
phase.

## Architecture

The implementation is split into two independently testable stages.

1. **Future compaction hardening** changes only the existing REST fetch and
   Python compaction path.
2. **Historical-extra audit contract** extends the existing version 2 bounded
   audit, checkpoint validation, readiness report, and retired-BoltOdds
   closure. It does not create a cleanup executor.

Both stages remain local-only until separately reviewed and merged. A merge
still does not authorize a live audit or production deployment.

## Stage 1: Future Compaction Hardening

### Deterministic source order

`scripts/compact_market_snapshots.py` must request snapshot pages with:

`observed_at.asc,id.asc`

`market_infra/market_snapshot_compaction.py` must use the same logical order:

`(_parse_datetime(observed_at), str(id))`

The implementation must not use arrival order as a tiebreaker. Movement count,
first/last odds, snapshot count, and `source_snapshot_ids` must all derive from
the validated deterministic sequence.

### Source-ID validation and duplicate handling

Every compaction input row must have a non-empty source ID. Missing IDs fail
closed before an upsert can be built.

When the same source ID appears more than once:

- exact duplicate mappings collapse to one row; and
- conflicting mappings for the same ID raise a bounded error.

The equality comparison is performed on the complete input mapping after the
fetcher has applied its existing `slate_date` default. No field is silently
preferred from one conflicting copy.

The page fetcher applies the rule before returning rows, so the script's
`snapshot_rows` count reflects unique validated sources. The pure compactor
also applies the rule so direct callers cannot bypass it.

### Runtime boundaries

This stage does not change:

- provider selection or source-of-truth behavior;
- the compaction table or upsert conflict key;
- provider usage accounting other than avoiding duplicate fetched rows;
- schedules, polling cadence, limits, timeouts, or secrets; or
- historical compact rows already stored in Supabase.

## Stage 2: Historical-Extra Audit Contract

### Preserve strict coverage truth

The existing `unexpected_compact_group_count` and `coverage_exact` fields keep
their current literal meanings. Therefore `coverage_exact` remains false when
any compact-only group exists, even when the extra is safely redundant.

The version 2 coverage record adds:

- `preserved_unexpected_compact_group_count`;
- `unpreserved_unexpected_compact_group_count`; and
- `retention_preservation_complete`.

The runner and reporter enforce:

`unexpected_compact_group_count = preserved_unexpected_compact_group_count + unpreserved_unexpected_compact_group_count`

`retention_preservation_complete` is true only when missing, duplicate,
mismatched, and unpreserved-unexpected counts are all zero. It is recomputed by
the local validator and never trusted as an independent database assertion.

Readiness and retired-BoltOdds closure use
`retention_preservation_complete`, not literal `coverage_exact`, for the narrow
raw-retention completeness decision. Reports continue displaying strict
coverage, total extras, preserved extras, and unpreserved extras.

Version 1 behavior remains unchanged. The version 2 query-contract hash and
runner version change, so all older checkpoints fail closed and cannot be mixed
with the extended contract.

### Exact historical allowlist

Only compact-only groups satisfying one of these classes can enter the
preserved count:

1. **BoltOdds May 17 alias class**
   - compact `slate_date = 2026-05-17`;
   - compact market key `pitcher_strikeouts`;
   - every listed source market key is exactly `Strikeouts`;
   - every source run date and Phoenix observation date is May 16 or May 17;
   - provider, book, normalized player, side, and numeric line match; and
   - every resolved correct-date raw group has an exact canonical compact.
2. **BoltOdds May 18 carryover class**
   - compact `slate_date = 2026-05-18`;
   - every listed source run date and Phoenix observation date is May 17;
   - provider, book, normalized player, market key, side, and numeric line
     match exactly; and
   - every resolved May 17 raw group has an exact canonical compact.

Every other provider, date, alias, or timing pattern remains unpreserved and
blocking. The implementation does not hardcode the observed group counts, so
new or changed rows must independently satisfy the full proof.

### Required proof for each candidate extra

An allowlisted candidate is preserved only when all of these checks pass:

1. `source_snapshot_ids` is a non-empty JSON array.
2. Every distinct listed ID resolves to exactly one `market_snapshots` row.
3. Every source links to an existing `market_provider_runs` row.
4. Duplicate listed IDs do not change the distinct source set.
5. All source dimensions satisfy the applicable historical class.
6. Sources partition into one or more correct-date canonical movement groups.
7. Every canonical group has exactly one compact row.
8. Each canonical compact's first/last timestamps, first/last/min/max odds,
   movement count, snapshot count, and distinct source-ID set equal the full
   raw group under canonical `(observed_at, id)` ordering.
9. Every distinct source listed by the extra is contained in its exact
   canonical compact.

The extra row's own movement metrics are not season truth and are not required
to match. The safety proof is that its referenced raw evidence already exists
inside exact canonical correct-date compacts.

### Bounded query shape

The classification stays inside the existing provider/date chunk SELECT. It
starts from compact-only groups after indexed provider/date boundaries are
applied. JSON source expansion and correct-date proof run only for the two
allowlisted BoltOdds dates.

The SQL must:

- remain one SELECT-only statement;
- emit aggregate counts only;
- keep IDs, players, books, group keys, payloads, and credentials out of the
  result;
- retain raw indexed predicates on date, provider, run ID, and compact group
  keys;
- use canonical ascending `(observed_at, id)` movement order;
- contain no retry, mutation, DDL, repair, cleanup, or timeout change; and
- fail closed when any proof component is missing or contradictory.

## Files in Scope

### Stage 1

- `market_infra/market_snapshot_compaction.py`
- `scripts/compact_market_snapshots.py`
- `tests/test_market_snapshot_compaction.py`
- `tests/test_compact_market_snapshots_script.py`

### Stage 2

- `scripts/retention_bounded_sql.py`
- `scripts/bounded_retention_audit.py`
- `scripts/build_season_retention_readiness.py`
- `tests/test_retention_bounded_sql.py`
- `tests/test_bounded_retention_audit.py`
- `tests/test_build_season_retention_readiness.py`

### Handoff documentation

- `docs/superpowers/plans/2026-08-18-bounded-retention-audit.md`
- `docs/current-state.md`
- the BBE Operations Brief automation memory

No migration, schema, dependency, retention executor, dashboard file, Render
configuration, Netlify function, provider flag, model file, or production
artifact is in scope.

## Error Handling

- Missing or conflicting source IDs stop compaction before any upsert.
- Unknown version 2 fields, missing new fields, invalid count equations, or an
  inconsistent preservation boolean invalidate the checkpoint.
- A preserved-extra count larger than the total unexpected count fails closed.
- Any historical candidate outside the exact allowlist remains unpreserved.
- Existing `53100`, `57014`, pooler, authentication, timeout, redaction, and
  no-retry guardrails remain unchanged.

## Testing Strategy

Implementation follows red-green TDD.

### Stage 1 regressions

- tied timestamps produce stable first/last odds, movement count, and source
  ordering by ID;
- REST page requests use `observed_at.asc,id.asc`;
- identical source IDs repeated across pages collapse;
- conflicting duplicates fail closed;
- missing source IDs fail closed; and
- ordinary unique rows keep current output.

### Stage 2 regressions

- the SQL exposes total/preserved/unpreserved counts and the exact sum
  equation;
- only the two BoltOdds historical classes can be preserved;
- missing IDs, missing runs, wrong dimensions, wrong dates, wrong aliases,
  incomplete source sets, duplicate canonical groups, or metric mismatches stay
  unpreserved;
- strict `coverage_exact` remains false when preserved extras exist;
- `retention_preservation_complete` becomes true only when all blocking
  preservation counts are zero;
- validators reject old/mixed query contracts and all equation or boolean
  contradictions;
- readiness and BoltOdds closure display preserved extras but block only on
  unpreserved extras for version 2;
- version 1 fixtures remain unchanged; and
- focused and full repository suites pass on the exact commit.

No test connects to Supabase. Live validation remains a later approval gate.

## Delivery and Approval Gates

1. Commit this design specification on the isolated branch.
2. After written-spec approval, create a detailed TDD implementation plan.
3. Implement and review Stage 1, then Stage 2, with separate commits.
4. Run focused and full local verification.
5. Present the reviewed branch for a separate local-merge decision.
6. After merge, request separate approval for any fresh linked audit.
7. Even a passing live audit permits only a deletion proposal; deletion,
   vacuum, and storage reclamation require further explicit approval.

## Success Criteria

The implementation is successful when:

- compaction is deterministic for tied timestamps and cannot emit duplicate
  source IDs;
- the audit distinguishes strict extras from proven redundant extras without a
  generic waiver;
- every preserved extra is backed by exact canonical correct-date evidence;
- all unknown or incomplete cases remain blocking;
- version 1 behavior is unchanged;
- no live system or database is touched; and
- the exact implementation commit passes focused and full local tests.
