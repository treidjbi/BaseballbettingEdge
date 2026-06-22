Status: DONE

Task: Task 2 - Wire Shadow Metadata Into Pitcher Records

Files changed:
- pipeline/build_features.py
- tests/test_build_features.py
- .superpowers/sdd/task-2-report.md

Implementation summary:
- Added the Task 1 projection challenger import to build_features.
- Preserved the existing post-bias, line-gap-capped model lambda as `model_lambda`.
- Kept default/off mode behavior on the existing selected lambda path.
- In `shadow`, build_features now adds top-level and side-level `projection_challenger` metadata while preserving `lambda`, EV, and verdict behavior.
- In `enforce`, build_features selects the challenger lambda before over/under probabilities, EV, adjusted EV, and verdicts are calculated.
- Added focused tests for `shadow` metadata preservation and `enforce` selected-lambda replacement.

TDD evidence:
- Red test command:
  `python -m pytest tests/test_build_features.py::test_market_shrink_shadow_preserves_lambda_and_adds_metadata tests/test_build_features.py::test_market_shrink_enforce_replaces_selected_lambda -q`
- Red result:
  Expected failure observed: both tests failed with missing `model_lambda` / `projection_challenger` keys.
- Green focused test command:
  `python -m pytest tests/test_build_features.py::test_market_shrink_shadow_preserves_lambda_and_adds_metadata tests/test_build_features.py::test_market_shrink_enforce_replaces_selected_lambda -q`
- Green focused result:
  `2 passed in 1.75s`
- Full touched-file test command:
  `python -m pytest tests/test_build_features.py -q`
- Full touched-file result:
  `133 passed in 2.00s`
- Final combined verification command:
  `python -m pytest tests/test_projection_challenger.py tests/test_build_features.py -q`
- Final combined verification result:
  `141 passed in 2.18s`
- Whitespace check:
  `git diff --check` exited 0; it reported only existing Windows LF-to-CRLF conversion warnings.

Constraints honored:
- No production environment variables were changed.
- No formula_change_date, thresholds, staking, provider order, notifications, locks, retention, or dashboard source-of-truth behavior was changed.
- Runtime challenger inputs are only the current model lambda after the existing line-gap cap and the posted K line.
- Task scope stayed limited to build_features, its tests, and this requested Task 2 report.

Concerns:
- None from implementation or tests.
