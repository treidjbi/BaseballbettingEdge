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

## Separately approved inbox cleanup — completed September 12

After retirement, Tyler approved a recoverable, webhook-inbox-only cleanup.
This supersedes the earlier no-deletion scope only for the retired raw inbox.
The latest completed physical backup was 1651459386, inserted at
2026-09-12T05:39:32.056Z; PITR was disabled. A separate custom pg_dump archive
was created at:

`/Users/tyler/Documents/Codex/Backups/BaseballBettingEdge/2026-09-12-webhook-inbox/inbox.dump`

The 67,161,418-byte archive was restored successfully into an isolated local
PostgreSQL 17 container. Its exact count (727,311), row fingerprint sum
(419543915638217971468961), and received range (May 5 through September 9)
matched production. Archive SHA256:
`f2b58a1f331e2ccd2f98cf520ba7a71bc5b73e424e2a49ec15a3758ba05e7f0e`.
The archive and manifest are private local files outside Git; the sanitized
manifest and execution receipt are tracked under
`data/research/retention/webhook-inbox-2026-09-12/`.

Dependency checks found zero incoming foreign keys, dependent rewrite rules,
or user triggers. The 13:41Z natural cycle still skipped webhooks. Execution
used a two-second lock timeout and 30-second statement timeout, repeated the
exact count/fingerprint and dependency checks while holding the inbox lock,
and ran TRUNCATE ONLY ... CONTINUE IDENTITY RESTRICT with no CASCADE.

The successful receipt at 13:42:54Z reported zero remaining rows and a
32,768-byte table footprint, down from 768,843,776 bytes: 768,811,008 bytes
(733.20 MiB) reclaimed from the inbox. Database size decreased from
6,359,125,139 to 5,590,379,667 bytes (about 5.92 to 5.21 GiB). Independent
13:43:21Z verification confirmed the empty inbox, both critical published
artifacts, and the continued presence of market_snapshots and
line_movement_events. No other table was truncated or altered; no VACUUM FULL
or production restore was run. Recovery instructions accompany the archive.
Keep the archive; any production restoration or other-table cleanup requires
its own scope. Raw payloads are no longer retained in the production inbox.
