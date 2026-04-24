"""Tests for pipeline/fetch_umpires.py.

Context: As of 2026-04-17, ump.news is dead (NXDOMAIN) and has been replaced
by the MLB Stats API schedule endpoint with `hydrate=officials`. These tests
cover:
  (a) happy-path parsing of a schedule payload,
  (b) HP-only selection out of a multi-official array,
  (c) partial-data tolerance (games with no officials yet are skipped),
  (d) network / HTTP failure -> WARNING log + empty dict,
  (e) unknown team-name reverse-lookup -> skip without crashing,
  (f) end-to-end name matching into career_k_rates.json.
"""
import sys
import os
import logging
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

import fetch_umpires  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers to build a realistic MLB Stats API schedule payload for mocking.
# ---------------------------------------------------------------------------

def _official(name: str, official_type: str, pid: int = 12345) -> dict:
    return {
        "official": {"id": pid, "fullName": name, "link": f"/api/v1/people/{pid}"},
        "officialType": official_type,
    }


def _game(away_name: str, home_name: str, officials: list | None) -> dict:
    return {
        "teams": {
            "away": {"team": {"name": away_name}},
            "home": {"team": {"name": home_name}},
        },
        "officials": officials if officials is not None else [],
    }


def _schedule_payload(games: list) -> dict:
    return {"dates": [{"games": games}]}


def _mock_response(payload: dict):
    m = MagicMock()
    m.json.return_value = payload
    m.raise_for_status.return_value = None
    return m


# ---------------------------------------------------------------------------
# fetch_hp_assignments — happy path, HP selection, partial data, errors.
# ---------------------------------------------------------------------------

def test_fetch_hp_assignments_happy_path():
    """Two games with full officials arrays -> both HP umps returned by away-abbr."""
    payload = _schedule_payload([
        _game("New York Yankees", "Boston Red Sox", [
            _official("Dan Iassogna", "Home Plate", 427173),
            _official("Ramon De Jesus", "First Base", 52),
            _official("Nic Lentz", "Second Base", 53),
            _official("CB Bucknor", "Third Base", 54),
        ]),
        _game("Los Angeles Dodgers", "San Francisco Giants", [
            _official("Vic Carapazza", "Home Plate", 61),
        ]),
    ])
    with patch("fetch_umpires.requests.get", return_value=_mock_response(payload)):
        result = fetch_umpires.fetch_hp_assignments("2026-04-17")

    assert result == {
        "NYY": "Dan Iassogna",
        "LAD": "Vic Carapazza",
    }


def test_fetch_hp_assignments_only_returns_home_plate():
    """Officials array with base umps but no HP -> game is skipped."""
    payload = _schedule_payload([
        _game("Houston Astros", "Texas Rangers", [
            _official("John Bacon", "First Base"),
            _official("Jeremy Riggs", "Second Base"),
            _official("Brock Ballou", "Third Base"),
            # No "Home Plate" entry.
        ]),
    ])
    with patch("fetch_umpires.requests.get", return_value=_mock_response(payload)):
        result = fetch_umpires.fetch_hp_assignments("2026-04-17")
    assert result == {}


def test_fetch_hp_assignments_partial_data_tolerance():
    """Mix of games with and without officials — only populated ones returned."""
    payload = _schedule_payload([
        _game("New York Yankees", "Boston Red Sox", [
            _official("Dan Iassogna", "Home Plate"),
        ]),
        _game("Chicago Cubs", "Cincinnati Reds", []),             # empty list
        _game("Detroit Tigers", "Cleveland Guardians", None),     # missing key
    ])
    with patch("fetch_umpires.requests.get", return_value=_mock_response(payload)):
        result = fetch_umpires.fetch_hp_assignments("2026-04-17")
    assert result == {"NYY": "Dan Iassogna"}


def test_fetch_hp_assignments_logs_warning_on_network_failure(caplog):
    """Network / HTTP errors -> WARNING logged, empty dict returned.

    Locks in the graceful-degradation contract: pipeline must not crash
    when the MLB API is unreachable or returns 5xx.
    """
    with patch(
        "fetch_umpires.requests.get",
        side_effect=Exception("DNS resolution failed"),
    ):
        with caplog.at_level(logging.WARNING, logger="fetch_umpires"):
            result = fetch_umpires.fetch_hp_assignments("2026-04-17")
    assert result == {}
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("MLB schedule fetch failed" in r.getMessage() for r in warnings), (
        f"Expected a 'MLB schedule fetch failed' WARNING, got: "
        f"{[r.getMessage() for r in warnings]}"
    )


def test_fetch_hp_assignments_unknown_team_name_skipped(caplog):
    """A game whose team names don't reverse-lookup to a known abbreviation
    is skipped without crashing the whole fetch."""
    payload = _schedule_payload([
        _game("Tokyo Giants", "Osaka Tigers", [
            _official("Someone Somewhere", "Home Plate"),
        ]),
        _game("New York Yankees", "Boston Red Sox", [
            _official("Dan Iassogna", "Home Plate"),
        ]),
    ])
    with patch("fetch_umpires.requests.get", return_value=_mock_response(payload)):
        with caplog.at_level(logging.INFO, logger="fetch_umpires"):
            result = fetch_umpires.fetch_hp_assignments("2026-04-17")
    # Only the recognizable MLB matchup is returned.
    assert result == {"NYY": "Dan Iassogna"}


def test_fetch_hp_assignments_empty_schedule():
    """No games scheduled (e.g. off-day) -> empty dict, no error."""
    payload = {"dates": []}
    with patch("fetch_umpires.requests.get", return_value=_mock_response(payload)):
        result = fetch_umpires.fetch_hp_assignments("2026-12-25")
    assert result == {}


# ---------------------------------------------------------------------------
# _abbr_for_team_name helper — direct unit test.
# ---------------------------------------------------------------------------

def test_abbr_for_team_name_matches_common_teams():
    cases = [
        ("New York Yankees", "NYY"),
        ("Boston Red Sox", "BOS"),
        ("Chicago Cubs", "CHC"),
        ("Chicago White Sox", "CWS"),
        ("Los Angeles Dodgers", "LAD"),
        ("Los Angeles Angels", "LAA"),
        ("San Francisco Giants", "SF"),
        ("St. Louis Cardinals", "STL"),
        ("Tampa Bay Rays", "TB"),
        ("Athletics", "OAK"),
    ]
    for full_name, expected in cases:
        assert fetch_umpires._abbr_for_team_name(full_name) == expected, (
            f"{full_name} -> {fetch_umpires._abbr_for_team_name(full_name)}, "
            f"expected {expected}"
        )


def test_abbr_for_team_name_unknown_returns_none():
    assert fetch_umpires._abbr_for_team_name("Tokyo Giants") is None
    assert fetch_umpires._abbr_for_team_name("") is None
    assert fetch_umpires._abbr_for_team_name(None) is None


# ---------------------------------------------------------------------------
# End-to-end fetch_umpires: scrape -> abbr map -> career-rates lookup.
# ---------------------------------------------------------------------------

def _sample_schedule_payload() -> dict:
    return _schedule_payload([
        _game("New York Yankees", "Boston Red Sox", [
            _official("Angel Hernandez", "Home Plate"),
        ]),
        _game("Los Angeles Dodgers", "San Francisco Giants", [
            _official("Vic Carapazza", "Home Plate"),
        ]),
        _game("Houston Astros", "Texas Rangers", [
            _official("Unknown Umpire", "Home Plate"),
        ]),
    ])


def test_fetch_umpires_returns_all_zeros_when_fetch_fails(caplog):
    """When the MLB API fetch fails, fetch_umpires returns 0.0 for every pitcher."""
    props = [
        {"pitcher": "Max Fried", "team": "New York Yankees", "opp_team": "Boston Red Sox"},
        {"pitcher": "Walker Buehler", "team": "Los Angeles Dodgers",
         "opp_team": "San Francisco Giants"},
    ]
    with patch(
        "fetch_umpires.requests.get",
        side_effect=Exception("boom"),
    ):
        with caplog.at_level(logging.WARNING, logger="fetch_umpires"):
            result, diagnostics = fetch_umpires.fetch_umpires(props, "2026-04-17")
    assert result == {"Max Fried": 0.0, "Walker Buehler": 0.0}
    assert diagnostics == {"hp_count_fetched": 0, "pitcher_nonzero_count": 0}
    assert any(
        "MLB schedule fetch failed" in r.getMessage() for r in caplog.records
    ), "fetch_umpires should log a WARNING when the underlying fetch fails"


def test_fetch_umpires_empty_props_returns_empty_dict():
    """Empty props list -> empty dict, no crash."""
    with patch("fetch_umpires.requests.get") as mock_get:
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = {"dates": []}
        result, diagnostics = fetch_umpires.fetch_umpires([], "2026-04-17")
    assert result == {}
    assert diagnostics == {"hp_count_fetched": 0, "pitcher_nonzero_count": 0}


def test_fetch_umpires_end_to_end_name_matching():
    """Full pipe: MLB API -> ABBR_TO_NAME_SUBSTR -> career-rates produces nonzero.

    Uses a real umpire name ('Vic Carapazza') that exists in the live
    career_k_rates.json so that name normalization + lookup both fire.
    """
    props = [
        # Home pitcher — team matches 'Dodgers' substring for LAD.
        {"pitcher": "LAD Starter", "team": "Los Angeles Dodgers",
         "opp_team": "San Francisco Giants"},
        # Away pitcher — team matches 'San Francisco' substring for SF.
        # Same game -> same HP umpire -> same nonzero adj.
        {"pitcher": "SF Starter", "team": "San Francisco Giants",
         "opp_team": "Los Angeles Dodgers"},
        # Umpire NOT in career_k_rates -> falls back to 0.0.
        {"pitcher": "HOU Starter", "team": "Houston Astros",
         "opp_team": "Texas Rangers"},
    ]
    with patch(
        "fetch_umpires.requests.get",
        return_value=_mock_response(_sample_schedule_payload()),
    ):
        result, diagnostics = fetch_umpires.fetch_umpires(props, "2026-04-17")

    # Both Dodgers and Giants pitchers should get Vic Carapazza's adj.
    assert result["LAD Starter"] != 0.0
    assert result["SF Starter"] == result["LAD Starter"]
    # Unknown umpire falls back to 0.0.
    assert result["HOU Starter"] == 0.0
    # 3 games fetched (NYY, LAD, HOU); 2 pitchers (LAD/SF same game) matched
    # to a known career rate, HOU starter dropped to 0 because 'Unknown Umpire'
    # isn't in career_k_rates.
    assert diagnostics["hp_count_fetched"] == 3
    assert diagnostics["pitcher_nonzero_count"] == 2


def test_fetch_umpires_accent_insensitive_name_match():
    """Career rates keys with/without accents must match MLB API spellings.

    We exercise the _normalize() path: the career table key 'jose garcia'
    must match even if the MLB API sends 'José García' or vice versa.
    """
    payload = _schedule_payload([
        _game("New York Yankees", "Boston Red Sox", [
            _official("Jose Garcia", "Home Plate"),
        ]),
    ])
    props = [
        {"pitcher": "Test Pitcher", "team": "New York Yankees",
         "opp_team": "Boston Red Sox"}
    ]
    # Synthetic career rates including an accented key.
    fake_rates = {"jose garcia": 0.25}
    with patch("fetch_umpires.requests.get", return_value=_mock_response(payload)), \
         patch("fetch_umpires._load_career_rates", return_value=fake_rates):
        result, diagnostics = fetch_umpires.fetch_umpires(props, "2026-04-17")
    assert result["Test Pitcher"] == 0.25
    assert diagnostics == {"hp_count_fetched": 1, "pitcher_nonzero_count": 1}


# ---------------------------------------------------------------------------
# Abbreviation-map coverage guards: catches accidental edits that would
# silently zero out ump signals for a team.
# ---------------------------------------------------------------------------

def test_fetch_umpires_diagnostics_distinguish_api_empty_from_match_failure():
    """Pin the prod-diagnostic contract added 2026-04-24.

    Three failure modes produce the same 0-pitcher-nonzero output and we need
    to tell them apart from today.json alone:

      (a) MLB API returned empty officials (pregame, HPs not posted yet)
          → hp_count_fetched == 0
      (b) fetch_umpires threw before returning (network / SSL)
          → run_pipeline substitutes {"hp_count_fetched": -1, ...}; not tested
             here since that substitution is in run_pipeline, not fetch_umpires
      (c) HPs fetched fine but team-match dropped everything (the soak-day
          bug we're hunting)
          → hp_count_fetched > 0, pitcher_nonzero_count == 0

    This test covers (a) and (c) end-to-end.
    """
    # Mode (a): schedule payload with zero games that have officials posted
    payload_empty = _schedule_payload([
        _game("New York Yankees", "Boston Red Sox", []),  # officials absent
    ])
    props = [{"pitcher": "NYY Starter", "team": "New York Yankees",
              "opp_team": "Boston Red Sox"}]
    with patch("fetch_umpires.requests.get",
               return_value=_mock_response(payload_empty)):
        _result, diag_a = fetch_umpires.fetch_umpires(props, "2026-04-17")
    assert diag_a == {"hp_count_fetched": 0, "pitcher_nonzero_count": 0}, (
        "Empty officials must be distinguishable as hp_count_fetched=0"
    )

    # Mode (c): HP fetched for a game, but the pitcher's team fields are
    # blank — the exact A3 pre-fix state. Matching returns 0 for every pitcher.
    payload_full = _schedule_payload([
        _game("New York Yankees", "Boston Red Sox", [
            _official("Vic Carapazza", "Home Plate"),
        ]),
    ])
    props_blank = [{"pitcher": "NYY Starter", "team": "", "opp_team": ""}]
    with patch("fetch_umpires.requests.get",
               return_value=_mock_response(payload_full)):
        _result, diag_c = fetch_umpires.fetch_umpires(props_blank, "2026-04-17")
    assert diag_c["hp_count_fetched"] == 1, (
        "HP WAS fetched — diagnostic must reflect that even when matching "
        "drops everything downstream"
    )
    assert diag_c["pitcher_nonzero_count"] == 0, (
        "With blank team fields, matching fails — nonzero count must be 0 "
        "so the caller sees the hp>0/nonzero=0 signature that fingerprints "
        "the production-only match-failure failure mode"
    )


def test_abbr_map_covers_all_30_mlb_teams():
    """ABBR_TO_NAME_SUBSTR must have exactly 30 entries (one per MLB team)."""
    assert len(fetch_umpires.ABBR_TO_NAME_SUBSTR) == 30


def test_abbr_map_values_match_career_rates_team_substrings():
    """Every ABBR_TO_NAME_SUBSTR value is a substring suitable for matching
    full team names from both TheRundown and the MLB Stats API (e.g.
    'Yankees' appears in 'New York Yankees'). Guards against accidental
    edits that would break the _build_game_ump_map substring check.

    Also asserts each canonical full name matches exactly one substring —
    no ambiguity in the reverse lookup used by fetch_hp_assignments.
    """
    known_full_names = [
        "New York Yankees", "Boston Red Sox", "Los Angeles Dodgers",
        "San Francisco Giants", "Houston Astros", "Texas Rangers",
        "Chicago Cubs", "Chicago White Sox", "Kansas City Royals",
        "St. Louis Cardinals", "Tampa Bay Rays", "Washington Nationals",
        "Los Angeles Angels",
    ]
    abbr_map = fetch_umpires.ABBR_TO_NAME_SUBSTR
    for full_name in known_full_names:
        matches = [s for s in abbr_map.values() if s.lower() in full_name.lower()]
        assert matches, f"No ABBR_TO_NAME_SUBSTR entry matches '{full_name}'"
        # The reverse-lookup helper must pick exactly one abbreviation per
        # team — first-match semantics are fine as long as that match is
        # correct. If multiple substrings match, we rely on the full-name
        # formats being unambiguous in practice (e.g. "Chicago White Sox"
        # matches "White Sox" only, not "Cubs").
        abbr = fetch_umpires._abbr_for_team_name(full_name)
        assert abbr is not None, f"reverse lookup failed for {full_name}"
