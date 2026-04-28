# One-Week Evaluation Cadence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use the new post-Phase-C evaluation tooling over the next week to decide whether the next implementation plan should focus on lambda shape, opponent/environment structure, or bet-ranking/staking conversion.

**Architecture:** This is an operating cadence, not a model-change plan. It treats `2026-04-28+` as the clean post-ROI / post-SwStr-live regime, re-runs the evaluation diagnostics on a fixed schedule, and records decisions only when enough clean graded rows exist to support them.

**Tech Stack:** Python 3.11, pytest, `data/picks_history.json`, `data/params.json`, `analytics/diagnostics/e1_regime_map.py`, `e2_storage_integrity.py`, `e3_projection_audit.py`, `e4_bet_selection_audit.py`, `therundown_fetch_audit.py`, markdown notes in `analytics/output/`.

---

## Objective

Over the next seven days, we want to answer these questions with clean-window evidence instead of mixed-era instinct:

1. Is the new post-`2026-04-28` model directionally healthier than the old regime?
2. Is lambda-shape still the dominant miss, especially in the upper buckets?
3. Are we converting good projections into bets correctly, or is the 2u ladder still too aggressive?
4. Is `edge` separating stronger than `adj_ev`, even after the ROI semantics cleanup?
5. Can TheRundown intake be made cheaper and less noisy without losing resolved pitcher coverage?

This cadence deliberately avoids random tweaks while the first clean regime accumulates.

---

## Canonical files

**Read every check-in**
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/data/picks_history.json`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/data/params.json`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/superpowers/plans/2026-04-27-post-phase-c-model-evaluation.md`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e1_regime_map.md`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e2_storage_integrity.md`

**Run repeatedly**
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e3_projection_audit.py`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e4_bet_selection_audit.py`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/therundown_fetch_audit.py`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/performance.py`

**Write local-only outputs**
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e3_projection_audit.md`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e4_bet_selection_audit.md`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/therundown_fetch_audit.md`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e5_synthesis.md`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/post_phase_c_weekly_check.md`

---

## Guardrails

- Do not change `formula_change_date` during this cadence.
- Do not change verdict thresholds during this cadence.
- Do not change staking during this cadence.
- Do not judge the new model from `2026-04-24` through `2026-04-27`; that window is transition-only.
- Treat `2026-04-28+` as the only clean regime for decisions about the new model.
- Do not change TheRundown production query parameters from one slate alone. Require at least two audit runs where the cheaper query preserves resolved pitcher coverage.
- If a day’s pipeline is obviously degraded, record it and exclude it from interpretation before making model decisions.

---

### Task 1: Confirm the clean-window sample is growing correctly

**Files:**
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/data/picks_history.json`
- Run: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e1_regime_map.py`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e1_regime_map.md`

- [ ] **Step 1: Re-run the regime map at the start of each morning review**

Run:

```bash
python analytics/diagnostics/e1_regime_map.py > analytics/output/e1_regime_map.md
```

Expected: `post_roi_clean` row count increases as fresh rows are added.

- [ ] **Step 2: Check whether the clean regime has graded rows yet**

Look for:
- `post_roi_clean` row count
- `post_roi_clean` graded row count

Expected:
- before the first grading cycle, graded row count may still be `0`
- after the first grading cycle, it should become nonzero and stay isolated from transition rows

- [ ] **Step 3: Record the count in the weekly note**

Append a bullet to `analytics/output/post_phase_c_weekly_check.md`:

```markdown
- YYYY-MM-DD morning: `post_roi_clean` rows = X, graded = Y
```

---

### Task 2: Re-run the projection audit once clean graded rows exist

**Files:**
- Run: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e3_projection_audit.py`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e3_projection_audit.md`

- [ ] **Step 1: Re-run the projection audit each day after grading**

Run:

```bash
python analytics/diagnostics/e3_projection_audit.py > analytics/output/e3_projection_audit.md
```

Expected:
- if no clean graded rows exist yet, the report stays mostly empty
- once clean graded rows exist, the side and lambda-bucket sections populate

- [ ] **Step 2: Watch for the first real lambda-shape signal**

Look for:
- high lambda buckets with clearly negative mean residuals
- over/under asymmetry in the clean regime
- repeated pitcher archetype clusters
- whether `projection vs sportsbook line vs actual` suggests the line itself was smarter than our tail assumptions on certain buckets

Expected decision signals:
- if `6+` or high-tail buckets stay materially negative, queue bucketed lambda correction
- if residuals cluster more by side than by lambda, queue side/price conversion work
- if residuals cluster by team/opponent profile, queue environment/opponent structure work

- [ ] **Step 3: Record the daily decision hint**

Append a bullet to `analytics/output/post_phase_c_weekly_check.md`:

```markdown
- YYYY-MM-DD projection read: [tail issue | side issue | opponent/environment issue | insufficient sample]
```

---

### Task 3: Re-run the bet-selection audit each day after grading

**Files:**
- Run: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e4_bet_selection_audit.py`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e4_bet_selection_audit.md`

- [ ] **Step 1: Re-run the bet-selection audit**

Run:

```bash
python analytics/diagnostics/e4_bet_selection_audit.py > analytics/output/e4_bet_selection_audit.md
```

Expected:
- verdict, adjusted EV ROI, and edge sections all populate from history

- [ ] **Step 2: Compare `FIRE 1u` versus `FIRE 2u` in the clean regime context**

Read with caution:
- season-wide summary is still mixed-regime context
- the real signal matters once clean graded rows accumulate

Expected decision signals:
- if `FIRE 2u` still underperforms meaningfully after several clean slates, queue a staking/ladder review
- if `adj_ev` buckets do not separate but `edge` buckets do, queue a ranking-conversion review

- [ ] **Step 3: Record the daily bet-selection hint**

Append a bullet to `analytics/output/post_phase_c_weekly_check.md`:

```markdown
- YYYY-MM-DD bet-selection read: [adj_ev separating | edge stronger | 2u weak | insufficient sample]
```

---

### Task 4: Run the broad analytics health-check every 2-3 days

**Files:**
- Run: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/performance.py`

- [ ] **Step 1: Run the current-era analytics slice**

Run:

```bash
python analytics/performance.py --since 2026-04-28
```

Expected:
- no dead-signal warning for the clean regime
- B5 activation rates stay healthy for SwStr, opening odds, and other critical fields

- [ ] **Step 2: Cross-check the model-health lines**

Look for:
- `swstr_delta_k9 != 0`
- `opening_over_odds set`
- `opening_under_odds set`
- `park_factor populated`
- `pitcher_throws populated`

Expected:
- those should remain live
- if any drift toward `0%`, investigate pipeline integrity before blaming the model

- [ ] **Step 3: Record any pipeline-health caveat**

Append to `analytics/output/post_phase_c_weekly_check.md`:

```markdown
- YYYY-MM-DD health read: [healthy | degraded upstream field X | degraded storage field Y]
```

---

### Task 5: Audit TheRundown intake noise and CLV/steam readiness

**Files:**
- Run: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/therundown_fetch_audit.py`
- Write local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/therundown_fetch_audit.md`

- [ ] **Step 1: Run the TheRundown query-shape audit after a fresh pipeline run**

Run:

```bash
python analytics/diagnostics/therundown_fetch_audit.py 2026-04-28 > analytics/output/therundown_fetch_audit.md
```

Replace `2026-04-28` with the current slate date during future check-ins.

Expected:
- `offset_affiliates` should preserve resolved pitcher coverage versus `current`
- `offset_affiliates` should use fewer datapoints than `current`
- `offset_affiliates_main_line` is expected to be too sparse until proven otherwise
- `books_seen` should confirm which TheRundown affiliate IDs are actually present, including whether Kalshi `25` is available

- [ ] **Step 2: Record the daily TheRundown intake read**

Append a bullet to `analytics/output/post_phase_c_weekly_check.md`:

```markdown
- YYYY-MM-DD TheRundown read: current resolved = X, offset+affiliate resolved = Y, datapoints saved = Z%, books seen = [...]
```

- [ ] **Step 3: Decide whether production fetch can be narrowed**

Only queue a production fetch change if at least two audit runs show:
- `offset_affiliates` matches or improves resolved pitcher count
- no important target book disappears
- Kalshi `25` is present often enough to track
- `main_line=true` remains too sparse or becomes reliable enough to reconsider

Expected decision signals:
- if `offset_affiliates` preserves coverage, queue a small production query update
- if Kalshi is present but thin, track it in steam/audit first before making it actionable
- if official openers become necessary for CLV, queue an opener comparison task rather than relying on `price_delta`

---

### Task 6: Make the one-week decision

**Files:**
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e3_projection_audit.md`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e4_bet_selection_audit.md`
- Read: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/therundown_fetch_audit.md`
- Modify local-only: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/output/e5_synthesis.md`

- [ ] **Step 1: At the one-week mark, update the synthesis memo**

Add a dated section:

```markdown
## One-week post-Phase-C decision

- Clean graded rows observed: X
- Projection read: ...
- Bet-selection read: ...
- TheRundown intake read: ...
- Recommended next implementation track: ...
```

- [ ] **Step 2: Choose one next-plan direction only**

Choose exactly one:
- `projection-first`
- `bet-selection-first`
- `environment/opponent-first`
- `therundown-intake-first`
- `two-stage` if one small storage or instrumentation fix still blocks confidence

- [ ] **Step 3: Explicitly defer what should wait**

The weekly decision must also say what **not** to change yet:
- thresholds
- staking
- lambda shape
- extra features

until the chosen next implementation plan is written

---

## Success criteria

This cadence is successful if, after roughly a week of clean post-`2026-04-28` history, we can answer:

1. Is the new model directionally healthier than the old regime?
2. Is the next biggest win lambda shape, environment structure, or bet conversion?
3. Is `adj_ev` the right main ranking signal, or is `edge` still carrying more truth?
4. Is `FIRE 2u` still justified?
5. Can the TheRundown query be narrowed to reduce data-point burn/noise while preserving resolved pitcher coverage?

If those are still answered with “not enough clean data,” the right response is to extend the cadence, not to start random tuning.
