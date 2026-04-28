import test from "node:test";
import assert from "node:assert/strict";
import { buildFactorGroups } from "./v2-factor-details.js";

test("buildFactorGroups returns the expected group ids and row shape", () => {
  const groups = buildFactorGroups(
    {
      k_line: 7.5,
      lambda: 8.1,
      raw_ev_roi: 0.041,
      adj_ev_roi: 0.032,
      avg_ip: 5.8,
      opp_k_rate: 0.241,
      recent_k9: 9.4,
      season_k9: 8.7,
      career_k9: 8.4,
      swstr_pct: 0.132,
      swstr_delta_k9: 0.3,
      umpire: "Angel Hernandez",
      ump_k_adj: 0.12,
      park_factor: 1.08,
      rest_k9_delta: -0.4,
      days_since_last_start: 5,
      last_pitch_count: 88,
      lineup_used: true,
      data_complete: true,
    },
    "OVER",
  );

  assert.deepEqual(
    groups.map((group) => group.key),
    [
      "projection-core",
      "opponent-context",
      "pitcher-form",
      "environment",
      "workload-rest",
      "data-health",
    ],
  );

  const projection = groups.find((group) => group.key === "projection-core");
  const environment = groups.find((group) => group.key === "environment");
  const dataHealth = groups.find((group) => group.key === "data-health");

  assert.ok(projection);
  assert.ok(environment);
  assert.ok(dataHealth);

  assert.deepEqual(
    projection.rows.map((row) => row.key),
    ["line", "lambda", "raw_ev_roi", "adjusted_ev_roi", "edge", "expected_ip"],
  );
  assert.deepEqual(
    environment.rows.map((row) => row.key),
    ["park_factor", "ump", "lineup"],
  );
  assert.deepEqual(
    dataHealth.rows.map((row) => row.key),
    ["data_complete"],
  );

  const allKeys = groups.flatMap((group) => group.rows.map((row) => row.key));
  assert.equal(new Set(allKeys).size, allKeys.length);

  for (const group of groups) {
    assert.equal(typeof group.label, "string");
    assert.ok(Array.isArray(group.rows));
    assert.ok(group.rows.length > 0);

    for (const row of group.rows) {
      assert.equal(typeof row.label, "string");
      assert.equal(typeof row.value, "string");
      assert.ok("rawValue" in row);
      assert.ok(["active", "neutral", "missing"].includes(row.status));
    }
  }
});

test("buildFactorGroups derives row status for missing, neutral, and active values", () => {
  const groups = buildFactorGroups(
    {
      lineup_used: false,
      umpire: null,
      ump_k_adj: 0,
      park_factor: 1.00,
      swstr_delta_k9: null,
      rest_k9_delta: 0,
      data_complete: false,
    },
    "UNDER",
  );

  const environment = groups.find((group) => group.key === "environment");
  const pitcherForm = groups.find((group) => group.key === "pitcher-form");
  const workloadRest = groups.find((group) => group.key === "workload-rest");
  const dataHealth = groups.find((group) => group.key === "data-health");

  assert.ok(environment);
  assert.ok(pitcherForm);
  assert.ok(workloadRest);
  assert.ok(dataHealth);

  const envLookup = new Map(environment.rows.map((row) => [row.key, row]));
  const pitcherFormLookup = new Map(pitcherForm.rows.map((row) => [row.key, row]));
  const workloadRestLookup = new Map(workloadRest.rows.map((row) => [row.key, row]));
  const dataHealthLookup = new Map(dataHealth.rows.map((row) => [row.key, row]));

  assert.equal(envLookup.get("lineup").status, "missing");
  assert.equal(envLookup.get("ump").status, "missing");
  assert.equal(envLookup.get("park_factor").status, "neutral");
  assert.equal(pitcherFormLookup.get("swstr_delta_k9").status, "missing");
  assert.equal(workloadRestLookup.get("rest_k9_delta").status, "neutral");
  assert.equal(dataHealthLookup.get("data_complete").status, "missing");
});

test("buildFactorGroups includes raw and adjusted EV ROI plus SwStr % coverage", () => {
  const groups = buildFactorGroups(
    {
      ev_over: { ev: -0.041, adj_ev: -0.029, edge: -0.014 },
      ev_under: { ev: 0.031, adj_ev: 0.018, edge: 0.009 },
      raw_ev_roi: 0.777,
      adj_ev_roi: 0.666,
      swstr_pct: 0.132,
    },
    "UNDER",
  );

  const lookup = new Map();
  for (const group of groups) {
    for (const row of group.rows) {
      lookup.set(row.key, row);
    }
  }

  assert.equal(lookup.get("raw_ev_roi").value, "+3.1%");
  assert.equal(lookup.get("adjusted_ev_roi").value, "+1.8%");
  assert.equal(lookup.get("edge").value, "+0.9%");
  assert.equal(lookup.get("raw_ev_roi").tone, "pos");
  assert.equal(lookup.get("adjusted_ev_roi").tone, "pos");
  assert.equal(lookup.get("edge").tone, "pos");
  assert.equal(lookup.get("swstr_pct").value, "13.2%");
});

test("buildFactorGroups marks no-name umpire context active when adjustment is nonzero", () => {
  const groups = buildFactorGroups(
    {
      ev_over: { ev: 0.02, adj_ev: 0.03 },
      ev_under: { ev: -0.01, adj_ev: -0.02 },
      umpire: null,
      ump_k_adj: 0.12,
    },
    "OVER",
  );

  const environment = groups.find((group) => group.key === "environment");
  assert.ok(environment);

  const ump = environment.rows.find((row) => row.key === "ump");
  assert.ok(ump);
  assert.equal(ump.status, "active");
  assert.match(ump.value, /Assigned/i);
  assert.match(ump.value, /\+0\.12/);
});
