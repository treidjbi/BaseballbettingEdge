"""
calibrate.py
Aggregates pick results into performance.json.
On Phase 1 (n>=30): calibrates lambda_bias and EV thresholds, writes params.json.
On Phase 2 (n>=60): also calibrates ump_scale and blend weights.
Run as part of the 8pm pipeline run only.
"""
import json
import logging
import math
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from scipy.stats import pearsonr

log = logging.getLogger(__name__)

DB_PATH           = Path(__file__).parent.parent / "data" / "results.db"
PARAMS_PATH       = Path(__file__).parent.parent / "data" / "params.json"
PERFORMANCE_PATH  = Path(__file__).parent.parent / "dashboard" / "data" / "performance.json"

PHASE1_THRESHOLD       = 30
PHASE2_THRESHOLD       = 60
SWSTR_SCALE_THRESHOLD  = 100

# Adaptive lambda bias step size: scales with sqrt(n / LAMBDA_BIAS_SCALE_N).
# At n=30 (phase 1 floor): max step = 0.05 — cautious, sample is small.
# At n=100: max step = ~0.09 — faster convergence as estimate stabilises.
# At n=252: max step = ~0.14 — near-immediate convergence for reliable estimates.
# Hard ceiling at 0.15 to prevent any single run from overcorrecting.
LAMBDA_BIAS_BASE_DELTA = 0.05
LAMBDA_BIAS_SCALE_N    = 30
LAMBDA_BIAS_MAX_DELTA  = 0.15  # hard ceiling regardless of n

DEFAULTS = {
    "weight_season_cap": 0.70,
    "weight_recent":     0.20,
    "ump_scale":         1.0,
    "lambda_bias":       0.0,
    "swstr_k9_scale":    30.0,
}


def _load_current_params() -> dict:
    try:
        with open(PARAMS_PATH) as f:
            data = json.load(f)
        result = {**DEFAULTS, **data}
        return result
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _american_to_implied(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


_ROW_ORDER = [
    ("FIRE 2u", "over"),
    ("FIRE 2u", "under"),
    ("FIRE 1u", "over"),
    ("FIRE 1u", "under"),
    ("LEAN",    "over"),
    ("LEAN",    "under"),
]


def build_calibration_notes(old_params: dict, new_params: dict) -> list[str]:
    """Generate human-readable notes describing what changed during calibration."""
    notes = []

    old_bias = old_params.get("lambda_bias", 0.0)
    new_bias = new_params.get("lambda_bias", 0.0)
    if abs(new_bias - old_bias) >= 0.005:
        direction = "under" if new_bias > 0 else "over"
        notes.append(
            f"Lambda bias adjusted {old_bias:+.3f} \u2192 {new_bias:+.3f} "
            f"(model was systematically {direction}-predicting Ks)"
        )

    old_ump = old_params.get("ump_scale", 1.0)
    new_ump = new_params.get("ump_scale", 1.0)
    if abs(new_ump - old_ump) >= 0.005:
        direction = "increased" if new_ump > old_ump else "decreased"
        reason = "umpire adjustment correlates positively with outcomes" if new_ump > old_ump else "umpire adjustment not reliably predictive"
        notes.append(
            f"Umpire scale {direction} {old_ump:.3f} \u2192 {new_ump:.3f} ({reason})"
        )

    old_ws = old_params.get("weight_season_cap", DEFAULTS["weight_season_cap"])
    new_ws = new_params.get("weight_season_cap", DEFAULTS["weight_season_cap"])
    old_wr = old_params.get("weight_recent", DEFAULTS["weight_recent"])
    new_wr = new_params.get("weight_recent", DEFAULTS["weight_recent"])
    if abs(new_ws - old_ws) >= 0.005 or abs(new_wr - old_wr) >= 0.005:
        notes.append(
            f"K/9 blend weights updated: season {old_ws*100:.0f}% \u2192 {new_ws*100:.0f}%, "
            f"recent {old_wr*100:.0f}% \u2192 {new_wr*100:.0f}%"
        )

    old_swstr_scale = old_params.get("swstr_k9_scale", DEFAULTS.get("swstr_k9_scale", 30.0))
    new_swstr_scale = new_params.get("swstr_k9_scale", DEFAULTS.get("swstr_k9_scale", 30.0))
    if abs(new_swstr_scale - old_swstr_scale) >= 0.5:
        direction = "increased" if new_swstr_scale > old_swstr_scale else "decreased"
        reason = ("SwStr%% delta correlates positively with K outcomes"
                  if new_swstr_scale > old_swstr_scale
                  else "SwStr%% delta not reliably predictive of K outcomes")
        notes.append(
            f"SwStr%% K/9 scale {direction} {old_swstr_scale:.1f} \u2192 {new_swstr_scale:.1f} ({reason})"
        )

    return notes


def build_performance(closed: list, current_params: dict | None = None,
                      calibration_notes: list[str] | None = None) -> dict:
    """Aggregate closed picks into a performance dict. Pure function (no I/O)."""
    total = len(closed)
    buckets: dict[tuple, dict] = {}

    for row in closed:
        v = row["verdict"]
        if v == "PASS":
            continue
        s = row["side"]
        key = (v, s)
        if key not in buckets:
            buckets[key] = {"picks": 0, "wins": 0, "losses": 0, "pushes": 0,
                            "total_pnl": 0.0, "sum_ev": 0.0}
        b = buckets[key]
        b["picks"]     += 1
        b["total_pnl"] += row["pnl"] or 0.0
        b["sum_ev"]    += row["adj_ev"] or 0.0
        if row["result"] == "win":    b["wins"]   += 1
        elif row["result"] == "loss": b["losses"] += 1
        elif row["result"] == "push": b["pushes"] += 1

    rows = []
    for (v, s) in _ROW_ORDER:
        b = buckets.get((v, s), {"picks": 0, "wins": 0, "losses": 0,
                                  "pushes": 0, "total_pnl": 0.0, "sum_ev": 0.0})
        picks    = b["picks"]
        wl       = b["wins"] + b["losses"]
        win_pct  = round(b["wins"] / wl, 3) if wl else None
        roi      = round((b["total_pnl"] / picks) * 100, 2) if picks else None
        avg_ev   = round(b["sum_ev"] / picks, 4) if picks else None
        rows.append({
            "verdict":  v,
            "side":     s,
            "picks":    picks,
            "wins":     b["wins"],
            "losses":   b["losses"],
            "pushes":   b["pushes"],
            "win_pct":  win_pct,
            "roi":      roi,
            "avg_ev":   avg_ev,
        })

    lam_rows = [(r["raw_lambda"], r["actual_ks"]) for r in closed
                if r["raw_lambda"] is not None and r["actual_ks"] is not None]
    if lam_rows:
        avg_pred   = sum(r[0] for r in lam_rows) / len(lam_rows)
        avg_actual = sum(r[1] for r in lam_rows) / len(lam_rows)
        lam_acc = {
            "avg_predicted": round(avg_pred, 2),
            "avg_actual":    round(avg_actual, 2),
            "bias":          round(avg_actual - avg_pred, 2),
        }
    else:
        lam_acc = {"avg_predicted": None, "avg_actual": None, "bias": None}

    # Use passed params instead of reading from disk
    params = current_params or {}
    last_cal = params.get("updated_at")
    cal_n    = params.get("sample_size", 0) if last_cal else None

    return {
        "generated_at":        datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_picks":         total,
        "last_calibrated":     last_cal,
        "calibration_sample":  cal_n,
        "rows":                rows,
        "lambda_accuracy":     lam_acc,
        "params":              params if last_cal else None,
        "calibration_notes":   calibration_notes or [],
    }


def write_performance(perf: dict) -> None:
    PERFORMANCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PERFORMANCE_PATH, "w") as f:
        json.dump(perf, f, indent=2)
    log.info("Wrote performance.json (%d total picks)", perf["total_picks"])


def _calibrate_phase1(closed_picks: list, current_params: dict) -> dict:
    """Calibrate lambda_bias only. EV thresholds are static. Returns updated params dict."""
    params = dict(current_params)

    # Lambda bias — uses raw_lambda as baseline to avoid drift across cycles.
    # Step size scales with sqrt(n / LAMBDA_BIAS_SCALE_N): cautious early in the
    # season when sample is small, converges faster mid-season when the mean is stable.
    lam_pairs = [(r["raw_lambda"], r["actual_ks"]) for r in closed_picks
                 if r["raw_lambda"] is not None and r["actual_ks"] is not None]
    if lam_pairs:
        n            = len(lam_pairs)
        target_bias  = sum(a - p for p, a in lam_pairs) / n
        current_bias = current_params.get("lambda_bias", 0.0)
        delta        = target_bias - current_bias
        adaptive_cap = min(LAMBDA_BIAS_MAX_DELTA,
                           LAMBDA_BIAS_BASE_DELTA * math.sqrt(n / LAMBDA_BIAS_SCALE_N))
        if abs(delta) <= adaptive_cap:
            params["lambda_bias"] = round(target_bias, 3)
        else:
            step = adaptive_cap if delta > 0 else -adaptive_cap
            params["lambda_bias"] = round(current_bias + step, 3)
        log.info("Lambda bias: target=%.3f current=%.3f adaptive_cap=%.3f (n=%d)",
                 target_bias, current_bias, adaptive_cap, n)

    return params


def _calibrate_phase2(closed_picks: list, current_params: dict) -> dict:
    """Calibrate ump_scale and blend weights. Returns updated params dict."""
    params = dict(current_params)

    # Ump scale: Pearson correlation between ump_k_adj and residual
    ump_data = [(r["ump_k_adj"], r["actual_ks"] - r["raw_lambda"])
                for r in closed_picks
                if r["ump_k_adj"] is not None and r["raw_lambda"] is not None
                and r["actual_ks"] is not None]

    if len(ump_data) >= 60:
        umps   = [d[0] for d in ump_data]
        resids = [d[1] for d in ump_data]
        if len(set(umps)) > 1:
            corr, _ = pearsonr(umps, resids)
            current_scale = params.get("ump_scale", 1.0)
            if not math.isnan(corr) and corr > 0.15:
                # Strong positive correlation: ump adjustment is predictive — increase weight
                params["ump_scale"] = round(max(0.0, min(1.5, current_scale + 0.05)), 3)
            elif math.isnan(corr) or abs(corr) < 0.05:
                # Near-zero or undefined correlation: ump adjustment not predictive — decrease weight
                params["ump_scale"] = round(max(0.0, min(1.5, current_scale - 0.05)), 3)
            elif corr < -0.15:
                # Strong negative correlation: ump adjustment predicts wrong direction — decrease weight
                params["ump_scale"] = round(max(0.0, min(1.5, current_scale - 0.05)), 3)
            # Between -0.15 and -0.05, or 0.05 and 0.15: leave scale unchanged

    # SwStr% K/9 scale: Pearson correlation between swstr_delta contribution and residual.
    # Requires n>=100 so the SwStr% delta has enough variety to measure signal.
    # swstr_delta_k9 stored in picks is the post-dampened K/9 delta (before avg_ip scaling).
    # We multiply by avg_ip/9 to approximate the lambda contribution for this pick.
    if len(closed_picks) >= SWSTR_SCALE_THRESHOLD:
        swstr_data = [
            (r["swstr_delta_k9"] * (r["avg_ip"] / 9.0),
             r["actual_ks"] - r["raw_lambda"])
            for r in closed_picks
            if r["swstr_delta_k9"] is not None
            and r["avg_ip"] is not None
            and r["raw_lambda"] is not None
            and r["actual_ks"] is not None
        ]
        if len(swstr_data) >= SWSTR_SCALE_THRESHOLD:
            contribs = [d[0] for d in swstr_data]
            resids   = [d[1] for d in swstr_data]
            if len(set(contribs)) > 1:  # need variance to compute correlation
                corr, _ = pearsonr(contribs, resids)
                current_scale = params.get("swstr_k9_scale", 30.0)
                if not math.isnan(corr) and corr > 0.15:
                    # Delta predicts more Ks than model gives credit for — increase scale
                    params["swstr_k9_scale"] = round(max(5.0, min(60.0, current_scale + 2.0)), 1)
                    log.info("swstr_k9_scale: corr=%.3f → increasing %.1f to %.1f (n=%d)",
                             corr, current_scale, params["swstr_k9_scale"], len(swstr_data))
                elif math.isnan(corr) or abs(corr) < 0.05:
                    # Near-zero or undefined correlation — delta not adding signal, reduce
                    params["swstr_k9_scale"] = round(max(5.0, min(60.0, current_scale - 2.0)), 1)
                    log.info("swstr_k9_scale: corr=%.3f → decreasing %.1f to %.1f (n=%d)",
                             corr, current_scale, params["swstr_k9_scale"], len(swstr_data))
                elif corr < -0.15:
                    # Negative correlation — delta predicting wrong direction, reduce
                    params["swstr_k9_scale"] = round(max(5.0, min(60.0, current_scale - 2.0)), 1)
                    log.info("swstr_k9_scale: corr=%.3f → decreasing %.1f to %.1f (n=%d)",
                             corr, current_scale, params["swstr_k9_scale"], len(swstr_data))
                else:
                    # Between -0.15 and 0.15: leave scale unchanged
                    log.info("swstr_k9_scale: corr=%.3f → no change (scale=%.1f, n=%d)",
                             corr, current_scale, len(swstr_data))

    # Blend weights: linear regression on k9 components
    blend_data = [(r["season_k9"], r["recent_k9"], r["career_k9"], r["actual_ks"])
                  for r in closed_picks
                  if all(r[k] is not None for k in ("season_k9", "recent_k9", "career_k9", "actual_ks"))]

    if len(blend_data) >= 60:
        try:
            import numpy as np
            from scipy.optimize import nnls
            X = np.array([[d[0], d[1], d[2]] for d in blend_data])
            y = np.array([d[3] for d in blend_data], dtype=float)

            # Normalize each feature column to mean=1 for unit-consistent regression
            col_means = X.mean(axis=0)
            col_means[col_means == 0] = 1.0
            X_norm = X / col_means

            # Also normalize y to mean=1 so coefficients are in comparable units
            y_mean = y.mean() if y.mean() != 0 else 1.0
            y_norm = y / y_mean

            coeffs, _ = nnls(X_norm, y_norm)
            total = coeffs.sum()
            if total > 0:
                w = coeffs / total          # normalize to sum=1
                w = [max(0.05, wi) for wi in w]  # floor each weight at 5%
                w_total = sum(w)
                w = [wi / w_total for wi in w]   # renormalize after floor
                params["weight_season_cap"] = round(min(0.85, max(0.40, w[0])), 3)
                params["weight_recent"]     = round(min(0.40, max(0.05, w[1])), 3)
        except Exception as e:
            log.warning("Blend weight regression failed: %s — keeping current weights", e)

    return params


def _current_season_start() -> str:
    """Returns the season start date floor (March 1 of the current calendar year)."""
    return f"{datetime.now().year}-03-01"


def _calibration_cutoff() -> str:
    """Returns the effective calibration cutoff date.

    Uses the later of (a) March 1 of the current season and (b) any
    formula_change_date stored in params.json.  Picks before a formula change
    were generated by a different model and should not contaminate calibration
    of the new formula — they are kept in picks_history.json for reference and
    per-pitcher dashboard display but excluded from bias/scale estimation.
    """
    season_start = _current_season_start()
    try:
        with open(PARAMS_PATH) as f:
            params = json.load(f)
        fcd = params.get("formula_change_date", "")
        if fcd and fcd > season_start:
            log.info("Calibration cutoff: formula_change_date %s (later than season start %s)",
                     fcd, season_start)
            return fcd
    except Exception:
        pass
    return season_start


def _load_closed_picks() -> list:
    """Load current-season closed picks from DB. Returns empty list if DB missing.

    Filtered to the effective calibration cutoff (the later of March 1 and any
    formula_change_date) so picks graded under a different formula don't distort
    calibration. Old picks remain in picks_history.json for reference.
    """
    cutoff = _calibration_cutoff()
    try:
        conn = _get_db()
        rows = conn.execute("""
            SELECT verdict, side, result, odds,
                   COALESCE(locked_adj_ev, adj_ev) AS adj_ev,
                   raw_lambda, actual_ks,
                   season_k9, recent_k9, career_k9, avg_ip, ump_k_adj,
                   swstr_delta_k9, fetched_at, pnl
            FROM picks
            WHERE result IN ('win','loss','push')
              AND date >= ?
        """, (cutoff,)).fetchall()
        conn.close()
        log.info("Loaded %d closed picks since %s", len(rows), cutoff)
        return rows
    except Exception as e:
        log.error("Could not load picks for calibration: %s", e)
        return []


def run() -> None:
    """Main entry point. Always writes performance.json. Writes params.json when n>=30."""
    closed = _load_closed_picks()
    n = len(closed)

    current_params = _load_current_params()
    log.info("Calibration: %d closed picks", n)

    if n < PHASE1_THRESHOLD:
        log.info("Below Phase 1 threshold (%d), skipping calibration", PHASE1_THRESHOLD)
        perf = build_performance(closed, current_params=current_params)
        write_performance(perf)
        return

    updated_params = _calibrate_phase1(closed, current_params)

    if n >= PHASE2_THRESHOLD:
        updated_params = _calibrate_phase2(closed, updated_params)

    updated_params["updated_at"]  = datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated_params["sample_size"] = n

    # Generate notes describing what changed, then persist in params.json
    notes = build_calibration_notes(current_params, updated_params)
    if notes:
        log.info("Calibration changes: %s", "; ".join(notes))
    # Carry forward any existing notes, prepend new ones with timestamp
    existing_notes = current_params.get("calibration_notes", [])
    if notes:
        timestamp = datetime.now(pytz.utc).strftime("%Y-%m-%d")
        stamped = [f"[{timestamp}] {note}" for note in notes]
        updated_params["calibration_notes"] = (stamped + existing_notes)[:50]
    else:
        updated_params["calibration_notes"] = existing_notes[:50]

    PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PARAMS_PATH, "w") as f:
        json.dump(updated_params, f, indent=2)
    log.info("Wrote params.json (n=%d)", n)

    # Write performance.json with the updated params and notes
    perf = build_performance(closed, current_params=updated_params,
                             calibration_notes=updated_params.get("calibration_notes", []))
    write_performance(perf)
