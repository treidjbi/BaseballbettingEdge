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
            "is_opener": False, "starter_mismatch": False,
            "last_pitch_count": 95, "days_since_last_start": 5,
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
        snapshot_read_complete=True,
        snapshot_window_started_at="2026-07-22T08:10:00+00:00",
        snapshot_read_reason_codes=(),
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


def test_v2_incomplete_snapshot_read_still_records_with_pending_preclose(monkeypatch):
    captured = {}
    monkeypatch.setattr(recording, "resolve_candidate_bindings_v2", lambda **kwargs: {
        "ready": True,
    })
    monkeypatch.setattr(recording, "resolve_candidate_windows_v2", lambda **kwargs: {
        "ready": True,
        "candidate_became_current_at": "2026-07-22T19:55:00+00:00",
        "provider_window_started_at": {"therundown": "2026-07-22T19:55:00+00:00"},
    })

    def build_exact(**kwargs):
        captured["snapshot_contract"] = {
            key: kwargs[key]
            for key in (
                "snapshot_read_complete", "snapshot_window_started_at",
                "snapshot_read_reason_codes",
            )
        }
        return Mock(
            market_evidence={
                "freshness_status": "pending",
                "aggregation_reason_codes": ["snapshot_page_cap_reached"],
            },
            evidence_window={"reason_codes": ("snapshot_page_cap_reached",)},
            proof_fragment={
                "exact_preclose": {"reason_codes": ["snapshot_page_cap_reached"]},
            },
        )

    monkeypatch.setattr(recording, "build_exact_preclose_evidence_v2", build_exact)
    monkeypatch.setattr(
        recording,
        "evaluate_alternative_pick_v2",
        lambda **kwargs: Mock(
            eligible=True, selection_status="selected", lane="consensus_core",
            family_states={
                "preclose": Mock(
                    state="pending", reason_codes=("snapshot_page_cap_reached",),
                ),
            },
        ),
    )

    def build_proof(**kwargs):
        captured["proof_reason_codes"] = kwargs["exact_preclose"].proof_fragment[
            "exact_preclose"
        ]["reason_codes"]
        return Mock()

    monkeypatch.setattr(recording, "build_evaluation_proof_v2", build_proof)
    monkeypatch.setattr(
        recording,
        "build_provisional_row_v2",
        lambda **kwargs: {
            **kwargs["candidate"],
            "bundle_id": recording.BUNDLE_ID,
            "checkpoint": "provisional",
            "selection_status": "selected",
            "lane": "consensus_core",
            "observed_at": NOW.isoformat(),
            "source_artifact_byte_sha256": "b" * 64,
            "official_odds": -120,
            "official_book": "fanduel",
            "lock_source_artifact_path": None,
            "evaluation_proof": {
                "preclose": {"reason_codes": ["snapshot_page_cap_reached"]},
            },
        },
    )

    writer = Writer()
    result = _record(
        writer,
        snapshot_read_complete=False,
        snapshot_window_started_at="2026-07-22T19:50:00+00:00",
        snapshot_read_reason_codes=("snapshot_page_cap_reached",),
    )

    assert result["rows"] == 1
    assert captured["snapshot_contract"] == {
        "snapshot_read_complete": False,
        "snapshot_window_started_at": "2026-07-22T19:50:00+00:00",
        "snapshot_read_reason_codes": ("snapshot_page_cap_reached",),
    }
    assert captured["proof_reason_codes"] == ["snapshot_page_cap_reached"]


def test_v2_writer_uses_only_tracked_non_pass_current_artifact_candidates():
    payload = _payload()
    payload["pitchers"].append({**payload["pitchers"][0], "pitcher": "Untracked", "tracked_picks": []})
    payload["pitchers"].append({**payload["pitchers"][0], "pitcher": "Pass", "tracked_picks": [{
        **payload["pitchers"][0]["tracked_picks"][0], "pitcher": "Pass", "display_verdict": "PASS",
    }]})
    candidates = recording.extract_alternative_pick_candidates_v2(slate_date="2026-07-22", payload=payload)
    assert [item[0]["pitcher"] for item in candidates] == ["Tarik Skubal"]


def test_v2_evaluation_inputs_use_effective_pitcher_book_when_tracked_pick_omits_book():
    payload = _payload()
    payload["pitchers"][0]["tracked_picks"][0].pop("display_book")
    candidate, pitcher, tracked_pick = recording.extract_alternative_pick_candidates_v2(
        slate_date="2026-07-22",
        payload=payload,
    )[0]

    pitcher_input, _pick_input = recording._evaluation_inputs(
        pitcher=pitcher,
        tracked_pick=tracked_pick,
        candidate=candidate,
    )

    assert pitcher_input["best_over_book"] == "fanduel"
    assert candidate["official_book"] == "fanduel"
    assert candidate["official_odds"] == -120


def test_v2_evaluation_inputs_do_not_pair_unmatched_tracked_price_with_pitcher_book():
    payload = _payload()
    tracked_pick = payload["pitchers"][0]["tracked_picks"][0]
    tracked_pick.pop("display_book")
    tracked_pick["display_odds"] = -125
    candidate, pitcher, tracked_pick = recording.extract_alternative_pick_candidates_v2(
        slate_date="2026-07-22",
        payload=payload,
    )[0]

    pitcher_input, _pick_input = recording._evaluation_inputs(
        pitcher=pitcher,
        tracked_pick=tracked_pick,
        candidate=candidate,
    )

    assert pitcher_input["best_over_odds"] == -125
    assert pitcher_input["best_over_book"] is None
    assert candidate["official_odds"] == -125
    assert candidate["official_book"] == ""


def _pitcher_payload(*, pitcher, game_time, line_source_provider="therundown"):
    row = _payload(game_time=game_time)["pitchers"][0]
    row["pitcher"] = pitcher
    row["tracked_picks"][0]["pitcher"] = pitcher
    if line_source_provider is None:
        row.pop("line_source_provider", None)
        row.pop("source_current_market_line_ids", None)
    else:
        row["line_source_provider"] = line_source_provider
    return row


def test_v2_assessment_excludes_started_missing_provider_row_before_validating_future_candidate():
    payload = _payload()
    payload["pitchers"] = [
        _pitcher_payload(
            pitcher="Chris Sale", game_time="2026-07-22T20:00:00+00:00",
            line_source_provider=None,
        ),
        _pitcher_payload(
            pitcher="Shane Bieber", game_time="2026-07-22T23:00:00+00:00",
        ),
    ]

    assessment = recording.assess_alternative_pick_artifact_v2(
        slate_date="2026-07-22", payload=payload, observed_at=NOW,
        require_before_t30=False,
    )

    assert assessment["ok"] is True
    assert assessment["reason"] == "clean"
    assert [candidate[0]["pitcher"] for candidate in assessment["candidates"]] == ["Shane Bieber"]


def test_v2_assessment_keeps_future_missing_provider_row_as_global_artifact_failure():
    payload = _payload()
    payload["pitchers"] = [
        _pitcher_payload(
            pitcher="Shane Bieber", game_time="2026-07-22T23:00:00+00:00",
            line_source_provider=None,
        ),
    ]

    assessment = recording.assess_alternative_pick_artifact_v2(
        slate_date="2026-07-22", payload=payload, observed_at=NOW,
        require_before_t30=False,
    )

    assert assessment == {
        "ok": False,
        "reason": "invalid_source_posture",
        "candidates": [],
    }


def test_v2_assessment_and_runtime_never_return_or_write_started_valid_candidate(monkeypatch):
    payload = _payload(game_time="2026-07-22T20:00:00+00:00")

    assessment = recording.assess_alternative_pick_artifact_v2(
        slate_date="2026-07-22", payload=payload, observed_at=NOW,
        require_before_t30=False,
    )

    assert assessment["ok"] is True
    assert assessment["reason"] == "no_candidates"
    assert assessment["candidates"] == []
    _stub_pipeline(monkeypatch)
    writer = Writer()
    result = _record(writer, payload=payload)
    assert result == {"skipped": True, "reason": "no_candidates", "rows": 0}
    assert not writer.select_calls and not writer.upserts and not writer.inserts


def test_v2_assessment_keeps_candidate_at_t30_before_game_for_runtime_freeze():
    assessment = recording.assess_alternative_pick_artifact_v2(
        slate_date="2026-07-22", payload=_payload(game_time="2026-07-22T20:40:00+00:00"),
        observed_at=NOW, require_before_t30=False,
    )

    assert assessment["ok"] is True
    assert assessment["reason"] == "clean"
    assert len(assessment["candidates"]) == 1
    assert assessment["candidate_t30"][assessment["candidates"][0][0]["candidate_identity"]] == NOW


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


def test_v2_current_lock_at_t30_still_freezes_instead_of_becoming_too_late(monkeypatch):
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
    result = _record(writer, payload=_payload(game_time="2026-07-22T20:40:00+00:00"))
    assert result["frozen_rows"] == 1
    assert len(writer.inserts) == 1


def test_v2_current_lock_freezes_when_shadow_timing_contains_optional_webhook_error(
    monkeypatch,
):
    _stub_pipeline(monkeypatch, status="selected", lane="consensus_core")
    lock = {
        "dedupe_key": "2026-07-22:tarik skubal:over",
        "slate_date": "2026-07-22",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "locked_at": NOW.isoformat(),
        "observed_at": NOW.isoformat(),
        "status_at_capture": "due_now",
    }
    shadow_pipeline_timing = {
        "skipped": False,
        "pipeline_runs": 1,
        "pick_lock_observations": 1,
        "pipeline_run_row": {
            "metadata": {
                "propline_webhooks": {
                    "skipped": True,
                    "reason": "webhook_processing_failed",
                    "error": "Supabase REST returned 500",
                },
            },
        },
    }
    writer = Writer({"operational_pick_locks": [lock]})
    monkeypatch.setattr(recording, "build_frozen_row", lambda **kwargs: {
        **kwargs["provisional_row"], "checkpoint": "frozen_pregame",
    })

    result = _record(
        writer,
        payload=_payload(game_time="2026-07-22T20:40:00+00:00"),
        shadow_pipeline_timing=shadow_pipeline_timing,
    )

    assert result["frozen_rows"] == 1
    assert len(writer.inserts) == 1


def test_v2_continues_when_only_market_compaction_failed(monkeypatch):
    _stub_pipeline(monkeypatch, status="selected", lane="consensus_core")
    writer = Writer()

    result = _record(
        writer,
        market_line_build={
            "skipped": False,
            "compact": {
                "skipped": True,
                "reason": "build_failed",
                "error": "snapshot query reached its fail-closed page ceiling",
            },
        },
    )

    assert result["skipped"] is False
    assert result["provisional_rows"] == 1
    assert result["rows"] == 1


@pytest.mark.parametrize(
    "prerequisite,summary",
    [
        ("operational_pick_locks", {"skipped": True, "reason": "write_failed"}),
        ("market_line_build", {"skipped": True, "reason": "build_failed"}),
        (
            "market_line_build",
            {"skipped": False, "current": {"reason": "build_failed"}},
        ),
        ("shadow_pipeline_timing", {"skipped": True, "error": "write failed"}),
        ("ready_to_bet_write", {"skipped": True, "reason": "write_failed"}),
    ],
)
def test_v2_top_level_prerequisite_failures_still_fail_closed(prerequisite, summary):
    writer = Writer()

    result = _record(writer, **{prerequisite: summary})

    assert result == {"skipped": True, "reason": "prerequisite_failed", "rows": 0}
    assert writer.select_calls == []


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


@pytest.mark.parametrize(
    "game_time",
    ["2026-07-22T20:40:00+00:00", "2026-07-22T20:39:59+00:00"],
)
def test_v2_no_lock_at_or_after_t30_never_writes_provisional(monkeypatch, game_time):
    _stub_pipeline(monkeypatch)
    writer = Writer()
    result = _record(writer, payload=_payload(game_time=game_time))
    assert result["reason"] == "too_late"
    assert result["rows"] == 0
    assert not writer.upserts and not writer.inserts


@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda payload: payload.update(generated_at="2026-07-22T18:00:00+00:00"), "stale_artifact"),
        (lambda payload: payload.update(date="2026-07-21"), "wrong_phoenix_slate_date"),
        (
            lambda payload: payload["pitchers"][0].update(
                odds_source="boltodds", market_source_mode="boltodds"
            ),
            "invalid_source_posture",
        ),
    ],
)
def test_v2_runtime_rejects_stale_wrong_date_and_retired_source_before_reads(mutate, reason):
    payload = _payload()
    mutate(payload)
    writer = Writer()
    result = _record(writer, payload=payload)
    assert result == {"skipped": True, "reason": reason, "rows": 0}
    assert writer.select_calls == []


def test_v2_malformed_candidate_extraction_is_bounded_sidecar_failure(monkeypatch):
    monkeypatch.setattr(
        recording, "extract_alternative_pick_candidates_v2",
        Mock(side_effect=ValueError("malformed candidate")),
    )
    writer = Writer()
    result = _record(writer)
    assert result["skipped"] is True
    assert result["reason"] == "failed"
    assert result["rows"] == 0
    assert len(result["warning"]) <= 200
    assert writer.select_calls == []


def test_v2_early_line_id_preparation_exception_is_bounded_sidecar_failure(monkeypatch):
    monkeypatch.setattr(
        recording, "artifact_current_line_ids_v2",
        Mock(side_effect=TypeError("malformed source ids")),
    )
    writer = Writer()
    result = _record(writer)
    assert result["skipped"] is True
    assert result["reason"] == "failed"
    assert result["rows"] == 0
    assert writer.select_calls == []


def test_v2_early_preparation_timeout_is_bounded_sidecar_failure(monkeypatch):
    monkeypatch.setattr(
        recording, "extract_alternative_pick_candidates_v2",
        Mock(side_effect=TimeoutError("budget")),
    )
    result = _record(Writer())
    assert result["skipped"] is True
    assert result["reason"] == "timeout"
    assert result["rows"] == 0


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


def test_v2_recorder_filters_snapshot_page_to_candidate_before_exact_evaluation(
    monkeypatch,
):
    _stub_pipeline(monkeypatch)
    virtual_clock = {"seconds": 0.0}
    seen_snapshot_counts = []
    monkeypatch.setattr(
        recording.time,
        "monotonic",
        lambda: virtual_clock["seconds"],
    )

    def charge_for_snapshot_scan(**kwargs):
        row_count = len(kwargs["snapshot_rows"])
        seen_snapshot_counts.append(row_count)
        virtual_clock["seconds"] += row_count / 1_000
        return {"ready": True}

    def build_exact(**kwargs):
        charge_for_snapshot_scan(**kwargs)
        return Mock(market_evidence={"freshness_status": "pending"}, evidence_window={})

    monkeypatch.setattr(
        recording,
        "resolve_candidate_bindings_v2",
        charge_for_snapshot_scan,
    )
    monkeypatch.setattr(recording, "build_exact_preclose_evidence_v2", build_exact)

    snapshots = [
        {
            "id": f"00000000-0000-4000-8000-{index:012x}",
            "provider": "therundown",
            "slate_date": "2026-07-22",
            "provider_event_id": f"noise-{index}",
            "normalized_player_name": f"noise pitcher {index}",
            "market_key": "pitcher_strikeouts",
            "side": "over",
        }
        for index in range(4_999)
    ]
    snapshots.append({
        "id": "11111111-1111-4111-8111-111111111111",
        "provider": "therundown",
        "slate_date": "2026-07-22",
        "provider_event_id": "game-1",
        "normalized_player_name": "tarik skubal",
        "market_key": "pitcher_strikeouts",
        "side": "over",
    })

    writer = Writer()
    result = _record(
        writer,
        snapshot_rows=snapshots,
        snapshot_read_complete=False,
        snapshot_read_reason_codes=("snapshot_page_cap_reached",),
        budget_seconds=5.0,
    )

    assert result["rows"] == 1
    assert seen_snapshot_counts == [1, 1]
    assert len(writer.upserts) == 1
