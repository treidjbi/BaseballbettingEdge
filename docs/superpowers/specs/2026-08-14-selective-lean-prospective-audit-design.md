# Selective LEAN Prospective Audit Design

Date: 2026-08-14
Status: Approved by Tyler for research-only implementation

## Decision

Freeze one prospective research counter for the Strong Base candidate
`expand_lean_low_line_capped_model_fade`. The counter is an offline,
post-grading diagnostic. It does not change official picks, model math,
verdicts, thresholds, staking, providers, notifications, locks, dashboard
artifacts, accepted bets, history, retention, or source-of-truth behavior.

The exact historical selector is:

```json
{
  "display_verdict": "LEAN",
  "line_bucket": "2.5-3.5",
  "model_market_relationship": "model_fades_favorite",
  "quality_gate_level": "capped"
}
```

Its frozen SHA-256 fingerprint is
`4e00a180e35fe75dc8889d47065a25c4351cb37ac55664eb42f01b77c07fd13a`.
Any definition drift blocks the audit.

## Evidence windows

- Historical nomination ends on 2026-08-12. The locked reference is 103 rows,
  55-48, +11.415935 units. The current-provider reference is 56 rows, 28-28,
  +2.999676 units.
- August 13-14 are a freeze gap. They are visible after the decision review or
  before the implementation was complete, so they may be reported but never
  receive prospective credit.
- Formal prospective credit starts on 2026-08-15, the first fully unobserved
  slate after implementation. No back-credit is allowed.

## Inputs and fail-closed eligibility

The audit reads the existing canonical Gate C JSONL only and writes ignored
Markdown and JSON reports under `analytics/output/`. It creates no table and
calls no provider or production API.

A row earns prospective credit only when all of these are true:

1. It is a tracked, graded win/loss row on or after 2026-08-15.
2. It matches the frozen selector exactly.
3. It is not history-recovered and has a unique dataset key.
4. Its timing is exactly `pre_30` and its lock timestamp is present.
5. It includes consumed operational-lock proof: a lock identifier or key,
   `consumed_at`, and the source artifact path used by that lock.
6. Provider and market-agreement attribution are present.
7. Every critical field required to select, grade, and slice the row is present.

The current Gate C schema carries a lock timestamp and artifact provenance but
does not yet carry consumed-ledger linkage. The audit therefore exposes those
rows as blocked input gaps instead of silently crediting them. Adding that
linkage is a separate dataset-enrichment decision; this implementation does
not mutate the dataset builder or Supabase.

Post-start rows, unknown timing, missing attribution, and ambiguous duplicates
are excluded. Results and PnL are used only after the fixed rule selects the
row.

## Review output and gates

The report separates historical nomination, freeze-gap observations,
prospective eligible rows, and prospective blocked candidates. It includes
side, price, K-line, quality, timing, model/market, Path B, workload, pre-close
proxy, final CLV, provider, agreement, and latest-14-slate slices.

Statuses are:

- `blocked_rule_drift`
- `blocked_duplicate_keys`
- `blocked_baseline_drift`
- `blocked_input_gap`
- `collecting`
- `ready_for_review`

`ready_for_review` requires all of the following:

- at least 75 eligible graded rows;
- at least 20 UNDER rows;
- at least 10 plus-price rows;
- positive prospective PnL and positive latest-14-slate PnL;
- complete provider and market-agreement attribution;
- no mandatory slice with at least 10 rows and negative PnL; and
- positive leave-one-slate-out minimum PnL.

The decision remains `continue_research` until every gate passes. Passing only
permits a separate review; it does not authorize an official-pick or staking
design.

## Runner integration

The post-grading shadow runner invokes the audit after Gate C and Strong Base
reports are available. It accepts explicit Markdown/JSON output paths and an
independent skip flag. Tests prove invocation, skip behavior, frozen-rule
integrity, fail-closed eligibility, zero initial prospective credit, slices,
and no production writes.
