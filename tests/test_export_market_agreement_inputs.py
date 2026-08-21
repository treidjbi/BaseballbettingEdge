import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from scripts import export_market_agreement_inputs as exporter


@dataclass
class SelectCall:
    table: str
    params: dict[str, str]


class FakeWriter:
    def __init__(self, table_rows):
        self.table_rows = table_rows
        self.count_calls = []
        self.select_calls = []
        self.supabase_url = "https://secret-project.test"
        self.service_role_key = "secret-service-role"

    def count_rows(self, table, params):
        self.count_calls.append(SelectCall(table, dict(params)))
        return len(self.table_rows[table])

    def select_rows(self, table, params, **kwargs):
        self.select_calls.append(SelectCall(table, dict(params)))
        if table == "published_pipeline_artifacts":
            return self.table_rows[table]
        offset = int(params["offset"])
        limit = int(params["limit"])
        return self.table_rows[table][offset : offset + limit]


def _rows(prefix, count):
    return [
        {
            "id": f"{prefix}-{index:04d}",
            "slate_date": "2026-07-22",
            "normalized_pitcher": f"pitcher {index:04d}",
            "side": "over",
            "provider": "propline",
            "observed_at": f"2026-07-22T12:{index % 60:02d}:00Z",
        }
        for index in range(count)
    ]


def _artifact_loader(artifact_type):
    if artifact_type == "picks_history":
        return [
            {"date": "2026-04-27", "pitcher": "Before Window"},
            {"date": "2026-04-28", "pitcher": "Window Start"},
            {"date": "2026-07-23", "pitcher": "Window End"},
            {"date": "2026-07-24", "pitcher": "After Window"},
        ]
    if artifact_type == "today":
        return {"slate_date": "2026-07-23", "pitchers": []}
    raise AssertionError(f"unexpected artifact type: {artifact_type}")


def test_export_inputs_pages_only_compact_tables_with_exact_bounded_counts(tmp_path):
    writer = FakeWriter(
        {
            "market_pick_evidence": _rows("evidence", 1005),
            "live_market_display_state": _rows("display", 1001),
        }
    )

    result = exporter.export_inputs(
        writer=writer,
        artifact_loader=_artifact_loader,
        output_dir=tmp_path,
        start_date="2026-04-28",
        end_date="2026-07-23",
        page_size=1000,
    )

    assert result["tables"]["market_pick_evidence"]["rows"] == 1005
    assert result["tables"]["live_market_display_state"]["rows"] == 1001
    assert {call.table for call in writer.select_calls} == {
        "market_pick_evidence",
        "live_market_display_state",
    }
    assert not any(call.table == "market_snapshots" for call in writer.select_calls)
    first_page_calls = [call for call in writer.select_calls if call.params["offset"] == "0"]
    assert all(
        call.params["and"]
        == "(slate_date.gte.2026-04-28,slate_date.lte.2026-07-23)"
        for call in first_page_calls
    )
    assert all(
        call.params["order"]
        == "slate_date.asc,normalized_pitcher.asc,side.asc,provider.asc,observed_at.asc,id.asc"
        for call in writer.select_calls
    )
    assert [call.params["offset"] for call in writer.select_calls] == [
        "0",
        "1000",
        "0",
        "1000",
    ]

    history = json.loads((tmp_path / "picks_history.json").read_text(encoding="utf-8"))
    assert [row["pitcher"] for row in history] == ["Window Start", "Window End"]
    assert json.loads((tmp_path / "today.json").read_text(encoding="utf-8"))["slate_date"] == (
        "2026-07-23"
    )
    assert result["guardrails"] == [
        "read_only",
        "compact_tables_only",
        "no_market_snapshots",
        "no_live_behavior_change",
    ]


def test_export_inputs_fetch_failure_leaves_prior_files_unchanged(tmp_path):
    expected = {}
    for filename in exporter.OUTPUT_FILENAMES:
        path = tmp_path / filename
        path.write_bytes(f"prior-{filename}".encode("utf-8"))
        expected[filename] = path.read_bytes()

    class FailingWriter(FakeWriter):
        def select_rows(self, table, params):
            if table == "market_pick_evidence" and params["offset"] == "1000":
                raise RuntimeError("second page failed")
            return super().select_rows(table, params)

    writer = FailingWriter(
        {
            "market_pick_evidence": _rows("evidence", 1005),
            "live_market_display_state": _rows("display", 1),
        }
    )

    with pytest.raises(RuntimeError, match="second page failed"):
        exporter.export_inputs(
            writer=writer,
            artifact_loader=_artifact_loader,
            output_dir=tmp_path,
            start_date="2026-04-28",
            end_date="2026-07-23",
            page_size=1000,
        )

    assert {
        filename: (tmp_path / filename).read_bytes()
        for filename in exporter.OUTPUT_FILENAMES
    } == expected


def test_export_inputs_manifest_has_hashes_and_never_contains_credentials(tmp_path):
    writer = FakeWriter(
        {
            "market_pick_evidence": _rows("evidence", 1),
            "live_market_display_state": _rows("display", 1),
        }
    )

    result = exporter.export_inputs(
        writer=writer,
        artifact_loader=_artifact_loader,
        output_dir=tmp_path,
        start_date="2026-04-28",
        end_date="2026-07-23",
    )

    manifest_text = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert result["generated_at"]
    assert result["tables"]["market_pick_evidence"]["min_date"] == "2026-07-22"
    assert result["tables"]["market_pick_evidence"]["max_date"] == "2026-07-22"
    assert set(result["files"]) == {
        "market_pick_evidence.json",
        "live_market_display_state.json",
        "picks_history.json",
        "today.json",
    }
    assert all(file_info["sha256"] for file_info in result["files"].values())
    assert writer.supabase_url not in manifest_text
    assert writer.service_role_key not in manifest_text


def test_export_inputs_rejects_count_mismatch_and_malformed_payloads(tmp_path):
    duplicate_id_rows = _rows("evidence", 2)
    duplicate_id_rows[1]["id"] = duplicate_id_rows[0]["id"]
    writer = FakeWriter(
        {
            "market_pick_evidence": duplicate_id_rows,
            "live_market_display_state": _rows("display", 1),
        }
    )
    with pytest.raises(ValueError, match="exact count mismatch"):
        exporter.export_inputs(
            writer=writer,
            artifact_loader=_artifact_loader,
            output_dir=tmp_path,
            start_date="2026-04-28",
            end_date="2026-07-23",
        )

    malformed_writer = FakeWriter(
        {
            "market_pick_evidence": ["not-an-object"],
            "live_market_display_state": _rows("display", 1),
        }
    )
    with pytest.raises(ValueError, match="non-object"):
        exporter.export_inputs(
            writer=malformed_writer,
            artifact_loader=_artifact_loader,
            output_dir=tmp_path,
            start_date="2026-04-28",
            end_date="2026-07-23",
        )

    with pytest.raises(ValueError, match="picks_history"):
        exporter.export_inputs(
            writer=FakeWriter(
                {
                    "market_pick_evidence": _rows("evidence", 1),
                    "live_market_display_state": _rows("display", 1),
                }
            ),
            artifact_loader=lambda artifact_type: {}
            if artifact_type == "picks_history"
            else {"slate_date": "2026-07-23"},
            output_dir=tmp_path,
            start_date="2026-04-28",
            end_date="2026-07-23",
        )


def test_main_requires_credentials_before_creating_output(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(SystemExit, match="SUPABASE_URL"):
        exporter.main(["--output-dir", str(tmp_path)])

    assert list(tmp_path.iterdir()) == []


def test_load_artifact_reads_oversized_history_directly_from_supabase(monkeypatch):
    writer = FakeWriter(
        {
            "published_pipeline_artifacts": [
                {
                    "artifact_key": "picks_history",
                    "payload": [{"date": "2026-08-20", "pitcher": "Brady Singer"}],
                    "payload_sha256": "history-sha",
                }
            ]
        }
    )
    monkeypatch.setattr(
        exporter,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("picks_history must not use Netlify")
        ),
    )

    payload = exporter._load_artifact(
        "https://example.test/artifact",
        "picks_history",
        writer=writer,
    )

    assert payload == [{"date": "2026-08-20", "pitcher": "Brady Singer"}]
    assert writer.select_calls == [
        SelectCall(
            "published_pipeline_artifacts",
            {
                "artifact_key": "eq.picks_history",
                "select": "artifact_key,payload,payload_sha256",
                "limit": "1",
            },
        )
    ]


def test_load_artifact_rejects_missing_direct_history():
    writer = FakeWriter({"published_pipeline_artifacts": []})

    with pytest.raises(RuntimeError, match="missing or malformed"):
        exporter._load_artifact(
            "https://example.test/artifact",
            "picks_history",
            writer=writer,
        )


def test_exporter_supports_direct_script_execution():
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [sys.executable, "scripts/export_market_agreement_inputs.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--output-dir" in result.stdout
