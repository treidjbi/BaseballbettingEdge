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
