from datetime import datetime

from scripts import publish_pipeline_artifacts_to_supabase as publisher
from scripts.publish_pipeline_artifacts_to_supabase import collect_artifact_rows, run


class FakeWriter:
    def __init__(self, selected_rows=None):
        self.selected_rows = list(selected_rows or [])
        self.selects = []
        self.upserts = []
        self.inserts = []

    def select_rows(self, table, params):
        self.selects.append((table, params))
        return list(self.selected_rows)

    def upsert_rows(self, table, rows, on_conflict, **options):
        self.upserts.append((table, rows, on_conflict, options))
        return len(rows)

    def insert_rows(self, table, rows):
        self.inserts.append((table, rows))
        return len(rows)


def _write_lock_artifacts(root, *, slate_date="2026-05-24"):
    processed = root / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    payload = f'{{"date":"{slate_date}","pitchers":[]}}'
    (processed / "today.json").write_text(payload, encoding="utf-8")
    (processed / f"{slate_date}.json").write_text(payload, encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "picks_history.json").write_text("[]", encoding="utf-8")


def _lock_artifact_rows(root, *, slate_date="2026-05-24"):
    return collect_artifact_rows(
        root=root,
        slate_date=slate_date,
        source="render_pipeline",
        source_run_id="run-1",
        source_commit_sha="sha",
        scope="lock",
    )


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


def test_collect_artifact_rows_can_prefix_shadow_artifact_keys(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    (processed / "2026-05-22.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")

    rows = collect_artifact_rows(
        root=tmp_path,
        slate_date="2026-05-22",
        source="render_pipeline",
        source_run_id="run-1",
        source_commit_sha="sha",
        artifact_key_prefix="render_shadow:2026-05-22:",
    )

    assert [row["artifact_key"] for row in rows] == [
        "render_shadow:2026-05-22:today",
        "render_shadow:2026-05-22:dated_slate:2026-05-22",
    ]
    assert rows[0]["metadata"]["base_artifact_key"] == "today"


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
        "index",
        "dated_slate:2026-05-22",
    ]


def test_collect_artifact_rows_preview_scope_excludes_stale_non_preview_artifacts(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-23","pitchers":[]}', encoding="utf-8")
    (processed / "index.json").write_text('{"dates":[{"date":"2026-05-24"}]}', encoding="utf-8")
    (processed / "steam.json").write_text('{"date":"2026-05-23","steam":[]}', encoding="utf-8")
    (processed / "2026-05-24.json").write_text('{"date":"2026-05-24","pitchers":[]}', encoding="utf-8")
    (tmp_path / "dashboard" / "data").mkdir(exist_ok=True)
    (tmp_path / "dashboard" / "data" / "performance.json").write_text('{"updated_at":"stale"}', encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "params.json").write_text('{"updated_at":"stale"}', encoding="utf-8")
    (tmp_path / "data" / "picks_history.json").write_text("[]", encoding="utf-8")
    (tmp_path / "data" / "preview_lines.json").write_text('{"date":"2026-05-24"}', encoding="utf-8")

    rows = collect_artifact_rows(
        root=tmp_path,
        slate_date="2026-05-24",
        source="render_pipeline",
        source_run_id="run-1",
        source_commit_sha="sha",
        scope="preview",
    )

    assert [row["artifact_key"] for row in rows] == [
        "index",
        "preview_lines",
        "dated_slate:2026-05-24",
    ]


def test_collect_artifact_rows_pipeline_scope_excludes_stale_non_pipeline_artifacts(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-24","pitchers":[]}', encoding="utf-8")
    (processed / "index.json").write_text('{"dates":[{"date":"2026-05-24"}]}', encoding="utf-8")
    (processed / "steam.json").write_text('{"date":"2026-05-24","steam":[]}', encoding="utf-8")
    (processed / "2026-05-24.json").write_text('{"date":"2026-05-24","pitchers":[]}', encoding="utf-8")
    (tmp_path / "dashboard" / "data").mkdir(exist_ok=True)
    (tmp_path / "dashboard" / "data" / "performance.json").write_text('{"updated_at":"stale"}', encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "params.json").write_text('{"updated_at":"stale"}', encoding="utf-8")
    (tmp_path / "data" / "preview_lines.json").write_text('{"date":"stale"}', encoding="utf-8")
    (tmp_path / "data" / "picks_history.json").write_text("[]", encoding="utf-8")

    rows = collect_artifact_rows(
        root=tmp_path,
        slate_date="2026-05-24",
        source="render_pipeline",
        source_run_id="run-1",
        source_commit_sha="sha",
        scope="pipeline",
    )

    assert [row["artifact_key"] for row in rows] == [
        "today",
        "index",
        "steam",
        "picks_history",
        "dated_slate:2026-05-24",
    ]


def test_collect_artifact_rows_lock_scope_excludes_stale_non_lock_artifacts(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-24","pitchers":[]}', encoding="utf-8")
    (processed / "index.json").write_text('{"dates":[{"date":"2026-05-24"}]}', encoding="utf-8")
    (processed / "steam.json").write_text('{"date":"2026-05-24","steam":[]}', encoding="utf-8")
    (processed / "2026-05-24.json").write_text('{"date":"2026-05-24","pitchers":[]}', encoding="utf-8")
    (tmp_path / "dashboard" / "data").mkdir(exist_ok=True)
    (tmp_path / "dashboard" / "data" / "performance.json").write_text('{"updated_at":"stale"}', encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "params.json").write_text('{"updated_at":"stale"}', encoding="utf-8")
    (tmp_path / "data" / "preview_lines.json").write_text('{"date":"stale"}', encoding="utf-8")
    (tmp_path / "data" / "picks_history.json").write_text("[]", encoding="utf-8")

    rows = collect_artifact_rows(
        root=tmp_path,
        slate_date="2026-05-24",
        source="render_pipeline",
        source_run_id="run-1",
        source_commit_sha="sha",
        scope="lock",
    )

    assert [row["artifact_key"] for row in rows] == [
        "today",
        "picks_history",
        "dated_slate:2026-05-24",
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


def test_run_execute_bounds_artifact_timeout_resilience_to_the_publisher(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    writer = FakeWriter()

    run(
        root=tmp_path,
        writer=writer,
        slate_date="2026-05-22",
        source="render_pipeline",
        source_run_id="run-1",
        source_commit_sha="sha",
        execute=True,
    )

    assert writer.upserts[0][3] == {
        "return_representation": False,
        "attempts": 2,
        "retry_database_codes": {"57014"},
    }


def test_run_execute_lock_scope_skips_unchanged_artifact_upsert(tmp_path):
    _write_lock_artifacts(tmp_path)
    candidate_rows = _lock_artifact_rows(tmp_path)
    writer = FakeWriter(
        selected_rows=[
            {
                "artifact_key": row["artifact_key"],
                "payload_sha256": row["payload_sha256"],
            }
            for row in candidate_rows
        ]
    )

    result = run(
        root=tmp_path,
        writer=writer,
        slate_date="2026-05-24",
        source="render_pipeline",
        source_run_id="run-1",
        source_commit_sha="sha",
        execute=True,
        scope="lock",
    )

    assert result == {
        "artifact_count": 0,
        "candidate_artifact_count": 3,
        "unchanged_artifact_count": 3,
        "execute": True,
    }
    assert writer.selects == [
        (
            "published_pipeline_artifacts",
            {
                "artifact_key": "in.(today,picks_history,dated_slate:2026-05-24)",
                "select": "artifact_key,payload_sha256",
                "limit": "3",
            },
        )
    ]
    assert writer.upserts == []
    run_row = writer.inserts[0][1][0]
    assert run_row["artifact_count"] == 0
    assert run_row["metadata"]["candidate_artifact_count"] == 3
    assert run_row["metadata"]["unchanged_artifact_count"] == 3


def test_run_execute_lock_scope_upserts_only_changed_artifacts(tmp_path):
    _write_lock_artifacts(tmp_path)
    candidate_rows = _lock_artifact_rows(tmp_path)
    writer = FakeWriter(
        selected_rows=[
            {
                "artifact_key": row["artifact_key"],
                "payload_sha256": (
                    "stale-hash"
                    if row["artifact_key"] == "picks_history"
                    else row["payload_sha256"]
                ),
            }
            for row in candidate_rows
        ]
    )

    result = run(
        root=tmp_path,
        writer=writer,
        slate_date="2026-05-24",
        source="render_pipeline",
        source_run_id="run-1",
        source_commit_sha="sha",
        execute=True,
        scope="lock",
    )

    assert result == {
        "artifact_count": 1,
        "candidate_artifact_count": 3,
        "unchanged_artifact_count": 2,
        "execute": True,
    }
    assert [row["artifact_key"] for row in writer.upserts[0][1]] == ["picks_history"]
    run_row = writer.inserts[0][1][0]
    assert run_row["artifact_count"] == 1
    assert run_row["metadata"]["candidate_artifact_count"] == 3
    assert run_row["metadata"]["unchanged_artifact_count"] == 2


def test_run_execute_pipeline_scope_publishes_all_without_hash_lookup(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-24"}', encoding="utf-8")
    (processed / "index.json").write_text('{"dates":[]}', encoding="utf-8")
    (processed / "steam.json").write_text('{"steam":[]}', encoding="utf-8")
    (processed / "2026-05-24.json").write_text('{"date":"2026-05-24"}', encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "picks_history.json").write_text("[]", encoding="utf-8")
    writer = FakeWriter(
        selected_rows=[{"artifact_key": "today", "payload_sha256": "same"}]
    )

    result = run(
        root=tmp_path,
        writer=writer,
        slate_date="2026-05-24",
        source="render_pipeline",
        source_run_id="run-1",
        source_commit_sha="sha",
        execute=True,
        scope="pipeline",
    )

    assert writer.selects == []
    assert [row["artifact_key"] for row in writer.upserts[0][1]] == [
        "today",
        "index",
        "steam",
        "picks_history",
        "dated_slate:2026-05-24",
    ]
    assert result == {
        "artifact_count": 5,
        "candidate_artifact_count": 5,
        "unchanged_artifact_count": 0,
        "execute": True,
    }


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
