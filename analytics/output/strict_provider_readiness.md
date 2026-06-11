# Strict Provider Readiness

Generated at: `2026-06-11T15:54:03Z`

Read-only: this report summarizes whether the current BoltOdds + PropLine provider-source canary is ready for a separate strict-mode discussion. It does not set `OFFICIAL_MARKET_STRICT=true`, change provider order, change model behavior, change notifications, change locks, or change dashboard source-of-truth.

## Executive Read

- Readiness status: `watch`
- Blocking reasons: none
- Watch reasons:
  - provider runs include failures

## Artifact Path

- `today`: generated `2026-06-11T15:38:25Z`, published `2026-06-11T15:52:38Z`
- Today pitcher rows: `15`
- Today tracked picks: `13`
- Today market source mode: `boltodds_propline`
- Today line source providers: `boltodds=15`
- `dated_slate:2026-06-10`: `28` pitcher rows, `boltodds=26`, `propline=2`

## Official Lines

| Slate | Rows | Ready | BoltOdds | PropLine | Cross-book conflicts |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2026-06-10` | 28 | 26 | 26 | 0 | 1 |
| `2026-06-11` | 15 | 15 | 15 | 0 | 3 |

## Provider Evidence

- BoltOdds heartbeat fresh at `2026-06-11T15:53:17Z`; books seen: FanDuel, BetMGM, BetRivers, Caesars; message count `2019`.
- BoltOdds line evidence context is fresh: `15` ready official BoltOdds rows, `67` complete current-line rows, latest current-line update `2026-06-11T15:40:54Z`.
- Latest BoltOdds coverage audit for `2026-06-11`: `1` parsed prop and `1` complete pitcher-line group. The zero-audit warning is now contextualized in the SQL report so it no longer reads as a dead feed when heartbeat/current/official line evidence is fresh.
- Latest PropLine coverage audit for `2026-06-11`: `0` target events, `0` parsed props, and missing DraftKings/FanDuel/BetRivers/Kalshi. PropLine needs the zero-event diagnostic instrumentation deployed before it can be trusted as DraftKings/fallback support.
- Provider runs still include recent BoltOdds websocket close-frame failures.
- Request usage is controlled: `2026-06-11` had BoltOdds `2` requests / `1522` snapshots and PropLine `16` requests / `0` snapshots by the check.

## Locks, Notifications, And Webhooks

- `2026-06-10` lock ledger: `20` rows, `20` consumed, `0` due unconsumed, `0` duplicate rows.
- Notification events for `2026-06-10` and `2026-06-11`: `0` failed sends in the readiness query.
- PropLine webhooks over the last 7 days: `5529` signed, `5529` processed, `0` unprocessed, `1817` processing-error rows from unsupported alt strikeout ladder payloads.

## Read Rule

Strict provider mode remains a separate decision, not a same-step flip. BoltOdds current evidence is healthier than the older zero-audit wording implied, but provider-run failures still need observation and PropLine current-day zero-event polling needs diagnostic proof before strict mode can rely on it.
