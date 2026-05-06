import { timingSafeEqual } from 'node:crypto';

const JSON_HEADERS = { 'Content-Type': 'application/json' };
const DEFAULT_BATCH_LIMIT = 10;
const MAX_BATCH_LIMIT = 25;

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

export function envValue(name) {
  return globalThis.Netlify?.env?.get?.(name) || process.env[name] || '';
}

function safeSecretEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

export function isLiveNotificationsEnabled(value) {
  const normalized = String(value || '').trim().toLowerCase();
  return normalized === 'true' || normalized === '1' || normalized === 'yes';
}

function supabaseHeaders(serviceRoleKey, prefer = 'return=representation') {
  return {
    apikey: serviceRoleKey,
    Authorization: `Bearer ${serviceRoleKey}`,
    'Content-Type': 'application/json',
    Prefer: prefer,
  };
}

export function buildPushPayload(row) {
  return {
    title: row.title,
    body: row.body,
    tag: row.dedupe_key || row.id,
    url: row.url || '/',
    data: {
      eventId: row.id,
      eventType: row.event_type,
      slateDate: row.slate_date,
      severity: row.severity,
      payload: row.payload || {},
    },
  };
}

export async function fetchPendingNotificationEvents({
  supabaseUrl,
  serviceRoleKey,
  limit = DEFAULT_BATCH_LIMIT,
}) {
  const safeLimit = Math.max(1, Math.min(Number(limit) || DEFAULT_BATCH_LIMIT, MAX_BATCH_LIMIT));
  const params = new URLSearchParams({
    select: 'id,slate_date,event_type,severity,title,body,url,dedupe_key,payload,occurred_at,send_attempts',
    sent_at: 'is.null',
    send_attempts: 'lt.3',
    order: 'occurred_at.asc',
    limit: String(safeLimit),
  });
  const response = await fetch(
    `${supabaseUrl.replace(/\/$/, '')}/rest/v1/notification_events?${params}`,
    { headers: supabaseHeaders(serviceRoleKey) },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`supabase_pending_failed:${response.status}:${text.slice(0, 500)}`);
  }
  return response.json();
}

async function patchNotificationEvent({ supabaseUrl, serviceRoleKey, id, patch }) {
  const params = new URLSearchParams({ id: `eq.${id}` });
  const response = await fetch(
    `${supabaseUrl.replace(/\/$/, '')}/rest/v1/notification_events?${params}`,
    {
      method: 'PATCH',
      headers: supabaseHeaders(serviceRoleKey, 'return=minimal'),
      body: JSON.stringify(patch),
    },
  );
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`supabase_patch_failed:${response.status}:${text.slice(0, 500)}`);
  }
}

async function markSent({ supabaseUrl, serviceRoleKey, row, sentAt }) {
  await patchNotificationEvent({
    supabaseUrl,
    serviceRoleKey,
    id: row.id,
    patch: {
      sent_at: sentAt,
      send_attempts: Number(row.send_attempts || 0) + 1,
      last_send_error: null,
    },
  });
}

async function markFailed({ supabaseUrl, serviceRoleKey, row, error }) {
  await patchNotificationEvent({
    supabaseUrl,
    serviceRoleKey,
    id: row.id,
    patch: {
      send_attempts: Number(row.send_attempts || 0) + 1,
      last_send_error: String(error || 'send_failed').slice(0, 1000),
    },
  });
}

async function loadSubscriptions() {
  const { getStore } = await import('@netlify/blobs');
  const subStore = getStore({ name: 'push-subscriptions', consistency: 'strong' });
  const { blobs } = await subStore.list();
  const subscriptions = [];
  for (const blob of blobs || []) {
    const subscription = await subStore.get(blob.key, { type: 'json' }).catch(() => null);
    if (subscription) subscriptions.push({ key: blob.key, subscription });
  }
  return { subStore, subscriptions };
}

async function sendToSubscriptions({ rows, subscriptions, vapid }) {
  const webPush = (await import('web-push')).default;
  webPush.setVapidDetails(vapid.subject, vapid.publicKey, vapid.privateKey);

  const staleKeys = new Set();
  const sentByEventId = new Map(rows.map((row) => [row.id, 0]));
  const errorsByEventId = new Map();

  for (const { key, subscription } of subscriptions) {
    for (const row of rows) {
      try {
        await webPush.sendNotification(subscription, JSON.stringify(buildPushPayload(row)));
        sentByEventId.set(row.id, (sentByEventId.get(row.id) || 0) + 1);
      } catch (error) {
        if (error.statusCode === 404 || error.statusCode === 410) {
          staleKeys.add(key);
        } else {
          errorsByEventId.set(row.id, error.message || 'push_failed');
        }
      }
    }
  }

  return { staleKeys, sentByEventId, errorsByEventId };
}

export default async function sendLiveNotifications(req) {
  if (req.method !== 'POST') return json(405, { error: 'Method not allowed' });

  let body = {};
  try {
    body = await req.json();
  } catch {}

  const isScheduledRun = typeof body?.next_run === 'string';
  const notifySecret = envValue('NOTIFY_SECRET');
  if (!isScheduledRun && (!notifySecret || !safeSecretEqual(req.headers.get('x-notify-secret') || '', notifySecret))) {
    return json(401, { error: 'Unauthorized' });
  }

  const supabaseUrl = envValue('SUPABASE_URL');
  const serviceRoleKey = envValue('SUPABASE_SERVICE_ROLE_KEY');
  if (!supabaseUrl || !serviceRoleKey) {
    return json(500, { error: 'Supabase not configured' });
  }

  let pending;
  try {
    pending = await fetchPendingNotificationEvents({
      supabaseUrl,
      serviceRoleKey,
      limit: body?.limit,
    });
  } catch (error) {
    console.error('send-live-notifications: failed to read queue', error.message);
    return json(500, { error: 'Could not read notification queue' });
  }

  if (pending.length === 0) {
    return json(200, { sent: 0, pending: 0, message: 'No pending live notifications' });
  }

  const enabled = isLiveNotificationsEnabled(envValue('LIVE_NOTIFICATIONS_ENABLED'));
  if (!enabled) {
    return json(200, {
      mode: 'dry_run',
      enabled: false,
      pending: pending.length,
      events: pending.map((row) => ({
        id: row.id,
        event_type: row.event_type,
        title: row.title,
        body: row.body,
      })),
    });
  }

  const vapid = {
    publicKey: envValue('VAPID_PUBLIC_KEY'),
    privateKey: envValue('VAPID_PRIVATE_KEY'),
    subject: envValue('VAPID_SUBJECT'),
  };
  if (!vapid.publicKey || !vapid.privateKey || !vapid.subject) {
    return json(500, { error: 'VAPID not configured' });
  }

  let subStore;
  let subscriptions;
  try {
    ({ subStore, subscriptions } = await loadSubscriptions());
  } catch (error) {
    console.error('send-live-notifications: failed to load subscriptions', error.message);
    return json(500, { error: 'Could not load subscriptions' });
  }

  if (subscriptions.length === 0) {
    return json(200, { sent: 0, pending: pending.length, subscribers: 0, message: 'No subscribers' });
  }

  const { staleKeys, sentByEventId, errorsByEventId } = await sendToSubscriptions({
    rows: pending,
    subscriptions,
    vapid,
  });

  const sentAt = new Date().toISOString();
  let sent = 0;
  let failed = 0;
  for (const row of pending) {
    const eventSent = sentByEventId.get(row.id) || 0;
    if (eventSent > 0) {
      await markSent({ supabaseUrl, serviceRoleKey, row, sentAt });
      sent += eventSent;
    } else {
      await markFailed({
        supabaseUrl,
        serviceRoleKey,
        row,
        error: errorsByEventId.get(row.id) || 'no_successful_subscriber_send',
      });
      failed += 1;
    }
  }

  await Promise.allSettled([...staleKeys].map((key) => subStore.delete(key)));

  return json(200, {
    sent,
    failed,
    notifications: pending.length,
    subscribers: subscriptions.length,
    staleRemoved: staleKeys.size,
  });
}

export const config = {
  schedule: '*/10 * * * *',
};
