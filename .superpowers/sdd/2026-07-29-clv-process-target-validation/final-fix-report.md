# Final CLV Process Target Review Fix Report

Run: 2026-07-30 America/Phoenix

## Implemented

- Replaced the runner's implicit `market_pick_evidence` close input with the
  explicit `--clv-process-target-close-evidence` packet. The agreement/movement
  export remains isolated from final-CLV validation.
- Added bounded JSON/JSONL close-packet validation: every non-empty row must be
  an `official_close` with identity, provider/book, observation id,
  timezone-aware timestamp, numeric line/price, and freshness. A valid empty
  packet is accepted. Missing, unreadable, malformed, and wrong-schema packets
  emit `proxy_failed` without stopping later shadow reports.
- Preserved Gate C `pick_history_pnl` and `theoretical_pnl` only as top-level,
  descriptive report context; neither enters pre-close proxy inputs.
- Corrected the runner's current-era lookup to the shared
  `official_therundown_propline` label.
- Enforced timezone-aware timestamps and `close > lock`, returning
  `invalid_lock_timestamp`, `invalid_close_timestamp`, or
  `close_not_after_lock` as applicable.
- Updated the controlling plan first, then the CLV research review and current
  state: no approved close-packet producer exists; refreshed movement exports
  are insufficient; policy remains `keep_as_process_kpi`; default runner state
  is `proxy_failed` until an explicit valid packet exists.

## TDD Evidence

1. Explicit close packet boundary
   - RED: `python -m pytest tests/test_post_grading_shadow_reports.py -q -k distinct_explicit_close_packet`
     failed because `--clv-process-target-close-evidence` was unrecognized.
   - GREEN: same focused run passed after adding the explicit runner/validator
     arguments and keeping movement input out of CLV arguments.
2. Movement-rollup rejection
   - RED: `python -m pytest tests/test_post_grading_shadow_reports.py -q -k rejects_real_shape_market_pick_evidence`
     failed because the runner invoked CLV for a real-shape movement row.
   - GREEN: the three runner boundary tests passed after packet validation.
3. Descriptive PnL isolation
   - RED: `python -m pytest tests/test_clv_process_target_validation.py -q -k preserves_gate_c_pnl`
     failed with missing `pick_history_pnl` on the target row.
   - GREEN: the same test passed after retaining PnL outside proxy inputs.
4. Provider-era label
   - RED: `python -m pytest tests/test_post_grading_shadow_reports.py -q -k shared_official_provider_era_label`
     printed current-provider drift as `--`.
   - GREEN: the same test passed after using
     `official_therundown_propline`.
5. Timestamp eligibility
   - RED: `python -m pytest tests/test_clv_process_target_validation.py -q -k aware_strictly_later_close_timestamp`
     produced three `eligible` rows for invalid/non-increasing timestamps.
   - GREEN: the same test passed after aware parsing and strict ordering.
6. Validator contract and row schema
   - RED: `python -m pytest tests/test_clv_process_target_validation.py -q -k main_writes_process_only`
     failed because `--market-input` remained required; the side-schema test
     also failed because a non-OVER/UNDER side was accepted.
   - GREEN: both focused tests passed after the close-evidence CLI and schema
     guard were added.

Malformed and unreadable packet tests also pass and prove the runner continues
to later shadow reports with bounded `proxy_failed` output.

## Verification

- `python -m pytest tests/test_clv_process_target_validation.py tests/test_post_grading_shadow_reports.py -q` — 43 passed.
- `python -m pytest tests/test_export_market_agreement_inputs.py tests/test_market_agreement_tracker.py tests/test_gate_f_preclose_clv_proxy_lab.py -q` — 25 passed.
- `python -m pytest tests -q` — 2000 passed in 103.15s after restoring the
  generated Gate F report.
- `python -m py_compile analytics/diagnostics/clv_process_target_validation.py scripts/run_post_grading_shadow_reports.py` — passed.
- `git diff --check` — passed.

## Self-review

The patch is limited to the offline CLV validator/runner, their tests, and
required handoff documents. It adds no producer, exporter, database/schema,
runtime/provider/model/notification/lock/UI/environment, deployment, or raw
snapshot reconstruction behavior. The pre-existing generated Gate F report is
restored before commit and excluded from the final diff.

## Concerns

No approved producer exists for the explicit official-close packet. This is
intentional fail-closed posture, not a production readiness signal.
