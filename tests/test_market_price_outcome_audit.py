from analytics.diagnostics.market_price_outcome_audit import (
    american_implied_probability,
    build_report,
    line_bucket,
    market_favorite_side,
    model_market_gap_bucket,
    miss_distance_bucket,
    no_vig_probabilities,
    no_vig_side_probability,
    no_vig_movement_bucket,
    price_movement_bucket,
    price_bucket,
    summarize_book_side_price_buckets,
    summarize_book_outliers,
    summarize_game_timing,
    summarize_line_side_price_contexts,
    summarize_line_buckets,
    summarize_lineup_state,
    summarize_miss_distance,
    summarize_model_market_gap,
    summarize_model_vs_favorite,
    summarize_no_vig_movement,
    summarize_pitcher_repeat_errors,
    summarize_side_movement_contexts,
    summarize_favorite_results,
    summarize_side_price_buckets,
    time_to_game_bucket,
    winning_side,
)


def test_winning_side_compares_actual_strikeouts_to_line():
    assert winning_side(actual_ks=6, k_line=5.5) == "over"
    assert winning_side(actual_ks=4, k_line=4.5) == "under"
    assert winning_side(actual_ks=5, k_line=5.0) == "push"


def test_price_bucket_groups_minus_and_plus_ranges():
    assert price_bucket(-115) == "-100 to -129"
    assert price_bucket(-130) == "-130 to -149"
    assert price_bucket(-150) == "-150 to -200"
    assert price_bucket(105) == "+100 to +119"
    assert price_bucket(125) == "+120 to +149"
    assert price_bucket(166) == "+150+"


def test_line_bucket_groups_common_pitcher_k_lines():
    assert line_bucket(3.5) == "2.5-3.5"
    assert line_bucket(4.5) == "4.5"
    assert line_bucket(5.5) == "5.5"
    assert line_bucket(6.5) == "6.5"
    assert line_bucket(7.5) == "7.5+"


def test_miss_distance_bucket_separates_close_and_smoked_results():
    assert miss_distance_bucket(winning_side_name="over", actual_ks=6, k_line=5.5) == "won by 0.5"
    assert miss_distance_bucket(winning_side_name="under", actual_ks=3, k_line=5.5) == "won by 2+"
    assert miss_distance_bucket(winning_side_name="under", actual_ks=2, k_line=5.5) == "won by 3+"


def test_market_favorite_side_uses_relative_implied_probability():
    assert market_favorite_side(-115, -105) == "over"
    assert market_favorite_side(-105, -115) == "under"
    assert market_favorite_side(105, 120) == "over"
    assert market_favorite_side(120, -105) == "under"
    assert market_favorite_side(-110, -110) == "tie"


def test_price_movement_bucket_uses_side_specific_odds_direction():
    assert price_movement_bucket(opening_odds=-115, current_odds=-140) == "with_side"
    assert price_movement_bucket(opening_odds=-115, current_odds=105) == "against_side"
    assert price_movement_bucket(opening_odds=-115, current_odds=-108) == "unchanged"


def test_american_implied_probability_supports_positive_and_negative_odds():
    assert american_implied_probability(-150) == 0.6
    assert round(american_implied_probability(120), 4) == 0.4545


def test_no_vig_probabilities_remove_two_sided_hold():
    over, under = no_vig_probabilities(-120, 100)

    assert round(over + under, 6) == 1.0
    assert round(over, 4) == 0.5217
    assert round(under, 4) == 0.4783


def test_no_vig_side_probability_returns_requested_side():
    assert round(no_vig_side_probability(-120, 100, "over"), 4) == 0.5217
    assert round(no_vig_side_probability(-120, 100, "under"), 4) == 0.4783


def test_model_market_gap_bucket_groups_edge_over_market():
    assert model_market_gap_bucket(-0.01) == "model below market"
    assert model_market_gap_bucket(0.015) == "0-2%"
    assert model_market_gap_bucket(0.04) == "2-5%"
    assert model_market_gap_bucket(0.08) == "5%+"


def test_no_vig_movement_bucket_uses_probability_direction():
    assert no_vig_movement_bucket(0.48, 0.54) == "toward_side"
    assert no_vig_movement_bucket(0.54, 0.48) == "away_from_side"
    assert no_vig_movement_bucket(0.50, 0.505) == "unchanged"


def test_time_to_game_bucket_groups_freshness():
    assert time_to_game_bucket("2026-05-01T18:00:00Z", "2026-05-01T19:30:00Z") == "<2h"
    assert time_to_game_bucket("2026-05-01T12:00:00Z", "2026-05-01T19:30:00Z") == "6h+"


def test_summarize_favorite_results_tracks_favorite_wins_including_double_minus():
    markets = [
        {
            "winning_side": "over",
            "over_odds": -115,
            "under_odds": -105,
        },
        {
            "winning_side": "over",
            "over_odds": -105,
            "under_odds": -115,
        },
        {
            "winning_side": "under",
            "over_odds": 105,
            "under_odds": 120,
        },
    ]

    summary = summarize_favorite_results(markets)

    assert summary["favorite"]["markets"] == 3
    assert summary["favorite"]["wins"] == 1
    assert summary["underdog"]["wins"] == 2


def test_summarize_side_price_buckets_counts_each_market_side():
    markets = [
        {
            "winning_side": "over",
            "over_odds": -135,
            "under_odds": 105,
        },
        {
            "winning_side": "under",
            "over_odds": 120,
            "under_odds": -160,
        },
    ]

    summary = summarize_side_price_buckets(markets)

    assert summary[("over", "-130 to -149")]["wins"] == 1
    assert summary[("over", "+120 to +149")]["losses"] == 1
    assert summary[("under", "+100 to +119")]["losses"] == 1
    assert summary[("under", "-150 to -200")]["wins"] == 1


def test_summarize_side_movement_contexts_tracks_side_sign_transition_and_result():
    markets = [
        {
            "winning_side": "over",
            "over_odds": -140,
            "under_odds": 105,
            "opening_over_odds": -115,
            "opening_under_odds": -105,
        },
        {
            "winning_side": "under",
            "over_odds": -150,
            "under_odds": 102,
            "opening_over_odds": -125,
            "opening_under_odds": -155,
        },
    ]

    summary = summarize_side_movement_contexts(markets)

    over_key = ("over", "with_side", "- money -> - money")
    under_key = ("under", "against_side", "- money -> + money")
    assert summary[over_key]["wins"] == 1
    assert summary[under_key]["wins"] == 1
    assert summary[under_key]["losses"] == 1
    assert summary[under_key]["avg_delta"] == 233.5


def test_summarize_model_vs_favorite_tracks_agreement_and_disagreement():
    markets = [
        {
            "winning_side": "over",
            "over_odds": -130,
            "under_odds": 105,
            "model_side": "over",
        },
        {
            "winning_side": "under",
            "over_odds": -130,
            "under_odds": 105,
            "model_side": "under",
        },
    ]

    summary = summarize_model_vs_favorite(markets)

    assert summary["model_agrees_with_favorite"]["wins"] == 1
    assert summary["model_fades_favorite"]["wins"] == 1


def test_summarize_model_market_gap_tracks_model_probability_over_market():
    markets = [
        {
            "winning_side": "over",
            "over_odds": -120,
            "under_odds": 100,
            "model_side": "over",
            "model_win_prob": 0.57,
        },
        {
            "winning_side": "under",
            "over_odds": -120,
            "under_odds": 100,
            "model_side": "over",
            "model_win_prob": 0.51,
        },
    ]

    summary = summarize_model_market_gap(markets)

    assert summary["2-5%"]["wins"] == 1
    assert summary["model below market"]["losses"] == 1


def test_summarize_no_vig_movement_tracks_probability_movement():
    markets = [
        {
            "winning_side": "over",
            "over_odds": -130,
            "under_odds": 105,
            "opening_over_odds": -110,
            "opening_under_odds": -110,
        }
    ]

    summary = summarize_no_vig_movement(markets)

    assert summary[("over", "toward_side")]["wins"] == 1
    assert summary[("under", "away_from_side")]["losses"] == 1


def test_summarize_pitcher_repeat_errors_tracks_directional_tendencies():
    markets = [
        {"pitcher": "Repeat Arm", "winning_side": "over", "actual_ks": 7, "k_line": 5.5},
        {"pitcher": "Repeat Arm", "winning_side": "over", "actual_ks": 6, "k_line": 4.5},
        {"pitcher": "Repeat Arm", "winning_side": "under", "actual_ks": 3, "k_line": 4.5},
    ]

    summary = summarize_pitcher_repeat_errors(markets, min_markets=2)

    assert summary["Repeat Arm"]["markets"] == 3
    assert summary["Repeat Arm"]["over_wins"] == 2


def test_summarize_book_outliers_flags_ref_book_away_from_market():
    markets = [
        {
            "winning_side": "over",
            "ref_book": "FanDuel",
            "book_odds": {
                "FanDuel": {"over": -140, "under": 110},
                "BetMGM": {"over": -110, "under": -110},
                "DraftKings": {"over": -112, "under": -108},
            },
        }
    ]

    summary = summarize_book_outliers(markets, min_delta=20)

    assert summary[("FanDuel", "over", "ref_more_favored")]["wins"] == 1


def test_summarize_game_timing_tracks_freshness_to_start():
    markets = [
        {
            "winning_side": "over",
            "model_side": "over",
            "generated_at": "2026-05-01T18:00:00Z",
            "game_time": "2026-05-01T19:30:00Z",
        }
    ]

    summary = summarize_game_timing(markets)

    assert summary["<2h"]["wins"] == 1


def test_summarize_lineup_state_tracks_confirmed_vs_projected():
    markets = [
        {"winning_side": "under", "model_side": "under", "lineup_used": True},
        {"winning_side": "over", "model_side": "under", "lineup_used": False},
    ]

    summary = summarize_lineup_state(markets)

    assert summary["confirmed_lineup"]["wins"] == 1
    assert summary["projected_lineup"]["losses"] == 1


def test_summarize_line_side_price_contexts_tracks_trap_line_candidates():
    markets = [
        {"winning_side": "under", "k_line": 7.5, "under_odds": -120, "over_odds": 100},
        {"winning_side": "over", "k_line": 3.5, "under_odds": -140, "over_odds": 110},
    ]

    summary = summarize_line_side_price_contexts(markets)

    assert summary[("under", "7.5+", "-100 to -129")]["wins"] == 1
    assert summary[("over", "2.5-3.5", "+100 to +119")]["wins"] == 1


def test_summarize_line_buckets_tracks_market_rows_by_k_line():
    markets = [
        {"winning_side": "over", "k_line": 4.5},
        {"winning_side": "under", "k_line": 7.5},
    ]

    summary = summarize_line_buckets(markets)

    assert summary["4.5"]["wins"] == 1
    assert summary["7.5+"]["losses"] == 1


def test_summarize_miss_distance_tracks_margin_quality():
    markets = [
        {"winning_side": "over", "actual_ks": 6, "k_line": 5.5},
        {"winning_side": "under", "actual_ks": 2, "k_line": 5.5},
    ]

    summary = summarize_miss_distance(markets)

    assert summary["won by 0.5"]["markets"] == 1
    assert summary["won by 3+"]["markets"] == 1


def test_summarize_book_side_price_buckets_keeps_book_context():
    markets = [
        {
            "winning_side": "over",
            "ref_book": "FanDuel",
            "over_odds": -135,
            "under_odds": 105,
        }
    ]

    summary = summarize_book_side_price_buckets(markets)

    assert summary[("FanDuel", "over", "-130 to -149")]["wins"] == 1
    assert summary[("FanDuel", "under", "+100 to +119")]["losses"] == 1


def test_build_report_includes_shadow_scope_and_market_favorite_section():
    report = build_report(
        [
            {
                "date": "2026-04-28",
                "winning_side": "over",
                "over_odds": -115,
                "under_odds": -105,
                "opening_over_odds": -125,
                "opening_under_odds": -100,
                "model_side": "over",
            }
        ],
        title="Test Market Price Audit",
    )

    assert "# Test Market Price Audit" in report
    assert "shadow-only" in report
    assert "## Market Favorite Results" in report
    assert "## Side Price Movement Contexts" in report
    assert "## Model Versus Market Favorite" in report
    assert "## Line Buckets" in report
    assert "## Miss Distance" in report
    assert "## Book Side Price Buckets" in report
    assert "## Model Edge Over No-Vig Market" in report
    assert "## No-Vig Movement" in report
    assert "## Pitcher Repeat Tendencies" in report
    assert "## Book Outliers" in report
    assert "## Game Timing" in report
    assert "## Lineup State" in report
    assert "## Line Side Price Contexts" in report
    assert "`-115` vs `-105`" in report
