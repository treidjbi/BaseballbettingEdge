import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from unittest.mock import patch, MagicMock
import pandas as pd
import fetch_batter_stats
from build_features import LEAGUE_AVG_K_RATE


SAMPLE_AGGREGATE = pd.DataFrame([
    {"Name": "Mookie Betts",    "K%": 0.135},
    {"Name": "Freddie Freeman", "K%": 0.098},
])

SAMPLE_VS_R = pd.DataFrame([
    {"Name": "Mookie Betts",    "K%": 0.150},
    {"Name": "Freddie Freeman", "K%": 0.110},
])

SAMPLE_VS_L = pd.DataFrame([
    {"Name": "Mookie Betts",    "K%": 0.115},
    {"Name": "Freddie Freeman", "K%": 0.080},
])


def test_fetch_aggregate_uses_fangraphs_json_payload(monkeypatch):
    payload = {
        "data": [
            {"PlayerName": "Mookie Betts", "K%": 0.135},
            {"Name": "<a>Freddie Freeman</a>", "K%": 0.098},
        ]
    }

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    fake_get = MagicMock(return_value=response)
    monkeypatch.setattr(fetch_batter_stats.requests, "get", fake_get)

    df = fetch_batter_stats._fetch_aggregate(2026)

    assert list(df["Name"]) == ["Mookie Betts", "Freddie Freeman"]
    assert list(df["K%"]) == [0.135, 0.098]
    assert fake_get.call_args.kwargs["params"]["stats"] == "bat"


def test_fetch_batter_stats_returns_splits(monkeypatch):
    """When splits available, returns vs_R and vs_L per batter."""
    monkeypatch.setattr("fetch_batter_stats._fetch_aggregate", lambda season: SAMPLE_AGGREGATE)
    monkeypatch.setattr("fetch_batter_stats._fetch_splits", lambda season: (SAMPLE_VS_R, SAMPLE_VS_L))
    result = fetch_batter_stats.fetch_batter_stats(2026)
    # Keys are normalized by _build_lookup so lineup names from MLB Stats API
    # (which may have accents/casing differences) match reliably.
    assert abs(result["mookie betts"]["vs_R"] - 0.150) < 0.001
    assert abs(result["mookie betts"]["vs_L"] - 0.115) < 0.001


def test_fetch_batter_stats_falls_back_to_aggregate_when_splits_fail(monkeypatch):
    """When _fetch_splits raises, returns aggregate K% for both splits."""
    monkeypatch.setattr("fetch_batter_stats._fetch_aggregate", lambda season: SAMPLE_AGGREGATE)
    def raise_splits(season):
        raise AttributeError("no splits")
    monkeypatch.setattr("fetch_batter_stats._fetch_splits", raise_splits)
    result = fetch_batter_stats.fetch_batter_stats(2026)
    assert abs(result["mookie betts"]["vs_R"] - 0.135) < 0.001
    assert abs(result["mookie betts"]["vs_L"] - 0.135) < 0.001


def test_fetch_batter_stats_unknown_batter_returns_league_avg(monkeypatch):
    """Batters not in FanGraphs data return None (caller uses LEAGUE_AVG_K_RATE as fallback)."""
    monkeypatch.setattr("fetch_batter_stats._fetch_aggregate", lambda season: SAMPLE_AGGREGATE)
    monkeypatch.setattr("fetch_batter_stats._fetch_splits", lambda season: (SAMPLE_VS_R, SAMPLE_VS_L))
    result = fetch_batter_stats.fetch_batter_stats(2026)
    unknown = result.get("Unknown Player")
    assert unknown is None  # not in result dict — caller uses .get() with fallback


def test_fetch_batter_stats_uses_league_avg_k_rate_from_build_features(monkeypatch):
    """LEAGUE_AVG_K_RATE should come from build_features, not be redefined."""
    import build_features
    assert fetch_batter_stats.LEAGUE_AVG_K_RATE is build_features.LEAGUE_AVG_K_RATE


def test_fetch_batter_stats_returns_empty_dict_on_total_failure(monkeypatch):
    """When aggregate fetch also fails, returns {} (pipeline continues with team K%)."""
    def raise_agg(season):
        raise Exception("FanGraphs down")
    monkeypatch.setattr("fetch_batter_stats._fetch_aggregate", raise_agg)
    result = fetch_batter_stats.fetch_batter_stats(2026)
    assert result == {}


def test_extract_bref_platoon_split_rates_from_pybaseball_table():
    table = pd.DataFrame(
        [
            {"Split Type": "Platoon Splits", "Split": "vs RHP", "PA": 100, "SO": 25},
            {"Split Type": "Platoon Splits", "Split": "vs LHP", "PA": 50, "SO": 5},
        ]
    ).set_index(["Split Type", "Split"])

    result = fetch_batter_stats._extract_bref_platoon_split_rates(table)

    assert result == {
        "vs_R": {"pa": 100, "so": 25, "k_rate": 0.25},
        "vs_L": {"pa": 50, "so": 5, "k_rate": 0.1},
    }


def test_collect_batter_split_samples_writes_collection_only_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "batter_splits_2026.json"
    lineups = [
        [
            {"name": "Mookie Betts", "bats": "R", "mlbam_id": 605141},
            {"name": "No Id Batter", "bats": "L"},
        ]
    ]

    lookup = pd.DataFrame(
        [
            {
                "key_mlbam": 605141,
                "key_bbref": "bettsmo01",
            }
        ]
    )

    monkeypatch.setattr(
        fetch_batter_stats,
        "playerid_reverse_lookup",
        lambda player_ids, key_type="mlbam": lookup,
    )
    monkeypatch.setattr(
        fetch_batter_stats,
        "_fetch_bref_platoon_split_rates",
        lambda bbref_id, season: {
            "vs_R": {"pa": 80, "so": 12, "k_rate": 0.15},
            "vs_L": {"pa": 20, "so": 2, "k_rate": 0.10},
        },
    )

    summary = fetch_batter_stats.collect_batter_split_samples(
        lineups,
        2026,
        cache_path=cache_path,
        max_new=5,
    )

    assert summary["projection_status"] == "collection_only"
    assert summary["requested_batters"] == 1
    assert summary["already_cached"] == 0
    assert summary["queued_not_attempted"] == 0
    assert summary["collected"] == 1

    payload = __import__("json").loads(cache_path.read_text())
    assert payload["projection_status"] == "collection_only"
    assert payload["batters"]["mlbam:605141"]["name"] == "Mookie Betts"
    assert payload["batters"]["mlbam:605141"]["vs_R"]["k_rate"] == 0.15


def test_collect_batter_split_samples_reports_queue_separately_from_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "batter_splits_2026.json"
    lineups = [
        [
            {"name": "Cached Batter", "bats": "R", "mlbam_id": 1},
            {"name": "New Batter One", "bats": "R", "mlbam_id": 2},
            {"name": "New Batter Two", "bats": "L", "mlbam_id": 3},
        ]
    ]
    cache_path.write_text(
        __import__("json").dumps(
            {
                "season": 2026,
                "projection_status": "collection_only",
                "batters": {"mlbam:1": {"name": "Cached Batter"}},
            }
        )
    )

    lookup = pd.DataFrame([{"key_mlbam": 2, "key_bbref": "newone01"}])
    monkeypatch.setattr(
        fetch_batter_stats,
        "playerid_reverse_lookup",
        lambda player_ids, key_type="mlbam": lookup,
    )
    monkeypatch.setattr(
        fetch_batter_stats,
        "_fetch_bref_platoon_split_rates",
        lambda bbref_id, season: {
            "vs_R": {"pa": 50, "so": 10, "k_rate": 0.20},
            "vs_L": {"pa": 20, "so": 5, "k_rate": 0.25},
        },
    )

    summary = fetch_batter_stats.collect_batter_split_samples(
        lineups,
        2026,
        cache_path=cache_path,
        max_new=1,
    )

    assert summary["requested_batters"] == 3
    assert summary["already_cached"] == 1
    assert summary["attempted"] == 1
    assert summary["queued_not_attempted"] == 1
