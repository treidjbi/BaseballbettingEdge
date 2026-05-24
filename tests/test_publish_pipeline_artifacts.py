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
