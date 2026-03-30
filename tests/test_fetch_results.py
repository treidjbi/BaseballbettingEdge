import json, os, sys, sqlite3, tempfile, pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))


@pytest.fixture
def tmp_db(tmp_path):
    """Patch DB_PATH to a temp file, yield path."""
    db = tmp_path / "results.db"
    with patch("fetch_results.DB_PATH", db):
        import fetch_results
        fetch_results.init_db()
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
                "ev_over":  {"ev": 0.05, "adj_ev": 0.05, "verdict": "FIRE 1u", "win_prob": 0.58, "movement_conf": 1.0},
                "ev_under": {"ev": -0.02, "adj_ev": -0.02, "verdict": "PASS", "win_prob": 0.42, "movement_conf": 1.0},
            },
            {
                "pitcher": "Shane Bieber", "team": "Cleveland", "opp_team": "Detroit",
                "game_time": "2026-04-15T18:10:00Z", "k_line": 6.5,
                "raw_lambda": 6.1, "lambda": 6.1,
                "season_k9": 8.5, "recent_k9": 8.2, "career_k9": 8.8,
                "avg_ip": 5.5, "opp_k_rate": 0.220, "ump_k_adj": 0.0,
                "best_over_odds": -110, "best_under_odds": -110,
                "ev_over":  {"ev": 0.008, "adj_ev": 0.008, "verdict": "PASS",   "win_prob": 0.51, "movement_conf": 1.0},
                "ev_under": {"ev": 0.07,  "adj_ev": 0.07,  "verdict": "FIRE 2u","win_prob": 0.49, "movement_conf": 1.0},
            },
        ],
    }
    p = tmp_path / "today.json"
    p.write_text(json.dumps(data))
    return p, data


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

    def test_returns_inserted_count(self, tmp_db, today_json):
        db_path, fr = tmp_db
        p, _ = today_json
        assert fr.seed_picks(p) == 2
        assert fr.seed_picks(p) == 0  # second run inserts nothing


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


class TestFetchAndCloseResults:
    def _seed_yesterday_pick(self, db_path, fr, pitcher="Gerrit Cole", side="over",
                              k_line=7.5, odds=-115, verdict="FIRE 1u"):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute("""
            INSERT INTO picks (date, pitcher, team, side, k_line, verdict,
                               ev, adj_ev, raw_lambda, applied_lambda, odds, movement_conf)
            VALUES (date('now','-1 day','localtime'), ?,?,?,?,?,0.05,0.05,7.2,7.2,?,1.0)
        """, (pitcher, "New York", side, k_line, verdict, odds))
        conn.commit()
        conn.close()

    def test_win_over_recorded(self, tmp_db):
        db_path, fr = tmp_db
        self._seed_yesterday_pick(db_path, fr, pitcher="Gerrit Cole", side="over", k_line=7.5)

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Gerrit Cole", ks=8)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
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

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Gerrit Cole", ks=6)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
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

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Gerrit Cole", ks=7)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
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

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Gerrit Cole", ks=8, game_final=False)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
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

        mock_resp = MagicMock()
        mock_resp.json.return_value = _make_schedule_response("Other Pitcher", ks=5)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
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

        mock_resp = MagicMock()
        # under wins when actual < line: 6 < 7.5
        mock_resp.json.return_value = _make_schedule_response("Gerrit Cole", ks=6)
        mock_resp.raise_for_status = MagicMock()

        with patch("fetch_results.requests.get", return_value=mock_resp):
            fr.fetch_and_close_results()

        import sqlite3
        conn = sqlite3.connect(db_path)
        pnl = conn.execute("SELECT pnl FROM picks").fetchone()[0]
        conn.close()
        assert abs(pnl - 1.20) < 0.01
