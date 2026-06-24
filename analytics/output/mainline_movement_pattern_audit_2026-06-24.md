# Mainline Movement Pattern Audit - 2026-06-24

Read-only diagnostic. This report evaluates movement-notification patterns; it does not change production behavior.

- Access status: `complete`
- Window: `2026-06-18` through `2026-06-24`
- Movement events: 2000 alerts=28 sent=27
- Sources: `{"mainline_polling": 28, "propline_webhook": 1972}`
- Line classes: `{"line_move_different_line": 44, "line_move_touches_pick_line": 362, "line_move_unknown_pick_line": 391, "same_line_price_move": 1203}`
- Supported-book rows: 1079 unsupported=921
- Webhook/polling timing: `{"matched_movements": 3, "median_webhook_lead_seconds": 399.603266, "polling_first": 0, "ties": 0, "webhook_first": 3}`
- Recommendation: `review_supported_same_line_and_touching_pick_line_alert_patterns`

## Candidate Alert Patterns

- mainline_polling / betrivers / odds / toward_pick / worse_now / same_line_price_move / line_moved_against_us: count=6 alerts=6 sent=6
- mainline_polling / draftkings / odds / toward_pick / worse_now / same_line_price_move / line_moved_against_us: count=5 alerts=5 sent=5
- mainline_polling / draftkings / odds / away_from_pick / better_now / same_line_price_move / line_moved_with_us: count=4 alerts=4 sent=4
- mainline_polling / fanduel / odds / toward_pick / worse_now / same_line_price_move / line_moved_against_us: count=4 alerts=4 sent=4
- mainline_polling / betrivers / odds / away_from_pick / better_now / same_line_price_move / line_moved_with_us: count=3 alerts=3 sent=3
- mainline_polling / betrivers / line_and_odds / away_from_pick / better_now / line_move_touches_pick_line / line_moved_with_us: count=2 alerts=2 sent=2
- mainline_polling / draftkings / line_and_odds / toward_pick / worse_now / line_move_touches_pick_line / line_moved_against_us: count=2 alerts=2 sent=1
- mainline_polling / betrivers / line_and_odds / toward_pick / worse_now / line_move_touches_pick_line / line_moved_against_us: count=1 alerts=1 sent=1
- mainline_polling / draftkings / line_and_odds / away_from_pick / better_now / line_move_touches_pick_line / line_moved_with_us: count=1 alerts=1 sent=1

## Top Patterns

- propline_webhook / novig / odds / unknown / unknown / same_line_price_move / line_movement: count=566 alerts=0 sent=0
- propline_webhook / betmgm / odds / unknown / unknown / same_line_price_move / line_movement: count=292 alerts=0 sent=0
- propline_webhook / draftkings / odds / unknown / unknown / same_line_price_move / line_movement: count=149 alerts=0 sent=0
- propline_webhook / betmgm / line_and_odds / unknown / unknown / line_move_unknown_pick_line / line_movement: count=116 alerts=0 sent=0
- propline_webhook / draftkings / line_and_odds / unknown / unknown / line_move_touches_pick_line / line_movement: count=114 alerts=0 sent=0
- propline_webhook / draftkings / line_and_odds / unknown / unknown / line_move_unknown_pick_line / line_movement: count=108 alerts=0 sent=0
- propline_webhook / betmgm / line_and_odds / unknown / unknown / line_move_touches_pick_line / line_movement: count=93 alerts=0 sent=0
- propline_webhook / underdog / odds / unknown / unknown / same_line_price_move / line_movement: count=52 alerts=0 sent=0
- propline_webhook / prizepicks / line / unknown / unknown / line_move_unknown_pick_line / line_movement: count=43 alerts=0 sent=0
- propline_webhook / betmgm / line_and_odds / unknown / unknown / line_move_different_line / line_movement: count=42 alerts=0 sent=0
- propline_webhook / betrivers / line_and_odds / unknown / unknown / line_move_touches_pick_line / line_movement: count=41 alerts=0 sent=0
- propline_webhook / pinnacle / odds / unknown / unknown / same_line_price_move / line_movement: count=36 alerts=0 sent=0
- propline_webhook / underdog / line_and_odds / unknown / unknown / line_move_touches_pick_line / line_movement: count=35 alerts=0 sent=0
- propline_webhook / betrivers / odds / unknown / unknown / same_line_price_move / line_movement: count=32 alerts=0 sent=0
- propline_webhook / betrivers / line_and_odds / unknown / unknown / line_move_unknown_pick_line / line_movement: count=31 alerts=0 sent=0

## Blocked Uses

- `official_odds_source`
- `model_input`
- `staking_input`
- `automatic_bet_trigger`
