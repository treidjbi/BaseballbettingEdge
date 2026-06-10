# Gate F FIRE Re-Entry Selection Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-only Gate F lab that identifies which capped or retained FIRE-like rows deserve a future FIRE re-entry canary, so the profit-rescue brake does not permanently make the product unbettable.

**Architecture:** Add a diagnostic over the Gate C pitcher outcome dataset that scores runtime-safe FIRE re-entry candidates by PnL, ROI, retained volume, CLV/process support, and slice stability. The lab produces a markdown report and promotion-readiness labels only; it does not change live projections, verdicts, thresholds, staking, provider order, locks, notifications, retention, or dashboard source-of-truth behavior.

**Tech Stack:** Python 3.11, pytest, existing Gate C JSONL dataset, existing analytics/output markdown reports.

---

## Guardrails

- Runtime selectors may use only pregame/runtime-safe fields: verdict, raw verdict, side, edge, adjusted EV, no-vig gap, CLV labels, market relationship, quality gate, K-line bucket, price sign, timing window, workload/opportunity labels, Path B coverage, provider/source attribution, and market agreement labels when present.
- Hindsight-only fields such as actual Ks, PnL, result, actual IP, pitch count, batters faced, and miss distance may score candidates but must not define candidate membership.
- This work may draft a future re-entry canary candidate, but it must not turn that candidate on.
- The active production brake remains `PROFIT_RESCUE_REFEREE_MODE=enforce` unless Tyler separately approves a rollback or refinement.
- Strict provider mode remains separate.

## File Map

- Create: `analytics/diagnostics/gate_f_fire_reentry_lab.py`
  - Reads `data/research/gate_c/pitcher_k_outcome_dataset.jsonl`.
  - Applies the current profit-rescue policy in shadow to label retained FIRE versus capped-to-LEAN rows.
  - Scores re-entry candidates and slice stability.
- Create: `tests/test_gate_f_fire_reentry_lab.py`
  - Covers candidate labels, scoring thresholds, slice risk, and report language.
- Output: `analytics/output/gate_f_fire_reentry_lab.md`
  - Decision-oriented report with top candidates, readiness labels, volume, ROI, CLV support, and recommended next step.
- Modify: `docs/current-state.md`
  - Add the new report to the model-lane overlay if it produces useful next-step evidence.
- Modify: `docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md`
  - Add Gate 12C for FIRE re-entry selection work.

## Tasks

### Task 1: Candidate Rules And Tests

**Files:**
- Create: `tests/test_gate_f_fire_reentry_lab.py`
- Create: `analytics/diagnostics/gate_f_fire_reentry_lab.py`

- [x] Write failing tests for the profit-rescue shadow decision:
  - current FIRE 2u becomes retained FIRE 1u unless later capped;
  - FIRE under becomes capped to LEAN;
  - model-fades-market-favorite FIRE becomes capped to LEAN.
- [x] Write failing tests for re-entry candidate labels:
  - `clv_supported_reentry` when a capped/retained row has close-price or close-line support;
  - `market_aligned_reentry` when the model agrees with market favorite and has no-vig support;
  - `moderate_edge_quality_reentry` for clean moderate edge and no-vig support;
  - `avoid_fire_under_reentry` for FIRE unders with weak support.
- [x] Run tests and confirm they fail before implementation.

### Task 2: Summary And Readiness Scoring

**Files:**
- Modify: `analytics/diagnostics/gate_f_fire_reentry_lab.py`
- Modify: `tests/test_gate_f_fire_reentry_lab.py`

- [x] Implement clean tracked row filtering from 2026-04-28 onward.
- [x] Implement candidate summary buckets with rows, W-L, PnL, ROI, retained/capped counts, beat-close counts, and rolling windows.
- [x] Implement readiness labels:
  - `ready_for_plan` when rows >= 100, ROI > 0, CLV support >= 40%, recent ROI >= 0, and no major negative slice;
  - `watch_more` when rows >= 50 and ROI > 0 but one readiness condition is missing;
  - `not_ready` otherwise.
- [x] Add slice checks by side, verdict, K-line, price sign, quality, model-market relationship, timing, no-vig, CLV, workload, Path B, provider, and market agreement.
- [x] Run focused tests.

### Task 3: Markdown Report And Docs

**Files:**
- Modify: `analytics/diagnostics/gate_f_fire_reentry_lab.py`
- Create: `analytics/output/gate_f_fire_reentry_lab.md`
- Modify: `docs/current-state.md`
- Modify: `docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md`

- [x] Render a concise Gate F report with:
  - executive read;
  - candidate scoreboard;
  - readiness reasons;
  - capped versus retained FIRE volume;
  - top slice risks;
  - recommendation focused on a future re-entry canary, not same-day promotion.
- [x] Generate the report from the current Gate C dataset.
- [x] Update docs to say Gate F is now measuring FIRE re-entry volume and decision value, not only avoiding FIRE exposure.
- [x] Run focused and touched-area tests.

## Success Criteria

- The report names at least one concrete candidate family to keep studying or draft as a future canary, or clearly says none has enough volume/process support.
- The report explicitly measures whether the active profit-rescue canary risks zero-FIRE slates.
- No production behavior, model math, thresholds, staking, provider, notification, lock, retention, or dashboard source-of-truth behavior changes.

## 2026-06-10 Implementation Result

- Added `analytics/diagnostics/gate_f_fire_reentry_lab.py` and
  `tests/test_gate_f_fire_reentry_lab.py`.
- Generated `analytics/output/gate_f_fire_reentry_lab.md` from the current
  Gate C dataset.
- Current result: no candidate is ready for a production re-entry plan. Runtime
  watch candidates are `moderate_edge_quality_reentry` (`68` rows, `+4.77u`,
  `+7.0% ROI`) and `retained_fire_control` (`134` rows, `+2.71u`,
  `+2.0% ROI`). `clv_supported_reentry` is a process anchor only because CLV is
  post-close evidence.
- Production behavior unchanged: `PROFIT_RESCUE_REFEREE_MODE=enforce` remains
  the active brake; no FIRE re-entry, lambda, threshold, staking, provider,
  notification, lock, retention, or dashboard source-of-truth change was made.
