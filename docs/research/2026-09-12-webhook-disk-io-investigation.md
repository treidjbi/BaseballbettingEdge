# September 12 webhook Disk IO investigation

Scope: read-only investigation of authenticated Supabase warning emails on
September 5 and 12 for project `htoaytcsjrdyyzcwxjfg`. No runtime repair,
deployment, database mutation, retention or compute upgrade was performed.

## Confirmed finding

`scripts/process_propline_webhooks.py:261` uses `processed=eq.false`.
The same filter remains in freshly fetched `origin/main`. The writer passes
the filter directly to PostgREST. The live layer invokes this reader with a
default 180-minute lookback and 100-row limit.

The deployed partial index is valid and ready, but its predicate is
`processed IS FALSE`. On September 12, EXPLAIN for `processed=false` with
a 24-hour cutoff planned a parallel sequential scan and sort; `IS FALSE`
with the same cutoff planned the existing index. This supersedes the August
14 claim that index validation proved the actual application query shape.

## Recent production evidence

Query ID `2522072932639700476` is the PostgREST webhook-inbox equality read.
Between approximately 12:53Z and 13:21:43Z:

| Counter | Earlier | Later | Delta |
| --- | ---: | ---: | ---: |
| Calls | 9415 | 9418 | 3 |
| Shared blocks read | 263781348 | 264009459 | 228111 |
| Total execution milliseconds | 45056166 (rounded) | 45077761.9548161 | approximately 21596 |

At 8 KiB per block, the delta is approximately 1.74 GiB read into PostgreSQL
buffers, or 594 MiB per call. These counters are not a measurement of physical
storage-device IO: operating-system cache may satisfy some reads. The three
calls were naturally occurring; this investigation did not execute the heavy
equality query. EXPLAIN without ANALYZE was used for that query.

A read-only `EXPLAIN (ANALYZE, BUFFERS)` for the index-compatible predicate
with the default three-hour cutoff returned zero rows, used the partial index,
read three blocks, and completed in 4.909 ms (planning 8.584 ms). This is a
bounded empty-inbox check, not a matched workload benchmark or deployed proof.

The partial index had only four recorded scans at the later checkpoint,
including diagnostic reads. Query statistics reset on July 7; cumulative
rankings alone cannot attribute September's alert. The recent delta does
establish ongoing avoidable read pressure.

## Health and limits

Supabase reported ACTIVE_HEALTHY. At 12:53Z the database measured 6064 MiB;
market_snapshots accounted for 3975 MiB and webhook deliveries 733 MiB.
History published at 10:18Z. The then-current today artifact was September 11,
before the scheduled September 12 full run. This was not an end-to-end health
check. Exact remaining IO burst budget, hourly physical IO and compute metrics
were unavailable because the browser dashboard required sign-in.

## Proposed repair and verification

Change only the reader's `eq.false` to `is.false`, preserving lookback, limit,
ordering, processing and notification behavior. Both WHERE predicates select
false rows and exclude NULL. PostgREST documents `eq` as `=` and `is` as `IS`:
https://docs.postgrest.org/en/stable/references/api/tables_views.html#operators

Before release, add a regression covering the outgoing filter, run existing
webhook processor/live-layer tests, and verify the application query uses the
existing index. After an approved deployment, observe natural cycles, query
counter deltas, inbox processing and hourly IO. No new index, raw-row deletion,
vacuum, capture shutdown or paid upgrade is required by this proposed repair.
This investigation does not authorize production deployment.
