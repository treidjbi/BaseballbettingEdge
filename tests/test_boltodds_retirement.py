from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RETIRED_WORKER_PATH = "scripts/boltodds_ws_worker.py"
RETIRED_SERVICE_NAME = "bbe-boltodds-shadow-worker"


def _substantive_lines(text):
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_render_blueprint_cannot_recreate_retired_boltodds_worker():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert _substantive_lines(text) == ["services: []"]
    assert RETIRED_WORKER_PATH not in text
    assert RETIRED_SERVICE_NAME not in text


def test_github_workflows_do_not_launch_retired_boltodds_worker():
    workflow_dir = ROOT / ".github" / "workflows"
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for pattern in ("*.yml", "*.yaml")
        for path in sorted(workflow_dir.glob(pattern))
    )
    assert RETIRED_WORKER_PATH not in text
    assert RETIRED_SERVICE_NAME not in text


def test_render_cron_deployer_does_not_launch_retired_boltodds_worker():
    text = (ROOT / "scripts" / "deploy_render_pipeline_crons.py").read_text(
        encoding="utf-8"
    )
    assert RETIRED_WORKER_PATH not in text
    assert RETIRED_SERVICE_NAME not in text
