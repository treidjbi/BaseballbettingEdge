from __future__ import annotations

from datetime import date

from analytics.diagnostics import alternative_pick_v2_historical_comparator as comparator


def test_legacy_official_close_comparator_reproduces_frozen_lane_anchors():
    rows = comparator.load_legacy_parity_fixture(comparator.DEFAULT_PARITY_INPUT)

    summary = comparator.summarize_legacy_official_close(rows)

    assert summary["research_only"] is True
    assert len(rows) == 1621
    assert set().union(*(row for row in rows)) <= comparator.LEGACY_PARITY_FIELDS
    assert summary["observed"]["consensus_core"] == {
        "rows": 152, "wins": 106, "losses": 46, "pnl": 32.603,
    }
    assert summary["observed"]["reentry_expansion"] == {
        "rows": 80, "wins": 42, "losses": 38, "pnl": 5.982,
    }
    assert summary["observed"]["combined"] == {
        "rows": 232, "wins": 148, "losses": 84, "pnl": 38.585,
    }
    assert summary["matches_frozen_anchors"] is True


def test_legacy_comparator_cutoff_is_2026_07_20_and_never_writes_prospective_state():
    rows = comparator.load_legacy_parity_fixture(comparator.DEFAULT_PARITY_INPUT)

    summary = comparator.summarize_legacy_official_close(rows, end_date=date(2026, 7, 20))

    assert summary["end_date"] == "2026-07-20"
    assert min(row["slate_date"] for row in rows) == "2026-04-28"
    assert max(row["slate_date"] for row in rows) == "2026-07-20"
    assert summary["prospective_ledger"] == {"rows": 0, "pnl": 0.0}
    assert not any("prospective" in key or "result" in key for key in summary["lane_rows"])

    manifest = comparator.load_fixture_manifest()
    parity = manifest["fixtures"]["legacy_official_close_parity.json.gz"]
    assert parity["classification"] == "hindsight_capable_research_only"
    assert parity["fixed_start_date"] == "2026-04-28"
    assert parity["fixed_end_date"] == "2026-07-20"
    assert parity["row_count"] == 1621
    assert parity["source_corpus_row_count"] == 3106
    assert parity["source_tracked_pick_row_count"] == 1621
    assert parity["source_corpus_sha256"] == (
        "c59cc4fd2a03110ad492163240f5563a85e142d785c258eeb25914ad0273bda4"
    )
    assert parity["source_manifest_sha256"] == (
        "7f59abe7a4522e793e68a58bac92122585fbfea76658a63b0d09bb3195c85072"
    )
