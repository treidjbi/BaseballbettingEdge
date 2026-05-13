from datetime import datetime, timedelta, timezone

from market_infra.official_market_lines import choose_official_lines, retire_missing_official_lines


NOW = datetime(2026, 5, 13, 19, 0, tzinfo=timezone.utc)


def _line(
    line_id,
    *,
    provider="boltodds",
    book_key="fanduel",
    book_name="FanDuel",
    player="Jose Berrios",
    normalized_player="jose berrios",
    line=5.5,
    over_odds=-110,
    under_odds=-110,
    freshness_seconds=60,
    is_complete=True,
    quality_flags=None,
):
    last_seen_at = (NOW - timedelta(seconds=freshness_seconds)).isoformat()
    return {
        "id": line_id,
        "slate_date": "2026-05-13",
        "provider": provider,
        "book_key": book_key,
        "book_name": book_name,
        "player_name": player,
        "normalized_player_name": normalized_player,
        "market_key": "pitcher_strikeouts",
        "line": line,
        "over_odds": over_odds,
        "under_odds": under_odds,
        "freshness_seconds": freshness_seconds,
        "last_seen_at": last_seen_at,
        "is_complete": is_complete,
        "quality_flags": quality_flags or [],
    }


def test_boltodds_fanduel_beats_propline_fanduel_when_fresh():
    official_rows, decision_rows = choose_official_lines(
        [
            _line(1, provider="propline", over_odds=-105),
            _line(2, provider="boltodds", over_odds=-115),
        ],
        NOW,
    )

    assert len(official_rows) == 1
    official = official_rows[0]
    assert official["selected_provider"] == "boltodds"
    assert official["ref_book_key"] == "fanduel"
    assert official["ref_over_odds"] == -115
    assert official["book_odds"]["FanDuel"]["provider"] == "boltodds"
    assert "boltodds_primary" in official["arbitration_reasons"]
    assert decision_rows[0]["decision"] == "use"


def test_propline_draftkings_is_used_when_boltodds_has_no_draftkings():
    official_rows, _ = choose_official_lines(
        [
            _line(1, provider="boltodds", book_key="betmgm", book_name="BetMGM"),
            _line(
                2,
                provider="propline",
                book_key="draftkings",
                book_name="DraftKings",
                over_odds=100,
                under_odds=-120,
            ),
        ],
        NOW,
    )

    official = official_rows[0]
    assert official["ref_book_key"] == "draftkings"
    assert official["selected_provider"] == "propline"
    assert official["book_odds"]["DraftKings"]["provider"] == "propline"
    assert "propline_draftkings" in official["arbitration_reasons"]


def test_stale_boltodds_is_rejected_in_favor_of_fresh_propline():
    official_rows, decision_rows = choose_official_lines(
        [
            _line(1, provider="boltodds", freshness_seconds=1800, quality_flags=["stale"]),
            _line(2, provider="propline", freshness_seconds=90, over_odds=-102),
        ],
        NOW,
        stale_after_seconds=900,
    )

    official = official_rows[0]
    assert official["selected_provider"] == "propline"
    assert official["ref_over_odds"] == -102
    assert decision_rows[0]["stale_candidate_count"] == 1


def test_only_kalshi_is_skipped_because_it_is_not_supported():
    official_rows, decision_rows = choose_official_lines(
        [
            _line(1, book_key="kalshi", book_name="Kalshi"),
        ],
        NOW,
    )

    assert len(official_rows) == 1
    assert official_rows[0]["ready_for_pipeline"] is False
    assert official_rows[0]["quality_flags"] == ["not_ready_for_pipeline", "no_supported_rows"]
    assert decision_rows == [{
        "slate_date": "2026-05-13",
        "normalized_player_name": "jose berrios",
        "market_key": "pitcher_strikeouts",
        "selected_provider": None,
        "selected_book_key": None,
        "selected_line": None,
        "decision": "skip",
        "reasons": ["no_supported_rows"],
        "candidate_count": 0,
        "stale_candidate_count": 0,
        "missing_book_keys": ["fanduel", "draftkings", "betmgm", "betrivers", "caesars"],
        "source_line_ids": [],
    }]


def test_one_sided_over_line_is_skipped():
    official_rows, decision_rows = choose_official_lines(
        [
            _line(1, under_odds=None, is_complete=False, quality_flags=["missing_under"]),
        ],
        NOW,
    )

    assert len(official_rows) == 1
    assert official_rows[0]["ready_for_pipeline"] is False
    assert official_rows[0]["ref_book_key"] is None
    assert decision_rows[0]["decision"] == "skip"
    assert decision_rows[0]["reasons"] == ["no_complete_line"]
    assert decision_rows[0]["candidate_count"] == 1


def test_cross_book_line_conflicts_are_preserved_with_ref_priority():
    official_rows, _ = choose_official_lines(
        [
            _line(1, book_key="fanduel", book_name="FanDuel", line=5.5),
            _line(2, book_key="draftkings", book_name="DraftKings", provider="propline", line=6.5),
        ],
        NOW,
    )

    official = official_rows[0]
    assert official["ref_book_key"] == "fanduel"
    assert official["ref_line"] == 5.5
    assert official["book_odds"]["FanDuel"]["line"] == 5.5
    assert official["book_odds"]["DraftKings"]["line"] == 6.5
    assert official["quality_flags"] == ["cross_book_line_conflict"]
    assert "cross_book_line_conflict" in official["arbitration_reasons"]


def test_decisions_explain_selected_missing_and_stale_inputs():
    _, decision_rows = choose_official_lines(
        [
            _line(1, provider="boltodds", book_key="fanduel", book_name="FanDuel"),
            _line(
                2,
                provider="propline",
                book_key="draftkings",
                book_name="DraftKings",
                freshness_seconds=2000,
                quality_flags=["stale"],
            ),
        ],
        NOW,
    )

    decision = decision_rows[0]
    assert decision["decision"] == "use"
    assert decision["selected_provider"] == "boltodds"
    assert decision["selected_book_key"] == "fanduel"
    assert decision["selected_line"] == 5.5
    assert "selected_ref_book:fanduel" in decision["reasons"]
    assert "selected_provider:boltodds" in decision["reasons"]
    assert "missing_books:draftkings,betmgm,betrivers,caesars" in decision["reasons"]
    assert decision["stale_candidate_count"] == 1
    assert decision["source_line_ids"] == [1]


def test_the_odds_is_blocked_unless_emergency_mode_is_enabled():
    current_rows = [
        _line(1, provider="the_odds", book_key="fanduel", book_name="FanDuel"),
    ]

    blocked_rows, blocked_decisions = choose_official_lines(current_rows, NOW)
    assert blocked_rows[0]["ready_for_pipeline"] is False
    assert blocked_decisions[0]["decision"] == "skip"

    emergency_rows, emergency_decisions = choose_official_lines(
        current_rows,
        NOW,
        allow_the_odds_emergency=True,
    )
    assert emergency_rows[0]["ready_for_pipeline"] is True
    assert emergency_rows[0]["selected_provider"] == "the_odds"
    assert emergency_decisions[0]["decision"] == "use"


def test_the_odds_emergency_is_limited_to_fanduel_and_draftkings():
    official_rows, decision_rows = choose_official_lines(
        [
            _line(1, provider="the_odds", book_key="betmgm", book_name="BetMGM"),
        ],
        NOW,
        allow_the_odds_emergency=True,
    )

    assert official_rows[0]["ready_for_pipeline"] is False
    assert decision_rows[0]["decision"] == "skip"


def test_draftkings_keeps_propline_until_boltodds_draftkings_is_enabled():
    current_rows = [
        _line(1, provider="boltodds", book_key="draftkings", book_name="DraftKings", over_odds=-130),
        _line(2, provider="propline", book_key="draftkings", book_name="DraftKings", over_odds=-105),
    ]

    default_rows, _ = choose_official_lines(current_rows, NOW)
    assert default_rows[0]["selected_provider"] == "propline"
    assert default_rows[0]["ref_over_odds"] == -105

    enabled_rows, _ = choose_official_lines(
        current_rows,
        NOW,
        boltodds_draftkings_enabled=True,
    )
    assert enabled_rows[0]["selected_provider"] == "boltodds"
    assert enabled_rows[0]["ref_over_odds"] == -130


def test_missing_freshness_is_not_treated_as_fresh():
    row = _line(1)
    row.pop("freshness_seconds")
    row.pop("last_seen_at")

    official_rows, decision_rows = choose_official_lines([row], NOW)

    assert official_rows[0]["ready_for_pipeline"] is False
    assert decision_rows[0]["decision"] == "skip"
    assert decision_rows[0]["stale_candidate_count"] == 1


def test_freshness_is_recomputed_from_last_seen_at():
    row = _line(1, freshness_seconds=60)
    row["freshness_seconds"] = 60
    row["last_seen_at"] = "2026-05-13T18:00:00+00:00"

    official_rows, decision_rows = choose_official_lines([row], NOW, stale_after_seconds=900)

    assert official_rows[0]["ready_for_pipeline"] is False
    assert decision_rows[0]["decision"] == "skip"
    assert decision_rows[0]["stale_candidate_count"] == 1


def test_retire_missing_official_lines_marks_existing_ready_rows_inactive():
    retired_rows, decision_rows = retire_missing_official_lines(
        official_rows=[],
        existing_official_rows=[{
            "slate_date": "2026-05-13",
            "normalized_player_name": "jose berrios",
            "player_name": "Jose Berrios",
            "market_key": "pitcher_strikeouts",
            "ready_for_pipeline": True,
            "current_market_line_ids": [123],
        }],
        now_utc=NOW,
    )

    assert len(retired_rows) == 1
    assert retired_rows[0]["ready_for_pipeline"] is False
    assert retired_rows[0]["arbitration_reasons"] == ["missing_from_current_market_lines"]
    assert retired_rows[0]["current_market_line_ids"] == [123]
    assert decision_rows[0]["decision"] == "skip"
    assert decision_rows[0]["source_line_ids"] == [123]


def test_retire_missing_official_lines_keeps_rows_seen_in_current_build():
    official_rows, _ = choose_official_lines([_line(1)], NOW)

    retired_rows, decision_rows = retire_missing_official_lines(
        official_rows=official_rows,
        existing_official_rows=[{
            "slate_date": "2026-05-13",
            "normalized_player_name": "jose berrios",
            "player_name": "Jose Berrios",
            "market_key": "pitcher_strikeouts",
            "ready_for_pipeline": True,
        }],
        now_utc=NOW,
    )

    assert retired_rows == []
    assert decision_rows == []
