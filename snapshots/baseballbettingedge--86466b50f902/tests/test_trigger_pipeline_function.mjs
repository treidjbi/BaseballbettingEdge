import assert from 'node:assert/strict';
import test from 'node:test';

const { handler } = await import('../netlify/functions/trigger-pipeline.js');

function withEnv(values, fn) {
  const previous = {};
  for (const key of Object.keys(values)) {
    previous[key] = process.env[key];
    process.env[key] = values[key];
  }
  return Promise.resolve()
    .then(fn)
    .finally(() => {
      for (const key of Object.keys(values)) {
        if (previous[key] === undefined) {
          delete process.env[key];
        } else {
          process.env[key] = previous[key];
        }
      }
    });
}

test('trigger-pipeline forwards lock mode and date inputs', async () => {
  const calls = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return { status: 204, text: async () => '' };
  };

  try {
    const response = await withEnv({
      GITHUB_PAT: 'secret-token',
      GITHUB_REPO: 'treidjbi/BaseballBettingEdge',
      GITHUB_WORKFLOW: 'pipeline.yml',
    }, () => handler({
      httpMethod: 'POST',
      body: JSON.stringify({ mode: 'lock', date: '2026-05-21' }),
    }));

    assert.equal(response.statusCode, 200);
    assert.deepEqual(JSON.parse(calls[0].options.body), {
      ref: 'main',
      inputs: { mode: 'lock', date: '2026-05-21' },
    });
    assert.equal(calls[0].options.headers.Authorization, 'Bearer secret-token');
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('trigger-pipeline keeps dashboard default dispatch without inputs', async () => {
  const calls = [];
  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return { status: 204, text: async () => '' };
  };

  try {
    const response = await withEnv({
      GITHUB_PAT: 'secret-token',
      GITHUB_REPO: 'treidjbi/BaseballBettingEdge',
      GITHUB_WORKFLOW: 'pipeline.yml',
    }, () => handler({ httpMethod: 'POST', body: '' }));

    assert.equal(response.statusCode, 200);
    assert.deepEqual(JSON.parse(calls[0].options.body), { ref: 'main' });
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test('trigger-pipeline rejects invalid workflow inputs', async () => {
  const response = await withEnv({
    GITHUB_PAT: 'secret-token',
    GITHUB_REPO: 'treidjbi/BaseballBettingEdge',
    GITHUB_WORKFLOW: 'pipeline.yml',
  }, () => handler({
    httpMethod: 'POST',
    body: JSON.stringify({ mode: 'grading', date: '2026-05-21' }),
  }));

  assert.equal(response.statusCode, 400);
});
