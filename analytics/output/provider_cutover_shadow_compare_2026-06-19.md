# TheRundown + PropLine Official Provider Parity - 2026-06-19

Generated: `2026-06-19T17:42:17.221911+00:00`

## Input Availability

- Provider Supabase evidence: **unavailable/partial**
- Provider coverage counts and failed coverage gates are not proof that TheRundown + PropLine provider evidence failed.
- supabase: **unavailable** - provider Supabase writer unavailable: OSError: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required

## Summary

- Production pitchers: 29
- Provider pitchers: 0
- Covered pitchers: 0 (0.0%)
- FD/DK coverage: 0.0%
- Line conflict rate: 0.0%
- Missing DraftKings: 0
- Ref-book changes: 0
- Verdict changes: 0
- Verdict comparison available: False

## Schedule-First Coverage

- Scheduled probable starters: 28
- Provider covered starters: 0 (0.0%)
- Provider FD/DK starters: 0 (0.0%)
- Provider DraftKings starters: 0 (0.0%)
- Provider FanDuel starters: 0 (0.0%)
- Provider 2+ supported books: 0
- Provider 3+ supported books: 0
- No provider book coverage: 28
- Missing provider starters: 28
- Missing TheRundown starters: 1

## Readiness Gates

- official_provider_pitcher_coverage_90: **unknown** (value=0.0, threshold=>=0.90, 0/29)
- official_provider_fd_or_dk_coverage_85: **unknown** (value=0.0, threshold=>=0.85, 0/29)
- official_rows_ready_for_pipeline_90: **unknown** (value=0.0, threshold=>=0.90, 0/28)
- line_conflict_rate_under_10: **unknown** (value=0.0, threshold=<=0.10, 0/29)
- prop_contract_valid: **unknown** (value=0, threshold=0 missing-field rows, )
- propline_usage_under_70_percent_hobby: **unknown** (value=None, threshold=<=0.7, unknown/5000)
- no_boltodds_active_rows: **unknown** (value=0, threshold=0 active BoltOdds current-line/heartbeat rows, )

Overall ready: **False**

## Notes

- This is diagnostic evidence only. It does not change provider order, live artifacts, model math, locks, staking, notifications, or retention.
- Unknown gates should be treated as not ready before an official-provider decision.
