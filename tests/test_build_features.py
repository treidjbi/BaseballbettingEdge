import pytest
import sys
import os
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
        lam = calc_lambda(blended_k9=9.0, expected_innings=5.5, opp_k_rate=0.255, ump_k_adj=0)
        assert lam > 5.5

    def test_low_k_opponent_deflates_lambda(self):
        lam = calc_lambda(blended_k9=9.0, expected_innings=5.5, opp_k_rate=0.200, ump_k_adj=0)
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
        assert calc_verdict(0.04) == "FIRE 1u"

    def test_fire_2u(self):
        assert calc_verdict(0.07) == "FIRE 2u"


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
        from build_features import build_pitcher_record
        rec = build_pitcher_record(self.BASE_ODDS, self.BASE_STATS, ump_k_adj=0.0)
        # At 9.0 K/9, neutral conditions, 6.0 IP → lambda = 6.0
        assert abs(rec["lambda"] - 6.0) < 0.05
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
