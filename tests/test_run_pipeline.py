import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from run_pipeline import _game_date_et


class TestGameDateEt:
    def test_utc_midnight_converts_to_previous_et_date(self):
        # 00:05 UTC on Mar 26 is 20:05 ET on Mar 25 (ET = UTC-4 in summer / UTC-5 in winter)
        # Mar 26 is after DST spring-forward (2026), so ET = UTC-4; 00:05Z → 20:05 ET Mar 25
        result = _game_date_et("2026-03-26T00:05:00Z", "2026-03-26")
        assert result == "2026-03-25"

    def test_afternoon_game_stays_same_et_date(self):
        # 19:10 UTC = 15:10 ET (EDT, UTC-4) — still Mar 26
        result = _game_date_et("2026-03-26T19:10:00Z", "2026-03-26")
        assert result == "2026-03-26"

    def test_empty_string_returns_fallback(self):
        result = _game_date_et("", "2026-03-25")
        assert result == "2026-03-25"

    def test_unparseable_string_returns_fallback(self):
        result = _game_date_et("not-a-date", "2026-03-25")
        assert result == "2026-03-25"
