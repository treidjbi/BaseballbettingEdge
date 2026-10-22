import json
from datetime import date
from io import StringIO
from pathlib import Path

import pytest

from scripts import build_season_retention_readiness as readiness
from scripts.build_retention_season_manifests import (
    build_manifests,
    load_query_counts,
    parse_manual_pin,
)


ROOT = Path(__file__).resolve().parent.parent
SQL_PATH = ROOT / "scripts" / "supabase_retention_season_counts.sql"


def _aggregate_counts(**overrides):
    row = {
        "slate_date": "2026-06-03",
        "accepted_bets": 1,
        "accepted_bets_complete": 1,
        "sent_notifications": 2,
        "sent_notifications_complete": 2,
        "consumed_locks": 1,
        "consumed_locks_complete": 1,
        "frozen_alt_v2_rows": 0,
        "frozen_alt_v2_rows_complete": 0,
    }
    row.update(overrides)
    return {
        "schema_version": 1,
        "generated_at": "2026-08-21T22:00:00+00:00",
        "scope": {
            "start_date": "2026-06-03",
            "end_date": "2026-06-03",
            "providers": ["boltodds"],
        },
        "dates": [row],
    }


def _gate_c_row(**overrides):
    row = {
        "slate_date": "2026-06-03",
        "is_tracked_pick": True,
        "result": "win",
        "price_clv_cents": 8,
        "closing_line": 4.5,
        "american_odds": -110,
        "official_odds_source": "boltodds+propline",
        "official_market_source_mode": "boltodds_propline",
        "official_line_source_provider": "boltodds",
    }
    row.update(overrides)
    return row


def test_retention_season_counts_sql_is_bounded_select_only_and_aggregate_only():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert "date '2026-05-07' as start_date" in sql
    assert "date '2026-06-16' as end_date" in sql
    assert "public.accepted_bets" in sql
    assert "public.notification_events" in sql
    assert "public.operational_pick_locks" in sql
    assert "public.alternative_pick_selection_state" in sql
    assert "retention_season_counts" in sql
    assert "count(*)" in sql
    for forbidden in (
        "insert ", "update ", "delete ", "truncate ", "alter ", "drop ",
        "vacuum ", "create ", "title", "body", "payload", "model_snapshot",
    ):
        assert forbidden not in sql


def test_load_query_counts_accepts_supabase_json_wrapper_and_json_string():
    counts = _aggregate_counts()
    wrapper = [{"retention_season_counts": json.dumps(counts)}]

    assert load_query_counts("-", stdin=StringIO(json.dumps(wrapper))) == counts


def test_load_query_counts_accepts_current_cli_rows_envelope():
    counts = _aggregate_counts()
    wrapper = {
        "boundary": "safe-boundary",
        "rows": [{"retention_season_counts": counts}],
        "warning": "untrusted database results",
    }

    assert load_query_counts("-", stdin=StringIO(json.dumps(wrapper))) == counts


def test_build_manifests_uses_existing_contracts_and_preserves_manual_incident_pin():
    season, pins = build_manifests(
        aggregate_counts=_aggregate_counts(),
        gate_c_rows=[_gate_c_row()],
        gate_c_jsonl_sha256="a" * 64,
        query_sql_sha256="b" * 64,
        gate_c_artifact="data/research/gate_c/pitcher_k_outcome_dataset.jsonl",
        season_evidence_artifact=(
            "data/research/retention/season-evidence-2026-05-07-2026-06-16.json"
        ),
        operator_incident_pins={
            "2026-06-03": [
                "docs/research/2026-08-21-boltodds-retention-closure-preflight.md"
            ]
        },
        model_review_pins={},
    )

    assert season["schema_version"] == 1
    assert season["generated_at"] == "2026-08-21T22:00:00+00:00"
    record = season["dates"][0]
    assert record["decision_linked"] is True
    assert record["evidence_counts"] == {
        "official_tracked_picks": 1,
        "accepted_bets": 1,
        "sent_notifications": 2,
        "consumed_locks": 1,
        "frozen_alt_v2_rows": 0,
        "operator_incidents": 1,
        "model_review_pins": 0,
    }
    assert record["required_evidence"] == {
        "results": True,
        "bet_timing": True,
        "checkpoint_market": True,
        "close_clv": True,
        "provider_metadata": True,
    }
    assert season["source_evidence"]["gate_c_jsonl_sha256"] == "a" * 64
    assert season["source_evidence"]["query_sql_sha256"] == "b" * 64
    assert season["source_evidence"]["retained_detail_sources"] == {
        "accepted_bets": "public.accepted_bets",
        "consumed_locks": "public.operational_pick_locks",
        "frozen_alt_v2_rows": "public.alternative_pick_selection_state",
        "sent_notifications": "public.notification_events",
    }
    assert season["retention_execution_closed"] is True
    assert season["deletion_approved"] is False
    assert season["production_authority"] == "none"

    assert pins["schema_version"] == 1
    assert pins["retention_execution_closed"] is True
    assert pins["deletion_approved"] is False
    assert pins["production_authority"] == "none"
    partition = pins["partitions"][0]
    assert partition["slate_date"] == "2026-06-03"
    assert partition["provider"] == "boltodds"
    assert partition["reconciled"] is True
    assert {(pin["reason"], pin["preserved_artifact"]) for pin in partition["pins"]} == {
        (
            "accepted_bet",
            "data/research/retention/season-evidence-2026-05-07-2026-06-16.json",
        ),
        (
            "consumed_lock",
            "data/research/retention/season-evidence-2026-05-07-2026-06-16.json",
        ),
        (
            "official_tracked_pick",
            "data/research/gate_c/pitcher_k_outcome_dataset.jsonl",
        ),
        (
            "operator_incident",
            "docs/research/2026-08-21-boltodds-retention-closure-preflight.md",
        ),
        (
            "sent_notification",
            "data/research/retention/season-evidence-2026-05-07-2026-06-16.json",
        ),
    }
    assert readiness._index_season_evidence(
        season, as_of=date(2026, 8, 21)
    )["2026-06-03"] == record
    assert readiness._index_pins(
        pins, as_of=date(2026, 8, 21)
    )[("2026-06-03", "boltodds")] == partition


def test_build_manifests_fails_closed_on_missing_official_source_metadata():
    season, pins = build_manifests(
        aggregate_counts=_aggregate_counts(
            accepted_bets=0,
            accepted_bets_complete=0,
            sent_notifications=0,
            sent_notifications_complete=0,
            consumed_locks=0,
            consumed_locks_complete=0,
        ),
        gate_c_rows=[_gate_c_row(official_odds_source=None)],
        gate_c_jsonl_sha256="a" * 64,
        query_sql_sha256="b" * 64,
        gate_c_artifact="data/research/gate_c/pitcher_k_outcome_dataset.jsonl",
        season_evidence_artifact="data/research/retention/season-evidence.json",
        operator_incident_pins={},
        model_review_pins={},
    )

    assert season["dates"][0]["required_evidence"]["provider_metadata"] is False
    assert pins["partitions"][0]["reconciled"] is False


def test_build_manifests_rejects_incomplete_aggregate_timing_evidence():
    with pytest.raises(ValueError, match="accepted_bets_complete"):
        build_manifests(
            aggregate_counts=_aggregate_counts(accepted_bets=2, accepted_bets_complete=1),
            gate_c_rows=[_gate_c_row()],
            gate_c_jsonl_sha256="a" * 64,
            query_sql_sha256="b" * 64,
            gate_c_artifact="data/research/gate_c/pitcher_k_outcome_dataset.jsonl",
            season_evidence_artifact="data/research/retention/season-evidence.json",
            operator_incident_pins={},
            model_review_pins={},
        )


def test_parse_manual_pin_requires_date_and_repository_relative_path():
    assert parse_manual_pin(
        "2026-06-03=docs/research/2026-08-21-boltodds-retention-closure-preflight.md"
    ) == (
        "2026-06-03",
        "docs/research/2026-08-21-boltodds-retention-closure-preflight.md",
    )

    with pytest.raises(ValueError, match="DATE=REPO_PATH"):
        parse_manual_pin("2026-06-03")
    with pytest.raises(ValueError, match="repository-relative"):
        parse_manual_pin("2026-06-03=C:/private/raw.json")
