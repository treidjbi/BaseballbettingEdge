/**
 * save-subscription.js
 * Manages push subscription storage in Netlify Blobs.
 *
 * GET    → returns the VAPID public key (needed by the browser before subscribing)
 * POST   → saves a push subscription object
 * DELETE → removes a push subscription (user unsubscribed)
 *
 * Required Netlify env var:
 *   VAPID_PUBLIC_KEY — generated with: npx web-push generate-vapid-keys
 */
const { getStore } = require('@netlify/blobs');

const HEADERS = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

function subKey(endpoint) {
  return Buffer.from(endpoint).toString('base64url').slice(0, 64);
}

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: HEADERS, body: '' };
  }

  const { VAPID_PUBLIC_KEY } = process.env;
  if (!VAPID_PUBLIC_KEY) {
    return { statusCode: 500, headers: HEADERS, body: JSON.stringify({ error: 'VAPID not configured' }) };
  }

  // GET — return public VAPID key so the browser can call pushManager.subscribe()
  if (event.httpMethod === 'GET') {
    return {
      statusCode: 200,
      headers: HEADERS,
      body: JSON.stringify({ vapidPublicKey: VAPID_PUBLIC_KEY }),
    };
  }

  let body;
  try {
    body = JSON.parse(event.body || '{}');
  } catch {
    return { statusCode: 400, headers: HEADERS, body: JSON.stringify({ error: 'Invalid JSON' }) };
  }

  // POST — save subscription
  if (event.httpMethod === 'POST') {
    if (!body?.endpoint) {
      return { statusCode: 400, headers: HEADERS, body: JSON.stringify({ error: 'Missing endpoint' }) };
    }
    const store = getStore({ name: 'push-subscriptions', consistency: 'strong' });
    await store.setJSON(subKey(body.endpoint), body);
    return { statusCode: 201, headers: HEADERS, body: JSON.stringify({ ok: true }) };
  }

  // DELETE — remove subscription
  if (event.httpMethod === 'DELETE') {
    if (!body?.endpoint) {
      return { statusCode: 400, headers: HEADERS, body: JSON.stringify({ error: 'Missing endpoint' }) };
    }
    const store = getStore({ name: 'push-subscriptions', consistency: 'strong' });
    await store.delete(subKey(body.endpoint));
    return { statusCode: 200, headers: HEADERS, body: JSON.stringify({ ok: true }) };
  }

  return { statusCode: 405, headers: HEADERS, body: JSON.stringify({ error: 'Method not allowed' }) };
};
