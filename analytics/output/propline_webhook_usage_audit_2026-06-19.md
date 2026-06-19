# PropLine Webhook Usage Audit - 2026-06-19

Read-only diagnostic. PropLine webhooks are not a full odds source and this report does not change production behavior.

- Access status: `complete`
- Window UTC: `2026-06-17T00:00:00+00:00` through `2026-06-19T23:59:59.999999+00:00`
- Deliveries: 514 signed=514 processed=512 unsupported=57
- Book metadata: bookmaker_key=514 stable_market_ids=514
- Movement events: 377 webhook_only=377 polling_confirmed=0
- Notification events: 0
- Duplicate dedupe keys: 0
- Post-start or stale events: 0
- Accepted-bet overlap: 0

## Recommended Uses

- `dashboard_webhook_confirmed_badge`
- `movement_strength_label`
- `provider_refresh_trigger_shadow`

## Blocked Uses

- `official_odds_source`
- `model_input`
- `staking_input`
- `automatic_bet_trigger`
