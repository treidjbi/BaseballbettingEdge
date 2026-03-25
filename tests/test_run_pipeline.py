import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from run_pipeline import _update_index_dates


class TestUpdateIndexDates:
    def test_prepends_new_date(self):
        result = _update_index_dates(["2026-03-26", "2026-03-25"], "2026-03-27")
        assert result[0] == "2026-03-27"

    def test_existing_dates_preserved_in_order(self):
        result = _update_index_dates(["2026-03-26", "2026-03-25"], "2026-03-27")
        assert result == ["2026-03-27", "2026-03-26", "2026-03-25"]

    def test_deduplicates_same_date(self):
        # Running pipeline twice on same day should not duplicate the date
        result = _update_index_dates(["2026-03-27", "2026-03-26"], "2026-03-27")
        assert result.count("2026-03-27") == 1
        assert len(result) == 2

    def test_caps_at_max_entries(self):
        # List must be most-recent-first, so descending — "2026-01-01" is oldest (last)
        existing = [f"2026-01-{i:02d}" for i in range(60, 0, -1)]  # 60 dates, most recent first
        result = _update_index_dates(existing, "2026-03-27", max_entries=60)
        assert len(result) == 60
        assert result[0] == "2026-03-27"
        assert "2026-01-01" not in result  # oldest entry dropped

    def test_empty_existing_returns_single_entry(self):
        result = _update_index_dates([], "2026-03-27")
        assert result == ["2026-03-27"]

    def test_respects_custom_max_entries(self):
        existing = ["2026-03-26", "2026-03-25", "2026-03-24"]
        result = _update_index_dates(existing, "2026-03-27", max_entries=3)
        assert len(result) == 3
        assert "2026-03-24" not in result
