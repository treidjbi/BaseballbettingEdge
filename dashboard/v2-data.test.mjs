import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";

const scriptPath = path.resolve("dashboard/v2-data.js");
const scriptSource = await fs.readFile(scriptPath, "utf8");

function jsonResponse(payload) {
  return {
    ok: true,
    async json() {
      return payload;
    },
  };
}

async function runV2DataTest({
  locationSearch = "",
  now = null,
  artifactSource = null,
  artifactApiMode = "ok",
  todayJson,
  perfJson = { rows: [], total_picks: 0 },
  paramsJson = {},
  dateIndex = [],
  steamJson = null,
  liveMarketDisplay = undefined,
  liveMarketApiMode = "ok",
  liveMarketApiPayload = { generated_at: null, rows: [] },
}) {
  const window = {};
  if (liveMarketDisplay !== undefined) {
    window.V2_LIVE_MARKET_DISPLAY = liveMarketDisplay;
  }
  const fetchUrls = [];
  const TestDate = now == null ? Date : class extends Date {
    constructor(...args) {
      super(...(args.length ? args : [now]));
    }
    static now() {
      return now;
    }
  };
  const fetch = async (url) => {
    const rawUrl = String(url);
    fetchUrls.push(rawUrl);
    const bareUrl = rawUrl.replace(/[?&]t=\d+$/, "");
    if (bareUrl.startsWith("/.netlify/functions/live-market-display")) {
      if (liveMarketApiMode === "error") {
        return { ok: false, status: 502, async text() { return "bad gateway"; } };
      }
      return jsonResponse(liveMarketApiPayload);
    }
    if (bareUrl.startsWith("/.netlify/functions/get-artifact")) {
      if (artifactApiMode === "error") {
        return { ok: false, status: 502, async text() { return "bad gateway"; } };
      }
      const parsed = new URL(bareUrl, "https://example.com");
      const type = parsed.searchParams.get("type") || "today";
      if (type === "performance") return jsonResponse(perfJson);
      if (type === "params") return jsonResponse(paramsJson);
      if (type === "index") return jsonResponse({ dates: dateIndex });
      if (type === "steam") return jsonResponse(steamJson);
      if (type === "today" || type === "dated_slate") return jsonResponse(todayJson);
    }
    if (/\/\d{4}-\d{2}-\d{2}\.json$/.test(bareUrl)) return jsonResponse(todayJson);
    if (bareUrl.endsWith("/2026-04-27.json")) return jsonResponse(todayJson);
    if (bareUrl.endsWith("/today.json")) return jsonResponse(todayJson);
    if (bareUrl.endsWith("/performance.json")) return jsonResponse(perfJson);
    if (bareUrl.endsWith("/params.json")) return jsonResponse(paramsJson);
    if (bareUrl.endsWith("/index.json")) return jsonResponse({ dates: dateIndex });
    if (bareUrl.endsWith("/steam.json")) return jsonResponse(steamJson);
    throw new Error(`Unexpected fetch URL: ${bareUrl}`);
  };

  const context = {
    window,
    location: {
      hostname: "example.com",
      protocol: "https:",
      search: locationSearch,
    },
    fetch,
    console,
    Date: TestDate,
    URLSearchParams,
    URL,
    localStorage: {
      getItem(key) {
        return key === "bbe_artifact_source" ? artifactSource : null;
      },
    },
    setTimeout,
    clearTimeout,
  };
  context.globalThis = context;

  vm.runInNewContext(scriptSource, context, { filename: scriptPath });
  await window.__v2DataPromise;
  window.__fetchUrls = fetchUrls;
  return window;
}

test("loads artifacts from api when enabled", async () => {
  const todayJson = { date: "2026-04-28", generated_at: "2026-04-28T15:00:00Z", pitchers: [] };
  const window = await runV2DataTest({
    artifactSource: "supabase",
    todayJson,
    perfJson: { rows: [], total_picks: 4 },
    dateIndex: [{ date: "2026-04-28", wins: 0, losses: 0 }],
    steamJson: { date: "2026-04-28", snapshots: [] },
  });

  assert.equal(window.V2_DATA.date, "2026-04-28");
  assert.equal(window.V2_PERF.total_picks, 4);
  assert.equal(window.V2_DATES.length, 1);
  assert.ok(window.__fetchUrls.some(url => String(url).startsWith("/.netlify/functions/get-artifact")));
});

test("loads artifacts from api by default", async () => {
  const todayJson = { date: "2026-04-28", generated_at: "2026-04-28T15:00:00Z", pitchers: [] };
  const window = await runV2DataTest({
    todayJson,
    perfJson: { rows: [], total_picks: 5 },
    dateIndex: [{ date: "2026-04-28", wins: 0, losses: 0 }],
    steamJson: { date: "2026-04-28", snapshots: [] },
  });

  assert.equal(window.V2_DATA.date, "2026-04-28");
  assert.equal(window.V2_PERF.total_picks, 5);
  assert.ok(window.__fetchUrls.some(url => String(url).startsWith("/.netlify/functions/get-artifact")));
});

test("falls back to static artifacts when api fails", async () => {
  const todayJson = { date: "2026-04-28", generated_at: "2026-04-28T15:00:00Z", pitchers: [] };
  const window = await runV2DataTest({
    artifactSource: "supabase",
    artifactApiMode: "error",
    todayJson,
    perfJson: { rows: [], total_picks: 3 },
    dateIndex: [{ date: "2026-04-28", wins: 0, losses: 0 }],
    steamJson: { date: "2026-04-28", snapshots: [] },
  });

  assert.equal(window.V2_DATA.date, "2026-04-28");
  assert.equal(window.V2_PERF.total_picks, 3);
  assert.equal(window.V2_DATES.length, 1);
  assert.ok(window.__fetchUrls.some(url => String(url).startsWith("/.netlify/functions/get-artifact")));
  assert.ok(window.__fetchUrls.some(url => String(url).includes("/today.json") || /\d{4}-\d{2}-\d{2}\.json/.test(String(url))));
});

test("getAppDate stays on current Phoenix date after 9pm", async () => {
  const todayJson = { date: "2026-04-28", generated_at: "2026-04-28T04:30:00Z", pitchers: [] };
  const window = await runV2DataTest({
    now: Date.parse("2026-04-29T04:30:00Z"), // 2026-04-28 9:30 PM in Phoenix
    todayJson,
  });

  assert.equal(window.__v2GetAppDate(), "2026-04-28");
  assert.equal(window.V2_CURRENT_DATE, "2026-04-28");
});

test("archive loads ignore steam snapshots from a different date", async () => {
  const todayJson = {
    date: "2026-04-27",
    generated_at: "2026-04-27T23:00:00Z",
    pitchers: [
      {
        pitcher: "Test Pitcher",
        team: "A",
        opp_team: "B",
        game_time: "2026-04-27T23:10:00Z",
        k_line: 6.5,
        opening_line: 6.5,
        best_over_odds: -120,
        best_under_odds: 100,
        opening_over_odds: -110,
        opening_under_odds: -102,
        lambda: 6.8,
        avg_ip: 5.8,
        opp_k_rate: 0.24,
        ump_k_adj: 0.1,
        season_k9: 9.1,
        recent_k9: 9.3,
        career_k9: 8.9,
        ev_over: { adj_ev: 0.08, ev: 0.09, edge: 0.03, verdict: "FIRE 1u" },
        ev_under: { adj_ev: -0.05, ev: -0.04, edge: -0.02, verdict: "PASS" },
      },
    ],
  };
  const steamJson = {
    date: "2026-04-28",
    snapshots: [
      {
        t: "2026-04-28T12:00:00Z",
        pitchers: {
          "Test Pitcher": {
            k_line: 6.5,
            FanDuel: { over: -110, under: -102 },
          },
        },
      },
      {
        t: "2026-04-28T18:00:00Z",
        pitchers: {
          "Test Pitcher": {
            k_line: 6.5,
            FanDuel: { over: -125, under: 104 },
          },
        },
      },
    ],
  };

  const window = await runV2DataTest({
    locationSearch: "?date=2026-04-27",
    todayJson,
    dateIndex: [{ date: "2026-04-27", wins: 0, losses: 0 }],
    steamJson,
  });

  assert.equal(window.V2_CURRENT_DATE, "2026-04-27");
  assert.equal(window.V2_STEAM.rows.length, 1);
  assert.equal(window.V2_STEAM.rows[0].books_total, null);
  assert.equal(window.V2_STEAM.rows[0].books_moved, null);
  assert.ok(window.V2_STEAM_RAW);
  assert.ok(Array.isArray(window.V2_STEAM_RAW.snapshots));
  assert.equal(window.V2_STEAM_RAW.snapshots.length, 0);
});

test("archive loads accept steam snapshots when archive_dates includes the slate", async () => {
  const todayJson = {
    date: "2026-04-27",
    generated_at: "2026-04-27T23:00:00Z",
    pitchers: [
      {
        pitcher: "Late Night Pitcher",
        team: "A",
        opp_team: "B",
        game_time: "2026-04-28T00:05:00Z",
        k_line: 6.5,
        opening_line: 6.5,
        best_over_odds: -125,
        best_under_odds: 104,
        opening_over_odds: -110,
        opening_under_odds: -102,
        lambda: 6.8,
        avg_ip: 5.8,
        opp_k_rate: 0.24,
        ump_k_adj: 0.1,
        season_k9: 9.1,
        recent_k9: 9.3,
        career_k9: 8.9,
        ev_over: { adj_ev: 0.08, ev: 0.09, edge: 0.03, verdict: "FIRE 1u" },
        ev_under: { adj_ev: -0.05, ev: -0.04, edge: -0.02, verdict: "PASS" },
      },
    ],
  };
  const steamJson = {
    date: "2026-04-28",
    archive_dates: ["2026-04-27"],
    snapshots: [
      {
        t: "2026-04-28T12:00:00Z",
        pitchers: {
          "Late Night Pitcher": {
            k_line: 6.5,
            FanDuel: { over: -110, under: -102 },
          },
        },
      },
      {
        t: "2026-04-28T18:00:00Z",
        pitchers: {
          "Late Night Pitcher": {
            k_line: 6.5,
            FanDuel: { over: -125, under: 104 },
          },
        },
      },
    ],
  };

  const window = await runV2DataTest({
    locationSearch: "?date=2026-04-27",
    todayJson,
    dateIndex: [{ date: "2026-04-27", wins: 0, losses: 0 }],
    steamJson,
  });

  assert.equal(window.V2_CURRENT_DATE, "2026-04-27");
  assert.equal(window.V2_STEAM.rows.length, 1);
  assert.equal(window.V2_STEAM.rows[0].books_total, 1);
  assert.equal(window.V2_STEAM.rows[0].books_moved, 1);
  assert.ok(window.V2_STEAM_RAW);
  assert.ok(Array.isArray(window.V2_STEAM_RAW.snapshots));
  assert.equal(window.V2_STEAM_RAW.snapshots.length, 2);
});

test("tracked picks are exposed top-level and attached to matching pitchers", async () => {
  const todayJson = {
    date: "2026-04-28",
    generated_at: "2026-04-28T23:00:00Z",
    tracked_picks: [
      {
        date: "2026-04-28",
        pitcher: "Tracked Pitcher",
        team: "SEA",
        opp_team: "CLE",
        side: "under",
        display_side: "UNDER",
        verdict: "FIRE 1u",
        locked_verdict: "FIRE 1u",
        display_verdict: "FIRE 1u",
        k_line: 5.5,
        locked_k_line: 5.5,
        display_k_line: 5.5,
        odds: -112,
        locked_odds: -118,
        display_odds: -118,
        adj_ev: 0.08,
        locked_adj_ev: 0.09,
        display_adj_ev: 0.09,
        locked_at: "2026-04-28T23:15:00Z",
      },
    ],
    pitchers: [
      {
        pitcher: "Tracked Pitcher",
        team: "SEA",
        opp_team: "CLE",
        game_time: "2026-04-28T23:10:00Z",
        k_line: 5.5,
        best_over_odds: -105,
        best_under_odds: -118,
        lambda: 4.9,
        avg_ip: 5.8,
        opp_k_rate: 0.24,
        season_k9: 9.1,
        recent_k9: 9.3,
        career_k9: 8.9,
        ev_over: { adj_ev: -0.02, ev: -0.01, edge: -0.02, verdict: "PASS" },
        ev_under: { adj_ev: 0.04, ev: 0.05, edge: 0.02, verdict: "LEAN" },
      },
    ],
  };

  const window = await runV2DataTest({ todayJson });

  assert.equal(window.V2_DATA.tracked_picks.length, 1);
  assert.equal(window.V2_DATA.tracked_picks[0].verdict, "FIRE 1u");
  assert.equal(window.V2_DATA.tracked_picks[0].k_line, 5.5);
  assert.equal(window.V2_DATA.tracked_picks[0].odds, -118);
  assert.equal(window.V2_DATA.pitchers[0].tracked_picks.length, 1);
  assert.equal(window.V2_DATA.pitchers[0].tracked_picks[0].direction, "UNDER");
});

test("live market display stays disabled without the hidden query flag", async () => {
  const todayJson = {
    date: "2026-04-28",
    generated_at: "2026-04-28T23:00:00Z",
    pitchers: [
      {
        pitcher: "Market Pitcher",
        team: "SEA",
        opp_team: "CLE",
        game_time: "2026-04-28T23:10:00Z",
        k_line: 5.5,
        best_over_odds: -105,
        best_under_odds: -118,
        lambda: 4.9,
        avg_ip: 5.8,
        opp_k_rate: 0.24,
        season_k9: 9.1,
        recent_k9: 9.3,
        career_k9: 8.9,
        ev_over: { adj_ev: -0.02, ev: -0.01, edge: -0.02, verdict: "PASS" },
        ev_under: { adj_ev: 0.04, ev: 0.05, edge: 0.02, verdict: "LEAN", win_prob: 0.54 },
      },
    ],
  };

  const window = await runV2DataTest({
    todayJson,
    liveMarketDisplay: [
      {
        slate_date: "2026-04-28",
        normalized_pitcher: "market pitcher",
        side: "under",
        actionable_state: "shop_price",
        freshness_status: "fresh",
        best_book: "DraftKings",
        best_line: 5.5,
        best_odds: -112,
        book_count: 3,
      },
    ],
  });

  assert.equal(window.V2_MARKET_DISPLAY.enabled, false);
  assert.equal(Array.isArray(window.V2_MARKET_DISPLAY.rows), true);
  assert.equal(window.V2_MARKET_DISPLAY.rows.length, 0);
  assert.equal(window.V2_DATA.pitchers[0].market_display, undefined);
  assert.equal(window.__fetchUrls.some(url => String(url).startsWith("/.netlify/functions/live-market-display")), false);
});

test("live market display fetches sanitized endpoint rows only behind the hidden flag", async () => {
  const todayJson = {
    date: "2026-04-28",
    generated_at: "2026-04-28T23:00:00Z",
    pitchers: [
      {
        pitcher: "Endpoint Pitcher",
        team: "SEA",
        opp_team: "CLE",
        game_time: "2026-04-28T23:10:00Z",
        k_line: 5.5,
        best_over_odds: -105,
        best_under_odds: -118,
        lambda: 4.9,
        avg_ip: 5.8,
        opp_k_rate: 0.24,
        season_k9: 9.1,
        recent_k9: 9.3,
        career_k9: 8.9,
        ev_over: { adj_ev: -0.02, ev: -0.01, edge: -0.02, verdict: "PASS", win_prob: 0.46 },
        ev_under: { adj_ev: 0.04, ev: 0.05, edge: 0.02, verdict: "LEAN", win_prob: 0.54 },
      },
    ],
  };

  const window = await runV2DataTest({
    locationSearch: "?marketSheet=1",
    todayJson,
    liveMarketApiPayload: {
      generated_at: "2026-04-28T22:57:00Z",
      slate_date: "2026-04-28",
      source: "live_market_display_state",
      rows: [
        {
          slate_date: "2026-04-28",
          normalized_pitcher: "endpoint pitcher",
          pitcher: "Endpoint Pitcher",
          side: "under",
          provider: "boltodds",
          observed_at: "2026-04-28T22:57:00Z",
          freshness_status: "fresh",
          market_status: "market_confirmed_playable",
          actionable_state: "playable_now",
          market_consensus: "toward_pick",
          bet_value_consensus: "worse_now",
          main_line: 5.5,
          best_book: "DraftKings",
          best_line: 5.5,
          best_odds: -112,
          book_count: 3,
          books_seen: ["DraftKings", "FanDuel", "BetMGM"],
          broad_confirmation: true,
          book_rows: [
            { bookmaker_key: "draftkings", bookmaker_title: "DraftKings", line: 5.5, odds: -112 },
          ],
        },
      ],
    },
  });

  const marketFetch = window.__fetchUrls.find(url => String(url).startsWith("/.netlify/functions/live-market-display"));
  const pitcher = window.V2_DATA.pitchers[0];
  assert.ok(marketFetch);
  assert.match(marketFetch, /date=2026-04-28/);
  assert.equal(window.V2_MARKET_DISPLAY.enabled, true);
  assert.equal(window.V2_MARKET_DISPLAY.generated_at, "2026-04-28T22:57:00Z");
  assert.equal(window.V2_MARKET_DISPLAY.rows.length, 1);
  assert.equal(pitcher.market_display.UNDER.action_label, "playable");
  assert.equal(pitcher.market_display.UNDER.best_book, "DraftKings");
  assert.equal(pitcher.market_display.UNDER.best_odds, -112);
});

test("live market display prefers fresh provider rows over stale rows for the same pitcher side", async () => {
  const todayJson = {
    date: "2026-04-28",
    generated_at: "2026-04-28T23:00:00Z",
    pitchers: [
      {
        pitcher: "Provider Pitcher",
        team: "SEA",
        opp_team: "CLE",
        game_time: "2026-04-28T23:10:00Z",
        k_line: 5.5,
        best_over_odds: -105,
        best_under_odds: -118,
        lambda: 4.9,
        avg_ip: 5.8,
        opp_k_rate: 0.24,
        season_k9: 9.1,
        recent_k9: 9.3,
        career_k9: 8.9,
        ev_over: { adj_ev: -0.02, ev: -0.01, edge: -0.02, verdict: "PASS", win_prob: 0.46 },
        ev_under: { adj_ev: 0.04, ev: 0.05, edge: 0.02, verdict: "LEAN", win_prob: 0.54 },
      },
    ],
  };

  const window = await runV2DataTest({
    locationSearch: "?marketSheet=1",
    todayJson,
    liveMarketDisplay: {
      generated_at: "2026-04-28T22:57:00Z",
      rows: [
        {
          slate_date: "2026-04-28",
          normalized_pitcher: "provider pitcher",
          pitcher: "Provider Pitcher",
          side: "under",
          provider: "boltodds",
          observed_at: "2026-04-28T22:57:00Z",
          freshness_status: "fresh",
          market_status: "market_confirmed_playable",
          actionable_state: "playable_now",
          market_consensus: "toward_pick",
          bet_value_consensus: "worse_now",
          main_line: 5.5,
          best_book: "DraftKings",
          best_line: 5.5,
          best_odds: -112,
          book_count: 3,
          books_seen: ["DraftKings", "FanDuel", "BetMGM"],
        },
        {
          slate_date: "2026-04-28",
          normalized_pitcher: "provider pitcher",
          pitcher: "Provider Pitcher",
          side: "under",
          provider: "propline",
          observed_at: "2026-04-28T22:58:00Z",
          freshness_status: "stale",
          market_status: "no_clear_signal",
          actionable_state: "stale",
          market_consensus: "none",
          bet_value_consensus: "none",
          main_line: 5.5,
          best_book: null,
          best_line: null,
          best_odds: null,
          book_count: 3,
          books_seen: ["DraftKings", "FanDuel", "BetRivers"],
        },
      ],
    },
  });

  const row = window.V2_DATA.pitchers[0].market_display.UNDER;
  assert.equal(row.provider, "boltodds");
  assert.equal(row.freshness_status, "fresh");
  assert.equal(row.best_book, "DraftKings");
  assert.equal(row.best_odds, -112);
});

test("live market display rows normalize and attach to matching pitcher sides behind the hidden flag", async () => {
  const todayJson = {
    date: "2026-04-28",
    generated_at: "2026-04-28T23:00:00Z",
    pitchers: [
      {
        pitcher: "Market Pitcher",
        team: "SEA",
        opp_team: "CLE",
        game_time: "2026-04-28T23:10:00Z",
        k_line: 5.5,
        best_over_odds: -105,
        best_under_odds: -118,
        lambda: 4.9,
        avg_ip: 5.8,
        opp_k_rate: 0.24,
        season_k9: 9.1,
        recent_k9: 9.3,
        career_k9: 8.9,
        ev_over: { adj_ev: -0.02, ev: -0.01, edge: -0.02, verdict: "PASS", win_prob: 0.46 },
        ev_under: { adj_ev: 0.04, ev: 0.05, edge: 0.02, verdict: "LEAN", win_prob: 0.54 },
      },
    ],
  };

  const window = await runV2DataTest({
    locationSearch: "?marketSheet=1",
    todayJson,
    liveMarketDisplay: {
      generated_at: "2026-04-28T22:55:00Z",
      rows: [
        {
          slate_date: "2026-04-28",
          normalized_pitcher: "market pitcher",
          pitcher: "Market Pitcher",
          side: "under",
          provider: "boltodds",
          observed_at: "2026-04-28T22:55:00Z",
          freshness_status: "fresh",
          market_status: "market_confirmed_playable",
          actionable_state: "shop_price",
          market_consensus: "toward_pick",
          bet_value_consensus: "worse_now",
          main_line: 5.5,
          best_book: "DraftKings",
          best_line: 5.5,
          best_odds: -112,
          book_count: 3,
          books_seen: ["DraftKings", "FanDuel", "BetMGM"],
          broad_confirmation: true,
          book_rows: [
            { bookmaker_key: "draftkings", bookmaker_title: "DraftKings", line: 5.5, odds: -112 },
            { bookmaker_key: "fanduel", bookmaker_title: "FanDuel", line: 5.5, odds: -118 },
          ],
        },
      ],
    },
  });

  const pitcher = window.V2_DATA.pitchers[0];
  assert.equal(window.V2_MARKET_DISPLAY.enabled, true);
  assert.equal(window.V2_MARKET_DISPLAY.rows.length, 1);
  assert.equal(pitcher.market_display.UNDER.action_label, "shop_price");
  assert.equal(pitcher.market_display.UNDER.best_book, "DraftKings");
  assert.equal(pitcher.market_display.UNDER.best_odds, -112);
  assert.equal(pitcher.market_display.UNDER.book_rows.length, 2);
  assert.equal(pitcher.market_display.OVER, undefined);
});

test("live market display ignores wrong-date and malformed rows", async () => {
  const todayJson = {
    date: "2026-04-28",
    generated_at: "2026-04-28T23:00:00Z",
    pitchers: [
      {
        pitcher: "Market Pitcher",
        team: "SEA",
        opp_team: "CLE",
        game_time: "2026-04-28T23:10:00Z",
        k_line: 5.5,
        best_over_odds: -105,
        best_under_odds: -118,
        lambda: 4.9,
        avg_ip: 5.8,
        opp_k_rate: 0.24,
        ev_over: { adj_ev: -0.02, ev: -0.01, edge: -0.02, verdict: "PASS" },
        ev_under: { adj_ev: 0.04, ev: 0.05, edge: 0.02, verdict: "LEAN" },
      },
    ],
  };

  const window = await runV2DataTest({
    locationSearch: "?marketSheet=1",
    todayJson,
    liveMarketDisplay: [
      { slate_date: "2026-04-27", normalized_pitcher: "market pitcher", side: "under", best_odds: -112 },
      { slate_date: "2026-04-28", normalized_pitcher: "market pitcher", best_odds: -112 },
      { slate_date: "2026-04-28", side: "under", best_odds: -112 },
      { slate_date: "2026-04-28", normalized_pitcher: "market pitcher", side: "under", provider: "unsupported_provider", best_odds: -112 },
    ],
  });

  assert.equal(window.V2_MARKET_DISPLAY.enabled, true);
  assert.equal(Array.isArray(window.V2_MARKET_DISPLAY.rows), true);
  assert.equal(window.V2_MARKET_DISPLAY.rows.length, 0);
  assert.equal(window.V2_DATA.pitchers[0].market_display, undefined);
});

test("live market display labels stale rows and cleans malformed book rows", async () => {
  const todayJson = {
    date: "2026-04-28",
    generated_at: "2026-04-28T23:00:00Z",
    pitchers: [
      {
        pitcher: "Market Pitcher",
        team: "SEA",
        opp_team: "CLE",
        game_time: "2026-04-28T23:10:00Z",
        k_line: 5.5,
        best_over_odds: -105,
        best_under_odds: -118,
        lambda: 4.9,
        avg_ip: 5.8,
        opp_k_rate: 0.24,
        ev_over: { adj_ev: -0.02, ev: -0.01, edge: -0.02, verdict: "PASS" },
        ev_under: { adj_ev: 0.04, ev: 0.05, edge: 0.02, verdict: "LEAN" },
      },
    ],
  };

  const window = await runV2DataTest({
    locationSearch: "?marketSheet=1",
    todayJson,
    liveMarketDisplay: [
      {
        slate_date: "2026-04-28",
        normalized_pitcher: "market pitcher",
        side: "under",
        provider: "propline",
        freshness_status: "stale",
        actionable_state: "shop_price",
        best_book: "DraftKings",
        best_line: "5.5",
        best_odds: "-112",
        book_rows: [
          {},
          { bookmaker_title: "DraftKings", line: "5.5", odds: "-112" },
        ],
      },
    ],
  });

  const row = window.V2_DATA.pitchers[0].market_display.UNDER;
  assert.equal(row.action_label, "stale");
  assert.equal(row.best_line, 5.5);
  assert.equal(row.best_odds, -112);
  assert.equal(row.book_rows.length, 1);
  assert.equal(row.book_rows[0].bookmaker_title, "DraftKings");
});

test("old archive records default to clean quality metadata", async () => {
  const todayJson = {
    date: "2026-04-29",
    generated_at: "2026-04-29T18:00:00Z",
    pitchers: [
      {
        pitcher: "Legacy Pitcher",
        team: "A",
        opp_team: "B",
        game_time: "2026-04-29T23:10:00Z",
        k_line: 6.5,
        best_over_odds: -110,
        best_under_odds: -110,
        lambda: 6.9,
        avg_ip: 5.7,
        opp_k_rate: 0.23,
        ev_over: { adj_ev: 0.08, ev: 0.09, edge: 0.03, verdict: "FIRE 1u" },
        ev_under: { adj_ev: -0.04, ev: -0.03, edge: -0.02, verdict: "PASS" },
      },
    ],
  };

  const window = await runV2DataTest({ todayJson });
  const pitcher = window.V2_DATA.pitchers[0];

  assert.equal(Array.isArray(pitcher.input_quality_flags), true);
  assert.equal(pitcher.input_quality_flags.length, 0);
  assert.equal(pitcher.projection_safe, true);
  assert.equal(pitcher.quality_gate_level, "clean");
  assert.equal(Array.isArray(pitcher.quality_gate_reasons), true);
  assert.equal(pitcher.quality_gate_reasons.length, 0);
  assert.equal(pitcher.verdict_cap_reason, "");
  assert.equal(pitcher.ev_over.raw_verdict, "FIRE 1u");
  assert.equal(pitcher.ev_over.actionable_verdict, "FIRE 1u");
});

test("quality metadata and raw actionable verdicts pass through", async () => {
  const todayJson = {
    date: "2026-04-29",
    generated_at: "2026-04-29T18:00:00Z",
    quality_gate_summary: { clean: 0, capped: 1, blocked: 0 },
    pitchers: [
      {
        pitcher: "Capped Pitcher",
        team: "A",
        opp_team: "B",
        game_time: "2026-04-29T23:10:00Z",
        k_line: 6.5,
        best_over_odds: -110,
        best_under_odds: -110,
        lambda: 7.2,
        avg_ip: 5.7,
        opp_k_rate: 0.23,
        input_quality_flags: ["unrated_umpire"],
        projection_safe: true,
        quality_gate_level: "capped",
        quality_gate_reasons: ["unrated umpire"],
        verdict_cap_reason: "1 soft input flag: unrated_umpire",
        data_maturity: { pitcher: "mature", umpire: "unknown", lineup: "confirmed", market: "preview_open" },
        ev_over: {
          adj_ev: 0.19,
          raw_adj_ev: 0.19,
          ev: 0.2,
          edge: 0.08,
          verdict: "FIRE 1u",
          raw_verdict: "FIRE 2u",
          actionable_verdict: "FIRE 1u",
        },
        ev_under: { adj_ev: -0.04, raw_adj_ev: -0.04, ev: -0.03, edge: -0.02, verdict: "PASS", raw_verdict: "PASS", actionable_verdict: "PASS" },
      },
    ],
  };

  const window = await runV2DataTest({ todayJson });
  const pitcher = window.V2_DATA.pitchers[0];

  assert.deepEqual(window.V2_DATA.quality_gate_summary, { clean: 0, capped: 1, blocked: 0 });
  assert.equal(pitcher.quality_gate_level, "capped");
  assert.deepEqual(pitcher.input_quality_flags, ["unrated_umpire"]);
  assert.equal(pitcher.data_maturity.umpire, "unknown");
  assert.equal(pitcher.ev_over.raw_verdict, "FIRE 2u");
  assert.equal(pitcher.ev_over.actionable_verdict, "FIRE 1u");
});

test("pitcher normalization preserves confirmed unrated umpire metadata", async () => {
  const todayJson = {
    date: "2026-04-29",
    generated_at: "2026-04-29T18:00:00Z",
    pitchers: [
      {
        pitcher: "Taj Bradley",
        team: "Minnesota Twins",
        opp_team: "Seattle Mariners",
        game_time: "2026-04-29T17:40:00Z",
        k_line: 5.5,
        best_over_odds: -105,
        best_under_odds: -125,
        lambda: 5.1,
        avg_ip: 5.8,
        opp_k_rate: 0.24,
        umpire: "Dexter Kelley",
        umpire_has_rating: false,
        ump_k_adj: 0.0,
        season_k9: 9.1,
        recent_k9: 9.3,
        career_k9: 8.9,
        ev_over: { adj_ev: -0.02, ev: -0.01, edge: -0.02, verdict: "PASS" },
        ev_under: { adj_ev: 0.04, ev: 0.05, edge: 0.02, verdict: "LEAN" },
      },
    ],
  };

  const window = await runV2DataTest({ todayJson });
  const pitcher = window.V2_DATA.pitchers[0];

  assert.equal(pitcher.umpire, "Dexter Kelley");
  assert.equal(pitcher.umpire_has_rating, false);
  assert.equal(pitcher.ump_k_adj, 0);
});
