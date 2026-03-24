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
