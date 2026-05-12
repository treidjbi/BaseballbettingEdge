# Pitcher K Outcome Research Dataset

This dataset is shadow-only research evidence for pitcher strikeout markets. It
does not change live picks, locks, thresholds, staking, provider order,
notifications, calibration, or `formula_change_date`.

## Row Grain

One row represents one pitcher K side at one research snapshot:

```text
slate_date + context_snapshot + normalized_pitcher + side + k_line
```

The stable key is:

```text
{slate_date}:{context_snapshot}:{normalized_pitcher}:{side}:{k_line}
```

The first implemented snapshot is `official_close`, built from the committed
dashboard archive after the market is graded. Future snapshots may include:

- `opening`
- `pre_120`
- `pre_60`
- `pre_30`
- `pre_15`
- `pre_5`
- `final_pre_start`

`post_start` is not an approved research snapshot because it leaks information
that was unavailable before betting decisions.

## Source Hierarchy

Use this order when fields disagree:

1. Production archive JSON under `dashboard/data/processed/YYYY-MM-DD.json`
2. Durable grading history in `data/picks_history.json`
3. Shadow live-market exports from Supabase
4. Derived research fields computed by diagnostics

TheRundown-derived artifacts remain the production source of truth. BoltOdds and
PropLine are evidence layers, not replacements for official model state.

## Required Fields

Rows must include explicit `None` values for unknown optional fields. Do not
omit fields or silently invent neutral values.

Required field groups:

- identity: `dataset_key`, `slate_date`, `context_snapshot`, `pitcher`,
  `normalized_pitcher`, `side`, `k_line`
- market: `bookmaker_key`, `american_odds`, `price_sign`, `price_bucket`,
  `market_favorite_side`
- model: `model_side`, `model_win_prob`, `model_no_vig_gap`,
  `projected_ks`, `k_margin_to_line`, `verdict`, `quality_gate_level`
- result: `actual_ks`, `result`, `theoretical_pnl`
- context: `home_away`, `opp_team`, `lineup_used`, `source_artifact_path`
- live market: `provider`, `market_consensus`, `bet_value_consensus`,
  `broad_confirmation`
- bet timing / CLV: `is_tracked_pick`, `bet_time_line`, `bet_time_odds`,
  `bet_time_book`, `closing_line`, `price_clv_cents`, `line_clv_delta`,
  `beat_close_price`, `beat_close_line`
- model/market disagreement: `model_market_relationship`,
  `model_edge_bucket`, `projection_margin_bucket`
- lineup / handedness / opportunity: `pitcher_throws`, `lineup_count`,
  `lineup_right_batters`, `lineup_left_batters`, `lineup_switch_batters`,
  `handedness_matchup_bucket`, `avg_ip`, `recent_start_count`,
  `opportunity_bucket`, `leash_risk_bucket`
- post-result opportunity: `actual_ip`, `actual_pitch_count`,
  `batters_faced`

Some fields are intentionally `null` today because the production artifact does
not yet store the underlying value. Keep those columns in the compact row
contract anyway so future BoltOdds, lineup-handedness, and MLB result enrichers
can fill them without changing the dataset shape.

## No-Leakage Rule

Rows used for future model or ranking research must only include data known at
or before their `context_snapshot`. Official-close rows can be used for
descriptive post-slate analysis, but not as if their closing state was known at
opening or lock time.

## Sample Row

```json
{
  "dataset_key": "2026-05-12:official_close:bryan woo:under:5.5",
  "slate_date": "2026-05-12",
  "context_snapshot": "official_close",
  "pitcher": "Bryan Woo",
  "normalized_pitcher": "bryan woo",
  "side": "under",
  "k_line": 5.5,
  "bookmaker_key": "fanduel",
  "american_odds": 104,
  "price_sign": "plus",
  "price_bucket": "+100 to +119",
  "market_favorite_side": "over",
  "model_side": "under",
  "model_win_prob": 0.57,
  "model_no_vig_gap": 0.04,
  "projected_ks": 4.9,
  "k_margin_to_line": 0.6,
  "verdict": "FIRE 2u",
  "quality_gate_level": "clean",
  "actual_ks": 4,
  "result": "win",
  "theoretical_pnl": 1.04,
  "home_away": "home",
  "opp_team": "NYY",
  "lineup_used": "confirmed",
  "provider": null,
  "market_consensus": null,
  "bet_value_consensus": null,
  "broad_confirmation": false,
  "source_artifact_path": "dashboard/data/processed/2026-05-12.json"
}
```
