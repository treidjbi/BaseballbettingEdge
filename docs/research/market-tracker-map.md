# Market Tracker Map

This map keeps the weekend data-hunting stack clear. It is shadow/research
documentation only and does not change production picks, thresholds, staking,
provider order, notifications, or calibration.

## Already Tracked

| Need | Current Tracker | Notes |
| --- | --- | --- |
| Feed uptime and recency | `market_feed_heartbeats` | Fastest proof that the BoltOdds worker is alive. |
| Raw book movement | `market_snapshots` | High-volume evidence; summarize before keeping long term. |
| Slate/book coverage | `provider_coverage_audits` | First place to judge whether BoltOdds covers enough books/pitchers. |
| Per-pick movement rollup | `market_pick_evidence` | Compact model-vs-market movement for LEAN/FIRE sides. |
| App-ready live state | `live_market_display_state` | Consensus, best actionable book, off-market books, freshness. |
| Would-have-alerted rows | `shadow_notification_candidates` | Alert research only; does not send pushes. |
| Whole-market price outcomes | `market_price_outcome_audit.py` | Includes PASS-level markets, favorite behavior, side price buckets. |
| Live market outcome slices | `live_market_outcome_audit.py` | Joins exported live market evidence to graded results. |
| Compact pitcher outcome row | `pitcher_k_outcome_dataset.py` | Canonical research row for market, model, context, CLV, and result. |

## Added To Compact Outcome Rows

These are now stored in the local pitcher K outcome dataset when source data is
available:

- bet-time/locked line, odds, book, and timestamp
- official-close line and odds
- price CLV and line CLV
- beat-close-price and beat-close-line flags
- model-versus-market-favorite relationship
- model edge and projection-margin buckets
- pitcher hand
- lineup count and future handedness count placeholders
- opportunity and leash-risk buckets
- future post-result opportunity placeholders: actual IP, pitch count, batters faced

## Still Needs Future Source Data

These should be collected before being used for model or selection rules:

- confirmed lineup handedness counts: R/L/S batters by pitcher hand
- projected-to-confirmed lineup K-rate delta
- actual innings pitched, pitch count, batters faced, and times-through-order
- injury/ramp-up and return-from-IL flags
- bullpen rest and likely leash/team pull tendency
- weather, roof, and game-total/run-environment context
- provider-specific bet-time consensus rows once BoltOdds is promoted

## Weekend Read Rule

If BoltOdds becomes production this weekend, judge it by three proofs:

1. Coverage: books and pitchers are present and fresh.
2. Timing: pick-time rows have a complete market state.
3. CLV: tracked picks beat the close more often than the old path.

Do not copy raw WebSocket tick history into long-term research storage unless a
separate cost and retention decision says it is worth it.
