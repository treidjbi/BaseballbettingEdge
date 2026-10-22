const ALLOWED_TYPES = new Set([
  'today',
  'dated_slate',
  'index',
  'steam',
  'performance',
  'params',
  'preview_lines',
  'picks_history',
  'fangraphs_cache',
]);

function jsonResponse(statusCode, body, headers = {}) {
  return {
    statusCode,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      ...headers,
    },
    body: JSON.stringify(body),
  };
}

function artifactKey(type, date) {
  if (type === 'dated_slate') {
    if (!date) throw new Error('date is required for dated_slate');
    return `dated_slate:${date}`;
  }
  return type;
}

function isIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime())
    && parsed.toISOString().slice(0, 10) === value;
}

function historyRowDate(row) {
  if (!row || typeof row !== 'object' || Array.isArray(row)) return '';
  return String(row.date || row.slate_date || '');
}

export async function handler(event) {
  const params = event.queryStringParameters || {};
  const type = params.type || 'today';
  const date = params.date || '';
  const startDate = params.start_date || '';
  const endDate = params.end_date || '';

  if (!ALLOWED_TYPES.has(type)) {
    return jsonResponse(400, { error: 'unsupported artifact type' });
  }
  if ((startDate || endDate) && type !== 'picks_history') {
    return jsonResponse(400, { error: 'date windows are supported only for picks_history' });
  }
  if ((startDate && !isIsoDate(startDate)) || (endDate && !isIsoDate(endDate))) {
    return jsonResponse(400, { error: 'start_date and end_date must use YYYY-MM-DD' });
  }
  if (startDate && endDate && startDate > endDate) {
    return jsonResponse(400, { error: 'start_date must be on or before end_date' });
  }

  let key;
  try {
    key = artifactKey(type, date);
  } catch (error) {
    return jsonResponse(400, { error: error.message });
  }

  const supabaseUrl = process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !serviceRoleKey) {
    return jsonResponse(500, { error: 'artifact api is not configured' });
  }

  const url = new URL(`${supabaseUrl}/rest/v1/published_pipeline_artifacts`);
  url.searchParams.set('artifact_key', `eq.${key}`);
  url.searchParams.set('select', 'artifact_key,payload,payload_sha256,published_at');
  url.searchParams.set('limit', '1');

  const response = await fetch(url, {
    headers: {
      apikey: serviceRoleKey,
      authorization: `Bearer ${serviceRoleKey}`,
    },
  });

  if (!response.ok) {
    return jsonResponse(502, { error: 'failed to read artifact' });
  }

  const rows = await response.json();
  if (!rows.length) {
    return jsonResponse(404, { error: 'artifact not found' });
  }

  const row = rows[0];
  let payload = row.payload;
  if (type === 'picks_history' && (startDate || endDate)) {
    payload = payload.filter((item) => {
      const itemDate = historyRowDate(item);
      if (!isIsoDate(itemDate)) return false;
      return (!startDate || itemDate >= startDate) && (!endDate || itemDate <= endDate);
    });
  }
  return jsonResponse(200, payload, {
    'cache-control': 'public, max-age=30, stale-while-revalidate=120',
    ETag: `"${row.payload_sha256}"`,
    'x-artifact-key': row.artifact_key,
    'x-artifact-published-at': row.published_at,
  });
}
