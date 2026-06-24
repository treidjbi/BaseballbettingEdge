import subprocess
import sys
from datetime import date
from pathlib import Path

from analytics.diagnostics.mainline_movement_pattern_audit import (
    _linked_cli_queries,
    summarize_mainline_movement_patterns,
)


def _movement(
    *,
    dedupe_key="move-1",
    source="mainline_polling",
    pitcher="Joe Ryan",
    side="over",
    book="draftkings",
    previous_line=5.5,
    current_line=5.5,
    previous_odds=-110,
    current_odds=-135,
    observed_at="2026-06-24T16:00:00+00:00",
    market_direction="toward_pick",
    bet_value_direction="worse_now",
    movement_kind="odds",
):
    metadata = {
        "bet_value_direction": bet_value_direction,
        "market_direction": market_direction,
    }
    if source == "propline_webhook":
        metadata["source"] = "propline_webhook"
    return {
        "slate_date": "2026-06-24",
        "normalized_pitcher": pitcher.lower(),
        "pitcher": pitcher,
        "side": side,
        "bookmaker_key": book,
        "previous_line": previous_line,
        "current_line": current_line,
        "previous_odds": previous_odds,
        "current_odds": current_odds,
        "movement_kind": movement_kind,
        "movement_direction": "against_model",
        "observed_at": observed_at,
        "dedupe_key": dedupe_key,
        "metadata": metadata,
    }


def _evidence(pitcher="Joe Ryan", side="over", k_line=5.5, verdict="FIRE 1u"):
    return {
        "slate_date": "2026-06-24",
        "normalized_pitcher": pitcher.lower(),
        "pitcher": pitcher,
        "side": side,
        "provider": "therundown",
        "current_verdict": verdict,
        "k_line": k_line,
        "metadata": {"tracked_verdict": verdict},
    }


def test_summarize_mainline_patterns_classifies_sources_lines_and_alerts():
    summary = summarize_mainline_movement_patterns(
        movement_events=[
            _movement(dedupe_key="polling-1"),
            _movement(
                dedupe_key="webhook-1",
                source="propline_webhook",
                previous_line=4.5,
                current_line=5.5,
                movement_kind="line",
            ),
        ],
        notification_events=[
            {
                "dedupe_key": "polling-1",
                "event_type": "line_moved_against_us",
                "sent_at": "2026-06-24T16:01:00+00:00",
            }
        ],
        market_pick_evidence=[_evidence(k_line=5.5)],
        compact_market_movements=[],
    )

    assert summary["movement_events"] == 2
    assert summary["by_source"] == {"mainline_polling": 1, "propline_webhook": 1}
    assert summary["same_line_price_moves"] == 1
    assert summary["line_moves_touching_pick_line"] == 1
    assert summary["supported_book_rows"] == 2
    assert summary["alert_rows"] == 1
    assert summary["sent_alert_rows"] == 1
    assert summary["top_patterns"][0]["count"] >= 1
    assert "official_odds_source" in summary["blocked_uses"]


def test_summarize_mainline_patterns_measures_webhook_vs_polling_timing():
    movement_signature = {
        "pitcher": "Tanner Bibee",
        "side": "over",
        "book": "draftkings",
        "previous_line": 4.5,
        "current_line": 4.5,
        "previous_odds": -160,
        "current_odds": -180,
        "movement_kind": "odds",
    }

    summary = summarize_mainline_movement_patterns(
        movement_events=[
            _movement(
                dedupe_key="webhook-first",
                source="propline_webhook",
                observed_at="2026-06-24T16:00:00+00:00",
                **movement_signature,
            ),
            _movement(
                dedupe_key="polling-second",
                source="mainline_polling",
                observed_at="2026-06-24T16:10:00+00:00",
                **movement_signature,
            ),
        ],
        notification_events=[],
        market_pick_evidence=[_evidence(pitcher="Tanner Bibee", k_line=4.5)],
        compact_market_movements=[],
    )

    timing = summary["webhook_vs_polling_timing"]
    assert timing["matched_movements"] == 1
    assert timing["webhook_first"] == 1
    assert timing["polling_first"] == 0
    assert timing["median_webhook_lead_seconds"] == 600


def test_candidate_alert_patterns_are_not_hidden_by_high_volume_noise():
    noisy_rows = []
    for index in range(16):
        noisy_rows.extend(
            [
                _movement(
                    dedupe_key=f"noise-{index}-a",
                    book=f"unsupported-{index}",
                    previous_odds=-100,
                    current_odds=-120 - index,
                ),
                _movement(
                    dedupe_key=f"noise-{index}-b",
                    book=f"unsupported-{index}",
                    previous_odds=-100,
                    current_odds=-120 - index,
                ),
            ]
        )
    candidate = _movement(dedupe_key="candidate", book="fanduel")

    summary = summarize_mainline_movement_patterns(
        movement_events=[*noisy_rows, candidate],
        notification_events=[
            {
                "dedupe_key": "candidate",
                "event_type": "line_moved_against_us",
                "sent_at": "2026-06-24T16:01:00+00:00",
            }
        ],
        market_pick_evidence=[_evidence(k_line=5.5)],
        compact_market_movements=[],
    )

    assert summary["candidate_alert_patterns"]
    assert summary["candidate_alert_patterns"][0]["bookmaker_key"] == "fanduel"


def test_linked_cli_queries_use_processed_movement_tables_not_raw_webhook_inbox():
    queries = _linked_cli_queries(
        start_date=date(2026, 6, 18),
        end_date=date(2026, 6, 24),
        limit=500,
    )
    sql_blob = " ".join(spec["sql"] for spec in queries.values())

    assert "public.line_movement_events" in sql_blob
    assert "public.notification_events" in sql_blob
    assert "public.market_pick_evidence" in sql_blob
    assert "public.compact_market_line_movements" in sql_blob
    assert "propline_webhook_deliveries" not in sql_blob


def test_cli_help_runs_when_executed_by_file_path():
    root = Path(__file__).resolve().parents[1]

    completed = subprocess.run(
        [
            sys.executable,
            "analytics/diagnostics/mainline_movement_pattern_audit.py",
            "--help",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    assert "--lookback-days" in completed.stdout
