from datetime import datetime, timezone

from analytics.diagnostics.provider_cutover_shadow_compare import (
    _extract_cli_rows,
    _load_provider_inputs_via_cli,
    _provider_usage_from_rows,
    compare_provider_cutover,
    format_markdown_report,
)
from pipeline.fetch_provider_market_odds import official_row_to_prop


NOW = datetime(2026, 5, 13, 20, 0, tzinfo=timezone.utc)


def _official_row():
    return {
        "id": 101,
        "slate_date": "2026-06-19",
        "market_key": "pitcher_strikeouts",
        "ready_for_pipeline": True,
        "player_name": "Jose Berrios",
        "normalized_player_name": "jose berrios",
        "ref_book_name": "FanDuel",
        "ref_book_key": "fanduel",
        "ref_line": 5.5,
        "ref_over_odds": -115,
        "ref_under_odds": -105,
        "game_time": "2026-06-19T23:05:00Z",
        "book_odds": {
            "FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "therundown"},
            "DraftKings": {"line": 5.5, "over": -112, "under": -108, "provider": "propline"},
        },
        "selected_provider": "therundown",
        "current_market_line_ids": [201, 202],
        "provider_coverage": {
            "fanduel": {"provider": "therundown", "book": "FanDuel"},
            "draftkings": {"provider": "propline", "book": "DraftKings"},
        },
        "arbitration_reasons": [],
    }


def _opening_baseline_row():
    return {
        "slate_date": "2026-06-19",
        "market_key": "pitcher_strikeouts",
        "normalized_player_name": "jose berrios",
        "book_name": "FanDuel",
        "book_key": "fanduel",
        "line": 5.5,
        "opening_over_odds": -110,
        "opening_under_odds": -110,
        "opening_source": "preview",
        "first_seen_at": "2026-06-19T05:00:00Z",
    }


def _current_line_row():
    return {
        "id": 201,
        "slate_date": "2026-06-19",
        "provider": "therundown",
        "book_key": "fanduel",
        "book_name": "FanDuel",
        "player_name": "Jose Berrios",
        "normalized_player_name": "jose berrios",
        "market_key": "pitcher_strikeouts",
        "line": 5.5,
        "over_odds": -115,
        "under_odds": -105,
        "last_seen_at": "2026-06-19T19:59:00+00:00",
        "is_complete": True,
        "quality_flags": [],
    }


def _heartbeat_row():
    return {
        "provider": "therundown",
        "slate_date": "2026-06-19",
        "observed_at": "2026-06-19T19:59:50+00:00",
        "last_message_at": "2026-06-19T19:59:45+00:00",
        "books_seen": ["fanduel"],
        "metadata": {"event": "poll"},
    }


def _usage_row():
    return {
        "provider": "propline",
        "request_count": 42,
        "snapshot_count": 300,
        "source": "scripts/shadow_propline_to_supabase.py",
        "updated_at": "2026-06-19T19:59:00Z",
    }


def _cli_runner_with(rows_by_table, failures=()):
    def fake_runner(command):
        sql = command[-1]
        for table in failures:
            if f"public.{table}" in sql:
                raise RuntimeError(f"{table} failed")
        for table, rows in rows_by_table.items():
            if f"public.{table}" in sql:
                return {"rows": rows}
        raise AssertionError(f"unexpected SQL: {sql}")

    return fake_runner


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
        "market_source_mode": "therundown_propline",
        "line_source_provider": "therundown",
        "provider_coverage": {
            ref_book.lower(): {"provider": odds_source, "book": ref_book},
        },
        "provider_arbitration_reasons": reasons or [],
        "source_line_ids": [101],
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
                odds_source="therundown+propline",
                book_odds={
                    "FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "therundown"},
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
    gate_statuses = {gate["name"]: gate["status"] for gate in report["readiness"]["gates"]}
    assert gate_statuses["official_provider_pitcher_coverage_90"] == "fail"


def test_linked_cli_fallback_builds_provider_props_and_current_lines():
    inputs = _load_provider_inputs_via_cli(
        date_str="2026-06-19",
        min_props=1,
        cli_runner=_cli_runner_with({
            "official_market_lines": [_official_row()],
            "market_opening_baselines": [_opening_baseline_row()],
            "current_market_lines": [_current_line_row()],
            "market_feed_heartbeats": [_heartbeat_row()],
            "provider_request_usage_daily": [_usage_row()],
        }),
    )

    assert len(inputs["provider_props"]) == 1
    assert len(inputs["provider_current_lines"]) == 1
    assert len(inputs["provider_heartbeats"]) == 1
    assert inputs["provider_usage"]["propline_requests"] == 42
    assert inputs["warnings"] == []

    report = compare_provider_cutover(
        date_str="2026-06-19",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=inputs["provider_props"],
        provider_current_lines=inputs["provider_current_lines"],
        provider_heartbeats=inputs["provider_heartbeats"],
        provider_usage=inputs["provider_usage"],
        provider_input_warnings=inputs["warnings"],
        generated_at=NOW,
    )

    assert report["input_availability"]["provider_evidence_available"] is True
    assert report["input_availability"]["provider_current_lines_available"] is True
    assert report["summary"]["provider_pitcher_count"] == 1
    assert report["mainline_selection"]["raw_candidate_count"] == 1


def test_linked_cli_fallback_marks_provider_gates_unknown_when_required_reads_fail():
    required_tables = {
        "official_market_lines",
        "market_opening_baselines",
        "current_market_lines",
        "market_feed_heartbeats",
    }
    inputs = _load_provider_inputs_via_cli(
        date_str="2026-06-19",
        min_props=1,
        cli_runner=_cli_runner_with(
            {"provider_request_usage_daily": [_usage_row()]},
            failures=required_tables,
        ),
    )

    report = compare_provider_cutover(
        date_str="2026-06-19",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=inputs["provider_props"],
        scheduled_pitchers=[{"pitcher": "Jose Berrios"}],
        provider_current_lines=inputs["provider_current_lines"],
        provider_heartbeats=inputs["provider_heartbeats"],
        provider_usage=inputs["provider_usage"],
        provider_input_warnings=inputs["warnings"],
        generated_at=NOW,
    )

    gate_statuses = {gate["name"]: gate["status"] for gate in report["readiness"]["gates"]}
    assert gate_statuses["official_provider_pitcher_coverage_90"] == "unknown"
    assert gate_statuses["official_provider_fd_or_dk_coverage_85"] == "unknown"
    assert gate_statuses["official_rows_ready_for_pipeline_90"] == "unknown"
    assert gate_statuses["prop_contract_valid"] == "unknown"
    assert report["input_availability"]["provider_evidence_available"] is False
    assert any(warning["status"] == "unavailable" for warning in inputs["warnings"])


def test_linked_cli_usage_failure_does_not_block_provider_evidence():
    inputs = _load_provider_inputs_via_cli(
        date_str="2026-06-19",
        min_props=1,
        cli_runner=_cli_runner_with(
            {
                "official_market_lines": [_official_row()],
                "market_opening_baselines": [_opening_baseline_row()],
                "current_market_lines": [_current_line_row()],
                "market_feed_heartbeats": [_heartbeat_row()],
            },
            failures={"provider_request_usage_daily"},
        ),
    )

    report = compare_provider_cutover(
        date_str="2026-06-19",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=inputs["provider_props"],
        provider_current_lines=inputs["provider_current_lines"],
        provider_heartbeats=inputs["provider_heartbeats"],
        provider_usage=inputs["provider_usage"],
        provider_input_warnings=inputs["warnings"],
        generated_at=NOW,
    )

    assert inputs["provider_usage"] is None
    assert report["input_availability"]["provider_evidence_available"] is True
    assert {warning["status"] for warning in inputs["warnings"]} == {"warning"}
    gate_statuses = {gate["name"]: gate["status"] for gate in report["readiness"]["gates"]}
    assert gate_statuses["official_provider_pitcher_coverage_90"] == "pass"


def test_linked_cli_payload_parser_rejects_malformed_shape():
    try:
        _extract_cli_rows({"data": []})
    except ValueError as error:
        assert "missing rows" in str(error)
    else:
        raise AssertionError("malformed CLI payload should raise")


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
                odds_source="therundown+propline",
                book_odds={
                    "FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "therundown"},
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
    assert gate_statuses["official_provider_pitcher_coverage_90"] == "fail"


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


def test_compare_mainline_coverage_uses_fresh_boltodds_heartbeat_hold():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        scheduled_pitchers=[
            {"pitcher": "Jose Berrios", "team": "Blue Jays"},
        ],
        rundown_props=[
            _prop("Jose Berrios"),
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
                "last_seen_at": "2026-05-13T19:30:00+00:00",
                "is_complete": True,
                "quality_flags": ["stale"],
            },
        ],
        provider_heartbeats=[
            {
                "provider": "boltodds",
                "mode": "shadow_stream",
                "slate_date": "2026-05-13",
                "observed_at": "2026-05-13T19:59:50+00:00",
                "last_message_at": "2026-05-13T19:59:45+00:00",
                "books_seen": ["fanduel"],
                "metadata": {"event": "message"},
            },
        ],
        generated_at=NOW,
    )

    schedule = report["schedule_first"]
    assert schedule["provider_raw_covered_count"] == 1
    assert schedule["provider_mainline_ready_count"] == 1
    assert schedule["provider_official_ready_count"] == 1


def test_compare_tracks_missing_draftkings_and_line_conflicts():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[
            _prop(
                "Jose Berrios",
                book_odds={"FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "therundown"}},
                reasons=["cross_book_line_conflict"],
            ),
        ],
        generated_at=NOW,
    )

    assert report["coverage"]["missing_draftkings_pitchers"] == ["jose berrios"]
    assert report["coverage"]["line_conflict_pitchers"] == ["jose berrios"]
    assert report["summary"]["line_conflict_rate"] == 1.0
    gate_statuses = {gate["name"]: gate["status"] for gate in report["readiness"]["gates"]}
    assert gate_statuses["line_conflict_rate_under_10"] == "fail"


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
                book_odds={"FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "therundown"}},
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
        "provider": "therundown",
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
    assert gate_statuses["prop_contract_valid"] == "fail"
    assert gate_statuses["propline_usage_under_70_percent_hobby"] == "fail"
    assert report["summary"]["provider_contract_issue_count"] == 1


def test_prop_contract_requires_provider_provenance_fields():
    row = _prop("Jose Berrios")
    for field in (
        "odds_source",
        "market_source_mode",
        "line_source_provider",
        "provider_coverage",
        "provider_arbitration_reasons",
        "source_line_ids",
    ):
        row.pop(field, None)

    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[row],
        generated_at=NOW,
    )

    issue = report["artifact_contract"]["provider_contract_issues"][0]
    assert issue["missing_fields"] == [
        "odds_source",
        "market_source_mode",
        "line_source_provider",
        "provider_coverage",
        "provider_arbitration_reasons",
        "source_line_ids",
    ]
    gate_statuses = {gate["name"]: gate["status"] for gate in report["readiness"]["gates"]}
    assert gate_statuses["prop_contract_valid"] == "fail"


def test_converted_official_row_with_source_line_alias_satisfies_prop_contract(monkeypatch):
    monkeypatch.setenv("OFFICIAL_MARKET_SOURCE", "therundown_propline")
    provider_prop = official_row_to_prop(_official_row(), {})

    assert provider_prop["source_line_ids"] == [201, 202]

    report = compare_provider_cutover(
        date_str="2026-06-19",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[provider_prop],
        generated_at=NOW,
    )

    assert report["artifact_contract"]["provider_contract_issues"] == []
    gate_statuses = {gate["name"]: gate["status"] for gate in report["readiness"]["gates"]}
    assert gate_statuses["prop_contract_valid"] == "pass"


def test_unavailable_provider_inputs_make_provider_gates_unknown():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[],
        scheduled_pitchers=[{"pitcher": "Jose Berrios", "team": "Blue Jays"}],
        provider_current_lines=None,
        provider_heartbeats=None,
        provider_input_warnings=[
            {
                "source": "supabase",
                "status": "unavailable",
                "message": "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required",
            }
        ],
        generated_at=NOW,
    )

    gate_statuses = {gate["name"]: gate["status"] for gate in report["readiness"]["gates"]}
    assert gate_statuses["official_provider_pitcher_coverage_90"] == "unknown"
    assert gate_statuses["official_provider_fd_or_dk_coverage_85"] == "unknown"
    assert gate_statuses["official_rows_ready_for_pipeline_90"] == "unknown"
    assert gate_statuses["prop_contract_valid"] == "unknown"
    assert gate_statuses["no_boltodds_active_rows"] == "unknown"
    assert report["input_availability"]["provider_evidence_available"] is False
    assert report["input_availability"]["warnings"][0]["status"] == "unavailable"


def test_markdown_report_warns_when_provider_inputs_unavailable():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[],
        provider_input_warnings=[
            {
                "source": "supabase",
                "status": "unavailable",
                "message": "provider Supabase writer unavailable",
            }
        ],
        generated_at=NOW,
    )

    markdown = format_markdown_report(report)

    assert "## Input Availability" in markdown
    assert "Provider Supabase evidence: **unavailable/partial**" in markdown
    assert "provider Supabase writer unavailable" in markdown
    assert "Provider pitchers: 0" in markdown
    assert "not proof that TheRundown + PropLine provider evidence failed" in markdown


def test_provider_usage_rows_feed_hobby_budget_gate():
    usage = _provider_usage_from_rows([
        {
            "provider": "propline",
            "request_count": 304,
            "snapshot_count": 2622,
            "source": "scripts/shadow_propline_to_supabase.py",
        },
        {
            "provider": "boltodds",
            "request_count": 4,
            "snapshot_count": 1477,
            "source": "scripts/boltodds_ws_worker.py",
        },
    ])

    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[_prop("Jose Berrios")],
        provider_usage=usage,
        generated_at=NOW,
    )

    gate_statuses = {gate["name"]: gate for gate in report["readiness"]["gates"]}
    assert usage["propline_requests"] == 304
    assert usage["propline_snapshots"] == 2622
    assert usage["boltodds_requests"] == 4
    assert gate_statuses["propline_usage_under_70_percent_hobby"]["status"] == "pass"
    assert gate_statuses["propline_usage_under_70_percent_hobby"]["value"] == 0.0608


def test_readiness_gates_use_therundown_propline_official_contract():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[_prop("Jose Berrios", odds_source="therundown+propline")],
        provider_current_lines=[
            {
                "id": 1,
                "slate_date": "2026-05-13",
                "provider": "therundown",
                "book_name": "FanDuel",
                "player_name": "Jose Berrios",
                "normalized_player_name": "jose berrios",
                "market_key": "pitcher_strikeouts",
                "line": 5.5,
                "over_odds": -115,
                "under_odds": -105,
                "last_seen_at": "2026-05-13T19:59:00+00:00",
                "is_complete": True,
                "quality_flags": [],
            },
        ],
        provider_usage={"propline_requests": 300},
        generated_at=NOW,
    )

    gate_names = [gate["name"] for gate in report["readiness"]["gates"]]
    assert gate_names == [
        "official_provider_pitcher_coverage_90",
        "official_provider_fd_or_dk_coverage_85",
        "official_rows_ready_for_pipeline_90",
        "line_conflict_rate_under_10",
        "prop_contract_valid",
        "propline_usage_under_70_percent_hobby",
        "no_boltodds_active_rows",
    ]
    assert {gate["name"]: gate["status"] for gate in report["readiness"]["gates"]}[
        "no_boltodds_active_rows"
    ] == "pass"


def test_no_boltodds_active_rows_gate_fails_when_current_lines_include_boltodds():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[_prop("Jose Berrios", odds_source="therundown+propline")],
        provider_current_lines=[
            {
                "id": 1,
                "slate_date": "2026-05-13",
                "provider": "boltodds",
                "book_name": "FanDuel",
                "player_name": "Jose Berrios",
                "normalized_player_name": "jose berrios",
                "market_key": "pitcher_strikeouts",
                "line": 5.5,
                "over_odds": -115,
                "under_odds": -105,
                "last_seen_at": "2026-05-13T19:59:00+00:00",
                "is_complete": True,
                "quality_flags": [],
            },
        ],
        generated_at=NOW,
    )

    gate_statuses = {gate["name"]: gate for gate in report["readiness"]["gates"]}
    assert gate_statuses["no_boltodds_active_rows"]["status"] == "fail"
    assert gate_statuses["no_boltodds_active_rows"]["value"] == 1


def test_markdown_report_includes_gate_summary():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[_prop("Jose Berrios")],
        generated_at=NOW,
    )

    markdown = format_markdown_report(report)

    assert "# TheRundown + PropLine Official Provider Parity - 2026-05-13" in markdown
    assert "Schedule-First Coverage" in markdown
    assert "official_provider_pitcher_coverage_90" in markdown
    assert "Overall ready" in markdown


def test_markdown_report_names_therundown_propline_official_parity():
    report = compare_provider_cutover(
        date_str="2026-05-13",
        rundown_props=[_prop("Jose Berrios")],
        provider_props=[_prop("Jose Berrios", odds_source="therundown+propline")],
        generated_at=NOW,
    )

    markdown = format_markdown_report(report)

    assert "TheRundown + PropLine Official Provider Parity" in markdown
    assert "BoltOdds + PropLine" not in markdown.splitlines()[0]
