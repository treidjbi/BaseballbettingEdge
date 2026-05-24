# BBE Render Pipeline Runner

This service replaces GitHub scheduled pipeline execution only after artifact
parity and dashboard API canaries pass.

## Proposed Services

| Service | Command | Schedule |
| --- | --- | --- |
| `bbe-pipeline-preview` | `python pipeline/run_pipeline.py $SLATE_DATE --run-type preview && python scripts/publish_pipeline_artifacts_to_supabase.py --date $SLATE_DATE --source render_pipeline --source-run-id $RENDER_RUN_ID --execute` | 12:17 AM Phoenix |
| `bbe-pipeline-grading` | `python pipeline/run_pipeline.py $SLATE_DATE --run-type grading && python scripts/publish_pipeline_artifacts_to_supabase.py --date $SLATE_DATE --source render_pipeline --source-run-id $RENDER_RUN_ID --execute` | 3:17 AM Phoenix |
| `bbe-pipeline-full-refresh` | `python pipeline/run_pipeline.py $SLATE_DATE && python scripts/publish_pipeline_artifacts_to_supabase.py --date $SLATE_DATE --source render_pipeline --source-run-id $RENDER_RUN_ID --execute` | 6:17 AM, then 8:07 AM-6:07 PM Phoenix |
| `bbe-pipeline-lock` | `python pipeline/run_pipeline.py $SLATE_DATE --run-type lock && python scripts/publish_pipeline_artifacts_to_supabase.py --date $SLATE_DATE --source render_pipeline --source-run-id $RENDER_RUN_ID --execute` | Triggered by live layer, not cron |

## Required Environment

- `RUNDOWN_API_KEY`
- `ODDS_API_KEY`
- `PROPLINE_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ENABLE_SUPABASE_LOCK_CONSUMER=true`
- `SUPABASE_LOCK_CONSUMER_STRICT=true`
- `OFFICIAL_MARKET_SOURCE` unset or `therundown`
- `ENABLE_BOLTODDS_PIPELINE_SOURCE=false`

## Promotion Gate

Run Render in shadow for one slate while GitHub remains official. Promote only
when Render-generated Supabase artifact hashes match GitHub committed artifacts
for `today`, dated archive, `steam`, `performance`, `params`,
`preview_lines`, and `picks_history` where those files are expected for the run
type.

## Rollback

Disable Render schedules and set dashboard artifact source back to static.
Manual GitHub `workflow_dispatch` remains available.
