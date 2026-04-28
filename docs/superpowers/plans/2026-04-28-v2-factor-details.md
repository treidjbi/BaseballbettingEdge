# V2 Factor Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsed `Factor details` section to the v2 pick detail sheet that exposes all major lambda drivers with `active` / `neutral` / `missing` status while keeping the default sheet compact and readable.

**Architecture:** Keep `PickDetail` as the owner of the detail sheet, but move factor normalization and status derivation into a small pure helper so the UI does not accumulate a large conditional tree. Use existing v2 data fields wherever possible, render the current summary unchanged, and add one disclosure section for the full factor audit.

**Tech Stack:** React 18 UMD + JSX compiled to browser JS, static `dashboard/` assets, Node built-in test runner, Babel standalone rebuild flow for `v2-app.js`.

---

### Task 1: Normalize factor detail rows in a pure helper

**Files:**
- Create: `C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\v2-factor-details.js`
- Create: `C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\v2-factor-details.test.mjs`
- Modify: `C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\v2.html`

- [ ] **Step 1: Write the failing helper tests**

Create `dashboard/v2-factor-details.test.mjs` with focused expectations for:
- grouped output shape
- `active` / `neutral` / `missing` statuses
- picked-side tone derivation
- graceful handling of null/neutral data

```js
import test from "node:test";
import assert from "node:assert/strict";
import { buildFactorGroups } from "./v2-factor-details.js";

test("buildFactorGroups marks confirmed lineup and nonzero ump as active", () => {
  const groups = buildFactorGroups({
    k_line: 4.5,
    lambda: 5.1,
    lineup_used: true,
    ump_k_adj: 0.18,
    umpire: "Mark Wegner",
    park_factor: 1.04,
    opp_k_rate: 0.248,
    season_k9: 9.2,
    recent_k9: 10.1,
    career_k9: 8.7,
    swstr_pct: 0.132,
    swstr_delta_k9: 0.28,
    days_since_last_start: 5,
    last_pitch_count: 94,
    rest_k9_delta: 0.0,
    data_complete: true,
    ev_over: { ev: 0.141, adj_ev: 0.136, edge: 0.062 },
    ev_under: { ev: -0.19, adj_ev: -0.19, edge: -0.08 },
  }, "OVER");

  const env = groups.find((g) => g.key === "environment");
  assert.equal(env.rows.find((r) => r.key === "lineup").status, "active");
  assert.equal(env.rows.find((r) => r.key === "ump").status, "active");
});

test("buildFactorGroups marks projected lineup and missing ump as missing", () => {
  const groups = buildFactorGroups({
    k_line: 4.5,
    lambda: 4.44,
    lineup_used: false,
    ump_k_adj: 0,
    umpire: null,
    park_factor: 0.99,
    opp_k_rate: 0.196,
    season_k9: 7.3,
    recent_k9: 7.3,
    career_k9: 9.1,
    swstr_pct: 0.108,
    swstr_delta_k9: 0.0,
    days_since_last_start: 5,
    last_pitch_count: 91,
    rest_k9_delta: 0.0,
    data_complete: true,
    ev_over: { ev: -0.225, adj_ev: -0.225, edge: -0.096 },
    ev_under: { ev: 0.1287, adj_ev: 0.1287, edge: 0.062 },
  }, "UNDER");

  const env = groups.find((g) => g.key === "environment");
  assert.equal(env.rows.find((r) => r.key === "lineup").status, "missing");
  assert.equal(env.rows.find((r) => r.key === "ump").status, "missing");
});
```

- [ ] **Step 2: Run the tests to confirm failure**

Run:

```powershell
node --test dashboard/v2-factor-details.test.mjs
```

Expected: fail because `dashboard/v2-factor-details.js` does not exist yet.

- [ ] **Step 3: Implement the helper**

Create `dashboard/v2-factor-details.js` as a pure shared helper that:
- exports `buildFactorGroups(pick, direction)`
- exports `factorStatus(...)` helpers if useful
- attaches itself to `window.V2FactorDetails`
- groups rows into:
  - `projection-core`
  - `opponent-context`
  - `pitcher-form`
  - `environment`
  - `workload-rest`
  - `data-health`

Expected shape:

```js
{
  key: "environment",
  label: "Environment",
  rows: [
    {
      key: "park_factor",
      label: "Park factor",
      value: "0.99",
      rawValue: 0.99,
      status: "neutral",
      tone: "pos",
      note: "Slightly pitcher-friendly"
    }
  ]
}
```

Status rules to encode:
- `lineup_used === true` -> `active`; otherwise `missing`
- `umpire == null` or `ump_k_adj === 0` with no umpire -> `missing`
- `park_factor == null` -> `missing`
- `park_factor` between `0.98` and `1.02` -> `neutral`
- `swstr_delta_k9 == null` -> `missing`
- `swstr_delta_k9 === 0` -> `neutral`
- `rest_k9_delta == null` -> `missing`
- `rest_k9_delta === 0` -> `neutral`
- `data_complete === true` -> `active`; otherwise `missing`

- [ ] **Step 4: Expose the helper in the browser**

Modify `dashboard/v2.html` to load the new helper before `v2-app.js`.

```html
<script src="v2-data.js?v=2026-04-28-5"></script>
<script src="v2-movement-helpers.js?v=2026-04-28-5"></script>
<script src="v2-factor-details.js?v=2026-04-28-5"></script>
<script src="v2-app.js?v=2026-04-28-5" defer></script>
```

- [ ] **Step 5: Run tests to confirm the helper passes**

Run:

```powershell
node --test dashboard/v2-factor-details.test.mjs
```

Expected: PASS for all new helper tests.

- [ ] **Step 6: Commit Task 1**

```powershell
git add dashboard/v2-factor-details.js dashboard/v2-factor-details.test.mjs dashboard/v2.html
git commit -m "feat(v2): normalize factor detail groups"
```

### Task 2: Render a collapsible Factor Details section in the sheet

**Files:**
- Modify: `C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\v2-app.jsx`
- Modify: `C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\v2-app.js`
- Modify: `C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\v2.html`

- [ ] **Step 1: Add the failing UI test or render harness check**

Add a small assertion to `dashboard/v2-factor-details.test.mjs` or a second minimal test file that checks the collapse labels and group presence through a helper-facing contract rather than full DOM mounting.

```js
test("buildFactorGroups always includes all major sections", () => {
  const groups = buildFactorGroups(samplePick, "UNDER");
  assert.deepEqual(
    groups.map((g) => g.key),
    ["projection-core", "opponent-context", "pitcher-form", "environment", "workload-rest", "data-health"],
  );
});
```

- [ ] **Step 2: Wire disclosure state into `PickDetail`**

In `dashboard/v2-app.jsx`, add local state:

```js
const [showFactorDetails, setShowFactorDetails] = React.useState(false);
const factorHelpers = window.V2FactorDetails || {};
const factorGroups = factorHelpers.buildFactorGroups
  ? factorHelpers.buildFactorGroups(p, best.direction)
  : [];
```

Render a disclosure row under the default `Why this bet` section:

```jsx
<button
  className="v2-factor-toggle"
  type="button"
  onClick={() => setShowFactorDetails((v) => !v)}
  aria-expanded={showFactorDetails}
>
  <span>{showFactorDetails ? "Hide factor details" : "Show factor details"}</span>
  <span className="v2-factor-toggle-caret">{showFactorDetails ? "−" : "+"}</span>
</button>
```

- [ ] **Step 3: Render grouped factor rows**

Still in `PickDetail`, render the groups only when expanded:

```jsx
{showFactorDetails && (
  <div className="v2-factor-panel">
    {factorGroups.map((group) => (
      <div key={group.key} className="v2-factor-group">
        <div className="v2-factor-group-head">{group.label}</div>
        {group.rows.map((row) => (
          <div key={row.key} className="v2-factor-row">
            <span className="lbl">{row.label}</span>
            <span className={`val ${row.tone || ""}`}>
              {row.value}
              <span className={`v2-factor-status ${row.status}`}>{row.status}</span>
            </span>
          </div>
        ))}
      </div>
    ))}
  </div>
)}
```

- [ ] **Step 4: Add the supporting styles**

In `dashboard/v2.html`, add compact styles for:
- `.v2-factor-toggle`
- `.v2-factor-panel`
- `.v2-factor-group`
- `.v2-factor-group-head`
- `.v2-factor-status.active`
- `.v2-factor-status.neutral`
- `.v2-factor-status.missing`

Keep the visual direction subtle and consistent with existing v2 sheet rows.

- [ ] **Step 5: Rebuild `dashboard/v2-app.js`**

Run the existing Babel standalone rebuild flow:

```powershell
@'
const fs = require('fs');
const path = require('path');
const vm = require('vm');
(async () => {
  const res = await fetch('https://unpkg.com/@babel/standalone@7.27.1/babel.min.js');
  const src = await res.text();
  const ctx = { window: {}, self: {}, global: {} };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(src, ctx);
  const Babel = ctx.Babel || ctx.window.Babel;
  const result = Babel.transform(fs.readFileSync(path.resolve('dashboard/v2-app.jsx'), 'utf8'), {
    presets: ['react'],
    comments: false,
    compact: false,
  });
  fs.writeFileSync(path.resolve('dashboard/v2-app.js'), result.code, 'utf8');
})();
'@ | node
```

- [ ] **Step 6: Verify syntax**

Run:

```powershell
node --check dashboard/v2-app.js
```

Expected: no syntax errors.

- [ ] **Step 7: Commit Task 2**

```powershell
git add dashboard/v2-app.jsx dashboard/v2-app.js dashboard/v2.html
git commit -m "feat(v2): add collapsible factor details"
```

### Task 3: Verify real data behavior and mobile-sheet quality

**Files:**
- Modify: `C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\v2-factor-details.test.mjs` (if more assertions are needed)
- Verify only: `C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\data\processed\today.json`

- [ ] **Step 1: Add one real-data safety assertion**

Extend the helper test or add a tiny smoke script to ensure known live rows produce sensible statuses.

Example smoke:

```powershell
@'
const { buildFactorGroups } = require('./dashboard/v2-factor-details.js');
const fs = require('fs');
const today = JSON.parse(fs.readFileSync('./dashboard/data/processed/today.json', 'utf8'));
const pick = today.pitchers.find((p) => p.pitcher === 'Shane Baz');
const groups = buildFactorGroups(pick, 'UNDER');
console.log(JSON.stringify(groups.find((g) => g.key === 'environment'), null, 2));
'@ | node
```

Expected: park factor present, lineup marked missing/projected when appropriate, ump marked missing when TBA.

- [ ] **Step 2: Run the helper tests again**

```powershell
node --test dashboard/v2-factor-details.test.mjs
```

Expected: PASS.

- [ ] **Step 3: Browser/mobile sanity check**

Verify on a live detail sheet that:
- default `Why this bet` remains compact
- `Show factor details` expands/collapses cleanly
- all major factor groups appear
- status pills are readable on mobile
- mixed good/missing inputs display correctly

- [ ] **Step 4: Final verification sweep**

Run:

```powershell
node --test dashboard/v2-factor-details.test.mjs
node --check dashboard/v2-app.js
```

Expected: both pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add dashboard/v2-factor-details.test.mjs dashboard/v2-factor-details.js dashboard/v2-app.jsx dashboard/v2-app.js dashboard/v2.html
git commit -m "test(v2): verify factor details states"
```

### Task 4: Push and handoff

**Files:**
- No code changes required if previous tasks are complete

- [ ] **Step 1: Review the branch state**

Run:

```powershell
git status --short
git log --oneline -5
```

Expected: only intended UI files changed and committed.

- [ ] **Step 2: Push the branch**

```powershell
git push origin codex/v2-factor-details
```

Expected: branch published cleanly for integration.

- [ ] **Step 3: Summarize the user-facing outcome**

Include:
- what the collapsed panel shows by default
- what expands in factor details
- what debugging value it adds
- how it should be spot-checked on the next healthy slate
