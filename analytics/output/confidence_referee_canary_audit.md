# Confidence Referee Canary Audit

This is feature-flag audit evidence for `confidence_referee` metadata in the Gate C pitcher outcome dataset. The legacy picks_history-only read is retired because it does not carry current referee metadata.

Shadow-only: this report does not change live picks, locks, thresholds, staking, provider order, notifications, calibration, or dashboard source-of-truth.

## Summary

- Total rows: `1662`
- Rows with referee metadata: `164`
- Applied caps: `14`

## Mode Counts

- `enforce`: `70`
- `shadow`: `94`

## Relationship Counts

- `model_agrees_with_favorite`: `77`
- `model_fades_favorite`: `79`
- `unknown`: `8`

## Applied Cap Transitions

- `FIRE 1u -> LEAN`: `6`
- `FIRE 2u -> FIRE 1u`: `1`
- `FIRE 2u -> LEAN`: `7`
