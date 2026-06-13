# Pitcher K Outcome Dataset Summary

Shadow-only: this dataset does not change live picks, locks, thresholds, staking, provider order, notifications, or calibration.

- Total rows: `1840`
- Clean-window rows: `1840`
- Graded rows: `1840`
- Rows missing result: `0`
- Duplicate dataset keys: `0`
- Missing team/opponent: `0`
- Missing book odds: `0`
- Missing model fields: `2`
- Tracked pick rows: `956`
- Rows with price CLV: `956`
- Beat-close price rows: `153`
- Beat-close line rows: `18`
- Rows with lineup hand counts: `1174`
- Rows with actual IP: `1718`
- Rows with actual pitch count: `1718`
- Rows with batters faced: `1718`
- Rows with market agreement labels: `195`
- Rows with market book counts: `281`
- Rows with toward/away counts: `195`
- Rows with live display book-board fields: `223`
- Broad market confirmation rows: `42`
- Best off-market rows: `75`
- Large-edge skepticism rows: `419`
- Clean graded picks reconciled: `957/957`
- Unique side fallback reconciliations: `30`
- Unmatched clean graded picks: `0`

## Context Snapshots

- `official_close`: `1840`

## Model Vs Market Relationship

- `model_agrees_with_favorite`: `838`
- `model_fades_favorite`: `936`
- `unknown`: `66`

## CLV Types

- `line_only`: `18`
- `no_clv_edge`: `785`
- `not_tracked`: `884`
- `price_only`: `153`

## Process Outcome Buckets

- `good_process_loss`: `75`
- `good_process_win`: `96`
- `unknown`: `884`
- `weak_process_loss`: `404`
- `weak_process_win`: `381`

## Bet Timing Windows

- `post_start`: `46`
- `pre_120`: `5`
- `pre_15`: `165`
- `pre_30`: `654`
- `pre_5`: `49`
- `unknown`: `921`

## Opportunity Buckets

- `deep_starter`: `210`
- `normal`: `1486`
- `short_leash`: `144`

## Leash Risk Buckets

- `high`: `144`
- `medium`: `66`
- `normal`: `1630`

## Pitcher Archetype Buckets

- `deep_starter`: `134`
- `high_k_deep_starter`: `76`
- `high_k_standard`: `440`
- `low_k_standard`: `108`
- `short_leash`: `144`
- `standard_starter`: `938`

## Lineup Handedness Sources

- `missing`: `666`
- `mlb_boxscore_reconstructed`: `1174`

## Actual Opportunity Sources

- `missing`: `122`
- `mlb_boxscore_reconstructed`: `1718`

## Market Agreement Labels

- `market_against_model`: `32`
- `market_mixed`: `62`
- `market_no_signal`: `63`
- `market_with_model`: `38`
- `missing`: `1645`

## Movement Strength Labels

- `broad_against_model`: `7`
- `broad_with_model`: `6`
- `missing`: `1645`
- `mixed_or_reversed`: `108`
- `no_movement_signal`: `63`
- `single_book_against_model`: `6`
- `single_book_with_model`: `5`

## Live Display States

- `market_fade`: `16`
- `missing`: `1617`
- `mixed`: `17`
- `monitor`: `66`
- `off_market`: `30`
- `playable_now`: `22`
- `stale`: `72`