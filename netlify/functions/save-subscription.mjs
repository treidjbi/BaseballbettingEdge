/**
 * save-subscription — Netlify Functions v2
 * Manages push subscription storage in Netlify Blobs.
 *
 * GET    → returns the VAPID public key (needed by the browser before subscribing)
 * POST   → saves a push subscription object
 * DELETE → removes a push subscription (user unsubscribed)
 *
 * Required Netlify env var:
 *   VAPID_PUBLIC_KEY — generated with: npx web-push generate-vapid-keys
 */
import { getStore } from '@netlify/blobs';

const jsonHeaders = { 'Content-Type': 'application/json' };
const subKey = (endpoint) => Buffer.from(endpoint).toString('base64url').slice(0, 64);
const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: jsonHeaders });

export default async (req) => {
  const { VAPID_PUBLIC_KEY } = process.env;
  if (!VAPID_PUBLIC_KEY) return json(500, { error: 'VAPID not configured' });

  // GET — return public VAPID key so the browser can call pushManager.subscribe()
  if (req.method === 'GET') {
    return json(200, { vapidPublicKey: VAPID_PUBLIC_KEY });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return json(400, { error: 'Invalid JSON' });
  }

  if (!body?.endpoint) return json(400, { error: 'Missing endpoint' });

  const store = getStore({ name: 'push-subscriptions', consistency: 'strong' });

  if (req.method === 'POST') {
    await store.setJSON(subKey(body.endpoint), body);
    return json(201, { ok: true });
  }

  if (req.method === 'DELETE') {
    await store.delete(subKey(body.endpoint));
    return json(200, { ok: true });
  }

  return json(405, { error: 'Method not allowed' });
};
