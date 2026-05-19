# PropLine Webhook Follow-Up

Last updated: 2026-05-19

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

As of 2026-05-19, Tyler confirmed PropLine fixed the Streaming Lite entitlement
mistake. Real signed `line_movement` deliveries are landing in
`public.propline_webhook_deliveries`.

Current implementation state:

- Receiver: active Netlify function.
- Inbox: real rows are landing with `signature_valid=true`.
- Processor: implemented as a shadow-only script and wired into the Render live
  layer behind `LIVE_PROCESS_PROPLINE_WEBHOOKS=false` by default.
- Known payload caveat: current real line-movement payloads do not include a
  sportsbook key, so the processor writes neutral movement rows with
  `bookmaker_key='propline_webhook'` and metadata
  `bookmaker_key_missing=true`. Do not treat these as official book prices.

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

Use PropLine webhooks as shadow movement evidence only. Enable automated
processor runs only after the lock-ledger observation is not at risk, then
compare webhook timing, coverage, duplicate behavior, and noise against
PropLine polling and BoltOdds before any notification or provider-source use.
