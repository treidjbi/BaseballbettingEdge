import test from "node:test";
import assert from "node:assert/strict";
import {
  buildPickedSideMovement,
  summarizeLineMovement,
  parkFactorTone,
} from "./v2-movement-helpers.js";

const steam = {
  snapshots: [
    {
      t: "2026-04-28T00:00:00Z",
      pitchers: {
        "Shohei Ohtani": {
          k_line: 6.5,
          FanDuel: { over: -110, under: -118 },
        },
      },
    },
    {
      t: "2026-04-28T03:00:00Z",
      pitchers: {
        "Shohei Ohtani": {
          k_line: 7.5,
          FanDuel: { over: +102, under: -122 },
        },
      },
    },
  ],
};

test("buildPickedSideMovement returns FanDuel picked-side odds and k-line points", () => {
  const result = buildPickedSideMovement(steam, {
    pitcher: "Shohei Ohtani",
    direction: "OVER",
  });

  assert.equal(result.book, "FanDuel");
  assert.equal(result.direction, "OVER");
  assert.deepEqual(
    result.points.map((point) => ({ odds: point.odds, kLine: point.kLine })),
    [
      { odds: -110, kLine: 6.5 },
      { odds: 102, kLine: 7.5 },
    ],
  );
});

test("buildPickedSideMovement returns empty state when there are fewer than two usable points", () => {
  const result = buildPickedSideMovement(
    { snapshots: [steam.snapshots[0]] },
    { pitcher: "Shohei Ohtani", direction: "OVER" },
  );

  assert.equal(result.ready, false);
  assert.equal(result.reason, "insufficient_history");
});

test("summarizeLineMovement reports line change when k-line moved", () => {
  const movement = buildPickedSideMovement(steam, {
    pitcher: "Shohei Ohtani",
    direction: "OVER",
  });

  assert.deepEqual(summarizeLineMovement(movement), {
    lineMoved: true,
    openingLine: 6.5,
    currentLine: 7.5,
    openingOdds: -110,
    currentOdds: 102,
  });
});

test("parkFactorTone marks OVER-friendly parks as positive for OVER picks", () => {
  assert.equal(parkFactorTone(1.08, "OVER"), "pos");
  assert.equal(parkFactorTone(1.08, "UNDER"), "neg");
  assert.equal(parkFactorTone(0.94, "UNDER"), "pos");
});
