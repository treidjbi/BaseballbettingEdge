# Market Anchor Selector Canary Audit

Generated at: `2026-06-17T17:54:24.916752+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.

## Executive Read

- Tracked graded rows: `1050`
- Rows with selector metadata: `24`
- Displayed FIRE with selector metadata: `2` rows, `2-0`, `+1.46`, `+73.1%` ROI.
- Market-anchor strict displayed FIRE: `0` rows, `0-0`, `+0.00`, `+0.0%` ROI.
- Non-strict displayed FIRE: `2` rows, `2-0`, `+1.46`, `+73.1%` ROI.
- All market-anchor strict tracked rows: `8` rows, `4-4`, `-1.24`, `-15.5%` ROI.

## Input Coverage

- Slate date range: `2026-04-28` to `2026-06-16`
- Selector shadow deployment date: `2026-06-16`

## Strict Slice Check

- line_bucket=4.5: `5` rows, `2-3`, `-1.53`, `-30.6%` ROI.
- model_market_relationship=model_agrees_with_favorite: `8` rows, `4-4`, `-1.24`, `-15.5%` ROI.
- price_sign=minus: `8` rows, `4-4`, `-1.24`, `-15.5%` ROI.
- quality_gate_level=clean: `8` rows, `4-4`, `-1.24`, `-15.5%` ROI.
- side=under: `8` rows, `4-4`, `-1.24`, `-15.5%` ROI.

## Promotion Gate

- Do not enable `MARKET_ANCHOR_SELECTOR_MODE=enforce_downside` from this report alone.
- A promotion review requires at least `150` clean tracked rows with selector metadata and at least `75` strict rows.
- Strict rows must stay positive after excluding one slate and must survive side, K-line, price, quality, timing, CLV, workload, Path B, provider/source, and market-agreement slices.
- Non-strict FIRE rows must remain clearly worse before any downside-only cap can be considered.
