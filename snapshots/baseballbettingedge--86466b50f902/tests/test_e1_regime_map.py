from analytics.diagnostics.e1_regime_map import classify_regime, summarize_regimes


def test_classify_regime_pre_formula_cutover():
    assert classify_regime("2026-04-07") == "pre_2026_04_08"


def test_classify_regime_phase_a_to_pre_swstr_live():
    assert classify_regime("2026-04-16") == "phase_a_to_pre_swstr_live"


def test_classify_regime_swstr_transition_window():
    assert classify_regime("2026-04-27") == "swstr_roi_transition"


def test_classify_regime_clean_post_roi_window():
    assert classify_regime("2026-04-28") == "post_roi_clean"


def test_summarize_regimes_groups_counts_rates_and_field_presence():
    rows = [
        {
            "date": "2026-04-07",
            "actual_ks": 6,
            "locked_at": "2026-04-07T16:00:00Z",
            "data_complete": 1,
            "pitcher_throws": "R",
            "career_swstr_pct": 11.2,
            "swstr_delta_k9": None,
            "park_factor": 1.01,
            "days_since_last_start": 5,
            "last_pitch_count": 93,
            "rest_k9_delta": 0.2,
            "opening_odds_source": "fanduel",
            "edge": 0.08,
        },
        {
            "date": "2026-04-07",
            "actual_ks": None,
            "locked_at": None,
            "data_complete": 0,
            "pitcher_throws": None,
            "career_swstr_pct": None,
            "swstr_delta_k9": None,
            "park_factor": None,
            "days_since_last_start": None,
            "last_pitch_count": None,
            "rest_k9_delta": None,
            "opening_odds_source": None,
        },
        {
            "date": "2026-04-28",
            "actual_ks": 4,
            "locked_at": "2026-04-28T17:00:00Z",
            "data_complete": 1,
            "pitcher_throws": "L",
            "career_swstr_pct": 10.4,
            "swstr_delta_k9": 0.6,
            "park_factor": 0.98,
            "days_since_last_start": 6,
            "last_pitch_count": 88,
            "rest_k9_delta": -0.1,
            "opening_odds_source": "draftkings",
            "edge": 0.05,
        },
    ]

    summary = summarize_regimes(rows)

    assert summary["pre_2026_04_08"]["row_count"] == 2
    assert summary["pre_2026_04_08"]["graded_row_count"] == 1
    assert summary["pre_2026_04_08"]["locked_row_count"] == 1
    assert summary["pre_2026_04_08"]["data_complete_rate"] == 0.5
    assert (
        summary["pre_2026_04_08"]["field_presence_rates"]["pitcher_throws"] == 0.5
    )
    assert summary["pre_2026_04_08"]["field_presence_rates"]["edge"] == 0.5
    assert summary["post_roi_clean"]["row_count"] == 1
    assert summary["post_roi_clean"]["graded_row_count"] == 1
    assert summary["post_roi_clean"]["locked_row_count"] == 1
    assert summary["post_roi_clean"]["data_complete_rate"] == 1.0
    assert (
        summary["post_roi_clean"]["field_presence_rates"]["opening_odds_source"] == 1.0
    )
