# Post-Phase-C Model Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate whether the current data model, strikeout projection stack, and bet-ranking logic are structurally sound now that Phase A/B/C is complete, then end with explicit decisions about what to rebuild next.

**Architecture:** This is an evaluation-first plan with three tracks that build on each other. Track 1 maps the data regimes and storage integrity so later analysis does not mix broken and clean eras. Track 2 audits projection accuracy and lambda construction using only the clean post-fix windows plus carefully labeled transition eras. Track 3 audits whether the system is selecting the right bets even when the raw projection is directionally correct. Each track ends with a written decision memo so the next implementation plan is driven by evidence instead of isolated feature ideas.

**Tech Stack:** Python 3.11, pytest, pandas, matplotlib, json, pathlib, existing `analytics/` local tooling, existing `data/picks_history.json`, `data/params.json`, and `docs/data-caveats.md`.

---

## Why this plan exists

We have enough 2026-season data now to stop making one-off improvements in isolation and instead answer the higher-order questions:

1. Is the data structured and stored in a way that preserves the truth of what the model knew at decision time?
2. Is lambda the real problem, or are the main misses coming from opponent context, season-environment drift, signal weighting, or calibration regime mixing?
3. Even if projection quality is acceptable, are we converting projections into bets correctly?

This plan is intentionally **evaluation and decision only**. It should produce:

- a storage/integrity decision
- a projection-accuracy decision
- a bet-selection decision
- a prioritized implementation queue for the next plan

It should **not** change live model behavior unless a task explicitly calls for creating local diagnostics or report helpers.

---

## File structure

**Canonical references**
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/CLAUDE.md`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/data-caveats.md`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/data/params.json`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/data/picks_history.json`

**New diagnostics to create**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e1_regime_map.py`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e2_storage_integrity.py`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e3_projection_audit.py`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e4_bet_selection_audit.py`

**New tests to create**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_e1_regime_map.py`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_e2_storage_integrity.py`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_e3_projection_audit.py`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_e4_bet_selection_audit.py`

**Generated local outputs**
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e1_regime_map.md`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e2_storage_integrity.md`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e3_projection_audit.md`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e4_bet_selection_audit.md`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e5_synthesis.md`

**Tracking docs to update**
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md`
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/CLAUDE.md` only if the evaluation reveals a durable architecture rule worth preserving

---

## Guardrails

- Do not backfill or rewrite `picks_history.json` as part of this plan.
- Do not change `formula_change_date` as part of this plan.
- Treat `2026-04-27` as the ROI-semantics transition slate and `2026-04-28+` as the first clean post-ROI / post-SwStr-live evaluation era unless the data itself proves otherwise.
- Every diagnostic must label rows by regime so we never accidentally mix:
  - pre-`2026-04-08`
  - `2026-04-08` through `2026-04-23`
  - `2026-04-24` through `2026-04-27`
  - `2026-04-28+`
- Every decision memo must answer:
  - what we learned
  - what we still cannot trust
  - what should be implemented next
  - what should explicitly wait

---

### Task 1: Build the regime map and evaluation windows

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e1_regime_map.py`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_e1_regime_map.py`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e1_regime_map.md`

- [ ] **Step 1: Write failing tests for regime labeling and window assignment**

```python
from analytics.diagnostics.e1_regime_map import classify_regime


def test_classify_regime_pre_formula_cutover():
    assert classify_regime("2026-04-07") == "pre_2026_04_08"


def test_classify_regime_phase_a_to_pre_swstr_live():
    assert classify_regime("2026-04-16") == "phase_a_to_pre_swstr_live"


def test_classify_regime_swstr_transition_window():
    assert classify_regime("2026-04-27") == "swstr_roi_transition"


def test_classify_regime_clean_post_roi_window():
    assert classify_regime("2026-04-28") == "post_roi_clean"
```

- [ ] **Step 2: Run the focused test file to verify it fails**

Run:

```bash
python -m pytest tests/test_e1_regime_map.py -q
```

Expected: FAIL because `e1_regime_map.py` does not exist yet.

- [ ] **Step 3: Implement the minimal regime map helper**

Implement helpers in `e1_regime_map.py` for:
- `classify_regime(date_str: str) -> str`
- `load_history() -> list[dict]`
- `summarize_regimes(rows: list[dict]) -> dict`

The summary must include:
- row count by regime
- graded row count by regime
- locked row count by regime
- `data_complete` rate by regime
- field-presence rates for `pitcher_throws`, `career_swstr_pct`, `swstr_delta_k9`, `park_factor`, `days_since_last_start`, `last_pitch_count`, `rest_k9_delta`, `opening_odds_source`, `edge`

- [ ] **Step 4: Re-run tests and confirm pass**

Run:

```bash
python -m pytest tests/test_e1_regime_map.py -q
```

Expected: PASS.

- [ ] **Step 5: Generate the regime-map report**

Run:

```bash
python analytics/diagnostics/e1_regime_map.py > analytics/output/e1_regime_map.md
```

Expected: a markdown summary that clearly identifies which date windows are safe for later projection and bet-selection analysis.

- [ ] **Step 6: Commit the regime-map helper**

```bash
git add analytics/diagnostics/e1_regime_map.py tests/test_e1_regime_map.py
git commit -m "feat(eval): add regime map diagnostic"
```

---

### Task 2: Audit storage integrity and historical truthfulness

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work\BaseballBettingEdge/analytics/diagnostics/e2_storage_integrity.py`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work\BaseballBettingEdge/tests/test_e2_storage_integrity.py`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work\BaseballBettingEdge/analytics/output/e2_storage_integrity.md`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work\BaseballBettingEdge/pipeline/fetch_results.py`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work\BaseballBettingEdge/pipeline/run_pipeline.py`

- [ ] **Step 1: Write failing tests for storage audit helpers**

```python
from analytics.diagnostics.e2_storage_integrity import field_presence_rate


def test_field_presence_rate_counts_none_as_missing():
    rows = [{"park_factor": 1.02}, {"park_factor": None}, {}]
    assert field_presence_rate(rows, "park_factor") == 1 / 3


def test_field_presence_rate_accepts_false_boolean_as_present():
    rows = [{"is_opener": False}, {"is_opener": True}, {}]
    assert field_presence_rate(rows, "is_opener") == 2 / 3
```

- [ ] **Step 2: Run the focused test file to verify it fails**

Run:

```bash
python -m pytest tests/test_e2_storage_integrity.py -q
```

Expected: FAIL because `e2_storage_integrity.py` does not exist yet.

- [ ] **Step 3: Implement the storage-integrity audit**

The diagnostic must answer:
- Are all decision-time fields that matter to future analysis actually persisted?
- Which fields are forward-only and intentionally sparse?
- Which rows are mixed transition rows that should never be used for clean benchmarking?
- Are locked rows preserving the intended pregame truth?

Minimum sections in the generated report:
- persisted field matrix by regime
- locked vs unlocked field-population comparison
- same-day transition-slate exceptions
- history fields that are safe for future modeling
- history fields that are too regime-fragile for naive reuse

The report must explicitly call out whether the current storage model is:
- good enough for season learning
- good enough for multi-season scaling
- or ready for a structural split like per-season files or a committed database

- [ ] **Step 4: Re-run tests and confirm pass**

Run:

```bash
python -m pytest tests/test_e2_storage_integrity.py -q
```

Expected: PASS.

- [ ] **Step 5: Generate the storage-integrity report**

Run:

```bash
python analytics/diagnostics/e2_storage_integrity.py > analytics/output/e2_storage_integrity.md
```

Expected: a markdown decision memo that explicitly says whether `picks_history.json` is still the right storage contract for the next stage of work.

- [ ] **Step 6: Commit the storage-integrity helper**

```bash
git add analytics/diagnostics/e2_storage_integrity.py tests/test_e2_storage_integrity.py
git commit -m "feat(eval): add storage integrity diagnostic"
```

---

### Task 3: Audit projection accuracy and lambda construction

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e3_projection_audit.py`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_e3_projection_audit.py`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e3_projection_audit.md`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/performance.py`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/pipeline/build_features.py`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/pipeline/calibrate.py`

- [ ] **Step 1: Write failing tests for projection-audit helpers**

```python
from analytics.diagnostics.e3_projection_audit import residual


def test_residual_is_actual_minus_projection():
    row = {"actual_ks": 7, "lambda": 5.8}
    assert round(residual(row), 2) == 1.20


def test_residual_returns_none_when_actual_missing():
    row = {"actual_ks": None, "lambda": 5.8}
    assert residual(row) is None
```

- [ ] **Step 2: Run the focused test file to verify it fails**

Run:

```bash
python -m pytest tests/test_e3_projection_audit.py -q
```

Expected: FAIL because `e3_projection_audit.py` does not exist yet.

- [ ] **Step 3: Implement the projection audit**

The diagnostic must answer, at minimum:
- Is overall residual bias still mostly a lambda problem?
- Is the miss concentrated by:
  - lambda bucket
  - over/under side
  - pitcher
  - opponent
  - team
  - month / regime
  - market line bucket
- Which inputs appear most associated with good vs bad residuals in the clean era?
- Is there evidence that season-environment drift matters enough to justify a monthly or rolling K-environment adjustment?

Required output sections:
- residuals by lambda bucket
- residuals by side
- residuals by line bucket
- worst over-projected pitchers
- worst under-projected pitchers
- residuals by opponent and by team
- residuals by month / regime
- activation and contribution context for `swstr_delta_k9`, `ump_k_adj`, `opp_k_rate`, `park_factor`, `rest_k9_delta`
- explicit decision section:
  - “lambda architecture is the main problem”
  - or “contextual inputs are the main problem”
  - or “projection is acceptable; bet-selection is the bigger issue”

- [ ] **Step 4: Re-run tests and confirm pass**

Run:

```bash
python -m pytest tests/test_e3_projection_audit.py -q
```

Expected: PASS.

- [ ] **Step 5: Generate the projection audit report**

Run:

```bash
python analytics/diagnostics/e3_projection_audit.py > analytics/output/e3_projection_audit.md
```

Expected: a markdown memo that clearly states what would have improved projection accuracy the most so far:
- lambda architecture
- opponent modeling
- season drift handling
- calibration regime boundaries
- or missing/underweighted signals

- [ ] **Step 6: Commit the projection-audit helper**

```bash
git add analytics/diagnostics/e3_projection_audit.py tests/test_e3_projection_audit.py
git commit -m "feat(eval): add projection audit diagnostic"
```

---

### Task 4: Audit bet selection, ranking, and staking logic

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e4_bet_selection_audit.py`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_e4_bet_selection_audit.py`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e4_bet_selection_audit.md`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/performance.py`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/index.html`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/pipeline/build_features.py`

- [ ] **Step 1: Write failing tests for bet-selection helpers**

```python
from analytics.diagnostics.e4_bet_selection_audit import stake_units


def test_stake_units_for_current_verdicts():
    assert stake_units("LEAN") == 0
    assert stake_units("FIRE 1u") == 1
    assert stake_units("FIRE 2u") == 2


def test_stake_units_unknown_verdict_defaults_zero():
    assert stake_units("PASS") == 0
```

- [ ] **Step 2: Run the focused test file to verify it fails**

Run:

```bash
python -m pytest tests/test_e4_bet_selection_audit.py -q
```

Expected: FAIL because `e4_bet_selection_audit.py` does not exist yet.

- [ ] **Step 3: Implement the bet-selection audit**

The diagnostic must answer:
- Are the current ROI bands separating good bets from bad bets?
- Is stake sizing coherent with realized ROI and drawdown?
- Is `adj_ev` the right ranking signal, or does `edge`, raw `ev`, movement, line size, or opponent context produce a better ranking?
- Are we better off narrowing the card, widening it, or re-ranking within the same card size?

Required output sections:
- realized ROI by verdict
- realized ROI by `adj_ev` bucket
- realized ROI by `edge` bucket
- realized ROI by price bucket
- realized ROI by movement-confidence bucket
- top-N ranking simulation:
  - all stakeable picks
  - top 10 by `adj_ev`
  - top 10 by `edge`
  - top 10 by win probability
- side split for stakeable picks
- drawdown / losing-streak context for 1u vs 2u plays
- explicit decision section:
  - “current bands are acceptable”
  - or “ranking metric is wrong”
  - or “staking is too aggressive / too passive”

- [ ] **Step 4: Re-run tests and confirm pass**

Run:

```bash
python -m pytest tests/test_e4_bet_selection_audit.py -q
```

Expected: PASS.

- [ ] **Step 5: Generate the bet-selection report**

Run:

```bash
python analytics/diagnostics/e4_bet_selection_audit.py > analytics/output/e4_bet_selection_audit.md
```

Expected: a markdown memo that states whether we are currently finding optimal bets the right way, or whether the projection may be acceptable but the ranking and staking layer is leaving money on the table.

- [ ] **Step 6: Commit the bet-selection helper**

```bash
git add analytics/diagnostics/e4_bet_selection_audit.py tests/test_e4_bet_selection_audit.py
git commit -m "feat(eval): add bet selection audit diagnostic"
```

---

### Task 5: Synthesize findings into the next build queue

**Files:**
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e5_synthesis.md`
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md`
- Modify only when the evaluation establishes a durable architecture rule: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/CLAUDE.md`

- [ ] **Step 1: Assemble the four reports into one synthesis memo**

The synthesis memo must have these sections:
- Safe evaluation windows
- Storage / historical truth decision
- Projection / lambda decision
- Bet-selection / staking decision
- What should be implemented next
- What should explicitly wait

- [ ] **Step 2: Write the next-plan queue directly into the synthesis memo**

The memo must end with one of these recommendation shapes:

1. **Storage-first**
   - if the main blocker is historical truth, regime hygiene, or scale limits
2. **Projection-first**
   - if lambda architecture, opponent modeling, or season drift is the dominant miss
3. **Bet-selection-first**
   - if projection is acceptable but ranking/staking is not
4. **Two-stage**
   - if one small storage fix is needed before a deeper projection audit

- [ ] **Step 3: Update the canonical tracker**

Append a dated note to `2026-04-16-model-audit-and-gaps.md` that records:
- this evaluation plan was created
- the three-track scope
- that implementation work is intentionally paused until the decision memos exist

- [ ] **Step 4: Re-run the full test suite before closing the evaluation branch**

Run:

```bash
python -m pytest tests -q
```

Expected: PASS.

- [ ] **Step 5: Commit the tracking update**

```bash
git add docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md
git commit -m "docs(eval): track post-phase-c evaluation plan"
```

---

## Success criteria

This plan is successful when we can answer these questions with evidence instead of instinct:

1. Is `picks_history.json` preserving the right truth for learning over time?
2. Is the main projection problem lambda shape, opponent context, season drift, or calibration-regime mixing?
3. Are ROI bands, `adj_ev`, and current staking actually selecting the best bets?
4. What is the next implementation plan, in priority order?

If any of those four are still answered with “probably” or “maybe,” the evaluation is not done yet.

---

## Final handoff

When the evaluation branch is done, the next session should create **one** implementation plan based on the strongest conclusion from `analytics/output/e5_synthesis.md`, not reopen all three tracks at once.

---

## Queued UI follow-up

After the evaluation decisions are complete, queue one small dashboard follow-up for line movement visualization:

- Replace the current synthetic bar-strip in v2 with a true open-to-now line chart.
- Use `FanDuel` as the default charted book, matching the app's default odds reference.
- Source the chart from real `steam.json` snapshots, not fabricated interpolation.
- Plot at minimum:
  - snapshot timestamp
  - `k_line`
  - `over` odds
  - `under` odds
- The implementation plan for this UI change must first confirm that the current `steam.json` history is trustworthy enough for per-pitcher movement rendering across the clean post-ROI era.
- If the evaluation finds one missing contract for chart trust, prefer the smallest schema addition rather than inventing UI-only derived history.
