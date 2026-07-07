import test from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';

import {
  buildPushPayload,
  buildSenderLog,
  envValue,
  fetchPendingNotificationEvents,
  isNotificationEventPostStart,
  isNotificationEventStale,
  isLiveNotificationsEnabled,
  notificationMaxAgeMinutes,
} from '../netlify/functions/_shared/live-notification-sender.mjs';
import sendLiveNotificationsNow, {
  config as httpConfig,
} from '../netlify/functions/send-live-notifications-now.mjs';
import sendLiveNotificationsScheduled, {
  config as scheduledConfig,
} from '../netlify/functions/send-live-notifications.mjs';

const notificationTestState = globalThis.__bbeNotificationTestState ??= {
  webPush: {
    setVapidDetailsCalls: [],
    sendNotificationCalls: [],
  },
  blobs: {
    listCalls: 0,
    getCalls: [],
    deleteCalls: [],
    subscriptions: {},
    listBlobs: [],
  },
};

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === 'web-push') return { url: 'mock:web-push', shortCircuit: true };
    if (specifier === '@netlify/blobs') return { url: 'mock:@netlify/blobs', shortCircuit: true };
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === 'mock:web-push') {
      return {
        format: 'module',
        shortCircuit: true,
        source: `
          const runtime = globalThis.__bbeNotificationTestState;
          export default {
            setVapidDetails(...args) {
              runtime.webPush.setVapidDetailsCalls.push(args);
            },
            async sendNotification(subscription, payload) {
              runtime.webPush.sendNotificationCalls.push({ subscription, payload });
            },
          };
        `,
      };
    }
    if (url === 'mock:@netlify/blobs') {
      return {
        format: 'module',
        shortCircuit: true,
        source: `
          export function getStore() {
            const runtime = globalThis.__bbeNotificationTestState;
            return {
              async list() {
                runtime.blobs.listCalls += 1;
                return { blobs: runtime.blobs.listBlobs };
              },
              async get(key, options) {
                runtime.blobs.getCalls.push({ key, options });
                return runtime.blobs.subscriptions[key] || null;
              },
              async delete(key) {
                runtime.blobs.deleteCalls.push(key);
                delete runtime.blobs.subscriptions[key];
              },
            };
          }
        `,
      };
    }
    return nextLoad(url, context);
  },
});

function resetNotificationTestState() {
  notificationTestState.webPush.setVapidDetailsCalls.length = 0;
  notificationTestState.webPush.sendNotificationCalls.length = 0;
  notificationTestState.blobs.listCalls = 0;
  notificationTestState.blobs.getCalls.length = 0;
  notificationTestState.blobs.deleteCalls.length = 0;
  notificationTestState.blobs.subscriptions = {};
  notificationTestState.blobs.listBlobs = [];
}

function eventRow(overrides = {}) {
  return {
    id: 'event-1',
    slate_date: '2026-07-07',
    event_type: 'mainline_best_price_changed',
    severity: 'action',
    title: 'Best Price Better Now',
    body: 'Jacob Misiorowski OVER 7.5 best price -120->-105 at fanduel; same main line, price better',
    dedupe_key: '2026-07-07:mainline_best_price:propline:jacob misiorowski:over:7.5:-120:fanduel:-105',
    occurred_at: '2099-07-07T18:30:00Z',
    payload: {
      pitcher: 'Jacob Misiorowski',
      normalized_pitcher: 'jacob misiorowski',
      side: 'over',
      provider: 'propline',
      k_line: 7.5,
      previous_best_book: 'fanduel',
      previous_best_odds: -120,
      current_best_book: 'fanduel',
      current_best_odds: -105,
      price_delta: 15,
      game_time: '2099-07-07T23:40:00Z',
    },
    ...overrides,
  };
}

function subscriptionRow(key = 'sub-1') {
  return {
    key,
    subscription: {
      endpoint: 'https://push.example.test/send/sub-1',
      keys: { p256dh: 'p256dh-key', auth: 'auth-key' },
    },
  };
}

test('isLiveNotificationsEnabled is false unless explicitly enabled', () => {
  assert.equal(isLiveNotificationsEnabled(''), false);
  assert.equal(isLiveNotificationsEnabled('false'), false);
  assert.equal(isLiveNotificationsEnabled('TRUE'), true);
  assert.equal(isLiveNotificationsEnabled('1'), true);
});

test('buildPushPayload maps live event rows to push payloads', () => {
  const payload = buildPushPayload({
    id: 'event-1',
    title: 'New FIRE Pick',
    body: 'Tarik Skubal FIRE 1u OVER 6.5 Ks',
    url: '/?pitcher=tarik-skubal',
    dedupe_key: '2026-05-06:new_fire_pick:tarik skubal:over:FIRE 1u:6.5',
    event_type: 'new_fire_pick',
  });

  assert.equal(payload.title, 'New FIRE Pick');
  assert.equal(payload.body, 'Tarik Skubal FIRE 1u OVER 6.5 Ks');
  assert.equal(payload.url, '/?pitcher=tarik-skubal');
  assert.equal(payload.tag, '2026-05-06:new_fire_pick:tarik skubal:over:FIRE 1u:6.5');
  assert.equal(payload.data.eventId, 'event-1');
  assert.equal(payload.data.eventType, 'new_fire_pick');
});

test('buildPushPayload adds alert attribution context to default click urls', () => {
  const payload = buildPushPayload({
    id: 'event-2',
    title: 'Playable price',
    body: 'Jameson Taillon UNDER 4.5 Ks',
    url: '/',
    event_type: 'line_movement',
    slate_date: '2026-06-07',
    payload: {
      pitcher: 'Jameson Taillon',
      side: 'UNDER',
      decision_label: 'playable_price',
      observed_at: '2026-06-07T21:30:00Z',
      source_artifact_sha256: 'sha-1',
    },
  });

  const url = new URL(payload.url, 'https://example.test');
  assert.equal(url.pathname, '/v2.html');
  assert.equal(url.searchParams.get('marketSheet'), '1');
  assert.equal(url.searchParams.get('notification_event_id'), 'event-2');
  assert.equal(url.searchParams.get('slate_date'), '2026-06-07');
  assert.equal(url.searchParams.get('pitcher'), 'Jameson Taillon');
  assert.equal(url.searchParams.get('side'), 'UNDER');
  assert.equal(url.searchParams.get('decision_label'), 'playable_price');
  assert.equal(url.searchParams.get('source'), 'notification');
});

test('buildPushPayload keeps mainline best price rows on the generic sender path', () => {
  const row = eventRow();
  const payload = buildPushPayload(row);

  assert.equal(payload.title, row.title);
  assert.equal(payload.body, row.body);
  assert.equal(payload.tag, row.dedupe_key);
  assert.equal(payload.data.eventType, 'mainline_best_price_changed');
  assert.equal(payload.data.payload.current_best_odds, -105);
  assert.equal(
    isNotificationEventPostStart(
      eventRow({
        payload: {
          ...eventRow().payload,
          game_time: '2026-07-07T23:40:00Z',
        },
      }),
      { now: new Date('2026-07-07T23:40:00Z') },
    ),
    true,
  );
});

test('sender sends mainline best price rows through the existing push flow', async () => {
  resetNotificationTestState();
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalEnv = {
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    LIVE_NOTIFICATIONS_ENABLED: process.env.LIVE_NOTIFICATIONS_ENABLED,
    VAPID_PUBLIC_KEY: process.env.VAPID_PUBLIC_KEY,
    VAPID_PRIVATE_KEY: process.env.VAPID_PRIVATE_KEY,
    VAPID_SUBJECT: process.env.VAPID_SUBJECT,
  };
  process.env.NOTIFY_SECRET = 'notify-secret';
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';
  process.env.LIVE_NOTIFICATIONS_ENABLED = 'true';
  process.env.VAPID_PUBLIC_KEY = 'public-key';
  process.env.VAPID_PRIVATE_KEY = 'private-key';
  process.env.VAPID_SUBJECT = 'mailto:test@example.com';
  notificationTestState.blobs.listBlobs = [subscriptionRow()];
  notificationTestState.blobs.subscriptions = {
    'sub-1': subscriptionRow().subscription,
  };

  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    if (!options.method || options.method === 'GET') {
      return new Response(JSON.stringify([eventRow()]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response('', { status: 200 });
  };

  try {
    const response = await sendLiveNotificationsNow(new Request('https://example.test/api/send-live-notifications-now', {
      method: 'POST',
      headers: { 'x-notify-secret': 'notify-secret' },
      body: JSON.stringify({ limit: 1 }),
    }));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.sent, 1);
    assert.equal(payload.notifications, 1);
    assert.equal(notificationTestState.webPush.sendNotificationCalls.length, 1);
    assert.equal(notificationTestState.webPush.setVapidDetailsCalls.length, 1);
    assert.equal(calls.filter((call) => !call.options.method || call.options.method === 'GET').length, 1);
    const pushPayload = JSON.parse(notificationTestState.webPush.sendNotificationCalls[0].payload);
    assert.equal(pushPayload.title, 'Best Price Better Now');
    assert.equal(pushPayload.tag, eventRow().dedupe_key);
    assert.equal(pushPayload.data.eventType, 'mainline_best_price_changed');
    assert.equal(pushPayload.data.payload.current_best_odds, -105);
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});

test('sender suppresses post-start mainline best price rows through the same flow', async () => {
  resetNotificationTestState();
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalEnv = {
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    LIVE_NOTIFICATIONS_ENABLED: process.env.LIVE_NOTIFICATIONS_ENABLED,
    VAPID_PUBLIC_KEY: process.env.VAPID_PUBLIC_KEY,
    VAPID_PRIVATE_KEY: process.env.VAPID_PRIVATE_KEY,
    VAPID_SUBJECT: process.env.VAPID_SUBJECT,
  };
  process.env.NOTIFY_SECRET = 'notify-secret';
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';
  process.env.LIVE_NOTIFICATIONS_ENABLED = 'true';
  process.env.VAPID_PUBLIC_KEY = 'public-key';
  process.env.VAPID_PRIVATE_KEY = 'private-key';
  process.env.VAPID_SUBJECT = 'mailto:test@example.com';
  notificationTestState.blobs.listBlobs = [subscriptionRow()];
  notificationTestState.blobs.subscriptions = {
    'sub-1': subscriptionRow().subscription,
  };

  const row = eventRow({
    payload: {
      ...eventRow().payload,
      occurred_at: '2099-07-07T18:30:00Z',
      game_time: '2026-07-06T18:35:00Z',
    },
  });

  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    if (!options.method || options.method === 'GET') {
      return new Response(JSON.stringify([row]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response('', { status: 200 });
  };

  try {
    const response = await sendLiveNotificationsNow(new Request('https://example.test/api/send-live-notifications-now', {
      method: 'POST',
      headers: { 'x-notify-secret': 'notify-secret' },
      body: JSON.stringify({ limit: 1 }),
    }));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.sent, 0);
    assert.equal(payload.postStartSuppressed, 1);
    assert.equal(notificationTestState.webPush.sendNotificationCalls.length, 0);
    assert.equal(calls.some((call) => call.options.method === 'PATCH'), true);
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});

test('buildSenderLog produces inspectable non-secret telemetry', () => {
  const line = buildSenderLog({
    stage: 'dry_run',
    enabled: false,
    pending: 16,
    subscribers: 0,
    sent: 0,
    failed: 0,
  });

  assert.equal(
    line,
    'send-live-notifications stage=dry_run enabled=false pending=16 subscribers=0 sent=0 failed=0 staleRemoved=0 staleSuppressed=0',
  );
  assert.equal(line.includes('SUPABASE_SERVICE_ROLE_KEY'), false);
});

test('notification age guard uses a bounded positive TTL', () => {
  assert.equal(notificationMaxAgeMinutes(''), 20);
  assert.equal(notificationMaxAgeMinutes('-5'), 20);
  assert.equal(notificationMaxAgeMinutes('7'), 7);
  assert.equal(notificationMaxAgeMinutes('9999'), 240);
});

test('isNotificationEventStale compares occurred_at against max age', () => {
  const now = new Date('2026-05-24T22:40:00Z');

  assert.equal(
    isNotificationEventStale(
      { occurred_at: '2026-05-24T22:19:59Z' },
      { now, maxAgeMinutes: 20 },
    ),
    true,
  );
  assert.equal(
    isNotificationEventStale(
      { occurred_at: '2026-05-24T22:20:01Z' },
      { now, maxAgeMinutes: 20 },
    ),
    false,
  );
  assert.equal(isNotificationEventStale({ occurred_at: 'not-a-date' }, { now }), false);
  assert.equal(isNotificationEventStale({}, { now }), false);
});

test('fetchPendingNotificationEvents reads unsent queue through Supabase REST', async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify([{ id: 'event-1' }]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  try {
    const rows = await fetchPendingNotificationEvents({
      supabaseUrl: 'https://example.supabase.co/',
      serviceRoleKey: 'service-key',
      limit: 7,
    });

    assert.deepEqual(rows, [{ id: 'event-1' }]);
    assert.equal(calls.length, 1);
    assert.match(calls[0].url, /\/rest\/v1\/notification_events\?/);
    assert.match(calls[0].url, /sent_at=is\.null/);
    assert.match(calls[0].url, /limit=7/);
    assert.equal(calls[0].options.headers.apikey, 'service-key');
    assert.equal(calls[0].options.headers.Authorization, 'Bearer service-key');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('envValue prefers Netlify env with process fallback', () => {
  const originalNetlify = globalThis.Netlify;
  const originalProcessValue = process.env.SEND_LIVE_TEST_ENV;
  process.env.SEND_LIVE_TEST_ENV = 'process-value';
  globalThis.Netlify = {
    env: {
      get(name) {
        return name === 'SEND_LIVE_TEST_ENV' ? 'netlify-value' : '';
      },
    },
  };

  try {
    assert.equal(envValue('SEND_LIVE_TEST_ENV'), 'netlify-value');
  } finally {
    globalThis.Netlify = originalNetlify;
    if (originalProcessValue === undefined) {
      delete process.env.SEND_LIVE_TEST_ENV;
    } else {
      process.env.SEND_LIVE_TEST_ENV = originalProcessValue;
    }
  }
});

test('handler returns dry-run events when live notifications are disabled', async () => {
  const originalFetch = globalThis.fetch;
  const originalEnv = {
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    LIVE_NOTIFICATIONS_ENABLED: process.env.LIVE_NOTIFICATIONS_ENABLED,
  };
  process.env.NOTIFY_SECRET = 'notify-secret';
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';
  process.env.LIVE_NOTIFICATIONS_ENABLED = 'false';

  globalThis.fetch = async () => new Response(JSON.stringify([{
    id: 'event-1',
    event_type: 'new_fire_pick',
    title: 'New FIRE Pick',
    body: 'Tarik Skubal FIRE 1u OVER 6.5 Ks',
    dedupe_key: 'event-1-key',
  }]), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

  try {
    const response = await sendLiveNotificationsNow(new Request('https://example.test/api/send-live-notifications-now', {
      method: 'POST',
      headers: { 'x-notify-secret': 'notify-secret' },
      body: JSON.stringify({ limit: 3 }),
    }));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.mode, 'dry_run');
    assert.equal(payload.pending, 1);
    assert.equal(payload.events[0].event_type, 'new_fire_pick');
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});

test('handler falls back to known Supabase project URL when env URL is missing', async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalEnv = {
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    LIVE_NOTIFICATIONS_ENABLED: process.env.LIVE_NOTIFICATIONS_ENABLED,
  };
  process.env.NOTIFY_SECRET = 'notify-secret';
  delete process.env.SUPABASE_URL;
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';
  process.env.LIVE_NOTIFICATIONS_ENABLED = 'false';

  globalThis.fetch = async (url) => {
    calls.push(url);
    return new Response(JSON.stringify([{
      id: 'event-1',
      event_type: 'new_fire_pick',
      title: 'New FIRE Pick',
      body: 'Tarik Skubal FIRE 1u OVER 6.5 Ks',
      dedupe_key: 'event-1-key',
    }]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  try {
    const response = await sendLiveNotificationsNow(new Request('https://example.test/api/send-live-notifications-now', {
      method: 'POST',
      headers: { 'x-notify-secret': 'notify-secret' },
      body: JSON.stringify({ limit: 3 }),
    }));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.mode, 'dry_run');
    assert.equal(payload.pending, 1);
    assert.match(calls[0], /^https:\/\/htoaytcsjrdyyzcwxjfg\.supabase\.co\/rest\/v1\/notification_events/);
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});

test('scheduled handler can dry-run without notify secret header', async () => {
  const originalFetch = globalThis.fetch;
  const originalEnv = {
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    LIVE_NOTIFICATIONS_ENABLED: process.env.LIVE_NOTIFICATIONS_ENABLED,
  };
  delete process.env.NOTIFY_SECRET;
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';
  process.env.LIVE_NOTIFICATIONS_ENABLED = 'false';

  globalThis.fetch = async () => new Response(JSON.stringify([{
    id: 'event-1',
    event_type: 'line_moved_against_us',
    title: 'Line Moved Against Us',
    body: 'Tarik Skubal OVER moved against us',
    dedupe_key: 'event-1-key',
  }]), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

  try {
    const response = await sendLiveNotificationsScheduled(new Request('https://example.test/.netlify/functions/send-live-notifications', {
      method: 'POST',
      body: JSON.stringify({ next_run: '2026-05-06T20:10:00Z' }),
    }));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.mode, 'dry_run');
    assert.equal(payload.pending, 1);
    assert.equal(scheduledConfig.schedule, '*/10 * * * *');
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});

test('scheduled function dry-runs without notify secret when Run now sends an empty body', async () => {
  const originalFetch = globalThis.fetch;
  const originalEnv = {
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    LIVE_NOTIFICATIONS_ENABLED: process.env.LIVE_NOTIFICATIONS_ENABLED,
  };
  delete process.env.NOTIFY_SECRET;
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';
  process.env.LIVE_NOTIFICATIONS_ENABLED = 'false';

  globalThis.fetch = async () => new Response(JSON.stringify([{
    id: 'event-1',
    event_type: 'new_fire_pick',
    title: 'New FIRE Pick',
    body: 'Tarik Skubal FIRE 1u OVER 6.5 Ks',
    dedupe_key: 'event-1-key',
  }]), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

  try {
    const response = await sendLiveNotificationsScheduled(new Request('https://example.test/.netlify/functions/send-live-notifications', {
      method: 'POST',
      body: '',
    }));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.mode, 'dry_run');
    assert.equal(payload.pending, 1);
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});

test('scheduled function dry-runs when Run now uses GET', async () => {
  const originalFetch = globalThis.fetch;
  const originalEnv = {
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    LIVE_NOTIFICATIONS_ENABLED: process.env.LIVE_NOTIFICATIONS_ENABLED,
  };
  delete process.env.NOTIFY_SECRET;
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';
  process.env.LIVE_NOTIFICATIONS_ENABLED = 'false';

  globalThis.fetch = async () => new Response(JSON.stringify([{
    id: 'event-1',
    event_type: 'pick_upgraded',
    title: 'Pick Upgraded',
    body: 'Miles Mikolas FIRE 1u UNDER 3.5 Ks',
    dedupe_key: 'event-1-key',
  }]), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

  try {
    const response = await sendLiveNotificationsScheduled(new Request('https://example.test/.netlify/functions/send-live-notifications', {
      method: 'GET',
    }));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.mode, 'dry_run');
    assert.equal(payload.pending, 1);
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});

test('scheduled public sender rejects smoke checks', async () => {
  const originalFetch = globalThis.fetch;
  let fetchCalled = false;
  globalThis.fetch = async () => {
    fetchCalled = true;
    return new Response('[]', { status: 200 });
  };

  try {
    const response = await sendLiveNotificationsScheduled(new Request('https://example.test/.netlify/functions/send-live-notifications', {
      method: 'POST',
      body: JSON.stringify({ smoke_check: true }),
    }));
    const payload = await response.json();

    assert.equal(response.status, 401);
    assert.equal(payload.error, 'Unauthorized');
    assert.equal(fetchCalled, false);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('http sender rejects missing notify secret', async () => {
  const originalEnv = {
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
  };
  process.env.NOTIFY_SECRET = 'notify-secret';

  try {
    const response = await sendLiveNotificationsNow(new Request('https://example.test/api/send-live-notifications-now', {
      method: 'POST',
      body: JSON.stringify({ limit: 1 }),
    }));
    const payload = await response.json();

    assert.equal(response.status, 401);
    assert.equal(payload.error, 'Unauthorized');
    assert.equal(httpConfig.path, '/api/send-live-notifications-now');
  } finally {
    if (originalEnv.NOTIFY_SECRET === undefined) delete process.env.NOTIFY_SECRET;
    else process.env.NOTIFY_SECRET = originalEnv.NOTIFY_SECRET;
  }
});

test('enabled sender suppresses stale queue rows instead of sending late alerts', async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalEnv = {
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    LIVE_NOTIFICATIONS_ENABLED: process.env.LIVE_NOTIFICATIONS_ENABLED,
    LIVE_NOTIFICATION_MAX_EVENT_AGE_MINUTES: process.env.LIVE_NOTIFICATION_MAX_EVENT_AGE_MINUTES,
  };
  process.env.NOTIFY_SECRET = 'notify-secret';
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';
  process.env.LIVE_NOTIFICATIONS_ENABLED = 'true';
  process.env.LIVE_NOTIFICATION_MAX_EVENT_AGE_MINUTES = '20';

  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    if (!options.method || options.method === 'GET') {
      return new Response(JSON.stringify([{
        id: 'event-stale',
        slate_date: '2026-05-24',
        event_type: 'game_reminder_due',
        severity: 'action',
        title: 'Pick Starts Soon',
        body: 'Old reminder',
        dedupe_key: 'event-stale-key',
        occurred_at: '2026-05-24T18:00:00Z',
        send_attempts: 0,
      }]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response('', { status: 200 });
  };

  try {
    const response = await sendLiveNotificationsNow(new Request('https://example.test/api/send-live-notifications-now', {
      method: 'POST',
      headers: { 'x-notify-secret': 'notify-secret' },
      body: JSON.stringify({ limit: 1 }),
    }));
    const payload = await response.json();
    const patchCall = calls.find((call) => call.options.method === 'PATCH');

    assert.equal(response.status, 200);
    assert.equal(payload.sent, 0);
    assert.equal(payload.staleSuppressed, 1);
    assert.equal(payload.message, 'No fresh live notifications');
    assert.ok(patchCall);
    assert.match(patchCall.url, /\/rest\/v1\/notification_events\?id=eq\.event-stale/);
    assert.deepEqual(JSON.parse(patchCall.options.body), {
      send_attempts: 3,
      last_send_error: 'suppressed_stale_live_notification:max_age_minutes=20',
    });
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});

test('enabled sender suppresses queue rows after listed game time', async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalEnv = {
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
    LIVE_NOTIFICATIONS_ENABLED: process.env.LIVE_NOTIFICATIONS_ENABLED,
    LIVE_NOTIFICATION_MAX_EVENT_AGE_MINUTES: process.env.LIVE_NOTIFICATION_MAX_EVENT_AGE_MINUTES,
  };
  const gameTime = new Date(Date.now() - 60 * 1000).toISOString();
  process.env.NOTIFY_SECRET = 'notify-secret';
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';
  process.env.LIVE_NOTIFICATIONS_ENABLED = 'true';
  process.env.LIVE_NOTIFICATION_MAX_EVENT_AGE_MINUTES = '20';

  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    if (!options.method || options.method === 'GET') {
      return new Response(JSON.stringify([{
        id: 'event-post-start',
        slate_date: '2026-05-24',
        event_type: 'line_moved_against_us',
        severity: 'action',
        title: 'Line Worse Now',
        body: 'Old movement',
        dedupe_key: 'event-post-start-key',
        occurred_at: new Date().toISOString(),
        send_attempts: 0,
        payload: {
          pitcher: 'Tarik Skubal',
          side: 'over',
          game_time: gameTime,
        },
      }]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response('', { status: 200 });
  };

  try {
    assert.equal(isNotificationEventPostStart({
      payload: { game_time: gameTime },
    }), true);

    const response = await sendLiveNotificationsNow(new Request('https://example.test/api/send-live-notifications-now', {
      method: 'POST',
      headers: { 'x-notify-secret': 'notify-secret' },
      body: JSON.stringify({ limit: 1 }),
    }));
    const payload = await response.json();
    const patchCall = calls.find((call) => call.options.method === 'PATCH');
    const patchBody = JSON.parse(patchCall.options.body);

    assert.equal(response.status, 200);
    assert.equal(payload.sent, 0);
    assert.equal(payload.staleSuppressed, 0);
    assert.equal(payload.postStartSuppressed, 1);
    assert.equal(payload.message, 'No fresh live notifications');
    assert.ok(patchCall);
    assert.match(patchCall.url, /\/rest\/v1\/notification_events\?id=eq\.event-post-start/);
    assert.equal(patchBody.send_attempts, 3);
    assert.match(patchBody.last_send_error, /^suppressed_post_start_live_notification:game_time=/);
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});
