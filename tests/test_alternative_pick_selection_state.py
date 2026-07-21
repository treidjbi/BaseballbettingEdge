import hashlib
import json

from market_infra import alternative_pick_selection_state as state
from market_infra.published_artifacts import canonical_payload_sha256


GAME_TIME = "2026-07-21T23:10:00Z"
OBSERVED_AT = "2026-07-21T22:40:00Z"
CANONICAL_SHA = "a" * 64
LOCK_SHA = "b" * 64


def _candidate(**overrides):
    values = {
        "slate_date": "2026-07-21",
        "pitcher": "Test Pitcher",
        "side": "over",
        "model_k_line": 5.5,
        "team": "ARI",
        "opp_team": "LAD",
        "game_time": GAME_TIME,
        "provider_posture": "therundown_propline",
    }
    values.update(overrides)
    return state.candidate_record(**values)


def _evaluation():
    return {
        "selector_fingerprint": "c" * 64,
        "family_states": {"base": {"state": "agree", "reason_codes": ["base_ok"]}},
        "family_count": 1,
        "lane": "consensus_core",
        "selection_status": "selected",
        "reason_codes": ("selected",),
        "normalized_inputs": {
            "official_verdict": "FIRE 1u",
            "odds": -115,
            "official_book": "fanduel",
        },
    }


def _artifact(payload=None, **overrides):
    payload = payload or {"date": "2026-07-21", "pitchers": [{"pitcher": "Test Pitcher"}]}
    values = {
        "path": "dashboard/data/processed/today.json",
        "payload": payload,
        "payload_sha256": canonical_payload_sha256(payload),
        "byte_sha256": LOCK_SHA,
        "generated_at": "2026-07-21T22:35:00Z",
    }
    values.update(overrides)
    return values


def _snapshots(candidate, **overrides):
    rows = [
        {"id": "therundown-1", "provider": "therundown", "candidate_identity": candidate["candidate_identity"], "observed_at": "2026-07-21T22:20:00Z", "freshness_status": "fresh"},
        {"id": "propline-2", "provider": "propline", "candidate_identity": candidate["candidate_identity"], "observed_at": "2026-07-21T22:30:00Z", "freshness_status": "fresh"},
    ]
    if overrides:
        rows[0].update(overrides)
    return rows


def _lock(candidate, **overrides):
    values = {
        "dedupe_key": "2026-07-21:test pitcher:over",
        "slate_date": candidate["slate_date"],
        "normalized_pitcher": candidate["normalized_pitcher"],
        "side": candidate["side"],
        "locked_k_line": candidate["model_k_line"],
        "game_time": candidate["game_time"],
        "status_at_capture": "due_now",
        "locked_at": OBSERVED_AT,
        "should_lock_at": "2026-07-21T22:40:00Z",
        "minutes_until_start": 30.0,
        "source_artifact_sha256": LOCK_SHA,
        "metadata": {"team": candidate["team"], "opp_team": candidate["opp_team"]},
    }
    values.update(overrides)
    return values


def test_candidate_identity_is_deterministic_and_includes_game_pitcher_side_line_and_provider_posture():
    candidate = _candidate()
    assert candidate["game_identity"] == state.game_identity(
        slate_date="2026-07-21", team="ARI", opp_team="LAD", game_time=GAME_TIME
    )
    assert candidate["candidate_identity"] == state.candidate_identity(
        slate_date="2026-07-21", pitcher="Test Pitcher", side="over", model_k_line=5.5,
        team="ARI", opp_team="LAD", game_time=GAME_TIME, provider_posture="therundown_propline",
    )
    assert candidate["candidate_identity"] != _candidate(side="under")["candidate_identity"]
    assert candidate["candidate_identity"] != _candidate(model_k_line=6.5)["candidate_identity"]
    assert candidate["candidate_identity"] != _candidate(provider_posture="therundown")["candidate_identity"]


def test_candidate_observations_start_at_the_current_identity_and_require_two_supported_snapshots():
    candidate = _candidate()
    window = state.associate_candidate_observations(
        candidate=candidate,
        snapshot_rows=_snapshots(candidate),
        first_current_at="2026-07-21T22:15:00Z",
        observed_at=OBSERVED_AT,
    )
    assert window["observation_ids"] == ["propline-2", "therundown-1"]
    assert window["observation_count"] == 2
    assert window["first_observed_at"] == "2026-07-21T22:20:00+00:00"
    assert window["last_observed_at"] == "2026-07-21T22:30:00+00:00"
    assert window["ready"] is True


def test_identity_change_resets_old_snapshot_membership_and_invalid_evidence_stays_pending():
    old_candidate, current = _candidate(model_k_line=4.5), _candidate()
    stale = _snapshots(current, freshness_status="stale")
    mixed = [
        {**_snapshots(old_candidate)[0], "candidate_identity": old_candidate["candidate_identity"]},
        *stale,
    ]
    window = state.associate_candidate_observations(
        candidate=current, snapshot_rows=mixed,
        first_current_at="2026-07-21T22:15:00Z", observed_at=OBSERVED_AT,
    )
    assert window["observation_count"] == 0
    assert window["ready"] is False
    assert "evidence_stale" in window["reason_codes"]
    assert "evidence_candidate_mismatch" in window["reason_codes"]
    unknown = state.associate_candidate_observations(
        candidate=current, snapshot_rows=_snapshots(current, provider="boltodds"),
        first_current_at="2026-07-21T22:15:00Z", observed_at=OBSERVED_AT,
    )
    assert unknown["ready"] is False
    assert "evidence_provider_unsupported" in unknown["reason_codes"]


def test_provisional_row_uses_canonical_hash_and_stops_after_freeze_or_game_start():
    candidate = _candidate()
    artifact = _artifact()
    row = state.build_provisional_row(
        candidate=candidate, evaluation=_evaluation(),
        evidence_window=state.associate_candidate_observations(candidate=candidate, snapshot_rows=_snapshots(candidate), first_current_at="2026-07-21T22:15:00Z", observed_at=OBSERVED_AT),
        artifact=artifact, observed_at=OBSERVED_AT,
    )
    assert row["checkpoint"] == "provisional"
    assert row["source_artifact_sha256"] == canonical_payload_sha256(artifact["payload"])
    assert row["lock_artifact_sha256"] is None
    assert state.build_provisional_row(candidate={**candidate, "frozen_exists": True}, evaluation=_evaluation(), evidence_window={}, artifact=artifact, observed_at=OBSERVED_AT) is None
    assert state.build_provisional_row(candidate=candidate, evaluation=_evaluation(), evidence_window={}, artifact=artifact, observed_at=GAME_TIME) is None
    assert state.build_provisional_row(candidate=candidate, evaluation=_evaluation(), evidence_window={}, artifact={**artifact, "payload_sha256": CANONICAL_SHA}, observed_at=OBSERVED_AT) is None


def test_lock_validation_checks_lookup_key_but_uses_full_candidate_identity_and_exact_byte_hash():
    candidate = _candidate()
    lock = _lock(candidate)
    assert state.lock_matches_candidate(lock, candidate, LOCK_SHA)
    for key, value in (
        ("dedupe_key", "2026-07-21:other:over"),
        ("slate_date", "2026-07-20"),
        ("side", "under"),
        ("locked_k_line", 6.5),
        ("game_time", "2026-07-21T23:11:00Z"),
        ("source_artifact_sha256", CANONICAL_SHA),
        ("metadata", {"team": "LAD", "opp_team": "ARI"}),
    ):
        assert not state.lock_matches_candidate({**lock, key: value}, candidate, LOCK_SHA)


def test_frozen_row_requires_current_cycle_due_or_missed_lock_and_never_reconstructs_after_start():
    candidate, artifact = _candidate(), _artifact()
    provisional = state.build_provisional_row(
        candidate=candidate, evaluation=_evaluation(),
        evidence_window=state.associate_candidate_observations(candidate=candidate, snapshot_rows=_snapshots(candidate), first_current_at="2026-07-21T22:15:00Z", observed_at=OBSERVED_AT),
        artifact=artifact, observed_at=OBSERVED_AT,
    )
    frozen = state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate), observed_at=OBSERVED_AT)
    assert frozen["checkpoint"] == "frozen_pregame"
    assert frozen["frozen_at"] == OBSERVED_AT.replace("Z", "+00:00")
    assert frozen["lock_artifact_sha256"] == LOCK_SHA
    assert frozen["source_artifact_sha256"] == provisional["source_artifact_sha256"]
    assert state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate, status_at_capture="missed_lock"), observed_at=OBSERVED_AT)["lock_status"] == "missed_lock"
    assert state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate, locked_at="2026-07-21T22:35:00Z"), observed_at=OBSERVED_AT) is None
    assert state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate), observed_at=GAME_TIME) is None
    assert state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate, source_artifact_sha256="d" * 64), observed_at=OBSERVED_AT) is None


def test_frozen_row_cannot_reconstruct_an_older_provisional_on_a_later_same_hash_cycle():
    candidate, artifact = _candidate(), _artifact()
    provisional = state.build_provisional_row(
        candidate=candidate, evaluation=_evaluation(),
        evidence_window=state.associate_candidate_observations(candidate=candidate, snapshot_rows=_snapshots(candidate), first_current_at="2026-07-21T22:15:00Z", observed_at=OBSERVED_AT),
        artifact=artifact, observed_at=OBSERVED_AT,
    )
    later = "2026-07-21T22:45:00Z"
    assert state.frozen_link_reason(
        provisional_row=provisional, lock_row=_lock(candidate, locked_at=later), observed_at=later,
    ) == "missed_freeze"
    assert state.build_frozen_row(
        provisional_row=provisional, lock_row=_lock(candidate, locked_at=later), observed_at=later,
    ) is None


def test_golden_payload_keeps_canonical_and_exact_byte_hash_domains_separate_through_freeze():
    payload_one = {"date": "2026-07-21", "pitchers": [{"team": "ARI", "pitcher": "Test Pitcher"}]}
    payload_two = {"pitchers": [{"pitcher": "Test Pitcher", "team": "ARI"}], "date": "2026-07-21"}
    assert canonical_payload_sha256(payload_one) == canonical_payload_sha256(payload_two)
    exact_bytes = json.dumps(payload_one, indent=2).encode("utf-8")
    exact_sha = hashlib.sha256(exact_bytes).hexdigest()
    candidate = _candidate()
    provisional = state.build_provisional_row(
        candidate=candidate, evaluation=_evaluation(),
        evidence_window=state.associate_candidate_observations(candidate=candidate, snapshot_rows=_snapshots(candidate), first_current_at="2026-07-21T22:15:00Z", observed_at=OBSERVED_AT),
        artifact=_artifact(payload_one, byte_sha256=exact_sha), observed_at=OBSERVED_AT,
    )
    frozen = state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate, source_artifact_sha256=exact_sha), observed_at=OBSERVED_AT)
    assert frozen["source_artifact_sha256"] == canonical_payload_sha256(payload_two)
    assert frozen["lock_artifact_sha256"] == exact_sha


def test_unique_columns_bound_one_provisional_and_one_frozen_row_and_frozen_conflicts_are_insert_ignore():
    assert state.UNIQUE_COLUMNS == ("slate_date", "game_identity", "normalized_pitcher", "side", "bundle_id", "checkpoint")
    assert state.frozen_insert_on_conflict() == ",".join(state.UNIQUE_COLUMNS)
