import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from unittest.mock import MagicMock
import fetch_lineups


# Real MLB Stats API shape (verified 2026-04-23 against Cardinals @ Marlins
# 2026-04-22 game_pk=823878). The /schedule endpoint returns teams + gamePk
# but does NOT carry battingOrder on its hydrated lineup players; that field
# lives on /game/{pk}/boxscore via teams.{away,home}.battingOrder as an
# ordered list of ints, plus per-player entries in teams.{away,home}.players.
SAMPLE_SCHEDULE_RESPONSE = {
    "dates": [{
        "games": [{
            "gamePk": 745000,
            "teams": {
                "away": {"team": {"name": "New York Yankees"}},
                "home": {"team": {"name": "Boston Red Sox"}},
            },
        }]
    }]
}

SAMPLE_BOXSCORE_RESPONSE = {
    "teams": {
        "away": {
            "team": {"name": "New York Yankees"},
            "battingOrder": [111, 222, 333, 444, 555, 666, 777, 888, 999],
            "players": {
                "ID111": {"person": {"fullName": "Aaron Judge", "batSide": {"code": "R"}}},
                "ID222": {"person": {"fullName": "Giancarlo Stanton", "batSide": {"code": "R"}}},
                "ID333": {"person": {"fullName": "Juan Soto", "batSide": {"code": "L"}}},
                "ID444": {"person": {"fullName": "Anthony Rizzo", "batSide": {"code": "L"}}},
                "ID555": {"person": {"fullName": "Gleyber Torres", "batSide": {"code": "R"}}},
                "ID666": {"person": {"fullName": "Alex Verdugo", "batSide": {"code": "L"}}},
                "ID777": {"person": {"fullName": "Anthony Volpe", "batSide": {"code": "R"}}},
                "ID888": {"person": {"fullName": "Jose Trevino", "batSide": {"code": "R"}}},
                "ID999": {"person": {"fullName": "Oswaldo Cabrera", "batSide": {"code": "S"}}},
            },
        },
        "home": {
            "team": {"name": "Boston Red Sox"},
            "battingOrder": [],
            "players": {},
        },
    },
}


def _make_mock_response(data):
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status.return_value = None
    return m


def _routed_get(schedule_response, boxscore_response):
    """Returns a mock `requests.get` that routes by URL substring.

    `/schedule` URLs get schedule_response; `/game/{pk}/boxscore` URLs get
    boxscore_response. Anything else raises (surfaces URL-construction bugs).
    """
    def _get(url, *args, **kwargs):
        if "/schedule" in url:
            return _make_mock_response(schedule_response)
        if "/boxscore" in url:
            return _make_mock_response(boxscore_response)
        raise AssertionError(f"unexpected URL: {url}")
    return _get


def test_fetch_lineups_returns_batters_in_batting_order(monkeypatch):
    """fetch_lineups returns 9 batters in the order given by battingOrder."""
    monkeypatch.setattr(
        "fetch_lineups.requests.get",
        _routed_get(SAMPLE_SCHEDULE_RESPONSE, SAMPLE_BOXSCORE_RESPONSE),
    )
    result = fetch_lineups.fetch_lineups("2026-04-15", "New York Yankees")
    assert result is not None, "expected 9 batters for the Yankees, got None"
    assert len(result) == 9
    # First three in battingOrder are Judge, Stanton, Soto
    assert [b["name"] for b in result[:3]] == ["Aaron Judge", "Giancarlo Stanton", "Juan Soto"]


def test_fetch_lineups_returns_none_when_battingorder_empty(monkeypatch):
    """Empty battingOrder (pregame, lineup not posted yet) returns None."""
    monkeypatch.setattr(
        "fetch_lineups.requests.get",
        _routed_get(SAMPLE_SCHEDULE_RESPONSE, SAMPLE_BOXSCORE_RESPONSE),
    )
    # Ask for the home team — SAMPLE_BOXSCORE_RESPONSE has home.battingOrder = []
    result = fetch_lineups.fetch_lineups("2026-04-15", "Boston Red Sox")
    assert result is None


def test_fetch_lineups_returns_none_on_schedule_api_error(monkeypatch):
    """Schedule API failure: return None, do not raise."""
    def raise_error(*a, **kw):
        raise Exception("network error")
    monkeypatch.setattr("fetch_lineups.requests.get", raise_error)
    result = fetch_lineups.fetch_lineups("2026-04-15", "NYY")
    assert result is None


def test_fetch_lineups_returns_none_on_boxscore_api_error(monkeypatch):
    """Boxscore API failure (after schedule succeeds): return None."""
    def _get(url, *a, **kw):
        if "/schedule" in url:
            return _make_mock_response(SAMPLE_SCHEDULE_RESPONSE)
        raise Exception("boxscore down")
    monkeypatch.setattr("fetch_lineups.requests.get", _get)
    result = fetch_lineups.fetch_lineups("2026-04-15", "New York Yankees")
    assert result is None


def test_fetch_lineups_includes_bats_field(monkeypatch):
    """Each batter dict has a bats field in {R, L, S}. Missing batSide -> R."""
    monkeypatch.setattr(
        "fetch_lineups.requests.get",
        _routed_get(SAMPLE_SCHEDULE_RESPONSE, SAMPLE_BOXSCORE_RESPONSE),
    )
    result = fetch_lineups.fetch_lineups("2026-04-15", "New York Yankees")
    assert result is not None
    for batter in result:
        assert "bats" in batter
        assert batter["bats"] in ("R", "L", "S")


def test_fetch_lineups_returns_none_when_team_not_scheduled(monkeypatch):
    """Team plays no game on that date -> None (no boxscore call expected)."""
    monkeypatch.setattr(
        "fetch_lineups.requests.get",
        _routed_get(SAMPLE_SCHEDULE_RESPONSE, SAMPLE_BOXSCORE_RESPONSE),
    )
    result = fetch_lineups.fetch_lineups("2026-04-15", "Chicago Cubs")
    assert result is None


def test_fetch_lineups_case_insensitive_team_match(monkeypatch):
    """Team name matching is case-insensitive (mirrors prior behavior)."""
    monkeypatch.setattr(
        "fetch_lineups.requests.get",
        _routed_get(SAMPLE_SCHEDULE_RESPONSE, SAMPLE_BOXSCORE_RESPONSE),
    )
    result = fetch_lineups.fetch_lineups("2026-04-15", "new york yankees")
    assert result is not None
    assert len(result) == 9
