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
graded rows exist, and use the durable Gate C dataset as the historical
metadata/result overlay when local history is behind production grading.
Optionally overlay tracked-pick metadata from a current artifact so same-day
referee caps can be evaluated before grading.

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

2026-06-09 update: the CLI now defaults `--gate-c-dataset` to
`data/research/gate_c/pitcher_k_outcome_dataset.jsonl`. That row is used only
as a historical metadata/result overlay so referee caps and recent graded rows
do not disappear when local `picks_history.json` is stale. A compact Supabase
backfill from `market_pick_evidence` and `live_market_display_state` produced
`2,482` evidence rows, `2,171` graded rows, and `56` graded
confidence-referee cap rows in the local report. This remains shadow-only
review evidence.

The sample gate was added on 2026-06-07:

- overall tracker read stays `watch_only` until at least `75` graded rows have
  movement-backed evidence
- each candidate bucket stays `watch_only` until it has at least `50` graded
  rows
- buckets below the threshold may be reported, but not used for promotion
  discussion

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
- [x] Normalize Gate C JSONL metadata and `pick_history_pnl` /
      `theoretical_pnl` as a historical overlay for backfilled reports.
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

## 2026-07-23 Scheduled Compact-Input Repair

The research branch adds
`scripts/export_market_agreement_inputs.py` and an explicit
`--refresh-market-agreement-inputs` post-grading runner mode.

The exporter:

- reads only `market_pick_evidence` and `live_market_display_state`;
- applies inclusive clean-regime start/end bounds;
- paginates with a stable order and verifies the fetched unique row count
  against an exact Supabase count;
- fetches current production `picks_history` and `today` artifacts;
- stages and hashes every output before replacement; and
- never reads scheduled raw `market_snapshots`, writes Supabase rows, or
  changes live artifacts.

The refreshed runner order is:

1. compact export;
2. market-agreement prebuild from production history/current artifact;
3. one Gate C build using the fresh tracker/display inputs;
4. final market-agreement render from the fresh Gate C dataset; and
5. existing downstream shadow reports.

Flag-off behavior remains unchanged. A live temporary export through
`2026-07-22` returned `3,089` evidence rows and `3,227` display rows, and the
tracker wrote `6,316` rows. This is useful shadow evidence, not approval for a
model, provider, notification, lock, UI, staking, threshold, retention, or
source-of-truth change. Deployment remains gated by the unresolved exact Gate
C reconciliation exception documented in the parent dataset plan.
