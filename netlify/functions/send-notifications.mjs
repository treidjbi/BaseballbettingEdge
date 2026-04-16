/**
 * send-notifications — Netlify Functions v2
 * Called by GitHub Actions after each pipeline commit.
 * Reads today's picks, compares to last-known state stored in Netlify Blobs,
 * and fires push notifications for meaningful changes:
 *   - New FIRE picks appearing on the slate
 *   - LEAN → FIRE upgrades
 *   - Picks transitioning to locked (batched if multiple in one run)
 *   - Game-time reminders (~30 min before first pitch, one per pick, deduped)
 *   - Daily results summary (grading run only)
 *
 * Required Netlify env vars:
 *   VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT, NOTIFY_SECRET
 */
import webPush from 'web-push';
import { getStore } from '@netlify/blobs';
import { timingSafeEqual } from 'node:crypto';

const RAW_BASE = 'https://raw.githubusercontent.com/treidjbi/baseballbettingedge/main';

/**
 * Constant-time string compare. Protects against timing attacks on the shared
 * NOTIFY_SECRET since the function is exposed on the public internet.
 * Returns false for any length mismatch or non-string input without leaking
 * where the strings diverge.
 */
function safeSecretEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

/**
 * Current date in America/Phoenix (UTC-7, no DST) as "YYYY-MM-DD".
 * Replaces the hardcoded `Date.now() - 7*60*60*1000` math so the day boundary
 * matches the user's local day even if Node's default TZ differs.
 */
function phoenixDateString(d = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Phoenix',
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(d);
}

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
        game_time: p.game_time || null,
      };
    }
  }
  return picks;
}

export default async (req) => {
  if (req.method !== 'POST') return json(405, { error: 'Method not allowed' });

  const { NOTIFY_SECRET, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT } = process.env;

  if (!NOTIFY_SECRET || !safeSecretEqual(req.headers.get('x-notify-secret') || '', NOTIFY_SECRET)) {
    return json(401, { error: 'Unauthorized' });
  }
  if (!VAPID_PUBLIC_KEY || !VAPID_PRIVATE_KEY || !VAPID_SUBJECT) {
    console.error('send-notifications: VAPID env vars not set');
    return json(500, { error: 'VAPID not configured' });
  }

  webPush.setVapidDetails(VAPID_SUBJECT, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY);

  let runType = 'full';
  let isTest = false;
  try {
    const body = await req.json();
    runType = body?.runType || 'full';
    isTest = body?.test === true;
  } catch {}

  // ── Test mode — send a single dummy push to all subscribers ───
  if (isTest) {
    const subStore = getStore({ name: 'push-subscriptions', consistency: 'strong' });
    const { blobs } = await subStore.list();
    if (!blobs || blobs.length === 0) return json(200, { sent: 0, message: 'No subscribers' });

    const testNotif = {
      title: '⚾ Test notification',
      body: 'Push notifications are working!',
      tag: `test-${Date.now()}`,
      url: '/',
    };

    let sent = 0;
    const staleKeys = new Set();
    for (const blob of blobs) {
      const sub = await subStore.get(blob.key, { type: 'json' }).catch(() => null);
      if (!sub) continue;
      try {
        await webPush.sendNotification(sub, JSON.stringify(testNotif));
        sent++;
      } catch (err) {
        if (err.statusCode === 404 || err.statusCode === 410) staleKeys.add(blob.key);
        else console.error(`test push failed for ${blob.key}:`, err.message);
      }
    }
    await Promise.allSettled([...staleKeys].map((k) => subStore.delete(k)));
    return json(200, { sent, subscribers: blobs.length, mode: 'test' });
  }

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
      // Tag uses date + sorted pitcher keys only — omitting Date.now() lets the
      // OS deduplicate if the same batch re-fires (e.g., pipeline retries) so
      // users don't see "5 picks locked" twice in five minutes.
      const batchKey = justLocked.map((p) => `${p.pitcher}|${p.side}`).sort().join('~');
      notifications.push({
        title: `🔒 ${justLocked.length} picks locked`,
        body: names.length > 140 ? names.slice(0, 137) + '…' : names,
        tag: `locked-batch-${date}-${batchKey}`,
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

  // 3. Game-time reminders: "go bet this" alerts ~30 min before first pitch.
  //    Fires once per pick (deduped via `reminded` set in state blob).
  //    Window: 5–75 min before game_time. With 30-min pipeline cadence,
  //    each pick hits this window on exactly one run.
  const REMINDER_MIN_MS = 5 * 60 * 1000;
  const REMINDER_MAX_MS = 75 * 60 * 1000;
  const now = Date.now();
  const prevReminded = new Set(
    (prevState?.date === date) ? (prevState.reminded || []) : []
  );
  const newReminded = new Set(prevReminded);

  if (runType === 'full') {
    for (const [key, pick] of Object.entries(currentPicks)) {
      if (pick.locked || !pick.game_time || prevReminded.has(key)) continue;

      const gameMs = new Date(pick.game_time).getTime();
      if (Number.isNaN(gameMs)) continue;
      const minsUntil = Math.round((gameMs - now) / 60_000);
      const msUntil = gameMs - now;

      if (msUntil >= REMINDER_MIN_MS && msUntil <= REMINDER_MAX_MS) {
        const verdictEmoji = pick.verdict.startsWith('FIRE') ? '🔥' : '📋';
        notifications.push({
          title: `⏰ ${pick.pitcher} ${pick.side.toUpperCase()} ${pick.k_line} Ks`,
          body: `${verdictEmoji} ${pick.verdict} — first pitch ~${minsUntil} min`,
          tag: `reminder-${date}-${key}`,
          renotify: true,
        });
        newReminded.add(key);
      }
    }
  }

  // 4. Daily results summary (grading run only)
  if (runType === 'grading') {
    let picksHistory;
    try {
      picksHistory = await fetchJSON(`${RAW_BASE}/data/picks_history.json`);
    } catch (err) {
      console.warn('send-notifications: could not fetch picks_history.json:', err.message);
    }

    if (picksHistory) {
      // "Yesterday" from the user's perspective = Phoenix-local yesterday.
      // Compute today in Phoenix, then subtract one day — correct regardless
      // of Netlify runtime TZ and stable across the 11pm→midnight boundary.
      const todayPhx = phoenixDateString();              // e.g. "2026-04-13"
      const [y, m, d] = todayPhx.split('-').map(Number);
      const yesterday = new Date(Date.UTC(y, m - 1, d));
      yesterday.setUTCDate(yesterday.getUTCDate() - 1);
      const yDate = yesterday.toISOString().slice(0, 10);

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
      reminded: [...newReminded],
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
