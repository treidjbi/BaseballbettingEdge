from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "live-layer-proof.yml"


def test_live_layer_proof_workflow_is_manual_only():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text
    assert "git commit" not in text


def test_live_layer_proof_workflow_runs_worker_with_existing_secrets():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "python scripts/build_live_events_to_supabase.py" in text
    assert "SUPABASE_URL: ${{ secrets.SUPABASE_URL }}" in text
    assert "SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}" in text
    assert "PROPLINE_API_KEY" not in text
    assert "RUNDOWN_API_KEY" not in text
    assert "scripts/shadow_propline_to_supabase.py" not in text
    assert "pipeline/run_pipeline.py" not in text
