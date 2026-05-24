import { timingSafeEqual } from 'node:crypto';

const JSON_HEADERS = { 'Content-Type': 'application/json' };
const DEFAULT_BATCH_LIMIT = 10;
const MAX_BATCH_LIMIT = 25;
const DEFAULT_MAX_EVENT_AGE_MINUTES = 20;
const DEFAULT_SUPABASE_URL = 'https://htoaytcsjrdyyzcwxjfg.supabase.co';

export function json(status, body) {
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

export function notificationMaxAgeMinutes(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return DEFAULT_MAX_EVENT_AGE_MINUTES;
  return Math.max(1, Math.min(parsed, 240));
}

export function isNotificationEventStale(row, {
  now = new Date(),
  maxAgeMinutes = DEFAULT_MAX_EVENT_AGE_MINUTES,
} = {}) {
  if (!row?.occurred_at) return false;
  const occurredAt = new Date(row.occurred_at);
  const nowDate = now instanceof Date ? now : new Date(now);
  if (Number.isNaN(occurredAt.getTime()) || Number.isNaN(nowDate.getTime())) return false;
  return nowDate.getTime() - occurredAt.getTime() > maxAgeMinutes * 60 * 1000;
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

export function buildSenderLog({
  stage,
  enabled,
  pending = 0,
  subscribers = 0,
  sent = 0,
  failed = 0,
  staleRemoved = 0,
  staleSuppressed = 0,
}) {
  return [
    'send-live-notifications',
    `stage=${stage}`,
    `enabled=${Boolean(enabled)}`,
    `pending=${Number(pending) || 0}`,
    `subscribers=${Number(subscribers) || 0}`,
    `sent=${Number(sent) || 0}`,
    `failed=${Number(failed) || 0}`,
    `staleRemoved=${Number(staleRemoved) || 0}`,
    `staleSuppressed=${Number(staleSuppressed) || 0}`,
  ].join(' ');
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

async function markStale({ supabaseUrl, serviceRoleKey, row, maxAgeMinutes }) {
  await patchNotificationEvent({
    supabaseUrl,
    serviceRoleKey,
    id: row.id,
    patch: {
      send_attempts: 3,
      last_send_error: `suppressed_stale_live_notification:max_age_minutes=${maxAgeMinutes}`,
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

export async function sendLiveNotifications(req, { requiresSharedSecret }) {
  if (requiresSharedSecret && req.method !== 'POST') return json(405, { error: 'Method not allowed' });

  let body = {};
  try {
    body = await req.json();
  } catch {}

  if (body?.smoke_check === true && !requiresSharedSecret) {
    return json(401, { error: 'Unauthorized' });
  }

  const notifySecret = envValue('NOTIFY_SECRET');
  if (requiresSharedSecret && (!notifySecret || !safeSecretEqual(req.headers.get('x-notify-secret') || '', notifySecret))) {
    return json(401, { error: 'Unauthorized' });
  }

  const supabaseUrl = envValue('SUPABASE_URL') || DEFAULT_SUPABASE_URL;
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

  const enabled = isLiveNotificationsEnabled(envValue('LIVE_NOTIFICATIONS_ENABLED'));
  const maxAgeMinutes = notificationMaxAgeMinutes(envValue('LIVE_NOTIFICATION_MAX_EVENT_AGE_MINUTES'));
  const now = new Date();
  const staleRows = pending.filter((row) => isNotificationEventStale(row, { now, maxAgeMinutes }));
  const freshRows = pending.filter((row) => !isNotificationEventStale(row, { now, maxAgeMinutes }));

  if (body?.smoke_check === true) {
    let subscriptions;
    try {
      ({ subscriptions } = await loadSubscriptions());
    } catch (error) {
      console.error('send-live-notifications: smoke check failed to load subscriptions', error.message);
      return json(500, { error: 'Could not load subscriptions during smoke check' });
    }
    console.log(buildSenderLog({
      stage: 'smoke_check',
      enabled,
      pending: pending.length,
      subscribers: subscriptions.length,
      staleSuppressed: staleRows.length,
    }));
    return json(200, {
      mode: 'smoke_check',
      enabled,
      pending: pending.length,
      stale: staleRows.length,
      subscribers: subscriptions.length,
      sends: 0,
    });
  }

  if (pending.length === 0) {
    console.log(buildSenderLog({ stage: 'empty_queue', enabled }));
    return json(200, { enabled, sent: 0, pending: 0, message: 'No pending live notifications' });
  }

  if (!enabled) {
    console.log(buildSenderLog({ stage: 'dry_run', enabled, pending: pending.length }));
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

  for (const row of staleRows) {
    await markStale({ supabaseUrl, serviceRoleKey, row, maxAgeMinutes });
  }

  if (freshRows.length === 0) {
    console.log(buildSenderLog({
      stage: 'stale_queue',
      enabled,
      pending: 0,
      staleSuppressed: staleRows.length,
    }));
    return json(200, {
      enabled,
      sent: 0,
      pending: 0,
      staleSuppressed: staleRows.length,
      message: 'No fresh live notifications',
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
    console.log(buildSenderLog({
      stage: 'no_subscribers',
      enabled,
      pending: freshRows.length,
      staleSuppressed: staleRows.length,
    }));
    return json(200, {
      enabled,
      sent: 0,
      pending: freshRows.length,
      staleSuppressed: staleRows.length,
      subscribers: 0,
      message: 'No subscribers',
    });
  }

  const { staleKeys, sentByEventId, errorsByEventId } = await sendToSubscriptions({
    rows: freshRows,
    subscriptions,
    vapid,
  });

  const sentAt = new Date().toISOString();
  let sent = 0;
  let failed = 0;
  for (const row of freshRows) {
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

  console.log(buildSenderLog({
    stage: 'sent',
    enabled,
    pending: freshRows.length,
    subscribers: subscriptions.length,
    sent,
    failed,
    staleRemoved: staleKeys.size,
    staleSuppressed: staleRows.length,
  }));

  return json(200, {
    enabled,
    sent,
    failed,
    notifications: freshRows.length,
    staleSuppressed: staleRows.length,
    subscribers: subscriptions.length,
    staleRemoved: staleKeys.size,
  });
}
