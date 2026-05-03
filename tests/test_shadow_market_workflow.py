from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "shadow-market-infra.yml"


def test_shadow_market_workflow_is_scheduled_manual_and_observation_only():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "schedule:" in text
    assert "22 15,17,19,21,23,1 * * *" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text
    assert "git commit" not in text


def test_shadow_market_workflow_runs_only_sidecar_scripts_with_required_secrets():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "scripts/shadow_propline_to_supabase.py" in text
    assert "scripts/shadow_artifacts_to_supabase.py" in text
    assert "SUPABASE_URL: ${{ secrets.SUPABASE_URL }}" in text
    assert "SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}" in text
    assert "PROPLINE_API_KEY: ${{ secrets.PROPLINE_API_KEY }}" in text
    assert "pipeline/run_pipeline.py" not in text


def test_shadow_market_workflow_defaults_capture_flags_for_scheduled_runs():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "Resolve capture flags" in text
    assert 'if [ "${{ github.event_name }}" = "schedule" ]; then' in text
    assert 'CAPTURE_PROPLINE="true"' in text
    assert 'CAPTURE_ARTIFACTS="true"' in text
    assert "steps.capture.outputs.capture_propline == 'true'" in text
    assert "steps.capture.outputs.capture_artifacts == 'true'" in text
