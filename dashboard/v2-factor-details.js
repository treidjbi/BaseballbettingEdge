(function attachFactorDetails(root, factory) {
  const helpers = factory();

  if (typeof module !== "undefined" && module.exports) {
    module.exports.buildFactorGroups = helpers.buildFactorGroups;
  }

  if (root) {
    root.V2FactorDetails = helpers;
  }
})(
  typeof globalThis !== "undefined"
    ? globalThis
    : typeof window !== "undefined"
      ? window
      : this,
  function createFactorDetails() {
    const GROUPS = [
      { key: "projection-core", label: "Projection Core" },
      { key: "opponent-context", label: "Opponent Context" },
      { key: "pitcher-form", label: "Pitcher Form" },
      { key: "environment", label: "Environment" },
      { key: "workload-rest", label: "Workload / Rest" },
      { key: "data-health", label: "Data Health" },
    ];

    const OPP_K_BASELINE = 0.227;

    function normalizeDirection(direction) {
      return direction === "UNDER" ? "UNDER" : "OVER";
    }

    function toNumber(value) {
      return typeof value === "number" && Number.isFinite(value) ? value : null;
    }

    function formatNumber(value, digits = 1) {
      const n = toNumber(value);
      return n == null ? "—" : n.toFixed(digits);
    }

    function formatSignedNumber(value, digits = 2, suffix = "") {
      const n = toNumber(value);
      if (n == null) {
        return "—";
      }

      const sign = n > 0 ? "+" : "";
      return `${sign}${n.toFixed(digits)}${suffix}`;
    }

    function formatEvRoi(value) {
      const n = toNumber(value);
      return n == null ? "—" : `${n > 0 ? "+" : ""}${(n * 100).toFixed(1)}%`;
    }

    function formatPercent(value, digits = 1) {
      const n = toNumber(value);
      return n == null ? "—" : `${(n * 100).toFixed(digits)}%`;
    }

    function formatPitchCount(value) {
      const n = toNumber(value);
      return n == null ? "—" : `${Math.round(n)} pitches`;
    }

    function formatDays(value) {
      const n = toNumber(value);
      return n == null ? "—" : `${n} days`;
    }

    function formatUmpire(umpire, umpKAdj) {
      const adj = toNumber(umpKAdj);

      if (umpire == null) {
        if (adj == null || adj === 0) {
          return "TBA";
        }

        return `Assigned (${formatSignedNumber(adj, 2)})`;
      }

      if (adj == null || adj === 0) {
        return String(umpire);
      }

      return `${String(umpire)} (${formatSignedNumber(adj, 2)})`;
    }

    function toneForDirection(delta, direction) {
      const n = toNumber(delta);
      if (n == null || n === 0) {
        return n === 0 ? "neutral" : null;
      }

      const support = direction === "OVER" ? n > 0 : n < 0;
      return support ? "pos" : "neg";
    }

    function toneForSignedValue(value) {
      const n = toNumber(value);
      if (n == null || n === 0) {
        return n === 0 ? "neutral" : null;
      }

      return n > 0 ? "pos" : "neg";
    }

    function parkFactorTone(parkFactor, direction) {
      const n = toNumber(parkFactor);
      if (n == null) {
        return "neutral";
      }

      if (n >= 0.98 && n <= 1.02) {
        return "neutral";
      }

      return n > 1.02
        ? (direction === "OVER" ? "pos" : "neg")
        : (direction === "UNDER" ? "pos" : "neg");
    }

    function buildRow({ key, label, value, rawValue, status, tone, note }) {
      const row = {
        key,
        label,
        value,
        rawValue,
        status,
      };

      if (tone) {
        row.tone = tone;
      }

      if (note) {
        row.note = note;
      }

      return row;
    }

    function lineupStatus(lineupUsed) {
      return lineupUsed ? "active" : "missing";
    }

    function umpStatus(umpire, umpKAdj) {
      const adj = toNumber(umpKAdj);

      if (umpire == null) {
        return adj == null || adj === 0 ? "missing" : "active";
      }

      if (adj === 0) {
        return "neutral";
      }

      return "active";
    }

    function buildFactorGroups(pick, direction) {
      const dir = normalizeDirection(direction ?? pick?.direction);
      const selectedSide = dir === "UNDER" ? pick?.ev_under : pick?.ev_over;
      const line = toNumber(pick?.k_line);
      const lambda = toNumber(pick?.lambda);
      const rawEvRoi = toNumber(selectedSide?.ev ?? pick?.raw_ev_roi);
      const adjEvRoi = toNumber(selectedSide?.adj_ev ?? pick?.adj_ev_roi);
      const avgIp = toNumber(pick?.avg_ip);
      const edge = toNumber(selectedSide?.edge ?? pick?.edge);
      const oppKRate = toNumber(pick?.opp_k_rate);
      const recentK9 = toNumber(pick?.recent_k9);
      const seasonK9 = toNumber(pick?.season_k9);
      const careerK9 = toNumber(pick?.career_k9);
      const swstrPct = toNumber(pick?.swstr_pct);
      const swstrDeltaK9 = toNumber(pick?.swstr_delta_k9);
      const restK9Delta = toNumber(pick?.rest_k9_delta);
      const parkFactor = toNumber(pick?.park_factor);
      const umpire = pick?.umpire ?? null;
      const umpKAdj = toNumber(pick?.ump_k_adj);
      const daysSinceLastStart = toNumber(pick?.days_since_last_start);
      const lastPitchCount = toNumber(pick?.last_pitch_count);
      const lineupUsed = pick?.lineup_used === true;
      const dataComplete = pick?.data_complete === true;

      return [
        {
          key: GROUPS[0].key,
          label: GROUPS[0].label,
          rows: [
            buildRow({
              key: "line",
              label: "Line",
              value: `${formatNumber(line, 1)} K`,
              rawValue: line,
              status: line == null ? "missing" : "active",
            }),
            buildRow({
              key: "lambda",
              label: "Model lambda",
              value: `${formatNumber(lambda, 2)} K`,
              rawValue: lambda,
              status: lambda == null ? "missing" : "active",
              tone: toneForDirection(edge, dir),
              note: "Model strikeout projection",
            }),
            buildRow({
              key: "raw_ev_roi",
              label: "Raw EV ROI",
              value: formatEvRoi(rawEvRoi),
              rawValue: rawEvRoi,
              status: rawEvRoi == null ? "missing" : (rawEvRoi === 0 ? "neutral" : "active"),
              tone: toneForSignedValue(rawEvRoi),
              note: "Selected-side raw EV ROI",
            }),
            buildRow({
              key: "adjusted_ev_roi",
              label: "Adjusted EV ROI",
              value: formatEvRoi(adjEvRoi),
              rawValue: adjEvRoi,
              status: adjEvRoi == null ? "missing" : (adjEvRoi === 0 ? "neutral" : "active"),
              tone: toneForSignedValue(adjEvRoi),
              note: "Selected-side adjusted EV ROI",
            }),
            buildRow({
              key: "edge",
              label: "Probability edge",
              value: formatEvRoi(edge),
              rawValue: edge,
              status: edge == null ? "missing" : (edge === 0 ? "neutral" : "active"),
              tone: toneForSignedValue(edge),
              note: "Selected-side probability edge",
            }),
            buildRow({
              key: "expected_ip",
              label: "Expected IP",
              value: formatNumber(avgIp, 1),
              rawValue: avgIp,
              status: avgIp == null ? "missing" : "active",
            }),
          ],
        },
        {
          key: GROUPS[1].key,
          label: GROUPS[1].label,
          rows: [
            buildRow({
              key: "opp_k_rate",
              label: "Opp. K-rate",
              value: formatPercent(oppKRate, 1),
              rawValue: oppKRate,
              status: oppKRate == null ? "missing" : "active",
              tone: toneForDirection(oppKRate == null ? null : oppKRate - OPP_K_BASELINE, dir),
              note: "Opponent strikeout baseline",
            }),
          ],
        },
        {
          key: GROUPS[2].key,
          label: GROUPS[2].label,
          rows: [
            buildRow({
              key: "recent_k9",
              label: "Recent K/9 (L5)",
              value: formatNumber(recentK9, 1),
              rawValue: recentK9,
              status: recentK9 == null ? "missing" : "active",
              tone: toneForDirection(recentK9 == null || seasonK9 == null ? null : recentK9 - seasonK9, dir),
            }),
            buildRow({
              key: "season_k9",
              label: "Season K/9",
              value: formatNumber(seasonK9, 1),
              rawValue: seasonK9,
              status: seasonK9 == null ? "missing" : "active",
            }),
            buildRow({
              key: "career_k9",
              label: "Career K/9",
              value: formatNumber(careerK9, 1),
              rawValue: careerK9,
              status: careerK9 == null ? "missing" : "active",
            }),
            buildRow({
              key: "swstr_pct",
              label: "SwStr %",
              value: formatPercent(swstrPct, 1),
              rawValue: swstrPct,
              status: swstrPct == null ? "missing" : "active",
              note: "Swinging-strike rate",
            }),
            buildRow({
              key: "swstr_delta_k9",
              label: "SwStr Delta / K9",
              value: formatSignedNumber(swstrDeltaK9, 2),
              rawValue: swstrDeltaK9,
              status: swstrDeltaK9 == null ? "missing" : (swstrDeltaK9 === 0 ? "neutral" : "active"),
              tone: toneForDirection(swstrDeltaK9, dir),
            }),
          ],
        },
        {
          key: GROUPS[3].key,
          label: GROUPS[3].label,
          rows: [
            buildRow({
              key: "park_factor",
              label: "Park Factor",
              value: formatNumber(parkFactor, 2),
              rawValue: parkFactor,
              status: parkFactor == null ? "missing" : (parkFactor >= 0.98 && parkFactor <= 1.02 ? "neutral" : "active"),
              tone: parkFactorTone(parkFactor, dir),
              note: "Ballpark run environment",
            }),
            buildRow({
              key: "ump",
              label: "Umpire",
              value: formatUmpire(umpire, umpKAdj),
              rawValue: umpire ?? umpKAdj,
              status: umpStatus(umpire, umpKAdj),
              tone: toneForDirection(umpKAdj, dir),
              note: umpire == null
                ? (umpKAdj == null || umpKAdj === 0 ? "TBA" : "Assigned home plate umpire context")
                : "Home plate umpire context",
            }),
            buildRow({
              key: "lineup",
              label: "Lineup",
              value: lineupUsed ? "Confirmed" : "Projected",
              rawValue: lineupUsed,
              status: lineupStatus(lineupUsed),
              note: lineupUsed ? "Starting lineup confirmed from boxscore" : "Projected lineup only",
            }),
          ],
        },
        {
          key: GROUPS[4].key,
          label: GROUPS[4].label,
          rows: [
            buildRow({
              key: "rest_k9_delta",
              label: "Rest Delta / K9",
              value: formatSignedNumber(restK9Delta, 2),
              rawValue: restK9Delta,
              status: restK9Delta == null ? "missing" : (restK9Delta === 0 ? "neutral" : "active"),
              tone: toneForDirection(restK9Delta, dir),
            }),
            buildRow({
              key: "days_since_last_start",
              label: "Days Since Last Start",
              value: formatDays(daysSinceLastStart),
              rawValue: daysSinceLastStart,
              status: daysSinceLastStart == null ? "missing" : "active",
            }),
            buildRow({
              key: "last_pitch_count",
              label: "Last Pitch Count",
              value: formatPitchCount(lastPitchCount),
              rawValue: lastPitchCount,
              status: lastPitchCount == null ? "missing" : "active",
            }),
          ],
        },
        {
          key: GROUPS[5].key,
          label: GROUPS[5].label,
          rows: [
            buildRow({
              key: "data_complete",
              label: "Data Completeness",
              value: dataComplete ? "Complete" : "Partial",
              rawValue: dataComplete,
              status: dataComplete ? "active" : "missing",
              note: dataComplete ? "All required inputs present" : "One or more inputs missing",
            }),
          ],
        },
      ];
    }

    return {
      buildFactorGroups,
      parkFactorTone,
    };
  },
);
