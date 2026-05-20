# 2026-05-20 Live Notification Coordinator Plan

**Goal:** After the Supabase operational/provider switch is stable, replace noisy
duplicated push behavior with one coordinated notification system that sends
fewer, better-timed, more useful alerts.

**Status:** Future-state plan only. No current notification behavior changes.

**Controlling posture:** Do not change live notification behavior until the
lock-consumer canary and production-source switch are reviewed. GitHub
`send-notifications` remains allowed as the current production fallback until
Supabase notification delivery is proven stable.

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
6. After one clean slate, reduce GitHub `send-notifications` to fallback or
   artifact-health mode.
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
