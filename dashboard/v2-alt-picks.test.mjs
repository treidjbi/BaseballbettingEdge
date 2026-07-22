import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import vm from "node:vm";

const source = await fs.readFile(new URL("./v2-alt-picks.js", import.meta.url), "utf8");

function load({ payload, status = 200 } = {}) {
  const calls = [];
  const window = {
    V2_DATA: { date: "2026-07-21", pitchers: [{ pitcher: "Official pick" }] },
    V2_PERF: { rows: [] },
    V2_APP_STATE: "ready",
    V2_CURRENT_DATE: "2026-07-21",
  };
  const fetch = async (url) => {
    calls.push(String(url));
    return { ok: status >= 200 && status < 300, status, json: async () => payload };
  };
  const context = { window, fetch, Intl, Date, console };
  context.globalThis = context;
  vm.runInNewContext(source, context, { filename: "v2-alt-picks.js" });
  return { api: window.V2AltPicks, window, calls };
}

function row(overrides = {}) {
  return {
    slate_date: "2026-07-21", pitcher: "Test Pitcher", team: "ARI", opp_team: "LAD",
    game_time: "2026-07-21T23:00:00Z", side: "over", model_k_line: 5.5,
    official_odds: -115, official_book: "fanduel", official_verdict: "FIRE 1u",
    selector_id: "no_drag_distinct_family_consensus_core_v1",
    lane: "consensus_core", selection_status: "selected", checkpoint: "frozen_pregame",
    family_states: {
      base: { state: "agree" }, anchor: { state: "disagree" },
      preclose: { state: "pending", reason_codes: ["awaiting"] }, reentry: { state: "agree" },
    },
    family_count: 3, reason_codes: ["selected"], source_artifact_generated_at: "2026-07-21T20:00:00Z",
    evidence_freshness_status: "fresh", evidence_observation_count: 2,
    evidence_first_observed_at: "2026-07-21T19:40:00Z", evidence_last_observed_at: "2026-07-21T19:50:00Z",
    frozen_at: "2026-07-21T22:32:00Z", should_lock_at: "2026-07-21T22:30:00Z",
    minutes_until_start: 28, lock_status: "due_now", artifact_advanced_after_freeze: false,
    ...overrides,
  };
}

test("fetchCurrentSlate calls only the current alternative-picks endpoint", async () => {
  const { api, calls } = load({ payload: { slate_date: "2026-07-21", status: "ready", counts: {}, rows: [] } });
  await api.fetchCurrentSlate();
  assert.deepEqual(calls, ["/.netlify/functions/alternative-picks"]);
});

test("normalizeResponse retains only current-slate rows with the approved two lanes, checkpoints, and four family keys", () => {
  const { api } = load();
  const normalized = api.normalizeResponse({
    slate_date: "2026-07-21", status: "ready", counts: { selected: 1 }, rows: [
      row(), row({ lane: "not_a_lane" }), row({ selection_status: "invalid" }), row({ checkpoint: "postgame" }),
      row({ slate_date: "2026-07-20" }), row({ family_states: { base: { state: "agree" } } }),
    ],
  });
  assert.equal(normalized.status, "ready");
  assert.equal(normalized.rows.length, 1);
  assert.deepEqual(Object.keys(normalized.rows[0].family_states), ["base", "anchor", "preclose", "reentry"]);
});

test("normalizeResponse retains null-lane supporting rows and rejects invalid lane-selector-status combinations", () => {
  const { api } = load();
  const missingLane = row({ lane: null, selector_id: null, selection_status: "pending" });
  delete missingLane.lane;
  const missingSelector = row({ lane: null, selector_id: null, selection_status: "pending" });
  delete missingSelector.selector_id;
  const normalized = api.normalizeResponse({
    slate_date: "2026-07-21", status: "ready", counts: {}, rows: [
      row({ lane: null, selector_id: null, selection_status: "not_selected" }),
      row({ lane: null, selector_id: null, selection_status: "pending" }),
      row({ selection_status: "pending" }),
      row({ lane: null, selector_id: null, selection_status: "selected" }),
      row({ selection_status: "not_selected" }),
      row({ lane: null, selector_id: "no_drag_distinct_family_consensus_core_v1", selection_status: "pending" }),
      row({ selector_id: null, selection_status: "pending" }),
      row({ selector_id: "moderate_edge_quality_reentry_expansion_v1", selection_status: "pending" }),
      row({ lane: "", selector_id: "", selection_status: "pending" }),
      row({ lane: "   ", selector_id: "\t", selection_status: "pending" }),
      row({ lane: undefined, selector_id: undefined, selection_status: "pending" }),
      missingLane,
      missingSelector,
    ],
  });
  assert.deepEqual(
    normalized.rows.map(item => [item.selection_status, item.lane, item.selector_id]),
    [
      ["not_selected", null, null],
      ["pending", null, null],
      ["pending", "consensus_core", "no_drag_distinct_family_consensus_core_v1"],
    ],
  );
});

test("normalized supporting rows distinguish healthy no qualifiers from waiting for rows", () => {
  const { api } = load();
  const healthy = api.normalizeResponse({
    slate_date: "2026-07-21", status: "ready", counts: {},
    rows: [row({ lane: null, selector_id: null, selection_status: "not_selected" })],
  });
  const waiting = api.normalizeResponse({
    slate_date: "2026-07-21", status: "ready", counts: {}, rows: [],
  });
  assert.equal(healthy.rows.length, 1);
  assert.equal(healthy.rows[0].selection_status, "not_selected");
  assert.equal(waiting.rows.length, 0);
});

test("formatFreezeLabel uses actual checkpoint capture values", () => {
  const { api } = load();
  assert.equal(api.formatFreezeLabel(row({ checkpoint: "provisional", frozen_at: null, minutes_until_start: null })), "Provisional");
  assert.equal(api.formatFreezeLabel(row({ minutes_until_start: 28, lock_status: "due_now" })), "Frozen T-28");
  assert.equal(api.formatFreezeLabel(row({ minutes_until_start: 21, lock_status: "missed_lock" })), "Frozen T-21 (late)");
});

test("frozen rows require real ISO capture timestamps and known lock states", () => {
  const { api } = load();
  const normalized = api.normalizeResponse({
    slate_date: "2026-07-21", status: "ready", counts: {}, rows: [
      row({ frozen_at: "not-a-timestamp" }),
      row({ lock_status: "unknown_lock_state" }),
      row({ evidence_last_observed_at: "not-a-timestamp" }),
      row(),
    ],
  });
  assert.equal(normalized.rows.length, 1);
  assert.equal(api.formatFreezeLabel(row({ frozen_at: "not-a-timestamp", lock_status: "unknown_lock_state" })), "Provisional");
});

test("zero-observation pending rows allow paired null evidence times only", () => {
  const { api } = load();
  const normalized = api.normalizeResponse({
    slate_date: "2026-07-21", status: "ready", counts: {}, rows: [
      row({ checkpoint: "provisional", selection_status: "pending", evidence_observation_count: 0, evidence_freshness_status: "pending", evidence_first_observed_at: null, evidence_last_observed_at: null }),
      row({ checkpoint: "provisional", selection_status: "pending", evidence_observation_count: 0, evidence_freshness_status: "pending", evidence_first_observed_at: null }),
      row({ checkpoint: "provisional", selection_status: "not_selected", evidence_observation_count: 0, evidence_freshness_status: "pending", evidence_first_observed_at: null, evidence_last_observed_at: null }),
      row({ checkpoint: "provisional", selection_status: "pending", evidence_observation_count: 0, evidence_freshness_status: "fresh", evidence_first_observed_at: null, evidence_last_observed_at: null }),
      row({ checkpoint: "provisional", evidence_observation_count: 2, evidence_first_observed_at: "not-a-timestamp" }),
    ],
  });
  assert.equal(normalized.rows.length, 1);
  assert.equal(normalized.rows[0].selection_status, "pending");
});

test("adapter failures stay local and do not mutate official or accepted-bet state", async () => {
  const { api, window } = load({ payload: null, status: 503 });
  const data = window.V2_DATA, perf = window.V2_PERF, state = window.V2_APP_STATE, pitcher = data.pitchers[0];
  const result = await api.fetchCurrentSlate();
  assert.equal(result.status, "unavailable");
  assert.equal(window.V2_DATA, data);
  assert.equal(window.V2_PERF, perf);
  assert.equal(window.V2_APP_STATE, state);
  assert.equal(window.V2_DATA.pitchers[0], pitcher);
  assert.equal(window.__v2DataPromise, undefined);
  assert.equal(window.BET_LOG_ACCEPTED_STORAGE, undefined);
});
