/* ──────────────────────────────────────────────────────────────
 *  v2-data.js — real-data adapter for the v2 preview UI.
 *
 *  Transforms the existing pipeline output (dashboard/data/processed/today.json
 *  and dashboard/data/performance.json) into the shapes the v2 React prototype
 *  expects on window.V2_DATA / window.V2_PERF / window.V2_STEAM.
 *  Raw steam snapshots are also exposed on window.V2_STEAM_RAW for the detail
 *  sheet movement chart.
 *
 *  Fields the pipeline doesn't produce yet are omitted or synthesized; v2-app.jsx
 *  degrades gracefully for those. See docs/ui-redesign/deferred-pipeline-work.md
 *  for the wishlist.
 *
 *  v2-app.jsx awaits window.__v2DataPromise before mounting React.
 * ─────────────────────────────────────────────────────────────── */
(() => {
  const IS_LOCAL = location.hostname === 'localhost' ||
                   location.hostname === '127.0.0.1' ||
                   location.protocol === 'file:';
  const RAW_BASE = IS_LOCAL
    ? 'data/processed'
    : 'https://raw.githubusercontent.com/treidjbi/baseballbettingedge/main/dashboard/data/processed';
  const PERF_URL = IS_LOCAL
    ? 'data/performance.json'
    : 'https://raw.githubusercontent.com/treidjbi/baseballbettingedge/main/dashboard/data/performance.json';
  const PARAMS_URL = 'https://raw.githubusercontent.com/treidjbi/baseballbettingedge/main/data/params.json';
  const STEAM_URL = IS_LOCAL
    ? 'data/processed/steam.json'
    : 'https://raw.githubusercontent.com/treidjbi/baseballbettingedge/main/dashboard/data/processed/steam.json';

  // Stakes-per-pick mapping — mirrors CLAUDE.md thresholds.
  const STAKE = { 'FIRE 2u': 2, 'FIRE 1u': 1, 'LEAN': 0, 'PASS': 0 };

  // Slate date - Phoenix-aware. Midnight preview runs now cover the current game day.
  function getAppDate() {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/Phoenix',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date());
    const byType = Object.fromEntries(parts.map(p => [p.type, p.value]));
    return `${byType.year}-${byType.month}-${byType.day}`;
  }

  async function fetchJSON(url) {
    const res = await fetch(`${url}?t=${Date.now()}`);
    if (!res.ok) throw new Error(`${url} → HTTP ${res.status}`);
    return res.json();
  }

  // ── Transform: pitcher record → V2_DATA.pitchers[] entry ──────
  function normalizePitcher(p) {
    // Fallbacks for fields not in pipeline output.
    const pitcher_throws = p.pitcher_throws || 'R';
    const game_state = p.game_state || 'pregame';

    // Preserve all V2-expected fields; pass through the rest unchanged.
    const out = {
      pitcher: p.pitcher,
      team: p.team,
      opp_team: p.opp_team,
      pitcher_throws,
      game_time: p.game_time,
      k_line: p.k_line,
      opening_line: p.opening_line ?? p.k_line,
      best_over_odds: p.best_over_odds,
      best_under_odds: p.best_under_odds,
      opening_over_odds: p.opening_over_odds ?? p.best_over_odds,
      opening_under_odds: p.opening_under_odds ?? p.best_under_odds,
        lambda: p.lambda,
        avg_ip: p.avg_ip,
        opp_k_rate: p.opp_k_rate,
        park_factor: p.park_factor ?? null,
        ump_k_adj: p.ump_k_adj ?? 0,
        umpire: p.umpire ?? null,
        umpire_has_rating: p.umpire_has_rating ?? null,
        // Signal-confirmation flags surfaced in the sheet's "Why this pick" header.
        // lineup_used=true when the starting 9 came from MLB's boxscore (A5); false
        // while we're still falling back to the projected lineup.
        lineup_used: p.lineup_used === true,
        days_since_last_start: p.days_since_last_start ?? null,
        last_pitch_count: p.last_pitch_count ?? null,
        rest_k9_delta: p.rest_k9_delta ?? null,
        season_k9: p.season_k9,
      recent_k9: p.recent_k9,
      career_k9: p.career_k9,
      ev_over: p.ev_over,
      ev_under: p.ev_under,
      game_state,
      // Pipeline provides best_over_book; no best_under_book yet — fall back.
      best_over_book: p.best_over_book || 'Best book',
      best_under_book: p.best_under_book || p.best_over_book || 'Best book',
      // Pass-through for the sheet's "why this pick" section.
      swstr_pct: p.swstr_pct,
      swstr_delta_k9: p.swstr_delta_k9,
      data_complete: p.data_complete,
    };

    // live block — pipeline doesn't hydrate in-game K yet. Leave undefined so the
    // sheet's LIVE state block renders its generic fallback (handled in v2-app.jsx).
    // result block — today's snapshot doesn't carry grading. Same deal.
    return out;
  }

  function normalizeTrackedPick(p) {
    const side = (p.display_side || p.side || '').toUpperCase();
    const verdict = p.display_verdict || p.locked_verdict || p.verdict || 'PASS';
    return {
      date: p.date,
      pitcher: p.pitcher,
      team: p.team,
      opp_team: p.opp_team,
      side: p.side,
      direction: side,
      display_side: side,
      verdict,
      locked_verdict: p.locked_verdict ?? null,
      original_verdict: p.verdict ?? null,
      k_line: p.display_k_line ?? p.locked_k_line ?? p.k_line,
      odds: p.display_odds ?? p.locked_odds ?? p.odds,
      adj_ev: p.display_adj_ev ?? p.locked_adj_ev ?? p.adj_ev ?? 0,
      edge: p.edge ?? null,
      ev: p.ev ?? null,
      result: p.result ?? null,
      actual_ks: p.actual_ks ?? null,
      pnl: p.pnl ?? null,
      locked_at: p.locked_at ?? null,
      status: p.status || (p.locked_at ? 'locked' : 'tracking'),
      game_time: p.game_time ?? null,
      data_complete: p.data_complete ?? null,
    };
  }

  function trackedPitcherKey(name) {
    return String(name || '').trim().toLowerCase();
  }

  function buildV2Data(today) {
    const pitchers = (today.pitchers || []).map(normalizePitcher);
    const rawTracked = Array.isArray(today.tracked_picks)
      ? today.tracked_picks
      : (today.pitchers || []).flatMap(p => Array.isArray(p.tracked_picks) ? p.tracked_picks : []);
    const tracked_picks = rawTracked.map(normalizeTrackedPick);
    const trackedByPitcher = new Map();
    for (const pick of tracked_picks) {
      const key = trackedPitcherKey(pick.pitcher);
      if (!key) continue;
      if (!trackedByPitcher.has(key)) trackedByPitcher.set(key, []);
      trackedByPitcher.get(key).push(pick);
    }
    for (const p of pitchers) {
      p.tracked_picks = trackedByPitcher.get(trackedPitcherKey(p.pitcher)) || [];
    }

    // Defensive sort by game_time ascending — the pipeline can emit pitchers out
    // of order (late-arriving lineup/odds data gets appended), which bubbles up
    // to the UI as "one 3:40 game at the bottom of the Upcoming list."
    // v2-app.jsx's PicksTab filter → upcoming/live split preserves this order,
    // so sorting once here is sufficient. Secondary sort on pitcher name keeps
    // same-time games stable across runs. localeCompare works because
    // game_time is ISO UTC (e.g. '2026-04-22T22:40:00Z').
    pitchers.sort((a, b) => {
      const t = (a.game_time || '').localeCompare(b.game_time || '');
      if (t !== 0) return t;
      return (a.pitcher || '').localeCompare(b.pitcher || '');
    });
    return { generated_at: today.generated_at, date: today.date, pitchers, tracked_picks };
  }

  // ── Transform: performance.json → V2_PERF shape ────────────────
  function buildV2Perf(perf) {
    const rows = (perf.rows || []).map(r => ({
      verdict: r.verdict,
      side: r.side,
      picks: r.picks,
      wins: r.wins,
      losses: r.losses,
      pushes: r.pushes || 0,
      win_pct: r.win_pct,
      roi: r.roi,
      avg_ev: r.avg_ev,
    }));

    // Unit totals from rows: only FIRE tiers carry stake; LEAN is tracked but not wagered.
    let totalUnits = 0, totalWagered = 0, totalWins = 0, totalLosses = 0, totalPushes = 0, totalStakedPicks = 0;
    let bestRow = null;
    for (const r of rows) {
      const stake = STAKE[r.verdict] || 0;
      if (stake > 0) {
        totalUnits   += r.picks * stake * (r.roi / 100);
        totalWagered += r.picks * stake;
        totalWins    += r.wins;
        totalLosses  += r.losses;
        totalPushes  += r.pushes;
        totalStakedPicks += r.picks;
        if (!bestRow || r.roi > bestRow.roi) bestRow = r;
      }
    }
    const totalRoi = totalWagered > 0 ? (totalUnits / totalWagered) * 100 : 0;
    const winRate  = totalStakedPicks > 0
      ? totalWins / (totalWins + totalLosses) * 100
      : 0;
    const bestTierLabel = bestRow
      ? `${bestRow.verdict.replace('FIRE ', 'F')} ${bestRow.side.toUpperCase()}`
      : '—';

    return {
      total_picks: perf.total_picks ?? totalStakedPicks,
      total_units: totalUnits,
      total_roi: totalRoi,
      record: `${totalWins}-${totalLosses}-${totalPushes}`,
      rows,
      // Meta pieces the PerfTab header reads.
      best_tier: bestTierLabel,
      win_rate: winRate,
      last_calibrated: perf.last_calibrated,
      calibration_sample: perf.calibration_sample,
      calibration_notes: perf.calibration_notes || [],
    };
  }

  // ── Derive: steam feed from today's pitchers ───────────────────
  // The pipeline doesn't publish a standalone steam feed yet; we reconstruct
  // from per-pitcher opening vs current odds. books_moved/books_total unknown —
  // we omit those counts and present price-movement only.
  function calcCents(opening, current) {
    if (opening == null || current == null) return 0;
    const sameSign = (opening > 0 && current > 0) || (opening < 0 && current < 0);
    return sameSign
      ? Math.abs(current - opening)
      : (Math.abs(opening) - 100) + (Math.abs(current) - 100);
  }
  function impliedProb(odds) {
    if (odds == null) return null;
    return odds < 0 ? Math.abs(odds) / (Math.abs(odds) + 100) : 100 / (odds + 100);
  }

  function buildV2Steam(today) {
    const rows = [];
    for (const p of (today.pitchers || [])) {
      const overCents  = calcCents(p.opening_over_odds,  p.best_over_odds);
      const underCents = calcCents(p.opening_under_odds, p.best_under_odds);
      const overCheaper  = impliedProb(p.best_over_odds)  < impliedProb(p.opening_over_odds);
      const underCheaper = impliedProb(p.best_under_odds) < impliedProb(p.opening_under_odds);

      // Steam flows into the side that became MORE expensive (harder to hit).
      // Which side is being hammered: pick the one that did NOT get cheaper.
      let direction = null, cents = 0;
      if (!overCheaper && overCents >= 5)  { direction = 'over';  cents = overCents;  }
      if (!underCheaper && underCents > cents) { direction = 'under'; cents = underCents; }
      if (!direction || cents < 5) continue;

      // Tag pitcher's model pick if FIRE-grade.
      const best = (p.ev_over?.adj_ev ?? -1) >= (p.ev_under?.adj_ev ?? -1)
        ? { dir: 'OVER',  v: p.ev_over }
        : { dir: 'UNDER', v: p.ev_under };
      const my_pick = (best.v?.verdict || '').startsWith('FIRE') && best.dir.toLowerCase() === direction
        ? `${best.dir} ${best.v.verdict}`
        : null;

      rows.push({
        pitcher: p.pitcher,
        team: p.team,
        opp: p.opp_team,
        game_time: p.game_time,
        k_line: p.k_line,
        open_line: p.opening_line ?? p.k_line,
        direction,
        cents,
        open_odds: direction === 'over' ? p.opening_over_odds : p.opening_under_odds,
        cur_odds:  direction === 'over' ? p.best_over_odds    : p.best_under_odds,
        // Not available from current data:
        books_moved: null,
        books_total: null,
        note: p.k_line !== (p.opening_line ?? p.k_line)
          ? `Line ${p.opening_line} → ${p.k_line}`
          : 'Odds only',
        my_pick,
      });
    }
    rows.sort((a, b) => b.cents - a.cents);
    return { updated_at: today.generated_at, rows };
  }

  // ── Steam feed from steam.json (Phase A: books_moved counts) ──
  // Falls back to synthetic steam if steamJson is null or has no snapshots.
  // books_moved requires ≥2 snapshots; books_total is populated from snapshot 1+.
  function buildV2SteamFromFile(steamJson, todayJson) {
    const base = buildV2Steam(todayJson);
    if (!steamJson || !steamJson.snapshots?.length) return base;

    const snaps  = steamJson.snapshots;
    const first  = snaps[0];
    const latest = snaps[snaps.length - 1];

    for (const row of base.rows) {
      const latestP = latest.pitchers?.[row.pitcher];
      if (!latestP) continue;

      const books = Object.keys(latestP).filter(k => k !== 'k_line');
      row.books_total = books.length;

      if (snaps.length >= 2) {
        const firstP = first.pitchers?.[row.pitcher];
        if (firstP) {
          let moved = 0;
          for (const book of books) {
            const fo = firstP[book]?.[row.direction];
            const lo = latestP[book]?.[row.direction];
            if (fo != null && lo != null && fo !== lo) moved++;
          }
          row.books_moved = moved;
        }
      }
    }

    return base;
  }

  function steamJsonForDate(steamJson, slateDate) {
    if (!steamJson || !steamJson.snapshots?.length) return null;
    if (Array.isArray(steamJson.archive_dates) && steamJson.archive_dates.includes(slateDate)) {
      return steamJson;
    }
    return steamJson.date === slateDate ? steamJson : null;
  }

  // ── Fetch archived dates for the DateBar ───────────────────────
  async function fetchDateIndex() {
    try {
      const idx = await fetchJSON(`${RAW_BASE}/index.json`);
      if (!Array.isArray(idx.dates)) return [];
      // Handle both old shape (strings) and new shape ({date, wins, losses})
      return idx.dates.map(d => typeof d === 'string' ? { date: d, wins: 0, losses: 0 } : d);
    } catch {
      return [];
    }
  }

  // ── Wire up globals ─────────────────────────────────────────────
  window.__v2GetAppDate = getAppDate;

  window.__v2DataPromise = (async () => {
    const today = getAppDate();
    // Default to today; URL override `?date=YYYY-MM-DD` loads an archive.
    const qDate = new URLSearchParams(location.search).get('date');
    const dateToLoad = qDate || today;
    const dataUrl = `${RAW_BASE}/${dateToLoad}.json`;

    try {
      const [todayJson, perfJson, paramsJson, dateIndex, steamJson] = await Promise.all([
        fetchJSON(dataUrl).catch(() => fetchJSON(`${RAW_BASE}/today.json`)),
        fetchJSON(PERF_URL).catch(() => ({ rows: [], total_picks: 0 })),
        fetchJSON(PARAMS_URL).catch(() => ({})),
        fetchDateIndex(),
        fetchJSON(STEAM_URL).catch(() => null),
      ]);
      const datedSteam = steamJsonForDate(steamJson, todayJson.date);
      const perfWithNotes = { ...perfJson, calibration_notes: paramsJson.calibration_notes || perfJson.calibration_notes || [] };
      window.V2_DATA  = buildV2Data(todayJson);
      window.V2_PERF  = buildV2Perf(perfWithNotes);
      window.V2_STEAM = buildV2SteamFromFile(datedSteam, todayJson);
      window.V2_STEAM_RAW = datedSteam || { snapshots: [] };
      window.V2_DATES     = dateIndex;
      window.V2_DATE_META = Object.fromEntries(dateIndex.map(d => [d.date, d]));
      window.V2_CURRENT_DATE = dateToLoad;
      window.V2_APP_STATE = (window.V2_DATA.pitchers.length === 0) ? 'empty' : 'ready';
    } catch (err) {
      console.error('[v2-data] fetch failed:', err);
      window.V2_DATA  = { pitchers: [], tracked_picks: [] };
      window.V2_PERF  = { total_picks: 0, total_units: 0, total_roi: 0, record: '0-0-0', rows: [] };
      window.V2_STEAM = { rows: [] };
      window.V2_STEAM_RAW = { snapshots: [] };
      window.V2_DATES     = [];
      window.V2_DATE_META = {};
      window.V2_CURRENT_DATE = getAppDate();
      window.V2_APP_STATE = 'error';
      window.V2_APP_ERROR = String(err.message || err);
    }
    return true;
  })();
})();
