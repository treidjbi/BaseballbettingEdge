# Final Review Fix Report

Run time: 2026-06-23 America/Phoenix

## Files changed

- `analytics/diagnostics/season_end_model_rebuild_dataset.py`
- `tests/test_season_end_model_rebuild_dataset.py`
- `analytics/diagnostics/next_season_candidate_model_lab.py`
- `tests/test_next_season_candidate_model_lab.py`
- `analytics/diagnostics/next_season_model_decision_packet.py`
- `tests/test_next_season_model_decision_packet.py`
- `analytics/output/season_end_model_rebuild_dataset_summary.md`
- `analytics/output/next_season_candidate_model_lab.md`
- `analytics/output/next_season_model_decision_packet.md`
- `.superpowers/sdd/final-fix-report.md`

## Commit

- Final-fix commit created after this report was written; see the committed Git history for the hash.

## Commands and results

- `python -m pytest tests\test_season_end_model_rebuild_dataset.py tests\test_next_season_candidate_model_lab.py tests\test_next_season_model_decision_packet.py -q`
  - Result: `15 passed in 0.29s`
- `python analytics\diagnostics\season_end_model_rebuild_dataset.py --input data\research\gate_c\pitcher_k_outcome_dataset.jsonl`
  - Result: wrote `analytics\output\season_end_model_rebuild_dataset.jsonl` with 2020 rows and wrote `analytics\output\season_end_model_rebuild_dataset_summary.md`
- `python analytics\diagnostics\next_season_candidate_model_lab.py`
  - Result: wrote `analytics\output\next_season_candidate_model_lab.md`
- `python analytics\diagnostics\next_season_model_decision_packet.py`
  - Result: wrote `analytics\output\next_season_model_decision_packet.md`
- `git diff --check`
  - Result: no whitespace errors; Windows line-ending warnings only

## Fix summary

- Runtime/hindsight separation now honors Gate C runtime-safe flags before exposing lineup handedness or actual-opportunity fields as runtime features.
- `theoretical_pnl` and `pick_history_pnl` are captured as hindsight labels, and candidate scoring uses `pick_history_pnl`, then `theoretical_pnl`, then legacy `pnl`.
- Candidate selectors receive only `runtime_features`, not the full row with `hindsight_labels`.
- Candidate lab output includes whole-sample, train, and test metrics.
- Decision packet gating uses test metrics when present and blocks canary-plan decisions if required source reports are unavailable.

## Concerns

- None.
