const SOURCE = 'live_market_display_state';
const SUPPORTED_PROVIDERS = new Set(['boltodds', 'propline']);
const SUPPORTED_BOOKS = new Set([
  'fanduel',
  'draftkings',
  'betmgm',
  'betrivers',
  'kalshi',
  'caesars',
  'thescore',
]);
const SELECT_FIELDS = [
  'slate_date',
  'pitcher',
  'normalized_pitcher',
  'side',
  'provider',
  'observed_at',
  'freshness_status',
  'market_status',
  'actionable_state',
  'market_consensus',
  'bet_value_consensus',
  'main_line',
  'best_book',
  'best_line',
  'best_odds',
  'book_count',
  'books_seen',
  'broad_confirmation',
  'book_rows',
  'movement_events',
  'source_artifact_path',
  'source_artifact_sha256',
].join(',');

const JSON_HEADERS = {
  'content-type': 'application/json; charset=utf-8',
  'cache-control': 'no-store',
  'access-control-allow-origin': '*',
  'access-control-allow-methods': 'GET,OPTIONS',
  'access-control-allow-headers': 'content-type',
};

function envValue(name) {
  return globalThis.Netlify?.env?.get?.(name) || process.env[name] || '';
}

function jsonResponse(statusCode, body, headers = {}) {
  return {
    statusCode,
    headers: {
      ...JSON_HEADERS,
      ...headers,
    },
    body: JSON.stringify(body),
  };
}

function emptyPayload(slateDate, error) {
  return {
    generated_at: null,
    slate_date: slateDate || null,
    source: SOURCE,
    rows: [],
    error,
  };
}

function validDate(value) {
  const text = String(value || '').trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : '';
}

function normalizeBook(value) {
  const compact = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9]+/g, '');
  const aliases = {
    fanaticsfanduel: 'fanduel',
    fanduelsportsbook: 'fanduel',
    draftkingssportsbook: 'draftkings',
    betmgmsportsbook: 'betmgm',
    betriverssportsbook: 'betrivers',
    caesarssportsbook: 'caesars',
    thescorebet: 'thescore',
    thescoresportsbook: 'thescore',
    scorebet: 'thescore',
  };
  return aliases[compact] || compact;
}

function supportedBook(value) {
  const book = normalizeBook(value);
  return SUPPORTED_BOOKS.has(book) ? book : '';
}

function textOrNull(value) {
  const text = String(value || '').trim();
  return text || null;
}

function numberOrNull(value) {
  if (value == null || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function integerOrNull(value) {
  const n = numberOrNull(value);
  return n == null ? null : Math.trunc(n);
}

function compactObject(row) {
  return Object.fromEntries(Object.entries(row).filter(([, value]) => value !== undefined));
}

function sanitizeBooksSeen(value) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.map(supportedBook).filter(Boolean))].sort();
}

function sanitizeBookRow(row) {
  if (!row || typeof row !== 'object') return null;
  const book = supportedBook(row.book || row.bookmaker_key || row.bookmaker_title);
  if (!book) return null;
  return compactObject({
    book,
    line: numberOrNull(row.line),
    odds: integerOrNull(row.odds ?? row.american_odds ?? row.price),
    first_line: numberOrNull(row.first_line),
    first_odds: integerOrNull(row.first_odds),
    line_delta: numberOrNull(row.line_delta),
    odds_delta: integerOrNull(row.odds_delta),
    market_direction: textOrNull(row.market_direction),
    bet_value_direction: textOrNull(row.bet_value_direction),
    last_seen_at: textOrNull(row.last_seen_at || row.observed_at),
  });
}

function sanitizeMovementEvent(row) {
  if (!row || typeof row !== 'object') return null;
  const book = supportedBook(row.book || row.bookmaker_key || row.bookmaker_title);
  return compactObject({
    observed_at: textOrNull(row.observed_at),
    book: book || undefined,
    event_kind: textOrNull(row.event_kind),
    from_line: numberOrNull(row.from_line),
    to_line: numberOrNull(row.to_line),
    from_odds: integerOrNull(row.from_odds),
    to_odds: integerOrNull(row.to_odds),
    bet_value_direction: textOrNull(row.bet_value_direction),
  });
}

function sanitizeRow(row, slateDate) {
  if (!row || typeof row !== 'object') return null;
  const rowDate = validDate(row.slate_date);
  if (rowDate !== slateDate) return null;
  const provider = String(row.provider || '').trim().toLowerCase();
  if (!SUPPORTED_PROVIDERS.has(provider)) return null;
  const side = String(row.side || '').trim().toLowerCase();
  if (side !== 'over' && side !== 'under') return null;
  const normalizedPitcher = textOrNull(row.normalized_pitcher);
  if (!normalizedPitcher) return null;
  const bookRows = Array.isArray(row.book_rows)
    ? row.book_rows.map(sanitizeBookRow).filter(Boolean)
    : [];
  const booksSeen = sanitizeBooksSeen(row.books_seen);
  const movementEvents = Array.isArray(row.movement_events)
    ? row.movement_events.map(sanitizeMovementEvent).filter(Boolean).slice(0, 12)
    : [];
  const supportedBookCount = Math.max(bookRows.length, booksSeen.length);

  return {
    slate_date: rowDate,
    pitcher: textOrNull(row.pitcher) || normalizedPitcher,
    normalized_pitcher: normalizedPitcher,
    side,
    provider,
    observed_at: textOrNull(row.observed_at),
    freshness_status: textOrNull(row.freshness_status),
    market_status: textOrNull(row.market_status),
    actionable_state: textOrNull(row.actionable_state),
    market_consensus: textOrNull(row.market_consensus),
    bet_value_consensus: textOrNull(row.bet_value_consensus),
    main_line: numberOrNull(row.main_line),
    best_book: supportedBook(row.best_book) || null,
    best_line: numberOrNull(row.best_line),
    best_odds: integerOrNull(row.best_odds),
    book_count: supportedBookCount || integerOrNull(row.book_count),
    books_seen: booksSeen,
    broad_confirmation: row.broad_confirmation === true,
    book_rows: bookRows,
    movement_events: movementEvents,
    source_artifact_path: textOrNull(row.source_artifact_path),
    source_artifact_sha256: textOrNull(row.source_artifact_sha256),
  };
}

function latestObservedAt(rows) {
  const values = rows
    .map(row => row.observed_at)
    .filter(Boolean)
    .sort();
  return values.length ? values[values.length - 1] : null;
}

async function readRowsFromSupabase({ slateDate, supabaseUrl, serviceRoleKey }) {
  const url = new URL(`${supabaseUrl.replace(/\/$/, '')}/rest/v1/live_market_display_state`);
  url.searchParams.set('select', SELECT_FIELDS);
  url.searchParams.set('slate_date', `eq.${slateDate}`);
  url.searchParams.set('order', 'observed_at.desc');
  url.searchParams.set('limit', '250');

  const response = await fetch(url, {
    headers: {
      apikey: serviceRoleKey,
      authorization: `Bearer ${serviceRoleKey}`,
    },
  });

  if (!response.ok) {
    throw new Error(`supabase_read_failed:${response.status}`);
  }

  const rows = await response.json();
  return Array.isArray(rows) ? rows : [];
}

export async function handler(event) {
  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 204,
      headers: JSON_HEADERS,
      body: '',
    };
  }
  if (event.httpMethod && event.httpMethod !== 'GET') {
    return jsonResponse(405, { error: 'method_not_allowed' });
  }

  const params = event.queryStringParameters || {};
  const slateDate = validDate(params.date || params.slate_date);
  if (!slateDate) {
    return jsonResponse(200, emptyPayload(null, 'invalid_date'));
  }

  const supabaseUrl = envValue('SUPABASE_URL');
  const serviceRoleKey = envValue('SUPABASE_SERVICE_ROLE_KEY');
  if (!supabaseUrl || !serviceRoleKey) {
    return jsonResponse(200, emptyPayload(slateDate, 'missing_supabase_config'));
  }

  try {
    const rawRows = await readRowsFromSupabase({ slateDate, supabaseUrl, serviceRoleKey });
    const rows = rawRows.map(row => sanitizeRow(row, slateDate)).filter(Boolean);
    return jsonResponse(200, {
      generated_at: latestObservedAt(rows),
      slate_date: slateDate,
      source: SOURCE,
      rows,
    });
  } catch (error) {
    return jsonResponse(200, emptyPayload(slateDate, error.message || 'supabase_read_failed'));
  }
}
