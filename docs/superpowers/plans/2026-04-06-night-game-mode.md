# Night Game Mode Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a day/night theme toggle to the dashboard with a restructured top bar layout.

**Architecture:** All changes are in a single file — `dashboard/index.html` — which contains HTML structure, CSS, and JavaScript in one self-contained page. There are no build tools; edits take effect immediately in the browser. The dark theme uses `[data-theme='dark']` CSS selector to override 5 CSS variables plus targeted hardcoded colors. A small IIFE in `<head>` prevents flash of light theme on load. Changes are organized into 4 logical tasks, each committed independently.

**Tech Stack:** Vanilla HTML/CSS/JS, Phosphor icons (already loaded), localStorage

---

## File Map

| File | What changes |
|------|-------------|
| `dashboard/index.html` | All 4 tasks — CSS, HTML, and JS |

No other files are touched. No Python tests affected (dashboard has no test harness).

---

## Spec

`docs/superpowers/specs/2026-04-06-night-game-mode-design.md`

---

### Task 1: Dark theme CSS — variable overrides + hardcoded color overrides

Add the `[data-theme='dark']` CSS block and delete the unused `.badge-delay` class.

**Files:**
- Modify: `dashboard/index.html` (CSS section, lines 11–390)

---

- [ ] **Step 1: Add `[data-theme='dark']` variable overrides after `:root`**

  In `dashboard/index.html`, find this block (lines 12–21):
  ```css
    :root {
      --bg:        #f5f0e8;
      --surface:   #faf6ee;
      --border:    #d0c8b8;
      --ink:       #1a1a1a;
      --ink-dim:   #888888;
      --fire:      #c0392b;
      --positive:  #27ae60;
      --tab-h:     58px;
    }
  ```

  Immediately after the closing `}`, add:

  ```css

    [data-theme='dark'] {
      --bg:      #0d1929;
      --surface: #132035;
      --border:  #1e3050;
      --ink:     #f0ede6;
      --ink-dim: #6b7f99;
    }

    /* ── Dark mode targeted overrides ───────────────────────── */
    [data-theme='dark'] #top-bar { background: #080f1a; border-bottom-color: #1e3050; }
    [data-theme='dark'] #nav { background: #080f1a; border-top-color: #1e3050; }
    [data-theme='dark'] .nav-btn { color: #6b7f99; }
    [data-theme='dark'] .card-header {
      background: repeating-linear-gradient(45deg, #080f1a, #080f1a 2px, #0d1929 2px, #0d1929 8px);
    }
    [data-theme='dark'] .pitcher-card {
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 3px rgba(0,0,0,0.3);
    }
    [data-theme='dark'] .pitcher-matchup { color: #6b7f99; }
    [data-theme='dark'] .adj-pos { background: #0d2b1a; border-color: #1a5c35; }
    [data-theme='dark'] .adj-neg { background: #2b0d0d; border-color: #5c1a1a; }
    [data-theme='dark'] .adj-neutral { background: #132035; border-color: #1e3050; color: #6b7f99; }
    [data-theme='dark'] .verdict-pass { background: #1e3050; color: #6b7f99; }
    [data-theme='dark'] .badge-started { background: #1e3050 !important; color: #6b7f99 !important; }
    [data-theme='dark'] .banner-info { background: #0d2b1a; border-bottom-color: #1a5c35; color: #f0ede6; }
    [data-theme='dark'] .banner-warn { background: #2b1f0d; border-bottom-color: #5c3d1a; color: #f0ede6; }
    [data-theme='dark'] #date-select { border-color: #1e3050; }
    [data-theme='dark'] #date-select:focus { border-color: #6b7f99; }
  ```

- [ ] **Step 2: Delete the `.badge-delay` CSS class**

  Find and remove this entire block (lines 85–93):
  ```css
    .badge-delay {
      background: #555;
      color: #ccc;
      padding: 2px 8px;
      border-radius: 3px;
      font-size: 10px;
      font-family: monospace;
      margin-left: 6px;
    }
  ```

- [ ] **Step 3: Add theme toggle button CSS and scoped freshness badge override**

  Find this comment (line 103):
  ```css
    /* ── Date selector ──────────────────────────────────────── */
  ```

  Insert before it:
  ```css
    /* ── Theme toggle ──────────────────────────────────────── */
    #theme-toggle {
      background: none;
      border: none;
      cursor: pointer;
      font-size: 18px;
      padding: 0;
      line-height: 1;
      color: #fff;
    }

    /* Freshness badge — scoped overrides for relocated badge under wordmark */
    #freshness-badge .badge-ok,
    #freshness-badge .badge-warn { font-size: 10px; padding: 1px 6px; }

  ```

  **Note:** The toggle uses `color: #fff` (not `var(--bg)`) because the top bar is always a dark background regardless of theme. Using `var(--bg)` would make the icon invisible in dark mode (`--bg` becomes dark navy).

- [ ] **Step 5: Update `#date-row` CSS for centering**

  Find (lines 104–106):
  ```css
    #date-row {
      display: none;   /* shown by JS when dates exist */
    }
  ```

  Replace with:
  ```css
    #date-row {
      display: none;   /* shown by JS when dates exist */
      flex: 1;
      justify-content: center;
    }
  ```

- [ ] **Step 6: Verify in browser (light mode)**

  Open `dashboard/index.html` locally. Confirm the existing light mode looks identical — the new CSS should have no effect without `data-theme="dark"` on `<html>`.

- [ ] **Step 7: Commit**

  ```bash
  git add dashboard/index.html
  git commit -m "feat: add dark theme CSS overrides, delete badge-delay class"
  ```

---

### Task 2: Top bar HTML restructure — move freshness badge, center date picker, add toggle

Restructure the `#top-row` HTML and add the theme-restore IIFE in `<head>`.

**Files:**
- Modify: `dashboard/index.html` (HTML section, lines 391–437; `<head>` section)

---

- [ ] **Step 1: Update `#top-right` CSS for new layout**

  The `#top-right` element previously held the date picker and freshness badge (stacked vertically). Now it holds only the theme toggle button. Update its CSS to match.

  Find this CSS block:
  ```css
    /* ── Top-right cluster ───────────────────────────────────── */
    #top-right {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 4px;
    }
  ```

  Replace with:
  ```css
    /* ── Top-right cluster ───────────────────────────────────── */
    #top-right {
      display: flex;
      align-items: center;
    }
  ```

- [ ] **Step 2: Add theme-restore IIFE in `<head>`**

  Find (line 390 — note the 2-space indentation):
  ```html
    </style>
  </head>
  ```

  Replace with:
  ```html
    </style>
  <script>
  (function() {
    var saved = 'light';
    try { saved = localStorage.getItem('theme') || 'light'; } catch(e) {}
    document.documentElement.setAttribute('data-theme', saved);
    document.addEventListener('DOMContentLoaded', function() {
      document.getElementById('theme-toggle').innerHTML =
        saved === 'dark' ? '<i class="ph-bold ph-sun"></i>' : '<i class="ph-bold ph-moon"></i>';
    });
  })();
  </script>
  </head>
  ```

- [ ] **Step 3: Restructure `#top-row` HTML**

  Find the entire top-row block (lines 396–410):
  ```html
    <div id="top-row">
      <div id="title-date">
        <svg class="k-mark" width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="14" cy="14" r="12" stroke="var(--fire)" stroke-width="2"/>
          <text x="14" y="19" text-anchor="middle" font-family="Oswald, sans-serif" font-weight="700" font-size="14" fill="#fff">K</text>
        </svg>
        <span class="wordmark-bottom">Betting Edge</span>
      </div>
      <div id="top-right">
        <div id="date-row">
          <input type="date" id="date-select" onchange="onDateChange(this.value)" />
        </div>
        <span id="freshness-badge"></span>
      </div>
    </div>
  ```

  Replace with:
  ```html
    <div id="top-row">
      <div id="title-date">
        <svg class="k-mark" width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="14" cy="14" r="12" stroke="var(--fire)" stroke-width="2"/>
          <text x="14" y="19" text-anchor="middle" font-family="Oswald, sans-serif" font-weight="700" font-size="14" fill="#fff">K</text>
        </svg>
        <div>
          <span class="wordmark-bottom">Betting Edge</span>
          <span id="freshness-badge" style="display:block;font-size:10px;color:#6b7f99;font-family:'IBM Plex Mono',monospace;margin-top:1px"></span>
        </div>
      </div>
      <div id="date-row">
        <input type="date" id="date-select" onchange="onDateChange(this.value)" />
      </div>
      <div id="top-right">
        <button id="theme-toggle" onclick="toggleTheme()" title="Day game / Night game"></button>
      </div>
    </div>
  ```

  **What changed:**
  - `.wordmark-bottom` and `#freshness-badge` are wrapped in a `<div>` for vertical stacking
  - `#freshness-badge` moved from `#top-right` to the title cluster with inline styles for the muted status line
  - `#date-row` is now a direct child of `#top-row` (between title and top-right) for flex centering
  - `#top-right` now contains only the theme toggle button

- [ ] **Step 4: Verify in browser**

  Open `dashboard/index.html`. Confirm:
  - The freshness badge appears below "Betting Edge" as a small muted line
  - The date picker is centered in the top bar
  - The theme toggle button area exists on the right (icon won't appear yet until the IIFE runs — if the page is fresh/no localStorage, you may see an empty button)
  - Overall top bar layout: brand+status on left, date center, toggle right

- [ ] **Step 5: Commit**

  ```bash
  git add dashboard/index.html
  git commit -m "feat: restructure top bar — freshness under wordmark, centered date, theme toggle"
  ```

---

### Task 3: JavaScript — toggle function + setFreshness cleanup

Add the `toggleTheme()` function and remove all "60s delay" badge output from `setFreshness()`.

**Files:**
- Modify: `dashboard/index.html` (JS section)

---

- [ ] **Step 1: Add `toggleTheme()` function**

  Find this exact block (the closing brace of `esc()` followed by the Config comment):
  ```javascript
    }

    // ── Config ────────────────────────────────────────────────
  ```

  Replace with:
  ```javascript
    }

    // ── Theme toggle ───────────────────────────────────────────
    function toggleTheme() {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      const next = isDark ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      document.getElementById('theme-toggle').innerHTML =
        next === 'dark' ? '<i class="ph-bold ph-sun"></i>' : '<i class="ph-bold ph-moon"></i>';
      try { localStorage.setItem('theme', next); } catch(e) {}
    }

    // ── Config ────────────────────────────────────────────────
  ```

- [ ] **Step 2: Remove "60s delay" from stale-data branch in `setFreshness()`**

  Find (line 569):
  ```javascript
      badge.innerHTML = '<span class="badge-warn">Data may be outdated</span><span class="badge-delay">60s delay</span>';
  ```

  Replace with:
  ```javascript
      badge.innerHTML = '<span class="badge-warn">Data may be outdated</span>';
  ```

- [ ] **Step 3: Remove "60s delay" from fresh-data branch in `setFreshness()`**

  Find (line 573):
  ```javascript
      badge.innerHTML = '<span class="badge-ok">Updated ' + time + '</span><span class="badge-delay">60s delay</span>';
  ```

  Replace with:
  ```javascript
      badge.innerHTML = '<span class="badge-ok">Updated ' + time + '</span>';
  ```

- [ ] **Step 4: Verify in browser**

  Open `dashboard/index.html`. Confirm:
  - The moon icon (☽) appears in the top right
  - Clicking it switches to dark mode — the entire UI changes to the dark navy palette
  - Clicking again switches back to light mode
  - The freshness badge shows "Updated X:XX PM" with no "60s delay" suffix
  - On a past date: no "60s delay" (this was already fixed earlier, just confirm)
  - Refresh the page — theme preference persists

- [ ] **Step 5: Commit**

  ```bash
  git add dashboard/index.html
  git commit -m "feat: add toggleTheme() function, remove 60s delay badge from setFreshness"
  ```

---

### Task 4: Visual verification — walk through every element in dark mode

No code changes. Systematic check that every element looks correct in dark mode.

**Files:**
- None (verification only)

---

- [ ] **Step 1: Verify Picks tab in dark mode**

  Toggle to dark mode, navigate to today's data. Check:
  - Page background is deep navy (#0d1929)
  - "N pitchers today" section header: text is `--ink-dim` blue-gray, red underline accent visible
  - Pitcher cards: navy surface, navy border, dark card header with diagonal stripe
  - Pitcher name: warm white on dark header
  - Pitcher matchup: muted blue-gray (`#6b7f99`) on dark header
  - Stat values (Line, Proj K, EV): warm white text
  - Stat labels: blue-gray muted text
  - FIRE 2u badge: red with white text (same as light mode)
  - LEAN badge: orange border, orange text on transparent background (readable on navy)
  - PASS badge: navy background, blue-gray text
  - Adjustment badges: dark green/dark red/navy backgrounds with colored borders
  - EV border-left: red and orange visible on navy card surface
  - Game time: blue-gray muted text
  - "Show PASS verdicts" checkbox: text readable

- [ ] **Step 2: Verify Watchlist tab in dark mode**

  Switch to Watchlist tab. Check:
  - Watch cards: navy surface, navy border
  - Pitcher names: `var(--ink)` warm white
  - Odds text: `var(--ink-dim)` blue-gray
  - Delta arrows: red (`var(--fire)`) still visible
  - Bridging note (if any): italic blue-gray

- [ ] **Step 3: Verify Performance tab in dark mode**

  Switch to Performance tab. Check:
  - Table headers: blue-gray text
  - Table borders: navy border
  - ROI positive: green (`var(--positive)`)
  - ROI negative: red (`var(--fire)`)
  - Units column: same green/red
  - Lambda accuracy text: warm white
  - Calibration note: blue-gray

- [ ] **Step 4: Verify top bar + nav in dark mode**

  Check:
  - Top bar: very dark navy (#080f1a), border is `#1e3050`
  - Wordmark: white text (unchanged)
  - Freshness badge: small green/orange badge on dark background
  - Date picker: border visible (`#1e3050`), text readable
  - Theme toggle: sun icon visible in warm white
  - Bottom nav: very dark navy, inactive tabs are blue-gray, active tab has fire-red top border

- [ ] **Step 5: Verify banners in dark mode**

  If you can trigger a banner (load with stale data or manually call `showBanner()`):
  - Info banner: dark green background, green border, warm white text
  - Warn banner: dark amber background, amber border, warm white text

- [ ] **Step 6: Verify light mode is unchanged**

  Toggle back to light mode. Do a quick scan:
  - Cream background is back
  - All cards, badges, text look identical to before this feature
  - No visual regressions

- [ ] **Step 7: Final commit (if any fixes were needed)**

  If any fixes were made during verification:
  ```bash
  git add dashboard/index.html
  git commit -m "fix: dark mode visual adjustments from verification pass"
  ```

  If no fixes needed, skip this step.

---

## Commit Summary

| Task | Commit message |
|------|---------------|
| 1 | `feat: add dark theme CSS overrides, delete badge-delay class` |
| 2 | `feat: restructure top bar — freshness under wordmark, centered date, theme toggle` |
| 3 | `feat: add toggleTheme() function, remove 60s delay badge from setFreshness` |
| 4 | `fix: dark mode visual adjustments from verification pass` (only if needed) |
