# TheRundown + PropLine Official Provider Parity - 2026-06-19

Generated: `2026-06-19T19:54:39.819711+00:00`

## Input Availability

- Provider Supabase evidence: **available**

## Summary

- Production pitchers: 29
- Provider pitchers: 22
- Covered pitchers: 22 (75.9%)
- FD/DK coverage: 75.9%
- Line conflict rate: 0.0%
- Missing DraftKings: 0
- Ref-book changes: 0
- Verdict changes: 0
- Verdict comparison available: False

## Schedule-First Coverage

- Scheduled probable starters: 28
- Provider covered starters: 20 (71.4%)
- Provider FD/DK starters: 20 (71.4%)
- Provider DraftKings starters: 20 (71.4%)
- Provider FanDuel starters: 20 (71.4%)
- Provider 2+ supported books: 20
- Provider 3+ supported books: 20
- No provider book coverage: 8
- Missing provider starters: 8
- Missing TheRundown starters: 3

- Raw provider coverage: 25 (89.3%)
- Mainline-ready coverage: 25 (89.3%)
- Official-ready coverage: 20 (71.4%)

## Readiness Gates

- official_provider_pitcher_coverage_90: **fail** (value=0.7586, threshold=>=0.90, 22/29)
- official_provider_fd_or_dk_coverage_85: **fail** (value=0.7586, threshold=>=0.85, 22/29)
- official_rows_ready_for_pipeline_90: **fail** (value=0.7143, threshold=>=0.90, 20/28)
- line_conflict_rate_under_10: **pass** (value=0.0, threshold=<=0.10, 0/29)
- prop_contract_valid: **pass** (value=0, threshold=0 missing-field rows, )
- propline_usage_under_70_percent_hobby: **pass** (value=0.1418, threshold=<=0.7, 709/5000)
- no_boltodds_active_rows: **pass** (value=0, threshold=0 active BoltOdds current-line/heartbeat rows, )

Overall ready: **False**

## Notes

- This is diagnostic evidence only. It does not change provider order, live artifacts, model math, locks, staking, notifications, or retention.
- Unknown gates should be treated as not ready before an official-provider decision.
