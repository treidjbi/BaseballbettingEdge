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

## Active Shadow Rehearsal Services

Created 2026-05-26 on `main` commit `4c6d0edc`, then redeployed on guarded
commit `228d67fd` after the May 26 stale-artifact repair showed GitHub
scheduler timing as the weak point:

| Service | Render ID | Schedule | Status |
| --- | --- | --- | --- |
| `bbe-pipeline-preview-shadow` | `crn-d8as4l1akrks738ngep0` | `17 7 * * *` | shadow-only active |
| `bbe-pipeline-grading-shadow` | `crn-d8as4pdckfvc73dgpme0` | `17 10 * * *` | shadow-only active |
| `bbe-pipeline-full-shadow` | `crn-d8as4r8g4nts73b5f510` | `17 13 * * *` | shadow-only active |
| `bbe-pipeline-refresh-shadow-day` | `crn-d8asbonavr4c73drnrhg` | `7,37 15-23 * * *` | shadow-only active |
| `bbe-pipeline-refresh-shadow-evening` | `crn-d8asbrel51nc73ahmh60` | `7,37 0 * * *` | shadow-only active |
| `bbe-pipeline-refresh-shadow-final` | `crn-d8asbv0jo6nc7381gma0` | `7 1 * * *` | shadow-only active |

These services do not replace GitHub schedules. They publish to
`render_shadow:<publish-date>:` keys only, so the normal Netlify artifact API
mirror stays on GitHub/static-compatible keys until promotion is explicit.
The wrapper also forces `ENABLE_SUPABASE_LOCK_CONSUMER=false`,
`SUPABASE_LOCK_CONSUMER_STRICT=false`, `OFFICIAL_MARKET_SOURCE=therundown`, and
`ENABLE_BOLTODDS_PIPELINE_SOURCE=false` during shadow-prefixed runs. That keeps
shadow scheduler rehearsal from consuming official lock rows or testing the
provider cutover path by accident.

May 29 correction: these active scheduler-shadow services are back on the
TheRundown-equivalent wrapper command without `--provider-rehearsal`. The
provider-rehearsal flag is useful for a separate BoltOdds/PropLine source
trial, but it intentionally fails strict when `official_market_lines` coverage
is incomplete and therefore is not clean Task 11 scheduler proof.

Latest proof run: Render job `job-d8ascuj7uimc73ckb640` succeeded for
`2026-05-26` full mode on commit `228d67fd`, writing 8 prefixed artifacts
through publication run
`manual-render-pipeline-2026-05-26-20260526T161330Z`. The normal live artifact
keys still passed strict parity 8/8 afterward.

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
