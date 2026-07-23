from __future__ import annotations

import inspect
from copy import deepcopy

import pytest

from market_infra import alternative_pick_preclose_v2 as preclose


OBSERVED_AT = "2026-07-22T20:10:00+00:00"
WINDOW_START = "2026-07-22T19:55:00+00:00"
GAME_TIME = "2026-07-22T23:00:00+00:00"
TR_OVER = "11111111-1111-4111-8111-111111111111"
TR_UNDER = "22222222-2222-4222-8222-222222222222"
TR_LATER = "33333333-3333-4333-8333-333333333333"
PL_OVER = "44444444-4444-4444-8444-444444444444"
PL_LATER = "55555555-5555-4555-8555-555555555555"
TR_REVERSAL = "77777777-7777-4777-8777-777777777777"


def _candidate(**overrides):
    row = {
        "slate_date": "2026-07-22",
        "pitcher": "Tarik Skubal",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "model_k_line": 6.5,
        "game_time": GAME_TIME,
        "candidate_identity": "candidate-v2",
        "provider_posture": "therundown_propline",
    }
    row.update(overrides)
    return row


def _pitcher(**overrides):
    row = {
        "line_source_provider": "therundown",
        "source_current_market_line_ids": [101, 202],
        "source_line_ids": [],
        "source_snapshot_ids": [],
    }
    row.update(overrides)
    return row


def _line(line_id, provider, event_id, over_id, *, line=6.5, game_time=GAME_TIME, **overrides):
    row = {
        "id": line_id,
        "slate_date": "2026-07-22",
        "provider": provider,
        "provider_event_id": event_id,
        "normalized_player_name": "tarik skubal",
        "market_key": "pitcher_strikeouts",
        "line": line,
        "game_time": game_time,
        "over_snapshot_id": over_id,
        "under_snapshot_id": TR_UNDER,
    }
    row.update(overrides)
    return row


def _snapshot(identifier, provider, event_id, odds, observed_at, *, book="fanduel", line=6.5, side="over", game_time=GAME_TIME, **overrides):
    row = {
        "id": identifier,
        "provider": provider,
        "provider_event_id": event_id,
        "slate_date": "2026-07-22",
        "normalized_player_name": "tarik skubal",
        "player_name": "Tarik Skubal",
        "market_key": "pitcher_strikeouts",
        "bookmaker_key": book,
        "side": side,
        "line": line,
        "american_odds": odds,
        "game_time": game_time,
        "observed_at": observed_at,
    }
    row.update(overrides)
    return row


def _base_rows():
    return [
        _snapshot(TR_OVER, "therundown", "tr-event", -105, "2026-07-22T20:00:00+00:00"),
        _snapshot(TR_LATER, "therundown", "tr-event", -120, "2026-07-22T20:06:00+00:00"),
        _snapshot(PL_OVER, "propline", "pl-event", -104, "2026-07-22T20:01:00+00:00", book="draftkings"),
        _snapshot(PL_LATER, "propline", "pl-event", -112, "2026-07-22T20:07:00+00:00", book="draftkings"),
    ]


def _bindings(rows=None, pitcher=None, candidate=None, current_lines=None):
    candidate = candidate or _candidate()
    rows = rows or _base_rows()
    current_lines = current_lines or {
        "101": _line(101, "therundown", "tr-event", TR_OVER),
        "202": _line(202, "propline", "pl-event", PL_OVER, under_snapshot_id="66666666-6666-4666-8666-666666666666"),
    }
    return preclose.resolve_candidate_bindings_v2(
        candidate=candidate,
        pitcher=pitcher or _pitcher(),
        current_lines_by_id=current_lines,
        snapshot_rows=rows,
    )


def _windows(bindings, *, existing=None, candidate=None):
    if existing is None:
        existing = {
            "candidate_identity": "candidate-v2",
            "candidate_became_current_at": WINDOW_START,
            "evaluation_proof": {
                "schema_version": "alternative_pick_preclose_v2",
                "exact_preclose": {
                    "official_binding_key": bindings.get("official_binding_key"),
                    "sidecar_binding_keys": bindings.get("sidecar_binding_keys", {}),
                    "provider_window_started_at": {
                        "therundown": WINDOW_START,
                        "propline": WINDOW_START,
                    },
                },
            },
        }
    return preclose.resolve_candidate_windows_v2(
        candidate=candidate or _candidate(), bindings=bindings,
        existing_state_row=existing, observed_at=OBSERVED_AT,
    )


def _build(rows=None, bindings=None, windows=None, **overrides):
    rows = _base_rows() if rows is None else rows
    bindings = bindings or _bindings(rows=rows)
    windows = windows or _windows(bindings)
    args = {
        "candidate": _candidate(), "bindings": bindings, "windows": windows,
        "snapshot_rows": rows, "provider_heartbeats": [], "observed_at": OBSERVED_AT,
        "source_artifact_path": "dashboard/data/processed/today.json",
        "source_artifact_byte_sha256": "b" * 64,
    }
    args.update(overrides)
    return preclose.build_exact_preclose_evidence_v2(**args)


def test_v2_binding_uses_explicit_line_source_provider_and_current_line_mapping():
    bindings = _bindings()
    assert preclose.artifact_current_line_ids_v2(_pitcher(source_snapshot_ids=[303, TR_OVER])) == ("101", "202", "303")
    assert bindings["ready"] is True
    assert bindings["official_provider"] == "therundown"
    assert bindings["official_binding"]["provider_event_id"] == "tr-event"
    assert bindings["official_binding"]["current_line_ids"] == ["101"]
    assert bindings["official_binding"]["seed_snapshot_ids"] == [TR_OVER]


def test_v2_does_not_infer_official_provider_from_combined_posture():
    bindings = _bindings(pitcher=_pitcher(line_source_provider=None))
    assert bindings["ready"] is False
    assert bindings["official_provider"] is None
    assert "official_provider_missing" in bindings["reason_codes"]


def test_v2_binding_rejects_unbound_time_skew_wrong_event_line_and_side():
    skewed = _line(101, "therundown", "tr-event", TR_OVER, game_time="2026-07-22T23:05:00+00:00")
    assert _bindings(current_lines={"101": skewed}, pitcher=_pitcher(source_current_market_line_ids=[101]))["ready"] is True
    for bad_row in (
        _snapshot(TR_OVER, "therundown", "wrong-event", -105, "2026-07-22T20:00:00+00:00"),
        _snapshot(TR_OVER, "therundown", "tr-event", -105, "2026-07-22T20:00:00+00:00", line=7.5),
        _snapshot(TR_OVER, "therundown", "tr-event", -105, "2026-07-22T20:00:00+00:00", side="under"),
    ):
        result = _bindings(rows=[bad_row], current_lines={"101": skewed}, pitcher=_pitcher(source_current_market_line_ids=[101]))
        assert result["ready"] is False


@pytest.mark.parametrize("seed_slate", [None, "2026-07-21"])
def test_v2_seed_binding_requires_present_exact_slate_date(seed_slate):
    seed = _base_rows()[0]
    if seed_slate is None:
        seed.pop("slate_date")
    else:
        seed["slate_date"] = seed_slate

    bindings = _bindings(
        rows=[seed],
        pitcher=_pitcher(source_current_market_line_ids=[101]),
        current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)},
    )

    assert bindings["ready"] is False
    assert bindings["official_binding"] is None
    assert "side_snapshot_mismatch" in bindings["reason_codes"]


def test_v2_later_rows_require_present_exact_slate_date():
    seed = _base_rows()[0]
    valid_later = _base_rows()[1]
    missing_slate = _snapshot(
        "ffffffff-ffff-4fff-8fff-ffffffffffff",
        "therundown", "tr-event", -122,
        "2026-07-22T20:06:00+00:00",
    )
    missing_slate.pop("slate_date")
    wrong_slate = _snapshot(
        "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        "therundown", "tr-event", -125,
        "2026-07-22T20:07:00+00:00",
    )
    wrong_slate["slate_date"] = "2026-07-21"
    rows = [seed, valid_later, missing_slate, wrong_slate]
    bindings = _bindings(
        rows=[seed],
        pitcher=_pitcher(source_current_market_line_ids=[101]),
        current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)},
    )

    result = _build(rows=rows, bindings=bindings, windows=_windows(bindings))

    assert result.market_evidence["freshness_status"] == "fresh"
    assert result.market_evidence["observation_ids"] == [
        f"therundown:{TR_OVER}", f"therundown:{TR_LATER}",
    ]


@pytest.mark.parametrize("conflict", [
    {"provider_event_id": "other-event"},
    {"provider_event_id": None, "slate_date": None, "side": None},
])
def test_v2_conflicting_duplicate_tokens_are_rejected_before_semantic_filtering(conflict):
    valid_seed = _base_rows()[0]
    conflicting_seed = {**valid_seed, **conflict}
    current_line = {"101": _line(101, "therundown", "tr-event", TR_OVER)}
    pitcher = _pitcher(source_current_market_line_ids=[101])

    bindings = _bindings(
        rows=[conflicting_seed, valid_seed], pitcher=pitcher,
        current_lines=current_line,
    )
    assert bindings["ready"] is False
    assert "duplicate_snapshot_conflict" in bindings["reason_codes"]

    clean_bindings = _bindings(
        rows=[valid_seed], pitcher=pitcher, current_lines=current_line,
    )
    result = _build(
        rows=_base_rows() + [conflicting_seed], bindings=clean_bindings,
        windows=_windows(clean_bindings),
    )
    assert result.market_evidence["freshness_status"] == "pending"
    assert "duplicate_snapshot_conflict" in result.market_evidence["aggregation_reason_codes"]


@pytest.mark.parametrize(("provider", "event_id"), [
    ("therundown", "unrelated-tr-event"),
    ("propline", "unrelated-pl-event"),
    ("boltodds", "retired-unrelated-event"),
])
def test_v2_unrelated_duplicate_collision_does_not_poison_clean_candidate(provider, event_id):
    identifier = "abababab-abab-4bab-8bab-abababababab"
    unrelated = _snapshot(
        identifier, provider, event_id, -110,
        "2026-07-22T20:02:00+00:00", player="Other Pitcher",
        normalized_player_name="other pitcher",
    )
    conflict = {**unrelated, "american_odds": 125, "side": "under"}
    rows = _base_rows() + [unrelated, conflict]

    bindings = _bindings(rows=rows)
    assert bindings["ready"] is True
    assert "duplicate_snapshot_conflict" not in bindings["reason_codes"]

    result = _build(rows=rows, bindings=bindings, windows=_windows(bindings))
    assert result.market_evidence["freshness_status"] == "fresh"
    assert "duplicate_snapshot_conflict" not in result.market_evidence["aggregation_reason_codes"]


def test_v2_bound_event_non_seed_collision_still_fails_closed():
    identifier = "cdcdcdcd-cdcd-4dcd-8dcd-cdcdcdcdcdcd"
    candidate_row = _snapshot(
        identifier, "therundown", "tr-event", -111,
        "2026-07-22T20:03:00+00:00", book="betmgm",
    )
    conflict = {**candidate_row, "american_odds": 120, "side": "under"}
    rows = _base_rows() + [candidate_row, conflict]

    bindings = _bindings(rows=rows)
    assert bindings["ready"] is False
    assert "duplicate_snapshot_conflict" in bindings["reason_codes"]

    clean_bindings = _bindings()
    result = _build(
        rows=rows, bindings=clean_bindings, windows=_windows(clean_bindings),
    )
    assert result.market_evidence["freshness_status"] == "pending"
    assert "duplicate_snapshot_conflict" in result.market_evidence["aggregation_reason_codes"]


def test_v2_same_uuid_boltodds_collision_does_not_poison_therundown_seed():
    bolt_seed = _snapshot(
        TR_OVER, "boltodds", "retired-bolt-event", -108,
        "2026-07-22T20:02:00+00:00",
    )
    bolt_conflict = {**bolt_seed, "american_odds": 125, "side": "under"}
    rows = _base_rows() + [bolt_seed, bolt_conflict]
    pitcher = _pitcher(
        source_snapshot_ids=[TR_OVER], therundown_event_id="tr-event",
    )

    bindings = _bindings(rows=rows, pitcher=pitcher)
    assert bindings["ready"] is True
    assert "duplicate_snapshot_conflict" not in bindings["reason_codes"]

    result = _build(rows=rows, bindings=bindings, windows=_windows(bindings))
    assert result.market_evidence["freshness_status"] == "fresh"
    assert "duplicate_snapshot_conflict" not in result.market_evidence["aggregation_reason_codes"]


def test_v2_exact_therundown_qualified_seed_collision_still_fails_closed():
    valid_seed = _base_rows()[0]
    conflicting_seed = {**valid_seed, "american_odds": 125}
    rows = [valid_seed, conflicting_seed]
    pitcher = _pitcher(
        source_current_market_line_ids=[101],
        source_snapshot_ids=[TR_OVER],
        therundown_event_id="tr-event",
    )
    current_lines = {"101": _line(101, "therundown", "tr-event", TR_OVER)}

    bindings = _bindings(
        rows=rows, pitcher=pitcher, current_lines=current_lines,
    )
    assert bindings["ready"] is False
    assert "duplicate_snapshot_conflict" in bindings["reason_codes"]

    clean_bindings = _bindings(
        rows=[valid_seed], pitcher=pitcher, current_lines=current_lines,
    )
    result = _build(
        rows=rows, bindings=clean_bindings, windows=_windows(clean_bindings),
    )
    assert result.market_evidence["freshness_status"] == "pending"
    assert "duplicate_snapshot_conflict" in result.market_evidence["aggregation_reason_codes"]


def test_v2_unsupported_direct_seed_cannot_bind():
    unsupported_seed = _snapshot(
        TR_OVER, "therundown", "tr-event", -105,
        "2026-07-22T20:00:00+00:00", book="bovada",
    )
    bindings = _bindings(
        rows=[unsupported_seed],
        pitcher=_pitcher(
            source_current_market_line_ids=[],
            source_snapshot_ids=[TR_OVER],
            therundown_event_id="tr-event",
        ),
    )

    assert bindings["ready"] is False
    assert bindings["official_binding"] is None


def test_v2_unsupported_current_line_side_seed_cannot_bind():
    unsupported_seed = _snapshot(
        TR_OVER, "therundown", "tr-event", -105,
        "2026-07-22T20:00:00+00:00", book="bovada",
    )
    bindings = _bindings(
        rows=[unsupported_seed],
        pitcher=_pitcher(source_current_market_line_ids=[101]),
        current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)},
    )

    assert bindings["ready"] is False
    assert bindings["official_binding"] is None
    assert "side_snapshot_mismatch" in bindings["reason_codes"]


def test_v2_unsupported_only_bound_event_collision_is_isolated():
    identifier = "edededed-eded-4ded-8ded-edededededed"
    unsupported = _snapshot(
        identifier, "therundown", "tr-event", -111,
        "2026-07-22T20:03:00+00:00", book="bovada",
    )
    conflict = {**unsupported, "american_odds": 125, "side": "under"}
    rows = _base_rows() + [unsupported, conflict]

    bindings = _bindings(rows=rows)
    assert bindings["ready"] is True
    assert "duplicate_snapshot_conflict" not in bindings["reason_codes"]

    result = _build(rows=rows, bindings=bindings, windows=_windows(bindings))
    assert result.market_evidence["freshness_status"] == "fresh"
    assert "duplicate_snapshot_conflict" not in result.market_evidence["aggregation_reason_codes"]


def test_v2_mixed_book_collision_with_supported_version_still_fails_closed():
    identifier = "efefefef-efef-4fef-8fef-efefefefefef"
    supported = _snapshot(
        identifier, "therundown", "tr-event", -111,
        "2026-07-22T20:03:00+00:00", book="fanduel",
    )
    unsupported_conflict = {**supported, "american_odds": 125, "bookmaker_key": "bovada"}
    rows = _base_rows() + [supported, unsupported_conflict]

    bindings = _bindings(rows=rows)
    assert bindings["ready"] is False
    assert "duplicate_snapshot_conflict" in bindings["reason_codes"]

    clean_bindings = _bindings()
    result = _build(
        rows=rows, bindings=clean_bindings, windows=_windows(clean_bindings),
    )
    assert result.market_evidence["freshness_status"] == "pending"
    assert "duplicate_snapshot_conflict" in result.market_evidence["aggregation_reason_codes"]


def test_v2_explicit_artifact_event_conflict_rejects_current_line_binding():
    bindings = _bindings(
        pitcher=_pitcher(
            source_current_market_line_ids=[101],
            therundown_event_id="artifact-event",
        ),
        current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)},
    )

    assert bindings["ready"] is False
    assert bindings["official_binding"] is None
    assert "therundown_binding_conflict" in bindings["reason_codes"]


def test_v2_mature_official_event_only_binding_builds_exact_evidence():
    rows = _base_rows()[:2]
    bindings = _bindings(
        rows=rows,
        pitcher=_pitcher(
            source_current_market_line_ids=[],
            therundown_event_id="tr-event",
        ),
    )

    assert bindings["ready"] is True
    assert bindings["official_binding"]["provider_event_id"] == "tr-event"
    assert bindings["official_binding"]["current_line_ids"] == []
    assert bindings["official_binding"]["seed_snapshot_ids"] == []

    result = _build(rows=rows, bindings=bindings, windows=_windows(bindings))
    assert result.market_evidence["freshness_status"] == "fresh"
    assert result.market_evidence["participating_providers"] == ["therundown"]


@pytest.mark.parametrize(("field", "value"), [
    ("provider_event_id", "wrong-event"),
    ("normalized_player_name", "other pitcher"),
    ("side", "under"),
    ("line", 7.5),
    ("slate_date", "2026-07-21"),
    ("bookmaker_key", "bovada"),
])
def test_v2_event_only_binding_rejects_wrong_candidate_semantics(field, value):
    rows = [{**row, field: value} for row in _base_rows()[:2]]
    bindings = _bindings(
        rows=rows,
        pitcher=_pitcher(
            source_current_market_line_ids=[],
            therundown_event_id="tr-event",
        ),
    )

    assert bindings["ready"] is False
    assert bindings["official_binding"] is None


def test_v2_event_only_binding_rejects_multiple_declared_provider_events():
    bindings = _bindings(
        rows=_base_rows()[:2],
        pitcher=_pitcher(
            source_current_market_line_ids=[],
            therundown_event_id="tr-event",
            rundown_event_id="other-event",
        ),
    )

    assert bindings["ready"] is False
    assert bindings["official_binding"] is None
    assert "therundown_binding_conflict" in bindings["reason_codes"]


def test_v2_event_only_binding_does_not_override_invalid_current_line_attempt():
    bindings = _bindings(
        rows=_base_rows()[:2],
        pitcher=_pitcher(
            source_current_market_line_ids=[101],
            therundown_event_id="tr-event",
        ),
        current_lines={
            "101": _line(
                101, "therundown", "tr-event", TR_OVER,
                normalized_player_name="other pitcher",
            ),
        },
    )

    assert bindings["ready"] is False
    assert bindings["official_binding"] is None
    assert "current_line_mismatch" in bindings["reason_codes"]


def test_v2_explicit_event_only_binding_tolerates_provider_start_time_skew():
    skewed_game_time = "2026-07-22T23:45:00+00:00"
    rows = [{**row, "game_time": skewed_game_time} for row in _base_rows()[:2]]
    bindings = _bindings(
        rows=rows,
        pitcher=_pitcher(
            source_current_market_line_ids=[],
            therundown_event_id="tr-event",
        ),
    )

    assert bindings["ready"] is True
    assert bindings["official_binding"]["mapped_game_times"] == [skewed_game_time]

    result = _build(rows=rows, bindings=bindings, windows=_windows(bindings))
    assert result.market_evidence["freshness_status"] == "fresh"


@pytest.mark.parametrize("sidecar_rows", [
    [_base_rows()[2]],
    [
        _snapshot(PL_OVER, "propline", "pl-event", -104, "2026-07-22T19:30:00+00:00", book="draftkings"),
        _snapshot(PL_LATER, "propline", "pl-event", -112, "2026-07-22T19:35:00+00:00", book="draftkings"),
    ],
])
def test_v2_optional_event_only_sidecar_is_nonessential_until_mature_and_fresh(sidecar_rows):
    rows = _base_rows()[:2] + sidecar_rows
    bindings = _bindings(
        rows=rows,
        pitcher=_pitcher(
            source_current_market_line_ids=[101],
            propline_event_id="pl-event",
        ),
        current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)},
    )

    assert bindings["ready"] is True
    assert bindings["sidecar_bindings"]["propline"]["provider_event_id"] == "pl-event"

    result = _build(rows=rows, bindings=bindings, windows=_windows(bindings))
    assert result.market_evidence["freshness_status"] == "fresh"
    assert result.market_evidence["participating_providers"] == ["therundown"]


def test_v2_payload_hash_change_alone_does_not_reset_the_window():
    bindings = _bindings()
    windows = _windows(bindings)
    assert windows["candidate_became_current_at"] == WINDOW_START
    assert windows["provider_window_started_at"]["therundown"] == WINDOW_START


def test_v2_official_binding_change_resets_the_candidate_window():
    bindings = _bindings()
    existing = deepcopy(_windows(bindings))
    prior = {
        "candidate_identity": "candidate-v2", "candidate_became_current_at": WINDOW_START,
        "evaluation_proof": {"exact_preclose": {
            "official_binding_key": "old", "sidecar_binding_keys": bindings["sidecar_binding_keys"],
            "provider_window_started_at": existing["provider_window_started_at"],
        }},
    }
    windows = _windows(bindings, existing=prior)
    assert windows["candidate_became_current_at"] == OBSERVED_AT
    assert set(windows["provider_window_started_at"].values()) == {OBSERVED_AT}


def test_v2_sidecar_binding_change_resets_only_the_sidecar_window():
    bindings = _bindings()
    prior = {
        "candidate_identity": "candidate-v2", "candidate_became_current_at": WINDOW_START,
        "evaluation_proof": {"exact_preclose": {
            "official_binding_key": bindings["official_binding_key"],
            "sidecar_binding_keys": {"propline": "old"},
            "provider_window_started_at": {"therundown": WINDOW_START, "propline": WINDOW_START},
        }},
    }
    windows = _windows(bindings, existing=prior)
    assert windows["candidate_became_current_at"] == WINDOW_START
    assert windows["provider_window_started_at"] == {"therundown": WINDOW_START, "propline": OBSERVED_AT}


def test_v2_exact_movement_requires_two_official_ids_and_timestamps():
    rows = [_base_rows()[0]]
    result = _build(rows=rows, bindings=_bindings(rows=rows, pitcher=_pitcher(source_current_market_line_ids=[101]), current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)}))
    assert result.market_evidence["freshness_status"] == "pending"
    assert result.market_evidence["toward_pick_count"] is None


@pytest.mark.parametrize(
    "duplicate_odds",
    [(-105, -120), (-120, -105)],
)
def test_v2_same_book_same_timestamp_duplicates_cannot_satisfy_provider_maturity(duplicate_odds):
    duplicate_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    other_book_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    rows = [
        _snapshot(TR_OVER, "therundown", "tr-event", duplicate_odds[0], "2026-07-22T20:00:00+00:00"),
        _snapshot(duplicate_id, "therundown", "tr-event", duplicate_odds[1], "2026-07-22T20:00:00+00:00"),
        _snapshot(
            other_book_id, "therundown", "tr-event", -110,
            "2026-07-22T20:06:00+00:00", book="draftkings",
        ),
    ]
    bindings = _bindings(
        rows=rows,
        pitcher=_pitcher(source_current_market_line_ids=[101]),
        current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)},
    )

    result = _build(rows=list(reversed(rows)), bindings=bindings, windows=_windows(bindings))

    assert result.market_evidence["freshness_status"] == "pending"
    assert "official_provider_immature" in result.market_evidence["aggregation_reason_codes"]
    assert result.market_evidence["toward_pick_count"] is None
    assert result.proof_fragment["exact_preclose"]["direction_change_pivot_tokens"] == []


@pytest.mark.parametrize("reverse_input", [False, True])
def test_v2_conflicting_same_timestamp_prices_are_neutral_not_uuid_ordered(reverse_input):
    same_time_second = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    fanduel_later = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    draftkings_first = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    draftkings_later = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    rows = [
        _snapshot(TR_OVER, "therundown", "tr-event", -105, "2026-07-22T20:00:00+00:00"),
        _snapshot(same_time_second, "therundown", "tr-event", -120, "2026-07-22T20:00:00+00:00"),
        _snapshot(fanduel_later, "therundown", "tr-event", -110, "2026-07-22T20:06:00+00:00"),
        _snapshot(
            draftkings_first, "therundown", "tr-event", -105,
            "2026-07-22T20:00:00+00:00", book="draftkings",
        ),
        _snapshot(
            draftkings_later, "therundown", "tr-event", -120,
            "2026-07-22T20:06:00+00:00", book="draftkings",
        ),
    ]
    bindings = _bindings(
        rows=rows,
        pitcher=_pitcher(source_current_market_line_ids=[101]),
        current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)},
    )
    if reverse_input:
        rows = list(reversed(rows))

    result = _build(rows=rows, bindings=bindings, windows=_windows(bindings))

    assert result.market_evidence["freshness_status"] == "fresh"
    assert result.market_evidence["toward_pick_count"] == 1
    assert result.market_evidence["away_from_pick_count"] == 0
    assert result.market_evidence["reversal_book_count"] == 0
    assert result.proof_fragment["exact_preclose"]["direction_change_pivot_tokens"] == []


def test_v2_same_price_duplicate_checkpoint_preserves_legitimate_timeline():
    duplicate_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    later_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    rows = [
        _snapshot(TR_OVER, "therundown", "tr-event", -105, "2026-07-22T20:00:00+00:00"),
        _snapshot(duplicate_id, "therundown", "tr-event", -105, "2026-07-22T20:00:00+00:00"),
        _snapshot(later_id, "therundown", "tr-event", -120, "2026-07-22T20:06:00+00:00"),
    ]
    bindings = _bindings(
        rows=rows,
        pitcher=_pitcher(source_current_market_line_ids=[101]),
        current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)},
    )

    result = _build(rows=list(reversed(rows)), bindings=bindings, windows=_windows(bindings))

    assert result.market_evidence["freshness_status"] == "fresh"
    assert result.market_evidence["toward_pick_count"] == 1
    assert result.market_evidence["away_from_pick_count"] == 0
    assert result.market_evidence["reversal_book_count"] == 0


def test_v2_exact_checkpoint_conflicts_are_permutation_invariant_for_ladder_and_movement():
    conflict_a = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    conflict_b = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    draftkings_first = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    draftkings_later = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

    def build_rows(*, swap_conflict_prices=False, reverse=False):
        conflict_prices = (120, -140) if not swap_conflict_prices else (-140, 120)
        rows = [
            _snapshot(TR_OVER, "therundown", "tr-event", -105, "2026-07-22T20:00:00+00:00"),
            _snapshot(conflict_a, "therundown", "tr-event", conflict_prices[0], "2026-07-22T20:06:00+00:00"),
            _snapshot(conflict_b, "therundown", "tr-event", conflict_prices[1], "2026-07-22T20:06:00+00:00"),
            _snapshot(
                draftkings_first, "therundown", "tr-event", -105,
                "2026-07-22T20:00:00+00:00", book="draftkings",
            ),
            _snapshot(
                draftkings_later, "therundown", "tr-event", -120,
                "2026-07-22T20:06:00+00:00", book="draftkings",
            ),
        ]
        return list(reversed(rows)) if reverse else rows

    results = []
    for swap_conflict_prices, reverse in ((False, False), (False, True), (True, False), (True, True)):
        rows = build_rows(swap_conflict_prices=swap_conflict_prices, reverse=reverse)
        bindings = _bindings(
            rows=rows,
            pitcher=_pitcher(source_current_market_line_ids=[101]),
            current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)},
        )
        result = _build(rows=rows, bindings=bindings, windows=_windows(bindings))
        ladder = result.proof_fragment["exact_preclose"]["ladder"]
        results.append({
            "freshness_status": result.market_evidence["freshness_status"],
            "toward_pick_count": result.market_evidence["toward_pick_count"],
            "away_from_pick_count": result.market_evidence["away_from_pick_count"],
            "reversal_book_count": result.market_evidence["reversal_book_count"],
            "movement_observation_ids": result.proof_fragment["exact_preclose"]["movement_observation_ids"],
            "ladder": {
                key: ladder[key]
                for key in (
                    "main_line", "best_book", "best_line", "best_odds",
                    "best_is_off_market", "book_rows",
                )
            },
        })

    assert all(result == results[0] for result in results[1:])
    assert results[0]["freshness_status"] == "fresh"
    assert results[0]["toward_pick_count"] == 1
    assert results[0]["away_from_pick_count"] == 0
    assert results[0]["reversal_book_count"] == 0
    assert all(token.split(":", 1)[1] not in {conflict_a, conflict_b} for token in results[0]["movement_observation_ids"])


def test_v2_movement_excludes_adjacent_event_and_alternate_line():
    rows = _base_rows() + [
        _snapshot("77777777-7777-4777-8777-777777777777", "therundown", "adjacent", 150, "2026-07-22T20:08:00+00:00"),
        _snapshot("88888888-8888-4888-8888-888888888888", "therundown", "tr-event", 150, "2026-07-22T20:08:00+00:00", line=7.5),
    ]
    result = _build(rows=rows)
    assert result.market_evidence["observation_ids"] == [f"therundown:{TR_OVER}", f"propline:{PL_OVER}", f"therundown:{TR_LATER}", f"propline:{PL_LATER}"]


def test_v2_ladder_allows_only_same_exact_event_alternate_lines():
    rows = _base_rows() + [
        _snapshot("88888888-8888-4888-8888-888888888888", "therundown", "tr-event", 120, "2026-07-22T20:08:00+00:00", line=5.5, book="betmgm"),
        _snapshot("99999999-9999-4999-8999-999999999999", "therundown", "adjacent", 130, "2026-07-22T20:09:00+00:00", line=4.5, book="caesars"),
    ]
    result = _build(rows=rows)
    ladder = result.proof_fragment["exact_preclose"]["ladder"]
    assert {row["book"] for row in ladder["book_rows"]} == {"fanduel", "draftkings", "betmgm"}
    assert "caesars" not in ladder["books_seen"]


def test_v2_optional_sidecar_absence_or_immaturity_does_not_block_official_evidence():
    rows = _base_rows()[:2]
    bindings = _bindings(rows=rows, pitcher=_pitcher(source_current_market_line_ids=[101]), current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)})
    result = _build(rows=rows, bindings=bindings, windows=_windows(bindings))
    assert result.market_evidence["freshness_status"] == "fresh"
    assert result.market_evidence["participating_providers"] == ["therundown"]


def test_v2_mature_provider_book_disagreement_fails_closed():
    rows = _base_rows()
    rows[2]["bookmaker_key"] = "fanduel"
    rows[3]["bookmaker_key"] = "fanduel"
    rows[3]["american_odds"] = -95
    result = _build(rows=rows)
    assert result.market_evidence["freshness_status"] == "pending"
    assert "provider_book_disagreement" in result.market_evidence["aggregation_reason_codes"]


def test_v2_opposing_mature_provider_majorities_fail_closed():
    rows = _base_rows() + [
        _snapshot("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "therundown", "tr-event", -100, "2026-07-22T20:00:00+00:00", book="betmgm"),
        _snapshot("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "therundown", "tr-event", -115, "2026-07-22T20:06:00+00:00", book="betmgm"),
        _snapshot("cccccccc-cccc-4ccc-8ccc-cccccccccccc", "propline", "pl-event", -110, "2026-07-22T20:01:00+00:00", book="caesars"),
        _snapshot("dddddddd-dddd-4ddd-8ddd-dddddddddddd", "propline", "pl-event", -90, "2026-07-22T20:07:00+00:00", book="caesars"),
    ]
    rows[3]["american_odds"] = -90
    result = _build(rows=rows)
    assert result.market_evidence["freshness_status"] == "pending"
    assert "provider_majority_disagreement" in result.market_evidence["aggregation_reason_codes"]


def test_v2_duplicate_provider_qualified_id_with_conflicting_content_fails_closed():
    rows = _base_rows() + [{**_base_rows()[0], "american_odds": 120}]
    result = _build(rows=rows)
    assert result.market_evidence["freshness_status"] == "pending"
    assert "duplicate_snapshot_conflict" in result.market_evidence["aggregation_reason_codes"]


def test_v2_future_post_start_and_stale_rows_are_excluded():
    rows = _base_rows() + [
        _snapshot("aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa", "therundown", "tr-event", -140, "2026-07-22T20:11:00+00:00"),
        _snapshot("bbbbbbbb-1111-4111-8111-bbbbbbbbbbbb", "therundown", "tr-event", -140, GAME_TIME),
        _snapshot("cccccccc-1111-4111-8111-cccccccccccc", "therundown", "tr-event", -140, "2026-07-22T19:00:00+00:00"),
    ]
    result = _build(rows=rows)
    ids = result.market_evidence["observation_ids"]
    assert all(token.split(":", 1)[1] not in {row["id"] for row in rows[-3:]} for token in ids)


def test_v2_missing_counts_or_best_is_off_market_never_reach_the_scorer():
    result = _build(rows=[] , bindings={"ready": False, "official_provider": "therundown", "reason_codes": ("unbound",)}, windows={})
    assert result.market_evidence["freshness_status"] == "pending"
    assert result.market_evidence["book_count"] is None
    assert result.market_evidence["best_is_off_market"] is None


def test_v2_uses_native_snapshot_age_freshness_without_broad_trackers():
    rows = _base_rows()[:2]
    stale_observed = "2026-07-22T20:30:00+00:00"
    bindings = _bindings(rows=rows, pitcher=_pitcher(source_current_market_line_ids=[101]), current_lines={"101": _line(101, "therundown", "tr-event", TR_OVER)})
    windows = {"candidate_became_current_at": WINDOW_START, "provider_window_started_at": {"therundown": WINDOW_START}}
    result = _build(rows=rows, bindings=bindings, windows=windows, observed_at=stale_observed, provider_heartbeats=[{"provider": "therundown", "slate_date": "2026-07-22", "observed_at": stale_observed, "last_message_at": stale_observed, "books_seen": ["fanduel"]}])
    assert result.market_evidence["freshness_status"] == "pending"
    assert "official_provider_immature" in result.market_evidence["aggregation_reason_codes"]


def test_v2_proof_fragment_captures_direction_pivots_and_latest_ladder_tokens():
    rows = _base_rows() + [
        _snapshot(
            TR_REVERSAL, "therundown", "tr-event", -110,
            "2026-07-22T20:08:00+00:00",
        )
    ]
    result = _build(rows=rows)
    exact = result.proof_fragment["exact_preclose"]

    assert exact["direction_change_pivot_tokens"] == [f"therundown:{TR_REVERSAL}"]
    assert set(exact["latest_ladder_observation_tokens"]) == {
        f"therundown:{TR_REVERSAL}", f"propline:{PL_LATER}",
    }
    assert exact["ladder_observation_token_sha256"] == __import__("hashlib").sha256(
        "|".join(exact["ladder_observation_ids"]).encode("utf-8")
    ).hexdigest()


def test_v2_preclose_interface_has_no_market_pick_evidence_or_persisted_display_argument():
    for function in (
        preclose.resolve_candidate_bindings_v2,
        preclose.resolve_candidate_windows_v2,
        preclose.build_exact_preclose_evidence_v2,
    ):
        parameters = set(inspect.signature(function).parameters)
        assert "market_pick_evidence_rows" not in parameters
        assert "live_market_display_rows" not in parameters
