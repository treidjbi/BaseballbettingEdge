# TheRundown + PropLine Official Provider Parity - 2026-06-19

Generated: `2026-06-19T18:31:28.350087+00:00`

## Input Availability

- Provider Supabase evidence: **available**

## Summary

- Production pitchers: 29
- Provider pitchers: 27
- Covered pitchers: 27 (93.1%)
- FD/DK coverage: 93.1%
- Line conflict rate: 17.2%
- Missing DraftKings: 0
- Ref-book changes: 0
- Verdict changes: 0
- Verdict comparison available: False

## Schedule-First Coverage

- Scheduled probable starters: 28
- Provider covered starters: 27 (96.4%)
- Provider FD/DK starters: 27 (96.4%)
- Provider DraftKings starters: 27 (96.4%)
- Provider FanDuel starters: 27 (96.4%)
- Provider 2+ supported books: 27
- Provider 3+ supported books: 26
- No provider book coverage: 1
- Missing provider starters: 1
- Missing TheRundown starters: 1

- Raw provider coverage: 27 (96.4%)
- Mainline-ready coverage: 27 (96.4%)
- Official-ready coverage: 27 (96.4%)

## Readiness Gates

- official_provider_pitcher_coverage_90: **pass** (value=0.931, threshold=>=0.90, 27/29)
- official_provider_fd_or_dk_coverage_85: **pass** (value=0.931, threshold=>=0.85, 27/29)
- official_rows_ready_for_pipeline_90: **pass** (value=0.9643, threshold=>=0.90, 27/28)
- line_conflict_rate_under_10: **fail** (value=0.1724, threshold=<=0.10, 5/29)
- prop_contract_valid: **fail** (value=27, threshold=0 missing-field rows, )
- propline_usage_under_70_percent_hobby: **pass** (value=0.1002, threshold=<=0.7, 501/5000)
- no_boltodds_active_rows: **pass** (value=0, threshold=0 active BoltOdds current-line/heartbeat rows, )

Overall ready: **False**

## Notes

- This is diagnostic evidence only. It does not change provider order, live artifacts, model math, locks, staking, notifications, or retention.
- Unknown gates should be treated as not ready before an official-provider decision.
