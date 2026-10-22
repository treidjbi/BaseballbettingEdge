from market_infra.provider_usage import (
    build_provider_usage_rows,
    propline_budget_warnings,
    write_provider_usage_rows,
)


def test_build_provider_usage_rows_aggregates_requests_and_snapshots_by_source():
    rows = build_provider_usage_rows(
        run_rows=[
            {
                "id": "run-1",
                "provider": "propline",
                "mode": "shadow_poll",
                "slate_date": "2026-05-14",
                "request_count": 9,
                "metadata": {"script": "scripts/shadow_propline_to_supabase.py"},
            },
            {
                "id": "run-2",
                "provider": "propline",
                "mode": "shadow_poll",
                "slate_date": "2026-05-14",
                "request_count": 4,
                "metadata": {"script": "scripts/shadow_propline_to_supabase.py"},
            },
            {
                "id": "run-3",
                "provider": "boltodds",
                "mode": "shadow_stream",
                "slate_date": "2026-05-14",
                "request_count": 1,
                "metadata": {"worker": "scripts/boltodds_ws_worker.py"},
            },
        ],
        snapshot_rows=[
            {"run_id": "run-1", "provider": "propline"},
            {"run_id": "run-2", "provider": "propline"},
            {"run_id": "run-2", "provider": "propline"},
            {"run_id": "run-3", "provider": "boltodds"},
        ],
        usage_date="2026-05-14",
    )

    assert rows == [
        {
            "usage_date": "2026-05-14",
            "provider": "boltodds",
            "source": "scripts/boltodds_ws_worker.py",
            "request_count": 1,
            "snapshot_count": 1,
        },
        {
            "usage_date": "2026-05-14",
            "provider": "propline",
            "source": "scripts/shadow_propline_to_supabase.py",
            "request_count": 13,
            "snapshot_count": 3,
        },
    ]


def test_propline_budget_warning_starts_at_seventy_percent():
    warnings = propline_budget_warnings([
        {
            "usage_date": "2026-05-14",
            "provider": "propline",
            "source": "scripts/shadow_propline_to_supabase.py",
            "request_count": 3500,
            "snapshot_count": 200,
        }
    ])

    assert warnings == [
        "PropLine request usage 3500/5000 (70.0%) for 2026-05-14 source=scripts/shadow_propline_to_supabase.py"
    ]


class FakeWriter:
    def __init__(self):
        self.selects = []
        self.upserts = []

    def select_rows(self, table, params):
        self.selects.append((table, dict(params)))
        if table == "provider_request_usage_daily":
            return [{
                "usage_date": "2026-05-14",
                "provider": "propline",
                "source": "scripts/shadow_propline_to_supabase.py",
                "request_count": 287,
                "snapshot_count": 958,
            }]
        return []

    def upsert_rows(self, table, rows, on_conflict):
        self.upserts.append((table, rows, on_conflict))
        return rows


def test_write_provider_usage_rows_keeps_existing_max_counts():
    writer = FakeWriter()

    write_provider_usage_rows(
        writer,
        [{
            "usage_date": "2026-05-14",
            "provider": "propline",
            "source": "scripts/shadow_propline_to_supabase.py",
            "request_count": 282,
            "snapshot_count": 389,
        }],
    )

    assert writer.upserts == [(
        "provider_request_usage_daily",
        [{
            "usage_date": "2026-05-14",
            "provider": "propline",
            "source": "scripts/shadow_propline_to_supabase.py",
            "request_count": 287,
            "snapshot_count": 958,
        }],
        "usage_date,provider,source",
    )]
