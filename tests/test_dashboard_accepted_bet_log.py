from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_APP = ROOT / "dashboard" / "v2-app.jsx"
DASHBOARD_HTML = ROOT / "dashboard" / "v2.html"


def test_dashboard_exposes_manual_accepted_bet_action_without_service_key():
    app = DASHBOARD_APP.read_text(encoding="utf-8")

    assert "/api/accepted-bets" in app
    assert "/.netlify/functions/accepted-bets" not in app
    assert "Log Bet" in app
    assert "x-bet-log-secret" in app
    assert "SUPABASE_SERVICE_ROLE_KEY" not in app


def test_dashboard_uses_inline_bet_ticket_not_browser_prompts():
    app = DASHBOARD_APP.read_text(encoding="utf-8")

    assert "window.prompt" not in app
    assert "window.alert" not in app
    assert "v2-bet-ticket" in app
    assert "Bet ticket" in app
    assert "Save Bet" in app
    for label in ["Line", "Odds", "Book", "Units", "Bet log key"]:
        assert f">{label}<" in app


def test_dashboard_busts_v2_app_cache_for_accepted_bet_ui():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "v2-app.js?v=2026-05-08-bet-ticket" in html
