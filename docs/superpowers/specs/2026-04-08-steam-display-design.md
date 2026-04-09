# Steam Display Redesign — Spec

**Date:** 2026-04-08
**Scope:** Display-only changes to Watchlist and Picks tabs in `dashboard/index.html`
**No backend or model logic changes.**

---

## Problem

The current line movement display shows raw delta values (naive subtraction of American odds) with no context about whether the movement supports or opposes the model's recommendation. Additionally, the delta math is wrong when odds cross even money — e.g., +118 → -108 shows as 226 cents when the actual movement is 26 cents.

## Design

### 1. Delta Calculation — Zero-Crossing-Aware Math

Replace naive `best - opening` subtraction with:

```
function calcCentsMove(opening, current):
  if both same sign (both + or both -):
    return |current - opening|
  else (crosses even money):
    return (|opening| - 100) + (|current| - 100)
```

This treats +100 and -100 as the same point (even money) on the odds number line.

**Examples:**
| Movement | Current (wrong) | Corrected |
|---|---|---|
| +118 → -108 | 226 | 26 |
| -108 → +108 | 216 | 16 |
| -154 → -120 | 34 | 34 |
| -145 → -130 | 15 | 15 |

### 2. Model Alignment — "Steam With" vs "Steam Against"

Determine whether line movement supports or opposes the model's recommended side (OVER or UNDER).

**Direction determination** — did a side get cheaper or more expensive?

```
function sideGotCheaper(opening, current):
  // Convert to implied probability: lower prob = cheaper
  // For negative odds: prob = |odds| / (|odds| + 100)
  // For positive odds: prob = 100 / (odds + 100)
  // If implied prob decreased, the side got cheaper (less favored)
  return impliedProb(current) < impliedProb(opening)
```

Equivalently without computing probabilities:
- Both negative: current is closer to 0 (e.g., -154 → -120) → got cheaper
- Both positive: current is larger (e.g., +110 → +140) → got cheaper
- Crossed + to −: got more expensive (became the favorite)
- Crossed − to +: got cheaper (became the underdog)

**Decision matrix** — the movement is measured on whichever side (over/under) had the larger corrected delta:

| Model recommends | Side with biggest move | That side got... | Label |
|---|---|---|---|
| OVER | OVER | more expensive | **steam with** |
| OVER | OVER | cheaper | **steam against** |
| OVER | UNDER | more expensive | **steam against** |
| OVER | UNDER | cheaper | **steam with** |
| UNDER | UNDER | more expensive | **steam with** |
| UNDER | UNDER | cheaper | **steam against** |
| UNDER | OVER | more expensive | **steam against** |
| UNDER | OVER | cheaper | **steam with** |

Rule: if the biggest-moving side IS the model's recommended side, "more expensive" = steam with. If it's the OPPOSITE side, "more expensive" = steam against. (Over and under are inversely related.)

### 3. Picks Tab — Compact Inline Display

**Current:** `-120 ↑3` with red/grey coloring based on raw delta direction.

**New:** `-120` followed by a colored semantic arrow + corrected cents:
- **Green `↑26`** — movement supports model's recommended side
- **Red `↓16`** — movement opposes model's recommended side
- **No indicator** if delta is 0

Arrow direction represents **model alignment**, not raw odds direction. Green up = good for us, red down = bad for us.

### 4. Watchlist Tab — Full Steam Labels

**Filtering:**
- Only show FIRE and LEAN verdict picks (exclude PASS)
- Only show picks with non-zero movement
- If no qualifying picks, show "No significant steam yet — check back after the 1pm ET run"
- Cap at **5 entries** (same as current)

**Sort:** Biggest corrected cents moved first (descending).

**Card layout:**
- Pitcher name + matchup
- Model's recommended side + K line (e.g., `OVER (5.5K)`)
- Opening → current odds for the side with the bigger move
- **`Steam with ↑26`** (green) or **`Steam against ↓16`** (red)
- Verdict badge (`FIRE 1u`, `LEAN`, etc.)

### 5. CSS Changes

Replace `.delta-over` / `.delta-under` classes with:
- `.steam-with` — green (`#27ae60`), bold, monospace, 11px
- `.steam-against` — red (`var(--fire)` / `#c0392b`), bold, monospace, 11px

### 6. Edge Cases

- **Zero movement:** No arrow/label shown; pick excluded from Watchlist
- **No qualifying picks on Watchlist:** Display "No significant steam yet — check back after the 1pm ET run"
- **Same-side movement (no zero crossing):** Standard `|current - opening|` math
- **Null/missing opening odds:** Backend defaults missing opening to best odds (delta = 0); frontend guards against null/undefined — treat as no movement
- **Past picks (`isPast` flag):** Steam display applies to past picks too (historical context is useful)

## Files Modified

- `dashboard/index.html` — all changes in this single file:
  - `priceDeltaHtml()` → replace with new `calcCentsMove()` + `steamHtml()` helpers
  - `renderWatchlist()` → add FIRE/LEAN filter, use steam labels, show model's side
  - `renderProps()` → use new compact green/red arrow display
  - CSS section — replace `.delta-over`/`.delta-under` with `.steam-with`/`.steam-against`

## Out of Scope

- No changes to steam haircut / EV adjustment calculations
- No changes to the Performance tab

## Known Issue — Backend Delta Math

The same naive subtraction exists in `build_features.py` (`calc_price_delta`), where it feeds into `calc_movement_confidence()` and `adj_ev`. This means zero-crossing pitchers get over-penalized (e.g., a 26-cent move treated as 226 cents fully fades confidence to 0.0). **This is a separate fix** that should be addressed in a follow-up task — this spec only fixes the frontend display.
