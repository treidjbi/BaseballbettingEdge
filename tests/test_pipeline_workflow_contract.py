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


def test_pipeline_run_step_handles_preview_cron_explicitly():
    workflow_text = _read_workflow()
    run_block = _extract_step_block(workflow_text, "Run pipeline")
    assert 'if [ "$SCHEDULE" = "17 7 * * *" ]; then' in run_block
    assert "python pipeline/run_pipeline.py $TODAY --run-type preview" in run_block


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
