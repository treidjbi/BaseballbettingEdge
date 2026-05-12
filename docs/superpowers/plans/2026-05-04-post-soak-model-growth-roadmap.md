# Post-Soak Model Growth Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move BaseballBettingEdge from healthy soak mode into mature model growth without shipping projection or staking changes before the clean sample can support them.

**Architecture:** Keep the current pipeline, dashboard, quality gates, and static JSON contract intact. Add a decision-gated roadmap where source reliability and shadow analytics can improve immediately, while live projection math, batter handedness, lambda-shape corrections, and staking changes require explicit clean-sample thresholds.

**Tech Stack:** Python 3.11, GitHub Actions, `data/picks_history.json`, `data/params.json`, `data/batter_splits_2026.json`, diagnostics under `analytics/diagnostics/`, output notes under `analytics/output/`, static dashboard JSON under `dashboard/data/processed/`.

---

## Current Baseline

As of 2026-05-04 morning after the May 3 grading cycle:

- Clean regime: `2026-04-28+`
- Clean rows: `158`
- Clean graded rows: `146`
- Open clean rows: `12`
- Calibration complete-data sample: `117`
- Graded actionable `FIRE 1u`: `72`
- Graded actionable `FIRE 2u`: `24`
- Current model warning: global residual is close to neutral, but side and high-lambda shape are not stable enough yet.
- Current source warning: The Odds fallback is exhausted or unauthorized, so PropLine is temporarily carrying fallback coverage when TheRundown is thin.

This is real signal now, but it is not enough to justify changing live model math or staking.

---

## Decision Gates

These gates define what can happen now versus what must wait.

### Gate A: Collection And Instrumentation

Allowed now, with no minimum pick count:

- Add diagnostics.
- Improve notes and dashboards that explain source quality.
- Keep collecting batter handedness split samples.
- Add shadow-only calculations that do not affect `ev_*["verdict"]`, `adj_ev`, pick seeding, or calibration.
- Fix obvious pipeline/source bugs.
- Keep PropLine as temporary fallback while The Odds is not reliable.

Required guardrail:

- Shadow fields must be clearly named and excluded from live projection, verdicts, grading, and calibration unless a later gate explicitly promotes them.

### Gate B: Post-Soak Synthesis

Minimum to write the next implementation plan:

- At least `200` clean graded rows.
- At least `8` fully graded clean slates.
- No unresolved pipeline-health defect affecting the included slates.
- At least one fresh run each of:
  - `analytics/diagnostics/e1_regime_map.py`
  - `analytics/diagnostics/e3_projection_audit.py`
  - `analytics/diagnostics/e4_bet_selection_audit.py`
  - `analytics/diagnostics/e5_quality_gate_audit.py --since 2026-04-28`
  - `analytics/diagnostics/market_price_outcome_audit.py`
  - `analytics/diagnostics/live_market_outcome_audit.py`

If the project has fewer than `200` clean graded rows, the allowed next step is analysis, shadow instrumentation, or source cleanup, not live model changes.

### Gate C: Live Projection Change

Minimum to implement a live projection change:

- At least `250` clean graded rows.
- At least `10` fully graded clean slates.
- At least `100` graded actionable FIRE rows.
- The proposed change must identify one primary target:
  - `projection-first`
  - `bet-selection-first`
  - `environment/opponent-first`
  - `therundown-intake-first`
  - `two-stage`
- The plan must state what is explicitly not changing.
- A shadow or backtest read must show the proposed change improves the target metric without making source-degraded rows look artificially better.

Live projection changes include:

- Batter handedness splits used in `calc_lineup_k_rate`.
- Lambda bucket correction.
- New environment/opponent feature inputs.
- Changing how `edge`, `ev`, or `adj_ev` feed ranking.

### Gate D: Staking Or Threshold Change

Minimum to alter FIRE/LEAN thresholds or stake ladder:

- At least `350` clean graded rows.
- At least `50` graded actionable `FIRE 2u` rows.
- At least `150` graded actionable FIRE rows total.
- Evidence that `FIRE 2u` underperformance or overperformance is not just one or two slate swings.

Until this gate is met, keep thresholds and staking static.

### Gate E: Batter Handedness Path B Promotion

Minimum to promote real batter vs-LHP/vs-RHP splits into live projection:

- Preserve the existing AGENTS trigger:
  - `data/params.json.sample_size >= 400`, or
  - current date is on or after `2026-05-25`.
- Also require:
  - At least `250` clean graded rows.
  - At least `10` fully graded clean slates.
  - Split collection audit shows at least `80%` coverage of confirmed-lineup batters by name.
  - At least `65%` of confirmed-lineup batters have usable handedness split sample metadata, not just aggregate fallback.
  - A shadow comparison over at least `100` pitcher records shows either:
    - lower absolute residual in opponent/environment slices, or
    - materially better side conversion without worse high-lambda tail behavior.

If the date/sample trigger is met but split coverage is weak, do not promote Path B. Extend collection and keep Path A live.

---

## Recommended Next Track

Current evidence points to a two-stage path:

1. **Stage 1: Continue soak to Gate B while improving shadow/source visibility.**
   This keeps PropLine, batter split collection, quality-gate auditing, and post-slate notes moving.

2. **Stage 2: Choose between bet-conversion-first and projection-first at Gate B.**
   The current diagnostics show side asymmetry and weak adjusted-EV separation. Batter handedness remains a strong maturity feature, but it should be promoted only if the opponent/environment read becomes the primary blocker.

Do not choose `staking-first` yet. The `FIRE 2u` sample is too small.

---

## File Plan

Create:

- `docs/superpowers/plans/2026-05-04-post-soak-model-growth-roadmap.md`

Likely future files if this plan is executed:

- `analytics/output/post_soak_synthesis.md`
- `analytics/output/batter_handedness_shadow_audit.md`
- `analytics/output/model_growth_decision.md`

Possible future code files, only after gates are met:

- `analytics/diagnostics/batter_handedness_shadow_audit.py`
- `analytics/diagnostics/model_growth_decision_gate.py`
- `tests/test_batter_handedness_shadow_audit.py`
- `tests/test_model_growth_decision_gate.py`

---

## Task 1: Keep The Soak Open Until Gate B

**Files:**

- Read: `data/picks_history.json`
- Read: `data/params.json`
- Run: `analytics/diagnostics/e1_regime_map.py`
- Run: `analytics/diagnostics/e3_projection_audit.py`
- Run: `analytics/diagnostics/e4_bet_selection_audit.py`
- Run: `analytics/diagnostics/e5_quality_gate_audit.py`
- Run: `analytics/diagnostics/market_price_outcome_audit.py`
- Write local-only: `analytics/output/post_soak_synthesis.md`

- [ ] **Step 1: Run the clean-window diagnostics after each grading run**

Run:

```bash
python analytics/diagnostics/e1_regime_map.py > analytics/output/e1_regime_map.md
python analytics/diagnostics/e3_projection_audit.py > analytics/output/e3_projection_audit.md
python analytics/diagnostics/e4_bet_selection_audit.py > analytics/output/e4_bet_selection_audit.md
python analytics/diagnostics/e5_quality_gate_audit.py --since 2026-04-28 > analytics/output/e5_quality_gate_audit.md
python analytics/diagnostics/market_price_outcome_audit.py --end-date YYYY-MM-DD > analytics/output/market_price_outcome_audit.md
python analytics/diagnostics/live_market_outcome_audit.py --market-pick-evidence PATH --live-market-display PATH --market-snapshots PATH > analytics/output/live_market_outcome_audit.md
```

Use the latest fully graded archive date for `YYYY-MM-DD`.

Expected:

- `post_roi_clean` graded count increases after each grading run.
- E3 residuals stay separated by clean regime.
- E4 keeps verdict, adjusted-EV, and edge buckets separated.
- E5 shows raw versus actionable verdict counts.
- Market price outcome audit shows whole-market PASS/LEAN/FIRE price behavior,
  over/under side buckets, and relative market favorite results such as
  `-115` versus `-105`.
- Live market outcome audit shows BoltOdds/PropLine movement contexts joined to
  graded outcomes, including market-with-us/against-us, better/worse available
  number, over/under side, broad confirmation, and reversal/volatility buckets.

- [ ] **Step 2: Check Gate B numerically**

Use this current threshold:

```text
Gate B is open only when:
- clean graded rows >= 200
- fully graded clean slates >= 8
- no unresolved data-source defect affects the included slates
```

Expected as of 2026-05-04:

```text
clean graded rows = 146
Gate B = not open yet
Action = keep soaking and collect shadow evidence
```

- [ ] **Step 3: Append the daily decision line**

Append to `analytics/output/post_soak_synthesis.md`:

```markdown
## YYYY-MM-DD Gate B Check

- Clean graded rows: X
- Clean graded slates: Y
- Source caveat: none | explain degraded slate
- Gate B status: open | closed
- Action: keep soaking | write next implementation plan
```

Expected:

- No live model-change plan is written until Gate B is open.

---

## Task 2: Add A Batter Handedness Shadow Audit Plan Before Promotion

**Files:**

- Read: `AGENTS.md`
- Read: `data/batter_splits_2026.json`
- Read: `data/picks_history.json`
- Read: `dashboard/data/processed/YYYY-MM-DD.json`
- Future create after Gate A approval: `analytics/diagnostics/batter_handedness_shadow_audit.py`
- Future test after Gate A approval: `tests/test_batter_handedness_shadow_audit.py`
- Write local-only: `analytics/output/batter_handedness_shadow_audit.md`

- [ ] **Step 1: Confirm Path A remains live**

Check:

```text
AGENTS.md says Path A is live:
- aggregate batter K%
- league-average platoon K delta
- real splits collection only
```

Expected:

- Do not wire real splits into `calc_lineup_k_rate` yet.

- [ ] **Step 2: Audit split collection coverage**

When writing the audit script, it must report:

```text
- confirmed-lineup batters seen
- batters matched to split cache
- batters with vs_R and vs_L sample metadata
- batters falling back to aggregate
- team/opponent slices with weak coverage
- top missing names by frequency
```

Expected promotion-read thresholds:

```text
confirmed-lineup batter name coverage >= 80%
usable split sample metadata >= 65%
shadow comparison pitcher records >= 100
```

- [ ] **Step 3: Keep Path B as shadow-only until Gate E**

Shadow output may include:

```json
{
  "shadow_lineup_k_rate_path_b": 0.241,
  "shadow_lineup_k_rate_delta": 0.014,
  "shadow_split_coverage": 0.89,
  "shadow_split_sample_quality": "usable"
}
```

Expected:

- These fields must not affect `lambda`, `raw_lambda`, `applied_lambda`, `ev`, `adj_ev`, `verdict`, `seed_picks`, or calibration.

- [ ] **Step 4: Decide whether Path B deserves a live implementation plan**

Gate E must be met:

```text
params.sample_size >= 400 OR date >= 2026-05-25
clean graded rows >= 250
fully graded clean slates >= 10
split name coverage >= 80%
usable split metadata >= 65%
shadow comparison records >= 100
```

Expected:

- If all are true, write a dedicated Path B implementation plan.
- If any are false, keep collecting and do not promote.

---

## Task 3: Decide Whether Bet Conversion Beats Projection Work

**Files:**

- Read: `analytics/output/e3_projection_audit.md`
- Read: `analytics/output/e4_bet_selection_audit.md`
- Read: `analytics/output/e5_quality_gate_audit.md`
- Write local-only: `analytics/output/model_growth_decision.md`

- [ ] **Step 1: Compare adjusted EV against edge**

Use E4:

```text
If 17%+ adjusted EV underperforms while 2-6% edge or 4-6% edge outperforms,
the next track should lean bet-conversion-first.
```

Expected as of 2026-05-04:

```text
17%+ adjusted EV is negative ROI.
2-4% and 4-6% edge buckets are positive.
Decision hint = bet-conversion-first is a serious candidate.
```

- [ ] **Step 2: Check whether the issue is projection shape instead**

Use E3:

```text
If high lambda buckets remain materially negative and side residuals stay wide,
projection-first or lambda-shape work remains a serious candidate.
```

Expected as of 2026-05-04:

```text
High-lambda buckets are still negative.
Over side residual is negative and under side residual is positive.
Decision hint = projection shape is still unresolved.
```

- [ ] **Step 3: Make one recommendation only at Gate B**

At Gate B, write:

```markdown
## Model Growth Decision

- Clean graded rows:
- Clean graded slates:
- Primary problem:
- Recommended next track:
- Deferred tracks:
- Why this is not a threshold/staking change yet:
```

Expected:

- Choose one primary next track.
- Do not blend multiple model changes into one implementation batch.

---

## Task 4: Source Reliability Track For PropLine And The Odds

**Files:**

- Read: `.github/workflows/pipeline.yml`
- Read: `pipeline/fetch_odds.py`
- Read: `data/preview_lines.json`
- Read: `dashboard/data/processed/today.json`
- Write local-only: `analytics/output/source_reliability_notes.md`

- [ ] **Step 1: Treat PropLine as temporary fallback, not a full migration**

Current behavior should remain:

```text
TheRundown primary -> The Odds FD/DK fallback -> PropLine fallback
```

Expected:

- PropLine can keep the slate alive.
- Do not make PropLine the primary provider from one healthy fallback week.

- [ ] **Step 2: Track The Odds failure separately from model performance**

Record:

```text
- The Odds status: ok | quota exhausted | unauthorized | no coverage
- PropLine status: not used | used | partial | failed
- merged fallback records
- line-conflict skips
- raw books returned
```

Expected:

- Source failures do not get misread as model-quality failures.

- [ ] **Step 3: Promote provider changes only through source evidence**

Minimum to change provider order:

```text
- at least 5 slates with PropLine fallback evidence
- at least 3 slates where PropLine coverage is compared against TheRundown
- no recurring parsing mismatch on pitcher names or line values
- clear target-book coverage advantage
```

Expected:

- Provider changes remain source-track work, not projection-track work.

---

## Task 5: Write The Next Live Implementation Plan Only After Gates

**Files:**

- Create after Gate B: `docs/superpowers/plans/YYYY-MM-DD-<chosen-track>.md`
- Read: `analytics/output/model_growth_decision.md`
- Read: `analytics/output/post_soak_synthesis.md`

- [ ] **Step 1: Confirm the gate before writing**

Required:

```text
Gate B open:
- clean graded rows >= 200
- clean graded slates >= 8
- no unresolved source defect
```

Expected:

- If Gate B is closed, do not write a live implementation plan.

- [ ] **Step 2: Pick one implementation track**

Allowed choices:

```text
projection-first
bet-selection-first
environment/opponent-first
therundown-intake-first
two-stage
```

Expected:

- One track only.
- If batter handedness is chosen, it must also pass Gate E.

- [ ] **Step 3: State what will not change**

Every next implementation plan must include:

```markdown
## Explicit Deferrals

- Verdict thresholds:
- Staking ladder:
- Formula change date:
- Batter handedness projection:
- Provider order:
```

Expected:

- No hidden scope creep.
- No accidental formula/staking changes bundled into source cleanup.

---

## Success Criteria

This roadmap is working when:

- The next model decision is made from at least `200` clean graded rows, not one emotional slate.
- Live projection changes wait for at least `250` clean graded rows and a target-specific shadow read.
- Staking and threshold changes wait for at least `350` clean graded rows and `50` graded actionable `FIRE 2u` rows.
- Batter handedness Path B is researched now, but promoted only after both the AGENTS trigger and coverage gates are met.
- PropLine remains useful fallback infrastructure without becoming an accidental model variable.
- Each future implementation plan chooses exactly one primary track.
