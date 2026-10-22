# Steam Display Redesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace raw line movement arrows with betting-oriented "steam with/against" indicators that show whether market movement supports or opposes the model's recommendation, with corrected zero-crossing math.

**Architecture:** All changes in `dashboard/index.html` (single-file app). Replace `priceDeltaHtml()` with three new helpers (`calcCentsMove`, `sideGotCheaper`, `steamHtml`), update CSS classes, and rewrite the Watchlist filter/render logic.

**Tech Stack:** Vanilla JS/HTML/CSS (no build tools, no framework)

**Spec:** `docs/superpowers/specs/2026-04-08-steam-display-design.md`

---

### File Map

- **Modify:** `dashboard/index.html`
  - CSS (lines 341-342): Replace `.delta-over`/`.delta-under` with `.steam-with`/`.steam-against`
  - JS helpers (lines 720-725): Replace `priceDeltaHtml()` with `calcCentsMove()`, `sideGotCheaper()`, `steamHtml()`, `steamLabelHtml()`
  - `renderProps()` (line 785): Swap `priceDeltaHtml` call for `steamHtml` call, passing model side context
  - `renderWatchlist()` (lines 820-862): Add FIRE/LEAN filter, use corrected delta, render steam labels

No new files created. No backend changes.

---

### Task 1: Replace CSS classes

**Files:**
- Modify: `dashboard/index.html:341-342`

- [ ] **Step 1: Replace `.delta-over` and `.delta-under` CSS rules**

Find (lines 341-342):
```css
    .delta-over  { color: var(--fire);    font-weight: 700; font-family: monospace; font-size: 11px; }
    .delta-under { color: var(--ink-dim); font-weight: 700; font-family: monospace; font-size: 11px; }
```

Replace with:
```css
    .steam-with    { color: #27ae60;      font-weight: 700; font-family: monospace; font-size: 11px; }
    .steam-against { color: var(--fire);   font-weight: 700; font-family: monospace; font-size: 11px; }
```

- [ ] **Step 2: Verify no other references to old class names**

Search the file for `delta-over` and `delta-under`. They should only appear in the `priceDeltaHtml()` function (which we replace in Task 2). No references should remain after all tasks are complete.

- [ ] **Step 3: Commit**

```bash
git add dashboard/index.html
git commit -m "style: replace delta-over/under CSS with steam-with/against classes"
```

---

### Task 2: Add new helper functions

**Files:**
- Modify: `dashboard/index.html:720-725` (replace `priceDeltaHtml`, add new helpers)

- [ ] **Step 1: Replace `priceDeltaHtml()` with four new functions**

Find (lines 720-725):
```javascript
  function priceDeltaHtml(delta) {
    if (!delta) return '';
    const dir = delta < 0 ? '↓' : '↑';
    const cls = delta < 0 ? 'delta-over' : 'delta-under';
    return ` <span class="${cls}">${dir}${Math.abs(delta)}</span>`;
  }
```

Replace with:
```javascript
  /**
   * Zero-crossing-aware cents-moved calculation.
   * Treats +100 and -100 as the same point (even money).
   * Returns absolute magnitude (always >= 0).
   */
  function calcCentsMove(opening, current) {
    if (opening == null || current == null) return 0;
    const sameSign = (opening > 0 && current > 0) || (opening < 0 && current < 0);
    if (sameSign) return Math.abs(current - opening);
    // Crosses even money: distance from each side to the +100/-100 boundary
    return (Math.abs(opening) - 100) + (Math.abs(current) - 100);
  }

  /**
   * Did this side get cheaper (less favored by the book)?
   * Uses implied probability: cheaper = lower implied prob.
   * Returns true if the side got cheaper, false if more expensive.
   */
  function sideGotCheaper(opening, current) {
    if (opening == null || current == null) return false;
    function impliedProb(odds) {
      return odds < 0
        ? Math.abs(odds) / (Math.abs(odds) + 100)
        : 100 / (odds + 100);
    }
    return impliedProb(current) < impliedProb(opening);
  }

  /**
   * Core steam computation shared by steamHtml and steamLabel.
   * Returns { cents, steamWith, biggerIsOver } or null if no movement.
   */
  function _steamCore(p, modelDir) {
    const overMove  = calcCentsMove(p.opening_over_odds, p.best_over_odds);
    const underMove = calcCentsMove(p.opening_under_odds, p.best_under_odds);
    const biggerIsOver = overMove >= underMove;
    const cents = biggerIsOver ? overMove : underMove;
    if (cents === 0) return null;

    // Did the bigger-moving side get cheaper?
    const cheaper = biggerIsOver
      ? sideGotCheaper(p.opening_over_odds, p.best_over_odds)
      : sideGotCheaper(p.opening_under_odds, p.best_under_odds);

    // Decision matrix: same side as model + more expensive = steam with
    // If measuring the opposite side, invert (over/under are inversely related)
    const sameSide = (biggerIsOver ? 'OVER' : 'UNDER') === modelDir;
    const steamWith = sameSide ? !cheaper : cheaper;

    return { cents, steamWith, biggerIsOver };
  }

  /**
   * Compact steam indicator for the Picks tab.
   * Green ↑N = movement supports model's side.
   * Red ↓N = movement against model's side.
   */
  function steamHtml(p, modelDir) {
    const core = _steamCore(p, modelDir);
    if (!core) return '';
    const arrow = core.steamWith ? '↑' : '↓';
    const cls   = core.steamWith ? 'steam-with' : 'steam-against';
    return ` <span class="${cls}">${arrow}${core.cents}</span>`;
  }

  /**
   * Full steam label for the Watchlist tab.
   * Returns e.g. "Steam with ↑26" (green) or "Steam against ↓16" (red).
   * Also returns metadata for the card layout.
   */
  function steamLabel(p, modelDir) {
    const core = _steamCore(p, modelDir);
    if (!core) return null;
    return {
      cents: core.cents,
      steamWith: core.steamWith,
      biggerIsOver: core.biggerIsOver,
      html: `<span class="${core.steamWith ? 'steam-with' : 'steam-against'}">${core.steamWith ? 'Steam with' : 'Steam against'} ${core.steamWith ? '↑' : '↓'}${core.cents}</span>`
    };
  }
```

- [ ] **Step 2: Manually verify the helpers against spec examples**

Open browser console and test (after page loads):
```javascript
// +118 → -108 should be 26 (crosses zero)
console.assert(calcCentsMove(118, -108) === 26, '+118→-108 should be 26');
// -108 → +108 should be 16 (crosses zero)
console.assert(calcCentsMove(-108, 108) === 16, '-108→+108 should be 16');
// -154 → -120 should be 34 (same side)
console.assert(calcCentsMove(-154, -120) === 34, '-154→-120 should be 34');
// -145 → -130 should be 15 (same side)
console.assert(calcCentsMove(-145, -130) === 15, '-145→-130 should be 15');
// null handling
console.assert(calcCentsMove(null, -108) === 0, 'null opening should be 0');

// +118 → -108: became more expensive (not cheaper)
console.assert(sideGotCheaper(118, -108) === false, '+118→-108 should NOT be cheaper');
// -154 → -120: became cheaper (less favored)
console.assert(sideGotCheaper(-154, -120) === true, '-154→-120 should be cheaper');
// -108 → +108: became cheaper (became underdog)
console.assert(sideGotCheaper(-108, 108) === true, '-108→+108 should be cheaper');

console.log('All steam helper tests passed');
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/index.html
git commit -m "feat: add zero-crossing-aware steam calculation helpers"
```

---

### Task 3: Update Picks tab to use steam indicators

**Files:**
- Modify: `dashboard/index.html:767,785` (inside `renderProps()`)

- [ ] **Step 1: Replace priceDelta usage in renderProps**

Find (line 767):
```javascript
      const priceDelta = side.direction === 'OVER' ? p.price_delta_over : p.price_delta_under;
```

Replace with:
```javascript
      const steamIndicator = steamHtml(p, side.direction);
```

- [ ] **Step 2: Update the Line stat-sub to use steamIndicator**

Find (line 785):
```javascript
            <div class="stat-sub">${fmtOdds(side.odds)}${priceDeltaHtml(priceDelta)}</div>
```

Replace with:
```javascript
            <div class="stat-sub">${fmtOdds(side.odds)}${steamIndicator}</div>
```

- [ ] **Step 3: Verify in browser**

Load the dashboard. On the Picks tab:
- Cards with movement should show green `↑N` or red `↓N` next to the odds
- Cards with no movement should show just the odds with no arrow
- Green arrow = movement supports model's recommended side
- Red arrow = movement opposes model's recommended side

- [ ] **Step 4: Commit**

```bash
git add dashboard/index.html
git commit -m "feat: use steam-with/against indicators on Picks tab"
```

---

### Task 4: Rewrite Watchlist tab

**Files:**
- Modify: `dashboard/index.html:820-862` (entire `renderWatchlist()` function)

- [ ] **Step 1: Replace the entire `renderWatchlist()` function**

Find (lines 820-862):
```javascript
  function renderWatchlist(pitchers) {
    const el = document.getElementById('panel-watch');

    const movers = [...pitchers]
      .filter(p => p.price_delta_over !== 0 || p.price_delta_under !== 0)
      .sort((a, b) => {
        const maxA = Math.max(Math.abs(a.price_delta_over || 0), Math.abs(a.price_delta_under || 0));
        const maxB = Math.max(Math.abs(b.price_delta_over || 0), Math.abs(b.price_delta_under || 0));
        return maxB - maxA;
      })
      .slice(0, 5);

    if (!movers.length) {
      el.innerHTML = '<p class="empty">No juice movement yet — check back after the 1pm ET run.</p>';
      return;
    }

    let html = '<div class="watchlist-hd">Biggest juice moves today</div>';
    for (const p of movers) {
      const useOver = Math.abs(p.price_delta_over || 0) >= Math.abs(p.price_delta_under || 0);
      const activeDelta = useOver ? (p.price_delta_over || 0) : (p.price_delta_under || 0);
      const dir = activeDelta < 0 ? '↓' : '↑';
      const cls = activeDelta < 0 ? 'delta-over' : 'delta-under';
      html += `
      <div class="watch-card">
        <div class="watch-left">
          <span class="pitcher-name" style="color:var(--ink)">${esc(p.pitcher)}</span>
          <span class="pitcher-matchup" style="color:var(--ink-dim)">${esc(p.team)} vs ${esc(p.opp_team)}</span>
        </div>
        <div class="watch-mid">
          <span style="font-size:10px;text-transform:uppercase;letter-spacing:.05em">${useOver ? 'Over' : 'Under'} (${p.k_line}K)</span>
          <span>${fmtOdds(useOver ? p.opening_over_odds : p.opening_under_odds)} → ${fmtOdds(useOver ? p.best_over_odds : p.best_under_odds)}</span>
          <span class="${cls}">${dir} ${Math.abs(activeDelta)}</span>
          ${(bestSide(p).direction === 'OVER') !== useOver
            ? `<span style="font-size:9px;color:var(--ink-dim);font-style:italic">model favors ${bestSide(p).direction.toLowerCase()}</span>`
            : ''}
        </div>
        <span class="verdict-badge ${verdictClass(bestSide(p).verdict)}">${badgeLabel(bestSide(p))}</span>
      </div>`;
    }

    el.innerHTML = html;
  }
```

Replace with:
```javascript
  function renderWatchlist(pitchers) {
    const el = document.getElementById('panel-watch');

    // Filter: FIRE/LEAN only, with non-zero corrected movement
    const movers = [...pitchers]
      .map(p => {
        const side = bestSide(p);
        const steam = steamLabel(p, side.direction);
        return { p, side, steam };
      })
      .filter(({ side, steam }) =>
        side.verdict !== 'PASS' && steam != null && steam.cents > 0
      )
      .sort((a, b) => b.steam.cents - a.steam.cents)
      .slice(0, 5);

    if (!movers.length) {
      el.innerHTML = '<p class="empty">No significant steam yet — check back after the 1pm ET run.</p>';
      return;
    }

    let html = '<div class="watchlist-hd">Biggest steam moves today</div>';
    for (const { p, side, steam } of movers) {
      // Show odds for the side with the bigger move
      const openOdds = steam.biggerIsOver ? p.opening_over_odds : p.opening_under_odds;
      const currOdds = steam.biggerIsOver ? p.best_over_odds : p.best_under_odds;
      html += `
      <div class="watch-card">
        <div class="watch-left">
          <span class="pitcher-name" style="color:var(--ink)">${esc(p.pitcher)}</span>
          <span class="pitcher-matchup" style="color:var(--ink-dim)">${esc(p.team)} vs ${esc(p.opp_team)}</span>
        </div>
        <div class="watch-mid">
          <span style="font-size:10px;text-transform:uppercase;letter-spacing:.05em">${side.direction} (${p.k_line}K)</span>
          <span>${fmtOdds(openOdds)} → ${fmtOdds(currOdds)}</span>
          ${steam.html}
        </div>
        <span class="verdict-badge ${verdictClass(side.verdict)}">${badgeLabel(side)}</span>
      </div>`;
    }

    el.innerHTML = html;
  }
```

- [ ] **Step 2: Verify in browser**

Load the dashboard. On the Watchlist tab:
- Only FIRE/LEAN picks with movement should appear (no PASS cards)
- Each card shows the model's recommended side (e.g., "OVER (5.5K)")
- Opening → current odds for the bigger-moving side
- "Steam with ↑N" in green or "Steam against ↓N" in red
- Verdict badge on the right
- Max 5 cards
- If no qualifying picks, shows "No significant steam yet — check back after the 1pm ET run."
- Header reads "Biggest steam moves today"

- [ ] **Step 3: Verify with the spec examples**

Cross-check against the spec's four test cases:
- **Will Warren** O5.5K +118→-108: model favors Under, over became more expensive → steam against ↓26 (red)
- **Joey Cantillo** U5.5K -154→-120: model favors Over, under became cheaper → steam with ↑34 (green)
- **Cole Ragans** O6.5K -145→-130: model favors Under, over became cheaper → steam with ↑15 (green)

(Will Warren and Cristian Javier would not appear if their verdict is PASS.)

- [ ] **Step 4: Commit**

```bash
git add dashboard/index.html
git commit -m "feat: rewrite Watchlist with steam labels, FIRE/LEAN filter"
```

---

### Task 5: Final cleanup and verification

**Files:**
- Modify: `dashboard/index.html` (if any dead code remains)

- [ ] **Step 1: Search for any remaining references to old code**

Search for these strings in `dashboard/index.html` — all should return zero matches:
- `priceDeltaHtml` — old function, should be fully removed
- `delta-over` — old CSS class, should be fully removed
- `delta-under` — old CSS class, should be fully removed
- `price_delta_over` — old field references in render functions (OK if still in data, but should not be used in display logic)
- `price_delta_under` — same as above

Note: `price_delta_over`/`price_delta_under` will still exist in the JSON data from the backend. That's fine — they're just unused by the display now.

- [ ] **Step 2: Full browser smoke test**

1. Load dashboard with today's data
2. **Picks tab:** Verify green/red arrows next to odds on cards with movement
3. **Watchlist tab:** Verify only FIRE/LEAN cards, steam labels, corrected cents
4. Switch between tabs — no console errors
5. Toggle "Show PASS verdicts" checkbox — steam indicators still render correctly on PASS cards in Picks view
6. Check on mobile viewport (375px width) — cards don't overflow
7. Navigate to a past date (if available) — steam indicators should render correctly on historical picks too (spec edge case: isPast flag)

- [ ] **Step 3: Final commit**

```bash
git add dashboard/index.html
git commit -m "chore: remove dead delta-over/under references"
```

(Only if Step 1 found anything to clean up. If not, skip this commit.)
