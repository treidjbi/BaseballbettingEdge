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
| Gate C | Compact Evidence / Storage Proof | Row volume/cost is acceptable, idempotent keys are tested, and the confidence-referee report separates runtime-safe evidence from hindsight | Supabase compact research table or committed daily artifact plus shadow referee report | Model/ranking influence |
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

The first projection challenger harness now exists as
`analytics/diagnostics/k_projection_shadow_lab.py` with tests in
`tests/test_k_projection_shadow_lab.py`. It reuses the local compact dataset to
compare current lambda against transparent variants such as market shrink,
high-line tempering, leash caps, and simple recent/career rate blends. Its
output is a local `analytics/output/k_projection_shadow_lab.md` report and is
shadow-only; it does not change live projection math.

As of 2026-05-23, the first local confidence-referee diagnostic exists as
`analytics/diagnostics/confidence_referee_shadow_report.py` with tests in
`tests/test_confidence_referee_shadow_report.py`. It reads the compact outcome
dataset, writes `analytics/output/confidence_referee_shadow_report.md`, and
separates runtime-safe label inputs from hindsight validation fields. The
report is Gate C shadow evidence only; it must not change live verdicts,
thresholds, staking, notifications, provider order, projection math, or
calibration without a separate promotion plan.

Later on 2026-05-23, the same report was expanded from top-level referee
buckets into Gate C cross-slice scoreboards for side, price sign, K-line bucket,
model-versus-market relationship, timing window, quality gate,
opportunity/leash, and pitcher archetype. These scoreboards are for diagnosis
and briefing only; they are not a new gate and must not become dynamic
notifications, threshold changes, staking changes, or lambda changes without
Gate E/F evidence and Tyler approval.

Supabase is not required yet. Gate C should stay closed until we decide whether
the value of a compact daily research table beats the simplicity of local
generated artifacts. If promoted later, store compact rows only; do not retain
raw WebSocket tick history without a separate retention/cost decision.

### Rolling Evidence Update: 2026-05-20

Use the 2026-04-28 formula boundary as the live clean-regime split, but keep a
small pre/post comparison beside Gate C reads so agents do not forget how the
signal changed.

For near-term comparisons, use 2026-04-08 through 2026-04-27 as the fair
immediate pre-bump reference window. Older pre-4/28 rows mix earlier regimes
and should be treated as broader history, not a like-for-like baseline.

The current read through graded rows on 2026-05-19:

- Immediate pre-bump FIRE weighted: 347 rows, 190-157, +12.95u on 536 staked
  units, +2.42% ROI. FIRE flat: +17.94u, +5.17% ROI.
- Clean post-bump FIRE weighted: 321 rows, 163-158, -9.12u on 397 staked
  units, -2.30% ROI. FIRE flat: -11.93u, -3.72% ROI.
- The shape inverted: pre-bump FIRE 1u, unders, and high-edge rows were strong;
  post-bump FIRE 1u, unders, and high-edge rows are weak.
- Post-bump FIRE 2u, overs, moderate-edge rows, beat-close-price rows, and
  pre-30 timing rows look more promising, but this is still shadow evidence.

Do not use this comparison to roll back thresholds, staking, formula date, or
provider behavior. Use it to keep Gate C honest: current-regime buckets matter
most, and any future Gate E/F candidate must survive side, price, line, timing,
CLV, quality, and provider slices rather than replaying a pre-bump pattern.

## Consolidated Source Of Truth

This plan is the controlling handoff for the pitcher K research dataset,
Gate C confidence-referee work, batter-handedness Path A/Path B, opportunity
and leash tracking, and K-projection challenger evidence.

Use the other docs as summaries or inventories:

- `AGENTS.md`: repo entrypoint and short operating reminders
- `docs/current-state.md`: current status snapshot and next checkpoint pointers
- `docs/research/market-tracker-map.md`: tracker inventory and duplication
  guardrails
- `docs/operational-risk-register.md`: risk, retention, and promotion
  guardrails
- `docs/superpowers/plans/2026-05-07-bet-conversion-shadow-audit.md`:
  historical diagnostic plan for the first bet-selection-first audit

When a gate changes, update this plan first, then update `AGENTS.md` and
`docs/current-state.md` only with a short pointer or status summary. The goal
is to keep the detailed rules here instead of repeating them in multiple files.

## Daily Brief Synthesis Contract

The BBE Operations Brief should digest this dataset after grading and report:

- row count, duplicate-key count, missing results, missing odds, and
  `picks_history.json` reconciliation
- tracked pick count, rows with price CLV, beat-close-price count, and
  beat-close-line count
- model-versus-market-favorite counts and any W/L or PnL skew if enough rows
  are graded
- opportunity and leash-risk bucket counts, with notable loss clusters
- whether live-market checkpoint rows from BoltOdds/PropLine are available or
  still absent from the compact dataset
- whether lineup-handedness fields are populated or still collection-only
  placeholders
- a compact Gate C bucket scoreboard for the clean 2026-04-28+ regime:
  FIRE 1u/2u, over/under, moderate edge, high edge, CLV/no-CLV, timing window,
  quality gate, model-versus-market favorite, opportunity/leash, and pitcher
  archetype
- the immediate pre-bump versus post-bump comparison when the comparison changes
  the interpretation of a current bucket

The daily read should explain what the trackers suggest, but explicitly avoid
turning them into live betting rules until Gate E/F. In plain terms: this is
the market-memory and confidence-referee layer, not an automatic model change.

## Gate C / Confidence-Referee Scope

Gate C should make the evidence easier to read and trust. It must not make the
model more aggressive by itself.

The referee should compare:

- adjusted EV, raw edge, and model margin
- side-specific conversion for overs and unders
- price buckets, plus/minus sides, and no-vig market-favorite context
- opening-source context and price/line CLV
- model-versus-market relationship
- quality-gate level, reasons, and data-maturity state
- live-market movement checkpoints when available
- opportunity, leash-risk, and pitcher-archetype buckets
- K-projection shadow-lab challenger results
- lineup count and batter-handedness field availability

Gate C can create shadow labels such as:

- `bet_now_candidate`
- `wait_for_late_data`
- `demand_better_price`
- `monitor_only`
- `do_not_upgrade_without_more_rows`

Those labels are research annotations only. They may appear in reports, but
they must not change `verdict`, `adj_ev`, stake sizing, push notifications,
provider order, calibration, or dashboard production artifacts.

### Runtime-Safe Versus Hindsight Evidence

Runtime-safe fields are allowed in future candidate rules because they can be
known before lock:

- pitcher, side, K line, book, odds, and scheduled game time
- model side, model win probability, no-vig gap, edge, EV, adjusted EV, and
  projected Ks
- quality-gate level, reasons, and data-maturity state
- opening source and pregame price/line movement checkpoints
- model-versus-market favorite relationship
- lineup availability, lineup count, and handedness counts when actually known
  before lock
- rest/workload metadata, opener/starter-mismatch state, umpire state, and park
  factor
- opportunity/leash buckets if built only from pregame workload, role, lineup,
  and team-context evidence

Hindsight-only fields are useful for learning but cannot be used as pregame
rule inputs:

- result, actual Ks, PnL, and miss distance
- beat-close price/line labels after the market closes
- actual innings pitched, pitch count, batters faced, and times-through-order
- post-start market movement
- postgame injury, bullpen, or role explanations

Every report should call out which side of this line it is using. This is the
main leakage guardrail for the confidence-referee layer.

### Gate C Proof Standard

Gate C is open only when the shadow report shows a cleaner ranking or selection
story across enough clean rows to be worth continued collection. A useful story
must survive at least these slices:

- over versus under
- plus-money versus minus-money
- low, medium, and high K-line buckets
- FIRE 1u versus FIRE 2u and strong LEAN buckets
- model with market favorite versus model fading market favorite
- clean quality gates versus soft-capped rows
- price CLV, line CLV, and no-CLV rows
- opportunity/leash and pitcher-archetype buckets

One positive slate or one attractive bucket is not enough. Gate C may recommend
more evidence collection, a better shadow label, or a Gate E research question.
It cannot recommend a live threshold, staking, formula, or provider change.

Gate C should preserve a short "what changed since the 2026-04-28 bump" note.
If a bucket flipped versus the immediate pre-bump window, treat that as a
skepticism prompt, not as proof the old regime should be restored. Current
post-bump evidence has priority for live-candidate thinking.

## Batter Handedness / Lineup Context Plan

### Current Path A

Path A is the live behavior.

- Aggregate batter K% is live.
- `pipeline/fetch_batter_stats.py` returns the current caller contract:
  `{normalized_batter_name: {"vs_R": float, "vs_L": float}}`.
- True per-batter `vs_R` / `vs_L` splits remain collection-only.
- The pipeline may cache Baseball-Reference platoon split samples in
  `data/batter_splits_YYYY.json`.
- Projection still uses aggregate K% for both `vs_R` and `vs_L`, then applies
  the league-average platoon adjustment in
  `build_features.calc_lineup_k_rate`.
- Switch hitters are modeled as batting opposite the pitcher's hand.

This is deliberately conservative. It captures a real handedness effect without
letting noisy early split samples swing the projection.

### Collection-Only Fields

The compact dataset should keep these fields even while they are incomplete:

- `pitcher_throws`
- `lineup_count`
- `lineup_right_batters`
- `lineup_left_batters`
- `lineup_switch_batters`
- `handedness_matchup_bucket`
- projected-to-confirmed lineup K-rate delta when available

Unknown values should stay `None`, not invented neutral values. The daily brief
should report whether these fields are populated or still placeholders.

### Path B Trigger

Path B becomes a candidate only when both conditions are true:

- the repo has reached the old volume reminder of `params.json.sample_size >=
  400` or the calendar is on/after 2026-05-25
- the compact dataset shows enough confirmed-lineup and split-coverage evidence
  to test the change without guessing

The date/sample trigger is a reminder to investigate, not permission to promote.
Any live projection change still needs Gate E/F evidence and a separate
implementation plan.

### Path B Implementation Shape

When approved later, Path B should:

1. Implement real split collection in `pipeline/fetch_batter_stats.py`.
2. Return real `vs_R` / `vs_L` K% plus per-split plate-appearance sample size.
3. Apply Bayesian regression toward league same-hand or opposite-hand averages,
   weighted by split PA.
4. In `pipeline/build_features.py`, use real split values when available.
5. Remove the generic `+ platoon_k_delta(...)` adjustment only for batters with
   trusted real splits, while keeping `PLATOON_K_DELTA` / `platoon_k_delta()`
   as the fallback.
6. Bump `formula_change_date` in `data/params.json` only on the actual live
   formula-change deploy date.
7. Verify `TestCalcLineupKRate` and `TestPlatoonKDelta` still cover fallback
   behavior.

### Path B Promotion Checks

Before Path B can affect live lambda, prove:

- at least 10 straight graded slates include stable lineup-handedness fields
- split coverage is good enough for confirmed lineups, not only projected
  lineups
- fallback rows are explicit and do not silently look like real split rows
- holdout accuracy improves versus Path A
- the improvement survives RHP/LHP starters, over/under sides, and K-line
  buckets
- no hidden degradation appears in FIRE 2u or clean quality-gate rows

If the evidence is thin, keep Path A live and continue collecting.

## Opportunity / Leash Evidence Plan

The compact row should keep opportunity and leash evidence because pitcher K
misses often come from workload and role, not only strikeout skill.

Already represented or planned in compact rows:

- `avg_ip`
- `recent_start_count`
- `days_since_last_start`
- `last_pitch_count`
- `is_opener`
- `starter_mismatch`
- `opportunity_bucket`
- `leash_risk_bucket`
- `actual_ip`
- `actual_pitch_count`
- `batters_faced`

Pregame opportunity/leash labels may be used for future candidate rules only if
they are built from information known before lock. Actual IP, pitch count, and
batters faced are postgame explanations and must remain hindsight-only.

## Open Evidence Backlog

Before adding a new table or tracker, first ask whether the compact outcome row
can answer the question with a derived label. Add new storage only when the
source data is truly missing.

Still-needed source data:

- confirmed lineup handedness counts by pitcher hand
- projected-to-confirmed lineup K-rate delta
- actual innings pitched, pitch count, batters faced, and times-through-order
- injury/ramp-up and return-from-IL flags
- bullpen rest and likely leash/team pull tendency
- weather, roof, and game-total/run-environment context
- provider-specific bet-time consensus rows once BoltOdds is promoted

Already answerable from the compact row or derived labels:

- price CLV and line CLV
- CLV type
- process-outcome bucket
- bet timing window
- model-versus-market relationship
- model edge and projection-margin buckets
- large-edge skepticism flag and reasons
- pitcher archetype bucket
- opportunity and leash-risk buckets
- K-projection challenger comparison

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
- `accepted_bet_source`
- `notification_event_id`
- `shadow_candidate_id`

The current local enrichment primarily reads tracked-pick history fields such as
locked line, locked odds, and `locked_at`. Future accepted-bet enrichment should
optionally read Supabase `accepted_bets` and prefer actual Tyler bet rows for
bet-time fields when a row can be matched safely by slate, normalized pitcher,
side, book, line, odds, and accepted time. If no accepted-bet row exists, keep
the current pick-history fallback so historical artifact research remains
available.

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

## Gate C: Compact Evidence / Storage Proof

**Purpose:** Decide whether this should live only as generated files or as a
compact Supabase research table, and prove the confidence-referee report can
summarize the evidence without creating leakage or live behavior changes.

**Files:**

- Create only after approval: `supabase/migrations/YYYYMMDD_pitcher_k_outcome_research.sql`
- Create: `analytics/diagnostics/pitcher_k_outcome_storage_audit.py`
- Create: `analytics/diagnostics/confidence_referee_shadow_report.py`
- Create: `tests/test_pitcher_k_outcome_storage_audit.py`
- Create: `tests/test_confidence_referee_shadow_report.py`
- Write local-only: `analytics/output/confidence_referee_shadow_report.md`

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

- [ ] **Step 3: Build the shadow confidence-referee report**

The report should read the compact artifact and summarize:

- candidate labels such as `bet_now_candidate`, `wait_for_late_data`,
  `demand_better_price`, and `monitor_only`
- runtime-safe evidence used by each label
- hindsight-only evidence used for explanation, not selection
- row counts and win/loss or PnL by side, price, K-line, quality-gate,
  model-versus-market, CLV, opportunity/leash, pitcher-archetype, and
  K-projection challenger slices
- rows that look like large model edges but carry stacked caution signals
- sparse slices that need more collection before being trusted

- [ ] **Step 4: Gate C pass criteria**

Gate C opens when:

- estimated Supabase row growth is comfortably within free-tier expectations
- idempotent `dataset_key` behavior is tested
- no raw snapshot flood is copied into the research table
- the research table stores compact derived rows only
- the shadow confidence-referee report separates runtime-safe evidence from
  hindsight-only explanation
- candidate labels are report-only and do not alter `verdict`, `adj_ev`,
  staking, notifications, provider order, calibration, or dashboard artifacts
- the report survives the core over/under, plus/minus, K-line, quality-gate,
  model-versus-market, CLV, and opportunity/leash slices without relying on one
  positive slate
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
- tracked pick count
- price CLV and line CLV availability
- beat-close-price and beat-close-line counts
- model-versus-market relationship counts
- opportunity and leash-risk bucket counts
- confidence-referee candidate-label counts
- runtime-safe versus hindsight-only field availability
- live-market checkpoint availability
- lineup-handedness field availability
- Path A versus Path B handedness coverage evidence
- accepted-bet match count and unmatched accepted-bet rows
- notification-attributed accepted bets once `notification_event_id` and
  `shadow_candidate_id` are wired through the dashboard
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
- Path B batter-handedness projection changes

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
- for Path B handedness, confirmed-lineup split coverage and holdout lift
  versus Path A

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
