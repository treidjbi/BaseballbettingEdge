/* global React, ReactDOM */
const { useState, useMemo } = React;

const ABBR = {
  "Arizona Diamondbacks":"ARI","Atlanta Braves":"ATL","Baltimore Orioles":"BAL",
  "Boston Red Sox":"BOS","Chicago Cubs":"CHC","Chicago White Sox":"CWS",
  "Cincinnati Reds":"CIN","Cleveland Guardians":"CLE","Colorado Rockies":"COL",
  "Detroit Tigers":"DET","Houston Astros":"HOU","Kansas City Royals":"KC",
  "Los Angeles Angels":"LAA","Los Angeles Dodgers":"LAD","Miami Marlins":"MIA",
  "Milwaukee Brewers":"MIL","Minnesota Twins":"MIN","New York Mets":"NYM",
  "New York Yankees":"NYY","Oakland Athletics":"OAK","Philadelphia Phillies":"PHI",
  "Pittsburgh Pirates":"PIT","San Diego Padres":"SD","San Francisco Giants":"SF",
  "Seattle Mariners":"SEA","St. Louis Cardinals":"STL","Tampa Bay Rays":"TB",
  "Texas Rangers":"TEX","Toronto Blue Jays":"TOR","Washington Nationals":"WSH",
  "Athletics":"OAK"
};
const ab = n => ABBR[n] || n;
const fmtOdds = n => n == null ? "—" : (n > 0 ? `+${n}` : `${n}`);
const isFiniteNumber = (v) => typeof v === "number" && Number.isFinite(v);
const fmtFixedOrDash = (v, digits = 1) => isFiniteNumber(v) ? v.toFixed(digits) : "--";
const PHX_TZ = "America/Phoenix";
const phxDateISO = () => new Intl.DateTimeFormat("en-CA", {
  timeZone: PHX_TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
}).format(new Date());
const fmtTime = iso => {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: PHX_TZ,
  });
};

// ── Tiny inline icons (no external font/web component) ──
const Icon = {
  users: <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor" aria-hidden="true"><circle cx="5" cy="5.5" r="2.3"/><circle cx="11" cy="5.5" r="2"/><path d="M1 13.5c0-2.2 1.8-3.8 4-3.8s4 1.6 4 3.8v.5H1v-.5z"/><path d="M9.2 14c.1-.3.1-.6.1-1 0-1.4-.7-2.6-1.7-3.3.4-.1.8-.2 1.3-.2 2 0 3.5 1.4 3.5 3.3V14H9.2z"/></svg>,
  ball:  <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true"><circle cx="8" cy="8" r="6.2"/><path d="M3.5 4.5c1.3 1.4 2.1 3.2 2.1 5.3 0 1-.2 2-.5 2.9M12.5 4.5c-1.3 1.4-2.1 3.2-2.1 5.3 0 1 .2 2 .5 2.9"/></svg>,
  ump:   <svg viewBox="0 0 16 16" width="13" height="13" fill="currentColor" aria-hidden="true"><circle cx="8" cy="5" r="2.4"/><path d="M3 14c0-2.4 2.2-4.3 5-4.3s5 1.9 5 4.3v.5H3V14z"/></svg>,
  up:    <svg viewBox="0 0 10 10" width="10" height="10" fill="currentColor" aria-hidden="true"><path d="M5 1.5L9 8H1z"/></svg>,
  down:  <svg viewBox="0 0 10 10" width="10" height="10" fill="currentColor" aria-hidden="true"><path d="M5 8.5L1 2h8z"/></svg>,
  live:  <svg viewBox="0 0 8 8" width="8" height="8" fill="currentColor" aria-hidden="true"><circle cx="4" cy="4" r="4"/></svg>,
  bell:  <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3.5 12h9l-1.2-1.6V7.2a3.3 3.3 0 0 0-2.6-3.3v-.4a.7.7 0 0 0-1.4 0v.4A3.3 3.3 0 0 0 4.7 7.2v3.2z"/><path d="M6.5 13.5a1.5 1.5 0 0 0 3 0"/></svg>,
  bellOn: <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor" stroke="none"><path d="M8 1.5a.7.7 0 0 0-.7.7v.4a3.3 3.3 0 0 0-2.6 3.3v3.2L3.5 10.4V12h9v-1.6l-1.2-1.6V7.2a3.3 3.3 0 0 0-2.6-3.3v-.4A.7.7 0 0 0 8 1.5z"/><path d="M6.5 13.5a1.5 1.5 0 0 0 3 0z"/><line x1="1" y1="2" x2="3" y2="4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><line x1="15" y1="2" x2="13" y2="4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><line x1="8" y1="0" x2="8" y2="1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  moon:  <svg viewBox="0 0 16 16" width="15" height="15" fill="currentColor"><path d="M8 1.5A6.5 6.5 0 1 0 14.5 8 5 5 0 0 1 8 1.5z"/></svg>,
  sun:   <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><circle cx="8" cy="8" r="2.8" fill="currentColor"/><path d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3 3l1 1M12 12l1 1M13 3l-1 1M4 12l-1 1"/></svg>,
  refresh:<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 3v4h-4"/><path d="M13.5 7A6 6 0 1 0 14 10"/></svg>,
  picks: <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="10" cy="10" r="7.5"/><path d="M4.5 5.8c1.6 1.7 2.6 4 2.6 6.6 0 1.2-.2 2.4-.6 3.5M15.5 5.8c-1.6 1.7-2.6 4-2.6 6.6 0 1.2.2 2.4.6 3.5"/></svg>,
  steam: <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M5 14l4-4 3 3 4-5"/><path d="M13 8h3v3"/></svg>,
  history: <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4v4h4"/><path d="M4.4 8A6.2 6.2 0 1 0 6 4.1"/><path d="M10 6.5V10l2.4 1.6"/></svg>,
  results:<svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><rect x="3.5" y="9" width="3.5" height="7.5" rx=".6"/><rect x="8.5" y="5" width="3.5" height="11.5" rx=".6"/><rect x="13.5" y="11" width="3.5" height="5.5" rx=".6"/></svg>,
};

function urlBase64ToUint8Array(b64) {
  const padding = '='.repeat((4 - b64.length % 4) % 4);
  const base64 = (b64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}

function usePipelineTrigger() {
  const [state, setState] = useState("idle"); // idle | running | triggered | error

  async function trigger() {
    if (state === "running") return;
    setState("running");
    try {
      const res = await fetch("/.netlify/functions/trigger-pipeline", { method: "POST" });
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

  const title = state === "running"  ? "Running… (~3 min)"
              : state === "triggered" ? "Triggered!"
              : state === "error"     ? "Error — try again"
              : "Refresh pipeline";

  return { trigger, state, title };
}

function useNotifications() {
  const [supported, setSupported] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const swRef = React.useRef(null);

  React.useEffect(() => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
    navigator.serviceWorker.register('/sw.js')
      .then(reg => {
        swRef.current = reg;
        setSupported(true);
        return reg.pushManager.getSubscription();
      })
      .then(existing => setSubscribed(existing != null))
      .catch(() => {});
  }, []);

  async function toggleNotify() {
    const reg = swRef.current;
    if (!reg) return;
    const existing = await reg.pushManager.getSubscription();
    if (existing) {
      await existing.unsubscribe();
      fetch('/.netlify/functions/save-subscription', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: existing.endpoint }),
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
    } catch { return; }
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return;
    try {
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      });
      fetch('/.netlify/functions/save-subscription', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sub),
      }).catch(() => {});
      setSubscribed(true);
    } catch {}
  }

  return { supported, subscribed, toggleNotify };
}

function bestSide(p) {
  if (p.ev_over.adj_ev >= p.ev_under.adj_ev) {
    return { ...p.ev_over, direction: "OVER",  odds: p.best_over_odds,  opening: p.opening_over_odds };
  }
  return   { ...p.ev_under, direction: "UNDER", odds: p.best_under_odds, opening: p.opening_under_odds };
}
function verdictStake(v) {
  if (v === "FIRE 2u") return 2;
  if (v === "FIRE 1u") return 1;
  return 0;
}
const BET_LOG_SECRET_STORAGE = "bbe.betLogSecret";
const BET_LOG_ACCEPTED_STORAGE = "bbe.acceptedBetKeys";
const BET_LOG_BOOK_OPTIONS = [
  "FanDuel",
  "DraftKings",
  "BetMGM",
  "BetRivers",
  "Caesars",
  "Kalshi",
  "theScore Bet",
];
function bookForSide(p, side) {
  return side.direction === "OVER" ? p.best_over_book : p.best_under_book;
}
function slateDateForBetLog() {
  return window.V2_DATA?.date || window.V2_CURRENT_DATE || phxDateISO();
}
function storedBetLogSecret() {
  try { return localStorage.getItem(BET_LOG_SECRET_STORAGE) || ""; } catch { return ""; }
}
function saveBetLogSecret(secret) {
  try { localStorage.setItem(BET_LOG_SECRET_STORAGE, secret); } catch {}
}
function clearBetLogSecret() {
  try { localStorage.removeItem(BET_LOG_SECRET_STORAGE); } catch {}
}
function readLoggedBetKeys() {
  try {
    const parsed = JSON.parse(localStorage.getItem(BET_LOG_ACCEPTED_STORAGE) || "[]");
    return new Set(Array.isArray(parsed) ? parsed.filter(Boolean) : []);
  } catch {
    return new Set();
  }
}
function writeLoggedBetKeys(keys) {
  try { localStorage.setItem(BET_LOG_ACCEPTED_STORAGE, JSON.stringify([...keys].slice(-200))); } catch {}
}
function acceptedBetPitcherKey(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}
function acceptedBetSessionKey(p, side) {
  return [
    "accepted_bet",
    slateDateForBetLog(),
    acceptedBetPitcherKey(p.pitcher),
    String(side.direction || "").toLowerCase(),
  ].join(":");
}
function canonicalBetLogBook(book) {
  const value = String(book || "").trim();
  const normalized = value.toLowerCase().replace(/\s+/g, "");
  if (!normalized) return "";
  if (normalized === "thescore" || normalized === "thescorebet") return "theScore Bet";
  return BET_LOG_BOOK_OPTIONS.find((option) => option.toLowerCase().replace(/\s+/g, "") === normalized) || "";
}
function defaultBetLogBook(book) {
  const value = String(book || "").trim();
  const canonical = canonicalBetLogBook(value);
  return {
    book: canonical || (value ? "Other" : ""),
    bookOther: canonical ? "" : value,
  };
}
function defaultAcceptedBetForm(p, side) {
  const defaultBook = defaultBetLogBook(bookForSide(p, side));
  return {
    line: String(side.k_line ?? p.k_line ?? ""),
    odds: String(side.odds ?? ""),
    book: defaultBook.book,
    bookOther: defaultBook.bookOther,
    units: String(verdictStake(side.verdict) || 1),
    secret: "",
  };
}
function buildAcceptedBetPayload(p, side, { line, odds, book, units }) {
  return {
    slate_date: slateDateForBetLog(),
    pitcher: p.pitcher,
    side: side.direction,
    verdict: side.verdict,
    k_line: line,
    odds,
    book,
    units,
    game_time: p.game_time || null,
    source: "dashboard_manual",
    model_snapshot: {
      lambda: p.lambda ?? null,
      adj_ev: side.adj_ev ?? null,
      ev: side.ev ?? null,
      edge: side.edge ?? null,
      win_prob: side.win_prob ?? null,
      movement_conf: side.movement_conf ?? null,
      quality_gate_level: p.quality_gate_level || null,
    },
    metadata: {
      team: p.team || null,
      opp_team: p.opp_team || null,
      game_state: p.game_state || null,
      ref_book: bookForSide(p, side) || null,
      generated_at: window.V2_DATA?.generated_at || null,
    },
  };
}
function parseBetLogNumber(value) {
  return Number(String(value ?? "").trim().replace(/\u2212/g, "-"));
}
function trackedPicksForPitcher(p) {
  return Array.isArray(p.tracked_picks) ? p.tracked_picks : [];
}
function trackedPillsForCard(p, side) {
  const picks = trackedPicksForPitcher(p);
  if (!picks.length) return [];
  const matchingSide = picks.filter((pick) => pick.direction === side.direction);
  return matchingSide.length > 0 ? matchingSide : picks;
}
function primaryTrackedPick(p) {
  const picks = trackedPicksForPitcher(p);
  if (!picks.length) return null;
  return [...picks].sort((a, b) => (
    verdictStake(b.verdict) - verdictStake(a.verdict) ||
    (b.adj_ev ?? -99) - (a.adj_ev ?? -99)
  ))[0];
}
function sideFromTrackedPick(p, pick) {
  const isOver = pick.direction === "OVER";
  const current = isOver ? p.ev_over : p.ev_under;
  return {
    ...current,
    verdict: pick.verdict || current.verdict,
    direction: pick.direction,
    odds: pick.odds ?? (isOver ? p.best_over_odds : p.best_under_odds),
    opening: isOver ? p.opening_over_odds : p.opening_under_odds,
    adj_ev: pick.adj_ev ?? current.adj_ev,
    edge: pick.edge ?? current.edge,
    ev: pick.ev ?? current.ev,
    result: pick.result ?? current.result,
    k_line: pick.k_line ?? p.k_line,
    status: pick.status,
    locked_at: pick.locked_at,
  };
}
function displaySide(p) {
  const tracked = primaryTrackedPick(p);
  return tracked ? sideFromTrackedPick(p, tracked) : bestSide(p);
}
function trackedMatchesFilter(p, filter) {
  const picks = trackedPicksForPitcher(p);
  if (filter === "FIRE") return picks.some(pick => (pick.verdict || "").startsWith("FIRE"));
  if (filter === "LEAN") return picks.some(pick => pick.verdict === "LEAN");
  return true;
}
// Slate is "past" when the user is viewing an archived YYYY-MM-DD earlier than today.
// Enables W/L badges on cards + grading summary banner at the top of the list.
function isPastSlate() {
  const today   = window.__v2GetAppDate ? window.__v2GetAppDate() : phxDateISO();
  const current = window.V2_CURRENT_DATE || today;
  return current < today;
}
// Result pill for past-date cards. `result` is "win" | "loss" | "push" (from ev_*.result).
function ResultPill({ result }) {
  if (!result) return null;
  const label = result === "win" ? "W" : result === "loss" ? "L" : "P";
  return <span className={`v2-result-pill ${result}`}>{label}</span>;
}
function verdictClass(v, dir) {
  if (v && v.startsWith("FIRE")) return dir === "OVER" ? "fire-over" : "fire";
  if (v === "LEAN") return "lean";
  return "pass";
}
function centsMove(o, c) {
  if (o == null || c == null) return 0;
  const same = (o > 0 && c > 0) || (o < 0 && c < 0);
  if (same) return Math.abs(c - o);
  return (Math.abs(o) - 100) + (Math.abs(c) - 100);
}
function sideCheaper(o, c) {
  const ip = x => x < 0 ? Math.abs(x) / (Math.abs(x) + 100) : 100 / (x + 100);
  return ip(c) < ip(o);
}
function steamInfo(p, dir) {
  const isOver = dir === "OVER";
  const o = isOver ? p.opening_over_odds : p.opening_under_odds;
  const c = isOver ? p.best_over_odds    : p.best_under_odds;
  const cents = centsMove(o, c);
  if (!cents) return null;
  return { cents, steamWith: !sideCheaper(o, c) };
}

function historyDataBase() {
  const isLocal = location.hostname === "localhost" ||
                  location.hostname === "127.0.0.1" ||
                  location.protocol === "file:";
  return isLocal
    ? "data/processed"
    : "https://raw.githubusercontent.com/treidjbi/baseballbettingedge/main/dashboard/data/processed";
}

async function fetchHistorySlate(date) {
  const res = await fetch(`${historyDataBase()}/${date}.json?t=${Date.now()}`);
  if (!res.ok) throw new Error(`history_${date}_${res.status}`);
  return res.json();
}

function normalizeHistorySide(side) {
  return String(side || "").toUpperCase();
}

function historySideFromPitcher(p) {
  if (!p?.ev_over || !p?.ev_under) return null;
  const over = p.ev_over;
  const under = p.ev_under;
  const side = (over.adj_ev ?? -99) >= (under.adj_ev ?? -99)
    ? { ...over, direction: "OVER", odds: p.best_over_odds, opening: p.opening_over_odds }
    : { ...under, direction: "UNDER", odds: p.best_under_odds, opening: p.opening_under_odds };
  return {
    ...side,
    verdict: side.verdict || "PASS",
    k_line: side.k_line ?? p.k_line,
  };
}

function historyRowsFromSlate(slate) {
  const rows = [];
  const pitchers = Array.isArray(slate?.pitchers) ? slate.pitchers : [];
  const byPitcher = new Map(pitchers.map((p) => [String(p.pitcher || "").toLowerCase(), p]));
  const tracked = Array.isArray(slate?.tracked_picks)
    ? slate.tracked_picks
    : pitchers.flatMap((p) => Array.isArray(p.tracked_picks) ? p.tracked_picks : []);

  if (tracked.length) {
    for (const pick of tracked) {
      const p = byPitcher.get(String(pick.pitcher || "").toLowerCase()) || {};
      const direction = normalizeHistorySide(pick.display_side || pick.side);
      const sideForSteam = direction || "OVER";
      const steam = p.pitcher ? steamInfo(p, sideForSteam) : null;
      rows.push({
        date: pick.date || slate.date,
        pitcher: pick.pitcher || p.pitcher || "",
        team: pick.team || p.team || "",
        opp_team: pick.opp_team || p.opp_team || "",
        direction,
        verdict: pick.display_verdict || pick.locked_verdict || pick.verdict || "PASS",
        k_line: pick.display_k_line ?? pick.locked_k_line ?? pick.k_line ?? p.k_line,
        odds: pick.display_odds ?? pick.locked_odds ?? pick.odds,
        adj_ev: pick.display_adj_ev ?? pick.locked_adj_ev ?? pick.adj_ev ?? 0,
        edge: pick.edge ?? null,
        result: pick.result || p.ev_over?.result || p.ev_under?.result || null,
        actual_ks: pick.actual_ks ?? p.actual_ks ?? p.result?.final_k ?? null,
        pnl: pick.pnl ?? p.result?.units_won ?? null,
        game_time: pick.game_time || p.game_time || null,
        quality_gate_level: pick.quality_gate_level || p.quality_gate_level || "clean",
        steam,
      });
    }
  } else {
    for (const p of pitchers) {
      const side = historySideFromPitcher(p);
      if (!side) continue;
      const steam = steamInfo(p, side.direction);
      rows.push({
        date: slate.date,
        pitcher: p.pitcher || "",
        team: p.team || "",
        opp_team: p.opp_team || "",
        direction: side.direction,
        verdict: side.verdict,
        k_line: side.k_line ?? p.k_line,
        odds: side.odds,
        adj_ev: side.adj_ev ?? 0,
        edge: side.edge ?? side.ev ?? null,
        result: side.result || null,
        actual_ks: p.actual_ks ?? p.result?.final_k ?? null,
        pnl: p.result?.units_won ?? null,
        game_time: p.game_time || null,
        quality_gate_level: p.quality_gate_level || "clean",
        steam,
      });
    }
  }

  return rows;
}

function impliedProb(odds) {
  if (odds == null) return null;
  return odds < 0 ? Math.abs(odds) / (Math.abs(odds) + 100) : 100 / (odds + 100);
}

function getMovementHelpers() {
  return window.V2MovementHelpers || {};
}

function MovementChart({ movement }) {
  if (!movement?.ready) {
    return <div className="v2-move-empty">Not enough line history yet</div>;
  }

  const points = movement.points || [];
  const width = 320;
  const height = 92;
  const topPad = 10;
  const lineBandTop = 58;
  const lineBandBottom = 82;
  const odds = points.map((p) => p.odds).filter((v) => v != null);
  const lines = points.map((p) => p.kLine);
  const minOdds = Math.min(...odds);
  const maxOdds = Math.max(...odds);
  const minLine = Math.min(...lines);
  const maxLine = Math.max(...lines);
  const xFor = (idx) => points.length === 1 ? width / 2 : (idx / (points.length - 1)) * width;
  const yForOdds = (val) => {
    if (val == null || minOdds === maxOdds) return topPad + 18;
    return topPad + ((maxOdds - val) / (maxOdds - minOdds)) * 36;
  };
  const yForLine = (val) => {
    if (minLine === maxLine) return (lineBandTop + lineBandBottom) / 2;
    return lineBandTop + ((maxLine - val) / (maxLine - minLine)) * (lineBandBottom - lineBandTop);
  };

  const oddsPath = points
    .map((pt, idx) => `${idx === 0 ? "M" : "L"} ${xFor(idx).toFixed(1)} ${yForOdds(pt.odds).toFixed(1)}`)
    .join(" ");
  const linePath = points
    .map((pt, idx) => {
      if (idx === 0) {
        return `M ${xFor(idx).toFixed(1)} ${yForLine(pt.kLine).toFixed(1)}`;
      }
      const prev = points[idx - 1];
      return `L ${xFor(idx).toFixed(1)} ${yForLine(prev.kLine).toFixed(1)} L ${xFor(idx).toFixed(1)} ${yForLine(pt.kLine).toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="v2-move-chart-wrap">
      <svg className="v2-move-chart" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <path d={oddsPath} className="v2-move-odds-line" />
        <path d={linePath} className="v2-move-kline-step" />
        {points.map((pt, idx) => (
          <React.Fragment key={`${pt.t}-${idx}`}>
            <circle
              className={`v2-move-point ${idx === 0 ? "start" : idx === points.length - 1 ? "end" : ""}`}
              cx={xFor(idx)}
              cy={yForOdds(pt.odds)}
              r={idx === points.length - 1 ? 3 : 2.2}
            />
            <circle
              className="v2-move-line-point"
              cx={xFor(idx)}
              cy={yForLine(pt.kLine)}
              r={1.6}
            />
          </React.Fragment>
        ))}
      </svg>
      <div className="v2-move-legend">
        <span className="odds">picked-side odds</span>
        <span className="line">K line</span>
      </div>
    </div>
  );
}

// ── Verdict badge (big, two-line) ──
function VerdictBadge({ side }) {
  const v = side.verdict;
  if (v === "PASS") {
    return <div className="v2-verdict pass">PASS</div>;
  }
  const cls = verdictClass(v, side.direction);
  const isOver = side.direction === "OVER";
  const dirArrow = isOver ? Icon.up : Icon.down;
  const label = v === "LEAN" ? "LEAN" : v.replace("FIRE ", "").toUpperCase(); // "1U" / "2U" / "LEAN"
  return (
    <div className={`v2-verdict ${cls}`}>
      <span className="dir">{dirArrow} {side.direction}</span>
      <span className="label">{v === "LEAN" ? "LEAN" : `FIRE \u00B7 ${label}`}</span>
    </div>
  );
}

// ── Projection bar — shows line vs lambda ──
function ProjBar({ line, lambda }) {
  // Scale: min/max around line ± 3
  const lo = line - 3;
  const hi = line + 3;
  const cl = x => Math.max(0, Math.min(1, (x - lo) / (hi - lo)));
  return (
    <div className="v2-projbar">
      <div className="line" style={{ left: `${cl(line) * 100}%` }} />
      <div className="proj" style={{ left: `${cl(lambda) * 100}%` }} />
    </div>
  );
}

// ── "Why" pill row ──
function WhyPills({ p, side }) {
  const stats = [];
  const oppK = p.opp_k_rate;
  const oppVs = ((oppK - 0.227) / 0.227) * 100;
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
      v: `${p.ump_k_adj > 0 ? "+" : ""}${(p.ump_k_adj).toFixed(2)}`,
      tone: (side.direction === "OVER" ? p.ump_k_adj > 0 : p.ump_k_adj < 0) ? "pos" : "neg",
      title: `Umpire K-adjustment ${p.ump_k_adj > 0 ? "+" : ""}${p.ump_k_adj.toFixed(2)} K/g`
    });
  }
  const steam = steamInfo(p, side.direction);
  return (
    <div className="v2-why v2-why-compact">
      {stats.map((s, i) => (
        <span key={i} className={`v2-stat ${s.tone}`} title={s.title}>
          {s.icon}
          <span className="v">{s.v}</span>
        </span>
      ))}
      {steam && (
        <span className={`v2-stat ${steam.steamWith ? "pos" : "neg"}`} title={`Steam ${steam.steamWith ? "with" : "against"} the pick, ${steam.cents}¢`}>
          {steam.steamWith ? Icon.up : Icon.down}
          <span className="v">{steam.cents}¢</span>
        </span>
      )}
    </div>
  );
}

// ── Pick card ──
function marketDisplayEnabled() {
  return window.V2_MARKET_DISPLAY?.enabled === true;
}

function marketDisplayForSide(p, side) {
  if (!marketDisplayEnabled() || !p?.market_display || !side?.direction) return null;
  return p.market_display[side.direction] || null;
}

function marketActionTone(row) {
  if (!row) return "neutral";
  if (row.action_label === "stale" || row.action_label === "monitor") return "warn";
  if (row.action_label === "market_disagrees") return "neg";
  return "pos";
}

function marketActionText(row) {
  if (!row) return "Market pending";
  const labels = {
    shop_price: "Shop price",
    playable: "Playable",
    market_agrees: "Market with us",
    market_disagrees: "Market against",
    stale: "Market stale",
    monitor: "Monitor",
  };
  return labels[row.action_label] || "Monitor";
}

function marketConsensusText(value) {
  const key = String(value || "").toLowerCase();
  if (key.includes("toward") || key.includes("with")) return "with pick";
  if (key.includes("away") || key.includes("against")) return "against pick";
  if (key) return key.replace(/_/g, " ");
  return "no consensus";
}

function marketValueText(value) {
  const key = String(value || "").toLowerCase();
  if (key.includes("better")) return "better now";
  if (key.includes("worse")) return "worse now";
  if (key.includes("same") || key.includes("flat")) return "flat";
  if (key) return key.replace(/_/g, " ");
  return "unknown";
}

function bestMarketText(row) {
  if (!row) return "No live row yet";
  const book = row.best_book || "Best book";
  const line = row.best_line ?? row.main_line;
  const lineText = line == null ? "" : ` ${line}K`;
  return `${book}${lineText} ${fmtOdds(row.best_odds)}`;
}

function fairOddsFromProbability(prob) {
  if (!isFiniteNumber(prob) || prob <= 0 || prob >= 1) return null;
  if (prob >= 0.5) return Math.round(-100 * prob / (1 - prob));
  return Math.round(100 * (1 - prob) / prob);
}

function priceCushion(liveOdds, fairOdds) {
  if (!isFiniteNumber(liveOdds) || !isFiniteNumber(fairOdds)) return null;
  return Math.round(liveOdds - fairOdds);
}

function formatCents(value) {
  if (!isFiniteNumber(value)) return "--";
  return `${value > 0 ? "+" : ""}${value}c`;
}

function MarketCardStrip({ p, side }) {
  if (!marketDisplayEnabled() || side.verdict === "PASS") return null;
  const row = marketDisplayForSide(p, side);
  const tone = marketActionTone(row);
  return (
    <div className={`v2-market-strip ${tone}`}>
      <span className="v2-market-strip-k">Market</span>
      <span className="v2-market-strip-main">{marketActionText(row)}</span>
      <span className="v2-market-strip-sub">{bestMarketText(row)}</span>
    </div>
  );
}

function MarketDecisionPanel({ p, side }) {
  if (!marketDisplayEnabled() || side.verdict === "PASS") return null;
  const row = marketDisplayForSide(p, side);
  const refBook = bookForSide(p, side) || "Model ref";
  const fairOdds = fairOddsFromProbability(side.win_prob);
  const cushion = row ? priceCushion(row.best_odds, fairOdds) : null;
  const observed = row?.observed_at ? fmtTime(row.observed_at) : "--";
  const books = row?.book_count ?? row?.books_seen?.length ?? row?.book_rows?.length ?? null;

  return (
    <div className="v2-sheet-section">
      <div className="h">Live market decision</div>
      {!row ? (
        <div className="v2-market-empty">No live market row is attached for this pick yet.</div>
      ) : (
        <>
          <div className={`v2-market-decision ${marketActionTone(row)}`}>
            <div>
              <div className="v2-market-eyebrow">Decision read</div>
              <div className="v2-market-decision-title">{marketActionText(row)}</div>
            </div>
            <div className="v2-market-decision-price">
              <span>{row.best_book || "Best book"}</span>
              <b>{row.best_line ?? row.main_line ?? "--"}K {fmtOdds(row.best_odds)}</b>
            </div>
          </div>
          <div className="v2-market-grid">
            <div className="v2-market-cell">
              <span>Model ref</span>
              <b>{refBook} {side.k_line ?? p.k_line}K {fmtOdds(side.odds)}</b>
            </div>
            <div className="v2-market-cell">
              <span>Model fair</span>
              <b>{fmtOdds(fairOdds)} {cushion != null && <em>{formatCents(cushion)}</em>}</b>
            </div>
            <div className="v2-market-cell">
              <span>Market pulse</span>
              <b>{marketConsensusText(row.market_consensus)}</b>
            </div>
            <div className="v2-market-cell">
              <span>Bet value</span>
              <b>{marketValueText(row.bet_value_consensus)}</b>
            </div>
            <div className="v2-market-cell">
              <span>Freshness</span>
              <b>{row.freshness_status || "unknown"} <em>{observed}</em></b>
            </div>
            <div className="v2-market-cell">
              <span>Books</span>
              <b>{books == null ? "--" : books}{row.broad_confirmation ? " broad" : ""}</b>
            </div>
          </div>
          {row.book_rows?.length > 0 && (
            <div className="v2-market-books">
              {row.book_rows.slice(0, 4).map((book, idx) => (
                <div className="v2-market-book-row" key={`${book.bookmaker_key || book.bookmaker_title}-${idx}`}>
                  <span>{book.bookmaker_title || book.bookmaker_key || "Book"}</span>
                  <b>{book.line ?? "--"}K {fmtOdds(book.odds)}</b>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function qualityLabel(level) {
  if (level === "blocked") return "Current blocked";
  if (level === "capped") return "Current capped";
  return "Current clean";
}

function qualityReason(p, side) {
  if (p.verdict_cap_reason) return p.verdict_cap_reason;
  const reasons = side.quality_gate_reasons || p.quality_gate_reasons || [];
  if (reasons.length) return reasons.join(", ");
  const flags = p.input_quality_flags || [];
  return flags.length ? flags.join(", ") : "";
}

function PickCard({ p, onOpen }) {
  const side = displaySide(p);
  const tracked = trackedPillsForCard(p, side);
  const cls = verdictClass(side.verdict, side.direction);
  const started = p.game_state !== "pregame";
  const directionMod =
    side.verdict === "PASS"
      ? "pass"
      : side.direction === "OVER"
        ? "over-pick"
        : "under-pick";
  const cardMod = started ? "final" : `${cls} ${directionMod}`;
  // Past-date: show the W/L pill inline with the verdict badge — but only for
  // picks we would have actually played. PASS cards don't get a result pill
  // (matches the grading-summary banner, which also excludes PASS).
  const past = isPastSlate();
  const showResult = past && side.verdict !== "PASS";

  return (
    <article
      className={`v2-card ${cardMod}`}
      onClick={() => onOpen && onOpen(p)}
      role="button" tabIndex={0}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onOpen && onOpen(p); }}
    >
      <div className="v2-card-top">
        <div className="v2-teamblock">
          <div className="v2-matchup">
            <span>{ab(p.team)}</span>
            <span className="vs">vs</span>
            <span>{ab(p.opp_team)}</span>
            <span className="time">
              {p.game_state === "in_progress" ? (
                <span style={{display:"inline-flex",gap:5,alignItems:"center"}}>
                  <span className="v2-livedot"/>LIVE
                </span>
              ) : fmtTime(p.game_time)}
            </span>
          </div>
          <div className="v2-pitcher-name">
            {p.pitcher}
            <span className="v2-pitcher-throws">{p.pitcher_throws}HP</span>
          </div>
        </div>
        <div style={{display:"flex",alignItems:"center"}}>
          <VerdictBadge side={side} />
          {showResult && <ResultPill result={side.result} />}
        </div>
      </div>

      <div className="v2-line">
        <div className="v2-line-cell">
          <div className="v2-line-label">Line · {side.direction}</div>
          <div className="v2-line-value">{side.k_line ?? p.k_line}<span style={{fontSize:14,opacity:.5}}> K</span></div>
          <div className="v2-line-sub mono">{fmtOdds(side.odds)} · {side.direction === "OVER" ? (p.best_over_book || "book") : (p.best_under_book || "book")}</div>
        </div>
        <div className="v2-line-cell">
          <div className="v2-line-label">Projection</div>
          <div className="v2-line-value">{p.lambda.toFixed(2)}</div>
          <ProjBar line={side.k_line ?? p.k_line} lambda={p.lambda} />
        </div>
        <div className="v2-line-cell">
          <div className="v2-line-label">EV ROI · Edge</div>
          <div className={`v2-line-value ${side.adj_ev > 0 ? "pos" : "neg"}`}>
            {side.adj_ev > 0 ? "+" : ""}{(side.adj_ev * 100).toFixed(1)}%
          </div>
          <div className="v2-line-sub mono">
            edge {(side.edge ?? side.ev) > 0 ? "+" : ""}{(((side.edge ?? side.ev) || 0) * 100).toFixed(1)}% · p = {(side.win_prob * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      <MarketCardStrip p={p} side={side} />

      {tracked.length > 0 && (
        <div className="v2-tracked-row">
          {tracked.map((pick, idx) => (
            <span key={`${pick.direction}-${idx}`} className={`v2-tracked-pill ${pick.status === "locked" ? "locked" : ""}`}>
              {pick.status === "locked" ? "Locked pick" : "Tracked pick"} {pick.direction} {pick.k_line ?? p.k_line} · {pick.verdict}
            </span>
          ))}
        </div>
      )}

      {p.quality_gate_level && p.quality_gate_level !== "clean" && (
        <div className="v2-tracked-row">
          <span className={`v2-tracked-pill ${p.quality_gate_level === "blocked" ? "locked" : ""}`}>
            {qualityLabel(p.quality_gate_level)}
          </span>
          {side.raw_verdict && side.raw_verdict !== side.verdict && (
            <span className="v2-tracked-pill">
              Raw model {side.raw_verdict}
            </span>
          )}
        </div>
      )}

      <WhyPills p={p} side={side} />
    </article>
  );
}

// ── Date scroller — renders 3 days back → 3 days forward from slate date ──
function DateBar() {
  const today = window.__v2GetAppDate ? window.__v2GetAppDate() : phxDateISO();
  const current = window.V2_CURRENT_DATE || today;
  const meta = window.V2_DATE_META || {};
  const archive = new Set(Object.keys(meta).concat(
    (window.V2_DATES || []).map(d => typeof d === "string" ? d : d.date)
  ));
  const parse = s => { const [y, m, d] = s.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d)); };
  const fmt   = d => d.toISOString().slice(0, 10);
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
      losses: meta[iso]?.losses ?? 0,
    });
  }
  const navigate = iso => {
    const u = new URL(location.href);
    if (iso === today) u.searchParams.delete("date"); else u.searchParams.set("date", iso);
    location.href = u.toString();
  };
  return (
    <div className="v2-datebar">
      {entries.map((x) => {
        const isActive = x.iso === current;
        const clickable = x.isToday || x.archived;
        const isPast = x.archived && !x.isToday;
        const dotCls = isPast && (x.wins > 0 || x.losses > 0)
          ? (x.wins >= x.losses ? " past-win" : " past-loss")
          : "";
        const cls = "v2-datepill" + (isActive ? " today" : "") + dotCls;
        return (
          <button
            key={x.iso}
            type="button"
            className={cls}
            style={{ opacity: clickable ? 1 : 0.35, cursor: clickable ? "pointer" : "default" }}
            onClick={clickable ? () => navigate(x.iso) : undefined}
            disabled={!clickable}
            aria-current={isActive ? "date" : undefined}
            aria-label={`${x.dow} ${x.iso}`}
          >
            <span className="dow">{x.dow}</span>
            <span className="d">{x.d}</span>
          </button>
        );
      })}
    </div>
  );
}

// ── Pick detail sheet ──
function PickDetail({ p, onClose }) {
  if (!p) return null;
  const sideOver = { ...p.ev_over, direction: "OVER", odds: p.best_over_odds, opening: p.opening_over_odds };
  const sideUnder = { ...p.ev_under, direction: "UNDER", odds: p.best_under_odds, opening: p.opening_under_odds };
  const best = displaySide(p);
  const displayOver = best.direction === "OVER" ? best : sideOver;
  const displayUnder = best.direction === "UNDER" ? best : sideUnder;
  const helpers = getMovementHelpers();
  const [showFactorDetails, setShowFactorDetails] = useState(false);
  const [betLogState, setBetLogState] = useState("idle");
  const [betTicketOpen, setBetTicketOpen] = useState(false);
  const [betLogError, setBetLogError] = useState("");
  const [betForm, setBetForm] = useState(() => defaultAcceptedBetForm(p, best));
  const [loggedBetKeys, setLoggedBetKeys] = useState(() => readLoggedBetKeys());
  const factorGroups = useMemo(() => {
    const buildFactorGroups = window.V2FactorDetails?.buildFactorGroups;
    return buildFactorGroups ? buildFactorGroups(p, best.direction) : [];
  }, [p, best.direction]);
  const steam = steamInfo(p, best.direction) || { cents: 0, steamWith: false };
  const movement = helpers.buildPickedSideMovement
    ? helpers.buildPickedSideMovement(window.V2_STEAM_RAW || { snapshots: [] }, {
        pitcher: p.pitcher,
        direction: best.direction,
        selectedBook: best.direction === "OVER" ? p.best_over_book : p.best_under_book,
        openingLine: p.opening_line,
        openingOdds: best.direction === "OVER" ? p.opening_over_odds : p.opening_under_odds,
      })
    : { ready: false, points: [], reason: "helpers_missing" };
  const movementSummary = helpers.summarizeLineMovement
    ? helpers.summarizeLineMovement(movement)
    : null;

  // ESC to close
  React.useEffect(() => {
    const h = (e) => {
      if (e.key !== "Escape") return;
      if (betTicketOpen) closeBetTicket();
      else onClose();
    };
    window.addEventListener("keydown", h);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", h); document.body.style.overflow = ""; };
  }, [onClose, betTicketOpen, betLogState]);

  React.useEffect(() => {
    setBetTicketOpen(false);
    setBetLogState("idle");
    setBetLogError("");
    setBetForm(defaultAcceptedBetForm(p, best));
  }, [p.pitcher, best.direction, best.k_line, best.odds, best.verdict]);

  const SideCard = ({ s: rawSide }) => {
    const s = {
      ...rawSide,
      adj_ev: isFiniteNumber(rawSide.adj_ev) ? rawSide.adj_ev : 0,
      win_prob: isFiniteNumber(rawSide.win_prob) ? rawSide.win_prob : 0,
      ev: isFiniteNumber(rawSide.ev) ? rawSide.ev : 0,
      edge: isFiniteNumber(rawSide.edge) ? rawSide.edge : null,
    };
    const picked = s.direction === best.direction;
    const adjEv = isFiniteNumber(s.adj_ev) ? s.adj_ev : null;
    const winProb = isFiniteNumber(s.win_prob) ? s.win_prob : null;
    const edgeVal = isFiniteNumber(s.edge ?? s.ev) ? (s.edge ?? s.ev) : null;
    const pos = adjEv != null && adjEv > 0;
    return (
      <div className={`v2-side-card ${picked ? "picked" : ""}`}>
        {picked && <span className="badge-mini">PICK</span>}
        <div className="dir">{s.direction} {s.k_line ?? p.k_line}</div>
        <div className="odds">{fmtOdds(s.odds)} · open {fmtOdds(s.opening)}</div>
        <div className={`ev ${adjEv == null ? "" : pos ? "pos" : "neg"}`}>
          {adjEv == null ? "--" : `${pos ? "+" : ""}${(adjEv * 100).toFixed(1)}%`}
        </div>
        <div className="wp">
          p = {(s.win_prob * 100).toFixed(1)}% · edge {((s.edge ?? s.ev) || 0) > 0 ? "+" : ""}{((((s.edge ?? s.ev) || 0) * 100).toFixed(1))}%
        </div>
      </div>
    );
  };

  // Stat deltas vs league average (rough thresholds)
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
  const umpireName = p.umpire || null;
  const umpireHasRating = p.umpire_has_rating === true || ump !== 0;

  // Whether each stat supports the pick direction
  const supportsUnder = best.direction === "UNDER";
  const oppSupports = oppDelta == null ? null : supportsUnder ? oppDelta < 0 : oppDelta > 0;
  const k9Supports = k9Delta == null ? null : supportsUnder ? k9Delta < 0 : k9Delta > 0;
  const umpSupports = umpireHasRating && (supportsUnder ? ump < 0 : ump > 0);

  // State flags
  const isLive = p.game_state === "in_progress";
  const isFinal = p.game_state === "final";
  const isPass = best.verdict === "PASS";
  const live = p.live;
  const result = p.result;
  const canLogBet = !isPass && !isFinal;
  const needsBetLogSecret = !storedBetLogSecret();
  const currentBetLogKey = acceptedBetSessionKey(p, best);
  const betAlreadyLogged = loggedBetKeys.has(currentBetLogKey);

  function updateBetForm(field, value) {
    setBetForm((prev) => ({ ...prev, [field]: value }));
    setBetLogError("");
  }

  function openBetTicket() {
    if (!canLogBet || betAlreadyLogged) return;
    setBetTicketOpen(true);
    setBetLogError("");
    if (betLogState === "saved") setBetLogState("idle");
  }

  function closeBetTicket() {
    if (betLogState === "saving") return;
    setBetTicketOpen(false);
    setBetLogError("");
    setBetLogState("idle");
  }

  async function handleAcceptedBetSave(e) {
    e.preventDefault();
    if (!canLogBet || betLogState === "saving" || betAlreadyLogged) return;

    const line = parseBetLogNumber(betForm.line);
    const odds = parseBetLogNumber(betForm.odds);
    const units = parseBetLogNumber(betForm.units);
    const book = String(betForm.book === "Other" ? betForm.bookOther : betForm.book || "").trim();
    const secret = storedBetLogSecret() || String(betForm.secret || "").trim();
    if (!Number.isFinite(line) || !Number.isFinite(odds) || !book || !Number.isFinite(units) || units <= 0) {
      setBetLogError("Check line, odds, book, and units before saving.");
      return;
    }
    if (!secret) {
      setBetLogError("Enter the bet log key before saving.");
      return;
    }

    setBetLogState("saving");
    try {
      const response = await fetch("/api/accepted-bets", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-bet-log-secret": secret,
        },
        body: JSON.stringify(buildAcceptedBetPayload(p, best, {
          line,
          odds: Math.trunc(odds),
          book,
          units,
        })),
      });
      if (response.status === 401) {
        clearBetLogSecret();
        setBetForm((prev) => ({ ...prev, secret: "" }));
        setBetLogError("Bet log key was rejected.");
        setBetLogState("error");
        return;
      }
      if (!response.ok) throw new Error(`accepted_bet_failed:${response.status}`);
      saveBetLogSecret(secret);
      setLoggedBetKeys((prev) => {
        const next = new Set(prev);
        next.add(currentBetLogKey);
        writeLoggedBetKeys(next);
        return next;
      });
      setBetLogState("saved");
      setBetLogError("");
      setTimeout(() => {
        setBetTicketOpen(false);
        setBetLogState("idle");
      }, 1800);
    } catch {
      setBetLogError("Could not save the bet. Try again in a minute.");
      setBetLogState("error");
    }
  }

  return ReactDOM.createPortal(
    <>
      <div className="v2-sheet-backdrop" onClick={onClose} />
      <div className="v2-sheet" role="dialog" aria-modal="true">
        <div className="v2-sheet-grip" />
        <div className="v2-sheet-head">
          <div>
            <div className="meta">
              {ab(p.team)} vs {ab(p.opp_team)} · {isLive ? "LIVE" : isFinal ? "FINAL" : fmtTime(p.game_time)}
            </div>
            <div className="pitcher">
              {p.pitcher}<span className="throws">{p.pitcher_throws}HP</span>
            </div>
          </div>
          <button className="v2-sheet-close" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M3 3l10 10M13 3L3 13"/></svg>
          </button>
        </div>

        {/* ── LIVE state: current K progress ── */}
        {isLive && live && (
          <div className="v2-sheet-state v2-sheet-live">
            <div className="state-head">
              <span className="pulse" />
              <span className="state-lbl">LIVE · {live.innings} IP · {live.pitches} pitches</span>
            </div>
            <div className="live-k">
              <span className="live-k-num">{live.current_k}</span>
              <span className="live-k-sep">/</span>
              <span className="live-k-line">{p.k_line}</span>
              <span className="live-k-lbl">K</span>
            </div>
            <div className="live-meta">
              Projected final: <b>{fmtFixedOrDash(live.proj_final_k, 1)} K</b>
              <span className={`live-verdict ${isFiniteNumber(live.proj_final_k) && kLine != null && live.proj_final_k > kLine ? "over" : "under"}`}>
                {live.proj_final_k > p.k_line ? "→ OVER pace" : "→ UNDER pace"}
              </span>
            </div>
          </div>
        )}
        {isLive && !live && (
          <div className="v2-sheet-state v2-sheet-live">
            <div className="state-head">
              <span className="pulse" />
              <span className="state-lbl">LIVE · game in progress</span>
            </div>
            <div className="live-meta">Live K tracking not wired yet — pipeline does not hydrate in-game stats.</div>
          </div>
        )}

        {/* ── FINAL state: result ── */}
        {isFinal && !result && (
          <div className="v2-sheet-state v2-sheet-final outcome-pass">
            <div className="state-head"><span className="state-lbl">FINAL</span></div>
            <div className="final-meta">Grading not available in today's snapshot — check Results tab.</div>
          </div>
        )}
        {isFinal && result && (
          <div className={`v2-sheet-state v2-sheet-final outcome-${result.outcome}`}>
            <div className="state-head">
              <span className="state-lbl">FINAL · {result.final_k} K</span>
            </div>
            {result.outcome === "pass" ? (
              <>
                <div className="final-outcome">NO BET</div>
                <div className="final-meta">
                  Model found no edge on either side. Line closed at {p.k_line}, final {result.final_k} K
                  {result.final_k > p.k_line ? " · OVER hit" : result.final_k < p.k_line ? " · UNDER hit" : " · push"}.
                </div>
              </>
            ) : (
              <>
                <div className="final-outcome">
                  {result.outcome === "win" ? "WIN" : result.outcome === "loss" ? "LOSS" : "PUSH"}
                  <span className={`final-units ${result.units_won >= 0 ? "pos" : "neg"}`}>
                    {result.units_won >= 0 ? "+" : ""}{result.units_won.toFixed(2)}u
                  </span>
                </div>
                <div className="final-meta">
                  {result.side_taken?.toUpperCase()} {result.line_at_bet} @ {fmtOdds(result.odds_at_bet)} · {result.units_risked}u risked
                </div>
              </>
            )}
          </div>
        )}

        {/* ── PASS (pregame): no edge ── */}
        {isPass && !isLive && !isFinal && (
          <div className="v2-sheet-state v2-sheet-pass">
            <div className="state-head">
              <span className="state-lbl">NO EDGE</span>
            </div>
            <div className="pass-copy">
              Model projection ({fmtFixedOrDash(lambda, 2)} K) is too close to the line ({kLine ?? "--"}) on both sides.
              Skipping this one.
            </div>
          </div>
        )}

        <div className="v2-sheet-section">
          <div className="h">Sides · EV ROI comparison</div>
          <div className="v2-sides">
            <SideCard s={displayOver} />
            <SideCard s={displayUnder} />
          </div>
        </div>

        <MarketDecisionPanel p={p} side={best} />

        <div className="v2-sheet-section">
          <div className="h">Projection</div>
          <div className="v2-stat-row">
            <span className="lbl">Line (K)</span>
            <span className="val">{kLine ?? "--"}</span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Model λ</span>
            <span className="val">{fmtFixedOrDash(lambda, 2)}</span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Edge</span>
            <span className={`val ${lambda == null || kLine == null ? "" : lambda > kLine ? "pos" : "neg"}`}>
              {lambda == null || kLine == null ? "--" : `${lambda > kLine ? "+" : ""}${(lambda - kLine).toFixed(2)} K`}
            </span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Expected IP</span>
            <span className="val">{fmtFixedOrDash(avgIp, 1)}</span>
          </div>
        </div>

        <div className="v2-sheet-section">
          <div className="h">Why this bet</div>
          <div className="v2-stat-row">
            <span className="lbl">{Icon.users} Lineup</span>
            {p.lineup_used ? (
              <span className="val pos">Confirmed</span>
            ) : (
              <span className="val" style={{color: "var(--ink-dim)"}}>Projected</span>
            )}
          </div>
          <div className="v2-stat-row">
            <span className="lbl">{Icon.ump} Umpire</span>
            {umpireHasRating ? (
              <span className={`val ${umpSupports ? "pos" : "neg"}`}>
                Confirmed
                <span className="delta">{ump > 0 ? "+" : ""}{ump.toFixed(2)}</span>
              </span>
            ) : umpireName ? (
              <span className="val" style={{color: "var(--ink-dim)"}}>
                {umpireName}
                <span className="delta">neutral</span>
              </span>
            ) : (
              <span className="val" style={{color: "var(--ink-dim)"}}>TBA</span>
            )}
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Park factor</span>
            {parkFactor != null ? (
              <span className={`val ${helpers.parkFactorTone ? helpers.parkFactorTone(parkFactor, best.direction) : ""}`}>
                {parkFactor.toFixed(2)}
              </span>
            ) : (
              <span className="val" style={{color: "var(--ink-dim)"}}>Unknown</span>
            )}
          </div>
          <button
            type="button"
            className="v2-factor-toggle"
            aria-expanded={showFactorDetails}
            aria-controls="v2-factor-details"
            onClick={() => setShowFactorDetails((prev) => !prev)}
          >
            {showFactorDetails ? "Hide factor details" : "Show factor details"}
          </button>
          {showFactorDetails && (
            <div className="v2-factor-panel" id="v2-factor-details">
              {factorGroups.map((group) => (
                <div className="v2-factor-group" key={group.key}>
                  <div className="v2-factor-group-h">{group.label}</div>
                  <div className="v2-factor-rows">
                    {group.rows.map((row) => (
                      <div className="v2-factor-row" key={row.key}>
                        <div className="v2-factor-row-top">
                          <span className="v2-factor-label">{row.label}</span>
                          <span className={`v2-factor-pill ${row.status}`}>{row.status}</span>
                        </div>
                        <div className={`v2-factor-value ${row.tone ? row.tone : ""}`}>{row.value}</div>
                        {row.note && <div className="v2-factor-note">{row.note}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
          <div className="v2-stat-row">
            <span className="lbl">{Icon.users} Opp. K-rate (bats)</span>
            <span className={`val ${oppSupports == null ? "" : oppSupports ? "pos" : "neg"}`}>
              {oppKRate == null ? "--" : `${(oppKRate * 100).toFixed(1)}%`}
              {oppDelta != null && <span className="delta">{oppDelta >= 0 ? "+" : ""}{oppDelta.toFixed(1)} vs lg</span>}
            </span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">{Icon.ball} Recent K/9 (L5)</span>
            <span className={`val ${k9Supports == null ? "" : k9Supports ? "pos" : "neg"}`}>
              {fmtFixedOrDash(recentK9, 1)}
              {k9Delta != null && <span className="delta">{k9Delta >= 0 ? "+" : ""}{k9Delta.toFixed(1)} vs lg</span>}
            </span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Season K/9</span>
            <span className="val">{fmtFixedOrDash(seasonK9, 1)}</span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Career K/9</span>
            <span className="val">{fmtFixedOrDash(careerK9, 1)}</span>
          </div>
        </div>

        <div className="v2-sheet-section">
          <div className="h">
            {`${movement.book || (best.direction === "OVER" ? p.best_over_book : p.best_under_book) || "Market"} · ${best.direction} · open to now`}
            {movementSummary?.lineMoved && (
              <span className="v2-line-move-badge">
                {`line moved ${movementSummary.openingLine} -> ${movementSummary.currentLine}`}
              </span>
            )}
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Opening line</span>
            <span className="val">{p.opening_line} · {fmtOdds(p.opening_over_odds)}/{fmtOdds(p.opening_under_odds)}</span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Current line</span>
            <span className="val">{p.k_line} · {fmtOdds(sideOver.odds)}/{fmtOdds(sideUnder.odds)}</span>
          </div>
          <MovementChart movement={movement} />
          <div style={{fontSize:11, color:"var(--ink-dim)", marginTop:6, fontFamily:"JetBrains Mono, monospace"}}>
            {steam.cents > 0 ? `${steam.cents}¢ ${steam.steamWith ? "with" : "against"} the pick` : "No steam signal at the picked side price"}
          </div>
        </div>

        <div className="v2-sheet-section">
          <div className="h">Model confidence</div>
          <div className="v2-stat-row">
            <span className="lbl">Actionable verdict</span>
            <span className="val">{best.verdict}</span>
          </div>
          {best.raw_verdict && best.raw_verdict !== best.verdict && (
            <div className="v2-stat-row">
              <span className="lbl">Raw model verdict</span>
              <span className="val">{best.raw_verdict}</span>
            </div>
          )}
          <div className="v2-stat-row">
            <span className="lbl">Input quality</span>
            <span className={`val ${p.quality_gate_level === "clean" ? "pos" : ""}`}>
              {qualityLabel(p.quality_gate_level)}
              {qualityReason(p, best) && <span className="delta">{qualityReason(p, best)}</span>}
            </span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Movement confidence</span>
            <span className="val">{(best.movement_conf * 100).toFixed(0)}%</span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Edge</span>
            <span className={`val ${((best.edge ?? best.ev) || 0) > 0 ? "pos" : "neg"}`}>
              {((best.edge ?? best.ev) || 0) > 0 ? "+" : ""}{((((best.edge ?? best.ev) || 0) * 100).toFixed(1))}%
            </span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Raw EV ROI</span>
            <span className="val">{best.ev > 0 ? "+" : ""}{(best.ev * 100).toFixed(1)}%</span>
          </div>
          <div className="v2-stat-row">
            <span className="lbl">Adjusted EV ROI</span>
            <span className={`val ${best.adj_ev > 0 ? "pos" : "neg"}`}>
              {best.adj_ev > 0 ? "+" : ""}{(best.adj_ev * 100).toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Footer: optional manual accepted-bet log plus Close. */}
        <div className={`v2-sheet-actions ${canLogBet ? "has-bet-log" : ""}`}>
          {canLogBet && (
            <button
              className="v2-btn-primary"
              onClick={openBetTicket}
              disabled={betLogState === "saving" || betAlreadyLogged}
            >
              {betAlreadyLogged ? "Logged" : betTicketOpen ? "Bet Ticket" : betLogState === "saved" ? "Logged" : "Log Bet"}
            </button>
          )}
          <button className="v2-btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>

      {betTicketOpen && (
        <div className="v2-bet-ticket-modal" onClick={(e) => {
          if (e.target === e.currentTarget) closeBetTicket();
        }}>
          <form
            className="v2-bet-ticket"
            onSubmit={handleAcceptedBetSave}
            role="dialog"
            aria-modal="true"
            aria-labelledby="v2-bet-ticket-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="v2-bet-ticket-head">
              <div>
                <div className="eyebrow">Bet ticket</div>
                <div className="title" id="v2-bet-ticket-title">
                  {p.pitcher} {best.direction} {best.k_line ?? p.k_line} Ks
                </div>
              </div>
              <span className={`v2-bet-verdict ${verdictClass(best.verdict, best.direction)}`}>
                {best.verdict}
              </span>
            </div>
            <div className="v2-bet-ticket-meta">
              Model ref: {bookForSide(p, best) || "Market"} {fmtOdds(best.odds)}
              <span>EV {best.adj_ev > 0 ? "+" : ""}{(best.adj_ev * 100).toFixed(1)}%</span>
            </div>
            <div className="v2-bet-fields">
              <label className="v2-bet-field">
                <span>Line</span>
                <input
                  value={betForm.line}
                  onChange={(e) => updateBetForm("line", e.target.value)}
                  inputMode="decimal"
                  autoComplete="off"
                />
              </label>
              <label className="v2-bet-field">
                <span>Odds</span>
                <input
                  value={betForm.odds}
                  onChange={(e) => updateBetForm("odds", e.target.value)}
                  inputMode="text"
                  pattern="[+-]?[0-9]*"
                  placeholder="-145"
                  autoComplete="off"
                />
              </label>
              <label className="v2-bet-field">
                <span>Book</span>
                <select
                  value={betForm.book}
                  onChange={(e) => updateBetForm("book", e.target.value)}
                >
                  <option value="" disabled>Choose book</option>
                  {BET_LOG_BOOK_OPTIONS.map((book) => (
                    <option key={book} value={book}>{book}</option>
                  ))}
                  <option value="Other">Other</option>
                </select>
              </label>
              <label className="v2-bet-field">
                <span>Units</span>
                <input
                  value={betForm.units}
                  onChange={(e) => updateBetForm("units", e.target.value)}
                  inputMode="decimal"
                  autoComplete="off"
                />
              </label>
              {betForm.book === "Other" && (
                <label className="v2-bet-field full">
                  <span>Other book</span>
                  <input
                    value={betForm.bookOther}
                    onChange={(e) => updateBetForm("bookOther", e.target.value)}
                    autoComplete="off"
                  />
                </label>
              )}
              {needsBetLogSecret && (
                <label className="v2-bet-field full">
                  <span>Bet log key</span>
                  <input
                    value={betForm.secret}
                    onChange={(e) => updateBetForm("secret", e.target.value)}
                    type="password"
                    autoComplete="off"
                  />
                </label>
              )}
            </div>
            {betLogError && <div className="v2-bet-error">{betLogError}</div>}
            {betLogState === "saved" && <div className="v2-bet-success">Bet logged</div>}
            <div className="v2-bet-ticket-actions">
              <button
                type="button"
                className="v2-btn-ghost"
                onClick={closeBetTicket}
              >
                Cancel
              </button>
              <button className="v2-btn-primary" type="submit" disabled={betLogState === "saving" || betLogState === "saved" || betAlreadyLogged}>
                {betLogState === "saving" ? "Saving..." : "Save Bet"}
              </button>
            </div>
          </form>
        </div>
      )}
    </>,
    document.body
  );
}

// ── Empty / loading / error states ──
function EmptyState({ filter }) {
  const messages = {
    ALL:  { ttl: "No slate today", sub: "MLB is off. Check back tomorrow — the next slate posts around 9 AM ET." },
    FIRE: { ttl: "No FIRE picks", sub: "Model didn't find any 1u+ ROI edges in today's slate. That's a signal, not a bug — skip days are a strategy." },
    LEAN: { ttl: "No leans", sub: "Nothing between +2% and +6% EV ROI right now." },
    LIVE: { ttl: "No games live", sub: "First pitch hasn't dropped yet. Live picks will appear here during games." }
  };
  const m = messages[filter] || messages.ALL;
  return (
    <div className="v2-state">
      <div className="glyph">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="9"/><path d="M8 14s1.5 2 4 2 4-2 4-2" strokeLinecap="round"/><circle cx="9" cy="10" r="1" fill="currentColor"/><circle cx="15" cy="10" r="1" fill="currentColor"/></svg>
      </div>
      <div className="ttl">{m.ttl}</div>
      <div className="sub">{m.sub}</div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="v2-cards" style={{paddingTop: 12}}>
      <div className="v2-section-h" style={{margin: "0 18px 8px"}}>
        <span className="v2-skel" style={{display:"inline-block", width: 90, height: 11}} />
      </div>
      {[0,1,2].map(i => (
        <div key={i} className="v2-skel-card">
          <div style={{display:"flex", justifyContent:"space-between"}}>
            <div className="v2-skel" style={{width: "40%", height: 14}} />
            <div className="v2-skel" style={{width: 60, height: 36, borderRadius: 4}} />
          </div>
          <div className="v2-skel" style={{width: "55%", height: 22}} />
          <div style={{display:"flex", gap:10, marginTop:6}}>
            <div className="v2-skel" style={{flex:1, height: 50}} />
            <div className="v2-skel" style={{flex:1, height: 50}} />
            <div className="v2-skel" style={{flex:1, height: 50}} />
          </div>
        </div>
      ))}
    </div>
  );
}

function ErrorState({ onRetry }) {
  return (
    <div className="v2-state">
      <div className="glyph" style={{background:"color-mix(in oklab, var(--neg) 18%, transparent)", color:"var(--neg)"}}>
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M12 7v6M12 17h.01"/><circle cx="12" cy="12" r="9.5"/></svg>
      </div>
      <div className="ttl">Couldn't load today's slate</div>
      <div className="sub">The odds feed didn't respond. Data may be stale.</div>
      <div className="err-detail">ODDS_API: 504 · fetched 2m ago</div>
      <div style={{marginTop: 22}}>
        <button className="v2-btn-ghost" style={{padding:"10px 22px"}} onClick={onRetry}>
          Retry
        </button>
      </div>
    </div>
  );
}

// ── Tab: Picks ──
// Aggregate W/L for a past slate. Mirrors v1 index.html: excludes PASS from
// the count so the summary reflects picks we actually would have played.
function GradingSummary({ pitchers, trackedPicks = [] }) {
  let w = 0, l = 0, p = 0, n = 0;
  if (trackedPicks.length > 0) {
    for (const pick of trackedPicks) {
      if (pick.verdict === "PASS" || !pick.result) continue;
      if (pick.result === "win") w++;
      else if (pick.result === "loss") l++;
      else if (pick.result === "push") p++;
      else continue;
      n++;
    }
  } else {
    for (const pit of pitchers) {
      const side = displaySide(pit);
      if (side.verdict === "PASS" || !side.result) continue;
      if (side.result === "win")  w++;
      else if (side.result === "loss") l++;
      else if (side.result === "push") p++;
      n++;
    }
  }
  if (n === 0) return null;
  return (
    <div className="v2-grading-summary">
      <span className="w">{w}W</span>
      <span className="n">·</span>
      <span className="l">{l}L</span>
      {p > 0 && <><span className="n">·</span><span className="p">{p}P</span></>}
    </div>
  );
}

function PicksTab({ pitchersOverride }) {
  const [filter, setFilter] = useState("ALL");
  const [detail, setDetail] = useState(null);
  const { supported: notifySupported, subscribed: notifyOn, toggleNotify } = useNotifications();
  const { trigger: triggerPipeline, state: pipelineState, title: pipelineTitle } = usePipelineTrigger();
  const pitchers = pitchersOverride ?? window.V2_DATA.pitchers;
  const trackedPicks = window.V2_DATA?.tracked_picks || [];
  const hasTrackedPicks = trackedPicks.length > 0;
  const pitcherByName = useMemo(() => {
    const map = new Map();
    for (const p of pitchers) map.set((p.pitcher || "").toLowerCase(), p);
    return map;
  }, [pitchers]);
  const past = isPastSlate();
  const filtered = useMemo(() => {
    if (filter === "ALL") return pitchers;
    if (filter === "FIRE") {
      return hasTrackedPicks
        ? pitchers.filter(p => trackedMatchesFilter(p, "FIRE"))
        : pitchers.filter(p => displaySide(p).verdict.startsWith("FIRE"));
    }
    if (filter === "LEAN") {
      return hasTrackedPicks
        ? pitchers.filter(p => trackedMatchesFilter(p, "LEAN"))
        : pitchers.filter(p => displaySide(p).verdict === "LEAN");
    }
    if (filter === "LIVE") return pitchers.filter(p => p.game_state === "in_progress");
    return pitchers;
  }, [filter, pitchers, hasTrackedPicks]);

  const counts = {
    FIRE: hasTrackedPicks
      ? trackedPicks.filter(p => (p.verdict || "").startsWith("FIRE")).length
      : pitchers.filter(p => displaySide(p).verdict.startsWith("FIRE")).length,
    LEAN: hasTrackedPicks
      ? trackedPicks.filter(p => p.verdict === "LEAN").length
      : pitchers.filter(p => displaySide(p).verdict === "LEAN").length,
    LIVE: pitchers.filter(p => p.game_state === "in_progress").length,
    ALL: pitchers.length
  };
  const chips = [
    ["ALL", "All"], ["FIRE", "Fire"], ["LEAN", "Lean"], ["LIVE", "Live"]
  ];

  const upcoming = filtered.filter(p => p.game_state === "pregame");
  const live = filtered.filter(p => p.game_state !== "pregame");

  // Best of the day
  const fires = hasTrackedPicks
    ? trackedPicks.filter(p => (p.verdict || "").startsWith("FIRE"))
    : pitchers
        .filter(p => displaySide(p).verdict.startsWith("FIRE"))
        .map(p => ({ ...displaySide(p), pitcher: p.pitcher, game_state: p.game_state }));
  const trackedUniqueFirePitchers = new Set(fires.map(p => p.pitcher)).size;

  return (
    <>
      <div className="v2-header">
        <div className="v2-header-row">
          <div className="v2-brand">
            <div className="v2-kmark">K</div>
            <div>
              <div className="v2-wordmark">Betting Edge</div>
              <div className="v2-subtitle">{(() => {
                const gen = window.V2_DATA?.generated_at ? new Date(window.V2_DATA.generated_at) : null;
                const t = gen ? gen.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) : "—";
                return `Updated ${t} · ${window.V2_DATA?.pitchers?.length ?? 0} props`;
              })()}</div>
            </div>
          </div>
          <div className="v2-header-actions">
            {notifySupported && (
              <button
                className={`v2-icon-btn${notifyOn ? " active" : ""}`}
                title={notifyOn ? "Notifications on — click to disable" : "Enable push notifications"}
                onClick={toggleNotify}
              >
                {notifyOn ? Icon.bellOn : Icon.bell}
              </button>
            )}
            <button
              className={`v2-icon-btn${pipelineState === "triggered" ? " active" : ""}`}
              title={pipelineTitle}
              onClick={triggerPipeline}
              disabled={pipelineState === "running"}
              style={pipelineState === "running" ? { opacity: 0.5 } : {}}
            >
              {Icon.refresh}
            </button>
            <button className="v2-icon-btn" title="Theme" onClick={() => window.__v2Theme?.toggleTheme()}>
              {window.__v2Theme?.theme === "dark" ? Icon.sun : Icon.moon}
            </button>
          </div>
        </div>
        <DateBar />
      </div>

      {past && <GradingSummary pitchers={pitchers} trackedPicks={trackedPicks} />}

      <div className="v2-digest">
        <div className="v2-digest-count">{fires.length}</div>
        <div className="v2-digest-body">
          <div className="v2-digest-title">{hasTrackedPicks ? "Tracked FIRE picks" : "Fire picks today"}</div>
          <div className="v2-digest-sub">
            {fires.length > 0
              ? (() => {
                  const avgEv = fires.reduce((s, p) => s + (p.adj_ev ?? 0), 0) / fires.length * 100;
                  const pre = fires.filter(p => {
                    const card = pitcherByName.get((p.pitcher || "").toLowerCase());
                    return (p.game_state || card?.game_state) === "pregame";
                  }).length;
                  const unique = hasTrackedPicks ? ` · ${trackedUniqueFirePitchers} pitchers` : "";
                  return `${fires.length} actionable${unique} · avg EV ROI +${avgEv.toFixed(1)}% · ${pre} pregame`;
                })()
              : "No FIRE picks in slate"}
          </div>
        </div>
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{color:"var(--ink-dim)"}}><path d="M6 3l5 5-5 5"/></svg>
      </div>

      <div className="v2-chipbar">
        {chips.map(([k, l]) => (
          <button
            key={k}
            className={`v2-chip ${filter === k ? "active" : ""}`}
            onClick={() => setFilter(k)}
          >
            {l} <span className="n">{counts[k]}</span>
          </button>
        ))}
      </div>

      <div className="v2-cards">
        {upcoming.length > 0 && (
          <div className="v2-section-h">Upcoming</div>
        )}
        {upcoming.map((p, i) => <PickCard key={"u"+i} p={p} onOpen={setDetail} />)}

        {live.length > 0 && (
          <div className="v2-section-h">Live & Final</div>
        )}
        {live.map((p, i) => <PickCard key={"l"+i} p={p} onOpen={setDetail} />)}

        {filtered.length === 0 && <EmptyState filter={filter} />}
      </div>
      {detail && <PickDetail p={detail} onClose={() => setDetail(null)} />}
    </>
  );
}

// ── Tab: Performance ──
function PerfTab() {
  const d = window.V2_PERF;
  const maxAbsRoi = Math.max(0, ...d.rows.map(r => typeof r.roi === "number" ? Math.abs(r.roi) : 0));
  const [showCalib, setShowCalib] = useState(false);
  const notes = d.calibration_notes || [];

  return (
    <>
      <div className="v2-header">
        <div className="v2-header-row">
          <div className="v2-brand">
            <div className="v2-kmark">K</div>
            <div>
              <div className="v2-wordmark">Performance</div>
              <div className="v2-subtitle">Season · {d.total_picks ?? 0} graded picks</div>
            </div>
          </div>
          <div className="v2-header-actions">
            <button
              className={`v2-icon-btn${showCalib ? " active" : ""}`}
              title="Calibration log"
              onClick={() => setShowCalib(s => !s)}
            >
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M2 4h12M4 8h8M6 12h4"/></svg>
            </button>
          </div>
        </div>
      </div>
      {showCalib && (
        <div className="v2-calib-panel">
          <div className="v2-calib-title">Calibration log · {notes.length} entries</div>
          {notes.length === 0 && <div className="v2-calib-empty">No calibration notes yet.</div>}
          {notes.map((n, i) => {
            const match = n.match(/^\[(\d{4}-\d{2}-\d{2})\]\s*(.+)$/);
            const date = match ? match[1] : null;
            const text = match ? match[2] : n;
            return (
              <div key={i} className="v2-calib-row">
                {date && <span className="v2-calib-date">{date}</span>}
                <span className="v2-calib-text">{text}</span>
              </div>
            );
          })}
        </div>
      )}

      <div className="v2-perf-hero">
        <div className={`v2-perf-units ${d.total_units >= 0 ? "pos" : "neg"}`}>
          {d.total_units >= 0 ? "+" : ""}{d.total_units.toFixed(1)}u
        </div>
        <div className="v2-perf-sub">
          Net units · {d.record} · ROI {d.total_roi >= 0 ? "+" : ""}{d.total_roi.toFixed(1)}%
        </div>
        <div className="v2-perf-meta">
          <div>
            <div className="lbl">Best tier</div>
            <div className="val">{d.best_tier || "—"}</div>
          </div>
          <div>
            <div className="lbl">Win rate</div>
            <div className="val">{d.win_rate != null ? d.win_rate.toFixed(1) + "%" : "—"}</div>
          </div>
          <div>
            <div className="lbl">Last calib.</div>
            <div className="val">{d.last_calibrated ? new Date(d.last_calibrated).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "—"}</div>
          </div>
        </div>
      </div>

      <div className="v2-tier">
        <div className="v2-section-h" style={{margin:"16px 0 4px"}}>By tier</div>
        {d.rows.map((r, i) => {
          const isFire = r.verdict.startsWith("FIRE");
          const isFire2 = r.verdict === "FIRE 2u";
          const badgeCls = isFire
            ? (r.side === "over" ? "fire-over" : "fire")
            : (r.side === "over" ? "lean-over" : "lean-under");
          const roiPct = typeof r.roi === "number" ? r.roi : null;
          const winPct = typeof r.win_pct === "number" ? r.win_pct : null;
          const hasRoi = roiPct != null;
          const pct = hasRoi ? Math.min(1, Math.abs(roiPct) / Math.max(maxAbsRoi, 1)) : 0;
          return (
            <div key={i} className="v2-tier-row">
              <div className={`v2-tier-badge ${badgeCls}`}>
                {r.verdict === "FIRE 1u" ? "F1u" : r.verdict === "FIRE 2u" ? "F2u" : "LEAN"}
                <span className="s">{r.side.toUpperCase()}</span>
              </div>
              <div className="v2-tier-bar-wrap">
                <div className="v2-tier-bar-head">
                  <span>{r.picks} picks · {r.wins}-{r.losses}</span>
                  <span className="wr">{winPct != null ? `${(winPct * 100).toFixed(1)}%` : "--"}</span>
                </div>
                <div className="v2-tier-bar">
                  <div className="break" style={{left:"50%"}}/>
                  {hasRoi ? roiPct >= 0 ? (
                    <div className="fill pos" style={{left:"50%", width: `${pct * 50}%`}}/>
                  ) : (
                    <div className="fill neg" style={{right:"50%", width: `${pct * 50}%`, left:"auto"}}/>
                  ) : null}
                </div>
              </div>
              <div className={`v2-tier-roi ${hasRoi ? (roiPct >= 0 ? "pos" : "neg") : ""}`}>
                {hasRoi ? `${roiPct >= 0 ? "+" : ""}${roiPct.toFixed(1)}%` : "--"}
                <span className="n">ROI</span>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

// ── Tab: Steam ──
// History replaces the old standalone Steam workflow. Steam still appears as
// pick context in rows/cards, where it is tied to model direction.
function HistoryTab() {
  const dateIndex = (window.V2_DATES || []).map(d => typeof d === "string" ? { date: d } : d);
  const today = window.__v2GetAppDate ? window.__v2GetAppDate() : phxDateISO();
  const completedDates = dateIndex.filter(d => d.date && d.date < today);
  const [query, setQuery] = useState("");
  const [verdictFilter, setVerdictFilter] = useState("ALL");
  const [resultFilter, setResultFilter] = useState("ALL");
  const [teamFilter, setTeamFilter] = useState("ALL");
  const [dateFilter, setDateFilter] = useState("ALL");
  const [state, setState] = useState({ status: "loading", rows: [], error: "", skipped: 0 });

  React.useEffect(() => {
    let cancelled = false;
    const dates = completedDates.map(d => d.date).slice(0, 14);
    async function load() {
      if (!dates.length) {
        setState({ status: "ready", rows: [], error: "", skipped: 0 });
        return;
      }
      setState({ status: "loading", rows: [], error: "", skipped: 0 });
      try {
        const slateResults = await Promise.all(dates.map(async (date) => {
          try {
            return { date, slate: await fetchHistorySlate(date), error: false };
          } catch {
            return { date, slate: null, error: true };
          }
        }));
        if (cancelled) return;
        const rows = slateResults
          .filter(result => result.slate)
          .flatMap(result => historyRowsFromSlate(result.slate))
          .filter(row => row.result !== "push" && row.result !== "void")
          .sort((a, b) => (
            String(b.date || "").localeCompare(String(a.date || "")) ||
            verdictStake(b.verdict) - verdictStake(a.verdict) ||
            (b.adj_ev ?? -99) - (a.adj_ev ?? -99)
          ));
        const skipped = slateResults.filter(result => result.error).length;
        setState({ status: "ready", rows, error: "", skipped });
      } catch (err) {
        if (!cancelled) setState({ status: "error", rows: [], error: String(err.message || err) });
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const teams = useMemo(() => {
    const names = new Set();
    for (const row of state.rows) {
      if (row.team) names.add(ab(row.team));
      if (row.opp_team) names.add(ab(row.opp_team));
    }
    return [...names].sort();
  }, [state.rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return state.rows.filter((row) => {
      const haystack = `${row.pitcher} ${ab(row.team)} ${row.team} ${ab(row.opp_team)} ${row.opp_team}`.toLowerCase();
      if (q && !haystack.includes(q)) return false;
      if (dateFilter !== "ALL" && row.date !== dateFilter) return false;
      if (teamFilter !== "ALL" && ab(row.team) !== teamFilter && ab(row.opp_team) !== teamFilter) return false;
      if (verdictFilter === "FIRE" && !String(row.verdict || "").startsWith("FIRE")) return false;
      if (verdictFilter === "LEAN" && row.verdict !== "LEAN") return false;
      if (verdictFilter === "PASS" && row.verdict !== "PASS") return false;
      if (resultFilter !== "ALL" && row.result !== resultFilter.toLowerCase()) return false;
      return true;
    });
  }, [state.rows, query, verdictFilter, resultFilter, teamFilter, dateFilter]);

  const gradedRows = state.rows.filter(r => r.result === "win" || r.result === "loss");
  const wins = gradedRows.filter(r => r.result === "win").length;
  const losses = gradedRows.filter(r => r.result === "loss").length;
  const fireCount = state.rows.filter(r => String(r.verdict || "").startsWith("FIRE")).length;

  const openSlate = (date) => {
    const today = window.__v2GetAppDate ? window.__v2GetAppDate() : phxDateISO();
    const u = new URL(location.href);
    if (date === today) u.searchParams.delete("date"); else u.searchParams.set("date", date);
    u.searchParams.delete("state");
    location.href = u.toString();
  };

  return (
    <>
      <div className="v2-header">
        <div className="v2-header-row">
          <div className="v2-brand">
            <div className="v2-kmark">K</div>
            <div>
              <div className="v2-wordmark">History</div>
              <div className="v2-subtitle">Completed slates - pitcher and team lookup</div>
            </div>
          </div>
          <div className="v2-header-actions">
            <button className="v2-icon-btn" title="Theme" onClick={() => window.__v2Theme?.toggleTheme()}>
              {window.__v2Theme?.theme === "dark" ? Icon.sun : Icon.moon}
            </button>
          </div>
        </div>
      </div>

      <div className="v2-history-hero">
        <div>
          <div className="n">{filtered.length}</div>
        </div>
        <div style={{flex:1}}>
          <div className="lbl">Rows in view</div>
          <div className="ttl">
            {state.status === "loading"
              ? "Loading recent slates"
              : `${wins}W-${losses}L - ${fireCount} FIRE`}
          </div>
          {state.skipped > 0 && (
            <div className="v2-history-note">{state.skipped} archived date{state.skipped === 1 ? "" : "s"} skipped</div>
          )}
        </div>
      </div>

      <div className="v2-history-tools">
        <input
          className="v2-history-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search pitcher or team"
          aria-label="Search history by pitcher or team"
        />
        <div className="v2-history-select-row">
          <select value={dateFilter} onChange={(e) => setDateFilter(e.target.value)} aria-label="Filter by date">
            <option value="ALL">All dates</option>
            {completedDates.slice(0, 14).map(d => (
              <option key={d.date} value={d.date}>{d.date}</option>
            ))}
          </select>
          <select value={teamFilter} onChange={(e) => setTeamFilter(e.target.value)} aria-label="Filter by team">
            <option value="ALL">All teams</option>
            {teams.map(team => <option key={team} value={team}>{team}</option>)}
          </select>
        </div>
      </div>

      <div className="v2-steam-filter v2-history-filter">
        {[["ALL","All"],["FIRE","Fire"],["LEAN","Lean"]].map(([k,l]) => (
          <button
            key={k}
            className={`f ${verdictFilter === k ? "active" : ""}`}
            onClick={() => setVerdictFilter(k)}
          >{l}</button>
        ))}
      </div>

      <div className="v2-steam-filter v2-history-filter secondary">
        {[["ALL","Results"],["WIN","Wins"],["LOSS","Losses"]].map(([k,l]) => (
          <button
            key={k}
            className={`f ${resultFilter === k ? "active" : ""}`}
            onClick={() => setResultFilter(k)}
          >{l}</button>
        ))}
      </div>

      <div className="v2-history-list">
        {state.status === "loading" && (
          <>
            <div className="v2-skel-card"><div className="v2-skel" style={{height:18,width:"55%"}}/><div className="v2-skel" style={{height:12,width:"80%"}}/><div className="v2-skel" style={{height:34,width:"100%"}}/></div>
            <div className="v2-skel-card"><div className="v2-skel" style={{height:18,width:"45%"}}/><div className="v2-skel" style={{height:12,width:"70%"}}/><div className="v2-skel" style={{height:34,width:"100%"}}/></div>
          </>
        )}
        {state.status === "error" && (
          <div className="v2-state">
            <div className="ttl">History unavailable</div>
            <div className="sub">Could not load the recent slate archive.</div>
            <div className="err-detail">{state.error}</div>
          </div>
        )}
        {state.status === "ready" && filtered.map((r, i) => {
          const result = r.result || "pending";
          const resultClass = result === "win" ? "win" : result === "loss" ? "loss" : result === "push" ? "push" : result === "void" ? "void" : "pending";
          const sideClass = r.direction === "OVER" ? "up" : "down";
          const steam = r.steam;
          return (
            <article key={`${r.date}-${r.pitcher}-${r.direction}-${i}`} className={`v2-history-row ${verdictClass(r.verdict, r.direction)}`}>
              <button className="v2-history-date" type="button" onClick={() => openSlate(r.date)} title="Open slate">
                <span>{new Date(`${r.date}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })}</span>
                <span>View</span>
              </button>
              <div className={`v2-steam-dir ${sideClass}`}>
                {r.direction === "OVER" ? "OV" : "UN"}
              </div>
              <div className="v2-history-main">
                <div className="v2-history-name">{r.pitcher}</div>
                <div className="v2-history-meta">
                  {ab(r.team)} vs {ab(r.opp_team)} - {r.direction} {r.k_line} K - {fmtOdds(r.odds)}
                </div>
                <div className="v2-history-tags">
                  <span className={`v2-history-verdict ${verdictClass(r.verdict, r.direction)}`}>{r.verdict}</span>
                  <span className={`v2-history-result ${resultClass}`}>
                    {result === "pending" ? "Pending" : result.toUpperCase()}{r.actual_ks != null ? ` - ${r.actual_ks} K` : ""}
                  </span>
                  {steam && (
                    <span className={`v2-steam ${steam.steamWith ? "with" : "against"}`}>
                      {steam.steamWith ? "odds with" : "odds against"} {steam.cents}c
                    </span>
                  )}
                </div>
              </div>
              <div className="v2-history-ev">
                <span className={(r.adj_ev ?? 0) >= 0 ? "pos" : "neg"}>
                  {(r.adj_ev ?? 0) >= 0 ? "+" : ""}{((r.adj_ev ?? 0) * 100).toFixed(1)}%
                </span>
                <span>EV ROI</span>
              </div>
            </article>
          );
        })}
        {state.status === "ready" && filtered.length === 0 && (
          <div className="v2-state">
            <div className="ttl">No matching history</div>
            <div className="sub">Try clearing a filter or searching another pitcher or team.</div>
          </div>
        )}
      </div>
    </>
  );
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
  const avgCents = totalMoved > 0
    ? Math.round(d.rows.reduce((s, r) => s + r.cents, 0) / totalMoved)
    : 0;
  const mine = d.rows.filter(r => r.my_pick).length;

  return (
    <>
      <div className="v2-header">
        <div className="v2-header-row">
          <div className="v2-brand">
            <div className="v2-kmark">K</div>
            <div>
              <div className="v2-wordmark">Steam</div>
              <div className="v2-subtitle">Line movement · open → now</div>
            </div>
          </div>
          <div className="v2-header-actions">
            <button className="v2-icon-btn" title="Refresh">{Icon.refresh}</button>
          </div>
        </div>
      </div>

      <div className="v2-steam-hero">
        <div>
          <div className="n">{totalMoved}</div>
        </div>
        <div style={{flex:1}}>
          <div className="lbl">Active moves</div>
          <div className="ttl">{totalMoved > 0 ? `${avgCents}¢ avg · ${mine} align with my picks` : "No meaningful movement"}</div>
        </div>
      </div>

      <div className="v2-steam-filter">
        {[["ALL","All"],["OVER","Over ↑"],["UNDER","Under ↑"],["MINE","My picks"]].map(([k,l]) => (
          <button
            key={k}
            className={`f ${filter === k ? "active" : ""}`}
            onClick={() => setFilter(k)}
          >{l}</button>
        ))}
      </div>

      <div style={{paddingBottom: 90}}>
        {filtered.map((r, i) => (
          <div key={i} className="v2-steam-row">
            <div className={`v2-steam-dir ${r.direction === "over" ? "up" : "down"}`}>
              {r.direction === "over" ? "OV" : "UN"}
            </div>
            <div>
              <div className="v2-steam-name">{r.pitcher}</div>
              <div className="v2-steam-meta">
                {r.team} vs {r.opp} · {r.k_line} K
                {r.books_moved != null && r.books_total != null && ` · ${r.books_moved}/${r.books_total} books`}
                {r.note && ` · ${r.note}`}
                {r.my_pick && <span style={{color:"var(--accent)", marginLeft:6}}>· {r.my_pick}</span>}
              </div>
            </div>
            <div className="v2-steam-delta" style={{color: r.direction === "over" ? "var(--pos)" : "var(--neg)"}}>
              {r.cents}¢
              <span className="t">{r.direction === "over" ? "↑ OVER" : "↑ UNDER"}</span>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="v2-state"><div className="ttl">No movement</div><div className="sub">No books have moved in this category.</div></div>
        )}
      </div>
    </>
  );
}

// ── Root app ──
function App() {
  const [tab, setTab] = useState(() => {
    const t = new URLSearchParams(location.search).get("tab");
    return ["picks", "history", "perf"].includes(t) ? t : "picks";
  });
  const [appState, setAppState] = useState(() => {
    const u = new URLSearchParams(location.search);
    return u.get("state") || window.V2_APP_STATE || "ready";
  });
  const [theme, setTheme] = useState(() => {
    const qTheme = new URLSearchParams(location.search).get("theme");
    if (qTheme === "dark" || qTheme === "light") return qTheme;
    try { return localStorage.getItem("v2-theme") || "light"; } catch { return "light"; }
  });
  React.useEffect(() => {
    document.body.setAttribute("data-theme", theme);
    try { localStorage.setItem("v2-theme", theme); } catch {}
  }, [theme]);
  const toggleTheme = () => setTheme(t => t === "dark" ? "light" : "dark");
  window.__v2Theme = { theme, toggleTheme };

  const renderPicks = () => {
    if (appState === "loading") return (<>
      <div className="v2-header"><div className="v2-header-row">
        <div className="v2-brand"><div className="v2-kmark">K</div>
          <div><div className="v2-wordmark">Betting Edge</div>
          <div className="v2-subtitle">Loading slate…</div></div></div>
      </div></div>
      <LoadingState />
    </>);
    if (appState === "error") return (<>
      <div className="v2-header"><div className="v2-header-row">
        <div className="v2-brand"><div className="v2-kmark">K</div>
          <div><div className="v2-wordmark">Betting Edge</div>
          <div className="v2-subtitle" style={{color:"var(--neg)"}}>Connection error</div></div></div>
      </div></div>
      <ErrorState onRetry={() => window.location.reload()} />
    </>);
    if (appState === "empty") return <PicksTab pitchersOverride={[]} />;
    return <PicksTab />;
  };

  return (
    <>
      {tab === "picks" && renderPicks()}
      {tab === "perf" && <PerfTab />}
      {tab === "history" && <HistoryTab />}
      <nav className="v2-tabbar">
        {[
          ["picks", Icon.picks,   "Picks",   null],
          ["history", Icon.history, "History", null],
          ["perf",  Icon.results, "Results", null]
        ].map(([k, ic, l, badge]) => (
          <button
            key={k}
            className={`v2-tab ${tab === k ? "active" : ""}`}
            onClick={() => setTab(k)}
          >
            {ic}
            <span>{l}</span>
            {badge != null && <span className="v2-tab-badge">{badge}</span>}
            {tab === k && <span className="v2-tab-dot active" style={{background:"var(--accent)"}}/>}
          </button>
        ))}
      </nav>
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
(async () => {
  try { await window.__v2DataPromise; } catch { /* adapter already set error state */ }
  root.render(<App/>);
})();
