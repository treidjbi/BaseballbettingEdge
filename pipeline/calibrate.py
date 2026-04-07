"""
calibrate.py
Aggregates pick results into performance.json.
On Phase 1 (n>=30): calibrates lambda_bias and EV thresholds, writes params.json.
On Phase 2 (n>=60): also calibrates ump_scale and blend weights.
Run as part of the 8pm pipeline run only.
"""
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from scipy.stats import pearsonr

log = logging.getLogger(__name__)

DB_PATH           = Path(__file__).parent.parent / "data" / "results.db"
PARAMS_PATH       = Path(__file__).parent.parent / "data" / "params.json"
PERFORMANCE_PATH  = Path(__file__).parent.parent / "dashboard" / "data" / "performance.json"

PHASE1_THRESHOLD  = 30
PHASE2_THRESHOLD  = 60

# Maximum lambda bias shift per calibration run. Prevents a single bad day
# from causing a large overnight swing early in the season (small n). As the
# sample grows the true mean stabilises anyway; this just smooths convergence.
LAMBDA_BIAS_MAX_DELTA = 0.05

DEFAULTS = {
    "ev_thresholds": {"fire2": 0.06, "fire1": 0.03, "lean": 0.01},
    "weight_season_cap": 0.70,
    "weight_recent":     0.20,
    "ump_scale":         1.0,
    "lambda_bias":       0.0,
}

_EV_THRESHOLD_BOUNDS = {
    "fire2": (0.04, 0.10),
    "fire1": (0.02, 0.05),   # max 5% — keeps a meaningful gap below fire2
    "lean":  (0.005, 0.02),  # max 2% — LEAN is a surface-the-edge tier, not calibrated up
}

# LEAN is intentionally excluded from win-rate threshold calibration.
# Its purpose is to surface minor edges for user judgment — penalising it
# for winning would suppress valid signals. Only FIRE tiers are calibrated.
_CALIBRATE_THRESHOLDS = {"FIRE 2u", "FIRE 1u"}

# Minimum picks in the 30-day window before a tier's EV threshold can move.
# Higher bar for FIRE tiers — they require real conviction before adjusting
# since early-season small samples caused FIRE 1u to collapse previously.
_CALIBRATE_MIN_PICKS = {
    "FIRE 2u": 30,
    "FIRE 1u": 30,
}

_VERDICT_TO_THRESHOLD = {
    "FIRE 2u": "fire2",
    "FIRE 1u": "fire1",
    "LEAN":    "lean",
}


def _load_current_params() -> dict:
    try:
        with open(PARAMS_PATH) as f:
            data = json.load(f)
        result = {**DEFAULTS, **data}
        result["ev_thresholds"] = {**DEFAULTS["ev_thresholds"], **data.get("ev_thresholds", {})}
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

    old_ev = old_params.get("ev_thresholds", DEFAULTS["ev_thresholds"])
    new_ev = new_params.get("ev_thresholds", DEFAULTS["ev_thresholds"])
    label_map = {"fire2": "FIRE 2u", "fire1": "FIRE 1u", "lean": "LEAN"}
    for key, label in label_map.items():
        ov = old_ev.get(key, DEFAULTS["ev_thresholds"][key])
        nv = new_ev.get(key, DEFAULTS["ev_thresholds"][key])
        if abs(nv - ov) >= 0.0005:
            direction = "raised" if nv > ov else "lowered"
            reason = "strong recent win rate" if nv > ov else "win rate below expectation"
            notes.append(
                f"{label} EV threshold {direction} {ov*100:.1f}% \u2192 {nv*100:.1f}% ({reason})"
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
    """Calibrate lambda_bias and EV thresholds. Returns updated params dict."""
    params = dict(current_params)
    params["ev_thresholds"] = dict(current_params["ev_thresholds"])

    # Lambda bias — uses raw_lambda as baseline to avoid drift across cycles.
    # Change is capped at ±LAMBDA_BIAS_MAX_DELTA per run so a single bad day
    # can't cause a large overnight swing, especially early in the season.
    lam_pairs = [(r["raw_lambda"], r["actual_ks"]) for r in closed_picks
                 if r["raw_lambda"] is not None and r["actual_ks"] is not None]
    if lam_pairs:
        target_bias = sum(a - p for p, a in lam_pairs) / len(lam_pairs)
        current_bias = current_params.get("lambda_bias", 0.0)
        delta = target_bias - current_bias
        clamped_delta = max(-LAMBDA_BIAS_MAX_DELTA, min(LAMBDA_BIAS_MAX_DELTA, delta))
        params["lambda_bias"] = round(current_bias + clamped_delta, 3)

    # EV threshold adjustment — 30-day rolling window
    cutoff = (datetime.now(pytz.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = [r for r in closed_picks if (r["fetched_at"] or "") >= cutoff]

    by_verdict: dict[str, list] = {}
    for row in recent:
        v = row["verdict"]
        if v not in _VERDICT_TO_THRESHOLD:
            continue
        by_verdict.setdefault(v, []).append(row)

    thresholds = params["ev_thresholds"]
    for verdict, rows in by_verdict.items():
        # LEAN is excluded — it exists to surface minor edges for user judgment,
        # not to be tightened when it's winning. Only FIRE tiers are calibrated.
        if verdict not in _CALIBRATE_THRESHOLDS:
            continue
        if len(rows) < _CALIBRATE_MIN_PICKS.get(verdict, 10):
            continue
        wins  = sum(1 for r in rows if r["result"] == "win")
        total = sum(1 for r in rows if r["result"] in ("win", "loss"))
        if total == 0:
            continue
        observed = wins / total
        implied  = sum(_american_to_implied(r["odds"]) for r in rows) / len(rows)
        key      = _VERDICT_TO_THRESHOLD[verdict]
        lo, hi   = _EV_THRESHOLD_BOUNDS[key]
        current  = thresholds[key]
        if observed > implied + 0.03:
            thresholds[key] = min(hi, round(current + 0.005, 4))
        elif observed < implied - 0.03:
            thresholds[key] = max(lo, round(current - 0.005, 4))

    # Enforce tier ordering: lean < fire1 < fire2 with minimum gaps.
    # Prevents calibration drift from collapsing adjacent tiers.
    thresholds["fire1"] = min(thresholds["fire1"], thresholds["fire2"] - 0.01)
    thresholds["lean"]  = min(thresholds["lean"],  thresholds["fire1"] - 0.005)

    # Clamp lean to its absolute bounds. The calibration loop skips LEAN rows,
    # so without this an existing config with lean=0.03 would never be brought
    # down to the new max of 0.02 — leaving signals suppressed despite this fix.
    _lo, _hi = _EV_THRESHOLD_BOUNDS["lean"]
    thresholds["lean"] = round(max(_lo, min(_hi, thresholds["lean"])), 4)

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
            import math
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


def _load_closed_picks() -> list:
    """Load all closed picks from DB. Returns empty list if DB missing."""
    try:
        conn = _get_db()
        rows = conn.execute("""
            SELECT verdict, side, result, odds, adj_ev, raw_lambda, actual_ks,
                   season_k9, recent_k9, career_k9, ump_k_adj, fetched_at, pnl
            FROM picks
            WHERE result IN ('win','loss','push')
        """).fetchall()
        conn.close()
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
        updated_params["calibration_notes"] = stamped + existing_notes
    else:
        updated_params["calibration_notes"] = existing_notes

    PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PARAMS_PATH, "w") as f:
        json.dump(updated_params, f, indent=2)
    log.info("Wrote params.json (n=%d)", n)

    # Write performance.json with the updated params and notes
    perf = build_performance(closed, current_params=updated_params,
                             calibration_notes=updated_params.get("calibration_notes", []))
    write_performance(perf)
