from __future__ import annotations

import hashlib
import json
from pathlib import Path

from market_infra import alternative_pick_preclose_v2 as preclose
from market_infra import alternative_pick_selector as v1
from market_infra import alternative_pick_selector_v2 as selector


FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "alternative_pick_selection_v2"
SYNTHETIC_PATH = FIXTURE_DIRECTORY / "synthetic_mature_preclose.json"
LEGACY_PARITY_PATH = FIXTURE_DIRECTORY / "legacy_official_close_parity.json.gz"
MANIFEST_PATH = FIXTURE_DIRECTORY / "manifest.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _exact_evidence(fixture: dict) -> dict:
    exact = fixture["exact_preclose"]
    bindings = preclose.resolve_candidate_bindings_v2(
        candidate=exact["candidate"],
        pitcher=exact["pitcher"],
        current_lines_by_id=exact["current_lines_by_id"],
        snapshot_rows=exact["snapshot_rows"],
    )
    windows = preclose.resolve_candidate_windows_v2(
        candidate=exact["candidate"],
        bindings=bindings,
        existing_state_row=exact["existing_state_row"],
        observed_at=fixture["observed_at"],
    )
    return preclose.build_exact_preclose_evidence_v2(
        candidate=exact["candidate"],
        bindings=bindings,
        windows=windows,
        snapshot_rows=exact["snapshot_rows"],
        provider_heartbeats=exact["provider_heartbeats"],
        observed_at=fixture["observed_at"],
        source_artifact_path=fixture["source_artifact"]["path"],
        source_artifact_byte_sha256=fixture["source_artifact"]["byte_sha256"],
    ).market_evidence


def test_v2_fixture_manifest_hashes_match_raw_bytes():
    manifest = _load(MANIFEST_PATH)
    paths = {
        "synthetic_mature_preclose.json": SYNTHETIC_PATH,
        "legacy_official_close_parity.json.gz": LEGACY_PARITY_PATH,
    }

    assert set(manifest["fixtures"]) == set(paths)
    for name, path in paths.items():
        assert manifest["fixtures"][name]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert manifest["fixtures"]["synthetic_mature_preclose.json"]["source"] == (
        "synthetic mature exact-line Preclose regression evidence"
    )


def test_v2_fixture_manifest_marks_prospective_capture_required():
    manifest = _load(MANIFEST_PATH)

    assert manifest["prospective_capture"] == {
        "status": "required_before_production_gate_a",
    }


def test_v2_synthetic_fixture_contains_no_broad_tracker_or_hindsight_input():
    fixture = _load(SYNTHETIC_PATH)
    serialized = json.dumps(fixture, sort_keys=True).lower()

    forbidden = (
        "market_pick_evidence",
        "live_market_display_state",
        "result",
        "actual_ks",
        "pnl",
        "beat_close",
        "accepted_bet",
        "notification",
        "post_start",
    )
    assert not any(token in serialized for token in forbidden)


def test_v2_synthetic_fixture_resolves_affirmative_exact_preclose():
    fixture = _load(SYNTHETIC_PATH)
    evidence = _exact_evidence(fixture)
    evaluation = selector.evaluate_alternative_pick_v2(
        pitcher=fixture["selector_input"]["pitcher"],
        pick=fixture["selector_input"]["pick"],
        exact_evidence=evidence,
        slate_date=fixture["slate_date"],
        is_tracked=True,
        source_artifact_path=fixture["source_artifact"]["path"],
        source_payload_sha256=fixture["source_artifact"]["payload_sha256"],
        source_artifact_byte_sha256=fixture["source_artifact"]["byte_sha256"],
        observed_at=fixture["observed_at"],
    )

    assert evidence["freshness_status"] == "fresh"
    assert evidence["best_is_off_market"] is False
    assert evaluation.family_states["preclose"].state == "agree"
    assert evaluation.selection_status == "selected"
    assert evaluation.lane == "consensus_core"


def test_v2_replay_starts_prospective_ledger_at_zero():
    fixture = _load(SYNTHETIC_PATH)

    assert v1.prospective_ledger_seed() == {
        "rows": 0,
        "pnl": 0.0,
    }
    assert "pnl" not in json.dumps(fixture, sort_keys=True).lower()
