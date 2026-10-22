# PropLine Webhook Follow-Up

Last updated: 2026-05-24

## Current Goal

Test PropLine webhooks as a shadow-only line movement feed for one month.

The goal is not to replace TheRundown yet. The goal is to learn whether PropLine
webhooks give us faster or more complete movement evidence, especially for
FanDuel and BetRivers, while the production pipeline keeps using the existing
provider flow.

## What We Built

- Added a Netlify webhook receiver at:
  `https://baseballbettingedge.netlify.app/api/propline-webhook`
- Receiver file:
  `netlify/functions/propline-webhook.mjs`
- Added helper script:
  `scripts/create_propline_webhook_subscription.py`
- Added tests:
  `tests/test_propline_webhook_function.mjs`
- Added shadow processor:
  `scripts/process_propline_webhooks.py`
- Added processor tests:
  `tests/test_process_propline_webhooks.py`
- Merged in PR #22:
  `https://github.com/treidjbi/BaseballBettingEdge/pull/22`

## Safety Guardrails

The receiver and processor are shadow-only.

The receiver writes only to:

- `public.propline_webhook_deliveries`

The processor can mark inbox rows processed and write neutral movement facts to:

- `public.line_movement_events`

It does not change:

- production odds provider order
- `today.json`
- dashboard output
- picks
- grading
- calibration
- notifications

## Verification Already Done

Before merge:

- `node --test tests/test_propline_webhook_function.mjs`
- `python -m py_compile scripts/create_propline_webhook_subscription.py`
- `python -m pytest tests/test_shadow_propline_to_supabase.py tests/test_market_infra_prop_snapshot.py tests/test_market_infra_supabase_writer.py -v`
- `git diff -- .github/workflows/pipeline.yml pipeline/fetch_odds.py pipeline/run_pipeline.py dashboard`

Results:

- Webhook function tests passed.
- Helper script compiled.
- Focused market-infra tests passed.
- Production pipeline/dashboard diff was empty.

After merge:

- Netlify production deploy included `propline-webhook`.
- Netlify deploy metadata showed the function route:
  `/api/propline-webhook`

## Current Status

As of 2026-05-24, Tyler approved starting shadow-only webhook consumption. Real
signed `line_movement` deliveries are landing in
`public.propline_webhook_deliveries`, and the live-layer worker now processes a
bounded recent canary slice into `public.line_movement_events`.

Current implementation state:

- Receiver: active Netlify function.
- Inbox: real rows are landing with `signature_valid=true`.
- Processor: implemented as a shadow-only script and wired into the live layer
  with `LIVE_PROCESS_PROPLINE_WEBHOOKS=true` by default. Roll back by setting it
  to `false`.
- Canary bounds: `LIVE_PROCESS_PROPLINE_WEBHOOK_LIMIT` defaults to `100` rows
  per run, and `LIVE_PROCESS_PROPLINE_WEBHOOK_MAX_AGE_MINUTES` defaults to
  `180`. Set max age to `0` only for an explicit backlog drain.
- Notification bounds: as of 2026-06-24, webhook movement notifications use a
  separate queue-eligibility gate,
  `LIVE_PROPLINE_WEBHOOK_NOTIFICATION_MAX_AGE_MINUTES=20`, so stale webhook
  evidence can still be processed without queuing stale sends.
- Direct Supabase check before enabling showed 2,638 valid unprocessed
  deliveries from 2026-05-05 through 2026-05-24, but zero current
  `line_movement_events` with `metadata->>'source'='propline_webhook'`. The
  canary intentionally avoids draining the historic backlog.
- Proof runs on 2026-05-24 processed the current recent slice: 95
  webhook-sourced `line_movement_events`, 26 processed
  `unsupported_payload_shape` deliveries, zero unprocessed rows inside the
  current 3-hour window, and zero `notification_events` created by the proof
  window. Older backlog rows remain unprocessed by design.
- `shadow_movement_source_comparisons` already has PropLine webhook versus
  BoltOdds snapshot rows, but they are stale as of 2026-05-16. Use the new
  webhook movement rows to refresh that comparison before making any provider
  timing claim.
- Comparison refreshed on 2026-05-24. The refresh materialized the new webhook
  rows into `shadow_provider_movement_events`, matched them to nearest
  BoltOdds snapshots within 90 minutes using normalized pitcher + side and the
  `pitcher_strikeouts` / `Strikeouts` market-key alias, and upserted 95 current
  comparison rows: 42 `propline_webhook_first`, 21 `boltodds_first`, and 32
  `no_boltodds_match`.
- Payload update: PropLine shipped `bookmaker_key`, `bookmaker_title`,
  `market_id`, and `outcome_id` on every `line_movement` and `resolution`
  delivery after Tyler's 2026-05-19 support thread with Andy. `market_id` and
  `outcome_id` match the IDs returned by `/odds`, `/odds/history`, and
  `/results`, so webhook movement can be reconciled to polled snapshots without
  fuzzy player+line+book matching.
- Processor behavior: if those fields are present, the processor writes the
  actual `bookmaker_key` and stores `bookmaker_title`, `market_id`, and
  `outcome_id` in metadata. Legacy rows without a book still use
  `bookmaker_key='propline_webhook'` with `bookmaker_key_missing=true`.
- Follow-up on 2026-05-26: after `bbe-live-layer` was redeployed to current
  `main`, the normal 23:50 UTC scheduled run processed 8 webhook deliveries
  into 8 movement rows. Recent unsupported rows were alternate strikeout ladder
  outcomes such as `9+ Strikeouts` with `point=null`; those are not standard
  over/under K-line movements, so the processor classifies them separately as
  unsupported ladder outcomes instead of writing movement events.
- Optional provider follow-up: Andy offered a future `filter_bookmaker_key`
  subscription option for including/excluding specific books. Do not request or
  depend on it until webhook noise/coverage evidence says book filtering would
  materially reduce cost or alert noise.

## Verification

Check the inbox:

   ```sql
   select prop_line_event, signature_valid, processed, processing_error, received_at
   from public.propline_webhook_deliveries
   order by received_at desc
   limit 10;
   ```

After processor runs, check shadow movement rows:

   ```sql
   select slate_date, pitcher, side, bookmaker_key, previous_line, current_line,
          previous_odds, current_odds, movement_kind, observed_at, metadata
   from public.line_movement_events
   where metadata->>'source' = 'propline_webhook'
   order by observed_at desc
   limit 20;
   ```

Check canary backlog behavior:

   ```sql
   select processed, count(*), min(received_at), max(received_at)
   from public.propline_webhook_deliveries
   group by processed
   order by processed;
   ```

## Historical Blocker

PropLine originally rejected webhook creation with:

```text
403 {"detail":"Webhooks require the Streaming tier. Upgrade at https://prop-line.com/#pricing"}
```

That is no longer the active blocker. PropLine acknowledged the entitlement
mistake and real signed deliveries are now present.

## One-Month Evaluation Criteria

Evaluate these before changing production behavior:

- Did webhook deliveries arrive reliably?
- Did HMAC signatures validate?
- Were there duplicate or out-of-order deliveries?
- Did webhooks catch FanDuel or BetRivers movement before scheduled polls?
- Did DraftKings movement improve, or stay flat?
- Did Kalshi remain absent?
- Did any webhook-only movement change pick confidence, CLV read, or actionability?

## Current Recommendation

Stay on TheRundown for production.

Use webhook rows only as shadow comparison evidence against PropLine polling and
BoltOdds snapshots. Do not use webhook rows for official odds, picks, provider
promotion, or user-facing notification sends without a separate reviewed gate.

Use the bounded automated processor run to compare webhook timing, coverage,
duplicate behavior, and noise against PropLine polling and BoltOdds before any
notification or provider-source use.
