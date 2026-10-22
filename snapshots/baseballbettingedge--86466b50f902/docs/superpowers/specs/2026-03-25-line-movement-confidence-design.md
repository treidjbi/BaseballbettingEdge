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
- Moving delta computation — `price_delta_over/under` is computed inside `build_pitcher_record` in `build_features.py` (lines 131–132), not in `fetch_odds.py`. This does not change.

---

## Design

### 1. New function: `calc_movement_confidence`

Added to `build_features.py`.

```python
# Display threshold: show ↓steam label when confidence drops to this level or below
STEAM_DISPLAY_THRESHOLD = 0.75   # corresponds to delta ≥ 15 pts (first meaningful stake reduction)

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

The confidence multiplication must be applied to the **raw Python floats** — before the output dict is constructed (i.e., before the existing `ev_over` / `ev_under` dict literals on the final `return` statement). Applying it to the dict would be a type error.

```python
# --- existing code (unchanged) ---
price_delta_over  = calc_price_delta(best_over_odds,  odds.get("opening_over_odds", best_over_odds))
price_delta_under = calc_price_delta(best_under_odds, odds.get("opening_under_odds", best_under_odds))

# --- new: confidence multiplier (applied to raw floats, before dict construction) ---
conf_over  = calc_movement_confidence(price_delta_over)
conf_under = calc_movement_confidence(price_delta_under)

adj_ev_over  = ev_over  * conf_over
adj_ev_under = ev_under * conf_under

# --- existing dict construction, updated to use adj_ev for verdict ---
return {
    ...
    "price_delta_over":  price_delta_over,
    "price_delta_under": price_delta_under,
    "ev_over":  {
        "ev":            round(ev_over,      4),
        "adj_ev":        round(adj_ev_over,  4),   # NEW
        "verdict":       calc_verdict(adj_ev_over), # changed from ev_over
        "win_prob":      round(win_prob_over,  3),
        "movement_conf": round(conf_over, 4),        # NEW
    },
    "ev_under": {
        "ev":            round(ev_under,      4),
        "adj_ev":        round(adj_ev_under,  4),  # NEW
        "verdict":       calc_verdict(adj_ev_under), # changed from ev_under
        "win_prob":      round(win_prob_under,  3),
        "movement_conf": round(conf_under, 4),       # NEW
    },
}
```

**Opening odds key handling:** `fetch_odds.py` always populates `opening_over_odds` and `opening_under_odds` on every record, so these keys will be present at runtime. The `.get()` fallback in the `calc_price_delta` calls is **purely defensive** — it has no effect in production. The existing direct key access on the output dict lines (e.g. `"opening_over_odds": odds["opening_over_odds"]`) is intentionally left unchanged. Do not convert those lines to `.get()`.

### 3. Updated JSON schema

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

`movement_conf: 1.0` means no penalty was applied. `movement_conf < 1.0` means steam was detected. All new fields are additive — existing JSON consumers that don't read `adj_ev` / `movement_conf` continue to work unchanged.

---

## Dashboard Changes

### `bestSide()` helper — use `adj_ev` for selection

`bestSide()` compares `adj_ev` (not raw `ev`) to select the recommended side. This means a large steam penalty on the over can flip the selection to under — this is the intended behaviour.

The `conf` property returned by `bestSide()` is the confidence of the **selected side** (after possible flip), so the steam label always reflects the side being displayed.

```javascript
function bestSide(p) {
  if (p.ev_over.adj_ev >= p.ev_under.adj_ev) {
    return { verdict:  p.ev_over.verdict,
             ev:       p.ev_over.adj_ev,
             rawEv:    p.ev_over.ev,
             winProb:  p.ev_over.win_prob,
             conf:     p.ev_over.movement_conf,
             direction: 'OVER',
             odds:     p.best_over_odds };
  } else {
    return { verdict:  p.ev_under.verdict,
             ev:       p.ev_under.adj_ev,
             rawEv:    p.ev_under.ev,
             winProb:  p.ev_under.win_prob,
             conf:     p.ev_under.movement_conf,
             direction: 'UNDER',
             odds:     p.best_under_odds };
  }
}
```

### Stats grid — replace "Book" column with "Raw EV"

Four columns: **Line · λ · EV · Raw EV**

- **EV column**: shows `adj_ev` percentage. If `side.conf <= 0.75` (i.e. delta ≥ 15 pts), show a faint `↓steam` sub-label. The 0.75 threshold (constant `STEAM_DISPLAY_THRESHOLD` defined in Python, mirrored as a JS constant) avoids triggering on insignificant moves. Matches the first row of the threshold table where a meaningful stake reduction occurs.
- **Raw EV column**: shows `side.rawEv` percentage (the model's unadjusted opinion before market haircut).
- **Book column** (`best_over_book`): removed from the card display. The field remains in the JSON for potential future use — no change to `build_pitcher_record` output.

### Watchlist tab

No changes needed in `renderWatchlist`. It calls `bestSide(p)` for the badge, which automatically reflects the updated `adj_ev`-based selection. The movement direction display (opening → current odds) is based on `price_delta_over` directly and is unaffected.

---

## Files Changed

| File | Change |
|---|---|
| `pipeline/build_features.py` | Add `STEAM_DISPLAY_THRESHOLD` constant; add `calc_movement_confidence`; update `build_pitcher_record` to apply confidence on raw floats before dict construction; update `ev_over`/`ev_under` dicts with `adj_ev`, `movement_conf`, and `calc_verdict(adj_ev_*)` |
| `tests/test_build_features.py` | New `TestCalcMovementConfidence` class (9 tests); add movement-penalty test to `TestBuildPitcherRecord` |
| `dashboard/index.html` | Declare `const STEAM_LABEL_THRESHOLD = 0.75;` at the top of the script block alongside existing constants (e.g. next to `STALE_HOURS`); update `bestSide()` to use `adj_ev` and return `rawEv`/`conf`; replace Book stat cell with Raw EV cell; add `↓steam` sub-label when `conf <= STEAM_LABEL_THRESHOLD` |

No changes to `fetch_odds.py`, `fetch_stats.py`, `run_pipeline.py`, or `index.json`.

---

## Test Cases

### `TestCalcMovementConfidence`

| delta | expected |
|-------|----------|
| -15   | 1.00 |
|  0    | 1.00 |
|  5    | 1.00 |
|  10   | 1.00 (at noise floor) |
|  15   | 0.75 |
|  20   | 0.50 |
|  25   | 0.25 |
|  30   | 0.00 |
|  40   | 0.00 (clamped above full_fade) |

### `TestBuildPitcherRecord` additions

**Zero-movement case** (baseline, existing tests): `opening_over_odds == best_over_odds` → `price_delta_over=0` → `conf=1.0` → `adj_ev == ev`.

**With-movement case** (new test): Override the baseline fixture with `opening_over_odds=-110`, `best_over_odds=-125`, `opening_under_odds=-110` (all other `BASE_ODDS` fields inherited unchanged) → `price_delta_over=15` → `conf_over=0.75` → `adj_ev_over = ev_over * 0.75`. Assert `result["ev_over"]["adj_ev"] == round(ev_over * 0.75, 4)` and `result["ev_over"]["movement_conf"] == 0.75`. Assert verdict is based on `adj_ev`, not raw `ev`. Since `opening_under_odds == best_under_odds`, `conf_under=1.0` and `adj_ev_under == ev_under`.

---

## Thresholds (defaults, tunable)

| Movement | Confidence | Effect on a FIRE 2u (raw ev=0.08) | Steam label shown? |
|----------|------------|-----------------------------------|--------------------|
| < 10 pts | 1.00 | No change | No |
| 15 pts   | 0.75 | FIRE 2u → FIRE 1u | Yes |
| 20 pts   | 0.50 | FIRE 2u → LEAN | Yes |
| 25 pts   | 0.25 | FIRE 2u → PASS | Yes |
| 30+ pts  | 0.00 | PASS regardless | Yes |

`noise_floor` and `full_fade` are parameters on `calc_movement_confidence` — easy to tune after observing real-world results. `STEAM_DISPLAY_THRESHOLD` (0.75) is a separate display constant that controls when the `↓steam` label appears.
