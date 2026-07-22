/* Isolated, read-only adapter for same-day alternative methodology evidence. */
(function () {
  const ENDPOINT = "/.netlify/functions/alternative-picks";
  const LANES = new Set(["consensus_core", "reentry_expansion"]);
  const STATUSES = new Set(["selected", "not_selected", "pending"]);
  const CHECKPOINTS = new Set(["provisional", "frozen_pregame"]);
  const LOCK_STATUSES = new Set(["due_now", "missed_lock"]);
  const FAMILY_KEYS = ["base", "anchor", "preclose", "reentry"];
  const FAMILY_STATES = new Set(["agree", "disagree", "pending"]);

  function phoenixDate() {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Phoenix", year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  }

  function text(value) { return typeof value === "string" ? value.trim() : ""; }
  function finite(value) { return typeof value === "number" && Number.isFinite(value); }
  function isoTimestamp(value) {
    const timestamp = text(value);
    const match = timestamp.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/);
    if (!match || !Number.isFinite(Date.parse(timestamp))) return false;
    const [year, month, day, hour, minute, second] = match.slice(1, 7).map(Number);
    const calendar = new Date(Date.UTC(year, month - 1, day));
    return calendar.getUTCFullYear() === year && calendar.getUTCMonth() === month - 1 && calendar.getUTCDate() === day
      && hour <= 23 && minute <= 59 && second <= 59;
  }

  function normalizeFamilyStates(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    if (Object.keys(value).length !== FAMILY_KEYS.length || !FAMILY_KEYS.every((key) => Object.hasOwn(value, key))) return null;
    const normalized = {};
    for (const key of FAMILY_KEYS) {
      const state = text(value[key]?.state);
      if (!FAMILY_STATES.has(state)) return null;
      normalized[key] = { state, reason_codes: Array.isArray(value[key]?.reason_codes) ? value[key].reason_codes.filter((code) => typeof code === "string") : [] };
    }
    return normalized;
  }

  function normalizeRow(row, slateDate) {
    if (!row || typeof row !== "object" || Array.isArray(row)) return null;
    const lane = text(row.lane);
    const selectionStatus = text(row.selection_status);
    const checkpoint = text(row.checkpoint);
    const familyStates = normalizeFamilyStates(row.family_states);
    if (text(row.slate_date) !== slateDate || !LANES.has(lane) || !STATUSES.has(selectionStatus) || !CHECKPOINTS.has(checkpoint) || !familyStates) return null;
    if (!text(row.pitcher) || !text(row.team) || !text(row.opp_team) || !text(row.side) || !finite(row.model_k_line)) return null;
    if (!isoTimestamp(row.game_time) || !isoTimestamp(row.source_artifact_generated_at) || !isoTimestamp(row.evidence_first_observed_at) || !isoTimestamp(row.evidence_last_observed_at)) return null;
    if (checkpoint === "frozen_pregame" && (!isoTimestamp(row.frozen_at) || !isoTimestamp(row.should_lock_at) || !finite(row.minutes_until_start) || !LOCK_STATUSES.has(text(row.lock_status)))) return null;
    return {
      slate_date: slateDate, pitcher: text(row.pitcher), team: text(row.team), opp_team: text(row.opp_team),
      game_time: text(row.game_time), side: text(row.side).toUpperCase(), model_k_line: row.model_k_line,
      official_odds: finite(row.official_odds) ? row.official_odds : null, official_book: text(row.official_book), official_verdict: text(row.official_verdict),
      lane, selection_status: selectionStatus, checkpoint, family_states: familyStates,
      family_count: Number.isInteger(row.family_count) ? row.family_count : 0,
      reason_codes: Array.isArray(row.reason_codes) ? row.reason_codes.filter((code) => typeof code === "string") : [],
      source_artifact_generated_at: text(row.source_artifact_generated_at), evidence_freshness_status: text(row.evidence_freshness_status),
      evidence_observation_count: Number.isInteger(row.evidence_observation_count) ? row.evidence_observation_count : 0,
      evidence_last_observed_at: text(row.evidence_last_observed_at), frozen_at: text(row.frozen_at),
      should_lock_at: text(row.should_lock_at), minutes_until_start: finite(row.minutes_until_start) ? row.minutes_until_start : null,
      lock_status: text(row.lock_status), artifact_advanced_after_freeze: row.artifact_advanced_after_freeze === true,
    };
  }

  function normalizeResponse(payload) {
    const slateDate = phoenixDate();
    if (!payload || typeof payload !== "object" || text(payload.slate_date) !== slateDate) return { slate_date: slateDate, status: "unavailable", counts: {}, rows: [], error: "invalid_response" };
    const status = text(payload.status);
    if (status === "unavailable") return { slate_date: slateDate, status, counts: {}, rows: [], error: "unavailable" };
    if (status !== "ready" || !Array.isArray(payload.rows)) return { slate_date: slateDate, status: "unavailable", counts: {}, rows: [], error: "invalid_response" };
    const rows = payload.rows.map((row) => normalizeRow(row, slateDate)).filter(Boolean);
    return { slate_date: slateDate, generated_at: text(payload.generated_at), status: "ready", counts: payload.counts && typeof payload.counts === "object" ? payload.counts : {}, rows, error: null };
  }

  function formatFreezeLabel(row) {
    if (row?.checkpoint !== "frozen_pregame" || !isoTimestamp(row.frozen_at) || !finite(row.minutes_until_start) || !LOCK_STATUSES.has(text(row.lock_status))) return "Provisional";
    const minutes = Number.isFinite(row.minutes_until_start) ? Math.max(0, Math.round(row.minutes_until_start)) : null;
    const suffix = row.lock_status === "missed_lock" ? " (late)" : "";
    return minutes == null ? `Frozen${suffix}` : `Frozen T-${minutes}${suffix}`;
  }

  async function fetchCurrentSlate() {
    try {
      const response = await fetch(ENDPOINT);
      if (!response.ok) throw new Error(`alternative_picks_${response.status}`);
      return normalizeResponse(await response.json());
    } catch {
      return { slate_date: phoenixDate(), status: "unavailable", counts: {}, rows: [], error: "fetch_failed" };
    }
  }

  window.V2AltPicks = { fetchCurrentSlate, normalizeResponse, formatFreezeLabel };
})();
