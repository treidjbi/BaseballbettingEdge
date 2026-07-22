import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

import { handler } from '../netlify/functions/alternative-picks.mjs';

const NOW = '2026-07-21T20:10:00.000Z';
const CURRENT_SHA = 'a'.repeat(64);
const FROZEN_CANONICAL_SHA = 'b'.repeat(64);
const LOCK_SHA = 'c'.repeat(64);
const SECRET = 'service-role-secret';
const LOCK_URL = 'https://app.example/.netlify/functions/get-artifact?type=today';
const MANIFEST = JSON.parse(readFileSync(
  new URL('../market_infra/alternative_pick_selector_manifest_v1.json', import.meta.url),
));
function sortManifest(value) {
  if (Array.isArray(value)) return value.map(sortManifest);
  if (value && typeof value === 'object') return Object.fromEntries(
    Object.keys(value).sort().map(key => [key, sortManifest(value[key])])
  );
  return value;
}
const MANIFEST_FINGERPRINT = createHash('sha256')
  .update(JSON.stringify(sortManifest(MANIFEST)), 'utf8').digest('hex');
const ALLOWED_ROW_KEYS = [
  'artifact_advanced_after_freeze', 'bundle_id', 'checkpoint',
  'evidence_first_observed_at', 'evidence_freshness_status',
  'evidence_last_observed_at', 'evidence_observation_count', 'family_count',
  'family_states', 'frozen_at', 'game_time', 'lane', 'lock_status',
  'minutes_until_start', 'model_k_line', 'official_book', 'official_odds',
  'official_verdict', 'opp_team', 'pitcher', 'reason_codes', 'selector_id',
  'selection_status', 'should_lock_at', 'side', 'slate_date',
  'source_artifact_generated_at', 'team',
].sort();

const ORIGINAL_ENV = {
  SUPABASE_URL: process.env.SUPABASE_URL,
  SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
};

function restoreEnv() {
  for (const [key, value] of Object.entries(ORIGINAL_ENV)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  delete globalThis.__alternativePicksNow;
}

function event(queryStringParameters = {}, httpMethod = 'GET') {
  return { httpMethod, queryStringParameters };
}

async function responseJson(input) {
  const response = await handler(input);
  return { ...response, json: response.body ? JSON.parse(response.body) : null };
}

function canonicalArtifact(overrides = {}) {
  return {
    artifact_key: 'today',
    payload_sha256: CURRENT_SHA,
    slate_date: '2026-07-21',
    generated_at: '2026-07-21T20:00:00Z',
    source: 'render_pipeline',
    payload_date: '2026-07-21',
    payload_pitchers: [{ odds_source: 'therundown_propline', market_source_mode: 'therundown_propline' }],
    artifact_path: 'dashboard/data/processed/today.json',
    ...overrides,
  };
}

function frozenState(overrides = {}) {
  return {
    id: 'never-expose-state-id',
    slate_date: '2026-07-21',
    game_identity: 'never-expose-game-identity',
    candidate_identity: 'never-expose-candidate-identity',
    pitcher: 'Test Pitcher',
    normalized_pitcher: 'test pitcher',
    team: 'ARI',
    opp_team: 'LAD',
    game_time: '2026-07-21T21:00:00Z',
    side: 'over',
    model_k_line: 5.5,
    bundle_id: 'pregame_alternative_pick_methodology_v1',
    selector_id: MANIFEST.selector_ids.consensus_core,
    selector_fingerprint: MANIFEST_FINGERPRINT,
    checkpoint: 'frozen_pregame',
    official_odds: -115,
    official_book: 'fanduel',
    official_verdict: 'FIRE 1u',
    lane: 'consensus_core',
    selection_status: 'selected',
    family_states: { base: { state: 'agree', reason_codes: ['base_ok'] } },
    family_count: 1,
    reason_codes: ['selected'],
    source_artifact_generated_at: '2026-07-21T19:55:00Z',
    source_artifact_path: 'dashboard/data/processed/today.json',
    source_artifact_sha256: FROZEN_CANONICAL_SHA,
    source_artifact_byte_sha256: LOCK_SHA,
    evidence_observation_ids: ['never-expose-observation-id'],
    evidence_observation_count: 2,
    evidence_first_observed_at: '2026-07-21T19:40:00Z',
    evidence_last_observed_at: '2026-07-21T19:50:00Z',
    evidence_freshness_status: 'fresh',
    frozen_at: '2026-07-21T20:00:00Z',
    lock_dedupe_key: '2026-07-21:test pitcher:over',
    lock_artifact_sha256: LOCK_SHA,
    lock_source_artifact_path: LOCK_URL,
    locked_at: '2026-07-21T20:00:00Z',
    should_lock_at: '2026-07-21T20:00:00Z',
    minutes_until_start: 60,
    lock_status: 'due_now',
    metadata: { internal_url: 'https://private.example/secret' },
    ...overrides,
  };
}

function provisionalState(overrides = {}) {
  return frozenState({
    checkpoint: 'provisional',
    source_artifact_sha256: CURRENT_SHA,
    frozen_at: null,
    lock_dedupe_key: null,
    lock_artifact_sha256: null,
    lock_source_artifact_path: null,
    locked_at: null,
    should_lock_at: null,
    minutes_until_start: null,
    lock_status: null,
    ...overrides,
  });
}

function matchingLock(state, overrides = {}) {
  return {
    id: 'never-expose-lock-id',
    dedupe_key: state.lock_dedupe_key,
    slate_date: state.slate_date,
    normalized_pitcher: state.normalized_pitcher,
    side: state.side,
    locked_k_line: state.model_k_line,
    locked_odds: state.official_odds,
    locked_book: state.official_book,
    game_time: state.game_time,
    status_at_capture: state.lock_status,
    observed_at: state.locked_at,
    locked_at: state.locked_at,
    should_lock_at: state.should_lock_at,
    minutes_until_start: state.minutes_until_start,
    source_artifact_path: state.lock_source_artifact_path,
    source_artifact_sha256: state.lock_artifact_sha256,
    metadata: { team: state.team, opp_team: state.opp_team, raw: 'never-expose-lock-metadata' },
    ...overrides,
  };
}

function installFetch({ artifact = canonicalArtifact(), stateRows = [], lockRows = [], status = 200 } = {}) {
  const calls = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    const href = String(url);
    calls.push({ href, options });
    if (status !== 200) return new Response(`${SECRET} raw database failure`, { status });
    const table = new URL(href).pathname.split('/').at(-1);
    const body = table === 'published_pipeline_artifacts' ? [artifact]
      : table === 'alternative_pick_selection_state' ? stateRows
        : table === 'operational_pick_locks' ? lockRows : [];
    return new Response(JSON.stringify(body), { status: 200 });
  };
  return { calls, restore: () => { globalThis.fetch = originalFetch; } };
}

function configure() {
  process.env.SUPABASE_URL = 'https://example.supabase.co/';
  process.env.SUPABASE_SERVICE_ROLE_KEY = SECRET;
  globalThis.__alternativePicksNow = NOW;
}

test('alternative-picks handles OPTIONS and rejects non-GET requests', async () => {
  const options = await handler(event({}, 'OPTIONS'));
  assert.equal(options.statusCode, 204);
  assert.equal(options.body, '');
  const post = await responseJson(event({}, 'POST'));
  assert.equal(post.statusCode, 405);
  assert.equal(post.json.error, 'method_not_allowed');
  restoreEnv();
});

test('alternative-picks returns a stable unavailable payload without configuration', async () => {
  delete process.env.SUPABASE_URL;
  delete process.env.SUPABASE_SERVICE_ROLE_KEY;
  globalThis.__alternativePicksNow = NOW;
  try {
    const response = await responseJson(event());
    assert.equal(response.statusCode, 200);
    assert.equal(response.headers['cache-control'], 'no-store');
    assert.deepEqual(response.json, {
      slate_date: '2026-07-21', generated_at: null, status: 'unavailable',
      counts: { provisional: 0, frozen: 0, selected: 0, pending: 0 }, rows: [],
      error: 'missing_supabase_config',
    });
  } finally { restoreEnv(); }
});

test('alternative-picks computes Phoenix today server-side and never queries a caller supplied historical slate', async () => {
  configure();
  const fake = installFetch();
  try {
    const response = await responseJson(event({ date: '2026-07-20' }));
    assert.equal(response.statusCode, 200);
    assert.equal(response.json.slate_date, '2026-07-21');
    assert.equal(response.json.status, 'ready');
    assert.deepEqual(response.json.rows, []);
    assert.equal(fake.calls.length, 0);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks uses canonical today first and returns only a fully linked frozen row after artifact advance', async () => {
  configure();
  const frozen = frozenState();
  const staleProvisional = frozenState({ checkpoint: 'provisional', frozen_at: null, lock_dedupe_key: null, lock_artifact_sha256: null, lock_source_artifact_path: null, locked_at: null, should_lock_at: null, minutes_until_start: null, lock_status: null });
  const fake = installFetch({ stateRows: [staleProvisional, frozen], lockRows: [matchingLock(frozen)] });
  try {
    const response = await responseJson(event());
    assert.equal(response.statusCode, 200);
    assert.equal(response.json.status, 'ready');
    assert.deepEqual(response.json.counts, { provisional: 0, frozen: 1, selected: 1, pending: 0 });
    assert.equal(response.json.rows.length, 1);
    assert.deepEqual(Object.keys(response.json.rows[0]).sort(), ALLOWED_ROW_KEYS);
    assert.equal(response.json.rows[0].artifact_advanced_after_freeze, true);
    assert.equal(JSON.stringify(response.json).includes(LOCK_URL), false);
    assert.equal(JSON.stringify(response.json).includes(SECRET), false);
    assert.equal(JSON.stringify(response.json).includes('never-expose'), false);
    assert.equal(fake.calls.length, 3);
    const canonical = fake.calls[0];
    assert.match(canonical.href, /published_pipeline_artifacts/);
    assert.match(canonical.href, /artifact_key=eq\.today/);
    assert.match(canonical.href, /payload_sha256/);
    assert.doesNotMatch(canonical.href, /order=/);
    assert.equal(canonical.options.headers.apikey, SECRET);
    assert.equal(canonical.options.headers.authorization, `Bearer ${SECRET}`);
    assert.match(fake.calls[1].href, /alternative_pick_selection_state/);
    assert.match(fake.calls[1].href, /slate_date=eq\.2026-07-21/);
    assert.match(fake.calls[1].href, /bundle_id=eq\.pregame_alternative_pick_methodology_v1/);
    assert.match(fake.calls[2].href, /operational_pick_locks/);
    assert.match(fake.calls[2].href, /dedupe_key=in\./);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks preserves the Task 2 logical-artifact and exact-fetch lock-path contract', async () => {
  configure();
  const frozen = frozenState();
  const fake = installFetch({ stateRows: [frozen], lockRows: [matchingLock(frozen)] });
  try {
    const response = await responseJson(event());
    assert.equal(frozen.source_artifact_path, 'dashboard/data/processed/today.json');
    assert.equal(frozen.lock_source_artifact_path, LOCK_URL);
    assert.equal(matchingLock(frozen).source_artifact_path, LOCK_URL);
    assert.equal(response.json.rows.length, 1);
    assert.equal(JSON.stringify(response.json).includes(LOCK_URL), false);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks rejects foreign selectors, bad fingerprints, untyped values, and unsafe display text', async () => {
  const invalidRows = [
    frozenState({ selector_id: 'foreign_selector_v1' }),
    frozenState({ selector_fingerprint: 'e'.repeat(64) }),
    frozenState({ selector_fingerprint: 'not-a-hash' }),
    frozenState({ model_k_line: '5.5' }),
    frozenState({ official_odds: null }),
    frozenState({ official_book: 'https://private.example/book' }),
    frozenState({ pitcher: 'https://private.example/secret' }),
    frozenState({ team: 'ARI?token=secret' }),
    frozenState({ reason_codes: ['https://private.example/raw'] }),
    frozenState({ family_states: { 'https://private.example/family': { state: 'agree' } } }),
  ];
  for (const state of invalidRows) {
    configure();
    const fake = installFetch({ stateRows: [state], lockRows: [matchingLock(state)] });
    try {
      const response = await responseJson(event());
      assert.deepEqual(response.json.rows, []);
    } finally { fake.restore(); restoreEnv(); }
  }
});

test('alternative-picks accepts null-lane supporting rows while keeping selected lane identity strict', async () => {
  const validRows = [
    provisionalState({ lane: null, selector_id: null, selection_status: 'not_selected' }),
    provisionalState({ lane: null, selector_id: null, selection_status: 'pending' }),
    provisionalState({ selection_status: 'pending' }),
  ];
  configure();
  const validFetch = installFetch({ stateRows: validRows });
  try {
    const response = await responseJson(event());
    assert.equal(response.json.status, 'ready');
    assert.equal(response.json.rows.length, 3);
    assert.deepEqual(
      response.json.rows.map(row => [row.selection_status, row.lane, row.selector_id]),
      [
        ['not_selected', null, null],
        ['pending', null, null],
        ['pending', 'consensus_core', MANIFEST.selector_ids.consensus_core],
      ],
    );
    assert.deepEqual(response.json.counts, { provisional: 3, frozen: 0, selected: 0, pending: 2 });
  } finally { validFetch.restore(); restoreEnv(); }

  const invalidRows = [
    provisionalState({ lane: null, selector_id: null, selection_status: 'selected' }),
    provisionalState({ selection_status: 'not_selected' }),
    provisionalState({ lane: null, selector_id: MANIFEST.selector_ids.consensus_core, selection_status: 'pending' }),
    provisionalState({ selector_id: null, selection_status: 'pending' }),
    provisionalState({ selector_id: MANIFEST.selector_ids.reentry_expansion, selection_status: 'pending' }),
    provisionalState({ lane: '', selector_id: '', selection_status: 'pending' }),
    provisionalState({ lane: '   ', selector_id: '\t', selection_status: 'pending' }),
    provisionalState({ lane: undefined, selector_id: undefined, selection_status: 'pending' }),
  ];
  const missingLane = provisionalState({ lane: null, selector_id: null, selection_status: 'pending' });
  delete missingLane.lane;
  const missingSelector = provisionalState({ lane: null, selector_id: null, selection_status: 'pending' });
  delete missingSelector.selector_id;
  invalidRows.push(missingLane, missingSelector);
  for (const state of invalidRows) {
    configure();
    const invalidFetch = installFetch({ stateRows: [state] });
    try { assert.deepEqual((await responseJson(event())).json.rows, []); }
    finally { invalidFetch.restore(); restoreEnv(); }
  }
});

test('alternative-picks distinguishes a healthy no-qualifier row from waiting on current evidence', async () => {
  configure();
  const healthyFetch = installFetch({
    stateRows: [provisionalState({ lane: null, selector_id: null, selection_status: 'not_selected' })],
  });
  try {
    const healthy = await responseJson(event());
    assert.equal(healthy.json.status, 'ready');
    assert.equal(healthy.json.rows.length, 1);
    assert.equal(healthy.json.rows[0].selection_status, 'not_selected');
  } finally { healthyFetch.restore(); restoreEnv(); }

  configure();
  const waitingFetch = installFetch({
    stateRows: [provisionalState({
      lane: null, selector_id: null, selection_status: 'pending', source_artifact_sha256: FROZEN_CANONICAL_SHA,
    })],
  });
  try {
    const waiting = await responseJson(event());
    assert.equal(waiting.json.status, 'ready');
    assert.deepEqual(waiting.json.rows, []);
  } finally { waitingFetch.restore(); restoreEnv(); }
});

test('alternative-picks requires every declared provider posture and an approved publication source', async () => {
  const artifacts = [
    canonicalArtifact({ source: 'github_actions' }),
    canonicalArtifact({ source: 'render_pipeline' }),
    canonicalArtifact({ source: 'render_live_layer' }),
    canonicalArtifact({ source: 'manual_backfill' }),
  ];
  for (const artifact of artifacts) {
    configure();
    const fake = installFetch({ artifact });
    try { assert.equal((await responseJson(event())).json.status, 'ready'); }
    finally { fake.restore(); restoreEnv(); }
  }
  for (const artifact of [
    canonicalArtifact({ source: 'unknown_source' }),
    canonicalArtifact({ payload_pitchers: [{ market_source_mode: 'therundown', odds_source: 'boltodds' }] }),
    canonicalArtifact({ payload_pitchers: [{ market_source_mode: 'therundown', odds_source: 'propline' }] }),
  ]) {
    configure();
    const fake = installFetch({ artifact });
    try { assert.equal((await responseJson(event())).json.status, 'unavailable'); }
    finally { fake.restore(); restoreEnv(); }
  }
});

test('alternative-picks suppresses frozen rows for every lock-link mismatch', async () => {
  const cases = {
    dedupe_key: 'wrong:key', slate_date: '2026-07-20', normalized_pitcher: 'wrong pitcher',
    side: 'under', locked_k_line: 6.5, locked_odds: -110, locked_book: 'draftkings',
    game_time: '2026-07-21T21:30:00Z', status_at_capture: 'missed_lock',
    observed_at: '2026-07-21T20:01:00Z', locked_at: '2026-07-21T20:01:00Z',
    should_lock_at: '2026-07-21T20:01:00Z', minutes_until_start: 59,
    source_artifact_path: 'other.json', source_artifact_sha256: 'd'.repeat(64),
    metadata: { team: 'LAD', opp_team: 'ARI' },
  };
  for (const [field, value] of Object.entries(cases)) {
    configure();
    const frozen = frozenState();
    const fake = installFetch({ stateRows: [frozen], lockRows: [matchingLock(frozen, { [field]: value })] });
    try {
      const response = await responseJson(event());
      assert.equal(response.json.status, 'ready', field);
      assert.deepEqual(response.json.rows, [], field);
      assert.deepEqual(response.json.counts, { provisional: 0, frozen: 0, selected: 0, pending: 0 }, field);
    } finally { fake.restore(); restoreEnv(); }
  }
});

test('alternative-picks rejects malformed/unapproved canonical artifacts and sanitizes read failures', async () => {
  for (const artifact of [
    canonicalArtifact({ artifact_key: 'not-today' }),
    canonicalArtifact({ slate_date: '2026-07-20' }),
    canonicalArtifact({ payload_sha256: 'not-a-hash' }),
    canonicalArtifact({ payload_pitchers: [{ odds_source: 'propline' }] }),
    canonicalArtifact({ payload_pitchers: [{ odds_source: 'boltodds' }] }),
  ]) {
    configure();
    const fake = installFetch({ artifact });
    try {
      const response = await responseJson(event());
      assert.equal(response.statusCode, 200);
      assert.equal(response.json.status, 'unavailable');
      assert.deepEqual(response.json.rows, []);
      assert.equal(fake.calls.length, 1);
    } finally { fake.restore(); restoreEnv(); }
  }
  configure();
  const fake = installFetch({ status: 500 });
  try {
    const response = await responseJson(event());
    assert.equal(response.statusCode, 200);
    assert.equal(response.json.status, 'unavailable');
    assert.equal(response.json.error, 'supabase_read_failed');
    assert.equal(JSON.stringify(response.json).includes(SECRET), false);
  } finally { fake.restore(); restoreEnv(); }
});
