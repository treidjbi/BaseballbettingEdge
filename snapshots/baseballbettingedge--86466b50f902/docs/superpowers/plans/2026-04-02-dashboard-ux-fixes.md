# Dashboard UX Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all UI/UX issues identified in the April 2 code review so the dashboard is clear and correct for sports bettors.

**Architecture:** All changes are in a single file — `dashboard/index.html` — which contains HTML structure, CSS, and JavaScript in one self-contained page. There are no build tools; edits take effect immediately in the browser. Changes are organized into 5 logical tasks, each committed independently.

**Tech Stack:** Vanilla HTML/CSS/JS, served statically from Netlify; data loaded from GitHub raw URLs or local filesystem.

---

## File Map

| File | What changes |
|------|-------------|
| `dashboard/index.html` | All 5 tasks — HTML, CSS, and JS |

No other files are touched.

---

### Task 1: Date picker tomorrow cap, "Picks" tab rename, context-aware section header

Three small but visible changes that correct misleading labels.

**Files:**
- Modify: `dashboard/index.html`

**Context:**
- `populateDateSelector()` (line ~427–436): sets `sel.min` but never sets `sel.max`. User wants max = tomorrow so they can see lines as soon as books post them the night before.
- The bottom nav (line ~374–386) labels the first tab "Props". It should say "Picks".
- `renderProps(pitchers)` (line ~597–668): the section header always says "N pitchers **today**" even on historical dates.

---

- [ ] **Step 1: Open the file and verify the three locations**

  In `dashboard/index.html`:
  1. Find `populateDateSelector` — confirm `sel.min` is set but `sel.max` is not.
  2. Find `<span>Props</span>` in the nav — it's inside the first `nav-btn`.
  3. Find `html += \`<div class="section-date">${sorted.length} pitcher${...} today</div>\`` in `renderProps`.

- [ ] **Step 2: Implement all three changes**

  **Change A — date picker max = tomorrow** (in `populateDateSelector`):

  Find this block:
  ```js
  if (dates && dates.length > 0) {
    sel.min = dates[dates.length - 1];
  }
  ```
  Replace with:
  ```js
  if (dates && dates.length > 0) {
    sel.min = dates[dates.length - 1];
  }
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  sel.max = tomorrow.toISOString().slice(0, 10);
  ```

  **Change B — tab label "Props" → "Picks"** (in the nav HTML):

  Find:
  ```html
  <span>Props</span>
  ```
  (inside the first `nav-btn`, next to `⚾`)
  Replace with:
  ```html
  <span>Picks</span>
  ```

  **Change C — section header uses `isPast` flag** (in `renderProps`):

  The function signature is `function renderProps(pitchers)`. Change the call site in `renderAll`:

  Find:
  ```js
  renderProps(data.pitchers);
  ```
  Replace with:
  ```js
  renderProps(data.pitchers, isPast);
  ```

  Then change the function signature and the header line:

  Find:
  ```js
  function renderProps(pitchers) {
  ```
  Replace with:
  ```js
  function renderProps(pitchers, isPast = false) {
  ```

  Find:
  ```js
  html += `<div class="section-date">${sorted.length} pitcher${sorted.length !== 1 ? 's' : ''} today</div>`;
  ```
  Replace with:
  ```js
  html += `<div class="section-date">${sorted.length} pitcher${sorted.length !== 1 ? 's' : ''}${isPast ? '' : ' today'}</div>`;
  ```

- [ ] **Step 3: Verify in browser**

  Open `dashboard/index.html` locally (or use Live Server). Confirm:
  - Date picker cannot be set beyond tomorrow's date.
  - Bottom nav first tab reads "Picks" (not "Props").
  - On today's data: header reads "N pitchers today".
  - On a past date (select yesterday): header reads "N pitchers" (no "today").

- [ ] **Step 4: Commit**

  ```bash
  git add dashboard/index.html
  git commit -m "fix: date picker max=tomorrow, rename Props→Picks tab, remove 'today' on past dates"
  ```

---

### Task 2: Replace λ stat cell with "Proj K" and fix arrow direction

Two clarity fixes that affect every pitcher card and the watchlist.

**Files:**
- Modify: `dashboard/index.html`

**Context:**
- The center stat cell (line ~646–649) labels itself `λ` with sub-label `Poisson`. Bettors don't know what Poisson lambda is. Should read "Proj K" with sub-label "vs line X.X" so it reads as "model projects 6.1 Ks vs. a 6.5 line".
- `priceDeltaHtml(delta)` (line ~580–585): a negative delta (odds shortened, e.g. -110 → -130) currently shows `↑` in red. But `↑` reads as "price went up" in bettor shorthand, which means the opposite (odds loosened). Fix: flip the arrow direction so `↑` means "odds went up (looser)" and `↓` means "odds went down (tighter/steam)". Keep the red/dim color coding as-is (red = steam = sharpening).

---

- [ ] **Step 1: Change the stat cell in the pitcher card template**

  Find this block in the `for (const p of sorted)` loop inside `renderProps`
  (note: 10-space indent on `<div class="stat-cell">`, 12-space on inner divs — match exactly):
  ```js
          <div class="stat-cell">
            <div class="stat-label">λ</div>
            <div class="stat-value">${p.lambda}</div>
            <div class="stat-sub">Poisson</div>
          </div>
  ```
  Replace with:
  ```js
          <div class="stat-cell">
            <div class="stat-label">Proj K</div>
            <div class="stat-value">${p.lambda}</div>
            <div class="stat-sub">vs line ${p.k_line}</div>
          </div>
  ```

- [ ] **Step 2: Fix arrow direction in `priceDeltaHtml`**

  Find:
  ```js
  function priceDeltaHtml(delta) {
    if (!delta) return '';
    const dir = delta < 0 ? '↑' : '↓';
    const cls = delta < 0 ? 'delta-over' : 'delta-under';
    return ` <span class="${cls}">${dir}${Math.abs(delta)}</span>`;
  }
  ```
  Replace with:
  ```js
  function priceDeltaHtml(delta) {
    if (!delta) return '';
    const dir = delta < 0 ? '↓' : '↑';
    const cls = delta < 0 ? 'delta-over' : 'delta-under';
    return ` <span class="${cls}">${dir}${Math.abs(delta)}</span>`;
  }
  ```

  **Why:** `↓` now means "odds dropped" (tightened, steam), `↑` means "odds rose" (opened up). Red color (`delta-over`) still signals steam; the arrow now points in the direction the number moved.

- [ ] **Step 3: Fix the watchlist arrow direction (same bug, different location)**

  `renderWatchlist` has its own inline `dir` computation at line ~699 that is identical to the bug in `priceDeltaHtml`. It is NOT covered by the `priceDeltaHtml` fix — it must be fixed separately.

  Find in `renderWatchlist`:
  ```js
      const dir = activeDelta < 0 ? '↑' : '↓';
  ```
  Replace with:
  ```js
      const dir = activeDelta < 0 ? '↓' : '↑';
  ```

- [ ] **Step 4: Verify in browser**

  Open the dashboard with today's or any historical date. Confirm:
  - The center stat cell on every pitcher card reads "PROJ K" (label) and "vs line 6.5" (sub-label).
  - If any pitcher has a price delta shown in the Line cell, a negative delta shows `↓` in red, a positive delta shows `↑` in gray.
  - In the Watchlist tab, a pitcher whose odds tightened (e.g. -110 → -130, negative delta) shows `↓` in red.

- [ ] **Step 5: Commit**

  ```bash
  git add dashboard/index.html
  git commit -m "fix: rename lambda stat to Proj K with line context, flip price delta arrow direction"
  ```

---

### Task 3: Watchlist — bridging note when steam side conflicts with verdict side

When the biggest steam move is on the Under but the model's best EV is on the Over, the card currently shows both without explanation. A bettor reads this as contradictory. Add a small italic note below the odds line that explains the discrepancy.

**Files:**
- Modify: `dashboard/index.html`

**Context:**
- In `renderWatchlist` (line ~678–717), each watch-card shows:
  - `useOver` (the side with the bigger delta) controls the label and odds display.
  - `bestSide(p)` controls the verdict badge at the right.
- When `useOver` disagrees with `bestSide(p).direction === 'OVER'`, add a note: `"Model favors Under — steam is counter-move"` or `"Model favors Over — steam is counter-move"`.

---

- [ ] **Step 1: Add the bridging note to the watch-card template**

  In `renderWatchlist`, find the `watch-mid` block inside the card template:
  ```js
        <div class="watch-mid">
          <span style="font-size:10px;text-transform:uppercase;letter-spacing:.05em">${useOver ? 'Over' : 'Under'} (${p.k_line}K)</span>
          <span>${fmtOdds(useOver ? p.opening_over_odds : p.opening_under_odds)} → ${fmtOdds(useOver ? p.best_over_odds : p.best_under_odds)}</span>
          <span class="${cls}">${dir} ${Math.abs(activeDelta)}</span>
        </div>
  ```
  Replace with:
  ```js
        <div class="watch-mid">
          <span style="font-size:10px;text-transform:uppercase;letter-spacing:.05em">${useOver ? 'Over' : 'Under'} (${p.k_line}K)</span>
          <span>${fmtOdds(useOver ? p.opening_over_odds : p.opening_under_odds)} → ${fmtOdds(useOver ? p.best_over_odds : p.best_under_odds)}</span>
          <span class="${cls}">${dir} ${Math.abs(activeDelta)}</span>
          ${(bestSide(p).direction === 'OVER') !== useOver
            ? `<span style="font-size:9px;color:var(--ink-dim);font-style:italic">model favors ${bestSide(p).direction.toLowerCase()}</span>`
            : ''}
        </div>
  ```

- [ ] **Step 2: Verify in browser**

  To test this: find a pitcher with both `price_delta_over` and `price_delta_under` non-zero where the larger delta is on one side but `bestSide(p).direction` is the other. If today's data doesn't have such a case, temporarily edit a JSON fixture or check a historical date. Confirm:
  - When sides agree: no note appears.
  - When sides disagree: a small italic "model favors over" or "model favors under" appears below the odds line inside the mid column.

- [ ] **Step 3: Commit**

  ```bash
  git add dashboard/index.html
  git commit -m "fix: add bridging note in watchlist when steam side conflicts with model verdict"
  ```

---

### Task 4: Performance tab — light theme + copy fixes + units column

Three related fixes in the Performance tab, all in `dashboard/index.html`.

**Files:**
- Modify: `dashboard/index.html`

**Context:**
- CSS (line ~339–346): `.perf-table th`, `.perf-lam`, `.perf-cal`, `.perf-empty` use dark-mode colors (`#aaa`, `#ccc`, `#888`) that are nearly invisible on the cream `--bg` surface. These must be converted to on-theme values matching the rest of the app.
- `renderPerformance` (line ~744–794): the `calNote` text reads "Not yet calibrated — need X/30 closed picks". Should read: "Tracking X picks — accuracy stats unlock at 30 graded results".
- The performance table is missing a "Units" column (net units won/lost). This can be computed client-side: `units = (r.roi / 100) * r.picks` (since ROI is stored as a percentage and 1 unit = 1 pick at flat stake). Display as `+2.3u` or `-1.1u`.

---

- [ ] **Step 1: Fix performance tab CSS**

  Find this CSS block:
  ```css
  /* ── Performance tab ─────────────────────────────────────────── */
  .perf-table { width: 100%; border-collapse: collapse; margin-bottom: 1rem; }
  .perf-table th, .perf-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #333; }
  .perf-table th { font-weight: 600; color: #aaa; font-size: 0.85rem; }
  .perf-lam { font-size: 0.9rem; color: #ccc; margin: 0.5rem 0; }
  .perf-cal { font-size: 0.82rem; color: #888; margin-top: 0.5rem; }
  .perf-empty { color: #888; padding: 2rem 0; text-align: center; }
  .roi-pos { color: #4caf50; }
  .roi-neg { color: #f44336; }
  ```
  Replace with:
  ```css
  /* ── Performance tab ─────────────────────────────────────────── */
  .perf-table { width: 100%; border-collapse: collapse; margin-bottom: 1rem; }
  .perf-table th, .perf-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
  .perf-table th { font-weight: 600; color: var(--ink-dim); font-size: 0.85rem; }
  .perf-lam { font-size: 0.9rem; color: var(--ink); margin: 0.5rem 0; }
  .perf-cal { font-size: 0.82rem; color: var(--ink-dim); margin-top: 0.5rem; }
  .perf-empty { color: var(--ink-dim); padding: 2rem 0; text-align: center; }
  .roi-pos { color: var(--positive); }
  .roi-neg { color: var(--fire); }
  ```

- [ ] **Step 2: Add "Units" column header to the table**

  In `renderPerformance`, find:
  ```js
            <th>Verdict</th><th>Side</th><th>Picks</th><th>Win %</th><th>ROI</th><th>Avg EV</th>
  ```
  Replace with:
  ```js
            <th>Verdict</th><th>Side</th><th>Picks</th><th>Win %</th><th>Units</th><th>ROI</th><th>Avg EV</th>
  ```

- [ ] **Step 3: Add "Units" value to each table row**

  In `renderPerformance`, find the zero-picks row:
  ```js
        return `<tr>
          <td><strong>${esc(r.verdict)}</strong></td>
          <td>${side}</td>
          <td colspan="4" style="color:#666">—</td>
        </tr>`;
  ```
  Replace with:
  ```js
        return `<tr>
          <td><strong>${esc(r.verdict)}</strong></td>
          <td>${side}</td>
          <td colspan="5" style="color:#666">—</td>
        </tr>`;
  ```
  (colspan 4 → 5 to cover the new column)

  Then find the data row (immediately after the zero-picks return):
  ```js
      const winPct  = r.win_pct  != null ? (r.win_pct * 100).toFixed(1) + '%' : '—';
      const roi     = r.roi      != null ? (r.roi >= 0 ? '+' : '') + r.roi.toFixed(2) + '%' : '—';
      const avgEv   = r.avg_ev   != null ? (r.avg_ev * 100).toFixed(1) + '%' : '—';
      const roiClass = r.roi != null ? (r.roi >= 0 ? 'roi-pos' : 'roi-neg') : '';
      return `<tr>
        <td><strong>${esc(r.verdict)}</strong></td>
        <td>${side}</td>
        <td>${r.picks}</td>
        <td>${winPct}</td>
        <td class="${roiClass}">${roi}</td>
        <td>${avgEv}</td>
      </tr>`;
  ```
  Replace with:
  ```js
      const winPct   = r.win_pct  != null ? (r.win_pct * 100).toFixed(1) + '%' : '—';
      const roi      = r.roi      != null ? (r.roi >= 0 ? '+' : '') + r.roi.toFixed(2) + '%' : '—';
      const avgEv    = r.avg_ev   != null ? (r.avg_ev * 100).toFixed(1) + '%' : '—';
      const roiClass = r.roi != null ? (r.roi >= 0 ? 'roi-pos' : 'roi-neg') : '';
      const unitsRaw = r.roi != null ? (r.roi / 100) * r.picks : null;
      const units    = unitsRaw != null ? (unitsRaw >= 0 ? '+' : '') + unitsRaw.toFixed(1) + 'u' : '—';
      const unitsClass = unitsRaw != null ? (unitsRaw >= 0 ? 'roi-pos' : 'roi-neg') : '';
      return `<tr>
        <td><strong>${esc(r.verdict)}</strong></td>
        <td>${side}</td>
        <td>${r.picks}</td>
        <td>${winPct}</td>
        <td class="${unitsClass}">${units}</td>
        <td class="${roiClass}">${roi}</td>
        <td>${avgEv}</td>
      </tr>`;
  ```

- [ ] **Step 4: Fix the "not yet calibrated" copy**

  Find:
  ```js
      : `<p class="perf-cal">Not yet calibrated &mdash; need ${data.total_picks}/30 closed picks</p>`;
  ```
  Replace with:
  ```js
      : `<p class="perf-cal">Tracking ${data.total_picks} pick${data.total_picks !== 1 ? 's' : ''} &mdash; accuracy stats unlock at 30 graded results</p>`;
  ```

- [ ] **Step 5: Verify in browser**

  Open the Performance tab. Confirm:
  - Table headers and text are readable on the cream background (not washed out).
  - Table has a "Units" column between "Win %" and "ROI".
  - If no calibration data: the footer reads "Tracking X picks — accuracy stats unlock at 30 graded results".
  - ROI positive = green, negative = red (using CSS vars, same as the rest of the app).

- [ ] **Step 6: Commit**

  ```bash
  git add dashboard/index.html
  git commit -m "fix: performance tab light theme, add units column, improve not-yet-calibrated copy"
  ```

---

### Task 5: Batch polish — 60s delay badge, OPP K% context, PASS count, mobile game time

Four small independent fixes bundled into one commit.

**Files:**
- Modify: `dashboard/index.html`

**Context:**
- `setFreshness` (line ~501–519): the `isPast` branch appends a `badge-delay` span reading "60s delay". This is meaningless for historical data. Remove it from that branch only (keep it on current-data branches).
- `adjBadge` (line ~587–592): renders `OPP K% +14%` with no context for "vs what". Append " vs avg" to the label so it reads `OPP K% +14% vs avg`.
- `renderProps` (line ~611–617): the "Show PASS verdicts" checkbox has no count. Compute `passCount` and show it in the label.
- `adj-row` CSS (line ~243–248) + game-time (line ~260–263): on narrow screens the game time wraps to a new line and loses its right-alignment. Fix with `flex-wrap: nowrap` on `.adj-row` and add `overflow: hidden` + `text-overflow: ellipsis` on the badges if needed, or move game time to its own line with `width: 100%` when wrapped.

---

- [ ] **Step 1: Remove "60s delay" badge from past-date branch in `setFreshness`**

  Find (in the `isPast` branch):
  ```js
      badge.innerHTML = '<span class="badge-ok">' + dateLabel + ' · ' + timeLabel + '</span><span class="badge-delay">60s delay</span>';
  ```
  Replace with:
  ```js
      badge.innerHTML = '<span class="badge-ok">' + dateLabel + ' · ' + timeLabel + '</span>';
  ```

- [ ] **Step 2: Add "vs avg" context to OPP K% badge**

  Find `adjBadge`:
  ```js
  function adjBadge(label, actual, avg) {
    const pct  = ((actual - avg) / avg * 100).toFixed(0);
    const sign = pct > 0 ? '+' : '';
    const cls  = pct > 0 ? 'adj-pos' : (pct < 0 ? 'adj-neg' : 'adj-neutral');
    return `<span class="adj-badge ${cls}">${label} ${sign}${pct}%</span>`;
  }
  ```
  Replace with:
  ```js
  function adjBadge(label, actual, avg) {
    const pct  = ((actual - avg) / avg * 100).toFixed(0);
    const sign = pct > 0 ? '+' : '';
    const cls  = pct > 0 ? 'adj-pos' : (pct < 0 ? 'adj-neg' : 'adj-neutral');
    return `<span class="adj-badge ${cls}">${label} ${sign}${pct}% vs avg</span>`;
  }
  ```

- [ ] **Step 3: Add PASS count to the "Show PASS verdicts" checkbox label**

  In `renderProps`, find the passCount computation location. The `sorted` array is already built. Add the count before the `hasAction` block:

  Find (right after `const hasAction = ...`):
  ```js
    const hasAction = sorted.some(p => bestSide(p).verdict !== 'PASS');
    let html = '';
  ```
  Replace with:
  ```js
    const hasAction = sorted.some(p => bestSide(p).verdict !== 'PASS');
    const passCount = sorted.filter(p => bestSide(p).verdict === 'PASS').length;
    let html = '';
  ```

  Then find the checkbox label:
  ```js
        <label>
          <input type="checkbox" id="show-all" onchange="togglePassCards()">
          Show PASS verdicts
        </label>
  ```
  Replace with:
  ```js
        <label>
          <input type="checkbox" id="show-all" onchange="togglePassCards()">
          Show PASS verdicts${passCount > 0 ? ` (${passCount})` : ''}
        </label>
  ```

- [ ] **Step 4: Fix game time wrapping on mobile**

  The `.adj-row` is `flex-wrap: wrap` (inherited from the `flex` default). The `game-time` uses `margin-left: auto` which only works when it's on the same line. Fix by making the game time its own row when it would wrap, by giving it `flex-basis: 100%` and `text-align: right` when wrapped, OR by making adj-row `nowrap` and letting badges truncate.

  The simplest correct fix: give `.game-time` `flex-shrink: 0` so it never gets squeezed off, and add `min-width: 0` to the badge group so they truncate instead.

  Find the `.game-time` CSS rule:
  ```css
  .game-time {
    font-size: 10px;
    color: var(--ink-dim);
    margin-left: auto;
  }
  ```
  Replace with:
  ```css
  .game-time {
    font-size: 10px;
    color: var(--ink-dim);
    margin-left: auto;
    flex-shrink: 0;
    white-space: nowrap;
  }
  ```

  Also add `min-width: 0` to `.adj-row` so flex children can shrink:
  Find:
  ```css
  .adj-row {
    padding: 7px 12px;
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }
  ```
  Replace with:
  ```css
  .adj-row {
    padding: 7px 12px;
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
    min-width: 0;
  }
  ```

- [ ] **Step 5: Verify in browser**

  - Switch to a past date: confirm the freshness badge shows no "60s delay".
  - On a current date: confirm "60s delay" still appears.
  - Check OPP K% badge — should read "OPP K% +14% vs avg".
  - If there are PASS verdicts hidden: label reads "Show PASS verdicts (N)".
  - Narrow the browser window to ~375px: confirm game time stays right-aligned and doesn't orphan on its own line (the badges shrink/wrap first).

- [ ] **Step 6: Commit**

  ```bash
  git add dashboard/index.html
  git commit -m "fix: remove 60s delay on past dates, add OPP K% context, PASS count in checkbox, game time mobile fix"
  ```

---

## Testing Strategy

All tasks modify `dashboard/index.html` only. Since there is no JS test harness for the dashboard, verification is browser-based:

1. Open `dashboard/index.html` directly in Chrome (file:// protocol triggers `IS_LOCAL=true`, uses local data files).
2. For live data verification: check the deployed Netlify URL after pushing to `main`.
3. For past-date verification: use the date picker to select a date that has a historical JSON file in `dashboard/data/processed/`.

There are no pytest tests to write for this task — the existing Python test suite in `tests/` is unaffected.

---

## Commit Summary

| Task | Commit message |
|------|---------------|
| 1 | `fix: date picker max=tomorrow, rename Props→Picks tab, remove 'today' on past dates` |
| 2 | `fix: rename lambda stat to Proj K with line context, flip price delta arrow direction` |
| 3 | `fix: add bridging note in watchlist when steam side conflicts with model verdict` |
| 4 | `fix: performance tab light theme, add units column, improve not-yet-calibrated copy` |
| 5 | `fix: remove 60s delay on past dates, add OPP K% context, PASS count in checkbox, game time mobile fix` |
