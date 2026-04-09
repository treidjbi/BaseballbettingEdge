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

For the model's recommended side:
- Odds became **more expensive** (more negative, or crossed from + to −) → market agrees → **steam with** (green ↑)
- Odds became **less expensive** (more positive, or crossed from − to +) → market disagrees → **steam against** (red ↓)

The movement is measured on **whichever side (over/under) had the larger corrected delta**, and the "steam with/against" label is relative to the model's pick. If the under gets cheaper, that inherently means the over is getting more expensive — so "steam with" applies to an OVER recommendation.

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
- If no qualifying picks, show "No significant steam today"

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
- **No qualifying picks on Watchlist:** Display "No significant steam today"
- **Same-side movement (no zero crossing):** Standard `|current - opening|` math

## Files Modified

- `dashboard/index.html` — all changes in this single file:
  - `priceDeltaHtml()` → replace with new `calcCentsMove()` + `steamHtml()` helpers
  - `renderWatchlist()` → add FIRE/LEAN filter, use steam labels, show model's side
  - `renderProps()` → use new compact green/red arrow display
  - CSS section — replace `.delta-over`/`.delta-under` with `.steam-with`/`.steam-against`

## Out of Scope

- No changes to backend data pipeline or model logic
- No changes to steam haircut / EV adjustment calculations
- No changes to the Performance tab
