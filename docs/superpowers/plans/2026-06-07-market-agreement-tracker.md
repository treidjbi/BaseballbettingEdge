# Market Agreement Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shadow-only market agreement tracker that evaluates whether
BoltOdds/PropLine movement moved with or against BBE picks, including LEANs and
confidence-referee capped rows.

**Architecture:** Reuse existing live-market evidence and the live market
outcome audit. Add a diagnostic that derives agreement, value, strength,
magnitude, and referee/LEAN/FIRE buckets. Join to `picks_history.json` when
graded rows exist. Optionally overlay tracked-pick metadata from a current
artifact so same-day referee caps can be evaluated before grading.

**Tech Stack:** Python 3.11, pytest, existing `analytics/diagnostics/`
patterns, Markdown/JSONL output under `analytics/output/`.

---

## Operating Decision

This is a child plan of:

- `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
- `docs/superpowers/plans/2026-06-05-market-favorite-confidence-referee-production-canary.md`
- `docs/research/market-tracker-map.md`

It answers a tracking question only. It does not approve a model change,
provider cutover, new notification send class, retention deletion, dashboard
change, or staking/threshold change.

## Implementation Status

Implemented on `main` on 2026-06-07.

- Diagnostic: `analytics/diagnostics/market_agreement_tracker.py`
- Tests: `tests/test_market_agreement_tracker.py`
- Design note:
  `docs/superpowers/specs/2026-06-07-market-agreement-tracker-design.md`
- Default report path: `analytics/output/market_agreement_tracker.md`
- Default row export path: `analytics/output/market_agreement_tracker.jsonl`

This version is derived reporting only. It can read exported live market
evidence and optional current artifact tracked picks to label movement with or
against the model, but it does not write Supabase rows or change production
behavior.

## Non-Goals

- Do not change production picks, verdicts, locks, thresholds, staking, model
  parameters, provider order, notification sends, calibration, retention, or
  dashboard source-of-truth behavior.
- Do not create a new Supabase table.
- Do not use hindsight-only result fields to define runtime movement labels.
- Do not promote LEANs automatically based on market movement.
- Do not make confidence-referee caps stricter or looser.

## File Map

- Create: `analytics/diagnostics/market_agreement_tracker.py`
  - Load optional exported market evidence, display state, snapshots, history,
    and current artifact rows.
  - Reuse `live_market_outcome_audit.build_rows_from_inputs()`.
  - Add derived labels and tracker buckets.
  - Write Markdown and optional JSONL.
- Create: `tests/test_market_agreement_tracker.py`
  - Test labels, strength/magnitude extraction, referee/LEAN buckets, current
    artifact overlay, and report content.
- Modify: `docs/research/market-tracker-map.md`
  - Register the tracker as derived, shadow-only reporting.
- Modify: `docs/current-state.md`
  - Add the plan to the tracking lane and daily read posture.

## Task 1: Add Tests First

- [x] Write failing tests for movement agreement labels.
- [x] Write failing tests for strength and magnitude buckets using existing
      `metadata.book_summaries`.
- [x] Write failing tests for LEAN and confidence-referee capped tracker
      buckets.
- [x] Write failing tests for current artifact metadata overlay.
- [x] Write failing tests for the Markdown report read rule.

## Task 2: Implement Diagnostic

- [x] Create `analytics/diagnostics/market_agreement_tracker.py`.
- [x] Import and reuse the existing live-market outcome audit builder.
- [x] Normalize verdict fields:
      `current_verdict`, `verdict`, `actionable_verdict`, `raw_verdict`, and
      `locked_verdict`.
- [x] Normalize confidence-referee metadata from either movement rows or
      tracked-pick artifact rows.
- [x] Add agreement/value/strength/magnitude labels.
- [x] Add tracker buckets for LEAN, FIRE, and referee caps.
- [x] Add `main()` with input paths and output paths.

## Task 3: Wire Documentation

- [x] Update `docs/research/market-tracker-map.md` so daily briefs know to
      read/regenerate the tracker.
- [x] Update `docs/current-state.md` tracking lane to reference this plan.
- [x] Keep every update explicit that this remains shadow-only.

## Task 4: Verify

- [x] Run `python -m pytest tests/test_market_agreement_tracker.py -q`.
- [x] Run `python -m pytest tests/test_market_agreement_tracker.py tests/test_live_market_outcome_audit.py -q`.
- [x] Run a broader relevant test set if time allows.
- [x] Run the diagnostic with default local inputs and confirm it writes a
      shadow-only report without requiring Supabase credentials.

## Task 5: Finish

- [x] Update the BBE Operations Brief automation memory so future briefs carry
      the new tracker checklist.
- [x] Commit and push the scoped changes.
