from analytics.diagnostics import confidence_referee_canary_audit as audit


def test_load_rows_accepts_gate_c_jsonl(tmp_path):
    path = tmp_path / "gate_c.jsonl"
    path.write_text(
        '{"pitcher":"A","confidence_referee":{"mode":"enforce"}}\n'
        '{"pitcher":"B","confidence_referee":null}\n',
        encoding="utf-8",
    )

    rows = audit.load_rows(path)

    assert [row["pitcher"] for row in rows] == ["A", "B"]


def test_summarize_counts_modes_relationships_and_applied_caps():
    rows = [
        {
            "raw_verdict": "FIRE 2u",
            "verdict": "LEAN",
            "confidence_referee": {
                "mode": "enforce",
                "relationship": "model_fades_favorite",
                "applied": True,
            },
        },
        {
            "raw_verdict": "FIRE 1u",
            "verdict": "FIRE 1u",
            "confidence_referee": {
                "mode": "shadow",
                "relationship": "model_agrees_with_favorite",
                "applied": False,
            },
        },
    ]

    summary = audit.summarize(rows)

    assert summary["total_rows"] == 2
    assert summary["rows_with_referee_metadata"] == 2
    assert summary["applied_caps"] == 1
    assert summary["mode_counts"] == {"enforce": 1, "shadow": 1}
    assert summary["relationship_counts"] == {
        "model_agrees_with_favorite": 1,
        "model_fades_favorite": 1,
    }


def test_summarize_tolerates_missing_or_non_object_referee_metadata():
    rows = [
        {"verdict": "PASS"},
        {"verdict": "LEAN", "confidence_referee": None},
        {"verdict": "FIRE 1u", "confidence_referee": "not-a-dict"},
        {
            "verdict": "FIRE 2u",
            "confidence_referee": {"mode": "enforce", "relationship": "unknown"},
        },
    ]

    summary = audit.summarize(rows)

    assert summary["total_rows"] == 4
    assert summary["rows_with_referee_metadata"] == 1
    assert summary["applied_caps"] == 0
    assert summary["mode_counts"] == {"enforce": 1}
    assert summary["relationship_counts"] == {"unknown": 1}


def test_summarize_accepts_stringified_referee_metadata_and_display_verdict():
    rows = [
        {
            "raw_verdict": "FIRE 2u",
            "display_verdict": "LEAN",
            "confidence_referee": '{"mode":"enforce","relationship":"model_fades_favorite","applied":true}',
        }
    ]

    summary = audit.summarize(rows)

    assert summary["rows_with_referee_metadata"] == 1
    assert summary["applied_caps"] == 1
    assert summary["cap_transition_counts"] == {"FIRE 2u -> LEAN": 1}


def test_summarize_counts_applied_cap_transitions():
    rows = [
        {
            "raw_verdict": "FIRE 2u",
            "verdict": "FIRE 1u",
            "confidence_referee": {"mode": "enforce", "applied": True},
        },
        {
            "raw_verdict": "FIRE 2u",
            "verdict": "LEAN",
            "confidence_referee": {"mode": "enforce", "applied": True},
        },
        {
            "raw_verdict": "FIRE 2u",
            "verdict": "LEAN",
            "confidence_referee": {"mode": "shadow", "applied": False},
        },
    ]

    summary = audit.summarize(rows)

    assert summary["applied_caps"] == 2
    assert summary["cap_transition_counts"] == {
        "FIRE 2u -> FIRE 1u": 1,
        "FIRE 2u -> LEAN": 1,
    }


def test_build_report_names_feature_flag_audit_evidence():
    report = audit.build_report(
        [
            {
                "raw_verdict": "FIRE 2u",
                "verdict": "LEAN",
                "confidence_referee": {
                    "mode": "enforce",
                    "relationship": "model_fades_favorite",
                    "applied": True,
                },
            }
        ]
    )

    assert "# Confidence Referee Canary Audit" in report
    assert "feature-flag audit evidence" in report
    assert "Gate C pitcher outcome dataset" in report
    assert "FIRE 2u -> LEAN" in report
