from analytics.diagnostics.d_connection_health import (
    build_connection_health,
    format_stage_summary,
)


def test_format_stage_summary_uses_stable_key_value_output():
    message = format_stage_summary(
        "fetch_stats",
        0.1234,
        requested=2,
        resolved=1,
    )

    assert message == "stage=fetch_stats ms=123 requested=2 resolved=1"


def test_build_connection_health_counts_missing_stats_and_build_failures():
    props = [
        {"pitcher": "Built Pitcher"},
        {"pitcher": "Missing Stats Pitcher"},
        {"pitcher": "Build Failed Pitcher"},
    ]
    stats_map = {
        "Built Pitcher": {"team": "A"},
        "Build Failed Pitcher": {"team": "B"},
    }
    records = [
        {"pitcher": "Built Pitcher"},
    ]

    health = build_connection_health(
        props,
        stats_map,
        records,
        build_failures=["Build Failed Pitcher"],
    )

    assert health == {
        "props_seen": 3,
        "stats_resolved": 2,
        "records_built": 1,
        "unresolved_count": 2,
        "model_candidate_count": 2,
        "intake_filtered_count": 1,
        "missing_stats_count": 1,
        "unresolved_after_stats_count": 1,
        "feature_build_failures_count": 1,
        "ignored_non_starter_count": 0,
        "degraded": True,
        "sample_intake_filtered_pitchers": [
            "Missing Stats Pitcher",
        ],
        "sample_feature_build_failures": [
            "Build Failed Pitcher",
        ],
        "sample_ignored_non_starter_props": [],
        "sample_unresolved_pitchers": [
            "Missing Stats Pitcher",
            "Build Failed Pitcher",
        ],
    }


def test_build_connection_health_separates_ignored_non_starter_noise():
    props = [
        {"pitcher": "Built Pitcher"},
        {"pitcher": "Real Probable Pitcher"},
        {"pitcher": "Hitter Noise"},
    ]
    stats_map = {
        "Built Pitcher": {"team": "A"},
    }
    records = [
        {"pitcher": "Built Pitcher"},
    ]

    health = build_connection_health(
        props,
        stats_map,
        records,
        ignored_non_starter_names=["Hitter Noise"],
    )

    assert health["props_seen"] == 3
    assert health["ignored_non_starter_count"] == 1
    assert health["sample_ignored_non_starter_props"] == ["Hitter Noise"]
    assert health["missing_stats_count"] == 1
    assert health["unresolved_count"] == 1
    assert health["sample_unresolved_pitchers"] == ["Real Probable Pitcher"]
