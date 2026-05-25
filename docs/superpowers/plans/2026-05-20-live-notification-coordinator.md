# 2026-05-20 Live Notification Coordinator Plan

**Goal:** After the Supabase operational/provider switch is stable, replace noisy
duplicated push behavior with one coordinated notification system that sends
fewer, better-timed, more useful alerts.

**Status:** Future-state plan only. No current notification behavior changes.

**Controlling posture:** Do not change live notification behavior until the
lock-consumer canary and production-source switch are reviewed. GitHub
`send-notifications` remains allowed as the current production fallback until
Supabase notification delivery is proven stable.

**2026-05-23 canary exception:** Tyler approved a single-sender notification
canary during the Supabase lock migration because duplicate pushes were already
hurting trust. `ENABLE_GITHUB_LEGACY_NOTIFICATIONS=false` disables the GitHub
artifact-diff sender while keeping GitHub artifact publishing and grading
intact. Supabase `notification_events` plus Netlify `send-live-notifications`
is the only user-facing sender during this canary. Roll back by setting
`ENABLE_GITHUB_LEGACY_NOTIFICATIONS=true`.

**2026-05-24 stale-queue guard:** After a Netlify function dependency deploy
left live notification events queued but unsent during the active slate,
`send-live-notifications` now suppresses stale queued rows instead of sending
late betting-action pushes. The default TTL is 20 minutes, overrideable with
`LIVE_NOTIFICATION_MAX_EVENT_AGE_MINUTES`; suppressed rows are retained in
`notification_events` with `send_attempts=3` and a stale-suppression
`last_send_error`. The authenticated manual endpoint supports `smoke_check`
mode for post-deploy queue/subscriber checks without sending pushes.

**2026-05-24 PropLine webhook canary:** The live layer may process recent
PropLine webhook inbox rows into shadow `line_movement_events` using
`LIVE_PROCESS_PROPLINE_WEBHOOKS`. This is comparison evidence only and must not
write user-facing `notification_events` or change notification eligibility
without the provider notification gates in this plan.

## Problem

Today there are two notification paths:

- GitHub pipeline runs call `send-notifications`, which reads static artifacts
  and can send new-pick, lock, reminder, and result-style pushes.
- The Render live layer writes Supabase `notification_events`, and Netlify
  `send-live-notifications` sends those queued events.

That split causes three product problems:

1. Duplicate or near-duplicate alerts when both systems notice the same pick
   transition.
2. Individual pitcher pushes during clustered start windows, which creates a
   bulk-alert reminder instead of a useful decision signal.
3. Bad timing trust: reminders can arrive too early, while some lock alerts can
   arrive after game start when GitHub is delayed.

Tyler's current workaround is to treat the push pile as a rough reminder, close
the notifications, and open the app. The future system should make the push
itself useful and direct the full detail to the app.

## Non-Goals

- Do not change model math, thresholds, staking, grading, provider order, or
  source-of-truth rules.
- Do not enable BoltOdds/PropLine production notification sends without the
  existing provider notification gates.
- Do not remove GitHub artifact notifications until Supabase queue delivery has
  at least one clean canary slate.
- Do not add user-facing notification preferences until the core event classes
  are clean and low-noise.

## Recommended Architecture

Use Supabase `notification_events` as the durable notification source, then make
all producers write semantic, deduped events into that queue.

```text
GitHub artifacts / lock consumer / live layer / provider movement
        |
        v
notification coordinator rules
        |
        v
Supabase notification_events
        |
        v
Netlify send-live-notifications
        |
        v
Push subscribers + dashboard deep links
```

GitHub `send-notifications` should move from "parallel sender" to
"fallback/artifact-health sender" only after the queue has proven reliable. The
main user-facing sender should be `send-live-notifications`.

## Dynamic When-To-Bet Signals

The coordinator should not depend on a full artifact publish every time the
market moves. Its first-class input should be the live market/control loop:

- `live_market_display_state` for current best book, best line, best odds,
  freshness, market consensus, and actionable-state labels.
- `market_pick_evidence` for compact directionality such as better-now,
  worse-now, toward-pick, away-from-pick, reversal, and volatility context.
- `official_market_lines` or fresh `current_market_lines` only after the provider
  cutover gates approve those rows as production-grade inputs.
- `shadow_notification_candidates` as the would-have-sent audit layer before a
  new provider-driven alert class writes user-facing `notification_events`.

The goal is to answer "should I act now, shop, wait, or ignore this move?" while
keeping model math, thresholds, staking, and provider order unchanged. A
10-minute live-layer cadence can support this timing without requiring every
pipeline artifact to refresh every 10 minutes.

## First-Pass Decision Policy

Before any new provider-driven alert class sends to Tyler, implement these as
shadow-only decision labels and review at least one slate of would-have-sent
rows:

- `bet_now`: fresh provider state, before lock/start, current or best supported
  book still clears model fair price, and either the official ref book or broad
  supported-book confirmation backs the read.
- `shop_price`: selected/current artifact book is worse than the best supported
  live book by a material margin, initially 5-10 cents, and the best price still
  clears model fair price.
- `wait`: no supported book clears model fair price, or provider agreement is
  incomplete but not stale enough to call a technical issue.
- `monitor`: evidence is fresh but mixed, single-provider only, or volatile.
- `ignore_stale`: provider rows are stale, heartbeat support is missing, or the
  event would arrive after the betting window.
- `system_issue`: the problem is operational, such as stale official artifacts,
  stuck notification queue, missing lock consumption, or sender failure.

These labels must remain informational until a later promotion review approves a
specific send class. Do not use them to change model verdicts, thresholds,
stakes, provider order, or automatic bet placement.

### Decision Label v0 Inputs

Use explicit fields so the same label can be reproduced in the live layer,
dashboard, and daily review:

- `decision_label`: one of `bet_now`, `shop_price`, `wait`, `monitor`,
  `ignore_stale`, or `system_issue`.
- `decision_reason_codes`: compact list such as `fresh`, `pre_lock`,
  `best_price_playable`, `selected_book_worse`, `broad_confirmation`,
  `single_provider`, `volatile`, `stale`, or `post_window`.
- `model_fair_odds`: model fair American odds for the pick side.
- `selected_book`, `selected_line`, `selected_odds`: the current artifact or
  official ref-book price being compared.
- `best_book`, `best_line`, `best_odds`: the best supported live price when
  available.
- `shop_delta_cents`: best supported odds minus selected/current odds, positive
  when the best book is better for Tyler.
- `freshness_status`, `observed_at`, and `provider_heartbeat_held`: enough
  context to explain why a row was trusted or suppressed.
- `window_status`: `pre_lock`, `lock_window`, `post_lock_pre_start`,
  `post_start`, or `unknown`.
- `confirmation_status`: `official_ref_book`, `broad_confirmation`,
  `single_provider`, `mixed`, or `stale`.

Initial shadow thresholds:

- `shop_price` requires `shop_delta_cents >= 5` and best live price still
  playable. Treat 5-10 cents as the review band before locking a production
  threshold.
- `bet_now` requires fresh state, `window_status` before `post_lock_pre_start`,
  playable selected or best price, and `confirmation_status` of
  `official_ref_book` or `broad_confirmation`.
- `monitor` is the default for fresh but mixed, single-provider, or volatile
  rows.
- `ignore_stale` wins over betting labels when freshness or timing is not
  trustworthy.
- `system_issue` is reserved for operational failures and should not be mixed
  with betting-action copy.

## Notification-To-Bet Attribution

`accepted_bets` already supports `notification_event_id` and
`shadow_candidate_id`. The missing product contract is to carry those IDs from
alert source to dashboard bet ticket:

- Push deep links should include enough non-secret context for the app to know
  which `notification_events` row or `shadow_notification_candidates` row opened
  the ticket.
- The live market panel and bet ticket should preserve that context when Tyler
  logs a bet.
- Manual dashboard logs without notification context should continue to use
  `source=dashboard_manual`.
- Notification-originated logs should use `source=notification`; shadow review
  flows can use `source=shadow_candidate`.

Without this bridge, the system can count sent pushes and logged bets, but it
cannot prove whether a notification changed Tyler's action.

### Alert Context / Deep-Link Contract

Any real push, shadow review link, or dashboard candidate-link should carry a
small non-secret context object. Query parameters are acceptable for the first
implementation; avoid provider raw payloads and service-role data.

Required context:

- `slate_date`
- `pitcher`
- `normalized_pitcher`
- `side`
- `decision_label`
- `source`: `notification`, `shadow_candidate`, or `dashboard_manual`

One of:

- `notification_event_id`
- `shadow_candidate_id`

Recommended context when available:

- `dedupe_key`
- `game_time`
- `selected_book`, `selected_line`, `selected_odds`
- `best_book`, `best_line`, `best_odds`
- `model_fair_odds`
- `observed_at`
- `source_artifact_sha256`

The dashboard should store this context only long enough to prefill the market
panel and bet ticket. The accepted-bet payload should persist the stable IDs,
`source`, price source, and model snapshot, not the full alert payload.

### Attribution Match Rules

When joining accepted bets back to notifications or candidates, use this
precedence:

1. Exact `notification_event_id` match.
2. Exact `shadow_candidate_id` match.
3. Same `slate_date`, `normalized_pitcher`, and `side`, with `accepted_at` after
   alert/candidate creation and before game start.
4. Same slate/pitcher/side within a configurable review window, initially 30
   minutes after alert/candidate creation, marked as `time_window_match`.
5. Otherwise classify as `dashboard_manual_unattributed`.

If multiple candidates match by time window, prefer the most recent actionable
candidate before `accepted_at`. If ambiguity remains, leave the bet unmatched and
report it for manual review rather than overstating attribution.

## Notification Classes

### 1. Start Window Digest

Send one grouped push for a tight start cluster instead of one reminder per
pitcher.

Example:

```text
4 tracked pitchers start at 3:40/3:45
2 FIRE, 1 LEAN, 1 watch. Best prices changed on 2.
```

Default behavior:

- Group by slate date and start window.
- Use a 10-15 minute reminder window before the first game in the cluster.
- Include only active tracked picks and high-value watch items.
- Keep individual pitcher detail in the app, not in the push body.

This replaces the current "bulk push pile as reminder" behavior with a
purpose-built digest.

### 2. Lock Batch

Send one lock-cluster push when multiple picks lock in the same operational
window.

Example:

```text
3 picks locked for 4:10 starts
2 FIRE, 1 LEAN. Open app for final prices.
```

Rules:

- Never send post-start lock pushes as normal success messages.
- If a lock is late, send a system/watch alert or suppress it and mark it in the
  operations brief, depending on severity.
- Use shared semantic keys so GitHub and Supabase cannot both send the same lock
  transition.

### 3. Urgent Market Movement

Keep individual pushes for market movement only when the alert is actionable.

Candidate examples:

- FIRE pick price moves materially against us and the pick is still playable.
- Better book appears with meaningful cushion.
- Broad-book confirmation changes the action window.
- A selected book becomes materially worse than best available.

Suppress:

- Tiny price changes.
- One-book noise without broad confirmation.
- Reversal/volatility unless summarized later.
- Stale provider rows.

### 4. System Health

Send sparingly, but do send when action is needed:

- Official artifact stale close to a lock window.
- Supabase queue has pending unsent actionable events.
- Lock ledger captured rows that GitHub did not consume.
- Sender failed during an active slate.

These should be separate from betting-action alerts so Tyler can tell
"technical issue" from "betting decision."

### 5. Daily / Post-Slate Summary

Optional later class. This should stay out of the real-time path until the core
push experience is clean.

## Shadow-To-Production Alert Review

Before moving any new alert class from `shadow_notification_candidates` to real
`notification_events`, daily review should join:

- would-have-sent candidate rows and suppression reasons;
- actual notification rows and send status;
- accepted bets logged after an alert or candidate, when attribution exists;
- market state at alert time and at accepted-bet time;
- CLV and final outcome after grading.

The first production movement-alert class should be the narrowest class that
shows decision value without noise, likely `shop_price` or `bet_now` for active
FIRE picks only. Do not promote broad movement summaries, single-book moves, or
volatile reversals before this review proves they help.

### Daily Review Output v0

The first review artifact can be a Markdown table plus JSON export. It should
include one row per candidate or notification:

- `slate_date`
- `event_source`: `shadow_candidate` or `notification_event`
- `event_id`
- `dedupe_key`
- `decision_label`
- `suppression_reason`
- `pitcher`
- `side`
- `verdict`
- `window_status`
- `confirmation_status`
- `selected_book`, `selected_line`, `selected_odds`
- `best_book`, `best_line`, `best_odds`
- `shop_delta_cents`
- `accepted_bet_id`
- `accepted_bet_source`
- `accepted_at`
- `accepted_book`, `accepted_line`, `accepted_odds`, `accepted_units`
- `attribution_match_type`
- `price_clv_cents`, `line_clv_delta`, `result`, and `pnl` when graded

The review should summarize counts by `decision_label`, suppression reason,
alert class, accepted-bet source, attribution match type, and eventual
CLV/result once available.

## Dedupe Model

Add a semantic notification identity that is shared across producers:

```text
slate_date:event_family:window_or_pick_key:source_role
```

Examples:

```text
2026-05-20:start-window:2026-05-20T22:40Z:tracked
2026-05-20:lock-batch:2026-05-20T19:10Z
2026-05-20:movement:tyler-mahle:over:material-against
2026-05-20:system:stale-artifact:pre-lock
```

`notification_events.dedupe_key` remains the database uniqueness guard, but the
coordinator should also reason about event families so a GitHub lock and a
Supabase lock cannot both send different-looking copies of the same alert.

## Timing Rules

Start-window digests should be based on actual game-time clusters, not broad
per-pick reminder windows.

Recommended first pass:

- Cluster starts within a 10-minute span.
- Send 10-15 minutes before the first game in the cluster.
- Send at most one start-window digest per cluster.
- If a pick is already locked and included in a lock batch, do not separately
  send a pitcher reminder unless market movement creates a new action.
- If the reminder would be later than first pitch, suppress normal reminder and
  log it as late.

This directly targets the current "hour early reminder" and "post-start lock"
failure modes.

## Promotion Sequence

1. Finish full lock-ledger soak and run the non-strict Supabase lock-consumer
   canary.
2. Confirm `notification_events` queue health: pending, sent, failed, duplicate
   count, and stale event count.
3. Add shadow-only coordinator rows or metadata for start-window digests and
   lock batches. Do not send them yet.
4. Compare would-have-sent coordinator output to actual received pushes for at
   least one clean slate.
5. Enable coordinator sends for one class at a time:
   - Start-window digest first.
   - Lock batch second.
   - Urgent market movement third.
6. During the 2026-05-23 canary, GitHub `send-notifications` is fully disabled
   for user-facing pushes; after review, either keep it as fallback/artifact
   health only or roll it back temporarily if the live queue fails.
7. After several clean slates, decide whether old per-pitcher reminder behavior
   can be removed entirely.

## Evidence To Collect

Daily operations should report:

- Total pushes sent.
- Pushes by class.
- Duplicate semantic events suppressed.
- Start-window digests that would have replaced individual reminders.
- Lock batches that would have replaced per-pitcher lock pushes.
- Late reminders suppressed.
- Post-start lock alerts suppressed or marked system-health.
- Failed and pending queue rows.
- Whether any notification likely changed Tyler's action.
- Accepted bets by source: `dashboard_manual`, `notification`,
  `shadow_candidate`, and `other`.
- Attributed alert-to-bet rows once `notification_event_id` and
  `shadow_candidate_id` are wired through the app.

## Acceptance Gates

The coordinator is ready for production only when:

- No duplicate FIRE/new-pick/lock notifications in a clean slate.
- No normal reminder is sent after game start.
- No normal lock alert is sent after game start.
- Start-window digests arrive in the intended 10-15 minute window.
- GitHub delayed runs do not create duplicate or stale betting-action pushes.
- Sender failure is visible without creating noisy repeats.
- Tyler can use notifications as triage and then open the app for detail.

## Rollback

Rollback should be simple:

1. Disable coordinator-generated sends.
2. Keep `notification_events` rows for audit.
3. Restore GitHub `send-notifications` as the fallback sender.
4. Leave model, grading, artifacts, provider order, and lock logic untouched.

## Future UI Tie-In

The push should be a concise triage layer. The app should carry the full detail:

- grouped start window
- final locked price
- best available price
- selected book
- market movement read
- provider agreement
- late/stale/system warning if relevant

This connects to
`docs/superpowers/plans/2026-05-20-live-market-decision-ui.md`, but the
notification coordinator can be built first as long as pushes deep-link to the
existing dashboard.
