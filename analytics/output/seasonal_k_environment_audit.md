# Seasonal K Environment Audit

This is a shadow read. Do not apply month constants directly to live lambda.

Warning: app picks are selection-biased; validate against MLB-wide starter K/start before any live prior.

## Monthly Actual K Snapshot
- `2026-03`: n=110, avg_actual_ks=5.109
- `2026-04`: n=610, avg_actual_ks=4.7
- `2026-05`: n=605, avg_actual_ks=4.988

## Side By Regime
- `early_season | over`: rows=305, 144-161, pnl=-27.7
- `early_season | under`: rows=415, 229-186, pnl=20.12
- `spring_midseason | over`: rows=275, 154-121, pnl=16.82
- `spring_midseason | under`: rows=330, 173-157, pnl=-7.92

## Decision Rule

- If a month/week environment signal is real, implement it as a shrunk prior or calibration feature, not a hard-coded calendar bump.
- Do not change lambda, verdict thresholds, staking, or formula_change_date from this audit alone.
