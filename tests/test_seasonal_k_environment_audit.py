import json
import subprocess
import sys
from pathlib import Path

from analytics.diagnostics import seasonal_k_environment_audit as audit


def test_month_bucket_uses_year_month():
    assert audit.month_bucket("2026-05-04") == "2026-05"


def test_summarize_by_month_uses_only_graded_rows_with_actual_ks():
    rows = [
        {"date": "2026-04-30", "result": "win", "actual_ks": 4},
        {"date": "2026-04-29", "result": "loss", "actual_ks": 6},
        {"date": "2026-05-01", "result": "void", "actual_ks": 12},
        {"date": "2026-05-02", "result": "pending", "actual_ks": 5},
        {"date": "2026-05-03", "result": "win", "actual_ks": None},
    ]

    summary = audit.summarize_by_month(rows)

    assert summary == {
        "2026-04": {
            "n": 2,
            "avg_actual_ks": 5.0,
        }
    }


def test_render_includes_selection_bias_warning_and_no_live_prior_language():
    rendered = audit.render({"2026-04": {"n": 2, "avg_actual_ks": 5.0}})

    assert "app picks are selection-biased" in rendered
    assert "MLB-wide starter K/start" in rendered
    assert "before any live prior" in rendered
    assert "Do not apply month constants directly to live lambda" in rendered
    assert "`2026-04`: n=2, avg_actual_ks=5.0" in rendered


def test_cli_reads_picks_history_json(tmp_path):
    root = Path(__file__).resolve().parents[1]
    history_path = tmp_path / "picks_history.json"
    history_path.write_text(
        json.dumps(
            [
                {"date": "2026-04-30", "result": "win", "actual_ks": 7},
                {"date": "2026-05-01", "result": "loss", "actual_ks": 3},
            ]
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "analytics/diagnostics/seasonal_k_environment_audit.py",
            "--history",
            str(history_path),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "`2026-04`: n=1, avg_actual_ks=7.0" in completed.stdout
    assert "`2026-05`: n=1, avg_actual_ks=3.0" in completed.stdout
