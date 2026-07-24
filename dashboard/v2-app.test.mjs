import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import vm from "node:vm";

const scriptPath = path.resolve("dashboard/v2-app.js");
const scriptSource = await fs.readFile(scriptPath, "utf8");

function loadTicketContextHelper() {
  const footerStart = scriptSource.indexOf("const root = ReactDOM.createRoot");
  assert.notEqual(footerStart, -1, "dashboard app root footer is present");
  const context = {
    React: {
      createElement: () => null,
      Fragment: Symbol("Fragment"),
      useEffect: () => {},
      useMemo: (fn) => fn(),
      useState: () => [null, () => {}],
    },
    window: { V2_MARKET_DISPLAY: { enabled: true } },
    console,
  };
  context.globalThis = context;
  vm.runInNewContext(
    `${scriptSource.slice(0, footerStart)}\nglobalThis.__ticketContext = marketBetTicketContext;`,
    context,
    { filename: scriptPath },
  );
  return context.__ticketContext;
}

function loadTicketHelpers() {
  const footerStart = scriptSource.indexOf("const root = ReactDOM.createRoot");
  assert.notEqual(footerStart, -1, "dashboard app root footer is present");
  const context = {
    React: {
      createElement: () => null,
      Fragment: Symbol("Fragment"),
      useEffect: () => {},
      useMemo: (fn) => fn(),
      useState: () => [null, () => {}],
    },
    window: { V2_MARKET_DISPLAY: { enabled: true }, V2_DATA: { date: "2026-07-17" } },
    console,
  };
  context.globalThis = context;
  vm.runInNewContext(
    `${scriptSource.slice(0, footerStart)}\nglobalThis.__ticketHelpers = { marketBetTicketContext, isLiveMarketBetPrefill, selectedMarketBetRowForForm: typeof selectedMarketBetRowForForm === "function" ? selectedMarketBetRowForForm : null, buildAcceptedBetPayload, altCountLabel: typeof altCountLabel === "function" ? altCountLabel : null, altCandidateStatusCopy: typeof altCandidateStatusCopy === "function" ? altCandidateStatusCopy : null, altZeroSelectedCopy: typeof altZeroSelectedCopy === "function" ? altZeroSelectedCopy : null, altBookTitle: typeof altBookTitle === "function" ? altBookTitle : null, altSelectionProofCopy: typeof altSelectionProofCopy === "function" ? altSelectionProofCopy : null };`,
    context,
    { filename: scriptPath },
  );
  return context.__ticketHelpers;
}

test("different-line display rows retain manual book choices without live prefill", () => {
  const marketBetTicketContext = loadTicketContextHelper();
  const side = { direction: "OVER", k_line: 6.5, win_prob: 0.55 };
  const pick = {
    best_over_book: "DraftKings",
    market_display: {
      OVER: {
        best_book: "FanDuel",
        best_line: 7.5,
        best_odds: -110,
        freshness_status: "fresh",
        action_label: "playable",
        book_rows: [
          { bookmaker_title: "FanDuel", line: 7.5, odds: -110 },
          { bookmaker_title: "DraftKings", line: 6.5, odds: -105 },
        ],
      },
    },
  };

  const ticketContext = marketBetTicketContext(pick, side);

  assert.equal(ticketContext.prefillRow, null);
  assert.equal(ticketContext.bookRows.length, 2);
  const bookRows = Object.fromEntries(ticketContext.bookRows.map((row) => [row.bookName, [row.line, row.sameLine]]));
  assert.deepEqual(bookRows, {
    DraftKings: [6.5, true],
    FanDuel: [7.5, false],
  });
});

test("live ticket prefill accepts only explicit fresh statuses", () => {
  const { isLiveMarketBetPrefill } = loadTicketHelpers();
  const side = { direction: "OVER", k_line: 6.5, win_prob: 0.55 };
  const baseRow = {
    best_book: "FanDuel",
    best_line: 6.5,
    best_odds: -110,
    action_label: "playable",
  };

  for (const freshness_status of ["fresh", "held_fresh", "heartbeat_held"]) {
    assert.equal(isLiveMarketBetPrefill({ ...baseRow, freshness_status }, side), true, freshness_status);
  }
  for (const freshness_status of [undefined, "", "unknown", "stale"]) {
    assert.equal(isLiveMarketBetPrefill({ ...baseRow, freshness_status }, side), false, String(freshness_status));
  }
});

test("manual alternate book selection retains live provenance without automatic prefill", () => {
  const { marketBetTicketContext, selectedMarketBetRowForForm, buildAcceptedBetPayload } = loadTicketHelpers();
  assert.equal(typeof selectedMarketBetRowForForm, "function");
  assert.match(scriptSource, /const liveBetSourceText = selectedMarketBetRow/);
  assert.match(scriptSource, /marketRow: selectedMarketBetRow/);
  const side = { direction: "OVER", k_line: 6.5, verdict: "FIRE 1u", win_prob: 0.55 };
  const pick = {
    pitcher: "Tarik Skubal",
    game_time: "2026-07-17T23:10:00Z",
    market_display: {
      OVER: {
        provider: "therundown_propline",
        observed_at: "2026-07-17T18:00:00Z",
        action_label: "alt_line_context",
        best_book: "FanDuel",
        best_line: 7.5,
        best_odds: -110,
        freshness_status: "fresh",
        book_rows: [
          { bookmaker_title: "FanDuel", line: 7.5, odds: -110 },
          { bookmaker_title: "DraftKings", line: 6.5, odds: -105 },
        ],
      },
    },
  };
  const ticketContext = marketBetTicketContext(pick, side);
  assert.equal(ticketContext.prefillRow, null);
  const selected = selectedMarketBetRowForForm({
    prefillRow: ticketContext.prefillRow,
    displayRow: ticketContext.displayRow,
    bookRows: ticketContext.bookRows,
    form: { priceSource: "live_best", book: "DraftKings", bookOther: "", line: "6.5", odds: "-105" },
  });
  assert.equal(selected.best_book, "DraftKings");
  assert.equal(selected.best_line, 6.5);
  assert.equal(selected.best_odds, -105);
  assert.equal(selected.provider, "therundown_propline");
  const payload = buildAcceptedBetPayload(pick, side, {
    line: 6.5,
    odds: -105,
    book: "DraftKings",
    units: 1,
    priceSource: "live_best",
    marketRow: selected,
  });
  assert.equal(payload.metadata.selected_live_provider, "therundown_propline");
  assert.equal(payload.metadata.selected_live_observed_at, "2026-07-17T18:00:00Z");
});

test("Alt Picks labels singular counts and canonical endpoint book keys", () => {
  const { altCountLabel, altCandidateStatusCopy, altBookTitle } = loadTicketHelpers();
  assert.equal(typeof altCountLabel, "function");
  assert.equal(altCountLabel(1, "candidate"), "1 candidate");
  assert.equal(altCountLabel(2, "candidate"), "2 candidates");
  assert.equal(altCountLabel(1, "observation"), "1 observation");
  assert.equal(altCountLabel(3, "observation"), "3 observations");
  assert.equal(typeof altCandidateStatusCopy, "function");
  assert.equal(altCandidateStatusCopy(1), "1 candidate remains not selected or pending");
  assert.equal(altCandidateStatusCopy(2), "2 candidates remain not selected or pending");
  assert.equal(typeof altBookTitle, "function");
  assert.deepEqual(
    ["fanduel", "draftkings", "betmgm", "betrivers", "kalshi", "caesars", "thescore", "thescore_bet"].map(altBookTitle),
    ["FanDuel", "DraftKings", "BetMGM", "BetRivers", "Kalshi", "Caesars", "theScore Bet", "theScore Bet"],
  );
});

test("Alt Picks zero-selected copy distinguishes completed no-qualifier rows from pending evaluations", () => {
  const { altZeroSelectedCopy } = loadTicketHelpers();
  assert.equal(typeof altZeroSelectedCopy, "function");

  const allNotSelected = altZeroSelectedCopy([
    { selection_status: "not_selected" },
    { selection_status: "not_selected" },
  ]);
  const pendingOnly = altZeroSelectedCopy([
    { selection_status: "pending" },
    { selection_status: "pending" },
  ]);
  const mixed = altZeroSelectedCopy([
    { selection_status: "not_selected" },
    { selection_status: "pending" },
  ]);

  assert.match(allNotSelected.title, /No alternative qualifiers/);
  assert.match(allNotSelected.sub, /Evidence is healthy/);
  for (const copy of [pendingOnly, mixed]) {
    assert.equal(copy.title, "Alternative evaluation still pending.");
    assert.doesNotMatch(copy.sub, /Evidence is healthy/);
  }
  assert.match(pendingOnly.sub, /2 candidates are awaiting complete family evidence/);
  assert.match(mixed.sub, /1 candidate is awaiting complete family evidence/);
});

test("Alt Picks selected proof copy distinguishes confirmed families from pending Preclose", () => {
  const { altSelectionProofCopy } = loadTicketHelpers();
  assert.equal(typeof altSelectionProofCopy, "function");
  const family_states = {
    base: { state: "agree" }, anchor: { state: "agree" },
    preclose: { state: "pending" }, reentry: { state: "disagree" },
  };
  assert.equal(
    altSelectionProofCopy({ selection_status: "selected", family_count: 2, family_states }),
    "Selected with 2 confirmed families; Preclose still pending.",
  );
  assert.equal(
    altSelectionProofCopy({
      selection_status: "selected", family_count: 3,
      family_states: { ...family_states, preclose: { state: "agree" } },
    }),
    "Selected with 3 confirmed families.",
  );
});
