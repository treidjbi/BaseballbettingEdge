# BBE Render Pipeline Runner

This service replaces GitHub scheduled pipeline execution only after artifact
parity and dashboard API canaries pass.

During the rehearsal stage, Render should publish under shadow artifact keys
with `--shadow-prefix`. That writes rows such as
`render_shadow:2026-05-26:today` and keeps the live Netlify artifact API mirror
on the normal `today`, `dated_slate:YYYY-MM-DD`, `steam`, and related keys.

## Proposed Services

| Service | Command | Schedule |
| --- | --- | --- |
| `bbe-pipeline-preview` | `python scripts/run_render_pipeline_mode.py --mode preview --shadow-prefix --execute` | 12:17 AM Phoenix |
| `bbe-pipeline-grading` | `python scripts/run_render_pipeline_mode.py --mode grading --shadow-prefix --execute` | 3:17 AM Phoenix |
| `bbe-pipeline-full-refresh` | `python scripts/run_render_pipeline_mode.py --mode pipeline --shadow-prefix --execute` | 6:17 AM, then 8:07 AM-6:07 PM Phoenix |
| `bbe-pipeline-lock` | `python scripts/run_render_pipeline_mode.py --mode lock --shadow-prefix --execute` | Triggered by live layer, not cron |

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
when Render-generated Supabase artifact hashes under
`render_shadow:<date>:` match GitHub committed artifacts for `today`, dated
archive, `steam`, `performance`, `params`, `preview_lines`, and
`picks_history` where those files are expected for the run type.

Use the parity checker with the same prefix:

```powershell
python scripts/compare_supabase_artifacts.py --date YYYY-MM-DD --remote-key-prefix "render_shadow:YYYY-MM-DD:" --strict
```

## Rollback

Disable Render schedules and set dashboard artifact source back to static.
Manual GitHub `workflow_dispatch` remains available.
