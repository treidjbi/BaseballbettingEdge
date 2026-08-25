import importlib
import json

import pytest
import requests


RUN_ID = "11111111-1111-4111-8111-111111111111"
OTHER_RUN_ID = "22222222-2222-4222-8222-222222222222"
SNAP_1 = "00000000-0000-4000-8000-000000000001"
SNAP_2 = "00000000-0000-4000-8000-000000000002"
SNAP_3 = "00000000-0000-4000-8000-000000000003"


def _module():
    return importlib.import_module("scripts.repair_compact_market_snapshot_partition")


def _snapshot(snapshot_id, observed_at, odds, *, provider="boltodds", run_id=RUN_ID,
              slate_date="2026-06-16"):
    return {
        "id": snapshot_id,
        "run_id": run_id,
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
        "source_snapshot_ids": list(source_ids or [SNAP_2]),
    }


class FakeWriter:
    def __init__(self, *, snapshots=None, existing=None, run_rows=None, heartbeats=None,
                 parent_rows=None, post_write_snapshots=None, post_write_heartbeats=None,
                 upsert_error=None, apply_before_error=False):
        self.snapshots = list([
            _snapshot(SNAP_1, "2026-06-16T18:00:00Z", -110),
            _snapshot(SNAP_2, "2026-06-16T18:05:00Z", -125),
        ] if snapshots is None else snapshots)
        self.existing = list([_compact()] if existing is None else existing)
        self.run_rows = list([{
            "id": RUN_ID,
            "provider": "boltodds",
            "slate_date": "2026-06-16",
            "created_at": "2026-06-16T18:00:00Z",
        }] if run_rows is None else run_rows)
        self.heartbeats = list([] if heartbeats is None else heartbeats)
        self.parent_rows = list([] if parent_rows is None else parent_rows)
        self.post_write_snapshots = (
            None if post_write_snapshots is None else list(post_write_snapshots)
        )
        self.post_write_heartbeats = (
            None if post_write_heartbeats is None else list(post_write_heartbeats)
        )
        self.upsert_error = upsert_error
        self.apply_before_error = apply_before_error
        self.selects = []
        self.upserts = []

    def select_rows(self, table, params, **kwargs):
        self.selects.append((table, dict(params), dict(kwargs)))
        if table == "market_provider_runs" and "slate_date" in params:
            return list(self.run_rows)
        if table == "market_feed_heartbeats":
            if self.upserts and self.post_write_heartbeats is not None:
                return list(self.post_write_heartbeats)
            return list(self.heartbeats)
        if table == "market_provider_runs" and "id" in params:
            wanted = params["id"]
            return [row for row in self.parent_rows if row["id"] in wanted]
        if table == "market_snapshots":
            selected = (
                self.post_write_snapshots
                if self.upserts and self.post_write_snapshots is not None
                else self.snapshots
            )
            if "offset" in params:
                return list(selected) if params["offset"] == "0" else []
            return list(selected) if "or" not in params else []
        if table == "compact_market_line_movements":
            selected = [
                dict(row, id=row.get("id", index))
                for index, row in enumerate(self.existing, start=1)
            ]
            if "offset" in params:
                return selected if params["offset"] == "0" else []
            return selected if "id" not in params else []
        return []

    def upsert_rows(self, table, rows, on_conflict, **kwargs):
        copied = [dict(row) for row in rows]
        self.upserts.append((table, copied, on_conflict, dict(kwargs)))
        if self.upsert_error is not None and not self.apply_before_error:
            raise self.upsert_error
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
        if self.upsert_error is not None:
            raise self.upsert_error
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
    assert report["snapshot_in_window_count"] == 2
    assert report["snapshot_out_of_window_count"] == 0
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
    assert report["preview_fingerprint_version"] == 4
    assert len(report["preview_sha256"]) == 64
    assert writer.upserts == []
    rendered = json.dumps(report, sort_keys=True)
    assert SNAP_1 not in rendered
    assert SNAP_2 not in rendered

    by_table = {}
    for table, params, kwargs in writer.selects:
        by_table.setdefault(table, []).append((params, kwargs))
    assert by_table["market_provider_runs"][0][0]["provider"] == "eq.boltodds"
    assert by_table["market_provider_runs"][0][0]["slate_date"] == "eq.2026-06-16"
    assert by_table["market_feed_heartbeats"][0][0]["provider"] == "eq.boltodds"
    assert by_table["market_snapshots"][0][0]["provider"] == "eq.boltodds"
    assert "source_payload" not in by_table["market_snapshots"][0][0]["select"]
    assert "and" not in by_table["market_snapshots"][0][0]
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


@pytest.mark.parametrize(
    "slate_date",
    [
        "2026-06-02",
        "2026-06-03",
        "2026-06-05",
        "2026-06-06",
        "2026-06-09",
        "2026-06-12",
        "2026-06-13",
        "2026-06-14",
        "2026-06-15",
        "2026-06-16",
    ],
)
def test_execute_allowlist_contains_only_reviewed_boltodds_repair_dates(slate_date):
    repair = _module()

    assert repair.is_execution_partition("boltodds", slate_date) is True
    assert repair.is_execution_partition("propline", slate_date) is False


@pytest.mark.parametrize("provider", ["propline", "therundown"])
def test_execute_is_hard_limited_to_reviewed_boltodds_repair_partitions(provider):
    repair = _module()
    writer = FakeWriter()
    with pytest.raises(ValueError, match="reviewed BoltOdds repair partitions"):
        repair.run(
            provider=provider,
            slate_date="2026-06-16",
            writer=writer,
            execute=True,
            expected_preview_sha256="0" * 64,
            allow_execute=True,
        )
    assert writer.selects == []


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


def test_execute_rechecks_raw_partition_and_fails_exactness_if_source_rows_change():
    repair = _module()
    initial = [
        _snapshot(SNAP_1, "2026-06-16T18:00:00Z", -110),
        _snapshot(SNAP_2, "2026-06-16T18:05:00Z", -125),
    ]
    changed = initial + [
        _snapshot(SNAP_3, "2026-06-16T18:10:00Z", -120),
    ]
    writer = FakeWriter(snapshots=initial, post_write_snapshots=changed)
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

    assert report["post_write_preview_still_current"] is False
    assert report["post_write_exact"] is False
    assert report["post_write_mismatched_compact_count"] == 1


def test_execute_rejects_current_preview_when_quarantined_heartbeat_count_changes():
    repair = _module()
    changed_heartbeat = {
        "id": "33333333-3333-4333-8333-333333333333",
        "run_id": OTHER_RUN_ID,
        "provider": "boltodds",
        "slate_date": "2026-06-16",
        "observed_at": "2026-06-17T17:20:59Z",
    }
    writer = FakeWriter(post_write_heartbeats=[changed_heartbeat])
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

    assert report["post_write_out_of_window_heartbeat_count"] == 1
    assert report["post_write_preview_still_current"] is False
    assert report["post_write_exact"] is False


def test_ambiguous_upsert_failure_is_sanitized_and_followed_by_exact_post_check():
    repair = _module()
    writer = FakeWriter(
        upsert_error=requests.Timeout(
            "https://example.supabase.co/rest/v1/table?run_id=secret-row-id"
        )
    )
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

    assert report["database_write_outcome"] == "ambiguous"
    assert report["database_write_performed"] is None
    assert report["write_error_type"] == "Timeout"
    assert report["post_write_check_completed"] is True
    assert report["post_write_exact"] is False
    rendered = json.dumps(report, sort_keys=True)
    assert "secret-row-id" not in rendered
    assert "example.supabase.co" not in rendered


def test_ambiguous_upsert_that_reached_database_is_confirmed_only_by_post_state():
    repair = _module()
    writer = FakeWriter(
        upsert_error=requests.Timeout("ambiguous"),
        apply_before_error=True,
    )
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

    assert report["database_write_outcome"] == "confirmed_by_post_state"
    assert report["database_write_performed"] is None
    assert report["post_write_exact"] is True


def test_keyset_paged_raw_partition_is_not_blocked_only_for_pagination():
    repair = _module()
    snapshots = [
        _snapshot(
            f"00000000-0000-4000-8000-{index + 1:012x}",
            "2026-06-16T18:00:00Z",
            -110,
        )
        for index in range(1000)
    ]
    writer = FakeWriter(snapshots=snapshots)

    report = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=writer,
        execute=False,
    )

    assert report["raw_snapshot_count"] == 1000
    assert "snapshot_pagination_required" not in report["blockers"]


def test_snapshot_reader_uses_strict_observed_at_and_id_keyset(monkeypatch):
    repair = _module()
    monkeypatch.setattr(repair, "PAGE_SIZE", 2)
    rows = [
        _snapshot(
            "00000000-0000-4000-8000-000000000001",
            "2026-06-16T18:00:00Z",
            -110,
        ),
        _snapshot(
            "00000000-0000-4000-8000-000000000002",
            "2026-06-16T18:00:00Z",
            -115,
        ),
        _snapshot(
            "00000000-0000-4000-8000-000000000003",
            "2026-06-16T18:01:00Z",
            -120,
        ),
    ]

    class PagingWriter:
        def __init__(self):
            self.calls = []

        def select_rows(self, table, params, **kwargs):
            self.calls.append((table, dict(params), dict(kwargs)))
            return rows[:2] if len(self.calls) == 1 else rows[2:]

    writer = PagingWriter()
    selected = repair._fetch_snapshot_rows(
        writer,
        provider="boltodds",
        slate_date="2026-06-16",
        run_rows=[{"id": RUN_ID}],
    )

    assert len(selected) == 3
    assert len(writer.calls) == 2
    first = writer.calls[0][1]
    second = writer.calls[1][1]
    assert first["order"] == "observed_at.asc,id.asc"
    assert "offset" not in first
    assert "offset" not in second
    assert second["or"] == (
        "(observed_at.gt.2026-06-16T18:00:00Z,"
        "and(observed_at.eq.2026-06-16T18:00:00Z,"
        "id.gt.00000000-0000-4000-8000-000000000002))"
    )
    assert all(kwargs == {"attempts": 1} for _, _, kwargs in writer.calls)


def test_snapshot_preview_keyset_paging_continues_beyond_twenty_full_pages(
    monkeypatch,
):
    repair = _module()
    monkeypatch.setattr(repair, "PAGE_SIZE", 1)
    rows = [
        _snapshot(
            f"00000000-0000-4000-8000-{index:012x}",
            "2026-06-16T18:00:00Z",
            -110,
        )
        for index in range(1, 22)
    ]

    class PagingWriter:
        def __init__(self):
            self.calls = []

        def select_rows(self, table, params, **kwargs):
            self.calls.append((table, dict(params), dict(kwargs)))
            page = len(self.calls) - 1
            return rows[page:page + 1]

    writer = PagingWriter()
    selected = repair._fetch_snapshot_rows(
        writer,
        provider="boltodds",
        slate_date="2026-06-16",
        run_rows=[{"id": RUN_ID}],
    )

    assert len(selected) == 21
    assert len(writer.calls) == 22
    assert all(kwargs == {"attempts": 1} for _, _, kwargs in writer.calls)


def test_snapshot_preview_still_fails_closed_at_enlarged_page_ceiling(monkeypatch):
    repair = _module()
    monkeypatch.setattr(repair, "PAGE_SIZE", 1)

    class FullPageWriter:
        def __init__(self):
            self.calls = []

        def select_rows(self, table, params, **kwargs):
            self.calls.append((table, dict(params), dict(kwargs)))
            index = len(self.calls)
            return [
                _snapshot(
                    f"00000000-0000-4000-8000-{index:012x}",
                    "2026-06-16T18:00:00Z",
                    -110,
                )
            ]

    writer = FullPageWriter()
    with pytest.raises(
        ValueError,
        match="snapshot query reached its fail-closed page ceiling",
    ):
        repair._fetch_snapshot_rows(
            writer,
            provider="boltodds",
            slate_date="2026-06-16",
            run_rows=[{"id": RUN_ID}],
        )

    assert len(writer.calls) == 75


def test_compact_reader_uses_strict_id_keyset(monkeypatch):
    repair = _module()
    monkeypatch.setattr(repair, "PAGE_SIZE", 2)
    rows = []
    for compact_id in (1, 2, 3):
        row = _compact(player=f"pitcher {compact_id}")
        row["id"] = compact_id
        rows.append(row)

    class PagingWriter:
        def __init__(self):
            self.calls = []

        def select_rows(self, table, params, **kwargs):
            self.calls.append((table, dict(params), dict(kwargs)))
            return rows[:2] if len(self.calls) == 1 else rows[2:]

    writer = PagingWriter()
    selected = repair._fetch_existing_compacts(
        writer,
        provider="boltodds",
        slate_date="2026-06-16",
    )

    assert len(selected) == 3
    assert all("id" not in row for row in selected)
    assert len(writer.calls) == 2
    first = writer.calls[0][1]
    second = writer.calls[1][1]
    assert first["select"].startswith("id,")
    assert first["order"] == "id.asc"
    assert "offset" not in first
    assert "offset" not in second
    assert second["id"] == "gt.2"
    assert all(kwargs == {"attempts": 1} for _, _, kwargs in writer.calls)


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
        _snapshot(SNAP_1, "2026-06-16T18:00:00Z", -110, provider="propline")
    ])
    with pytest.raises(ValueError, match="snapshot provider escaped requested partition"):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=wrong_provider,
            execute=False,
        )

    wrong_date = FakeWriter(snapshots=[
        _snapshot(SNAP_1, "2026-06-16T18:00:00Z", -110, slate_date="2026-06-15")
    ])
    with pytest.raises(ValueError, match="snapshot date escaped requested partition"):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=wrong_date,
            execute=False,
        )


def test_normal_schema_snapshot_without_slate_date_uses_verified_run_lineage():
    repair = _module()
    snapshot = _snapshot(SNAP_1, "2026-06-16T18:00:00Z", -110)
    snapshot.pop("slate_date")
    report = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=FakeWriter(snapshots=[snapshot], existing=[]),
        execute=False,
    )
    assert report["raw_snapshot_count"] == 1


def test_partition_scope_rejects_run_drift():
    repair = _module()
    snapshot = _snapshot(
        SNAP_1,
        "2026-06-16T18:00:00Z",
        -110,
        run_id=OTHER_RUN_ID,
    )
    with pytest.raises(ValueError, match="snapshot run escaped requested partition"):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=FakeWriter(snapshots=[snapshot]),
            execute=False,
        )


def test_verified_run_lineage_includes_and_counts_cross_phoenix_boundary_snapshot():
    repair = _module()
    snapshot = _snapshot(SNAP_1, "2026-06-17T07:00:00Z", -110)

    report = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=FakeWriter(snapshots=[snapshot], existing=[]),
        execute=False,
    )

    assert report["raw_snapshot_count"] == 1
    assert report["snapshot_in_window_count"] == 0
    assert report["snapshot_out_of_window_count"] == 1
    assert "unexpected_compact_rows" not in report["blockers"]


@pytest.mark.parametrize(
    "heartbeat",
    [
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "run_id": OTHER_RUN_ID,
            "provider": "propline",
            "slate_date": "2026-06-16",
            "observed_at": "2026-06-16T18:00:00Z",
        },
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "run_id": OTHER_RUN_ID,
            "provider": "boltodds",
            "slate_date": "2026-06-15",
            "observed_at": "2026-06-16T18:00:00Z",
        },
    ],
)
def test_partition_scope_rejects_heartbeat_provider_or_date_drift(heartbeat):
    repair = _module()
    writer = FakeWriter(heartbeats=[heartbeat])
    with pytest.raises(ValueError, match="heartbeat escaped requested partition"):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=writer,
            execute=False,
        )


def test_out_of_window_heartbeat_is_quarantined_and_reported_without_expanding_lineage():
    repair = _module()
    heartbeat = {
        "id": "33333333-3333-4333-8333-333333333333",
        "run_id": OTHER_RUN_ID,
        "provider": "boltodds",
        "slate_date": "2026-06-16",
        "observed_at": "2026-06-17T17:20:59Z",
    }
    parent = {
        "id": OTHER_RUN_ID,
        "provider": "boltodds",
        "slate_date": "2026-06-17",
        "created_at": "2026-06-17T17:20:59Z",
    }
    writer = FakeWriter(heartbeats=[heartbeat], parent_rows=[parent])

    report = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=writer,
        execute=False,
    )

    assert report["provider_run_count"] == 1
    assert report["heartbeat_row_count"] == 1
    assert report["in_window_heartbeat_count"] == 0
    assert report["out_of_window_heartbeat_count"] == 1
    assert report["execution_eligible"] is True
    parent_reads = [
        params
        for table, params, _kwargs in writer.selects
        if table == "market_provider_runs" and "id" in params
    ]
    assert parent_reads == []


def test_preview_fingerprint_binds_out_of_window_heartbeat_count():
    repair = _module()
    baseline = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=FakeWriter(),
        execute=False,
    )
    heartbeat = {
        "id": "33333333-3333-4333-8333-333333333333",
        "run_id": OTHER_RUN_ID,
        "provider": "boltodds",
        "slate_date": "2026-06-16",
        "observed_at": "2026-06-17T17:20:59Z",
    }
    quarantined = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=FakeWriter(heartbeats=[heartbeat]),
        execute=False,
    )

    assert baseline["rebuilt_compacts_sha256"] == quarantined["rebuilt_compacts_sha256"]
    assert baseline["preview_sha256"] != quarantined["preview_sha256"]


def test_partition_scope_rejects_malformed_provider_run_uuid():
    repair = _module()
    writer = FakeWriter(run_rows=[{
        "id": "run-1)or(true",
        "provider": "boltodds",
        "slate_date": "2026-06-16",
        "created_at": "2026-06-16T18:00:00Z",
    }])
    with pytest.raises(ValueError, match="provider run id must be a UUID"):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=writer,
            execute=False,
        )


def test_valid_heartbeat_parent_keeps_original_run_date_and_uses_snapshot_window():
    repair = _module()
    heartbeat = {
        "id": "33333333-3333-4333-8333-333333333333",
        "run_id": OTHER_RUN_ID,
        "provider": "boltodds",
        "slate_date": "2026-06-16",
        "observed_at": "2026-06-16T18:00:00Z",
    }
    parent = {
        "id": OTHER_RUN_ID,
        "provider": "boltodds",
        "slate_date": "2026-05-01",
        "created_at": "2026-05-01T18:00:00Z",
    }
    snapshot = _snapshot(
        SNAP_1,
        "2026-06-16T18:05:00Z",
        -125,
        run_id=OTHER_RUN_ID,
    )
    snapshot.pop("slate_date")
    writer = FakeWriter(
        run_rows=[],
        heartbeats=[heartbeat],
        parent_rows=[parent],
        snapshots=[snapshot],
        existing=[],
    )

    report = repair.run(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=writer,
        execute=False,
    )

    assert report["provider_run_count"] == 1
    assert report["raw_snapshot_count"] == 1
    assert parent["slate_date"] == "2026-05-01"


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
        source_ids=[SNAP_1, SNAP_2],
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


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("line", "NaN", "line must be a finite number"),
        ("snapshot_count", 1.5, "snapshot_count must be an integer"),
        ("odds_move_count", -1, "odds_move_count must be nonnegative"),
    ],
)
def test_malformed_compact_numeric_values_fail_closed(field, value, message):
    repair = _module()
    malformed = _compact()
    malformed[field] = value
    with pytest.raises(ValueError, match=message):
        repair.run(
            provider="boltodds",
            slate_date="2026-06-16",
            writer=FakeWriter(existing=[malformed]),
            execute=False,
        )


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


def test_cli_sanitizes_supabase_select_failure_without_writing_report(
    tmp_path, monkeypatch, capsys,
):
    repair = _module()

    class FailingWriter(FakeWriter):
        def select_rows(self, table, params, **kwargs):
            raise requests.HTTPError(
                "https://example.supabase.co/rest/v1/table?run_id=secret-row-id"
            )

    monkeypatch.setattr(repair, "SupabaseMarketWriter", lambda *_: FailingWriter())
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret-not-rendered")

    exit_code = repair.main([
        "--provider", "boltodds",
        "--date", "2026-06-16",
        "--output-dir", str(tmp_path),
    ])

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "supabase_request_failed: HTTPError" in captured.err
    assert "secret-row-id" not in captured.err
    assert "secret-not-rendered" not in captured.err
    assert list(tmp_path.iterdir()) == []
