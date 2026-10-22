import json

from analytics.diagnostics.boltodds_migration_risk_audit import (
    audit_migration_risk,
    main,
)


NOW = "2026-05-07T18:00:00+00:00"


def _run(status="completed", **overrides):
    row = {
        "provider": "boltodds",
        "mode": "shadow_stream",
        "slate_date": "2026-05-07",
        "status": status,
        "created_at": "2026-05-07T17:30:00+00:00",
        "completed_at": "2026-05-07T17:45:00+00:00",
        "request_count": 1,
        "books_seen": ["fanduel", "draftkings", "betmgm"],
        "metadata": {"selected_markets": ["pitcher_strikeouts"]},
    }
    row.update(overrides)
    return row


def _completed_run_with_probe_summary(**overrides):
    return _run(
        metadata={
            "probe_summary": {
                "selected_markets": ["Pitcher Strikeouts"],
            }
        },
        **overrides,
    )


def _coverage(**overrides):
    row = {
        "provider": "boltodds",
        "slate_date": "2026-05-07",
        "created_at": "2026-05-07T17:50:00+00:00",
        "target_event_count": 15,
        "parsed_pitcher_prop_count": 18,
        "complete_pitcher_line_groups": 18,
        "same_line_overlap_count": 14,
        "line_conflict_count": 0,
        "missing_target_books": [],
        "metadata": {
            "target_book_group_counts": {
                "fanduel": 18,
                "draftkings": 17,
                "betmgm": 10,
            },
            "production_book_group_counts": {
                "fanduel": 18,
                "draftkings": 17,
            },
        },
    }
    row.update(overrides)
    return row


def _heartbeat(**overrides):
    row = {
        "provider": "boltodds",
        "mode": "shadow_stream",
        "slate_date": "2026-05-07",
        "observed_at": "2026-05-07T17:58:00+00:00",
        "last_message_at": "2026-05-07T17:57:30+00:00",
        "books_seen": ["fanduel", "draftkings", "betmgm"],
        "metadata": {"event": "flush", "selected_markets": ["pitcher_strikeouts"]},
    }
    row.update(overrides)
    return row


def test_ready_for_trial_when_feed_runs_coverage_and_artifacts_are_fresh():
    result = audit_migration_risk(
        provider_run_rows=[_run()],
        coverage_audit_rows=[_coverage()],
        heartbeat_rows=[_heartbeat()],
        artifact_metadata={
            "current_slate_date": "2026-05-07",
            "today_json_updated_at": "2026-05-07T17:40:00+00:00",
            "notifications_last_sent_at": "2026-05-07T17:42:00+00:00",
        },
        now=NOW,
    )

    assert result["status"] == "ready_for_trial"
    assert result["blocking_reasons"] == []
    assert result["book_coverage"]["required_books"] == {
        "fanduel": "present",
        "betmgm_or_betrivers": "present",
    }
    assert result["book_coverage"]["optional_books"]["draftkings"] == "present"
    assert "kalshi" not in result["book_coverage"]["optional_books"]
    assert result["slate_alignment"] == {
        "current_slate_date": "2026-05-07",
        "latest_provider_run_slate_date": "2026-05-07",
        "latest_heartbeat_slate_date": "2026-05-07",
        "latest_coverage_audit_slate_date": "2026-05-07",
        "current_slate_coverage_rows": 1,
    }


def test_caesars_missing_is_reported_but_not_blocking():
    result = audit_migration_risk(
        provider_run_rows=[_run()],
        coverage_audit_rows=[
            _coverage(
                missing_target_books=["caesars"],
                metadata={
                    "target_book_group_counts": {
                        "fanduel": 10,
                        "betrivers": 7,
                        "caesars": 0,
                    }
                },
            )
        ],
        heartbeat_rows=[_heartbeat(books_seen=["fanduel", "draftkings", "betrivers"])],
        now=NOW,
    )

    assert result["status"] == "proceed_with_caution"
    assert "caesars_missing_optional" in result["risk_flags"]
    assert all("caesars" not in reason for reason in result["blocking_reasons"])
    assert result["book_coverage"]["required_books"]["betmgm_or_betrivers"] == "present"


def test_not_ready_with_stale_heartbeat_and_failed_latest_run():
    result = audit_migration_risk(
        provider_run_rows=[
            _run(status="completed", completed_at="2026-05-07T16:00:00+00:00"),
            _run(
                status="failed",
                completed_at="2026-05-07T17:55:00+00:00",
                error_message="socket closed",
            ),
        ],
        coverage_audit_rows=[_coverage()],
        heartbeat_rows=[
            _heartbeat(
                observed_at="2026-05-07T17:00:00+00:00",
                last_message_at="2026-05-07T17:00:00+00:00",
            )
        ],
        now=NOW,
    )

    assert result["status"] == "not_ready"
    assert "stale_heartbeat" in result["risk_flags"]
    assert "latest_provider_run_failed" in result["risk_flags"]
    assert "Latest BoltOdds provider run failed." in result["blocking_reasons"]


def test_not_ready_when_required_books_or_selected_market_are_missing():
    result = audit_migration_risk(
        provider_run_rows=[_run(metadata={"selected_markets": ["moneyline"]})],
        coverage_audit_rows=[
            _coverage(
                same_line_overlap_count=0,
                metadata={
                    "target_book_group_counts": {
                        "fanduel": 0,
                        "draftkings": 12,
                        "caesars": 8,
                    }
                },
            )
        ],
        heartbeat_rows=[
            _heartbeat(metadata={"event": "flush", "selected_markets": ["moneyline"]})
        ],
        now=NOW,
    )

    assert result["status"] == "not_ready"
    assert "missing_required_book:fanduel" in result["risk_flags"]
    assert "missing_required_book:betmgm_or_betrivers" in result["risk_flags"]
    assert "missing_selected_market:pitcher_strikeouts" in result["risk_flags"]
    assert "no_same_line_overlap" in result["risk_flags"]


def test_selected_market_can_come_from_provider_run_probe_summary():
    result = audit_migration_risk(
        provider_run_rows=[_completed_run_with_probe_summary()],
        coverage_audit_rows=[_coverage()],
        heartbeat_rows=[_heartbeat(metadata={"event": "completed"})],
        artifact_metadata={
            "today_json_updated_at": "2026-05-07T17:40:00+00:00",
            "notifications_last_sent_at": "2026-05-07T17:42:00+00:00",
        },
        now=NOW,
    )

    assert result["status"] == "ready_for_trial"
    assert "pitcher_strikeouts" in result["selected_markets"]
    assert "missing_selected_market:pitcher_strikeouts" not in result["risk_flags"]


def test_missing_artifact_metadata_is_caution_not_green():
    result = audit_migration_risk(
        provider_run_rows=[_run()],
        coverage_audit_rows=[_coverage()],
        heartbeat_rows=[_heartbeat()],
        now=NOW,
    )

    assert result["status"] == "proceed_with_caution"
    assert "missing_today_artifact_metadata" in result["risk_flags"]
    assert "missing_notification_metadata" in result["risk_flags"]
    assert result["blocking_reasons"] == []


def test_coverage_uses_best_counts_across_batches_not_latest_only():
    result = audit_migration_risk(
        provider_run_rows=[_run()],
        coverage_audit_rows=[
            _coverage(
                created_at="2026-05-07T17:45:00+00:00",
                same_line_overlap_count=10,
                metadata={
                    "target_book_group_counts": {
                        "fanduel": 10,
                        "draftkings": 9,
                        "betmgm": 4,
                    }
                },
            ),
            _coverage(
                created_at="2026-05-07T17:55:00+00:00",
                same_line_overlap_count=0,
                complete_pitcher_line_groups=1,
                metadata={
                    "target_book_group_counts": {
                        "fanduel": 0,
                        "draftkings": 0,
                        "betmgm": 0,
                    }
                },
            ),
        ],
        heartbeat_rows=[_heartbeat()],
        artifact_metadata={
            "today_json_updated_at": "2026-05-07T17:40:00+00:00",
            "notifications_last_sent_at": "2026-05-07T17:42:00+00:00",
        },
        now=NOW,
    )

    assert result["status"] == "ready_for_trial"
    assert result["book_coverage"]["required_books"] == {
        "fanduel": "present",
        "betmgm_or_betrivers": "present",
    }
    assert result["coverage"]["same_line_overlap_count"] == 10


def test_draftkings_missing_is_optional_after_partial_trial_approval():
    result = audit_migration_risk(
        provider_run_rows=[_run(books_seen=["fanduel", "betmgm"])],
        coverage_audit_rows=[
            _coverage(
                metadata={
                    "target_book_group_counts": {
                        "fanduel": 12,
                        "draftkings": 0,
                        "betmgm": 8,
                    }
                }
            )
        ],
        heartbeat_rows=[_heartbeat(books_seen=["fanduel", "betmgm"])],
        artifact_metadata={
            "today_json_updated_at": "2026-05-07T17:40:00+00:00",
            "notifications_last_sent_at": "2026-05-07T17:42:00+00:00",
        },
        now=NOW,
    )

    assert result["status"] == "ready_for_trial"
    assert result["book_coverage"]["required_books"] == {
        "fanduel": "present",
        "betmgm_or_betrivers": "present",
    }
    assert result["book_coverage"]["optional_books"]["draftkings"] == "missing_optional"
    assert "draftkings_missing_optional" in result["risk_flags"]
    assert all("draftkings" not in reason.lower() for reason in result["blocking_reasons"])


def test_not_ready_when_fresh_heartbeat_uses_previous_slate():
    result = audit_migration_risk(
        provider_run_rows=[
            _run(
                slate_date="2026-05-10",
                completed_at=None,
                created_at="2026-05-11T16:42:49+00:00",
            )
        ],
        coverage_audit_rows=[_coverage(slate_date="2026-05-10")],
        heartbeat_rows=[
            _heartbeat(
                slate_date="2026-05-10",
                observed_at="2026-05-11T16:48:00+00:00",
                last_message_at="2026-05-11T16:48:00+00:00",
            )
        ],
        artifact_metadata={
            "current_slate_date": "2026-05-11",
            "today_json_updated_at": "2026-05-11T16:12:15+00:00",
            "notifications_last_sent_at": "2026-05-11T16:10:49+00:00",
        },
        now="2026-05-11T16:49:00+00:00",
    )

    assert result["status"] == "not_ready"
    assert "stale_slate:latest_provider_run" in result["risk_flags"]
    assert "stale_slate:latest_heartbeat" in result["risk_flags"]
    assert "stale_slate:coverage_audit" in result["risk_flags"]
    assert result["slate_alignment"] == {
        "current_slate_date": "2026-05-11",
        "latest_provider_run_slate_date": "2026-05-10",
        "latest_heartbeat_slate_date": "2026-05-10",
        "latest_coverage_audit_slate_date": "2026-05-10",
        "current_slate_coverage_rows": 0,
    }


def test_proceed_with_caution_for_line_conflicts_and_stale_app_artifacts():
    result = audit_migration_risk(
        provider_run_rows=[_run()],
        coverage_audit_rows=[_coverage(line_conflict_count=2)],
        heartbeat_rows=[_heartbeat()],
        artifact_metadata={
            "today_json_updated_at": "2026-05-07T15:00:00+00:00",
            "notifications_last_sent_at": "2026-05-07T15:05:00+00:00",
        },
        now=NOW,
    )

    assert result["status"] == "proceed_with_caution"
    assert "line_conflicts_present" in result["risk_flags"]
    assert "stale_today_artifact" in result["risk_flags"]
    assert "stale_notification_path" in result["risk_flags"]
    assert result["blocking_reasons"] == []


def test_main_reads_json_files_and_prints_sorted_json(tmp_path, capsys):
    runs_path = tmp_path / "provider_runs.json"
    audits_path = tmp_path / "coverage_audits.json"
    heartbeats_path = tmp_path / "heartbeats.json"
    metadata_path = tmp_path / "artifact_metadata.json"
    runs_path.write_text(json.dumps([_run()]), encoding="utf-8")
    audits_path.write_text(json.dumps([_coverage()]), encoding="utf-8")
    heartbeats_path.write_text(json.dumps([_heartbeat()]), encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "today_json_updated_at": "2026-05-07T17:40:00+00:00",
                "notifications_last_sent_at": "2026-05-07T17:42:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    main(
        [
            "--provider-runs",
            str(runs_path),
            "--coverage-audits",
            str(audits_path),
            "--heartbeats",
            str(heartbeats_path),
            "--artifact-metadata",
            str(metadata_path),
            "--now",
            NOW,
        ]
    )

    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "ready_for_trial"
    assert output.startswith("{\n  ")
