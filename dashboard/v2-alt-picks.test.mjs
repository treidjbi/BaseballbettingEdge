import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import vm from "node:vm";

const source = await fs.readFile(new URL("./v2-alt-picks.js", import.meta.url), "utf8");
const FIXED_NOW = "2026-07-21T20:10:00.000Z";
const BUNDLE_ID = "pregame_alternative_pick_methodology_v2";
const SELECTOR_FINGERPRINT = "23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4";
const SELECTOR_IDS = Object.freeze({
  consensus_core: "no_drag_distinct_family_consensus_core_v2",
  reentry_expansion: "moderate_edge_quality_reentry_expansion_v2",
});

class FixedDate extends Date {
  constructor(...args) {
    super(...(args.length ? args : [FIXED_NOW]));
  }

  static now() { return Date.parse(FIXED_NOW); }
}

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
  const context = { window, fetch, Intl, Date: FixedDate, console };
  context.globalThis = context;
  vm.runInNewContext(source, context, { filename: "v2-alt-picks.js" });
  return { api: window.V2AltPicks, window, calls };
}

function decisionProof(value) {
  const familyStates = value.family_states;
  const decisiveFamilies = ["base", "anchor", "preclose", "reentry"]
    .filter((name) => familyStates[name].state === "agree");
  let laneStates;
  if (value.selection_status === "selected") {
    laneStates = value.lane === "consensus_core"
      ? { consensus_core: "true", reentry_expansion: "false" }
      : { consensus_core: "false", reentry_expansion: "true" };
  } else if (value.selection_status === "not_selected") {
    laneStates = { consensus_core: "false", reentry_expansion: "false" };
  } else {
    laneStates = { consensus_core: "pending", reentry_expansion: "false" };
  }
  const states = value.selection_status === "pending"
    ? { support: "true", drag_core: "pending", no_drag: "pending" }
    : value.selection_status === "not_selected" || value.lane === "reentry_expansion"
      ? { support: "false", drag_core: "false", no_drag: "false" }
      : { support: "true", drag_core: "false", no_drag: "true" };
  return {
    ...states,
    lane_states: laneStates,
    decisive_families: decisiveFamilies,
    preclose_required_for_selected_lane: false,
  };
}

function row(overrides = {}) {
  const value = {
    slate_date: "2026-07-21", pitcher: "Test Pitcher", team: "ARI", opp_team: "LAD",
    game_time: "2026-07-21T23:00:00Z", side: "over", model_k_line: 5.5,
    official_odds: -115, official_book: "fanduel", official_verdict: "FIRE 1u",
    bundle_id: BUNDLE_ID,
    selector_id: SELECTOR_IDS.consensus_core,
    lane: "consensus_core", selection_status: "selected", checkpoint: "frozen_pregame",
    family_states: {
      base: { state: "agree", reason_codes: ["base_ok"] },
      anchor: { state: "agree", reason_codes: ["anchor_ok"] },
      preclose: { state: "pending", reason_codes: ["official_provider_immature"] },
      reentry: { state: "disagree", reason_codes: ["reentry_false"] },
    },
    family_count: 2, reason_codes: ["selected"], source_artifact_generated_at: "2026-07-21T20:00:00Z",
    evidence_freshness_status: "pending", evidence_observation_count: 0,
    evidence_first_observed_at: null, evidence_last_observed_at: null,
    frozen_at: "2026-07-21T22:32:00Z", should_lock_at: "2026-07-21T22:30:00Z",
    minutes_until_start: 28, lock_status: "due_now", artifact_advanced_after_freeze: false,
    ...overrides,
  };
  if (!Object.hasOwn(overrides, "decision_proof")) value.decision_proof = decisionProof(value);
  return value;
}

function payload(rows = [], overrides = {}) {
  return {
    slate_date: "2026-07-21", generated_at: "2026-07-21T20:10:00Z", status: "ready",
    bundle_id: BUNDLE_ID, selector_fingerprint: SELECTOR_FINGERPRINT,
    counts: { provisional: 99, frozen: 99, selected: 99, pending: 99 }, rows,
    ...overrides,
  };
}

function manualScheduler() {
  const tasks = [];
  return {
    tasks,
    schedule(fn, delay) {
      const task = { fn, delay, cancelled: false };
      tasks.push(task);
      return task;
    },
    cancelSchedule(task) {
      if (task) task.cancelled = true;
    },
  };
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

async function flushAsyncWork() {
  await new Promise((resolve) => setImmediate(resolve));
}

test("fetchCurrentSlate uses the neutral same-origin v2 comparison route", async () => {
  const { api, calls } = load({ payload: payload() });
  await api.fetchCurrentSlate();
  assert.deepEqual(calls, ["/api/slate-comparison?bundle_version=v2"]);
});

test("polling fetches immediately and schedules a 60-second non-overlapping refresh", async () => {
  const { api } = load();
  const scheduler = manualScheduler();
  const first = deferred();
  const second = deferred();
  const updates = [];
  let calls = 0;
  const fetcher = () => {
    calls += 1;
    return calls === 1 ? first.promise : second.promise;
  };
  const ready = api.normalizeResponse(payload([row()]));

  const stop = api.startCurrentSlatePolling({
    fetcher,
    onUpdate: (state) => updates.push(state),
    schedule: scheduler.schedule,
    cancelSchedule: scheduler.cancelSchedule,
  });

  assert.equal(calls, 1);
  assert.equal(scheduler.tasks.length, 0);
  first.resolve(ready);
  await flushAsyncWork();
  assert.equal(updates.length, 1);
  assert.equal(updates[0].refresh_status, "current");
  assert.equal(scheduler.tasks.length, 1);
  assert.equal(scheduler.tasks[0].delay, 60000);

  const refresh = scheduler.tasks.shift().fn();
  assert.equal(calls, 2);
  assert.equal(scheduler.tasks.length, 0);
  second.resolve(ready);
  await refresh;
  assert.equal(updates.length, 2);
  assert.equal(scheduler.tasks.length, 1);
  stop();
});

test("polling retains the last valid state when a later read fails", async () => {
  const { api } = load();
  const scheduler = manualScheduler();
  const ready = api.normalizeResponse(payload([row({ pitcher: "Current Pitcher" })]));
  const failed = { status: "unavailable", rows: [], counts: {}, error: "fetch_failed" };
  const responses = [ready, failed];
  const updates = [];

  const stop = api.startCurrentSlatePolling({
    fetcher: async () => responses.shift(),
    onUpdate: (state) => updates.push(state),
    schedule: scheduler.schedule,
    cancelSchedule: scheduler.cancelSchedule,
  });
  await flushAsyncWork();
  await scheduler.tasks.shift().fn();

  assert.equal(updates.length, 2);
  assert.equal(updates[1].status, "ready");
  assert.equal(updates[1].rows[0].pitcher, "Current Pitcher");
  assert.equal(updates[1].refresh_status, "retrying");
  assert.equal(updates[1].refresh_error, "fetch_failed");
  stop();
});

test("polling replaces retained data with a valid empty current state", async () => {
  const { api } = load();
  const scheduler = manualScheduler();
  const responses = [
    api.normalizeResponse(payload([row({ pitcher: "Old Pitcher" })])),
    { status: "unavailable", rows: [], counts: {}, error: "fetch_failed" },
    api.normalizeResponse(payload([])),
  ];
  const updates = [];

  const stop = api.startCurrentSlatePolling({
    fetcher: async () => responses.shift(),
    onUpdate: (state) => updates.push(state),
    schedule: scheduler.schedule,
    cancelSchedule: scheduler.cancelSchedule,
  });
  await flushAsyncWork();
  await scheduler.tasks.shift().fn();
  await scheduler.tasks.shift().fn();

  assert.equal(updates.length, 3);
  assert.equal(updates[1].refresh_status, "retrying");
  assert.equal(updates[2].status, "ready");
  assert.equal(updates[2].rows.length, 0);
  assert.equal(updates[2].refresh_status, "current");
  assert.equal(updates[2].refresh_error, "");
  stop();
});

test("stopping polling clears a scheduled refresh and ignores a late response", async () => {
  const { api } = load();
  const scheduler = manualScheduler();
  const ready = api.normalizeResponse(payload([row()]));
  const updates = [];

  const firstStop = api.startCurrentSlatePolling({
    fetcher: async () => ready,
    onUpdate: (state) => updates.push(state),
    schedule: scheduler.schedule,
    cancelSchedule: scheduler.cancelSchedule,
  });
  await flushAsyncWork();
  assert.equal(scheduler.tasks.length, 1);
  firstStop();
  assert.equal(scheduler.tasks[0].cancelled, true);

  const late = deferred();
  const lateUpdates = [];
  const lateStop = api.startCurrentSlatePolling({
    fetcher: () => late.promise,
    onUpdate: (state) => lateUpdates.push(state),
    schedule: scheduler.schedule,
    cancelSchedule: scheduler.cancelSchedule,
  });
  lateStop();
  late.resolve(ready);
  await flushAsyncWork();
  assert.equal(lateUpdates.length, 0);
});

test("normalizeResponse requires the exact v2 bundle and fingerprint before accepting rows or counts", () => {
  const { api } = load();
  for (const response of [
    payload([row()], { bundle_id: undefined }),
    payload([row()], { bundle_id: "pregame_alternative_pick_methodology_v1" }),
    payload([row()], { selector_fingerprint: undefined }),
    payload([row()], { selector_fingerprint: "f".repeat(64) }),
  ]) {
    const normalized = api.normalizeResponse(response);
    assert.equal(normalized.status, "unavailable");
    assert.equal(normalized.rows.length, 0);
    assert.equal(Object.keys(normalized.counts).length, 0);
  }
});

test("normalizeResponse fails the whole response closed when any v2 row is invalid", () => {
  const { api } = load();
  const invalid = row();
  invalid.family_states = { base: { state: "agree" } };
  const normalized = api.normalizeResponse(payload([row(), invalid]));
  assert.equal(normalized.status, "unavailable");
  assert.equal(normalized.rows.length, 0);
  assert.equal(Object.keys(normalized.counts).length, 0);
});

test("normalizeResponse recomputes counts from accepted rows and ignores inconsistent server counts", () => {
  const { api } = load();
  const pending = row({
    pitcher: "Pending Pitcher", checkpoint: "provisional", lane: null, selector_id: null,
    selection_status: "pending", frozen_at: null, should_lock_at: null,
    minutes_until_start: null, lock_status: null,
    family_states: {
      base: { state: "agree", reason_codes: ["base_ok"] },
      anchor: { state: "disagree", reason_codes: ["anchor_false"] },
      preclose: { state: "pending", reason_codes: ["official_provider_immature"] },
      reentry: { state: "disagree", reason_codes: ["reentry_false"] },
    },
    family_count: 1,
  });
  const normalized = api.normalizeResponse(payload([row(), pending]));
  assert.equal(normalized.status, "ready");
  assert.deepEqual({ ...normalized.counts }, { provisional: 1, frozen: 1, selected: 1, pending: 1 });
});

test("selected v2 can retain zero Preclose observations only with a proven nonessential pending family", () => {
  const { api } = load();
  const accepted = api.normalizeResponse(payload([row()]));
  assert.equal(accepted.status, "ready");
  assert.equal(accepted.rows.length, 1);
  assert.equal(accepted.rows[0].family_count, 2);
  assert.equal(accepted.rows[0].family_states.preclose.state, "pending");
  assert.equal(accepted.rows[0].decision_proof.preclose_required_for_selected_lane, false);

  const badProofs = [
    { ...decisionProof(row()), preclose_required_for_selected_lane: true },
    { ...decisionProof(row()), lane_states: { consensus_core: "pending", reentry_expansion: "false" } },
    { ...decisionProof(row()), decisive_families: ["base"] },
  ];
  for (const proof of badProofs) {
    const rejected = api.normalizeResponse(payload([row({ decision_proof: proof })]));
    assert.equal(rejected.status, "unavailable");
    assert.equal(rejected.rows.length, 0);
  }
});

test("selected v2 accepts observed but still pending nonessential Preclose evidence", () => {
  const { api } = load();
  const accepted = api.normalizeResponse(payload([row({
    evidence_observation_count: 1,
    evidence_first_observed_at: "2026-07-21T19:50:00Z",
    evidence_last_observed_at: "2026-07-21T19:50:00Z",
  })]));

  assert.equal(accepted.status, "ready");
  assert.equal(accepted.rows.length, 1);
  assert.equal(accepted.rows[0].evidence_freshness_status, "pending");
  assert.equal(accepted.rows[0].evidence_observation_count, 1);
});

test("decision proof recomputes whether Preclose is required for the selected lane", () => {
  const { api } = load();
  const family_states = {
    base: { state: "agree", reason_codes: ["base_ok"] },
    anchor: { state: "disagree", reason_codes: ["anchor_false"] },
    preclose: { state: "agree", reason_codes: ["preclose_ok"] },
    reentry: { state: "disagree", reason_codes: ["reentry_false"] },
  };
  const candidate = row({
    family_states,
    family_count: 2,
    evidence_freshness_status: "fresh",
    evidence_observation_count: 2,
    evidence_first_observed_at: "2026-07-21T19:45:00Z",
    evidence_last_observed_at: "2026-07-21T19:55:00Z",
  });
  const requiredProof = {
    ...decisionProof(candidate),
    preclose_required_for_selected_lane: true,
  };
  const accepted = api.normalizeResponse(payload([{ ...candidate, decision_proof: requiredProof }]));
  assert.equal(accepted.status, "ready");

  const rejected = api.normalizeResponse(payload([{
    ...candidate,
    decision_proof: { ...requiredProof, preclose_required_for_selected_lane: false },
  }]));
  assert.equal(rejected.status, "unavailable");
  assert.equal(rejected.rows.length, 0);
});

test("normalizeResponse validates v2 row bundle selector lane status and family count as one contract", () => {
  const { api } = load();
  const cases = [
    row({ bundle_id: "pregame_alternative_pick_methodology_v1" }),
    row({ selector_id: "no_drag_distinct_family_consensus_core_v1" }),
    row({ lane: "not_a_lane" }),
    row({ family_count: 3 }),
    row({ selection_status: "not_selected" }),
  ];
  for (const candidate of cases) {
    const normalized = api.normalizeResponse(payload([candidate]));
    assert.equal(normalized.status, "unavailable");
  }
});

test("normalized supporting rows distinguish healthy no qualifiers from waiting for rows", () => {
  const { api } = load();
  const notSelected = row({
    lane: null, selector_id: null, selection_status: "not_selected", family_count: 0,
    family_states: {
      base: { state: "disagree", reason_codes: ["base_false"] },
      anchor: { state: "disagree", reason_codes: ["anchor_false"] },
      preclose: { state: "pending", reason_codes: ["official_provider_immature"] },
      reentry: { state: "disagree", reason_codes: ["reentry_false"] },
    },
  });
  const healthy = api.normalizeResponse(payload([notSelected]));
  const waiting = api.normalizeResponse(payload([]));
  assert.equal(healthy.rows.length, 1);
  assert.equal(healthy.rows[0].selection_status, "not_selected");
  assert.equal(waiting.rows.length, 0);
});

test("zero exact observations do not invalidate a dependency-short-circuited supporting row", () => {
  const { api } = load();
  const candidate = row({
    lane: null, selector_id: null, selection_status: "not_selected", family_count: 0,
    family_states: {
      base: { state: "disagree", reason_codes: ["base_false"] },
      anchor: { state: "disagree", reason_codes: ["anchor_false"] },
      preclose: { state: "disagree", reason_codes: ["base_short_circuit"] },
      reentry: { state: "disagree", reason_codes: ["reentry_false"] },
    },
  });
  const normalized = api.normalizeResponse(payload([candidate]));
  assert.equal(normalized.status, "ready");
  assert.equal(normalized.rows.length, 1);
  assert.equal(normalized.rows[0].selection_status, "not_selected");
});

test("formatFreezeLabel uses actual checkpoint capture values", () => {
  const { api } = load();
  assert.equal(api.formatFreezeLabel(row({ checkpoint: "provisional", frozen_at: null, minutes_until_start: null })), "Provisional");
  assert.equal(api.formatFreezeLabel(row({ minutes_until_start: 28, lock_status: "due_now" })), "Frozen T-28");
  assert.equal(api.formatFreezeLabel(row({ minutes_until_start: 21, lock_status: "missed_lock" })), "Frozen T-21 (late)");
});

test("frozen rows require real ISO capture timestamps and known lock states", () => {
  const { api } = load();
  for (const candidate of [row({ frozen_at: "not-a-timestamp" }), row({ lock_status: "unknown_lock_state" })]) {
    const normalized = api.normalizeResponse(payload([candidate]));
    assert.equal(normalized.status, "unavailable");
  }
  assert.equal(api.formatFreezeLabel(row({ frozen_at: "not-a-timestamp", lock_status: "unknown_lock_state" })), "Provisional");
});

test("normalizeResponse fails the whole v2 response closed when a row uses PASS", () => {
  const { api } = load();
  const normalized = api.normalizeResponse(payload([row({ official_verdict: "PASS" })]));
  assert.equal(normalized.status, "unavailable");
  assert.equal(normalized.rows.length, 0);
});

test("normalizeResponse neither requires nor copies raw top-level reason codes", () => {
  const { api } = load();
  const withoutReasons = row();
  delete withoutReasons.reason_codes;
  const acceptedWithoutReasons = api.normalizeResponse(payload([withoutReasons]));
  assert.equal(acceptedWithoutReasons.status, "ready");
  assert.equal(Object.hasOwn(acceptedWithoutReasons.rows[0], "reason_codes"), false);

  const malicious = row({ reason_codes: ["internal_database_probe"] });
  const acceptedMalicious = api.normalizeResponse(payload([malicious]));
  assert.equal(acceptedMalicious.status, "ready");
  assert.equal(Object.hasOwn(acceptedMalicious.rows[0], "reason_codes"), false);
  assert.equal(JSON.stringify(acceptedMalicious).includes("internal_database_probe"), false);
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
