# TheRundown + PropLine Official Provider And Webhook Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote the active low-cost TheRundown + PropLine path from sidecar evidence to an explicit official provider mode, while separately auditing PropLine webhooks for additional safe uses.

**Architecture:** Add a new `therundown_propline` official-market mode rather than reusing the retired `boltodds_propline` mode. The pipeline reads curated `official_market_lines` only after current-line/official-line preflight evidence passes, falls back to direct TheRundown in non-strict mode, and records source provenance clearly. PropLine webhooks remain movement/timing evidence first; the audit decides whether to expand them into UI labels, stronger alerts, or provider-refresh triggers.

**Tech Stack:** Python 3.11 pipeline and diagnostics, Supabase REST/CLI-backed market tables, Render cron wrappers, Netlify functions, pytest, existing vanilla dashboard surfaces.

## Status Update - 2026-06-24

- Tyler approved the narrow production posture change from sidecar-only to
  explicit non-strict `therundown_propline` official mode for live preview/full
  Render runs. TheRundown remains the direct fallback and strict mode stays
  closed.
- The Render wrapper now sets `OFFICIAL_MARKET_SOURCE=therundown_propline`,
  `ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE=true`,
  `OFFICIAL_MARKET_SOURCE_FALLBACK=therundown`, and
  `OFFICIAL_MARKET_STRICT=false` for live preview/full runs only. Grading, lock,
  shadow-prefixed runs, model math, staking, thresholds, and dashboard contracts
  remain unchanged.
- PropLine webhook rows remain movement/timing evidence, not official odds
  source rows. Webhook evidence processing keeps the 180-minute inbox window,
  but movement notifications now have a separate 20-minute queue-eligibility
  gate so stale webhook rows can be archived without creating dead
  notifications.
- Supported/actionable webhook movement notification books are a live-alert
  allow-list, not identical to the PropLine polling fallback target set. The
  current allow-list is FanDuel, DraftKings, BetMGM, BetRivers, Kalshi, Caesars,
  theScore/scorebet.
- Next proof step after merge/deploy: verify fresh Render preview/full artifacts
  show `market_source_mode=therundown_propline` or non-strict TheRundown fallback
  with no `boltodds_propline`, stale official rows, strict-mode behavior, model
  changes, or notification noise.
- Added `analytics/diagnostics/mainline_movement_pattern_audit.py` to evaluate
  the last-seven-day movement-notification pattern from processed
  `line_movement_events`, `notification_events`, `market_pick_evidence`, and
  `compact_market_line_movements`. It intentionally avoids broad raw
  `propline_webhook_deliveries` scans and remains read-only. First 2026-06-24
  report showed raw webhook volume is high, but reviewed candidate alert
  patterns still come from supported-book mainline polling; do not expand
  webhook alert classes from raw volume alone.

## Status Update - 2026-06-19

- `therundown_propline` mode support, non-strict TheRundown fallback, retired BoltOdds guards, provider parity CLI fallback, PropLine webhook audit, and cross-book line-conflict fail-closed behavior are implemented on `main`.
- Render pipeline cron services and `bbe-live-layer` are deployed on `1ec4a726`.
- Supabase live-layer rollup constraints were widened for `therundown` on `market_pick_evidence`, `live_market_display_state`, and `shadow_notification_candidates`; final live-layer one-off `job-d8qpj8u7r5hc73dflev0` succeeded.
- Latest parity report for 2026-06-19 is safer but not promotion-ready: line conflict rate is `0.0%`, but provider pitcher coverage is `22/29` (`75.9%`) and official-ready scheduled starter coverage is `21/28` (`75.0%`).
- Superseded on 2026-06-24 by Tyler's approval for the non-strict live wrapper
  flip. Strict mode and any source-of-truth/model promotion remain closed.

## Global Constraints

- BoltOdds stays retired; do not restart `bbe-boltodds-shadow-worker`.
- Do not set `OFFICIAL_MARKET_SOURCE=boltodds_propline` or `ENABLE_BOLTODDS_PIPELINE_SOURCE=true`.
- New official source mode must be `OFFICIAL_MARKET_SOURCE=therundown_propline`.
- New enable flag must be `ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE=true`.
- Initial production mode is non-strict: `OFFICIAL_MARKET_STRICT=false`.
- If curated official rows are stale, incomplete, below minimum coverage, or fail dashboard contract, the pipeline must fall back to direct TheRundown unless Tyler separately approves strict mode.
- Do not change model math, thresholds, staking, `formula_change_date`, confidence-referee behavior, profit-rescue behavior, market-anchor behavior, lock behavior, retention deletion, or dashboard source-of-truth in this plan.
- PropLine webhooks are not a full odds source by themselves. They can support movement, timing, confirmation, UI labels, alert strength, and refresh triggers only after audit evidence.
- Preserve source provenance fields: `odds_source`, `market_source_mode`, `line_source_provider`, `provider_coverage`, `provider_arbitration_reasons`, and source line IDs.

---

## File Structure

- Modify `pipeline/fetch_provider_market_odds.py`: introduce `therundown_propline` official mode, new enable flag, source labels, and legacy BoltOdds guard.
- Modify `pipeline/fetch_odds.py`: allow the new official mode to use curated provider rows with non-strict TheRundown fallback.
- Modify `scripts/run_render_pipeline_mode.py`: add optional TheRundown+PropLine official runtime overrides only after preflight support exists.
- Modify `market_infra/official_market_lines.py`: remove remaining BoltOdds-first assumptions from active selection reasons and tests where they no longer describe the current mode.
- Modify `analytics/diagnostics/provider_cutover_shadow_compare.py`: rename/report TheRundown+PropLine official parity, not BoltOdds cutover.
- Create `analytics/diagnostics/propline_webhook_usage_audit.py`: summarize signed webhook quality, lag, book metadata, polling overlap, notification impact, and candidate new uses.
- Create `tests/test_propline_webhook_usage_audit.py`: pure unit tests for webhook audit summarization.
- Modify existing tests in `tests/test_fetch_provider_market_odds.py`, `tests/test_fetch_odds.py`, `tests/test_render_pipeline_entrypoint.py`, `tests/test_official_market_lines.py`, and `tests/test_provider_cutover_shadow_compare.py`.
- Update `docs/current-state.md`, `AGENTS.md`, `docs/provider-cost-ledger.md`, `docs/operational-risk-register.md`, and `docs/research/market-tracker-map.md` after implementation and verification.

---

### Task 1: Add Explicit TheRundown + PropLine Official Mode

**Files:**
- Modify: `pipeline/fetch_provider_market_odds.py`
- Test: `tests/test_fetch_provider_market_odds.py`

**Interfaces:**
- Consumes: `OFFICIAL_MARKET_SOURCE`, `ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE`, `ENABLE_BOLTODDS_PIPELINE_SOURCE`, `ALLOW_BOLTODDS_PROVIDER_REHEARSAL`.
- Produces: `official_market_enabled()`, `official_row_to_prop()`, `fetch_official_market_odds()` with current-mode source labels.

- [ ] **Step 1: Write failing tests for the new mode and legacy guard**

Add tests like:

```python
def test_therundown_propline_mode_requires_new_enable_flag(monkeypatch):
    monkeypatch.setenv("OFFICIAL_MARKET_SOURCE", "therundown_propline")
    monkeypatch.delenv("ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE", raising=False)
    monkeypatch.delenv("ENABLE_BOLTODDS_PIPELINE_SOURCE", raising=False)
    assert official_market_enabled() is False

    monkeypatch.setenv("ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE", "true")
    assert official_market_enabled() is True


def test_retired_boltodds_mode_stays_closed_without_rehearsal_approval(monkeypatch):
    monkeypatch.setenv("OFFICIAL_MARKET_SOURCE", "boltodds_propline")
    monkeypatch.setenv("ENABLE_BOLTODDS_PIPELINE_SOURCE", "true")
    monkeypatch.delenv("ALLOW_BOLTODDS_PROVIDER_REHEARSAL", raising=False)
    assert official_market_enabled() is False
```

Update the row-to-prop source assertion:

```python
def test_official_row_to_prop_labels_therundown_propline_source(monkeypatch):
    monkeypatch.setenv("OFFICIAL_MARKET_SOURCE", "therundown_propline")
    prop = official_row_to_prop(_official_row(selected_provider="therundown"), {})
    assert prop["odds_source"] == "therundown+propline"
    assert prop["market_source_mode"] == "therundown_propline"
    assert prop["line_source_provider"] == "therundown"
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
python -m pytest tests/test_fetch_provider_market_odds.py -q
```

Expected before implementation: failures around missing `therundown_propline` mode and old `boltodds+propline` labels.

- [ ] **Step 3: Implement the minimal provider-mode change**

Change `pipeline/fetch_provider_market_odds.py` along these lines:

```python
THERUNDOWN_PROPLINE_MARKET_SOURCE = "therundown_propline"
LEGACY_BOLTODDS_PROPLINE_MARKET_SOURCE = "boltodds_propline"
THERUNDOWN_PROPLINE_ODDS_SOURCE = "therundown+propline"
LEGACY_BOLTODDS_PROPLINE_ODDS_SOURCE = "boltodds+propline"


def official_market_enabled() -> bool:
    mode = official_market_source_mode()
    if mode == THERUNDOWN_PROPLINE_MARKET_SOURCE:
        return _truthy(os.environ.get("ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE", "false"))
    if mode == LEGACY_BOLTODDS_PROPLINE_MARKET_SOURCE:
        return (
            _truthy(os.environ.get("ALLOW_BOLTODDS_PROVIDER_REHEARSAL", "false"))
            and _truthy(os.environ.get("ENABLE_BOLTODDS_PIPELINE_SOURCE", "false"))
        )
    return False


def official_market_source_label() -> str:
    mode = official_market_source_mode()
    if mode == THERUNDOWN_PROPLINE_MARKET_SOURCE:
        return THERUNDOWN_PROPLINE_MARKET_SOURCE
    if mode == LEGACY_BOLTODDS_PROPLINE_MARKET_SOURCE:
        return LEGACY_BOLTODDS_PROPLINE_MARKET_SOURCE
    return mode


def official_odds_source_label() -> str:
    mode = official_market_source_mode()
    if mode == THERUNDOWN_PROPLINE_MARKET_SOURCE:
        return THERUNDOWN_PROPLINE_ODDS_SOURCE
    if mode == LEGACY_BOLTODDS_PROPLINE_MARKET_SOURCE:
        return LEGACY_BOLTODDS_PROPLINE_ODDS_SOURCE
    return mode
```

Then use those functions in `official_row_to_prop()`:

```python
"odds_source": official_odds_source_label(),
"market_source_mode": official_market_source_label(),
```

- [ ] **Step 4: Run focused tests and verify pass**

Run:

```bash
python -m pytest tests/test_fetch_provider_market_odds.py -q
```

Expected: all tests in that file pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch_provider_market_odds.py tests/test_fetch_provider_market_odds.py
git commit -m "feat: add therundown propline official mode"
```

---

### Task 2: Wire New Official Mode Through `fetch_odds` With Non-Strict Fallback

**Files:**
- Modify: `pipeline/fetch_odds.py`
- Test: `tests/test_fetch_odds.py`

**Interfaces:**
- Consumes: `official_market_enabled()`, `official_market_strict_mode()`, `fetch_official_market_odds()`.
- Produces: unchanged public `fetch_odds(date_str)` behavior except new official mode can use curated rows.

- [ ] **Step 1: Write failing tests for new mode fetch behavior**

Add tests parallel to the existing BoltOdds-mode tests:

```python
def test_official_market_source_therundown_propline_uses_curated_rows(self):
    provider_props = [{"pitcher": "Gerrit Cole", "k_line": 7.5, "odds_source": "therundown+propline"}]
    with patch.dict(
        "os.environ",
        {
            "OFFICIAL_MARKET_SOURCE": "therundown_propline",
            "ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE": "true",
        },
    ):
        with patch("fetch_odds.fetch_official_market_odds", return_value=provider_props):
            with patch("fetch_odds._fetch_therundown_odds") as mock_therundown:
                result = fetch_odds("2026-05-13")

    assert result == provider_props
    mock_therundown.assert_not_called()


def test_therundown_propline_non_strict_falls_back_to_therundown(self):
    fallback_props = [{"pitcher": "Gerrit Cole", "k_line": 7.5, "odds_source": "therundown"}]
    with patch.dict(
        "os.environ",
        {
            "OFFICIAL_MARKET_SOURCE": "therundown_propline",
            "ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE": "true",
            "OFFICIAL_MARKET_STRICT": "false",
        },
    ):
        with patch("fetch_odds.fetch_official_market_odds", return_value=[]):
            with patch("fetch_odds._fetch_therundown_odds", return_value=fallback_props):
                result = fetch_odds("2026-05-13")

    assert result == fallback_props
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
python -m pytest tests/test_fetch_odds.py -q
```

Expected before implementation: new mode does not route through official rows.

- [ ] **Step 3: Implement minimal routing**

Use the existing provider-market branch. Do not add a second branch. The implementation should become source-mode agnostic:

```python
if official_market_enabled():
    provider_props = fetch_official_market_odds(date_str)
    if provider_props:
        return provider_props
    if official_market_strict_mode():
        raise OfficialMarketSourceError(...)
    return _fetch_therundown_odds(date_str)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_fetch_odds.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/fetch_odds.py tests/test_fetch_odds.py
git commit -m "feat: route therundown propline official odds"
```

---

### Task 3: Add Render Wrapper Support Without Enabling Strict Mode

**Files:**
- Modify: `scripts/run_render_pipeline_mode.py`
- Test: `tests/test_render_pipeline_entrypoint.py`

**Interfaces:**
- Consumes: Render mode and artifact key prefix.
- Produces: runtime env overrides for live preview/full only.

- [ ] **Step 1: Write failing wrapper test**

Update the live official provider test:

```python
def test_live_official_provider_uses_therundown_propline_mode_for_live_preview_and_pipeline():
    for mode in ("preview", "pipeline"):
        overrides = run_render_pipeline_mode.live_official_provider_env_overrides(mode, "")
        assert overrides["OFFICIAL_MARKET_SOURCE"] == "therundown_propline"
        assert overrides["ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE"] == "true"
        assert overrides["ENABLE_BOLTODDS_PIPELINE_SOURCE"] == "false"
        assert overrides["OFFICIAL_MARKET_STRICT"] == "false"
```

Keep the shadow-prefix test proving shadow runs still force TheRundown unless explicitly approved.

- [ ] **Step 2: Run focused test and verify failure**

Run:

```bash
python -m pytest tests/test_render_pipeline_entrypoint.py -q
```

Expected before implementation: overrides still set `OFFICIAL_MARKET_SOURCE=therundown`.

- [ ] **Step 3: Implement wrapper override**

Change only the live official override:

```python
return {
    "OFFICIAL_MARKET_SOURCE": "therundown_propline",
    "OFFICIAL_MARKET_SOURCE_FALLBACK": "therundown",
    "ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE": "true",
    "ENABLE_BOLTODDS_PIPELINE_SOURCE": "false",
    "OFFICIAL_MARKET_STRICT": "false",
}
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_render_pipeline_entrypoint.py tests/test_fetch_odds.py tests/test_fetch_provider_market_odds.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_render_pipeline_mode.py tests/test_render_pipeline_entrypoint.py
git commit -m "feat: set therundown propline render mode"
```

---

### Task 4: Strengthen Official-Line Preflight And Parity Reporting

**Files:**
- Modify: `analytics/diagnostics/provider_cutover_shadow_compare.py`
- Modify: `tests/test_provider_cutover_shadow_compare.py`

**Interfaces:**
- Consumes: TheRundown production props, curated `official_market_lines` props, `current_market_lines`, provider usage rows.
- Produces: `analytics/output/provider_cutover_shadow_compare_YYYY-MM-DD.md` and `.json` renamed in text to TheRundown+PropLine official parity.

- [ ] **Step 1: Write failing report-label tests**

Update assertions so reports no longer describe the active comparison as BoltOdds cutover:

```python
def test_markdown_report_names_therundown_propline_official_parity():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[_prop("Jose Berrios", odds_source="therundown+propline")],
        generated_at=NOW,
    )
    markdown = format_markdown_report(report)
    assert "TheRundown + PropLine Official Provider Parity" in markdown
    assert "BoltOdds + PropLine" not in markdown.splitlines()[0]
```

- [ ] **Step 2: Add readiness gates for the new official mode**

Gates to report:

```text
official_provider_pitcher_coverage_90
official_provider_fd_or_dk_coverage_85
official_rows_ready_for_pipeline_90
line_conflict_rate_under_10
prop_contract_valid
propline_usage_under_70_percent_hobby
no_boltodds_active_rows
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
python -m pytest tests/test_provider_cutover_shadow_compare.py -q
```

- [ ] **Step 4: Implement report changes**

Keep function names to avoid broad churn, but update user-facing titles and gate labels.

- [ ] **Step 5: Run same-day read-only report before any deployment**

Run:

```bash
python analytics/diagnostics/provider_cutover_shadow_compare.py --date 2026-06-19 --provider-min-props 1
```

Expected: writes output report only; does not change artifacts, env vars, picks, locks, or notifications.

- [ ] **Step 6: Commit**

```bash
git add analytics/diagnostics/provider_cutover_shadow_compare.py tests/test_provider_cutover_shadow_compare.py analytics/output/provider_cutover_shadow_compare_2026-06-19.md analytics/output/provider_cutover_shadow_compare_2026-06-19.json
git commit -m "chore: update provider parity report for therundown propline"
```

---

### Task 5: Build PropLine Webhook Usage Audit

**Files:**
- Create: `analytics/diagnostics/propline_webhook_usage_audit.py`
- Create: `tests/test_propline_webhook_usage_audit.py`

**Interfaces:**
- Consumes rows shaped like `propline_webhook_deliveries`, `line_movement_events`, `notification_events`, `market_pick_evidence`, and optionally `accepted_bets`.
- Produces `analytics/output/propline_webhook_usage_audit_YYYY-MM-DD.md` and `.json`.

- [ ] **Step 1: Write pure summarizer tests**

Test these cases without Supabase access:

```python
def test_summarize_webhook_rows_counts_signed_processed_and_book_metadata():
    summary = summarize_webhook_usage(
        deliveries=[
            {
                "id": "1",
                "signature_valid": True,
                "processed": True,
                "processing_error": None,
                "received_at": "2026-06-19T16:00:00+00:00",
                "payload": {
                    "event_type": "line_movement",
                    "bookmaker_key": "draftkings",
                    "bookmaker_title": "DraftKings",
                    "market_id": "m1",
                    "outcome_id": "o1",
                },
            }
        ],
        movement_events=[],
        notification_events=[],
        market_pick_evidence=[],
        accepted_bets=[],
    )
    assert summary["deliveries"] == 1
    assert summary["signed_deliveries"] == 1
    assert summary["processed_deliveries"] == 1
    assert summary["with_bookmaker_key"] == 1
    assert summary["with_stable_market_ids"] == 1
```

```python
def test_summarize_webhook_rows_recommends_dashboard_badge_not_source_switch_for_webhook_only_moves():
    summary = summarize_webhook_usage(
        deliveries=[],
        movement_events=[
            {
                "source": "propline_webhook",
                "bookmaker_key": "fanduel",
                "movement_kind": "odds",
                "observed_at": "2026-06-19T16:00:00+00:00",
            }
        ],
        notification_events=[],
        market_pick_evidence=[],
        accepted_bets=[],
    )
    assert "dashboard_webhook_confirmed_badge" in summary["recommended_uses"]
    assert "official_odds_source" not in summary["recommended_uses"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest tests/test_propline_webhook_usage_audit.py -q
```

Expected: import failure before the diagnostic exists.

- [ ] **Step 3: Implement pure summarizer and CLI**

Create:

```python
def summarize_webhook_usage(
    *,
    deliveries: list[dict[str, Any]],
    movement_events: list[dict[str, Any]],
    notification_events: list[dict[str, Any]],
    market_pick_evidence: list[dict[str, Any]],
    accepted_bets: list[dict[str, Any]],
) -> dict[str, Any]:
    ...
```

Required output keys:

```text
deliveries
signed_deliveries
processed_deliveries
unsupported_deliveries
with_bookmaker_key
with_stable_market_ids
line_movement_events
webhook_notification_events
duplicate_dedupe_keys
post_start_or_stale_events
webhook_only_movement_events
polling_confirmed_movement_events
accepted_bet_overlap_count
recommended_uses
blocked_uses
```

Recommended uses can include:

```text
dashboard_webhook_confirmed_badge
movement_strength_label
notification_priority_boost
accepted_bet_context_tag
provider_refresh_trigger_shadow
```

Blocked uses must include:

```text
official_odds_source
model_input
staking_input
automatic_bet_trigger
```

- [ ] **Step 4: Add Supabase read-only CLI path**

The CLI should accept:

```bash
python analytics/diagnostics/propline_webhook_usage_audit.py --date 2026-06-19 --lookback-days 3
```

It should read bounded rows only:

```text
propline_webhook_deliveries received_at >= start and <= end
line_movement_events slate_date between dates and metadata->source = propline_webhook where possible
notification_events slate_date between dates
market_pick_evidence slate_date between dates
accepted_bets accepted_at between dates when table exists
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
python -m pytest tests/test_propline_webhook_usage_audit.py tests/test_process_propline_webhooks.py -q
```

Expected: all pass.

- [ ] **Step 6: Run live read-only audit**

Run:

```bash
python analytics/diagnostics/propline_webhook_usage_audit.py --date 2026-06-19 --lookback-days 3
```

Expected: writes `analytics/output/propline_webhook_usage_audit_2026-06-19.md` and `.json`.

- [ ] **Step 7: Commit**

```bash
git add analytics/diagnostics/propline_webhook_usage_audit.py tests/test_propline_webhook_usage_audit.py analytics/output/propline_webhook_usage_audit_2026-06-19.md analytics/output/propline_webhook_usage_audit_2026-06-19.json
git commit -m "chore: audit propline webhook decision value"
```

---

### Task 6: Decide And Implement First Safe Webhook Expansion

**Files:**
- Likely modify: `market_infra/live_market_display.py`
- Likely modify: `netlify/functions/live-market-display.mjs`
- Likely modify: `dashboard/v2-app.jsx`
- Test: existing live-market display and dashboard tests.

**Interfaces:**
- Consumes: webhook audit output from Task 5.
- Produces one narrow enhancement only.

- [ ] **Step 1: Pick exactly one expansion from audit results**

Allowed first choices:

```text
dashboard_webhook_confirmed_badge
movement_strength_label
notification_priority_boost
accepted_bet_context_tag
provider_refresh_trigger_shadow
```

Default recommendation if audit is clean: `dashboard_webhook_confirmed_badge`, because it improves operator interpretation without changing picks or sends.

- [ ] **Step 2: Write tests for selected expansion**

Example if badge is selected:

```python
def test_live_market_display_marks_recent_webhook_confirmed_movement():
    rows = build_live_market_display_rows(...)
    assert rows[0]["metadata"]["webhook_confirmed"] is True
    assert rows[0]["metadata"]["webhook_books"] == ["draftkings"]
```

- [ ] **Step 3: Implement minimal expansion**

Keep it read-only/display-only unless Tyler separately approves alert behavior.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_market_infra_live_market_display.py tests/test_live_market_display_function.mjs -q
```

Adjust command if JS tests use the repo's existing npm/node invocation.

- [ ] **Step 5: Commit**

```bash
git add market_infra/live_market_display.py netlify/functions/live-market-display.mjs dashboard/v2-app.jsx tests
git commit -m "feat: surface propline webhook confirmation"
```

---

### Task 7: Documentation, Deployment, And Rollback Handoff

**Files:**
- Modify: `docs/current-state.md`
- Modify: `AGENTS.md`
- Modify: `docs/provider-cost-ledger.md`
- Modify: `docs/operational-risk-register.md`
- Modify: `docs/research/market-tracker-map.md`

**Interfaces:**
- Consumes: test results, live parity report, webhook usage audit.
- Produces: durable handoff docs and rollback instructions.

- [ ] **Step 1: Update docs with exact new posture**

Document:

```text
Official provider mode: therundown_propline
Primary source: TheRundown
Fallback/current-line supplement: PropLine supported books
Strict mode: false
Rollback: OFFICIAL_MARKET_SOURCE=therundown, ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE=false
Closed: boltodds_propline, ENABLE_BOLTODDS_PIPELINE_SOURCE, strict provider
```

- [ ] **Step 2: Run full focused suite**

Run:

```bash
python -m pytest tests/test_fetch_provider_market_odds.py tests/test_fetch_odds.py tests/test_official_market_lines.py tests/test_build_current_market_lines_to_supabase.py tests/test_build_official_market_lines_to_supabase.py tests/test_provider_cutover_shadow_compare.py tests/test_process_propline_webhooks.py tests/test_live_layer_worker.py -q
```

- [ ] **Step 3: Verify current artifact source after deploy**

After Tyler approves deployment and Render cron redeploy:

```bash
python scripts/deploy_render_pipeline_crons.py --execute
```

Then verify:

```bash
npx supabase db query --linked -o json "select artifact_type, artifact_key, generated_at, metadata from published_pipeline_artifacts where artifact_type in ('today','dated_slate','preview_lines') order by published_at desc limit 10;"
```

Expected after official mode is live:

```text
odds_source contains therundown+propline only when curated official rows passed preflight
market_source_mode is therundown_propline for provider-official rows
fallback artifacts remain odds_source=therundown if preflight failed in non-strict mode
no BoltOdds rows are consumed
```

- [ ] **Step 4: Commit docs**

```bash
git add docs/current-state.md AGENTS.md docs/provider-cost-ledger.md docs/operational-risk-register.md docs/research/market-tracker-map.md
git commit -m "docs: document therundown propline official posture"
```

---

## Promotion Decision Gates

The first live flip should not happen until the same-day parity report shows:

- At least 90% production-pitcher coverage from ready `official_market_lines`.
- FanDuel or DraftKings coverage for at least 85% of production pitchers.
- No stale official rows used in FIRE picks.
- Line-conflict rows either match TheRundown ref book or fail closed.
- PropLine request usage stays below 70% of the assumed 5,000/day Hobby budget.
- No fresh BoltOdds rows after `2026-06-17T17:22:29Z`.
- Dashboard artifact contract validates for provider-official output.
- Non-strict fallback to direct TheRundown works.

Webhook expansion should not happen until the webhook audit shows:

- Signed delivery rate is effectively 100%.
- Bookmaker key/title and market/outcome IDs are present on normal movement rows.
- Unsupported rows are mostly known alt ladders or non-standard markets.
- Duplicate dedupe keys are not creating repeated sends.
- Webhook movement is not mostly post-start/stale.
- Webhook rows add timing or confirmation value beyond 10-minute polling.

## Recommended Execution Order

1. Task 1 and Task 2: source-mode correctness.
2. Task 4 and Task 5: live read-only evidence reports.
3. Tyler yes/no review on the reports.
4. Task 3: Render wrapper official-mode flip.
5. Task 6: one webhook expansion, preferably display-only first.
6. Task 7: docs, deploy, and rollback proof.

## Self-Review

- Spec coverage: The plan covers official TheRundown+PropLine promotion, PropLine webhook evaluation, BoltOdds retirement, non-strict fallback, docs, tests, and rollout gates.
- Placeholder scan: No task depends on an unspecified implementation path; the only choice point is Task 6 and it is intentionally gated by audit output.
- Type consistency: New mode names are consistent: `therundown_propline`, `ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE`, `therundown+propline`.
