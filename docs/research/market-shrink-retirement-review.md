# Market-Shrink Shadow Posture Review

Date: 2026-07-29

Decision: **`retain_diagnostic_shadow`**

This review is research-only. It does not authorize `enforce`, an environment
change, a projection/model change, thresholds, staking, providers,
notifications, locks, artifacts, UI, retention, or source-of-truth changes.

## Executive decision

Keep `MARKET_SHRINK_PROJECTION_MODE=shadow`, but close the current candidate's
betting-promotion path. The betting result is materially negative while the
paired projection diagnostic is materially positive, and the shadow's
marginal provider/compute cost is negligible.

The useful retained question is narrow: does shrinking the current lambda 25%
toward the posted K line continue to reduce pitcher-level projection error?
The metadata must not be interpreted as evidence that the associated tracked
bet portfolio should be promoted.

## Evidence through July 28

The production-shaped hybrid build reconciled `3,434` Gate C side rows,
`1,793` tracked rows, zero duplicate keys, and `1,750/1,750` graded picks.

| Read | Rows | Record | PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| Tracked graded metadata | 605 | 300-305 | -42.56u | -7.0% |
| Current-provider window | 574 | 285-289 | -39.81u | -6.9% |
| Latest 14 metadata slates | 255 | 123-132 | -27.47u | -10.8% |

Runtime and decision-value accounting:

- Metadata rows: `1,156`, all candidate `market_shrink_25` and mode `shadow`.
- Applied rows: `0`.
- Selected-lambda drift: `0` rows; the production lambda stayed unchanged.
- Verdict-change metadata: unavailable on `1,156/1,156`, so no verdict-change
  agreement claim is allowed.
- Paired unique pitcher-game projection rows: `578`.
- Current-lambda MAE: `1.9472`; would-lambda MAE: `1.8932`.
- MAE lift: `+0.0540` strikeouts, positive for the shrink diagnostic.

The MAE lift is large enough to preserve the research signal. It is not a
betting lift: the graded betting portfolio is negative in the full,
current-provider, and recent windows.

## Marginal cost and noise

- Provider calls: **zero marginal calls**. The calculation uses only the
  already-computed model lambda and posted K line.
- Compute: a local one-million-call benchmark measured about `10.06` microseconds
  per calculation, or roughly `0.3 ms` for a 30-pitcher slate. This is not a
  material cron-duration cost.
- Database rows: **zero new Supabase rows or tables**. Metadata is serialized
  into the existing ephemeral SQLite pick column and published JSON artifacts.
- Artifact size: the public `today` artifact generated at
  `2026-07-29T19:08:26Z` was `265,650` compact bytes with the metadata and
  `240,486` without it, a `25,164` byte (`9.5%`) delta. Public
  `picks_history` was `4,522,534` bytes with the metadata and `4,288,903`
  without it, a `233,631` byte (`5.2%`) delta across `804` metadata rows.
- Operational noise: nonzero but bounded. The primary noise is repeated JSON
  metadata on pitcher, side, tracked-pick, dated, and history surfaces, not
  provider spend, worker uptime, or database row growth.

No provider-cost-ledger change is warranted because there is no marginal
provider plan/request cost and compute is immaterial. No operational-risk
register change is warranted because this decision preserves the existing
shadow posture.

## Dependency and preservation map

- Runtime producer: `pipeline/projection_challenger.py` and
  `pipeline/build_features.py`.
- Existing persistence: `pipeline/fetch_results.py` and tracked-pick builders
  in `pipeline/run_pipeline.py`.
- Direct research consumers: the market-shrink canary audit, Gate F projection
  reports/labs, Gate C dataset hydration, and next-season model research.
- No-drag, Strong Base, and market-anchor selectors do not consume the
  challenger metadata; their classifications and live behavior remain
  unchanged.
- Historical metadata and tests remain preserved even if a future approved
  simplification stops new collection.

## Decision rule

`retain_diagnostic_shadow` is selected because:

1. projection MAE improves by more than the existing `0.025` Gate F materiality
   floor;
2. the calculation has zero marginal provider cost and negligible compute;
3. selected lambda, verdicts, and live behavior did not change; and
4. the betting-promotion evidence is decisively negative, so collection is
   useful only as projection-error attribution.

Do not draft an enforce plan for `market_shrink_25`. If artifact growth or
operator noise later becomes material, use a separate Tyler-approved
simplification plan to retain only the pitcher-level diagnostic and stop
duplicating it across side/history surfaces. No environment or Render change
is approved by this review.
