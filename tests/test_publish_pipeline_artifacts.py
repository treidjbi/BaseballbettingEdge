from datetime import datetime

from scripts import publish_pipeline_artifacts_to_supabase as publisher
from scripts.publish_pipeline_artifacts_to_supabase import collect_artifact_rows, run


class FakeWriter:
    def __init__(self):
        self.upserts = []
        self.inserts = []

    def upsert_rows(self, table, rows, on_conflict):
        self.upserts.append((table, rows, on_conflict))
        return len(rows)

    def insert_rows(self, table, rows):
        self.inserts.append((table, rows))
        return len(rows)


def test_collect_artifact_rows_includes_today_and_dated_archive(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    (processed / "2026-05-22.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")

    rows = collect_artifact_rows(
        root=tmp_path,
        slate_date="2026-05-22",
        source="github_actions",
        source_run_id="run-1",
        source_commit_sha="sha",
    )

    assert [row["artifact_key"] for row in rows] == ["today", "dated_slate:2026-05-22"]


def test_collect_artifact_rows_grading_scope_excludes_current_slate_artifacts(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-23","pitchers":[]}', encoding="utf-8")
    (processed / "index.json").write_text('{"dates":["2026-05-22"]}', encoding="utf-8")
    (processed / "steam.json").write_text('{"date":"2026-05-23","steam":[]}', encoding="utf-8")
    (processed / "2026-05-22.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    (tmp_path / "dashboard" / "data").mkdir(exist_ok=True)
    (tmp_path / "dashboard" / "data" / "performance.json").write_text('{"updated_at":"2026-05-23T10:00:00Z"}', encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "params.json").write_text('{"updated_at":"2026-05-23T10:00:00Z"}', encoding="utf-8")
    (tmp_path / "data" / "picks_history.json").write_text("[]", encoding="utf-8")
    (tmp_path / "data" / "preview_lines.json").write_text('{"date":"2026-05-23"}', encoding="utf-8")

    rows = collect_artifact_rows(
        root=tmp_path,
        slate_date="2026-05-22",
        source="github_actions",
        source_run_id="run-1",
        source_commit_sha="sha",
        scope="grading",
    )

    assert [row["artifact_key"] for row in rows] == [
        "performance",
        "params",
        "picks_history",
        "dated_slate:2026-05-22",
    ]


def test_run_dry_run_does_not_write(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    writer = FakeWriter()

    result = run(
        root=tmp_path,
        writer=writer,
        slate_date="2026-05-22",
        source="github_actions",
        source_run_id="run-1",
        source_commit_sha="sha",
        execute=False,
    )

    assert result["artifact_count"] == 1
    assert writer.upserts == []


def test_main_dry_run_does_not_require_supabase_env(tmp_path, monkeypatch, capsys):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    monkeypatch.setattr(publisher, "ROOT", tmp_path)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    assert publisher.main(["--date", "2026-05-22"]) == 0

    assert "artifact_publish mode=dry_run date=2026-05-22 artifacts=1" in capsys.readouterr().out


def test_run_execute_upserts_artifacts_and_run_row(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    writer = FakeWriter()

    result = run(
        root=tmp_path,
        writer=writer,
        slate_date="2026-05-22",
        source="github_actions",
        source_run_id="run-1",
        source_commit_sha="sha",
        execute=True,
    )

    assert result["artifact_count"] == 1
    assert writer.upserts[0][0] == "published_pipeline_artifacts"
    assert writer.upserts[0][2] == "artifact_key"
    assert writer.inserts[0][0] == "pipeline_artifact_publication_runs"


def test_run_execute_sets_started_before_completed(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    writer = FakeWriter()

    run(
        root=tmp_path,
        writer=writer,
        slate_date="2026-05-22",
        source="github_actions",
        source_run_id="run-1",
        source_commit_sha="sha",
        execute=True,
    )

    run_row = writer.inserts[0][1][0]
    assert "started_at" in run_row
    assert datetime.fromisoformat(run_row["started_at"]) <= datetime.fromisoformat(run_row["completed_at"])


def test_run_execute_stamps_artifact_published_at_for_upserts(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    writer = FakeWriter()

    run(
        root=tmp_path,
        writer=writer,
        slate_date="2026-05-22",
        source="github_actions",
        source_run_id="run-1",
        source_commit_sha="sha",
        execute=True,
    )

    upsert_rows = writer.upserts[0][1]
    assert upsert_rows[0]["published_at"]
