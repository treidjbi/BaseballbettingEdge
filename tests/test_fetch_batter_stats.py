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


def test_fetch_batter_stats_returns_splits(monkeypatch):
    """When splits available, returns vs_R and vs_L per batter."""
    monkeypatch.setattr("fetch_batter_stats._fetch_aggregate", lambda season: SAMPLE_AGGREGATE)
    monkeypatch.setattr("fetch_batter_stats._fetch_splits", lambda season: (SAMPLE_VS_R, SAMPLE_VS_L))
    result = fetch_batter_stats.fetch_batter_stats(2026)
    assert abs(result["Mookie Betts"]["vs_R"] - 0.150) < 0.001
    assert abs(result["Mookie Betts"]["vs_L"] - 0.115) < 0.001


def test_fetch_batter_stats_falls_back_to_aggregate_when_splits_fail(monkeypatch):
    """When _fetch_splits raises, returns aggregate K% for both splits."""
    monkeypatch.setattr("fetch_batter_stats._fetch_aggregate", lambda season: SAMPLE_AGGREGATE)
    def raise_splits(season):
        raise AttributeError("no splits")
    monkeypatch.setattr("fetch_batter_stats._fetch_splits", raise_splits)
    result = fetch_batter_stats.fetch_batter_stats(2026)
    assert abs(result["Mookie Betts"]["vs_R"] - 0.135) < 0.001
    assert abs(result["Mookie Betts"]["vs_L"] - 0.135) < 0.001


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
