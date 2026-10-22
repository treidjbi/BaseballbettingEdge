from datetime import datetime, timezone

from analytics.diagnostics.executable_market_shadow_audit import (
    build_executable_market_shadow,
    format_markdown_report,
)


NOW = datetime(2026, 5, 15, 20, 0, tzinfo=timezone.utc)


def _model_row(pitcher="Example Pitcher", *, line=4.5, raw_lambda=5.5):
    return {
        "pitcher": pitcher,
        "k_line": line,
        "raw_lambda": raw_lambda,
        "lambda": raw_lambda,
        "best_over_book": "FanDuel",
        "best_under_book": "FanDuel",
        "best_over_odds": -110,
        "best_under_odds": -110,
        "ev_over": {"adj_ev": 0.05, "ev": 0.05, "verdict": "LEAN"},
        "ev_under": {"adj_ev": -0.2, "ev": -0.2, "verdict": "PASS"},
    }


def _line(
    pitcher="Example Pitcher",
    *,
    book_key="fanduel",
    book_name="FanDuel",
    line=4.5,
    over=-110,
    under=-110,
    provider="boltodds",
    is_complete=True,
    freshness_seconds=30,
):
    return {
        "id": hash((pitcher, book_key, line)) % 100000,
        "slate_date": "2026-05-15",
        "provider": provider,
        "book_key": book_key,
        "book_name": book_name,
        "player_name": pitcher,
        "normalized_player_name": pitcher.lower(),
        "market_key": "pitcher_strikeouts",
        "line": line,
        "over_odds": over,
        "under_odds": under,
        "last_seen_at": "2026-05-15T19:59:00+00:00",
        "freshness_seconds": freshness_seconds,
        "is_complete": is_complete,
        "quality_flags": [],
    }


def test_shadow_scores_each_supported_book_line_and_side():
    report = build_executable_market_shadow(
        date_str="2026-05-15",
        model_rows=[_model_row(raw_lambda=5.5)],
        current_market_lines=[
            _line(book_key="fanduel", book_name="FanDuel", line=4.5, over=-110, under=-110),
            _line(book_key="betrivers", book_name="BetRivers", line=3.5, over=-170, under=130),
        ],
        params={"lambda_bias": 0.0},
        generated_at=NOW,
    )

    best = report["best_candidates"][0]

    assert report["summary"]["model_pitcher_count"] == 1
    assert report["summary"]["pitchers_with_candidates"] == 1
    assert report["summary"]["total_candidate_count"] == 4
    assert best["pitcher"] == "Example Pitcher"
    assert best["side"] == "over"
    assert best["book_name"] == "BetRivers"
    assert best["line"] == 3.5
    assert best["line_value_vs_official"] == "better_than_official"


def test_shadow_classifies_ref_vs_majority_conflict_separately_from_outlier():
    ref_vs_majority = build_executable_market_shadow(
        date_str="2026-05-15",
        model_rows=[_model_row("Aaron Civale", line=4.5, raw_lambda=4.4)],
        current_market_lines=[
            _line("Aaron Civale", book_key="fanduel", book_name="FanDuel", line=4.5),
            _line("Aaron Civale", book_key="betmgm", book_name="BetMGM", line=3.5),
            _line("Aaron Civale", book_key="betrivers", book_name="BetRivers", line=3.5),
            _line("Aaron Civale", book_key="caesars", book_name="Caesars", line=3.5),
        ],
        generated_at=NOW,
    )
    single_outlier = build_executable_market_shadow(
        date_str="2026-05-15",
        model_rows=[_model_row("Shane Baz", line=4.5, raw_lambda=4.4)],
        current_market_lines=[
            _line("Shane Baz", book_key="fanduel", book_name="FanDuel", line=4.5),
            _line("Shane Baz", book_key="betrivers", book_name="BetRivers", line=4.5),
            _line("Shane Baz", book_key="caesars", book_name="Caesars", line=4.5),
            _line("Shane Baz", book_key="betmgm", book_name="BetMGM", line=5.5),
        ],
        generated_at=NOW,
    )

    assert ref_vs_majority["by_pitcher"][0]["conflict_type"] == "ref_vs_majority"
    assert single_outlier["by_pitcher"][0]["conflict_type"] == "single_book_outlier"
    assert ref_vs_majority["summary"]["ref_vs_majority_conflict_count"] == 1
    assert single_outlier["summary"]["single_book_outlier_count"] == 1


def test_shadow_skips_stale_incomplete_and_unsupported_rows():
    report = build_executable_market_shadow(
        date_str="2026-05-15",
        model_rows=[_model_row()],
        current_market_lines=[
            _line(book_key="fanduel", book_name="FanDuel", line=4.5, is_complete=False),
            _line(book_key="kalshi", book_name="Kalshi", line=4.5),
            _line(book_key="betmgm", book_name="BetMGM", line=4.5, freshness_seconds=1200),
            _line(book_key="caesars", book_name="Caesars", line=4.5, over=-120, under=100),
        ],
        generated_at=NOW,
        stale_after_seconds=900,
    )

    assert report["summary"]["eligible_market_line_count"] == 1
    assert report["summary"]["total_candidate_count"] == 2
    assert {candidate["book_name"] for candidate in report["candidates"]} == {"Caesars"}


def test_markdown_report_names_shadow_only_monday_check():
    report = build_executable_market_shadow(
        date_str="2026-05-15",
        model_rows=[_model_row()],
        current_market_lines=[_line()],
        generated_at=NOW,
    )

    markdown = format_markdown_report(report, top_n=3)

    assert "# Best Executable Market Shadow Audit - 2026-05-15" in markdown
    assert "Monday cutover check" in markdown
    assert "shadow-only" in markdown
