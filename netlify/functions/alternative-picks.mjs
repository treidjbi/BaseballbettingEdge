const CONTRACTS = Object.freeze({
  v1: Object.freeze({
    bundleId: 'pregame_alternative_pick_methodology_v1',
    selectorFingerprint: 'f8f7ccf652b8eda4860d07798bc4673920b0b9d727552bc7e2e6547d478b4579',
    selectorIds: Object.freeze({
      consensus_core: 'no_drag_distinct_family_consensus_core_v1',
      reentry_expansion: 'moderate_edge_quality_reentry_expansion_v1',
    }),
    requiresProof: false,
  }),
  v2: Object.freeze({
    bundleId: 'pregame_alternative_pick_methodology_v2',
    selectorFingerprint: '23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4',
    selectorIds: Object.freeze({
      consensus_core: 'no_drag_distinct_family_consensus_core_v2',
      reentry_expansion: 'moderate_edge_quality_reentry_expansion_v2',
    }),
    requiresProof: true,
  }),
});
const CANONICAL_ARTIFACT_KEY = 'today';
const CANONICAL_ARTIFACT_PATH = 'dashboard/data/processed/today.json';
const APPROVED_POSTURES = new Set(['therundown', 'therundown_propline']);
const APPROVED_PUBLICATION_SOURCES = new Set([
  'github_actions', 'render_pipeline', 'render_live_layer', 'manual_backfill',
]);
const LANES = new Set(['consensus_core', 'reentry_expansion']);
const FAMILY_ORDER = Object.freeze(['base', 'anchor', 'preclose', 'reentry']);
const SELECTION_STATUSES = new Set(['selected', 'not_selected', 'pending']);
const CHECKPOINTS = new Set(['provisional', 'frozen_pregame']);
const FAMILY_STATES = new Set(['agree', 'disagree', 'pending']);
const FAMILY_KEYS = new Set(['base', 'anchor', 'preclose', 'reentry']);
const SUPPORTED_PROVIDERS = new Set(['therundown', 'propline']);
const NORMALIZED_INPUT_FIELDS = new Set([
  'side', 'official_verdict', 'source_fire_verdict', 'pitcher', 'game_time',
  'k_line', 'line_bucket', 'odds', 'official_book', 'price_sign',
  'bet_timing_window', 'model_market_relationship', 'model_no_vig_gap', 'edge',
  'adjusted_ev', 'adjusted_ev_error', 'quality_gate_level', 'opportunity_bucket',
  'leash_risk_bucket', 'pitcher_archetype_bucket', 'large_edge_skepticism_flag',
  'is_opener', 'starter_mismatch', 'last_pitch_count', 'days_since_last_start',
  'workload_input_status', 'anchor_labels', 'anchor_metadata_malformed', 'observed_at',
]);
const NORMALIZED_TEXT_FIELDS = new Set([
  'side', 'official_verdict', 'source_fire_verdict', 'pitcher', 'game_time',
  'line_bucket', 'official_book', 'price_sign', 'bet_timing_window',
  'model_market_relationship', 'adjusted_ev_error', 'quality_gate_level',
  'opportunity_bucket', 'leash_risk_bucket', 'pitcher_archetype_bucket',
  'workload_input_status', 'observed_at',
]);
const NORMALIZED_NUMBER_FIELDS = new Set([
  'k_line', 'model_no_vig_gap', 'edge', 'adjusted_ev',
]);
const NORMALIZED_INTEGER_FIELDS = new Set(['odds']);
const NORMALIZED_BOOLEAN_FIELDS = new Set([
  'large_edge_skepticism_flag', 'anchor_metadata_malformed',
]);
const NORMALIZED_NULLABLE_BOOLEAN_FIELDS = new Set(['is_opener', 'starter_mismatch']);
const NORMALIZED_NULLABLE_INTEGER_FIELDS = new Set(['last_pitch_count', 'days_since_last_start']);
const ROW_BINDING_INPUT_FIELDS = new Set([
  'side', 'pitcher', 'game_time', 'k_line', 'odds', 'official_book', 'official_verdict',
]);
const PROOF_THRESHOLDS = Object.freeze({
  edgeHigh: 0.06, edgeLow: 0.02, edgeModerateLow: 0.04, edgeModerate: 0.06,
  evLow: 0.06, evModerate: 0.17, noVigBase: 0.02, noVigReentry: 0.04,
  precloseStrong: 5, precloseMedium: 3,
});
const PROOF_WEIGHTS = Object.freeze({
  movementToward: 3, movementAway: -2, edgeLow: 3, edgeModerateLow: 2,
  edgeModerate: 1, edgeHigh: -2, evLow: 2, evModerate: 1, evHigh: -1,
  thinNoVig: 1, highNoVig: -1, minusPrice: 1, plusPrice: -1,
  cleanQuality: 1, blockedQuality: -2, earlyTiming: 1, lateTiming: -1,
  multiBook: 1, singleBook: -1, offMarket: -2, volatile: -2,
  lowVolatility: 1, underMarketFade: -1,
});
const LOCK_STATUSES = new Set(['due_now', 'missed_lock']);
const EVIDENCE_FRESHNESS = new Set(['fresh', 'pending']);
const OFFICIAL_VERDICTS = new Set(['PASS', 'LEAN', 'FIRE 1u', 'FIRE 2u']);
const V2_OFFICIAL_VERDICTS = new Set(['LEAN', 'FIRE 1u', 'FIRE 2u']);
const SUPPORTED_BOOKS = new Set(['fanduel', 'draftkings', 'betmgm', 'betrivers', 'kalshi', 'caesars', 'thescore']);
const MLB_TEAM_CODES = new Map([
  ['arizona diamondbacks', 'ARI'], ['athletics', 'OAK'], ['oakland athletics', 'OAK'],
  ['atlanta braves', 'ATL'], ['baltimore orioles', 'BAL'], ['boston red sox', 'BOS'],
  ['chicago cubs', 'CHC'], ['chicago white sox', 'CWS'], ['cincinnati reds', 'CIN'],
  ['cleveland guardians', 'CLE'], ['colorado rockies', 'COL'], ['detroit tigers', 'DET'],
  ['houston astros', 'HOU'], ['kansas city royals', 'KC'], ['los angeles angels', 'LAA'],
  ['los angeles dodgers', 'LAD'], ['miami marlins', 'MIA'], ['milwaukee brewers', 'MIL'],
  ['minnesota twins', 'MIN'], ['new york mets', 'NYM'], ['new york yankees', 'NYY'],
  ['philadelphia phillies', 'PHI'], ['pittsburgh pirates', 'PIT'], ['san diego padres', 'SD'],
  ['san francisco giants', 'SF'], ['seattle mariners', 'SEA'], ['st. louis cardinals', 'STL'],
  ['tampa bay rays', 'TB'], ['texas rangers', 'TEX'], ['toronto blue jays', 'TOR'],
  ['washington nationals', 'WSH'],
]);

const CANONICAL_SELECT = [
  'artifact_key', 'payload_sha256', 'slate_date', 'generated_at', 'source',
  'payload_date:payload->>date',
  'payload_odds_source:payload->>odds_source',
  'payload_provider_posture:payload->>provider_posture',
  'payload_pitchers:payload->pitchers',
  'artifact_path:metadata->>artifact_path',
].join(',');

const STATE_SELECT = [
  'slate_date', 'candidate_identity', 'pitcher', 'normalized_pitcher', 'team', 'opp_team', 'game_time', 'side',
  'model_k_line', 'bundle_id', 'selector_id', 'checkpoint', 'official_odds', 'official_book',
  'official_verdict', 'lane', 'selector_fingerprint', 'selection_status', 'family_states', 'family_count', 'reason_codes',
  'source_artifact_path', 'source_artifact_generated_at', 'source_artifact_sha256',
  'source_artifact_byte_sha256', 'evidence_observation_ids', 'evidence_observation_count', 'evidence_first_observed_at',
  'evidence_last_observed_at', 'evidence_freshness_status', 'frozen_at', 'lock_dedupe_key',
  'lock_artifact_sha256', 'lock_source_artifact_path', 'locked_at', 'should_lock_at',
  'minutes_until_start', 'lock_status', 'evaluation_proof',
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

function emptyPayload(slateDate, error = null, status = 'ready', contract = CONTRACTS.v1) {
  return {
    slate_date: slateDate,
    generated_at: null,
    status,
    bundle_id: contract?.bundleId ?? null,
    selector_fingerprint: contract?.selectorFingerprint ?? null,
    counts: { provisional: 0, frozen: 0, selected: 0, pending: 0 },
    rows: [],
    error,
  };
}

function requestedContract(event) {
  const value = event.queryStringParameters?.bundle_version;
  if (value == null || value === '' || (typeof value === 'string' && value.trim() === '')) return CONTRACTS.v1;
  if (value === 'v1') return CONTRACTS.v1;
  if (value === 'v2') return CONTRACTS.v2;
  return null;
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

function safeText(value, maximum = 120) {
  const output = text(value);
  if (!output || output.length > maximum || /(?:https?:\/\/|www\.|bearer|authorization|password|secret|token|api[_-]?key)/i.test(output)) return '';
  return /^[\p{L}\p{N} .,'’&()/_-]+$/u.test(output) ? output : '';
}

function safeTeam(value) {
  const team = text(value);
  const code = team.toUpperCase();
  if (/^[A-Z]{2,4}$/.test(code)) return code;
  return MLB_TEAM_CODES.get(team.toLowerCase()) || '';
}

function supportedBook(value) {
  const compact = text(value).toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, '');
  const aliases = {
    fanduelsportsbook: 'fanduel', draftkingssportsbook: 'draftkings', betmgmsportsbook: 'betmgm',
    betriverssportsbook: 'betrivers', caesarssportsbook: 'caesars', thescorebet: 'thescore',
    thescoresportsbook: 'thescore', scorebet: 'thescore',
  };
  const book = aliases[compact] || compact;
  return SUPPORTED_BOOKS.has(book) ? book : '';
}

function validHash(value) {
  const hash = text(value).toLowerCase();
  return /^[a-f0-9]{64}$/.test(hash) ? hash : '';
}

function number(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
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

function safeReasonCodes(value, maximum = 24) {
  if (!Array.isArray(value) || value.length > maximum) return null;
  const reasons = value.map(item => text(item));
  return reasons.every(reason => /^[a-z][a-z0-9_]{0,79}$/.test(reason)) ? reasons : null;
}

function safeFamilyStates(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const result = {};
  for (const [name, vote] of Object.entries(value)) {
    const key = text(name);
    const state = text(vote?.state).toLowerCase();
    const reasons = safeReasonCodes(vote?.reason_codes, 12);
    if (!FAMILY_KEYS.has(key) || !FAMILY_STATES.has(state) || reasons == null) return null;
    result[key] = { state, reason_codes: reasons };
  }
  return result;
}

function sameFamilyStates(left, right) {
  const leftStates = safeFamilyStates(left);
  const rightStates = safeFamilyStates(right);
  if (!leftStates || !rightStates) return false;
  if (Object.keys(leftStates).length !== FAMILY_KEYS.size || Object.keys(rightStates).length !== FAMILY_KEYS.size) return false;
  return [...FAMILY_KEYS].every(name => {
    const leftVote = leftStates[name];
    const rightVote = rightStates[name];
    return leftVote && rightVote && leftVote.state === rightVote.state
      && leftVote.reason_codes.length === rightVote.reason_codes.length
      && leftVote.reason_codes.every((reason, index) => reason === rightVote.reason_codes[index]);
  });
}

function plainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function triValue(value) {
  return value === 'true' ? true : value === 'false' ? false : value === 'pending' ? null : undefined;
}

function triName(value) {
  return value === true ? 'true' : value === false ? 'false' : 'pending';
}

function triNot(value) {
  return value == null ? null : !value;
}

function triAnd(...values) {
  if (values.some(value => value === false)) return false;
  return values.every(value => value === true) ? true : null;
}

function triOr(...values) {
  if (values.some(value => value === true)) return true;
  return values.every(value => value === false) ? false : null;
}

function equalStringArray(left, right) {
  return Array.isArray(left) && Array.isArray(right)
    && left.length === right.length
    && left.every((value, index) => typeof value === 'string' && value === right[index]);
}

function nullableTimestampMatches(left, right) {
  if (left == null && right == null) return true;
  return sameTimestamp(left, right);
}

function sameKeys(value, expected) {
  return plainObject(value)
    && Object.keys(value).sort().join('|') === [...expected].sort().join('|');
}

function proofText(value, maximum = 256) {
  const output = text(value);
  return output && Buffer.byteLength(output, 'utf8') <= maximum ? output : '';
}

function proofReasonList(value) {
  return Array.isArray(value) && value.length <= 16
    && value.every(reason => proofText(reason, 128));
}

function proofStringList(value, maximum = 32, itemBytes = 256) {
  if (!Array.isArray(value) || value.length > maximum) return false;
  const normalized = value.map(item => proofText(item, itemBytes));
  return normalized.every(Boolean) && new Set(normalized).size === normalized.length;
}

function finiteJson(value, seen = new Set()) {
  if (value == null || typeof value === 'string' || typeof value === 'boolean') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (typeof value !== 'object' || seen.has(value)) return false;
  seen.add(value);
  const valid = Array.isArray(value)
    ? value.every(item => finiteJson(item, seen))
    : Object.entries(value).every(([key, item]) => typeof key === 'string' && finiteJson(item, seen));
  seen.delete(value);
  return valid;
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (plainObject(value)) return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}

function jsonEqual(left, right) {
  return stableJson(left) === stableJson(right);
}

function boundedNormalizedInputs(value) {
  if (!sameKeys(value, NORMALIZED_INPUT_FIELDS)) return null;
  const output = { ...value };
  for (const [field, item] of Object.entries(output)) {
    if (field === 'anchor_labels') {
      if (item !== null && !proofStringList(item, 16, 128)) return null;
    } else if (NORMALIZED_TEXT_FIELDS.has(field)) {
      if (item !== null && (typeof item !== 'string' || !proofText(item))) return null;
    } else if (NORMALIZED_NUMBER_FIELDS.has(field)) {
      if (item !== null && (typeof item !== 'number' || !Number.isFinite(item))) return null;
    } else if (NORMALIZED_INTEGER_FIELDS.has(field)) {
      if (item !== null && (typeof item !== 'number' || !Number.isInteger(item))) return null;
    } else if (NORMALIZED_BOOLEAN_FIELDS.has(field)) {
      if (typeof item !== 'boolean') return null;
    } else if (NORMALIZED_NULLABLE_BOOLEAN_FIELDS.has(field)) {
      if (item !== null && typeof item !== 'boolean') return null;
    } else if (NORMALIZED_NULLABLE_INTEGER_FIELDS.has(field)) {
      if (item !== null && (typeof item !== 'number' || !Number.isInteger(item))) return null;
    } else return null;
  }
  const workloadValues = [
    output.is_opener, output.starter_mismatch,
    output.last_pitch_count, output.days_since_last_start,
  ];
  if (!['complete', 'missing', 'malformed'].includes(output.workload_input_status)) return null;
  if (output.workload_input_status === 'complete'
      && (typeof output.is_opener !== 'boolean'
        || typeof output.starter_mismatch !== 'boolean'
        || !Number.isInteger(output.last_pitch_count) || output.last_pitch_count < 0
        || !Number.isInteger(output.days_since_last_start) || output.days_since_last_start < 0)) return null;
  if (output.workload_input_status !== 'complete'
      && !workloadValues.some(item => item === null)
      && ![output.last_pitch_count, output.days_since_last_start].some(item => Number.isInteger(item) && item < 0)) return null;
  return output;
}

function familyVote(state, reasonCodes) {
  return { state, reason_codes: reasonCodes };
}

function familyTri(vote) {
  return vote.state === 'agree' ? true : vote.state === 'disagree' ? false : null;
}

function composeVote(value, trueReason, falseReason, pendingReason) {
  return value === true ? familyVote('agree', [trueReason])
    : value === false ? familyVote('disagree', [falseReason])
      : familyVote('pending', [pendingReason]);
}

function missingProofInput(value) {
  return value == null || value === '' || value === 'unknown';
}

function strongBaseVote(inputs) {
  const required = [
    'official_verdict', 'side', 'adjusted_ev', 'model_market_relationship', 'line_bucket',
    'leash_risk_bucket', 'pitcher_archetype_bucket', 'model_no_vig_gap',
    'quality_gate_level', 'bet_timing_window',
  ];
  if (inputs.adjusted_ev_error || required.some(field => missingProofInput(inputs[field]))) {
    return familyVote('pending', [inputs.adjusted_ev_error || 'base_inputs_missing']);
  }
  const verdict = inputs.official_verdict.toUpperCase();
  const fire = verdict.startsWith('FIRE');
  const lean = verdict === 'LEAN';
  const moderateEv = inputs.adjusted_ev >= PROOF_THRESHOLDS.evLow
    && inputs.adjusted_ev < PROOF_THRESHOLDS.evModerate;
  const strict = fire && ((inputs.model_market_relationship === 'model_agrees_with_favorite'
      && moderateEv && inputs.bet_timing_window === 'pre_30')
    || (inputs.side === 'over' && moderateEv && inputs.leash_risk_bucket === 'normal'));
  const selective = lean && ((inputs.line_bucket === '4.5'
      && inputs.adjusted_ev >= 0 && inputs.adjusted_ev < PROOF_THRESHOLDS.evLow
      && inputs.leash_risk_bucket === 'normal')
    || (inputs.pitcher_archetype_bucket === 'low_k_standard'
      && inputs.model_no_vig_gap >= PROOF_THRESHOLDS.noVigBase)
    || (inputs.line_bucket === '2.5-3.5'
      && inputs.model_market_relationship === 'model_fades_favorite'
      && inputs.quality_gate_level === 'capped'));
  return familyVote(strict || selective ? 'agree' : 'disagree', [
    strict ? 'strong_base_strict_runtime_core'
      : selective ? 'strong_base_selective_lean' : 'base_predicate_false',
  ]);
}

function anchorVotes(inputs, base) {
  let strict;
  let core;
  if (Array.isArray(inputs.anchor_labels) && inputs.anchor_metadata_malformed !== true) {
    const labels = new Set(inputs.anchor_labels.map(label => text(label).toLowerCase()));
    strict = familyVote(labels.has('market_anchor_strict') ? 'agree' : 'disagree', [
      labels.has('market_anchor_strict') ? 'market_anchor_strict' : 'market_anchor_strict_absent',
    ]);
    core = familyVote(labels.has('market_anchor_core') ? 'agree' : 'disagree', [
      labels.has('market_anchor_core') ? 'market_anchor_core' : 'market_anchor_core_absent',
    ]);
  } else {
    const reason = inputs.anchor_metadata_malformed === true ? 'anchor_metadata_malformed' : 'anchor_metadata_absent';
    strict = familyVote('pending', [reason]);
    core = familyVote('pending', [reason]);
  }
  const anchor = composeVote(
    triOr(familyTri(strict), triAnd(familyTri(base), familyTri(core))),
    'market_anchor_v2_confirmed', 'market_anchor_not_matched', 'anchor_dependency_pending',
  );
  return { strict, anchor };
}

function moderateReentryVote(inputs) {
  const required = [
    'source_fire_verdict', 'side', 'model_market_relationship', 'quality_gate_level',
    'edge', 'adjusted_ev', 'model_no_vig_gap', 'large_edge_skepticism_flag',
  ];
  if (inputs.adjusted_ev_error || required.some(field => missingProofInput(inputs[field]))
      || inputs.model_market_relationship === 'unknown') {
    return familyVote('pending', [inputs.adjusted_ev_error || 'reentry_inputs_missing']);
  }
  if (!inputs.source_fire_verdict.toUpperCase().startsWith('FIRE')) return familyVote('disagree', ['source_not_fire']);
  const agrees = inputs.edge >= PROOF_THRESHOLDS.edgeLow
    && inputs.edge < PROOF_THRESHOLDS.edgeModerate
    && inputs.adjusted_ev < PROOF_THRESHOLDS.evModerate
    && inputs.model_no_vig_gap >= PROOF_THRESHOLDS.noVigReentry
    && ['', 'clean', 'none'].includes(inputs.quality_gate_level)
    && !inputs.large_edge_skepticism_flag;
  return familyVote(agrees ? 'agree' : 'disagree', [agrees ? 'moderate_edge_quality_reentry' : 'reentry_predicate_false']);
}

function precloseScore(inputs, preclose) {
  let score = 0;
  const positiveReasons = [];
  const riskReasons = [];
  const add = (points, reason, target) => { score += points; target.push(reason); };
  if (preclose.side_price_movement === 'with_side'
      || preclose.toward_pick_count > preclose.away_from_pick_count) {
    add(PROOF_WEIGHTS.movementToward, 'movement_toward_pick', positiveReasons);
  }
  if (preclose.side_price_movement === 'against_side'
      || preclose.away_from_pick_count > preclose.toward_pick_count) {
    add(PROOF_WEIGHTS.movementAway, 'movement_against_pick', riskReasons);
  }
  if (inputs.edge < PROOF_THRESHOLDS.edgeLow) add(PROOF_WEIGHTS.edgeLow, 'low_edge_market_validation', positiveReasons);
  else if (inputs.edge < PROOF_THRESHOLDS.edgeModerateLow) add(PROOF_WEIGHTS.edgeModerateLow, 'moderate_low_edge_market_validation', positiveReasons);
  else if (inputs.edge < PROOF_THRESHOLDS.edgeModerate) add(PROOF_WEIGHTS.edgeModerate, 'moderate_edge_market_validation', positiveReasons);
  else add(PROOF_WEIGHTS.edgeHigh, 'high_edge_clv_risk', riskReasons);
  if (inputs.model_no_vig_gap > 0 && inputs.model_no_vig_gap < PROOF_THRESHOLDS.noVigReentry) {
    add(PROOF_WEIGHTS.thinNoVig, 'thin_or_price_only_no_vig_gap', positiveReasons);
  } else if (inputs.model_no_vig_gap >= PROOF_THRESHOLDS.noVigReentry) {
    add(PROOF_WEIGHTS.highNoVig, 'model_edge_not_clv_proxy', riskReasons);
  }
  if (inputs.price_sign === 'minus') add(PROOF_WEIGHTS.minusPrice, 'minus_price_market_support', positiveReasons);
  else if (inputs.price_sign === 'plus') add(PROOF_WEIGHTS.plusPrice, 'plus_price_clv_risk', riskReasons);
  if (['', 'clean', 'none'].includes(inputs.quality_gate_level)) add(PROOF_WEIGHTS.cleanQuality, 'clean_quality', positiveReasons);
  else if (['blocked', 'severe'].includes(inputs.quality_gate_level)) add(PROOF_WEIGHTS.blockedQuality, 'blocked_quality', riskReasons);
  if (['pre_120', 'pre_60', 'pre_30'].includes(inputs.bet_timing_window)) add(PROOF_WEIGHTS.earlyTiming, 'early_lock_window', positiveReasons);
  else if (['pre_5', 'post_start'].includes(inputs.bet_timing_window)) add(PROOF_WEIGHTS.lateTiming, 'late_timing', riskReasons);
  if (preclose.broad_confirmation || preclose.book_count >= 3) add(PROOF_WEIGHTS.multiBook, 'multi_book_support', positiveReasons);
  else if (preclose.book_count === 1) add(PROOF_WEIGHTS.singleBook, 'single_book_support', riskReasons);
  if (preclose.best_is_off_market) add(PROOF_WEIGHTS.offMarket, 'off_market_best_book', riskReasons);
  if (preclose.reversal_book_count > 0 || preclose.volatile_book_count > 1) add(PROOF_WEIGHTS.volatile, 'reversal_or_volatility', riskReasons);
  else if (preclose.reversal_book_count === 0 && preclose.volatile_book_count === 0) add(PROOF_WEIGHTS.lowVolatility, 'low_volatility', positiveReasons);
  if (inputs.side === 'under' && inputs.model_market_relationship === 'model_fades_favorite') {
    add(PROOF_WEIGHTS.underMarketFade, 'under_market_fade', riskReasons);
  }
  if (inputs.adjusted_ev < PROOF_THRESHOLDS.evLow) add(PROOF_WEIGHTS.evLow, 'low_ev_market_validation', positiveReasons);
  else if (inputs.adjusted_ev < PROOF_THRESHOLDS.evModerate) add(PROOF_WEIGHTS.evModerate, 'moderate_ev_market_validation', positiveReasons);
  else add(PROOF_WEIGHTS.evHigh, 'high_ev_clv_risk', riskReasons);
  return {
    score,
    label: score >= PROOF_THRESHOLDS.precloseStrong ? 'strong_preclose_clv_proxy'
      : score >= PROOF_THRESHOLDS.precloseMedium ? 'medium_preclose_clv_proxy' : 'weak_preclose_clv_proxy',
    positive_reasons: positiveReasons,
    risk_reasons: riskReasons,
  };
}

function recomputeDecision(inputs, preclose) {
  const workloadReason = `workload_inputs_${inputs.workload_input_status}`;
  const base = inputs.workload_input_status === 'complete'
    ? strongBaseVote(inputs) : familyVote('pending', [workloadReason]);
  const { strict, anchor } = anchorVotes(inputs, base);
  let scored = null;
  let rawPreclose;
  if (preclose.freshness_status === 'fresh') {
    scored = precloseScore(inputs, preclose);
    rawPreclose = familyVote(scored.label === 'strong_preclose_clv_proxy' ? 'agree' : 'disagree', [scored.label]);
  } else {
    rawPreclose = familyVote('pending', preclose.reason_codes.length ? [...preclose.reason_codes] : ['preclose_evidence_pending']);
  }
  const precloseValue = triAnd(familyTri(base), familyTri(rawPreclose));
  const precloseVote = precloseValue == null
    ? familyVote('pending', [...(rawPreclose.state === 'pending' ? rawPreclose.reason_codes : base.reason_codes)])
    : composeVote(precloseValue, 'preclose_v2_confirmed', 'preclose_not_supported', 'preclose_dependency_pending');
  const reentry = inputs.workload_input_status === 'complete'
    ? moderateReentryVote(inputs) : familyVote('pending', [workloadReason]);
  const families = { base, anchor, preclose: precloseVote, reentry };
  const support = triOr(familyTri(base), familyTri(strict));
  const highEdge = typeof inputs.edge === 'number' ? inputs.edge >= PROOF_THRESHOLDS.edgeHigh : null;
  const fade = inputs.model_market_relationship === 'model_fades_favorite' ? true
    : ['model_agrees_with_favorite', 'model_neutral'].includes(inputs.model_market_relationship) ? false : null;
  const verdict = text(inputs.source_fire_verdict || inputs.official_verdict);
  const fireUnderFade = triAnd(verdict ? verdict.toUpperCase().startsWith('FIRE') : null,
    ['over', 'under'].includes(inputs.side) ? inputs.side === 'under' : null, fade);
  const drag = triOr(highEdge, fade, fireUnderFade);
  const noDrag = triAnd(support, triNot(drag));
  const familyCount = FAMILY_ORDER.filter(name => families[name].state === 'agree').length;
  const maximumFamilyCount = FAMILY_ORDER.filter(name => families[name].state !== 'disagree').length;
  const countGate = familyCount >= 2 ? true : maximumFamilyCount < 2 ? false : null;
  const consensus = triAnd(noDrag, countGate);
  const expansion = triAnd(familyTri(reentry), triNot(noDrag));
  const selectedLane = consensus === true ? 'consensus_core' : expansion === true ? 'reentry_expansion' : null;
  const selectionStatus = selectedLane ? 'selected' : consensus === false && expansion === false ? 'not_selected' : 'pending';
  const decisiveFamilies = FAMILY_ORDER.filter(name => families[name].state === 'agree');
  const precloseRequired = selectedLane === 'consensus_core' && precloseVote.state === 'agree'
    && FAMILY_ORDER.filter(name => name !== 'preclose' && families[name].state === 'agree').length < 2;
  return {
    decision: {
      support: triName(support), drag_core: triName(drag), no_drag: triName(noDrag),
      family_states: families, consensus_core: triName(consensus), reentry_expansion: triName(expansion),
      selected_lane: selectedLane, selection_status: selectionStatus, family_count: familyCount,
      maximum_family_count: maximumFamilyCount, decisive_families: decisiveFamilies,
      preclose_required_for_selected_lane: precloseRequired,
    },
    score: scored,
  };
}

function providerTokenValid(token, bindings) {
  const value = proofText(token, 384);
  const separator = value.indexOf(':');
  if (separator <= 0 || separator === value.length - 1) return false;
  const provider = value.slice(0, separator);
  return SUPPORTED_PROVIDERS.has(provider) && Object.hasOwn(bindings, provider);
}

function providerContractValid(candidate, bindings, freshness, precloseStatus, diagnostic) {
  if (!plainObject(bindings) || !plainObject(freshness) || Object.keys(bindings).length > SUPPORTED_PROVIDERS.size) return false;
  if (diagnostic) return Object.keys(bindings).length === 0 && Object.keys(freshness).length === 0;
  const candidateProvider = text(candidate.line_source_provider).toLowerCase();
  const officialProviders = [];
  const matureProviders = [];
  for (const [provider, binding] of Object.entries(bindings)) {
    if (!SUPPORTED_PROVIDERS.has(provider) || !plainObject(binding)) return false;
    if (binding.role === 'official') officialProviders.push(provider);
    if (binding.mature === true) matureProviders.push(provider);
    const expectedRole = provider === candidateProvider ? 'official' : 'sidecar';
    if (binding.role !== expectedRole || !proofText(binding.provider_event_id)
        || !validHash(binding.binding_key) || !timestamp(binding.window_started_at)
        || typeof binding.mature !== 'boolean'
        || !proofStringList(binding.seed_observation_tokens, 32, 384)
        || binding.seed_observation_tokens.some(token => !proofText(token, 384).startsWith(`${provider}:`))
        || !proofStringList(binding.current_line_ids, 32, 384)) return false;
  }
  if (officialProviders.length !== 1 || officialProviders[0] !== candidateProvider
      || validHash(bindings[candidateProvider]?.binding_key) !== validHash(candidate.official_binding_key)) return false;
  if (Object.keys(freshness).sort().join('|') !== matureProviders.sort().join('|')) return false;
  for (const [provider, value] of Object.entries(freshness)) {
    if (!Object.hasOwn(bindings, provider) || !plainObject(value)
        || !['fresh', 'stale', 'pending'].includes(value.freshness_status)
        || !timestamp(value.latest_snapshot_at)) return false;
  }
  if (precloseStatus === 'fresh') {
    if (bindings[candidateProvider]?.mature !== true
        || freshness[candidateProvider]?.freshness_status !== 'fresh'
        || Object.values(freshness).some(value => value.freshness_status !== 'fresh')) return false;
  }
  return true;
}

function precloseContractValid(preclose, bindings) {
  const status = text(preclose.freshness_status).toLowerCase();
  const count = integer(preclose.qualifying_observation_count);
  if (!['fresh', 'pending'].includes(status) || count == null || count < 0
      || !Array.isArray(preclose.decisive_observation_tokens)
      || preclose.decisive_observation_tokens.length > 32
      || new Set(preclose.decisive_observation_tokens).size !== preclose.decisive_observation_tokens.length
      || preclose.decisive_observation_tokens.some(token => !providerTokenValid(token, bindings))
      || !validHash(preclose.full_ordered_token_sha256)
      || !proofStringList(preclose.direction_change_pivot_tokens, 32, 384)
      || !proofStringList(preclose.latest_ladder_observation_tokens, 32, 384)
      || [...preclose.direction_change_pivot_tokens, ...preclose.latest_ladder_observation_tokens]
        .some(token => !providerTokenValid(token, bindings) || !preclose.decisive_observation_tokens.includes(token))
      || !validHash(preclose.ladder_observation_token_sha256)
      || !proofStringList(preclose.books_seen, 32, 64)
      || !proofReasonList(preclose.positive_reasons)
      || !proofReasonList(preclose.risk_reasons)
      || !proofReasonList(preclose.reason_codes)) return false;
  if (count > 0 && (!timestamp(preclose.first_observed_at) || !timestamp(preclose.last_observed_at))) return false;
  const aggregateFields = [
    'book_count', 'toward_pick_count', 'away_from_pick_count', 'side_price_movement',
    'broad_confirmation', 'reversal_book_count', 'volatile_book_count',
    'best_is_off_market', 'score', 'label',
  ];
  if (status === 'pending') {
    return aggregateFields.every(field => preclose[field] === null)
      && preclose.reason_codes.length > 0
      && preclose.positive_reasons.length === 0 && preclose.risk_reasons.length === 0;
  }
  const integers = ['book_count', 'toward_pick_count', 'away_from_pick_count', 'reversal_book_count', 'volatile_book_count', 'score'];
  if (count < 2 || integers.some(field => integer(preclose[field]) == null || integer(preclose[field]) < 0)
      || typeof preclose.broad_confirmation !== 'boolean'
      || typeof preclose.best_is_off_market !== 'boolean'
      || !['with_side', 'against_side', 'neutral'].includes(preclose.side_price_movement)
      || preclose.reversal_book_count !== preclose.volatile_book_count
      || preclose.toward_pick_count + preclose.away_from_pick_count > preclose.book_count
      || preclose.books_seen.length !== preclose.book_count
      || !timestamp(preclose.first_observed_at) || !timestamp(preclose.last_observed_at)
      || new Date(preclose.first_observed_at) > new Date(preclose.last_observed_at)
      || !proofText(preclose.label) || preclose.reason_codes.length !== 0) return false;
  return true;
}

function validateV2Proof(row) {
  const proof = row.evaluation_proof;
  if (!plainObject(proof) || !finiteJson(proof)) return null;
  let serialized;
  try { serialized = JSON.stringify(proof); } catch { return null; }
  if (!serialized || Buffer.byteLength(serialized, 'utf8') > 30720) return null;
  const expectedRoot = [
    'schema_version', 'bundle_id', 'selector_fingerprint', 'candidate', 'artifact',
    'bindings', 'freshness', 'normalized_inputs', 'preclose', 'decision',
  ].sort();
  if (Object.keys(proof).sort().join('|') !== expectedRoot.join('|')) return null;
  if (proof.schema_version !== 'v2'
      || proof.bundle_id !== CONTRACTS.v2.bundleId
      || proof.selector_fingerprint !== CONTRACTS.v2.selectorFingerprint) return null;

  const candidate = proof.candidate;
  const artifact = proof.artifact;
  const normalized = proof.normalized_inputs;
  const preclose = proof.preclose;
  const decision = proof.decision;
  if (![candidate, artifact, proof.bindings, proof.freshness, normalized, preclose, decision].every(plainObject)) return null;
  const diagnosticReasons = decision.reason_codes;
  const isDiagnostic = decision.selection_status === 'pending' && decision.selected_lane === null
    && Array.isArray(diagnosticReasons) && diagnosticReasons.length === 1
    && ['evaluation_proof_invalid', 'evaluation_proof_oversized'].includes(diagnosticReasons[0]);
  if (!validHash(row.candidate_identity)
      || text(candidate.candidate_identity) !== text(row.candidate_identity)
      || !validHash(candidate.candidate_identity)
      || validDate(candidate.slate_date) !== row.slate_date
      || text(candidate.normalized_pitcher) !== text(row.normalized_pitcher)
      || !proofText(candidate.normalized_pitcher, 128)
      || text(candidate.side).toLowerCase() !== text(row.side).toLowerCase()
      || number(candidate.model_k_line) !== number(row.model_k_line)
      || !sameTimestamp(candidate.game_time, row.game_time)
      || !SUPPORTED_PROVIDERS.has(text(candidate.line_source_provider).toLowerCase())
      || (isDiagnostic ? candidate.official_binding_key !== null : !validHash(candidate.official_binding_key))) return null;
  if (artifact.source_artifact_path !== CANONICAL_ARTIFACT_PATH
      || text(artifact.source_artifact_path) !== text(row.source_artifact_path)
      || !sameTimestamp(artifact.source_artifact_generated_at, row.source_artifact_generated_at)
      || validHash(artifact.source_artifact_sha256) !== validHash(row.source_artifact_sha256)
      || validHash(artifact.source_artifact_byte_sha256) !== validHash(row.source_artifact_byte_sha256)) return null;

  const normalizedInputs = isDiagnostic
    ? (sameKeys(normalized, ROW_BINDING_INPUT_FIELDS) ? normalized : null)
    : boundedNormalizedInputs(normalized);
  if (!normalizedInputs
      || text(normalizedInputs.pitcher).toLowerCase() !== text(row.normalized_pitcher).toLowerCase()
      || text(normalized.side).toLowerCase() !== text(row.side).toLowerCase()
      || !sameTimestamp(normalized.game_time, row.game_time)
      || number(normalized.k_line) !== number(row.model_k_line)
      || integer(normalized.odds) !== integer(row.official_odds)
      || text(normalized.official_book).toLowerCase() !== text(row.official_book).toLowerCase()
      || text(normalized.official_verdict) !== text(row.official_verdict)) return null;
  if (!providerContractValid(candidate, proof.bindings, proof.freshness, text(preclose.freshness_status).toLowerCase(), isDiagnostic)
      || !precloseContractValid(preclose, proof.bindings)) return null;

  const familyStates = safeFamilyStates(decision.family_states);
  const familyCount = integer(decision.family_count);
  const maximumFamilyCount = integer(decision.maximum_family_count);
  if (!familyStates || !sameFamilyStates(familyStates, row.family_states)) return null;
  const decisiveFamilies = decision.decisive_families;
  const expectedDecisiveFamilies = FAMILY_ORDER.filter(name => familyStates[name].state === 'agree');
  if (!equalStringArray(decisiveFamilies, expectedDecisiveFamilies)
      || !proofReasonList(decision.reason_codes)
      || typeof decision.preclose_required_for_selected_lane !== 'boolean') return null;

  if (isDiagnostic) {
    const expectedFamilyStates = Object.fromEntries(FAMILY_ORDER.map(name => [name, familyVote('pending', [...diagnosticReasons])]));
    if (!jsonEqual(familyStates, expectedFamilyStates)
        || decision.support !== 'pending' || decision.drag_core !== 'pending' || decision.no_drag !== 'pending'
        || decision.consensus_core !== 'pending' || decision.reentry_expansion !== 'pending'
        || decision.selected_lane !== null || decision.selection_status !== 'pending'
        || familyCount !== 0 || maximumFamilyCount !== FAMILY_ORDER.length
        || decisiveFamilies.length !== 0 || decision.preclose_required_for_selected_lane !== false
        || !equalStringArray(preclose.reason_codes, diagnosticReasons)) return null;
  } else {
    const recomputed = recomputeDecision(normalizedInputs, preclose);
    const semanticKeys = [
      'support', 'drag_core', 'no_drag', 'family_states', 'consensus_core',
      'reentry_expansion', 'selected_lane', 'selection_status', 'family_count',
      'maximum_family_count', 'decisive_families', 'preclose_required_for_selected_lane',
    ];
    if (semanticKeys.some(key => !jsonEqual(decision[key], recomputed.decision[key]))) return null;
    const expectedPrecloseScore = recomputed.score || {
      score: null, label: null, positive_reasons: [], risk_reasons: [],
    };
    if (['score', 'label', 'positive_reasons', 'risk_reasons']
      .some(key => !jsonEqual(preclose[key], expectedPrecloseScore[key]))) return null;
  }

  if (familyCount !== integer(row.family_count)
      || text(decision.selection_status) !== text(row.selection_status)
      || (decision.selected_lane ?? null) !== (row.lane ?? null)) return null;

  const observationIds = Array.isArray(row.evidence_observation_ids) ? row.evidence_observation_ids : [];
  if (integer(preclose.qualifying_observation_count) !== integer(row.evidence_observation_count)
      || !equalStringArray(preclose.decisive_observation_tokens, observationIds)
      || !nullableTimestampMatches(preclose.first_observed_at, row.evidence_first_observed_at)
      || !nullableTimestampMatches(preclose.last_observed_at, row.evidence_last_observed_at)
      || text(preclose.freshness_status) !== text(row.evidence_freshness_status)) return null;

  return {
    support: decision.support,
    drag_core: decision.drag_core,
    no_drag: decision.no_drag,
    lane_states: {
      consensus_core: decision.consensus_core,
      reentry_expansion: decision.reentry_expansion,
    },
    decisive_families: [...decisiveFamilies],
    preclose_required_for_selected_lane: decision.preclose_required_for_selected_lane,
  };
}

function responseRow(row, contract, { artifactAdvancedAfterFreeze, decisionProof = null }) {
  const lane = text(row.lane) || null;
  const selectorId = text(row.selector_id) || null;
  const output = {
    slate_date: row.slate_date,
    pitcher: safeText(row.pitcher),
    team: safeTeam(row.team),
    opp_team: safeTeam(row.opp_team),
    game_time: timestamp(row.game_time),
    side: text(row.side).toLowerCase(),
    model_k_line: number(row.model_k_line),
    official_odds: integer(row.official_odds),
    official_book: supportedBook(row.official_book),
    official_verdict: text(row.official_verdict),
    bundle_id: contract.bundleId,
    selector_id: selectorId,
    lane,
    selection_status: text(row.selection_status),
    family_states: safeFamilyStates(row.family_states),
    family_count: integer(row.family_count) ?? 0,
    checkpoint: text(row.checkpoint),
    source_artifact_generated_at: timestamp(row.source_artifact_generated_at) || null,
    evidence_observation_count: integer(row.evidence_observation_count) ?? 0,
    evidence_first_observed_at: timestamp(row.evidence_first_observed_at) || null,
    evidence_last_observed_at: timestamp(row.evidence_last_observed_at) || null,
    evidence_freshness_status: text(row.evidence_freshness_status),
    frozen_at: timestamp(row.frozen_at) || null,
    should_lock_at: timestamp(row.should_lock_at) || null,
    minutes_until_start: number(row.minutes_until_start),
    lock_status: text(row.lock_status),
    artifact_advanced_after_freeze: artifactAdvancedAfterFreeze,
  };
  if (!contract.requiresProof) output.reason_codes = safeReasonCodes(row.reason_codes);
  if (contract.requiresProof) output.decision_proof = decisionProof;
  return output;
}

function validSelectionIdentity(row, contract) {
  const lane = row.lane;
  const selectorId = row.selector_id;
  const selectionStatus = text(row.selection_status);
  const hasApprovedLane = typeof lane === 'string'
    && typeof selectorId === 'string'
    && LANES.has(lane)
    && selectorId === contract.selectorIds[lane];
  const hasNoLane = Object.hasOwn(row, 'lane') && Object.hasOwn(row, 'selector_id')
    && lane === null && selectorId === null;
  if (selectionStatus === 'selected') return hasApprovedLane;
  if (selectionStatus === 'not_selected') return hasNoLane;
  return selectionStatus === 'pending' && (hasNoLane || hasApprovedLane);
}

function validStateBase(row, slateDate, contract) {
  if (!row || typeof row !== 'object') return false;
  const checkpoint = text(row.checkpoint);
  const familyStates = safeFamilyStates(row.family_states);
  const reasons = safeReasonCodes(row.reason_codes);
  return validDate(row.slate_date) === slateDate
    && text(row.bundle_id) === contract.bundleId
    && CHECKPOINTS.has(checkpoint)
    && safeText(row.pitcher) && safeText(row.normalized_pitcher) && safeTeam(row.team) && safeTeam(row.opp_team)
    && timestamp(row.game_time) && ['over', 'under'].includes(text(row.side).toLowerCase())
    && number(row.model_k_line) != null
    && validSelectionIdentity(row, contract)
    && validHash(row.selector_fingerprint) === contract.selectorFingerprint
    && integer(row.official_odds) != null && supportedBook(row.official_book)
    && (contract.requiresProof ? V2_OFFICIAL_VERDICTS : OFFICIAL_VERDICTS).has(text(row.official_verdict))
    && SELECTION_STATUSES.has(text(row.selection_status))
    && integer(row.family_count) != null && integer(row.family_count) >= 0
    && integer(row.evidence_observation_count) != null && integer(row.evidence_observation_count) >= 0
    && familyStates != null && reasons != null && EVIDENCE_FRESHNESS.has(text(row.evidence_freshness_status))
    && validHash(row.source_artifact_sha256) && validHash(row.source_artifact_byte_sha256);
}

function coalesceV2Visible(items) {
  const byCandidate = new Map();
  for (const item of items) {
    const candidateIdentity = text(item.row.candidate_identity);
    const priority = text(item.row.checkpoint) === 'frozen_pregame' ? 2 : 1;
    const current = byCandidate.get(candidateIdentity);
    if (!current || priority > current.priority) {
      byCandidate.set(candidateIdentity, {
        priority,
        response: item.response,
        ambiguous: false,
      });
      continue;
    }
    if (priority < current.priority || current.ambiguous) continue;
    if (!jsonEqual(current.response, item.response)) current.ambiguous = true;
  }
  return [...byCandidate.values()]
    .filter(item => !item.ambiguous)
    .map(item => item.response);
}

function validCanonical(row, slateDate) {
  if (!row || typeof row !== 'object') return null;
  const normalizePosture = value => text(value).toLowerCase().replace(/\+/g, '_');
  const postures = [row.payload_odds_source, row.payload_provider_posture];
  if (row.payload_pitchers != null && !Array.isArray(row.payload_pitchers)) return null;
  if (Array.isArray(row.payload_pitchers)) {
    for (const pitcher of row.payload_pitchers) {
      if (!pitcher || typeof pitcher !== 'object') return null;
      postures.push(pitcher.market_source_mode, pitcher.odds_source, pitcher.provider_posture);
    }
  }
  const declaredPostures = postures.map(normalizePosture).filter(Boolean);
  const approvedPosture = declaredPostures.length > 0
    && declaredPostures.every(posture => APPROVED_POSTURES.has(posture));
  if (text(row.artifact_key) !== CANONICAL_ARTIFACT_KEY
      || validDate(row.slate_date) !== slateDate
      || validDate(row.payload_date) !== slateDate
      || !validHash(row.payload_sha256)
      || !approvedPosture
      || text(row.artifact_path) !== CANONICAL_ARTIFACT_PATH
      || !timestamp(row.generated_at)
      || !APPROVED_PUBLICATION_SOURCES.has(text(row.source)) ) return null;
  return {
    payloadSha: validHash(row.payload_sha256),
    generatedAt: timestamp(row.generated_at),
    path: CANONICAL_ARTIFACT_PATH,
  };
}

function provisionalIsCurrent(row, artifact, contract) {
  return validStateBase(row, row.slate_date, contract)
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
    && text(row.lock_source_artifact_path)
    && text(row.lock_source_artifact_path) === text(lock.source_artifact_path)
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

  const contract = requestedContract(event);
  if (!contract) return jsonResponse(200, emptyPayload(null, 'unsupported_bundle_version', 'unavailable', null));

  let slateDate;
  try { slateDate = currentPhoenixDate(); } catch { return jsonResponse(200, emptyPayload(null, 'clock_unavailable', 'unavailable', contract)); }
  const requestedDate = text(event.queryStringParameters?.date || event.queryStringParameters?.slate_date);
  if (requestedDate && requestedDate !== slateDate) return jsonResponse(200, emptyPayload(slateDate, null, 'ready', contract));

  const supabaseUrl = envValue('SUPABASE_URL');
  const serviceRoleKey = envValue('SUPABASE_SERVICE_ROLE_KEY');
  if (!supabaseUrl || !serviceRoleKey) return jsonResponse(200, emptyPayload(slateDate, 'missing_supabase_config', 'unavailable', contract));

  try {
    const canonicalRows = await supabaseRead({
      supabaseUrl, serviceRoleKey, table: 'published_pipeline_artifacts',
      params: { select: CANONICAL_SELECT, artifact_key: 'eq.today', limit: '1' },
    });
    const artifact = canonicalRows.length === 1 ? validCanonical(canonicalRows[0], slateDate) : null;
    if (!artifact) return jsonResponse(200, emptyPayload(slateDate, 'canonical_artifact_unavailable', 'unavailable', contract));

    const stateRows = await supabaseRead({
      supabaseUrl, serviceRoleKey, table: 'alternative_pick_selection_state',
      params: {
        select: STATE_SELECT, slate_date: `eq.${slateDate}`, bundle_id: `eq.${contract.bundleId}`,
        checkpoint: 'in.(provisional,frozen_pregame)', limit: '250',
      },
    });
    const rows = stateRows.flatMap(row => {
      if (!validStateBase(row, slateDate, contract)) return [];
      if (!contract.requiresProof) return [{ row, decisionProof: null }];
      let decisionProof;
      try { decisionProof = validateV2Proof(row); } catch { return []; }
      return decisionProof ? [{ row, decisionProof }] : [];
    });
    const frozenRows = rows.filter(item => text(item.row.checkpoint) === 'frozen_pregame');
    const dedupeKeys = [...new Set(frozenRows.map(item => text(item.row.lock_dedupe_key)).filter(Boolean))];
    const locks = dedupeKeys.length ? await supabaseRead({
      supabaseUrl, serviceRoleKey, table: 'operational_pick_locks',
      params: { select: LOCK_SELECT, slate_date: `eq.${slateDate}`, dedupe_key: lockFilter(dedupeKeys), limit: String(dedupeKeys.length) },
    }) : [];
    const lockByKey = new Map(locks.map(lock => [text(lock.dedupe_key), lock]));
    const visibleItems = rows.flatMap(({ row, decisionProof }) => {
      if (text(row.checkpoint) === 'provisional') {
        return provisionalIsCurrent(row, artifact, contract)
          ? [{
            row,
            response: responseRow(row, contract, { artifactAdvancedAfterFreeze: false, decisionProof }),
          }] : [];
      }
      const lock = lockByKey.get(text(row.lock_dedupe_key));
      if (!lockMatchesFrozenRow(row, lock, artifact)) return [];
      return [{
        row,
        response: responseRow(row, contract, {
          artifactAdvancedAfterFreeze: validHash(row.source_artifact_sha256) !== artifact.payloadSha,
          decisionProof,
        }),
      }];
    });
    const visible = contract.requiresProof
      ? coalesceV2Visible(visibleItems)
      : visibleItems.map(item => item.response);
    const counts = {
      provisional: visible.filter(row => row.checkpoint === 'provisional').length,
      frozen: visible.filter(row => row.checkpoint === 'frozen_pregame').length,
      selected: visible.filter(row => row.selection_status === 'selected').length,
      pending: visible.filter(row => row.selection_status === 'pending').length,
    };
    return jsonResponse(200, {
      slate_date: slateDate, generated_at: artifact.generatedAt, status: 'ready',
      bundle_id: contract.bundleId, selector_fingerprint: contract.selectorFingerprint,
      counts, rows: visible, error: null,
    });
  } catch {
    return jsonResponse(200, emptyPayload(slateDate, 'supabase_read_failed', 'unavailable', contract));
  }
}
