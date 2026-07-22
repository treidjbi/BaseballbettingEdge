# Task 3 Implementer Report

## Scope

Integrated and adversarially hardened the default-off alternative-pick recorder
after existing notification, lock, timing, and shadow-market work. The recorder
uses only the already-loaded official artifact, raw snapshots, and derived
market-evidence rows. It makes no provider calls and does not change official
picks, model math, thresholds, staking, notifications, operational locks, or
provider order.

No migration was applied, no environment variable was activated, and no
deployment or remote-system mutation was performed.

## RED evidence

TDD regressions reproduced and then closed these failure modes:

- raw stale, alternate-line, old-event, and unsupported-provider snapshots
  could be relabeled as current evidence and reach a freeze;
- a combined-provider candidate could mature from one provider's exact rows,
  while broad provider summaries supplied unbound movement counts;
- candidate-window time reset every cycle instead of persisting while the
  exact identity remained current;
- tracked rows bypassed canonical `ev_over` / `ev_under` inputs, and the
  selected tracked price did not reach the evaluator;
- `Z` and `+00:00` game/lock timestamps could compare as different instants;
- malformed boolean/non-finite lines and malformed count/odds values could be
  coerced into usable numbers;
- provider posture could be inferred from available evidence or conflicting
  artifact fields instead of the official artifact contract;
- exact frozen linkage omitted locked odds/book;
- same-state and doubleheader lock-key collisions were not stopped before I/O;
- the second read, evaluation, and first write failure boundaries lacked
  complete stop/no-leak coverage;
- ready-to-bet and nested prerequisite failures could be missed; and
- operational lock rows, arbitrary future fields, error text, and private
  artifact URLs could escape through the returned summary.

The external re-review then exposed five additional regressions. Focused RED
runs reproduced all five before implementation:

```text
mixed-row binder + duplicate provider summaries + SQL normalization
3 failed

pending freeze + old-lock mutation + frozen-first write/failure/timeout order
6 failed

artifact-listed alternate-line snapshot admitted before semantic filtering
1 failed
```

Specifically, unrelated alternate-line, old-event, and other-provider rows
poisoned otherwise-valid exact evidence; duplicate exact provider summaries
were last-row-wins; pending state remained mutable after its operational lock;
provisional writes ran before irreplaceable frozen inserts; and Python/SQL book
case normalization disagreed. The final external pass then proved that an
artifact-listed alternate-line snapshot could still bypass semantic identity
filtering and poison two valid exact-line observations.

## Implemented contract

- `ALTERNATIVE_PICK_SELECTION_MODE` remains fail-closed unless its trimmed,
  case-insensitive value is exactly `record`; off mode performs no alternative
  reads or writes.
- Candidate identity and provider posture come only from supported,
  internally-consistent official artifact fields. Evidence availability cannot
  change identity.
- The exact candidate's first-current timestamp persists across cycles and
  resets only when its candidate identity changes.
- Raw evidence must match candidate pitcher, side, model line, game/event or
  artifact snapshot binding, provider, current-candidate window, and real
  metadata freshness. Unrelated ladder, event, and provider rows are ignored
  and never count; malformed rows explicitly bound to the exact candidate fail
  closed. Candidate provider, pitcher, side, and line semantics must match
  before either snapshot-ID or provider-event provenance can associate a row.
  Every provider declared by the posture must have bound raw observations.
- Market movement, book count, reversal, and volatility are derived from the
  exact bound raw rows. Broad provider summaries are used only as a freshness
  and reconciliation check; missing, duplicate, malformed, stale, conflicting,
  or unbound summaries remain pending. Exact provider summaries are grouped
  before binding, so duplicate input order cannot change the result.
- Runtime evaluation begins with the canonical side payload, overlays only the
  tracked display/lock contract, normalizes game time, preserves exact integer
  selected odds/book, and never pairs an alternate line with current-line
  opposite-side odds.
- Every exact current-cycle operational lock freezes the already-evaluated row,
  including a pending selection and its complete evidence/reason state. An old
  lock without a frozen row permits no later provisional mutation. A frozen row
  still requires exact slate, game, teams, pitcher, side, line, odds, normalized
  book, time, status, logical source, and byte-level artifact hash. Python and
  the unapplied SQL trigger enforce the same case-insensitive book linkage.
- Reads are current-slate, bundle/checkpoint or exact-lock-key scoped with
  explicit selected fields. The recorder uses one attempt and the positive
  remainder of a five-second monotonic budget for each request.
- Any prerequisite, read, evaluation, or write failure stops alternative work
  for that cycle and returns a bounded stable summary. Public lock/artifact
  summaries use strict allow-lists and expose no lock rows, raw errors, or
  private URLs.
- Frozen insert-ignore batches run before provisional merge-upserts. A frozen
  failure blocks provisional work; a later provisional failure or timeout does
  not undo the already-written immutable freeze.

## Real-artifact dry run

Using the checked-in `dashboard/data/processed/today.json` with mocked storage
and no provider calls produced 23 provisional rows, all with official odds and
books, all pending, and zero frozen writes. All 23 carry
`evidence_event_unbound` because this TheRundown artifact has neither usable raw
snapshot IDs nor a TheRundown event ID. That is the intended fail-closed
activation gate, not a prospective frozen sample.

## GREEN evidence

```text
python -m pytest tests/test_market_infra_supabase_writer.py tests/test_live_layer_worker.py tests/test_notification_coordinator.py tests/test_operational_locks.py -q
107 passed

python -m pytest tests/test_alternative_pick_selector.py tests/test_no_drag_composite_canary_audit.py tests/test_gate_f_fire_reentry_lab.py tests/test_gate_f_preclose_clv_proxy_lab.py tests/test_build_pitcher_k_outcome_dataset.py -q
132 passed

python -m pytest tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_schema.py tests/test_live_layer_worker.py tests/test_operational_locks.py tests/test_operational_pick_locks_schema.py -q
115 passed

python -m py_compile market_infra/alternative_pick_selection_state.py market_infra/alternative_pick_selector.py scripts/build_live_events_to_supabase.py
exit 0

git diff --check
exit 0
```

The original bounded review was superseded by the external five-finding pass.
The post-fix bounded adversarial re-review concluded `CLEAN`: all five findings
were closed, its relevant suite passed 106 tests, and `git diff --check` was
clean. A final external pass found the snapshot-ID ordering blocker documented
above; the added focused regression failed before the predicate fix and passed
after it, while the full 115-test Task 3/lock matrix remained green.

## Closed gates

The migration remains unapplied and record mode remains unactivated. No Render,
Netlify, Supabase, provider, workflow, or other remote change was made. A later
activation decision must first provide exact artifact-to-raw snapshot/event
provenance for the intended official posture.
