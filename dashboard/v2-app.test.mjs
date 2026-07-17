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
