from datetime import datetime, timezone

from analytics.diagnostics import propline_webhook_usage_audit as audit
from analytics.diagnostics.propline_webhook_usage_audit import (
    _read_supabase_rows,
    _run_linked_supabase_cli,
    summarize_webhook_usage,
)


def test_summarize_webhook_rows_counts_signed_processed_and_book_metadata():
    summary = summarize_webhook_usage(
        deliveries=[
            {
                "id": "1",
                "signature_valid": True,
                "processed": True,
                "processing_error": None,
                "received_at": "2026-06-19T16:00:00+00:00",
                "payload": {
                    "event_type": "line_movement",
                    "bookmaker_key": "draftkings",
                    "bookmaker_title": "DraftKings",
                    "market_id": "m1",
                    "outcome_id": "o1",
                },
            }
        ],
        movement_events=[],
        notification_events=[],
        market_pick_evidence=[],
        accepted_bets=[],
    )

    assert summary["deliveries"] == 1
    assert summary["signed_deliveries"] == 1
    assert summary["processed_deliveries"] == 1
    assert summary["with_bookmaker_key"] == 1
    assert summary["with_stable_market_ids"] == 1


def test_summarize_webhook_rows_recommends_dashboard_badge_not_source_switch_for_webhook_only_moves():
    summary = summarize_webhook_usage(
        deliveries=[],
        movement_events=[
            {
                "source": "propline_webhook",
                "bookmaker_key": "fanduel",
                "movement_kind": "odds",
                "observed_at": "2026-06-19T16:00:00+00:00",
            }
        ],
        notification_events=[],
        market_pick_evidence=[],
        accepted_bets=[],
    )

    assert "dashboard_webhook_confirmed_badge" in summary["recommended_uses"]
    assert "official_odds_source" not in summary["recommended_uses"]


def test_summarize_webhook_rows_keeps_blocked_uses_closed():
    summary = summarize_webhook_usage(
        deliveries=[],
        movement_events=[],
        notification_events=[],
        market_pick_evidence=[],
        accepted_bets=[],
    )

    assert summary["blocked_uses"] == [
        "official_odds_source",
        "model_input",
        "staking_input",
        "automatic_bet_trigger",
    ]


def test_summarize_webhook_rows_counts_duplicates_stale_and_confirmed_overlap():
    summary = summarize_webhook_usage(
        deliveries=[],
        movement_events=[
            {
                "dedupe_key": "same",
                "metadata": {"source": "propline_webhook", "polling_confirmed": True},
            },
            {
                "dedupe_key": "same",
                "metadata": {"source": "propline_webhook", "freshness_status": "stale"},
            },
            {
                "dedupe_key": "other",
                "metadata": {"source": "propline_polling"},
            },
        ],
        notification_events=[
            {"event_type": "line_movement", "payload": {"source": "propline_webhook"}},
            {"event_type": "lock_reminder", "payload": {"source": "scheduler"}},
        ],
        market_pick_evidence=[
            {"metadata": {"propline_webhook_confirmed": True}},
        ],
        accepted_bets=[
            {"metadata": {"propline_webhook_confirmed": True}},
            {"metadata": {"source": "manual"}},
        ],
    )

    assert summary["duplicate_dedupe_keys"] == 1
    assert summary["post_start_or_stale_events"] == 1
    assert summary["polling_confirmed_movement_events"] == 1
    assert summary["webhook_only_movement_events"] == 1
    assert summary["webhook_notification_events"] == 1
    assert summary["accepted_bet_overlap_count"] == 1
    assert "movement_strength_label" in summary["recommended_uses"]
    assert "notification_priority_boost" in summary["recommended_uses"]
    assert "accepted_bet_context_tag" in summary["recommended_uses"]
    assert "provider_refresh_trigger_shadow" in summary["recommended_uses"]


def test_read_supabase_rows_uses_linked_cli_when_service_role_env_missing(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    calls = []

    def fake_cli_runner(command, **kwargs):
        calls.append(command)
        sql = command[-1]
        if "propline_webhook_deliveries" in sql:
            return {
                "rows": [
                    {
                        "id": "delivery-1",
                        "signature_valid": True,
                        "processed": True,
                        "payload": {"bookmaker_key": "draftkings"},
                    }
                ]
            }
        if "line_movement_events" in sql:
            return {
                "rows": [
                    {
                        "id": "movement-1",
                        "metadata": {"source": "propline_webhook"},
                        "dedupe_key": "move-1",
                    }
                ]
            }
        return {"rows": []}

    result = _read_supabase_rows(
        start_dt=datetime(2026, 6, 17, tzinfo=timezone.utc),
        end_dt=datetime(2026, 6, 19, 23, 59, 59, tzinfo=timezone.utc),
        limit=100,
        cli_runner=fake_cli_runner,
    )

    assert result["access_status"] == "complete"
    assert result["deliveries"][0]["id"] == "delivery-1"
    assert result["movement_events"][0]["id"] == "movement-1"
    assert result["row_counts"]["propline_webhook_deliveries"] == 1
    assert result["row_counts"]["line_movement_events"] == 1
    assert all(command[:6] == ["npx", "supabase", "db", "query", "--linked", "-o"] for command in calls)
    assert all(command[6] == "json" for command in calls)
    assert all("\n" not in command[-1] for command in calls)


def test_read_supabase_rows_marks_partial_when_optional_cli_table_fails(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    def fake_cli_runner(command, **kwargs):
        sql = command[-1]
        if "accepted_bets" in sql:
            raise RuntimeError("relation does not exist")
        return {"rows": []}

    result = _read_supabase_rows(
        start_dt=datetime(2026, 6, 17, tzinfo=timezone.utc),
        end_dt=datetime(2026, 6, 19, 23, 59, 59, tzinfo=timezone.utc),
        limit=100,
        cli_runner=fake_cli_runner,
    )

    assert result["access_status"] == "partial"
    assert result["accepted_bets"] == []
    assert any("accepted_bets table unavailable" in issue for issue in result["access_issues"])


def test_read_supabase_rows_blocks_when_linked_cli_path_fails(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    def fake_cli_runner(command, **kwargs):
        raise RuntimeError("pooler unavailable")

    result = _read_supabase_rows(
        start_dt=datetime(2026, 6, 17, tzinfo=timezone.utc),
        end_dt=datetime(2026, 6, 19, 23, 59, 59, tzinfo=timezone.utc),
        limit=100,
        cli_runner=fake_cli_runner,
    )

    assert result["access_status"] == "blocked"
    assert result["row_counts"] == {}
    assert any("Linked Supabase CLI read failed" in issue for issue in result["access_issues"])


def test_linked_cli_runner_resolves_windows_npx_cmd(monkeypatch):
    commands = []

    def fake_which(executable):
        return {"npx": None, "npx.cmd": "C:/tools/npx.cmd"}.get(executable)

    def fake_run(command, **kwargs):
        commands.append(command)

        class Completed:
            stdout = '{"rows":[]}'

        return Completed()

    monkeypatch.setattr(audit.shutil, "which", fake_which)
    monkeypatch.setattr(audit.subprocess, "run", fake_run)

    assert _run_linked_supabase_cli(["npx", "supabase", "db", "query", "--linked", "-o", "json", "select now();"]) == {
        "rows": []
    }
    assert commands[0][0] == "C:/tools/npx.cmd"
