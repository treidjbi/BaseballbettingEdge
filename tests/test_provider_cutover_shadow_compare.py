from datetime import datetime, timezone

from analytics.diagnostics.provider_cutover_shadow_compare import (
    compare_provider_cutover,
    format_markdown_report,
)


NOW = datetime(2026, 5, 13, 20, 0, tzinfo=timezone.utc)


def _prop(
    pitcher,
    *,
    line=5.5,
    ref_book="FanDuel",
    over=-115,
    under=-105,
    book_odds=None,
    odds_source="therundown",
    reasons=None,
    ev_over=None,
    ev_under=None,
):
    return {
        "pitcher": pitcher,
        "team": "",
        "opp_team": "",
        "game_time": "2026-05-13T23:05:00Z",
        "k_line": line,
        "opening_line": line,
        "ref_book": ref_book,
        "best_over_book": ref_book,
        "best_under_book": ref_book,
        "best_over_odds": over,
        "best_under_odds": under,
        "opening_over_odds": over,
        "opening_under_odds": under,
        "opening_odds_source": "first_seen",
        "book_odds": book_odds if book_odds is not None else {
            ref_book: {"line": line, "over": over, "under": under, "provider": odds_source},
        },
        "odds_source": odds_source,
        "provider_arbitration_reasons": reasons or [],
        "ev_over": ev_over or {"verdict": "PASS"},
        "ev_under": ev_under or {"verdict": "PASS"},
    }


def test_compare_reports_pitcher_and_fd_dk_coverage():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[
            _prop("Jose Berrios"),
            _prop("Gerrit Cole"),
        ],
        provider_props=[
            _prop(
                "Jose Berrios",
                odds_source="boltodds+propline",
                book_odds={
                    "FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "boltodds"},
                    "DraftKings": {"line": 5.5, "over": -112, "under": -108, "provider": "propline"},
                },
            ),
        ],
        generated_at=NOW,
    )

    assert report["summary"]["production_pitcher_count"] == 2
    assert report["summary"]["provider_pitcher_count"] == 1
    assert report["summary"]["pitcher_coverage_rate"] == 0.5
    assert report["summary"]["fd_or_dk_coverage_rate"] == 0.5
    assert report["coverage"]["missing_provider_pitchers"] == ["gerrit cole"]
    assert report["coverage"]["missing_draftkings_pitchers"] == []
    assert report["readiness"]["gates"][0]["status"] == "fail"


def test_compare_reports_schedule_first_provider_coverage():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        scheduled_pitchers=[
            {"pitcher": "Jose Berrios", "team": "Blue Jays"},
            {"pitcher": "Gerrit Cole", "team": "Yankees"},
            {"pitcher": "Missing Arm", "team": "Mets"},
        ],
        rundown_props=[
            _prop("Jose Berrios"),
            _prop("Gerrit Cole"),
        ],
        provider_props=[
            _prop(
                "Jose Berrios",
                odds_source="boltodds+propline",
                book_odds={
                    "FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "boltodds"},
                    "DraftKings": {"line": 5.5, "over": -112, "under": -108, "provider": "propline"},
                },
            ),
        ],
        generated_at=NOW,
    )

    schedule = report["schedule_first"]
    assert schedule["scheduled_pitcher_count"] == 3
    assert schedule["rundown_covered_count"] == 2
    assert schedule["provider_covered_count"] == 1
    assert schedule["provider_draftkings_count"] == 1
    assert schedule["provider_at_least_2_books_count"] == 1
    assert schedule["missing_provider_pitchers"] == ["gerrit cole", "missing arm"]
    assert schedule["missing_rundown_pitchers"] == ["missing arm"]

    gate_statuses = {gate["name"]: gate["status"] for gate in report["readiness"]["gates"]}
    assert gate_statuses["schedule_provider_coverage_90"] == "fail"


def test_compare_reports_raw_mainline_and_official_schedule_coverage():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        scheduled_pitchers=[
            {"pitcher": "Jose Berrios", "team": "Blue Jays"},
            {"pitcher": "Gerrit Cole", "team": "Yankees"},
        ],
        rundown_props=[
            _prop("Jose Berrios"),
            _prop("Gerrit Cole"),
        ],
        provider_props=[
            _prop("Jose Berrios", odds_source="boltodds+propline"),
        ],
        provider_current_lines=[
            {
                "id": 1,
                "slate_date": "2026-05-13",
                "provider": "boltodds",
                "book_key": "fanduel",
                "book_name": "FanDuel",
                "player_name": "Jose Berrios",
                "normalized_player_name": "jose berrios",
                "market_key": "pitcher_strikeouts",
                "line": 5.5,
                "over_odds": -110,
                "under_odds": -110,
                "last_seen_at": "2026-05-13T19:59:00+00:00",
                "is_complete": True,
                "quality_flags": ["line_conflict"],
            },
            {
                "id": 2,
                "slate_date": "2026-05-13",
                "provider": "boltodds",
                "book_key": "fanduel",
                "book_name": "FanDuel",
                "player_name": "Jose Berrios",
                "normalized_player_name": "jose berrios",
                "market_key": "pitcher_strikeouts",
                "line": 6.5,
                "over_odds": 140,
                "under_odds": -180,
                "last_seen_at": "2026-05-13T19:59:00+00:00",
                "is_complete": True,
                "quality_flags": ["line_conflict"],
            },
            {
                "id": 3,
                "slate_date": "2026-05-13",
                "provider": "propline",
                "book_key": "fanduel",
                "book_name": "FanDuel",
                "player_name": "Jose Berrios",
                "normalized_player_name": "jose berrios",
                "market_key": "pitcher_strikeouts",
                "line": 5.5,
                "over_odds": -112,
                "under_odds": -108,
                "last_seen_at": "2026-05-13T19:59:00+00:00",
                "is_complete": True,
                "quality_flags": [],
            },
            {
                "id": 4,
                "slate_date": "2026-05-13",
                "provider": "boltodds",
                "book_key": "fanduel",
                "book_name": "FanDuel",
                "player_name": "Gerrit Cole",
                "normalized_player_name": "gerrit cole",
                "market_key": "pitcher_strikeouts",
                "line": 6.5,
                "over_odds": -110,
                "under_odds": -110,
                "last_seen_at": "2026-05-13T19:59:00+00:00",
                "is_complete": True,
                "quality_flags": ["line_conflict"],
            },
            {
                "id": 5,
                "slate_date": "2026-05-13",
                "provider": "boltodds",
                "book_key": "fanduel",
                "book_name": "FanDuel",
                "player_name": "Gerrit Cole",
                "normalized_player_name": "gerrit cole",
                "market_key": "pitcher_strikeouts",
                "line": 7.5,
                "over_odds": 135,
                "under_odds": -165,
                "last_seen_at": "2026-05-13T19:59:00+00:00",
                "is_complete": True,
                "quality_flags": ["line_conflict"],
            },
        ],
        generated_at=NOW,
    )

    schedule = report["schedule_first"]
    assert schedule["provider_raw_covered_count"] == 2
    assert schedule["provider_mainline_ready_count"] == 1
    assert schedule["provider_official_ready_count"] == 1
    assert schedule["provider_raw_coverage_rate"] == 1.0
    assert schedule["provider_mainline_ready_rate"] == 0.5
    assert schedule["provider_official_ready_rate"] == 0.5
    assert report["coverage"]["ambiguous_mainline_pitchers"] == ["gerrit cole"]


def test_compare_tracks_missing_draftkings_and_line_conflicts():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[
            _prop(
                "Jose Berrios",
                book_odds={"FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "boltodds"}},
                reasons=["cross_book_line_conflict"],
            ),
        ],
        generated_at=NOW,
    )

    assert report["coverage"]["missing_draftkings_pitchers"] == ["jose berrios"]
    assert report["coverage"]["line_conflict_pitchers"] == ["jose berrios"]
    assert report["summary"]["line_conflict_rate"] == 1.0
    assert report["readiness"]["gates"][2]["status"] == "fail"


def test_compare_reports_ref_book_changes_and_odds_deltas():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[
            _prop(
                "Jose Berrios",
                ref_book="BetMGM",
                over=-110,
                under=-110,
                book_odds={"FanDuel": {"line": 5.5, "over": -120, "under": 100}},
            )
        ],
        provider_props=[
            _prop(
                "Jose Berrios",
                ref_book="FanDuel",
                over=-115,
                under=-105,
                book_odds={"FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "boltodds"}},
            )
        ],
        generated_at=NOW,
    )

    assert report["market_differences"]["ref_book_changes"] == [{
        "pitcher": "Jose Berrios",
        "rundown_ref_book": "BetMGM",
        "provider_ref_book": "FanDuel",
    }]
    assert report["market_differences"]["odds_deltas_by_book"] == [{
        "pitcher": "Jose Berrios",
        "book": "FanDuel",
        "same_line": True,
        "rundown_line": 5.5,
        "provider_line": 5.5,
        "over_delta": 5,
        "under_delta": -205,
        "provider": "boltodds",
    }]


def test_compare_reports_verdict_changes_when_records_have_verdicts():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios", ev_over={"verdict": "PASS"})],
        provider_props=[_prop("Jose Berrios", ev_over={"verdict": "FIRE 1u"})],
        generated_at=NOW,
    )

    assert report["summary"]["verdict_change_count"] == 1
    assert report["market_differences"]["verdict_changes"] == [{
        "pitcher": "Jose Berrios",
        "side": "over",
        "rundown_verdict": "PASS",
        "provider_verdict": "FIRE 1u",
    }]


def test_compare_contract_and_usage_gates():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[{**_prop("Jose Berrios"), "book_odds": None}],
        provider_usage={"propline_requests": 4000},
        generated_at=NOW,
    )

    gate_statuses = {gate["name"]: gate["status"] for gate in report["readiness"]["gates"]}
    assert gate_statuses["today_contract_valid"] == "fail"
    assert gate_statuses["propline_usage_under_70pct_hobby"] == "fail"
    assert report["summary"]["provider_contract_issue_count"] == 1


def test_markdown_report_includes_gate_summary():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[_prop("Jose Berrios")],
        generated_at=NOW,
    )

    markdown = format_markdown_report(report)

    assert "# Provider Cutover Shadow Compare - 2026-05-13" in markdown
    assert "Schedule-First Coverage" in markdown
    assert "pitcher_coverage_90" in markdown
    assert "Overall ready" in markdown
