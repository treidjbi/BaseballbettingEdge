# Alt Picks UI Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the comparison-only Alt Picks tab automatically recover from temporary read failures without erasing the last valid current-slate evidence.

**Architecture:** Add a small polling controller to the existing isolated Alt adapter. The controller performs an immediate read, schedules the next read 60 seconds after completion, preserves the last valid state only when a later read fails, and exposes a stop function for React cleanup. `AltPicksTab` consumes that controller and renders honest retry status; the existing endpoint and V2 contract remain unchanged.

**Tech Stack:** Vanilla JavaScript, React hooks in the existing Babel-compiled dashboard, Node built-in test runner, pytest source/isolation checks, Netlify static deployment.

## Global Constraints

- Poll every `60000` milliseconds only while `AltPicksTab` is mounted.
- Permit at most one in-flight Alt request.
- Preserve last-good state only after a failed/rejected read; a valid new empty `ready` state replaces prior cards.
- Keep `pregame_alternative_pick_methodology_v2` and selector fingerprint `23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4` unchanged.
- Do not change the endpoint, Supabase state, selector, model, official picks, accepted bets, locks, notifications, providers, artifacts, history, or source-of-truth behavior.
- Keep the Alt surface comparison-only with no wager, stake, Log Bet, Save Bet, or notification controls.
- Use `2026-07-24-alt-route-recovery` for `v2-alt-picks.js` and
  `2026-07-24-alt-ui-recovery` for `v2-app.js`.

---

### Task 1: Add a test-driven Alt polling controller

**Files:**
- Modify: `dashboard/v2-alt-picks.test.mjs`
- Modify: `dashboard/v2-alt-picks.js`

**Interfaces:**
- Consumes: existing `fetchCurrentSlate(): Promise<AltState>`, where `AltState.status` is `ready` or `unavailable`.
- Produces: `startCurrentSlatePolling(options): () => void`.
- `options` contains `onUpdate(state)`, optional `fetcher`, optional `intervalMs`, optional `schedule`, and optional `cancelSchedule`.
- Emitted healthy states carry `refresh_status: "current"` and `refresh_error: ""`.
- Emitted retained states carry `refresh_status: "retrying"` and the failed read's `error`.

- [ ] **Step 1: Write failing polling behavior tests**

Add a manual scheduler and tests that exercise the real polling controller:

```js
function manualScheduler() {
  const tasks = [];
  return {
    tasks,
    schedule(fn, delay) {
      const task = { fn, delay, cancelled: false };
      tasks.push(task);
      return task;
    },
    cancelSchedule(task) {
      if (task) task.cancelled = true;
    },
  };
}
```

Test these literal behaviors:

```js
test("polling fetches immediately and schedules a 60-second non-overlapping refresh", async () => {
  // First unresolved fetch creates no timer; resolving it emits once and
  // schedules exactly one task with delay 60000.
});

test("polling retains the last valid state when a later read fails", async () => {
  // ready row A -> unavailable must emit row A with refresh_status retrying.
});

test("polling replaces retained data with a valid empty current state", async () => {
  // ready row A -> unavailable -> ready [] must end with rows [] and current.
});

test("stopping polling ignores a late response and clears the timer", async () => {
  // stop before a deferred response resolves; no update or new timer occurs.
});
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
node --test dashboard/v2-alt-picks.test.mjs
```

Expected: the new tests fail because `startCurrentSlatePolling` is not exported.

- [ ] **Step 3: Implement the minimal polling controller**

Add beside `fetchCurrentSlate`:

```js
function startCurrentSlatePolling({
  onUpdate,
  fetcher = fetchCurrentSlate,
  intervalMs = 60000,
  schedule = setTimeout,
  cancelSchedule = clearTimeout,
} = {}) {
  if (typeof onUpdate !== "function") throw new TypeError("onUpdate is required");
  let active = true;
  let timer = null;
  let lastGood = null;

  async function poll() {
    if (!active) return;
    let next;
    try {
      next = await fetcher();
    } catch {
      next = unavailable(phoenixDate(), "fetch_failed");
    }
    if (!active) return;

    if (next?.status === "ready") {
      lastGood = next;
      onUpdate({ ...next, refresh_status: "current", refresh_error: "" });
    } else if (lastGood) {
      onUpdate({
        ...lastGood,
        refresh_status: "retrying",
        refresh_error: text(next?.error) || "fetch_failed",
      });
    } else {
      const failed = next?.status === "unavailable"
        ? next
        : unavailable(phoenixDate(), "fetch_failed");
      onUpdate({
        ...failed,
        refresh_status: "retrying",
        refresh_error: text(failed.error) || "fetch_failed",
      });
    }
    if (active) timer = schedule(poll, intervalMs);
  }

  void poll();
  return () => {
    active = false;
    if (timer != null) cancelSchedule(timer);
  };
}
```

Export it on `window.V2AltPicks`. Scheduling after `await fetcher()` is the
one-in-flight guarantee; no separate interval or retry loop is added.

- [ ] **Step 4: Run the focused adapter tests and verify GREEN**

Run:

```powershell
node --test dashboard/v2-alt-picks.test.mjs
```

Expected: all adapter tests pass, including immediate fetch, 60-second
scheduling, last-good preservation, valid-empty replacement, and cleanup.

- [ ] **Step 5: Commit the polling controller**

```powershell
git add -- dashboard/v2-alt-picks.js dashboard/v2-alt-picks.test.mjs
git commit -m "fix: make Alt Picks reads self-recovering"
```

### Task 2: Integrate retry state into the Alt tab and refresh both assets

**Files:**
- Modify: `dashboard/v2-app.jsx`
- Modify: `dashboard/v2-app.js`
- Modify: `dashboard/v2.html`
- Modify: `tests/test_dashboard_alt_picks_ui.py`
- Modify: `tests/test_dashboard_accepted_bet_log.py`

**Interfaces:**
- Consumes: `window.V2AltPicks.startCurrentSlatePolling({ onUpdate })`.
- Produces: React cleanup by returning the poller's stop function.
- Consumes: `state.refresh_status` values `current` and `retrying`.

- [ ] **Step 1: Write failing UI and delivery tests**

Update the dashboard tests to require:

```python
assert "Alternative methodology unavailable." in alt
assert "Retrying automatically." in alt
assert "Last update retained; retrying current evidence." in alt
assert "startCurrentSlatePolling" in alt
assert "v2-alt-picks.js?v=2026-07-24-alt-ui-recovery" in html
assert "v2-app.js?v=2026-07-24-alt-ui-recovery" in html
```

Keep the existing forbidden-control assertions. Change the accepted-bet cache
test to the new app token.

- [ ] **Step 2: Run the UI tests and verify RED**

Run:

```powershell
python -m pytest tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py -q
```

Expected: failures for missing polling integration, retry copy, and new asset
tokens.

- [ ] **Step 3: Replace the one-shot effect with polling cleanup**

In `AltPicksTab`, initialize `refresh_status: "current"` and replace the
one-shot async effect with:

```jsx
React.useEffect(() => {
  const adapter = window.V2AltPicks;
  if (!adapter?.startCurrentSlatePolling) {
    setState({
      status: "unavailable",
      rows: [],
      counts: {},
      slate_date: "",
      error: "adapter_missing",
      refresh_status: "retrying",
      refresh_error: "adapter_missing",
    });
    return undefined;
  }
  return adapter.startCurrentSlatePolling({ onUpdate: setState });
}, []);
```

Render:

```jsx
{state.status === "unavailable" && (
  <div className="v2-state v2-alt-unavailable">
    <div className="ttl">Alternative methodology unavailable.</div>
    <div className="sub">Retrying automatically. Main picks are unaffected.</div>
  </div>
)}
{state.status === "ready" && state.refresh_status === "retrying" && (
  <div className="v2-state v2-alt-retrying">
    <div className="sub">Last update retained; retrying current evidence.</div>
  </div>
)}
```

Do not hide valid cards while the second banner is visible.

- [ ] **Step 4: Update both asset tokens and compile JSX**

Set in `dashboard/v2.html`:

```html
<script src="v2-alt-picks.js?v=2026-07-24-alt-ui-recovery"></script>
<script src="v2-app.js?v=2026-07-24-alt-ui-recovery" defer></script>
```

Compile:

```powershell
npx --yes -p @babel/core@7 -p @babel/cli@7 -p @babel/preset-react@7 babel dashboard/v2-app.jsx --presets=@babel/preset-react -o dashboard/v2-app.js
```

- [ ] **Step 5: Run focused UI/adapter/isolation tests and verify GREEN**

Run:

```powershell
node --test dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs
python -m pytest tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py -q
```

Expected: all focused Node and pytest tests pass.

- [ ] **Step 6: Commit the UI integration**

```powershell
git add -- dashboard/v2-app.jsx dashboard/v2-app.js dashboard/v2.html tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py
git commit -m "fix: recover the Alt Picks tab without reload"
```

### Task 3: Verify the complete dashboard change

**Files:**
- Verify only: all changed files from Tasks 1 and 2.

**Interfaces:**
- Produces: a reviewed feature-branch commit that can be merged without any
  endpoint, database, Render, or environment mutation.

- [ ] **Step 1: Verify compiled-source parity**

Compile JSX to a temporary file and compare it with the committed asset:

```powershell
npx --yes -p @babel/core@7 -p @babel/cli@7 -p @babel/preset-react@7 babel dashboard/v2-app.jsx --presets=@babel/preset-react -o dashboard/v2-app.verify.js
git diff --no-index --exit-code -- dashboard/v2-app.js dashboard/v2-app.verify.js
Remove-Item -LiteralPath dashboard/v2-app.verify.js
```

Expected: diff exits `0`; the temporary file is removed.

- [ ] **Step 2: Run all JavaScript tests**

Run:

```powershell
node --test dashboard/*.test.mjs tests/*.mjs
```

Expected: zero failures.

- [ ] **Step 3: Run the complete dashboard isolation checks**

Run:

```powershell
python -m pytest tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py tests/test_dashboard_perf_payload.py -q
```

Expected: zero failures.

- [ ] **Step 4: Inspect scope and repository hygiene**

Run:

```powershell
git diff 495476e5..HEAD --stat
git diff 495476e5..HEAD -- dashboard/v2-alt-picks.js dashboard/v2-app.jsx dashboard/v2.html
git diff --check
git status --short
```

Expected: only the approved adapter, Alt UI, compiled asset, HTML version
tokens, tests, and this plan changed; no untracked generated files remain.

### Task 4: Merge, deploy, live-verify, and hand off

**Files:**
- Modify after live proof if needed: `docs/current-state.md`
- Modify after live proof if needed:
  `docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md`
- Modify outside repo:
  `C:/Users/TylerReid/.codex/automations/yesterdays-pipeline-health-bbe/memory.md`

**Interfaces:**
- Consumes: exact verified feature commit.
- Produces: a Netlify production deploy from the merged `main` commit and a
  live browser proof of recovery behavior.

- [ ] **Step 1: Re-read the plan and design acceptance criteria**

Confirm every approved requirement has a changed file and passing check. Do not
merge if any endpoint/model/lock/provider/notification surface changed.

- [ ] **Step 2: Merge the verified feature branch into current `main`**

From the main clone:

```powershell
git pull --ff-only
git merge --ff-only codex/alt-picks-ui-recovery
git push origin main
```

Expected: `main`, `origin/main`, and the verified feature commit are identical.

- [ ] **Step 3: Verify the Git-linked Netlify production deploy**

Confirm the deploy is `ready` and bound to the exact merged commit. Do not
change Netlify environment variables, functions, schedules, or dashboard data.

- [ ] **Step 4: Verify production files and endpoint contract**

Check that production HTML references both
`2026-07-24-alt-ui-recovery` assets, both assets return `200`, and the existing
explicit V2 endpoint still returns its reviewed bundle and fingerprint.

- [ ] **Step 5: Verify the live app**

Open a fresh production app session, select Alt Picks, and confirm the current
state renders. Keep the tab open across one 60-second refresh and confirm it
does not fall back to permanent unavailable. Verify no wager controls appear.

- [ ] **Step 6: Update handoffs with observed facts**

Record the exact commit, deploy ID, test counts, current endpoint state, live UI
result, and preserved guardrails. If the page remains unavailable, mark the
handoff broken with the exact observed error instead of claiming success.

### Task 5: Correct the production-confirmed client-blocked route

**Files:**
- Modify: `dashboard/v2-alt-picks.js`
- Modify: `dashboard/v2-alt-picks.test.mjs`
- Modify: `dashboard/v2.html`
- Modify: `netlify.toml`
- Modify: `tests/test_dashboard_alt_picks_ui.py`
- Modify: `docs/superpowers/specs/2026-07-24-alt-picks-ui-recovery-design.md`

**Interfaces:**
- Preserves: the existing `alternative-picks` function and V2 response
  contract.
- Produces: neutral same-origin alias
  `/api/slate-comparison?bundle_version=v2`.

- [x] **Step 1: Capture the live failure**

The first production recovery deploy served the new assets and a healthy
endpoint, but Chrome showed `ERR_BLOCKED_BY_CLIENT` for the function URL while
the app rendered the retrying unavailable state.

- [x] **Step 2: Write and observe failing route tests**

The adapter test required `/api/slate-comparison?bundle_version=v2`, and a
TOML-parsing pytest required the exact Netlify rewrite. Both failed before the
route change.

- [x] **Step 3: Add the neutral alias and update the adapter**

Add:

```toml
[[redirects]]
  from = "/api/slate-comparison"
  to = "/.netlify/functions/alternative-picks"
  status = 200
  force = true
```

Point `ENDPOINT` at the alias and bump only the changed adapter asset to
`2026-07-24-alt-route-recovery`.

- [x] **Step 4: Run focused route, polling, UI, and isolation tests**

Run:

```powershell
node --test dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs
python -m pytest tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py -q
```

Expected: zero failures.

- [ ] **Step 5: Deploy and verify the neutral route in Chrome**

Verify the exact commit/deploy, a `200` JSON response from
`/api/slate-comparison?bundle_version=v2`, current Alt cards in Chrome, one
successful mounted refresh, and continued absence of wager controls.
