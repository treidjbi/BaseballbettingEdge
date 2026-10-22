from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "lock-ledger-monitor.yml"


def test_lock_ledger_monitor_workflow_is_manual_read_only():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text
    assert "git commit" not in text


def test_lock_ledger_monitor_workflow_uses_supabase_secrets_only():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "python scripts/monitor_lock_ledger.py" in text
    assert "SUPABASE_URL: ${{ secrets.SUPABASE_URL }}" in text
    assert "SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}" in text
    assert "RUNDOWN_API_KEY" not in text
    assert "PROPLINE_API_KEY" not in text
    assert "BOLTODDS_API_KEY" not in text
    assert "pipeline/run_pipeline.py" not in text
