import test from 'node:test';
import assert from 'node:assert/strict';
import handler from '../netlify/functions/propline-webhook.mjs';

test('retired receiver acknowledges without reading payloads or accessing storage', async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = () => { throw new Error('unexpected storage access'); };
  try {
    const response = await handler({
      method: 'POST',
      text() { throw new Error('unexpected payload access'); },
      json() { throw new Error('unexpected payload access'); },
      get headers() { throw new Error('unexpected header access'); },
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      ok: true, ignored: true, reason: 'webhooks_retired',
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('retired receiver rejects other methods', async () => {
  assert.equal((await handler({ method: 'GET' })).status, 405);
});
