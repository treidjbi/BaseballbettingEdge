import subprocess

import pytest

from scripts import backfill_compact_market_movements_via_cli as backfill


def test_parse_args_defaults_to_dry_run():
    args = backfill.parse_args(["--start-date", "2026-05-01", "--end-date", "2026-05-10"])

    assert args.start_date == "2026-05-01"
    assert args.end_date == "2026-05-10"
    assert args.execute is False


def test_validate_date_range_rejects_reversed_dates():
    with pytest.raises(ValueError, match="start date must be on or before end date"):
        backfill.validate_date_range("2026-05-10", "2026-05-01")


def test_dry_run_sql_is_read_only_and_reports_candidate_counts():
    sql = backfill.build_backfill_sql(
        start_date="2026-05-01",
        end_date="2026-05-10",
        execute=False,
    ).lower()

    assert "mode" in sql
    assert "dry_run" in sql
    assert "candidate_compact_rows" in sql
    assert "source_raw_rows" in sql
    assert "insert into" not in sql
    assert "on conflict" not in sql
    assert " delete " not in f" {sql} "


def test_execute_sql_upserts_only_compact_rows_and_never_deletes():
    sql = backfill.build_backfill_sql(
        start_date="2026-05-01",
        end_date="2026-05-10",
        execute=True,
    ).lower()

    assert "insert into public.compact_market_line_movements" in sql
    assert "on conflict" in sql
    assert "do update" in sql
    assert "public.market_snapshots" in sql
    assert " delete " not in f" {sql} "
    assert " truncate " not in f" {sql} "
    assert " drop " not in f" {sql} "


def test_run_query_uses_linked_supabase_cli_without_shell(monkeypatch):
    calls = []
    written_sql = []
    unlinked = []
    file_state = {"closed": False}

    monkeypatch.setattr(backfill.shutil, "which", lambda name: "C:\\node\\npx.cmd" if name == "npx" else None)

    class FakeSqlFile:
        name = "C:\\tmp\\backfill.sql"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            file_state["closed"] = True
            return False

        def write(self, value):
            written_sql.append(value)

        def flush(self):
            return None

    monkeypatch.setattr(backfill.tempfile, "NamedTemporaryFile", lambda *args, **kwargs: FakeSqlFile())
    monkeypatch.setattr(backfill.os, "unlink", lambda path: unlinked.append(path))

    def fake_run(args, **kwargs):
        assert file_state["closed"] is True
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr(backfill.subprocess, "run", fake_run)

    result = backfill.run_query("select 1;", timeout_seconds=12)

    assert result.returncode == 0
    assert calls[0][0] == [
        "C:\\node\\npx.cmd",
        "supabase",
        "db",
        "query",
        "--linked",
        "--file",
        "C:\\tmp\\backfill.sql",
        "-o",
        "json",
    ]
    assert written_sql == ["select 1;"]
    assert unlinked == ["C:\\tmp\\backfill.sql"]
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["timeout"] == 12
