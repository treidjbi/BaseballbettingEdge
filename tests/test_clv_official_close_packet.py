import importlib
import json

import pytest


def _producer_module():
    try:
        return importlib.import_module(
            "analytics.diagnostics.clv_official_close_packet"
        )
    except ModuleNotFoundError:
        pytest.fail("official close packet producer is not implemented")


def _lock(**overrides):
    row = {
        "id": "lock-1",
        "slate_date": "2026-08-26",
        "pitcher": "Chris Sale",
        "normalized_pitcher": "chris sale",
        "side": "over",
        "locked_k_line": 5.5,
        "locked_odds": -110,
        "locked_book": "FanDuel",
        "locked_at": "2026-08-26T17:40:00+00:00",
        "game_time": "2026-08-26T18:00:00+00:00",
        "consumed_at": "2026-08-26T17:42:00+00:00",
    }
    row.update(overrides)
    return row


def _snapshot(**overrides):
    row = {
        "id": "snapshot-lock",
        "provider": "therundown",
        "provider_event_id": "event-1",
        "bookmaker_key": "fanduel",
        "bookmaker_title": "FanDuel",
        "player_name": "Chris Sale",
        "normalized_player_name": "chris sale",
        "side": "over",
        "line": 5.5,
        "american_odds": -110,
        "observed_at": "2026-08-26T17:35:00+00:00",
        "game_time": "2026-08-26T18:00:00Z",
    }
    row.update(overrides)
    return row


def test_exact_lock_provenance_builds_latest_fresh_official_close_row():
    producer = _producer_module()
    snapshots = [
        _snapshot(),
        _snapshot(
            id="snapshot-close-early",
            observed_at="2026-08-26T17:48:00+00:00",
            american_odds=-115,
        ),
        _snapshot(
            id="snapshot-close-latest",
            observed_at="2026-08-26T17:55:00+00:00",
            line=6.5,
            american_odds=105,
        ),
    ]

    result = producer.build_close_packet(
        [_lock()],
        snapshots,
        start_date="2026-08-26",
        end_date="2026-08-26",
    )

    assert result["manifest"]["eligible_close_rows"] == 1
    assert result["exclusions"] == []
    assert result["packet_rows"] == [
        {
            "american_odds": 105,
            "bookmaker": "FanDuel",
            "bookmaker_key": "fanduel",
            "event_id": "event-1",
            "freshness": "fresh",
            "game_time": "2026-08-26T18:00:00+00:00",
            "line": 6.5,
            "lock_observed_at": "2026-08-26T17:40:00+00:00",
            "normalized_pitcher": "chris sale",
            "observation_id": "snapshot-close-latest",
            "observation_type": "official_close",
            "observed_at": "2026-08-26T17:55:00+00:00",
            "official_lock_reference": "lock-1",
            "pitcher": "Chris Sale",
            "provider": "therundown",
            "side": "over",
            "slate_date": "2026-08-26",
        }
    ]


def test_close_must_be_strictly_after_lock_and_before_game_start():
    producer = _producer_module()
    snapshots = [
        _snapshot(),
        _snapshot(id="at-lock", observed_at="2026-08-26T17:40:00+00:00"),
        _snapshot(id="post-start", observed_at="2026-08-26T18:01:00+00:00"),
    ]

    result = producer.build_close_packet(
        [_lock()],
        snapshots,
        start_date="2026-08-26",
        end_date="2026-08-26",
    )

    assert result["packet_rows"] == []
    assert result["exclusions"][0]["reason"] == "missing_pregame_close_snapshot"


def test_ambiguous_lock_provider_fails_closed():
    producer = _producer_module()
    snapshots = [
        _snapshot(),
        _snapshot(id="snapshot-propline", provider="propline"),
        _snapshot(id="snapshot-close", observed_at="2026-08-26T17:55:00+00:00"),
    ]

    result = producer.build_close_packet(
        [_lock()],
        snapshots,
        start_date="2026-08-26",
        end_date="2026-08-26",
    )

    assert result["packet_rows"] == []
    assert result["exclusions"][0]["reason"] == "ambiguous_lock_provider_or_event"


def test_gate_c_official_line_source_resolves_ambiguous_lock_provider():
    producer = _producer_module()
    snapshots = [
        _snapshot(),
        _snapshot(id="snapshot-propline", provider="propline"),
        _snapshot(id="snapshot-close-trd", observed_at="2026-08-26T17:55:00+00:00"),
        _snapshot(
            id="snapshot-close-propline",
            provider="propline",
            observed_at="2026-08-26T17:55:00+00:00",
        ),
    ]
    official_rows = [
        {
            "slate_date": "2026-08-26",
            "normalized_pitcher": "chris sale",
            "side": "over",
            "official_line_source_provider": "therundown",
        }
    ]

    result = producer.build_close_packet(
        [_lock()],
        snapshots,
        official_rows=official_rows,
        start_date="2026-08-26",
        end_date="2026-08-26",
    )

    assert result["exclusions"] == []
    assert result["packet_rows"][0]["provider"] == "therundown"
    assert result["packet_rows"][0]["observation_id"] == "snapshot-close-trd"
    assert result["manifest"]["official_provider_resolved_locks"] == 1


def test_exact_gate_c_official_odds_source_is_a_safe_fallback_resolver():
    producer = _producer_module()
    snapshots = [
        _snapshot(),
        _snapshot(id="snapshot-propline", provider="propline"),
        _snapshot(id="snapshot-close-trd", observed_at="2026-08-26T17:55:00+00:00"),
    ]

    result = producer.build_close_packet(
        [_lock()],
        snapshots,
        official_rows=[
            {
                "slate_date": "2026-08-26",
                "normalized_pitcher": "chris sale",
                "side": "over",
                "official_odds_source": "therundown",
            }
        ],
        start_date="2026-08-26",
        end_date="2026-08-26",
    )

    assert result["exclusions"] == []
    assert result["packet_rows"][0]["provider"] == "therundown"


def test_stale_latest_close_is_excluded():
    producer = _producer_module()
    snapshots = [
        _snapshot(
            observed_at="2026-08-26T17:05:00+00:00",
        ),
        _snapshot(
            id="snapshot-close",
            observed_at="2026-08-26T17:25:00+00:00",
        ),
    ]
    lock = _lock(locked_at="2026-08-26T17:10:00+00:00")

    result = producer.build_close_packet(
        [lock],
        snapshots,
        start_date="2026-08-26",
        end_date="2026-08-26",
        max_close_age_minutes=20,
    )

    assert result["packet_rows"] == []
    assert result["exclusions"][0]["reason"] == "stale_close_snapshot"


def test_close_without_observation_id_is_excluded_before_packet_validation():
    producer = _producer_module()
    snapshots = [
        _snapshot(),
        _snapshot(
            id=None,
            observed_at="2026-08-26T17:55:00+00:00",
            american_odds=-115,
        ),
    ]

    result = producer.build_close_packet(
        [_lock()],
        snapshots,
        start_date="2026-08-26",
        end_date="2026-08-26",
    )

    assert result["packet_rows"] == []
    assert result["exclusions"][0]["reason"] == "missing_close_observation_id"


def test_retired_boltodds_cannot_supply_lock_provenance_by_default():
    producer = _producer_module()
    snapshots = [
        _snapshot(provider="boltodds"),
        _snapshot(
            id="snapshot-close",
            provider="boltodds",
            observed_at="2026-08-26T17:55:00+00:00",
        ),
    ]

    result = producer.build_close_packet(
        [_lock()],
        snapshots,
        start_date="2026-08-26",
        end_date="2026-08-26",
    )

    assert result["packet_rows"] == []
    assert result["exclusions"][0]["reason"] == "missing_lock_provenance_snapshot"
    assert result["manifest"]["allowed_providers"] == ["propline", "therundown"]


def test_cli_writes_packet_exclusions_and_manifest_without_database_writes(tmp_path):
    producer = _producer_module()
    validator = importlib.import_module(
        "analytics.diagnostics.clv_process_target_validation"
    )
    locks_path = tmp_path / "locks.json"
    snapshots_path = tmp_path / "snapshots.jsonl"
    packet_path = tmp_path / "official-close.jsonl"
    exclusions_path = tmp_path / "official-close-exclusions.jsonl"
    manifest_path = tmp_path / "official-close-manifest.json"
    locks_path.write_text(json.dumps([_lock()]), encoding="utf-8")
    snapshots_path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                _snapshot(),
                _snapshot(id="snapshot-close", observed_at="2026-08-26T17:55:00+00:00"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = producer.main(
        [
            "--locks-input",
            str(locks_path),
            "--snapshots-input",
            str(snapshots_path),
            "--start-date",
            "2026-08-26",
            "--end-date",
            "2026-08-26",
            "--packet-output",
            str(packet_path),
            "--exclusions-output",
            str(exclusions_path),
            "--manifest-output",
            str(manifest_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(packet_path.read_text(encoding="utf-8"))["observation_type"] == "official_close"
    assert validator.load_close_evidence_packet(packet_path)[0]["observation_id"] == "snapshot-close"
    assert exclusions_path.read_text(encoding="utf-8") == ""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["mode"] == "offline_dry_run"
    assert manifest["database_writes"] == 0
