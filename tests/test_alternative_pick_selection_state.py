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
    candidate = state.candidate_record(**values)
    candidate["source_artifact_path"] = "dashboard/data/processed/today.json"
    candidate["lock_source_artifact_path"] = "dashboard/data/processed/today.json"
    candidate["official_odds"] = -115
    candidate["official_book"] = "fanduel"
    return candidate


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
        "locked_odds": -115,
        "locked_book": "fanduel",
        "game_time": candidate["game_time"],
        "status_at_capture": "due_now",
        "observed_at": OBSERVED_AT,
        "locked_at": OBSERVED_AT,
        "should_lock_at": "2026-07-21T22:40:00Z",
        "minutes_until_start": 30.0,
        "source_artifact_path": "dashboard/data/processed/today.json",
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
    assert candidate["candidate_identity"] == _candidate(game_time="2026-07-21T23:10:00+00:00")["candidate_identity"]


def _raw_snapshot(**overrides):
    row = {
        "id": "snapshot-1",
        "provider": "propline",
        "provider_event_id": "pl-game-current",
        "normalized_player_name": "test pitcher",
        "side": "over",
        "line": 5.5,
        "bookmaker_key": "fanduel",
        "american_odds": -110,
        "observed_at": "2026-07-21T22:20:00Z",
        "game_time": GAME_TIME,
    }
    row.update(overrides)
    return row


def _market_evidence(**overrides):
    row = {
        "slate_date": "2026-07-21",
        "normalized_pitcher": "test pitcher",
        "side": "over",
        "provider": "propline",
        "k_line": 5.5,
        "game_time": GAME_TIME,
        "book_count": 2,
        "books_seen": ["fanduel", "draftkings"],
        "toward_pick_count": 2,
        "away_from_pick_count": 0,
        "reversal_book_count": 0,
        "volatile_book_count": 0,
        "metadata": {"freshness_status": "fresh"},
    }
    row.update(overrides)
    return row


def test_raw_observation_binder_requires_exact_line_event_provider_and_real_freshness():
    candidate = _candidate(provider_posture="propline")
    exact_rows = [
        _raw_snapshot(),
        _raw_snapshot(id="snapshot-2", observed_at="2026-07-21T22:30:00Z"),
    ]
    kwargs = {
        "candidate": candidate,
        "market_evidence_rows": [_market_evidence()],
        "first_current_at": "2026-07-21T22:15:00Z",
        "observed_at": OBSERVED_AT,
        "artifact_snapshot_ids": [],
        "artifact_provider_event_ids": {"propline": ["pl-game-current"]},
    }
    exact = state.bind_candidate_observations(snapshot_rows=exact_rows, **kwargs)
    assert exact["ready"] is True
    assert exact["observation_ids"] == ["snapshot-1", "snapshot-2"]

    invalid_cases = (
        (exact_rows, [_market_evidence(metadata={"freshness_status": "stale"})], "evidence_stale"),
        ([_raw_snapshot(line=6.5), _raw_snapshot(id="snapshot-2", line=6.5)], [_market_evidence()], "evidence_line_mismatch"),
        ([_raw_snapshot(provider_event_id="old-doubleheader"), _raw_snapshot(id="snapshot-2", provider_event_id="old-doubleheader")], [_market_evidence()], "evidence_event_mismatch"),
        ([_raw_snapshot(provider="boltodds"), _raw_snapshot(id="snapshot-2", provider="boltodds")], [_market_evidence()], "evidence_provider_unsupported"),
    )
    for raw_rows, evidence_rows, reason in invalid_cases:
        window = state.bind_candidate_observations(
            snapshot_rows=raw_rows,
            **{**kwargs, "market_evidence_rows": evidence_rows},
        )
        assert window["ready"] is False
        assert window["observation_count"] == 0
        assert reason in window["reason_codes"]


def test_raw_observation_binder_stays_pending_without_exact_artifact_event_binding():
    window = state.bind_candidate_observations(
        candidate=_candidate(),
        snapshot_rows=[_raw_snapshot(), _raw_snapshot(id="snapshot-2")],
        market_evidence_rows=[_market_evidence()],
        first_current_at="2026-07-21T22:15:00Z",
        observed_at=OBSERVED_AT,
        artifact_snapshot_ids=[],
        artifact_provider_event_ids={},
    )
    assert window["ready"] is False
    assert window["observation_count"] == 0
    assert "evidence_event_unbound" in window["reason_codes"]


def test_candidate_window_start_persists_only_for_the_same_candidate_identity():
    candidate = _candidate()
    existing = [{
        **candidate,
        "checkpoint": "provisional",
        "candidate_became_current_at": "2026-07-21T22:15:00Z",
    }]
    assert state.resolve_candidate_became_current_at(
        candidate=candidate, existing_rows=existing, observed_at=OBSERVED_AT,
    ) == "2026-07-21T22:15:00+00:00"
    assert state.resolve_candidate_became_current_at(
        candidate=_candidate(model_k_line=6.5), existing_rows=existing, observed_at=OBSERVED_AT,
    ) == "2026-07-21T22:40:00+00:00"


def test_candidate_lines_reject_bool_nan_and_infinity_instead_of_hashing_them():
    for malformed in (True, float("nan"), float("inf"), float("-inf")):
        candidate = _candidate(model_k_line=malformed)
        assert candidate["model_k_line"] is None
        assert state.build_provisional_row(
            candidate=candidate,
            evaluation=_evaluation(),
            evidence_window={},
            artifact=_artifact(),
            observed_at=OBSERVED_AT,
        ) is None


def test_market_evidence_aggregation_is_order_independent_and_reads_metadata_freshness():
    candidate = _candidate()
    window = {
        "ready": True,
        "bound_observations": [
            {"id": "tr-1", "provider": "therundown", "bookmaker_key": "fanduel", "american_odds": -110, "observed_at": "2026-07-21T22:20:00+00:00"},
            {"id": "tr-2", "provider": "therundown", "bookmaker_key": "fanduel", "american_odds": -115, "observed_at": "2026-07-21T22:30:00+00:00"},
            {"id": "pl-1", "provider": "propline", "bookmaker_key": "draftkings", "american_odds": -105, "observed_at": "2026-07-21T22:20:00+00:00"},
            {"id": "pl-2", "provider": "propline", "bookmaker_key": "draftkings", "american_odds": -110, "observed_at": "2026-07-21T22:30:00+00:00"},
            {"id": "pl-3", "provider": "propline", "bookmaker_key": "betrivers", "american_odds": -108, "observed_at": "2026-07-21T22:30:00+00:00"},
        ],
        "observation_ids": ["pl-1", "pl-2", "pl-3", "tr-1", "tr-2"],
        "first_observed_at": "2026-07-21T22:20:00+00:00",
        "last_observed_at": "2026-07-21T22:30:00+00:00",
        "first_current_at": "2026-07-21T22:15:00+00:00",
    }
    therundown = _market_evidence(
        provider="therundown",
        books_seen=["fanduel"],
        book_count=1,
        toward_pick_count=1,
    )
    propline = _market_evidence(
        provider="propline",
        books_seen=["draftkings", "betrivers"],
        book_count=2,
        toward_pick_count=1,
    )
    forward = state.aggregate_candidate_market_evidence(
        candidate=candidate, market_evidence_rows=[therundown, propline], evidence_window=window,
    )
    reverse = state.aggregate_candidate_market_evidence(
        candidate=candidate, market_evidence_rows=[propline, therundown], evidence_window=window,
    )
    assert forward == reverse
    assert forward["provider"] == "therundown_propline"
    assert forward["freshness_status"] == "fresh"
    assert forward["book_count"] == 3
    assert forward["toward_pick_count"] == 2
    assert forward["aggregation_reason_codes"] == []


def test_market_evidence_provider_conflict_or_missing_component_stays_pending():
    candidate = _candidate()
    window = {
        "ready": True,
        "bound_observations": [
            {"id": "tr-1", "provider": "therundown", "bookmaker_key": "fanduel", "american_odds": -110, "observed_at": "2026-07-21T22:20:00+00:00"},
            {"id": "tr-2", "provider": "therundown", "bookmaker_key": "fanduel", "american_odds": -115, "observed_at": "2026-07-21T22:30:00+00:00"},
            {"id": "pl-1", "provider": "propline", "bookmaker_key": "draftkings", "american_odds": -110, "observed_at": "2026-07-21T22:20:00+00:00"},
            {"id": "pl-2", "provider": "propline", "bookmaker_key": "draftkings", "american_odds": -105, "observed_at": "2026-07-21T22:30:00+00:00"},
        ],
        "observation_ids": ["pl-1", "pl-2", "tr-1", "tr-2"],
        "first_observed_at": "2026-07-21T22:20:00+00:00",
        "last_observed_at": "2026-07-21T22:30:00+00:00",
        "first_current_at": "2026-07-21T22:15:00+00:00",
    }
    therundown = _market_evidence(provider="therundown", book_count=1, books_seen=["fanduel"], toward_pick_count=1)
    conflict = _market_evidence(provider="propline", book_count=1, books_seen=["draftkings"], toward_pick_count=0, away_from_pick_count=1)
    aggregate = state.aggregate_candidate_market_evidence(
        candidate=candidate, market_evidence_rows=[therundown, conflict], evidence_window=window,
    )
    assert aggregate["freshness_status"] == "pending"
    assert "provider_disagreement" in aggregate["aggregation_reason_codes"]

    incomplete = _market_evidence(provider="propline")
    incomplete.pop("volatile_book_count")
    aggregate = state.aggregate_candidate_market_evidence(
        candidate=candidate, market_evidence_rows=[therundown, incomplete], evidence_window=window,
    )
    assert aggregate["freshness_status"] == "pending"
    assert "provider_evidence_incomplete" in aggregate["aggregation_reason_codes"]


def test_combined_evidence_requires_exact_bound_rows_from_each_declared_provider():
    candidate = _candidate()
    window = {
        "ready": True,
        "bound_observations": [
            {"id": "pl-1", "provider": "propline", "bookmaker_key": "draftkings", "american_odds": -110, "observed_at": "2026-07-21T22:20:00+00:00"},
            {"id": "pl-2", "provider": "propline", "bookmaker_key": "draftkings", "american_odds": -115, "observed_at": "2026-07-21T22:30:00+00:00"},
        ],
        "observation_ids": ["pl-1", "pl-2"],
        "first_observed_at": "2026-07-21T22:20:00+00:00",
        "last_observed_at": "2026-07-21T22:30:00+00:00",
        "first_current_at": "2026-07-21T22:15:00+00:00",
    }
    aggregate = state.aggregate_candidate_market_evidence(
        candidate=candidate,
        market_evidence_rows=[
            _market_evidence(provider="therundown", book_count=0, books_seen=[], toward_pick_count=0),
            _market_evidence(provider="propline", book_count=1, books_seen=["draftkings"], toward_pick_count=1),
        ],
        evidence_window=window,
    )
    assert aggregate["freshness_status"] == "pending"
    assert "provider_observations_missing" in aggregate["aggregation_reason_codes"]


def test_market_evidence_counts_must_be_exact_nonnegative_integers_and_match_bound_raw_rows():
    candidate = _candidate(provider_posture="therundown")
    window = {
        "ready": True,
        "bound_observations": [
            {"id": "tr-1", "provider": "therundown", "bookmaker_key": "fanduel", "american_odds": -110, "observed_at": "2026-07-21T22:20:00+00:00"},
            {"id": "tr-2", "provider": "therundown", "bookmaker_key": "fanduel", "american_odds": -115, "observed_at": "2026-07-21T22:30:00+00:00"},
        ],
        "observation_ids": ["tr-1", "tr-2"],
        "first_observed_at": "2026-07-21T22:20:00+00:00",
        "last_observed_at": "2026-07-21T22:30:00+00:00",
        "first_current_at": "2026-07-21T22:15:00+00:00",
    }
    for malformed in (True, -1, 1.5, float("inf"), "not-a-count"):
        row = _market_evidence(
            provider="therundown", book_count=1, books_seen=["fanduel"], toward_pick_count=malformed,
        )
        aggregate = state.aggregate_candidate_market_evidence(
            candidate=candidate, market_evidence_rows=[row], evidence_window=window,
        )
        assert aggregate["freshness_status"] == "pending"
        assert "provider_evidence_incomplete" in aggregate["aggregation_reason_codes"]

    conflicting = _market_evidence(
        provider="therundown", book_count=1, books_seen=["fanduel"],
        toward_pick_count=0, away_from_pick_count=1,
    )
    aggregate = state.aggregate_candidate_market_evidence(
        candidate=candidate, market_evidence_rows=[conflicting], evidence_window=window,
    )
    assert aggregate["toward_pick_count"] == 1
    assert aggregate["away_from_pick_count"] == 0
    assert aggregate["freshness_status"] == "pending"
    assert "provider_evidence_conflict" in aggregate["aggregation_reason_codes"]


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


def test_forged_or_old_identities_are_rejected_before_evidence_provisional_or_freeze():
    candidate = _candidate()
    forged = {**candidate, "game_identity": "f" * 64, "candidate_identity": "e" * 64}
    window = state.associate_candidate_observations(
        candidate=forged, snapshot_rows=_snapshots(candidate),
        first_current_at="2026-07-21T22:15:00Z", observed_at=OBSERVED_AT,
    )
    assert window["ready"] is False
    assert "candidate_identity_invalid" in window["reason_codes"]
    assert state.build_provisional_row(
        candidate=forged, evaluation=_evaluation(), evidence_window=window,
        artifact=_artifact(), observed_at=OBSERVED_AT,
    ) is None
    provisional = state.build_provisional_row(
        candidate=candidate, evaluation=_evaluation(),
        evidence_window=state.associate_candidate_observations(candidate=candidate, snapshot_rows=_snapshots(candidate), first_current_at="2026-07-21T22:15:00Z", observed_at=OBSERVED_AT),
        artifact=_artifact(), observed_at=OBSERVED_AT,
    )
    assert state.build_frozen_row(
        provisional_row={**provisional, "candidate_identity": "e" * 64},
        lock_row=_lock(candidate), observed_at=OBSERVED_AT,
    ) is None


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
    assert row["lock_source_artifact_path"] is None
    assert row["candidate_became_current_at"] == "2026-07-21T22:15:00+00:00"
    assert state.build_provisional_row(candidate={**candidate, "frozen_exists": True}, evaluation=_evaluation(), evidence_window={}, artifact=artifact, observed_at=OBSERVED_AT) is None
    assert state.build_provisional_row(candidate=candidate, evaluation=_evaluation(), evidence_window={}, artifact=artifact, observed_at=GAME_TIME) is None
    assert state.build_provisional_row(candidate=candidate, evaluation=_evaluation(), evidence_window={}, artifact={**artifact, "payload_sha256": CANONICAL_SHA}, observed_at=OBSERVED_AT) is None
    assert state.build_provisional_row(candidate=candidate, evaluation=_evaluation(), evidence_window={}, artifact={**artifact, "path": "dashboard/data/processed/2026-07-21.json"}, observed_at=OBSERVED_AT) is None
    assert state.build_provisional_row(candidate=candidate, evaluation=_evaluation(), evidence_window={}, artifact={**artifact, "path": None}, observed_at=OBSERVED_AT) is None


def test_provisional_stores_lane_selector_identity_separately_from_manifest_fingerprint():
    candidate, artifact = _candidate(), _artifact()
    consensus = state.build_provisional_row(
        candidate=candidate, evaluation=_evaluation(),
        evidence_window={}, artifact=artifact, observed_at=OBSERVED_AT,
    )
    expansion = state.build_provisional_row(
        candidate=candidate,
        evaluation={**_evaluation(), "lane": "reentry_expansion"},
        evidence_window={}, artifact=artifact, observed_at=OBSERVED_AT,
    )
    pending = state.build_provisional_row(
        candidate=candidate,
        evaluation={**_evaluation(), "lane": None, "selection_status": "pending"},
        evidence_window={}, artifact=artifact, observed_at=OBSERVED_AT,
    )
    assert consensus["selector_id"] == state.CONSENSUS_SELECTOR_ID
    assert expansion["selector_id"] == state.EXPANSION_SELECTOR_ID
    assert pending["selector_id"] is None
    assert consensus["selector_fingerprint"] == "c" * 64
    assert consensus["selector_id"] != consensus["selector_fingerprint"]


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
        ("source_artifact_path", "dashboard/data/processed/other.json"),
        ("locked_odds", -110),
        ("locked_book", "draftkings"),
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
    assert frozen["candidate_became_current_at"] == provisional["candidate_became_current_at"]
    assert state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate, status_at_capture="missed_lock"), observed_at=OBSERVED_AT)["lock_status"] == "missed_lock"
    assert state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate, locked_at="2026-07-21T22:35:00Z"), observed_at=OBSERVED_AT) is None
    assert state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate), observed_at=GAME_TIME) is None
    assert state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate, source_artifact_sha256="d" * 64), observed_at=OBSERVED_AT) is None
    assert state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate, observed_at="2026-07-21T22:39:00Z"), observed_at=OBSERVED_AT) is None
    assert state.build_frozen_row(provisional_row=provisional, lock_row=_lock(candidate, observed_at=None), observed_at=OBSERVED_AT) is None


def test_frozen_row_requires_parseable_nonnegative_lock_timing_and_exact_artifact_path():
    candidate, artifact = _candidate(), _artifact()
    provisional = state.build_provisional_row(
        candidate=candidate, evaluation=_evaluation(),
        evidence_window={}, artifact=artifact, observed_at=OBSERVED_AT,
    )
    for key, value in (
        ("should_lock_at", None), ("should_lock_at", "not-a-time"),
        ("minutes_until_start", None), ("minutes_until_start", "nope"),
        ("minutes_until_start", -0.1),
    ):
        assert state.build_frozen_row(
            provisional_row=provisional, lock_row=_lock(candidate, **{key: value}), observed_at=OBSERVED_AT,
        ) is None


def test_frozen_row_keeps_logical_artifact_path_and_links_the_exact_netlify_lock_source_path():
    candidate, artifact = _candidate(), _artifact()
    provisional = state.build_provisional_row(
        candidate=candidate, evaluation=_evaluation(), evidence_window={}, artifact=artifact, observed_at=OBSERVED_AT,
    )
    netlify_url = "https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact?key=today"
    frozen = state.build_frozen_row(
        provisional_row=provisional,
        lock_row=_lock(candidate, source_artifact_path=netlify_url),
        observed_at=OBSERVED_AT,
    )
    assert frozen["source_artifact_path"] == "dashboard/data/processed/today.json"
    assert frozen["lock_source_artifact_path"] == netlify_url
    assert state.build_frozen_row(
        provisional_row={**provisional, "lock_source_artifact_path": "https://wrong.example/today"},
        lock_row=_lock(candidate, source_artifact_path=netlify_url),
        observed_at=OBSERVED_AT,
    ) is None


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
