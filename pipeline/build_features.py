"""
build_features.py
Joins odds, stats, and umpire data. Computes lambda, Poisson EV, verdicts, price deltas.
All functions are pure (no I/O) for testability.
"""
import math
from scipy.stats import poisson


# ── Verdict thresholds ──────────────────────────────────────────────────────
EDGE_PASS         = 0.01
EDGE_LEAN         = 0.03
EDGE_FIRE_1U      = 0.06
EXPECTED_INNINGS  = 5.5        # fallback only — pipeline uses per-pitcher avg IP
LEAGUE_AVG_K_RATE = 0.227
LEAGUE_AVG_SWSTR  = 0.110      # FanGraphs league avg swinging strike rate


def american_to_implied(odds: int) -> float:
    """Convert American odds to implied probability (no vig removed)."""
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def blend_k9(season_k9: float, recent_k9: float, career_k9: float, ip: float) -> float:
    """
    Weighted blend of K/9 rates. Weights shift toward season as IP accumulates.
    Callers must substitute season_k9 for recent_k9 if pitcher has <3 starts,
    and season_k9 for career_k9 if pitcher is a rookie with no MLB career data.
    """
    w_season = min(ip / 60, 0.7)
    w_recent = 0.2
    w_career = 1.0 - w_season - w_recent
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


def calc_lambda(blended_k9: float, expected_innings: float,
                opp_k_rate: float, ump_k_adj: float,
                swstr_mult: float = 1.0) -> float:
    """
    Expected strikeouts (Poisson lambda) for a pitcher start.
    opp_k_rate: opposing team's season batter K% (MLB avg = 0.227)
    ump_k_adj:  career K rate delta for HP umpire (0 if unknown)
    swstr_mult: SwStr% / league_avg_swstr (1.0 = neutral, default)
                Applied to base Ks only — ump adjustment is additive and unscaled.
    """
    base    = blended_k9 * (opp_k_rate / LEAGUE_AVG_K_RATE) * swstr_mult
    ump_add = ump_k_adj * (expected_innings / 9)
    return (base * (expected_innings / 9)) + ump_add


def calc_ev(win_prob: float, odds: int) -> float:
    """EV = win_prob - implied_probability(odds)."""
    return win_prob - american_to_implied(odds)


def calc_verdict(ev: float) -> str:
    """Map EV to a betting verdict string."""
    if ev <= EDGE_PASS:
        return "PASS"
    if ev <= EDGE_LEAN:
        return "LEAN"
    if ev <= EDGE_FIRE_1U:
        return "FIRE 1u"
    return "FIRE 2u"


def calc_price_delta(current_odds: int, opening_odds: int) -> int:
    """
    Juice movement signal. Negative = juice moved toward over (books taking over liability).
    e.g. -110 -> -135 returns -25.
    """
    return current_odds - opening_odds


def build_pitcher_record(odds: dict, stats: dict, ump_k_adj: float) -> dict:
    """
    Joins one pitcher's odds + stats + umpire adj into a complete record.
    Returns the dict that goes into today.json pitchers array.
    """
    ip = stats.get("innings_pitched_season", 0)

    # Apply fallbacks before blending
    season_k9 = stats["season_k9"]
    recent_k9  = stats.get("recent_k9") if stats.get("starts_count", 0) >= 3 else season_k9
    career_k9  = stats.get("career_k9") or season_k9  # rookie fallback

    blended = blend_k9(season_k9, recent_k9, career_k9, ip)
    lam = calc_lambda(blended, EXPECTED_INNINGS, stats["opp_k_rate"], ump_k_adj)

    k_line = odds["k_line"]
    # P(K > k_line) = P(K >= ceil(k_line)) = 1 - P(K <= floor(k_line))
    win_prob_over  = 1 - poisson.cdf(math.floor(k_line), lam)
    win_prob_under = 1 - win_prob_over

    best_over_odds  = odds["best_over_odds"]
    best_under_odds = odds["best_under_odds"]
    ev_over  = calc_ev(win_prob_over,  best_over_odds)
    ev_under = calc_ev(win_prob_under, best_under_odds)

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
        "price_delta_over":   calc_price_delta(best_over_odds,  odds["opening_over_odds"]),
        "price_delta_under":  calc_price_delta(best_under_odds, odds["opening_under_odds"]),
        "lambda":             round(lam, 2),
        "opp_k_rate":         stats["opp_k_rate"],
        "ump_k_adj":          ump_k_adj,
        "ev_over":  {"ev": round(ev_over, 4),  "verdict": calc_verdict(ev_over),  "win_prob": round(win_prob_over, 3)},
        "ev_under": {"ev": round(ev_under, 4), "verdict": calc_verdict(ev_under), "win_prob": round(win_prob_under, 3)},
    }
