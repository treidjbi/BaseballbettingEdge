# PropLine Webhook Receiver

Observation-only receiver for future PropLine line-movement and resolution webhooks.

This function is dormant until the user approves a PropLine Streaming or Streaming Lite tier.

Required secrets:

- `PROPLINE_WEBHOOK_SECRET`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Security model:

- Supabase JWT verification is disabled because PropLine does not send Supabase JWTs.
- The receiver verifies `X-PropLine-Signature` with HMAC-SHA256.
- `X-PropLine-Delivery` is used as the dedupe key.
- The function stores raw payloads only. It does not alter production picks, dashboard JSON, notifications, or grading.
