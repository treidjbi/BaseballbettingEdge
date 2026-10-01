# Seasonal K Environment Audit

This is a shadow read. Do not apply month constants directly to live lambda.

Warning: app picks are selection-biased; validate against MLB-wide starter K/start before any live prior.

## Monthly Actual K Snapshot
- `2026-03`: n=110, avg_actual_ks=5.109
- `2026-04`: n=610, avg_actual_ks=4.7
- `2026-05`: n=651, avg_actual_ks=4.977
- `2026-06`: n=613, avg_actual_ks=4.971
- `2026-07`: n=471, avg_actual_ks=5.081
- `2026-08`: n=538, avg_actual_ks=4.809
- `2026-09`: n=439, avg_actual_ks=4.79

## Side By Regime
- `early_season | over`: rows=305, 144-161, pnl=-27.7
- `early_season | under`: rows=415, 229-186, pnl=20.12
- `late_season | over`: rows=243, 120-123, pnl=-14.47
- `late_season | under`: rows=196, 101-95, pnl=-11.85
- `spring_midseason | over`: rows=447, 228-219, pnl=-11.63
- `spring_midseason | under`: rows=538, 273-265, pnl=-28.55
- `summer_midseason | over`: rows=491, 241-250, pnl=-37.58
- `summer_midseason | under`: rows=797, 397-400, pnl=-62.49

## Decision Rule

- If a month/week environment signal is real, implement it as a shrunk prior or calibration feature, not a hard-coded calendar bump.
- Do not change lambda, verdict thresholds, staking, or formula_change_date from this audit alone.
