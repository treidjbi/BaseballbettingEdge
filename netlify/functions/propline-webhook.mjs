import crypto from 'node:crypto';

const jsonHeaders = { 'Content-Type': 'application/json' };
const DEFAULT_SUPABASE_URL = 'https://htoaytcsjrdyyzcwxjfg.supabase.co';

// Shadow-only PropLine webhook inbox. Keep production odds behavior unchanged.
function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: jsonHeaders });
}

function envValue(name) {
  return globalThis.Netlify?.env?.get?.(name) || process.env[name] || '';
}

export function hmacSha256Hex(secret, timestamp, body) {
  return crypto
    .createHmac('sha256', secret)
    .update(`${timestamp}.${body}`)
    .digest('hex');
}

export function timingSafeEqualHex(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  return crypto.timingSafeEqual(Buffer.from(a, 'hex'), Buffer.from(b, 'hex'));
}

function parsePayload(body) {
  try {
    return JSON.parse(body);
  } catch {
    return { raw_body_parse_error: true };
  }
}

export function buildDeliveryRow({
  deliveryId,
  propLineEvent,
  timestamp,
  signatureValid,
  payload,
}) {
  const timestampSeconds = Number(timestamp);
  if (!Number.isFinite(timestampSeconds) || timestampSeconds <= 0) {
    throw new Error('invalid_timestamp');
  }

  return {
    prop_line_delivery_id: deliveryId,
    prop_line_event: propLineEvent,
    prop_line_timestamp: new Date(timestampSeconds * 1000).toISOString(),
    signature_valid: signatureValid,
    payload,
    processed: false,
    processing_error: signatureValid ? null : 'invalid_signature',
  };
}

async function storeDelivery({ supabaseUrl, serviceRoleKey, row }) {
  const response = await fetch(
    `${supabaseUrl.replace(/\/$/, '')}/rest/v1/propline_webhook_deliveries?on_conflict=prop_line_delivery_id`,
    {
      method: 'POST',
      headers: {
        apikey: serviceRoleKey,
        Authorization: `Bearer ${serviceRoleKey}`,
        'Content-Type': 'application/json',
        Prefer: 'resolution=merge-duplicates,return=minimal',
      },
      body: JSON.stringify(row),
    },
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`supabase_write_failed:${response.status}:${text.slice(0, 500)}`);
  }
}

export default async function proplineWebhook(req) {
  if (req.method !== 'POST') {
    return json(405, { error: 'Method not allowed' });
  }

  const secret = envValue('PROPLINE_WEBHOOK_SECRET');
  const supabaseUrl = envValue('SUPABASE_URL') || DEFAULT_SUPABASE_URL;
  const serviceRoleKey = envValue('SUPABASE_SERVICE_ROLE_KEY');
  if (!secret || !supabaseUrl || !serviceRoleKey) {
    return json(500, { error: 'Webhook receiver not configured' });
  }

  const propLineEvent = req.headers.get('X-PropLine-Event') || '';
  const timestamp = req.headers.get('X-PropLine-Timestamp') || '';
  const signature = req.headers.get('X-PropLine-Signature') || '';
  const deliveryId = req.headers.get('X-PropLine-Delivery') || '';
  const body = await req.text();

  if (!propLineEvent || !timestamp || !signature || !deliveryId) {
    return json(400, { error: 'Missing PropLine headers' });
  }

  let signatureValid = false;
  try {
    signatureValid = timingSafeEqualHex(
      hmacSha256Hex(secret, timestamp, body),
      signature,
    );
  } catch {
    signatureValid = false;
  }

  let row;
  try {
    row = buildDeliveryRow({
      deliveryId,
      propLineEvent,
      timestamp,
      signatureValid,
      payload: parsePayload(body),
    });
  } catch {
    return json(400, { error: 'Invalid PropLine timestamp' });
  }

  try {
    await storeDelivery({ supabaseUrl, serviceRoleKey, row });
  } catch (error) {
    console.error('propline-webhook: failed to store delivery', error.message);
    return json(500, { error: 'Failed to store delivery' });
  }

  if (!signatureValid) {
    return json(401, { error: 'Invalid signature' });
  }

  return json(200, { ok: true, deliveryId });
}

export const config = {
  path: '/api/propline-webhook',
};
