# Operational Risk Register

Last updated: 2026-05-07

This doc tracks the operational side of BaseballBettingEdge: provider trials,
failure modes, source-conflict rules, data retention, notification quality, and
kill/keep criteria. Use it with `docs/provider-cost-ledger.md` before adding
new services or changing provider behavior.

The goal is simple: do not let a useful betting side project become a fragile,
expensive system whose moving parts are hard to reason about.

## Current Trial / Subscription Register

Dates are exact where known and approximate where the billing timestamp is not
currently verified. Re-check provider dashboards before making billing decisions.

| Service | Cost | Started | Billing / trial status | Purpose | Current role | Next review | Keep criteria | Kill / downgrade criteria |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| TheRundown | ~$49-$50/mo | Approx. 2026-05-05 | Paid production provider | Scheduled odds source for official artifacts | Production book-of-record | Weekly during May, then monthly | Target-book K prop coverage stays healthy; artifacts auditable; no data-point overage pressure | Another provider proves equal production coverage, lower cost, and rollback safety |
| PropLine | ~$40/mo | Approx. 2026-05-06 | Paid shadow/fallback provider | Polling fallback and line-movement evidence | Shadow/fallback/live polling | Daily during trial; broad review 2026-06-01 | Useful FanDuel/BetRivers coverage; movement evidence improves notifications or decisions; request volume acceptable | Webhooks remain unproven and polling does not affect decisions; BoltOdds replaces live movement value; duplicate polling becomes waste |
| BoltOdds | $99/mo Starter | 2026-05-07 | Starter trial / early paid decision pending | WebSocket live market evidence | Shadow-only worker branch | Daily during first week; cancel/keep before renewal | Heartbeats fresh; target-book rows useful; movement evidence beats polling; row volume manageable | Stale feed, poor target-book rows, no decision impact, or complexity outweighs value |
| The Odds API | Free / limited | 2026-05-01 | Fallback only | FD/DK fallback when other providers leave gaps | Conservative fallback | Only when fallback is used | Stays low-volume and helps diagnose gaps | Credit burn grows or coverage is redundant |
| Netlify | ~$5/mo current account state | Existing | Active | Static dashboard, functions, Blobs subscriptions | Production hosting/sender | Monthly | Function usage and logs remain stable; deploys simple | Usage credits/log limits become a real bottleneck |
| Render live cron | ~$1/mo | 2026-05-07 | Active | `bbe-live-layer` every 10 minutes | Live notification event builder | Daily while new | Fresh GitHub raw artifact; queue/sender flow healthy; notifications useful | Duplicate PropLine polling adds cost/noise; notifications do not create value |
| Render BoltOdds worker | ~$7/mo | 2026-05-07 | Active during BoltOdds trial | Always-on WebSocket worker | Shadow-only | Daily during trial | Worker stays fresh, writes auditable rows, no runaway volume | BoltOdds trial fails or worker needs too much babysitting |
| Supabase | Free currently | 2026-05-01 shadow infra | Active | Shadow/live market evidence and notification queue | Evidence store | Weekly during trial | Free tier holds row volume; queries remain usable | Storage/egress/compute pressure without enough decision value |
| GitHub Actions | Free for current public-repo usage | Existing | Active | Pipeline, grading, artifacts, shadow jobs | Production automation | Weekday health checks | Jobs eventually complete and artifacts stay fresh | Scheduler delay causes real stale picks/locks/grading issues |
| Codex / ChatGPT | $20-$100/mo | Existing | Operator tooling | Engineering, monitoring, debugging, docs, automations | Build/ops assistant | Monthly | Pro plan saves enough time during build/trial periods | Quiet operations month where Plus can handle workload |

## Source Of Truth Hierarchy

Use this hierarchy when sources disagree.

1. **Production truth**: TheRundown-derived GitHub pipeline artifacts
   (`today.json`, dated archives, `steam.json`, `picks_history.json`,
   `params.json`) remain the official model and dashboard truth.
2. **Live notification evidence**: Render `bbe-live-layer` can create live
   pick-state, notification events, and shadow timing rows, but those events do
   not redefine the official pick or grading record.
3. **PropLine shadow/fallback evidence**: PropLine polling can support fallback,
   coverage, and movement analysis. PropLine webhooks are not considered proven
   until real provider deliveries appear in `propline_webhook_deliveries`.
4. **BoltOdds shadow evidence**: BoltOdds WebSocket rows are live-market
   evidence during the trial only. They do not alter production picks or
   notifications until explicitly promoted.
5. **Supabase**: Supabase stores evidence and queues; it is not the official
   source of model truth.

When feeds conflict, first check freshness, target-book identity, line value,
odds price, and whether the source is production, fallback, or shadow. Do not
silently replace production artifact values with shadow feed values.

## Active Decision Gates

### Bet Conversion / Gate C

Current track: `bet-selection-first`.

Gate C opens only when the shadow conversion diagnostics show a better ranking
or selection rule across enough clean rows. Do not change thresholds, staking,
or live verdict behavior from one slate or one positive bucket.

### PropLine June 1 Review

Review the full May shadow evidence on 2026-06-01:

- target-book coverage
- complete pitcher/line groups
- same-line overlap with TheRundown
- line conflicts
- movement detection
- polling schedule health
- real webhook delivery evidence
- whether PropLine would have changed decisions or notifications

Default until then: PropLine remains shadow/fallback/live polling evidence.

### BoltOdds Trial Review

Before keeping BoltOdds after trial, verify:

- worker uptime and heartbeat freshness
- websocket message volume
- normalized rows by FanDuel, BetMGM, BetRivers, Kalshi, Caesars, DraftKings,
  and theScore
- stale-feed risk
- row-volume risk
- whether WebSocket movement would have improved timing, confidence, or
  notifications compared with PropLine polling

Default until then: BoltOdds remains shadow-only.

### Cost Review

Use `docs/provider-cost-ledger.md`.

Pause before adding spend if app runtime/data cost rises above roughly
`$200/mo`, or if combined app plus operator tooling stays above roughly
`$300/mo` for more than a short build/trial period.

### Notification Quality Review

Live notifications are useful only if they improve action. Track:

- duplicates
- stale alerts
- late game reminders
- alerts that reverse quickly
- alerts that did not matter
- too many alerts in one slate

If trust drops, reduce notification classes before adding more data sources.

## Outcome Interpretation Guardrails

Do not confuse betting results with system health. A healthy system can lose a
slate, and a broken system can get lucky.

Daily or weekly reviews should separate four reads:

1. **System health**: Did the pipeline, live layer, sender, providers, and
   artifacts run correctly?
2. **Model health**: Were projections directionally reasonable against actual
   strikeouts?
3. **Bet-selection health**: Did the ranking/verdict layer choose the right
   edges from the projections?
4. **Betting outcome**: Did the slate win or lose money?

Do not make model, provider, or staking changes from the betting outcome alone.
First determine whether the day was a system failure, projection issue,
selection issue, ordinary variance, or a mix.

## Personal-Use Boundary

This project is currently personal-use decision support. Treat it as Tyler's
private betting dashboard and operations system.

Before sharing picks publicly, selling access, adding paid users, posting
automated recommendations, or distributing notifications beyond Tyler's own use,
pause and review:

- provider terms of service
- sportsbook / betting advisory rules
- state and federal compliance risk
- data redistribution rights
- disclaimers and user-facing risk language
- whether the app's reliability is good enough for anyone else to depend on it

Do not optimize for public distribution, multi-user scale, or monetization until
Tyler explicitly changes this boundary.

## Failure Modes

| Failure | How to detect it | User impact | First check | Recovery action | Escalation threshold |
| --- | --- | --- | --- | --- | --- |
| GitHub pipeline did not grade | Missing grading run or `picks_history.json` not updated | Prior slate record and calibration stale | GitHub Actions `pipeline.yml`; latest commits | Re-run grading workflow if safe; inspect logs | Missing grading before morning review |
| `today.json` stale | Generated timestamp old or dated archive missing | Dashboard and live layer use stale picks | GitHub Actions, raw GitHub artifact, dashboard fetch | Re-run full/refresh; verify raw URL | Slate already near lock or games started |
| Refresh/lock missed | Unlocked rows past lock time or no refresh commits | Picks may move after intended lock or stay stale | `today.json` locked fields; workflow run times | Run lock/refresh if before game starts; preserve locked snapshots | Game started with unlocked or stale actionable picks |
| Render live layer uses stale checkout | Supabase source artifact is local checkout, old SHA, or old generated_at | Notifications based on stale picks | `market_provider_runs` / live logs source metadata | Confirm GitHub raw artifact fetch; redeploy worker if needed | Any notification generated from stale artifact |
| PropLine polling stops | No recent PropLine runs/snapshots | Live movement evidence stale | Render logs, GitHub shadow workflow, `market_provider_runs` | Check API key/env, provider errors, schedule health | More than one live window missed during active slate |
| PropLine webhooks still absent | Only synthetic rows in `propline_webhook_deliveries` | Webhook feature cannot be trusted | Supabase webhook delivery table | Keep polling path; contact provider if needed | Do not promote webhooks without real deliveries |
| BoltOdds heartbeat stale | `market_feed_heartbeats` not fresh | WebSocket evidence stale or false confidence | Render worker logs and heartbeat table | Restart worker; inspect reconnect/error state | Stale during active slate or repeated overnight |
| BoltOdds row volume too high | Rapid `market_snapshots` growth | Supabase cost/query risk | Trial audit and migration-risk audit | Reduce raw capture, add retention, aggregate summaries | Free tier pressure or slow diagnostics |
| Netlify sender not sending | Pending queue grows; sender logs errors | Users miss live alerts | Netlify function logs; `notification_events` sent/failed counts | Check env, Supabase service key, VAPID, Blobs | Pending actionable events remain unsent through game window |
| Duplicate notifications | Same pick/move sends more than once | Trust drops fast | `notification_events.dedupe_key`; push tags | Patch dedupe logic; suppress noisy class | Any duplicate FIRE/new-pick notification |
| Source line conflict | Providers disagree on line/price | Confusing movement or wrong confidence | Compare production artifact, PropLine, BoltOdds rows | Treat TheRundown artifact as production; mark conflict in audit | Conflict would change a bet or alert |
| Shadow timing ledger grows too noisy | `shadow_pipeline_runs` or lock observations grow without decision value | Supabase cost/query noise and harder daily reads | Row counts, status distribution, and whether rows changed a lock decision | Retain compact status transitions only; add short retention to run rows | Ledger volume grows but does not support promotion/cut decision |
| Supabase free tier pressure | Storage/API/egress/compute rising | Surprise cost or degraded queries | Supabase dashboard; table row counts | Add retention/aggregation; pause noisy captures | Any need to upgrade without a clear decision value |
| Codex/automation drift | Agents miss current docs or duplicate work | More rework and context loss | `AGENTS.md`, `docs/current-state.md`, automations | Update handoff docs and automation prompts | Any repeated incorrect recommendation |

## Data Retention Rules

These are starting defaults, not hard policy. Add scripts only when row volume
or cost makes retention necessary.

| Data | Suggested retention | Reason |
| --- | --- | --- |
| `data/picks_history.json` | Indefinite | Durable model and grading history |
| Dated dashboard artifacts | Indefinite while repo size is manageable | User-facing audit trail |
| `provider_coverage_audits` | Indefinite or long-term | Small summary rows that support provider decisions |
| `artifact_snapshots` | Keep useful dated snapshots; review monthly | Useful for reconstructing provider comparisons |
| Raw `market_snapshots` | 14-30 days unless summarized | Can grow quickly; raw feed evidence ages fast |
| `market_pick_evidence` | Season or long-term if compact | Per-pick/provider market evidence rollup for model-vs-market outcome analysis |
| `live_market_display_state` | Season or long-term if compact | App-ready shadow summary for consensus, best book, off-market, and freshness decisions |
| `shadow_notification_candidates` | 30-90 days unless summarized | Would-have-sent alert evidence for provider promotion and notification fatigue decisions |
| `line_movement_events` | Season or long-term if compact | Higher-value summarized movement evidence |
| `notification_events` | 30-90 days | Debug delivery quality and fatigue |
| `market_feed_heartbeats` | 7-14 days | Operational freshness only |
| `shadow_pipeline_runs` | 30-90 days unless promoted | Operational timing proof; per-run rows should not become long-term research storage |
| `shadow_pick_lock_observations` | Season or long-term if compact | Deduped pick/status timing transitions useful for future lock-ledger promotion |
| Webhook raw deliveries | 30-90 days, longer for rare real provider proof | Useful until webhook trust is settled |

## Notification Quality Guardrails

Prefer fewer, higher-confidence notifications.

Good early notification classes:

- new FIRE pick
- LEAN upgrades to FIRE
- FIRE 1u upgrades to FIRE 2u
- FIRE pick downgrades or disappears before lock
- line moves materially against the model
- line moves materially with the model
- game reminder at a useful cadence

Avoid or suppress:

- tiny price changes
- one-book noise without broad confirmation
- stale feed updates
- repeated reminders for the same pick
- movement that reverses quickly unless it is summarized later

Daily checks should report sent, failed, pending, unsent, and obvious duplicate
counts. The review should also say whether any alert would have changed what
Tyler did.

## Monthly Cost / Complexity Review

Run with `docs/provider-cost-ledger.md`.

Questions:

- Are we paying for overlapping sources that answer the same question?
- Did each paid source change a pick, line lock, notification, or confidence
  read this month?
- Did any provider create more complexity than decision value?
- Can a provider be downgraded, paused, or moved to on-demand?
- Is live data improving action, or only creating interesting logs?
- Is Codex Pro still earning the cost this month, or can Plus carry a quieter
  operations month?
- Has any trial reached its renewal/cancel decision date?

## Change Log

- 2026-05-07: Created this register.
- 2026-05-07: BoltOdds Starter trial branch and Render worker started
  shadow-only.
- 2026-05-07: Render `bbe-live-layer` live notification cron active with fresh
  GitHub raw artifact fetch and Netlify live sender.
- 2026-05-07: `NOTIFY_SECRET` rotated after screenshot exposure; future checks
  should focus on notification health, not rotation.
- 2026-05-08: Added shadow-only `market_pick_evidence` rollup for model vs.
  market learning. It does not change picks, locks, thresholds, staking,
  provider order, or notification sends.
- 2026-05-08: Added shadow-only `shadow_notification_candidates` tracker for
  would-have-sent alert evidence. It logs suppression reasons and must not send
  live pushes without a separate promotion decision.
- 2026-05-12: Added shadow-only `live_market_display_state` plan/table for
  app-ready provider movement summaries. It is display/evaluation evidence only
  and does not change official picks, provider order, or notification sends.
- Approx. 2026-05-06: PropLine paid `$40/mo` shadow/fallback subscription active.
- Approx. 2026-05-05: TheRundown paid production provider active.
