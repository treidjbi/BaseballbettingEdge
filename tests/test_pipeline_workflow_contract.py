import importlib.util
import re
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "pipeline.yml"
DIAGNOSTIC_PATH = ROOT / "analytics" / "diagnostics" / "d_preview_health.py"


def _read_workflow() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _extract_step_block(workflow_text: str, step_name: str) -> str:
    pattern = (
        rf"- name: {re.escape(step_name)}\r?\n"
        rf"(?P<body>(?:\s{{6,}}.*(?:\r?\n|$))+)"
    )
    match = re.search(pattern, workflow_text)
    assert match, f"Step {step_name!r} not found in workflow"
    return match.group("body")


def _load_preview_health_module():
    spec = importlib.util.spec_from_file_location("d_preview_health", DIAGNOSTIC_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_notification_preview_branch_matches_actual_preview_cron():
    workflow_text = _read_workflow()
    notify_block = _extract_step_block(workflow_text, "Send push notifications")
    assert '[ "$SCHEDULE" = "17 7 * * *" ]' in notify_block
    assert '[ "$SCHEDULE" = "0 2 * * *" ]' not in notify_block


def test_legacy_github_notifications_can_be_disabled_by_variable():
    workflow_text = _read_workflow()
    notify_block = _extract_step_block(workflow_text, "Send push notifications")

    assert "ENABLE_GITHUB_LEGACY_NOTIFICATIONS" in notify_block
    assert "GitHub legacy notifications disabled" in notify_block
    assert 'exit 0' in notify_block


def test_pipeline_run_step_handles_preview_cron_explicitly():
    workflow_text = _read_workflow()
    run_block = _extract_step_block(workflow_text, "Run pipeline")
    assert 'if [ "$SCHEDULE" = "17 7 * * *" ]; then' in run_block
    assert "python pipeline/run_pipeline.py $TODAY --run-type preview" in run_block


def test_pipeline_workflow_exposes_manual_lock_mode():
    workflow_text = _read_workflow()
    run_block = _extract_step_block(workflow_text, "Run pipeline")

    assert "- lock" in workflow_text
    assert 'if [ "$MODE" = "lock" ]; then' in run_block
    assert "python pipeline/run_pipeline.py $TODAY --run-type lock" in run_block
    assert "exit 0" in run_block


def test_pipeline_workflow_exposes_manual_preview_and_grading_modes():
    workflow_text = _read_workflow()
    run_block = _extract_step_block(workflow_text, "Run pipeline")

    assert "- preview" in workflow_text
    assert "- grading" in workflow_text
    assert 'if [ "$MODE" = "preview" ]; then' in run_block
    assert "python pipeline/run_pipeline.py $TODAY --run-type preview" in run_block
    assert 'if [ "$MODE" = "grading" ]; then' in run_block
    assert "python pipeline/run_pipeline.py $TODAY --run-type grading" in run_block


def test_pipeline_workflow_passes_supabase_lock_flags_to_runner():
    workflow_text = _read_workflow()
    run_block = _extract_step_block(workflow_text, "Run pipeline")

    assert "ENABLE_SUPABASE_LOCK_CONSUMER: ${{ vars.ENABLE_SUPABASE_LOCK_CONSUMER }}" in run_block
    assert "SUPABASE_LOCK_CONSUMER_STRICT: ${{ vars.SUPABASE_LOCK_CONSUMER_STRICT }}" in run_block
    assert "ENABLE_GITHUB_FALLBACK_LOCKING: ${{ vars.ENABLE_GITHUB_FALLBACK_LOCKING }}" in run_block


def test_pipeline_workflow_can_shadow_publish_artifacts_to_supabase():
    workflow_text = _read_workflow()
    publish_block = _extract_step_block(workflow_text, "Publish artifacts to Supabase")

    assert "ENABLE_SUPABASE_ARTIFACT_PUBLISH" in publish_block
    assert "publish_pipeline_artifacts_to_supabase.py" in publish_block
    assert "--source github_actions" in publish_block
    assert "--execute" in publish_block
    assert "TODAY=$(TZ=America/Phoenix date +%Y-%m-%d)" in publish_block
    assert 'INPUT_DATE="${{ github.event.inputs.date }}"' in publish_block
    assert 'if [ "$MODE" = "lock" ]; then' in publish_block
    assert 'RUN_TYPE="preview"' in publish_block
    assert 'RUN_TYPE="grading"' in publish_block
    assert 'PIPELINE_RUN_TYPE="$RUN_TYPE"' in publish_block
    assert "ARTIFACT_COMMIT_SHA=$(git rev-parse HEAD)" in publish_block
    assert '--source-commit-sha "$ARTIFACT_COMMIT_SHA"' in publish_block
    assert '--scope "$ARTIFACT_SCOPE"' in publish_block


def test_grading_commit_stages_only_grading_safe_artifacts():
    workflow_text = _read_workflow()
    commit_block = _extract_step_block(workflow_text, "Commit pipeline output")

    assert 'if [ "$SCHEDULE" = "17 10 * * *" ]; then' in commit_block
    assert 'RUN_TYPE="grading"' in commit_block
    assert 'if [ "$RUN_TYPE" = "grading" ]; then' in commit_block
    assert "dashboard/data/processed/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json" in commit_block
    grading_branch = commit_block.split('if [ "$RUN_TYPE" = "grading" ]; then', 1)[1].split("else", 1)[0]
    grading_lines = [line.strip() for line in grading_branch.splitlines()]
    assert "git add dashboard/data/processed/" not in grading_lines
    assert "dashboard/data/processed/today.json" not in grading_branch


def test_grading_artifact_publish_uses_previous_slate_and_grading_scope():
    workflow_text = _read_workflow()
    publish_block = _extract_step_block(workflow_text, "Publish artifacts to Supabase")

    assert 'PUBLISH_DATE="$TODAY"' in publish_block
    assert 'ARTIFACT_SCOPE="all"' in publish_block
    assert 'if [ "$RUN_TYPE" = "grading" ]; then' in publish_block
    assert 'PUBLISH_DATE=$(TZ=America/Phoenix date -d "$TODAY -1 day" +%Y-%m-%d)' in publish_block
    assert 'ARTIFACT_SCOPE="grading"' in publish_block
    assert '--date "$PUBLISH_DATE"' in publish_block


def test_classify_preview_health_marks_auth_failures_distinctly():
    module = _load_preview_health_module()
    result = module.classify_preview_health(
        target_date="2026-04-28",
        preview_due=True,
        preview_date="2026-04-24",
        preview_line_count=24,
        probe_status="auth_failure",
    )
    assert result["status"] == "auth_failure"
    assert "401" in result["reason"]


def test_classify_preview_health_distinguishes_legit_no_lines_yet():
    module = _load_preview_health_module()
    result = module.classify_preview_health(
        target_date="2026-04-28",
        preview_due=True,
        preview_date=None,
        preview_line_count=0,
        probe_status="ok",
        probe_line_count=0,
    )
    assert result["status"] == "no_preview_lines_yet"


def test_expected_preview_date_uses_phoenix_game_day():
    module = _load_preview_health_module()
    assert module.expected_preview_date(date(2026, 4, 28)) == "2026-04-28"
