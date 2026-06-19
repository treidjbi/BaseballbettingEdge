# TheRundown + PropLine Official Provider Parity - 2026-06-19

Generated: `2026-06-19T19:29:21.224930+00:00`

## Input Availability

- Provider Supabase evidence: **available**

## Summary

- Production pitchers: 29
- Provider pitchers: 22
- Covered pitchers: 22 (75.9%)
- FD/DK coverage: 75.9%
- Line conflict rate: 0.0%
- Missing DraftKings: 0
- Ref-book changes: 2
- Verdict changes: 0
- Verdict comparison available: False

## Schedule-First Coverage

- Scheduled probable starters: 28
- Provider covered starters: 21 (75.0%)
- Provider FD/DK starters: 21 (75.0%)
- Provider DraftKings starters: 21 (75.0%)
- Provider FanDuel starters: 21 (75.0%)
- Provider 2+ supported books: 21
- Provider 3+ supported books: 20
- No provider book coverage: 7
- Missing provider starters: 7
- Missing TheRundown starters: 2

- Raw provider coverage: 26 (92.9%)
- Mainline-ready coverage: 26 (92.9%)
- Official-ready coverage: 21 (75.0%)

## Readiness Gates

- official_provider_pitcher_coverage_90: **fail** (value=0.7586, threshold=>=0.90, 22/29)
- official_provider_fd_or_dk_coverage_85: **fail** (value=0.7586, threshold=>=0.85, 22/29)
- official_rows_ready_for_pipeline_90: **fail** (value=0.75, threshold=>=0.90, 21/28)
- line_conflict_rate_under_10: **pass** (value=0.0, threshold=<=0.10, 0/29)
- prop_contract_valid: **pass** (value=0, threshold=0 missing-field rows, )
- propline_usage_under_70_percent_hobby: **pass** (value=0.1258, threshold=<=0.7, 629/5000)
- no_boltodds_active_rows: **pass** (value=0, threshold=0 active BoltOdds current-line/heartbeat rows, )

Overall ready: **False**

## Notes

- This is diagnostic evidence only. It does not change provider order, live artifacts, model math, locks, staking, notifications, or retention.
- Unknown gates should be treated as not ready before an official-provider decision.
