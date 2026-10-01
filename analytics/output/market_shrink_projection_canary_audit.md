# Market Shrink Projection Canary Audit

Generated at: `2026-10-01T14:59:54.010986+00:00`

Read-only: this report does not change lambda, thresholds, staking, provider order, notifications, locks, retention, or dashboard source-of-truth.

## Executive Read

- Total source rows: `5488`
- Rows with projection metadata: `3210`
- Changed would-have lambda rows: `3210`
- Applied rows: `0`
- Tracked graded rows with metadata: `1705` rows, `860-845`, `-94.91`, `-5.6%` ROI.
- Current-provider tracked graded: `1674` rows, `845-829`, `-92.15`, `-5.5%` ROI.
- Latest 14 metadata slates: `250` rows, `123-127`, `-18.88`, `-7.5%` ROI.

## Decision Value

- Would-change lambda rows: `3210`.
- Selected-lambda drift: `0` rows, mean absolute `0.0000`, maximum `0.0000`.
- Verdict-change agreement: `0` aligned / `0` opposed from `0` rows.
- Research classification changes: `{"gate_f": 0, "market_anchor": 0, "no_drag": 0, "strong_base": 0}`.
- Missing metadata: `{"actual_ks": 0, "current_lambda": 0, "current_verdict": 3210, "selected_lambda": 0, "would_lambda": 0, "would_verdict": 3210}`.

## Projection Error

- Paired pitcher-game rows: `1605`.
- Current lambda MAE: `1.8896`.
- Would-lambda MAE: `1.8339`.
- MAE lift (positive favors shrink): `0.0558`.

## Mode Counts

- `shadow`: `3210`

## Candidate Counts

- `market_shrink_25`: `3210`

## Verdict Split

- FIRE 1u: `215` rows, `120-95`, `-4.52`, `-2.1%` ROI.
- LEAN: `1391` rows, `689-702`, `-89.07`, `-6.4%` ROI.
- PASS: `99` rows, `51-48`, `-1.28`, `-1.3%` ROI.

## Side Split

- over: `753` rows, `372-381`, `-43.50`, `-5.8%` ROI.
- under: `952` rows, `488-464`, `-51.38`, `-5.4%` ROI.

## K-Line Split

- 2.5-3.5: `441` rows, `231-210`, `-8.10`, `-1.8%` ROI.
- 4.5: `582` rows, `282-300`, `-60.51`, `-10.4%` ROI.
- 5.5: `421` rows, `211-210`, `-16.19`, `-3.9%` ROI.
- 6.5: `168` rows, `94-74`, `+8.08`, `+4.8%` ROI.
- 7.5+: `93` rows, `42-51`, `-18.16`, `-19.5%` ROI.

## Model-Market Split

- model_agrees_with_favorite: `871` rows, `483-388`, `-33.66`, `-3.9%` ROI.
- model_fades_favorite: `787` rows, `350-437`, `-65.22`, `-8.3%` ROI.
- unknown: `47` rows, `27-20`, `+3.97`, `+8.5%` ROI.

## Quality Gate Split

- capped: `866` rows, `425-441`, `-71.79`, `-8.3%` ROI.
- clean: `839` rows, `435-404`, `-23.10`, `-2.8%` ROI.

## Workload Risk Split

- workload_fragile: `536` rows, `271-265`, `-26.77`, `-5.0%` ROI.
- workload_stable: `631` rows, `330-301`, `-6.75`, `-1.1%` ROI.
- workload_watch: `538` rows, `259-279`, `-61.36`, `-11.4%` ROI.

## Workload Sensitivity Split

- workload_sensitivity_half_k: `650` rows, `301-349`, `-46.86`, `-7.2%` ROI.
- workload_sensitivity_one_k: `608` rows, `321-287`, `-21.31`, `-3.5%` ROI.
- workload_stable_margin: `447` rows, `238-209`, `-26.72`, `-6.0%` ROI.

## No-Vig Split

- no_vig_confirmed_edge: `1045` rows, `569-476`, `-32.56`, `-3.1%` ROI.
- no_vig_market_disagrees: `68` rows, `36-32`, `-1.25`, `-1.8%` ROI.
- no_vig_no_edge: `57` rows, `27-30`, `-1.13`, `-2.0%` ROI.
- no_vig_referee_disagrees: `534` rows, `227-307`, `-60.76`, `-11.4%` ROI.
- no_vig_thin_edge: `1` rows, `1-0`, `+0.82`, `+82.0%` ROI.

## Rollback Recommendation

- Shadow metadata only; keep observing and do not enforce from this report alone.
- Do not change thresholds, staking, providers, notifications, locks, retention, or dashboard source-of-truth from this report.
