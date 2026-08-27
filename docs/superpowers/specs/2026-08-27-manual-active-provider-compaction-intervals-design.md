# Manual Active-Provider Compaction Intervals Design

**Status:** Tyler approved the manual-interval direction on 2026-08-27. This
design replaces the proposed paid Render cron with operator-run, one-date-at-a-
time execution. It does not approve a database write or deletion by itself.

## Decision

Do not create `bbe-market-compaction-finalizer` or another scheduled Render
service. Reuse the existing exact active-provider finalizer as a manual tool by
adding an explicit `--slate-date YYYY-MM-DD` option.

The manual tool remains preview-first, uses the fixed provider order
`propline`, then `therundown`, and accepts exactly one slate date per invocation.
It never accepts a provider override or date range.

## Date Boundary

- Omitting `--slate-date` preserves the existing Phoenix D-1 behavior.
- An explicit slate date must be canonical ISO `YYYY-MM-DD`.
- An explicit slate date must be within the clean evaluation regime beginning
  `2026-04-28` and must be no later than Phoenix D-1 at invocation time.
- Same-day, future, pre-regime, malformed, and range inputs fail before any
  Supabase request.

## Write Boundary

Preview remains the default and performs no write.

The existing D-1 execute gate remains valid only when no explicit date is
provided:

`ALLOW_DAILY_ACTIVE_PROVIDER_COMPACTION_WRITE=D1_ACTIVE_PROVIDERS_COMPACT_ONLY`

An explicit historical date requires its own exact manual gate in addition to
`--execute`:

`ALLOW_MANUAL_ACTIVE_PROVIDER_COMPACTION_WRITE=EXACT_DATE_ACTIVE_PROVIDERS_COMPACT_ONLY`

The daily gate must not authorize an explicit historical date, and the manual
gate must not authorize an implicit D-1 run. Execute mode retains the existing
source-fingerprint revalidation, deadline, compact-only upsert, one-attempt
write, post-write exactness proof, redaction, and fixed-provider constraints.

## Manual Cadence

Run the storage/coverage audit approximately every seven days and once at the
end of the season. Review sooner if database utilization reaches 70 percent.
Use the active-provider preview manifest to choose incomplete dates, then run
one date at a time. Do not loop automatically through every date.

Any raw `market_snapshots` deletion remains a later, separately reviewed step.
Before a deletion tranche, require exact compact coverage for every target
partition, a current completed backup and recovery proof, a deletion dry run,
and an explicit approval for the exact dates. Webhook retention remains a
separate gate and must not be bundled with market-snapshot cleanup.

## Non-Goals

- no Render service, cron, worker, or schedule;
- no automatic date-range execution;
- no provider override;
- no raw-row deletion, webhook deletion, vacuum, or retention activation;
- no schema, provider, model, notification, lock, UI, artifact, or source-of-
  truth change;
- no new dependency or secret.

## Acceptance Criteria

- explicit historical previews use the requested valid date for both fixed
  providers and perform zero writes;
- invalid or unsafe dates fail before any provider read;
- explicit-date execution requires the exact manual write gate;
- the legacy D-1 execute path still requires only its existing exact gate;
- safe output identifies whether the target came from Phoenix D-1 or an
  explicit manual date;
- all existing finalizer safety tests and the complete repository suite pass;
- no live preview, database mutation, deployment, or deletion occurs during
  implementation.
