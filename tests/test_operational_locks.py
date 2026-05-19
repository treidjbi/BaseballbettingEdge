from datetime import datetime

from market_infra.operational_locks import build_operational_lock_rows


def _pick(
    *,
    side="over",
    game_time="2026-05-19T20:00:00Z",
    locked_at=None,
    verdict="FIRE 1u",
    display_k_line=6.5,
    display_odds=-115,
    locked_k_line=7.5,
    locked_odds=125,
    display_verdict=None,
    book=None,
    current_book=None,
):
    row = {
        "pitcher": "Tarik Skubal",
        "side": side,
        "display_verdict": display_verdict or verdict,
        "locked_verdict": "LEAN",
        "display_k_line": display_k_line,
        "locked_k_line": locked_k_line,
        "display_odds": display_odds,
        "locked_odds": locked_odds,
        "locked_at": locked_at,
        "game_time": game_time,
        "book": book,
        "current_book": current_book,
        "display_adj_ev": 0.13,
    }
    return row


def _pitcher(
    *,
    game_time="2026-05-19T20:00:00Z",
    locked_at=None,
    verdict="FIRE 1u",
    tracked_picks=None,
):
    return {
        "pitcher": "Tarik Skubal",
        "team": "DET",
        "opp_team": "BOS",
        "ref_book": "FanDuel",
        "best_over_book": "BetMGM",
        "best_under_book": "DraftKings",
        "game_time": game_time,
        "tracked_picks": tracked_picks
        if tracked_picks is not None
        else [
            _pick(
                game_time=game_time,
                locked_at=locked_at,
                verdict=verdict,
            )
        ],
    }


def test_build_operational_lock_rows_captures_first_due_unlocked_pick():
    rows = build_operational_lock_rows(
        slate_date="2026-05-19",
        pitchers=[_pitcher()],
        observed_at=datetime.fromisoformat("2026-05-19T19:32:00+00:00"),
        source_artifact_path="https://raw.example/today.json",
        source_artifact_sha256="sha",
        artifact_generated_at="2026-05-19T19:20:00Z",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["dedupe_key"] == "2026-05-19:tarik skubal:over"
    assert row["status_at_capture"] == "due_now"
    assert row["observed_at"] == "2026-05-19T19:32:00+00:00"
    assert row["locked_at"] == "2026-05-19T19:32:00+00:00"
    assert row["should_lock_at"] == "2026-05-19T19:30:00+00:00"
    assert row["locked_k_line"] == 6.5
    assert row["locked_odds"] == -115
    assert row["locked_adj_ev"] == 0.13
    assert row["locked_verdict"] == "FIRE 1u"
    assert row["locked_book"] == "BetMGM"
    assert row["metadata"]["team"] == "DET"
    assert row["metadata"]["opp_team"] == "BOS"
    assert row["metadata"]["artifact_generated_at"] == "2026-05-19T19:20:00+00:00"
    assert row["metadata"]["lock_window_minutes"] == 30
    assert row["metadata"]["missed_lock_grace_minutes"] == 5


def test_build_operational_lock_rows_marks_exact_t_25_as_missed_lock():
    rows = build_operational_lock_rows(
        slate_date="2026-05-19",
        pitchers=[_pitcher()],
        observed_at=datetime.fromisoformat("2026-05-19T19:35:00+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
    )

    assert rows[0]["status_at_capture"] == "missed_lock"
    assert rows[0]["minutes_until_start"] == 25.0


def test_build_operational_lock_rows_captures_missed_before_game_start():
    rows = build_operational_lock_rows(
        slate_date="2026-05-19",
        pitchers=[_pitcher()],
        observed_at=datetime.fromisoformat("2026-05-19T19:35:01+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
    )

    assert rows[0]["status_at_capture"] == "missed_lock"
    assert rows[0]["minutes_until_start"] == 24.98


def test_build_operational_lock_rows_skips_not_due_locked_started_pass_and_incomplete():
    rows = build_operational_lock_rows(
        slate_date="2026-05-19",
        pitchers=[
            _pitcher(game_time="2026-05-19T21:30:00Z"),
            _pitcher(locked_at="2026-05-19T19:28:00Z"),
            _pitcher(game_time="2026-05-19T19:20:00Z"),
            _pitcher(verdict="PASS"),
            _pitcher(game_time=None),
            _pitcher(tracked_picks=[_pick(display_k_line=None, locked_k_line=None)]),
            _pitcher(tracked_picks=[_pick(display_odds=None, locked_odds=None)]),
        ],
        observed_at=datetime.fromisoformat("2026-05-19T19:32:00+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
    )

    assert rows == []


def test_build_operational_lock_rows_uses_pick_book_before_pitcher_fallbacks():
    rows = build_operational_lock_rows(
        slate_date="2026-05-19",
        pitchers=[
            _pitcher(
                tracked_picks=[
                    _pick(
                        side="under",
                        book=None,
                        current_book="Caesars",
                        display_k_line=5.5,
                        display_odds=105,
                    )
                ]
            )
        ],
        observed_at=datetime.fromisoformat("2026-05-19T19:32:00+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
    )

    assert rows[0]["dedupe_key"] == "2026-05-19:tarik skubal:under"
    assert rows[0]["locked_book"] == "Caesars"
    assert rows[0]["locked_k_line"] == 5.5
    assert rows[0]["locked_odds"] == 105
