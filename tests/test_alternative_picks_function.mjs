import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { gunzipSync } from 'node:zlib';

import { handler } from '../netlify/functions/alternative-picks.mjs';

const NOW = '2026-07-21T20:10:00.000Z';
const CURRENT_SHA = 'a'.repeat(64);
const FROZEN_CANONICAL_SHA = 'b'.repeat(64);
const LOCK_SHA = 'c'.repeat(64);
const SERVED_BODY_SHA = 'd5dd3a6a1c43476d0381c2aebed9a228edbfc0d24809046b3735b2e92cf1be9b';
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
const V1_BUNDLE_ID = 'pregame_alternative_pick_methodology_v1';
const V2_BUNDLE_ID = 'pregame_alternative_pick_methodology_v2';
const V2_FINGERPRINT = '23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4';
const V2_SELECTOR_IDS = Object.freeze({
  consensus_core: 'no_drag_distinct_family_consensus_core_v2',
  reentry_expansion: 'moderate_edge_quality_reentry_expansion_v2',
});
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
const V1_ROW_KEY_ORDER = [
  'slate_date', 'pitcher', 'team', 'opp_team', 'game_time', 'side',
  'model_k_line', 'official_odds', 'official_book', 'official_verdict',
  'bundle_id', 'selector_id', 'lane', 'selection_status', 'family_states',
  'family_count', 'checkpoint', 'reason_codes', 'source_artifact_generated_at',
  'evidence_observation_count', 'evidence_first_observed_at',
  'evidence_last_observed_at', 'evidence_freshness_status', 'frozen_at',
  'should_lock_at', 'minutes_until_start', 'lock_status',
  'artifact_advanced_after_freeze',
];

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
    payload: {
      date: '2026-07-21',
      generated_at: '2026-07-21T20:00:00Z',
      pitchers: [{ odds_source: 'therundown_propline', market_source_mode: 'therundown_propline' }],
    },
    artifact_path: 'dashboard/data/processed/today.json',
    ...overrides,
  };
}

function frozenState(overrides = {}) {
  return {
    id: 'never-expose-state-id',
    slate_date: '2026-07-21',
    game_identity: 'never-expose-game-identity',
    candidate_identity: '1'.repeat(64),
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

function v2Proof(row, overrides = {}) {
  const preclosePending = row.family_states?.preclose?.state === 'pending';
  const observationTokens = [
    'therundown:snapshot-000', 'therundown:snapshot-001', 'therundown:snapshot-002',
    'therundown:snapshot-003', 'therundown:snapshot-004', 'therundown:snapshot-005',
  ];
  const decisiveTokens = preclosePending ? [] : [observationTokens[0], observationTokens.at(-1)];
  const proof = {
    schema_version: 'v2',
    bundle_id: V2_BUNDLE_ID,
    selector_fingerprint: V2_FINGERPRINT,
    candidate: {
      candidate_identity: row.candidate_identity,
      slate_date: row.slate_date,
      normalized_pitcher: row.normalized_pitcher,
      side: row.side,
      model_k_line: row.model_k_line,
      game_time: row.game_time,
      line_source_provider: 'therundown',
      official_binding_key: 'd'.repeat(64),
    },
    artifact: {
      source_artifact_path: row.source_artifact_path,
      source_artifact_generated_at: row.source_artifact_generated_at,
      source_artifact_sha256: row.source_artifact_sha256,
      source_artifact_byte_sha256: row.source_artifact_byte_sha256,
    },
    bindings: {
      therundown: {
        role: 'official', provider_event_id: 'private-event-id', current_line_ids: ['private-line-id'],
        seed_observation_tokens: ['therundown:private-seed-id'], binding_key: 'd'.repeat(64),
        window_started_at: '2026-07-21T19:40:00Z', mature: !preclosePending,
      },
    },
    freshness: preclosePending ? {} : {
      therundown: { freshness_status: 'fresh', latest_snapshot_at: '2026-07-21T19:50:05Z' },
    },
    normalized_inputs: {
      side: row.side, official_verdict: row.official_verdict, source_fire_verdict: 'FIRE 1u',
      pitcher: row.normalized_pitcher, game_time: row.game_time, k_line: row.model_k_line,
      line_bucket: '5.5', odds: row.official_odds, official_book: row.official_book,
      price_sign: 'minus', bet_timing_window: 'pre_30',
      model_market_relationship: 'model_agrees_with_favorite', model_no_vig_gap: 0.031,
      edge: 0.035, adjusted_ev: 0.09, adjusted_ev_error: null,
      quality_gate_level: 'clean', opportunity_bucket: 'normal', leash_risk_bucket: 'normal',
      pitcher_archetype_bucket: 'standard', is_opener: false, starter_mismatch: false,
      last_pitch_count: 95, days_since_last_start: 5, workload_input_status: 'complete',
      large_edge_skepticism_flag: false,
      anchor_labels: ['market_anchor_strict'], anchor_metadata_malformed: false,
      observed_at: '2026-07-21T20:10:00Z',
    },
    preclose: {
      qualifying_observation_count: preclosePending ? 0 : observationTokens.length,
      decisive_observation_tokens: decisiveTokens,
      full_ordered_token_sha256: 'e'.repeat(64), direction_change_pivot_tokens: [],
      latest_ladder_observation_tokens: preclosePending ? [] : [observationTokens.at(-1)],
      ladder_observation_token_sha256: 'f'.repeat(64),
      first_observed_at: preclosePending ? null : '2026-07-21T19:50:00Z',
      last_observed_at: preclosePending ? null : '2026-07-21T19:50:05Z',
      freshness_status: preclosePending ? 'pending' : 'fresh',
      book_count: preclosePending ? null : 2,
      books_seen: preclosePending ? [] : ['draftkings', 'fanduel'],
      toward_pick_count: preclosePending ? null : 2,
      away_from_pick_count: preclosePending ? null : 0,
      side_price_movement: preclosePending ? null : 'with_side',
      broad_confirmation: preclosePending ? null : false,
      reversal_book_count: preclosePending ? null : 0,
      volatile_book_count: preclosePending ? null : 0,
      best_is_off_market: preclosePending ? null : false,
      score: preclosePending ? null : 11,
      label: preclosePending ? null : 'strong_preclose_clv_proxy',
      positive_reasons: preclosePending ? [] : [
        'movement_toward_pick', 'moderate_low_edge_market_validation',
        'thin_or_price_only_no_vig_gap', 'minus_price_market_support', 'clean_quality',
        'early_lock_window', 'low_volatility', 'moderate_ev_market_validation',
      ],
      risk_reasons: [], reason_codes: preclosePending ? ['official_provider_immature'] : [],
    },
    decision: {
      support: 'true', drag_core: 'false', no_drag: 'true',
      family_states: row.family_states,
      consensus_core: 'true', reentry_expansion: 'false', selected_lane: row.lane,
      selection_status: row.selection_status, family_count: row.family_count,
      maximum_family_count: Object.values(row.family_states).filter(vote => vote.state !== 'disagree').length,
      decisive_families: ['base', 'anchor', 'preclose', 'reentry']
        .filter(name => row.family_states[name].state === 'agree'),
      preclose_required_for_selected_lane: false,
      reason_codes: ['consensus_core_selected'],
    },
  };
  return { ...proof, ...overrides };
}

function v2ProvisionalState(overrides = {}) {
  const familyStates = {
    base: { state: 'agree', reason_codes: ['strong_base_strict_runtime_core'] },
    anchor: { state: 'agree', reason_codes: ['market_anchor_v2_confirmed'] },
    preclose: { state: 'pending', reason_codes: ['official_provider_immature'] },
    reentry: { state: 'disagree', reason_codes: ['reentry_predicate_false'] },
  };
  const row = provisionalState({
    bundle_id: V2_BUNDLE_ID,
    selector_id: V2_SELECTOR_IDS.consensus_core,
    selector_fingerprint: V2_FINGERPRINT,
    family_states: familyStates,
    family_count: 2,
    evidence_observation_ids: [],
    evidence_observation_count: 0,
    evidence_first_observed_at: null,
    evidence_last_observed_at: null,
    evidence_freshness_status: 'pending',
    ...overrides,
  });
  if (!Object.hasOwn(overrides, 'evaluation_proof')) row.evaluation_proof = v2Proof(row);
  return row;
}

function v2FreshProvisionalState(overrides = {}) {
  const row = v2ProvisionalState({
    family_states: {
      base: { state: 'agree', reason_codes: ['strong_base_strict_runtime_core'] },
      anchor: { state: 'agree', reason_codes: ['market_anchor_v2_confirmed'] },
      preclose: { state: 'agree', reason_codes: ['preclose_v2_confirmed'] },
      reentry: { state: 'disagree', reason_codes: ['reentry_predicate_false'] },
    },
    family_count: 3,
    evidence_observation_ids: ['therundown:snapshot-000', 'therundown:snapshot-005'],
    evidence_observation_count: 6,
    evidence_first_observed_at: '2026-07-21T19:50:00Z',
    evidence_last_observed_at: '2026-07-21T19:50:05Z',
    evidence_freshness_status: 'fresh',
    ...overrides,
  });
  if (!Object.hasOwn(overrides, 'evaluation_proof')) row.evaluation_proof = v2Proof(row);
  return row;
}

function v2NoncompleteWorkloadState(field, status, { includeNull = false } = {}) {
  const reason = `workload_inputs_${status}`;
  const pendingVote = { state: 'pending', reason_codes: [reason] };
  const familyStates = {
    base: pendingVote,
    anchor: { state: 'agree', reason_codes: ['market_anchor_v2_confirmed'] },
    preclose: pendingVote,
    reentry: pendingVote,
  };
  const state = v2FreshProvisionalState();
  Object.assign(state, {
    lane: null,
    selector_id: null,
    selection_status: 'pending',
    family_states: familyStates,
    family_count: 1,
    reason_codes: [reason],
  });
  Object.assign(state.evaluation_proof.normalized_inputs, {
    [field]: -1,
    workload_input_status: status,
  });
  if (includeNull) state.evaluation_proof.normalized_inputs.is_opener = null;
  Object.assign(state.evaluation_proof.decision, {
    support: 'true',
    drag_core: 'false',
    no_drag: 'true',
    family_states: familyStates,
    consensus_core: 'pending',
    reentry_expansion: 'false',
    selected_lane: null,
    selection_status: 'pending',
    family_count: 1,
    maximum_family_count: 4,
    decisive_families: ['anchor'],
    preclose_required_for_selected_lane: false,
    reason_codes: [reason],
  });
  return state;
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

function installFetch({
  artifact = canonicalArtifact(), stateRows = [], lockRows = [], status = 200,
  directStateRows = false,
} = {}) {
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
    if (directStateRows && table === 'alternative_pick_selection_state') {
      return { ok: true, json: async () => body };
    }
    return new Response(JSON.stringify(body), { status: 200 });
  };
  return { calls, restore: () => { globalThis.fetch = originalFetch; } };
}

function configure() {
  process.env.SUPABASE_URL = 'https://example.supabase.co/';
  process.env.SUPABASE_SERVICE_ROLE_KEY = SECRET;
  globalThis.__alternativePicksNow = NOW;
}

test('alternative-picks preserves reviewed signed proofs and rejects malformed scores and counts', async t => {
  const rows = JSON.parse(gunzipSync(readFileSync(new URL(
    '../docs/research/evidence/2026-09-04-signed-score-proof-review/run/synthetic-rows.json.gz', import.meta.url,
  ))));
  for (const [label, value] of [['nan', NaN], ['positive_infinity', Infinity], ['negative_infinity', -Infinity]]) {
    rows[label] = structuredClone(rows.negative);
    rows[label].evaluation_proof.preclose.score = value;
  }
  for (const [name, fixture] of Object.entries(rows)) {
    await t.test(name, async () => {
      const state = { ...structuredClone(fixture), checkpoint: 'provisional', reason_codes: [],
        frozen_at: null, locked_at: null, lock_artifact_sha256: null };
      const artifact = canonicalArtifact({
        slate_date: state.slate_date, payload_date: state.slate_date,
        generated_at: state.source_artifact_generated_at,
        payload_sha256: state.source_artifact_sha256,
        payload: { date: state.slate_date, generated_at: state.source_artifact_generated_at,
          pitchers: [{ odds_source: 'therundown', market_source_mode: 'therundown' }] },
      });
      configure();
      globalThis.__alternativePicksNow = state.observed_at;
      const fake = installFetch({ artifact, stateRows: [state], directStateRows: true });
      try {
        const response = await responseJson(event({ bundle_version: 'v2' }));
        const valid = ['negative', 'zero', 'positive'].includes(name);
        assert.equal(response.statusCode, 200);
        assert.equal(response.json.rows.length, Number(valid), name);
        if (valid) assert.equal(response.json.rows[0].selection_status, 'not_selected');
      } finally { fake.restore(); restoreEnv(); }
    });
  }
});

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
      bundle_id: V1_BUNDLE_ID, selector_fingerprint: MANIFEST_FINGERPRINT,
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

test('alternative-picks keeps current V2 provisional rows visible across publisher hash normalization', async () => {
  configure();
  const state = v2FreshProvisionalState({
    source_artifact_generated_at: '2026-07-21T20:00:00Z',
    source_artifact_sha256: FROZEN_CANONICAL_SHA,
    source_artifact_byte_sha256: SERVED_BODY_SHA,
  });
  const fake = installFetch({ stateRows: [state] });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.equal(response.json.status, 'ready');
    assert.equal(response.json.generated_at, '2026-07-21T20:00:00.000Z');
    assert.equal(response.json.rows.length, 1);
    assert.equal(response.json.rows[0].pitcher, 'Test Pitcher');
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

test('alternative-picks maps canonical full MLB team names to safe display codes', async () => {
  configure();
  const fake = installFetch({
    stateRows: [provisionalState({
      team: 'BALTIMORE ORIOLES',
      opp_team: 'Boston Red Sox',
      lane: null,
      selector_id: null,
      selection_status: 'pending',
    })],
  });
  try {
    const response = await responseJson(event());
    assert.equal(response.json.status, 'ready');
    assert.equal(response.json.rows.length, 1);
    assert.equal(response.json.rows[0].team, 'BAL');
    assert.equal(response.json.rows[0].opp_team, 'BOS');
    assert.deepEqual(response.json.counts, { provisional: 1, frozen: 0, selected: 0, pending: 1 });
  } finally { fake.restore(); restoreEnv(); }
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

test('alternative-picks defaults an unversioned request to v1', async () => {
  configure();
  const fake = installFetch();
  try {
    const response = await responseJson(event());
    assert.equal(response.json.bundle_id, V1_BUNDLE_ID);
    assert.equal(response.json.selector_fingerprint, MANIFEST_FINGERPRINT);
    assert.match(fake.calls[1].href, /bundle_id=eq\.pregame_alternative_pick_methodology_v1/);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks serves explicit bundle_version v1 and v2 independently', async () => {
  for (const [version, state, bundleId, fingerprint] of [
    ['v1', provisionalState(), V1_BUNDLE_ID, MANIFEST_FINGERPRINT],
    ['v2', v2ProvisionalState(), V2_BUNDLE_ID, V2_FINGERPRINT],
  ]) {
    configure();
    const fake = installFetch({ stateRows: [state] });
    try {
      const response = await responseJson(event({ bundle_version: version }));
      assert.equal(response.json.status, 'ready');
      assert.equal(response.json.bundle_id, bundleId);
      assert.equal(response.json.selector_fingerprint, fingerprint);
      assert.equal(response.json.rows.length, 1);
      assert.equal(response.json.rows[0].bundle_id, bundleId);
      assert.match(fake.calls[1].href, new RegExp(`bundle_id=eq\\.${bundleId}`));
    } finally { fake.restore(); restoreEnv(); }
  }
});

test('alternative-picks rejects unsupported explicit bundle versions', async () => {
  for (const version of ['v3', 'V2', ' v2 ', 'bogus']) {
    configure();
    const fake = installFetch();
    try {
      const response = await responseJson(event({ bundle_version: version }));
      assert.equal(response.json.status, 'unavailable');
      assert.equal(response.json.error, 'unsupported_bundle_version');
      assert.equal(response.json.bundle_id, null);
      assert.equal(response.json.selector_fingerprint, null);
      assert.equal(fake.calls.length, 0);
    } finally { fake.restore(); restoreEnv(); }
  }
});

test('alternative-picks includes bundle and fingerprint on ready empty and unavailable payloads', async () => {
  configure();
  const readyFetch = installFetch();
  try {
    const ready = await responseJson(event({ bundle_version: 'v2' }));
    assert.equal(ready.json.status, 'ready');
    assert.equal(ready.json.bundle_id, V2_BUNDLE_ID);
    assert.equal(ready.json.selector_fingerprint, V2_FINGERPRINT);
  } finally { readyFetch.restore(); restoreEnv(); }

  delete process.env.SUPABASE_URL;
  delete process.env.SUPABASE_SERVICE_ROLE_KEY;
  globalThis.__alternativePicksNow = NOW;
  try {
    const unavailable = await responseJson(event({ bundle_version: 'v2' }));
    assert.equal(unavailable.json.status, 'unavailable');
    assert.equal(unavailable.json.bundle_id, V2_BUNDLE_ID);
    assert.equal(unavailable.json.selector_fingerprint, V2_FINGERPRINT);
  } finally { restoreEnv(); }
});

test('alternative-picks filters Supabase by the selected bundle', async () => {
  configure();
  const v1 = provisionalState();
  const v2 = v2ProvisionalState();
  const fake = installFetch({ stateRows: [v1, v2] });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.deepEqual(response.json.rows.map(row => row.bundle_id), [V2_BUNDLE_ID]);
    const stateUrl = new URL(fake.calls[1].href);
    assert.equal(stateUrl.searchParams.get('bundle_id'), `eq.${V2_BUNDLE_ID}`);
    assert.match(stateUrl.searchParams.get('select'), /evaluation_proof/);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks rejects missing malformed oversized or cross-row v2 proof', async () => {
  const base = v2ProvisionalState();
  const cases = [];
  const missing = { ...base };
  delete missing.evaluation_proof;
  cases.push(missing);
  cases.push(v2ProvisionalState({ evaluation_proof: [] }));
  cases.push(v2ProvisionalState({ evaluation_proof: { ...v2Proof(base), padding: 'x'.repeat(32768) } }));
  const missingIdentity = v2ProvisionalState({ candidate_identity: null });
  missingIdentity.evaluation_proof = v2Proof(missingIdentity);
  cases.push(missingIdentity);
  const crossRow = v2ProvisionalState();
  crossRow.evaluation_proof = v2Proof(crossRow, {
    candidate: { ...v2Proof(crossRow).candidate, candidate_identity: '0'.repeat(64) },
  });
  cases.push(crossRow);
  for (const state of cases) {
    configure();
    const fake = installFetch({ stateRows: [state] });
    try {
      const response = await responseJson(event({ bundle_version: 'v2' }));
      assert.equal(response.json.bundle_id, V2_BUNDLE_ID);
      assert.deepEqual(response.json.rows, []);
    }
    finally { fake.restore(); restoreEnv(); }
  }
});

test('alternative-picks rejects mixed selector identity family logic and artifact hashes', async () => {
  const mixedSelector = v2ProvisionalState({ selector_id: MANIFEST.selector_ids.consensus_core });
  const mixedFamilies = v2ProvisionalState();
  mixedFamilies.evaluation_proof = v2Proof(mixedFamilies, {
    decision: { ...v2Proof(mixedFamilies).decision, family_count: 3 },
  });
  const mixedArtifact = v2ProvisionalState();
  mixedArtifact.evaluation_proof = v2Proof(mixedArtifact, {
    artifact: { ...v2Proof(mixedArtifact).artifact, source_artifact_sha256: '9'.repeat(64) },
  });
  for (const state of [mixedSelector, mixedFamilies, mixedArtifact]) {
    configure();
    const fake = installFetch({ stateRows: [state] });
    try {
      const response = await responseJson(event({ bundle_version: 'v2' }));
      assert.equal(response.json.bundle_id, V2_BUNDLE_ID);
      assert.deepEqual(response.json.rows, []);
    }
    finally { fake.restore(); restoreEnv(); }
  }
});

test('alternative-picks rejects every canonical-python-invalid nested v2 proof mutation', async () => {
  const mutations = [
    proof => { delete proof.normalized_inputs.edge; },
    proof => { proof.bindings.therundown.binding_key = '9'.repeat(64); },
    proof => { proof.freshness = {}; },
    proof => { proof.preclose.score = 999; },
    (proof, row) => {
      row.official_verdict = 'LEAN';
      proof.normalized_inputs.official_verdict = 'LEAN';
    },
  ];
  for (const mutate of mutations) {
    const state = v2FreshProvisionalState();
    mutate(state.evaluation_proof, state);
    configure();
    const fake = installFetch({ stateRows: [state] });
    try {
      const response = await responseJson(event({ bundle_version: 'v2' }));
      assert.deepEqual(response.json.rows, []);
    } finally { fake.restore(); restoreEnv(); }
  }
});

test('alternative-picks rejects empty or duplicate provider binding identifiers', async () => {
  const mutations = [
    proof => { proof.bindings.therundown.current_line_ids[0] = ' '; },
    proof => { proof.bindings.therundown.current_line_ids.push(proof.bindings.therundown.current_line_ids[0]); },
    proof => { proof.bindings.therundown.seed_observation_tokens[0] = ' '; },
    proof => {
      proof.bindings.therundown.seed_observation_tokens.push(
        proof.bindings.therundown.seed_observation_tokens[0],
      );
    },
  ];
  for (const mutate of mutations) {
    const state = v2FreshProvisionalState();
    mutate(state.evaluation_proof);
    configure();
    const fake = installFetch({ stateRows: [state] });
    try {
      const response = await responseJson(event({ bundle_version: 'v2' }));
      assert.deepEqual(response.json.rows, []);
    } finally { fake.restore(); restoreEnv(); }
  }
});

test('alternative-picks enforces the canonical 30720 byte application proof ceiling', async () => {
  const state = v2FreshProvisionalState();
  const proof = state.evaluation_proof;
  proof.bindings.therundown.current_line_ids = Array.from(
    { length: 32 }, (_, index) => `tr-line-${index}-${'x'.repeat(350)}`,
  );
  proof.bindings.therundown.seed_observation_tokens = Array.from(
    { length: 32 }, (_, index) => `therundown:seed-${index}-${'y'.repeat(350)}`,
  );
  proof.bindings.propline = {
    role: 'sidecar', provider_event_id: 'pl-event', current_line_ids: [],
    seed_observation_tokens: [], binding_key: '8'.repeat(64),
    window_started_at: '2026-07-21T19:40:00Z', mature: false,
  };
  let size = Buffer.byteLength(JSON.stringify(proof), 'utf8');
  for (let index = 0; size <= 30720 && index < 32; index += 1) {
    proof.bindings.propline.current_line_ids.push(`pl-line-${index}-${'z'.repeat(200)}`);
    size = Buffer.byteLength(JSON.stringify(proof), 'utf8');
  }
  assert.ok(size > 30720 && size <= 32768, `fixture size ${size}`);
  configure();
  const fake = installFetch({ stateRows: [state] });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.deepEqual(response.json.rows, []);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks requires decisive families to exactly match agreeing family order', async () => {
  for (const decisiveFamilies of [
    ['base', 'anchor'],
    ['base', 'anchor', 'preclose', 'reentry'],
    ['preclose', 'base', 'anchor'],
  ]) {
    const state = v2FreshProvisionalState();
    state.evaluation_proof.decision.decisive_families = decisiveFamilies;
    configure();
    const fake = installFetch({ stateRows: [state] });
    try {
      const response = await responseJson(event({ bundle_version: 'v2' }));
      assert.deepEqual(response.json.rows, []);
    } finally { fake.restore(); restoreEnv(); }
  }
});

test('alternative-picks accepts the complete canonical v2 proof fixture', async () => {
  configure();
  const state = v2FreshProvisionalState();
  const fake = installFetch({ stateRows: [state] });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.equal(response.json.rows.length, 1);
    assert.equal(response.json.rows[0].decision_proof.lane_states.consensus_core, 'true');
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks v2 proof binds complete workload inputs', async () => {
  configure();
  const row = v2FreshProvisionalState();
  const installed = installFetch({ stateRows: [row] });
  try {
    const response = await handler({ httpMethod: 'GET', queryStringParameters: { bundle_version: 'v2' } });
    const payload = JSON.parse(response.body);
    assert.equal(payload.status, 'ready');
    assert.equal(payload.rows.length, 1);
  } finally {
    installed.restore();
    restoreEnv();
  }
});

test('alternative-picks rejects negative workload integers labeled missing even with another null workload value', async t => {
  for (const field of ['last_pitch_count', 'days_since_last_start']) {
    await t.test(field, async () => {
      const state = v2NoncompleteWorkloadState(
        field, 'missing', { includeNull: true },
      );
      configure();
      const fake = installFetch({ stateRows: [state] });
      try {
        const response = await responseJson(event({ bundle_version: 'v2' }));
        assert.deepEqual(response.json.rows, []);
      } finally { fake.restore(); restoreEnv(); }
    });
  }
});

test('alternative-picks accepts negative workload integers labeled malformed with aligned pending state', async t => {
  for (const field of ['last_pitch_count', 'days_since_last_start']) {
    await t.test(field, async () => {
      const state = v2NoncompleteWorkloadState(field, 'malformed');
      configure();
      const fake = installFetch({ stateRows: [state] });
      try {
        const response = await responseJson(event({ bundle_version: 'v2' }));
        assert.equal(response.json.rows.length, 1);
        assert.equal(response.json.rows[0].selection_status, 'pending');
        assert.deepEqual(response.json.rows[0].family_states.base, {
          state: 'pending',
          reason_codes: ['workload_inputs_malformed'],
        });
      } finally { fake.restore(); restoreEnv(); }
    });
  }
});

test('alternative-picks rejects Python-invalid normalized scalar types per row', async t => {
  for (const [field, value] of [
    ['adjusted_ev', '0.09'],
    ['model_no_vig_gap', '0.031'],
    ['source_fire_verdict', 7],
  ]) {
    await t.test(field, async () => {
      const state = v2FreshProvisionalState();
      state.evaluation_proof.normalized_inputs[field] = value;
      configure();
      const fake = installFetch({ stateRows: [state] });
      try {
        const response = await responseJson(event({ bundle_version: 'v2' }));
        assert.equal(response.json.status, 'ready');
        assert.equal(response.json.counts.selected, 0);
        assert.deepEqual(response.json.rows, []);
      } finally { fake.restore(); restoreEnv(); }
    });
  }
});

test('alternative-picks rejects nullable or confused normalized Boolean proof inputs', async t => {
  const cases = [
    ['large_edge_skepticism_flag null', 'large_edge_skepticism_flag', null, true],
    ['anchor_metadata_malformed null', 'anchor_metadata_malformed', null, false],
    ['large_edge_skepticism_flag integer', 'large_edge_skepticism_flag', 0, false],
    ['anchor_metadata_malformed string', 'anchor_metadata_malformed', 'false', false],
  ];
  for (const [name, field, value, alignReentryPending] of cases) {
    await t.test(name, async () => {
      const state = v2FreshProvisionalState();
      if (alignReentryPending) {
        const pendingReentry = { state: 'pending', reason_codes: ['reentry_inputs_missing'] };
        state.family_states.reentry = pendingReentry;
        state.evaluation_proof.decision.family_states.reentry = pendingReentry;
        state.evaluation_proof.decision.maximum_family_count = 4;
      }
      state.evaluation_proof.normalized_inputs[field] = value;
      configure();
      const fake = installFetch({ stateRows: [state] });
      try {
        const response = await responseJson(event({ bundle_version: 'v2' }));
        assert.equal(response.json.status, 'ready');
        assert.equal(response.json.counts.selected, 0);
        assert.deepEqual(response.json.rows, []);
      } finally { fake.restore(); restoreEnv(); }
    });
  }
});

test('alternative-picks enforces the canonical normalized integer contract for odds', async t => {
  for (const [name, value] of [['fractional number', -115.5], ['numeric string', '-115']]) {
    await t.test(name, async () => {
      const state = v2FreshProvisionalState();
      state.evaluation_proof.normalized_inputs.odds = value;
      configure();
      const fake = installFetch({ stateRows: [state] });
      try {
        const response = await responseJson(event({ bundle_version: 'v2' }));
        assert.equal(response.json.status, 'ready');
        assert.deepEqual(response.json.rows, []);
      } finally { fake.restore(); restoreEnv(); }
    });
  }
});

test('alternative-picks suppresses one unexpected v2 proof exception without hiding valid rows', async () => {
  const explosive = v2FreshProvisionalState();
  Object.defineProperty(explosive.evaluation_proof, 'normalized_inputs', {
    enumerable: true,
    get() { throw new Error('unexpected proof accessor failure'); },
  });
  const valid = v2FreshProvisionalState();
  configure();
  const fake = installFetch({ stateRows: [explosive, valid], directStateRows: true });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.equal(response.json.status, 'ready');
    assert.equal(response.json.counts.selected, 1);
    assert.equal(response.json.rows.length, 1);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks sanitizes v2 proof without provider identifiers', async () => {
  configure();
  const state = v2ProvisionalState();
  const fake = installFetch({ stateRows: [state] });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    const decisionProof = response.json.rows[0].decision_proof;
    assert.deepEqual(Object.keys(decisionProof).sort(), [
      'decisive_families', 'drag_core', 'lane_states', 'no_drag',
      'preclose_required_for_selected_lane', 'support',
    ]);
    assert.equal(JSON.stringify(response.json).includes('private-event-id'), false);
    assert.equal(JSON.stringify(response.json).includes('private-line-id'), false);
    assert.equal(JSON.stringify(response.json).includes('private-seed-id'), false);
    assert.equal(JSON.stringify(response.json).includes('binding'), false);
    assert.equal(JSON.stringify(response.json).includes('normalized_inputs'), false);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks allows selected v2 with pending nonessential preclose and zero observations', async () => {
  configure();
  const state = v2ProvisionalState();
  const fake = installFetch({ stateRows: [state] });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.equal(response.json.rows.length, 1);
    assert.equal(response.json.rows[0].selection_status, 'selected');
    assert.equal(response.json.rows[0].family_states.preclose.state, 'pending');
    assert.equal(response.json.rows[0].evidence_observation_count, 0);
    assert.equal(response.json.rows[0].decision_proof.preclose_required_for_selected_lane, false);
    assert.deepEqual(response.json.rows[0].decision_proof.decisive_families, ['base', 'anchor']);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks allows a structurally valid fail-closed v2 diagnostic row', async () => {
  const pendingFamilies = Object.fromEntries(
    ['base', 'anchor', 'preclose', 'reentry'].map(name => [name, {
      state: 'pending', reason_codes: ['evaluation_proof_invalid'],
    }]),
  );
  const state = v2ProvisionalState({
    lane: null, selector_id: null, selection_status: 'pending',
    family_states: pendingFamilies, family_count: 0,
    reason_codes: ['evaluation_proof_invalid'],
  });
  const proof = v2Proof(state);
  proof.candidate.official_binding_key = null;
  proof.bindings = {};
  proof.freshness = {};
  proof.normalized_inputs = {
    side: state.side, pitcher: state.normalized_pitcher, game_time: state.game_time,
    k_line: state.model_k_line, odds: state.official_odds,
    official_book: state.official_book, official_verdict: state.official_verdict,
  };
  proof.decision = {
    support: 'pending', drag_core: 'pending', no_drag: 'pending',
    family_states: pendingFamilies,
    consensus_core: 'pending', reentry_expansion: 'pending', selected_lane: null,
    selection_status: 'pending', family_count: 0, maximum_family_count: 4,
    decisive_families: [], preclose_required_for_selected_lane: false,
    reason_codes: ['evaluation_proof_invalid'],
  };
  proof.preclose.reason_codes = ['evaluation_proof_invalid'];
  state.evaluation_proof = proof;
  configure();
  const fake = installFetch({ stateRows: [state] });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.equal(response.json.rows.length, 1);
    assert.equal(response.json.rows[0].selection_status, 'pending');
    assert.deepEqual(response.json.rows[0].decision_proof.lane_states, {
      consensus_core: 'pending', reentry_expansion: 'pending',
    });
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks keeps old client to new endpoint on the v1 contract', async () => {
  configure();
  const state = provisionalState();
  const fake = installFetch({ stateRows: [state] });
  try {
    const response = await responseJson(event());
    assert.equal(response.json.bundle_id, V1_BUNDLE_ID);
    assert.equal(response.json.selector_fingerprint, MANIFEST_FINGERPRINT);
    assert.equal(response.json.rows.length, 1);
    assert.equal(Object.hasOwn(response.json.rows[0], 'decision_proof'), false);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks preserves the serialized v1 row key order and reason position', async () => {
  configure();
  const state = provisionalState();
  const fake = installFetch({ stateRows: [state] });
  try {
    const response = await responseJson(event());
    const publicRow = response.json.rows[0];
    assert.equal(
      JSON.stringify(Object.keys(publicRow)),
      JSON.stringify(V1_ROW_KEY_ORDER),
    );
    assert.match(
      JSON.stringify(publicRow),
      /"checkpoint":"provisional","reason_codes":\["selected"\],"source_artifact_generated_at":/,
    );
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks rejects complete workload proofs whose raw values contradict derived buckets', async t => {
  const cases = [
    ['opener', { is_opener: true }],
    ['pitch count', { last_pitch_count: 105 }],
    ['short opportunity', { opportunity_bucket: 'short_leash' }],
    ['orphan opener archetype', { pitcher_archetype_bucket: 'opener_or_mismatch' }],
    ['orphan short-leash archetype', { pitcher_archetype_bucket: 'short_leash' }],
  ];
  for (const [name, updates] of cases) {
    await t.test(name, async () => {
      const state = v2FreshProvisionalState();
      Object.assign(state.evaluation_proof.normalized_inputs, updates);
      configure();
      const fake = installFetch({ stateRows: [state] });
      try {
        const response = await responseJson(event({ bundle_version: 'v2' }));
        assert.deepEqual(response.json.rows, []);
      } finally { fake.restore(); restoreEnv(); }
    });
  }
});

test('alternative-picks rejects extra normalized keys and whitespace with Python parity', async t => {
  const cases = [
    ['extra key', inputs => { inputs.unexpected_normalized_input = 'hidden'; }],
    ['padded text', inputs => { inputs.side = ' over '; }],
    ['padded anchor label', inputs => { inputs.anchor_labels = [' market_anchor_strict ']; }],
  ];
  for (const [name, mutate] of cases) {
    await t.test(name, async () => {
      const state = v2FreshProvisionalState();
      mutate(state.evaluation_proof.normalized_inputs);
      configure();
      const fake = installFetch({ stateRows: [state] });
      try {
        const response = await responseJson(event({ bundle_version: 'v2' }));
        assert.deepEqual(response.json.rows, []);
      } finally { fake.restore(); restoreEnv(); }
    });
  }
});

test('alternative-picks accepts complete workload proofs when raw values and derived buckets agree', async t => {
  const cases = [
    ['opener', {
      is_opener: true,
      leash_risk_bucket: 'high',
      pitcher_archetype_bucket: 'opener_or_mismatch',
    }],
    ['starter mismatch', {
      starter_mismatch: true,
      leash_risk_bucket: 'high',
      pitcher_archetype_bucket: 'opener_or_mismatch',
    }],
    ['pitch count', {
      last_pitch_count: 105,
      leash_risk_bucket: 'medium',
    }],
    ['short rest', {
      days_since_last_start: 3,
      leash_risk_bucket: 'medium',
    }],
    ['zero rest', {
      days_since_last_start: 0,
      leash_risk_bucket: 'medium',
    }],
    ['short opportunity', {
      opportunity_bucket: 'short_leash',
      leash_risk_bucket: 'high',
      pitcher_archetype_bucket: 'short_leash',
    }],
  ];
  for (const [name, updates] of cases) {
    await t.test(name, async () => {
      const state = v2FreshProvisionalState();
      Object.assign(state.evaluation_proof.normalized_inputs, updates);
      configure();
      const fake = installFetch({ stateRows: [state] });
      try {
        const response = await responseJson(event({ bundle_version: 'v2' }));
        assert.equal(response.json.rows.length, 1);
      } finally { fake.restore(); restoreEnv(); }
    });
  }
});

test('alternative-picks v2 prefers one valid frozen row over the same provisional candidate', async () => {
  const provisional = v2FreshProvisionalState();
  const frozen = v2FreshProvisionalState({
    checkpoint: 'frozen_pregame',
    frozen_at: '2026-07-21T20:00:00Z',
    lock_dedupe_key: '2026-07-21:test pitcher:over',
    lock_artifact_sha256: LOCK_SHA,
    lock_source_artifact_path: LOCK_URL,
    locked_at: '2026-07-21T20:00:00Z',
    should_lock_at: '2026-07-21T20:00:00Z',
    minutes_until_start: 60,
    lock_status: 'due_now',
  });
  configure();
  const fake = installFetch({
    stateRows: [provisional, frozen],
    lockRows: [matchingLock(frozen)],
  });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.equal(response.json.rows.length, 1);
    assert.equal(response.json.rows[0].checkpoint, 'frozen_pregame');
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks v2 does not let an invalid frozen row suppress a valid provisional row', async () => {
  const provisional = v2FreshProvisionalState();
  const invalidFrozen = v2FreshProvisionalState({
    checkpoint: 'frozen_pregame',
    frozen_at: '2026-07-21T20:00:00Z',
    lock_dedupe_key: '2026-07-21:test pitcher:over',
    lock_artifact_sha256: LOCK_SHA,
    lock_source_artifact_path: LOCK_URL,
    locked_at: '2026-07-21T20:00:00Z',
    should_lock_at: '2026-07-21T20:00:00Z',
    minutes_until_start: 60,
    lock_status: 'due_now',
    evaluation_proof: null,
  });
  configure();
  const fake = installFetch({
    stateRows: [invalidFrozen, provisional],
    lockRows: [matchingLock(invalidFrozen)],
  });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.equal(response.json.rows.length, 1);
    assert.equal(response.json.rows[0].checkpoint, 'provisional');
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks v2 suppresses same-priority conflicting public rows for one candidate', async () => {
  const first = v2FreshProvisionalState();
  const conflicting = v2FreshProvisionalState({ pitcher: 'Conflicting Display Name' });
  configure();
  const fake = installFetch({ stateRows: [first, conflicting] });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.deepEqual(response.json.rows, []);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks v2 rejects PASS even when the proof and row agree', async () => {
  const familyStates = {
    base: { state: 'disagree', reason_codes: ['base_predicate_false'] },
    anchor: { state: 'agree', reason_codes: ['market_anchor_v2_confirmed'] },
    preclose: { state: 'disagree', reason_codes: ['preclose_not_supported'] },
    reentry: { state: 'disagree', reason_codes: ['reentry_predicate_false'] },
  };
  const state = v2FreshProvisionalState({
    official_verdict: 'PASS',
    lane: null,
    selector_id: null,
    selection_status: 'not_selected',
    family_states: familyStates,
    family_count: 1,
  });
  state.evaluation_proof.decision = {
    ...state.evaluation_proof.decision,
    support: 'true',
    drag_core: 'false',
    no_drag: 'true',
    family_states: familyStates,
    consensus_core: 'false',
    reentry_expansion: 'false',
    selected_lane: null,
    selection_status: 'not_selected',
    family_count: 1,
    maximum_family_count: 1,
    decisive_families: ['anchor'],
    preclose_required_for_selected_lane: false,
  };
  configure();
  const fake = installFetch({ stateRows: [state] });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.deepEqual(response.json.rows, []);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks v1 preserves PASS and does not coalesce checkpoints', async () => {
  const provisional = provisionalState({ official_verdict: 'PASS' });
  const frozen = frozenState({ official_verdict: 'PASS' });
  configure();
  const fake = installFetch({
    stateRows: [provisional, frozen],
    lockRows: [matchingLock(frozen)],
  });
  try {
    const response = await responseJson(event());
    assert.equal(response.json.bundle_id, V1_BUNDLE_ID);
    assert.equal(response.json.rows.length, 2);
    assert.deepEqual(response.json.rows.map(row => row.official_verdict), ['PASS', 'PASS']);
  } finally { fake.restore(); restoreEnv(); }
});

test('alternative-picks v2 omits raw top-level reasons but retains sanitized decision evidence', async () => {
  const state = v2FreshProvisionalState({
    reason_codes: ['internal_database_probe'],
  });
  configure();
  const fake = installFetch({ stateRows: [state] });
  try {
    const response = await responseJson(event({ bundle_version: 'v2' }));
    assert.equal(response.json.rows.length, 1);
    const [publicRow] = response.json.rows;
    assert.equal(Object.hasOwn(publicRow, 'reason_codes'), false);
    assert.deepEqual(publicRow.family_states, state.family_states);
    assert.equal(publicRow.decision_proof.lane_states.consensus_core, 'true');
    assert.equal(JSON.stringify(response.json).includes('internal_database_probe'), false);
  } finally { fake.restore(); restoreEnv(); }
});
