"""
build_features.py
Joins odds, stats, and umpire data. Computes lambda, Poisson EV, verdicts, price deltas.
load_params() reads data/params.json for calibrated parameters (safe I/O with fallback).
All other functions are pure (no I/O) for testability.
"""
import math
import json
from pathlib import Path
from scipy.stats import poisson

PARAMS_PATH = str(Path(__file__).parent.parent / "data" / "params.json")

DEFAULTS = {
    "ev_thresholds": {"fire2": 0.06, "fire1": 0.03, "lean": 0.01},
    "weight_season_cap": 0.70,
    "weight_recent": 0.20,
    "ump_scale": 1.0,
    "lambda_bias": 0.0,
}

def load_params() -> dict:
    try:
        with open(PARAMS_PATH) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(DEFAULTS)

    result = {**DEFAULTS, **data}
    # Deep merge nested ev_thresholds so partial files don't drop keys
    result["ev_thresholds"] = {**DEFAULTS["ev_thresholds"], **data.get("ev_thresholds", {})}
    return result


# ── Verdict thresholds ──────────────────────────────────────────────────────
EDGE_PASS         = 0.01
EDGE_LEAN         = 0.03
EDGE_FIRE_1U      = 0.06
EXPECTED_INNINGS  = 5.5        # fallback only — pipeline uses per-pitcher avg IP
LEAGUE_AVG_K_RATE = 0.227
LEAGUE_AVG_SWSTR  = 0.110      # FanGraphs league avg swinging strike rate
STEAM_DISPLAY_THRESHOLD = 0.75  # show ↓steam label when confidence ≤ this value (delta ≥ 15 pts)
OPP_K_PRIOR_GAMES       = 50   # Bayesian prior: how many games league average is "worth"


def american_to_implied(odds: int) -> float:
    """Convert American odds to implied probability (no vig removed)."""
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def blend_k9(season_k9: float, recent_k9: float, career_k9: float, ip: float,
             weight_season_cap: float = 0.70, weight_recent: float = 0.20) -> float:
    """
    Weighted blend of K/9 rates. Weights shift toward season as IP accumulates.
    Callers must substitute season_k9 for recent_k9 if pitcher has <3 starts,
    and season_k9 for career_k9 if pitcher is a rookie with no MLB career data.
    """
    w_season = min(ip / 60, weight_season_cap)
    w_recent = weight_recent
    w_career = max(0.0, 1.0 - w_season - w_recent)
    return (w_season * season_k9) + (w_recent * recent_k9) + (w_career * career_k9)


def calc_swstr_mult(swstr_pct: float) -> float:
    """
    Multiplier on blended_k9 based on SwStr% relative to league average.
    A pitcher at 14% SwStr% (vs 11% avg) gets a 1.27x boost on expected Ks.
    Returns 1.0 (neutral) if swstr_pct is zero or missing.
    """
    if not swstr_pct:
        return 1.0
    return swstr_pct / LEAGUE_AVG_SWSTR


def bayesian_opp_k(obs_k_rate: float, opp_games_played: int,
                   league_avg: float = LEAGUE_AVG_K_RATE,
                   prior: int = OPP_K_PRIOR_GAMES) -> float:
    """
    Regress observed opponent K% toward league average weighted by sample size.

    Early season (8 games, prior=50): extreme rates barely move the needle.
    Mid-season (~81 games): observed data is ~62% of the blend.
    Full season (162 games): observed data is ~76% of the blend.

    opp_games_played=0 → returns league average (safe default, full regression).
    """
    if opp_games_played <= 0:
        return league_avg
    return (opp_games_played * obs_k_rate + prior * league_avg) / (opp_games_played + prior)


def calc_lambda(blended_k9: float, expected_innings: float,
                opp_k_rate: float, ump_k_adj: float,
                swstr_mult: float = 1.0,
                opp_games_played: int = 0) -> float:
    """
    Expected strikeouts (Poisson lambda) for a pitcher start.
    opp_k_rate:       opposing team's season batter K% (MLB avg = 0.227)
    ump_k_adj:        career K rate delta for HP umpire (0 if unknown)
    swstr_mult:       SwStr% / league_avg_swstr (1.0 = neutral, default)
                      Applied to base Ks only — ump adjustment is additive and unscaled.
    opp_games_played: games the opposing team has played this season. Used to
                      Bayesian-regress opp_k_rate toward league average early in season.
                      Defaults to 0 → full regression to league average (safe early-season default).
    """
    adj_opp_k = bayesian_opp_k(opp_k_rate, opp_games_played)
    base    = blended_k9 * (adj_opp_k / LEAGUE_AVG_K_RATE) * swstr_mult
    ump_add = ump_k_adj * (expected_innings / 9)
    return (base * (expected_innings / 9)) + ump_add


def calc_ev(win_prob: float, odds: int) -> float:
    """EV = win_prob - implied_probability(odds)."""
    return win_prob - american_to_implied(odds)


def calc_verdict(ev: float, thresholds: dict | None = None) -> str:
    """Map EV to a betting verdict string."""
    t = thresholds or {"lean": EDGE_PASS, "fire1": EDGE_LEAN, "fire2": EDGE_FIRE_1U}
    if ev <= t["lean"]:
        return "PASS"
    if ev <= t["fire1"]:
        return "LEAN"
    if ev <= t["fire2"]:
        return "FIRE 1u"
    return "FIRE 2u"


def calc_price_delta(current_odds: int, opening_odds: int) -> int:
    """
    Juice movement signal. Negative = juice moved toward over (books taking over liability).
    e.g. -110 -> -135 returns -25.
    """
    return current_odds - opening_odds


def calc_movement_confidence(delta: int,
                              noise_floor: int = 10,
                              full_fade:   int = 30) -> float:
    """
    Returns a confidence multiplier (0.0–1.0) based on line movement against the bet side.

    delta > 0  : that side got cheaper (sharp money on the other side) → penalty applied.
    delta <= 0 : movement in our favour or no movement → no penalty (returns 1.0).

    Linear decay from 1.0 at noise_floor to 0.0 at full_fade.
    Movements below noise_floor are treated as routine book adjustments (ignored).
    """
    if delta <= noise_floor:
        return 1.0
    if delta >= full_fade:
        return 0.0
    return 1.0 - (delta - noise_floor) / (full_fade - noise_floor)


def build_pitcher_record(odds: dict, stats: dict, ump_k_adj: float,
                         swstr_pct: float = LEAGUE_AVG_SWSTR) -> dict:
    """
    Joins one pitcher's odds + stats + umpire adj into a complete record.
    Returns the dict that goes into today.json pitchers array.

    swstr_pct: pitcher's swinging strike rate (decimal, e.g. 0.134).
               Defaults to league average (neutral multiplier = 1.0).
    """
    params = load_params()
    thresholds = params["ev_thresholds"]

    ip     = stats.get("innings_pitched_season", 0)
    avg_ip = stats.get("avg_ip_last5", EXPECTED_INNINGS)

    season_k9 = stats["season_k9"]
    recent_k9 = stats.get("recent_k9") if stats.get("starts_count", 0) >= 3 else season_k9
    career_k9 = stats.get("career_k9") or season_k9

    blended    = blend_k9(season_k9, recent_k9, career_k9, ip,
                          weight_season_cap=params["weight_season_cap"],
                          weight_recent=params["weight_recent"])
    swstr_mult = calc_swstr_mult(swstr_pct)
    opp_games  = stats.get("opp_games_played", 0)

    scaled_ump_k_adj = ump_k_adj * params["ump_scale"]
    raw_lam = calc_lambda(blended, avg_ip, stats["opp_k_rate"], scaled_ump_k_adj,
                          swstr_mult, opp_games_played=opp_games)
    applied_lam = raw_lam + params["lambda_bias"]
    applied_lam = max(0.01, applied_lam)  # guard against negative bias producing invalid Poisson lambda

    k_line = odds["k_line"]
    win_prob_over  = 1 - poisson.cdf(math.floor(k_line), applied_lam)
    win_prob_under = 1 - win_prob_over

    best_over_odds  = odds["best_over_odds"]
    best_under_odds = odds["best_under_odds"]
    ev_over  = calc_ev(win_prob_over,  best_over_odds)
    ev_under = calc_ev(win_prob_under, best_under_odds)

    price_delta_over  = calc_price_delta(best_over_odds,  odds.get("opening_over_odds",  best_over_odds))
    price_delta_under = calc_price_delta(best_under_odds, odds.get("opening_under_odds", best_under_odds))

    conf_over  = calc_movement_confidence(price_delta_over)
    conf_under = calc_movement_confidence(price_delta_under)
    adj_ev_over  = ev_over  * conf_over
    adj_ev_under = ev_under * conf_under

    return {
        "pitcher":            odds["pitcher"],
        "team":               odds["team"],
        "opp_team":           odds["opp_team"],
        "game_time":          odds["game_time"],
        "k_line":             k_line,
        "opening_line":       odds.get("opening_line", k_line),
        "best_over_book":     odds["best_over_book"],
        "best_over_odds":     best_over_odds,
        "best_under_odds":    best_under_odds,
        "opening_over_odds":  odds["opening_over_odds"],
        "opening_under_odds": odds["opening_under_odds"],
        "price_delta_over":   price_delta_over,
        "price_delta_under":  price_delta_under,
        "raw_lambda":         round(raw_lam, 2),
        "lambda":             round(applied_lam, 2),
        "avg_ip":             avg_ip,
        "swstr_pct":          round(swstr_pct, 4),
        "opp_k_rate":         stats["opp_k_rate"],
        "ump_k_adj":          ump_k_adj,
        "season_k9":          round(season_k9, 2),
        "recent_k9":          round(recent_k9, 2),
        "career_k9":          round(career_k9, 2),
        "ev_over":  {
            "ev":            round(ev_over,      4),
            "adj_ev":        round(adj_ev_over,  4),
            "verdict":       calc_verdict(adj_ev_over,  thresholds),
            "win_prob":      round(win_prob_over,  3),
            "movement_conf": round(conf_over,    4),
        },
        "ev_under": {
            "ev":            round(ev_under,      4),
            "adj_ev":        round(adj_ev_under,  4),
            "verdict":       calc_verdict(adj_ev_under, thresholds),
            "win_prob":      round(win_prob_under,  3),
            "movement_conf": round(conf_under,    4),
        },
    }
