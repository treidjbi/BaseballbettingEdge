// Retired September 12, 2026. Acknowledge residual deliveries without reading
// payloads, credentials, or writing the historical inbox. A 2xx avoids retries.
export default async function proplineWebhook(req) {
  return new Response(JSON.stringify(
    req.method === 'POST'
      ? { ok: true, ignored: true, reason: 'webhooks_retired' }
      : { error: 'Method not allowed' },
  ), {
    status: req.method === 'POST' ? 200 : 405,
    headers: { 'Content-Type': 'application/json' },
  });
}

export const config = { path: '/api/propline-webhook' };
