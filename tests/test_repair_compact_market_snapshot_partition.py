import importlib
import json

import pytest


def _module():
    return importlib.import_module("scripts.repair_compact_market_snapshot_partition")


def _snapshot(snapshot_id, observed_at, odds, *, provider="boltodds", slate_date="2026-06-16"):
    return {
        "id": snapshot_id,
        "run_id": "run-1",
        "slate_date": slate_date,
        "provider": provider,
        "bookmaker_key": "fanduel",
        "player_name": "Example Pitcher",
        "normalized_player_name": "example pitcher",
        "market_key": "pitcher_strikeouts",
        "side": "over",
        "line": 5.5,
        "american_odds": odds,
        "observed_at": observed_at,
    }


def _compact(*, first_seen="2026-06-16T18:05:00Z", first_odds=-125,
             min_odds=-125, max_odds=-125, move_count=0, snapshot_count=1,
             source_ids=None, player="example pitcher"):
    return {
        "slate_date": "2026-06-16",
        "provider": "boltodds",
        "book_key": "fanduel",
        "normalized_player_name": player,
        "player_name": "Example Pitcher",
        "market_key": "pitcher_strikeouts",
        "side": "over",
        "line": 5.5,
        "first_seen_at": first_seen,
        "last_seen_at": "2026-06-16T18:05:00Z",
        "first_odds": first_odds,
        "last_odds": -125,
        "min_odds": min_odds,
        "max_odds": max_odds,
        "odds_move_count": move_count,
        "snapshot_count": snapshot_count,
        "source_snapshot_ids": list(source_ids or ["snap-2"]),
    }


class FakeWriter:
    def __init__(self, *, snapshots=None, existing=None):
        self.snapshots = list(snapshots or [
            _snapshot("snap-1", "2026-06-16T18:00:00Z", -110),
            _snapshot("snap-2", "2026-06-16T18:05:00Z", -125),
        ])
        self.existing = list(existing or [_compact()])
        self.selects = []
        self.upserts = []

    def select_rows(self, table, params, **kwargs):
        self.selects.append((table, dict(params), dict(kwargs)))
        if table == "market_provider_runs" and "slate_date" in params:
            return [{
                "id": "run-1",
                "provider": "boltodds",
                "slate_date": "2026-06-16",
                "created_at": "2026-06-16T18:00:00Z",
            }]
        if table == "market_feed_heartbeats":
            return []
        if table == "market_snapshots":
            return list(self.snapshots) if params["offset"] == "0" else []
        if table == "compact_market_line_movements":
            return list(self.existing) if params["offset"] == "0" else []
        return []

    def upsert_rows(self, table, rows, on_conflict, **kwargs):
        copied = [dict(row) for row in rows]
        self.upserts.append((table, copied, on_conflict, dict(kwargs)))
        replacement_by_key = {
            (
                row["slate_date"], row["provider"], row["book_key"],
                row["normalized_player_name"], row["market_key"],
                row["side"], float(row["line"]),
            ): row
            for row in copied
        }
        retained = []
        for row in self.existing:
            key = (
                row["slate_date"], row["provider"], row["book_key"],
                row["normalized_player_name"], row["market_key"],
                row["side"], float(row["line"]),
            )
            if key not in replacement_by_key:
                retained.append(row)
        self.existing = retained + copied
        return copied


def test_preview_is_one_provider_one_date_and_reports_only_aggregate_differences():
    repair = _module()
    writer = FakeWriter()

    report = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=writer,
        execute=False,
    )

    assert report["action"] == "preview"
    assert report["provider"] == "boltodds"
    assert report["slate_date"] == "2026-06-16"
    assert report["provider_run_count"] == 1
    assert report["raw_snapshot_count"] == 2
    assert report["rebuilt_compact_count"] == 1
    assert report["existing_compact_count"] == 1
    assert report["missing_compact_count"] == 0
    assert report["mismatched_compact_count"] == 1
    assert report["unexpected_compact_count"] == 0
    assert report["rows_to_upsert_count"] == 1
    assert report["mismatch_field_counts"]["first_seen_at"] == 1
    assert report["mismatch_field_counts"]["snapshot_count"] == 1
    assert report["mismatch_field_counts"]["last_seen_at"] == 0
    assert report["execution_eligible"] is True
    assert report["deletion_approved"] is False
    assert report["retention_execution_closed"] is True
    assert report["database_write_performed"] is False
    assert len(report["preview_sha256"]) == 64
    assert writer.upserts == []
    rendered = json.dumps(report, sort_keys=True)
    assert "snap-1" not in rendered
    assert "snap-2" not in rendered

    by_table = {}
    for table, params, kwargs in writer.selects:
        by_table.setdefault(table, []).append((params, kwargs))
    assert by_table["market_provider_runs"][0][0]["provider"] == "eq.boltodds"
    assert by_table["market_provider_runs"][0][0]["slate_date"] == "eq.2026-06-16"
    assert by_table["market_feed_heartbeats"][0][0]["provider"] == "eq.boltodds"
    assert by_table["market_snapshots"][0][0]["provider"] == "eq.boltodds"
    assert by_table["compact_market_line_movements"][0][0]["provider"] == "eq.boltodds"
    assert all(kwargs == {"attempts": 1} for calls in by_table.values() for _, kwargs in calls)
    assert not any(table == "provider_request_usage_daily" for table, _, _ in writer.selects)


def test_execute_requires_environment_gate_and_exact_preview_fingerprint():
    repair = _module()
    preview_writer = FakeWriter()
    preview = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=preview_writer,
        execute=False,
    )

    gated_writer = FakeWriter()
    with pytest.raises(ValueError, match="ALLOW_COMPACT_MARKET_PARTITION_REPAIR"):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=gated_writer,
            execute=True,
            expected_preview_sha256=preview["preview_sha256"],
            allow_execute=False,
        )
    assert gated_writer.selects == []

    wrong_hash_writer = FakeWriter()
    with pytest.raises(ValueError, match="preview fingerprint"):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=wrong_hash_writer,
            execute=True,
            expected_preview_sha256="0" * 64,
            allow_execute=True,
        )
    assert wrong_hash_writer.upserts == []


def test_execute_upserts_only_changed_compacts_and_rechecks_exact_partition():
    repair = _module()
    writer = FakeWriter()
    preview = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=writer,
        execute=False,
    )

    report = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=writer,
        execute=True,
        expected_preview_sha256=preview["preview_sha256"],
        allow_execute=True,
    )

    assert report["action"] == "execute"
    assert report["database_write_performed"] is True
    assert report["written_compact_count"] == 1
    assert report["post_write_exact"] is True
    assert report["post_write_missing_compact_count"] == 0
    assert report["post_write_mismatched_compact_count"] == 0
    assert report["post_write_unexpected_compact_count"] == 0
    assert len(writer.upserts) == 1
    table, rows, on_conflict, kwargs = writer.upserts[0]
    assert table == "compact_market_line_movements"
    assert len(rows) == 1
    assert rows[0]["snapshot_count"] == 2
    assert rows[0]["odds_move_count"] == 1
    assert on_conflict == (
        "slate_date,provider,book_key,normalized_player_name,market_key,side,line"
    )
    assert kwargs == {"attempts": 1}
    assert not any(call[0] == "provider_request_usage_daily" for call in writer.upserts)


def test_unexpected_compact_blocks_execute_because_repair_never_deletes():
    repair = _module()
    extra = _compact(player="extra pitcher")
    writer = FakeWriter(existing=[_compact(), extra])

    preview = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=writer,
        execute=False,
    )

    assert preview["unexpected_compact_count"] == 1
    assert preview["execution_eligible"] is False
    with pytest.raises(ValueError, match="unexpected compact rows"):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=writer,
            execute=True,
            expected_preview_sha256=preview["preview_sha256"],
            allow_execute=True,
        )
    assert writer.upserts == []


def test_partition_scope_rejects_snapshot_provider_or_date_drift():
    repair = _module()
    wrong_provider = FakeWriter(snapshots=[
        _snapshot("snap-1", "2026-06-16T18:00:00Z", -110, provider="propline")
    ])
    with pytest.raises(ValueError, match="snapshot provider escaped requested partition"):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=wrong_provider,
            execute=False,
        )

    wrong_date = FakeWriter(snapshots=[
        _snapshot("snap-1", "2026-06-16T18:00:00Z", -110, slate_date="2026-06-15")
    ])
    with pytest.raises(ValueError, match="snapshot date escaped requested partition"):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=wrong_date,
            execute=False,
        )


def test_empty_or_already_exact_partition_is_not_execution_eligible():
    repair = _module()
    empty = FakeWriter(snapshots=[], existing=[])
    empty.snapshots = []
    empty.existing = []
    empty_report = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=empty,
        execute=False,
    )
    assert empty_report["execution_eligible"] is False
    assert "no_raw_snapshots" in empty_report["blockers"]

    exact = _compact(
        first_seen="2026-06-16T18:00:00Z",
        first_odds=-110,
        min_odds=-125,
        max_odds=-110,
        move_count=1,
        snapshot_count=2,
        source_ids=["snap-1", "snap-2"],
    )
    exact_report = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=FakeWriter(existing=[exact]),
        execute=False,
    )
    assert exact_report["rows_to_upsert_count"] == 0
    assert exact_report["execution_eligible"] is False
    assert "no_changes" in exact_report["blockers"]


def test_preview_cli_requires_output_directory_and_writes_aggregate_artifact(tmp_path, monkeypatch):
    repair = _module()
    writer = FakeWriter()
    monkeypatch.setattr(repair, "SupabaseMarketWriter", lambda *_: writer)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret-not-rendered")

    exit_code = repair.main([
        "--provider", "boltodds",
        "--date", "2026-06-16",
        "--output-dir", str(tmp_path),
    ])

    assert exit_code == 0
    output = tmp_path / "preview-boltodds-2026-06-16.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["action"] == "preview"
    assert payload["rows_to_upsert_count"] == 1
    assert "secret-not-rendered" not in output.read_text(encoding="utf-8")
    assert writer.upserts == []


def test_cli_rejects_execute_without_expected_fingerprint_before_connecting(tmp_path, monkeypatch):
    repair = _module()
    monkeypatch.setattr(
        repair,
        "SupabaseMarketWriter",
        lambda *_: pytest.fail("writer must not be created"),
    )

    exit_code = repair.main([
        "--provider", "boltodds",
        "--date", "2026-06-16",
        "--output-dir", str(tmp_path),
        "--execute",
    ])

    assert exit_code == 3
    assert list(tmp_path.iterdir()) == []


def test_cli_refuses_existing_evidence_path_before_connecting(tmp_path, monkeypatch):
    repair = _module()
    output = tmp_path / "preview-boltodds-2026-06-16.json"
    output.write_text("preserve me", encoding="utf-8")
    monkeypatch.setattr(
        repair,
        "SupabaseMarketWriter",
        lambda *_: pytest.fail("writer must not be created"),
    )
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret-not-rendered")

    exit_code = repair.main([
        "--provider", "boltodds",
        "--date", "2026-06-16",
        "--output-dir", str(tmp_path),
    ])

    assert exit_code == 3
    assert output.read_text(encoding="utf-8") == "preserve me"
