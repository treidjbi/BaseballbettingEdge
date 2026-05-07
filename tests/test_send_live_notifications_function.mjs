import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildPushPayload,
  buildSenderLog,
  envValue,
  fetchPendingNotificationEvents,
  isLiveNotificationsEnabled,
} from '../netlify/functions/_shared/live-notification-sender.mjs';
import sendLiveNotificationsNow, {
  config as httpConfig,
} from '../netlify/functions/send-live-notifications-now.mjs';
import sendLiveNotificationsScheduled, {
  config as scheduledConfig,
} from '../netlify/functions/send-live-notifications.mjs';

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
    'send-live-notifications stage=dry_run enabled=false pending=16 subscribers=0 sent=0 failed=0 staleRemoved=0',
  );
  assert.equal(line.includes('SUPABASE_SERVICE_ROLE_KEY'), false);
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
