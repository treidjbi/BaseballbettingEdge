# Current State

Last updated: 2026-04-28

## Read Order

For any new work in this repo:

1. Read `AGENTS.md` for the canonical project instructions and architecture notes.
2. Read this file for the current operating state.
3. Read the active evaluation plan:
   `docs/superpowers/plans/2026-04-28-one-week-evaluation-cadence.md`
4. Use the historical dated plans in `docs/superpowers/plans/` as archive context,
   not as replacements for the current state.

## Current Operating Mode

The project is in a soak and evaluation period following the recent grading and
post-Phase-C changes.

- Treat `2026-04-28` as the clean post-ROI / post-SwStr-live evaluation
  boundary.
- Do not make ad hoc model, threshold, staking, or `formula_change_date`
  changes during this soak unless the user explicitly decides to break cadence.
- Prefer evidence gathering, diagnostics, verification, and note-taking over
  feature churn during this window.

## Active Evaluation Stack

The active local diagnostics and tests are:

- `analytics/diagnostics/e1_regime_map.py`
- `analytics/diagnostics/e2_storage_integrity.py`
- `analytics/diagnostics/e3_projection_audit.py`
- `analytics/diagnostics/e4_bet_selection_audit.py`
- `tests/test_e1_regime_map.py`
- `tests/test_e2_storage_integrity.py`
- `tests/test_e3_projection_audit.py`
- `tests/test_e4_bet_selection_audit.py`

These are the current tools for checking regime health, storage integrity,
projection shape, and bet-selection quality.

## Next Decision Checkpoint

The active decision cadence is defined in:

- `docs/superpowers/plans/2026-04-28-one-week-evaluation-cadence.md`

That plan governs the next week of evaluation work and should be treated as the
current decision framework for new analysis in this regime.

## Historical Context

The dated plan archive is intentionally preserved so future agents can see what
changed, what was tried, and what mistakes to avoid repeating.

Important recent context:

- `docs/superpowers/plans/2026-04-27-post-phase-c-model-evaluation.md`
- `docs/superpowers/plans/2026-04-27-post-phase-c-live-check.md`
- `docs/superpowers/plans/2026-04-27-swstr-signal-repair-and-rebaseline.md`
- `docs/superpowers/plans/2026-04-27-pre-phase-c-cleanup.md`

When historical plans conflict with this file, treat this file plus the active
cadence plan as the current operating guidance.
