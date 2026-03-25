# Line Movement Confidence Design

## Overview

Add a market-signal layer to the EV model: when the sportsbook line moves significantly **against** the model's recommended side (e.g. the over gets cheaper, implying sharp money is on the under), the displayed EV is penalised proportionally. The raw model EV is preserved for transparency. The penalty is applied in the pipeline and reflected on the dashboard card.

---

## Background

The current model computes EV purely from Poisson probability vs. current odds. It does not consider *why* a line is at its current price. A line that moved from -145 to -125 on the over (↓20 pts) may reflect sharp money on the under — a counter-signal the model ignores today.

---

## Goals

- Surface the market's disagreement with the model as a confidence haircut on EV.
- Preserve the raw model EV so the bettor can compare model opinion vs. adjusted recommendation.
- Keep all scoring logic in `build_features.py` (pure functions, unit-testable).
- Minimal dashboard changes — replace the unused "Book" column with a "Raw EV" column.

---

## Non-Goals

- Boosting EV when movement is *in our favour* (no reward, only penalty).
- Changing `calc_lambda` or the Poisson model.
- Incorporating line movement into `fetch_odds.py` — `price_delta_over/under` is already computed there and passed through.

---

## Design

### 1. New function: `calc_movement_confidence`

Added to `build_features.py`.

```python
def calc_movement_confidence(delta: int,
                              noise_floor: int = 10,
                              full_fade:   int = 30) -> float:
    """
    Returns a confidence multiplier (0.0–1.0) based on line movement
    against the recommended side.

    delta       : price_delta of the side being evaluated.
                  Positive = that side got cheaper (sharp money on the other side).
                  Negative or zero = movement in our favour → no penalty.
    noise_floor : movements ≤ this value are ignored (routine book adjustment).
    full_fade   : movements ≥ this value collapse EV to 0 (strong steam signal).

    Linear decay between noise_floor and full_fade.

    Examples (defaults):
      delta =  0  → 1.00  (no movement)
      delta =  5  → 1.00  (below noise floor)
      delta = 10  → 1.00  (at noise floor)
      delta = 15  → 0.75
      delta = 20  → 0.50
      delta = 25  → 0.25
      delta = 30  → 0.00  (full fade)
      delta = 40  → 0.00  (clamped)
      delta = -15 → 1.00  (movement in our favour, no bonus)
    """
    if delta <= noise_floor:
        return 1.0
    if delta >= full_fade:
        return 0.0
    return 1.0 - (delta - noise_floor) / (full_fade - noise_floor)
```

### 2. Integration in `build_pitcher_record`

After computing `ev_over` and `ev_under`, apply the confidence multiplier:

```python
price_delta_over  = calc_price_delta(best_over_odds,  odds["opening_over_odds"])
price_delta_under = calc_price_delta(best_under_odds, odds["opening_under_odds"])

conf_over  = calc_movement_confidence(price_delta_over)
conf_under = calc_movement_confidence(price_delta_under)

adj_ev_over  = ev_over  * conf_over
adj_ev_under = ev_under * conf_under
```

Verdicts are based on `adj_ev_*`. Raw `ev_*` is preserved in the output record.

### 3. Updated JSON schema

`ev_over` and `ev_under` objects gain two new fields:

```json
"ev_over": {
  "ev":            0.0842,
  "adj_ev":        0.0421,
  "verdict":       "LEAN",
  "win_prob":      0.612,
  "movement_conf": 0.50
},
"ev_under": {
  "ev":           -0.0210,
  "adj_ev":       -0.0210,
  "verdict":       "PASS",
  "win_prob":      0.388,
  "movement_conf": 1.00
}
```

`movement_conf: 1.0` means no penalty was applied. `movement_conf < 1.0` means steam was detected.

---

## Dashboard Changes

### `bestSide()` helper — use `adj_ev`

```javascript
function bestSide(p) {
  if (p.ev_over.adj_ev >= p.ev_under.adj_ev) {
    return { verdict: p.ev_over.verdict, ev: p.ev_over.adj_ev,
             rawEv: p.ev_over.ev, winProb: p.ev_over.win_prob,
             conf: p.ev_over.movement_conf,
             direction: 'OVER',  odds: p.best_over_odds };
  } else {
    return { verdict: p.ev_under.verdict, ev: p.ev_under.adj_ev,
             rawEv: p.ev_under.ev, winProb: p.ev_under.win_prob,
             conf: p.ev_under.movement_conf,
             direction: 'UNDER', odds: p.best_under_odds };
  }
}
```

### Stats grid — replace "Book" column with "Raw EV"

Four columns: **Line · λ · EV · Raw EV**

- **EV column**: shows `adj_ev` percentage. If `conf < 1.0`, appends a faint `↓steam` label below the value.
- **Raw EV column**: shows `rawEv` percentage (model opinion before market adjustment).

The "Book" column (`best_over_book`) is removed entirely.

---

## Files Changed

| File | Change |
|---|---|
| `pipeline/build_features.py` | Add `calc_movement_confidence`; update `build_pitcher_record` to compute `conf_*`, `adj_ev_*`; update `ev_over`/`ev_under` dicts |
| `tests/test_build_features.py` | New `TestCalcMovementConfidence` class (8 tests); update `TestBuildPitcherRecord` fixture to assert `adj_ev` and `movement_conf` |
| `dashboard/index.html` | `bestSide()` uses `adj_ev`; stats grid replaces Book with Raw EV; `↓steam` label when `conf < 1.0` |

No changes to `fetch_odds.py`, `fetch_stats.py`, `run_pipeline.py`, or `index.json`.

---

## Test Cases for `calc_movement_confidence`

| delta | expected |
|-------|----------|
| -15   | 1.00     |
|  0    | 1.00     |
|  5    | 1.00     |
|  10   | 1.00     |
|  15   | 0.75     |
|  20   | 0.50     |
|  25   | 0.25     |
|  30   | 0.00     |
|  40   | 0.00     |

---

## Thresholds (defaults, tunable)

| Movement | Confidence | Effect on a FIRE 2u (ev=0.08) |
|----------|------------|-------------------------------|
| < 10 pts | 1.00 | No change |
| 15 pts   | 0.75 | FIRE 2u → FIRE 1u |
| 20 pts   | 0.50 | FIRE 2u → LEAN |
| 25 pts   | 0.25 | FIRE 2u → PASS |
| 30+ pts  | 0.00 | PASS regardless |

`noise_floor` and `full_fade` are parameters on `calc_movement_confidence` — easy to tune after observing real-world results.
