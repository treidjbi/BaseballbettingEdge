Status: DONE_WITH_CONCERNS

Files changed:
- analytics/diagnostics/provider_cutover_shadow_compare.py
- tests/test_provider_cutover_shadow_compare.py
- analytics/output/provider_cutover_shadow_compare_2026-06-19.md
- analytics/output/provider_cutover_shadow_compare_2026-06-19.json
- .superpowers/sdd/task-4-report.md

Tests/commands run with exact results:
- `git pull --ff-only` -> failed: local branch `codex/therundown-propline-official` has no tracking information.
- `git fetch origin` -> exit 0.
- RED: `python -m pytest tests/test_provider_cutover_shadow_compare.py -q` -> 9 failed, 4 passed in 0.58s.
- GREEN: `python -m pytest tests/test_provider_cutover_shadow_compare.py -q` -> 13 passed in 0.41s.
- Read-only report: `python analytics/diagnostics/provider_cutover_shadow_compare.py --date 2026-06-19 --provider-min-props 1` -> exit 0; warning: `provider Supabase writer unavailable: OSError: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required`; wrote `analytics/output/provider_cutover_shadow_compare_2026-06-19.json` and `.md`.

Commit SHA(s):
- Pending until commit; final SHA reported in task reply.

Self-review notes and concerns:
- Report labels now name TheRundown + PropLine official provider parity instead of BoltOdds cutover.
- Readiness gates now use the Task 4 gate names: `official_provider_pitcher_coverage_90`, `official_provider_fd_or_dk_coverage_85`, `official_rows_ready_for_pipeline_90`, `line_conflict_rate_under_10`, `prop_contract_valid`, `propline_usage_under_70_percent_hobby`, and `no_boltodds_active_rows`.
- Added active BoltOdds current-line/heartbeat counting only for diagnostics; no runtime provider flags, model math, locks, staking, notifications, retention, dashboard source-of-truth, Render env, or production behavior changed.
- Same-day report is incomplete because local Supabase service-role env is unavailable. It fetched TheRundown and schedule data, but provider coverage and PropLine usage gates are unknown/failing due to missing read access, not proven production provider absence.
