import { timingSafeEqual } from 'node:crypto';

const JSON_HEADERS = { 'Content-Type': 'application/json' };
const DEFAULT_SUPABASE_URL = 'https://htoaytcsjrdyyzcwxjfg.supabase.co';
const VALID_SOURCES = new Set(['dashboard_manual', 'notification', 'shadow_candidate', 'other']);
const ACCEPTED_BET_SELECT = [
  'id',
  'slate_date',
  'pitcher',
  'normalized_pitcher',
  'side',
  'verdict',
  'k_line',
  'odds',
  'book',
  'units',
  'source',
  'notification_event_id',
  'shadow_candidate_id',
  'model_snapshot',
  'metadata',
  'accepted_at',
].join(',');

export function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

export function envValue(name) {
  return globalThis.Netlify?.env?.get?.(name) || process.env[name] || '';
}

function safeSecretEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

export function normalizePitcherKey(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

function requireText(payload, key) {
  const value = String(payload[key] || '').trim();
  if (!value) throw new Error(`missing_${key}`);
  return value;
}

function requireNumber(payload, key) {
  const value = Number(String(payload[key] ?? '').trim().replace(/\u2212/g, '-'));
  if (!Number.isFinite(value)) throw new Error(`invalid_${key}`);
  return value;
}

function optionalObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function validDateOnly(value) {
  const text = String(value || '').trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) throw new Error('missing_slate_date');
  return text;
}

export function buildAcceptedBetRow(payload) {
  const slateDate = validDateOnly(payload.slate_date);
  const pitcher = requireText(payload, 'pitcher');
  const normalizedPitcher = normalizePitcherKey(payload.normalized_pitcher || pitcher);
  if (!normalizedPitcher) throw new Error('missing_normalized_pitcher');

  const side = requireText(payload, 'side').toLowerCase();
  if (side !== 'over' && side !== 'under') throw new Error('invalid_side');

  const book = requireText(payload, 'book');
  const kLine = requireNumber(payload, 'k_line');
  const odds = Math.trunc(requireNumber(payload, 'odds'));
  const units = requireNumber(payload, 'units');
  if (units <= 0) throw new Error('invalid_units');

  const source = String(payload.source || 'dashboard_manual').trim();
  if (!VALID_SOURCES.has(source)) throw new Error('invalid_source');

  const dedupeKey = [
    'accepted_bet',
    slateDate,
    normalizedPitcher,
    side,
    book.toLowerCase(),
    String(kLine),
    String(odds),
  ].join(':');

  return {
    slate_date: slateDate,
    pitcher,
    normalized_pitcher: normalizedPitcher,
    side,
    verdict: payload.verdict ? String(payload.verdict).trim() : null,
    k_line: kLine,
    odds,
    book,
    units,
    game_time: payload.game_time || null,
    source,
    notification_event_id: payload.notification_event_id || null,
    shadow_candidate_id: payload.shadow_candidate_id || null,
    model_snapshot: optionalObject(payload.model_snapshot),
    metadata: optionalObject(payload.metadata),
    dedupe_key: dedupeKey,
    accepted_at: new Date().toISOString(),
  };
}

async function writeAcceptedBet({ supabaseUrl, serviceRoleKey, row }) {
  const response = await fetch(
    `${supabaseUrl.replace(/\/$/, '')}/rest/v1/accepted_bets?on_conflict=dedupe_key`,
    {
      method: 'POST',
      headers: {
        apikey: serviceRoleKey,
        Authorization: `Bearer ${serviceRoleKey}`,
        'Content-Type': 'application/json',
        Prefer: 'resolution=merge-duplicates,return=representation',
      },
      body: JSON.stringify(row),
    },
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`supabase_write_failed:${response.status}:${text.slice(0, 500)}`);
  }

  const rows = await response.json();
  return Array.isArray(rows) ? rows[0] : rows;
}

function requireAcceptedBetAccess(req) {
  const acceptedSecret = envValue('BET_LOG_SECRET') || envValue('NOTIFY_SECRET');
  const suppliedSecret = req.headers.get('x-bet-log-secret') || '';
  const supabaseUrl = envValue('SUPABASE_URL') || DEFAULT_SUPABASE_URL;
  const serviceRoleKey = envValue('SUPABASE_SERVICE_ROLE_KEY');
  if (!acceptedSecret || !serviceRoleKey) {
    return { response: json(500, { error: 'Accepted bet log not configured' }) };
  }
  if (!safeSecretEqual(suppliedSecret, acceptedSecret)) {
    return { response: json(401, { error: 'Unauthorized' }) };
  }
  return { supabaseUrl, serviceRoleKey };
}

function sanitizeAcceptedBet(row) {
  return {
    id: row.id || null,
    slate_date: row.slate_date || null,
    pitcher: row.pitcher || '',
    normalized_pitcher: row.normalized_pitcher || normalizePitcherKey(row.pitcher),
    side: row.side || '',
    verdict: row.verdict || null,
    k_line: row.k_line ?? null,
    odds: row.odds ?? null,
    book: row.book || '',
    units: row.units ?? null,
    source: row.source || null,
    notification_event_id: row.notification_event_id || null,
    shadow_candidate_id: row.shadow_candidate_id || null,
    model_snapshot: optionalObject(row.model_snapshot),
    metadata: optionalObject(row.metadata),
    accepted_at: row.accepted_at || null,
  };
}

async function readAcceptedBets({ supabaseUrl, serviceRoleKey, slateDate }) {
  const url = new URL(`${supabaseUrl.replace(/\/$/, '')}/rest/v1/accepted_bets`);
  url.searchParams.set('select', ACCEPTED_BET_SELECT);
  url.searchParams.set('slate_date', `eq.${slateDate}`);
  url.searchParams.set('order', 'accepted_at.desc');
  url.searchParams.set('limit', '100');

  const response = await fetch(url, {
    headers: {
      apikey: serviceRoleKey,
      Authorization: `Bearer ${serviceRoleKey}`,
    },
  });

  if (!response.ok) {
    throw new Error(`supabase_read_failed:${response.status}`);
  }

  const rows = await response.json();
  return Array.isArray(rows) ? rows.map(sanitizeAcceptedBet) : [];
}

export async function handleAcceptedBetRequest(req) {
  if (req.method !== 'POST' && req.method !== 'GET') return json(405, { error: 'Method not allowed' });

  const access = requireAcceptedBetAccess(req);
  if (access.response) return access.response;
  const { supabaseUrl, serviceRoleKey } = access;

  if (req.method === 'GET') {
    let slateDate;
    try {
      const url = new URL(req.url);
      slateDate = validDateOnly(url.searchParams.get('slate_date') || url.searchParams.get('date'));
    } catch (error) {
      return json(400, { error: error.message || 'missing_slate_date' });
    }

    try {
      const acceptedBets = await readAcceptedBets({ supabaseUrl, serviceRoleKey, slateDate });
      return json(200, { ok: true, slate_date: slateDate, accepted_bets: acceptedBets });
    } catch (error) {
      console.error('accepted-bets: failed to read rows', error.message);
      return json(500, { error: 'Failed to read accepted bets' });
    }
  }

  let payload;
  try {
    payload = await req.json();
  } catch {
    return json(400, { error: 'Invalid JSON body' });
  }

  let row;
  try {
    row = buildAcceptedBetRow(payload);
  } catch (error) {
    return json(400, { error: error.message || 'Invalid accepted bet payload' });
  }

  try {
    const acceptedBet = await writeAcceptedBet({ supabaseUrl, serviceRoleKey, row });
    return json(200, { ok: true, accepted_bet: acceptedBet });
  } catch (error) {
    console.error('accepted-bets: failed to write row', error.message);
    return json(500, { error: 'Failed to store accepted bet' });
  }
}
