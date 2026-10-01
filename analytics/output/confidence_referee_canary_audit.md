# Confidence Referee Canary Audit

This is feature-flag audit evidence for `confidence_referee` metadata in the Gate C pitcher outcome dataset. The legacy picks_history-only read is retired because it does not carry current referee metadata.

Shadow-only: this report does not change live picks, locks, thresholds, staking, provider order, notifications, calibration, or dashboard source-of-truth.

## Summary

- Total rows: `5488`
- Rows with referee metadata: `3942`
- Applied caps: `643`

## Mode Counts

- `enforce`: `3848`
- `shadow`: `94`

## Relationship Counts

- `model_agrees_with_favorite`: `1909`
- `model_fades_favorite`: `1909`
- `unknown`: `124`

## Applied Cap Transitions

- `FIRE 1u -> LEAN`: `283`
- `FIRE 2u -> FIRE 1u`: `1`
- `FIRE 2u -> LEAN`: `358`
- `PASS -> PASS`: `1`
