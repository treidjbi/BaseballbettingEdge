# Market Agreement Tracker Design

## Purpose

Track whether live market movement agrees with BaseballBettingEdge picks over
time, especially for:

- LEAN rows that later get broad market support
- confidence-referee capped rows where the market later moves with or against
  the raw model side
- FIRE rows that either keep market support or become market-faded before lock

This is shadow-only research and operations evidence. It does not change live
picks, verdicts, thresholds, staking, provider order, notifications, locks,
retention, calibration, or dashboard source-of-truth behavior.

## Business Question

The daily question is not "did a line move?" It is:

1. When the model liked a side and the market moved with us, did those picks
   win more often or produce better PnL?
2. When the confidence referee capped a raw FIRE to LEAN, did later market
   movement confirm the cap or argue that the raw model may still have been
   right?
3. Are LEANs with broad movement support becoming a repeatable opportunity, or
   are they just noisy one-book moves?

## Data Sources

Use existing trackers only:

- `market_pick_evidence` for per-pick provider movement rollups
- `live_market_display_state` for app-ready current market state
- raw `market_snapshots` only when a fixed pregame checkpoint needs to be
  rebuilt
- `data/picks_history.json` for graded result and PnL joins
- optional current `today.json` / dated archive tracked picks for current-day
  referee metadata before grading

Do not add a Supabase table for this first version. The derived labels belong
in a diagnostic report until they prove useful enough to persist.

## Labels

The tracker adds derived labels on top of existing movement rows:

- `movement_agreement_label`
  - `market_with_model`
  - `market_against_model`
  - `market_mixed`
  - `market_no_signal`
- `movement_value_label`
  - `number_better_now`
  - `number_worse_now`
  - `value_mixed`
  - `value_no_signal`
- `movement_strength_label`
  - `broad_with_model`
  - `single_book_with_model`
  - `broad_against_model`
  - `single_book_against_model`
  - `mixed_or_reversed`
  - `no_movement_signal`
- `movement_magnitude_bucket`
  - `line_half_plus`
  - `odds_20c_plus`
  - `odds_10_19c`
  - `small_or_none`
- `tracker_bucket`
  - `lean_market_with_us`
  - `lean_market_against_us`
  - `fire_market_with_us`
  - `fire_market_against_us`
  - `referee_cap_market_with_us`
  - `referee_cap_market_against_us`
  - `referee_cap_mixed`
  - `referee_cap_no_signal`
  - fallback buckets for mixed/no-signal FIRE and LEAN rows

## Report Output

Create:

- `analytics/diagnostics/market_agreement_tracker.py`
- `analytics/output/market_agreement_tracker.md`
- optional `analytics/output/market_agreement_tracker.jsonl`

The report should summarize:

- row counts, graded counts, FIRE/LEAN/referee-cap counts
- outcome buckets by agreement/value/strength/magnitude
- LEAN movement buckets
- referee-cap movement buckets
- read rules that keep this evidence shadow-only

## Promotion Boundary

This tracker can later support a Gate C research plan if the bucket evidence
survives enough graded slates. It is not allowed to:

- promote LEANs to FIRE automatically
- remove all picks by default
- override the confidence referee
- change model math, thresholds, staking, provider order, or notification
  sends
- use post-result information as a runtime rule
