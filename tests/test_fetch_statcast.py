import importlib.util
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

PIPELINE_DIR = Path(__file__).resolve().parent.parent / "pipeline"
MODULE_PATH = PIPELINE_DIR / "fetch_statcast.py"
SPEC = importlib.util.spec_from_file_location("test_fetch_statcast_module", MODULE_PATH)
fetch_statcast = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
os.sys.path.insert(0, str(PIPELINE_DIR))
SPEC.loader.exec_module(fetch_statcast)


def _response_with_rows(rows):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"data": rows}
    return response


def _response_with_payload(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def test_fetch_swstr_uses_modern_fangraphs_json_for_current_and_three_year_career_average():
    responses_by_season = {
        2026: _response_with_rows([{"PlayerName": "Zack Wheeler", "SwStr%": 0.145}]),
        2023: _response_with_rows([{"PlayerName": "Zack Wheeler", "SwStr%": 0.110}]),
        2024: _response_with_rows([{"PlayerName": "Zack Wheeler", "SwStr%": 0.120}]),
        2025: _response_with_rows([{"PlayerName": "Zack Wheeler", "SwStr%": 0.130}]),
    }

    def fake_get(url, params=None, timeout=None):
        assert url == fetch_statcast.FANGRAPHS_LEADERBOARD_URL
        assert params["stats"] == "pit"
        assert params["type"] == "8"
        assert params["qual"] == "0"
        assert params["season"] == str(params["season1"])
        return responses_by_season[int(params["season"])]

    with patch.object(fetch_statcast.requests, "get", side_effect=fake_get):
        result = fetch_statcast.fetch_swstr(2026, ["Zack Wheeler"])

    assert result["Zack Wheeler"]["swstr_pct"] == pytest.approx(0.145)
    assert result["Zack Wheeler"]["career_swstr_pct"] == pytest.approx((0.110 + 0.120 + 0.130) / 3)


def test_fetch_swstr_averages_partial_career_window_when_only_two_prior_seasons_exist():
    responses_by_season = {
        2026: _response_with_rows([{"PlayerName": "Roki Sasaki", "SwStr%": 0.151}]),
        2023: _response_with_rows([]),
        2024: _response_with_rows([{"PlayerName": "Roki Sasaki", "SwStr%": 0.100}]),
        2025: _response_with_rows([{"PlayerName": "Roki Sasaki", "SwStr%": 0.140}]),
    }

    def fake_get(url, params=None, timeout=None):
        return responses_by_season[int(params["season"])]

    with patch.object(fetch_statcast.requests, "get", side_effect=fake_get):
        result = fetch_statcast.fetch_swstr(2026, ["Roki Sasaki"])

    assert result["Roki Sasaki"]["swstr_pct"] == pytest.approx(0.151)
    assert result["Roki Sasaki"]["career_swstr_pct"] == pytest.approx((0.100 + 0.140) / 2)


def test_fetch_swstr_matches_names_across_accents_and_still_averages_career():
    responses_by_season = {
        2026: _response_with_rows([{"PlayerName": "Shota Imanaga", "SwStr%": 0.133}]),
        2023: _response_with_rows([]),
        2024: _response_with_rows([{"PlayerName": "Shota Imanaga", "SwStr%": 0.120}]),
        2025: _response_with_rows([{"PlayerName": "Shota Imanaga", "SwStr%": 0.126}]),
    }

    def fake_get(url, params=None, timeout=None):
        return responses_by_season[int(params["season"])]

    accented_name = "Sh\u014dta Imanaga"
    with patch.object(fetch_statcast.requests, "get", side_effect=fake_get):
        result = fetch_statcast.fetch_swstr(2026, [accented_name])

    assert accented_name in result
    assert result[accented_name]["swstr_pct"] == pytest.approx(0.133)
    assert result[accented_name]["career_swstr_pct"] == pytest.approx((0.120 + 0.126) / 2)


def test_fetch_swstr_uses_html_name_when_player_name_is_missing():
    responses_by_season = {
        2026: _response_with_rows([
            {
                "Name": '<a href="statss.aspx?playerid=32095&position=P">Cameron Schlittler</a>',
                "SwStr%": 0.14990138,
            }
        ]),
        2023: _response_with_rows([]),
        2024: _response_with_rows([]),
        2025: _response_with_rows([]),
    }

    def fake_get(url, params=None, timeout=None):
        return responses_by_season[int(params["season"])]

    with patch.object(fetch_statcast.requests, "get", side_effect=fake_get):
        result = fetch_statcast.fetch_swstr(2026, ["Cameron Schlittler"])

    assert result["Cameron Schlittler"]["swstr_pct"] == pytest.approx(0.14990138)
    assert result["Cameron Schlittler"]["career_swstr_pct"] is None


def test_fetch_swstr_returns_fallback_when_payload_data_is_malformed():
    bad_payloads = [
        _response_with_payload(None),
        _response_with_payload({"data": {"PlayerName": "Pitcher A", "SwStr%": 0.123}}),
        _response_with_payload({"status": "ok"}),
    ]

    for bad_response in bad_payloads:
        with patch.object(fetch_statcast.requests, "get", return_value=bad_response):
            result = fetch_statcast.fetch_swstr(2026, ["Pitcher A"])

        assert result["Pitcher A"]["swstr_pct"] == pytest.approx(fetch_statcast.LEAGUE_AVG_SWSTR)
        assert result["Pitcher A"]["career_swstr_pct"] is None
        assert result["__meta__"] == {"current_usable": False, "career_usable": False}


def test_fetch_swstr_fetches_additional_pages_when_total_count_exceeds_first_page():
    responses_by_call = {
        (2026, None): _response_with_payload(
            {
                "data": [{"PlayerName": "Pitcher A", "SwStr%": 0.111}],
                "totalCount": 2,
            }
        ),
        (2026, "2"): _response_with_payload(
            {
                "data": [{"PlayerName": "Pitcher B", "SwStr%": 0.222}],
                "totalCount": 2,
            }
        ),
        (2023, None): _response_with_payload({"data": [], "totalCount": 0}),
        (2024, None): _response_with_payload({"data": [], "totalCount": 0}),
        (2025, None): _response_with_payload({"data": [], "totalCount": 0}),
    }
    seen_pages = []

    def fake_get(url, params=None, timeout=None):
        key = (int(params["season"]), params.get("pagenum"))
        seen_pages.append(key)
        return responses_by_call[key]

    with patch.object(fetch_statcast.requests, "get", side_effect=fake_get):
        result = fetch_statcast.fetch_swstr(2026, ["Pitcher A", "Pitcher B"])

    assert result["Pitcher A"]["swstr_pct"] == pytest.approx(0.111)
    assert result["Pitcher B"]["swstr_pct"] == pytest.approx(0.222)
    assert seen_pages[:2] == [(2026, None), (2026, "2")]


def test_fetch_swstr_retries_transient_current_season_request_failures():
    current_attempts = {"count": 0}

    def fake_get(url, params=None, timeout=None):
        season = int(params["season"])
        if season == 2026:
            current_attempts["count"] += 1
            if current_attempts["count"] == 1:
                raise fetch_statcast.requests.RequestException("temporary outage")
            return _response_with_payload(
                {"data": [{"PlayerName": "Pitcher A", "SwStr%": 0.123}], "totalCount": 1}
            )
        return _response_with_payload({"data": [], "totalCount": 0})

    with patch.object(fetch_statcast.requests, "get", side_effect=fake_get):
        result = fetch_statcast.fetch_swstr(2026, ["Pitcher A"])

    assert current_attempts["count"] == 2
    assert result["Pitcher A"]["swstr_pct"] == pytest.approx(0.123)


def test_fetch_swstr_returns_league_average_for_all_when_current_season_fetch_is_unavailable():
    def fake_get(url, params=None, timeout=None):
        season = int(params["season"])
        if season == 2026:
            raise fetch_statcast.requests.RequestException("blocked")
        return _response_with_rows([{"PlayerName": "Unused", "SwStr%": 0.101}])

    with patch.object(fetch_statcast.requests, "get", side_effect=fake_get):
        result = fetch_statcast.fetch_swstr(2026, ["Pitcher A", "Pitcher B"])

    assert result["Pitcher A"]["swstr_pct"] == pytest.approx(fetch_statcast.LEAGUE_AVG_SWSTR)
    assert result["Pitcher A"]["career_swstr_pct"] is None
    assert result["Pitcher B"]["swstr_pct"] == pytest.approx(fetch_statcast.LEAGUE_AVG_SWSTR)
    assert result["Pitcher B"]["career_swstr_pct"] is None
    assert result["__meta__"] == {"current_usable": False, "career_usable": False}


def test_fetch_swstr_marks_career_unusable_when_one_prior_year_fetch_fails():
    def fake_get(url, params=None, timeout=None):
        season = int(params["season"])
        if season == 2026:
            return _response_with_payload(
                {"data": [{"PlayerName": "Pitcher A", "SwStr%": 0.123}], "totalCount": 1}
            )
        if season == 2024:
            raise fetch_statcast.requests.RequestException("blocked prior season")
        return _response_with_payload({"data": [], "totalCount": 0})

    with patch.object(fetch_statcast.requests, "get", side_effect=fake_get):
        result = fetch_statcast.fetch_swstr(2026, ["Pitcher A"])

    assert result["Pitcher A"]["swstr_pct"] == pytest.approx(0.123)
    assert result["Pitcher A"]["career_swstr_pct"] is None
    assert result["__meta__"] == {"current_usable": True, "career_usable": False}
