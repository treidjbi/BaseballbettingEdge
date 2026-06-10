# Gate F Pre-Close CLV Proxy Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert post-close CLV evidence into a runtime-safe pre-close proxy that can be validated as a future FIRE re-entry selector.

**Architecture:** Add a shadow-only diagnostic that predicts historical CLV support from fields available before lock: side price movement, no-vig gap, market/model relationship, quality, timing, volatility/reversal counts when present, multi-book/broad-confirmation fields when present, and provider/book coverage when present. CLV remains the validation target; it must not define live candidate membership.

**Tech Stack:** Python 3.11, pytest, existing Gate C JSONL dataset, existing analytics output reports.

---

## Guardrails

- CLV fields (`beat_close_price`, `beat_close_line`, `price_clv_cents`, `line_clv_delta`) may score outcomes and evaluate proxy capture, but they must not affect proxy membership or score.
- Runtime-safe score inputs may include:
  - `side_price_movement`
  - `model_no_vig_gap`
  - `model_market_relationship`
  - `quality_gate_level`
  - `bet_timing_window`
  - `line_bucket`, `price_sign`, `side`
  - `broad_confirmation`, `book_count`, `books_seen`
  - `toward_pick_count`, `away_from_pick_count`
  - `better_now_count`, `worse_now_count`
  - `reversal_book_count`, `volatile_book_count`
  - `best_is_off_market`
  - provider/source fields when present
- Hindsight-only fields such as result, PnL, actual Ks, actual workload, and CLV may evaluate the proxy only.
- No live projection, verdict, threshold, staking, provider, notification, lock, retention, or dashboard source-of-truth behavior changes.

## File Map

- Create: `analytics/diagnostics/gate_f_preclose_clv_proxy_lab.py`
  - Scores pre-close CLV proxy evidence.
  - Compares proxy labels to historical CLV target and PnL.
  - Reports FIRE re-entry candidate volume and slice risk.
- Create: `tests/test_gate_f_preclose_clv_proxy_lab.py`
  - Proves CLV does not influence proxy score.
  - Covers scoring, target labels, candidate summaries, and report language.
- Output: `analytics/output/gate_f_preclose_clv_proxy_lab.md`
  - Decision report for proxy strength and next required data fields.
- Modify: `docs/current-state.md`
- Modify: `docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md`

## Tasks

### Task 1: Proxy Score Contract

**Files:**
- Create: `tests/test_gate_f_preclose_clv_proxy_lab.py`
- Create: `analytics/diagnostics/gate_f_preclose_clv_proxy_lab.py`

- [x] Write failing test that changing CLV outcome fields does not change `preclose_clv_proxy_score()`.
- [x] Write failing test for positive pre-lock score features: movement toward pick, no-vig support, market favorite agreement, clean quality, pre-30 timing, multi-book support, and low volatility.
- [x] Write failing test for risk penalties: movement against pick, off-market best book, reversals, volatility, late timing, and under/fade context.
- [x] Implement the score and label helpers.

### Task 2: Candidate Summary

**Files:**
- Modify: `analytics/diagnostics/gate_f_preclose_clv_proxy_lab.py`
- Modify: `tests/test_gate_f_preclose_clv_proxy_lab.py`

- [x] Filter clean tracked win/loss rows from 2026-04-28 onward.
- [x] Define `positive_clv_target` from CLV fields only for evaluation.
- [x] Summarize proxy buckets by rows, W-L, PnL, ROI, positive CLV target capture, retained/capped FIRE rows, and recent-window PnL.
- [x] Add slice checks by side, K-line, price sign, timing, quality, model-market relationship, no-vig label, and movement label.

### Task 3: Report And Docs

**Files:**
- Modify: `analytics/diagnostics/gate_f_preclose_clv_proxy_lab.py`
- Create: `analytics/output/gate_f_preclose_clv_proxy_lab.md`
- Modify: `docs/current-state.md`
- Modify: `docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md`

- [x] Render a concise report with:
  - available proxy fields;
  - missing richer market fields;
  - proxy scoreboard;
  - CLV capture;
  - candidate readiness;
  - next data/feature gap.
- [x] Generate the report from current Gate C rows.
- [x] Update docs with the current read and guardrails.
- [x] Run focused and touched-area tests.

## Success Criteria

- The report says whether the current pre-close proxy captures enough of the profitable CLV-supported rows to become a watch candidate.
- The report explicitly distinguishes CLV target fields from live-safe proxy inputs.
- No production behavior changes.

## 2026-06-10 Implementation Result

- Added `analytics/diagnostics/gate_f_preclose_clv_proxy_lab.py`,
  `tests/test_gate_f_preclose_clv_proxy_lab.py`, and generated
  `analytics/output/gate_f_preclose_clv_proxy_lab.md`.
- The first naive score incorrectly treated large model/no-vig edge as CLV
  support. Empirical Gate C slices showed the opposite: low/moderate edge plus
  market movement/price/timing support better captures positive CLV. The final
  score rewards those runtime-safe predictors and keeps CLV fields out of
  membership.
- Current report read: strong pre-close proxy is a `watch_more` bucket, not
  ready for production: `291` rows, `164-127`, `+9.05u`, `+3.1% ROI`, `93`
  positive-CLV rows (`32.0%`), `113` source-FIRE rows, `39` retained FIRE rows,
  and `74` capped-to-LEAN rows.
- Blockers: recent PnL is `-8.55u`, there are `12` negative slice risks, and
  current Gate C rows lack most richer live-market fields needed for a stronger
  proxy.
- No production behavior, lambda, threshold, staking, provider, notification,
  lock, retention, or dashboard source-of-truth behavior changed.
