import json

import pytest

from scripts import repair_missing_locked_picks as repair
from scripts.repair_missing_locked_picks import reconstruct_missing_history_rows


DATE = "2026-08-20"
PITCHER = "Brady Singer"
SIDE = "over"
LOCK_SHA = "a" * 64


def _archive(*, selected_odds=104, selected_adj_ev=0.1667):
    return {
        "date": DATE,
        "pitchers": [
            {
                "pitcher": PITCHER,
                "team": "Cincinnati Reds",
                "opp_team": "St. Louis Cardinals",
                "pitcher_throws": "R",
                "game_time": "2026-08-20T16:40:00Z",
                "k_line": 4.5,
                "lambda": 5.07,
                "raw_lambda": 5.06,
                "best_over_odds": selected_odds,
                "best_under_odds": -132,
                "opening_over_odds": 108,
                "opening_under_odds": -138,
                "opening_odds_source": "preview",
                "season_k9": 8.4,
                "recent_k9": 9.1,
                "career_k9": 8.6,
                "avg_ip": 5.7,
                "ump_k_adj": 0.01,
                "opp_k_rate": 0.24,
                "swstr_delta_k9": 0.03,
                "swstr_pct": 0.11,
                "career_swstr_pct": 0.105,
                "ref_book": "FanDuel",
                "lineup_used": True,
                "is_opener": False,
                "days_since_last_start": 5,
                "last_pitch_count": 93,
                "rest_k9_delta": 0.0,
                "park_factor": 1.0,
                "data_complete": True,
                "data_maturity": {"lineup": "confirmed"},
                "input_quality_flags": [],
                "ev_over": {
                    "verdict": "LEAN",
                    "actionable_verdict": "LEAN",
                    "raw_verdict": "FIRE 1u",
                    "edge": 0.0817,
                    "ev": selected_adj_ev,
                    "adj_ev": selected_adj_ev,
                    "raw_adj_ev": selected_adj_ev,
                    "movement_conf": 1,
                    "quality_gate_level": "clean",
                    "confidence_referee": {"mode": "enforce", "applied": True},
                    "market_anchor_selector": {"mode": "shadow", "applied": False},
                    "projection_challenger": {"mode": "shadow", "applied": False},
                },
                "ev_under": {"verdict": "PASS"},
            }
        ],
    }


def _lock():
    return {
        "dedupe_key": f"{DATE}:brady singer:{SIDE}",
        "slate_date": DATE,
        "status_at_capture": "due_now",
        "observed_at": "2026-08-20T16:10:40.196569+00:00",
        "locked_at": "2026-08-20T16:10:40.196569+00:00",
        "pitcher": PITCHER,
        "normalized_pitcher": "brady singer",
        "side": SIDE,
        "locked_verdict": "LEAN",
        "locked_k_line": 4.5,
        "locked_odds": 112,
        "locked_adj_ev": 0.2124,
        "locked_book": "FanDuel",
        "game_time": "2026-08-20T16:40:00+00:00",
        "should_lock_at": "2026-08-20T16:10:00+00:00",
        "minutes_until_start": 29.33,
        "source_artifact_path": "https://example.test/artifact?type=today",
        "source_artifact_sha256": LOCK_SHA,
        "consumed_at": "2026-08-20T16:38:06.783548+00:00",
        "metadata": {
            "team": "Cincinnati Reds",
            "opp_team": "St. Louis Cardinals",
        },
    }


def _frozen_state():
    return {
        "slate_date": DATE,
        "pitcher": PITCHER,
        "normalized_pitcher": "brady singer",
        "side": SIDE,
        "checkpoint": "frozen_pregame",
        "official_odds": 112,
        "official_verdict": "LEAN",
        "lock_artifact_sha256": LOCK_SHA,
        "locked_at": "2026-08-20T16:10:40.196569+00:00",
        "evaluation_proof": {
            "normalized_inputs": {
                "pitcher": "brady singer",
                "side": SIDE,
                "game_time": "2026-08-20T16:40:00+00:00",
                "k_line": 4.5,
                "odds": 112,
                "official_book": "FanDuel",
                "official_verdict": "LEAN",
                "adjusted_ev": 0.2124,
                "edge": 0.1002,
                "source_fire_verdict": "FIRE 2u",
                "quality_gate_level": "clean",
                "observed_at": "2026-08-20T16:10:40.196569+00:00",
            }
        },
    }


def test_reconstructs_exact_lock_fields_and_quarantines_nonmatching_archive_inputs():
    rows, audit = reconstruct_missing_history_rows(
        history=[],
        archive=_archive(),
        locks=[_lock()],
        frozen_states=[_frozen_state()],
        expected_keys=[(PITCHER, SIDE)],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["date"] == DATE
    assert row["pitcher"] == PITCHER
    assert row["side"] == SIDE
    assert row["odds"] == 112
    assert row["adj_ev"] == pytest.approx(0.2124)
    assert row["edge"] == pytest.approx(0.1002)
    assert row["verdict"] == "LEAN"
    assert row["raw_verdict"] == "FIRE 2u"
    assert row["locked_at"] == _lock()["locked_at"]
    assert row["locked_odds"] == 112
    assert row["raw_lambda"] == pytest.approx(5.06)
    assert row["applied_lambda"] == pytest.approx(5.07)
    assert row["result"] is None
    assert row["data_complete"] == 0
    assert "history_recovered_from_lock_evidence" in row["input_quality_flags"]
    assert row["confidence_referee"] is None
    assert audit == [
        {
            "date": DATE,
            "pitcher": PITCHER,
            "side": SIDE,
            "archive_core_match": False,
            "calibration_quarantined": True,
        }
    ]


def test_reconstruction_preserves_shadow_metadata_when_archive_core_matches_lock():
    archive = _archive(selected_odds=112, selected_adj_ev=0.2124)
    archive["pitchers"][0]["ev_over"]["edge"] = 0.1002
    archive["pitchers"][0]["ev_over"]["raw_verdict"] = "FIRE 2u"

    rows, audit = reconstruct_missing_history_rows(
        history=[],
        archive=archive,
        locks=[_lock()],
        frozen_states=[_frozen_state()],
        expected_keys=[(PITCHER, SIDE)],
    )

    assert rows[0]["confidence_referee"] == {"mode": "enforce", "applied": True}
    assert rows[0]["market_anchor_selector"] == {"mode": "shadow", "applied": False}
    assert audit[0]["archive_core_match"] is True


@pytest.mark.parametrize(
    ("history", "locks", "states", "match"),
    [
        ([{"date": DATE, "pitcher": PITCHER, "side": SIDE}], [_lock()], [_frozen_state()], "already exists"),
        ([], [], [_frozen_state()], "exactly one consumed lock"),
        ([], [_lock()], [], "exactly one frozen state"),
    ],
)
def test_reconstruction_fails_closed_on_ambiguous_or_duplicate_evidence(
    history, locks, states, match
):
    with pytest.raises(ValueError, match=match):
        reconstruct_missing_history_rows(
            history=history,
            archive=_archive(),
            locks=locks,
            frozen_states=states,
            expected_keys=[(PITCHER, SIDE)],
        )


def test_reconstruction_rejects_frozen_proof_that_disagrees_with_lock():
    state = _frozen_state()
    state["evaluation_proof"]["normalized_inputs"]["odds"] = 110

    with pytest.raises(ValueError, match="frozen proof does not match lock"):
        reconstruct_missing_history_rows(
            history=[],
            archive=_archive(),
            locks=[_lock()],
            frozen_states=[state],
            expected_keys=[(PITCHER, SIDE)],
        )


def test_linked_cli_loader_returns_bounded_repair_evidence(monkeypatch, tmp_path):
    payload = {
        "rows": [
            {
                "history": [],
                "archive": _archive(),
                "locks": [_lock()],
                "frozen_states": [_frozen_state()],
            }
        ]
    }
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]
        return type("Result", (), {"stdout": json.dumps(payload)})()

    monkeypatch.setattr(repair.subprocess, "run", fake_run)

    evidence = repair.load_live_evidence_with_cli(DATE, linked_root=tmp_path)

    assert evidence["archive"]["date"] == DATE
    assert evidence["locks"][0]["pitcher"] == PITCHER
    sql = captured["command"][-1]
    assert "published_pipeline_artifacts" in sql
    assert "operational_pick_locks" in sql
    assert "alternative_pick_selection_state" in sql
    assert "2026-08-20" in sql
    assert captured["cwd"] == tmp_path


def test_writer_loader_reads_full_canonical_artifacts_and_operational_evidence():
    class Writer:
        def select_rows(self, table, params, **kwargs):
            if table == "published_pipeline_artifacts":
                return [
                    {"artifact_key": "picks_history", "payload": []},
                    {"artifact_key": f"dated_slate:{DATE}", "payload": _archive()},
                    {"artifact_key": "performance", "payload": {"record": {}}},
                    {"artifact_key": "params", "payload": {"lambda_bias": 0.0}},
                    {"artifact_key": "index", "payload": {"dates": [DATE]}},
                ]
            if table == "operational_pick_locks":
                return [_lock()]
            if table == "alternative_pick_selection_state":
                return [_frozen_state()]
            raise AssertionError(table)

    evidence = repair.load_live_evidence_with_writer(Writer(), DATE)

    assert evidence["history"] == []
    assert evidence["archive"]["date"] == DATE
    assert evidence["performance"] == {"record": {}}
    assert evidence["params"] == {"lambda_bias": 0.0}
    assert evidence["index"] == {"dates": [DATE]}
    assert evidence["locks"][0]["consumed_at"]
    assert evidence["frozen_states"][0]["checkpoint"] == "frozen_pregame"


def test_stage_repair_artifacts_appends_rows_and_preserves_support_files(tmp_path):
    evidence = {
        "history": [{"date": "2026-08-19", "pitcher": "Prior", "side": "over"}],
        "archive": _archive(),
        "performance": {"record": {"wins": 1}},
        "params": {"lambda_bias": 0.01},
        "index": {"dates": [DATE]},
    }
    recovered = [{"date": DATE, "pitcher": PITCHER, "side": SIDE}]

    repair.stage_repair_artifacts(
        root=tmp_path,
        slate_date=DATE,
        evidence=evidence,
        reconstructed_rows=recovered,
    )

    history = json.loads((tmp_path / "data/picks_history.json").read_text(encoding="utf-8"))
    assert history == [evidence["history"][0], recovered[0]]
    assert json.loads(
        (tmp_path / f"dashboard/data/processed/{DATE}.json").read_text(encoding="utf-8")
    ) == _archive()
    assert json.loads(
        (tmp_path / "dashboard/data/performance.json").read_text(encoding="utf-8")
    ) == evidence["performance"]
    assert json.loads((tmp_path / "data/params.json").read_text(encoding="utf-8")) == evidence["params"]
    assert json.loads(
        (tmp_path / "dashboard/data/processed/index.json").read_text(encoding="utf-8")
    ) == evidence["index"]


def test_verify_graded_recoveries_requires_closed_exact_rows():
    history = [
        {
            "date": DATE,
            "pitcher": PITCHER,
            "side": SIDE,
            "result": "win",
            "actual_ks": 6,
            "pnl": 1.12,
            "locked_at": _lock()["locked_at"],
            "locked_odds": 112,
            "locked_verdict": "LEAN",
            "input_quality_flags": [repair.RECOVERY_FLAG],
        }
    ]

    summary = repair.verify_graded_recoveries(
        history=history,
        slate_date=DATE,
        expected_keys=[(PITCHER, SIDE)],
    )

    assert summary == [
        {
            "date": DATE,
            "pitcher": PITCHER,
            "side": SIDE,
            "result": "win",
            "actual_ks": 6,
            "pnl": 1.12,
        }
    ]

    history[0]["result"] = None
    with pytest.raises(ValueError, match="did not grade"):
        repair.verify_graded_recoveries(
            history=history,
            slate_date=DATE,
            expected_keys=[(PITCHER, SIDE)],
        )
