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
Current status: runtime flags saved; source release and natural-cycle proof pending.
The PropLine dashboard offers no webhook controls on Hobby; upstream subscription
active=false has not been independently verified. The retired receiver prevents
future inbox writes regardless of residual upstream configuration.
