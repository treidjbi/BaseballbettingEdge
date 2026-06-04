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

export async function handler(event) {
  const params = event.queryStringParameters || {};
  const type = params.type || 'today';
  const date = params.date || '';

  if (!ALLOWED_TYPES.has(type)) {
    return jsonResponse(400, { error: 'unsupported artifact type' });
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
  return jsonResponse(200, row.payload, {
    'cache-control': 'public, max-age=30, stale-while-revalidate=120',
    ETag: `"${row.payload_sha256}"`,
    'x-artifact-key': row.artifact_key,
    'x-artifact-published-at': row.published_at,
  });
}
