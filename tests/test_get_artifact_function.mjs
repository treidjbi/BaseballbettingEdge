import assert from 'node:assert/strict';
import test from 'node:test';

import { handler } from '../netlify/functions/get-artifact.mjs';

test('get-artifact rejects unknown artifact types', async () => {
  const response = await handler({ queryStringParameters: { type: 'raw_snapshots' } });

  assert.equal(response.statusCode, 400);
});

test('get-artifact returns latest artifact payload', async () => {
  const oldFetch = global.fetch;
  global.fetch = async (url) => {
    assert.match(String(url), /published_pipeline_artifacts/);
    return {
      ok: true,
      json: async () => [{
        artifact_key: 'today',
        payload_sha256: 'sha',
        published_at: '2026-05-22T15:41:07Z',
        payload: { date: '2026-05-22', pitchers: [] },
      }],
    };
  };
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-role';

  try {
    const response = await handler({ queryStringParameters: { type: 'today' } });
    assert.equal(response.statusCode, 200);
    assert.equal(JSON.parse(response.body).date, '2026-05-22');
    assert.equal(response.headers.ETag, '"sha"');
  } finally {
    global.fetch = oldFetch;
    delete process.env.SUPABASE_URL;
    delete process.env.SUPABASE_SERVICE_ROLE_KEY;
  }
});

test('get-artifact supports fangraphs cache artifact', async () => {
  const oldFetch = global.fetch;
  global.fetch = async (url) => {
    assert.match(String(url), /artifact_key=eq\.fangraphs_cache/);
    return {
      ok: true,
      json: async () => [{
        artifact_key: 'fangraphs_cache',
        payload_sha256: 'sha-cache',
        published_at: '2026-06-04T23:07:53Z',
        payload: { version: 1, entries: {} },
      }],
    };
  };
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-role';

  try {
    const response = await handler({ queryStringParameters: { type: 'fangraphs_cache' } });
    assert.equal(response.statusCode, 200);
    assert.equal(JSON.parse(response.body).version, 1);
  } finally {
    global.fetch = oldFetch;
    delete process.env.SUPABASE_URL;
    delete process.env.SUPABASE_SERVICE_ROLE_KEY;
  }
});

test('get-artifact filters picks_history to the inclusive requested date window', async () => {
  const oldFetch = global.fetch;
  global.fetch = async () => ({
    ok: true,
    json: async () => [{
      artifact_key: 'picks_history',
      payload_sha256: 'sha-history',
      published_at: '2026-08-21T20:08:03Z',
      payload: [
        { date: '2026-06-02', pitcher: 'Before Window' },
        { date: '2026-06-03', pitcher: 'Robert Gasser' },
        { slate_date: '2026-06-04', pitcher: 'Inside Window' },
        { date: '2026-06-05', pitcher: 'After Window' },
      ],
    }],
  });
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-role';

  try {
    const response = await handler({
      queryStringParameters: {
        type: 'picks_history',
        start_date: '2026-06-03',
        end_date: '2026-06-04',
      },
    });

    assert.equal(response.statusCode, 200);
    assert.deepEqual(JSON.parse(response.body), [
      { date: '2026-06-03', pitcher: 'Robert Gasser' },
      { slate_date: '2026-06-04', pitcher: 'Inside Window' },
    ]);
    assert.equal(response.headers.ETag, '"sha-history"');
  } finally {
    global.fetch = oldFetch;
    delete process.env.SUPABASE_URL;
    delete process.env.SUPABASE_SERVICE_ROLE_KEY;
  }
});

test('get-artifact rejects invalid picks_history date windows before reading Supabase', async () => {
  const oldFetch = global.fetch;
  let fetchCalled = false;
  global.fetch = async () => {
    fetchCalled = true;
    throw new Error('fetch must not run');
  };
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-role';

  try {
    const malformed = await handler({
      queryStringParameters: {
        type: 'picks_history',
        start_date: '06-03-2026',
      },
    });
    const reversed = await handler({
      queryStringParameters: {
        type: 'picks_history',
        start_date: '2026-06-04',
        end_date: '2026-06-03',
      },
    });
    const wrongType = await handler({
      queryStringParameters: {
        type: 'today',
        start_date: '2026-06-03',
      },
    });

    assert.equal(malformed.statusCode, 400);
    assert.equal(reversed.statusCode, 400);
    assert.equal(wrongType.statusCode, 400);
    assert.equal(fetchCalled, false);
  } finally {
    global.fetch = oldFetch;
    delete process.env.SUPABASE_URL;
    delete process.env.SUPABASE_SERVICE_ROLE_KEY;
  }
});
