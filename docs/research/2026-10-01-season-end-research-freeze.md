# 2026 Season-End Research Freeze

**Frozen through:** 2026-09-27  
**Built:** 2026-10-01  
**Decision:** preserve the evidence, keep every live gate closed, and do not draft a next-season canary until Tyler selects one frozen hypothesis for a separate plan.

## Executive Decision

The season-end dataset passes its integrity checks, but the current production selection system did not demonstrate positive full-season betting value. The most promising projection result is market shrink: the frozen Gate F holdout improves projection error at 15%, 25%, and 35% shrink weights. That is evidence for a future plan discussion, not for enabling a live candidate. The production-linked market-shrink metadata remained unapplied and its tracked selection rows were negative.

Market-anchor strict also illustrates why retrospective and prospective evidence must stay separate. The from-scratch retrospective rebuild is positive, but the prospective canary audit is negative overall and concentrated by side, line, and price. It remains shadow-only.

The structured accepted-bet table does not reconcile Tyler's approximately `-57u` season result. It ends July 27 and therefore cannot be the canonical full-season betting ledger.

## Frozen Evidence Identity

- Supabase `published_pipeline_artifacts/picks_history` publication: `2026-10-01T13:17:50.497283+00:00`
- Published history rows: `4,102`
- Published history SHA-256: `627f81ec28c00b31b624aea8f71c3fb9992b3f64b00df2a2bc3c636502ed421e`
- Gate C date range: `2026-04-28` through `2026-09-27`
- Gate C rows: `5,488`
- Gate C tracked rows: `2,893`
- Duplicate `dataset_key` values: `0`
- Published graded-pick reconciliation: `2,777 / 2,777`
- Gate C JSONL SHA-256: `4b44d70d1bcae23be35354ec9ea9b84886f62642c4900fd56c4e65817748a8cd`
- Final source date: `2026-09-27`

The Gate C tracked count exceeds the published settled-pick count because the research corpus retains recovered and descriptive pitcher-market rows. Published picks history controls official displayed-result claims; Gate C controls research comparisons.

## Official Published Outcome

For the clean regime from April 28 through September 27:

| Published slice | Rows | W-L-void | PnL |
| --- | ---: | ---: | ---: |
| All tracked exposure | 2,857 | 1,384-1,393-80 | -185.990537u |
| Displayed FIRE | 818 | 409-388-21 | -45.026171u |
| LEAN | 2,039 | 975-1,005-59 | -140.964366u |

This is published model-history exposure, not proof of Tyler's actual accepted bets. It must not be relabeled as account PnL.

## Accepted-Bet Reconciliation

The Supabase `accepted_bets` table contains `351` unique rows and no duplicate dedupe keys. Its last accepted date is July 27, so it is incomplete for the season.

Using exact slate date and pitcher matching to published history, then grading the accepted side at the accepted line and price:

- Matched and settled: `345` rows
- Unmatched: `6` rows
- Settled risk: `422u`
- Matched PnL: `-2.547867u`
- Matched ROI: `-0.60%`

The unmatched rows are Payton Tolle on May 9, Brady Singer on May 24, Erick Fedde on May 29, Jesus Luzardo and Ryan Feltner on May 30, and Casey Mize on June 14. Resolving those six rows cannot bridge the gap to approximately `-57u`. The remembered result therefore uses a different scope, later bets, different stake accounting, or an external ledger. Keep `-57u` user-reported and unreconciled until that ledger is available.

## Projection And Selection Decisions

### Projection candidates

The Gate F holdout contains `745` rows. Market shrink clears the frozen projection-error standards at all three tested weights:

| Candidate | MAE delta | RMSE delta | Positive rolling windows | Bad slices | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `market_shrink_15` | -0.044 | -0.060 | 25 | 0 | Eligible for a separate plan discussion |
| `market_shrink_25` | -0.070 | -0.094 | 25 | 0 | Eligible for a separate plan discussion |
| `market_shrink_35` | -0.094 | -0.125 | 25 | 0 | Eligible for a separate plan discussion |
| `high_line_temper` | -0.003 | -0.005 | 18 | 1 | Drop from active consideration |
| `leash_cap` | +0.016 | +0.026 | 1 | 5 | Drop from active consideration |
| `handedness_bucket_adjust` | 0.000 | 0.000 | 26 | 0 | Hindsight-only; no runtime plan |

The production-linked `market_shrink_25` metadata remains a brake on promotion: `1,705` tracked graded metadata rows were `860-845`, `-94.91u`, with `0` applied rows. It improved paired projection MAE by `0.0558 K`, but the retained metadata lacks would-verdict values. A child plan would need to define how projection improvement becomes a bounded decision rule without assuming betting-profit improvement.

### Market anchor

The retrospective rebuild's strict tracked selector is `468`, `276-192`, `+7.95u` (`+1.7%`). The prospective selector audit is weaker:

- All strict tracked rows: `370`, `214-156`, `-1.46u`
- Strict displayed FIRE: `84`, `47-37`, `-0.50u`
- Strict displayed FIRE is all OVER
- The 4.5-K strict slice is `66-54`, `-6.08u`; UNDER is `146-106`, `-2.52u`
- Market-agreement attribution is missing for all `370` strict rows

Decision: keep `MARKET_ANCHOR_SELECTOR_MODE=shadow`; do not draft a promotion plan from the retrospective win.

### Bet selection and risk caps

- Published displayed FIRE lost `-45.03u`; LEAN lost `-140.96u`.
- Gate C's high-edge-skeptic bucket lost `-131.65u`; the moderate-edge clean-context bucket made `+5.38u` on `94` rows and remains a research slice, not a rule.
- CLV-supported rows made `+3.58u` on `222` rows; worse-than-close rows lost `-37.64u` on `261` rows. CLV remains a process target.
- Profit-rescue's hindsight action labels identify `439` downgrade rows at `-48.66u`, while keep-FIRE rows were `340`, `199-141`, `+8.92u`. The last 30-day counterfactual would have been `-0.62u` worse, so the live downgrade-only cap stays a risk-control canary rather than a claimed profit improvement.
- Confidence-referee metadata covers `3,942` Gate C rows with `643` applied caps. It remains verdict-conversion only.

## Workload, Path B, Market, And Seasonality

- Workload-stable, fragile, and watch buckets were all negative; no workload bucket earns a live rule.
- Path B's largest buckets were negative. The `1-4` real-split bucket was positive but contains only `11` rows.
- The frozen market-agreement report remains useful historical evidence, but the season-end refresh could not be reconstructed from the locally retained compact inputs. Missing final attribution blocks any market-agreement promotion.
- Early-season UNDER was the only positive broad seasonal side (`229-186`, `+20.12u`). Both sides were negative in the late-season bucket. This is selection-biased evidence and can only inform a shrunk prior or future validation design.

## Final Gate Decision

- Gate C: frozen and integrity-valid.
- Gate D/E/F/12E production promotion: closed.
- Market-shrink: projection-plan discussion only; no live child plan approved.
- Market-anchor: keep shadow.
- Confidence referee, profit rescue, and Path B: preserve current bounded modes; no expansion.
- Thresholds, staking, providers, locks, notifications, dashboard source-of-truth, and retention: unchanged.
- Accepted-bet PnL: unresolved until Tyler provides the ledger behind approximately `-57u`.

No candidate is approved for deployment by this freeze.
