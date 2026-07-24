/* Isolated, read-only adapter for same-day alternative methodology evidence. */
(function () {
  const ENDPOINT = "/api/slate-comparison?bundle_version=v2";
  const BUNDLE_ID = "pregame_alternative_pick_methodology_v2";
  const SELECTOR_FINGERPRINT = "23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4";
  const LANES = ["consensus_core", "reentry_expansion"];
  const SELECTOR_IDS_BY_LANE = Object.freeze({
    consensus_core: "no_drag_distinct_family_consensus_core_v2",
    reentry_expansion: "moderate_edge_quality_reentry_expansion_v2",
  });
  const STATUSES = new Set(["selected", "not_selected", "pending"]);
  const CHECKPOINTS = new Set(["provisional", "frozen_pregame"]);
  const LOCK_STATUSES = new Set(["due_now", "missed_lock"]);
  const FAMILY_KEYS = ["base", "anchor", "preclose", "reentry"];
  const FAMILY_STATES = new Set(["agree", "disagree", "pending"]);
  const TRI_STATES = new Set(["true", "false", "pending"]);
  const EVIDENCE_FRESHNESS = new Set(["fresh", "pending"]);
  const OFFICIAL_VERDICTS = new Set(["LEAN", "FIRE 1u", "FIRE 2u"]);

  function phoenixDate() {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/Phoenix", year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  }

  function text(value) { return typeof value === "string" ? value.trim() : ""; }
  function finite(value) { return typeof value === "number" && Number.isFinite(value); }
  function exactKeys(value, keys) {
    return value && typeof value === "object" && !Array.isArray(value)
      && Object.keys(value).length === keys.length && keys.every((key) => Object.hasOwn(value, key));
  }
  function isoTimestamp(value) {
    const timestamp = text(value);
    const match = timestamp.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/);
    if (!match || !Number.isFinite(Date.parse(timestamp))) return false;
    const [year, month, day, hour, minute, second] = match.slice(1, 7).map(Number);
    const calendar = new Date(Date.UTC(year, month - 1, day));
    return calendar.getUTCFullYear() === year && calendar.getUTCMonth() === month - 1 && calendar.getUTCDate() === day
      && hour <= 23 && minute <= 59 && second <= 59;
  }
  function stringList(value) {
    if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) return null;
    return value.map((item) => item.trim()).filter(Boolean);
  }

  function triAnd(...values) {
    if (values.some((value) => value === false)) return false;
    return values.every((value) => value === true) ? true : null;
  }
  function triNot(value) { return value == null ? null : !value; }
  function triValue(value) { return value === "true" ? true : value === "false" ? false : null; }
  function triName(value) { return value == null ? "pending" : value ? "true" : "false"; }

  function normalizeFamilyStates(value) {
    if (!exactKeys(value, FAMILY_KEYS)) return null;
    const normalized = {};
    for (const key of FAMILY_KEYS) {
      if (!exactKeys(value[key], ["state", "reason_codes"])) return null;
      const state = text(value[key].state);
      const reasonCodes = stringList(value[key].reason_codes);
      if (!FAMILY_STATES.has(state) || reasonCodes == null) return null;
      normalized[key] = { state, reason_codes: reasonCodes };
    }
    return normalized;
  }

  function validSelectionIdentity(row, selectionStatus) {
    const lane = row.lane;
    const selectorId = row.selector_id;
    const hasApprovedLane = typeof lane === "string" && LANES.includes(lane)
      && typeof selectorId === "string" && selectorId === SELECTOR_IDS_BY_LANE[lane];
    const hasNoLane = Object.hasOwn(row, "lane") && Object.hasOwn(row, "selector_id")
      && lane === null && selectorId === null;
    if (selectionStatus === "selected") return hasApprovedLane;
    if (selectionStatus === "not_selected") return hasNoLane;
    return selectionStatus === "pending" && (hasNoLane || hasApprovedLane);
  }

  function normalizeDecisionProof(value, row, familyStates, selectionStatus) {
    const proofKeys = ["support", "drag_core", "no_drag", "lane_states", "decisive_families", "preclose_required_for_selected_lane"];
    if (!exactKeys(value, proofKeys) || !TRI_STATES.has(text(value.support))
      || !TRI_STATES.has(text(value.drag_core)) || !TRI_STATES.has(text(value.no_drag))
      || !exactKeys(value.lane_states, LANES)
      || !LANES.every((lane) => TRI_STATES.has(text(value.lane_states[lane])))
      || typeof value.preclose_required_for_selected_lane !== "boolean") return null;

    const decisiveFamilies = stringList(value.decisive_families);
    const expectedFamilies = FAMILY_KEYS.filter((name) => familyStates[name].state === "agree");
    if (decisiveFamilies == null || decisiveFamilies.length !== expectedFamilies.length
      || decisiveFamilies.some((name, index) => name !== expectedFamilies[index])) return null;

    const support = triValue(text(value.support));
    const dragCore = triValue(text(value.drag_core));
    const noDrag = triValue(text(value.no_drag));
    if (triName(triAnd(support, triNot(dragCore))) !== text(value.no_drag)) return null;
    const agreeCount = expectedFamilies.length;
    const maximumCount = FAMILY_KEYS.filter((name) => familyStates[name].state !== "disagree").length;
    const countGate = agreeCount >= 2 ? true : maximumCount < 2 ? false : null;
    const reentry = familyStates.reentry.state === "agree" ? true
      : familyStates.reentry.state === "disagree" ? false : null;
    const expectedLaneStates = {
      consensus_core: triName(triAnd(noDrag, countGate)),
      reentry_expansion: triName(triAnd(reentry, triNot(noDrag))),
    };
    const laneStates = Object.fromEntries(LANES.map((lane) => [lane, text(value.lane_states[lane])]));
    if (LANES.some((lane) => laneStates[lane] !== expectedLaneStates[lane])) return null;
    if (selectionStatus === "selected") {
      const otherLane = LANES.find((lane) => lane !== row.lane);
      if (laneStates[row.lane] !== "true" || laneStates[otherLane] !== "false") return null;
      if (row.lane === "consensus_core" && text(value.no_drag) !== "true") return null;
      if (row.lane === "reentry_expansion" && text(value.no_drag) !== "false") return null;
      if (familyStates.preclose.state === "pending" && value.preclose_required_for_selected_lane !== false) return null;
    } else if (selectionStatus === "not_selected") {
      if (!LANES.every((lane) => laneStates[lane] === "false")) return null;
    } else {
      if (LANES.some((lane) => laneStates[lane] === "true") || !LANES.some((lane) => laneStates[lane] === "pending")) return null;
      if (row.lane && laneStates[row.lane] !== "pending") return null;
    }
    const expectedPrecloseRequired = selectionStatus === "selected" && row.lane === "consensus_core"
      && familyStates.preclose.state === "agree"
      && FAMILY_KEYS.filter((name) => name !== "preclose" && familyStates[name].state === "agree").length < 2;
    if (value.preclose_required_for_selected_lane !== expectedPrecloseRequired) return null;

    return {
      support: text(value.support), drag_core: text(value.drag_core), no_drag: text(value.no_drag),
      lane_states: laneStates, decisive_families: decisiveFamilies,
      preclose_required_for_selected_lane: value.preclose_required_for_selected_lane,
    };
  }

  function validEvidenceTimes(row, selectionStatus, familyStates, decisionProof) {
    const count = row.evidence_observation_count;
    const first = text(row.evidence_first_observed_at);
    const last = text(row.evidence_last_observed_at);
    const freshness = text(row.evidence_freshness_status);
    if (!Number.isInteger(count) || count < 0 || !EVIDENCE_FRESHNESS.has(freshness)) return false;
    if (count === 0) {
      if (freshness !== "pending" || first || last) return false;
      return selectionStatus !== "selected"
        || (familyStates.preclose.state === "pending" && decisionProof.preclose_required_for_selected_lane === false);
    }
    return isoTimestamp(first) && isoTimestamp(last) && Date.parse(first) <= Date.parse(last);
  }

  function normalizeRow(row, slateDate) {
    if (!row || typeof row !== "object" || Array.isArray(row)) return null;
    const selectionStatus = text(row.selection_status);
    const checkpoint = text(row.checkpoint);
    const familyStates = normalizeFamilyStates(row.family_states);
    if (text(row.bundle_id) !== BUNDLE_ID || text(row.slate_date) !== slateDate
      || !STATUSES.has(selectionStatus) || !validSelectionIdentity(row, selectionStatus)
      || !CHECKPOINTS.has(checkpoint) || !familyStates) return null;
    if (!text(row.pitcher) || !text(row.team) || !text(row.opp_team)
      || !["over", "under"].includes(text(row.side).toLowerCase()) || !finite(row.model_k_line)
      || !Number.isInteger(row.official_odds) || !text(row.official_book)
      || !OFFICIAL_VERDICTS.has(text(row.official_verdict))) return null;
    if (!isoTimestamp(row.game_time) || !isoTimestamp(row.source_artifact_generated_at)) return null;

    const familyCount = FAMILY_KEYS.filter((name) => familyStates[name].state === "agree").length;
    if (row.family_count !== familyCount) return null;
    const decisionProof = normalizeDecisionProof(row.decision_proof, row, familyStates, selectionStatus);
    if (!decisionProof || !validEvidenceTimes(row, selectionStatus, familyStates, decisionProof)) return null;

    if (checkpoint === "frozen_pregame") {
      if (!isoTimestamp(row.frozen_at) || !isoTimestamp(row.should_lock_at)
        || !finite(row.minutes_until_start) || !LOCK_STATUSES.has(text(row.lock_status))) return null;
    } else if (text(row.frozen_at) || text(row.should_lock_at) || row.minutes_until_start != null || text(row.lock_status)) return null;

    return {
      slate_date: slateDate, pitcher: text(row.pitcher), team: text(row.team), opp_team: text(row.opp_team),
      game_time: text(row.game_time), side: text(row.side).toUpperCase(), model_k_line: row.model_k_line,
      official_odds: row.official_odds, official_book: text(row.official_book), official_verdict: text(row.official_verdict),
      bundle_id: BUNDLE_ID, lane: row.lane, selector_id: row.selector_id,
      selection_status: selectionStatus, checkpoint, family_states: familyStates,
      family_count: familyCount, decision_proof: decisionProof,
      source_artifact_generated_at: text(row.source_artifact_generated_at), evidence_freshness_status: text(row.evidence_freshness_status),
      evidence_observation_count: row.evidence_observation_count,
      evidence_first_observed_at: text(row.evidence_first_observed_at), evidence_last_observed_at: text(row.evidence_last_observed_at),
      frozen_at: text(row.frozen_at), should_lock_at: text(row.should_lock_at),
      minutes_until_start: finite(row.minutes_until_start) ? row.minutes_until_start : null,
      lock_status: text(row.lock_status), artifact_advanced_after_freeze: row.artifact_advanced_after_freeze === true,
    };
  }

  function unavailable(slateDate, error) {
    return { slate_date: slateDate, status: "unavailable", counts: {}, rows: [], error };
  }

  function countsFromRows(rows) {
    return {
      provisional: rows.filter((row) => row.checkpoint === "provisional").length,
      frozen: rows.filter((row) => row.checkpoint === "frozen_pregame").length,
      selected: rows.filter((row) => row.selection_status === "selected").length,
      pending: rows.filter((row) => row.selection_status === "pending").length,
    };
  }

  function normalizeResponse(payload) {
    const slateDate = phoenixDate();
    if (!payload || typeof payload !== "object" || Array.isArray(payload)
      || text(payload.slate_date) !== slateDate || text(payload.bundle_id) !== BUNDLE_ID
      || text(payload.selector_fingerprint) !== SELECTOR_FINGERPRINT) return unavailable(slateDate, "contract_mismatch");
    const status = text(payload.status);
    if (status === "unavailable") return unavailable(slateDate, "unavailable");
    if (status !== "ready" || !Array.isArray(payload.rows)) return unavailable(slateDate, "invalid_response");
    const rows = payload.rows.map((row) => normalizeRow(row, slateDate));
    if (rows.some((row) => row == null)) return unavailable(slateDate, "invalid_row");
    return {
      slate_date: slateDate, generated_at: text(payload.generated_at), status: "ready",
      bundle_id: BUNDLE_ID, selector_fingerprint: SELECTOR_FINGERPRINT,
      counts: countsFromRows(rows), rows, error: null,
    };
  }

  function formatFreezeLabel(row) {
    if (row?.checkpoint !== "frozen_pregame" || !isoTimestamp(row.frozen_at)
      || !finite(row.minutes_until_start) || !LOCK_STATUSES.has(text(row.lock_status))) return "Provisional";
    const minutes = Math.max(0, Math.round(row.minutes_until_start));
    const suffix = row.lock_status === "missed_lock" ? " (late)" : "";
    return `Frozen T-${minutes}${suffix}`;
  }

  async function fetchCurrentSlate() {
    try {
      const response = await fetch(ENDPOINT);
      if (!response.ok) throw new Error(`alternative_picks_${response.status}`);
      return normalizeResponse(await response.json());
    } catch {
      return unavailable(phoenixDate(), "fetch_failed");
    }
  }

  function startCurrentSlatePolling({
    onUpdate,
    fetcher = fetchCurrentSlate,
    intervalMs = 60000,
    schedule = setTimeout,
    cancelSchedule = clearTimeout,
  } = {}) {
    if (typeof onUpdate !== "function") throw new TypeError("onUpdate is required");
    let active = true;
    let timer = null;
    let lastGood = null;

    async function poll() {
      if (!active) return;
      let next;
      try {
        next = await fetcher();
      } catch {
        next = unavailable(phoenixDate(), "fetch_failed");
      }
      if (!active) return;

      if (next?.status === "ready") {
        lastGood = next;
        onUpdate({ ...next, refresh_status: "current", refresh_error: "" });
      } else if (lastGood) {
        onUpdate({
          ...lastGood,
          refresh_status: "retrying",
          refresh_error: text(next?.error) || "fetch_failed",
        });
      } else {
        const failed = next?.status === "unavailable"
          ? next
          : unavailable(phoenixDate(), "fetch_failed");
        onUpdate({
          ...failed,
          refresh_status: "retrying",
          refresh_error: text(failed.error) || "fetch_failed",
        });
      }
      if (active) timer = schedule(poll, intervalMs);
    }

    void poll();
    return () => {
      active = false;
      if (timer != null) cancelSchedule(timer);
    };
  }

  window.V2AltPicks = {
    fetchCurrentSlate,
    startCurrentSlatePolling,
    normalizeResponse,
    formatFreezeLabel,
  };
})();
