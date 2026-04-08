import pytest
import sys
import os
import json
import tempfile
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from build_features import (
    american_to_implied,
    calc_lambda,
    calc_ev,
    calc_verdict,
    calc_price_delta,
    blend_k9,
    calc_swstr_mult,
    calc_movement_confidence,
    bayesian_opp_k,
    build_pitcher_record,
    LEAGUE_AVG_K_RATE,
)


class TestAmericanToImplied:
    def test_minus_110(self):
        assert abs(american_to_implied(-110) - 0.5238) < 0.001

    def test_plus_100(self):
        assert abs(american_to_implied(100) - 0.5) < 0.001

    def test_minus_200(self):
        assert abs(american_to_implied(-200) - 0.6667) < 0.001

    def test_plus_150(self):
        assert abs(american_to_implied(150) - 0.4) < 0.001


class TestBlendK9:
    def test_early_season_leans_on_career(self):
        # 9 IP → w_season=0.15, w_recent=0.2, w_career=0.65 → 0.15*9 + 0.2*9 + 0.65*7 = 7.70
        result = blend_k9(season_k9=9.0, recent_k9=9.0, career_k9=7.0, ip=9)
        assert abs(result - 7.70) < 0.05

    def test_full_season_leans_on_season(self):
        # 90 IP → w_season=0.7 (capped), w_recent=0.2, w_career=0.1 → 0.7*10 + 0.2*9 + 0.1*8 = 9.6
        result = blend_k9(season_k9=10.0, recent_k9=9.0, career_k9=8.0, ip=90)
        assert abs(result - 9.6) < 0.05

    def test_rookie_career_fallback(self):
        result = blend_k9(season_k9=8.0, recent_k9=8.0, career_k9=8.0, ip=18)
        assert abs(result - 8.0) < 0.05

    def test_weights_sum_to_one(self):
        result = blend_k9(season_k9=10.0, recent_k9=8.0, career_k9=6.0, ip=30)
        assert 6.0 <= result <= 10.0


class TestCalcLambda:
    def test_neutral_conditions(self):
        lam = calc_lambda(blended_k9=9.0, expected_innings=5.5, opp_k_rate=0.227, ump_k_adj=0)
        assert abs(lam - 5.5) < 0.01  # 9.0 * 5.5 / 9 = 5.5

    def test_high_k_opponent_inflates_lambda(self):
        # Pass opp_games_played=162 so Bayesian blend trusts observed data
        lam = calc_lambda(blended_k9=9.0, expected_innings=5.5, opp_k_rate=0.255,
                          ump_k_adj=0, opp_games_played=162)
        assert lam > 5.5

    def test_low_k_opponent_deflates_lambda(self):
        # Pass opp_games_played=162 so Bayesian blend trusts observed data
        lam = calc_lambda(blended_k9=9.0, expected_innings=5.5, opp_k_rate=0.200,
                          ump_k_adj=0, opp_games_played=162)
        assert lam < 5.5

    def test_positive_ump_adj_raises_lambda(self):
        lam_no_ump = calc_lambda(9.0, 5.5, 0.227, 0)
        lam_with_ump = calc_lambda(9.0, 5.5, 0.227, 0.4)
        assert lam_with_ump > lam_no_ump


class TestCalcEV:
    def test_positive_ev_when_win_prob_beats_implied(self):
        ev = calc_ev(win_prob=0.572, odds=-112)
        assert ev > 0

    def test_negative_ev_when_implied_beats_win_prob(self):
        ev = calc_ev(win_prob=0.40, odds=-110)
        assert ev < 0

    def test_zero_ev_at_breakeven(self):
        ev = calc_ev(win_prob=0.5238, odds=-110)
        assert abs(ev) < 0.002


class TestCalcVerdict:
    def test_pass(self):
        assert calc_verdict(0.005) == "PASS"

    def test_pass_negative(self):
        assert calc_verdict(-0.05) == "PASS"

    def test_lean(self):
        assert calc_verdict(0.02) == "LEAN"

    def test_fire_1u(self):
        assert calc_verdict(0.05) == "FIRE 1u"

    def test_fire_2u(self):
        assert calc_verdict(0.10) == "FIRE 2u"


class TestCalcPriceDelta:
    def test_juice_moved_to_over(self):
        delta = calc_price_delta(current_odds=-135, opening_odds=-110)
        assert delta == -25

    def test_juice_moved_to_under(self):
        delta = calc_price_delta(current_odds=-100, opening_odds=-110)
        assert delta == 10

    def test_no_movement(self):
        assert calc_price_delta(-110, -110) == 0


class TestCalcSwstrMult:
    def test_league_avg_returns_one(self):
        assert abs(calc_swstr_mult(0.110) - 1.0) < 0.001

    def test_above_avg_returns_gt_one(self):
        assert calc_swstr_mult(0.150) > 1.0

    def test_below_avg_returns_lt_one(self):
        assert calc_swstr_mult(0.080) < 1.0

    def test_zero_swstr_returns_one(self):
        assert calc_swstr_mult(0.0) == 1.0

    def test_known_value(self):
        assert abs(calc_swstr_mult(0.140) - (0.140 / 0.110)) < 0.001


class TestCalcLambdaSwstrMult:
    def test_swstr_mult_default_unchanged(self):
        lam_old = calc_lambda(blended_k9=9.0, expected_innings=5.5, opp_k_rate=0.227, ump_k_adj=0)
        lam_new = calc_lambda(blended_k9=9.0, expected_innings=5.5, opp_k_rate=0.227, ump_k_adj=0, swstr_mult=1.0)
        assert abs(lam_old - lam_new) < 0.001

    def test_high_swstr_inflates_lambda(self):
        lam_base = calc_lambda(9.0, 5.5, 0.227, 0, swstr_mult=1.0)
        lam_high = calc_lambda(9.0, 5.5, 0.227, 0, swstr_mult=1.3)
        assert lam_high > lam_base

    def test_low_swstr_deflates_lambda(self):
        lam_base = calc_lambda(9.0, 5.5, 0.227, 0, swstr_mult=1.0)
        lam_low  = calc_lambda(9.0, 5.5, 0.227, 0, swstr_mult=0.75)
        assert lam_low < lam_base

    def test_swstr_mult_scales_base_not_ump(self):
        lam_no_ump   = calc_lambda(9.0, 5.5, 0.227, 0,   swstr_mult=1.3)
        lam_with_ump = calc_lambda(9.0, 5.5, 0.227, 0.4, swstr_mult=1.3)
        ump_contribution = lam_with_ump - lam_no_ump
        assert abs(ump_contribution - (0.4 * 5.5 / 9)) < 0.01


class TestBuildPitcherRecord:
    """Integration test for build_pitcher_record — exercises all fallback paths."""

    BASE_ODDS = {
        "pitcher": "Test Pitcher", "team": "NYY", "opp_team": "BOS",
        "game_time": "2026-04-01T23:05:00Z",
        "k_line": 7.5, "opening_line": 7.5,
        "best_over_book": "FanDuel", "best_over_odds": -110, "best_under_odds": -110,
        "opening_over_odds": -110, "opening_under_odds": -110,
    }
    BASE_STATS = {
        "season_k9": 9.0, "recent_k9": 9.0, "career_k9": 9.0,
        "starts_count": 5, "innings_pitched_season": 30.0,
        "avg_ip_last5": 6.0, "opp_k_rate": 0.227,
    }

    def test_returns_expected_keys(self):
        from build_features import build_pitcher_record
        rec = build_pitcher_record(self.BASE_ODDS, self.BASE_STATS, ump_k_adj=0.0)
        for key in ["pitcher", "lambda", "avg_ip", "swstr_pct", "ev_over", "ev_under"]:
            assert key in rec, f"Missing key: {key}"

    def test_uses_avg_ip_last5_not_constant(self):
        from build_features import build_pitcher_record, load_params
        rec = build_pitcher_record(self.BASE_ODDS, self.BASE_STATS, ump_k_adj=0.0)
        # At 9.0 K/9, neutral conditions, 6.0 IP → raw_lambda = 6.0.
        # applied_lambda = raw_lambda + lambda_bias (from params), so assert
        # against the bias-adjusted expectation rather than the raw value.
        params = load_params()
        expected_lam = 6.0 + params.get("lambda_bias", 0.0)
        assert abs(rec["lambda"] - expected_lam) < 0.05
        assert rec["avg_ip"] == 6.0

    def test_fallback_to_constant_when_avg_ip_missing(self):
        from build_features import build_pitcher_record, EXPECTED_INNINGS
        stats = {**self.BASE_STATS}
        del stats["avg_ip_last5"]
        rec = build_pitcher_record(self.BASE_ODDS, stats, ump_k_adj=0.0)
        assert rec["avg_ip"] == EXPECTED_INNINGS   # 5.5

    def test_rookie_career_fallback(self):
        from build_features import build_pitcher_record
        stats = {**self.BASE_STATS, "career_k9": None, "starts_count": 2}
        rec = build_pitcher_record(self.BASE_ODDS, stats, ump_k_adj=0.0)
        assert rec["lambda"] > 0

    def test_swstr_pct_above_avg_raises_lambda(self):
        from build_features import build_pitcher_record
        rec_neutral = build_pitcher_record(self.BASE_ODDS, self.BASE_STATS, ump_k_adj=0.0, swstr_pct=0.110)
        rec_high    = build_pitcher_record(self.BASE_ODDS, self.BASE_STATS, ump_k_adj=0.0, swstr_pct=0.150)
        assert rec_high["lambda"] > rec_neutral["lambda"]

    def test_verdict_and_win_prob_present(self):
        from build_features import build_pitcher_record
        rec = build_pitcher_record(self.BASE_ODDS, self.BASE_STATS, ump_k_adj=0.0)
        assert rec["ev_over"]["verdict"] in ("PASS", "LEAN", "FIRE 1u", "FIRE 2u")
        assert 0 <= rec["ev_over"]["win_prob"] <= 1

    def test_movement_confidence_applied(self):
        """
        When the over line moves from -125 (opening) to -110 (current),
        price_delta_over = -110 - (-125) = +15 → conf_over = 0.75.
        adj_ev_over should equal round(raw_ev_over * 0.75, 4).
        The under has no movement → conf_under = 1.0, adj_ev_under == ev_under.
        """
        from build_features import build_pitcher_record
        odds = {
            **self.BASE_ODDS,
            "opening_over_odds": -125,   # over was -125 at open
            "best_over_odds":    -110,   # over moved to -110 (cheaper) → delta = +15
            "opening_under_odds": -110,  # under unchanged
            "best_under_odds":    -110,
        }
        rec = build_pitcher_record(odds, self.BASE_STATS, ump_k_adj=0.0)

        raw_ev_over = rec["ev_over"]["ev"]
        assert abs(rec["ev_over"]["movement_conf"] - 0.75) < 0.001
        assert abs(rec["ev_over"]["adj_ev"] - round(raw_ev_over * 0.75, 4)) < 0.0002

        # Under: no movement → no haircut
        raw_ev_under = rec["ev_under"]["ev"]
        assert abs(rec["ev_under"]["movement_conf"] - 1.0) < 0.001
        assert rec["ev_under"]["adj_ev"] == raw_ev_under

        # Verdict must be based on adj_ev, not raw ev
        from build_features import calc_verdict
        assert rec["ev_over"]["verdict"] == calc_verdict(rec["ev_over"]["adj_ev"])
        assert rec["ev_under"]["verdict"] == calc_verdict(rec["ev_under"]["adj_ev"])

    def test_win_prob_over_plus_under_sum_to_one_half_line(self):
        """For half-point lines, over + under should sum to 1.0 (no push mass)."""
        from build_features import build_pitcher_record
        odds = {**self.BASE_ODDS, "k_line": 7.5}
        rec = build_pitcher_record(odds, self.BASE_STATS, ump_k_adj=0.0)
        total = rec["ev_over"]["win_prob"] + rec["ev_under"]["win_prob"]
        assert abs(total - 1.0) < 0.001

    def test_win_prob_over_plus_under_sum_to_one_integer_line(self):
        """For integer lines, over + under should sum to < 1.0 (push mass exists)."""
        from build_features import build_pitcher_record
        from scipy.stats import poisson
        import math
        odds = {**self.BASE_ODDS, "k_line": 7.0}
        rec = build_pitcher_record(odds, self.BASE_STATS, ump_k_adj=0.0)
        total = rec["ev_over"]["win_prob"] + rec["ev_under"]["win_prob"]
        # They should sum to < 1.0 (push probability is the gap)
        assert total < 1.0
        # And specifically the gap should equal P(X == 7) at the applied lambda
        lam = rec["lambda"]
        push_prob = poisson.pmf(7, lam)
        assert abs((1.0 - total) - push_prob) < 0.002

    def test_team_from_stats_overrides_empty_string_from_odds(self):
        """When stats contains team/opp_team (from MLB schedule), build_pitcher_record
        should output those values, not the empty strings from fetch_odds."""
        from build_features import build_pitcher_record
        odds = {**self.BASE_ODDS, "team": "", "opp_team": ""}
        stats = {**self.BASE_STATS, "team": "Boston Red Sox", "opp_team": "New York Yankees"}
        rec = build_pitcher_record(odds, stats, ump_k_adj=0.0)
        assert rec["team"] == "Boston Red Sox"
        assert rec["opp_team"] == "New York Yankees"

    def test_opp_games_played_affects_lambda(self):
        """opp_games_played=0 (no data) should produce same lambda as league avg opp.
        opp_games_played=162 with high K% team should produce higher lambda."""
        from build_features import build_pitcher_record
        stats_no_games = {**self.BASE_STATS, "opp_k_rate": 0.30, "opp_games_played": 0}
        stats_full_season = {**self.BASE_STATS, "opp_k_rate": 0.30, "opp_games_played": 162}
        rec_no = build_pitcher_record(self.BASE_ODDS, stats_no_games, ump_k_adj=0.0)
        rec_full = build_pitcher_record(self.BASE_ODDS, stats_full_season, ump_k_adj=0.0)
        # With 162 games of 0.30 K%, lambda should be higher than with 0 games (league avg)
        assert rec_full["lambda"] > rec_no["lambda"]


class TestCalcMovementConfidence:
    def test_negative_delta_no_penalty(self):
        # Movement in our favour — no penalty
        assert calc_movement_confidence(-15) == 1.0

    def test_zero_delta_no_penalty(self):
        assert calc_movement_confidence(0) == 1.0

    def test_below_noise_floor_no_penalty(self):
        assert calc_movement_confidence(5) == 1.0

    def test_at_noise_floor_no_penalty(self):
        # Exactly at noise_floor (10) → still 1.0
        assert calc_movement_confidence(10) == 1.0

    def test_midpoint_decay(self):
        # delta=20 is halfway between noise_floor=10 and full_fade=30 → 0.50
        assert abs(calc_movement_confidence(20) - 0.50) < 0.001

    def test_quarter_decay(self):
        # delta=15 → (15-10)/(30-10) = 5/20 = 0.25 penalty → 0.75
        assert abs(calc_movement_confidence(15) - 0.75) < 0.001

    def test_three_quarter_decay(self):
        # delta=25 → (25-10)/(30-10) = 15/20 = 0.75 penalty → 0.25
        assert abs(calc_movement_confidence(25) - 0.25) < 0.001

    def test_at_full_fade(self):
        assert calc_movement_confidence(30) == 0.0

    def test_above_full_fade_clamped(self):
        # Anything beyond full_fade is still 0.0
        assert calc_movement_confidence(40) == 0.0


class TestBayesianOppK:
    def test_zero_games_returns_league_avg(self):
        # No data → full regression to mean
        assert bayesian_opp_k(0.40, 0) == pytest.approx(LEAGUE_AVG_K_RATE)

    def test_negative_games_returns_league_avg(self):
        # Guard against bad data
        assert bayesian_opp_k(0.40, -5) == pytest.approx(LEAGUE_AVG_K_RATE)

    def test_early_season_extreme_high_regressed(self):
        # 8 games, extreme 45% K rate (OPP K% +145% territory)
        # With prior=50: (8*0.45 + 50*0.227) / 58 = (3.6 + 11.35) / 58 ≈ 0.2578
        result = bayesian_opp_k(0.45, 8)
        assert result < 0.27   # well below observed 0.45
        assert result > LEAGUE_AVG_K_RATE  # still slightly above average

    def test_early_season_extreme_low_regressed(self):
        # Low opp K% team gets pulled up toward average (symmetric)
        result = bayesian_opp_k(0.15, 8)
        assert result > 0.20   # pulled up toward 0.227
        assert result < LEAGUE_AVG_K_RATE  # still slightly below average

    def test_mid_season_partial_trust(self):
        # 81 games: (81*0.30 + 50*0.227) / 131 ≈ 0.274
        result = bayesian_opp_k(0.30, 81)
        assert 0.265 < result < 0.285

    def test_full_season_dominates(self):
        # 162 games, prior=50: (162*0.30 + 50*0.227) / 212 ≈ 0.2828
        # Observed data dominates — result clearly above league avg (0.227)
        result = bayesian_opp_k(0.30, 162)
        assert result > 0.275  # well above league avg, trending toward observed 0.30

    def test_league_avg_obs_unchanged(self):
        # If observed == league avg, result should equal league avg regardless of games
        assert bayesian_opp_k(LEAGUE_AVG_K_RATE, 8) == pytest.approx(LEAGUE_AVG_K_RATE)
        assert bayesian_opp_k(LEAGUE_AVG_K_RATE, 162) == pytest.approx(LEAGUE_AVG_K_RATE)


# -- load_params tests --

class TestLoadParams:
    def test_missing_file_returns_defaults(self):
        with patch("build_features.PARAMS_PATH", "/nonexistent/path/params.json"):
            from build_features import load_params
            p = load_params()
        assert p["lambda_bias"] == 0.0
        assert p["ump_scale"] == 1.0
        assert "ev_thresholds" not in p  # thresholds are now static constants, not in params

    def test_malformed_file_returns_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json{{{")
            path = f.name
        with patch("build_features.PARAMS_PATH", path):
            from build_features import load_params
            p = load_params()
        os.unlink(path)
        assert p["lambda_bias"] == 0.0

    def test_valid_file_overrides_defaults(self):
        data = {"lambda_bias": 0.3, "ump_scale": 0.8,
                "weight_season_cap": 0.65, "weight_recent": 0.25}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        with patch("build_features.PARAMS_PATH", path):
            from build_features import load_params
            p = load_params()
        os.unlink(path)
        assert p["lambda_bias"] == 0.3
        assert p["ump_scale"] == 0.8

    def test_partial_file_merges_with_defaults(self):
        data = {"lambda_bias": 0.5}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        with patch("build_features.PARAMS_PATH", path):
            from build_features import load_params
            p = load_params()
        os.unlink(path)
        assert p["lambda_bias"] == 0.5
        assert p["ump_scale"] == 1.0  # default intact

    def test_ev_thresholds_not_in_params(self):
        """ev_thresholds are static constants, never loaded from params file."""
        data = {"ev_thresholds": {"fire2": 0.99}}  # should be ignored
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        with patch("build_features.PARAMS_PATH", path):
            from build_features import load_params
            p = load_params()
        os.unlink(path)
        # ev_thresholds from file is ignored — it may appear as a stale key
        # but the pipeline never reads it; calc_verdict uses module constants
        from build_features import EDGE_FIRE_1U
        assert EDGE_FIRE_1U == 0.09


# -- blend_k9 weight params tests --

class TestBlendK9Params:
    def test_custom_season_cap_applied(self):
        # With cap=0.5: w_season=min(90/60, 0.5)=0.5, w_recent=0.2, w_career=0.3
        result = blend_k9(10.0, 9.0, 8.0, ip=90, weight_season_cap=0.5, weight_recent=0.2)
        expected = 0.5 * 10.0 + 0.2 * 9.0 + 0.3 * 8.0  # 5.0+1.8+2.4=9.2
        assert abs(result - expected) < 0.01

    def test_custom_recent_weight_applied(self):
        result = blend_k9(10.0, 9.0, 8.0, ip=0, weight_season_cap=0.70, weight_recent=0.30)
        # w_season=0, w_recent=0.30, w_career=0.70
        expected = 0.0 * 10.0 + 0.30 * 9.0 + 0.70 * 8.0  # 0+2.7+5.6=8.3
        assert abs(result - expected) < 0.01

    def test_w_career_never_negative(self):
        # weight_season_cap=0.8, weight_recent=0.3 → sum>1 at high IP, career should be 0 not negative
        result = blend_k9(10.0, 9.0, 8.0, ip=90, weight_season_cap=0.8, weight_recent=0.3)
        assert result >= 0


# -- calc_verdict threshold params tests --

class TestCalcVerdictThresholds:
    def test_static_thresholds(self):
        """EV thresholds are fixed: LEAN 1-3%, FIRE 1u 3-9%, FIRE 2u >9%."""
        assert calc_verdict(0.005) == "PASS"
        assert calc_verdict(0.02) == "LEAN"
        assert calc_verdict(0.05) == "FIRE 1u"
        assert calc_verdict(0.10) == "FIRE 2u"
        # Boundary tests
        assert calc_verdict(0.01) == "PASS"      # exactly 1% → PASS
        assert calc_verdict(0.03) == "LEAN"      # exactly 3% → LEAN
        assert calc_verdict(0.09) == "FIRE 1u"   # exactly 9% → FIRE 1u
        assert calc_verdict(0.091) == "FIRE 2u"  # just over 9% → FIRE 2u


# -- build_pitcher_record output fields --

SAMPLE_ODDS = {
    "pitcher": "Test Pitcher", "team": "Test Team", "opp_team": "Opp Team",
    "game_time": "2026-04-01T17:05:00Z", "k_line": 6.5,
    "opening_line": 6.5, "best_over_book": "FD",
    "best_over_odds": -115, "best_under_odds": -105,
    "opening_over_odds": -110, "opening_under_odds": -110,
}
SAMPLE_STATS = {
    "season_k9": 9.0, "recent_k9": 9.0, "career_k9": 8.0,
    "innings_pitched_season": 30.0, "avg_ip_last5": 5.5,
    "opp_k_rate": 0.227, "opp_games_played": 20, "starts_count": 5,
}

class TestBuildPitcherRecordFields:
    def test_raw_lambda_and_lambda_present(self):
        rec = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 0.0)
        assert "raw_lambda" in rec
        assert "lambda" in rec

    def test_raw_lambda_equals_lambda_when_no_bias(self):
        with patch("build_features.PARAMS_PATH", "/nonexistent"):
            rec = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 0.0)
        assert rec["raw_lambda"] == rec["lambda"]

    def test_lambda_bias_applied_to_lambda_not_raw(self):
        data = {"lambda_bias": 0.5}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f); path = f.name
        with patch("build_features.PARAMS_PATH", path):
            rec = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 0.0)
        os.unlink(path)
        assert abs(rec["lambda"] - (rec["raw_lambda"] + 0.5)) < 0.01

    def test_k9_components_in_output(self):
        rec = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 0.0)
        assert "season_k9" in rec
        assert "recent_k9" in rec
        assert "career_k9" in rec

    def test_ump_scale_applied(self):
        data = {"ump_scale": 0.0}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f); path = f.name
        with patch("build_features.PARAMS_PATH", path):
            rec_scaled = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 1.0)
        with patch("build_features.PARAMS_PATH", "/nonexistent"):
            rec_default = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 1.0)
        os.unlink(path)
        assert rec_scaled["raw_lambda"] < rec_default["raw_lambda"]
