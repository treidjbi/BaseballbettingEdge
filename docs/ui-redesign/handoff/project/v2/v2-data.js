// Real sample data lifted from dashboard/data/processed/today.json (2026-04-16)
// + a couple of pregame examples fabricated from the same shape so the
// redesign can show upcoming, live, and final states.
window.V2_DATA = {
  generated_at: "2026-04-16T20:09:54Z",
  date: "2026-04-16",
  pitchers: [
    // ── Upcoming (synthesized to represent a pregame slate) ──
    {
      pitcher: "Tarik Skubal", team: "Detroit Tigers", opp_team: "Houston Astros",
      pitcher_throws: "L", game_time: "2026-04-17T00:10:00Z",
      k_line: 7.5, opening_line: 7.5,
      best_over_odds: -115, best_under_odds: -105,
      opening_over_odds: -105, opening_under_odds: -115,
      lambda: 8.42, avg_ip: 6.3,
      opp_k_rate: 0.257, ump_k_adj: 0.18,
      season_k9: 11.8, recent_k9: 12.4, career_k9: 10.2,
      ev_over: { ev: 0.122, adj_ev: 0.104, verdict: "FIRE 2u", win_prob: 0.61, movement_conf: 0.85 },
      ev_under: { ev: -0.136, adj_ev: -0.136, verdict: "PASS", win_prob: 0.39, movement_conf: 1.0 },
      game_state: "pregame"
    },
    {
      pitcher: "Spencer Strider", team: "Atlanta Braves", opp_team: "Miami Marlins",
      pitcher_throws: "R", game_time: "2026-04-16T23:20:00Z",
      k_line: 8.5, opening_line: 9.5,
      best_over_odds: -110, best_under_odds: -110,
      opening_over_odds: -120, opening_under_odds: +100,
      lambda: 9.1, avg_ip: 6.1,
      opp_k_rate: 0.241, ump_k_adj: 0.0,
      season_k9: 13.2, recent_k9: 11.8, career_k9: 12.9,
      ev_over: { ev: 0.088, adj_ev: 0.068, verdict: "FIRE 1u", win_prob: 0.58, movement_conf: 0.78 },
      ev_under: { ev: -0.11, adj_ev: -0.11, verdict: "PASS", win_prob: 0.42, movement_conf: 1.0 },
      game_state: "pregame"
    },
    // ── Real data from today.json (live/final) ──
    {
      pitcher: "Max Fried", team: "New York Yankees", opp_team: "Los Angeles Angels",
      pitcher_throws: "R", game_time: "2026-04-16T17:35:00Z",
      k_line: 6.5, opening_line: 6.5,
      best_over_odds: 100, best_under_odds: -132,
      opening_over_odds: 110, opening_under_odds: -145,
      lambda: 5.26, avg_ip: 7.0,
      opp_k_rate: 0.2517, ump_k_adj: 0.0,
      season_k9: 6.43, recent_k9: 5.68, career_k9: 8.71,
      ev_over: { ev: -0.2238, adj_ev: -0.2238, verdict: "PASS", win_prob: 0.276, movement_conf: 1.0 },
      ev_under: { ev: 0.1548, adj_ev: 0.1316, verdict: "FIRE 2u", win_prob: 0.724, movement_conf: 0.85 },
      game_state: "in_progress",
      live: { current_k: 4, innings: "5.1", pitches: 78, proj_final_k: 5.8, updated_at: "2026-04-16T19:42:00Z" }
    },
    {
      pitcher: "Foster Griffin", team: "Washington Nationals", opp_team: "Pittsburgh Pirates",
      pitcher_throws: "R", game_time: "2026-04-16T16:35:00Z",
      k_line: 4.5, opening_line: 4.5,
      best_over_odds: -104, best_under_odds: -128,
      opening_over_odds: 108, opening_under_odds: -144,
      lambda: 3.5, avg_ip: 5.11,
      opp_k_rate: 0.2291, ump_k_adj: 0.0,
      season_k9: 7.04, recent_k9: 9.0, career_k9: 6.56,
      ev_over: { ev: -0.2345, adj_ev: -0.2345, verdict: "PASS", win_prob: 0.275, movement_conf: 1.0 },
      ev_under: { ev: 0.1633, adj_ev: 0.1143, verdict: "FIRE 2u", win_prob: 0.725, movement_conf: 0.7 },
      game_state: "final",
      result: { final_k: 3, side_taken: "under", line_at_bet: 4.5, odds_at_bet: -128, outcome: "win", units_won: 1.56, units_risked: 2.0 }
    },
    {
      pitcher: "Brandon Sproat", team: "Milwaukee Brewers", opp_team: "Toronto Blue Jays",
      pitcher_throws: "R", game_time: "2026-04-16T17:40:00Z",
      k_line: 3.5, opening_line: 3.5,
      best_over_odds: -102, best_under_odds: -130,
      opening_over_odds: 116, opening_under_odds: -154,
      lambda: 2.42, avg_ip: 3.44,
      opp_k_rate: 0.18, ump_k_adj: 0.0,
      season_k9: 8.71, recent_k9: 9.0, career_k9: 7.84,
      ev_over: { ev: -0.2798, adj_ev: -0.2798, verdict: "PASS", win_prob: 0.225, movement_conf: 1.0 },
      ev_under: { ev: 0.2096, adj_ev: 0.0629, verdict: "FIRE 1u", win_prob: 0.775, movement_conf: 0.3 },
      game_state: "in_progress"
    },
    {
      pitcher: "Jack Leiter", team: "Texas Rangers", opp_team: "Athletics",
      pitcher_throws: "R", game_time: "2026-04-16T19:05:00Z",
      k_line: 5.5, opening_line: 5.5,
      best_over_odds: -122, best_under_odds: -108,
      opening_over_odds: -106, opening_under_odds: -125,
      lambda: 5.44, avg_ip: 4.89,
      opp_k_rate: 0.2746, ump_k_adj: 0.0,
      season_k9: 12.89, recent_k9: 12.0, career_k9: 8.91,
      ev_over: { ev: -0.0892, adj_ev: -0.0892, verdict: "PASS", win_prob: 0.46, movement_conf: 1.0 },
      ev_under: { ev: 0.0204, adj_ev: 0.0133, verdict: "LEAN", win_prob: 0.54, movement_conf: 0.65 },
      game_state: "in_progress"
    },
    {
      pitcher: "Patrick Corbin", team: "Toronto Blue Jays", opp_team: "Milwaukee Brewers",
      pitcher_throws: "R", game_time: "2026-04-16T17:40:00Z",
      k_line: 4.5, opening_line: 4.5,
      best_over_odds: 132, best_under_odds: -178,
      opening_over_odds: 138, opening_under_odds: -186,
      lambda: 4.18, avg_ip: 5.5,
      opp_k_rate: 0.2187, ump_k_adj: 0.0,
      season_k9: 6.75, recent_k9: 6.75, career_k9: 8.17,
      ev_over: { ev: -0.0243, adj_ev: -0.0243, verdict: "PASS", win_prob: 0.407, movement_conf: 1.0 },
      ev_under: { ev: -0.0471, adj_ev: -0.0471, verdict: "PASS", win_prob: 0.593, movement_conf: 1.0 },
      game_state: "final",
      result: { final_k: 5, side_taken: null, line_at_bet: null, odds_at_bet: null, outcome: "pass", units_won: 0, units_risked: 0 }
    }
  ]
};

window.V2_PERF = {
  total_picks: 171,
  total_units: +18.5,
  total_roi: 10.8,
  record: "86-85-0",
  rows: [
    { verdict: "FIRE 2u", side: "under", picks: 50, wins: 33, losses: 17, win_pct: 0.66, roi: 24.04, avg_ev: 0.1933 },
    { verdict: "FIRE 2u", side: "over",  picks: 25, wins: 9,  losses: 16, win_pct: 0.36, roi: -28.5,  avg_ev: 0.1598 },
    { verdict: "FIRE 1u", side: "under", picks: 36, wins: 20, losses: 16, win_pct: 0.556, roi: 12.57, avg_ev: 0.0527 },
    { verdict: "FIRE 1u", side: "over",  picks: 34, wins: 19, losses: 15, win_pct: 0.559, roi: 10.97, avg_ev: 0.0584 },
    { verdict: "LEAN",    side: "under", picks: 17, wins: 10, losses: 7,  win_pct: 0.588, roi:  6.20, avg_ev: 0.0201 },
    { verdict: "LEAN",    side: "over",  picks: 13, wins: 5,  losses: 8,  win_pct: 0.385, roi: -28.37, avg_ev: 0.0179 }
  ]
};

// ── Steam (line-movement watchlist) ──
// Each item = a pitcher's K-prop that has moved since open.
// direction: which side is steaming ("over"|"under"); cents: how much moved
// book_moves: array of per-book cent moves for the sparkline-ish bars
window.V2_STEAM = {
  updated_at: "2026-04-16T20:09:54Z",
  rows: [
    {
      pitcher: "Tarik Skubal", team: "DET", opp: "HOU", game_time: "2026-04-17T00:10:00Z",
      k_line: 7.5, open_line: 7.5, direction: "over", cents: 13,
      open_odds: -105, cur_odds: -115, books_moved: 6, books_total: 7,
      note: "Sharp money on OVER 7.5", my_pick: "OVER FIRE 2u"
    },
    {
      pitcher: "Spencer Strider", team: "ATL", opp: "MIA", game_time: "2026-04-16T23:20:00Z",
      k_line: 8.5, open_line: 9.5, direction: "under", cents: 20,
      open_odds: +100, cur_odds: -110, books_moved: 7, books_total: 7,
      note: "Line dropped 1 full K — coordinated", my_pick: "OVER FIRE 1u"
    },
    {
      pitcher: "Patrick Corbin", team: "TOR", opp: "MIL", game_time: "2026-04-16T17:40:00Z",
      k_line: 4.5, open_line: 4.5, direction: "under", cents: 8,
      open_odds: -178, cur_odds: -186, books_moved: 4, books_total: 7,
      note: "Quiet drift toward UNDER", my_pick: null
    },
    {
      pitcher: "Jack Leiter", team: "TEX", opp: "ATH", game_time: "2026-04-16T19:05:00Z",
      k_line: 5.5, open_line: 5.5, direction: "over", cents: 17,
      open_odds: -106, cur_odds: -122, books_moved: 5, books_total: 7,
      note: "Reverse line move — public on UNDER", my_pick: "UNDER LEAN"
    }
  ]
};
