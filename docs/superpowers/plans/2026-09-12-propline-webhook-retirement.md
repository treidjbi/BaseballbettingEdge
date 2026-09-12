# PropLine webhook retirement — September 12, 2026

Tyler approved disabling webhook processing and deliveries, preserving historical
records, and retiring unused runtime integration. He confirmed that PropLine
was already downgraded because webhooks were unused. The signed-in dashboard
shows Hobby (5,000 requests/day) and no webhook subscription controls.

## Scope

- Render bbe-live-layer: set LIVE_PROCESS_PROPLINE_WEBHOOKS=false and
  LIVE_SEND_PROPLINE_WEBHOOK_MOVEMENT_NOTIFICATIONS=false; save and apply on
  next run without rebuilding. Both saved values were verified in the UI.
- The live entrypoint hardcodes both options false, so legacy flags cannot
  reactivate processing in a future deployment.
- Replace the Netlify receiver with a POST acknowledgement that ignores all
  payloads and does not access credentials or the database. Keep the route to
  avoid retries from any residual upstream deliveries.
- Preserve historical inbox rows, movement evidence, schemas and research
  helpers. No provider plan change, key rotation, raw deletion or vacuum.
- Keep polling, mainline best-price sends, reminders, operational locks and
  official pipeline behavior unchanged. Mainline alert mode was verified send.

## Verification and release

179 focused Python tests passed (live worker, Alt V2 integration and live events).
Two replacement receiver tests passed, including no network/payload access.
A regression proves legacy true flags cannot enable the runtime webhook path
and PropLine polling stays enabled when its key is configured.

Release is authorized by Tyler's instruction to execute this retirement.
Verify the deployed receiver acknowledgement, natural live-layer runs with
webhooks skipped and polling active, and stable equality-query counters.
## Release evidence

- PR #49 merged as 371504b007bdc671920b234fc1aa5cdc9e6a3318.
- Netlify production deploy 6aa5550d39f94100086a4940 is ready on that exact
  commit, published 2026-09-12T13:35:33.222Z. Production POST returned
  {"ok":true,"ignored":true,"reason":"webhooks_retired"}.
- Render live-layer build bld-daila3ks728c73allu40 succeeded on the same
  commit in 40.3 seconds. No other Render service was manually redeployed.
- The first natural cycle after the environment change, observed at
  13:30:51.763450Z, persisted propline_webhooks={"skipped":true}, with zero
  missed locks and zero started-unlocked picks. This is a pregame checkpoint,
  not proof of a newly due lock or actual alert delivery.
- That cycle completed TheRundown polling (2 requests, 13:30:55Z) and PropLine
  polling (16 requests, 13:31:10Z).
- Equality-query calls stayed 9418 and shared_blks_read stayed 264009459
  from 13:21:43Z through 13:36:04Z, across the 13:30 cycle.
- Runtime disablement and receiver retirement are verified. The first cycle
  on the newly built source remains a normal subsequent observation; the
  earlier cycle proves the identical two runtime false options.

No new notification was deliberately sent for validation. Mainline send mode
was preserved and its worker tests passed. Exact disk-burst replenishment is
not yet measured; historical storage is unchanged.
The PropLine dashboard offers no webhook controls on Hobby; upstream subscription
active=false has not been independently verified. The retired receiver prevents
future inbox writes regardless of residual upstream configuration.
