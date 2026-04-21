# v2 UI Rollout — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the v2 React dashboard to production *alongside* `index.html`, at a coexisting URL, so we can dogfood it for real on real slates without risking the existing production app. Every phase is reversible — the legacy dashboard stays fully operational and bookmarkable throughout, and the default landing page does not change until the final phase (which is gated on real usage criteria).

**Constraints the user has set:**
- Do **not** delete or break `dashboard/index.html`. It remains the fallback for the entire plan.
- Mobile-first is fine. The desktop phone-frame is acceptable.
- No pipeline changes for this plan — v2 must work with the pipeline shape that already lives on `main`. Deferred pipeline wishlist is in [`docs/ui-redesign/deferred-pipeline-work.md`](../../ui-redesign/deferred-pipeline-work.md) for later.
- Parallel pipeline work on `model-audit-phase-a` must not be blocked by this rollout.

**Safety theme:** every phase lists (1) what changes, (2) how to verify it's fine, (3) how to roll it back in one commit. Bookmarks to `/` keep working at every phase.

---

## Current Status (updated 2026-04-21) — ✅ PLAN COMPLETE

All phases landed. `/` now serves v2; v1 preserved at `/legacy`. Plan is closed.

- **Phase 0: DONE 2026-04-17.** Merge `4bb54a8`. `/v2.html` went live alongside `/`.
- **Phase 1 (dogfooding): DONE 2026-04-17 → 2026-04-20.** Weekend pass clean. Two small follow-ups landed before moving on:
  - `64c600b` — W/L pill + grading summary on past-date slates (merge `689e923`)
  - `87a54d4` — suppress W/L pill on PASS cards + collapse sheet footer to full-width CLOSE (merge `058970d`)
- **Phase 2 (SW + push): DONE 2026-04-20.** PR #13, commit `66d4839`. `useNotifications()` hook in `v2-app.jsx` handles SW registration + subscribe/unsubscribe. Bell icon wired in the v2 header. Same `/sw.js` serves both shells at scope `/`.
- **Phase 3 (precompile Babel): DONE 2026-04-20.** PR #14, commit `f841d5d`. `v2-app.js` is the committed build artifact; `v2.html` loads it via plain `<script src>`. Build command noted in an HTML comment: `babel v2-app.jsx --presets=@babel/preset-react -o v2-app.js`. Recompile before committing JSX changes.
- **Phase 4+5 (v2 becomes default): DONE 2026-04-20.** PRs #15 / commits `8ff98aa` + `c2f375d`. `netlify.toml` now has `/ → /v2.html` and `/legacy → /index.html` redirects. `index.html` still physically present and reachable, per the "keep the fallback alive" policy.
- **Also shipped alongside:**
  - `2ff8a10` — v2 refresh button wired to the `trigger-pipeline` Netlify function.
  - `fa2d713` (PR #17) — date-pill W/L dots + `best_under_book` (cleared deferred items from `docs/ui-redesign/deferred-pipeline-work.md`).
- **Bug caught during Phase 0 verification, intentionally left alone:** v1 `index.html` line 1230 computes `totalUnits` as flat-1u per pick, ignoring the F2u/F1u/LEAN staking ladder from CLAUDE.md. v2 does it correctly. Not fixing v1 — it's retired at `/legacy`.

---

## File Map

**Already on this branch (`ui-redesign-eval`), uncommitted:**
- `dashboard/v2.html` — v2 shell (inlined CSS, loads React+Babel via CDN)
- `dashboard/v2-data.js` — adapter: fetches pipeline output → `window.V2_DATA/V2_PERF/V2_STEAM`
- `dashboard/v2-app.jsx` — React app (JSX, compiled in-browser by Babel)
- `docs/ui-redesign/handoff/` — original Claude Design bundle, reference only
- `docs/ui-redesign/deferred-pipeline-work.md` — pipeline wishlist

**Not yet on this branch:**
- Update `netlify.toml` ignore rule so v2 files trigger deploys
- `dashboard/v2-app.js` (precompiled output — added in Phase 3)
- `dashboard/sw.js` — port push/notification registration to v2 (Phase 2)
- `dashboard/manifest.json` — decide later whether to split PWA scopes

**Stays untouched until final phase:**
- `dashboard/index.html` — production app, default at `/`

---

## Phase 0 — Land on main, deploy at `/v2.html` ✅ DONE 2026-04-17

**What changes:** v2 ships as a sibling static page. `/` still serves `index.html`. Users only see v2 if they explicitly type `/v2.html` or follow a link we share. Nothing auto-redirects.

**Shipped:** merged into `main` as commit `4bb54a8` (merge of `daa5eaa` + `2c23ae1`). All Phase 0 tasks complete.

### Task 0.1: Update Netlify ignore rule so v2 files trigger deploys

**Files:**
- Modify: `netlify.toml` — the `ignore` clause currently skips deploys unless `dashboard/index.html`, `sw.js`, `manifest.json`, `icon.svg`, `netlify/functions/`, or `netlify.toml` itself changes.

- [ ] **Step 1: Add v2 files to the deploy-trigger list**

Find in `netlify.toml`:
```toml
  ignore = "git diff --quiet ${CACHED_COMMIT_REF:-HEAD^1} HEAD -- dashboard/index.html dashboard/sw.js dashboard/manifest.json dashboard/icon.svg netlify/functions/ netlify.toml"
```

Replace with:
```toml
  ignore = "git diff --quiet ${CACHED_COMMIT_REF:-HEAD^1} HEAD -- dashboard/index.html dashboard/v2.html dashboard/v2-app.jsx dashboard/v2-data.js dashboard/sw.js dashboard/manifest.json dashboard/icon.svg netlify/functions/ netlify.toml"
```

**Why:** Without this, committing v2 files won't actually redeploy the Netlify site — the build will be skipped by the ignore rule and `/v2.html` will 404 in prod.

- [ ] **Step 2: Verify list by eyeballing — no typos, no removed entries.**

### Task 0.2: Commit the branch

- [ ] **Step 1: Review uncommitted surface once more**

Run locally:
```
git status
git diff --stat
```

Expect to see (roughly): 3 new `dashboard/v2*` files, new `docs/ui-redesign/` tree, 1 `netlify.toml` edit. Nothing under `pipeline/`, nothing under `tests/`, nothing under `data/`.

- [ ] **Step 2: Commit in two logical commits**

```
git add netlify.toml dashboard/v2.html dashboard/v2-app.jsx dashboard/v2-data.js
git commit -m "feat(dashboard): add v2 React preview at /v2.html (coexists with index.html)"

git add docs/ui-redesign/
git commit -m "docs(ui): Claude Design handoff bundle + deferred pipeline wishlist"
```

Do **not** `git add .claude/` or any other untracked paths — keep the PR focused.

### Task 0.3: Open PR → main

- [ ] **Step 1: Push branch, open PR**

```
git push -u origin ui-redesign-eval
gh pr create --title "v2 UI preview — ship at /v2.html (index.html unchanged)" --body ...
```

PR body should state explicitly: `index.html remains the default at /`; v2 is accessed only at `/v2.html`; no pipeline changes; rollback = revert the PR.

- [ ] **Step 2: Merge to main once CI is green**

Squash-merge is fine. Netlify will auto-deploy because `netlify.toml` changed.

### Task 0.4: Verify in production

- [ ] **Step 1:** Visit `https://<site>/` — expect existing `index.html` exactly as before. No visible change.
- [ ] **Step 2:** Visit `https://<site>/v2.html` — expect v2 preview rendering real data from the latest `today.json` on `main`.
- [ ] **Step 3:** Visit `https://<site>/v2.html?date=2026-04-01` — expect archived-date navigation to work.
- [ ] **Step 4:** Check DevTools console on `/v2.html` — expect one Babel in-browser warning, no errors.

### Rollback for Phase 0

Revert the merge commit. `/v2.html` 404s, `/` is unaffected. No data, no users are touched.

---

## Phase 1 — Personal dogfooding window (no code changes) ✅ DONE 2026-04-20

**What changes:** Nothing in the repo. Just usage and observation.

### Task 1.1: Dogfood for at least 5 slates

- [ ] **Step 1:** Use `/v2.html` as your primary view for **5 consecutive slates** (roughly one week).
- [ ] **Step 2:** Keep `/` open in a second tab as a sanity check — especially during the 8 AM–6 PM refresh cadence and at game time (T-30min line lock).
- [ ] **Step 3:** Keep a running note (scratch file, not committed) of:
  - Any pitcher that looked wrong on v2 vs index.html.
  - Any card state that broke (LIVE fallback, FINAL fallback, empty-slate handling).
  - Any visual/a11y issue on mobile specifically.
  - Any perf issue (initial load, tab switching).

### Task 1.2: Decision gate

- [ ] **Step 1: Decide one of three paths:**
  - **Green:** No bugs found → proceed to Phase 2.
  - **Yellow:** Small fixes needed → fix on a short-lived branch, merge, extend dogfooding another slate or two, then proceed.
  - **Red:** Fundamental issue → leave `/v2.html` up as-is, drop back to `/` as daily driver, reassess before investing more.

### Rollback for Phase 1

Nothing to roll back — no code changed. Just stop using `/v2.html`.

---

## Phase 2 — Port PWA/push notifications into v2 ✅ DONE 2026-04-20 (PR #13, `66d4839`)

**What changes:** v2.html gets the service-worker registration + push-subscription plumbing that `index.html` already has, so "Install as app" and game-time push reminders work when loading from `/v2.html`. `index.html` is not touched.

**Why this phase matters:** Push notifications are the main reason `index.html` is PWA-wired. If we ever cut over the default URL, v2 must already carry this capability.

**Why we don't touch `manifest.json` yet:** Its `start_url` currently points to `/`. Keeping it pointed at `/` means users who "Install app" from v2 still get a PWA that lands on `index.html` — that is a feature, not a bug, until we are ready to cut over. Phase 4 handles the manifest.

### Task 2.1: Inventory what `index.html` does today

**Files:**
- Read-only: `dashboard/index.html` (search for `serviceWorker`, `pushManager`, `subscription`, `notify`, `vapid`)
- Read-only: `dashboard/sw.js`
- Read-only: `netlify/functions/save-subscription.mjs`, `netlify/functions/send-notifications.mjs`

- [ ] **Step 1:** List exactly (a) the `navigator.serviceWorker.register(...)` call and its path/scope, (b) the push-subscription creation + POST to `save-subscription`, (c) the UI bits (bell icon / toggle) that drive subscribe/unsubscribe, (d) what VAPID public key is used and where it's read from.

### Task 2.2: Port the SW registration + subscribe logic into `v2-app.jsx`

**Files:**
- Modify: `dashboard/v2-app.jsx`
- Read-only: `dashboard/sw.js` (shared — same file serves both shells)

- [ ] **Step 1:** Add a top-level `useEffect` in the `App` component that mirrors `index.html`'s SW registration call. Use the same scope (`/`) so the same SW controls both shells; this keeps the existing `save-subscription` endpoint honest.
- [ ] **Step 2:** Add a bell/notify toggle somewhere sensible in the v2 header. (NotifyBell component is already stubbed in v2-app.jsx — wire it for real now.)
- [ ] **Step 3:** Reuse the same `VAPID_PUBLIC_KEY` read pattern that `index.html` uses. Do not duplicate the key in JS source.

### Task 2.3: Verify both shells still work

- [ ] **Step 1:** Locally, load `/v2.html`, register a push, close tab, fire a test notification via the Netlify function — receive it.
- [ ] **Step 2:** Load `/` (index.html) in the same browser — confirm existing subscription still recognized, existing bell still works, no double-subscription.
- [ ] **Step 3:** DevTools → Application → Service Workers: confirm only **one** SW is active, scope `/`.

### Rollback for Phase 2

Revert the Phase 2 commit. SW registration disappears from v2, `index.html` unchanged, existing subscribers unaffected (the SW file itself wasn't modified).

---

## Phase 3 — Precompile JSX (kill in-browser Babel) ✅ DONE 2026-04-20 (PR #14, `f841d5d`)

**What changes:** `dashboard/v2-app.jsx` is compiled to `dashboard/v2-app.js` at build time (or locally, committed). `v2.html`'s `<script type="text/babel">` tag is replaced with `<script src="v2-app.js">`. Babel CDN `<script>` is removed.

**Why:** The in-browser Babel warning is legitimate — it adds ~1 MB of JS to every load, slows first paint, and is explicitly not recommended for production. Precompiling also unblocks minification if we ever want it.

### Task 3.1: Decide compile strategy

- [ ] **Step 1:** Pick one:
  - **A, zero new build infra:** run `npx @babel/cli@7 --presets=@babel/preset-react v2-app.jsx -o v2-app.js` locally before each commit that touches the JSX. Commit both files. No CI changes.
  - **B, Netlify-side build:** add a trivial `package.json` with `build` script, add a `[build]` command to `netlify.toml`, let Netlify compile on deploy. Don't commit `v2-app.js`.

Given the "no build step" spirit of the existing app and that v2 changes infrequently, **option A is recommended** for now.

### Task 3.2: Compile, swap the script tag, verify

**Files:**
- New: `dashboard/v2-app.js` (generated output, committed)
- Modify: `dashboard/v2.html`
- Modify: `netlify.toml` ignore rule — add `dashboard/v2-app.js`

- [ ] **Step 1:** Run the Babel CLI once; review the output file for weirdness (it should be nearly 1:1 modulo JSX → `React.createElement` calls).
- [ ] **Step 2:** In `v2.html`, replace:
  ```html
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  ...
  <script type="text/babel" src="v2-app.jsx"></script>
  ```
  with:
  ```html
  <script src="v2-app.js" defer></script>
  ```
- [ ] **Step 3:** Add a short dev note in `v2.html` comment: *"v2-app.js is generated from v2-app.jsx via `npx @babel/cli --presets=@babel/preset-react v2-app.jsx -o v2-app.js`. Recompile before committing JSX changes."*
- [ ] **Step 4:** Verify `/v2.html` in prod:
  - No Babel warning in console.
  - First paint noticeably faster.
  - Archived-date navigation still works, sheet still opens, everything else unchanged.

### Rollback for Phase 3

Revert the commit. `v2.html` goes back to `<script type="text/babel">`, in-browser Babel resumes. `v2-app.js` is ignored. Zero user-visible impact beyond a slower first load.

---

## Phase 4 — Soft redirect: prefer v2 at `/`, keep a fallback URL ✅ DONE 2026-04-20 (PR #15, `8ff98aa` + `c2f375d`)

**What changes:** `/` starts serving v2 by default. `index.html` moves to `/legacy` (or `/classic`) and remains fully functional. Bookmarks to `/` get v2 immediately; bookmarks to `/index.html` still resolve (we preserve the file name).

**Do not proceed to this phase until:**
- Phase 1 dogfooding passed cleanly.
- Phase 2 push notifications have been confirmed working on at least one real slate.
- Phase 3 precompile landed and is stable.
- You've verified on **both iOS Safari and Android Chrome** that v2 behaves at game time (T-30 lock, refresh cadence) and at LIVE/FINAL transitions.

### Task 4.1: Route `/` to v2 via Netlify redirect

**Files:**
- Modify: `netlify.toml` (add `[[redirects]]` block — do **not** delete or rename `index.html`)

- [ ] **Step 1:** Add a redirect that serves `v2.html` when users hit `/` with an HTML Accept header. Keep `index.html` reachable at `/legacy` and at `/index.html` (Netlify serves physical files before redirect rules, so `/index.html` should keep working by default; add an explicit `/legacy` → `/index.html` alias for discoverability).
- [ ] **Step 2:** Update the PWA manifest `start_url` to `/` (unchanged) and confirm it loads v2. Add a short note to `dashboard/v2.html` header nav: "Switch to classic view" → `/legacy`.

### Task 4.2: Dogfood one more slate at the new default

- [ ] **Step 1:** Visit the bare site URL — confirm v2 loads.
- [ ] **Step 2:** Visit `/legacy` — confirm index.html loads, push subscription recognized, nothing degraded.
- [ ] **Step 3:** On the installed PWA (if you have one), confirm it still opens v2 cleanly.

### Rollback for Phase 4

Remove the redirect block from `netlify.toml`, redeploy. `/` serves `index.html` again, `/v2.html` remains accessible. Time-to-rollback: one commit + one Netlify deploy (~1 min).

---

## Phase 5 — Stop touching index.html for new features (but keep it alive) ✅ DONE 2026-04-20 (PR #15)

**What changes:** Nothing structural. This is a **policy** phase.

- [ ] **Step 1:** From this point on, all new UI work happens in v2. `index.html` gets security/data-shape fixes only — no new features, no visual refreshes.
- [ ] **Step 2:** Add a one-line banner to `index.html` nav: *"You're on the classic dashboard. New features live in the updated view."* linking to `/`.
- [ ] **Step 3:** Revisit after 30 days of stable v2 usage. Decide then whether to archive `index.html` entirely or keep the fallback indefinitely. **This plan does not commit to deleting it.**

---

## Cross-cutting: the `model-audit-phase-a` branch

The parallel pipeline branch (`model-audit-phase-a`) changes calculation internals (`pitcher_throws` fallback, `platoon_k_delta` inside `calc_lineup_k_rate`, etc.) but does **not** rename or remove any field in the per-pitcher record emitted to `today.json`. Specifically, the v2 adapter ([`v2-data.js`](../../../dashboard/v2-data.js)) reads: `pitcher, team, opp_team, pitcher_throws, game_time, k_line, opening_line, best_over_odds, best_under_odds, opening_over_odds, opening_under_odds, lambda, avg_ip, opp_k_rate, ump_k_adj, season_k9, recent_k9, career_k9, ev_over, ev_under, game_state, best_over_book, swstr_pct, swstr_delta_k9, data_complete`. All of those stay on `model-audit-phase-a`.

**Therefore:** merging `model-audit-phase-a` into `main` in any order relative to this rollout is safe. No field the adapter depends on is being removed or renamed. If that ever changes, the adapter is the single place to update.

---

## Cross-cutting: what we're NOT doing in this plan

These are explicitly out of scope. They live in [`docs/ui-redesign/deferred-pipeline-work.md`](../../ui-redesign/deferred-pipeline-work.md) and stay deferred:

- `best_under_book` on each pitcher
- Live in-game hydrate (`live.*` object)
- Per-pick `result` on finalized games in `today.json`
- Standalone `steam.json` feed
- Sportsbook deep links
- Date-pill win/loss dots
- Real line-movement chart (needs steam feed)

The v2 app already degrades gracefully for each of these — they don't block rollout.

---

## Summary of safety posture

| Phase | `/` serves | `index.html` reachable | Rollback cost |
|-------|-----------|------------------------|---------------|
| 0     | index.html | yes — it's `/`        | revert merge  |
| 1     | index.html | yes                   | none (no code) |
| 2     | index.html | yes                   | revert one commit |
| 3     | index.html | yes                   | revert one commit |
| 4     | v2.html   | yes at `/legacy`      | remove redirect block |
| 5     | v2.html   | yes at `/legacy`      | policy-only, no code |

At every phase, bookmarks to `/index.html` keep working, and the full legacy app is one URL away. The default page only changes at Phase 4, and only after Phase 1/2/3 have baked.
