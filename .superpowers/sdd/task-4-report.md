# Task 4 Report: Verify Netlify Sender Compatibility

## Scope

Validated the Netlify sender compatibility boundary for the new
`mainline_best_price_changed` notification rows.

- Added one focused compatibility test in `tests/test_send_live_notifications_function.mjs`
- Kept the change scoped to the sender test file only
- Did not change Netlify sender logic, Python worker logic, SQL, Render env vars, or production flags

## Test Evidence

### Added compatibility coverage

Added a test that asserts the generic sender path preserves the existing title/body/tag/payload behavior for a `mainline_best_price_changed` row:

- `buildPushPayload` keeps the row title and body unchanged
- `buildPushPayload` uses the row `dedupe_key` as the push tag
- `buildPushPayload` carries `event_type='mainline_best_price_changed'` through `data.eventType`
- `isNotificationEventPostStart` returns `true` when `payload.game_time` is at or before `now`

### Required command

Ran:

```bash
node --test tests/test_send_live_notifications_function.mjs
```

Result:

- `18 tests`
- `18 pass`
- `0 fail`

The test output also showed the existing sender still suppresses stale rows and post-start rows as expected.

## Files Changed

- `tests/test_send_live_notifications_function.mjs`

## Self-Review

- The compatibility test stays within the brief and uses the existing helper surface already present in the file.
- No event-type-specific sender code was added.
- No sender behavior changed for first observation, stale rows, locked picks, or unchanged prices.
- The existing sender implementation already treats the new event type as generic notification content.

## Concerns

- This task only verifies sender compatibility; it does not exercise the full live-layer production path end to end.
- The new coverage is intentionally unit-level, so it depends on the sender helper contract staying stable.

---

## Fix Report: Sender-Level Review Findings

## What Changed

- Added sender-level tests in `tests/test_send_live_notifications_function.mjs` that drive `sendLiveNotificationsNow` through the existing queue, subscription, and push flow.
- Verified `mainline_best_price_changed` produces exactly one push attempt with the expected title, tag, and payload fields.
- Verified post-start suppression for the same event type through the sender flow, without relying only on the helper-level `isNotificationEventPostStart` check.
- Kept the change scoped to the test file only.

## Test Command

```bash
node --test tests/test_send_live_notifications_function.mjs
```

## Test Result

- `20 tests`
- `20 pass`
- `0 fail`

## Files Changed

- `tests/test_send_live_notifications_function.mjs`

## Concerns

- Coverage is still unit-level around the Netlify sender boundary; it does not exercise the deployed function in Netlify.
