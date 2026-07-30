import json

from analytics.diagnostics.clv_process_target_validation import build_target_row
from analytics.diagnostics import clv_process_target_validation as clv


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


def test_build_target_row_marks_over_at_lower_locked_line_as_line_clv():
    row = build_target_row(
        {
            "slate_date": "2026-07-29",
            "pitcher": "Chris Sale",
            "side": "over",
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 5.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "close-line-1",
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
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 6.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "close-alt-1",
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
            "lock_provider": "therundown",
            "lock_book": "FanDuel",
            "lock_line": 6.5,
            "lock_odds": -110,
        },
        [
            {
                "observation_id": "stale-close-1",
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

    assert clv.classify_proxy(first) == "not_evaluated_task_1"
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
    market_input = tmp_path / "market.jsonl"
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
    market_input.write_text(
        json.dumps(
            {
                "observation_id": "close-1",
                "observed_at": "2026-07-29T22:00:00Z",
                "provider": "therundown",
                "bookmaker": "FanDuel",
                "side": "over",
                "line": 5.5,
                "american_odds": -125,
                "freshness": "fresh",
                "observation_type": "official_close",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert clv.main(
        [
            "--gate-c-input",
            str(gate_c_input),
            "--market-input",
            str(market_input),
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
