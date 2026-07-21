# Frozen No-Drag Composite Prospective Canary Design

Date: 2026-07-21

Status: approved design for a post-grading-only shadow canary. This design does
not approve live model, verdict, threshold, staking, provider, notification,
lock, UI, retention, artifact-contract, source-of-truth, or
`formula_change_date` changes.

## Executive Decision

Freeze `combined_runtime_broad_no_hindsight_no_drag` as a new versioned
research candidate and collect prospective evidence beginning with the
2026-07-21 slate.

The versioned selector id is:

`combined_runtime_broad_no_hindsight_no_drag_v1`

The new canary displaces `strict_runtime_core_plus_selective_lean` as the lead
research candidate. The older packet remains a comparison/control and must not
be rewritten as though it always selected the no-drag policy.

## Decision Baseline

The freeze occurs after the 2026-07-20 graded slate.

| Read | Rows | Record | Units | ROI |
| --- | ---: | ---: | ---: | ---: |
| Locked clean-window baseline | 186 | 124-62 | +29.20u | +15.7% |
| Locked current-provider baseline | 52 | 36-16 | +9.17u | +17.6% |
| Locked recent-14-slate reference | 35 | 24-11 | +5.68u | +16.2% |

The current-provider review floor is 75 graded candidate rows. The locked
starting point is 52, so the canary begins with 23 additional prospective
current-provider rows required.

Historical rebuilds may identify data corrections or drift, but they must not
rewrite the locked 52-row starting point, reduce the 23-row prospective
requirement, or quietly change the selector contract.

## Goals

1. Freeze the exact runtime-safe selection rule under a versioned id.
2. Count only 2026-07-21-and-later rows as prospective evidence.
3. Keep historical, prospective, and combined reads separate.
4. Track the mandatory promotion-review slices after every graded slate.
5. Detect rule drift, historical-baseline drift, duplicate rows, and missing
   critical inputs before advancing the counter.
6. Produce concise Markdown for operators and JSON for automation reads.
7. Allow the canary to become `ready_for_review`, never self-promote.

## Non-Goals

- Do not stamp `today.json`, dated dashboard artifacts, picks history, or live
  Supabase rows with candidate eligibility.
- Do not add an `off|shadow|enforce` runtime flag.
- Do not promote LEAN to FIRE or change any displayed/actionable verdict.
- Do not change lambda, edge, adjusted EV, thresholds, unit size, or staking.
- Do not change provider selection, notification behavior, locks, accepted-bet
  behavior, UI behavior, retention, calibration, or source-of-truth rules.
- Do not use final CLV, results, postgame opportunity, or closing information
  to decide whether a row qualified before the game.

## Frozen Selector Contract

The new diagnostic must implement the rule directly. It must not call the
mutable `combined_runtime_broad_no_hindsight_no_drag` entry in
`shadow_signal_synthesis_lab._composite_policies()`.

A tracked row qualifies when:

```text
(
  strong_base_strict_runtime_core
  OR strong_base_selective_lean
  OR market_anchor_strict
)
AND NOT drag_core
```

### Verdict precedence

Use the first non-empty verdict in this order:

1. `display_verdict`
2. `locked_verdict`
3. `actionable_verdict`
4. `current_verdict`
5. `verdict`

`FIRE` means the selected verdict begins with `FIRE`. `LEAN` means the selected
verdict equals `LEAN`.

### Strong Base strict runtime core

A row is in the strict runtime core when it is FIRE, matches at least one
frozen keep-FIRE rule below, and does not match `drag_core`.

Frozen keep-FIRE rules:

1. `keep_fire_market_agreed_moderate_ev`
   - FIRE
   - `model_market_relationship == model_agrees_with_favorite`
   - adjusted-EV bucket is `ev_6_to_17`
   - `bet_timing_window == pre_30`
2. `keep_fire_over_moderate_ev_normal_leash`
   - FIRE
   - `side == over`
   - adjusted-EV bucket is `ev_6_to_17`
   - leash/opportunity bucket is `normal`

Adjusted-EV bucket rules are frozen as:

- `< 0`: `ev_negative`
- `0 <= value < 0.06`: `ev_0_to_6`
- `0.06 <= value < 0.17`: `ev_6_to_17`
- `>= 0.17`: `ev_17_plus`

Preserve the current composite's exact adjusted-EV precedence semantics: parse
`locked_adj_ev`, `adj_ev`, then `ev`, joining them with Python truthy `or`.
A numeric zero therefore falls through to the next field. This behavior is
intentional for v1 compatibility; changing it requires a new selector id.

### Strong Base selective LEAN

A row is a selective LEAN when it is LEAN, matches at least one frozen
expand-LEAN rule below, and does not match `cap_high_raw_edge` or
`cap_fire_under_market_fade`. The outer `NOT drag_core` rule also removes all
remaining market-fade rows.

Frozen expand-LEAN rules:

1. `expand_lean_45_low_ev_normal_leash`
   - LEAN
   - `line_bucket == 4.5`
   - adjusted-EV bucket is `ev_0_to_6`
   - leash/opportunity bucket is `normal`
2. `expand_lean_low_k_standard_no_vig`
   - LEAN
   - `pitcher_archetype_bucket == low_k_standard`
   - `model_no_vig_gap >= 0.02`
3. `expand_lean_low_line_capped_model_fade`
   - LEAN
   - `line_bucket == 2.5-3.5`
   - `model_market_relationship == model_fades_favorite`
   - `quality_gate_level == capped`

### Market-anchor strict

A row matches the market-anchor branch when `market_anchor_strict` appears in
the normalized label set from either:

1. `market_anchor_selector.labels`, or
2. `market_anchor_selector_labels`.

The outer drag exclusion still applies to this branch.

### Frozen drag core

`drag_core` is true when any of these rules match:

1. `cap_high_raw_edge`: numeric `edge >= 0.06`.
2. `cap_market_fade`:
   `model_market_relationship == model_fades_favorite`.
3. `cap_fire_under_market_fade`: FIRE, `side == under`, and
   `model_market_relationship == model_fades_favorite`.

The third rule remains explicit even though the second rule already includes
it. This preserves the exact named contract and audit explanation.

## Rule Fingerprint

The diagnostic owns a canonical JSON-compatible rule specification containing:

- selector id and version
- prospective start date
- verdict precedence
- every frozen keep, expand, anchor, and drag predicate
- every numeric threshold and bucket boundary

Serialize it with sorted keys and compact separators, then publish its SHA-256
digest in both outputs. Tests must pin the digest. Any semantic rule change
requires a new selector id, new digest, new baseline, and new prospective
counter.

## Evidence Accounting

### Row eligibility

Analyze only tracked rows with `result` equal to `win` or `loss`.

Use this unique key:

```text
slate_date | normalized_pitcher | side
```

Normalize the pitcher using the existing project name normalizer. Duplicate
eligible keys block counter advancement for that run.

### Windows

- Historical rebuild: clean-regime rows from 2026-04-28 through 2026-07-20.
- Prospective: rows with `slate_date >= 2026-07-21`.
- Current provider: rows with `slate_date >= 2026-06-24`.
- Recent: candidate rows from the latest 14 distinct graded slates.

### Locked versus rebuilt history

Every run must show both:

1. The locked baseline constants from this design.
2. A historical rebuild using the frozen v1 predicate.

The historical rebuild must reconcile exactly to 186 rows, 124 wins, 62
losses, and +29.20u within a 0.005u rounding tolerance before the report can
advance its prospective counter. Any mismatch produces
`blocked_baseline_drift`, reports the difference, and leaves the locked
starting point unchanged.

### Prospective counter

The floor counter is:

```text
locked_current_provider_rows + prospective_qualified_rows
```

The remaining count is:

```text
max(0, 75 - counter_rows)
```

Historical rebuild corrections never change the locked 52-row component.

## Input Integrity

Prospective tracked graded rows must provide the fields needed to evaluate all
frozen runtime branches and exclusions:

- slate date, pitcher identity, side, result, and PnL
- verdict precedence fields
- edge and adjusted-EV inputs
- model-market relationship
- line bucket and price fields
- timing window and leash/opportunity bucket
- pitcher archetype and no-vig gap
- quality and Path B metadata
- market-anchor selector labels when the selector object is present

Absent market-anchor metadata means the anchor branch is false; it is not by
itself an integrity failure. Missing inputs needed to prove a Strong Base or
drag predicate create an unevaluable row. Any prospective unevaluable row
produces `blocked_input_gap` and does not advance the counter that run.

## Mandatory Slice Audit

For the rebuilt historical set, prospective set, and combined set, report rows,
wins, losses, PnL, and flat-stake ROI for:

- FIRE versus LEAN family
- over versus under
- K-line bucket
- price sign and price bucket
- clean, capped, and blocked quality
- Path B real/mixed, Path B without real splits, and Path A/unknown
- model agrees with favorite, fades favorite, and other/missing
- workload/leash bucket
- market-anchor strict/core/none
- market-agreement with/against/mixed/missing
- pre-close CLV proxy bucket
- final CLV bucket as outcome audit only
- provider era and provider attribution
- latest 14 graded slates

Also report missing coverage counts for every slice. A missing or weak slice can
block a recommendation, but it cannot silently remove rows from the frozen
candidate.

## Status Contract

Allowed statuses:

- `blocked_duplicate_keys`
- `blocked_baseline_drift`
- `blocked_input_gap`
- `collecting`
- `ready_for_review`

`ready_for_review` requires no integrity block and a counter of at least 75.
It does not mean approved, promotion-ready, or profitable. The report must
always state that live promotion requires a separate Tyler-approved plan.

## Outputs

Create a dedicated diagnostic with two outputs:

- `analytics/output/no_drag_composite_canary_audit.md`
- `analytics/output/no_drag_composite_canary_audit.json`

The JSON is the automation contract. The Markdown is the operator read and
must lead with:

- selector id and fingerprint
- status
- locked baseline
- rebuilt baseline and reconciliation
- prospective record
- counter and rows remaining
- current-provider and recent reads
- breakout or deterioration callouts
- mandatory slice risks
- explicit no-live-change boundary

## Post-Grading Integration

Add the diagnostic to `scripts/run_post_grading_shadow_reports.py` after the
Gate C dataset and Shadow Signal Synthesis report are available. The runner
prints only the executive/counter excerpt and keeps the existing cron
read-only.

The diagnostic recomputes from the durable Gate C dataset after every grading
run. It does not need a new database table, migration, runtime worker, provider
request, or live-artifact field.

## Documentation And Operating Board

Create a new research packet for the v1 candidate and preserve the prior
strict-plus-selective packet as historical/control context. Update the model
lane in `docs/current-state.md` to identify the v1 no-drag canary as the lead
research candidate and the prior aggressive packet as its comparison policy.

The operating board must keep these gates separate:

- prospective shadow evidence
- live model/ranking promotion
- provider/source promotion
- notification changes
- strict locks
- UI behavior
- retention execution

## Testing Strategy

Use test-driven development.

Focused tests must cover:

1. A truth table for every keep-FIRE, expand-LEAN, market-anchor, and drag rule.
2. Verdict precedence and numeric bucket boundaries.
3. The exact canonical rule fingerprint.
4. Historical/prospective date separation.
5. Locked baseline reconciliation and drift blocking.
6. Duplicate-key and missing-input blocking.
7. The initial 52 + 0 = 52 counter and 23-row remainder.
8. Counter advancement without historical-baseline mutation.
9. Mandatory slice and missing-coverage output.
10. Markdown and JSON status language.
11. Post-grading runner invocation and excerpt behavior.
12. Direct CLI execution from the repository root.

## Rollout And Rollback

Implementation occurs on an isolated feature branch with task-scoped
subagents, TDD, per-task spec/quality review, and a whole-branch review.

After integration approval:

1. Merge the reviewed branch.
2. Redeploy only `bbe-gate-c-post-grading-review`.
3. Preserve its schedule, command, environment, and read-only posture.
4. Run one read-only verification job.
5. Confirm the report starts at 52 counter rows with 23 remaining and that no
   production artifact or notification row changed.

Rollback is a code revert plus redeploy of the prior post-grading cron commit.
No schema or data rollback is required because the design adds only generated
research outputs.

## Acceptance Criteria

- The v1 rule is directly encoded and fingerprinted.
- The July 20 historical baseline reconciles or fails closed.
- The prospective counter starts from the locked 52-row current-provider base.
- The report clearly shows 23 remaining rows before new evidence arrives.
- Mandatory slices are available in JSON and Markdown.
- Reaching 75 rows yields only `ready_for_review`.
- Tests and reviews prove the post-grading runner remains read-only.
- No live artifact, model, provider, notification, lock, UI, retention, or
  source-of-truth contract changes.
