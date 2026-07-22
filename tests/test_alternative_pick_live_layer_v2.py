from __future__ import annotations

import inspect
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from market_infra import alternative_pick_recording_v2 as recording


NOW = datetime(2026, 7, 22, 20, 10, tzinfo=timezone.utc)


def _payload(*, verdict="LEAN", game_time="2026-07-22T23:00:00+00:00"):
    return {
        "date": "2026-07-22",
        "generated_at": "2026-07-22T20:05:00+00:00",
        "pitchers": [{
            "pitcher": "Tarik Skubal", "team": "DET", "opp_team": "PIT",
            "game_time": game_time, "k_line": 6.5,
            "odds_source": "therundown", "market_source_mode": "therundown",
            "line_source_provider": "therundown", "source_current_market_line_ids": [101],
            "best_over_odds": -120, "best_over_book": "fanduel",
            "ev_over": {"verdict": "FIRE 1u", "adj_ev": 0.09, "edge": 0.05},
            "tracked_picks": [{
                "pitcher": "Tarik Skubal", "side": "over",
                "display_verdict": verdict, "display_k_line": 6.5,
                "display_odds": -120, "display_book": "fanduel",
                "display_adj_ev": 0.09, "game_time": game_time,
            }],
        }],
    }


class Writer:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.select_calls = []
        self.upserts = []
        self.inserts = []

    def select_rows(self, table, params, **kwargs):
        self.select_calls.append((table, params, kwargs))
        return list(self.rows.get(table, []))

    def upsert_rows(self, table, rows, on_conflict, **kwargs):
        self.upserts.append((table, rows, on_conflict, kwargs))
        return rows

    def insert_ignore_rows(self, table, rows, on_conflict, **kwargs):
        self.inserts.append((table, rows, on_conflict, kwargs))
        return rows


def _record(writer, payload=None, **overrides):
    kwargs = dict(
        writer=writer, slate_date="2026-07-22", payload=payload or _payload(),
        snapshot_rows=[], provider_heartbeats=[], observed_at=NOW,
        artifact_source="https://example/get-artifact?type=today",
        source_payload_sha256="a" * 64, source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
        shadow_pipeline_timing={"skipped": True, "reason": "disabled"},
        ready_to_bet_write={"skipped": True, "reason": "disabled"},
    )
    kwargs.update(overrides)
    return recording.record_alternative_pick_selection_v2(**kwargs)


def _stub_pipeline(monkeypatch, *, status="selected", lane="consensus_core"):
    monkeypatch.setattr(recording, "resolve_candidate_bindings_v2", lambda **kwargs: {"ready": True})
    monkeypatch.setattr(recording, "resolve_candidate_windows_v2", lambda **kwargs: {
        "ready": True, "candidate_became_current_at": NOW.isoformat(),
        "provider_window_started_at": {"therundown": NOW.isoformat()},
    })
    exact = Mock(market_evidence={"freshness_status": "pending"}, evidence_window={})
    monkeypatch.setattr(recording, "build_exact_preclose_evidence_v2", lambda **kwargs: exact)
    evaluation = Mock(eligible=True, selection_status=status, lane=lane)
    monkeypatch.setattr(recording, "evaluate_alternative_pick_v2", lambda **kwargs: evaluation)
    monkeypatch.setattr(recording, "build_evaluation_proof_v2", lambda **kwargs: Mock())

    def row(**kwargs):
        candidate = kwargs["candidate"]
        return {
            **candidate, "bundle_id": recording.BUNDLE_ID, "checkpoint": "provisional",
            "selection_status": status, "lane": lane, "observed_at": NOW.isoformat(),
            "source_artifact_byte_sha256": "b" * 64, "official_odds": -120,
            "official_book": "fanduel", "lock_source_artifact_path": None,
            "evaluation_proof": {"decision": {"selection_status": status}},
        }

    monkeypatch.setattr(recording, "build_provisional_row_v2", row)


def test_v2_writer_has_no_broad_market_evidence_or_persisted_display_dependency():
    parameters = inspect.signature(recording.record_alternative_pick_selection_v2).parameters
    assert "market_pick_evidence_rows" not in parameters
    assert "live_market_display_rows" not in parameters


def test_v2_writer_batches_existing_state_locks_and_current_lines_once_each(monkeypatch):
    _stub_pipeline(monkeypatch)
    writer = Writer()
    _record(writer)
    tables = [call[0] for call in writer.select_calls]
    assert tables.count("alternative_pick_selection_state") == 1
    assert tables.count("operational_pick_locks") == 1
    assert tables.count("current_market_lines") == 1


def test_v2_writer_uses_only_tracked_non_pass_current_artifact_candidates():
    payload = _payload()
    payload["pitchers"].append({**payload["pitchers"][0], "pitcher": "Untracked", "tracked_picks": []})
    payload["pitchers"].append({**payload["pitchers"][0], "pitcher": "Pass", "tracked_picks": [{
        **payload["pitchers"][0]["tracked_picks"][0], "pitcher": "Pass", "display_verdict": "PASS",
    }]})
    candidates = recording.extract_alternative_pick_candidates_v2(slate_date="2026-07-22", payload=payload)
    assert [item[0]["pitcher"] for item in candidates] == ["Tarik Skubal"]


def test_v2_writer_reuses_persisted_full_proof_window_without_hash_only_reset():
    prior = {
        "candidate_identity": "candidate",
        "candidate_became_current_at": "2026-07-22T19:30:00+00:00",
        "evaluation_proof": {"bindings": {
            "therundown": {
                "role": "official", "binding_key": "a" * 64,
                "window_started_at": "2026-07-22T19:30:00+00:00",
            },
            "propline": {
                "role": "sidecar", "binding_key": "b" * 64,
                "window_started_at": "2026-07-22T19:35:00+00:00",
            },
        }},
    }
    adapted = recording._window_state_row(prior)
    exact = adapted["evaluation_proof"]["exact_preclose"]
    assert exact["official_binding_key"] == "a" * 64
    assert exact["sidecar_binding_keys"] == {"propline": "b" * 64}
    assert exact["provider_window_started_at"]["therundown"] == "2026-07-22T19:30:00+00:00"


def test_v2_selected_lane_with_pending_preclose_persists_selected(monkeypatch):
    _stub_pipeline(monkeypatch, status="selected", lane="consensus_core")
    writer = Writer()
    result = _record(writer)
    assert result["provisional_rows"] == 1
    assert writer.upserts[0][1][0]["selection_status"] == "selected"


def test_v2_selected_lane_with_pending_preclose_freezes_selected_at_exact_lock(monkeypatch):
    _stub_pipeline(monkeypatch, status="selected", lane="consensus_core")
    lock = {
        "dedupe_key": "2026-07-22:tarik skubal:over", "slate_date": "2026-07-22",
        "normalized_pitcher": "tarik skubal", "side": "over", "locked_at": NOW.isoformat(),
        "observed_at": NOW.isoformat(), "status_at_capture": "due_now",
    }
    writer = Writer({"operational_pick_locks": [lock]})
    monkeypatch.setattr(recording, "build_frozen_row", lambda **kwargs: {
        **kwargs["provisional_row"], "checkpoint": "frozen_pregame",
    })
    result = _record(writer)
    assert result["frozen_rows"] == 1
    assert writer.inserts[0][1][0]["selection_status"] == "selected"


def test_v2_relevant_pending_dependency_freezes_pending(monkeypatch):
    _stub_pipeline(monkeypatch, status="pending", lane=None)
    lock = {"dedupe_key": "2026-07-22:tarik skubal:over", "locked_at": NOW.isoformat(), "observed_at": NOW.isoformat()}
    writer = Writer({"operational_pick_locks": [lock]})
    monkeypatch.setattr(recording, "build_frozen_row", lambda **kwargs: {**kwargs["provisional_row"], "checkpoint": "frozen_pregame"})
    _record(writer)
    assert writer.inserts[0][1][0]["selection_status"] == "pending"


def test_v2_never_reconstructs_missed_or_existing_frozen_rows(monkeypatch):
    _stub_pipeline(monkeypatch)
    prior_lock = {"dedupe_key": "2026-07-22:tarik skubal:over", "locked_at": "2026-07-22T20:00:00+00:00", "observed_at": "2026-07-22T20:00:00+00:00"}
    writer = Writer({"operational_pick_locks": [prior_lock]})
    result = _record(writer)
    assert result["rows"] == 0
    assert not writer.upserts and not writer.inserts


def test_v2_proof_failure_is_sidecar_only_and_does_not_touch_other_tables(monkeypatch):
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(recording, "build_provisional_row_v2", lambda **kwargs: None)
    writer = Writer()
    result = _record(writer)
    assert result["rows"] == 0
    assert all(call[0] == "alternative_pick_selection_state" for call in writer.upserts + writer.inserts)


@pytest.mark.parametrize("failure", [TimeoutError(), RuntimeError("boom")])
def test_v2_timeout_and_exception_return_bounded_failure_summary(monkeypatch, failure):
    writer = Writer()
    writer.select_rows = Mock(side_effect=failure)
    result = _record(writer, budget_seconds=0.001)
    assert result["skipped"] is True
    assert result["reason"] in {"timeout", "failed"}
    assert len(result["warning"]) <= 200
