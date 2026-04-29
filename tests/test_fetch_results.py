import json, os, sys, sqlite3, tempfile, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))


@pytest.fixture
def tmp_db(tmp_path):
    """Patch DB_PATH and HISTORY_PATH to temp files, yield path."""
    db = tmp_path / "results.db"
    history = tmp_path / "picks_history.json"
    with patch("fetch_results.DB_PATH", db), patch("fetch_results.HISTORY_PATH", history):
        import fetch_results
        fetch_results.init_db()
        fetch_results.HISTORY_PATH = history
        yield db, fetch_results


@pytest.fixture
def today_json(tmp_path):
    """Write a minimal today.json and return path."""
    data = {
        "date": "2026-04-15",
        "props_available": True,
        "pitchers": [
            {
                "pitcher": "Gerrit Cole", "team": "New York", "opp_team": "Boston",
                "game_time": "2026-04-15T17:05:00Z", "k_line": 7.5,
                "raw_lambda": 7.2, "lambda": 7.2,
                "season_k9": 9.1, "recent_k9": 8.8, "career_k9": 9.0,
                "avg_ip": 5.8, "opp_k_rate": 0.235, "ump_k_adj": 0.2,
                "best_over_odds": -115, "best_under_odds": -105,
                "ref_book": "FanDuel",
                "pitcher_throws": "R",
                "opening_over_odds": -110,
                "opening_under_odds": -110,
                "swstr_pct": 0.120,
                "career_swstr_pct": 0.110,
                "swstr_delta_k9": 0.05,
                "ev_over":  {"edge": 0.032, "ev": 0.05, "adj_ev": 0.05, "verdict": "FIRE 1u", "win_prob": 0.58, "movement_conf": 1.0},
                "ev_under": {"edge": -0.018, "ev": -0.02, "adj_ev": -0.02, "verdict": "PASS", "win_prob": 0.42, "movement_conf": 1.0},
            },
            {
                "pitcher": "Shane Bieber", "team": "Cleveland", "opp_team": "Detroit",
                "game_time": "2026-04-15T18:10:00Z", "k_line": 6.5,
                "raw_lambda": 6.1, "lambda": 6.1,
                "season_k9": 8.5, "recent_k9": 8.2, "career_k9": 8.8,
                "avg_ip": 5.5, "opp_k_rate": 0.220, "ump_k_adj": 0.0,
                "best_over_odds": -110, "best_under_odds": -110,
                "ref_book": "FanDuel",
                "pitcher_throws": "R",
                "opening_over_odds": -110,
                "opening_under_odds": -110,
                "swstr_pct": 0.115,
                "career_swstr_pct": 0.108,
                "swstr_delta_k9": 0.03,
                "ev_over":  {"edge": 0.004, "ev": 0.008, "adj_ev": 0.008, "verdict": "PASS",   "win_prob": 0.51, "movement_conf": 1.0},
                "ev_under": {"edge": 0.041, "ev": 0.07,  "adj_ev": 0.07,  "verdict": "FIRE 2u","win_prob": 0.49, "movement_conf": 1.0},
            },
        ],
    }
    p = tmp_path / "today.json"
    p.write_text(json.dumps(data))
    return p, data


def test_seed_picks_missing_file_returns_zero():
    """seed_picks should return 0 and log a warning when today.json is missing."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from pathlib import Path
    from fetch_results import seed_picks
    result = seed_picks(Path("/nonexistent/path/today.json"))
    assert result == 0


def test_seed_picks_corrupt_json_returns_zero(tmp_path):
    """seed_picks should return 0 when today.json contains invalid JSON."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from fetch_results import seed_picks
    bad_json = tmp_path / "today.json"
    bad_json.write_text("{not valid json{{")
    result = seed_picks(bad_json)
    assert result == 0


class TestInitDb:
    def test_creates_picks_table(self, tmp_db):
        db_path, fr = tmp_db
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert ("picks",) in tables
        conn.close()

    def test_creates_unique_index(self, tmp_db):
        db_path, fr = tmp_db
        conn = sqlite3.connect(db_path)
        idx = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_picks_date_pitcher_side'").fetchone()
        assert idx is not None
        conn.close()

    def test_idempotent(self, tmp_db):
        """init_db twice does not error."""
        db_path, fr = tmp_db
        fr.init_db()  # second call

    def test_ref_book_column_exists(self, tmp_db):
        """picks table should have a ref_book column."""
        db_path, fr = tmp_db
        conn = sqlite3.connect(db_path)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(picks)").fetchall()]
        conn.close()
        assert "ref_book" in cols

    def test_quality_gate_columns_exist(self, tmp_db):
        """picks table stores raw/actionable verdict metadata."""
        db_path, fr = tmp_db
        conn = sqlite3.connect(db_path)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(picks)").fetchall()]
        conn.close()
        assert "raw_verdict" in cols
        assert "actionable_verdict" in cols
        assert "quality_gate_level" in cols
        assert "input_quality_flags_json" in cols
        assert "verdict_cap_reason" in cols
        assert "data_maturity_json" in cols
        assert "raw_adj_ev" in cols


class TestSeedPicks:
    def test_only_non_pass_sides_inserted(self, tmp_db, today_json):
        db_path, fr = tmp_db
        p, data = today_json
        count = fr.seed_picks(p)
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT pitcher, side, verdict FROM picks ORDER BY pitcher, side").fetchall()
        conn.close()
        # Cole: over=FIRE 1u (insert), under=PASS (skip)
        # Bieber: over=PASS (skip), under=FIRE 2u (insert)
        assert len(rows) == 2
        assert ("Gerrit Cole", "over", "FIRE 1u") in rows
        assert ("Shane Bieber", "under", "FIRE 2u") in rows

    def test_insert_or_ignore_on_rerun(self, tmp_db, today_json):
        db_path, fr = tmp_db
        p, _ = today_json
        fr.seed_picks(p)
        fr.seed_picks(p)  # second run, same data
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
        conn.close()
        assert count == 2  # no duplicates

    def test_seeds_correct_fields(self, tmp_db, today_json):
        db_path, fr = tmp_db
        p, _ = today_json
        fr.seed_picks(p)
        conn = sqlite3.connect(db_path)
        row = dict(zip(
            [d[1] for d in conn.execute("PRAGMA table_info(picks)").fetchall()],
            conn.execute("SELECT * FROM picks WHERE pitcher='Gerrit Cole'").fetchone()
        ))
        conn.close()
        assert row is not None
        assert row["k_line"] == 7.5
        assert row["odds"] == -115
        assert row["raw_lambda"] == 7.2
        assert row["edge"] == 0.032

    def test_returns_inserted_count(self, tmp_db, today_json):
        db_path, fr = tmp_db
        p, _ = today_json
        assert fr.seed_picks(p) == 2
        assert fr.seed_picks(p) == 0  # second run inserts nothing

    def test_seeds_ref_book(self, tmp_db, today_json):
        """seed_picks stores ref_book from today.json."""
        db_path, fr = tmp_db
        p, _ = today_json
        fr.seed_picks(p)
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT ref_book FROM picks WHERE pitcher='Gerrit Cole'").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "FanDuel"

    def test_seed_uses_actionable_verdict_and_preserves_raw_quality_fields(self, tmp_db, tmp_path):
        db_path, fr = tmp_db
        today = {
            "date": "2026-04-29",
            "pitchers": [
                {
                    "pitcher": "Quality Pitcher",
                    "team": "A",
                    "opp_team": "B",
                    "pitcher_throws": "R",
                    "game_time": "2026-04-29T20:05:00Z",
                    "k_line": 6.5,
                    "raw_lambda": 7.4,
                    "lambda": 7.4,
                    "season_k9": 9.8,
                    "recent_k9": 10.2,
                    "career_k9": 9.5,
                    "avg_ip": 5.9,
                    "opp_k_rate": 0.24,
                    "ump_k_adj": 0.0,
                    "best_over_odds": -110,
                    "best_under_odds": -110,
                    "ref_book": "FanDuel",
                    "opening_over_odds": -110,
                    "opening_under_odds": -110,
                    "opening_odds_source": "preview",
                    "lineup_used": True,
                    "data_complete": True,
                    "input_quality_flags": ["unrated_umpire"],
                    "quality_gate_level": "capped",
                    "verdict_cap_reason": "1 soft input flag: unrated_umpire",
                    "data_maturity": {"pitcher": "mature", "umpire": "unknown", "lineup": "confirmed", "market": "preview_open"},
                    "ev_over": {
                        "edge": 0.08,
                        "ev": 0.19,
                        "adj_ev": 0.19,
                        "raw_adj_ev": 0.19,
                        "raw_verdict": "FIRE 2u",
                        "actionable_verdict": "FIRE 1u",
                        "verdict": "FIRE 1u",
                        "win_prob": 0.61,
                        "movement_conf": 1.0,
                    },
                    "ev_under": {"edge": -0.03, "ev": -0.04, "adj_ev": -0.04, "verdict": "PASS", "win_prob": 0.39, "movement_conf": 1.0},
                }
            ],
        }
        today_path = tmp_path / "today.json"
        today_path.write_text(json.dumps(today))

        assert fr.seed_picks(today_path) == 1

        conn = sqlite3.connect(db_path)
        row = conn.execute("""
            SELECT verdict, raw_verdict, actionable_verdict, quality_gate_level,
                   input_quality_flags_json, verdict_cap_reason, data_maturity_json, raw_adj_ev
            FROM picks WHERE pitcher='Quality Pitcher'
        """).fetchone()
        conn.close()

        assert row[0] == "FIRE 1u"
        assert row[1] == "FIRE 2u"
        assert row[2] == "FIRE 1u"
        assert row[3] == "capped"
        assert json.loads(row[4]) == ["unrated_umpire"]
        assert row[5] == "1 soft input flag: unrated_umpire"
        assert json.loads(row[6])["umpire"] == "unknown"
        assert row[7] == 0.19

    def test_seed_skips_blocked_pass_even_when_raw_verdict_is_fire(self, tmp_db, tmp_path):
        db_path, fr = tmp_db
        today = {
            "date": "2026-04-29",
            "pitchers": [
                {
                    "pitcher": "Blocked Pitcher",
                    "team": "A",
                    "opp_team": "B",
                    "game_time": "2026-04-29T20:05:00Z",
                    "k_line": 6.5,
                    "raw_lambda": 7.4,
                    "lambda": 7.4,
                    "best_over_odds": -110,
                    "best_under_odds": -110,
                    "opening_over_odds": -110,
                    "opening_under_odds": -110,
                    "ev_over": {
                        "edge": 0.08,
                        "ev": 0.19,
                        "adj_ev": 0.0,
                        "raw_adj_ev": 0.19,
                        "raw_verdict": "FIRE 2u",
                        "actionable_verdict": "PASS",
                        "verdict": "PASS",
                        "win_prob": 0.61,
                        "movement_conf": 1.0,
                    },
                    "ev_under": {"edge": -0.03, "ev": -0.04, "adj_ev": 0.0, "raw_verdict": "PASS", "actionable_verdict": "PASS", "verdict": "PASS", "win_prob": 0.39, "movement_conf": 1.0},
                }
            ],
        }
        today_path = tmp_path / "today.json"
        today_path.write_text(json.dumps(today))

        assert fr.seed_picks(today_path) == 0

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
        conn.close()
        assert count == 0


class TestLoadHistoryIntoDb:
    def test_loads_closed_picks_into_db(self, tmp_db, tmp_path):
        """load_history_into_db inserts history records into the DB."""
        db_path, fr = tmp_db
        history = [
            {
                "date": "2026-03-31", "pitcher": "Max Fried", "team": "NYY",
                "side": "over", "k_line": 5.5, "verdict": "FIRE 2u",
                "edge": 0.031,
                "ev": 0.08, "adj_ev": 0.08, "raw_lambda": 6.1, "applied_lambda": 6.1,
                "odds": -110, "movement_conf": 1.0,
                "season_k9": 9.0, "recent_k9": 8.5, "career_k9": 9.2,
                "avg_ip": 5.5, "ump_k_adj": 0.1, "opp_k_rate": 0.23,
                "result": "win", "actual_ks": 7, "pnl": 0.909,
                "fetched_at": "2026-04-01T03:00:00Z", "ref_book": "FanDuel",
            }
        ]
        history_path = tmp_path / "picks_history.json"
        history_path.write_text(json.dumps(history))
        fr.load_history_into_db(history_path)
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT pitcher, result FROM picks").fetchall()
        conn.close()
        assert ("Max Fried", "win") in rows

    def test_ignores_duplicate_on_reload(self, tmp_db, tmp_path):
        """Calling load_history_into_db twice doesn't duplicate records."""
        db_path, fr = tmp_db
        history = [
            {
                "date": "2026-03-31", "pitcher": "Max Fried", "team": "NYY",
                "side": "over", "k_line": 5.5, "verdict": "FIRE 2u",
                "edge": 0.031,
                "ev": 0.08, "adj_ev": 0.08, "raw_lambda": 6.1, "applied_lambda": 6.1,
                "odds": -110, "movement_conf": 1.0,
                "season_k9": 9.0, "recent_k9": 8.5, "career_k9": 9.2,
                "avg_ip": 5.5, "ump_k_adj": 0.1, "opp_k_rate": 0.23,
                "result": "win", "actual_ks": 7, "pnl": 0.909,
                "fetched_at": "2026-04-01T03:00:00Z", "ref_book": "FanDuel",
            }
        ]
        history_path = tmp_path / "picks_history.json"
        history_path.write_text(json.dumps(history))
        fr.load_history_into_db(history_path)
        fr.load_history_into_db(history_path)
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]
        conn.close()
        assert count == 1

    def test_loads_quality_gate_fields_from_history(self, tmp_db, tmp_path):
        db_path, fr = tmp_db
        history = [
            {
                "date": "2026-04-29",
                "pitcher": "Quality Pitcher",
                "team": "A",
                "side": "over",
                "k_line": 6.5,
                "verdict": "FIRE 1u",
                "raw_verdict": "FIRE 2u",
                "actionable_verdict": "FIRE 1u",
                "edge": 0.08,
                "ev": 0.19,
                "adj_ev": 0.19,
                "raw_adj_ev": 0.19,
                "raw_lambda": 7.4,
                "applied_lambda": 7.4,
                "odds": -110,
                "movement_conf": 1.0,
                "quality_gate_level": "capped",
                "input_quality_flags": ["unrated_umpire"],
                "verdict_cap_reason": "1 soft input flag: unrated_umpire",
                "data_maturity": {"umpire": "unknown"},
            }
        ]
        history_path = tmp_path / "picks_history.json"
        history_path.write_text(json.dumps(history))

        fr.load_history_into_db(history_path)

        conn = sqlite3.connect(db_path)
        row = conn.execute("""
            SELECT raw_verdict, actionable_verdict, raw_adj_ev, quality_gate_level,
                   input_quality_flags_json, verdict_cap_reason, data_maturity_json
            FROM picks WHERE pitcher='Quality Pitcher'
        """).fetchone()
        conn.close()

        assert row[0] == "FIRE 2u"
        assert row[1] == "FIRE 1u"
        assert row[2] == 0.19
        assert row[3] == "capped"
        assert json.loads(row[4]) == ["unrated_umpire"]
        assert row[5] == "1 soft input flag: unrated_umpire"
        assert json.loads(row[6])["umpire"] == "unknown"

    def test_returns_zero_if_file_missing(self, tmp_db, tmp_path):
        """load_history_into_db returns 0 when history file doesn't exist."""
        db_path, fr = tmp_db
        result = fr.load_history_into_db(tmp_path / "nonexistent.json")
        assert result == 0


class TestExportDbToHistory:
    def test_writes_closed_picks_to_json(self, tmp_db, tmp_path):
        """export_db_to_history writes all closed picks to JSON."""
        db_path, fr = tmp_db
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT INTO picks (date, pitcher, team, side, k_line, verdict,
                  edge, ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf,
                  result, actual_ks, pnl)
                VALUES ('2026-04-01','Zack Wheeler','PHI','over',6.5,'FIRE 2u',
                  0.041,0.09,0.09,7.1,7.1,-108,1.0,'win',8,0.926)
            """)
            conn.execute("""
                INSERT INTO picks (date, pitcher, team, side, k_line, verdict,
                  edge, ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf,
                  result)
                VALUES ('2026-04-02','Dylan Cease','SDP','over',5.5,'FIRE 1u',
                  0.026,0.05,0.05,6.0,6.0,-110,1.0, NULL)
            """)
        history_path = tmp_path / "picks_history.json"
        fr.export_db_to_history(history_path)
        written = json.loads(history_path.read_text())
        pitchers = [r["pitcher"] for r in written]
        assert "Zack Wheeler" in pitchers
        assert "Dylan Cease" in pitchers  # open picks included for GHA persistence
        wheeler = next(r for r in written if r["pitcher"] == "Zack Wheeler")
        assert wheeler["edge"] == pytest.approx(0.041)

    def test_exports_quality_gate_fields_to_history(self, tmp_db, tmp_path):
        db_path, fr = tmp_db
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT INTO picks (
                  date, pitcher, team, side, k_line, verdict,
                  raw_verdict, actionable_verdict,
                  edge, ev, adj_ev, raw_adj_ev,
                  raw_lambda, applied_lambda, odds, movement_conf,
                  quality_gate_level, input_quality_flags_json,
                  verdict_cap_reason, data_maturity_json
                )
                VALUES (
                  '2026-04-29','Quality Pitcher','A','over',6.5,'FIRE 1u',
                  'FIRE 2u','FIRE 1u',
                  0.08,0.19,0.19,0.19,
                  7.4,7.4,-110,1.0,
                  'capped','["unrated_umpire"]',
                  '1 soft input flag: unrated_umpire','{"umpire":"unknown"}'
                )
            """)
        history_path = tmp_path / "picks_history.json"

        fr.export_db_to_history(history_path)

        written = json.loads(history_path.read_text())
        row = written[0]
        assert row["raw_verdict"] == "FIRE 2u"
        assert row["actionable_verdict"] == "FIRE 1u"
        assert row["raw_adj_ev"] == 0.19
        assert row["quality_gate_level"] == "capped"
        assert row["input_quality_flags"] == ["unrated_umpire"]
        assert row["verdict_cap_reason"] == "1 soft input flag: unrated_umpire"
        assert row["data_maturity"]["umpire"] == "unknown"

    def test_overwrites_existing_file(self, tmp_db, tmp_path):
        """export_db_to_history replaces existing history file."""
        db_path, fr = tmp_db
        history_path = tmp_path / "picks_history.json"
        history_path.write_text('[{"stale": true}]')
        fr.export_db_to_history(history_path)
        written = json.loads(history_path.read_text())
        assert written == []  # empty DB → empty array


def _make_schedule_response(pitcher_name: str, ks: int, game_final: bool = True):
    """Build a minimal MLB schedule+boxscore API response."""
    return {
        "dates": [{
            "date": "2026-04-14",
            "games": [{
                "gamePk": 111111,
                "status": {"abstractGameState": "Final" if game_final else "Live"},
                "teams": {
                    "home": {"team": {"name": "New York Yankees", "abbreviation": "NYY"}},
                    "away": {"team": {"name": "Boston Red Sox",   "abbreviation": "BOS"}},
                },
                "boxscore": {
                    "teams": {
                        "home": {
                            "pitchers": [123],
                            "players": {
                                "ID123": {
                                    "person": {"fullName": pitcher_name},
                                    "stats": {"pitching": {"strikeOuts": ks}},
                                }
                            },
                        },
                        "away": {"pitchers": [], "players": {}},
                    }
                },
            }]
        }]
    }


def _sched_resp(game_pk=12345, is_final=True):
    """Minimal schedule API response for two-call HTTP flow tests."""
    return {
        "dates": [{
            "games": [{
                "gamePk": game_pk,
                "status": {"abstractGameState": "Final" if is_final else "Live"},
                "teams": {
                    "home": {"team": {"name": "New York Yankees", "abbreviation": "NYY"}},
                    "away": {"team": {"name": "Boston Red Sox", "abbreviation": "BOS"}},
                }
            }]
        }]
    }


def _bs_resp(starter_name="Gerrit Cole", starter_id=123, ks=7):
    """Minimal boxscore API response for two-call HTTP flow tests."""
    return {
        "teams": {
            "home": {
                "pitchers": [starter_id],
                "players": {
                    f"ID{starter_id}": {
                        "person": {"fullName": starter_name},
                        "stats": {"pitching": {"strikeOuts": ks}}
                    }
                }
            },
            "away": {"pitchers": [], "players": {}}
        }
    }


_FIXED_TODAY     = "2026-04-08"
_FIXED_YESTERDAY = "2026-04-07"


class TestFetchAndCloseResults:
    def _seed_yesterday_pick(self, db_path, fr, pitcher="Gerrit Cole", side="over",
                              k_line=7.5, odds=-115, verdict="FIRE 1u"):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("""
            INSERT INTO picks (date, pitcher, team, side, k_line, verdict,
                               ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf)
            VALUES (?, ?,?,?,?,?,0.05,0.05,7.2,7.2,?,1.0)
        """, (_FIXED_YESTERDAY, pitcher, "New York Yankees", side, k_line, verdict, odds))
        conn.commit()
        conn.close()

    def test_win_over_recorded(self, tmp_db):
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, pitcher="Gerrit Cole", side="over", k_line=7.5)

        schedule_mock = MagicMock()
        schedule_mock.json.return_value = _sched_resp(game_pk=111111, is_final=True)
        schedule_mock.raise_for_status = MagicMock()

        boxscore_mock = MagicMock()
        boxscore_mock.json.return_value = _bs_resp("Gerrit Cole", 123, ks=8)
        boxscore_mock.raise_for_status = MagicMock()

        def mock_get(url, **kwargs):
            if "boxscore" in url:
                return boxscore_mock
            return schedule_mock

        with patch("fetch_results._et_dates", return_value=(_FIXED_TODAY, _FIXED_YESTERDAY)), \
             patch("fetch_results.requests.get", side_effect=mock_get):
            count = fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result, actual_ks, pnl FROM picks WHERE pitcher='Gerrit Cole'").fetchone()
        conn.close()
        assert row[0] == "win"
        assert row[1] == 8
        assert row[2] > 0

    def test_loss_over_recorded(self, tmp_db):
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, pitcher="Gerrit Cole", side="over", k_line=7.5)

        schedule_mock = MagicMock()
        schedule_mock.json.return_value = _sched_resp(game_pk=111111, is_final=True)
        schedule_mock.raise_for_status = MagicMock()

        boxscore_mock = MagicMock()
        boxscore_mock.json.return_value = _bs_resp("Gerrit Cole", 123, ks=6)
        boxscore_mock.raise_for_status = MagicMock()

        def mock_get(url, **kwargs):
            if "boxscore" in url:
                return boxscore_mock
            return schedule_mock

        with patch("fetch_results._et_dates", return_value=(_FIXED_TODAY, _FIXED_YESTERDAY)), \
             patch("fetch_results.requests.get", side_effect=mock_get):
            fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result, pnl FROM picks WHERE pitcher='Gerrit Cole'").fetchone()
        conn.close()
        assert row[0] == "loss"
        assert row[1] == -1.0

    def test_push_recorded(self, tmp_db):
        """Whole number line, pitcher hits exactly the line."""
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, pitcher="Gerrit Cole", side="over", k_line=7.0)

        schedule_mock = MagicMock()
        schedule_mock.json.return_value = _sched_resp(game_pk=111111, is_final=True)
        schedule_mock.raise_for_status = MagicMock()

        boxscore_mock = MagicMock()
        boxscore_mock.json.return_value = _bs_resp("Gerrit Cole", 123, ks=7)
        boxscore_mock.raise_for_status = MagicMock()

        def mock_get(url, **kwargs):
            if "boxscore" in url:
                return boxscore_mock
            return schedule_mock

        with patch("fetch_results._et_dates", return_value=(_FIXED_TODAY, _FIXED_YESTERDAY)), \
             patch("fetch_results.requests.get", side_effect=mock_get):
            fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result, pnl FROM picks").fetchone()
        conn.close()
        assert row[0] == "push"
        assert row[1] == 0.0

    def test_game_not_final_skipped(self, tmp_db):
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr)

        schedule_mock = MagicMock()
        schedule_mock.json.return_value = _sched_resp(game_pk=111111, is_final=False)
        schedule_mock.raise_for_status = MagicMock()

        # No boxscore call expected when game is not final, but define it defensively
        boxscore_mock = MagicMock()
        boxscore_mock.json.return_value = _bs_resp("Gerrit Cole", 123, ks=8)
        boxscore_mock.raise_for_status = MagicMock()

        def mock_get(url, **kwargs):
            if "boxscore" in url:
                return boxscore_mock
            return schedule_mock

        with patch("fetch_results.requests.get", side_effect=mock_get):
            count = fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result FROM picks").fetchone()
        conn.close()
        assert row[0] is None  # not closed
        assert count == 0

    def test_void_when_game_final_but_name_mismatch(self, tmp_db):
        """Pitcher scratched: game Final but their name not in starters."""
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, pitcher="Gerrit Cole")

        schedule_mock = MagicMock()
        schedule_mock.json.return_value = _sched_resp(game_pk=111111, is_final=True)
        schedule_mock.raise_for_status = MagicMock()

        boxscore_mock = MagicMock()
        boxscore_mock.json.return_value = _bs_resp("Other Pitcher", 123, ks=5)
        boxscore_mock.raise_for_status = MagicMock()

        def mock_get(url, **kwargs):
            if "boxscore" in url:
                return boxscore_mock
            return schedule_mock

        with patch("fetch_results._et_dates", return_value=(_FIXED_TODAY, _FIXED_YESTERDAY)), \
             patch("fetch_results.requests.get", side_effect=mock_get):
            fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result, pnl FROM picks WHERE pitcher='Gerrit Cole'").fetchone()
        conn.close()
        assert row[0] == "void"
        assert row[1] == 0.0

    def test_pnl_positive_odds(self, tmp_db):
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, odds=120, side="under", k_line=7.5)

        schedule_mock = MagicMock()
        schedule_mock.json.return_value = _sched_resp(game_pk=111111, is_final=True)
        schedule_mock.raise_for_status = MagicMock()

        boxscore_mock = MagicMock()
        # under wins when actual < line: 6 < 7.5
        boxscore_mock.json.return_value = _bs_resp("Gerrit Cole", 123, ks=6)
        boxscore_mock.raise_for_status = MagicMock()

        def mock_get(url, **kwargs):
            if "boxscore" in url:
                return boxscore_mock
            return schedule_mock

        with patch("fetch_results._et_dates", return_value=(_FIXED_TODAY, _FIXED_YESTERDAY)), \
             patch("fetch_results.requests.get", side_effect=mock_get):
            fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        pnl = conn.execute("SELECT pnl FROM picks").fetchone()[0]
        conn.close()
        assert abs(pnl - 1.20) < 0.01


class TestCloseOrphans:
    def _insert_pick(self, db_path, date_str, pitcher="Test Pitcher"):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("""
            INSERT INTO picks (date, pitcher, team, side, k_line, verdict,
                               ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf)
            VALUES (?,?,?,?,?,?,0.05,0.05,6.0,6.0,-110,1.0)
        """, (date_str, pitcher, "Test", "over", 6.5, "FIRE 1u"))
        conn.commit()
        conn.close()

    def test_old_null_result_marked_cancelled(self, tmp_db):
        db_path, fr = tmp_db
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")
        # close_orphans threshold is 7 days — use 8 to guarantee we're past it.
        old_date = (datetime.now(ET) - timedelta(days=8)).strftime("%Y-%m-%d")
        self._insert_pick(db_path, old_date)

        fr.close_orphans()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result, pnl FROM picks").fetchone()
        conn.close()
        assert row[0] == "cancelled"
        assert row[1] == 0.0

    def test_recent_null_result_untouched(self, tmp_db):
        db_path, fr = tmp_db
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")
        yesterday = (datetime.now(ET) - timedelta(days=1)).strftime("%Y-%m-%d")
        self._insert_pick(db_path, yesterday)

        fr.close_orphans()

        import sqlite3
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result FROM picks").fetchone()
        conn.close()
        assert row[0] is None  # untouched

    def test_already_closed_untouched(self, tmp_db):
        db_path, fr = tmp_db
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")
        old_date = (datetime.now(ET) - timedelta(days=5)).strftime("%Y-%m-%d")
        self._insert_pick(db_path, old_date)
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE picks SET result='win', pnl=0.87")
        conn.commit()
        conn.close()

        fr.close_orphans()

        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT result FROM picks").fetchone()
        conn.close()
        assert row[0] == "win"  # unchanged


def test_void_detection_does_not_cross_match_ny_teams(tmp_path):
    """A Mets pitcher should NOT be voided when only a Yankees game is final."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    import fetch_results
    from unittest.mock import patch, MagicMock

    db_path = tmp_path / "results.db"
    with patch.object(fetch_results, "DB_PATH", db_path):
        fetch_results.init_db()
        # Seed a Mets pitcher pick for yesterday
        with fetch_results.get_db() as conn:
            conn.execute("""
                INSERT INTO picks (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                                   raw_lambda, applied_lambda, odds, movement_conf)
                VALUES ('2026-03-31','Jacob deGrom','new york mets','over',
                        6.5,'FIRE 2u',0.10,0.09,5.5,5.5,-110,1.0)
            """)

        # Schedule: only Yankees game is final — Mets game is NOT final
        schedule_resp = MagicMock()
        schedule_resp.raise_for_status = MagicMock()
        schedule_resp.json.return_value = {
            "dates": [{
                "games": [
                    {
                        "gamePk": 1,
                        "status": {"abstractGameState": "Final"},
                        "teams": {
                            "home": {"team": {"name": "New York Yankees", "abbreviation": "NYY"}},
                            "away": {"team": {"name": "Boston Red Sox", "abbreviation": "BOS"}},
                        }
                    },
                    {
                        "gamePk": 2,
                        "status": {"abstractGameState": "Live"},  # Mets game NOT final
                        "teams": {
                            "home": {"team": {"name": "New York Mets", "abbreviation": "NYM"}},
                            "away": {"team": {"name": "Atlanta Braves", "abbreviation": "ATL"}},
                        }
                    }
                ]
            }]
        }

        boxscore_resp = MagicMock()
        boxscore_resp.raise_for_status = MagicMock()
        boxscore_resp.json.return_value = {
            "teams": {
                "home": {"pitchers": [999], "players": {
                    "ID999": {"person": {"fullName": "Gerrit Cole"},
                              "stats": {"pitching": {"strikeOuts": 8}}}
                }},
                "away": {"pitchers": [], "players": {}}
            }
        }

        def mock_get(url, **kwargs):
            if "boxscore" in url:
                return boxscore_resp
            return schedule_resp

        with patch("fetch_results.requests.get", side_effect=mock_get):
            with patch("fetch_results._et_dates", return_value=("2026-04-01", "2026-03-31")):
                closed = fetch_results.fetch_and_close_results()

        # Mets pitcher should NOT be voided (Yankees game finished but Mets game did not)
        with fetch_results.get_db() as conn:
            pick = conn.execute(
                "SELECT result FROM picks WHERE pitcher='Jacob deGrom'"
            ).fetchone()
        assert pick["result"] is None  # still open — not voided
        assert closed == 0


def test_schema_has_game_time_and_lock_columns(tmp_db):
    """init_db should create all new columns."""
    db_path, fr = tmp_db
    conn = sqlite3.connect(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(picks)")}
    conn.close()
    assert "game_time"     in cols
    assert "lineup_used"   in cols
    assert "locked_at"     in cols
    assert "locked_k_line" in cols
    assert "locked_odds"   in cols
    assert "locked_adj_ev" in cols
    assert "locked_verdict" in cols


def test_seed_picks_stores_game_time(tmp_db, today_json):
    """seed_picks should store game_time from today.json."""
    db_path, fr = tmp_db
    json_path, _ = today_json
    with patch("fetch_results.TODAY_JSON", json_path):
        fr.seed_picks(json_path)
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT game_time FROM picks").fetchall()
    conn.close()
    assert all(r[0] is not None for r in rows)
    assert rows[0][0] == "2026-04-15T17:05:00Z"


def test_seed_picks_stores_lineup_used_false_by_default(tmp_db, today_json):
    """seed_picks should store lineup_used=0 when field absent from today.json."""
    db_path, fr = tmp_db
    json_path, _ = today_json
    with patch("fetch_results.TODAY_JSON", json_path):
        fr.seed_picks(json_path)
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT lineup_used FROM picks").fetchall()
    conn.close()
    assert all(r[0] == 0 for r in rows)


def test_seed_picks_stores_lineup_used_true(tmp_db, tmp_path):
    """seed_picks should store lineup_used=1 when field is True in today.json."""
    import json as _json
    data = {
        "date": "2026-04-15",
        "props_available": True,
        "pitchers": [{
            "pitcher": "Gerrit Cole", "team": "New York", "opp_team": "Boston",
            "game_time": "2026-04-15T17:05:00Z", "k_line": 7.5,
            "raw_lambda": 7.2, "lambda": 7.2,
            "season_k9": 9.1, "recent_k9": 8.8, "career_k9": 9.0,
            "avg_ip": 5.8, "opp_k_rate": 0.235, "ump_k_adj": 0.2,
            "best_over_odds": -115, "best_under_odds": -105,
            "ref_book": "FanDuel",
            "lineup_used": True,
            "ev_over":  {"ev": 0.05, "adj_ev": 0.05, "verdict": "FIRE 1u", "win_prob": 0.58, "movement_conf": 1.0},
            "ev_under": {"ev": -0.02, "adj_ev": -0.02, "verdict": "PASS", "win_prob": 0.42, "movement_conf": 1.0},
        }],
    }
    json_path = tmp_path / "today_lineup.json"
    json_path.write_text(_json.dumps(data))
    db_path, fr = tmp_db
    import sqlite3 as _sqlite3
    fr.seed_picks(json_path)
    conn = _sqlite3.connect(db_path)
    val = conn.execute("SELECT lineup_used FROM picks WHERE side='over'").fetchone()[0]
    conn.close()
    assert val == 1


def test_fetch_and_close_results_calls_boxscore_separately(tmp_path):
    """Verify fetch_and_close_results makes two HTTP calls: schedule then boxscore."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    import fetch_results
    from unittest.mock import patch, MagicMock

    db_path = tmp_path / "results.db"
    with patch.object(fetch_results, "DB_PATH", db_path):
        fetch_results.init_db()
        with fetch_results.get_db() as conn:
            conn.execute("""
                INSERT INTO picks (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                                   raw_lambda, applied_lambda, odds, movement_conf)
                VALUES ('2026-03-31','Chris Sale','Boston Red Sox','over',7.5,'FIRE 2u',0.10,0.09,
                        5.5,5.5,-110,1.0)
            """)

        schedule_mock = MagicMock()
        schedule_mock.json.return_value = _sched_resp(game_pk=99, is_final=True)
        schedule_mock.raise_for_status = MagicMock()

        boxscore_mock = MagicMock()
        boxscore_mock.json.return_value = _bs_resp("Chris Sale", 456, ks=8)
        boxscore_mock.raise_for_status = MagicMock()

        call_count = [0]
        def mock_get(url, **kwargs):
            call_count[0] += 1
            if "boxscore" in url:
                return boxscore_mock
            return schedule_mock

        with patch("fetch_results.requests.get", side_effect=mock_get):
            with patch("fetch_results._et_dates", return_value=("2026-04-01", "2026-03-31")):
                closed = fetch_results.fetch_and_close_results()

        # Two HTTP calls: schedule + boxscore
        assert call_count[0] == 2
        assert closed == 1


def _seed_pick_with_game_time(conn, game_time_str, side="over", adj_ev=0.05, odds=-115):
    """Helper: insert a minimal open pick with given game_time."""
    conn.execute("""
        INSERT INTO picks (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                           raw_lambda, applied_lambda, odds, movement_conf, game_time)
        VALUES ('2026-04-15','Test Pitcher','NYY',?,7.5,'FIRE 1u',0.05,?,7.2,7.2,?,1.0,?)
    """, (side, adj_ev, odds, game_time_str))
    conn.commit()


def test_lock_due_picks_locks_imminent_game(tmp_db):
    """A pick whose game starts in 20 min should be locked."""
    db_path, fr = tmp_db
    now = datetime(2026, 4, 15, 17, 0, 0, tzinfo=timezone.utc)
    game_time = "2026-04-15T17:20:00Z"  # 20 min from now
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, game_time)
    with fr.get_db() as conn:
        count = fr.lock_due_picks(conn, now, lock_window_minutes=30)
    assert count == 1
    with fr.get_db() as conn:
        row = conn.execute("SELECT locked_at, locked_odds, locked_adj_ev FROM picks").fetchone()
    assert row["locked_at"] is not None
    assert row["locked_odds"] == -115
    assert abs(row["locked_adj_ev"] - 0.05) < 0.001


def test_lock_due_picks_skips_future_game(tmp_db):
    """A pick with game in 2 hours should NOT be locked."""
    db_path, fr = tmp_db
    now = datetime(2026, 4, 15, 15, 0, 0, tzinfo=timezone.utc)
    game_time = "2026-04-15T17:10:00Z"  # 2h 10min away
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, game_time)
    with fr.get_db() as conn:
        count = fr.lock_due_picks(conn, now, lock_window_minutes=30)
    assert count == 0


def test_lock_due_picks_idempotent(tmp_db):
    """Calling lock twice should not update locked_at a second time."""
    db_path, fr = tmp_db
    now = datetime(2026, 4, 15, 17, 0, 0, tzinfo=timezone.utc)
    game_time = "2026-04-15T17:10:00Z"
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, game_time)
    with fr.get_db() as conn:
        fr.lock_due_picks(conn, now)
    with fr.get_db() as conn:
        first_locked_at = conn.execute("SELECT locked_at FROM picks").fetchone()[0]
    with fr.get_db() as conn:
        fr.lock_due_picks(conn, now)
    with fr.get_db() as conn:
        second_locked_at = conn.execute("SELECT locked_at FROM picks").fetchone()[0]
    assert first_locked_at == second_locked_at


def test_lock_due_picks_all_past_locks_everything(tmp_db):
    """lock_all_past=True locks all open picks regardless of game_time."""
    db_path, fr = tmp_db
    now = datetime(2026, 4, 16, 4, 0, 0, tzinfo=timezone.utc)  # 3am next day
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, "2026-04-15T17:10:00Z", side="over")
        _seed_pick_with_game_time(conn, None, side="under")  # NULL game_time
    with fr.get_db() as conn:
        count = fr.lock_due_picks(conn, now, lock_all_past=True)
    assert count == 2


def test_lock_due_picks_skips_null_game_time_without_lock_all_past(tmp_db):
    """A pick with NULL game_time is skipped in normal mode."""
    db_path, fr = tmp_db
    now = datetime(2026, 4, 15, 17, 0, 0, tzinfo=timezone.utc)
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, None)
    with fr.get_db() as conn:
        count = fr.lock_due_picks(conn, now, lock_all_past=False)
    assert count == 0


def test_grading_uses_locked_odds_for_pnl(tmp_db):
    """fetch_and_close_results() must use locked_odds (not odds) when computing P&L."""
    db_path, fr = tmp_db

    # Seed a pick for yesterday with odds=-115 but locked_odds=-200
    with fr.get_db() as conn:
        conn.execute("""
            INSERT INTO picks (date, pitcher, team, side, k_line, verdict,
                               ev, adj_ev, raw_lambda, applied_lambda,
                               odds, movement_conf,
                               locked_odds, locked_at)
            VALUES (?, 'Gerrit Cole', 'New York Yankees', 'over', 7.5, 'FIRE 1u',
                    0.05, 0.05, 7.2, 7.2,
                    -115, 1.0,
                    -200, '2026-04-07T17:00:00Z')
        """, (_FIXED_YESTERDAY,))

    schedule_mock = MagicMock()
    schedule_mock.json.return_value = _sched_resp(game_pk=111111, is_final=True)
    schedule_mock.raise_for_status = MagicMock()

    # ks=8 > k_line=7.5 → over wins
    boxscore_mock = MagicMock()
    boxscore_mock.json.return_value = _bs_resp("Gerrit Cole", 123, ks=8)
    boxscore_mock.raise_for_status = MagicMock()

    def mock_get(url, **kwargs):
        if "boxscore" in url:
            return boxscore_mock
        return schedule_mock

    with patch("fetch_results._et_dates", return_value=(_FIXED_TODAY, _FIXED_YESTERDAY)), \
         patch("fetch_results.requests.get", side_effect=mock_get):
        count = fr.fetch_and_close_results()

    assert count == 1

    # P&L must be calculated from locked_odds=-200, not odds=-115
    # _calc_pnl("win", -200) = 100/200 = 0.5
    expected_pnl = fr._calc_pnl("win", -200)
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT result, pnl, locked_odds FROM picks WHERE pitcher='Gerrit Cole'"
    ).fetchone()
    conn.close()

    assert row[0] == "win"
    assert row[1] == pytest.approx(expected_pnl)   # ~0.5, NOT ~0.87 (which -115 would give)
    assert row[2] == -200

    # Also verify locked_odds survives the history export
    fr.export_db_to_history()
    with open(fr.HISTORY_PATH) as f:
        history = json.load(f)
    cole_over = next(p for p in history if p["pitcher"] == "Gerrit Cole" and p["side"] == "over")
    assert cole_over.get("locked_odds") == -200


def test_history_export_includes_lock_columns(tmp_db, today_json):
    """export_db_to_history should include all new columns."""
    db_path, fr = tmp_db
    json_path, _ = today_json
    fr.seed_picks(json_path)
    fr.export_db_to_history()
    with open(fr.HISTORY_PATH) as f:
        history = json.load(f)
    assert len(history) > 0
    pick = history[0]
    for col in ("game_time", "lineup_used", "locked_at", "locked_k_line",
                "locked_odds", "locked_adj_ev", "locked_verdict", "edge"):
        assert col in pick, f"missing column: {col}"


def test_history_load_includes_lock_columns(tmp_db, today_json):
    """load_history_into_db should load locked_* columns from history."""
    db_path, fr = tmp_db
    json_path, _ = today_json
    fr.seed_picks(json_path)
    # Manually write history with lock columns
    history = [{"date": "2026-04-10", "pitcher": "Old Pick", "team": "BOS", "side": "over",
                "k_line": 6.5, "verdict": "LEAN", "edge": 0.011, "ev": 0.02, "adj_ev": 0.02,
                "raw_lambda": 6.0, "applied_lambda": 6.0, "odds": -110,
                "movement_conf": 1.0, "result": "win", "actual_ks": 7, "pnl": 0.91,
                "fetched_at": "2026-04-10T12:00:00Z",
                "game_time": "2026-04-10T17:05:00Z", "lineup_used": 1,
                "locked_at": "2026-04-10T16:35:00Z", "locked_k_line": 6.5,
                "locked_odds": -110, "locked_adj_ev": 0.02, "locked_verdict": "LEAN"}]
    import json as _json
    fr.HISTORY_PATH.write_text(_json.dumps(history))
    fr.load_history_into_db()
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT locked_at, locked_odds, game_time, lineup_used, edge FROM picks WHERE pitcher = 'Old Pick'"
    ).fetchone()
    conn.close()
    assert row[0] == "2026-04-10T16:35:00Z"
    assert row[1] == -110
    assert row[2] == "2026-04-10T17:05:00Z"
    assert row[3] == 1
    assert row[4] == pytest.approx(0.011)


class TestNewColumns:
    """All new schema columns must exist after init_db()."""

    NEW_COLS = [
        "edge",
        "opp_team", "pitcher_throws",
        "best_over_odds", "best_under_odds",
        "opening_over_odds", "opening_under_odds",
        "swstr_pct", "career_swstr_pct",
        "is_opener", "opener_note",
        "days_since_last_start", "last_pitch_count",
        "rest_k9_delta", "park_factor",
    ]

    def test_new_columns_exist_after_init(self, tmp_db):
        db_path, fr = tmp_db
        conn = fr.get_db()
        cols = {row[1] for row in conn.execute("PRAGMA table_info(picks)")}
        conn.close()
        for col in self.NEW_COLS:
            assert col in cols, f"Missing column: {col}"

    def test_migration_adds_columns_to_existing_db(self, tmp_path):
        """init_db on a pre-existing DB without new columns must add them safely."""
        db = tmp_path / "old.db"
        # Create a minimal old-schema DB (no new columns)
        with sqlite3.connect(db) as conn:
            conn.execute("""
                CREATE TABLE picks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT, pitcher TEXT, team TEXT, side TEXT,
                    k_line REAL, verdict TEXT, ev REAL, adj_ev REAL,
                    raw_lambda REAL, applied_lambda REAL, odds INTEGER,
                    movement_conf REAL, result TEXT
                )
            """)
            conn.execute(
                "INSERT INTO picks (date,pitcher,team,side,k_line,verdict,ev,adj_ev,"
                "raw_lambda,applied_lambda,odds,movement_conf) "
                "VALUES ('2026-04-01','P','T','over',5.5,'LEAN',0.02,0.02,5.0,5.0,-115,1.0)"
            )

        with patch("fetch_results.DB_PATH", db):
            import fetch_results
            fetch_results.init_db()
            conn = fetch_results.get_db()
            cols = {row[1] for row in conn.execute("PRAGMA table_info(picks)")}
            conn.close()

        for col in self.NEW_COLS:
            assert col in cols, f"Migration failed to add: {col}"
        # Existing row must still be present
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0] == 1


class TestSeedPicksNewFields:

    def _make_today_json(self, tmp_path, extra_fields=None):
        """Build a minimal today.json with one FIRE 1u over pick."""
        base = {
            "date": "2026-04-15",
            "props_available": True,
            "pitchers": [{
                "pitcher": "Gerrit Cole", "team": "New York Yankees",
                "opp_team": "Boston Red Sox",
                "pitcher_throws": "R",
                "game_time": "2026-04-15T23:05:00Z",
                "k_line": 7.5,
                "raw_lambda": 7.2, "lambda": 7.2,
                "season_k9": 9.1, "recent_k9": 8.8, "career_k9": 9.0,
                "avg_ip": 5.8, "opp_k_rate": 0.235, "ump_k_adj": 0.2,
                "swstr_delta_k9": 0.15, "swstr_pct": 0.132, "career_swstr_pct": 0.120,
                "is_opener": False, "opener_note": None,
                "days_since_last_start": 5, "last_pitch_count": 96,
                "rest_k9_delta": 0.0, "park_factor": 0.98,
                "best_over_odds": -115, "best_under_odds": -105,
                "opening_over_odds": -110, "opening_under_odds": -110,
                "ref_book": "FanDuel",
                "lineup_used": False,
                "ev_over":  {"ev": 0.05, "adj_ev": 0.05, "verdict": "FIRE 1u",
                             "win_prob": 0.58, "movement_conf": 1.0},
                "ev_under": {"ev": -0.02, "adj_ev": -0.02, "verdict": "PASS",
                             "win_prob": 0.42, "movement_conf": 1.0},
            }],
        }
        if extra_fields:
            base["pitchers"][0].update(extra_fields)
        p = tmp_path / "today.json"
        p.write_text(json.dumps(base))
        return p

    def test_insert_stores_new_fields(self, tmp_db, tmp_path):
        db_path, fr = tmp_db
        today = self._make_today_json(tmp_path)
        fr.seed_picks(today)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT opp_team, pitcher_throws, best_over_odds, best_under_odds, "
            "opening_over_odds, opening_under_odds, swstr_pct, career_swstr_pct "
            "FROM picks WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()

        assert row["opp_team"] == "Boston Red Sox"
        assert row["pitcher_throws"] == "R"
        assert row["best_over_odds"] == -115
        assert row["best_under_odds"] == -105
        assert row["opening_over_odds"] == -110
        assert row["opening_under_odds"] == -110
        assert abs(row["swstr_pct"] - 0.132) < 0.001
        assert abs(row["career_swstr_pct"] - 0.120) < 0.001

    def test_insert_stores_phase_c_fields(self, tmp_db, tmp_path):
        db_path, fr = tmp_db
        today = self._make_today_json(tmp_path, extra_fields={
            "is_opener": True,
            "opener_note": "Opener/bullpen game - forced PASS.",
            "days_since_last_start": 3,
            "last_pitch_count": 112,
            "rest_k9_delta": -0.5,
            "park_factor": 1.04,
        })
        fr.seed_picks(today)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT is_opener, opener_note, days_since_last_start, "
            "last_pitch_count, rest_k9_delta, park_factor "
            "FROM picks WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()

        assert row["is_opener"] == 1
        assert row["opener_note"] == "Opener/bullpen game - forced PASS."
        assert row["days_since_last_start"] == 3
        assert row["last_pitch_count"] == 112
        assert abs(row["rest_k9_delta"] - (-0.5)) < 0.001
        assert abs(row["park_factor"] - 1.04) < 0.001

    def test_update_refreshes_stats_on_second_run(self, tmp_db, tmp_path):
        """A second seed_picks call with updated data should refresh stats + odds on unlocked picks."""
        db_path, fr = tmp_db
        today_v1 = self._make_today_json(tmp_path)
        fr.seed_picks(today_v1)

        today_v2 = self._make_today_json(tmp_path, extra_fields={
            "best_over_odds": -125,
            "opp_k_rate": 0.248,
            "swstr_delta_k9": 0.20,
            "days_since_last_start": 4,
            "last_pitch_count": 88,
            "rest_k9_delta": -0.1,
            "park_factor": 1.02,
            "lineup_used": True,
            "lambda": 7.4,
            "ev_over": {"ev": 0.06, "adj_ev": 0.06, "verdict": "FIRE 1u",
                        "win_prob": 0.60, "movement_conf": 1.0},
            "ev_under": {"ev": -0.03, "adj_ev": -0.03, "verdict": "PASS",
                         "win_prob": 0.40, "movement_conf": 1.0},
        })
        fr.seed_picks(today_v2)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT best_over_odds, opp_k_rate, swstr_delta_k9, lineup_used, "
            "applied_lambda, days_since_last_start, last_pitch_count, "
            "rest_k9_delta, park_factor "
            "FROM picks WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()

        assert row["best_over_odds"] == -125, "odds should refresh on second run"
        assert abs(row["opp_k_rate"] - 0.248) < 0.001, "opp_k_rate should refresh when lineup arrives"
        assert abs(row["swstr_delta_k9"] - 0.20) < 0.001
        assert row["lineup_used"] == 1
        assert abs(row["applied_lambda"] - 7.4) < 0.01
        assert row["days_since_last_start"] == 4
        assert row["last_pitch_count"] == 88
        assert abs(row["rest_k9_delta"] - (-0.1)) < 0.001
        assert abs(row["park_factor"] - 1.02) < 0.001

    def test_locked_pick_stats_not_refreshed(self, tmp_db, tmp_path):
        """Once a pick is locked, stats and odds must not change."""
        db_path, fr = tmp_db
        today_v1 = self._make_today_json(tmp_path)
        fr.seed_picks(today_v1)

        conn = fr.get_db()
        conn.execute(
            "UPDATE picks SET locked_at='2026-04-15T22:35:00Z' "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        )
        conn.commit()
        conn.close()

        today_v2 = self._make_today_json(tmp_path, extra_fields={
            "best_over_odds": -140,
            "opp_k_rate": 0.260,
        })
        fr.seed_picks(today_v2)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT best_over_odds, opp_k_rate FROM picks "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()

        assert row["best_over_odds"] == -115, "locked pick odds must not change"
        assert abs(row["opp_k_rate"] - 0.235) < 0.001, "locked pick stats must not change"


class TestExportLoadRoundTrip:
    """New fields survive a full DB → JSON → DB round trip."""

    def test_new_fields_survive_export_and_reload(self, tmp_db, tmp_path):
        import json
        db_path, fr = tmp_db
        history = tmp_path / "history.json"

        # Insert directly so we control all fields
        conn = fr.get_db()
        conn.execute("""
            INSERT INTO picks
            (date, pitcher, team, opp_team, pitcher_throws, side, k_line,
             verdict, ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf,
             season_k9, recent_k9, career_k9, avg_ip, ump_k_adj, opp_k_rate,
             swstr_delta_k9, swstr_pct, career_swstr_pct,
             best_over_odds, best_under_odds, opening_over_odds, opening_under_odds,
             ref_book, game_time, lineup_used,
             is_opener, opener_note, days_since_last_start, last_pitch_count,
             rest_k9_delta, park_factor,
             result, actual_ks, pnl, fetched_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "2026-04-15", "Export Test", "NYY", "BOS", "L", "over",
            6.5, "FIRE 1u", 0.05, 0.05, 6.2, 6.2, -115, 1.0,
            9.1, 8.8, 9.0, 5.8, 0.0, 0.235,
            0.12, 0.130, 0.115,
            -115, -105, -110, -110,
            "FanDuel", "2026-04-15T23:05:00Z", 0,
            1, "Opener/bullpen game - forced PASS.", 3, 111, -0.5, 1.04,
            "win", 8, 0.87, "2026-04-16T03:00:00Z",
        ))
        conn.commit()
        conn.close()

        # Export
        fr.export_db_to_history(history)

        # Verify JSON contains new fields
        with open(history) as f:
            exported = json.load(f)
        assert len(exported) == 1
        p = exported[0]
        assert p["opp_team"] == "BOS"
        assert p["pitcher_throws"] == "L"
        assert p["best_over_odds"] == -115
        assert p["best_under_odds"] == -105
        assert p["opening_over_odds"] == -110
        assert p["opening_under_odds"] == -110
        assert abs(p["swstr_pct"] - 0.130) < 0.001
        assert abs(p["career_swstr_pct"] - 0.115) < 0.001
        assert p["is_opener"] == 1
        assert p["opener_note"] == "Opener/bullpen game - forced PASS."
        assert p["days_since_last_start"] == 3
        assert p["last_pitch_count"] == 111
        assert abs(p["rest_k9_delta"] - (-0.5)) < 0.001
        assert abs(p["park_factor"] - 1.04) < 0.001

        # Reload into a fresh DB and verify
        from unittest.mock import patch
        fresh_db = tmp_path / "fresh.db"
        with patch("fetch_results.DB_PATH", fresh_db):
            fr.init_db()
            fr.load_history_into_db(history)
            conn2 = fr.get_db()
            row = conn2.execute(
                "SELECT opp_team, pitcher_throws, best_over_odds, swstr_pct, "
                "is_opener, opener_note, days_since_last_start, last_pitch_count, "
                "rest_k9_delta, park_factor "
                "FROM picks WHERE pitcher='Export Test'"
            ).fetchone()
            conn2.close()

        assert row["opp_team"] == "BOS"
        assert row["pitcher_throws"] == "L"
        assert row["best_over_odds"] == -115
        assert abs(row["swstr_pct"] - 0.130) < 0.001
        assert row["is_opener"] == 1
        assert row["opener_note"] == "Opener/bullpen game - forced PASS."
        assert row["days_since_last_start"] == 3
        assert row["last_pitch_count"] == 111
        assert abs(row["rest_k9_delta"] - (-0.5)) < 0.001
        assert abs(row["park_factor"] - 1.04) < 0.001


class TestOpeningOddsSource:
    """Task A2: opening_odds_source ∈ {'preview', 'first_seen'} or NULL for
    pre-migration legacy rows. INSERT captures whatever source was tagged at
    decision time; subsequent refreshes never overwrite it (same rule as
    opening_*_odds). Export/load preserves the field (legacy rows round-trip
    as None, not coerced to a default)."""

    def _make_today_json(self, tmp_path, source="first_seen"):
        """Build a minimal today.json with one FIRE 1u over pick and the given
        opening_odds_source tag."""
        base = {
            "date": "2026-04-15",
            "props_available": True,
            "pitchers": [{
                "pitcher": "Gerrit Cole", "team": "New York Yankees",
                "opp_team": "Boston Red Sox",
                "pitcher_throws": "R",
                "game_time": "2026-04-15T23:05:00Z",
                "k_line": 7.5,
                "raw_lambda": 7.2, "lambda": 7.2,
                "season_k9": 9.1, "recent_k9": 8.8, "career_k9": 9.0,
                "avg_ip": 5.8, "opp_k_rate": 0.235, "ump_k_adj": 0.2,
                "swstr_delta_k9": 0.15, "swstr_pct": 0.132, "career_swstr_pct": 0.120,
                "best_over_odds": -115, "best_under_odds": -105,
                "opening_over_odds": -110, "opening_under_odds": -110,
                "opening_odds_source": source,
                "ref_book": "FanDuel",
                "lineup_used": False,
                "ev_over":  {"ev": 0.05, "adj_ev": 0.05, "verdict": "FIRE 1u",
                             "win_prob": 0.58, "movement_conf": 1.0},
                "ev_under": {"ev": -0.02, "adj_ev": -0.02, "verdict": "PASS",
                             "win_prob": 0.42, "movement_conf": 1.0},
            }],
        }
        p = tmp_path / "today.json"
        p.write_text(json.dumps(base))
        return p

    def test_seed_picks_inserts_opening_odds_source(self, tmp_db, tmp_path):
        db_path, fr = tmp_db
        today = self._make_today_json(tmp_path, source="first_seen")
        fr.seed_picks(today)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT opening_odds_source FROM picks "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()
        assert row["opening_odds_source"] == "first_seen"

    def test_seed_picks_inserts_opening_odds_source_preview(self, tmp_db, tmp_path):
        db_path, fr = tmp_db
        today = self._make_today_json(tmp_path, source="preview")
        fr.seed_picks(today)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT opening_odds_source FROM picks "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()
        assert row["opening_odds_source"] == "preview"

    def test_seed_picks_update_does_not_overwrite_opening_odds_source(
            self, tmp_db, tmp_path):
        """Same invariant as opening_*_odds: once captured on INSERT, the source
        stays frozen. Simulates a later 6am/refresh run where preview_lines
        was absent (and fetch_odds therefore emitted source='first_seen') —
        the DB must still show 'preview' from the original insert."""
        db_path, fr = tmp_db
        today_v1 = self._make_today_json(tmp_path, source="preview")
        fr.seed_picks(today_v1)

        today_v2 = self._make_today_json(tmp_path, source="first_seen")
        fr.seed_picks(today_v2)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT opening_odds_source FROM picks "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()
        assert row["opening_odds_source"] == "preview", (
            "opening_odds_source must stay frozen to the first-seen value, "
            "same as opening_*_odds"
        )

    def test_export_db_to_history_includes_opening_odds_source(
            self, tmp_db, tmp_path):
        """Export round-trips opening_odds_source to picks_history.json.
        Legacy rows (source IS NULL) must land as None, not 'first_seen' —
        that's how diagnostics tell pre-migration rows apart."""
        db_path, fr = tmp_db
        history = tmp_path / "history.json"

        conn = fr.get_db()
        # Row 1: tagged source
        conn.execute("""
            INSERT INTO picks
            (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
             raw_lambda, applied_lambda, odds, movement_conf,
             opening_odds_source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "2026-04-15", "Tagged Pitcher", "NYY", "over", 7.5, "FIRE 1u",
            0.05, 0.05, 7.2, 7.2, -115, 1.0,
            "first_seen",
        ))
        # Row 2: legacy — no source
        conn.execute("""
            INSERT INTO picks
            (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
             raw_lambda, applied_lambda, odds, movement_conf)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "2026-04-01", "Legacy Pitcher", "NYY", "over", 6.5, "LEAN",
            0.02, 0.02, 6.2, 6.2, -110, 1.0,
        ))
        conn.commit()
        conn.close()

        fr.export_db_to_history(history)
        with open(history) as f:
            exported = json.load(f)

        by_name = {p["pitcher"]: p for p in exported}
        assert by_name["Tagged Pitcher"]["opening_odds_source"] == "first_seen"
        assert by_name["Legacy Pitcher"]["opening_odds_source"] is None


class TestDataCompleteRefresh:
    """Regression tests for the data_complete UPDATE bug.

    Before the fix, data_complete was only set on INSERT — the UPDATE path
    in seed_picks silently left the stored value frozen at the 6am full-run
    value.  On days where the 6am run saw ump_ok=False (HPs not yet posted),
    the flag stayed at 0 all day even after refresh runs filled in real
    umpire + SwStr data, causing the entire slate to be excluded from
    calibration and the dashboard performance rollup.

    The fix adds `data_complete = ?` to the UPDATE SET clause so the flag
    tracks the latest state of the underlying inputs.
    """

    def _make_today_json(self, tmp_path, data_complete=True):
        """Minimal today.json with one FIRE 1u over pick and the given flag."""
        base = {
            "date": "2026-04-15",
            "props_available": True,
            "pitchers": [{
                "pitcher": "Gerrit Cole", "team": "New York Yankees",
                "opp_team": "Boston Red Sox",
                "pitcher_throws": "R",
                "game_time": "2026-04-15T23:05:00Z",
                "k_line": 7.5,
                "raw_lambda": 7.2, "lambda": 7.2,
                "season_k9": 9.1, "recent_k9": 8.8, "career_k9": 9.0,
                "avg_ip": 5.8, "opp_k_rate": 0.235, "ump_k_adj": 0.2,
                "swstr_delta_k9": 0.15, "swstr_pct": 0.132, "career_swstr_pct": 0.120,
                "best_over_odds": -115, "best_under_odds": -105,
                "opening_over_odds": -110, "opening_under_odds": -110,
                "ref_book": "FanDuel",
                "lineup_used": False,
                "data_complete": data_complete,
                "ev_over":  {"ev": 0.05, "adj_ev": 0.05, "verdict": "FIRE 1u",
                             "win_prob": 0.58, "movement_conf": 1.0},
                "ev_under": {"ev": -0.02, "adj_ev": -0.02, "verdict": "PASS",
                             "win_prob": 0.42, "movement_conf": 1.0},
            }],
        }
        p = tmp_path / "today.json"
        p.write_text(json.dumps(base))
        return p

    def test_update_promotes_data_complete_from_false_to_true(
            self, tmp_db, tmp_path):
        """Simulates 6am run inserting with data_complete=0 (ump_ok=False,
        HPs not posted yet), then a refresh run arriving with
        data_complete=1 after the umpire feed populated.  The stored flag
        must promote — otherwise the slate stays excluded from calibration
        and the dashboard rollup all day."""
        db_path, fr = tmp_db

        # First seed — inputs degraded (simulates 6am before HPs posted)
        t0 = self._make_today_json(tmp_path, data_complete=False)
        fr.seed_picks(t0)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT data_complete FROM picks "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()
        assert row["data_complete"] == 0, "insert should have stored the degraded flag"

        # Second seed — inputs now clean (simulates later refresh run)
        t1 = self._make_today_json(tmp_path, data_complete=True)
        fr.seed_picks(t1)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT data_complete FROM picks "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()
        assert row["data_complete"] == 1, (
            "UPDATE must refresh data_complete so a clean refresh promotes "
            "the slate out of the calibration exclusion filter"
        )

    def test_update_demotes_data_complete_from_true_to_false(
            self, tmp_db, tmp_path):
        """The inverse: if a later run sees a signal regression (e.g.
        umpire feed went stale), data_complete must demote.  Keeps the
        flag honest as a 'current state' gauge rather than a sticky
        latch in either direction."""
        db_path, fr = tmp_db

        t0 = self._make_today_json(tmp_path, data_complete=True)
        fr.seed_picks(t0)

        t1 = self._make_today_json(tmp_path, data_complete=False)
        fr.seed_picks(t1)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT data_complete FROM picks "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()
        assert row["data_complete"] == 0, (
            "UPDATE must demote data_complete when inputs regress — "
            "the flag is latest-state, not sticky"
        )

    def test_update_does_not_touch_locked_rows(self, tmp_db, tmp_path):
        """Locked picks are frozen (locked_at IS NOT NULL) — the refresh
        UPDATE explicitly filters them out.  A post-lock signal change must
        NOT rewrite data_complete on a locked row, otherwise we'd mutate
        the record after the decision was stamped.  This is an existing
        invariant; the fix must not break it."""
        db_path, fr = tmp_db

        # Insert with degraded flag then manually lock the row
        t0 = self._make_today_json(tmp_path, data_complete=False)
        fr.seed_picks(t0)

        conn = fr.get_db()
        conn.execute(
            "UPDATE picks SET locked_at = '2026-04-15T22:35:00Z' "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        )
        conn.commit()
        conn.close()

        # Later refresh arrives clean
        t1 = self._make_today_json(tmp_path, data_complete=True)
        fr.seed_picks(t1)

        conn = fr.get_db()
        row = conn.execute(
            "SELECT data_complete FROM picks "
            "WHERE pitcher='Gerrit Cole' AND side='over'"
        ).fetchone()
        conn.close()
        assert row["data_complete"] == 0, (
            "locked rows must stay frozen — post-lock signal changes "
            "cannot rewrite the stored data_complete"
        )
