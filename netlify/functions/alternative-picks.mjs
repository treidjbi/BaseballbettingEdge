const BUNDLE_ID = 'pregame_alternative_pick_methodology_v1';
const CANONICAL_ARTIFACT_KEY = 'today';
const CANONICAL_ARTIFACT_PATH = 'dashboard/data/processed/today.json';
const APPROVED_POSTURES = new Set(['therundown', 'therundown_propline']);
const LANES = new Set(['consensus_core', 'reentry_expansion']);
const SELECTION_STATUSES = new Set(['selected', 'not_selected', 'pending']);
const CHECKPOINTS = new Set(['provisional', 'frozen_pregame']);
const FAMILY_STATES = new Set(['agree', 'disagree', 'pending']);
const LOCK_STATUSES = new Set(['due_now', 'missed_lock']);

const CANONICAL_SELECT = [
  'artifact_key', 'payload_sha256', 'slate_date', 'generated_at', 'source',
  'payload_date:payload->>date',
  'payload_odds_source:payload->>odds_source',
  'payload_provider_posture:payload->>provider_posture',
  'payload_pitchers:payload->pitchers',
  'artifact_path:metadata->>artifact_path',
].join(',');

const STATE_SELECT = [
  'slate_date', 'pitcher', 'normalized_pitcher', 'team', 'opp_team', 'game_time', 'side',
  'model_k_line', 'bundle_id', 'selector_id', 'checkpoint', 'official_odds', 'official_book',
  'official_verdict', 'lane', 'selection_status', 'family_states', 'family_count', 'reason_codes',
  'source_artifact_path', 'source_artifact_generated_at', 'source_artifact_sha256',
  'source_artifact_byte_sha256', 'evidence_observation_count', 'evidence_first_observed_at',
  'evidence_last_observed_at', 'evidence_freshness_status', 'frozen_at', 'lock_dedupe_key',
  'lock_artifact_sha256', 'lock_source_artifact_path', 'locked_at', 'should_lock_at',
  'minutes_until_start', 'lock_status',
].join(',');

const LOCK_SELECT = [
  'dedupe_key', 'slate_date', 'normalized_pitcher', 'side', 'locked_k_line', 'locked_odds',
  'locked_book', 'game_time', 'status_at_capture', 'observed_at', 'locked_at', 'should_lock_at',
  'minutes_until_start', 'source_artifact_path', 'source_artifact_sha256', 'metadata',
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

function jsonResponse(statusCode, body) {
  return { statusCode, headers: JSON_HEADERS, body: JSON.stringify(body) };
}

function emptyPayload(slateDate, error = null, status = 'ready') {
  return {
    slate_date: slateDate,
    generated_at: null,
    status,
    counts: { provisional: 0, frozen: 0, selected: 0, pending: 0 },
    rows: [],
    error,
  };
}

function currentPhoenixDate() {
  const frozen = globalThis.__alternativePicksNow;
  const now = frozen ? new Date(frozen) : new Date();
  if (Number.isNaN(now.getTime())) throw new Error('clock_invalid');
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Phoenix', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now);
  const values = Object.fromEntries(parts.filter(part => part.type !== 'literal').map(part => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function validDate(value) {
  const text = String(value || '').trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return '';
  const parsed = new Date(`${text}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== text ? '' : text;
}

function text(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function validHash(value) {
  const hash = text(value).toLowerCase();
  return /^[a-f0-9]{64}$/.test(hash) ? hash : '';
}

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function integer(value) {
  const parsed = number(value);
  return parsed != null && Number.isInteger(parsed) ? parsed : null;
}

function timestamp(value) {
  const textValue = text(value);
  const parsed = new Date(textValue);
  return textValue && !Number.isNaN(parsed.getTime()) ? parsed.toISOString() : '';
}

function sameTimestamp(left, right) {
  const leftValue = timestamp(left);
  return Boolean(leftValue) && leftValue === timestamp(right);
}

function sameBook(left, right) {
  return text(left).toLowerCase() === text(right).toLowerCase();
}

function boundedStrings(value, maximum = 24) {
  if (!Array.isArray(value)) return [];
  return value
    .filter(item => typeof item === 'string')
    .map(item => item.trim())
    .filter(Boolean)
    .slice(0, maximum)
    .map(item => item.slice(0, 160));
}

function safeFamilyStates(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  const result = {};
  for (const [name, vote] of Object.entries(value)) {
    const key = text(name).slice(0, 80);
    const state = text(vote?.state).toLowerCase();
    if (!key || !FAMILY_STATES.has(state)) continue;
    result[key] = { state, reason_codes: boundedStrings(vote.reason_codes, 12) };
  }
  return result;
}

function responseRow(row, { artifactAdvancedAfterFreeze }) {
  return {
    slate_date: row.slate_date,
    pitcher: text(row.pitcher),
    team: text(row.team),
    opp_team: text(row.opp_team),
    game_time: timestamp(row.game_time),
    side: text(row.side).toLowerCase(),
    model_k_line: number(row.model_k_line),
    official_odds: integer(row.official_odds),
    official_book: text(row.official_book) || null,
    official_verdict: text(row.official_verdict) || null,
    bundle_id: BUNDLE_ID,
    selector_id: text(row.selector_id) || null,
    lane: text(row.lane),
    selection_status: text(row.selection_status),
    family_states: safeFamilyStates(row.family_states),
    family_count: integer(row.family_count) ?? 0,
    checkpoint: text(row.checkpoint),
    reason_codes: boundedStrings(row.reason_codes),
    source_artifact_generated_at: timestamp(row.source_artifact_generated_at) || null,
    evidence_observation_count: integer(row.evidence_observation_count) ?? 0,
    evidence_first_observed_at: timestamp(row.evidence_first_observed_at) || null,
    evidence_last_observed_at: timestamp(row.evidence_last_observed_at) || null,
    evidence_freshness_status: text(row.evidence_freshness_status) || null,
    frozen_at: timestamp(row.frozen_at) || null,
    should_lock_at: timestamp(row.should_lock_at) || null,
    minutes_until_start: number(row.minutes_until_start),
    lock_status: text(row.lock_status) || null,
    artifact_advanced_after_freeze: artifactAdvancedAfterFreeze,
  };
}

function validStateBase(row, slateDate) {
  if (!row || typeof row !== 'object') return false;
  const checkpoint = text(row.checkpoint);
  return validDate(row.slate_date) === slateDate
    && text(row.bundle_id) === BUNDLE_ID
    && CHECKPOINTS.has(checkpoint)
    && text(row.pitcher) && text(row.normalized_pitcher) && text(row.team) && text(row.opp_team)
    && timestamp(row.game_time) && ['over', 'under'].includes(text(row.side).toLowerCase())
    && number(row.model_k_line) != null
    && LANES.has(text(row.lane))
    && SELECTION_STATUSES.has(text(row.selection_status))
    && integer(row.family_count) != null && integer(row.family_count) >= 0
    && integer(row.evidence_observation_count) != null && integer(row.evidence_observation_count) >= 0
    && validHash(row.source_artifact_sha256) && validHash(row.source_artifact_byte_sha256);
}

function validCanonical(row, slateDate) {
  if (!row || typeof row !== 'object') return null;
  const directPosture = text(row.payload_odds_source || row.payload_provider_posture)
    .toLowerCase().replace(/\+/g, '_');
  const pitcherPostures = Array.isArray(row.payload_pitchers) ? row.payload_pitchers.map(pitcher => {
    if (!pitcher || typeof pitcher !== 'object') return '';
    return text(pitcher.market_source_mode || pitcher.odds_source).toLowerCase().replace(/\+/g, '_');
  }) : [];
  const approvedPitchers = pitcherPostures.length > 0
    && pitcherPostures.every(posture => APPROVED_POSTURES.has(posture));
  const approvedPosture = pitcherPostures.length > 0
    ? approvedPitchers && (!directPosture || APPROVED_POSTURES.has(directPosture))
    : APPROVED_POSTURES.has(directPosture);
  if (text(row.artifact_key) !== CANONICAL_ARTIFACT_KEY
      || validDate(row.slate_date) !== slateDate
      || validDate(row.payload_date) !== slateDate
      || !validHash(row.payload_sha256)
      || !approvedPosture
      || text(row.artifact_path) !== CANONICAL_ARTIFACT_PATH
      || !timestamp(row.generated_at)
      || !text(row.source)) return null;
  return {
    payloadSha: validHash(row.payload_sha256),
    generatedAt: timestamp(row.generated_at),
    path: CANONICAL_ARTIFACT_PATH,
  };
}

function provisionalIsCurrent(row, artifact) {
  return validStateBase(row, row.slate_date)
    && text(row.checkpoint) === 'provisional'
    && text(row.source_artifact_path) === artifact.path
    && validHash(row.source_artifact_sha256) === artifact.payloadSha
    && !text(row.frozen_at) && !text(row.lock_dedupe_key) && !text(row.lock_artifact_sha256)
    && !text(row.lock_source_artifact_path) && !text(row.locked_at)
    && !text(row.should_lock_at) && row.minutes_until_start == null && !text(row.lock_status);
}

function lockMatchesFrozenRow(row, lock, artifact) {
  if (!lock || typeof lock !== 'object') return false;
  const stateLockHash = validHash(row.lock_artifact_sha256);
  const lockHash = validHash(lock.source_artifact_sha256);
  const metadata = lock.metadata;
  return text(row.checkpoint) === 'frozen_pregame'
    && text(row.source_artifact_path) === artifact.path
    && text(row.lock_source_artifact_path) === artifact.path
    && text(lock.source_artifact_path) === artifact.path
    && text(row.lock_dedupe_key) && text(lock.dedupe_key) === text(row.lock_dedupe_key)
    && validDate(lock.slate_date) === row.slate_date
    && text(lock.normalized_pitcher) === text(row.normalized_pitcher)
    && text(lock.side).toLowerCase() === text(row.side).toLowerCase()
    && number(lock.locked_k_line) === number(row.model_k_line)
    && integer(lock.locked_odds) === integer(row.official_odds)
    && sameBook(lock.locked_book, row.official_book)
    && sameTimestamp(lock.game_time, row.game_time)
    && LOCK_STATUSES.has(text(row.lock_status)) && text(lock.status_at_capture) === text(row.lock_status)
    && sameTimestamp(row.frozen_at, row.locked_at)
    && sameTimestamp(lock.locked_at, row.locked_at)
    && sameTimestamp(lock.observed_at, row.locked_at)
    && sameTimestamp(lock.should_lock_at, row.should_lock_at)
    && number(lock.minutes_until_start) === number(row.minutes_until_start)
    && stateLockHash && stateLockHash === lockHash
    && stateLockHash === validHash(row.source_artifact_byte_sha256)
    && metadata && typeof metadata === 'object'
    && text(metadata.team).toUpperCase() === text(row.team).toUpperCase()
    && text(metadata.opp_team).toUpperCase() === text(row.opp_team).toUpperCase();
}

async function supabaseRead({ supabaseUrl, serviceRoleKey, table, params }) {
  const url = new URL(`${supabaseUrl.replace(/\/$/, '')}/rest/v1/${table}`);
  for (const [key, value] of Object.entries(params)) url.searchParams.set(key, value);
  const response = await fetch(url, {
    headers: { apikey: serviceRoleKey, authorization: `Bearer ${serviceRoleKey}` },
  });
  if (!response.ok) throw new Error('supabase_read_failed');
  const body = await response.json();
  if (!Array.isArray(body)) throw new Error('supabase_response_invalid');
  return body;
}

function lockFilter(keys) {
  const quoted = keys.map(key => `"${key.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`);
  return `in.(${quoted.join(',')})`;
}

export async function handler(event = {}) {
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: JSON_HEADERS, body: '' };
  if (event.httpMethod && event.httpMethod !== 'GET') return jsonResponse(405, { error: 'method_not_allowed' });

  let slateDate;
  try { slateDate = currentPhoenixDate(); } catch { return jsonResponse(200, emptyPayload(null, 'clock_unavailable', 'unavailable')); }
  const requestedDate = text(event.queryStringParameters?.date || event.queryStringParameters?.slate_date);
  if (requestedDate && requestedDate !== slateDate) return jsonResponse(200, emptyPayload(slateDate));

  const supabaseUrl = envValue('SUPABASE_URL');
  const serviceRoleKey = envValue('SUPABASE_SERVICE_ROLE_KEY');
  if (!supabaseUrl || !serviceRoleKey) return jsonResponse(200, emptyPayload(slateDate, 'missing_supabase_config', 'unavailable'));

  try {
    const canonicalRows = await supabaseRead({
      supabaseUrl, serviceRoleKey, table: 'published_pipeline_artifacts',
      params: { select: CANONICAL_SELECT, artifact_key: 'eq.today', limit: '1' },
    });
    const artifact = canonicalRows.length === 1 ? validCanonical(canonicalRows[0], slateDate) : null;
    if (!artifact) return jsonResponse(200, emptyPayload(slateDate, 'canonical_artifact_unavailable', 'unavailable'));

    const stateRows = await supabaseRead({
      supabaseUrl, serviceRoleKey, table: 'alternative_pick_selection_state',
      params: {
        select: STATE_SELECT, slate_date: `eq.${slateDate}`, bundle_id: `eq.${BUNDLE_ID}`,
        checkpoint: 'in.(provisional,frozen_pregame)', limit: '250',
      },
    });
    const rows = stateRows.filter(row => validStateBase(row, slateDate));
    const frozenRows = rows.filter(row => text(row.checkpoint) === 'frozen_pregame');
    const dedupeKeys = [...new Set(frozenRows.map(row => text(row.lock_dedupe_key)).filter(Boolean))];
    const locks = dedupeKeys.length ? await supabaseRead({
      supabaseUrl, serviceRoleKey, table: 'operational_pick_locks',
      params: { select: LOCK_SELECT, slate_date: `eq.${slateDate}`, dedupe_key: lockFilter(dedupeKeys), limit: String(dedupeKeys.length) },
    }) : [];
    const lockByKey = new Map(locks.map(lock => [text(lock.dedupe_key), lock]));
    const visible = rows.flatMap(row => {
      if (text(row.checkpoint) === 'provisional') {
        return provisionalIsCurrent(row, artifact) ? [responseRow(row, { artifactAdvancedAfterFreeze: false })] : [];
      }
      const lock = lockByKey.get(text(row.lock_dedupe_key));
      if (!lockMatchesFrozenRow(row, lock, artifact)) return [];
      return [responseRow(row, {
        artifactAdvancedAfterFreeze: validHash(row.source_artifact_sha256) !== artifact.payloadSha,
      })];
    });
    const counts = {
      provisional: visible.filter(row => row.checkpoint === 'provisional').length,
      frozen: visible.filter(row => row.checkpoint === 'frozen_pregame').length,
      selected: visible.filter(row => row.selection_status === 'selected').length,
      pending: visible.filter(row => row.selection_status === 'pending').length,
    };
    return jsonResponse(200, {
      slate_date: slateDate, generated_at: artifact.generatedAt, status: 'ready', counts, rows: visible, error: null,
    });
  } catch {
    return jsonResponse(200, emptyPayload(slateDate, 'supabase_read_failed', 'unavailable'));
  }
}
