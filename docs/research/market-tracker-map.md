# Market Tracker Map

This map keeps the weekend data-hunting stack clear. It is shadow/research
documentation only and does not change production picks, thresholds, staking,
provider order, notifications, or calibration.

## Already Tracked

| Need | Current Tracker | Notes |
| --- | --- | --- |
| Feed uptime and recency | `market_feed_heartbeats` | Active proof for TheRundown/PropLine sidecar freshness; also the first place to detect accidental BoltOdds reactivation. |
| Raw book movement | `market_snapshots` | High-volume evidence; summarize before keeping long term. |
| Slate/book coverage | `provider_coverage_audits` | First place to judge active provider coverage, missing books, and historical provider trial value. |
| Per-pick movement rollup | `market_pick_evidence` | Compact model-vs-market movement for LEAN/FIRE sides. |
| App-ready live state | `live_market_display_state` | Consensus, best actionable book, off-market books, freshness. |
| Would-have-alerted rows | `shadow_notification_candidates` | Alert research only; does not send pushes. |
| Notification digest opportunities | `notification_events`, future coordinator summary metadata | Tracks same-category notification piles that should become grouped start-window or pick-change digests. |
| Render-vs-GitHub timing summary | `shadow_pipeline_runs` | Compact per-run artifact freshness and lock-window counts. |
| Pick lock timing observations | `shadow_pick_lock_observations` | Deduped status transitions for future lock-ledger decisions. |
| Whole-market price outcomes | `market_price_outcome_audit.py` | Includes PASS-level markets, favorite behavior, side price buckets. |
| Live market outcome slices | `live_market_outcome_audit.py` | Joins exported live market evidence to graded results. |
| Market agreement tracker | `market_agreement_tracker.py` | Derived LEAN/FIRE/referee-cap buckets for market movement with or against the model; no new storage. Use compact Supabase exports plus Gate C metadata/result overlay for historical backfills. |
| Compact pitcher outcome row | `pitcher_k_outcome_dataset.py`; durable artifact in `data/research/gate_c/` | Canonical research row for market, model, context, CLV, and result. |
| Bet-selection/edge synthesis | `bet_selection_edge_synthesis.py` | Derived Gate C report for side/verdict, edge, adjusted EV, no-vig, CLV, model-market, and opportunity/outcome buckets; no new storage. |
| K projection challengers | `k_projection_shadow_lab.py` | Reuses compact outcome rows to compare current lambda against transparent projection variants. |
| Pre/post 4/28 hard review | `pre_post_428_model_review.py` | Compares immediate pre-bump and clean post-bump grading, selection, and projection quality. |
| Historical lineup handedness backfill | `historical_lineup_handedness_backfill.py` | Reconstructs opponent lineup R/L/S counts from MLB boxscores into local shadow artifacts; not runtime proof. |
| Actual opportunity backfill | `actual_opportunity_backfill.py` | Reconstructs postgame IP, pitch count, and batters faced from MLB boxscores into local shadow artifacts; not runtime proof. |
| Batter-handedness Path B readiness | `batter_handedness_shadow_audit.py` | Checks whether lineup hand counts, matchup buckets, and split cache coverage justify anything beyond shadow collection. |
| Best executable market candidates | `executable_market_shadow_audit.py` | Scores fresh supported mainline book/line/side rows against the current model projection; shadow-only input for cutover review. |
| Mainline movement notification patterns | `mainline_movement_pattern_audit.py` | Reads processed movement/notification/evidence rows to find supported-book same-line and pick-line-touching alert patterns; avoids broad raw webhook inbox scans. |

## Provider Tracker Ownership

The active provider posture is TheRundown as the official artifact source with
PropLine as fallback/live-movement sidecar. The old BoltOdds + PropLine cutover
is retired; future provider trials need a new Tyler approval. Existing trackers
should still be reused instead of creating duplicate raw movement, per-pick
movement, display state, or would-have-alerted state.

| Table / artifact | Current role | Active action | Active writers | Long-term role |
| --- | --- | --- | --- | --- |
| `market_feed_heartbeats` | Active sidecar/source freshness and accidental-reactivation proof | Read for live-layer health and stale-row guards | Render live layer and provider scripts | Operational freshness, short retention |
| `market_provider_runs` | Provider run metadata, including `slate_date` | Read to attach raw snapshots to slate dates | Active provider pollers/processors | Provider audit and lineage |
| `market_snapshots` | Raw per-book/provider odds ticks | Read as raw source for current-line and live-display builders | Active TheRundown/PropLine writers; historical BoltOdds rows only | High-volume short-retention raw evidence |
| `provider_coverage_audits` | Slate/book/pitcher coverage summaries | Read for active source health and future provider-trial gates | Active provider audits; historical trial writers only | Long-term provider decision evidence |
| `market_pick_evidence` | Per-pick provider movement rollup | Leave as shadow/research | Existing live layer only | Model-vs-market learning |
| `live_market_display_state` | App-ready per-provider market state | Leave as shadow/display until explicit UI promotion | Existing live layer only | User-facing evidence after separate display decision |
| `shadow_notification_candidates` | Would-have-alerted rows | Continue shadow testing future notification classes | Existing live layer only | Notification promotion evidence |
| `propline_webhook_deliveries` | Raw signed PropLine webhook inbox | Process recent rows only for shadow comparison | Netlify receiver plus bounded live-layer processor | Webhook reliability, dedupe, and timing audit |
| `shadow_pipeline_runs` | Render-vs-GitHub timing summary | Add as existing-cron timing evidence | Existing live layer only | Short-retention scheduler reliability evidence |
| `shadow_pick_lock_observations` | Deduped lock timing observations | Add as existing-cron timing evidence | Existing live layer only | Compact evidence for future lock-ledger promotion |
| `line_movement_events` | Durable movement events | PropLine webhook line/price movement rows may write only for the reviewed class; keep new classes separate | Existing live layer; bounded PropLine webhook processor | Notification/event audit |
| `notification_events` | Real push queue | Do not write new provider-sourced alert classes without a separate flag/review | Existing live sender only | Delivery audit and fatigue control |
| `game_reminder_state` | Reminder dedupe/state | Unchanged | Existing live layer only | Reminder dedupe |
| `accepted_bets` | Manual Tyler bet log | Read for CLV, timing proof, and notification-to-bet attribution after the IDs are wired through the app | Manual/UI flow only, later notification-originated logs with explicit source attribution | Bet-timing, CLV, and alert-value audit |
| `data/preview_lines.json` | Official opening baseline artifact | Preserve shape; eventually feed from provider baselines | GitHub pipeline only | Official opening source for artifacts |
| `data/picks_history.json` | Durable graded pick history | Add source attribution fields only | GitHub pipeline grading/history only | Regime-aware performance history |
| `current_market_lines` | Derived complete book lines | Build from active raw snapshots; default active readers exclude retired BoltOdds | Current-line builder | Current provider state for research/arbitration rehearsal |
| `official_market_lines` | Provider-arbitrated market feed | Keep as rehearsal/evidence unless Tyler approves a source switch | Arbitration builder | Possible future official source after a fresh gate/review |
| `market_opening_baselines` | New provider opening baselines | Create and preserve first-seen baseline rows | New current-line builder | Provider-era opening-line source |
| `provider_arbitration_decisions` | New source-choice audit | Create for every official-line build | New arbitration builder | Explain bet/wait/skip/source decisions |
| `provider_request_usage_daily` | New provider request/cost counter | Write from shadow provider runs/snapshots | Current-line builder and compaction script | Cost and quota guardrail |
| `compact_market_line_movements` | New compact raw-snapshot summary | Write before long-term raw snapshot retention deletion | `scripts/compact_market_snapshots.py` | Season-long movement history without raw tick volume |

Future source-switch rule: if Tyler opens a new provider trial and approves a
pipeline adapter, the pipeline should read `official_market_lines`, not raw
`market_snapshots`. Today, TheRundown-derived Render artifacts remain the
production source of truth; raw snapshots and official lines remain evidence.

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
- accepted-bet source and notification/candidate attribution when available
- accepted-bet match type and price source when available
- model-versus-market-favorite relationship
- model edge and projection-margin buckets
- large-edge skepticism flag and reasons
- pitcher hand
- lineup count and future handedness count placeholders
- opportunity and leash-risk buckets
- pitcher archetype bucket
- post-result opportunity fields: actual IP, pitch count, batters faced, source, runtime-safety, game PK, and pitcher-match type

As of 2026-06-03, the full-corpus Gate C read should use the committed hybrid
artifact under `data/research/gate_c/`. Regenerate it with
`python scripts/build_pitcher_k_outcome_dataset.py --artifact-source hybrid --output-dir data/research/gate_c`.
Use production `get-artifact` directly for freshness checks, but not as the
only historical Gate C source when the production index or artifact mirror is
partial.

## Still Needs Future Source Data

These should be collected before being used for model or selection rules:

- runtime-confirmed lineup handedness counts: R/L/S batters by pitcher hand
- projected-to-confirmed lineup K-rate delta
- times-through-order and in-game removal reason
- injury/ramp-up and return-from-IL flags
- bullpen rest and likely leash/team pull tendency
- weather, roof, and game-total/run-environment context
- provider-specific bet-time consensus rows for the active TheRundown/PropLine
  sidecar or any future approved provider trial

## Active Provider Read Rule

For TheRundown/PropLine health, or any future provider trial, judge it by three
proofs:

1. Coverage: books and pitchers are present and fresh.
2. Timing: pick-time rows have a complete market state.
3. CLV: tracked picks beat the close more often than the old path.

Do not copy raw tick history into long-term research storage unless a separate
cost and retention decision says it is worth it.

The timing-ledger rule is the same: keep `shadow_pipeline_runs` as short-lived
operational proof and keep `shadow_pick_lock_observations` compact enough to
explain future lock decisions without storing every live-layer tick forever.

The raw-market rule is now concrete on the cutover branch: compact movement
rows can be written, but raw `market_snapshots` should not be deleted until the
compact rows have been reviewed for at least one slate and Tyler approves a
retention job.

## Duplication Guardrail

Before adding another tracker, first ask whether the compact outcome row can
answer the question with a derived label. Add new storage only when the source
data is truly missing, such as runtime-confirmed handedness counts,
times-through-order/removal context, or provider-specific bet-time consensus.
This keeps the long-term research model comprehensive without making multiple
tables disagree about the same pick.

## Daily Operations Brief Read

The BBE Operations Brief should synthesize this map every weekday:

1. Confirm feed health and coverage from `market_feed_heartbeats`,
   `market_snapshots`, and `provider_coverage_audits`.
2. Confirm pick-time and current-state market evidence from
   `market_pick_evidence` and `live_market_display_state`.
3. Regenerate or read `analytics/output/market_agreement_tracker.md` when live
   market evidence exports are available. Prefer compact exports from
   `market_pick_evidence` and `live_market_display_state`, with
   `data/research/gate_c/pitcher_k_outcome_dataset.jsonl` as the metadata and
   result overlay. Use it to summarize LEANs with broad market support,
   referee caps later confirmed or rejected by movement, and FIRE rows that
   became market-faded. Treat these as shadow Gate C review buckets only.
4. Regenerate or read
   `data/research/gate_c/pitcher_k_outcome_dataset_summary.md` and report CLV,
   process outcome, timing window, model-versus-market, opportunity/leash,
   pitcher archetype, large-edge skepticism, and reconciliation counts.
5. Keep a compact Gate C bucket scoreboard for the clean 2026-04-28+ regime:
   FIRE 1u/2u, over/under, moderate edge, high edge, CLV/no-CLV, timing window,
   quality gate, model-versus-market favorite, opportunity/leash, and pitcher
   archetype. Compare it to the immediate 2026-04-08 through 2026-04-27
   pre-bump window when the contrast changes the read, but do not use the
   older window as permission to roll back live rules.
6. Regenerate or read `analytics/output/bet_selection_edge_synthesis.md` when
   the question is bet-selection quality rather than projection accuracy. This
   report uses the durable Gate C row to separate side/verdict, edge, adjusted
   EV, no-vig, CLV, model-market, and opportunity/outcome slices. It is
   research evidence only and does not define a live betting rule. Use Gate
   12A in `docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md`
   to label each candidate bucket as watch-only, research-ready, or
   promotion-plan eligible.
7. Regenerate or read `k_projection_shadow_lab.md` when projection quality is
   in question; report whether a challenger improves accuracy without
   promoting it into live lambda.
8. For provider-trial, sidecar-health, or line-conflict days, run/read
   `executable_market_shadow_audit_YYYY-MM-DD.md` beside the provider cutover
   report. Separate `single_book_outlier` conflicts from
   `ref_vs_majority` conflicts, and treat best-executable EV as shadow evidence
   until CLV/outcome proof exists.
9. For notification work, report grouped start-window opportunities, grouped
   pick-change opportunities, stale/duplicate/post-start suppressions, and
   movement candidates by provider-strength label before recommending any new
   production send class. Regenerate or read
   `analytics/output/mainline_movement_pattern_audit_YYYY-MM-DD.md` when the
   question is which mainline or webhook movement patterns are worth sending;
   treat it as read-only evidence, not notification-class approval.
10. Tie any recommendation back to cost/risk docs before suggesting more
   infrastructure or provider spend.
11. Explicitly separate "collect more evidence" from "ready to change model or
   betting behavior."

The daily read should produce a compact confidence-referee note:

- What made yesterday's picks look sharper?
- What made them look stale, late, or market-faded?
- Were misses more about price/timing, projection, opportunity/leash, or
  variance?
- Which tracker is still too sparse to trust?
