# V2 Line Movement And Card Cues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fake v2 movement bars with a real FanDuel picked-side movement chart, surface K-line movement in the same module, add blue `OVER` card rails, and add park factor to the "Why this bet" section.

**Architecture:** Keep the UI pass small and truthful. Put movement parsing and chart-series preparation into a tiny plain-JS helper that works both in the browser and in Node tests, then wire the v2 sheet to use that helper and render a compact SVG chart. The browser keeps using checked-in `v2-app.js`, generated from `v2-app.jsx` with the existing Babel flow documented in `v2.html`.

**Tech Stack:** Plain browser JS, React UMD, Node built-in test runner (`node --test`), Babel CLI, existing `dashboard/data/processed/steam.json`, `dashboard/v2.html`, `dashboard/v2-app.jsx`, `dashboard/v2-app.js`.

---

## File structure

**Create**
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-movement-helpers.js`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-movement-helpers.test.mjs`

**Modify**
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2.html`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-app.jsx`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-app.js`

**Read for live verification**
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/data/processed/steam.json`

---

### Task 1: Create testable movement-history helpers

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-movement-helpers.js`
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-movement-helpers.test.mjs`

- [ ] **Step 1: Write the failing helper tests**

```js
import test from "node:test";
import assert from "node:assert/strict";
import {
  buildPickedSideMovement,
  summarizeLineMovement,
  parkFactorTone,
} from "./v2-movement-helpers.js";

const steam = {
  snapshots: [
    {
      t: "2026-04-28T00:00:00Z",
      pitchers: {
        "Shohei Ohtani": {
          k_line: 6.5,
          FanDuel: { over: -110, under: -118 },
        },
      },
    },
    {
      t: "2026-04-28T03:00:00Z",
      pitchers: {
        "Shohei Ohtani": {
          k_line: 7.5,
          FanDuel: { over: +102, under: -122 },
        },
      },
    },
  ],
};

test("buildPickedSideMovement returns FanDuel picked-side odds and k-line points", () => {
  const result = buildPickedSideMovement(steam, {
    pitcher: "Shohei Ohtani",
    direction: "OVER",
  });

  assert.equal(result.book, "FanDuel");
  assert.equal(result.direction, "OVER");
  assert.deepEqual(
    result.points.map((p) => ({ odds: p.odds, kLine: p.kLine })),
    [
      { odds: -110, kLine: 6.5 },
      { odds: 102, kLine: 7.5 },
    ],
  );
});

test("buildPickedSideMovement returns empty state when there are fewer than two usable points", () => {
  const result = buildPickedSideMovement(
    { snapshots: [steam.snapshots[0]] },
    { pitcher: "Shohei Ohtani", direction: "OVER" },
  );

  assert.equal(result.ready, false);
  assert.equal(result.reason, "insufficient_history");
});

test("summarizeLineMovement reports line change when k-line moved", () => {
  const movement = buildPickedSideMovement(steam, {
    pitcher: "Shohei Ohtani",
    direction: "OVER",
  });

  assert.deepEqual(summarizeLineMovement(movement), {
    lineMoved: true,
    openingLine: 6.5,
    currentLine: 7.5,
    openingOdds: -110,
    currentOdds: 102,
  });
});

test("parkFactorTone marks OVER-friendly parks as positive for OVER picks", () => {
  assert.equal(parkFactorTone(1.08, "OVER"), "pos");
  assert.equal(parkFactorTone(1.08, "UNDER"), "neg");
  assert.equal(parkFactorTone(0.94, "UNDER"), "pos");
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
node --test dashboard/v2-movement-helpers.test.mjs
```

Expected: FAIL because `dashboard/v2-movement-helpers.js` does not exist yet.

- [ ] **Step 3: Implement the minimal helper module**

```js
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) {
    module.exports = factory();
    return;
  }
  root.V2MovementHelpers = factory();
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  function buildPickedSideMovement(steam, pick) {
    const snapshots = Array.isArray(steam?.snapshots) ? steam.snapshots : [];
    const points = [];

    for (const snap of snapshots) {
      const entry = snap?.pitchers?.[pick.pitcher];
      const odds = entry?.FanDuel?.[pick.direction === "OVER" ? "over" : "under"];
      const kLine = entry?.k_line;
      if (odds == null || kLine == null || !snap?.t) continue;
      points.push({
        t: snap.t,
        odds,
        kLine,
      });
    }

    if (points.length < 2) {
      return {
        ready: false,
        reason: "insufficient_history",
        book: "FanDuel",
        direction: pick.direction,
        points,
      };
    }

    return {
      ready: true,
      reason: null,
      book: "FanDuel",
      direction: pick.direction,
      points,
    };
  }

  function summarizeLineMovement(movement) {
    const first = movement?.points?.[0];
    const last = movement?.points?.[movement.points.length - 1];
    if (!first || !last) return null;
    return {
      lineMoved: first.kLine !== last.kLine,
      openingLine: first.kLine,
      currentLine: last.kLine,
      openingOdds: first.odds,
      currentOdds: last.odds,
    };
  }

  function parkFactorTone(parkFactor, direction) {
    if (parkFactor == null) return "neutral";
    if (parkFactor > 1.02) return direction === "OVER" ? "pos" : "neg";
    if (parkFactor < 0.98) return direction === "UNDER" ? "pos" : "neg";
    return "neutral";
  }

  return {
    buildPickedSideMovement,
    summarizeLineMovement,
    parkFactorTone,
  };
});
```

- [ ] **Step 4: Re-run the helper tests**

Run:

```bash
node --test dashboard/v2-movement-helpers.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit the helper foundation**

```bash
git add dashboard/v2-movement-helpers.js dashboard/v2-movement-helpers.test.mjs
git commit -m "feat(ui): add v2 movement helper foundation"
```

---

### Task 2: Wire the real movement chart into the v2 sheet

**Files:**
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2.html`
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-app.jsx`
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-app.js`

- [ ] **Step 1: Load the helper before the app bundle**

Update the bottom of `dashboard/v2.html`:

```html
  <script src="v2-data.js"></script>
  <script src="v2-movement-helpers.js"></script>
  <script src="v2-app.js" defer></script>
```

- [ ] **Step 2: Replace the fake bar generation with real movement extraction**

In `dashboard/v2-app.jsx`, remove the synthetic section:

```jsx
  // Line movement: fake a 12-step history from open → current
  const moveSteps = 12;
  const delta = (p.k_line - p.opening_line);
  const bars = Array.from({ length: moveSteps }, (_, i) => {
    const t = i / (moveSteps - 1);
    const noise = (Math.sin(i * 1.3) * 0.15) - (i * 0.02);
    const v = 0.5 + (delta * 0.4 * t) + noise;
    return Math.max(0.15, Math.min(1, v));
  });
```

and replace it with:

```jsx
  const movement = window.V2MovementHelpers.buildPickedSideMovement(window.STEAM_DATA || {}, {
    pitcher: p.pitcher,
    direction: best.direction,
  });
  const movementSummary = window.V2MovementHelpers.summarizeLineMovement(movement);
```

- [ ] **Step 3: Add a small inline SVG chart component**

Add a compact sheet-local component in `dashboard/v2-app.jsx`:

```jsx
function MovementChart({ movement }) {
  if (!movement?.ready) {
    return <div className="v2-move-empty">Not enough FanDuel history yet</div>;
  }

  const points = movement.points;
  const width = 280;
  const height = 92;
  const topPad = 10;
  const lineBandTop = 58;
  const lineBandBottom = 82;
  const odds = points.map((p) => p.odds);
  const lines = points.map((p) => p.kLine);
  const minOdds = Math.min(...odds);
  const maxOdds = Math.max(...odds);
  const minLine = Math.min(...lines);
  const maxLine = Math.max(...lines);
  const xFor = (idx) => points.length === 1 ? width / 2 : (idx / (points.length - 1)) * width;
  const yForOdds = (val) => {
    if (minOdds === maxOdds) return topPad + 18;
    return topPad + ((maxOdds - val) / (maxOdds - minOdds)) * 36;
  };
  const yForLine = (val) => {
    if (minLine === maxLine) return (lineBandTop + lineBandBottom) / 2;
    return lineBandTop + ((maxLine - val) / (maxLine - minLine)) * (lineBandBottom - lineBandTop);
  };

  const oddsPath = points
    .map((pt, idx) => `${idx === 0 ? "M" : "L"} ${xFor(idx).toFixed(1)} ${yForOdds(pt.odds).toFixed(1)}`)
    .join(" ");

  const linePath = points
    .map((pt, idx) => `${idx === 0 ? "M" : "L"} ${xFor(idx).toFixed(1)} ${yForLine(pt.kLine).toFixed(1)}`)
    .join(" ");

  return (
    <div className="v2-move-chart-wrap">
      <svg className="v2-move-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <path d={oddsPath} className="v2-move-odds-line" />
        <path d={linePath} className="v2-move-kline-step" />
      </svg>
    </div>
  );
}
```

- [ ] **Step 4: Render the chart and line-move badge in the sheet**

Replace the fake movement strip section with:

```jsx
        <div className="v2-sheet-section">
          <div className="h">
            {`FanDuel · ${best.direction} · open to now`}
            {movementSummary?.lineMoved && (
              <span className="v2-line-move-badge">
                {`line moved ${movementSummary.openingLine} -> ${movementSummary.currentLine}`}
              </span>
            )}
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Opening line</span>
            <span className="val">{p.opening_line} · {fmtOdds(p.opening_over_odds)}/{fmtOdds(p.opening_under_odds)}</span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Current line</span>
            <span className="val">{p.k_line} · {fmtOdds(sideOver.odds)}/{fmtOdds(sideUnder.odds)}</span>
          </div>
          <MovementChart movement={movement} />
        </div>
```

- [ ] **Step 5: Rebuild the checked-in browser file**

Run:

```bash
cd dashboard
npx babel v2-app.jsx --presets=@babel/preset-react -o v2-app.js
```

Expected: `dashboard/v2-app.js` updates without syntax errors.

- [ ] **Step 6: Run a syntax smoke check on the compiled file**

Run:

```bash
node --check dashboard/v2-app.js
```

Expected: PASS with no output.

- [ ] **Step 7: Commit the chart wiring**

```bash
git add dashboard/v2.html dashboard/v2-app.jsx dashboard/v2-app.js
git commit -m "feat(ui): replace fake v2 movement bars with real chart"
```

---

### Task 3: Add blue OVER rails and park factor evidence row

**Files:**
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-app.jsx`
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-app.js`

- [ ] **Step 1: Update card modifier classes so OVER picks get a distinct rail**

Add direction-aware card state logic in `PickCard`:

```jsx
  const directionMod =
    side.verdict === "PASS"
      ? "pass"
      : side.direction === "OVER"
        ? "over-pick"
        : "under-pick";
  const cardMod = started ? "final" : `${cls} ${directionMod}`;
```

- [ ] **Step 2: Add the corresponding visual rules**

In the style block used by v2, add rules like:

```css
.v2-card.over-pick { border-left: 4px solid var(--pos); }
.v2-card.under-pick { border-left: 4px solid var(--neg); }
.v2-line-move-badge {
  margin-left: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--ink-dim);
}
.v2-move-chart-wrap { margin-top: 10px; }
.v2-move-chart { width: 100%; height: 92px; display: block; }
.v2-move-odds-line { fill: none; stroke: var(--ink); stroke-width: 2.2; }
.v2-move-kline-step { fill: none; stroke: var(--accent); stroke-width: 1.5; stroke-dasharray: 4 3; }
.v2-move-empty {
  margin-top: 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--ink-dim);
}
```

- [ ] **Step 3: Add park factor to the “Why this bet” section**

Add a row in the sheet after lineup / ump using the helper tone:

```jsx
          <div className="v2-stat-row">
            <span className="lbl">Park factor</span>
            {p.park_factor != null ? (
              <span className={`val ${window.V2MovementHelpers.parkFactorTone(p.park_factor, best.direction)}`}>
                {p.park_factor.toFixed(2)}
              </span>
            ) : (
              <span className="val" style={{ color: "var(--ink-dim)" }}>Unknown</span>
            )}
          </div>
```

- [ ] **Step 4: Rebuild the checked-in JS again**

Run:

```bash
cd dashboard
npx babel v2-app.jsx --presets=@babel/preset-react -o v2-app.js
node --check v2-app.js
```

Expected: both commands succeed.

- [ ] **Step 5: Commit the directional/evidence polish**

```bash
git add dashboard/v2-app.jsx dashboard/v2-app.js
git commit -m "feat(ui): add over rails and park factor evidence"
```

---

### Task 4: Verify in the browser against real data

**Files:**
- Read live: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/data/processed/steam.json`
- Open: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2.html`

- [ ] **Step 1: Open the v2 dashboard locally and inspect a pitcher with FanDuel history**

Verify:
- chart appears instead of fake bars
- chart title matches picked side
- odds line renders
- K-line track renders

- [ ] **Step 2: Inspect a pitcher with insufficient history**

Verify:
- empty state says `Not enough FanDuel history yet`
- opening/current text rows still appear

- [ ] **Step 3: Check card rail parity**

Verify:
- `UNDER` cards still show red rail
- `OVER` cards now show blue rail

- [ ] **Step 4: Check the “Why this bet” section**

Verify:
- park factor row appears
- tone changes correctly for at least one `OVER` and one `UNDER` pick
- mobile sheet still fits without overflow

- [ ] **Step 5: Commit after verification if no fixes are needed**

```bash
git status
git add dashboard/v2.html dashboard/v2-app.jsx dashboard/v2-app.js dashboard/v2-movement-helpers.js dashboard/v2-movement-helpers.test.mjs
git commit -m "feat(ui): ship truthful v2 movement chart and card cues"
```

---

## Success criteria

This plan is successful when:

1. The v2 detail sheet shows a real picked-side FanDuel history chart
2. K-line movement is visible when the market line itself moved
3. No fake interpolation remains
4. `OVER` cards have a blue left rail and `UNDER` cards keep the red rail
5. Park factor appears in the “Why this bet” section
6. Helper logic has automated Node tests
7. The compiled `v2-app.js` stays in sync with `v2-app.jsx`

---

## Final handoff

After this UI pass lands, the next related follow-up should be optional, not immediate:

- only add dual-side or multi-book movement views if the picked-side FanDuel chart proves genuinely useful
- do not expand this into a broader charting subsystem unless usage or evaluation work clearly asks for it
