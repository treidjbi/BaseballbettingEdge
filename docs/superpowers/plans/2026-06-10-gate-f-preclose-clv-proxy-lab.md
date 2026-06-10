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

## 2026-06-10 Gate C Market-Field Enrichment Follow-Up

- Added Gate C enrichment from `analytics/output/market_agreement_tracker.jsonl`
  into `analytics/diagnostics/pitcher_k_outcome_dataset.py` and
  `scripts/build_pitcher_k_outcome_dataset.py`.
- The enrichment ignores `post_start` tracker rows, chooses the latest/richest
  pre-start tracker row by slate date, normalized pitcher, side, and K-line
  with side fallback, and copies only shadow research fields such as provider,
  checkpoint, `book_count`, `books_seen`, toward/away counts, better/worse
  counts, consensus labels, reversal/volatility counts, and movement labels.
- Regenerated the durable Gate C artifact after rebuilding
  `actual_opportunity_backfill.json`, preserving actual-opportunity coverage:
  `1,718/1,718` rows have actual IP, pitch count, and batters faced. The
  durable Gate C summary now shows `195` market-agreement rows, `195`
  market-book-count rows, and `195` toward/away-count rows.
- Rerun CLV proxy read: `886` clean tracked win/loss rows, `155` positive-CLV
  rows, and `192/886` tracked rows (`21.7%`) with provider/book/movement fields
  populated. `strong_preclose_clv_proxy` remains `watch_more`, not ready:
  `299` rows, `166-133`, `+7.18u`, `+2.4% ROI`, `97` positive-CLV rows
  (`32.4%`), `121` source-FIRE rows, `41` retained FIRE rows, and `80`
  capped-to-LEAN rows.
- Remaining blockers: recent PnL is `-6.30u`, there are `13` negative slice
  risks, broad-confirmation rows are still `0`, `best_is_off_market` coverage
  is still `0.0%`, and most tracked rows still lack tracker-backed market
  fields.
- No production behavior, lambda, threshold, staking, provider, notification,
  lock, retention, or dashboard source-of-truth behavior changed.

## 2026-06-10 Live Display Confidence Follow-Up

- Added a second Gate C enrichment pass from
  `analytics/output/market_agreement_inputs/live_market_display_state.json`.
  It only accepts `game_state=pregame` rows whose `latest_snapshot_at` is before
  first pitch, so post-start display snapshots cannot feed the pre-close proxy.
- The enrichment fills `live_display_provider`, `live_display_state`,
  `live_display_latest_snapshot_at`, `broad_confirmation`,
  `best_is_off_market`, `best_book`, `best_line`, `best_odds`, and book-board
  counts/seen books when a matching pregame display row exists.
- Regenerated Gate C now has `223` live-display rows, `281` market-book-count
  rows, `42` broad-confirmation rows, and `75` best-off-market rows while
  preserving `1,718/1,718` actual-opportunity coverage.
- Rerun CLV proxy read: `book_count` coverage improved to `278/886` tracked
  rows (`31.4%`) and `best_is_off_market` coverage improved to `220/886`
  (`24.8%`). The candidate became more conservative, not more promotable:
  `strong_preclose_clv_proxy` is `294` rows, `162-132`, `+3.54u`, `+1.2% ROI`,
  `92` positive-CLV rows (`31.3%`), `121` source-FIRE rows, `41` retained FIRE
  rows, `80` capped-to-LEAN rows, `-12.33u` recent PnL, and `13` negative
  slices.
- Interpretation: the extra book-board evidence increases confidence by
  exposing risk. It is a reason to keep observing and not re-enter FIRE yet.
- No production behavior, lambda, threshold, staking, provider, notification,
  lock, retention, or dashboard source-of-truth behavior changed.
