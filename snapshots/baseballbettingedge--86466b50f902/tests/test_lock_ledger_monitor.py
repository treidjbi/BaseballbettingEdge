from datetime import datetime, timezone

from scripts import monitor_lock_ledger


def _row(dedupe_key="2026-05-19:tarik skubal:over", status="due_now"):
    return {
        "dedupe_key": dedupe_key,
        "slate_date": "2026-05-19",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "status_at_capture": status,
        "observed_at": "2026-05-19T19:32:00+00:00",
        "locked_at": "2026-05-19T19:32:00+00:00",
    }


class FakeWriter:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table
        self.select_calls = []
        self.insert_calls = []
        self.delete_calls = []

    def select_rows(self, table, params):
        self.select_calls.append((table, params))
        return self.rows_by_table.get(table, [])

    def insert_rows(self, *args, **kwargs):
        self.insert_calls.append((args, kwargs))
        raise AssertionError("monitor must be read-only")

    def delete_rows(self, *args, **kwargs):
        self.delete_calls.append((args, kwargs))
        raise AssertionError("monitor must be read-only")


def test_summarize_waiting_when_no_picks_are_due():
    summary = monitor_lock_ledger.summarize(
        slate_date="2026-05-19",
        observed_at=datetime(2026, 5, 19, 18, 0, tzinfo=timezone.utc),
        artifact_generated_at="2026-05-19T17:55:00Z",
        expected_rows=[],
        ledger_rows=[],
        shadow_runs=[],
    )

    assert summary["status"] == "waiting"
    assert summary["expected_lock_rows"] == 0
    assert summary["ledger_rows"] == 0
    assert summary["missing_expected_keys"] == []


def test_summarize_ok_when_expected_rows_are_in_ledger():
    expected = [_row()]
    ledger = [_row()]

    summary = monitor_lock_ledger.summarize(
        slate_date="2026-05-19",
        observed_at=datetime(2026, 5, 19, 19, 32, tzinfo=timezone.utc),
        artifact_generated_at="2026-05-19T19:20:00Z",
        expected_rows=expected,
        ledger_rows=ledger,
        shadow_runs=[],
    )

    assert summary["status"] == "ok"
    assert summary["expected_lock_rows"] == 1
    assert summary["ledger_rows"] == 1
    assert summary["matched_expected_rows"] == 1
    assert summary["missing_expected_keys"] == []


def test_summarize_gap_when_due_row_is_missing_from_ledger():
    summary = monitor_lock_ledger.summarize(
        slate_date="2026-05-19",
        observed_at=datetime(2026, 5, 19, 19, 32, tzinfo=timezone.utc),
        artifact_generated_at="2026-05-19T19:20:00Z",
        expected_rows=[_row()],
        ledger_rows=[],
        shadow_runs=[],
    )

    assert summary["status"] == "gap"
    assert summary["missing_expected_keys"] == ["2026-05-19:tarik skubal:over"]


def test_run_monitor_reads_expected_supabase_tables_without_writes():
    writer = FakeWriter({
        "operational_pick_locks": [_row()],
        "shadow_pipeline_runs": [
            {
                "observed_at": "2026-05-19T19:32:30+00:00",
                "due_now_count": 1,
                "missed_lock_count": 0,
            }
        ],
    })
    artifact = {
        "date": "2026-05-19",
        "generated_at": "2026-05-19T19:20:00Z",
        "pitchers": [
            {
                "pitcher": "Tarik Skubal",
                "team": "DET",
                "opp_team": "BOS",
                "game_time": "2026-05-19T20:00:00Z",
                "ref_book": "FanDuel",
                "tracked_picks": [
                    {
                        "pitcher": "Tarik Skubal",
                        "side": "over",
                        "display_verdict": "FIRE 1u",
                        "display_k_line": 6.5,
                        "display_odds": -115,
                        "game_time": "2026-05-19T20:00:00Z",
                    }
                ],
            }
        ],
    }

    summary = monitor_lock_ledger.run_monitor(
        writer=writer,
        artifact=artifact,
        slate_date="2026-05-19",
        observed_at=datetime(2026, 5, 19, 19, 32, tzinfo=timezone.utc),
        artifact_source="https://raw.example/today.json",
    )

    assert summary["status"] == "ok"
    assert [call[0] for call in writer.select_calls] == [
        "operational_pick_locks",
        "shadow_pipeline_runs",
    ]
    assert writer.insert_calls == []
    assert writer.delete_calls == []
