# PropLine Webhook Usage Audit - 2026-06-19

Read-only diagnostic. PropLine webhooks are not a full odds source and this report does not change production behavior.

- Access status: `blocked`
- Window UTC: `2026-06-17T00:00:00+00:00` through `2026-06-19T23:59:59.999999+00:00`
- Deliveries: 0 signed=0 processed=0 unsupported=0
- Book metadata: bookmaker_key=0 stable_market_ids=0
- Movement events: 0 webhook_only=0 polling_confirmed=0
- Notification events: 0
- Duplicate dedupe keys: 0
- Post-start or stale events: 0
- Accepted-bet overlap: 0

## Recommended Uses

- None from available evidence.

## Blocked Uses

- `official_odds_source`
- `model_input`
- `staking_input`
- `automatic_bet_trigger`

## Access Issues

- SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY unavailable; emitted partial zero-row audit.
