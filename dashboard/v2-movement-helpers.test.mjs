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

test("buildPickedSideMovement uses the selected book when it is available", () => {
  const result = buildPickedSideMovement(
    {
      snapshots: [
        {
          t: "2026-04-28T00:00:00Z",
          pitchers: {
            "Luis Castillo": {
              k_line: 5.5,
              BetMGM: { over: -104, under: -118 },
            },
          },
        },
        {
          t: "2026-04-28T03:00:00Z",
          pitchers: {
            "Luis Castillo": {
              k_line: 5.5,
              BetMGM: { over: -112, under: +102 },
            },
          },
        },
      ],
    },
    {
      pitcher: "Luis Castillo",
      direction: "UNDER",
      selectedBook: "BetMGM",
    },
  );

  assert.equal(result.ready, true);
  assert.equal(result.book, "BetMGM");
  assert.deepEqual(
    result.points.map((point) => ({ odds: point.odds, kLine: point.kLine })),
    [
      { odds: -118, kLine: 5.5 },
      { odds: 102, kLine: 5.5 },
    ],
  );
});

test("buildPickedSideMovement prepends the opening point when preview/open differs from snapshots", () => {
  const movement = buildPickedSideMovement(
    {
      snapshots: [
        {
          t: "2026-04-28T16:49:10Z",
          pitchers: {
            "Shane Baz": {
              k_line: 4.5,
              FanDuel: { over: -144, under: 108 },
            },
          },
        },
      ],
    },
    {
      pitcher: "Shane Baz",
      direction: "UNDER",
      openingLine: 4.5,
      openingOdds: 104,
    },
  );

  assert.equal(movement.ready, true);
  assert.equal(movement.points.length, 2);
  assert.equal(movement.points[0].t, "open");
  assert.equal(movement.points[0].odds, 104);
  assert.equal(movement.points[1].odds, 108);
});

test("buildPickedSideMovement returns empty state when there are fewer than two usable points", () => {
  const result = buildPickedSideMovement(
    { snapshots: [steam.snapshots[0]] },
    { pitcher: "Shohei Ohtani", direction: "OVER" },
  );

  assert.equal(result.ready, false);
  assert.equal(result.reason, "insufficient_history");
});

test("buildPickedSideMovement labels empty history with selected book when provided", () => {
  const result = buildPickedSideMovement(
    { snapshots: [] },
    { pitcher: "Freddy Peralta", direction: "OVER", selectedBook: "BetMGM" },
  );

  assert.equal(result.ready, false);
  assert.equal(result.book, "BetMGM");
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
