# Market Anchor Selector Canary Audit

Generated at: `2026-10-01T14:59:54.048806+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.

## Executive Read

- Review status: `collecting`.
- Tracked graded rows: `2893`
- Rows with selector metadata: `1843`
- Clean rows with selector metadata: `920`
- Displayed FIRE with selector metadata: `227` rows, `129-98`, `-0.49`, `-0.2%` ROI.
- Market-anchor strict displayed FIRE: `84` rows, `47-37`, `-0.50`, `-0.6%` ROI.
- Non-strict displayed FIRE: `143` rows, `82-61`, `+0.01`, `+0.0%` ROI.
- All market-anchor strict tracked rows: `370` rows, `214-156`, `-1.46`, `-0.4%` ROI.

## Input Coverage

- Slate date range: `2026-04-28` to `2026-09-27`
- Selector shadow deployment date: `2026-06-16`

## Review Floors And Windows

- The raw review floors are `150` clean selector rows and `75` strict rows.
- Clearing raw review floors opens a separate shadow review only; it is not promotion approval.
### All Strict Rows

- All: `370` rows, `214-156`, `-1.46`, `-0.4%` ROI.
- Current Provider: `330` rows, `191-139`, `+0.23`, `+0.1%` ROI.
- Recent 14 Slates: `51` rows, `32-19`, `+5.89`, `+11.6%` ROI.

### Strict Displayed FIRE Rows

- All: `84` rows, `47-37`, `-0.50`, `-0.6%` ROI.
- Current Provider: `77` rows, `42-35`, `-1.94`, `-2.5%` ROI.
- Recent 14 Slates: `16` rows, `8-8`, `+0.01`, `+0.1%` ROI.

## Strict Displayed FIRE Concentration

- Strict displayed FIRE is all `OVER`; the result is concentrated, not side-balanced.

## Mandatory Strict Slices

### All Strict Rows

#### side

- `over`: `118` rows, `68-50`, `+1.06`, `+0.9%` ROI.
- `under`: `252` rows, `146-106`, `-2.52`, `-1.0%` ROI.

#### k_line

- `2.5-3.5`: `77` rows, `51-26`, `+9.84`, `+12.8%` ROI.
- `4.5`: `120` rows, `66-54`, `-6.08`, `-5.1%` ROI.
- `5.5`: `127` rows, `73-54`, `-1.06`, `-0.8%` ROI.
- `6.5`: `46` rows, `24-22`, `-4.15`, `-9.0%` ROI.

#### price_sign

- `minus`: `368` rows, `213-155`, `-2.76`, `-0.8%` ROI.
- `plus`: `2` rows, `1-1`, `+1.30`, `+65.1%` ROI.

#### quality

- `capped`: `3` rows, `2-1`, `+1.89`, `+63.0%` ROI.
- `clean`: `367` rows, `212-155`, `-3.35`, `-0.9%` ROI.

#### timing

- `pre_30`: `366` rows, `210-156`, `-3.67`, `-1.0%` ROI.
- `unknown`: `4` rows, `4-0`, `+2.21`, `+55.2%` ROI.

#### final_clv

- `beat_close_line`: `2` rows, `1-1`, `+1.30`, `+65.1%` ROI.
- `beat_close_price`: `34` rows, `23-11`, `+5.92`, `+17.4%` ROI.
- `neutral_or_unknown`: `309` rows, `174-135`, `-11.70`, `-3.8%` ROI.
- `worse_close_price`: `25` rows, `16-9`, `+3.02`, `+12.1%` ROI.

#### preclose_clv_proxy

- `medium_preclose_clv_proxy`: `47` rows, `25-22`, `-3.87`, `-8.2%` ROI.
- `strong_preclose_clv_proxy`: `193` rows, `119-74`, `+8.21`, `+4.2%` ROI.
- `weak_preclose_clv_proxy`: `130` rows, `70-60`, `-5.79`, `-4.5%` ROI.

#### workload

- `high`: `53` rows, `30-23`, `-2.15`, `-4.1%` ROI.
- `medium`: `14` rows, `7-7`, `-1.94`, `-13.8%` ROI.
- `normal`: `303` rows, `177-126`, `+2.63`, `+0.9%` ROI.

#### path_b

- `path_b_real_or_mixed`: `370` rows, `214-156`, `-1.46`, `-0.4%` ROI.

#### provider

- `propline`: `3` rows, `2-1`, `+0.29`, `+9.6%` ROI.
- `therundown`: `367` rows, `212-155`, `-1.75`, `-0.5%` ROI.

#### provider_era

- `official_therundown_propline`: `330` rows, `191-139`, `+0.23`, `+0.1%` ROI.
- `post_boltodds_retirement`: `31` rows, `18-13`, `-1.14`, `-3.7%` ROI.
- `pre_current_provider`: `9` rows, `5-4`, `-0.55`, `-6.2%` ROI.

#### market_agreement

- `missing`: `370` rows, `214-156`, `-1.46`, `-0.4%` ROI.

#### model_market

- `model_agrees_with_favorite`: `365` rows, `211-154`, `-3.32`, `-0.9%` ROI.
- `model_fades_favorite`: `3` rows, `2-1`, `+2.02`, `+67.2%` ROI.
- `unknown`: `2` rows, `1-1`, `-0.15`, `-7.6%` ROI.

### Strict Displayed FIRE Rows

#### side

- `over`: `84` rows, `47-37`, `-0.50`, `-0.6%` ROI.

#### k_line

- `2.5-3.5`: `29` rows, `17-12`, `+0.30`, `+1.0%` ROI.
- `4.5`: `25` rows, `11-14`, `-3.94`, `-15.8%` ROI.
- `5.5`: `24` rows, `15-9`, `+2.17`, `+9.0%` ROI.
- `6.5`: `6` rows, `4-2`, `+0.97`, `+16.2%` ROI.

#### price_sign

- `minus`: `82` rows, `46-36`, `-1.80`, `-2.2%` ROI.
- `plus`: `2` rows, `1-1`, `+1.30`, `+65.1%` ROI.

#### quality

- `capped`: `2` rows, `1-1`, `+1.30`, `+65.1%` ROI.
- `clean`: `82` rows, `46-36`, `-1.80`, `-2.2%` ROI.

#### timing

- `pre_30`: `84` rows, `47-37`, `-0.50`, `-0.6%` ROI.

#### final_clv

- `beat_close_line`: `2` rows, `1-1`, `+1.30`, `+65.1%` ROI.
- `beat_close_price`: `7` rows, `5-2`, `+1.71`, `+24.4%` ROI.
- `neutral_or_unknown`: `69` rows, `37-32`, `-4.49`, `-6.5%` ROI.
- `worse_close_price`: `6` rows, `4-2`, `+0.98`, `+16.3%` ROI.

#### preclose_clv_proxy

- `medium_preclose_clv_proxy`: `10` rows, `7-3`, `+2.52`, `+25.1%` ROI.
- `strong_preclose_clv_proxy`: `42` rows, `22-20`, `-4.21`, `-10.0%` ROI.
- `weak_preclose_clv_proxy`: `32` rows, `18-14`, `+1.19`, `+3.7%` ROI.

#### workload

- `high`: `1` rows, `0-1`, `-1.00`, `-100.0%` ROI.
- `medium`: `2` rows, `1-1`, `-0.30`, `-14.8%` ROI.
- `normal`: `81` rows, `46-35`, `+0.80`, `+1.0%` ROI.

#### path_b

- `path_b_real_or_mixed`: `84` rows, `47-37`, `-0.50`, `-0.6%` ROI.

#### provider

- `propline`: `2` rows, `1-1`, `-0.44`, `-21.9%` ROI.
- `therundown`: `82` rows, `46-36`, `-0.06`, `-0.1%` ROI.

#### provider_era

- `official_therundown_propline`: `77` rows, `42-35`, `-1.94`, `-2.5%` ROI.
- `post_boltodds_retirement`: `7` rows, `5-2`, `+1.44`, `+20.5%` ROI.

#### market_agreement

- `missing`: `84` rows, `47-37`, `-0.50`, `-0.6%` ROI.

#### model_market

- `model_agrees_with_favorite`: `81` rows, `46-35`, `-0.80`, `-1.0%` ROI.
- `model_fades_favorite`: `2` rows, `1-1`, `+1.30`, `+65.1%` ROI.
- `unknown`: `1` rows, `0-1`, `-1.00`, `-100.0%` ROI.


## Leave-One-Slate-Out

### All Strict Rows

- Minimum after excluding `2026-09-19`: `365` rows, `209-156`, `-5.03`, `-1.4%` ROI.
- Maximum after excluding `2026-09-07`: `366` rows, `214-152`, `+2.54`, `+0.7%` ROI.

### Strict Displayed FIRE Rows

- Minimum after excluding `2026-09-17`: `82` rows, `45-37`, `-2.15`, `-2.6%` ROI.
- Maximum after excluding `2026-08-21`: `81` rows, `47-34`, `+2.50`, `+3.1%` ROI.

## Blocking Evidence

- Negative strict slices: `side=under`, `k_line=4.5`, `k_line=5.5`, `k_line=6.5`, `price_sign=minus`, `quality=clean`, `timing=pre_30`, `final_clv=neutral_or_unknown`, `preclose_clv_proxy=medium_preclose_clv_proxy`, `preclose_clv_proxy=weak_preclose_clv_proxy`, `workload=high`, `workload=medium`, `path_b=path_b_real_or_mixed`, `provider=therundown`, `provider_era=post_boltodds_retirement`, `provider_era=pre_current_provider`, `market_agreement=missing`, `model_market=model_agrees_with_favorite`, `model_market=unknown`.
- Missing strict coverage: `market_agreement=370`.
- Side concentration, negative slices, or missing coverage remain blockers even when raw review floors are met.

## Promotion Gate

- `enforce_downside` remains closed; keep `MARKET_ANCHOR_SELECTOR_MODE=shadow`.
- Strict rows must stay positive after excluding one slate and must survive side, K-line, price, quality, timing, CLV, workload, Path B, provider/source, and market-agreement slices.
- Non-strict FIRE rows must remain clearly worse before any downside-only cap can be considered.
- Any narrowed OVER-only candidate requires a new selector id, fingerprint, baseline, plan, and prospective canary.
