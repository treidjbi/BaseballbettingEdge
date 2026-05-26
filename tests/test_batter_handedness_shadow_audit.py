from analytics.diagnostics.batter_handedness_shadow_audit import (
    build_report,
    summarize_path_b_readiness,
)


def _row(**overrides):
    row = {
        "slate_date": "2026-05-25",
        "is_tracked_pick": True,
        "pitcher_throws": "R",
        "lineup_count": 9,
        "lineup_right_batters": None,
        "lineup_left_batters": None,
        "lineup_switch_batters": None,
        "handedness_matchup_bucket": None,
        "result": "win",
        "side": "over",
        "pick_history_pnl": 0.91,
    }
    row.update(overrides)
    return row


def test_summarize_path_b_readiness_blocks_live_lambda_without_record_level_counts():
    cache = {
        "batters": {
            "mlbam:1": {
                "vs_R": {"pa": 100, "k_rate": 0.2},
                "vs_L": {"pa": 80, "k_rate": 0.1},
            },
            "mlbam:2": {
                "vs_R": {"pa": 40, "k_rate": 0.25},
            },
        },
        "last_run": {"requested_batters": 2, "already_cached": 1, "attempted": 1},
    }

    summary = summarize_path_b_readiness(
        [_row(), _row(pitcher_throws="L")],
        cache,
        params={"sample_size": 501},
        current_date="2026-05-26",
    )

    assert summary["date_or_sample_trigger_met"] is True
    assert summary["pitcher_throws_rows"] == 2
    assert summary["lineup_count_rows"] == 2
    assert summary["lineup_hand_count_rows"] == 0
    assert summary["cache_batters"] == 2
    assert summary["cache_batters_with_both_splits"] == 1
    assert summary["path_b_live_lambda_ready"] is False
    assert "lineup hand counts are not populated" in summary["blockers"]


def test_summarize_path_b_readiness_opens_shadow_audit_when_coverage_exists():
    rows = [
        _row(lineup_right_batters=5, lineup_left_batters=3, lineup_switch_batters=1, handedness_matchup_bucket="balanced"),
        _row(lineup_right_batters=6, lineup_left_batters=2, lineup_switch_batters=1, handedness_matchup_bucket="right_heavy"),
    ]
    cache = {
        "batters": {
            "mlbam:1": {
                "vs_R": {"pa": 120, "k_rate": 0.2},
                "vs_L": {"pa": 90, "k_rate": 0.1},
            },
        }
    }

    summary = summarize_path_b_readiness(
        rows,
        cache,
        params={"sample_size": 501},
        current_date="2026-05-26",
    )

    assert summary["lineup_hand_count_rows"] == 2
    assert summary["handedness_bucket_rows"] == 2
    assert summary["handedness_matchup_bucket_counts"]["right_heavy"] == 1
    assert summary["handedness_matchup_bucket_counts"]["balanced"] == 1
    assert summary["tracked_outcome_by_bucket"]["balanced"]["rows"] == 1
    assert summary["tracked_outcome_by_bucket"]["right_heavy"]["pnl"] == 0.91
    assert summary["path_b_shadow_audit_ready"] is True
    assert summary["path_b_live_lambda_ready"] is False
    assert "holdout lift versus Path A has not been proven" in summary["blockers"]


def test_build_report_names_collection_promotion_not_live_model_promotion():
    report = build_report(
        [_row()],
        {"batters": {}},
        params={"sample_size": 501},
        current_date="2026-05-26",
    )

    assert "# Batter Handedness Path B Shadow Audit" in report
    assert "Path A is already live" in report
    assert "Path B live lambda status: `not ready`" in report
    assert "Promote now: active shadow collection/audit" in report
    assert "Do not promote now: live projection math" in report
    assert "## Tracked Outcome By Matchup Bucket" in report


def test_build_report_names_holdout_as_next_step_when_path_b_coverage_exists():
    report = build_report(
        [
            _row(lineup_right_batters=6, lineup_left_batters=2, lineup_switch_batters=1, handedness_matchup_bucket="same_hand_heavy"),
        ],
        {"batters": {"mlbam:1": {"vs_R": {"pa": 120}, "vs_L": {"pa": 90}}}},
        params={"sample_size": 501},
        current_date="2026-05-26",
    )

    assert "Path B shadow audit status: `ready for deeper audit`" in report
    assert "Next useful implementation: run a holdout comparison of Path B versus Path A" in report
