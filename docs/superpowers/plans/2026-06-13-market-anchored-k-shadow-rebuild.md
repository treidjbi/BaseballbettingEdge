# Market Anchored K Shadow Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-only diagnostic that tests whether a market-anchored pitcher strikeout projection plus a stricter selector would have produced better historical decisions than the current high-edge/FIRE posture.

**Architecture:** Read the durable Gate C pitcher outcome dataset and create a report-only comparison of current projection, market-implied projection, and a market-anchored blend. Score both projection quality and selector-style outcomes without changing live lambda, EV thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.

**Tech Stack:** Python 3.11, standard library math/json/pathlib, pytest, existing `data/research/gate_c/pitcher_k_outcome_dataset.jsonl`, output under `analytics/output/`.

---

## Guardrails

- Shadow-only. No live pipeline behavior changes.
- Do not edit `pipeline/run_pipeline.py`, `pipeline/build_features.py`, `data/params.json`, verdict thresholds, staking, provider flags, notification behavior, lock behavior, retention behavior, dashboard artifacts, or `formula_change_date`.
- Use only pregame/runtime-safe fields to define shadow selector membership.
- Keep result, PnL, CLV, actual IP, actual pitch count, and batters faced as scoring/explanation fields only.
- Treat theoretical selections from non-tracked official-close rows as research only, not proof of historical bet availability.

## File Structure

- Create `analytics/diagnostics/market_anchored_k_shadow_rebuild.py`
  - Reads Gate C JSONL.
  - Builds one market object per pitcher/date/line.
  - Converts no-vig market probability into a market-implied K projection.
  - Blends the current baseball projection toward the market projection.
  - Scores projection metrics and selector buckets.
  - Renders `analytics/output/market_anchored_k_shadow_rebuild.md`.
- Create `tests/test_market_anchored_k_shadow_rebuild.py`
  - Unit tests for probability inversion, market grouping, selector rules, and report boundary text.
- Modify `docs/current-state.md` only after the report exists, and only to note the shadow lane/report location.

## Task 1: Projection Primitives

**Files:**
- Create: `tests/test_market_anchored_k_shadow_rebuild.py`
- Create: `analytics/diagnostics/market_anchored_k_shadow_rebuild.py`

- [x] **Step 1: Write failing tests**

Test that:

```python
from analytics.diagnostics import market_anchored_k_shadow_rebuild as lab


def test_market_projection_inverts_no_vig_probability():
    projection = lab.market_implied_projection(k_line=4.5, over_probability=0.5)
    assert 4.0 < projection < 5.0

    favorite_over = lab.market_implied_projection(k_line=4.5, over_probability=0.62)
    assert favorite_over > projection
```

- [x] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_market_anchored_k_shadow_rebuild.py -q
```

Expected: fail because the module does not exist.

- [x] **Step 3: Implement minimal probability helpers**

Implement:

```python
def poisson_cdf(k: int, lam: float) -> float:
    ...

def poisson_over_probability(k_line: float, lam: float) -> float:
    ...

def market_implied_projection(k_line: float, over_probability: float) -> float:
    ...
```

- [x] **Step 4: Run green test**

Run:

```powershell
python -m pytest tests/test_market_anchored_k_shadow_rebuild.py -q
```

Expected: pass.

## Task 2: Market Grouping And Anchored Projection

**Files:**
- Modify: `tests/test_market_anchored_k_shadow_rebuild.py`
- Modify: `analytics/diagnostics/market_anchored_k_shadow_rebuild.py`

- [x] **Step 1: Write failing tests**

Test that one market is built from over/under side rows and that the anchored projection shrinks toward the market:

```python
def test_build_markets_pairs_over_and_under_rows():
    rows = [_row(side="over", no_vig_side_probability=0.55), _row(side="under", no_vig_side_probability=0.45)]
    markets = lab.build_markets(rows)
    assert len(markets) == 1
    assert markets[0]["over_row"]["side"] == "over"
    assert markets[0]["under_row"]["side"] == "under"


def test_market_anchor_projection_shrinks_current_toward_market():
    row = _row(side="over", projected_ks=6.8, no_vig_side_probability=0.5)
    anchored = lab.market_anchor_projection(row)
    assert anchored < 6.8
    assert anchored > lab.market_implied_projection(5.5, 0.5)
```

- [x] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_market_anchored_k_shadow_rebuild.py -q
```

Expected: fail for missing grouping/projection functions.

- [x] **Step 3: Implement grouping and blend**

Rules:

- Market key: `slate_date + context_snapshot + normalized_pitcher + k_line`.
- Prefer explicit over-side `no_vig_side_probability`; derive from under side as `1 - under_probability` if needed.
- Blend current projection toward market projection with lower baseball weight for capped quality, high/medium leash risk, short-leash opportunity, high lines, or model-fade rows.

- [x] **Step 4: Run green test**

Run:

```powershell
python -m pytest tests/test_market_anchored_k_shadow_rebuild.py -q
```

Expected: pass.

## Task 3: Selector Scoreboard

**Files:**
- Modify: `tests/test_market_anchored_k_shadow_rebuild.py`
- Modify: `analytics/diagnostics/market_anchored_k_shadow_rebuild.py`

- [x] **Step 1: Write failing tests**

Test selector buckets:

```python
def test_selector_requires_runtime_safe_market_anchor_support():
    row = _row(
        side="over",
        projected_ks=5.9,
        no_vig_side_probability=0.52,
        quality_gate_level="clean",
        model_market_relationship="model_agrees_with_favorite",
        model_no_vig_gap=0.04,
    )
    labels = lab.selector_labels(row)
    assert "market_anchor_core" in labels
    assert "market_anchor_strict" in labels

    fade = dict(row, model_market_relationship="model_fades_favorite")
    assert "market_anchor_strict" not in lab.selector_labels(fade)
```

- [x] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_market_anchored_k_shadow_rebuild.py -q
```

Expected: fail for missing selector logic.

- [x] **Step 3: Implement selector buckets**

Implement report-only labels:

- `market_anchor_side_agrees`: anchored projection points to the row side.
- `market_anchor_core`: side agrees, model/no-vig gap is positive, and anchored edge is in a modest positive band.
- `market_anchor_strict`: core plus market-favorite agreement, clean quality, stable workload, and non-high-risk timing/line context.
- `market_price_only_favorite`: row side equals market favorite.
- `current_action_fire`: current displayed/actionable verdict is FIRE.

- [x] **Step 4: Run green test**

Run:

```powershell
python -m pytest tests/test_market_anchored_k_shadow_rebuild.py -q
```

Expected: pass.

## Task 4: Report Generation

**Files:**
- Modify: `analytics/diagnostics/market_anchored_k_shadow_rebuild.py`
- Output: `analytics/output/market_anchored_k_shadow_rebuild.md`

- [x] **Step 1: Write failing report-boundary test**

Test that the report states:

- shadow-only
- no production changes
- projection comparison
- selector scoreboard
- recommendation/read rule

- [x] **Step 2: Implement report rendering**

Report sections:

1. Executive read
2. Projection scoreboard
3. Tracked-pick selector scoreboard
4. Theoretical official-close selector scoreboard
5. Slice risks
6. Read rule and next decision

- [x] **Step 3: Run focused tests**

Run:

```powershell
python -m pytest tests/test_market_anchored_k_shadow_rebuild.py -q
```

Expected: pass.

- [x] **Step 4: Generate report**

Run:

```powershell
python analytics/diagnostics/market_anchored_k_shadow_rebuild.py
```

Expected: writes `analytics/output/market_anchored_k_shadow_rebuild.md`.

## Task 5: Handoff

**Files:**
- Modify: `docs/current-state.md`
- Modify: this plan

- [x] **Step 1: Update model-lane docs**

Add a short note to the model lane saying the market-anchored K shadow rebuild exists, is report-only, and is the next research read before any true v2 selector/model plan.

- [x] **Step 2: Keep production gates closed**

Confirm in docs and final response:

- no live lambda change
- no threshold/staking change
- no provider/source change
- no notification/lock/dashboard behavior change

## 2026-06-13 Implementation Result

- Added `analytics/diagnostics/market_anchored_k_shadow_rebuild.py` and
  `tests/test_market_anchored_k_shadow_rebuild.py`.
- Generated `analytics/output/market_anchored_k_shadow_rebuild.md` from
  `data/research/gate_c/pitcher_k_outcome_dataset.jsonl`.
- First post-grading smoke read: `1,840` clean official-close side rows,
  `956` clean tracked rows, and `920` official-close markets.
- Projection read: market-implied projection beat current model MAE/RMSE
  (`1.732`/`2.168` vs. `1.832`/`2.286`) and side accuracy (`56.9%` vs.
  `53.9%`). The market-anchored blend was similar (`1.741` MAE, `2.175`
  RMSE, `56.9%` side accuracy).
- Tracked selector read: current FIRE was `549` rows, `269-280`, `-39.93u`,
  `-7.3% ROI`; market-anchor core was `485` rows, `269-216`, `-5.48u`,
  `-1.1% ROI`; market-anchor strict was `149` rows, `90-59`, `+6.41u`,
  `+4.3% ROI`.
- Gate status: promising shadow evidence, not a production plan. A live v2
  selector still needs rolling-window and slice survival plus a separate
  Tyler-approved feature-flagged plan.

## 2026-06-13 Post-Grading Review Hook

- Added `--run-market-anchored-rebuild` to
  `scripts/build_pitcher_k_outcome_dataset.py`, mirroring the existing
  workload/no-vig audit hook and using the freshly rebuilt Gate C JSONL as the
  report input.
- Added `scripts/run_post_grading_shadow_reports.py` as the Render-friendly
  daily command. It runs:
  `python scripts/run_post_grading_shadow_reports.py`
- Intended Render cron:
  - service name: `bbe-gate-c-post-grading-review`
  - schedule: `7 11 * * *` UTC (`4:07 AM` Phoenix), after the
    `bbe-pipeline-grading` cron at `17 10 * * *` UTC
  - command: `python scripts/run_post_grading_shadow_reports.py`
- The runner rebuilds the durable Gate C artifact, the workload/no-vig audit,
  and the market-anchored shadow report, then prints the Executive Read and
  Read Rule sections to Render logs for daily review.
- This schedule is review-only. It does not publish dashboard artifacts,
  update calibration, change lambda, change thresholds/staking, change provider
  source/order, change notification behavior, change locks, or change
  retention.
