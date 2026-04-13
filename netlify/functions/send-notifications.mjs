/**
 * send-notifications — Netlify Functions v2
 * Called by GitHub Actions after each pipeline commit.
 * Reads today's picks, compares to last-known state stored in Netlify Blobs,
 * and fires push notifications for meaningful changes:
 *   - New FIRE picks appearing on the slate
 *   - LEAN → FIRE upgrades
 *   - Picks transitioning to locked (batched if multiple in one run)
 *   - Daily results summary (grading run only)
 *
 * Required Netlify env vars:
 *   VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT, NOTIFY_SECRET
 */
import webPush from 'web-push';
import { getStore } from '@netlify/blobs';

const RAW_BASE = 'https://raw.githubusercontent.com/treidjbi/baseballbettingedge/main';

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

async function fetchJSON(url) {
  const res = await fetch(`${url}?t=${Date.now()}`);
  if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`);
  return res.json();
}

// Picks worth tracking: either side has a non-PASS verdict
function getFirePicks(pitchers) {
  const picks = {};
  for (const p of pitchers) {
    for (const side of ['over', 'under']) {
      const ev = p[`ev_${side}`];
      if (!ev || ev.verdict === 'PASS') continue;
      picks[`${p.pitcher}|${side}`] = {
        pitcher: p.pitcher,
        side,
        verdict: ev.verdict,
        k_line: p.k_line,
        locked: p.game_state === 'in_progress' || p.game_state === 'final',
        game_state: p.game_state,
      };
    }
  }
  return picks;
}

export default async (req) => {
  if (req.method !== 'POST') return json(405, { error: 'Method not allowed' });

  const { NOTIFY_SECRET, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT } = process.env;

  if (!NOTIFY_SECRET || req.headers.get('x-notify-secret') !== NOTIFY_SECRET) {
    return json(401, { error: 'Unauthorized' });
  }
  if (!VAPID_PUBLIC_KEY || !VAPID_PRIVATE_KEY || !VAPID_SUBJECT) {
    console.error('send-notifications: VAPID env vars not set');
    return json(500, { error: 'VAPID not configured' });
  }

  webPush.setVapidDetails(VAPID_SUBJECT, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY);

  let runType = 'full';
  try {
    const body = await req.json();
    runType = body?.runType || 'full';
  } catch {}

  // ── Fetch current picks data ──────────────────────────────────
  let todayData;
  try {
    todayData = await fetchJSON(`${RAW_BASE}/dashboard/data/processed/today.json`);
  } catch (err) {
    console.error('send-notifications: failed to fetch today.json:', err.message);
    return json(500, { error: 'Could not fetch picks data' });
  }

  const date = todayData.date;
  const pitchers = todayData.pitchers || [];
  const currentPicks = getFirePicks(pitchers);

  // ── Load previous state ───────────────────────────────────────
  const stateStore = getStore({ name: 'notification-state', consistency: 'strong' });
  let prevState = null;
  try { prevState = await stateStore.get('latest', { type: 'json' }); } catch {}

  // ── Detect changes ────────────────────────────────────────────
  const notifications = [];
  const prevPicks = (prevState?.date === date) ? (prevState.picks || {}) : null;

  const isFire = (v) => v === 'FIRE 1u' || v === 'FIRE 2u';
  const fireEmoji = (v) => (v === 'FIRE 2u' ? '🔥🔥' : '🔥');

  if (prevPicks) {
    // 1. New FIRE picks + LEAN→FIRE upgrades
    for (const [key, pick] of Object.entries(currentPicks)) {
      const prev = prevPicks[key];
      if (!prev) {
        if (isFire(pick.verdict)) {
          notifications.push({
            title: `${fireEmoji(pick.verdict)} New FIRE Pick`,
            body: `${pick.pitcher} — ${pick.verdict} ${pick.side.toUpperCase()} ${pick.k_line} Ks`,
            tag: `new-${key}`,
          });
        }
      } else if (isFire(pick.verdict) && !isFire(prev.verdict)) {
        notifications.push({
          title: `${fireEmoji(pick.verdict)} Upgraded to ${pick.verdict}`,
          body: `${pick.pitcher} — ${pick.side.toUpperCase()} ${pick.k_line} Ks`,
          tag: `upgrade-${key}`,
        });
      }
    }

    // 2. Batched lock notifications
    const justLocked = [];
    for (const [key, pick] of Object.entries(currentPicks)) {
      if (pick.locked && !prevPicks[key]?.locked) justLocked.push(pick);
    }
    if (justLocked.length === 1) {
      const p = justLocked[0];
      notifications.push({
        title: `🔒 ${p.pitcher} Locked`,
        body: `${p.verdict} — ${p.side.toUpperCase()} ${p.k_line} Ks`,
        tag: `locked-${date}-${p.pitcher}`,
      });
    } else if (justLocked.length > 1) {
      const names = justLocked.map((p) => p.pitcher).join(', ');
      notifications.push({
        title: `🔒 ${justLocked.length} picks locked`,
        body: names.length > 140 ? names.slice(0, 137) + '…' : names,
        tag: `locked-batch-${date}-${Date.now()}`,
      });
    }
  } else {
    // First run of the day (or new slate) — announce FIRE picks
    const firePicks = Object.values(currentPicks).filter((p) => isFire(p.verdict));
    if (firePicks.length > 0) {
      const count = firePicks.length;
      const top = firePicks[0];
      notifications.push({
        title: `⚾ ${count} FIRE pick${count > 1 ? 's' : ''} today`,
        body: `${top.pitcher} — ${top.verdict} ${top.side.toUpperCase()} ${top.k_line} Ks`,
        tag: 'new-slate',
      });
    }
  }

  // 3. Daily results summary (grading run only)
  if (runType === 'grading') {
    let picksHistory;
    try {
      picksHistory = await fetchJSON(`${RAW_BASE}/data/picks_history.json`);
    } catch (err) {
      console.warn('send-notifications: could not fetch picks_history.json:', err.message);
    }

    if (picksHistory) {
      const nowPhx = new Date(Date.now() - 7 * 60 * 60 * 1000);
      const yPhx = new Date(nowPhx);
      yPhx.setUTCDate(yPhx.getUTCDate() - 1);
      const yDate = yPhx.toISOString().slice(0, 10);

      const graded = picksHistory.filter((p) => p.date === yDate && p.result != null);
      if (graded.length > 0) {
        const wins = graded.filter((p) => p.result === 'win').length;
        const losses = graded.filter((p) => p.result === 'loss').length;
        const pnl = graded.reduce((s, p) => s + (p.pnl || 0), 0);
        const sign = pnl >= 0 ? '+' : '';
        notifications.push({
          title: pnl >= 0
            ? `✅ Yesterday: ${wins}-${losses} (${sign}${pnl.toFixed(1)}u)`
            : `❌ Yesterday: ${wins}-${losses} (${sign}${pnl.toFixed(1)}u)`,
          body: `${graded.length} pick${graded.length > 1 ? 's' : ''} graded`,
          tag: `results-${yDate}`,
        });
      }
    }
  }

  // ── Persist new state regardless of whether we sent anything ─
  try {
    await stateStore.setJSON('latest', {
      date,
      picks: currentPicks,
      updatedAt: new Date().toISOString(),
    });
  } catch (err) {
    console.error('send-notifications: failed to save state:', err.message);
  }

  if (notifications.length === 0) {
    return json(200, { sent: 0, message: 'No changes detected' });
  }

  // ── Load subscribers and send ─────────────────────────────────
  const subStore = getStore({ name: 'push-subscriptions', consistency: 'strong' });
  let blobs;
  try {
    ({ blobs } = await subStore.list());
  } catch (err) {
    console.error('send-notifications: failed to list subscriptions:', err.message);
    return json(500, { error: 'Could not load subscriptions' });
  }

  if (!blobs || blobs.length === 0) {
    return json(200, { sent: 0, message: 'No subscribers' });
  }

  let sent = 0;
  const staleKeys = new Set();

  for (const blob of blobs) {
    let sub;
    try { sub = await subStore.get(blob.key, { type: 'json' }); } catch { continue; }
    if (!sub) continue;

    for (const notif of notifications) {
      try {
        await webPush.sendNotification(sub, JSON.stringify({ ...notif, url: '/' }));
        sent++;
      } catch (err) {
        if (err.statusCode === 404 || err.statusCode === 410) {
          staleKeys.add(blob.key);
        } else {
          console.error(`send-notifications: push failed for ${blob.key}:`, err.message);
        }
      }
    }
  }

  await Promise.allSettled([...staleKeys].map((k) => subStore.delete(k)));

  return json(200, {
    sent,
    notifications: notifications.length,
    subscribers: blobs.length,
    staleRemoved: staleKeys.size,
  });
};
