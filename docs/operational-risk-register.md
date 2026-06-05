# Operational Risk Register

Last updated: 2026-06-05

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
| Netlify | ~$5/mo current account state | Existing | Active | Static dashboard, artifact API, functions, Blobs subscriptions | Production hosting/sender | Monthly | Function usage and logs remain stable; deploys simple; `get-artifact` stays fresh | Usage credits/log limits become a real bottleneck |
| Render live cron | ~$1/mo | 2026-05-07 | Active | `bbe-live-layer` every 10 minutes | Live notification event builder | Daily while new | Fresh Netlify/Supabase artifact; queue/sender flow healthy; notifications useful | Duplicate PropLine polling adds cost/noise; notifications do not create value |
| Render pipeline crons | Low-volume cron services; verify billing | 2026-05-30 production cutover | Active | Preview, grading, full, refresh, and lock scheduler | Production scheduler | Daily during first migrated week | Runs finish before betting windows; Supabase artifacts and locks are fresh; manual GitHub rollback stays available | Render misses scheduled windows, artifact publication fails, or lock cron misses due rows |
| Render BoltOdds worker | ~$7/mo | 2026-05-07 | Active during BoltOdds trial | Always-on WebSocket worker | Shadow-only | Daily during trial | Worker stays fresh, writes auditable rows, no runaway volume | BoltOdds trial fails or worker needs too much babysitting |
| Supabase | Pro, about $25/mo before overages | 2026-05-01 shadow infra; upgraded 2026-05-21 | Active | Artifact store, shadow/live market evidence, notification queue, and lock control plane | Production artifact/lock store plus evidence store | Daily during first migrated week, then weekly | Storage and egress stay bounded; spend cap remains on; artifacts/locks stay fresh; evidence changes locks, alerts, confidence, or provider decisions | Raw volume grows without decision value; spend-cap warnings; queries slow; storage approaches included Pro allowance |
| GitHub Actions | Free for current public-repo usage | Existing | Manual only after 2026-05-30 | Manual pipeline rollback, probes, audit backup | Rollback / repository automation | Weekday health checks | Manual dispatch works when needed; no stale scheduled runs compete with Render | Manual rollback fails or GitHub artifacts accidentally resume as competing production scheduler |
| Codex / ChatGPT | $20-$100/mo | Existing | Operator tooling | Engineering, monitoring, debugging, docs, automations | Build/ops assistant | Monthly | Pro plan saves enough time during build/trial periods | Quiet operations month where Plus can handle workload |

## Source Of Truth Hierarchy

Use this hierarchy when sources disagree.

1. **Production truth**: TheRundown-derived Render pipeline artifacts published
   to Supabase and served by Netlify `get-artifact` are the official model and
   dashboard truth. GitHub `workflow_dispatch` remains manual rollback/audit
   backup, and static JSON remains a fallback surface.
2. **Live notification evidence**: Render `bbe-live-layer` can create live
   pick-state, notification events, and shadow timing rows, but those events do
   not redefine the official pick or grading record.
   Its `shadow_pipeline_runs` and `shadow_pick_lock_observations` tables are
   scheduler/lock-timing evidence only until a separate promotion is approved.
3. **PropLine shadow/fallback evidence**: PropLine polling can support fallback,
   coverage, and movement analysis. PropLine webhooks now have real signed
   delivery evidence and book-level movement IDs, but webhook-derived movement
   remains shadow-only and must not drive production odds, picks, notifications,
   or provider promotion without a separate review.
4. **BoltOdds shadow evidence**: BoltOdds WebSocket rows are live-market
   evidence during the trial only. They do not alter production picks or
   notifications until explicitly promoted.
5. **Supabase**: Supabase stores the production artifact mirror, live evidence,
   notification queues, and operational lock ledger. It is still not a provider
   source or model-change authority; TheRundown-derived pipeline outputs remain
   the model truth until a separate provider/model promotion is approved.

When feeds conflict, first check freshness, target-book identity, line value,
odds price, and whether the source is production, fallback, or shadow. Do not
silently replace production artifact values with shadow feed values.

## Active Decision Gates

### Bet Conversion / Gate C

Current track: `bet-selection-first`.

Controlling plan:
`docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`.

Gate C opens only when the shadow confidence-referee diagnostics show a better
ranking or selection story across enough clean rows, while separating
runtime-safe evidence from hindsight-only explanation. Do not change thresholds,
staking, or live verdict behavior from one slate or one positive bucket.

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
- same-category notification piles that should have been grouped
- alerts that reverse quickly
- alerts that did not matter
- too many alerts in one slate

If trust drops, reduce notification classes before adding more data sources.

As of 2026-06-04, the active product goal is to group high-volume same-category
notifications before adding new alert classes:

- start-window reminders should become one digest for pitchers starting in the
  same 30-minute window;
- new FIRE, upgraded, and downgraded picks should group by category inside the
  same 10-minute Render live-layer run;
- line/price movement should usually remain individual, but broader production
  sends require stronger evidence labels from PropLine polling/webhooks,
  BoltOdds snapshots/heartbeats, broad confirmation, volatility, and single-book
  noise review.

The controlling implementation plan is
`docs/superpowers/plans/2026-06-04-live-notification-digest-coordinator.md`.

As of 2026-05-23, user-facing pushes are in a single-sender canary:
GitHub `send-notifications` is disabled with
`ENABLE_GITHUB_LEGACY_NOTIFICATIONS=false`, and Supabase
`notification_events` plus Netlify `send-live-notifications` is the primary
sender. Restore `ENABLE_GITHUB_LEGACY_NOTIFICATIONS=true` only if the live queue
or Netlify live sender fails during an active slate.

As of 2026-05-24, `send-live-notifications` has a stale-queue guard. Queued
events older than `LIVE_NOTIFICATION_MAX_EVENT_AGE_MINUTES` default 20 are
marked with `send_attempts=3` and a stale-suppression `last_send_error` instead
of being sent late. Use the authenticated smoke check on
`/api/send-live-notifications-now` or `scripts/smoke_live_notifications_sender.mjs`
after Netlify function deploys to prove the function can read Supabase and load
Netlify Blobs before relying on the next active slate.

### Supabase Lock Single-Writer Primary Path

| Risk | Impact | Detection | Mitigation | Escalate if |
| --- | --- | --- | --- | --- |
| GitHub fallback locking disabled but Render/Supabase misses a due row | A pick can start unlocked because the old GitHub T-30 fallback is intentionally suppressed | `operational_pick_locks`, `shadow_pick_lock_observations`, Render lock cron runs, started-unlocked rows | Re-enable GitHub/manual fallback only as an emergency; inspect Render source artifact freshness and live-layer lock writes | Any due pick lacks an operational lock row before first pitch |
| Artifact already locked before Supabase row with a different price | Ledger rows remain unconsumed and audits look like lock failures | `operational_pick_locks.metadata.consumer_status = artifact_already_locked_drift` | Keep row unconsumed for audit; verify Render lock cron is the only automatic consumer | Drift continues after GitHub fallback locking is disabled |
| Supabase consumer fails during non-strict primary soak | Render lock/full run logs a consumer problem but continues artifact publication | Render logs, `pipeline_artifact_publication_runs`, unconsumed due rows | Keep `SUPABASE_LOCK_CONSUMER_STRICT=false`; fix the consumer before discussing strict mode | More than one transient failure or any missed lock |

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
| Render grading did not run | Missing grading publication run or `picks_history.json` not updated | Prior slate record and calibration stale | Render `bbe-pipeline-grading`, `pipeline_artifact_publication_runs`, Netlify `get-artifact` | Re-run Render grading or manual GitHub grading workflow if safe; inspect logs | Missing grading before morning review |
| `today.json` stale | Generated timestamp old or dated archive missing | Dashboard and live layer use stale picks | Render pipeline cron, Supabase artifact rows, Netlify `get-artifact` | Re-run Render full/refresh or manual GitHub workflow rollback; verify the API artifact | Slate already near lock or games started |
| Supabase artifact API stale | Netlify `get-artifact` returns an older `published_at` or hash than the latest Render publication | Dashboard and live layer could show stale picks | `published_pipeline_artifacts`, Netlify response headers, Render logs | Re-run Render publisher; temporarily force dashboard/static rollback only if the API path is broken; inspect publisher rows | Any API-served current slate artifact lags the intended production publication during a betting window |
| Render shadow rehearsal overwrites live artifact mirror | A future rehearsal publishes to normal `today` / `dated_slate` keys instead of `render_shadow:<date>:` keys | A test run could replace production artifacts | `published_pipeline_artifacts.artifact_key`, `source`, `metadata.artifact_key_prefix`, `scripts/compare_supabase_artifacts.py --remote-key-prefix` | Stop the rehearsal, restore normal keys from Render/manual GitHub backfill, then rerun with `scripts/run_render_pipeline_mode.py --shadow-prefix` | Any rehearsal row upserts a normal live artifact key unintentionally |
| Render pipeline runner fails | Render primary run exits non-zero or does not publish expected artifact rows | Render scheduler misses artifacts that GitHub no longer publishes on schedule | Render run logs, `pipeline_artifact_publication_runs`, Netlify API | Use manual GitHub workflow rollback or rerun Render; disable affected Render schedule only if it repeats | Any preview/full/refresh/grading primary run misses its expected artifact set |
| Code pushed but Render cron services not redeployed | GitHub `main` contains an approved fix but Render cron services still run the previous deploy because autoDeploy is off | A merged pipeline fix may not affect preview, grading, full, refresh, or lock until the services are redeployed | `scripts/deploy_render_pipeline_crons.py` dry-run, Render deploy history, next cron logs | After the approved `main` push, run `python scripts/deploy_render_pipeline_crons.py` first as a dry-run, then `python scripts/deploy_render_pipeline_crons.py --execute` only when the group plan is correct; verify the next scheduled/manual run | Any production-affecting pipeline fix is merged without a Render cron deploy check |
| Render scheduler proof bundled with provider rehearsal | Active Task 11 cron services include `--provider-rehearsal`, so strict BoltOdds/PropLine coverage gaps look like scheduler failures | Migration decision confuses provider-readiness risk with GitHub-delay/scheduler risk | Render cron command, `metadata.provider_rehearsal`, provider strict failure logs | Remove `--provider-rehearsal` from scheduler-shadow services; run provider rehearsal as a separate shadow read | Any Task 11 parity decision is based on provider-rehearsal artifacts instead of TheRundown-equivalent shadow artifacts |
| Render/GitHub artifact parity mismatch | Manual GitHub rollback artifact differs from Render-published artifact for the same intended run | Rollback could change dashboard truth unexpectedly | `scripts/compare_supabase_artifacts.py`, `payload_sha256`, source run metadata | Diff artifacts and source logs before trusting rollback; keep provider source on TheRundown | Any mismatch in `today`, dated archive, `steam`, `performance`, `params`, `preview_lines`, or `picks_history` during rollback |
| FanGraphs leaderboard blocked or stale | SwStr and batter aggregate K% can fall neutral, capping quality gates or weakening lineup K context | `data_warnings`, Render logs with FanGraphs 403s, `fangraphs_cache` artifact freshness | Use the published last-good `data/fangraphs_cache.json` when fresh; if no cache exists, keep the safe neutral fallback and flag the slate as degraded | Repeated slates hit FanGraphs 403 before any fresh cache is available, or cache grows older than the allowed freshness window |
| Dashboard artifact API fallback hides stale Supabase data | App appears healthy because static fallback loads after API failure | Dashboard may mask a production API issue | Browser console warnings, Netlify `get-artifact` logs, Supabase artifact rows | Treat fallback warning as a production issue; fix API/publisher or intentionally force static rollback | Any fallback warning during a live betting window |
| Refresh/lock missed | Unlocked rows past lock time or no fresh Render artifact publication | Picks may move after intended lock or stay stale | `today.json` locked fields, Render run times, `operational_pick_locks` | Run Render lock/refresh or manual GitHub rollback if before game starts; preserve locked snapshots | Game started with unlocked or stale actionable picks |
| Supabase lock ledger writes bad row | A pick locks at an incorrect line/side/time | Artifact lock trust drops | `operational_pick_locks`, source artifact hash, game_time, should_lock_at | Disable `ENABLE_SUPABASE_LOCK_CONSUMER`; continue GitHub lock path; inspect row lineage | Any consumed lock row disagrees with the source artifact |
| Unexpected GitHub lock dispatch | Live layer sends workflow_dispatch lock runs after Render lock cron is primary | GitHub queue noise and competing artifact churn | GitHub Actions run list, live-layer logs, `ENABLE_LOCK_ONLY_WORKFLOW_DISPATCH`, `operational_pick_locks.consumed_at` | Keep `ENABLE_LOCK_ONLY_WORKFLOW_DISPATCH=false`; consume rows through Render lock cron; use GitHub lock only as manual rollback | Any automatic wrong-date or duplicate GitHub lock dispatch |
| Render live layer uses stale checkout | Supabase source artifact is local checkout, old SHA, or old generated_at | Notifications based on stale picks | `market_provider_runs` / live logs source metadata, `LIVE_ARTIFACT_URL`, Netlify `get-artifact` | Confirm the Netlify/Supabase artifact URL; redeploy worker if needed | Any notification generated from stale artifact |
| PropLine polling stops | No recent PropLine runs/snapshots | Live movement evidence stale | Render logs, GitHub shadow workflow, `market_provider_runs` | Check API key/env, provider errors, schedule health | More than one live window missed during active slate |
| PropLine webhook processor noisy or ambiguous | Signed webhook rows create duplicate/low-value movement facts, or legacy rows lack sportsbook key | Webhook evidence pollutes shadow reads or future alert logic | `propline_webhook_deliveries`, `line_movement_events`, dedupe keys, `bookmaker_key`, `metadata.market_id`, `metadata.outcome_id`, `metadata.bookmaker_key_missing` | Keep webhook processing shadow-only; compare against polling/BoltOdds; default canary is bounded to 100 recent rows / 180 minutes; disable `LIVE_PROCESS_PROPLINE_WEBHOOKS` if noisy | Do not promote webhook rows to notifications or provider source without book-level proof and reviewed noise evidence |
| BoltOdds heartbeat stale | `market_feed_heartbeats` not fresh | WebSocket evidence stale or false confidence | Render worker logs and heartbeat table | Restart worker; inspect reconnect/error state | Stale during active slate or repeated overnight |
| BoltOdds row volume too high | Rapid `market_snapshots` growth | Supabase cost/query risk | Trial audit, migration-risk audit, and `scripts/supabase_storage_guardrail.sql` | Reduce raw capture, add retention, aggregate summaries | Pro storage pressure, spend-cap warning, or slow diagnostics |
| Netlify sender not sending | Pending queue grows; sender logs errors | Users miss live alerts; stale-queue guard suppresses old events instead of sending them late | Netlify function logs; `notification_events` sent/failed counts; authenticated sender smoke check | Check env, Supabase service key, VAPID, Blobs, packaged function dependencies; deploy with function cache skipped if imports fail | Pending actionable events remain unsent through game window or stale-suppression count climbs during an active slate |
| Duplicate notifications | Same pick/move sends more than once | Trust drops fast | `notification_events.dedupe_key`; push tags | Patch dedupe logic; suppress noisy class | Any duplicate FIRE/new-pick notification |
| GitHub legacy notifications accidentally re-enabled | Duplicate artifact-diff pushes return while live sender is active | Duplicate lock/reminder/new-pick alerts | GitHub variables, workflow logs, received push tags | Set `ENABLE_GITHUB_LEGACY_NOTIFICATIONS=false`; keep live sender primary | Any duplicate from both `send-notifications` and `send-live-notifications` |
| Source line conflict | Providers disagree on line/price | Confusing movement or wrong confidence | Compare production artifact, PropLine, BoltOdds rows | Treat TheRundown artifact as production; mark conflict in audit | Conflict would change a bet or alert |
| Shadow timing ledger grows too noisy | `shadow_pipeline_runs` or lock observations grow without decision value | Supabase cost/query noise and harder daily reads | Row counts, status distribution, and whether rows changed a lock decision | Retain compact status transitions only; add short retention to run rows | Ledger volume grows but does not support promotion/cut decision |
| Provider arbitration wrong | `official_market_lines` selects stale, incomplete, or unsupported-book rows | Picks use bad market input even if model math is unchanged | `provider_arbitration_decisions`, `current_market_lines`, freshness flags | Switch `OFFICIAL_MARKET_SOURCE=therundown`; fix arbitration before retry | Any FIRE pick uses stale/incomplete provider line |
| Derived market-line rebuild delayed | GitHub scheduled `shadow-market-infra` does not rebuild `current_market_lines` / `official_market_lines` near fresh provider rows | Provider cutover evidence looks stale even while BoltOdds/PropLine are healthy | Compare latest `market_snapshots` / `market_feed_heartbeats` against `current_market_lines.updated_at` and `official_market_lines.updated_at` | Let guarded Render live-layer rebuild fill the gap; keep production on TheRundown until official rows are fresh and reviewed | Official rows lag fresh raw/provider rows by more than one active live-layer interval |
| Opening baseline overwritten | `market_opening_baselines` changes after first usable baseline | Steam and CLV reads become misleading | Compare baseline inserted_at/first_seen_at against preview artifact | Restore baseline from preview/archive; patch writer to preserve first-seen row | Any provider-era pick has moving opening odds |
| GitHub pipeline scans raw market snapshots | Pipeline runtime slows or returns inconsistent current rows | Slate artifacts become slow or unstable near lock | Pipeline logs and query plan/code review | Move reads back to `official_market_lines`; keep raw scans in builder jobs | Any scheduled run misses action window |
| Shadow timing ledger grows too noisy | `shadow_pipeline_runs` or lock observations grow without decision value | Supabase cost/query noise and harder daily reads | Row counts, status distribution, and whether rows changed a lock decision | Retain compact status transitions only; add short retention to run rows | Ledger volume grows but does not support promotion/cut decision |
| Post-TheRundown rollback weaker than expected | TheRundown canceled and BoltOdds/PropLine degraded | No full-strength fallback source | Provider env, billing status, coverage report | Use PropLine-first + The Odds emergency fallback; document degraded mode | Any slate loses FanDuel/DraftKings coverage after cancellation |
| Supabase Pro cost pressure | Storage/API/egress/compute rising | Surprise cost, spend-cap interruption, or degraded queries | Supabase dashboard; `scripts/supabase_storage_guardrail.sql`; table row counts | Add retention/aggregation; pause noisy captures; keep spend cap on unless Tyler approves overages | Database approaches 6 GB, egress trends toward allowance, spend-cap warning appears, or a table grows without decision value |
| Codex/automation drift | Agents miss current docs or duplicate work | More rework and context loss | `AGENTS.md`, `docs/current-state.md`, automations | Update handoff docs and automation prompts | Any repeated incorrect recommendation |

## Data Retention Rules

These are starting defaults, not hard policy. Add scripts only when row volume
or cost makes retention necessary.

Supabase moved to Pro on 2026-05-21 after the org exceeded the Free database
size cap. The active guardrail is now: keep spend cap on, track database/table
size before adding capture volume, and review dry-run retention output before
any deletion.

Raw snapshot deletion requires three conditions: compact summaries exist for the
affected window, `scripts/retire_market_snapshots.py --execute` is used, and
`ALLOW_MARKET_SNAPSHOT_DELETE=true` is set. Dry-run output should be reviewed
before every execute run.

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
| `current_market_lines` | Current slate plus short audit window | Derived current state; can be rebuilt from raw/compact evidence during overlap |
| `official_market_lines` | Season or long-term if compact | Official provider-era market source used by the pipeline |
| `market_opening_baselines` | Season or long-term | Needed for provider-era opening line, steam, and CLV audits |
| `provider_arbitration_decisions` | 30-90 days unless summarized | Explains source selection and skip/fallback decisions |
| `provider_request_usage_daily` | Season or long-term | Cost and quota guardrail evidence |
| `compact_market_line_movements` | Season or long-term | Low-volume movement history retained after raw snapshots age out |
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

Future notification behavior should follow
`docs/superpowers/plans/2026-05-20-live-notification-coordinator.md` once the
Supabase operational/provider switch is stable. Until then, treat duplicate,
early, or post-start pushes as operational evidence, not permission to change
the sender path mid-slate.

## Monthly Cost / Complexity Review

Run with `docs/provider-cost-ledger.md`.

Questions:

- Are we paying for overlapping sources that answer the same question?
- Did each paid source change a pick, line lock, notification, or confidence
  read this month?
- Did any provider create more complexity than decision value?
- Can a provider be downgraded, paused, or moved to on-demand?
- Is live data improving action, or only creating interesting logs?
- Is Supabase database growth still dominated by useful evidence, and is the
  spend cap still on?
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
- 2026-05-21: Supabase upgraded to Pro after Free database-size pressure.
  Added storage guardrail query and Pro spend-cap review language.
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
