# Line Movement Confidence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply a proportional EV haircut when the sportsbook line moves against the model's recommended side, surfacing market steam as a confidence signal alongside the preserved raw model EV.

**Architecture:** One new pure function `calc_movement_confidence(delta)` in `build_features.py` computes a 0–1 multiplier; `build_pitcher_record` applies it to raw EV floats before building the output dict, storing both raw and adjusted EV. The dashboard's `bestSide()` switches from raw to adjusted EV, the Book column is replaced with Raw EV, and a `↓steam` label appears when confidence drops enough to matter.

**Tech Stack:** Python / scipy (existing), vanilla JS (existing dashboard), pytest

---

## File Map

| File | What changes |
|---|---|
| `pipeline/build_features.py` | Add `STEAM_DISPLAY_THRESHOLD` constant + `calc_movement_confidence` function; update `build_pitcher_record` to extract delta vars, apply confidence on raw floats, emit `adj_ev` / `movement_conf` in both EV dicts |
| `tests/test_build_features.py` | New `TestCalcMovementConfidence` class (9 tests); new `test_movement_confidence_applied` in `TestBuildPitcherRecord` |
| `dashboard/index.html` | Add `STEAM_LABEL_THRESHOLD` JS constant; update `bestSide()`; replace Book stat cell with Raw EV; add steam sub-label to EV cell |

---

## Task 1: `calc_movement_confidence` — tests first, then implementation

**Files:**
- Modify: `tests/test_build_features.py` (add import + new class at end of file)
- Modify: `pipeline/build_features.py` (add constant + function)

### Background for the implementor

`calc_movement_confidence(delta)` takes a price delta (integer, `current_odds - opening_odds`).
- **Positive delta** = that side got cheaper (e.g. over was -145, now -125 → delta = +20). This means sharp money likely came in on the **other** side. Apply a penalty.
- **Negative or zero delta** = line moved in our favour, or no movement. No penalty (return 1.0).
- Linear decay: movements ≤ 10 pts are noise (return 1.0). Movements ≥ 30 pts fully fade EV to 0 (return 0.0). Between 10 and 30, decay linearly.

- [ ] **Step 1: Add the import to the test file**

At the top of `tests/test_build_features.py`, update the import from `build_features`:

```python
from build_features import (
    american_to_implied,
    calc_lambda,
    calc_ev,
    calc_verdict,
    calc_price_delta,
    blend_k9,
    calc_swstr_mult,
    calc_movement_confidence,   # ADD THIS LINE
)
```

- [ ] **Step 2: Write the failing tests**

Append this class to the end of `tests/test_build_features.py`:

```python
class TestCalcMovementConfidence:
    def test_negative_delta_no_penalty(self):
        # Movement in our favour — no penalty
        assert calc_movement_confidence(-15) == 1.0

    def test_zero_delta_no_penalty(self):
        assert calc_movement_confidence(0) == 1.0

    def test_below_noise_floor_no_penalty(self):
        assert calc_movement_confidence(5) == 1.0

    def test_at_noise_floor_no_penalty(self):
        # Exactly at noise_floor (10) → still 1.0
        assert calc_movement_confidence(10) == 1.0

    def test_midpoint_decay(self):
        # delta=20 is halfway between noise_floor=10 and full_fade=30 → 0.50
        assert abs(calc_movement_confidence(20) - 0.50) < 0.001

    def test_quarter_decay(self):
        # delta=15 → (15-10)/(30-10) = 5/20 = 0.25 penalty → 0.75
        assert abs(calc_movement_confidence(15) - 0.75) < 0.001

    def test_three_quarter_decay(self):
        # delta=25 → (25-10)/(30-10) = 15/20 = 0.75 penalty → 0.25
        assert abs(calc_movement_confidence(25) - 0.25) < 0.001

    def test_at_full_fade(self):
        assert calc_movement_confidence(30) == 0.0

    def test_above_full_fade_clamped(self):
        # Anything beyond full_fade is still 0.0
        assert calc_movement_confidence(40) == 0.0
```

- [ ] **Step 3: Run tests to confirm they fail**

```
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
python -m pytest tests/test_build_features.py::TestCalcMovementConfidence -v
```

Expected: 9 failures with `ImportError: cannot import name 'calc_movement_confidence'`

- [ ] **Step 4: Add the constant and function to `build_features.py`**

In `pipeline/build_features.py`, add `STEAM_DISPLAY_THRESHOLD` to the constants block after `LEAGUE_AVG_SWSTR` (around line 16):

```python
LEAGUE_AVG_SWSTR  = 0.110      # FanGraphs league avg swinging strike rate
STEAM_DISPLAY_THRESHOLD = 0.75  # show ↓steam label when confidence ≤ this value (delta ≥ 15 pts)
```

Then add `calc_movement_confidence` after the existing `calc_price_delta` function (after line 85):

```python
def calc_movement_confidence(delta: int,
                              noise_floor: int = 10,
                              full_fade:   int = 30) -> float:
    """
    Returns a confidence multiplier (0.0–1.0) based on line movement against the bet side.

    delta > 0  : that side got cheaper (sharp money on the other side) → penalty applied.
    delta <= 0 : movement in our favour or no movement → no penalty (returns 1.0).

    Linear decay from 1.0 at noise_floor to 0.0 at full_fade.
    Movements below noise_floor are treated as routine book adjustments (ignored).
    """
    if delta <= noise_floor:
        return 1.0
    if delta >= full_fade:
        return 0.0
    return 1.0 - (delta - noise_floor) / (full_fade - noise_floor)
```

- [ ] **Step 5: Run tests to confirm they pass**

```
python -m pytest tests/test_build_features.py::TestCalcMovementConfidence -v
```

Expected: 9 passed

- [ ] **Step 6: Run full test suite to confirm nothing broken**

```
python -m pytest tests/ -q
```

Expected: all existing tests pass (63+9 = 72 total)

- [ ] **Step 7: Commit**

```
git add pipeline/build_features.py tests/test_build_features.py
git commit -m "feat: add calc_movement_confidence with 9 tests"
```

---

## Task 2: Update `build_pitcher_record` to apply confidence

**Files:**
- Modify: `tests/test_build_features.py` (add one new test to `TestBuildPitcherRecord`)
- Modify: `pipeline/build_features.py` (update `build_pitcher_record`)

### Background for the implementor

Currently `build_pitcher_record` computes `price_delta_over` and `price_delta_under` inline inside the `return` dict (lines 131–132 of `build_features.py`). The update:
1. Extracts those two `calc_price_delta` calls to named variables **before** the `return`
2. Computes `conf_over` and `conf_under` from those variables
3. Computes `adj_ev_over = ev_over * conf_over` and `adj_ev_under = ev_under * conf_under` (on raw floats)
4. Updates the `ev_over` / `ev_under` dicts to include `adj_ev`, `movement_conf`, and to use `calc_verdict(adj_ev_*)` instead of `calc_verdict(ev_*)`

**Critical:** The confidence multiplication (`ev * conf`) must happen on raw Python floats — before the `round()` calls inside the dict. Putting it inside the dict would be a type error.

**Also note:** The `opening_over_odds` and `opening_under_odds` keys are always present in production (populated by `fetch_odds.py`). Use `.get()` with a fallback to the current odds purely for defensive safety — it has no runtime effect.

- [ ] **Step 1: Write the failing test**

Add this test to the `TestBuildPitcherRecord` class in `tests/test_build_features.py`:

```python
    def test_movement_confidence_applied(self):
        """
        When the over line moves from -125 (opening) to -110 (current),
        price_delta_over = -110 - (-125) = +15 → conf_over = 0.75.
        adj_ev_over should equal round(raw_ev_over * 0.75, 4).
        The under has no movement → conf_under = 1.0, adj_ev_under == ev_under.
        """
        from build_features import build_pitcher_record
        odds = {
            **self.BASE_ODDS,
            "opening_over_odds": -125,   # over was -125 at open
            "best_over_odds":    -110,   # over moved to -110 (cheaper) → delta = +15
            "opening_under_odds": -110,  # under unchanged
            "best_under_odds":    -110,
        }
        rec = build_pitcher_record(odds, self.BASE_STATS, ump_k_adj=0.0)

        raw_ev_over = rec["ev_over"]["ev"]
        assert abs(rec["ev_over"]["movement_conf"] - 0.75) < 0.001
        assert abs(rec["ev_over"]["adj_ev"] - round(raw_ev_over * 0.75, 4)) < 0.0001

        # Under: no movement → no haircut
        raw_ev_under = rec["ev_under"]["ev"]
        assert abs(rec["ev_under"]["movement_conf"] - 1.0) < 0.001
        assert rec["ev_under"]["adj_ev"] == raw_ev_under

        # Verdict must be based on adj_ev, not raw ev
        from build_features import calc_verdict
        assert rec["ev_over"]["verdict"] == calc_verdict(rec["ev_over"]["adj_ev"])
        assert rec["ev_under"]["verdict"] == calc_verdict(rec["ev_under"]["adj_ev"])
```

- [ ] **Step 2: Run the test to confirm it fails**

```
python -m pytest tests/test_build_features.py::TestBuildPitcherRecord::test_movement_confidence_applied -v
```

Expected: FAIL — `KeyError: 'adj_ev'` or similar

- [ ] **Step 3: Update `build_pitcher_record` in `pipeline/build_features.py`**

Find the section starting with `k_line = odds["k_line"]` (around line 109) through the end of the function. Replace the block from `best_over_odds = ...` through the final `return` with the updated version below.

The current code looks like this (lines ~114–140):

```python
    best_over_odds  = odds["best_over_odds"]
    best_under_odds = odds["best_under_odds"]
    ev_over  = calc_ev(win_prob_over,  best_over_odds)
    ev_under = calc_ev(win_prob_under, best_under_odds)

    return {
        "pitcher":            odds["pitcher"],
        "team":               odds["team"],
        "opp_team":           odds["opp_team"],
        "game_time":          odds["game_time"],
        "k_line":             k_line,
        "opening_line":       odds.get("opening_line", k_line),
        "best_over_book":     odds["best_over_book"],
        "best_over_odds":     best_over_odds,
        "best_under_odds":    best_under_odds,
        "opening_over_odds":  odds["opening_over_odds"],
        "opening_under_odds": odds["opening_under_odds"],
        "price_delta_over":   calc_price_delta(best_over_odds,  odds["opening_over_odds"]),
        "price_delta_under":  calc_price_delta(best_under_odds, odds["opening_under_odds"]),
        "lambda":             round(lam, 2),
        "avg_ip":             avg_ip,
        "swstr_pct":          round(swstr_pct, 4),
        "opp_k_rate":         stats["opp_k_rate"],
        "ump_k_adj":          ump_k_adj,
        "ev_over":  {"ev": round(ev_over, 4),  "verdict": calc_verdict(ev_over),  "win_prob": round(win_prob_over, 3)},
        "ev_under": {"ev": round(ev_under, 4), "verdict": calc_verdict(ev_under), "win_prob": round(win_prob_under, 3)},
    }
```

Replace it with:

```python
    best_over_odds  = odds["best_over_odds"]
    best_under_odds = odds["best_under_odds"]
    ev_over  = calc_ev(win_prob_over,  best_over_odds)
    ev_under = calc_ev(win_prob_under, best_under_odds)

    # Extract delta variables before applying confidence (must operate on raw floats)
    price_delta_over  = calc_price_delta(best_over_odds,  odds.get("opening_over_odds",  best_over_odds))
    price_delta_under = calc_price_delta(best_under_odds, odds.get("opening_under_odds", best_under_odds))

    # Market confidence: positive delta = that side got cheaper = steam on the other side
    conf_over  = calc_movement_confidence(price_delta_over)
    conf_under = calc_movement_confidence(price_delta_under)
    adj_ev_over  = ev_over  * conf_over
    adj_ev_under = ev_under * conf_under

    return {
        "pitcher":            odds["pitcher"],
        "team":               odds["team"],
        "opp_team":           odds["opp_team"],
        "game_time":          odds["game_time"],
        "k_line":             k_line,
        "opening_line":       odds.get("opening_line", k_line),
        "best_over_book":     odds["best_over_book"],
        "best_over_odds":     best_over_odds,
        "best_under_odds":    best_under_odds,
        "opening_over_odds":  odds["opening_over_odds"],
        "opening_under_odds": odds["opening_under_odds"],
        "price_delta_over":   price_delta_over,
        "price_delta_under":  price_delta_under,
        "lambda":             round(lam, 2),
        "avg_ip":             avg_ip,
        "swstr_pct":          round(swstr_pct, 4),
        "opp_k_rate":         stats["opp_k_rate"],
        "ump_k_adj":          ump_k_adj,
        "ev_over":  {
            "ev":            round(ev_over,      4),
            "adj_ev":        round(adj_ev_over,  4),
            "verdict":       calc_verdict(adj_ev_over),
            "win_prob":      round(win_prob_over,  3),
            "movement_conf": round(conf_over,    4),
        },
        "ev_under": {
            "ev":            round(ev_under,      4),
            "adj_ev":        round(adj_ev_under,  4),
            "verdict":       calc_verdict(adj_ev_under),
            "win_prob":      round(win_prob_under,  3),
            "movement_conf": round(conf_under,    4),
        },
    }
```

- [ ] **Step 4: Run the new test to confirm it passes**

```
python -m pytest tests/test_build_features.py::TestBuildPitcherRecord::test_movement_confidence_applied -v
```

Expected: PASS

- [ ] **Step 5: Run the full test suite**

```
python -m pytest tests/ -q
```

Expected: all 73 tests pass (63 original + 9 confidence + 1 new integration test)

- [ ] **Step 6: Commit**

```
git add pipeline/build_features.py tests/test_build_features.py
git commit -m "feat: apply movement confidence to EV in build_pitcher_record"
```

---

## Task 3: Dashboard — bestSide, Raw EV column, steam label

**Files:**
- Modify: `dashboard/index.html` (script block only — 3 targeted edits)

### Background for the implementor

Three changes to `dashboard/index.html`, all in the `<script>` block:

1. **Add `STEAM_LABEL_THRESHOLD` constant** near the top of the script block, next to `STALE_HOURS`
2. **Update `bestSide()`** to compare `adj_ev` instead of `ev`, and return `rawEv` + `conf`
3. **Update the stats grid** in `renderProps`: replace the Book cell with Raw EV, and update the EV cell to show a `↓steam` sub-label when confidence is low

No changes to `renderWatchlist` — it already calls `bestSide(p)` for the badge, so it picks up the `adj_ev`-based selection automatically.

- [ ] **Step 1: Add `STEAM_LABEL_THRESHOLD` constant**

In `dashboard/index.html`, find the constants block at the top of the `<script>` block:

```javascript
  const INDEX_URL   = 'data/processed/index.json';
  const TODAY_URL   = 'data/processed/today.json';
  const STALE_HOURS = 6;
```

Add the new constant on the line after `STALE_HOURS`:

```javascript
  const INDEX_URL          = 'data/processed/index.json';
  const TODAY_URL          = 'data/processed/today.json';
  const STALE_HOURS        = 6;
  const STEAM_LABEL_THRESHOLD = 0.75;  // show ↓steam when movement_conf ≤ this value
```

- [ ] **Step 2: Update `bestSide()`**

Find the existing `bestSide` function (in the Helpers section):

```javascript
  function bestSide(p) {
    if (p.ev_over.ev >= p.ev_under.ev) {
      return { verdict: p.ev_over.verdict,  ev: p.ev_over.ev,  winProb: p.ev_over.win_prob,  direction: 'OVER',  odds: p.best_over_odds  };
    } else {
      return { verdict: p.ev_under.verdict, ev: p.ev_under.ev, winProb: p.ev_under.win_prob, direction: 'UNDER', odds: p.best_under_odds };
    }
  }
```

Replace it with:

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

- [ ] **Step 3: Update the stats grid in `renderProps`**

Find the two stat cells for EV and Book inside the `renderProps` template literal. They currently look like this:

```javascript
          <div class="stat-cell">
            <div class="stat-label">EV</div>
            <div class="stat-value ${side.ev > 0 ? 'val-pos' : 'val-neg'}">${(side.ev * 100).toFixed(1)}%</div>
            <div class="stat-sub">p=${side.winProb}</div>
          </div>
          <div class="stat-cell">
            <div class="stat-label">Book</div>
            <div class="stat-value" style="font-size:12px">${p.best_over_book}</div>
            <div class="stat-sub">${fmtOdds(side.odds)}</div>
          </div>
```

Replace them with:

```javascript
          <div class="stat-cell">
            <div class="stat-label">EV</div>
            <div class="stat-value ${side.ev > 0 ? 'val-pos' : 'val-neg'}">${(side.ev * 100).toFixed(1)}%</div>
            <div class="stat-sub">${side.conf <= STEAM_LABEL_THRESHOLD ? '↓steam' : 'p=' + side.winProb}</div>
          </div>
          <div class="stat-cell">
            <div class="stat-label">Raw EV</div>
            <div class="stat-value ${side.rawEv > 0 ? 'val-pos' : 'val-neg'}">${(side.rawEv * 100).toFixed(1)}%</div>
            <div class="stat-sub">model</div>
          </div>
```

- [ ] **Step 4: Verify no Python tests broken**

```
python -m pytest tests/ -q
```

Expected: 73 passed (no Python changes in this task, but good to confirm)

- [ ] **Step 5: Manual smoke test**

Open `dashboard/index.html` directly in a browser (or via the Netlify preview). With today's data loaded:
- Each card shows 4 stat columns: Line · λ · EV · Raw EV
- No "Book" column visible
- When `movement_conf ≤ 0.75` (steam detected): EV cell shows `↓steam` sub-label
- When no steam: EV cell shows `p=0.xxx` as before
- Raw EV column shows a percentage (green if positive, grey if negative)
- Badge still shows e.g. `FIRE 2u OVER` or `LEAN UNDER`

- [ ] **Step 6: Commit**

```
git add dashboard/index.html
git commit -m "feat: dashboard Raw EV column, steam label, adj_ev bestSide selection"
```

---

## Task 4: Push and verify

- [ ] **Step 1: Pull rebase then push**

```
git pull --rebase
git push
```

- [ ] **Step 2: Confirm Netlify deploys successfully**

Check the Netlify dashboard or visit `https://baseballbettingedge.netlify.app` after the deploy completes. Confirm the card layout shows Line · λ · EV · Raw EV.

- [ ] **Step 3: Confirm GitHub Actions pipeline runs cleanly**

The pipeline writes `today.json` — the new `adj_ev` and `movement_conf` fields will appear in the next pipeline run. No workflow changes required.
