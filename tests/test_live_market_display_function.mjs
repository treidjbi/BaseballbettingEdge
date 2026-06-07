import test from 'node:test';
import assert from 'node:assert/strict';

import { handler } from '../netlify/functions/live-market-display.mjs';

const ORIGINAL_ENV = {
  SUPABASE_URL: process.env.SUPABASE_URL,
  SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
};

function restoreEnv() {
  for (const [key, value] of Object.entries(ORIGINAL_ENV)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}

function getEvent(queryStringParameters = {}) {
  return {
    httpMethod: 'GET',
    queryStringParameters,
  };
}

async function parseJsonResponse(response) {
  return {
    ...response,
    json: JSON.parse(response.body),
  };
}

test('live-market-display fails closed when Supabase config is missing', async () => {
  delete process.env.SUPABASE_URL;
  delete process.env.SUPABASE_SERVICE_ROLE_KEY;

  try {
    const response = await parseJsonResponse(await handler(getEvent({ date: '2026-06-07' })));

    assert.equal(response.statusCode, 200);
    assert.equal(response.json.slate_date, '2026-06-07');
    assert.equal(response.json.source, 'live_market_display_state');
    assert.deepEqual(response.json.rows, []);
    assert.equal(response.json.error, 'missing_supabase_config');
  } finally {
    restoreEnv();
  }
});

test('live-market-display reads Supabase through service-role REST and returns only app-safe fields', async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;
  process.env.SUPABASE_URL = 'https://example.supabase.co/';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-role-secret';

  globalThis.fetch = async (url, options) => {
    calls.push({ url: String(url), options });
    return new Response(JSON.stringify([
      {
        id: 'internal-row-id',
        slate_date: '2026-06-07',
        pitcher: 'Market Pitcher',
        normalized_pitcher: 'market pitcher',
        side: 'under',
        provider: 'boltodds',
        observed_at: '2026-06-07T18:40:00Z',
        freshness_status: 'fresh',
        market_status: 'market_confirmed_playable',
        actionable_state: 'playable_now',
        market_consensus: 'toward_pick',
        bet_value_consensus: 'worse_now',
        main_line: 5.5,
        best_book: 'draftkings',
        best_line: 5.5,
        best_odds: -122,
        book_count: 4,
        books_seen: ['draftkings', 'fanduel', 'unsupported_book'],
        broad_confirmation: true,
        source_artifact_path: 'https://raw.githubusercontent.com/treidjbi/BaseballbettingEdge/main/dashboard/data/processed/today.json',
        source_artifact_sha256: 'artifact-sha',
        book_rows: [
          {
            book: 'draftkings',
            line: 5.5,
            odds: -122,
            first_line: 5.5,
            first_odds: -110,
            line_delta: 0,
            odds_delta: -12,
            market_direction: 'toward_pick',
            bet_value_direction: 'worse_now',
            last_seen_at: '2026-06-07T18:39:30Z',
            raw_payload: { should_not: 'leak' },
          },
          {
            book: 'unsupported_book',
            line: 5.5,
            odds: -101,
            market_direction: 'toward_pick',
            bet_value_direction: 'worse_now',
          },
        ],
        movement_events: [
          {
            observed_at: '2026-06-07T18:38:00Z',
            book: 'draftkings',
            event_kind: 'price_moved',
            from_line: 5.5,
            to_line: 5.5,
            from_odds: -110,
            to_odds: -122,
            bet_value_direction: 'worse_now',
            raw_payload: { should_not: 'leak' },
          },
        ],
        metadata: { should_not: 'leak' },
        service_role_key: 'service-role-secret',
      },
    ]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  try {
    const response = await parseJsonResponse(await handler(getEvent({ date: '2026-06-07' })));
    const row = response.json.rows[0];

    assert.equal(response.statusCode, 200);
    assert.equal(response.json.generated_at, '2026-06-07T18:40:00Z');
    assert.equal(response.json.slate_date, '2026-06-07');
    assert.equal(response.json.source, 'live_market_display_state');
    assert.equal(response.json.rows.length, 1);
    assert.deepEqual(Object.keys(row).sort(), [
      'actionable_state',
      'best_book',
      'best_line',
      'best_odds',
      'bet_value_consensus',
      'book_count',
      'book_rows',
      'books_seen',
      'broad_confirmation',
      'freshness_status',
      'main_line',
      'market_consensus',
      'market_status',
      'movement_events',
      'normalized_pitcher',
      'observed_at',
      'pitcher',
      'provider',
      'side',
      'slate_date',
      'source_artifact_path',
      'source_artifact_sha256',
    ].sort());
    assert.equal(row.book_rows.length, 1);
    assert.deepEqual(Object.keys(row.book_rows[0]).sort(), [
      'bet_value_direction',
      'book',
      'first_line',
      'first_odds',
      'last_seen_at',
      'line',
      'line_delta',
      'market_direction',
      'odds',
      'odds_delta',
    ].sort());
    assert.deepEqual(row.books_seen, ['draftkings', 'fanduel']);
    assert.equal(row.movement_events.length, 1);
    assert.equal(row.movement_events[0].raw_payload, undefined);
    assert.equal(JSON.stringify(response.json).includes('service-role-secret'), false);
    assert.equal(calls.length, 1);
    assert.match(calls[0].url, /^https:\/\/example\.supabase\.co\/rest\/v1\/live_market_display_state\?/);
    assert.match(calls[0].url, /slate_date=eq\.2026-06-07/);
    assert.equal(calls[0].options.headers.apikey, 'service-role-secret');
    assert.equal(calls[0].options.headers.authorization, 'Bearer service-role-secret');
    assert.equal(response.headers['cache-control'], 'no-store');
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv();
  }
});

test('live-market-display fails closed without leaking Supabase error bodies', async () => {
  const originalFetch = globalThis.fetch;
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-role-secret';
  globalThis.fetch = async () => new Response('service-role-secret is invalid', { status: 500 });

  try {
    const response = await parseJsonResponse(await handler(getEvent({ date: '2026-06-07' })));

    assert.equal(response.statusCode, 200);
    assert.deepEqual(response.json.rows, []);
    assert.equal(response.json.error, 'supabase_read_failed:500');
    assert.equal(JSON.stringify(response.json).includes('service-role-secret'), false);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv();
  }
});

test('live-market-display handles OPTIONS preflight', async () => {
  const response = await handler({ httpMethod: 'OPTIONS', queryStringParameters: {} });
  assert.equal(response.statusCode, 204);
  assert.equal(response.body, '');
});
