from scripts.repair_stale_pass_picks import repair_history_against_archives


def test_repair_history_marks_unlocked_final_pass_rows_inactive():
    history = [
        {
            "date": "2026-06-20",
            "pitcher": "MacKenzie Gore",
            "side": "over",
            "verdict": "LEAN",
            "raw_verdict": "FIRE 1u",
            "actionable_verdict": "LEAN",
            "k_line": 6.5,
            "odds": 124,
            "adj_ev": 0.07,
            "locked_at": None,
            "result": "loss",
            "actual_ks": 4,
            "pnl": -1.0,
            "fetched_at": "2026-06-21T10:17:00Z",
        },
        {
            "date": "2026-06-20",
            "pitcher": "MacKenzie Gore",
            "side": "under",
            "verdict": "LEAN",
            "locked_at": "2026-06-20T19:40:21Z",
            "result": "win",
            "actual_ks": 4,
            "pnl": 0.69,
        },
        {
            "date": "2026-06-20",
            "pitcher": "Kyle Harrison",
            "side": "over",
            "verdict": "FIRE 1u",
            "locked_at": None,
            "result": "win",
            "actual_ks": 7,
            "pnl": 0.68,
        },
    ]
    archives = {
        "2026-06-20": {
            "pitchers": [
                {
                    "pitcher": "MacKenzie Gore",
                    "k_line": 6.5,
                    "best_over_odds": -144,
                    "ev_over": {
                        "verdict": "PASS",
                        "actionable_verdict": "PASS",
                        "raw_verdict": "PASS",
                        "edge": -0.04,
                        "ev": -0.05,
                        "adj_ev": -0.24,
                    },
                    "ev_under": {"verdict": "LEAN"},
                    "result": {"outcome": "loss"},
                },
                {
                    "pitcher": "Kyle Harrison",
                    "k_line": 5.5,
                    "best_over_odds": -146,
                    "ev_over": {"verdict": "FIRE 1u"},
                },
            ]
        }
    }

    repaired = repair_history_against_archives(history, archives, ["2026-06-20"])

    stale = history[0]
    assert repaired == [
        {
            "date": "2026-06-20",
            "pitcher": "MacKenzie Gore",
            "side": "over",
            "previous_verdict": "LEAN",
        }
    ]
    assert stale["verdict"] == "PASS"
    assert stale["raw_verdict"] == "PASS"
    assert stale["actionable_verdict"] == "PASS"
    assert stale["odds"] == -144
    assert stale["adj_ev"] == -0.24
    assert stale["result"] is None
    assert stale["actual_ks"] is None
    assert stale["pnl"] is None
    assert stale["fetched_at"] is None
    assert history[1]["result"] == "win"
    assert history[2]["verdict"] == "FIRE 1u"
    assert "result" not in archives["2026-06-20"]["pitchers"][0]
    assert "result" not in archives["2026-06-20"]["pitchers"][0]["ev_over"]
