# Task 3 Implementer Report

## Scope

Integrated the default-off alternative-pick recorder after the existing live
layer's lock, timing, and shadow-market work. The recorder uses only the
already-loaded artifact, snapshots, and market-evidence rows; it makes no
provider calls. No migration, environment-variable change, deployment, or
remote-system mutation was performed.

## RED evidence

`python -m pytest tests/test_market_infra_supabase_writer.py tests/test_live_layer_worker.py -q`

The first run had five expected failures: the writer did not accept a
per-request timeout/single attempt, and the alternative mode/recorder helpers
did not exist.

Follow-up RED regressions also caught:

- duplicate tracked candidates producing an invalid state-key lookup;
- logically equal `Z` and `+00:00` lock timestamps failing current-cycle
  freeze detection; and
- an evaluator exception escaping the sidecar instead of leaving the overall
  live-layer cycle successful.

## GREEN evidence

 ```text
python -m pytest tests/test_market_infra_supabase_writer.py tests/test_live_layer_worker.py tests/test_notification_coordinator.py tests/test_operational_locks.py -q
88 passed in 0.75s

git diff --check
exit 0
```

## Behavior confirmed

- `ALTERNATIVE_PICK_SELECTION_MODE` remains off unless its trimmed,
  case-insensitive value is exactly `record`; off mode performs no alternative
  state reads or writes.
- Alternative state runs only after notifications, market/display state,
  reminders, live state, operational locks, shadow timing, and shadow-market
  build complete. Existing lock write failure, timing error, or market build
  failure skips it before alternative I/O.
- The writer preserves 20-second/three-attempt defaults. Recorder reads use a
  positive remaining timeout and one attempt; provisional state merge-upserts
  and frozen state uses insert-ignore on the six-column key.
- The canonical payload SHA is separate from the existing exact-byte artifact
  SHA. Current-cycle freezing accepts parsed-equivalent timestamps, requires
  exact lock linkage, and does not reconstruct older missed locks.
- Duplicate candidates are deduplicated and each cycle writes at most one
  provisional and one frozen row per candidate.
