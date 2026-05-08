import test from 'node:test';
import assert from 'node:assert/strict';

import acceptedBets from '../netlify/functions/accepted-bets.mjs';
import {
  buildAcceptedBetRow,
  normalizePitcherKey,
} from '../netlify/functions/_shared/accepted-bets.mjs';

test('normalizePitcherKey creates stable accent-insensitive keys', () => {
  assert.equal(normalizePitcherKey('Jos\u00e9  Berr\u00edos Jr.'), 'jose berrios jr');
});

test('buildAcceptedBetRow validates and shapes manual dashboard logs', () => {
  const row = buildAcceptedBetRow({
    slate_date: '2026-05-08',
    pitcher: 'Kyle Bradish',
    side: 'UNDER',
    verdict: 'FIRE 1u',
    k_line: '4.5',
    odds: '-125',
    book: 'BetRivers',
    units: '1',
    game_time: '2026-05-08T23:05:00Z',
    model_snapshot: { adj_ev: 0.09 },
  });

  assert.equal(row.slate_date, '2026-05-08');
  assert.equal(row.pitcher, 'Kyle Bradish');
  assert.equal(row.normalized_pitcher, 'kyle bradish');
  assert.equal(row.side, 'under');
  assert.equal(row.k_line, 4.5);
  assert.equal(row.odds, -125);
  assert.equal(row.book, 'BetRivers');
  assert.equal(row.units, 1);
  assert.equal(row.source, 'dashboard_manual');
  assert.deepEqual(row.model_snapshot, { adj_ev: 0.09 });
});

test('buildAcceptedBetRow rejects invalid inputs', () => {
  assert.throws(() => buildAcceptedBetRow({ pitcher: 'Kyle Bradish' }), /missing_slate_date/);
  assert.throws(() => buildAcceptedBetRow({
    slate_date: '2026-05-08',
    pitcher: 'Kyle Bradish',
    side: 'middle',
    k_line: 4.5,
    odds: -125,
    book: 'BetRivers',
    units: 1,
  }), /invalid_side/);
});

test('acceptedBets rejects missing shared secret', async () => {
  const originalEnv = {
    BET_LOG_SECRET: process.env.BET_LOG_SECRET,
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
  };
  delete process.env.BET_LOG_SECRET;
  delete process.env.NOTIFY_SECRET;
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';

  try {
    const response = await acceptedBets(new Request('https://example.test/.netlify/functions/accepted-bets', {
      method: 'POST',
      body: JSON.stringify({}),
    }));
    assert.equal(response.status, 500);
  } finally {
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});

test('acceptedBets writes accepted bet through Supabase REST with secret fallback', async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalEnv = {
    BET_LOG_SECRET: process.env.BET_LOG_SECRET,
    NOTIFY_SECRET: process.env.NOTIFY_SECRET,
    SUPABASE_URL: process.env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
  };
  delete process.env.BET_LOG_SECRET;
  process.env.NOTIFY_SECRET = 'notify-secret';
  delete process.env.SUPABASE_URL;
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-key';

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify([{ id: 'bet-1', pitcher: 'Kyle Bradish' }]), {
      status: 201,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  try {
    const response = await acceptedBets(new Request('https://example.test/.netlify/functions/accepted-bets', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-bet-log-secret': 'notify-secret',
      },
      body: JSON.stringify({
        slate_date: '2026-05-08',
        pitcher: 'Kyle Bradish',
        side: 'UNDER',
        k_line: 4.5,
        odds: -125,
        book: 'BetRivers',
        units: 1,
      }),
    }));
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.ok, true);
    assert.equal(payload.accepted_bet.id, 'bet-1');
    assert.equal(calls.length, 1);
    assert.match(calls[0].url, /^https:\/\/htoaytcsjrdyyzcwxjfg\.supabase\.co\/rest\/v1\/accepted_bets\?on_conflict=/);
    assert.equal(calls[0].options.headers.Authorization, 'Bearer service-key');
    assert.match(calls[0].options.headers.Prefer, /resolution=merge-duplicates/);
  } finally {
    globalThis.fetch = originalFetch;
    for (const [key, value] of Object.entries(originalEnv)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
});
