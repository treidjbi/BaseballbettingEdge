# All-Star Break Operations Packet

Date: 2026-07-13

Status: break-window maintenance and review packet. This is not approval for
model, threshold, staking, provider, notification, lock, retention,
dashboard-source, Render environment, or `formula_change_date` changes.

## Executive Read

Use the All-Star break to reduce operational noise and sharpen the post-break
read. Do not use the gap to promote a model, provider, notification class, or
retention job.

The four useful tracks are:

1. Patch the off-day `dated_slate` hydration failure so no-slate refresh runs
   do not create false Render failure alerts.
2. Run a post-break restart checklist on the first real slate before trusting
   any model or provider conclusions.
3. Keep tracking the actual `strict_runtime_core_plus_selective_lean` record,
   with pre-close and market-anchor overlays as review flags only.
4. Keep cost and row-volume evidence current, but leave cadence and deletion
   decisions closed without a separate approval.

## Off-Day Artifact Noise

Observed failure:

- On 2026-07-13, `bbe-pipeline-refresh-day` attempted to hydrate
  `get-artifact?type=dated_slate&date=2026-07-13` before running.
- Netlify returned `404`.
- The same date had no normal MLB slate, so a current-day dated archive was not
  expected to exist yet.

Fix scope:

- Treat a missing pre-run `dated_slate` hydration artifact as optional.
- Keep `today`, `picks_history`, `params`, `performance`, `preview_lines`,
  `steam`, and required non-dated artifacts fail-closed.
- Do not change publication scope, provider source, model behavior, lock
  behavior, or dashboard source.

Post-fix proof should be a targeted regression test plus one post-break Render
run showing normal hydration/publish behavior.

Implementation status:

- Local branch patch updates `scripts/run_render_pipeline_mode.py` so
  `dated_slate` hydration is explicitly `required=False`.
- Regression coverage in `tests/test_render_pipeline_entrypoint.py` verifies a
  same-day `dated_slate` 404 is skipped and a required `today` 404 still fails.
- This patch is not a Render deployment by itself.

## Post-Break Restart Checklist

On the first real slate after the break:

- Verify `today.json` `generated_at`, production source/mode, pitcher count,
  tracked pick count, and provider attribution.
- Confirm `dated_slate`, `steam`, `performance`, `params`, `preview_lines`, and
  `picks_history` are fresh through Netlify `get-artifact`.
- Confirm grading has updated the prior graded slate before interpreting
  model or betting performance.
- Confirm live-layer reads the Netlify/Supabase artifact, not checkout JSON.
- Confirm `operational_pick_locks` has due rows, consumed rows, source artifact
  paths, and no started-unlocked rows.
- Confirm `notification_events` has no stale/post-start sends or duplicate
  dedupe keys.
- Confirm PropLine sidecar rows and TheRundown/PropLine display rows are fresh,
  but keep them separate from model/source-of-truth promotion.
- Confirm BoltOdds has no fresh rows after the documented suspension timestamp.

If any item fails, treat the first step as infrastructure repair of the current
approved path, not model/provider promotion.

## Strict Runtime Tracking

Current governing packet:

- `docs/research/strict-runtime-core-selective-lean-canary-packet.md`
- `analytics/output/shadow_signal_synthesis_lab.md`

Current read through the 2026-07-12 slate:

| Selector | Picks | Record | Units | ROI |
| --- | ---: | ---: | ---: | ---: |
| `strict_runtime_core_plus_selective_lean` | 231 | 142-89 | +27.46u | +11.9% |

Weekend interpretation:

- The added weekend rows were `6`, `2-4`, `-2.72u`.
- That was a real drawdown from the 2026-07-10 packet base of `225`, `140-85`,
  `+30.18u`.
- It does not invalidate the selector, but it makes the review focus obvious:
  pre-close support first, market-anchor confirmation second.

Overlay reads:

| Slice | Picks | Record | Units | ROI | Read |
| --- | ---: | ---: | ---: | ---: | --- |
| Full selector | 231 | 142-89 | +27.46u | +11.9% | Actual-record base |
| Strong pre-close | 168 | 110-58 | +30.26u | +18.0% | Best near-term overlay |
| Market-anchor core | 43 | 31-12 | +10.25u | +23.8% | Promising but small |

Known risk flags:

- Market against model: `17-19`, `-4.83u`.
- Weak pre-close: `6-10`, `-3.03u`.
- Worse close price: `17-16`, `-2.93u`.
- Price bucket `+100` to `+119`: `15-18`, `-2.07u`.

Recommendation:

- Keep the selector id unchanged.
- Keep the actual full record visible after each graded slate.
- Do not draft a separate canary plan unless Tyler asks for that review or the
  overlay slices survive the stated promotion floors.

## Cost And Row-Volume Read

Read-only checks on 2026-07-13:

- Supabase linked CLI storage guardrail: database `2539 MB`, `30.99%` of the
  8 GB Pro included allowance.
- Largest table: `market_snapshots`, about `1818 MB` total with indexes and
  `2,002,709` estimated rows.
- Other notable tables: `propline_webhook_deliveries` about `111 MB`,
  `shadow_notification_candidates` about `104 MB`,
  `compact_market_line_movements` about `97 MB`,
  `provider_arbitration_decisions` about `82 MB`, and
  `line_movement_events` about `80 MB`.

Render bandwidth, month-to-date 2026-07-01 through 2026-07-13 20:00Z:

| Service | GB | Approx. overage-equivalent at $0.15/GB |
| --- | ---: | ---: |
| `bbe-pipeline-lock` | 4.63 | $0.69 |
| `bbe-live-layer` | 1.78 | $0.27 |
| `bbe-pipeline-refresh-day` | 0.71 | $0.11 |
| All other checked BBE Render services combined | 0.24 | $0.04 |

Read:

- Storage growth is worth tracking but not urgent.
- Render bandwidth is concentrated in lock/live-layer paths, but the dollar
  exposure is still small.
- No cadence reduction, retention execution, provider reduction, or paid-tier
  change is justified from this break read alone.
- The next cost step, if needed, is a retention-readiness dry run and exact
  compact-coverage proof, not deletion.

## Do Not Do During The Gap

- Do not pause or change production schedules just because there are fewer
  games.
- Do not deploy model/ranking/staking changes into a thin restart sample.
- Do not enable strict provider mode or change source-of-truth.
- Do not enable retention deletion.
- Do not broaden notification classes.
- Do not treat off-day 404 noise as a failed production slate.

## Next Work

1. Merge and deploy the off-day hydration fix only after tests pass and Tyler
   wants it on Render.
2. Run the post-break restart checklist on the first real slate.
3. Keep the strict-runtime actual-record line in the daily brief after grading.
4. Rerun storage guardrail after the first full post-break slate and compare
   `market_snapshots`, webhook deliveries, lock rows, notification rows, and
   compact movement rows.
