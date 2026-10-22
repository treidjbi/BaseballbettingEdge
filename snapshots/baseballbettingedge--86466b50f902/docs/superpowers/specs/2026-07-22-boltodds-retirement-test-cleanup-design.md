# BoltOdds Retirement Test Cleanup Design

## Status

Approved by Tyler on 2026-07-22 with the instruction: "Do it."

## Problem

BoltOdds has been retired from active runtime since 2026-06-17, but
`tests/test_boltodds_ws_worker.py` still contains 28 tests for the former
WebSocket worker. Its slate-rotation test uses wall-clock timing and is
nondeterministic: the same failure reproduced on untouched `main`, so it is
not an Alt Picks regression. Keeping the retired worker behavior suite in the
default release gate creates noise without protecting an active production
path.

## Decision

Delete the retired worker behavior suite and replace it with a compact static
retirement guard suite.

The replacement suite will prove:

1. `render.yaml` remains intentionally non-deploying and cannot recreate the
   old BoltOdds worker.
2. GitHub workflows do not launch `scripts/boltodds_ws_worker.py` or reference
   the retired Render service name `bbe-boltodds-shadow-worker`.
3. The active Render cron deployment helper does not launch or name the
   retired worker.

Existing fail-closed and provider-exclusion tests remain in place, including:

- `tests/test_fetch_provider_market_odds.py`
- `tests/test_render_pipeline_entrypoint.py`
- `tests/test_market_infra_live_market_display.py`
- `tests/test_market_infra_market_evidence.py`
- `tests/test_build_official_market_lines_to_supabase.py`
- `tests/test_official_market_lines.py`

Historical parser/client coverage remains in:

- `tests/test_market_infra_boltodds_client.py`
- `tests/test_market_infra_boltodds_snapshot.py`
- `tests/test_probe_boltodds_markets.py`

## Alternatives Considered

### Quarantine or skip the old worker file

Rejected. It would preserve dead timing tests, add permanent skip noise, and
make the release gate less transparent.

### Delete every BoltOdds-related test

Rejected. Provider-exclusion and fail-closed tests prevent accidental runtime
reactivation, while parser coverage preserves explicitly historical research
paths.

### Recommended: remove worker behavior tests, retain retirement guards

Selected. It removes the flaky inactive-runtime suite while preserving the
small set of tests that enforce the current provider posture.

## Scope And Safety

- Test and documentation changes only.
- Do not modify `scripts/boltodds_ws_worker.py` or any production module.
- Do not change provider flags, source selection, notifications, locks,
  artifacts, model behavior, Supabase state, Render configuration, or Netlify.
- Keep the Alt Picks branches and their reviewed commits unchanged.
- Work on `codex/retire-boltodds-worker-tests` from `origin/main`.
- Commit and push the cleanup branch; do not merge or deploy it in this task.

## Verification

- The compact retirement guard suite passes.
- The existing fail-closed/provider-exclusion subset passes.
- The full Python and Node suites pass.
- `git diff --check` passes.
- The final diff contains only the approved test replacement and these design/
  plan documents.
