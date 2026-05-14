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
| Render-vs-GitHub timing summary | `shadow_pipeline_runs` | Compact per-run artifact freshness and lock-window counts. |
| Pick lock timing observations | `shadow_pick_lock_observations` | Deduped status transitions for future lock-ledger decisions. |
| Whole-market price outcomes | `market_price_outcome_audit.py` | Includes PASS-level markets, favorite behavior, side price buckets. |
| Live market outcome slices | `live_market_outcome_audit.py` | Joins exported live market evidence to graded results. |
| Compact pitcher outcome row | `pitcher_k_outcome_dataset.py` | Canonical research row for market, model, context, CLV, and result. |
| K projection challengers | `k_projection_shadow_lab.py` | Reuses compact outcome rows to compare current lambda against transparent projection variants. |

## Provider Cutover Tracker Ownership

The BoltOdds + PropLine cutover should add an official arbitration layer on top
of existing trackers. It should not create duplicate versions of raw movement,
per-pick movement, display state, or would-have-alerted state.

| Table / artifact | Current role | Cutover action | Writes during cutover | Long-term role |
| --- | --- | --- | --- | --- |
| `market_feed_heartbeats` | BoltOdds worker uptime and current-slate proof | Read for cutover freshness gates | Existing BoltOdds worker only | Operational freshness, short retention |
| `market_provider_runs` | Provider run metadata, including `slate_date` | Read to attach raw snapshots to slate dates | Existing provider workers only | Provider audit and lineage |
| `market_snapshots` | Raw per-book/provider odds ticks | Read as raw source for current-line builder | Existing BoltOdds/PropLine writers only | High-volume short-retention raw evidence |
| `provider_coverage_audits` | Slate/book/pitcher coverage summaries | Read for cutover gates | Existing provider audits plus BoltOdds trial writer | Long-term provider decision evidence |
| `market_pick_evidence` | Per-pick provider movement rollup | Leave as shadow/research | Existing live layer only | Model-vs-market learning |
| `live_market_display_state` | App-ready per-provider market state | Leave as shadow/display until explicit UI promotion | Existing live layer only | User-facing evidence after separate display decision |
| `shadow_notification_candidates` | Would-have-alerted rows | Continue shadow testing BoltOdds notification value | Existing live layer only | Notification promotion evidence |
| `shadow_pipeline_runs` | Render-vs-GitHub timing summary | Add as existing-cron timing evidence | Existing live layer only | Short-retention scheduler reliability evidence |
| `shadow_pick_lock_observations` | Deduped lock timing observations | Add as existing-cron timing evidence | Existing live layer only | Compact evidence for future lock-ledger promotion |
| `line_movement_events` | Durable movement events | Do not widen to BoltOdds sends until notification cutover | Existing live layer; later gated BoltOdds alerts | Notification/event audit |
| `notification_events` | Real push queue | Do not write BoltOdds-sourced alerts until separate flag | Existing live sender only | Delivery audit and fatigue control |
| `game_reminder_state` | Reminder dedupe/state | Unchanged | Existing live layer only | Reminder dedupe |
| `accepted_bets` | Manual Tyler bet log | Read later for CLV and timing proof | Manual/UI flow only | Bet-timing and CLV audit |
| `data/preview_lines.json` | Official opening baseline artifact | Preserve shape; eventually feed from provider baselines | GitHub pipeline only | Official opening source for artifacts |
| `data/picks_history.json` | Durable graded pick history | Add source attribution fields only | GitHub pipeline grading/history only | Regime-aware performance history |
| `current_market_lines` | New derived complete book lines | Create from raw snapshots | New current-line builder | Current provider state for official arbitration |
| `official_market_lines` | New official provider-arbitrated market feed | Create as the only pipeline-readable market source | New arbitration builder | Official market source after cutover |
| `market_opening_baselines` | New provider opening baselines | Create and preserve first-seen baseline rows | New current-line builder | Provider-era opening-line source |
| `provider_arbitration_decisions` | New source-choice audit | Create for every official-line build | New arbitration builder | Explain bet/wait/skip/source decisions |
| `provider_request_usage_daily` | New provider request/cost counter | Create for PropLine downgrade guardrails | Existing/new provider jobs | Cost and quota guardrail |
| `compact_market_line_movements` | New compact raw-snapshot summary | Create before long-term raw snapshot retention is enforced | New compaction script | Season-long movement history without raw tick volume |

Cutover rule: the GitHub pipeline should read `official_market_lines`, not raw
`market_snapshots`. Raw snapshots remain evidence; official lines are the
controlled product input.

## Added To Compact Outcome Rows

These are now stored in the local pitcher K outcome dataset when source data is
available:

- bet-time/locked line, odds, book, and timestamp
- official-close line and odds
- price CLV and line CLV
- beat-close-price and beat-close-line flags
- CLV type: price only, line only, both, or no CLV edge
- process-vs-result bucket: good-process wins/losses and weak-process wins/losses
- bet timing window relative to first pitch
- model-versus-market-favorite relationship
- model edge and projection-margin buckets
- large-edge skepticism flag and reasons
- pitcher hand
- lineup count and future handedness count placeholders
- opportunity and leash-risk buckets
- pitcher archetype bucket
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

The timing-ledger rule is the same: keep `shadow_pipeline_runs` as short-lived
operational proof and keep `shadow_pick_lock_observations` compact enough to
explain future lock decisions without storing every live-layer tick forever.

## Duplication Guardrail

Before adding another tracker, first ask whether the compact outcome row can
answer the question with a derived label. Add new storage only when the source
data is truly missing, such as confirmed handedness counts, actual pitch count,
or provider-specific bet-time consensus. This keeps the long-term research
model comprehensive without making multiple tables disagree about the same
pick.

## Daily Operations Brief Read

The BBE Operations Brief should synthesize this map every weekday:

1. Confirm feed health and coverage from `market_feed_heartbeats`,
   `market_snapshots`, and `provider_coverage_audits`.
2. Confirm pick-time and current-state market evidence from
   `market_pick_evidence` and `live_market_display_state`.
3. Regenerate or read `pitcher_k_outcome_dataset_summary.md` and report CLV,
   process outcome, timing window, model-versus-market, opportunity/leash,
   pitcher archetype, large-edge skepticism, and reconciliation counts.
4. Regenerate or read `k_projection_shadow_lab.md` when projection quality is
   in question; report whether a challenger improves accuracy without
   promoting it into live lambda.
5. Tie any recommendation back to cost/risk docs before suggesting more
   infrastructure or provider spend.
6. Explicitly separate "collect more evidence" from "ready to change model or
   betting behavior."

The daily read should produce a compact confidence-referee note:

- What made yesterday's picks look sharper?
- What made them look stale, late, or market-faded?
- Were misses more about price/timing, projection, opportunity/leash, or
  variance?
- Which tracker is still too sparse to trust?
