# BoltOdds Retirement Test Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the obsolete 28-test BoltOdds WebSocket worker behavior suite from the default release gate while retaining compact accidental-reactivation guards and historical parser coverage.

**Architecture:** This is a test-only retirement cleanup. Delete the former worker behavior test file, add one small static guard file for deployment surfaces, and rely on the existing provider-exclusion and fail-closed suites for runtime posture. Production code remains byte-unchanged.

**Tech Stack:** Python 3.11+, pytest, pathlib, Git.

## Global Constraints

- Modify tests and these handoff documents only.
- Do not modify `scripts/boltodds_ws_worker.py` or production code.
- Do not alter provider flags, provider order, source-of-truth behavior,
  notifications, locks, artifacts, model behavior, Supabase, Render, or Netlify.
- Preserve all existing provider-exclusion, fail-closed, and historical parser
  tests outside `tests/test_boltodds_ws_worker.py`.
- Do not change the reviewed Alt Picks branches.
- Commit and push this branch only; do not merge or deploy.

---

### Task 1: Replace the retired worker suite with static retirement guards

**Files:**

- Delete: `tests/test_boltodds_ws_worker.py`
- Create: `tests/test_boltodds_retirement.py`

**Interfaces:**

- Consumes: repository text files `render.yaml`, `.github/workflows/*.yml`,
  `.github/workflows/*.yaml`, and `scripts/deploy_render_pipeline_crons.py`.
- Produces: three deterministic pytest guards; no runtime interface.

- [ ] **Step 1: Preserve RED evidence for the obsolete suite**

Run the known flaky test repeatedly on the untouched baseline:

```powershell
$failures = 0
1..20 | ForEach-Object {
  python -m pytest tests/test_boltodds_ws_worker.py::test_worker_rotation_starts_new_run_before_writing_new_slate_snapshots -q
  if ($LASTEXITCODE -ne 0) { $failures++ }
}
Write-Output "retired_worker_flake_failures=$failures"
```

Expected: the test can pass or fail based on timing; prior verified evidence is
`1/10` failures on untouched `main` and `3/10` on the reviewed Alt worktree.
This red evidence concerns the test gate, not production behavior.

- [ ] **Step 2: Write the compact retirement guard file**

Create `tests/test_boltodds_retirement.py` with three tests:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RETIRED_WORKER_PATH = "scripts/boltodds_ws_worker.py"
RETIRED_SERVICE_NAME = "bbe-boltodds-shadow-worker"


def test_render_blueprint_cannot_recreate_retired_boltodds_worker():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "services: []" in text
    assert RETIRED_WORKER_PATH not in text
    assert RETIRED_SERVICE_NAME not in text


def test_github_workflows_do_not_launch_retired_boltodds_worker():
    workflow_dir = ROOT / ".github" / "workflows"
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for pattern in ("*.yml", "*.yaml")
        for path in sorted(workflow_dir.glob(pattern))
    )
    assert RETIRED_WORKER_PATH not in text
    assert RETIRED_SERVICE_NAME not in text


def test_render_cron_deployer_does_not_launch_retired_boltodds_worker():
    text = (ROOT / "scripts" / "deploy_render_pipeline_crons.py").read_text(
        encoding="utf-8"
    )
    assert RETIRED_WORKER_PATH not in text
    assert RETIRED_SERVICE_NAME not in text
```

- [ ] **Step 3: Delete the obsolete worker behavior suite**

Delete `tests/test_boltodds_ws_worker.py` without changing the retired worker
implementation or any other test file.

- [ ] **Step 4: Run the retirement and provider-posture tests**

```powershell
python -m pytest tests/test_boltodds_retirement.py tests/test_fetch_provider_market_odds.py tests/test_render_pipeline_entrypoint.py tests/test_market_infra_live_market_display.py tests/test_market_infra_market_evidence.py tests/test_build_official_market_lines_to_supabase.py tests/test_official_market_lines.py tests/test_market_infra_boltodds_client.py tests/test_market_infra_boltodds_snapshot.py tests/test_probe_boltodds_markets.py -q
```

Expected: all pass with no skips.

- [ ] **Step 5: Run full verification**

```powershell
python -m pytest tests/ -q
node --test dashboard/*.test.mjs tests/*.mjs
git diff --check
git status --short
```

Expected: all commands exit zero; the Python suite contains 25 fewer tests
than the 1,586-test baseline because 28 worker tests are replaced by 3 guards.

- [ ] **Step 6: Commit the implementation**

```powershell
git add tests/test_boltodds_retirement.py tests/test_boltodds_ws_worker.py
git commit -m "test: retire BoltOdds worker behavior suite"
```

Expected: the commit changes test files only.

---

### Task 2: Independently review and publish the cleanup branch

**Files:**

- Git history only.

**Interfaces:**

- Consumes: Task 1 commit and verification report.
- Produces: a reviewed remote branch; no production mutation.

- [ ] **Step 1: Review exact scope and safety**

Confirm the diff contains only:

- deletion of `tests/test_boltodds_ws_worker.py`;
- creation of `tests/test_boltodds_retirement.py`; and
- the approved design and plan documents.

Confirm production code and all existing provider-exclusion/fail-closed tests
are byte-unchanged.

- [ ] **Step 2: Run final verification after review**

```powershell
python -m pytest tests/ -q
node --test dashboard/*.test.mjs tests/*.mjs
git diff --check
git status --short --branch
```

Expected: 1,561 Python tests and 99 Node tests pass; the branch is clean.

- [ ] **Step 3: Push without merging**

```powershell
git push -u origin codex/retire-boltodds-worker-tests
```

Expected: the remote branch matches local HEAD; `main` and all production
systems remain unchanged.
