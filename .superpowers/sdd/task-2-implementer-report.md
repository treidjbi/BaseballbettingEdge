# Task 2 Implementer Report

## Scope

Implemented bounded, pure alternative-pick state shaping and one additive,
unapplied Supabase migration. No Task 1 files were changed.

## RED evidence

`python -m pytest tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_schema.py -q`

Initially failed during collection because
`market_infra.alternative_pick_selection_state` did not exist. After the first
implementation pass, the new later-cycle regression test failed as intended:
an older provisional state could be frozen from a later lock cycle. That test
now requires the provisional `observed_at`, lock `locked_at`, and evaluator
cycle timestamp to match exactly.

## GREEN evidence

```text
python -m pytest tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_schema.py tests/test_operational_pick_locks_schema.py -q
14 passed in 0.12s

git diff --check
exit 0
```

The tests cover candidate/game identity, identity-scoped evidence, stale and
unsupported evidence fail-closed behavior, provisional stop conditions, exact
lock matching, both hash domains, current-cycle/no-reconstruction freezes,
bounded checkpoints, immutable SQL guards, RLS, and grants.

## Review remediation evidence

The Task 2 review added current-cycle, forged-identity, exact artifact-path,
lock-timing, and selector-identity concerns. New tests first failed because
the pure state code accepted supplied identities, did not compare the lock's
`observed_at`, did not validate lock timing, did not require the exact artifact
path, and stored the manifest fingerprint as the selector ID. The migration
tests also failed until the new selector fingerprint and lock-path/current-lock
fragments were present.

After remediation:

```text
python -m pytest tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_schema.py tests/test_operational_locks.py tests/test_operational_pick_locks_schema.py -q
23 passed in 0.31s

git diff --check
exit 0
```

The frozen path now requires `operational_pick_locks.observed_at == locked_at
== evaluator observed_at`, canonical recomputation of both identities, valid
pregame timing, and exact `source_artifact_path` equality. State rows keep the
lane selector ID separate from the required 64-character manifest fingerprint.

## Lock source-path remediation

The normal live worker records the actual Netlify `get-artifact` URL in
`operational_pick_locks.source_artifact_path`; alternative state must instead
keep its logical canonical path. The added RED test proved that treating those
as one field rejected normal remote locks. Frozen rows now copy the exact lock
path into nullable/all-or-none `lock_source_artifact_path`, while provisional
rows leave it null and retain `dashboard/data/processed/today.json` in
`source_artifact_path`.

```text
python -m pytest tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_schema.py tests/test_operational_locks.py tests/test_operational_pick_locks_schema.py -q
24 passed in 0.44s

git diff --check
exit 0
```

## Safety and caveats

- Created `supabase/migrations/20260721222627_alternative_pick_selection_state.sql`
  with `npx supabase migration new alternative_pick_selection_state` and edited
  only that newly generated migration.
- The migration was **not applied**. No `db push`, `migration up`, linked
  database command, production SQL, environment variable change, deployment,
  or record-mode activation was run.
- The new module is pure state shaping only. Task 3 remains responsible for
  default-off integration, bounded requests, current-state reads, and writes.
