# Task 5 Implementer Report

Completed 2026-07-21 in the `codex/pregame-alt-picks` worktree only.

## Delivered

- Added `dashboard/v2-alt-picks.js`, a read-only adapter that fetches only
  `/.netlify/functions/alternative-picks`, derives the Phoenix current slate,
  validates the two lanes, three selection statuses, two checkpoints, and the
  exact four family-state keys, and keeps every failure local.
- Replaced the rendered middle navigation route with `Alt Picks`; legacy
  `?tab=history` canonicalizes to `?tab=alt` and tab changes persist the
  canonical query parameter.
- Added read-only `AltPicksTab`, `AltPickCard`, and `AltPickSheet` with
  Consensus Core before Re-entry Expansion, official-pick comparison, all four
  evidence chips, actual freeze labels, and scoped blue/teal mobile styles.
- Added adapter, UI contract, accepted-bet isolation, and one-cent PnL-format
  regression coverage. The PnL formatter already rendered `38.585` as
  `+38.59u` once, so no production PnL/math code changed.
- Regenerated the checked-in Babel build and advanced the adapter/data/app cache
  tokens.

## Verification

- `node --check dashboard/v2-alt-picks.js`
- `node --check dashboard/v2-app.js`
- `node --test dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs dashboard/v2-data.test.mjs dashboard/v2-movement-helpers.test.mjs` (39 passing)
- `python -m pytest tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py tests/test_no_drag_composite_canary_audit.py -q` (112 passing)
- `git diff --check`

The v2-data suite emits its existing mocked 502 fallback diagnostics while all
tests pass. No browser or Playwright QA was run, by request.

## Build note

On this Windows/npm 11 host Babel's named-preset lookup cannot see the npx
cache automatically. The build was regenerated with the same requested Babel
packages and an absolute cache path for `@babel/preset-react`; no dependency,
runtime, provider, migration, deployment, or remote change was made.
