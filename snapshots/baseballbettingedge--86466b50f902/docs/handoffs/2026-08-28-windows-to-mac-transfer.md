# BaseballBettingEdge Windows-to-Mac Transfer and AI Handoff

Prepared: 2026-08-28, America/Phoenix

Windows source clone: `C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge`

Mac target clone: `/Users/tyler/Documents/Codex/2026-05-02/pull-my-repos/BaseballbettingEdge`

GitHub remote: `https://github.com/treidjbi/BaseballbettingEdge.git`

Branch at handoff: `main`

Pre-handoff base commit: `dade7826cac232b285fb70160f29dd3102e0d05a`

## Purpose and authority

This is the one-time machine-transfer runbook and context bridge for moving
BaseballBettingEdge from Tyler's Windows laptop to his MacBook Air. It is
written for Tyler and for a fresh ChatGPT/Codex agent that has no conversation
history.

This file does **not** replace the project's canonical sources. If anything in
this snapshot conflicts with fresher verified evidence, use this authority
order:

1. Live verified production evidence.
2. `AGENTS.md` for global rules and source-of-truth boundaries.
3. `docs/current-state.md` for the Four-Lane Operating Board.
4. The newest active dated plan referenced by the board.
5. This transfer snapshot.
6. Historical plans, local generated reports, and old chat history.

Do not rewrite this handoff every day. Update `docs/current-state.md`, the
controlling plan, and the BBE Operations Brief memory through the normal policy.

## First 15 minutes on the Mac

A new agent should do these steps before diagnosing or changing anything:

1. Confirm the machine, repository root, remote, branch, and worktree.
2. Stop if the Mac clone has unexplained local changes. Do not overwrite them.
3. Fetch and fast-forward from GitHub; do not copy the Windows repo folder.
4. Read the canonical files in the order below.
5. Run only the read-only acceptance checks in this document.
6. Summarize the four lanes, current production truth, and closed gates to
   Tyler before proposing work.

First-session read order:

1. `AGENTS.md`
2. `docs/handoffs/2026-08-28-windows-to-mac-transfer.md`
3. `docs/current-state.md`
4. `docs/provider-cost-ledger.md`
5. `docs/operational-risk-register.md`
6. `docs/research/market-tracker-map.md`
7. The newest dated plans governing the requested lane.

Run from Terminal:

```bash
cd /Users/tyler/Documents/Codex/2026-05-02/pull-my-repos/BaseballbettingEdge
git rev-parse --show-toplevel
git remote -v
git branch --show-current
git status --short
git fetch --prune origin
git switch main
git pull --ff-only
git log -3 --oneline
```

Expected remote:

```text
https://github.com/treidjbi/BaseballbettingEdge.git
```

The latest `main` history should include a commit named similarly to
`docs: add Mac transfer handoff`. If it does not, stop and compare the Mac and
GitHub branch heads before continuing.

## What the project does

BaseballBettingEdge is Tyler's personal-use MLB pitcher strikeout prop decision
system. It combines sportsbook pitcher-K lines with MLB/FanGraphs context,
computes a Poisson-based projection and EV, applies bounded quality and
selection canaries, publishes dashboard artifacts, tracks market movement,
locks picks before games, sends approved notifications, records prospective
Alt V2 evidence, and grades results.

The production flow is:

```text
TheRundown official odds
  + approved non-strict PropLine fallback/sidecar
  + MLB/FanGraphs/lineup/umpire inputs
                 |
                 v
       Render scheduled pipeline
                 |
                 v
   Supabase published artifacts and ledgers
                 |
                 v
   Netlify get-artifact API and dashboard
```

Do not infer production truth from stale files in a Render checkout or from an
old local clone. The production model/dashboard truth is the TheRundown-derived
Render artifact path published through Supabase and served by Netlify.

## Current handoff posture

The 2026-08-28 morning read was **Watch, not Broken**:

- The production pipeline, public artifacts, grading, locks, notifications,
  dashboard, and approved provider provenance were healthy.
- The current model candidates were still soaking; no model or selection
  promotion was justified.
- Supabase storage was `5,598,211,219` bytes, about `5,339 MB` or `65.17%` of
  the included 8 GiB allowance. Storage growth remains a watch item.
- A completed physical backup at `2026-08-28T05:45:45.570Z` was newer than the
  last historical compact write. That satisfies backup freshness only. It is
  not recovery proof and does not authorize deletion or vacuum.
- The active-provider compact-only historical repair was complete for all 41
  source-complete dates. Keep 23 provider/date partitions and 1,274 compact
  rows fail-closed because the companion provider has no raw evidence.
- BoltOdds remained suspended with no new heartbeat or snapshot after its June
  2026 retirement.
- Alt V2 infrastructure was healthy, but its prospective selected-frozen record
  remained negative. The historical `148-84, +38.585u` result is a research
  benchmark, not the prospective record and not promotion evidence.

These numbers are a transfer snapshot. Recheck live artifacts, the current
board, and the latest automation memory before quoting them as current.

## Non-negotiable approval boundaries

Research and preparation do not authorize external or production changes.
Tyler must separately approve any action that changes:

- production behavior, schedules, or deploys;
- provider order, provider flags, strictness, or source-of-truth rules;
- model parameters, formulas, thresholds, verdicts, staking, or
  `formula_change_date`;
- notifications, notification classes, locks, or lock strictness;
- dashboard behavior or artifact contents;
- Supabase retention, deletion, compaction writes, vacuum, or recovery actions;
- secrets, Render environment variables, GitHub variables, or Netlify settings;
- accepted-bet records or other user-owned operating data.

Important closed gates at handoff:

- Do not enable BoltOdds or use it as a cutover candidate.
- Do not set `OFFICIAL_MARKET_SOURCE=boltodds_propline`.
- Do not set `ENABLE_BOLTODDS_PIPELINE_SOURCE=true`.
- Do not enable provider strict mode.
- Do not enable the strict lock consumer.
- Do not create new notification classes.
- Do not promote market-anchor, market-shrink, Gate F, CLV, Strong Base, or Alt
  V2 evidence into live behavior.
- Do not delete raw snapshots or webhook rows, run vacuum for reclamation, or
  weaken the fixed-provider evidence gates.
- Do not publicly share, sell, distribute, or monetize the app without a
  separate terms, compliance, and data-rights review.

## Four-Lane Operating Board snapshot

### 1. Pipeline / infrastructure

- Render is the primary scheduler.
- Supabase `published_pipeline_artifacts` is the artifact store.
- Netlify `get-artifact` serves the dashboard.
- GitHub scheduled workflows are disabled. `workflow_dispatch` is manual
  rollback/stale-artifact repair only.
- Preview, grading, full/refresh, and lock services hydrate from the remote
  artifact path where required so stale checkout files are not republished.
- `render.yaml` intentionally contains `services: []`. Never Blueprint-sync it
  expecting it to recreate production services; it is a BoltOdds-retirement
  safety control.
- Render cron services keep auto-deploy off. A code push does not automatically
  redeploy the pipeline cron group.

Current approved provider wrapper:

```text
OFFICIAL_MARKET_SOURCE=therundown_propline
ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE=true
OFFICIAL_MARKET_SOURCE_FALLBACK=therundown
ENABLE_BOLTODDS_PIPELINE_SOURCE=false
OFFICIAL_MARKET_STRICT=false
```

This means curated TheRundown+PropLine fallback can be used by the wrapper, but
TheRundown remains the book-of-record model source and direct fallback.

### 2. Model

- Treat `2026-04-28+` as the clean evaluation regime.
- The live strategy is bet-selection-first; shadow research does not authorize
  lambda or staking changes.
- Quality gating is active.
- Market-favorite confidence referee is enforce-mode verdict conversion only.
- Profit rescue is enforce-mode verdict conversion only.
- Batter handedness is Path B input canary only.
- Market anchor remains shadow.
- Market shrink is diagnostic-only and its promotion path is closed.
- No-drag v1 is retired as a promotion path.
- Strict-runtime evidence is a narrow prospective specialist watch and has not
  satisfied the required side, price, provider, agreement, rolling-window, and
  leave-one-slate-out gates.
- Final CLV is a process-quality target, not a live selection rule.
- Gate C is the canonical research dataset; Gates D/E/F/12E and all live
  behavior changes remain closed unless a separate plan passes every slice.

### 3. UI

- Netlify redirects `/` to `dashboard/v2.html`.
- Live-market context is default-on for actionable cards; `?marketSheet=0` is
  the rollback/opt-out.
- PASS cards stay quiet.
- Same-line/different-line and alternate-line context are display aids only.
- The live-book selector can populate the existing Log Bet form. Do not save a
  test bet without Tyler's approval.
- UI usefulness does not promote a provider, model rule, notification class,
  or source of truth.

### 4. Tracking / data collection / history

- Read `docs/research/market-tracker-map.md` before adding any tracker.
- Reuse raw and compact evidence; do not create duplicate tables because a
  report is inconvenient.
- Operational locks, market snapshots, notification rows, provider usage,
  compact movements, Gate C, market agreement, CLV packets, and Alt V2 proof
  are separate evidence surfaces.
- Compaction does not equal deletion or physical space recovery.
- Retention remains preview/read-only unless Tyler approves the exact execution
  scope after recovery proof.

## Production services and ownership map

| System | Role | Transfer fact |
| --- | --- | --- |
| GitHub | Source repository and manual rollback workflow | Remote is `treidjbi/BaseballbettingEdge`; scheduled Actions are disabled. |
| Render | Preview, grading, full/refresh, lock, live-layer, and post-grading research jobs | Production services were created/configured in Render, not from `render.yaml`; auto-deploy is off. |
| Supabase | Artifact store, operational ledgers, provider evidence, research rows | Project ref is `htoaytcsjrdyyzcwxjfg`; linked CLI state is local and ignored. |
| Netlify | Static dashboard and serverless functions | Site URL is `https://baseballbettingedge.netlify.app`; site ID is `47c15fdf-6278-4109-8877-545cc29eb418`. |
| TheRundown | Official book-of-record odds source | Keep existing cost/cadence guardrails. |
| PropLine | Approved fallback, DraftKings coverage, and live-movement sidecar | Polling and webhook evidence are separate; neither is an independent model-source promotion. |
| The Odds API | Capped emergency FanDuel/DraftKings fallback | Do not broaden calls without a cost decision. |
| BoltOdds | Retired provider trial | Worker must remain suspended; fresh rows mean accidental reactivation/noise. |

Known Render service names include:

- `bbe-pipeline-preview`
- `bbe-pipeline-grading`
- `bbe-pipeline-full`
- `bbe-pipeline-refresh-day`
- `bbe-pipeline-lock`
- `bbe-live-layer`
- `bbe-gate-c-post-grading-review`
- retired `bbe-boltodds-shadow-worker`

Do not infer that every historical `bbe-*` name found in plans is active.
Verify status in Render before acting.

## Normal production schedule

All times use America/Phoenix, UTC-7 year-round:

- 12:17 AM: preview/opening lines.
- 3:17 AM: grade the prior slate and calibrate approved parameters.
- 6:17 AM: full run.
- 8:07 AM through 6:07 PM: refresh every 30 minutes.
- Every 10 minutes at `:02/:12/:22/:32/:42/:52`: lock consumer.
- Every 10 minutes: live layer and Netlify notification sender, offset by their
  current service schedules.
- 11:07 AM UTC / 4:07 AM Phoenix: post-grading research runner according to the
  current Render configuration; verify the live schedule before relying on it.

Scheduler delay is not automatically an incident. It becomes important if it
causes stale artifacts, missed grading, missed locks, missed notifications, or
a user-facing betting problem.

## Repository map

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | Canonical global rules and source-of-truth entrypoint. |
| `docs/current-state.md` | Four-Lane Operating Board and newest verified handoff. |
| `docs/superpowers/plans/` | Detailed active and historical implementation/promotion plans. |
| `pipeline/` | Python data pipeline and model feature construction. |
| `dashboard/` | Static dashboard, data adapters, PWA assets, and local artifact fallbacks. |
| `netlify/functions/` | Artifact, live-market, notification, accepted-bet, and Alt V2 APIs. |
| `market_infra/` | Supabase market/live-event normalization and writers. |
| `analytics/diagnostics/` | Read-only model, market, selection, and outcome diagnostics. |
| `data/research/gate_c/` | Durable Gate C research artifacts. |
| `scripts/` | Operational, deployment, artifact, storage, retention, and research helpers. |
| `supabase/migrations/` | Hosted database schema history. |
| `tests/` | Python and Node regression tests. |

There is intentionally no root `README.md`. Start with `AGENTS.md`.

## What Git transfers and what it does not

GitHub is the transport for source, migrations, durable research artifacts,
plans, tests, and handoff documentation. Do not manually copy the Windows clone
over the Mac clone.

These ignored paths are local/generated and should normally be recreated, not
copied:

| Path | Mac action |
| --- | --- |
| `.venv/` | Recreate with Python 3.11. Never copy a Windows virtual environment. |
| `node_modules/` and `netlify/functions/node_modules/` | Recreate with `npm ci`. |
| `.netlify/` | Re-link the site with the Netlify CLI. |
| `supabase/.temp/` and `supabase/.branches/` | Re-link through the Supabase CLI. |
| `supabase/.env` and any local `.env` | Recreate securely only if local execution needs them; never commit them. |
| `data/results.db` | Ephemeral SQLite cache; rebuild from canonical history when needed. |
| `data/fangraphs_cache.json` | Generated cache; production also publishes an optional artifact. |
| `analytics/output/` | Generated local reports; regenerate from durable inputs or use fresh hosted research evidence. |
| `.pytest_cache/` and `__pycache__/` | Recreated automatically. |
| `.superpowers/`, `.claude/`, `.worktrees/` | Local agent/worktree state; do not treat as project truth. |

Before surrendering the Windows laptop, only move a local ignored file if it
contains unique, required, non-secret evidence that is not reproducible and is
not already stored in GitHub, Supabase, Netlify, Render, or the password
manager. Document any such exception explicitly. None was identified as a
required project transfer artifact during this handoff.

## Credentials and local authentication

This document intentionally contains no secret values. Do not paste secrets
into Git, this file, chat, terminal transcripts, screenshots, or issue/PR text.

Cloud-hosted production secrets remain in their service. The Mac needs local
credentials only for the actions Tyler authorizes there.

Credential inventory:

- GitHub account authentication for `gh` and Git operations.
- Supabase account login and database password/link authorization.
- Netlify account login and site link.
- Render account/CLI or `RENDER_API_KEY` only for approved service inspection or
  deploys.
- Provider keys: `RUNDOWN_API_KEY`, `PROPLINE_API_KEY`, and capped fallback
  `ODDS_API_KEY`.
- Supabase runtime values: `SUPABASE_URL` and
  `SUPABASE_SERVICE_ROLE_KEY`.
- Notification values: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
  `VAPID_SUBJECT`, and `NOTIFY_SECRET`.
- PropLine webhook secret where webhook administration requires it.
- Optional local/manual workflow values such as `GITHUB_PAT`, `GITHUB_REPO`,
  `GITHUB_WORKFLOW`, and `NETLIFY_SITE_URL`.

Use Tyler's password manager or the owning provider dashboard to restore local
credentials. Do not copy the entire Windows Codex home, browser profile,
keyring, `.netlify`, or Supabase temporary directory to the Mac.

## Mac bootstrap

### 1. Use or recover the clone

The expected Mac clone already exists. Use it if present:

```bash
cd /Users/tyler/Documents/Codex/2026-05-02/pull-my-repos/BaseballbettingEdge
git status --short
git remote -v
```

If it does not exist, clone from GitHub into the intended parent directory:

```bash
mkdir -p /Users/tyler/Documents/Codex/2026-05-02/pull-my-repos
cd /Users/tyler/Documents/Codex/2026-05-02/pull-my-repos
git clone https://github.com/treidjbi/BaseballbettingEdge.git
cd BaseballbettingEdge
```

Do not clone over an existing directory. Do not discard unexplained changes.

### 2. Install the local toolchain

Project Python is pinned by `.python-version` to `3.11.9`. The dashboard has no
frontend build step, but Node/npm are needed for Netlify functions and CLI
tools.

One Homebrew setup path is:

```bash
brew install git gh python@3.11 node
```

Create the environment from the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r pipeline/requirements.txt
python -m pip install -r requirements-live.txt
npm ci --prefix netlify/functions
```

`requirements-live.txt` supports the live/BoltOdds-era worker dependencies; it
does not authorize restarting BoltOdds.

### 3. Authenticate GitHub

```bash
gh auth login
gh auth status
git fetch --prune origin
```

Expected GitHub account: `treidjbi`.

### 4. Link Supabase

The link state under `supabase/.temp/` is ignored and will not transfer.

```bash
npx --yes supabase login
npx --yes supabase link --project-ref htoaytcsjrdyyzcwxjfg
npx --yes supabase db query --linked -o json "select now();"
```

The final command is read-only. If the pooler returns circuit-breaker or auth
retries, do not hammer it with rapid repeated commands. Resolve the link or
wait before retrying.

### 5. Link Netlify

The link state under `.netlify/` is ignored and will not transfer.

```bash
npx --yes netlify-cli login
npx --yes netlify-cli link --id 47c15fdf-6278-4109-8877-545cc29eb418
npx --yes netlify-cli status
```

Linking is local configuration. Do not deploy during transfer validation.
The current `link --id` contract is documented in Netlify's official
[CLI command reference](https://cli.netlify.com/commands/link/).

### 6. Render access

Ordinary repo work and read-only artifact/Supabase checks do not require a
Render deploy. Configure Render CLI/account access only when Tyler needs live
service inspection or explicitly approves a deployment.

`scripts/deploy_render_pipeline_crons.py` is dry-run by default:

```bash
python scripts/deploy_render_pipeline_crons.py
```

The `--execute` flag creates deploys. Never add it merely to test the Mac.

## Read-only transfer acceptance checks

Run these after setup. They should not change production state.

### Git and source

```bash
git status --short
git branch --show-current
git remote get-url origin
git rev-parse HEAD
git ls-remote origin refs/heads/main
git diff --check
```

Expected: clean worktree, branch `main`, expected remote, and matching local and
remote `main` commit hashes.

### Python and Node

```bash
source .venv/bin/activate
python --version
node --version
npm --version
python -m pytest tests/ -q
node --test tests/*.mjs
```

Use Python 3.11.x. A newer system Python is not a substitute for the project
virtual environment.

### Public artifact path

```bash
curl -fsS "https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact?type=today" \
  | python -m json.tool >/dev/null
```

This checks the public artifact path only. It does not prove every scheduled
run or every artifact is healthy; use the BBE Operations Brief for that.

### Supabase link

```bash
npx --yes supabase db query --linked -o json "select now();"
```

For longer SQL, use a bounded `.sql` file and `--file`. Confirm columns before
querying. `market_snapshots` has no `slate_date`; join through
`market_provider_runs` using `run_id`.

### Storage guardrail

```bash
npx --yes supabase db query --linked --file scripts/supabase_storage_guardrail.sql -o json
```

This is read-only. Storage pressure does not authorize deletion.

### Retention tooling command shape

Use package/module invocation for the season readiness reporter:

```bash
python -m scripts.build_season_retention_readiness --help
```

Launching `python scripts/build_season_retention_readiness.py --help` directly
does not establish the repository root as the `scripts` package import path and
can fail. No script change is required for the transfer.

## Safe operating workflow on the Mac

At the start of each session:

```bash
git rev-parse --show-toplevel
git remote -v
git branch --show-current
git status --short
git pull --ff-only
```

Then read the current board and the active plan for the lane being changed.

For code or documentation changes:

1. Confirm Tyler's requested scope and approval boundaries.
2. Use a named branch for experimental work.
3. Keep changes small and avoid unrelated cleanup.
4. Run focused tests, then proportional broader verification.
5. Update the controlling plan and board only when their status actually
   changes.
6. Check `git status`, commit intentional changes, and push the branch.
7. Report any untracked or unpushed state explicitly.

Do not use `git reset --hard`, discard unexplained files, or copy one computer's
working tree over the other. Sync through GitHub.

## Deployment and repair boundaries

### Render pipeline deployment

After an approved code change reaches `main`, pipeline cron services still need
an explicit group deployment:

```bash
python scripts/deploy_render_pipeline_crons.py
```

Review the dry-run plan. Only after separate approval:

```bash
python scripts/deploy_render_pipeline_crons.py --execute
```

Verify every requested service and job afterward. A Git push alone is not proof
that Render runs the new commit.

### GitHub rollback/repair

`.github/workflows/pipeline.yml` is manual-only. Use `gh workflow run` or the
GitHub UI only when Tyler approves rollback or stale-artifact repair. After any
repair, verify the fresh Netlify/Supabase artifact path; workflow success alone
is insufficient.

### Artifact publication

`scripts/publish_pipeline_artifacts_to_supabase.py` is dry-run by default. Its
`--execute` flag writes artifacts. Do not use it during transfer validation.

### Retention and compaction

Retention, compaction writes, deletion, and vacuum have independent gates.
Read the newest August 2026 retention/compaction plans before even proposing an
execution. Default to preview/read-only evidence. A backup is not recovery
proof, and compaction is not deletion.

## Daily operations brief handoff

Automation name: `BBE Operations Brief`

Windows automation ID: `yesterdays-pipeline-health-bbe`

Windows memory location:
`$CODEX_HOME/automations/yesterdays-pipeline-health-bbe/memory.md`

Automation memory is local recent-work context, not canonical project truth.
It may not appear automatically on the Mac. Do not copy the entire Windows
`$CODEX_HOME` directory because it can contain host-specific state,
credentials, and unrelated project data.

On the Mac:

1. Check whether the automation exists in the Codex app and whether its memory
   file exists under the Mac `$CODEX_HOME`.
2. If it exists, read the latest dated entry after the canonical repo docs.
3. If it does not exist, recreate/manage the automation through Codex's
   automation UI/tools rather than writing scheduler metadata by hand.
4. Use this document's handoff snapshot as the starting overlay. If needed,
   transfer only the latest memory text through a secure local method after the
   new automation ID/path is known.
5. Never let automation memory override fresher verified artifacts or current
   docs.

The brief must keep system health, model health, bet-selection health, and
betting outcome separate. A winning slate does not prove a healthy model, and
a losing slate does not prove a broken system.

## Common migration mistakes to avoid

- Opening the wrong clone because a sidebar label looks familiar.
- Working from a stale Mac branch without fetching GitHub.
- Copying the Windows `.venv`, `node_modules`, `.netlify`, Supabase temp state,
  or full Codex home.
- Assuming local `analytics/output/` files are current production reports.
- Running a local pipeline with partial keys and treating it as production
  evidence.
- Printing service-role keys, database passwords, provider keys, or tokens in
  terminal output.
- Treating `render.yaml` as the production service definition.
- Assuming a Git push deployed Render services with auto-deploy off.
- Using GitHub Actions as the normal scheduler.
- Querying nonexistent `market_snapshots.slate_date`.
- Rapidly repeating Supabase CLI queries after pooler circuit-breaker errors.
- Testing the accepted-bet flow by saving a fake bet.
- Interpreting PropLine movement or UI value as provider/model promotion.
- Reviving BoltOdds because historical plans contain implementation details.
- Treating compaction completion or a fresh backup as deletion approval.

## Ready-to-paste first prompt for ChatGPT on the Mac

```text
You are taking over BaseballBettingEdge on Tyler's MacBook Air after the
2026-08-28 Windows-to-Mac transfer.

Before doing any project work, verify the repo root, origin, branch, worktree,
and GitHub sync. The expected repo is:
/Users/tyler/Documents/Codex/2026-05-02/pull-my-repos/BaseballbettingEdge
with origin https://github.com/treidjbi/BaseballbettingEdge.git.

Read these files in order:
1. AGENTS.md
2. docs/handoffs/2026-08-28-windows-to-mac-transfer.md
3. docs/current-state.md
4. docs/provider-cost-ledger.md
5. docs/operational-risk-register.md
6. docs/research/market-tracker-map.md
7. the newest active dated plan for the requested lane.

Treat Render -> Supabase published artifacts -> Netlify get-artifact as the
production path. TheRundown remains the official book-of-record source;
PropLine is approved fallback/live-movement sidecar evidence; BoltOdds is
retired. GitHub schedules are disabled and manual workflow_dispatch is
rollback/repair only.

Do not change production behavior, deploys, provider order or flags, model
parameters or formulas, thresholds, staking, notifications, locks, dashboard
behavior, accepted-bet data, secrets, retention, deletion, or source-of-truth
rules without Tyler's explicit separate approval. Default to read-only
evidence and preview modes.

After reading, report:
- whether the Mac clone and tool links are healthy;
- the current state of pipeline/infrastructure, model, UI, and
  tracking/history;
- any conflict between this transfer snapshot and fresher evidence;
- which gates are still closed;
- the safest next action.

Do not start implementation until Tyler approves the proposed plan.
```

## Transfer acceptance checklist

The migration is accepted only when all applicable boxes are proven on the
Mac:

- [ ] The expected Mac path resolves to the correct Git repository.
- [ ] `origin` is the expected GitHub URL.
- [ ] Local `main` matches remote `main` and contains this handoff commit.
- [ ] The worktree is clean or every intentional local change is documented.
- [ ] Python 3.11 virtual environment exists and dependencies install.
- [ ] Netlify function dependencies install with `npm ci`.
- [ ] GitHub CLI is authenticated as Tyler's intended account.
- [ ] Supabase CLI is linked to `htoaytcsjrdyyzcwxjfg` and `select now()` works.
- [ ] Netlify CLI is linked to site `47c15fdf-6278-4109-8877-545cc29eb418`.
- [ ] Public `today` artifact returns valid JSON.
- [ ] Python and Node test suites pass, or exact failures are recorded without
      guessing or changing production.
- [ ] The Mac-side agent can accurately summarize all four lanes and closed
      gates.
- [ ] Required credentials are available through secure sources; none were
      committed or pasted into chat.
- [ ] The BBE Operations Brief automation and its memory posture are known.
- [ ] No deploy, workflow dispatch, database write, notification send,
      accepted-bet write, retention action, or provider/model/UI change was
      performed merely to validate the transfer.

## Final Windows departure checklist

Before this laptop is retired:

1. Confirm this document and the `AGENTS.md` pointer are committed and pushed.
2. Confirm local and remote `main` heads match.
3. Confirm `git status --short` is empty.
4. Confirm no required unique project file exists only in an ignored Windows
   path.
5. Confirm secrets are recoverable from the password manager or provider
   dashboards, not only from the Windows keyring or an untracked file.
6. Do not delete cloud resources, cancel providers, rotate secrets, or remove
   the Windows clone as part of writing this document.

The first safe Mac task is transfer verification, not feature work or a
production change.
