# PropLine Webhook Follow-Up

Last updated: 2026-05-05

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
- Merged in PR #22:
  `https://github.com/treidjbi/BaseballBettingEdge/pull/22`

## Safety Guardrails

The receiver is shadow-only.

It writes only to:

- `public.propline_webhook_deliveries`

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

## Current Blocker

PropLine rejected webhook creation with:

```text
403 {"detail":"Webhooks require the Streaming tier. Upgrade at https://prop-line.com/#pricing"}
```

This happened when calling the webhook creation helper against:

```text
https://baseballbettingedge.netlify.app/api/propline-webhook
```

Tyler's pricing screenshot showed Streaming Lite includes:

- webhook line-movement alerts
- resolution delivered on finish
- HMAC-signed deliveries with retry
- up to 5 active webhooks

So the likely issue is one of:

- Streaming Lite entitlement has not propagated yet.
- The API key is still tied to the old tier.
- PropLine's backend gate only recognizes full Streaming, despite the pricing
  page saying Streaming Lite includes webhooks.
- Their error message is stale and uses "Streaming" generically.

## Support Message To PropLine

Send this:

```text
I upgraded to Streaming Lite, which the pricing page says includes webhook
line-movement alerts, HMAC-signed deliveries with retry, and up to 5 active
webhooks.

When calling POST /v1/webhooks with my API key, I receive:
403 {"detail":"Webhooks require the Streaming tier. Upgrade at https://prop-line.com/#pricing"}

Can you confirm Streaming Lite has webhook access and enable it for my
key/account?
```

## When PropLine Responds

### If They Enable Streaming Lite Webhooks

1. Re-run:

   ```bash
   python scripts/create_propline_webhook_subscription.py \
     --url https://baseballbettingedge.netlify.app/api/propline-webhook
   ```

2. Store the returned one-time secret in Netlify as:

   ```text
   PROPLINE_WEBHOOK_SECRET
   ```

3. Trigger a PropLine test delivery.

4. Verify a row lands in Supabase:

   ```sql
   select prop_line_event, signature_valid, processed, processing_error, received_at
   from public.propline_webhook_deliveries
   order by received_at desc
   limit 10;
   ```

5. Let real deliveries accumulate before normalizing payloads into
   `market_snapshots`.

### If They Say Full Streaming Is Required

Do not upgrade automatically.

Decision question:

- Is webhook movement evidence worth an extra $40/month versus continuing
  scheduled shadow polling?

Current read:

- Probably not yet.
- Scheduled PropLine shadow polling already gives useful FanDuel/BetRivers
  evidence.
- Webhooks are worth testing at $39/month, but full Streaming at $79/month needs
  stronger proof that intraday movement changes real decisions.

### If They Say The Key Was Wrong Or Not Propagated

Use the corrected key, then retry webhook creation.

After setup succeeds, rotate any key that was shared in chat or appeared in
tool output.

## One-Month Evaluation Criteria

If webhooks become active, evaluate these before changing production behavior:

- Did webhook deliveries arrive reliably?
- Did HMAC signatures validate?
- Were there duplicate or out-of-order deliveries?
- Did webhooks catch FanDuel or BetRivers movement before scheduled polls?
- Did DraftKings movement improve, or stay flat?
- Did Kalshi remain absent?
- Did any webhook-only movement change pick confidence, CLV read, or actionability?

## Current Recommendation

Stay on TheRundown for production.

Use PropLine webhooks only if Streaming Lite entitlement works. If PropLine
requires the full $79 Streaming tier, pause and compare cost versus likely value
before upgrading.
