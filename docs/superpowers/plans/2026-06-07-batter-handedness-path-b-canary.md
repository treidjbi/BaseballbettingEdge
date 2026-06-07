# Batter Handedness Path B Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote batter handedness into a reversible live canary that uses real PA-backed batter split samples when available and falls back to current Path A per batter.

**Architecture:** Add `BATTER_HANDEDNESS_MODE=path_a|path_b`, default `path_a`. In `path_b`, `run_pipeline` overlays cached `data/batter_splits_YYYY.json` rows onto the existing batter stats map, and `build_features.calc_lineup_k_rate()` uses real split objects directly without applying the league-average platoon delta again. Missing or untrusted split rows use existing Path A behavior.

**Tech Stack:** Python 3.11, pytest, existing `pipeline/fetch_batter_stats.py`, `pipeline/build_features.py`, `pipeline/run_pipeline.py`, Render cron env deployment.

---

## Operating Decision

Tyler approved promoting better handedness on 2026-06-07. This is a live
model-input canary, not a threshold/staking/provider/notification change.

## Implementation Status

Implemented on `main` on 2026-06-07, pending/after Render cron deployment and
the `BATTER_HANDEDNESS_MODE=path_b` environment flip.

- `BATTER_HANDEDNESS_MODE=path_a|path_b`, default `path_a`
- `path_b` overlays live-collected `data/batter_splits_YYYY.json` samples onto
  the batter-stat map under `mlbam:{id}` keys
- `calc_lineup_k_rate_details()` uses trusted PA-backed real split samples
  directly and skips the generic platoon delta for those batters
- missing/untrusted split rows fall back per batter to Path A
- pitcher artifacts expose mode/source/count metadata for daily audit

## Non-Goals

- Do not use historical lineup-handedness backfill as a live model input.
- Do not change global verdict thresholds, staking, calibration, provider
  order, notifications, locks, retention, or dashboard source-of-truth behavior.
- Do not remove Path A. Every batter without a trusted real split must still
  fall back to Path A.
- Do not double-count platoon effects when a real split is used.

## File Map

- Modify: `pipeline/fetch_batter_stats.py`
  - Add split-cache loading and overlay helpers.
- Modify: `pipeline/build_features.py`
  - Add mode parsing, split-source accounting, Path B per-batter lookup, and
    artifact metadata.
- Modify: `pipeline/run_pipeline.py`
  - Pass the current handedness mode and overlay cached split samples before
    record building.
- Modify: `tests/test_fetch_batter_stats.py`
  - Cover trusted split-cache overlay and season mismatch fallback.
- Modify: `tests/test_build_features.py`
  - Cover Path A default, Path B real split use, no double-counted platoon
    delta, and fallback accounting.
- Modify: `tests/test_run_pipeline.py`
  - Cover that `path_b` overlays split-cache rows before `build_pitcher_record`.
- Modify: docs and automation memory.

## Tasks

- [x] Add failing tests for Path B split-cache overlay.
- [x] Add failing tests for `calc_lineup_k_rate()` Path B real split and
      fallback behavior.
- [x] Add failing test for `run_pipeline` using the overlay helper only in
      `path_b`.
- [x] Implement split-cache overlay helper in `fetch_batter_stats.py`.
- [x] Implement feature-flagged Path B lineup K-rate behavior in
      `build_features.py`.
- [x] Wire `run_pipeline.py` to overlay split cache and pass mode.
- [x] Update current-state/Gate C docs and automation memory.
- [x] Run focused tests and full test suite.
- [ ] Commit and push.
- [ ] Deploy Render pipeline crons and set `BATTER_HANDEDNESS_MODE=path_b` only
      after code is live.
