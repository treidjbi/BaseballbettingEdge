import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pipeline.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text()


def test_pipeline_crons_are_offset_from_top_of_hour():
    text = _workflow_text()
    crons = re.findall(r"cron: '([^']+)'", text)

    assert "17 7 * * *" in crons
    assert "17 10 * * *" in crons
    assert "17 13 * * *" in crons
    assert "7 15 * * *" in crons
    assert "37 15 * * *" in crons
    assert "7 1 * * *" in crons
    assert len(crons) == 24
    assert all(not cron.startswith(("0 ", "30 ")) for cron in crons)


def test_pipeline_run_type_mapping_uses_offset_crons():
    text = _workflow_text()

    assert '$SCHEDULE" = "17 7 * * *"' in text
    assert '$SCHEDULE" = "17 10 * * *"' in text
    assert '$SCHEDULE" = "7 15 * * *"' in text
    assert '$SCHEDULE" = "37 0 * * *"' in text
    assert '$SCHEDULE" = "7 1 * * *"' in text
    assert '$SCHEDULE" = "0 7 * * *"' not in text
    assert '$SCHEDULE" = "0 10 * * *"' not in text
