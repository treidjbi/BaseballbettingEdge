# Pitcher K Outcome Dataset Summary

Shadow-only: this dataset does not change live picks, locks, thresholds, staking, provider order, notifications, or calibration.

- Total rows: `2020`
- Clean-window rows: `2020`
- Graded rows: `2020`
- Rows missing result: `0`
- Duplicate dataset keys: `0`
- Missing team/opponent: `0`
- Missing book odds: `0`
- Missing model fields: `2`
- Tracked pick rows: `1050`
- Rows with price CLV: `1050`
- Beat-close price rows: `174`
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
- Large-edge skepticism rows: `460`
- Clean graded picks reconciled: `1051/1051`
- Unique side fallback reconciliations: `31`
- Unmatched clean graded picks: `0`

## Context Snapshots

- `official_close`: `2020`

## Model Vs Market Relationship

- `model_agrees_with_favorite`: `934`
- `model_fades_favorite`: `1014`
- `unknown`: `72`

## CLV Types

- `line_only`: `18`
- `no_clv_edge`: `858`
- `not_tracked`: `970`
- `price_only`: `174`

## Process Outcome Buckets

- `good_process_loss`: `84`
- `good_process_win`: `108`
- `unknown`: `970`
- `weak_process_loss`: `446`
- `weak_process_win`: `412`

## Bet Timing Windows

- `post_start`: `46`
- `pre_120`: `5`
- `pre_15`: `166`
- `pre_30`: `721`
- `pre_5`: `49`
- `unknown`: `1033`

## Opportunity Buckets

- `deep_starter`: `226`
- `normal`: `1634`
- `short_leash`: `160`

## Leash Risk Buckets

- `high`: `160`
- `medium`: `76`
- `normal`: `1784`

## Pitcher Archetype Buckets

- `deep_starter`: `144`
- `high_k_deep_starter`: `82`
- `high_k_standard`: `478`
- `low_k_standard`: `118`
- `short_leash`: `160`
- `standard_starter`: `1038`

## Lineup Handedness Sources

- `missing`: `846`
- `mlb_boxscore_reconstructed`: `1174`

## Actual Opportunity Sources

- `missing`: `302`
- `mlb_boxscore_reconstructed`: `1718`

## Market Agreement Labels

- `market_against_model`: `32`
- `market_mixed`: `62`
- `market_no_signal`: `63`
- `market_with_model`: `38`
- `missing`: `1825`

## Movement Strength Labels

- `broad_against_model`: `7`
- `broad_with_model`: `6`
- `missing`: `1825`
- `mixed_or_reversed`: `108`
- `no_movement_signal`: `63`
- `single_book_against_model`: `6`
- `single_book_with_model`: `5`

## Live Display States

- `market_fade`: `16`
- `missing`: `1797`
- `mixed`: `17`
- `monitor`: `66`
- `off_market`: `30`
- `playable_now`: `22`
- `stale`: `72`