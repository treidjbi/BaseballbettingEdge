from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "dashboard" / "v2-app.jsx")
HTML = (ROOT / "dashboard" / "v2.html")
NETLIFY = (ROOT / "netlify.toml")


def test_alt_picks_navigation_and_legacy_history_route_are_canonical():
    app = APP.read_text(encoding="utf-8")
    assert 't === "history" ? "alt" : t' in app
    assert '["picks", "alt", "perf"]' in app
    assert '["picks", Icon.picks,   "Picks",   null]' in app
    assert '["alt", Icon.history, "Alt Picks", null]' in app
    nav = app[app.index('<nav className="v2-tabbar">'):]
    assert nav.index('"Picks"') < nav.index('"Alt Picks"') < nav.index('"Results"')
    assert 'searchParams.set("tab", nextTab)' in app


def test_legacy_history_component_and_archive_helpers_are_removed():
    app = APP.read_text(encoding="utf-8")

    for removed in [
        "function HistoryTab", "function historyDataBase", "function fetchHistorySlate",
        "function historyRowsFromSlate", "function normalizeHistorySide", "function historySideFromPitcher",
    ]:
        assert removed not in app
    assert 't === "history" ? "alt" : t' in app


def test_alt_components_are_read_only_and_keep_required_groups_and_copy():
    app = APP.read_text(encoding="utf-8")
    start = app.index("function AltPickSheet")
    end = app.index("// ── Root app", start)
    alt = app[start:end]
    assert alt.index("Consensus Core") < alt.index("Re-entry Expansion")
    for copy in [
        "Alternative methodology unavailable.",
        "Retrying automatically. Main picks are unaffected.",
        "Last update retained; retrying current evidence.",
        "Waiting for current-slate evidence.",
        "No alternative qualifiers on this slate.",
        "Alternative evaluation still pending.",
        "Selected with",
        "confirmed families",
        "still pending.",
    ]:
        assert copy in app
    for copy in [
        "Not selected and pending",
        "Base", "Anchor", "Preclose", "Re-entry",
    ]:
        assert copy in alt
    for forbidden in ["Log Bet", "Save Bet", "Units", "stake", "PnL", "notification", "function PickSheet"]:
        assert forbidden not in alt
    assert "function AltPickSheet" in alt
    assert "function AltPickCard" in alt
    assert "altSelectionProofCopy(row)" in alt
    assert alt.count("altSelectionProofCopy(row)") == 2
    proof_helper = app[app.index("function altSelectionProofCopy"):start]
    assert "row.family_count" in proof_helper
    assert "row.evidence_freshness_status" in alt
    assert "Read-only same-day methodology comparison. Official picks are unchanged." in alt
    assert "startCurrentSlatePolling" in alt
    for forbidden_style in ["v2-alt-fire", "fire-red", "background: red", "#ef4444"]:
        assert forbidden_style not in alt.lower()


def test_zero_selected_copy_gates_healthy_language_on_zero_pending_rows():
    app = APP.read_text(encoding="utf-8")
    helper = app[app.index("function altZeroSelectedCopy"):app.index("function altBookTitle")]
    assert 'row?.selection_status === "pending"' in helper
    assert 'Evidence is healthy' in helper
    assert 'Alternative evaluation still pending.' in helper
    tab = app[app.index("function AltPicksTab"):app.index("function SteamTab")]
    assert "altZeroSelectedCopy(supporting)" in tab
    assert "zeroSelectedCopy.title" in tab
    assert "zeroSelectedCopy.sub" in tab


def test_expanded_supporting_candidates_show_read_only_chips_and_reason():
    app = APP.read_text(encoding="utf-8")
    start = app.index("function AltSupportingCandidate")
    end = app.index("function AltPicksTab", start)
    supporting = app[start:end]

    assert "v2-alt-supporting-candidate" in supporting
    assert "supportingReason(row)" in supporting
    assert "v2-alt-chip" in supporting
    assert "row.pitcher" in supporting
    assert "row.selection_status" in supporting
    assert "row.model_k_line" in supporting
    assert "v2-alt-card" not in supporting
    details = app[app.index('className="v2-alt-collapsed"'):]
    assert "supporting.map((row) => <AltSupportingCandidate" in details


def test_alt_picks_assets_and_scoped_mobile_styles_are_present():
    html = HTML.read_text(encoding="utf-8")
    assert "v2-alt-picks.js?v=2026-07-24-alt-ui-recovery" in html
    assert "v2-app.js?v=2026-07-24-alt-ui-recovery" in html
    assert "v2-alt-picks.js?v=2026-07-23-alt-picks-v2-repair" not in html
    assert "v2-app.js?v=2026-07-22-alt-picks-v2" not in html
    assert "v2-alt-picks.js?v=2026-07-22-alt-picks-v2" not in html
    assert "v2-alt-picks.js?v=2026-07-21-alt-picks" not in html
    assert "v2-app.js?v=2026-07-21-alt-picks" not in html
    assert html.rindex('<script src="v2-data.js') < html.rindex('<script src="v2-alt-picks.js') < html.rindex('<script src="v2-app.js')
    assert ".v2-alt-card" in html
    assert ".v2-alt-chip" in html
    assert "flex-wrap: wrap" in html
    assert "@media (max-width: 420px)" in html


def test_netlify_rebuild_watch_includes_v2_alt_picks_asset():
    netlify = NETLIFY.read_text(encoding="utf-8")
    ignore_line = next(
        line.strip() for line in netlify.splitlines()
        if line.strip().startswith("ignore = ")
    )

    assert "dashboard/v2-alt-picks.js" in ignore_line


def test_alt_sheet_layer_sits_above_persistent_tabbar():
    html = HTML.read_text(encoding="utf-8")
    assert ".v2-alt-sheet-backdrop { position: fixed; inset: 0; z-index: 80;" in html
    assert ".v2-alt-sheet { position: relative; z-index: 81;" in html
