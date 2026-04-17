"""Tests for pipeline/fetch_umpires.py (Task A3 regression coverage).

Context: As of 2026-04-17 the ump.news domain no longer resolves, so every
pick in history shows ump_k_adj = 0.0 (see analytics/diagnostics/a3_ump_adj.py).
These tests lock in the silent-failure contract so that:
  (a) network / DNS / HTTP failures are logged at WARNING level,
  (b) an empty scrape produces an empty result dict rather than an exception,
  (c) name-matching still works end-to-end when ump.news IS reachable.
"""
import sys
import os
import logging
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

import fetch_umpires  # noqa: E402


# ---------------------------------------------------------------------------
# A3.3 — silent-failure path: scrape must log WARNING and return {}.
# ---------------------------------------------------------------------------

def test_scrape_logs_warning_on_dns_failure(caplog):
    """DNS / network failures must not crash and must log at WARNING level.

    Regression: as of 2026-04-17, ump.news does not resolve. The pipeline
    depends on scrape_hp_assignments swallowing the exception and logging a
    warning so that fetch_umpires returns an empty dict. If someone changes
    this to raise, the whole pipeline breaks on every run.
    """
    with patch(
        "fetch_umpires.requests.get",
        side_effect=Exception("DNS resolution failed"),
    ):
        with caplog.at_level(logging.WARNING, logger="fetch_umpires"):
            result = fetch_umpires.scrape_hp_assignments()
    assert result == {}
    # Loud enough: at least one WARNING record mentioning the failure.
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("ump.news scrape failed" in r.getMessage() for r in warnings), (
        f"Expected a 'ump.news scrape failed' WARNING, got: {[r.getMessage() for r in warnings]}"
    )


def test_fetch_umpires_returns_all_zeros_when_scrape_fails(caplog):
    """When the scrape fails, fetch_umpires returns 0.0 for every pitcher.

    This is the current behavior that produces 100% ump_k_adj=0 in
    picks_history.json. The test locks it in so the all-zero outcome is
    intentional, not a silent bug introduced later.
    """
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
            result = fetch_umpires.fetch_umpires(props)
    assert result == {"Max Fried": 0.0, "Walker Buehler": 0.0}
    assert any(
        "ump.news scrape failed" in r.getMessage() for r in caplog.records
    ), "fetch_umpires should log a WARNING when the underlying scrape fails"


def test_fetch_umpires_empty_props_returns_empty_dict():
    """Empty props list -> empty dict, no crash, no network calls needed."""
    with patch("fetch_umpires.requests.get") as mock_get:
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.text = "<html></html>"
        result = fetch_umpires.fetch_umpires([])
    assert result == {}


# ---------------------------------------------------------------------------
# A3.4 — name-matching path: when ump.news IS reachable, the full chain
# from scrape -> abbreviation map -> career-rates lookup must produce a
# nonzero adjustment for known umpires.
# ---------------------------------------------------------------------------

_SAMPLE_UMP_NEWS_HTML = """
<html><body><table>
<tr><th>Matchup</th><th>HP</th></tr>
<tr><td>NYY @ BOS</td><td>Angel Hernandez</td></tr>
<tr><td>LAD @ SF</td><td>Vic Carapazza</td></tr>
<tr><td>HOU @ TEX</td><td>Unknown Umpire</td></tr>
</table></body></html>
"""


def _mock_response(text):
    m = MagicMock()
    m.text = text
    m.raise_for_status.return_value = None
    return m


def test_scrape_parses_matchup_rows_into_abbr_map():
    """scrape_hp_assignments returns {away_abbr: ump_name} from the HTML table."""
    with patch(
        "fetch_umpires.requests.get",
        return_value=_mock_response(_SAMPLE_UMP_NEWS_HTML),
    ):
        result = fetch_umpires.scrape_hp_assignments()
    assert result == {
        "NYY": "Angel Hernandez",
        "LAD": "Vic Carapazza",
        "HOU": "Unknown Umpire",
    }


def test_fetch_umpires_end_to_end_name_matching():
    """Full pipe: scrape -> ABBR_TO_NAME_SUBSTR -> career-rates produces nonzero.

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
        return_value=_mock_response(_SAMPLE_UMP_NEWS_HTML),
    ):
        result = fetch_umpires.fetch_umpires(props)

    # Both Dodgers and Giants pitchers should get Vic Carapazza's adj.
    assert result["LAD Starter"] != 0.0
    assert result["SF Starter"] == result["LAD Starter"]
    # Unknown umpire falls back to 0.0.
    assert result["HOU Starter"] == 0.0


def test_fetch_umpires_accent_insensitive_name_match():
    """Career rates keys with/without accents must match ump.news spellings.

    We exercise the _normalize() path: the career table key 'jose garcia'
    must match even if ump.news sends 'José García' or vice versa.
    """
    html = (
        "<html><body><table>"
        "<tr><td>NYY @ BOS</td><td>Jose Garcia</td></tr>"
        "</table></body></html>"
    )
    props = [
        {"pitcher": "Test Pitcher", "team": "New York Yankees",
         "opp_team": "Boston Red Sox"}
    ]
    # Synthetic career rates including an accented key.
    fake_rates = {"jose garcia": 0.25}
    with patch("fetch_umpires.requests.get", return_value=_mock_response(html)), \
         patch("fetch_umpires._load_career_rates", return_value=fake_rates):
        result = fetch_umpires.fetch_umpires(props)
    assert result["Test Pitcher"] == 0.25


# ---------------------------------------------------------------------------
# A3.4 — abbreviation-map coverage: every abbreviation scraped from
# ump.news needs to be in ABBR_TO_NAME_SUBSTR or the lookup silently zeros.
# This test catches the case where ump.news adds a new / renames an
# abbreviation (e.g. OAK -> ATH, SF -> SFG) and we fail to update the map.
# ---------------------------------------------------------------------------

def test_abbr_map_covers_all_30_mlb_teams():
    """ABBR_TO_NAME_SUBSTR must have exactly 30 entries (one per MLB team)."""
    assert len(fetch_umpires.ABBR_TO_NAME_SUBSTR) == 30


def test_abbr_map_values_match_career_rates_team_substrings():
    """Every ABBR_TO_NAME_SUBSTR value is a substring suitable for matching
    full team names from TheRundown API (e.g. 'Yankees' appears in
    'New York Yankees'). Guards against accidental edits that would break
    the _build_game_ump_map substring check.
    """
    # Known full names from TheRundown for a handful of teams.
    known_full_names = [
        "New York Yankees", "Boston Red Sox", "Los Angeles Dodgers",
        "San Francisco Giants", "Houston Astros", "Texas Rangers",
        "Chicago Cubs", "Chicago White Sox", "Kansas City Royals",
        "St. Louis Cardinals", "Tampa Bay Rays", "Washington Nationals",
    ]
    abbr_map = fetch_umpires.ABBR_TO_NAME_SUBSTR
    for full_name in known_full_names:
        # At least one mapped substring should appear in this full name.
        matches = [s for s in abbr_map.values() if s.lower() in full_name.lower()]
        assert matches, f"No ABBR_TO_NAME_SUBSTR entry matches '{full_name}'"
