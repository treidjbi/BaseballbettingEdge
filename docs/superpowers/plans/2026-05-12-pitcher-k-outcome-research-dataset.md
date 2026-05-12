# Pitcher K Outcome Research Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-only pitcher strikeout outcome research dataset that preserves market, model, context, and result evidence for future selection and projection improvements.

**Architecture:** Start with a local generated research artifact built from existing source-of-truth files and exported live-market evidence. After local backfill quality is proven, promote the same compact row contract to an idempotent Supabase research table or daily generated artifact. No field from this dataset may affect live picks, thresholds, staking, notifications, provider order, or calibration until a separate promotion gate is approved.

**Tech Stack:** Python 3.11, pytest, committed dashboard archives, `data/picks_history.json`, Supabase shadow exports, existing `analytics/diagnostics/` patterns, optional future Supabase compact research table.

---

## Why This Exists

The current shadow audits are telling us that price, side, favorite behavior,
line movement, and market agreement probably matter. The next step is not one
more ad hoc report. The next step is a durable research dataset where every
pitcher K market outcome can be sliced consistently.

This should answer questions like:

- Does this pitcher tend to clear low K lines but fail high K lines?
- Are unders at minus money behaving differently from overs at minus money?
- Did the market move with us, against us, or flip sides before first pitch?
- Did a broad-book move matter more than one-book noise?
- Did the model lose because projection was wrong, price was bad, line moved,
  context changed, or variance happened?
- Are there pitcher/team/park/rest/umpire/lineup contexts where we should be
  more skeptical?

This season can become the data collection season. Next season can use the
evidence.

## Non-Negotiable Guardrails

- Shadow-only until a separate promotion plan is approved.
- Do not change `pipeline/run_pipeline.py` model behavior in this plan.
- Do not change `data/params.json`, verdict thresholds, staking, or
  `formula_change_date`.
- Do not let live-market evidence overwrite production artifacts.
- Do not treat post-start movement as pregame signal.
- Do not train or tune on rows that would not have been known before lock time.
- Do not add provider spend, higher polling cadence, or new always-on
  infrastructure without checking `docs/provider-cost-ledger.md`.
- Do not create a large raw-data retention burden without checking
  `docs/operational-risk-register.md`.

## Gate Summary

| Gate | Name | Opens When | Allows | Blocks |
| --- | --- | --- | --- | --- |
| Gate A | Schema Approval | Canonical row contract and source hierarchy are documented | Local diagnostic/test work | Storage writes and automation |
| Gate B | Local Backfill Proof | Backfill covers at least 95% of clean archived pitcher markets and reconciles graded results | Local generated research artifact | Supabase table writes |
| Gate C | Compact Storage Proof | Row volume/cost is acceptable and idempotent keys are tested | Supabase compact research table or committed daily artifact | Model/ranking influence |
| Gate D | Daily Collection Proof | Daily append works for 10 straight graded slates with zero duplicate keys and clean reconciliation | Routine post-grading dataset refresh | Live behavior changes |
| Gate E | Research Readiness | At least 500 clean graded side rows, 30 graded slates, and stable core slices | Candidate selection/ranking hypotheses | Production thresholds/staking |
| Gate F | Promotion Candidate | Holdout/backtest lift survives side, price, line, and provider slices | A separate model-selection implementation plan | Direct deployment from this dataset |

## Current Implementation Status

As of 2026-05-12, Gate A and the local portion of Gate B are implemented.

- Contract doc: `docs/research/pitcher-k-outcome-dataset.md`
- Contract tests: `tests/test_pitcher_k_outcome_dataset_contract.py`
- Local diagnostic: `analytics/diagnostics/pitcher_k_outcome_dataset.py`
- Local tests: `tests/test_pitcher_k_outcome_dataset.py`
- Local generated outputs:
  - `analytics/output/pitcher_k_outcome_dataset.jsonl`
  - `analytics/output/pitcher_k_outcome_dataset_summary.md`

Clean-window proof from `2026-04-28+`: 574 graded side rows, 0 missing results,
0 duplicate dataset keys, 0 missing team/opponent, 0 missing book odds, and 2
rows missing model-side probability fields. The same build reconciled 294/294
clean graded `picks_history.json` rows, including 15 unique pitcher/side
fallback matches where the archived official-close line differed from the
locked pick-history line.

The compact row contract now also tracks bet-time/CLV fields from
`picks_history.json`, model-versus-market relationship, edge/margin buckets,
pitcher hand, lineup count, handedness placeholders, and opportunity/leash
buckets. On the same clean window, all 294 tracked picks have price CLV fields;
51 beat the official-close price and 10 beat the official-close line. These are
shadow research facts only, not betting rules.

Supabase is not required yet. Gate C should stay closed until we decide whether
the value of a compact daily research table beats the simplicity of local
generated artifacts. If promoted later, store compact rows only; do not retain
raw WebSocket tick history without a separate retention/cost decision.

## Canonical Row Grain

Use one row per:

```text
slate_date + game_id/game_pk + normalized_pitcher + side + k_line + context_snapshot
```

For the first version, `context_snapshot` should be one of:

- `official_close`: final official archived production state
- `opening`: preview/opening baseline where available
- `pre_120`, `pre_60`, `pre_30`, `pre_15`, `pre_5`, `final_pre_start`:
  rebuilt from raw live-market snapshots when available

Avoid one giant row that tries to hold every possible timestamp. A long-form
checkpoint dataset will be easier to slice and less likely to hide timing
leakage.

## Target Fields

### Identity

- `slate_date`
- `game_pk` or `provider_event_id` when available
- `pitcher`
- `normalized_pitcher`
- `pitcher_mlb_id` when available
- `team`
- `opp_team`
- `home_away`
- `park_team`
- `game_time`
- `context_snapshot`

### Market

- `side`
- `k_line`
- `bookmaker_key`
- `bookmaker_title`
- `american_odds`
- `opening_odds`
- `closing_odds`
- `price_sign`
- `price_bucket`
- `market_favorite_side`
- `favorite_gap_no_vig`
- `no_vig_side_probability`
- `side_price_movement`
- `line_movement`
- `minus_to_plus_or_plus_to_minus`

### Model

- `model_side`
- `model_win_prob`
- `model_no_vig_gap`
- `projected_ks`
- `k_margin_to_line`
- `edge`
- `ev`
- `adj_ev`
- `verdict`
- `raw_verdict`
- `quality_gate_level`
- `quality_gate_reasons`
- `data_maturity`

### Live Market Movement

- `provider`
- `checkpoint_minutes_to_game`
- `book_count`
- `books_seen`
- `toward_pick_count`
- `away_from_pick_count`
- `better_now_count`
- `worse_now_count`
- `market_consensus`
- `bet_value_consensus`
- `broad_confirmation`
- `reversal_book_count`
- `volatile_book_count`
- `best_book`
- `best_line`
- `best_odds`
- `best_is_off_market`

### Baseball Context

- `actual_ks`
- `result`
- `pnl`
- `miss_distance`
- `miss_distance_bucket`
- `line_bucket`
- `is_home_start`
- `is_opener`
- `starter_mismatch`
- `lineup_used`
- `opp_k_rate`
- `umpire`
- `umpire_has_rating`
- `ump_k_adj`
- `park_factor`
- `days_since_last_start`
- `last_pitch_count`
- `rest_k9_delta`
- `season_k9`
- `recent_k9`
- `career_k9`
- `current_swstr_pct`
- `career_swstr_pct`

### Bet Timing / CLV

- `is_tracked_pick`
- `pick_history_match_type`
- `bet_time_line`
- `bet_time_odds`
- `bet_time_book`
- `bet_time_at`
- `closing_line`
- `price_clv_cents`
- `line_clv_delta`
- `beat_close_price`
- `beat_close_line`

### Research Buckets

- `model_market_relationship`
- `model_edge_bucket`
- `projection_margin_bucket`
- `pitcher_throws`
- `lineup_count`
- `lineup_right_batters`
- `lineup_left_batters`
- `lineup_switch_batters`
- `handedness_matchup_bucket`
- `avg_ip`
- `recent_start_count`
- `opportunity_bucket`
- `leash_risk_bucket`
- `actual_ip`
- `actual_pitch_count`
- `batters_faced`

## Gate A: Schema Approval

**Purpose:** Make the dataset contract explicit before writing storage or
automation.

**Files:**

- Create: `docs/research/pitcher-k-outcome-dataset.md`
- Create: `tests/test_pitcher_k_outcome_dataset_contract.py`
- Future create: `analytics/diagnostics/pitcher_k_outcome_dataset.py`

- [x] **Step 1: Write the contract doc**

Document:

- row grain
- source hierarchy
- field names
- required vs optional fields
- no-leakage rule
- idempotent key
- sample row

- [x] **Step 2: Write failing schema contract tests**

The tests should require:

- every row has `dataset_key`
- every row has identity, market, model, and result fields
- `context_snapshot` is in the approved set
- post-start snapshots are excluded from pregame research rows
- unknown optional values are `None`, not invented neutral values

- [x] **Step 3: Gate A pass criteria**

Gate A is open when:

- contract doc exists
- contract tests fail for missing implementation
- Tyler agrees the field set is enough for future research

## Gate B: Local Backfill Proof

**Purpose:** Prove we can reconstruct useful history locally before adding new
storage.

**Files:**

- Create: `analytics/diagnostics/pitcher_k_outcome_dataset.py`
- Create: `tests/test_pitcher_k_outcome_dataset.py`
- Write local-only: `analytics/output/pitcher_k_outcome_dataset.jsonl`
- Write local-only: `analytics/output/pitcher_k_outcome_dataset_summary.md`

- [x] **Step 1: Build archive loader**

Read:

- `dashboard/data/processed/YYYY-MM-DD.json`
- `data/picks_history.json`
- optional exported `market_pick_evidence`
- optional exported `live_market_display_state`
- optional exported `market_snapshots`

- [x] **Step 2: Build official-close rows**

Generate `official_close` rows from archived production artifacts. Include
PASS/LEAN/FIRE markets, not only staked picks.

- [x] **Step 3: Join graded results**

Join by:

```text
slate_date + normalized_pitcher + side + k_line
```

Fallback join without `k_line` is allowed only when one side/line exists for
that pitcher/date.

- [x] **Step 4: Build local summary report**

Report:

- total rows
- clean-window rows
- graded rows
- rows missing result
- rows missing team/opponent
- rows missing book odds
- rows missing model fields
- rows by context snapshot
- duplicate dataset keys

- [x] **Step 5: Gate B pass criteria**

Gate B opens when:

- at least 95% of clean archived pitcher markets produce dataset rows
- 100% of clean `picks_history.json` win/loss rows reconcile to a dataset row
- duplicate dataset keys = 0
- no production files are modified
- focused tests pass

## Gate C: Compact Storage Proof

**Purpose:** Decide whether this should live only as generated files or as a
compact Supabase research table.

**Files:**

- Create only after approval: `supabase/migrations/YYYYMMDD_pitcher_k_outcome_research.sql`
- Create: `analytics/diagnostics/pitcher_k_outcome_storage_audit.py`
- Create: `tests/test_pitcher_k_outcome_storage_audit.py`

- [ ] **Step 1: Estimate row volume**

Use the local backfill artifact to estimate:

- rows per slate
- rows per month
- added rows if checkpoint snapshots are included
- projected full-season row count

- [ ] **Step 2: Choose storage mode**

Option A: generated local artifacts only.

- Lowest cost
- Easiest to reason about
- Best until we know the exact report cadence

Option B: compact Supabase table.

- Easier for cross-session querying
- Better for future dashboard/research UI
- Requires retention and idempotent upserts

Recommendation: Option A until Gate B is clean, then Option B only if the
dataset becomes part of weekly review.

- [ ] **Step 3: Gate C pass criteria**

Gate C opens when:

- estimated Supabase row growth is comfortably within free-tier expectations
- idempotent `dataset_key` behavior is tested
- no raw snapshot flood is copied into the research table
- the research table stores compact derived rows only
- `docs/operational-risk-register.md` retention rules are updated if storage is promoted

## Gate D: Daily Collection Proof

**Purpose:** Make the dataset routine after grading without affecting the live
app.

**Files:**

- Modify after approval: `.github/workflows/pipeline.yml` or add separate
  manual/scheduled diagnostics workflow
- Create: `scripts/build_pitcher_k_outcome_dataset.py`
- Create: `tests/test_build_pitcher_k_outcome_dataset.py`

- [ ] **Step 1: Add idempotent daily build script**

The script should:

- run after grading
- read official artifacts
- optionally read exported live-market evidence
- write compact local output or Supabase rows
- print counts and duplicate-key checks
- exit nonzero if reconciliation fails

- [ ] **Step 2: Run for 10 graded slates without promotion**

Track:

- row count
- duplicate count
- result reconciliation count
- missing context count
- runtime
- storage growth

- [ ] **Step 3: Gate D pass criteria**

Gate D opens when:

- 10 straight graded slates build successfully
- duplicate dataset keys = 0
- 100% of graded picks reconcile
- no live artifact is changed by the dataset build
- storage growth is acceptable

## Gate E: Research Readiness

**Purpose:** Decide when the dataset is strong enough to propose candidate
rules.

Minimum sample:

- at least 500 clean graded side rows
- at least 30 graded slates
- at least 75 graded rows from live-market checkpoint evidence
- at least 50 rows each for over and under FIRE/LEAN groups
- at least 25 rows each for plus-money and minus-money picked sides

Pitcher-specific minimum:

- no pitcher-level tendency rule until a pitcher has at least 5 graded starts
  in the dataset
- no pitcher-level price/line rule until at least 3 starts share a comparable
  K-line bucket
- no team/opponent rule until at least 40 relevant rows exist

Allowed at Gate E:

- write research reports
- propose shadow ranking features
- flag buckets for more collection
- create a Gate F promotion proposal

Still blocked at Gate E:

- live threshold changes
- staking changes
- calibration changes
- automatic pitcher-specific adjustments

## Gate F: Promotion Candidate

**Purpose:** Require proof before any dataset-derived signal affects the model.

Gate F opens only when a candidate rule:

- improves a primary metric on a holdout window, not only the training window
- survives separate over and under slices
- survives plus and minus price slices
- survives low, medium, and high K-line buckets
- does not rely on post-start or unavailable-before-lock data
- has an explainable failure mode
- can be turned off with one config flag

Minimum proof before live behavior:

- at least 800 clean graded side rows, or Tyler explicitly accepts a smaller
  personal-use experiment
- at least 50 candidate-selected graded rows
- positive flat ROI and better win rate than the current comparable bucket
- no hidden degradation in FIRE 2u rows
- written rollback plan

Promotion requires a separate implementation plan. This dataset plan must not
be used as the approval to change the live model.

## First Research Questions To Queue

1. Market favorite:
   - Does model agreement with the market favorite beat model fades?
   - Does this differ for overs versus unders?

2. Price:
   - Which minus buckets are actually winning?
   - Which plus buckets are traps versus real value?
   - Does `-115` versus `-105` matter after no-vig adjustment?

3. Movement:
   - Did broad movement toward our pick predict wins?
   - Did better available number but market moving away from us predict losses?
   - Did reversals mean volatility/noise or opportunity?

4. Pitcher tendencies:
   - Which pitchers repeatedly beat or miss their K line?
   - Are misses clustered around specific line buckets?
   - Does the model systematically overtrust specific pitcher archetypes?

5. Context:
   - Home vs away
   - opponent K profile
   - lineup confirmed vs projected
   - umpire known/rated vs unknown
   - rest and pitch count
   - park factor

## Execution Recommendation

Do not execute this whole plan at once.

Recommended order:

1. Gate A schema doc and tests.
2. Gate B local backfill artifact.
3. Let the dataset run locally through at least one weekly review.
4. Decide whether Supabase storage is worth it.
5. Add daily automation only after reconciliation is boring.

The business value is not the table itself. The value is making every future
bet-selection question answerable without rebuilding context from scratch.
