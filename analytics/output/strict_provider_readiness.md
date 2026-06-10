# Strict Provider Readiness

Generated at: `2026-06-10T16:00:58Z`

Read-only: this report summarizes whether the current BoltOdds + PropLine provider-source canary is ready for a separate strict-mode discussion. It does not set `OFFICIAL_MARKET_STRICT=true`, change provider order, change model behavior, change notifications, change locks, or change dashboard source-of-truth.

## Executive Read

- Readiness status: `watch`
- Blocking reasons: none
- Watch reasons:
  - latest BoltOdds coverage audit parsed zero rows
  - latest BoltOdds coverage audit has zero complete groups
  - provider coverage audits include line conflicts
  - provider runs include failures

## Artifact Path

- `today`: generated `2026-06-10T15:37:57Z`, published `2026-06-10T15:52:39Z`
- Today pitcher rows: `27`
- Today tracked picks: `22`
- Today market source mode: `boltodds_propline`
- Today line source providers: `boltodds=25`, `propline=2`
- `dated_slate:2026-06-09`: `29` pitcher rows, all `boltodds`

## Official Lines

| Slate | Rows | Ready | BoltOdds | PropLine | Cross-book conflicts |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2026-06-09` | 29 | 29 | 29 | 0 | 2 |
| `2026-06-10` | 27 | 27 | 26 | 1 | 4 |

## Provider Evidence

- BoltOdds heartbeat fresh at `2026-06-10T15:59:45Z`; books seen: FanDuel, BetMGM, BetRivers, Caesars; message count `3553`.
- Latest BoltOdds coverage audit for `2026-06-10`: `0` parsed props, `0` complete pitcher-line groups, missing FanDuel/BetMGM/BetRivers/Caesars in that audit, while official lines still selected BoltOdds for most rows. This mismatch should be explained before strict mode.
- Latest PropLine coverage audit for `2026-06-10`: `31` parsed props, `67` complete pitcher-line groups, `60` same-line overlaps, `5` line conflicts, missing Kalshi.
- Provider runs still include recent failures: BoltOdds websocket close-frame failures and prior PropLine Supabase timeout failures.
- Request usage is controlled: `2026-06-10` had BoltOdds `4` requests / `2610` snapshots and PropLine `293` requests / `2260` snapshots by the check.

## Locks, Notifications, And Webhooks

- `2026-06-09` lock ledger: `32` rows, `32` consumed, `0` due unconsumed, `0` duplicate rows.
- Notification events for `2026-06-09` and `2026-06-10`: `0` failed sends in the readiness query.
- PropLine webhooks over the last 7 days: `5803` signed, `5803` processed, `0` unprocessed, `1924` processing-error rows from unsupported alt strikeout ladder payloads.

## Read Rule

Strict provider mode is close enough for a focused yes/no review, but not a same-step flip. Clear the BoltOdds coverage-audit mismatch and line-conflict/provider-run-failure watch items first, then make `OFFICIAL_MARKET_STRICT=true` a separate env-var-only decision with rollback.
