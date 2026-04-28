const {
  useState,
  useMemo
} = React;
const ABBR = {
  "Arizona Diamondbacks": "ARI",
  "Atlanta Braves": "ATL",
  "Baltimore Orioles": "BAL",
  "Boston Red Sox": "BOS",
  "Chicago Cubs": "CHC",
  "Chicago White Sox": "CWS",
  "Cincinnati Reds": "CIN",
  "Cleveland Guardians": "CLE",
  "Colorado Rockies": "COL",
  "Detroit Tigers": "DET",
  "Houston Astros": "HOU",
  "Kansas City Royals": "KC",
  "Los Angeles Angels": "LAA",
  "Los Angeles Dodgers": "LAD",
  "Miami Marlins": "MIA",
  "Milwaukee Brewers": "MIL",
  "Minnesota Twins": "MIN",
  "New York Mets": "NYM",
  "New York Yankees": "NYY",
  "Oakland Athletics": "OAK",
  "Philadelphia Phillies": "PHI",
  "Pittsburgh Pirates": "PIT",
  "San Diego Padres": "SD",
  "San Francisco Giants": "SF",
  "Seattle Mariners": "SEA",
  "St. Louis Cardinals": "STL",
  "Tampa Bay Rays": "TB",
  "Texas Rangers": "TEX",
  "Toronto Blue Jays": "TOR",
  "Washington Nationals": "WSH",
  "Athletics": "OAK"
};
const ab = n => ABBR[n] || n;
const fmtOdds = n => n == null ? "—" : n > 0 ? `+${n}` : `${n}`;
const isFiniteNumber = v => typeof v === "number" && Number.isFinite(v);
const fmtFixedOrDash = (v, digits = 1) => isFiniteNumber(v) ? v.toFixed(digits) : "--";
const PHX_TZ = "America/Phoenix";
const phxDateISO = () => new Intl.DateTimeFormat("en-CA", {
  timeZone: PHX_TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit"
}).format(new Date());
const fmtTime = iso => {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: PHX_TZ
  });
};
const Icon = {
  users: React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "13",
    height: "13",
    fill: "currentColor",
    "aria-hidden": "true"
  }, React.createElement("circle", {
    cx: "5",
    cy: "5.5",
    r: "2.3"
  }), React.createElement("circle", {
    cx: "11",
    cy: "5.5",
    r: "2"
  }), React.createElement("path", {
    d: "M1 13.5c0-2.2 1.8-3.8 4-3.8s4 1.6 4 3.8v.5H1v-.5z"
  }), React.createElement("path", {
    d: "M9.2 14c.1-.3.1-.6.1-1 0-1.4-.7-2.6-1.7-3.3.4-.1.8-.2 1.3-.2 2 0 3.5 1.4 3.5 3.3V14H9.2z"
  })),
  ball: React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "13",
    height: "13",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.4",
    "aria-hidden": "true"
  }, React.createElement("circle", {
    cx: "8",
    cy: "8",
    r: "6.2"
  }), React.createElement("path", {
    d: "M3.5 4.5c1.3 1.4 2.1 3.2 2.1 5.3 0 1-.2 2-.5 2.9M12.5 4.5c-1.3 1.4-2.1 3.2-2.1 5.3 0 1 .2 2 .5 2.9"
  })),
  ump: React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "13",
    height: "13",
    fill: "currentColor",
    "aria-hidden": "true"
  }, React.createElement("circle", {
    cx: "8",
    cy: "5",
    r: "2.4"
  }), React.createElement("path", {
    d: "M3 14c0-2.4 2.2-4.3 5-4.3s5 1.9 5 4.3v.5H3V14z"
  })),
  up: React.createElement("svg", {
    viewBox: "0 0 10 10",
    width: "10",
    height: "10",
    fill: "currentColor",
    "aria-hidden": "true"
  }, React.createElement("path", {
    d: "M5 1.5L9 8H1z"
  })),
  down: React.createElement("svg", {
    viewBox: "0 0 10 10",
    width: "10",
    height: "10",
    fill: "currentColor",
    "aria-hidden": "true"
  }, React.createElement("path", {
    d: "M5 8.5L1 2h8z"
  })),
  live: React.createElement("svg", {
    viewBox: "0 0 8 8",
    width: "8",
    height: "8",
    fill: "currentColor",
    "aria-hidden": "true"
  }, React.createElement("circle", {
    cx: "4",
    cy: "4",
    r: "4"
  })),
  bell: React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "15",
    height: "15",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, React.createElement("path", {
    d: "M3.5 12h9l-1.2-1.6V7.2a3.3 3.3 0 0 0-2.6-3.3v-.4a.7.7 0 0 0-1.4 0v.4A3.3 3.3 0 0 0 4.7 7.2v3.2z"
  }), React.createElement("path", {
    d: "M6.5 13.5a1.5 1.5 0 0 0 3 0"
  })),
  bellOn: React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "15",
    height: "15",
    fill: "currentColor",
    stroke: "none"
  }, React.createElement("path", {
    d: "M8 1.5a.7.7 0 0 0-.7.7v.4a3.3 3.3 0 0 0-2.6 3.3v3.2L3.5 10.4V12h9v-1.6l-1.2-1.6V7.2a3.3 3.3 0 0 0-2.6-3.3v-.4A.7.7 0 0 0 8 1.5z"
  }), React.createElement("path", {
    d: "M6.5 13.5a1.5 1.5 0 0 0 3 0z"
  }), React.createElement("line", {
    x1: "1",
    y1: "2",
    x2: "3",
    y2: "4",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round"
  }), React.createElement("line", {
    x1: "15",
    y1: "2",
    x2: "13",
    y2: "4",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round"
  }), React.createElement("line", {
    x1: "8",
    y1: "0",
    x2: "8",
    y2: "1.5",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round"
  })),
  moon: React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "15",
    height: "15",
    fill: "currentColor"
  }, React.createElement("path", {
    d: "M8 1.5A6.5 6.5 0 1 0 14.5 8 5 5 0 0 1 8 1.5z"
  })),
  sun: React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "15",
    height: "15",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round"
  }, React.createElement("circle", {
    cx: "8",
    cy: "8",
    r: "2.8",
    fill: "currentColor"
  }), React.createElement("path", {
    d: "M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3 3l1 1M12 12l1 1M13 3l-1 1M4 12l-1 1"
  })),
  refresh: React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "14",
    height: "14",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, React.createElement("path", {
    d: "M14 3v4h-4"
  }), React.createElement("path", {
    d: "M13.5 7A6 6 0 1 0 14 10"
  })),
  picks: React.createElement("svg", {
    viewBox: "0 0 20 20",
    width: "20",
    height: "20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.6"
  }, React.createElement("circle", {
    cx: "10",
    cy: "10",
    r: "7.5"
  }), React.createElement("path", {
    d: "M4.5 5.8c1.6 1.7 2.6 4 2.6 6.6 0 1.2-.2 2.4-.6 3.5M15.5 5.8c-1.6 1.7-2.6 4-2.6 6.6 0 1.2.2 2.4.6 3.5"
  })),
  steam: React.createElement("svg", {
    viewBox: "0 0 20 20",
    width: "20",
    height: "20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.6",
    strokeLinecap: "round"
  }, React.createElement("path", {
    d: "M5 14l4-4 3 3 4-5"
  }), React.createElement("path", {
    d: "M13 8h3v3"
  })),
  results: React.createElement("svg", {
    viewBox: "0 0 20 20",
    width: "20",
    height: "20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.6",
    strokeLinecap: "round"
  }, React.createElement("rect", {
    x: "3.5",
    y: "9",
    width: "3.5",
    height: "7.5",
    rx: ".6"
  }), React.createElement("rect", {
    x: "8.5",
    y: "5",
    width: "3.5",
    height: "11.5",
    rx: ".6"
  }), React.createElement("rect", {
    x: "13.5",
    y: "11",
    width: "3.5",
    height: "5.5",
    rx: ".6"
  }))
};
function urlBase64ToUint8Array(b64) {
  const padding = '='.repeat((4 - b64.length % 4) % 4);
  const base64 = (b64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}
function usePipelineTrigger() {
  const [state, setState] = useState("idle");
  async function trigger() {
    if (state === "running") return;
    setState("running");
    try {
      const res = await fetch("/.netlify/functions/trigger-pipeline", {
        method: "POST"
      });
      const data = await res.json();
      if (data.status === "triggered") {
        setState("triggered");
        setTimeout(() => setState("idle"), 3 * 60 * 1000);
      } else {
        setState("error");
        setTimeout(() => setState("idle"), 5000);
      }
    } catch {
      setState("error");
      setTimeout(() => setState("idle"), 5000);
    }
  }
  const title = state === "running" ? "Running… (~3 min)" : state === "triggered" ? "Triggered!" : state === "error" ? "Error — try again" : "Refresh pipeline";
  return {
    trigger,
    state,
    title
  };
}
function useNotifications() {
  const [supported, setSupported] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const swRef = React.useRef(null);
  React.useEffect(() => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    navigator.serviceWorker.register('/sw.js').then(reg => {
      swRef.current = reg;
      setSupported(true);
      return reg.pushManager.getSubscription();
    }).then(existing => setSubscribed(existing != null)).catch(() => {});
  }, []);
  async function toggleNotify() {
    const reg = swRef.current;
    if (!reg) return;
    const existing = await reg.pushManager.getSubscription();
    if (existing) {
      await existing.unsubscribe();
      fetch('/.netlify/functions/save-subscription', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          endpoint: existing.endpoint
        })
      }).catch(() => {});
      setSubscribed(false);
      return;
    }
    if (Notification.permission === 'denied') {
      alert('Notifications are blocked. Please allow them in your browser settings.');
      return;
    }
    let vapidPublicKey;
    try {
      const res = await fetch('/.netlify/functions/save-subscription');
      vapidPublicKey = (await res.json()).vapidPublicKey;
    } catch {
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return;
    try {
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
      });
      fetch('/.netlify/functions/save-subscription', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(sub)
      }).catch(() => {});
      setSubscribed(true);
    } catch {}
  }
  return {
    supported,
    subscribed,
    toggleNotify
  };
}
function bestSide(p) {
  if (p.ev_over.adj_ev >= p.ev_under.adj_ev) {
    return {
      ...p.ev_over,
      direction: "OVER",
      odds: p.best_over_odds,
      opening: p.opening_over_odds
    };
  }
  return {
    ...p.ev_under,
    direction: "UNDER",
    odds: p.best_under_odds,
    opening: p.opening_under_odds
  };
}
function isPastSlate() {
  const today = window.__v2GetAppDate ? window.__v2GetAppDate() : phxDateISO();
  const current = window.V2_CURRENT_DATE || today;
  return current < today;
}
function ResultPill({
  result
}) {
  if (!result) return null;
  const label = result === "win" ? "W" : result === "loss" ? "L" : "P";
  return React.createElement("span", {
    className: `v2-result-pill ${result}`
  }, label);
}
function verdictClass(v, dir) {
  if (v && v.startsWith("FIRE")) return dir === "OVER" ? "fire-over" : "fire";
  if (v === "LEAN") return "lean";
  return "pass";
}
function centsMove(o, c) {
  if (o == null || c == null) return 0;
  const same = o > 0 && c > 0 || o < 0 && c < 0;
  if (same) return Math.abs(c - o);
  return Math.abs(o) - 100 + (Math.abs(c) - 100);
}
function sideCheaper(o, c) {
  const ip = x => x < 0 ? Math.abs(x) / (Math.abs(x) + 100) : 100 / (x + 100);
  return ip(c) < ip(o);
}
function steamInfo(p, dir) {
  const isOver = dir === "OVER";
  const o = isOver ? p.opening_over_odds : p.opening_under_odds;
  const c = isOver ? p.best_over_odds : p.best_under_odds;
  const cents = centsMove(o, c);
  if (!cents) return null;
  return {
    cents,
    steamWith: !sideCheaper(o, c)
  };
}
function impliedProb(odds) {
  if (odds == null) return null;
  return odds < 0 ? Math.abs(odds) / (Math.abs(odds) + 100) : 100 / (odds + 100);
}
function getMovementHelpers() {
  return window.V2MovementHelpers || {};
}
function MovementChart({
  movement
}) {
  if (!movement?.ready) {
    return React.createElement("div", {
      className: "v2-move-empty"
    }, "Not enough FanDuel history yet");
  }
  const points = movement.points || [];
  const width = 320;
  const height = 92;
  const topPad = 10;
  const lineBandTop = 58;
  const lineBandBottom = 82;
  const odds = points.map(p => p.odds).filter(v => v != null);
  const lines = points.map(p => p.kLine);
  const minOdds = Math.min(...odds);
  const maxOdds = Math.max(...odds);
  const minLine = Math.min(...lines);
  const maxLine = Math.max(...lines);
  const xFor = idx => points.length === 1 ? width / 2 : idx / (points.length - 1) * width;
  const yForOdds = val => {
    if (val == null || minOdds === maxOdds) return topPad + 18;
    return topPad + (maxOdds - val) / (maxOdds - minOdds) * 36;
  };
  const yForLine = val => {
    if (minLine === maxLine) return (lineBandTop + lineBandBottom) / 2;
    return lineBandTop + (maxLine - val) / (maxLine - minLine) * (lineBandBottom - lineBandTop);
  };
  const oddsPath = points.map((pt, idx) => `${idx === 0 ? "M" : "L"} ${xFor(idx).toFixed(1)} ${yForOdds(pt.odds).toFixed(1)}`).join(" ");
  const linePath = points.map((pt, idx) => {
    if (idx === 0) {
      return `M ${xFor(idx).toFixed(1)} ${yForLine(pt.kLine).toFixed(1)}`;
    }
    const prev = points[idx - 1];
    return `L ${xFor(idx).toFixed(1)} ${yForLine(prev.kLine).toFixed(1)} L ${xFor(idx).toFixed(1)} ${yForLine(pt.kLine).toFixed(1)}`;
  }).join(" ");
  return React.createElement("div", {
    className: "v2-move-chart-wrap"
  }, React.createElement("svg", {
    className: "v2-move-chart",
    viewBox: `0 0 ${width} ${height}`,
    preserveAspectRatio: "none"
  }, React.createElement("path", {
    d: oddsPath,
    className: "v2-move-odds-line"
  }), React.createElement("path", {
    d: linePath,
    className: "v2-move-kline-step"
  }), points.map((pt, idx) => React.createElement(React.Fragment, {
    key: `${pt.t}-${idx}`
  }, React.createElement("circle", {
    className: `v2-move-point ${idx === 0 ? "start" : idx === points.length - 1 ? "end" : ""}`,
    cx: xFor(idx),
    cy: yForOdds(pt.odds),
    r: idx === points.length - 1 ? 3 : 2.2
  }), React.createElement("circle", {
    className: "v2-move-line-point",
    cx: xFor(idx),
    cy: yForLine(pt.kLine),
    r: 1.6
  })))), React.createElement("div", {
    className: "v2-move-legend"
  }, React.createElement("span", {
    className: "odds"
  }, "picked-side odds"), React.createElement("span", {
    className: "line"
  }, "K line")));
}
function VerdictBadge({
  side
}) {
  const v = side.verdict;
  if (v === "PASS") {
    return React.createElement("div", {
      className: "v2-verdict pass"
    }, "PASS");
  }
  const cls = verdictClass(v, side.direction);
  const isOver = side.direction === "OVER";
  const dirArrow = isOver ? Icon.up : Icon.down;
  const label = v === "LEAN" ? "LEAN" : v.replace("FIRE ", "").toUpperCase();
  return React.createElement("div", {
    className: `v2-verdict ${cls}`
  }, React.createElement("span", {
    className: "dir"
  }, dirArrow, " ", side.direction), React.createElement("span", {
    className: "label"
  }, v === "LEAN" ? "LEAN" : `FIRE \u00B7 ${label}`));
}
function ProjBar({
  line,
  lambda
}) {
  const lo = line - 3;
  const hi = line + 3;
  const cl = x => Math.max(0, Math.min(1, (x - lo) / (hi - lo)));
  return React.createElement("div", {
    className: "v2-projbar"
  }, React.createElement("div", {
    className: "line",
    style: {
      left: `${cl(line) * 100}%`
    }
  }), React.createElement("div", {
    className: "proj",
    style: {
      left: `${cl(lambda) * 100}%`
    }
  }));
}
function WhyPills({
  p,
  side
}) {
  const stats = [];
  const oppK = p.opp_k_rate;
  const oppVs = (oppK - 0.227) / 0.227 * 100;
  stats.push({
    icon: Icon.users,
    v: `${(oppK * 100).toFixed(0)}%`,
    tone: (side.direction === "OVER" ? oppVs > 0 : oppVs < 0) ? "pos" : "neg",
    title: `Opponent K-rate ${(oppK * 100).toFixed(1)}% (${oppVs >= 0 ? "+" : ""}${oppVs.toFixed(0)}% vs avg)`
  });
  const k9Recent = p.recent_k9;
  const k9Season = p.season_k9;
  const k9Delta = k9Recent - k9Season;
  stats.push({
    icon: Icon.ball,
    v: k9Recent.toFixed(1),
    tone: (side.direction === "OVER" ? k9Delta > 0 : k9Delta < 0) ? "pos" : "neg",
    title: `Recent K/9 ${k9Recent.toFixed(1)} (${k9Delta >= 0 ? "+" : ""}${k9Delta.toFixed(1)} vs season ${k9Season.toFixed(1)})`
  });
  if (p.ump_k_adj && Math.abs(p.ump_k_adj) > 0.05) {
    stats.push({
      icon: Icon.ump,
      v: `${p.ump_k_adj > 0 ? "+" : ""}${p.ump_k_adj.toFixed(2)}`,
      tone: (side.direction === "OVER" ? p.ump_k_adj > 0 : p.ump_k_adj < 0) ? "pos" : "neg",
      title: `Umpire K-adjustment ${p.ump_k_adj > 0 ? "+" : ""}${p.ump_k_adj.toFixed(2)} K/g`
    });
  }
  const steam = steamInfo(p, side.direction);
  return React.createElement("div", {
    className: "v2-why v2-why-compact"
  }, stats.map((s, i) => React.createElement("span", {
    key: i,
    className: `v2-stat ${s.tone}`,
    title: s.title
  }, s.icon, React.createElement("span", {
    className: "v"
  }, s.v))), steam && React.createElement("span", {
    className: `v2-stat ${steam.steamWith ? "pos" : "neg"}`,
    title: `Steam ${steam.steamWith ? "with" : "against"} the pick, ${steam.cents}¢`
  }, steam.steamWith ? Icon.up : Icon.down, React.createElement("span", {
    className: "v"
  }, steam.cents, "\xA2")));
}
function PickCard({
  p,
  onOpen
}) {
  const side = bestSide(p);
  const cls = verdictClass(side.verdict, side.direction);
  const started = p.game_state !== "pregame";
  const directionMod = side.verdict === "PASS" ? "pass" : side.direction === "OVER" ? "over-pick" : "under-pick";
  const cardMod = started ? "final" : `${cls} ${directionMod}`;
  const past = isPastSlate();
  const showResult = past && side.verdict !== "PASS";
  return React.createElement("article", {
    className: `v2-card ${cardMod}`,
    onClick: () => onOpen && onOpen(p),
    role: "button",
    tabIndex: 0,
    onKeyDown: e => {
      if (e.key === "Enter" || e.key === " ") onOpen && onOpen(p);
    }
  }, React.createElement("div", {
    className: "v2-card-top"
  }, React.createElement("div", {
    className: "v2-teamblock"
  }, React.createElement("div", {
    className: "v2-matchup"
  }, React.createElement("span", null, ab(p.team)), React.createElement("span", {
    className: "vs"
  }, "vs"), React.createElement("span", null, ab(p.opp_team)), React.createElement("span", {
    className: "time"
  }, p.game_state === "in_progress" ? React.createElement("span", {
    style: {
      display: "inline-flex",
      gap: 5,
      alignItems: "center"
    }
  }, React.createElement("span", {
    className: "v2-livedot"
  }), "LIVE") : fmtTime(p.game_time))), React.createElement("div", {
    className: "v2-pitcher-name"
  }, p.pitcher, React.createElement("span", {
    className: "v2-pitcher-throws"
  }, p.pitcher_throws, "HP"))), React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center"
    }
  }, React.createElement(VerdictBadge, {
    side: side
  }), showResult && React.createElement(ResultPill, {
    result: side.result
  }))), React.createElement("div", {
    className: "v2-line"
  }, React.createElement("div", {
    className: "v2-line-cell"
  }, React.createElement("div", {
    className: "v2-line-label"
  }, "Line \xB7 ", side.direction), React.createElement("div", {
    className: "v2-line-value"
  }, p.k_line, React.createElement("span", {
    style: {
      fontSize: 14,
      opacity: .5
    }
  }, " K")), React.createElement("div", {
    className: "v2-line-sub mono"
  }, fmtOdds(side.odds), " \xB7 ", side.direction === "OVER" ? p.best_over_book || "book" : p.best_under_book || "book")), React.createElement("div", {
    className: "v2-line-cell"
  }, React.createElement("div", {
    className: "v2-line-label"
  }, "Projection"), React.createElement("div", {
    className: "v2-line-value"
  }, p.lambda.toFixed(2)), React.createElement(ProjBar, {
    line: p.k_line,
    lambda: p.lambda
  })), React.createElement("div", {
    className: "v2-line-cell"
  }, React.createElement("div", {
    className: "v2-line-label"
  }, "EV ROI \xB7 Edge"), React.createElement("div", {
    className: `v2-line-value ${side.adj_ev > 0 ? "pos" : "neg"}`
  }, side.adj_ev > 0 ? "+" : "", (side.adj_ev * 100).toFixed(1), "%"), React.createElement("div", {
    className: "v2-line-sub mono"
  }, "edge ", (side.edge ?? side.ev) > 0 ? "+" : "", (((side.edge ?? side.ev) || 0) * 100).toFixed(1), "% \xB7 p = ", (side.win_prob * 100).toFixed(1), "%"))), React.createElement(WhyPills, {
    p: p,
    side: side
  }));
}
function DateBar() {
  const today = window.__v2GetAppDate ? window.__v2GetAppDate() : phxDateISO();
  const current = window.V2_CURRENT_DATE || today;
  const meta = window.V2_DATE_META || {};
  const archive = new Set(Object.keys(meta).concat((window.V2_DATES || []).map(d => typeof d === "string" ? d : d.date)));
  const parse = s => {
    const [y, m, d] = s.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d));
  };
  const fmt = d => d.toISOString().slice(0, 10);
  const tDate = parse(today);
  const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const entries = [];
  for (let off = -3; off <= 3; off++) {
    const d = new Date(tDate);
    d.setUTCDate(d.getUTCDate() + off);
    const iso = fmt(d);
    entries.push({
      iso,
      d: String(d.getUTCDate()).padStart(2, "0"),
      dow: dayNames[d.getUTCDay()],
      isToday: iso === today,
      archived: archive.has(iso),
      wins: meta[iso]?.wins ?? 0,
      losses: meta[iso]?.losses ?? 0
    });
  }
  const navigate = iso => {
    const u = new URL(location.href);
    if (iso === today) u.searchParams.delete("date");else u.searchParams.set("date", iso);
    location.href = u.toString();
  };
  return React.createElement("div", {
    className: "v2-datebar"
  }, entries.map(x => {
    const isActive = x.iso === current;
    const clickable = x.isToday || x.archived;
    const isPast = x.archived && !x.isToday;
    const dotCls = isPast && (x.wins > 0 || x.losses > 0) ? x.wins >= x.losses ? " past-win" : " past-loss" : "";
    const cls = "v2-datepill" + (isActive ? " today" : "") + dotCls;
    return React.createElement("button", {
      key: x.iso,
      type: "button",
      className: cls,
      style: {
        opacity: clickable ? 1 : 0.35,
        cursor: clickable ? "pointer" : "default"
      },
      onClick: clickable ? () => navigate(x.iso) : undefined,
      disabled: !clickable,
      "aria-current": isActive ? "date" : undefined,
      "aria-label": `${x.dow} ${x.iso}`
    }, React.createElement("span", {
      className: "dow"
    }, x.dow), React.createElement("span", {
      className: "d"
    }, x.d));
  }));
}
function PickDetail({
  p,
  onClose
}) {
  if (!p) return null;
  const sideOver = {
    ...p.ev_over,
    direction: "OVER",
    odds: p.best_over_odds,
    opening: p.opening_over_odds
  };
  const sideUnder = {
    ...p.ev_under,
    direction: "UNDER",
    odds: p.best_under_odds,
    opening: p.opening_under_odds
  };
  const best = bestSide(p);
  const helpers = getMovementHelpers();
  const [showFactorDetails, setShowFactorDetails] = useState(false);
  const factorGroups = useMemo(() => {
    const buildFactorGroups = window.V2FactorDetails?.buildFactorGroups;
    return buildFactorGroups ? buildFactorGroups(p, best.direction) : [];
  }, [p, best.direction]);
  const steam = steamInfo(p, best.direction) || {
    cents: 0,
    steamWith: false
  };
  const movement = helpers.buildPickedSideMovement ? helpers.buildPickedSideMovement(window.V2_STEAM_RAW || {
    snapshots: []
  }, {
    pitcher: p.pitcher,
    direction: best.direction,
    openingLine: p.opening_line,
    openingOdds: best.direction === "OVER" ? p.opening_over_odds : p.opening_under_odds
  }) : {
    ready: false,
    points: [],
    reason: "helpers_missing"
  };
  const movementSummary = helpers.summarizeLineMovement ? helpers.summarizeLineMovement(movement) : null;
  React.useEffect(() => {
    const h = e => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", h);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", h);
      document.body.style.overflow = "";
    };
  }, [onClose]);
  const SideCard = ({
    s: rawSide
  }) => {
    const s = {
      ...rawSide,
      adj_ev: isFiniteNumber(rawSide.adj_ev) ? rawSide.adj_ev : 0,
      win_prob: isFiniteNumber(rawSide.win_prob) ? rawSide.win_prob : 0,
      ev: isFiniteNumber(rawSide.ev) ? rawSide.ev : 0,
      edge: isFiniteNumber(rawSide.edge) ? rawSide.edge : null
    };
    const picked = s.direction === best.direction;
    const adjEv = isFiniteNumber(s.adj_ev) ? s.adj_ev : null;
    const winProb = isFiniteNumber(s.win_prob) ? s.win_prob : null;
    const edgeVal = isFiniteNumber(s.edge ?? s.ev) ? s.edge ?? s.ev : null;
    const pos = adjEv != null && adjEv > 0;
    return React.createElement("div", {
      className: `v2-side-card ${picked ? "picked" : ""}`
    }, picked && React.createElement("span", {
      className: "badge-mini"
    }, "PICK"), React.createElement("div", {
      className: "dir"
    }, s.direction, " ", p.k_line), React.createElement("div", {
      className: "odds"
    }, fmtOdds(s.odds), " \xB7 open ", fmtOdds(s.opening)), React.createElement("div", {
      className: `ev ${adjEv == null ? "" : pos ? "pos" : "neg"}`
    }, adjEv == null ? "--" : `${pos ? "+" : ""}${(adjEv * 100).toFixed(1)}%`), React.createElement("div", {
      className: "wp"
    }, "p = ", (s.win_prob * 100).toFixed(1), "% \xB7 edge ", ((s.edge ?? s.ev) || 0) > 0 ? "+" : "", (((s.edge ?? s.ev) || 0) * 100).toFixed(1), "%"));
  };
  const LEAGUE_K = 0.22;
  const LEAGUE_K9 = 8.5;
  const lambda = isFiniteNumber(p.lambda) ? p.lambda : null;
  const kLine = isFiniteNumber(p.k_line) ? p.k_line : null;
  const avgIp = isFiniteNumber(p.avg_ip) ? p.avg_ip : null;
  const oppKRate = isFiniteNumber(p.opp_k_rate) ? p.opp_k_rate : null;
  const recentK9 = isFiniteNumber(p.recent_k9) ? p.recent_k9 : null;
  const seasonK9 = isFiniteNumber(p.season_k9) ? p.season_k9 : null;
  const careerK9 = isFiniteNumber(p.career_k9) ? p.career_k9 : null;
  const parkFactor = isFiniteNumber(p.park_factor) ? p.park_factor : null;
  const oppDelta = oppKRate == null ? null : (oppKRate - LEAGUE_K) * 100;
  const k9Delta = recentK9 == null ? null : recentK9 - LEAGUE_K9;
  const ump = isFiniteNumber(p.ump_k_adj) ? p.ump_k_adj : 0;
  const supportsUnder = best.direction === "UNDER";
  const oppSupports = oppDelta == null ? null : supportsUnder ? oppDelta < 0 : oppDelta > 0;
  const k9Supports = k9Delta == null ? null : supportsUnder ? k9Delta < 0 : k9Delta > 0;
  const umpSupports = supportsUnder ? ump < 0 : ump > 0;
  const isLive = p.game_state === "in_progress";
  const isFinal = p.game_state === "final";
  const isPass = best.verdict === "PASS";
  const live = p.live;
  const result = p.result;
  return ReactDOM.createPortal(React.createElement(React.Fragment, null, React.createElement("div", {
    className: "v2-sheet-backdrop",
    onClick: onClose
  }), React.createElement("div", {
    className: "v2-sheet",
    role: "dialog",
    "aria-modal": "true"
  }, React.createElement("div", {
    className: "v2-sheet-grip"
  }), React.createElement("div", {
    className: "v2-sheet-head"
  }, React.createElement("div", null, React.createElement("div", {
    className: "meta"
  }, ab(p.team), " vs ", ab(p.opp_team), " \xB7 ", isLive ? "LIVE" : isFinal ? "FINAL" : fmtTime(p.game_time)), React.createElement("div", {
    className: "pitcher"
  }, p.pitcher, React.createElement("span", {
    className: "throws"
  }, p.pitcher_throws, "HP"))), React.createElement("button", {
    className: "v2-sheet-close",
    onClick: onClose,
    "aria-label": "Close"
  }, React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "14",
    height: "14",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round"
  }, React.createElement("path", {
    d: "M3 3l10 10M13 3L3 13"
  })))), isLive && live && React.createElement("div", {
    className: "v2-sheet-state v2-sheet-live"
  }, React.createElement("div", {
    className: "state-head"
  }, React.createElement("span", {
    className: "pulse"
  }), React.createElement("span", {
    className: "state-lbl"
  }, "LIVE \xB7 ", live.innings, " IP \xB7 ", live.pitches, " pitches")), React.createElement("div", {
    className: "live-k"
  }, React.createElement("span", {
    className: "live-k-num"
  }, live.current_k), React.createElement("span", {
    className: "live-k-sep"
  }, "/"), React.createElement("span", {
    className: "live-k-line"
  }, p.k_line), React.createElement("span", {
    className: "live-k-lbl"
  }, "K")), React.createElement("div", {
    className: "live-meta"
  }, "Projected final: ", React.createElement("b", null, fmtFixedOrDash(live.proj_final_k, 1), " K"), React.createElement("span", {
    className: `live-verdict ${isFiniteNumber(live.proj_final_k) && kLine != null && live.proj_final_k > kLine ? "over" : "under"}`
  }, live.proj_final_k > p.k_line ? "→ OVER pace" : "→ UNDER pace"))), isLive && !live && React.createElement("div", {
    className: "v2-sheet-state v2-sheet-live"
  }, React.createElement("div", {
    className: "state-head"
  }, React.createElement("span", {
    className: "pulse"
  }), React.createElement("span", {
    className: "state-lbl"
  }, "LIVE \xB7 game in progress")), React.createElement("div", {
    className: "live-meta"
  }, "Live K tracking not wired yet \u2014 pipeline does not hydrate in-game stats.")), isFinal && !result && React.createElement("div", {
    className: "v2-sheet-state v2-sheet-final outcome-pass"
  }, React.createElement("div", {
    className: "state-head"
  }, React.createElement("span", {
    className: "state-lbl"
  }, "FINAL")), React.createElement("div", {
    className: "final-meta"
  }, "Grading not available in today's snapshot \u2014 check Results tab.")), isFinal && result && React.createElement("div", {
    className: `v2-sheet-state v2-sheet-final outcome-${result.outcome}`
  }, React.createElement("div", {
    className: "state-head"
  }, React.createElement("span", {
    className: "state-lbl"
  }, "FINAL \xB7 ", result.final_k, " K")), result.outcome === "pass" ? React.createElement(React.Fragment, null, React.createElement("div", {
    className: "final-outcome"
  }, "NO BET"), React.createElement("div", {
    className: "final-meta"
  }, "Model found no edge on either side. Line closed at ", p.k_line, ", final ", result.final_k, " K", result.final_k > p.k_line ? " · OVER hit" : result.final_k < p.k_line ? " · UNDER hit" : " · push", ".")) : React.createElement(React.Fragment, null, React.createElement("div", {
    className: "final-outcome"
  }, result.outcome === "win" ? "WIN" : result.outcome === "loss" ? "LOSS" : "PUSH", React.createElement("span", {
    className: `final-units ${result.units_won >= 0 ? "pos" : "neg"}`
  }, result.units_won >= 0 ? "+" : "", result.units_won.toFixed(2), "u")), React.createElement("div", {
    className: "final-meta"
  }, result.side_taken?.toUpperCase(), " ", result.line_at_bet, " @ ", fmtOdds(result.odds_at_bet), " \xB7 ", result.units_risked, "u risked"))), isPass && !isLive && !isFinal && React.createElement("div", {
    className: "v2-sheet-state v2-sheet-pass"
  }, React.createElement("div", {
    className: "state-head"
  }, React.createElement("span", {
    className: "state-lbl"
  }, "NO EDGE")), React.createElement("div", {
    className: "pass-copy"
  }, "Model projection (", fmtFixedOrDash(lambda, 2), " K) is too close to the line (", kLine ?? "--", ") on both sides. Skipping this one.")), React.createElement("div", {
    className: "v2-sheet-section"
  }, React.createElement("div", {
    className: "h"
  }, "Sides \xB7 EV ROI comparison"), React.createElement("div", {
    className: "v2-sides"
  }, React.createElement(SideCard, {
    s: sideOver
  }), React.createElement(SideCard, {
    s: sideUnder
  }))), React.createElement("div", {
    className: "v2-sheet-section"
  }, React.createElement("div", {
    className: "h"
  }, "Projection"), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Line (K)"), React.createElement("span", {
    className: "val"
  }, kLine ?? "--")), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Model \u03BB"), React.createElement("span", {
    className: "val"
  }, fmtFixedOrDash(lambda, 2))), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Edge"), React.createElement("span", {
    className: `val ${lambda == null || kLine == null ? "" : lambda > kLine ? "pos" : "neg"}`
  }, lambda == null || kLine == null ? "--" : `${lambda > kLine ? "+" : ""}${(lambda - kLine).toFixed(2)} K`)), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Expected IP"), React.createElement("span", {
    className: "val"
  }, fmtFixedOrDash(avgIp, 1)))), React.createElement("div", {
    className: "v2-sheet-section"
  }, React.createElement("div", {
    className: "h"
  }, "Why this bet"), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, Icon.users, " Lineup"), p.lineup_used ? React.createElement("span", {
    className: "val pos"
  }, "Confirmed") : React.createElement("span", {
    className: "val",
    style: {
      color: "var(--ink-dim)"
    }
  }, "Projected")), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, Icon.ump, " Umpire"), ump !== 0 ? React.createElement("span", {
    className: `val ${umpSupports ? "pos" : "neg"}`
  }, "Confirmed", React.createElement("span", {
    className: "delta"
  }, ump > 0 ? "+" : "", ump.toFixed(2))) : React.createElement("span", {
    className: "val",
    style: {
      color: "var(--ink-dim)"
    }
  }, "TBA")), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Park factor"), parkFactor != null ? React.createElement("span", {
    className: `val ${helpers.parkFactorTone ? helpers.parkFactorTone(parkFactor, best.direction) : ""}`
  }, parkFactor.toFixed(2)) : React.createElement("span", {
    className: "val",
    style: {
      color: "var(--ink-dim)"
    }
  }, "Unknown")), React.createElement("button", {
    type: "button",
    className: "v2-factor-toggle",
    "aria-expanded": showFactorDetails,
    "aria-controls": "v2-factor-details",
    onClick: () => setShowFactorDetails(prev => !prev)
  }, showFactorDetails ? "Hide factor details" : "Show factor details"), showFactorDetails && React.createElement("div", {
    className: "v2-factor-panel",
    id: "v2-factor-details"
  }, factorGroups.map(group => React.createElement("div", {
    className: "v2-factor-group",
    key: group.key
  }, React.createElement("div", {
    className: "v2-factor-group-h"
  }, group.label), React.createElement("div", {
    className: "v2-factor-rows"
  }, group.rows.map(row => React.createElement("div", {
    className: "v2-factor-row",
    key: row.key
  }, React.createElement("div", {
    className: "v2-factor-row-top"
  }, React.createElement("span", {
    className: "v2-factor-label"
  }, row.label), React.createElement("span", {
    className: `v2-factor-pill ${row.status}`
  }, row.status)), React.createElement("div", {
    className: `v2-factor-value ${row.tone ? row.tone : ""}`
  }, row.value), row.note && React.createElement("div", {
    className: "v2-factor-note"
  }, row.note))))))), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, Icon.users, " Opp. K-rate (bats)"), React.createElement("span", {
    className: `val ${oppSupports == null ? "" : oppSupports ? "pos" : "neg"}`
  }, oppKRate == null ? "--" : `${(oppKRate * 100).toFixed(1)}%`, oppDelta != null && React.createElement("span", {
    className: "delta"
  }, oppDelta >= 0 ? "+" : "", oppDelta.toFixed(1), " vs lg"))), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, Icon.ball, " Recent K/9 (L5)"), React.createElement("span", {
    className: `val ${k9Supports == null ? "" : k9Supports ? "pos" : "neg"}`
  }, fmtFixedOrDash(recentK9, 1), k9Delta != null && React.createElement("span", {
    className: "delta"
  }, k9Delta >= 0 ? "+" : "", k9Delta.toFixed(1), " vs lg"))), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Season K/9"), React.createElement("span", {
    className: "val"
  }, fmtFixedOrDash(seasonK9, 1))), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Career K/9"), React.createElement("span", {
    className: "val"
  }, fmtFixedOrDash(careerK9, 1)))), React.createElement("div", {
    className: "v2-sheet-section"
  }, React.createElement("div", {
    className: "h"
  }, `FanDuel · ${best.direction} · open to now`, movementSummary?.lineMoved && React.createElement("span", {
    className: "v2-line-move-badge"
  }, `line moved ${movementSummary.openingLine} -> ${movementSummary.currentLine}`)), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Opening line"), React.createElement("span", {
    className: "val"
  }, p.opening_line, " \xB7 ", fmtOdds(p.opening_over_odds), "/", fmtOdds(p.opening_under_odds))), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Current line"), React.createElement("span", {
    className: "val"
  }, p.k_line, " \xB7 ", fmtOdds(sideOver.odds), "/", fmtOdds(sideUnder.odds))), React.createElement(MovementChart, {
    movement: movement
  }), React.createElement("div", {
    style: {
      fontSize: 11,
      color: "var(--ink-dim)",
      marginTop: 6,
      fontFamily: "JetBrains Mono, monospace"
    }
  }, steam.cents > 0 ? `${steam.cents}¢ ${steam.steamWith ? "with" : "against"} the pick` : "No steam signal at the picked side price")), React.createElement("div", {
    className: "v2-sheet-section"
  }, React.createElement("div", {
    className: "h"
  }, "Model confidence"), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Verdict"), React.createElement("span", {
    className: "val"
  }, best.verdict)), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Movement confidence"), React.createElement("span", {
    className: "val"
  }, (best.movement_conf * 100).toFixed(0), "%")), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Edge"), React.createElement("span", {
    className: `val ${((best.edge ?? best.ev) || 0) > 0 ? "pos" : "neg"}`
  }, ((best.edge ?? best.ev) || 0) > 0 ? "+" : "", (((best.edge ?? best.ev) || 0) * 100).toFixed(1), "%")), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Raw EV ROI"), React.createElement("span", {
    className: "val"
  }, best.ev > 0 ? "+" : "", (best.ev * 100).toFixed(1), "%")), React.createElement("div", {
    className: "v2-stat-row"
  }, React.createElement("span", {
    className: "lbl"
  }, "Adjusted EV ROI"), React.createElement("span", {
    className: `val ${best.adj_ev > 0 ? "pos" : "neg"}`
  }, best.adj_ev > 0 ? "+" : "", (best.adj_ev * 100).toFixed(1), "%"))), React.createElement("div", {
    className: "v2-sheet-actions"
  }, React.createElement("button", {
    className: "v2-btn-ghost",
    onClick: onClose
  }, "Close")))), document.body);
}
function EmptyState({
  filter
}) {
  const messages = {
    ALL: {
      ttl: "No slate today",
      sub: "MLB is off. Check back tomorrow — the next slate posts around 9 AM ET."
    },
    FIRE: {
      ttl: "No FIRE picks",
      sub: "Model didn't find any 1u+ ROI edges in today's slate. That's a signal, not a bug — skip days are a strategy."
    },
    LEAN: {
      ttl: "No leans",
      sub: "Nothing between +2% and +6% EV ROI right now."
    },
    LIVE: {
      ttl: "No games live",
      sub: "First pitch hasn't dropped yet. Live picks will appear here during games."
    }
  };
  const m = messages[filter] || messages.ALL;
  return React.createElement("div", {
    className: "v2-state"
  }, React.createElement("div", {
    className: "glyph"
  }, React.createElement("svg", {
    viewBox: "0 0 24 24",
    width: "24",
    height: "24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5"
  }, React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "9"
  }), React.createElement("path", {
    d: "M8 14s1.5 2 4 2 4-2 4-2",
    strokeLinecap: "round"
  }), React.createElement("circle", {
    cx: "9",
    cy: "10",
    r: "1",
    fill: "currentColor"
  }), React.createElement("circle", {
    cx: "15",
    cy: "10",
    r: "1",
    fill: "currentColor"
  }))), React.createElement("div", {
    className: "ttl"
  }, m.ttl), React.createElement("div", {
    className: "sub"
  }, m.sub));
}
function LoadingState() {
  return React.createElement("div", {
    className: "v2-cards",
    style: {
      paddingTop: 12
    }
  }, React.createElement("div", {
    className: "v2-section-h",
    style: {
      margin: "0 18px 8px"
    }
  }, React.createElement("span", {
    className: "v2-skel",
    style: {
      display: "inline-block",
      width: 90,
      height: 11
    }
  })), [0, 1, 2].map(i => React.createElement("div", {
    key: i,
    className: "v2-skel-card"
  }, React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between"
    }
  }, React.createElement("div", {
    className: "v2-skel",
    style: {
      width: "40%",
      height: 14
    }
  }), React.createElement("div", {
    className: "v2-skel",
    style: {
      width: 60,
      height: 36,
      borderRadius: 4
    }
  })), React.createElement("div", {
    className: "v2-skel",
    style: {
      width: "55%",
      height: 22
    }
  }), React.createElement("div", {
    style: {
      display: "flex",
      gap: 10,
      marginTop: 6
    }
  }, React.createElement("div", {
    className: "v2-skel",
    style: {
      flex: 1,
      height: 50
    }
  }), React.createElement("div", {
    className: "v2-skel",
    style: {
      flex: 1,
      height: 50
    }
  }), React.createElement("div", {
    className: "v2-skel",
    style: {
      flex: 1,
      height: 50
    }
  })))));
}
function ErrorState({
  onRetry
}) {
  return React.createElement("div", {
    className: "v2-state"
  }, React.createElement("div", {
    className: "glyph",
    style: {
      background: "color-mix(in oklab, var(--neg) 18%, transparent)",
      color: "var(--neg)"
    }
  }, React.createElement("svg", {
    viewBox: "0 0 24 24",
    width: "22",
    height: "22",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round"
  }, React.createElement("path", {
    d: "M12 7v6M12 17h.01"
  }), React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "9.5"
  }))), React.createElement("div", {
    className: "ttl"
  }, "Couldn't load today's slate"), React.createElement("div", {
    className: "sub"
  }, "The odds feed didn't respond. Data may be stale."), React.createElement("div", {
    className: "err-detail"
  }, "ODDS_API: 504 \xB7 fetched 2m ago"), React.createElement("div", {
    style: {
      marginTop: 22
    }
  }, React.createElement("button", {
    className: "v2-btn-ghost",
    style: {
      padding: "10px 22px"
    },
    onClick: onRetry
  }, "Retry")));
}
function GradingSummary({
  pitchers
}) {
  let w = 0,
    l = 0,
    p = 0,
    n = 0;
  for (const pit of pitchers) {
    const side = bestSide(pit);
    if (side.verdict === "PASS" || !side.result) continue;
    if (side.result === "win") w++;else if (side.result === "loss") l++;else if (side.result === "push") p++;
    n++;
  }
  if (n === 0) return null;
  return React.createElement("div", {
    className: "v2-grading-summary"
  }, React.createElement("span", {
    className: "w"
  }, w, "W"), React.createElement("span", {
    className: "n"
  }, "\xB7"), React.createElement("span", {
    className: "l"
  }, l, "L"), p > 0 && React.createElement(React.Fragment, null, React.createElement("span", {
    className: "n"
  }, "\xB7"), React.createElement("span", {
    className: "p"
  }, p, "P")));
}
function PicksTab({
  pitchersOverride
}) {
  const [filter, setFilter] = useState("ALL");
  const [detail, setDetail] = useState(null);
  const {
    supported: notifySupported,
    subscribed: notifyOn,
    toggleNotify
  } = useNotifications();
  const {
    trigger: triggerPipeline,
    state: pipelineState,
    title: pipelineTitle
  } = usePipelineTrigger();
  const pitchers = pitchersOverride ?? window.V2_DATA.pitchers;
  const past = isPastSlate();
  const filtered = useMemo(() => {
    if (filter === "ALL") return pitchers;
    if (filter === "FIRE") return pitchers.filter(p => bestSide(p).verdict.startsWith("FIRE"));
    if (filter === "LEAN") return pitchers.filter(p => bestSide(p).verdict === "LEAN");
    if (filter === "LIVE") return pitchers.filter(p => p.game_state === "in_progress");
    return pitchers;
  }, [filter]);
  const counts = {
    FIRE: pitchers.filter(p => bestSide(p).verdict.startsWith("FIRE")).length,
    LEAN: pitchers.filter(p => bestSide(p).verdict === "LEAN").length,
    LIVE: pitchers.filter(p => p.game_state === "in_progress").length,
    ALL: pitchers.length
  };
  const chips = [["ALL", "All"], ["FIRE", "Fire"], ["LEAN", "Lean"], ["LIVE", "Live"]];
  const upcoming = filtered.filter(p => p.game_state === "pregame");
  const live = filtered.filter(p => p.game_state !== "pregame");
  const fires = pitchers.filter(p => bestSide(p).verdict.startsWith("FIRE"));
  return React.createElement(React.Fragment, null, React.createElement("div", {
    className: "v2-header"
  }, React.createElement("div", {
    className: "v2-header-row"
  }, React.createElement("div", {
    className: "v2-brand"
  }, React.createElement("div", {
    className: "v2-kmark"
  }, "K"), React.createElement("div", null, React.createElement("div", {
    className: "v2-wordmark"
  }, "Betting Edge"), React.createElement("div", {
    className: "v2-subtitle"
  }, (() => {
    const gen = window.V2_DATA?.generated_at ? new Date(window.V2_DATA.generated_at) : null;
    const t = gen ? gen.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit"
    }) : "—";
    return `Updated ${t} · ${window.V2_DATA?.pitchers?.length ?? 0} props`;
  })()))), React.createElement("div", {
    className: "v2-header-actions"
  }, notifySupported && React.createElement("button", {
    className: `v2-icon-btn${notifyOn ? " active" : ""}`,
    title: notifyOn ? "Notifications on — click to disable" : "Enable push notifications",
    onClick: toggleNotify
  }, notifyOn ? Icon.bellOn : Icon.bell), React.createElement("button", {
    className: `v2-icon-btn${pipelineState === "triggered" ? " active" : ""}`,
    title: pipelineTitle,
    onClick: triggerPipeline,
    disabled: pipelineState === "running",
    style: pipelineState === "running" ? {
      opacity: 0.5
    } : {}
  }, Icon.refresh), React.createElement("button", {
    className: "v2-icon-btn",
    title: "Theme",
    onClick: () => window.__v2Theme?.toggleTheme()
  }, window.__v2Theme?.theme === "dark" ? Icon.sun : Icon.moon), React.createElement("a", {
    href: "/legacy",
    className: "v2-classic-link",
    title: "Switch to classic dashboard"
  }, "classic"))), React.createElement(DateBar, null)), past && React.createElement(GradingSummary, {
    pitchers: pitchers
  }), React.createElement("div", {
    className: "v2-digest"
  }, React.createElement("div", {
    className: "v2-digest-count"
  }, fires.length), React.createElement("div", {
    className: "v2-digest-body"
  }, React.createElement("div", {
    className: "v2-digest-title"
  }, "Fire picks today"), React.createElement("div", {
    className: "v2-digest-sub"
  }, fires.length > 0 ? (() => {
    const avgEv = fires.reduce((s, p) => s + bestSide(p).adj_ev, 0) / fires.length * 100;
    const pre = fires.filter(p => p.game_state === "pregame").length;
    return `${fires.length} actionable · avg EV ROI +${avgEv.toFixed(1)}% · ${pre} pregame`;
  })() : "No FIRE picks in slate")), React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "14",
    height: "14",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    style: {
      color: "var(--ink-dim)"
    }
  }, React.createElement("path", {
    d: "M6 3l5 5-5 5"
  }))), React.createElement("div", {
    className: "v2-chipbar"
  }, chips.map(([k, l]) => React.createElement("button", {
    key: k,
    className: `v2-chip ${filter === k ? "active" : ""}`,
    onClick: () => setFilter(k)
  }, l, " ", React.createElement("span", {
    className: "n"
  }, counts[k])))), React.createElement("div", {
    className: "v2-cards"
  }, upcoming.length > 0 && React.createElement("div", {
    className: "v2-section-h"
  }, "Upcoming"), upcoming.map((p, i) => React.createElement(PickCard, {
    key: "u" + i,
    p: p,
    onOpen: setDetail
  })), live.length > 0 && React.createElement("div", {
    className: "v2-section-h"
  }, "Live & Final"), live.map((p, i) => React.createElement(PickCard, {
    key: "l" + i,
    p: p,
    onOpen: setDetail
  })), filtered.length === 0 && React.createElement(EmptyState, {
    filter: filter
  })), detail && React.createElement(PickDetail, {
    p: detail,
    onClose: () => setDetail(null)
  }));
}
function PerfTab() {
  const d = window.V2_PERF;
  const maxAbsRoi = Math.max(0, ...d.rows.map(r => typeof r.roi === "number" ? Math.abs(r.roi) : 0));
  const [showCalib, setShowCalib] = useState(false);
  const notes = d.calibration_notes || [];
  return React.createElement(React.Fragment, null, React.createElement("div", {
    className: "v2-header"
  }, React.createElement("div", {
    className: "v2-header-row"
  }, React.createElement("div", {
    className: "v2-brand"
  }, React.createElement("div", {
    className: "v2-kmark"
  }, "K"), React.createElement("div", null, React.createElement("div", {
    className: "v2-wordmark"
  }, "Performance"), React.createElement("div", {
    className: "v2-subtitle"
  }, "Season \xB7 ", d.total_picks ?? 0, " graded picks"))), React.createElement("div", {
    className: "v2-header-actions"
  }, React.createElement("button", {
    className: `v2-icon-btn${showCalib ? " active" : ""}`,
    title: "Calibration log",
    onClick: () => setShowCalib(s => !s)
  }, React.createElement("svg", {
    viewBox: "0 0 16 16",
    width: "14",
    height: "14",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round"
  }, React.createElement("path", {
    d: "M2 4h12M4 8h8M6 12h4"
  })))))), showCalib && React.createElement("div", {
    className: "v2-calib-panel"
  }, React.createElement("div", {
    className: "v2-calib-title"
  }, "Calibration log \xB7 ", notes.length, " entries"), notes.length === 0 && React.createElement("div", {
    className: "v2-calib-empty"
  }, "No calibration notes yet."), notes.map((n, i) => {
    const match = n.match(/^\[(\d{4}-\d{2}-\d{2})\]\s*(.+)$/);
    const date = match ? match[1] : null;
    const text = match ? match[2] : n;
    return React.createElement("div", {
      key: i,
      className: "v2-calib-row"
    }, date && React.createElement("span", {
      className: "v2-calib-date"
    }, date), React.createElement("span", {
      className: "v2-calib-text"
    }, text));
  })), React.createElement("div", {
    className: "v2-perf-hero"
  }, React.createElement("div", {
    className: `v2-perf-units ${d.total_units >= 0 ? "pos" : "neg"}`
  }, d.total_units >= 0 ? "+" : "", d.total_units.toFixed(1), "u"), React.createElement("div", {
    className: "v2-perf-sub"
  }, "Net units \xB7 ", d.record, " \xB7 ROI ", d.total_roi >= 0 ? "+" : "", d.total_roi.toFixed(1), "%"), React.createElement("div", {
    className: "v2-perf-meta"
  }, React.createElement("div", null, React.createElement("div", {
    className: "lbl"
  }, "Best tier"), React.createElement("div", {
    className: "val"
  }, d.best_tier || "—")), React.createElement("div", null, React.createElement("div", {
    className: "lbl"
  }, "Win rate"), React.createElement("div", {
    className: "val"
  }, d.win_rate != null ? d.win_rate.toFixed(1) + "%" : "—")), React.createElement("div", null, React.createElement("div", {
    className: "lbl"
  }, "Last calib."), React.createElement("div", {
    className: "val"
  }, d.last_calibrated ? new Date(d.last_calibrated).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric"
  }) : "—")))), React.createElement("div", {
    className: "v2-tier"
  }, React.createElement("div", {
    className: "v2-section-h",
    style: {
      margin: "16px 0 4px"
    }
  }, "By tier"), d.rows.map((r, i) => {
    const isFire = r.verdict.startsWith("FIRE");
    const isFire2 = r.verdict === "FIRE 2u";
    const badgeCls = isFire ? r.side === "over" ? "fire-over" : "fire" : r.side === "over" ? "lean-over" : "lean-under";
    const roiPct = typeof r.roi === "number" ? r.roi : null;
    const winPct = typeof r.win_pct === "number" ? r.win_pct : null;
    const hasRoi = roiPct != null;
    const pct = hasRoi ? Math.min(1, Math.abs(roiPct) / Math.max(maxAbsRoi, 1)) : 0;
    return React.createElement("div", {
      key: i,
      className: "v2-tier-row"
    }, React.createElement("div", {
      className: `v2-tier-badge ${badgeCls}`
    }, r.verdict === "FIRE 1u" ? "F1u" : r.verdict === "FIRE 2u" ? "F2u" : "LEAN", React.createElement("span", {
      className: "s"
    }, r.side.toUpperCase())), React.createElement("div", {
      className: "v2-tier-bar-wrap"
    }, React.createElement("div", {
      className: "v2-tier-bar-head"
    }, React.createElement("span", null, r.picks, " picks \xB7 ", r.wins, "-", r.losses), React.createElement("span", {
      className: "wr"
    }, winPct != null ? `${(winPct * 100).toFixed(1)}%` : "--")), React.createElement("div", {
      className: "v2-tier-bar"
    }, React.createElement("div", {
      className: "break",
      style: {
        left: "50%"
      }
    }), hasRoi ? roiPct >= 0 ? React.createElement("div", {
      className: "fill pos",
      style: {
        left: "50%",
        width: `${pct * 50}%`
      }
    }) : React.createElement("div", {
      className: "fill neg",
      style: {
        right: "50%",
        width: `${pct * 50}%`,
        left: "auto"
      }
    }) : null)), React.createElement("div", {
      className: `v2-tier-roi ${hasRoi ? roiPct >= 0 ? "pos" : "neg" : ""}`
    }, hasRoi ? `${roiPct >= 0 ? "+" : ""}${roiPct.toFixed(1)}%` : "--", React.createElement("span", {
      className: "n"
    }, "ROI")));
  })));
}
function SteamTab() {
  const d = window.V2_STEAM;
  const [filter, setFilter] = useState("ALL");
  const filtered = useMemo(() => {
    if (filter === "OVER") return d.rows.filter(r => r.direction === "over");
    if (filter === "UNDER") return d.rows.filter(r => r.direction === "under");
    if (filter === "MINE") return d.rows.filter(r => r.my_pick);
    return d.rows;
  }, [filter]);
  const totalMoved = d.rows.length;
  const avgCents = totalMoved > 0 ? Math.round(d.rows.reduce((s, r) => s + r.cents, 0) / totalMoved) : 0;
  const mine = d.rows.filter(r => r.my_pick).length;
  return React.createElement(React.Fragment, null, React.createElement("div", {
    className: "v2-header"
  }, React.createElement("div", {
    className: "v2-header-row"
  }, React.createElement("div", {
    className: "v2-brand"
  }, React.createElement("div", {
    className: "v2-kmark"
  }, "K"), React.createElement("div", null, React.createElement("div", {
    className: "v2-wordmark"
  }, "Steam"), React.createElement("div", {
    className: "v2-subtitle"
  }, "Line movement \xB7 open \u2192 now"))), React.createElement("div", {
    className: "v2-header-actions"
  }, React.createElement("button", {
    className: "v2-icon-btn",
    title: "Refresh"
  }, Icon.refresh)))), React.createElement("div", {
    className: "v2-steam-hero"
  }, React.createElement("div", null, React.createElement("div", {
    className: "n"
  }, totalMoved)), React.createElement("div", {
    style: {
      flex: 1
    }
  }, React.createElement("div", {
    className: "lbl"
  }, "Active moves"), React.createElement("div", {
    className: "ttl"
  }, totalMoved > 0 ? `${avgCents}¢ avg · ${mine} align with my picks` : "No meaningful movement"))), React.createElement("div", {
    className: "v2-steam-filter"
  }, [["ALL", "All"], ["OVER", "Over ↑"], ["UNDER", "Under ↑"], ["MINE", "My picks"]].map(([k, l]) => React.createElement("button", {
    key: k,
    className: `f ${filter === k ? "active" : ""}`,
    onClick: () => setFilter(k)
  }, l))), React.createElement("div", {
    style: {
      paddingBottom: 90
    }
  }, filtered.map((r, i) => React.createElement("div", {
    key: i,
    className: "v2-steam-row"
  }, React.createElement("div", {
    className: `v2-steam-dir ${r.direction === "over" ? "up" : "down"}`
  }, r.direction === "over" ? "OV" : "UN"), React.createElement("div", null, React.createElement("div", {
    className: "v2-steam-name"
  }, r.pitcher), React.createElement("div", {
    className: "v2-steam-meta"
  }, r.team, " vs ", r.opp, " \xB7 ", r.k_line, " K", r.books_moved != null && r.books_total != null && ` · ${r.books_moved}/${r.books_total} books`, r.note && ` · ${r.note}`, r.my_pick && React.createElement("span", {
    style: {
      color: "var(--accent)",
      marginLeft: 6
    }
  }, "\xB7 ", r.my_pick))), React.createElement("div", {
    className: "v2-steam-delta",
    style: {
      color: r.direction === "over" ? "var(--pos)" : "var(--neg)"
    }
  }, r.cents, "\xA2", React.createElement("span", {
    className: "t"
  }, r.direction === "over" ? "↑ OVER" : "↑ UNDER")))), filtered.length === 0 && React.createElement("div", {
    className: "v2-state"
  }, React.createElement("div", {
    className: "ttl"
  }, "No movement"), React.createElement("div", {
    className: "sub"
  }, "No books have moved in this category."))));
}
function App() {
  const [tab, setTab] = useState("picks");
  const [appState, setAppState] = useState(() => {
    const u = new URLSearchParams(location.search);
    return u.get("state") || window.V2_APP_STATE || "ready";
  });
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("v2-theme") || "light";
    } catch {
      return "light";
    }
  });
  React.useEffect(() => {
    document.body.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("v2-theme", theme);
    } catch {}
  }, [theme]);
  const toggleTheme = () => setTheme(t => t === "dark" ? "light" : "dark");
  window.__v2Theme = {
    theme,
    toggleTheme
  };
  const renderPicks = () => {
    if (appState === "loading") return React.createElement(React.Fragment, null, React.createElement("div", {
      className: "v2-header"
    }, React.createElement("div", {
      className: "v2-header-row"
    }, React.createElement("div", {
      className: "v2-brand"
    }, React.createElement("div", {
      className: "v2-kmark"
    }, "K"), React.createElement("div", null, React.createElement("div", {
      className: "v2-wordmark"
    }, "Betting Edge"), React.createElement("div", {
      className: "v2-subtitle"
    }, "Loading slate\u2026"))))), React.createElement(LoadingState, null));
    if (appState === "error") return React.createElement(React.Fragment, null, React.createElement("div", {
      className: "v2-header"
    }, React.createElement("div", {
      className: "v2-header-row"
    }, React.createElement("div", {
      className: "v2-brand"
    }, React.createElement("div", {
      className: "v2-kmark"
    }, "K"), React.createElement("div", null, React.createElement("div", {
      className: "v2-wordmark"
    }, "Betting Edge"), React.createElement("div", {
      className: "v2-subtitle",
      style: {
        color: "var(--neg)"
      }
    }, "Connection error"))))), React.createElement(ErrorState, {
      onRetry: () => setAppState("ready")
    }));
    if (appState === "empty") return React.createElement(PicksTab, {
      pitchersOverride: []
    });
    return React.createElement(PicksTab, null);
  };
  return React.createElement(React.Fragment, null, tab === "picks" && renderPicks(), tab === "perf" && React.createElement(PerfTab, null), tab === "watch" && React.createElement(SteamTab, null), React.createElement("nav", {
    className: "v2-tabbar"
  }, [["picks", Icon.picks, "Picks", null], ["watch", Icon.steam, "Steam", null], ["perf", Icon.results, "Results", null]].map(([k, ic, l, badge]) => React.createElement("button", {
    key: k,
    className: `v2-tab ${tab === k ? "active" : ""}`,
    onClick: () => setTab(k)
  }, ic, React.createElement("span", null, l), badge != null && React.createElement("span", {
    className: "v2-tab-badge"
  }, badge), tab === k && React.createElement("span", {
    className: "v2-tab-dot active",
    style: {
      background: "var(--accent)"
    }
  })))));
}
const root = ReactDOM.createRoot(document.getElementById("root"));
(async () => {
  try {
    await window.__v2DataPromise;
  } catch {}
  root.render(React.createElement(App, null));
})();