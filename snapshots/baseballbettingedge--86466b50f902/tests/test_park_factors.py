import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from team_codes import TEAM_NAME_TO_CODE, TEAM_CODES


PARK_FACTORS_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "park_factors.json",
)


def test_park_factors_include_source_metadata():
    with open(PARK_FACTORS_PATH, "r", encoding="utf-8") as fh:
        park_factors = json.load(fh)

    assert park_factors.get("_schema_version") == 1
    assert park_factors.get("_defaults_to") == 1.0
    source = park_factors.get("_source", {})
    assert source.get("provider") == "FanGraphs"
    assert source.get("url") == "https://www.fangraphs.com/tools/guts?season=2025&teamid=0&type=pf"
    assert source.get("metric") == "SO park factor, 3yr"
    assert source.get("season_range") == "2025 table / 3yr column"
    assert source.get("fetched_at") == "2026-04-27T00:00:00Z"
    assert "FanGraphs" in source.get("fetched_by", "")


def test_every_team_code_has_a_park_factor():
    with open(PARK_FACTORS_PATH, "r", encoding="utf-8") as fh:
        park_factors = json.load(fh)
    factors = park_factors["factors"]

    assert TEAM_CODES == frozenset(TEAM_NAME_TO_CODE.values())
    assert len(TEAM_CODES) == 30

    for team_name, team_code in TEAM_NAME_TO_CODE.items():
        assert team_code in factors, f"Missing park factor for {team_name} ({team_code})"
