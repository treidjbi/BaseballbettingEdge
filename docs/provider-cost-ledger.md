# Provider Cost Ledger

Last updated: 2026-05-21

This doc exists so provider and infrastructure choices stay tied to ROI, not
just engineering momentum. BaseballBettingEdge is a personal side project, so a
source is not "better" unless it improves decisions enough to justify its cost,
operational complexity, and failure risk.

Use this ledger before recommending:

- a new paid provider
- a provider upgrade
- higher polling frequency
- always-on infrastructure
- a migration away from TheRundown
- keeping multiple overlapping live feeds

Use `docs/operational-risk-register.md` beside this ledger for trial dates,
kill/keep criteria, failure modes, source-conflict rules, retention, and
notification quality guardrails.

Prices can drift. Treat the numbers below as decision notes, not accounting
truth. Re-check account dashboards or public pricing pages before approving a
new recurring spend.

## Cost Buckets

Separate the costs into two buckets:

1. **App runtime / data costs**: costs that exist because the app runs.
2. **Operator tooling costs**: tools Tyler uses to build, monitor, and improve
   the app. These may also support other business/client work.

This distinction matters for Codex. It is a meaningful monthly expense, but it
is not purely a BaseballBettingEdge runtime cost.

## Current Monthly Picture

Approximate current monthly cost, using known account state and current trial
context:

| Bucket | Low / steady state | With live trials active | Notes |
| --- | ---: | ---: | --- |
| App runtime/data, excluding Codex | ~$120/mo | ~$226/mo | Assumes TheRundown, PropLine, Netlify, Render live layer, Supabase Pro; adds BoltOdds Starter + Render worker during trial |
| Operator tooling, Codex | $20-$100/mo | $20-$100/mo | Plus may be enough later; Pro makes sense during heavy build/debug periods |
| Combined view | ~$140-$220/mo | ~$246-$326/mo | Use this as an affordability guardrail, not a precise bill |

Supabase moved to Pro on 2026-05-21 after the org exceeded the Free database
size quota. Keep Supabase spend caps enabled unless Tyler explicitly approves
overages. If PropLine moves from the current tier to the next tier, add the
delta. If BoltOdds Starter stays after trial, keep both the provider cost and
always-on worker cost in the steady-state view.

## Current Services

| Service | Current / likely cost | What it does | Current decision | Main cost risk |
| --- | ---: | --- | --- | --- |
| TheRundown | ~$49-$50/mo | Production book-of-record odds for scheduled pipeline artifacts | Keep as production source | Data-point overage; not suitable for 10-minute live polling |
| PropLine | ~$40/mo now; possible ~$80/mo tier | Shadow/fallback odds and live movement polling | Keep shadow/fallback; do not broadly migrate | Webhooks not proven; duplicate polling; unclear upgrade ROI |
| BoltOdds | $99/mo Starter during trial | WebSocket live market movement evidence | Trial only, shadow-only | Always-on worker complexity; book gaps; Pro is much more expensive |
| The Odds API | Free/limited fallback currently | FD/DK fallback when TheRundown/PropLine leave gaps | Keep conservative fallback only | Credit burn if called event-by-event too broadly |
| Netlify | Tyler account currently about ~$5/mo | Static dashboard, serverless notification functions, Netlify Blobs subscriptions | Keep | Usage credits, function calls, logs, bandwidth if traffic grows |
| Render live cron | ~$1/mo | `bbe-live-layer` every 10 minutes | Keep while live notifications matter | Duplicate PropLine calls if older GitHub polling remains active |
| Render BoltOdds worker | ~$7/mo | `bbe-boltodds-shadow-worker` always-on WebSocket worker | Trial only | One more always-on service to monitor |
| Supabase | Pro, about $25/mo before overages | Shadow/live market tables, notification queue, provider evidence | Keep Pro with spend cap on; monitor storage and egress | Raw market snapshot growth, compute/storage overages, spend-cap interruptions |
| GitHub Actions | Free for current public-repo usage | Scheduled pipeline, grading, artifacts, shadow jobs | Keep | Operational schedule jitter more important than cost right now |
| Codex / ChatGPT | $20-$100/mo depending on plan | Engineering, monitoring, debugging, automation, docs | Use the lowest plan that still supports the workflow | Pro can quietly become the biggest recurring cost |

## Source-Specific Decision Rules

### TheRundown

Use TheRundown for official scheduled artifacts:

- preview
- full run
- refresh/lock
- grading-adjacent source of truth
- dated archives

Do not increase TheRundown to high-frequency live polling without explicit cost
approval. Its value is reliable book-of-record data, not cheap live telemetry.

Keep if:

- target-book pitcher strikeout coverage remains healthy
- artifacts remain auditable
- data-point usage stays within plan

Review alternatives if:

- resolved pitcher coverage degrades
- data-point usage approaches overage
- another provider proves equal production coverage plus lower cost

### PropLine

Use PropLine for shadow/fallback and live movement evidence.

Current evidence:

- polling is useful
- webhook receiver works technically
- real signed provider webhook deliveries are landing as of 2026-05-19
- PropLine's 2026-05-19 payload fix adds `bookmaker_key`, `bookmaker_title`,
  `market_id`, and `outcome_id`, making webhook movement reconcilable to
  polling by stable IDs
- as of 2026-05-24, webhook consumption is enabled only as a bounded
  shadow canary into `line_movement_events` with a 100-row / 180-minute default
  window; historical backlog drains require an explicit max-age override
- FanDuel / BetRivers evidence appears more useful than a broad migration case

Keep current tier if:

- polling keeps producing useful line-movement or fallback evidence
- request volume stays comfortable
- it helps live notifications without confusing production truth

Upgrade only if:

- the higher tier clearly fixes a known blocker, such as reliable webhooks,
  materially better coverage, or lower operational burden
- the added cost is tied to a specific decision we can measure

Cut or reduce if:

- BoltOdds proves better live movement coverage
- duplicate polling creates noise or waste
- PropLine does not change decisions by the June 1 provider review

### BoltOdds

Use BoltOdds only as a shadow WebSocket trial until the evidence says otherwise.

Starter trial questions:

- Can one connection cover the needed MLB pitcher strikeout market?
- Are FanDuel, BetMGM, BetRivers, Kalshi, and Caesars rows useful enough?
- Does DraftKings staying weird matter?
- Does the worker stay fresh overnight without stale-feed problems?
- Do WebSocket movements add signal that 10-minute PropLine polling misses?
- Does the added complexity improve notification timing or decision quality?

Keep Starter after trial only if:

- uptime and heartbeats are healthy
- normalized rows cover enough target books
- row volume is manageable
- movement events would have improved timing/confidence
- it can replace or reduce another cost or manual burden

Do not buy Pro unless:

- Starter proves ROI
- the missing capability is explicitly tied to a better betting/product outcome
- Tyler approves the jump after seeing trial evidence

### Netlify

Netlify is a low concern while usage stays small.

Keep watching:

- function calls
- scheduled function behavior
- function log retention
- bandwidth
- deploy/usage credits
- Blobs subscription storage

Do not move off Netlify for cost unless there is real usage pressure. Right now
its value is simplicity.

### Render

Render cost is easy to reason about because the architecture maps to services:

- cron job for `bbe-live-layer`
- background worker for `bbe-boltodds-shadow-worker`

Keep the cron if live notifications are useful. Keep the always-on worker only
if BoltOdds is worth the provider cost plus the operational complexity.

The shadow pipeline-timing ledger rides on the existing `bbe-live-layer` cron.
Do not add another Render service just to evaluate GitHub lock timing unless
the existing cron proves too slow or overloaded.

### Supabase

Supabase is now Pro and is the right home for append-only evidence and the
staged operational control plane.

As Supabase becomes the operational foundation, the cost guardrail changes from
"can we store shadow evidence" to "can this remain the low-friction control
plane without surprise overages." The first required guardrails are row-volume
audit, database/table-size audit, compact movement summaries, and dry-run
retention. Pro is justified by lock-ledger reliability, live/provider evidence,
and avoiding Free read-only restrictions, but raw tick retention must stay
bounded.

Current baseline captured 2026-05-21:

- Supabase dashboard showed org database size `0.685 / 0.5 GB` on Free before
  upgrade.
- Linked BBE Postgres size via CLI: `639 MB`, about `7.8%` of the Pro included
  8 GB disk allowance.
- Largest table: `market_snapshots`, about `462 MB` total with roughly
  `399k` estimated rows.

Daily/weekly guardrail query:

```powershell
npx supabase db query --linked --file scripts\supabase_storage_guardrail.sql -o json
```

Watch for:

- table growth from `market_snapshots`
- total database size versus the included Pro 8 GB disk allowance
- compact rollup health from `market_pick_evidence`
- candidate-row volume from `shadow_notification_candidates`
- `notification_events` retention
- `market_feed_heartbeats` volume
- API throughput
- egress/storage once dashboards or diagnostics read more from Supabase

If database size approaches 6 GB or egress starts trending toward the plan
allowance, pause new capture work and run retention dry-runs before adding
spend or disabling spend caps.

### Codex / ChatGPT

Treat Codex as operator tooling, not app infrastructure.

The `$100/mo` plan makes sense during build-out months when the work involves:

- long repo sessions
- parallel debugging
- CI/deploy loops
- architecture planning
- provider investigation
- automation maintenance
- frequent context-heavy handoffs

The `$20/mo` Plus plan may be enough later if the app settles into:

- daily read-only operations briefs
- small docs updates
- scoped bugfixes
- occasional dashboard polish
- fewer long-running agents and fewer heavy code sessions

Suggested policy:

- Use Pro during active build/trial months.
- Re-evaluate monthly once live providers stabilize.
- Downgrade to Plus for a quiet month if the work is mostly monitoring and
  small edits.
- Upgrade again only when the workflow clearly hits limits or delayed work costs
  more than the plan difference.

This is not awkward; it is good project discipline. The goal is the cheapest
tooling tier that preserves momentum and context quality.

## Monthly Review Checklist

Run this once a month, or before adding/upgrading a provider. Pair it with the
monthly cost / complexity review in `docs/operational-risk-register.md`.

- What did each paid source improve this month?
- Did any provider change a pick, line lock, notification, or confidence read?
- Did any source fail, go stale, or require manual babysitting?
- Are we paying for overlapping sources that produce the same evidence?
- Can one source be downgraded, paused, or moved to on-demand use?
- Are we paying for live data before we have a live decision that uses it?
- Did app runtime costs exceed the monthly side-project comfort zone?
- Is Codex still earning the $100 plan this month, or can Plus handle the next
  month?

## Decision Guardrails

Default monthly posture:

- Keep production stable.
- Prefer one book-of-record source plus one live/shadow evidence source.
- Avoid paying two providers to answer the same question.
- Do not upgrade for theoretical future features.
- Upgrade only when the missing data is tied to a specific decision or workflow.
- Track trial end dates and cancel or downgrade before "maybe useful" becomes a
  permanent bill.

If monthly app runtime/data cost rises above roughly `$200/mo`, pause and write
a short ROI note before adding more spend. If combined app plus operator tooling
stays above roughly `$300/mo` for more than one trial/build month, review what
can be cut, downgraded, or automated away.

## Source Links

Last external pricing check: 2026-05-07.

- BoltOdds pricing: https://boltodds.com/pricing
- Netlify pricing: https://www.netlify.com/pricing/
- Supabase pricing: https://supabase.com/pricing
- GitHub Actions billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Render pricing: https://render.com/pricing/
- OpenAI Codex with ChatGPT plans: https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan
- OpenAI ChatGPT Pro tiers: https://help.openai.com/en/articles/9793128
