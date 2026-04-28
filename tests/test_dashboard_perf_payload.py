import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_BUNDLE = ROOT / "dashboard" / "v2-app.js"


def _run_perf_tab(perf_payload):
    script = """
const fs = require("fs");
const vm = require("vm");

const bundlePath = process.argv[1];
const perfPayload = JSON.parse(process.argv[2]);
let source = fs.readFileSync(bundlePath, "utf8");
source = source.replace(
  'const root = ReactDOM.createRoot(document.getElementById("root"));',
  'globalThis.__PerfTab = PerfTab;\\n'
    + 'const root = ReactDOM.createRoot(document.getElementById("root"));'
);

function collectText(node, out = []) {
  if (node == null || node === false) return out;
  if (Array.isArray(node)) {
    for (const child of node) collectText(child, out);
    return out;
  }
  if (typeof node === "string" || typeof node === "number") {
    out.push(String(node));
    return out;
  }
  if (node.children) collectText(node.children, out);
  return out;
}

const React = {
  Fragment: Symbol("Fragment"),
  createElement(type, props, ...children) {
    return { type, props: props || {}, children };
  },
  useState(initial) {
    return [typeof initial === "function" ? initial() : initial, () => {}];
  },
  useMemo(factory) {
    return factory();
  },
  useRef(initial) {
    return { current: initial };
  },
  useEffect() {},
};

const context = {
  console,
  Math,
  Date,
  Promise,
  setTimeout() { return 0; },
  clearTimeout() {},
  fetch: async () => ({ json: async () => ({}) }),
  atob: (value) => Buffer.from(value, "base64").toString("binary"),
  React,
  ReactDOM: {
    createRoot: () => ({ render() {} }),
    createPortal: (node) => node,
  },
  window: {
    V2_PERF: perfPayload,
    __v2DataPromise: Promise.resolve(),
  },
  document: {
    getElementById: () => ({}),
    body: { setAttribute() {} },
  },
  location: { search: "" },
  localStorage: {
    getItem: () => null,
    setItem() {},
  },
  navigator: {},
  Notification: {
    permission: "granted",
    requestPermission: async () => "granted",
  },
};
context.globalThis = context;

vm.runInNewContext(source, context);
const tree = context.__PerfTab();
const text = collectText(tree).join(" ");
console.log(JSON.stringify({ text }));
"""

    result = subprocess.run(
        ["node", "-e", script, str(DASHBOARD_BUNDLE), json.dumps(perf_payload)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result


def test_perf_tab_handles_zero_pick_rows_with_null_metrics():
    perf_payload = {
        "total_picks": 0,
        "total_units": 0,
        "total_roi": 0,
        "record": "0-0-0",
        "best_tier": None,
        "win_rate": 0,
        "last_calibrated": None,
        "calibration_notes": [],
        "rows": [
            {
                "verdict": verdict,
                "side": side,
                "picks": 0,
                "wins": 0,
                "losses": 0,
                "pushes": 0,
                "win_pct": None,
                "roi": None,
                "avg_ev": None,
            }
            for verdict, side in [
                ("FIRE 2u", "over"),
                ("FIRE 2u", "under"),
                ("FIRE 1u", "over"),
                ("FIRE 1u", "under"),
                ("LEAN", "over"),
                ("LEAN", "under"),
            ]
        ],
    }

    result = _run_perf_tab(perf_payload)

    assert result.returncode == 0, result.stderr
    rendered = json.loads(result.stdout)
    assert "NaN" not in rendered["text"]
    assert "undefined" not in rendered["text"]
    assert "null" not in rendered["text"]
