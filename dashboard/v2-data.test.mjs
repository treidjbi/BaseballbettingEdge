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
  todayJson,
  perfJson = { rows: [], total_picks: 0 },
  paramsJson = {},
  dateIndex = [],
  steamJson = null,
}) {
  const window = {};
  const fetch = async (url) => {
    const bareUrl = String(url).split("?t=")[0];
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
    Date,
    URLSearchParams,
    setTimeout,
    clearTimeout,
  };
  context.globalThis = context;

  vm.runInNewContext(scriptSource, context, { filename: scriptPath });
  await window.__v2DataPromise;
  return window;
}

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
