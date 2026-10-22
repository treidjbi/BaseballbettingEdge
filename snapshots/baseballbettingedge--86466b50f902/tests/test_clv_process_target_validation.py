import json

import pytest

from analytics.diagnostics.clv_process_target_validation import build_target_row
from analytics.diagnostics import clv_process_target_validation as clv


def _operational_close_packet(**overrides):
    row = {
        "observation_id": "close-operational-1",
        "observation_type": "official_close",
        "slate_date": "2026-08-26",
        "pitcher": "Logan Webb",
        "side": "under",
        "observed_at": "2026-08-26T19:29:00+00:00",
        "provider": "therundown",
        "bookmaker": "FanDuel",
        "line": 5.5,
        "american_odds": -110,
        "freshness": "fresh",
        "official_lock_reference": "lock-logan-webb",
        "lock_provider": "therundown",
        "lock_book": "FanDuel",
        "lock_line": 5.5,
        "lock_odds": -106,
        "lock_observed_at": "2026-08-26T19:20:23.821626+00:00",
        "lock_source_artifact_path": "https://example.net/api/get-artifact?type=today",
        "lock_source_artifact_sha256": "b" * 64,
    }
    row.update(overrides)
    return row


def test_build_target_row_marks_same_line_better_price_as_price_clv():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "José Berríos",
            "side": "over",
            "official_lock_reference": "lock-123",
            "locked_at": "2026-07-29T18:00:00Z",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 5.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "close-456",
                "slate_date": "2026-07-29",
                "pitcher": "José Berríos",
                "observed_at": "2026-07-29T22:00:00Z",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 5.5,
                "american_odds": -125,
                "freshness": "fresh",
                "observation_type": "official_close",
            }
        ],
    )

    assert row["target_key"] == "2026-07-29:jose berrios:over"
    assert row["display_pitcher"] == "José Berríos"
    assert row["official_lock_reference"] == "lock-123"
    assert row["lock_observed_at"] == "2026-07-29T18:00:00Z"
    assert row["close_observation_id"] == "close-456"
    assert row["close_observed_at"] == "2026-07-29T22:00:00Z"
    assert row["final_clv"] == "beat_close_price"


@pytest.mark.parametrize(
    "provider_fields",
    [
        {"official_line_source_provider": "therundown"},
        {"official_odds_source": "therundown"},
    ],
)
def test_build_target_row_accepts_exact_gate_c_official_provider_fields(
    provider_fields,
):
    gate_c_row = {
        "slate_date": "2026-08-25",
        "pitcher": "Aaron Nola",
        "side": "over",
        "bet_time_at": "2026-08-25T18:10:34-07:00",
        "bet_time_book": "FanDuel",
        "bet_time_line": 5.5,
        "bet_time_odds": -125,
        **provider_fields,
    }
    close_rows = [
        {
            "observation_id": "close-1",
            "observation_type": "official_close",
            "slate_date": "2026-08-25",
            "pitcher": "Aaron Nola",
            "side": "over",
            "provider": "therundown",
            "bookmaker": "FanDuel",
            "line": 5.5,
            "american_odds": -125,
            "observed_at": "2026-08-25T18:30:19-07:00",
            "freshness": "fresh",
        }
    ]

    row = build_target_row(gate_c_row, close_rows)

    assert row["lock_provider"] == "therundown"
    assert row["close_eligibility"] == "eligible"
    assert row["final_clv"] == "neutral_close"


def test_build_target_row_preserves_gate_c_pnl_outside_preclose_proxy_inputs():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Chris Sale",
            "side": "over",
            "locked_at": "2026-07-29T18:00:00+00:00",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 5.5,
            "lock_odds": -110,
            "pick_history_pnl": 1.25,
            "theoretical_pnl": 0.9,
        },
        [
            {
                "observation_id": "close-456",
                "slate_date": "2026-07-29",
                "pitcher": "Chris Sale",
                "observed_at": "2026-07-29T22:00:00+00:00",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 5.5,
                "american_odds": -125,
                "freshness": "fresh",
                "observation_type": "official_close",
            }
        ],
    )

    assert row["pick_history_pnl"] == 1.25
    assert row["theoretical_pnl"] == 0.9
    assert "pick_history_pnl" not in row["preclose_proxy_inputs"]
    assert "theoretical_pnl" not in row["preclose_proxy_inputs"]
    summary = clv.build_summary([row])
    proxy_label = summary["rows"][0]["proxy_label"]
    assert summary["pnl_crosstab"][proxy_label]["beat"]["pnl"] == 1.25


def test_build_target_row_marks_over_at_lower_locked_line_as_line_clv():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Chris Sale",
            "side": "over",
            "locked_at": "2026-07-29T18:00:00Z",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 5.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "close-line-1",
                "slate_date": "2026-07-29",
                "pitcher": "Chris Sale",
                "observed_at": "2026-07-29T22:00:00Z",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "freshness": "fresh",
                "observation_type": "official_close",
            }
        ],
    )

    assert row["final_clv"] == "beat_close_line"


def test_build_target_row_rejects_alternate_line_price_as_price_clv():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Zack Wheeler",
            "side": "over",
            "locked_at": "2026-07-29T18:00:00Z",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 6.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "close-alt-1",
                "slate_date": "2026-07-29",
                "pitcher": "Zack Wheeler",
                "observed_at": "2026-07-29T22:00:00Z",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 5.5,
                "american_odds": -125,
                "freshness": "fresh",
                "observation_type": "official_close",
            }
        ],
    )

    assert row["close_line_match"] == "alternate_line"
    assert row["final_clv"] == "worse_close_line"


def test_build_target_row_marks_stale_close_evidence_unknown():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Paul Skenes",
            "side": "under",
            "locked_at": "2026-07-29T18:00:00Z",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 6.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "stale-close-1",
                "slate_date": "2026-07-29",
                "pitcher": "Paul Skenes",
                "observed_at": "2026-07-29T20:00:00Z",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "under",
                "line": 6.5,
                "american_odds": -125,
                "freshness": "stale",
                "observation_type": "official_close",
            }
        ],
    )

    assert row["close_eligibility"] == "stale_evidence"
    assert row["final_clv"] == "unknown"


@pytest.mark.parametrize(
    ("lock_timestamp", "close_timestamp", "eligibility"),
    [
        ("2026-07-29T18:00:00", "2026-07-29T22:00:00+00:00", "invalid_lock_timestamp"),
        ("2026-07-29T18:00:00+00:00", "2026-07-29T22:00:00", "invalid_close_timestamp"),
        (
            "2026-07-29T22:00:00+00:00",
            "2026-07-29T22:00:00+00:00",
            "close_not_after_lock",
        ),
    ],
)
def test_build_target_row_requires_aware_strictly_later_close_timestamp(
    lock_timestamp, close_timestamp, eligibility
):
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Paul Skenes",
            "side": "under",
            "locked_at": lock_timestamp,
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 6.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "close-time-1",
                "slate_date": "2026-07-29",
                "pitcher": "Paul Skenes",
                "observed_at": close_timestamp,
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "under",
                "line": 6.5,
                "american_odds": -125,
                "freshness": "fresh",
                "observation_type": "official_close",
            }
        ],
    )

    assert row["close_eligibility"] == eligibility
    assert row["final_clv"] == "unknown"


def test_build_target_row_keeps_missing_close_unknown():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Max Fried",
            "side": "under",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 5.5,
            "lock_odds": -110,
        },
        [],
    )

    assert row["close_eligibility"] == "missing_close"
    assert row["close_observation_id"] is None
    assert row["close_line_match"] == "unknown"
    assert row["final_clv"] == "unknown"


def test_build_target_row_rejects_provider_mismatch_without_inferring_close():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Tarik Skubal",
            "side": "over",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 6.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "propline-close-1",
                "slate_date": "2026-07-29",
                "pitcher": "Tarik Skubal",
                "observed_at": "2026-07-29T22:00:00Z",
                "provider": "propline",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 6.5,
                "american_odds": -125,
                "freshness": "fresh",
                "observation_type": "official_close",
            }
        ],
    )

    assert row["close_eligibility"] == "provider_mismatch"
    assert row["close_observation_id"] == "propline-close-1"
    assert row["close_provider"] == "propline"
    assert row["final_clv"] == "unknown"


def test_build_target_row_rejects_book_mismatch_without_inferring_close():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Tarik Skubal",
            "side": "over",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 6.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "dk-close-1",
                "slate_date": "2026-07-29",
                "pitcher": "Tarik Skubal",
                "observed_at": "2026-07-29T22:00:00Z",
                "provider": "therundown",
                "bookmaker": "DraftKings",
                "side": "over",
                "line": 6.5,
                "american_odds": -125,
                "freshness": "fresh",
                "observation_type": "official_close",
            }
        ],
    )

    assert row["close_eligibility"] == "book_mismatch"
    assert row["close_book"] == "DraftKings"
    assert row["final_clv"] == "unknown"


def test_operational_lock_packet_overrides_gate_c_book_and_records_disagreement():
    gate_c_row = {
        "dataset_key": "2026-08-26:logan-webb:under:5.5",
        "slate_date": "2026-08-26",
        "pitcher": "Logan Webb",
        "side": "under",
        "bet_time_at": "2026-08-26T12:20:23.821626-07:00",
        "bet_time_book": "DraftKings",
        "bet_time_line": 5.5,
        "bet_time_odds": -106,
        "official_line_source_provider": "therundown",
    }

    row = build_target_row(gate_c_row, [_operational_close_packet()])

    assert row["close_eligibility"] == "eligible"
    assert row["official_lock_reference"] == "lock-logan-webb"
    assert row["lock_book"] == "FanDuel"
    assert row["lock_line"] == 5.5
    assert row["lock_odds"] == -106
    assert row["lock_observed_at"] == "2026-08-26T19:20:23.821626+00:00"
    assert row["gate_c_bet_time_book"] == "DraftKings"
    assert row["gate_c_book_agrees_with_operational_lock"] is False
    assert row["lock_source_artifact_sha256"] == "b" * 64


@pytest.mark.parametrize(
    ("gate_override", "eligibility"),
    [
        ({"bet_time_line": 6.5}, "gate_c_lock_line_mismatch"),
        ({"bet_time_odds": -105}, "gate_c_lock_odds_mismatch"),
        ({"bet_time_at": "2026-08-26T12:21:23.821626-07:00"}, "gate_c_lock_timestamp_mismatch"),
    ],
)
def test_operational_lock_packet_fails_closed_on_gate_c_value_disagreement(
    gate_override, eligibility
):
    gate_c_row = {
        "slate_date": "2026-08-26",
        "pitcher": "Logan Webb",
        "side": "under",
        "bet_time_at": "2026-08-26T12:20:23.821626-07:00",
        "bet_time_book": "FanDuel",
        "bet_time_line": 5.5,
        "bet_time_odds": -106,
        "official_line_source_provider": "therundown",
        **gate_override,
    }

    row = build_target_row(gate_c_row, [_operational_close_packet()])

    assert row["close_eligibility"] == eligibility
    assert row["final_clv"] == "unknown"


def test_build_target_row_selects_same_slate_same_pitcher_close_not_another_pitcher():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "José Berríos",
            "normalized_pitcher": "JOSE BERRIOS",
            "side": "over",
            "locked_at": "2026-07-29T18:00:00Z",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 5.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "wrong-pitcher",
                "slate_date": "2026-07-29",
                "pitcher": "Max Fried",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 5.5,
                "american_odds": -125,
                "observed_at": "2026-07-29T22:00:00Z",
                "freshness": "fresh",
                "observation_type": "official_close",
            },
            {
                "observation_id": "same-pitcher",
                "date": "2026-07-29",
                "normalized_pitcher": "josé berríos",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 5.5,
                "american_odds": -125,
                "observed_at": "2026-07-29T22:00:00Z",
                "freshness": "fresh",
                "observation_type": "official_close",
            },
        ],
    )

    assert row["normalized_pitcher"] == "jose berrios"
    assert row["close_observation_id"] == "same-pitcher"


def test_build_target_row_rejects_cross_date_close_for_same_pitcher_side_and_book():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Chris Sale",
            "side": "over",
            "locked_at": "2026-07-29T18:00:00Z",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 5.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "next-day-close",
                "slate_date": "2026-07-30",
                "player_name": "Chris Sale",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 5.5,
                "american_odds": -125,
                "observed_at": "2026-07-30T22:00:00Z",
                "freshness": "fresh",
                "observation_type": "official_close",
            }
        ],
    )

    assert row["close_eligibility"] == "identity_mismatch"
    assert row["close_observation_id"] is None
    assert row["final_clv"] == "unknown"


def test_build_target_row_rejects_same_pitcher_close_with_conflicting_event_identity():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Chris Sale",
            "side": "over",
            "provider_event_id": "game-1",
            "locked_at": "2026-07-29T18:00:00Z",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 5.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "wrong-event",
                "slate_date": "2026-07-29",
                "pitcher": "Chris Sale",
                "provider_event_id": "game-2",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 5.5,
                "american_odds": -125,
                "observed_at": "2026-07-29T22:00:00Z",
                "freshness": "fresh",
                "observation_type": "official_close",
            }
        ],
    )

    assert row["close_eligibility"] == "identity_mismatch"
    assert row["final_clv"] == "unknown"


@pytest.mark.parametrize(
    ("gate_override", "close_override", "eligibility"),
    [
        ({"lock_provider": ""}, {}, "missing_lock_provider"),
        ({}, {"provider": ""}, "missing_close_provider"),
        ({"lock_book": ""}, {}, "missing_lock_book"),
        ({}, {"bookmaker": ""}, "missing_close_book"),
        ({"locked_at": None}, {}, "missing_lock_timestamp"),
        ({}, {"observed_at": None}, "missing_close_timestamp"),
        ({"lock_line": None}, {}, "missing_lock_line"),
        ({}, {"line": None}, "missing_close_line"),
        ({}, {"freshness": None}, "missing_close_freshness"),
    ],
)
def test_build_target_row_marks_incomplete_provenance_ineligible(gate_override, close_override, eligibility):
    gate_row = {
        "slate_date": "2026-07-29",
        "pitcher": "Chris Sale",
        "side": "over",
        "locked_at": "2026-07-29T18:00:00Z",
        "lock_provider": "therundown",
        "lock_book": "FanDuel",
        "lock_line": 5.5,
        "lock_odds": -110,
    }
    close_row = {
        "observation_id": "close-1",
        "slate_date": "2026-07-29",
        "pitcher": "Chris Sale",
        "observed_at": "2026-07-29T22:00:00Z",
        "provider": "therundown",
        "bookmaker": "FanDuel",
        "side": "over",
        "line": 5.5,
        "american_odds": -125,
        "freshness": "fresh",
        "observation_type": "official_close",
    }
    gate_row.update(gate_override)
    close_row.update(close_override)

    row = build_target_row(gate_row, [close_row])

    assert row["close_eligibility"] == eligibility
    assert row["final_clv"] == "unknown"
    if eligibility == "missing_close_freshness":
        assert row["close_freshness"] is None
    if eligibility == "missing_lock_line" or eligibility == "missing_close_line":
        assert row["close_line_match"] == "unknown"


def test_summary_normalizes_distinct_case_and_accent_pitcher_variants_before_deduplication():
    summary = clv.build_summary(
        [
            {
                "slate_date": "2026-07-29",
                "normalized_pitcher": "JOSÉ BERRÍOS",
                "display_pitcher": "José Berríos",
                "side": "over",
            },
            {
                "date": "2026-07-29",
                "normalized_pitcher": "jose berrios",
                "display_pitcher": "Jose Berrios",
                "side": "over",
            },
        ]
    )

    assert summary["duplicate_rows"] == 1
    assert summary["rows"][0]["normalized_pitcher"] == "jose berrios"
    assert summary["rows"][0]["display_pitcher"] == "José Berríos"


def test_summary_deduplicates_normalized_pick_key_and_keeps_final_data_out_of_proxy_inputs():
    first = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "José Berríos",
            "side": "over",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 5.5,
            "lock_odds": -110,
            "result": "win",
            "actual_ks": 7,
            "actual_ip": 6.0,
        },
        [],
    )
    duplicate = {**first, "display_pitcher": "Jose Berrios"}

    summary = clv.build_summary([first, duplicate])

    assert clv.classify_proxy(first) == "weak_preclose_clv_proxy"
    assert summary["input_rows"] == 2
    assert summary["duplicate_rows"] == 1
    assert summary["rows"][0]["display_pitcher"] == "José Berríos"
    assert summary["rows"][0]["proxy_selector_inputs"] == {
        "lock_book": "FanDuel",
        "lock_line": 5.5,
        "lock_observed_at": None,
        "lock_odds": -110.0,
        "lock_provider": "therundown",
    }
    assert "final_clv" not in summary["rows"][0]["proxy_selector_inputs"]
    assert "close_line" not in summary["rows"][0]["proxy_selector_inputs"]
    assert "result" not in summary["rows"][0]["proxy_selector_inputs"]


def test_main_writes_process_only_markdown_and_json_from_gate_c_conventions(tmp_path):
    gate_c_input = tmp_path / "gate_c.jsonl"
    close_evidence_input = tmp_path / "official_close_packet.jsonl"
    output_dir = tmp_path / "output"
    gate_c_input.write_text(
        json.dumps(
            {
                "dataset_key": "2026-07-29:official_close:chris-sale:over:5.5",
                "slate_date": "2026-07-29",
                "pitcher": "Chris Sale",
                "side": "over",
                "bet_time_at": "2026-07-29T18:00:00Z",
                "bet_time_book": "FanDuel",
                "bet_time_line": 5.5,
                "bet_time_odds": -110,
                "provider": "therundown",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    close_evidence_input.write_text(
        json.dumps(
            {
                "observation_id": "close-1",
                "slate_date": "2026-07-29",
                "pitcher": "Chris Sale",
                "observed_at": "2026-07-29T22:00:00Z",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 5.5,
                "american_odds": -125,
                "freshness": "fresh",
                "observation_type": "official_close",
                "official_lock_reference": "2026-07-29:official_close:chris-sale:over:5.5",
                "lock_provider": "therundown",
                "lock_book": "FanDuel",
                "lock_line": 5.5,
                "lock_odds": -110,
                "lock_observed_at": "2026-07-29T18:00:00Z",
                "lock_source_artifact_path": "https://example.net/api/get-artifact?type=today",
                "lock_source_artifact_sha256": "c" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert clv.main(
        [
            "--gate-c-input",
            str(gate_c_input),
            "--close-evidence-input",
            str(close_evidence_input),
            "--output-dir",
            str(output_dir),
        ]
    ) == 0

    payload = json.loads((output_dir / "clv_process_target_validation.json").read_text(encoding="utf-8"))
    report = (output_dir / "clv_process_target_validation.md").read_text(encoding="utf-8")
    assert payload["rows"][0]["official_lock_reference"] == "2026-07-29:official_close:chris-sale:over:5.5"
    assert payload["rows"][0]["final_clv"] == "beat_close_price"
    assert "process benchmark" in report
    assert "-4.64u" in report
    assert "does not create a selector" in report


def test_close_packet_rejects_non_over_under_side_before_target_build(tmp_path):
    close_packet = tmp_path / "official_close_packet.json"
    close_packet.write_text(
        json.dumps(
            [
                {
                    "observation_id": "close-1",
                    "slate_date": "2026-07-29",
                    "pitcher": "Chris Sale",
                    "observed_at": "2026-07-29T22:00:00+00:00",
                    "provider": "therundown",
                    "bookmaker": "FanDuel",
                    "side": "both",
                    "line": 5.5,
                    "american_odds": -125,
                    "freshness": "fresh",
                    "observation_type": "official_close",
                    "official_lock_reference": "2026-07-29:official_close:chris-sale:over:5.5",
                    "lock_provider": "therundown",
                    "lock_book": "FanDuel",
                    "lock_line": 5.5,
                    "lock_odds": -110,
                    "lock_observed_at": "2026-07-29T18:00:00Z",
                    "lock_source_artifact_path": "https://example.net/api/get-artifact?type=today",
                    "lock_source_artifact_sha256": "c" * 64,
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="side"):
        clv.load_close_evidence_packet(close_packet)


def test_close_packet_rejects_rows_without_operational_lock_provenance(tmp_path):
    close_packet = tmp_path / "official_close_packet.json"
    legacy_row = _operational_close_packet()
    for field in (
        "official_lock_reference",
        "lock_provider",
        "lock_book",
        "lock_line",
        "lock_odds",
        "lock_observed_at",
        "lock_source_artifact_path",
        "lock_source_artifact_sha256",
    ):
        legacy_row.pop(field)
    close_packet.write_text(json.dumps([legacy_row]), encoding="utf-8")

    with pytest.raises(ValueError, match="operational lock provenance"):
        clv.load_close_evidence_packet(close_packet)


def _proxy_target(**overrides):
    row = {
        "slate_date": "2026-07-01",
        "normalized_pitcher": "test pitcher",
        "display_pitcher": "Test Pitcher",
        "side": "over",
        "close_eligibility": "eligible",
        "final_clv": "beat_close_price",
        "lock_provider": "therundown",
        "lock_book": "FanDuel",
        "close_provider": "therundown",
        "close_book": "FanDuel",
        "lock_line": 5.5,
        "lock_odds": -110,
        "edge": 0.015,
        "adj_ev": 0.05,
        "model_no_vig_gap": 0.015,
        "model_market_relationship": "model_agrees_with_favorite",
        "quality_gate_level": "clean",
        "line_bucket": "5.5",
        "price_sign": "minus",
        "bet_timing_window": "pre_30",
        "side_price_movement": "with_side",
        "toward_pick_count": 3,
        "away_from_pick_count": 0,
        "book_count": 4,
        "broad_confirmation": True,
        "best_is_off_market": False,
        "reversal_book_count": 0,
        "volatile_book_count": 0,
        "market_consensus": "toward_pick",
        "leash_risk_bucket": "normal",
        "batter_handedness_mode": "path_b",
        "lineup_real_split_count": 7,
        "pick_history_pnl": 0.91,
        "result": "win",
    }
    row.update(overrides)
    return row


def test_proxy_validation_compares_shared_preclose_and_agreement_buckets_without_hindsight_inputs():
    strong = _proxy_target()
    medium = _proxy_target(
        normalized_pitcher="medium pitcher",
        display_pitcher="Medium Pitcher",
        final_clv="neutral_close",
        edge=0.015,
        adj_ev=0.2,
        model_no_vig_gap=None,
        quality_gate_level="unknown",
        price_sign="unknown",
        bet_timing_window="unknown",
        side_price_movement="unchanged",
        toward_pick_count=None,
        away_from_pick_count=None,
        book_count=0,
        broad_confirmation=False,
        market_consensus="mixed",
    )
    weak = _proxy_target(
        normalized_pitcher="weak pitcher",
        display_pitcher="Weak Pitcher",
        final_clv="worse_close_price",
        side="under",
        edge=0.08,
        adj_ev=0.2,
        model_no_vig_gap=0.005,
        model_market_relationship="model_fades_favorite",
        quality_gate_level="blocked",
        price_sign="plus",
        bet_timing_window="pre_5",
        side_price_movement="against_side",
        toward_pick_count=0,
        away_from_pick_count=2,
        book_count=1,
        broad_confirmation=False,
        best_is_off_market=True,
        reversal_book_count=2,
        volatile_book_count=3,
        market_consensus="away_from_pick",
        pick_history_pnl=-1.0,
        result="loss",
    )

    summary = clv.build_summary([strong, medium, weak])

    assert summary["proxy_buckets"]["strong_preclose_clv_proxy"]["target_counts"] == {
        "beat": 1,
        "neutral": 0,
        "worse": 0,
    }
    assert summary["proxy_buckets"]["medium_preclose_clv_proxy"]["target_counts"] == {
        "beat": 0,
        "neutral": 1,
        "worse": 0,
    }
    assert summary["proxy_buckets"]["weak_preclose_clv_proxy"]["target_counts"] == {
        "beat": 0,
        "neutral": 0,
        "worse": 1,
    }
    assert summary["agreement_buckets"]["market_with_model"]["precision"] == 1.0
    assert summary["agreement_buckets"]["market_against_model"]["precision"] == 0.0
    assert summary["pnl_crosstab"]["strong_preclose_clv_proxy"]["beat"]["pnl"] == 0.91
    assert set(summary["slices"]) >= {
        "side", "price", "k_line", "timing", "quality", "path_b", "workload",
        "provider", "agreement", "rolling_14_slates",
    }
    assert "final_clv" not in summary["rows"][0]["proxy_selector_inputs"]


def test_proxy_validation_keeps_missing_close_unknown_and_proxy_membership_hindsight_free():
    base = _proxy_target(
        final_clv="unknown",
        close_eligibility="missing_close",
        result="loss",
        actual_ks=0,
        actual_workload="short",
        closing_line=9.5,
        closing_odds=-250,
    )
    changed_outcomes = {
        **base,
        "final_clv": "beat_close_line",
        "close_eligibility": "eligible",
        "result": "win",
        "actual_ks": 12,
        "actual_workload": "full",
        "closing_line": 2.5,
        "closing_odds": 200,
    }

    assert clv.classify_proxy(base) == clv.classify_proxy(changed_outcomes)
    summary = clv.build_summary([base])
    assert summary["eligible_target_rows"] == 0
    assert summary["unknown_target_rows"] == 1
    assert summary["proxy_buckets"]["strong_preclose_clv_proxy"]["evaluated_rows"] == 0


def test_proxy_readiness_requires_current_provider_coverage_and_two_positive_14_slate_windows():
    rows = []
    for day in range(1, 29):
        slate_date = f"2026-07-{day:02d}"
        for copy in range(2):
            rows.append(
                _proxy_target(
                    slate_date=slate_date,
                    normalized_pitcher=f"strong {day} {copy}",
                    display_pitcher=f"Strong {day} {copy}",
                )
            )
            rows.append(
                _proxy_target(
                    slate_date=slate_date,
                    normalized_pitcher=f"weak {day} {copy}",
                    display_pitcher=f"Weak {day} {copy}",
                    side="under",
                    final_clv="worse_close_price",
                    edge=0.08,
                    adj_ev=0.2,
                    model_no_vig_gap=0.005,
                    model_market_relationship="model_fades_favorite",
                    quality_gate_level="blocked",
                    price_sign="plus",
                    bet_timing_window="pre_5",
                    side_price_movement="against_side",
                    toward_pick_count=0,
                    away_from_pick_count=2,
                    book_count=1,
                    broad_confirmation=False,
                    best_is_off_market=True,
                    reversal_book_count=2,
                    volatile_book_count=3,
                    market_consensus="away_from_pick",
                    pick_history_pnl=-1.0,
                    result="loss",
                )
            )

    summary = clv.build_summary(rows)

    readiness = summary["readiness"]
    assert readiness["fully_attributed_current_provider_targets"] == 112
    assert readiness["positive_proxy_lift_windows"] == 2
    assert readiness["status"] == "ready_for_proxy_design"
    assert all(window["strong_lift_vs_base_rate"] > 0 for window in readiness["rolling_14_slate_windows"])


def test_proxy_readiness_does_not_count_historical_lift_windows_toward_current_provider_gate():
    rows = []
    for day in range(1, 29):
        slate_date = f"2026-04-{day:02d}"
        rows.extend(
            [
                _proxy_target(
                    slate_date=slate_date,
                    normalized_pitcher=f"historic strong {day}",
                    display_pitcher=f"Historic Strong {day}",
                ),
                _proxy_target(
                    slate_date=slate_date,
                    normalized_pitcher=f"historic weak {day}",
                    display_pitcher=f"Historic Weak {day}",
                    side="under",
                    final_clv="worse_close_price",
                    edge=0.08,
                    adj_ev=0.2,
                    model_no_vig_gap=0.005,
                    model_market_relationship="model_fades_favorite",
                    quality_gate_level="blocked",
                    price_sign="plus",
                    bet_timing_window="pre_5",
                    side_price_movement="against_side",
                    toward_pick_count=0,
                    away_from_pick_count=2,
                    book_count=1,
                    broad_confirmation=False,
                    best_is_off_market=True,
                    reversal_book_count=2,
                    volatile_book_count=3,
                    market_consensus="away_from_pick",
                    pick_history_pnl=-1.0,
                    result="loss",
                ),
            ]
        )
    for copy in range(100):
        rows.append(
            _proxy_target(
                slate_date="2026-07-01",
                normalized_pitcher=f"current weak {copy}",
                display_pitcher=f"Current Weak {copy}",
                side="under",
                final_clv="worse_close_price",
                edge=0.08,
                adj_ev=0.2,
                model_no_vig_gap=0.005,
                model_market_relationship="model_fades_favorite",
                quality_gate_level="blocked",
                price_sign="plus",
                bet_timing_window="pre_5",
                side_price_movement="against_side",
                toward_pick_count=0,
                away_from_pick_count=2,
                book_count=1,
                broad_confirmation=False,
                best_is_off_market=True,
                reversal_book_count=2,
                volatile_book_count=3,
                market_consensus="away_from_pick",
                pick_history_pnl=-1.0,
                result="loss",
            )
        )

    readiness = clv.build_summary(rows)["readiness"]

    assert readiness["fully_attributed_current_provider_targets"] == 100
    assert readiness["all_era_positive_proxy_lift_windows"] == 2
    assert readiness["positive_proxy_lift_windows"] == 0
    assert len(readiness["all_era_rolling_14_slate_windows"]) == 2
    assert readiness["readiness_rolling_14_slate_windows"][0]["slates"] == 1
    assert readiness["status"] == "keep_as_process_kpi"


def test_proxy_validation_report_marks_pnl_as_non_causal_and_brier_as_process_diagnostic():
    report = clv.render_report(clv.build_summary([_proxy_target()]))

    assert "Brier-style" in report
    assert "not causal" in report
    assert "does not create a selector" in report
