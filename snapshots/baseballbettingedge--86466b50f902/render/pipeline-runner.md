# BBE Render Pipeline Runner

These services replace GitHub scheduled pipeline execution. GitHub Actions
remains available for manual rollback through `workflow_dispatch`.

Render publishes to the live Supabase artifact keys used by the Netlify
`get-artifact` API. Shadow-key rehearsals remain available by adding
`--shadow-prefix` to a one-off job, but the scheduled services should not use
that flag after the 2026-05-30 cutover.

## Proposed Services

| Service | Command | Schedule |
| --- | --- | --- |
| `bbe-pipeline-preview` | `python scripts/run_render_pipeline_mode.py --mode preview --execute` | 12:17 AM Phoenix |
| `bbe-pipeline-grading` | `python scripts/run_render_pipeline_mode.py --mode grading --execute` | 3:17 AM Phoenix |
| `bbe-pipeline-full` | `python scripts/run_render_pipeline_mode.py --mode pipeline --execute` | 6:17 AM Phoenix |
| `bbe-pipeline-refresh-*` | `python scripts/run_render_pipeline_mode.py --mode pipeline --execute` | 8:07 AM-6:07 PM Phoenix |
| `bbe-pipeline-lock` | `python scripts/run_render_pipeline_mode.py --mode lock --execute` | Every 10 minutes, offset behind live-layer lock writes |

## Active Primary Services

Promoted on 2026-05-30 after GitHub schedule delay caused stale artifact risk
and Render scheduler canaries ran successfully on current commits:

| Service | Render ID | Schedule | Status |
| --- | --- | --- | --- |
| `bbe-pipeline-preview` | `crn-d8as4l1akrks738ngep0` | `17 7 * * *` | primary |
| `bbe-pipeline-grading` | `crn-d8as4pdckfvc73dgpme0` | `17 10 * * *` | primary |
| `bbe-pipeline-full` | `crn-d8as4r8g4nts73b5f510` | `17 13 * * *` | primary |
| `bbe-pipeline-refresh-day` | `crn-d8asbonavr4c73drnrhg` | `7,37 15-23 * * *` | primary |
| `bbe-pipeline-refresh-evening` | `crn-d8asbrel51nc73ahmh60` | `7,37 0 * * *` | primary |
| `bbe-pipeline-refresh-final` | `crn-d8asbv0jo6nc7381gma0` | `7 1 * * *` | primary |
| `bbe-pipeline-lock` | `crn-d8dgp6q8qa3s739n80s0` | `2,12,22,32,42,52 * * * *` | primary |

The primary services publish normal live artifact keys. Render env explicitly
keeps `OFFICIAL_MARKET_SOURCE=therundown` and
`ENABLE_BOLTODDS_PIPELINE_SOURCE=false`; this is a scheduler/artifact cutover,
not a provider cutover.

Lock mode hydrates the local checkout from Netlify `get-artifact` before
running. Render cron instances are stateless, so lock jobs must not republish
the stale JSON bundled in the deployed Git commit after a fresher refresh has
already published to Supabase.

Lock mode also fetches replayable same-slate `operational_pick_locks`,
including rows that already have `consumed_at`, so an artifact that fell behind
the lock ledger can be repaired idempotently. Existing consumed markers are not
overwritten; only newly represented rows receive a fresh marker.

May 29 correction: the scheduler-shadow services were returned to the
TheRundown-equivalent wrapper command without `--provider-rehearsal`. That
corrected the provider/scheduler evidence split before the May 30 promotion.
After promotion, scheduled services publish live keys; use `--shadow-prefix`
only for deliberate future rehearsals.

Cutover proof: on 2026-05-30, the refresh-day service was redeployed to current
commit `643b262f`, normal mode ran successfully, and lock mode published live
artifact keys through
`manual-render-lock-2026-05-30-20260530T162508Z`. The first primary soak should
watch the next scheduled preview/grading/full/refresh/lock windows closely.

## Required Environment

- `RUNDOWN_API_KEY`
- `ODDS_API_KEY`
- `PROPLINE_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ENABLE_SUPABASE_LOCK_CONSUMER=true`
- `SUPABASE_LOCK_CONSUMER_STRICT=false` during the first primary-scheduler soak
- `ENABLE_GITHUB_FALLBACK_LOCKING=false`
- `OFFICIAL_MARKET_SOURCE` unset or `therundown`
- `ENABLE_BOLTODDS_PIPELINE_SOURCE=false`
- `BATTER_SPLIT_COLLECTION_MAX_NEW=0` on starter cron services to avoid
  memory-heavy research backfill during live pipeline windows

## Promotion Gate

During the first primary-scheduler soak, check Render run success,
`pipeline_artifact_publication_runs`, live artifact freshness, dashboard API
response, lock cron consumption, and manual GitHub rollback availability.

## Rollback

Disable Render schedules or restore `--shadow-prefix`, set dashboard artifact
source back to static, and manually run GitHub `workflow_dispatch`. Manual
GitHub dispatch remains available.
