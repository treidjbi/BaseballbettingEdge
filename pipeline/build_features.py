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
from name_utils import normalize as _norm

PARAMS_PATH = str(Path(__file__).parent.parent / "data" / "params.json")

DEFAULTS = {
    "weight_season_cap": 0.70,
    "weight_recent": 0.20,
    "ump_scale": 1.0,
    "lambda_bias": 0.0,
    "swstr_k9_scale": 30.0,
    "opp_k_prior_games": 50,   # Bayesian prior weight on opponent K% (games of league avg)
    "swstr_prior_starts": 10,  # Bayesian prior weight on SwStr% delta (starts of career avg)
}

def load_params() -> dict:
    try:
        with open(PARAMS_PATH) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(DEFAULTS)

    result = {**DEFAULTS, **data}
    return result


# ── Verdict thresholds ──────────────────────────────────────────────────────
EDGE_PASS         = 0.02   # EV ROI < 2% → PASS
EDGE_LEAN         = 0.06   # EV ROI 2–6% → LEAN
EDGE_FIRE_1U      = 0.17   # EV ROI 6–17% → FIRE 1u, >17% → FIRE 2u
EXPECTED_INNINGS  = 5.5        # fallback only — pipeline uses per-pitcher avg IP
LEAGUE_AVG_K_RATE = 0.227
LEAGUE_AVG_SWSTR  = 0.110      # FanGraphs league avg swinging strike rate
STEAM_DISPLAY_THRESHOLD = 0.75  # show ↓steam label when confidence ≤ this value (delta ≥ 15 pts)
OPP_K_PRIOR_GAMES       = 50   # Bayesian prior: how many games league average is "worth"
OPENER_MEAN_IP_THRESHOLD = 2.5
OPENER_MIN_STARTS = 2
OPENER_NOTE = "Opener/bullpen game — K props unreliable; forced to PASS."

# SwStr% delta → K/9 conversion factor. Each 0.01 (1 percentage point) of SwStr%
# above/below the pitcher's career norm adjusts blended K/9 by this many runs.
# This constant is only a fallback default; the live value is calibrated each
# run and loaded from params.json (see calibrate.py::_calibrate_phase2).
SWSTR_K9_SCALE   = 30.0

# League-average platoon K% deltas (additive, rate points) applied on top of a
# batter's K% based on the (batter_hand, pitcher_throws) matchup. Values reflect
# multi-season MLB aggregate splits. Switch-hitters ("S") are modeled as batting
# opposite the pitcher's hand (standard convention).
#
# Path A stopgap: until per-batter vs-L/vs-R samples stabilize mid-season and
# fetch_batter_stats._fetch_splits is implemented, this captures the platoon
# signal at the league level. See CLAUDE.md "Batter Handedness Upgrade" reminder.
PLATOON_K_DELTA = {
    ("R", "R"): 0.005,   # RHB vs RHP: slight same-hand K bump
    ("R", "L"): -0.010,  # RHB vs LHP: platoon advantage
    ("L", "R"): -0.015,  # LHB vs RHP: strong platoon advantage
    ("L", "L"): 0.020,   # LHB vs LHP: reverse platoon (rare PA, stark split)
}


def platoon_k_delta(batter_hand: str, pitcher_throws: str) -> float:
    """
    League-average K% adjustment for a (batter_hand, pitcher_throws) matchup.

    Switch-hitters ("S") are modeled as batting opposite the pitcher's hand.
    Missing or unknown handedness returns 0.0 (neutral).
    """
    if batter_hand == "S":
        batter_hand = "L" if pitcher_throws == "R" else "R"
    return PLATOON_K_DELTA.get((batter_hand, pitcher_throws), 0.0)
# Bayesian prior starts: treat n starts of current-season SwStr% as reliable only
# after this many starts. At 3 starts (early season) the delta is ~23% weighted;
# at 10 starts it is 50%; at 20 starts it is 67%.
SWSTR_PRIOR_STARTS = 10


def american_to_implied(odds: int) -> float:
    """Convert American odds to implied probability (no vig removed)."""
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def american_to_profit_per_unit(odds: int) -> float:
    """Profit on a 1.0u stake when the bet wins."""
    if odds > 0:
        return odds / 100
    return 100 / abs(odds)


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
    w_total = w_season + w_recent + w_career
    w_season /= w_total
    w_recent /= w_total
    w_career /= w_total
    return (w_season * season_k9) + (w_recent * recent_k9) + (w_career * career_k9)


def calc_swstr_delta_k9(current_swstr: float, career_swstr: float | None,
                        n_starts: int, swstr_k9_scale: float = SWSTR_K9_SCALE,
                        swstr_prior_starts: int = SWSTR_PRIOR_STARTS) -> float:
    """
    Additive K/9 adjustment based on how the pitcher's current SwStr% compares to
    their career baseline. Replaces the old raw-vs-league-average multiplier which
    double-counted swing-and-miss ability already captured in K/9 rates.

    Returns 0.0 (no adjustment) when:
      - career_swstr is None (rookie or data unavailable)
      - current_swstr is missing/zero
      - n_starts is 0

    Bayesian dampening: early in the season (few starts) the delta is shrunk toward
    zero because the current-season SwStr% sample is small and noisy.

    Examples (swstr_k9_scale=30):
      Pitcher at 13% vs 11% career (+2pp delta):  +0.60 K/9 (fully undampened)
      Same pitcher after 3 starts:                +0.14 K/9 (~23% weight at 3/(3+10))
      After 10 starts:                            +0.30 K/9 (50% weight)
    """
    if current_swstr is None or career_swstr is None or n_starts <= 0:
        return 0.0
    raw_delta_k9 = (current_swstr - career_swstr) * swstr_k9_scale
    weight = n_starts / (n_starts + swstr_prior_starts)
    return raw_delta_k9 * weight


def calc_rest_k9_delta(days_since_last: int | None, last_pitch_count: int | None) -> float:
    """
    Conservative additive K/9 penalty for short rest / heavy prior workload.

    Missing data stays neutral. Penalties stack when both conditions fire.
    """
    delta = 0.0
    if days_since_last is not None and days_since_last < 4:
        delta -= 0.3
    if last_pitch_count is not None and last_pitch_count > 110:
        delta -= 0.2
    return delta


def calc_lineup_k_rate(
    lineup: list[dict] | None,
    batter_stats: dict,
    pitcher_throws: str,
) -> float | None:
    """
    Compute the mean K rate for a batting lineup against a given pitcher handedness.

    Applies a league-average platoon K% delta per batter based on the
    (batter_hand, pitcher_throws) matchup. See platoon_k_delta().

    Returns the unregressed raw mean — do NOT Bayesian-regress here.
    calc_lambda() applies bayesian_opp_k() to whatever rate it receives.

    Returns None when lineup is None or empty (caller falls back to team K%).
    Unknown batters use LEAGUE_AVG_K_RATE as the base rate; platoon delta is
    still applied when the batter's handedness is known.

    lineup:         list of {"name": str, "bats": str} dicts
    batter_stats:   {name: {"vs_R": float, "vs_L": float}} from fetch_batter_stats
    pitcher_throws: "R" or "L"
    """
    if not lineup:
        return None
    split_key = "vs_R" if pitcher_throws == "R" else "vs_L"
    rates = []
    for batter in lineup:
        name = batter.get("name", "")
        batter_hand = batter.get("bats", "")
        splits = batter_stats.get(_norm(name))
        base_k = splits[split_key] if splits else LEAGUE_AVG_K_RATE
        rates.append(base_k + platoon_k_delta(batter_hand, pitcher_throws))
    return sum(rates) / len(rates)


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
                swstr_delta_k9: float = 0.0,
                opp_games_played: int = 0,
                opp_k_prior: int = OPP_K_PRIOR_GAMES,
                park_factor: float = 1.0) -> float:
    """
    Expected strikeouts (Poisson lambda) for a pitcher start.

    blended_k9:     weighted blend of season/recent/career K/9 rates
    opp_k_rate:     opposing team's season batter K% (MLB avg = 0.227)
    ump_k_adj:      career K rate delta for HP umpire (0 if unknown)
    swstr_delta_k9: additive K/9 adjustment from SwStr% career-relative delta.
                    Positive = pitcher generating more whiffs than their career norm.
                    Defaults to 0 (no adjustment). See calc_swstr_delta_k9().
    opp_games_played: games the opposing team has played this season. Used to
                    Bayesian-regress opp_k_rate toward league average early in season.
                    Defaults to 0 → full regression to league average (safe early-season default).
    opp_k_prior:    Bayesian prior weight (in games) on opponent K%. Loaded from params.json.
    park_factor:    Multiplicative venue adjustment on the rate-driven portion
                    of lambda. Defaults to 1.0 (neutral). SwStr stays additive
                    to K/9 and umpire effect stays additive to lambda.
    """
    adj_opp_k  = bayesian_opp_k(opp_k_rate, opp_games_played, prior=opp_k_prior)
    adj_k9     = blended_k9 + swstr_delta_k9
    base       = adj_k9 * (adj_opp_k / LEAGUE_AVG_K_RATE)
    park_mult  = base * (expected_innings / 9) * park_factor
    ump_add    = ump_k_adj * (expected_innings / 9)
    return park_mult + ump_add


def calc_edge(win_prob: float, odds: int) -> float:
    """Probability edge = model win probability minus implied probability."""
    return win_prob - american_to_implied(odds)


def calc_ev(win_prob: float, odds: int) -> float:
    """Expected ROI on 1.0u risked."""
    lose_prob = 1.0 - win_prob
    return (win_prob * american_to_profit_per_unit(odds)) - lose_prob


def calc_verdict(ev: float) -> str:
    """Map EV to a betting verdict string. Thresholds are static."""
    if ev < EDGE_PASS:
        return "PASS"
    if ev < EDGE_LEAN:
        return "LEAN"
    if ev < EDGE_FIRE_1U:
        return "FIRE 1u"
    return "FIRE 2u"


def is_opener(
    recent_start_ips: list[float] | None,
    threshold: float = OPENER_MEAN_IP_THRESHOLD,
    min_starts: int = OPENER_MIN_STARTS,
) -> bool:
    """Flag likely opener / bullpen games from recent per-start innings."""
    if not recent_start_ips or len(recent_start_ips) < min_starts:
        return False
    return (sum(recent_start_ips) / len(recent_start_ips)) < threshold


def calc_price_delta(current_odds: int, opening_odds: int) -> int:
    """
    Juice movement signal. Negative = juice moved toward over (books taking over liability).
    e.g. -110 -> -135 returns -25.
    """
    return current_odds - opening_odds


def calc_movement_confidence(delta: int,
                              noise_floor: int = 10,
                              full_fade:   int = 30,
                              opening_odds_source: str | None = None) -> float:
    """
    Returns a confidence multiplier (0.0–1.0) based on line movement against the bet side.

    delta > 0  : that side got cheaper (sharp money on the other side) → penalty applied.
    delta <= 0 : movement in our favour or no movement → no penalty (returns 1.0).

    Linear decay from 1.0 at noise_floor to 0.0 at full_fade.
    Movements below noise_floor are treated as routine book adjustments (ignored).

    opening_odds_source gates the haircut (Task A2): only a "preview"-tagged
    opening is a true overnight baseline worth penalising against. For
    "first_seen" (within-day opening from TheRundown's price_delta) or None
    (legacy row pre-migration), we return 1.0 — applying the haircut against
    a same-day opening compares current odds to a baseline only hours old,
    which was the original 4/8 semantic bug.
    """
    if opening_odds_source != "preview":
        return 1.0
    if delta <= noise_floor:
        return 1.0
    if delta >= full_fade:
        return 0.0
    return 1.0 - (delta - noise_floor) / (full_fade - noise_floor)


def build_pitcher_record(odds: dict, stats: dict, ump_k_adj: float,
                         swstr_data: dict | None = None,
                         lineup: list[dict] | None = None,
                         batter_stats: dict | None = None,
                         park_factor: float = 1.0) -> dict:
    """
    Joins one pitcher's odds + stats + umpire adj into a complete record.
    Returns the dict that goes into today.json pitchers array.

    swstr_data:   {"swstr_pct": float, "career_swstr_pct": float | None}
                  from fetch_statcast.fetch_swstr(). Defaults to league-average
                  current SwStr% with no career baseline (zero delta adjustment).
    lineup:       list of {"name": str, "bats": str} dicts (confirmed starting lineup).
                  When provided with batter_stats, overrides stats["opp_k_rate"].
    batter_stats: {name: {"vs_R": float, "vs_L": float}} from fetch_batter_stats.
    park_factor:  Park/venue multiplier passed through to calc_lambda().
                  Defaults to 1.0 (neutral).
    """
    params = load_params()

    if swstr_data is None:
        swstr_data = {"swstr_pct": LEAGUE_AVG_SWSTR, "career_swstr_pct": None}

    swstr_pct        = swstr_data.get("swstr_pct", LEAGUE_AVG_SWSTR) or LEAGUE_AVG_SWSTR
    career_swstr_pct = swstr_data.get("career_swstr_pct")   # None = not available

    # team/opp_team: stats dict is authoritative (from MLB schedule); odds fallback for safety
    team     = stats.get("team")     or odds.get("team", "")
    opp_team = stats.get("opp_team") or odds.get("opp_team", "")

    ip       = stats.get("innings_pitched_season", 0)
    avg_ip   = stats.get("avg_ip_last5", EXPECTED_INNINGS)
    n_starts = stats.get("starts_count", 0)
    recent_start_ips = stats.get("recent_start_ips") or []
    opener = is_opener(recent_start_ips)
    opener_note = None
    if opener:
        avg_ip = round(sum(recent_start_ips) / len(recent_start_ips), 2)
        opener_note = OPENER_NOTE

    season_k9 = stats["season_k9"]
    recent_k9 = stats.get("recent_k9") if stats.get("starts_count", 0) >= 3 else season_k9
    career_k9 = stats.get("career_k9") or season_k9
    days_since_last_start = stats.get("days_since_last_start")
    last_pitch_count = stats.get("last_pitch_count")

    blended   = blend_k9(season_k9, recent_k9, career_k9, ip,
                         weight_season_cap=params["weight_season_cap"],
                         weight_recent=params["weight_recent"])
    rest_delta = calc_rest_k9_delta(days_since_last_start, last_pitch_count)
    blended += rest_delta

    swstr_delta = calc_swstr_delta_k9(
        swstr_pct, career_swstr_pct, n_starts,
        swstr_k9_scale=params.get("swstr_k9_scale", SWSTR_K9_SCALE),
        swstr_prior_starts=params.get("swstr_prior_starts", SWSTR_PRIOR_STARTS),
    )

    lineup_rate = None
    if lineup is not None and batter_stats is not None:
        lineup_rate = calc_lineup_k_rate(lineup, batter_stats, stats.get("throws", "R"))
    effective_opp_k_rate = lineup_rate if lineup_rate is not None else stats["opp_k_rate"]
    lineup_used = lineup_rate is not None

    opp_games        = stats.get("opp_games_played", 0)
    scaled_ump_k_adj = ump_k_adj * params["ump_scale"]

    # Task A7: phantom-starter guard. When MLB's probablePitcher for this team
    # disagrees with TheRundown's announced pitcher (the key under which we
    # fetched odds), the book is likely still holding a market on someone who
    # got scratched — picks like that void on no-action, which wastes slate
    # slots and erodes trust even though calibration is safe. `probable_name`
    # comes from fetch_stats and is accent-insensitive-equal to `odds["pitcher"]`
    # in the happy path; any divergence trips starter_mismatch. Default to False
    # when probable_name is absent (older cached stats, preview path) rather
    # than false-positive-flagging every record.
    probable_name = stats.get("probable_name")
    starter_mismatch = (
        bool(probable_name) and _norm(probable_name) != _norm(odds["pitcher"])
    )

    raw_lam = calc_lambda(blended, avg_ip, effective_opp_k_rate, scaled_ump_k_adj,
                          swstr_delta_k9=swstr_delta, opp_games_played=opp_games,
                          opp_k_prior=params.get("opp_k_prior_games", OPP_K_PRIOR_GAMES),
                          park_factor=park_factor)
    applied_lam = raw_lam + params["lambda_bias"]
    applied_lam = max(0.01, applied_lam)  # guard against negative bias producing invalid Poisson lambda

    k_line = odds["k_line"]

    # Cap applied_lam at ±MAX_LAMBDA_LINE_GAP from the k_line before computing win probs.
    # Data shows picks with gap ≥ 3 win at only 21% — the model over-reaches on extreme
    # predictions and generates inflated EVs that don't reflect real edge.
    MAX_LAMBDA_LINE_GAP = 2.5
    applied_lam = min(applied_lam, k_line + MAX_LAMBDA_LINE_GAP)
    applied_lam = max(applied_lam, k_line - MAX_LAMBDA_LINE_GAP)

    win_prob_over  = 1 - poisson.cdf(math.floor(k_line), applied_lam)
    win_prob_under = poisson.cdf(math.ceil(k_line) - 1, applied_lam)

    best_over_odds  = odds["best_over_odds"]
    best_under_odds = odds["best_under_odds"]
    edge_over  = calc_edge(win_prob_over,  best_over_odds)
    edge_under = calc_edge(win_prob_under, best_under_odds)
    ev_over  = calc_ev(win_prob_over,  best_over_odds)
    ev_under = calc_ev(win_prob_under, best_under_odds)

    price_delta_over  = calc_price_delta(best_over_odds,  odds.get("opening_over_odds",  best_over_odds))
    price_delta_under = calc_price_delta(best_under_odds, odds.get("opening_under_odds", best_under_odds))

    conf_over  = calc_movement_confidence(price_delta_over,
                                           opening_odds_source=odds.get("opening_odds_source"))
    conf_under = calc_movement_confidence(price_delta_under,
                                           opening_odds_source=odds.get("opening_odds_source"))
    adj_ev_over  = ev_over  * conf_over
    adj_ev_under = ev_under * conf_under
    over_verdict = calc_verdict(adj_ev_over)
    under_verdict = calc_verdict(adj_ev_under)

    return {
        "pitcher":            odds["pitcher"],
        "team":               team,
        "opp_team":           opp_team,
        "pitcher_throws":     stats.get("throws", "R"),
        "game_time":          odds["game_time"],
        "k_line":             k_line,
        "opening_line":       odds.get("opening_line", k_line),
        "best_over_book":     odds["best_over_book"],
        "best_under_book":    odds.get("best_under_book") or odds.get("best_over_book", ""),
        "ref_book":           odds.get("ref_book") or odds.get("best_over_book", ""),
        "best_over_odds":     best_over_odds,
        "best_under_odds":    best_under_odds,
        "opening_over_odds":  odds["opening_over_odds"],
        "opening_under_odds": odds["opening_under_odds"],
        "opening_odds_source": odds.get("opening_odds_source"),
        "odds_source":        odds.get("odds_source"),
        "the_odds_event_id":  odds.get("the_odds_event_id"),
        "price_delta_over":   price_delta_over,
        "price_delta_under":  price_delta_under,
        "raw_lambda":         round(raw_lam, 2),
        "lambda":             round(applied_lam, 2),
        "avg_ip":             avg_ip,
        "is_opener":          opener,
        "opener_note":        opener_note,
        "swstr_pct":          round(swstr_pct, 4),
        "career_swstr_pct":   round(career_swstr_pct, 4) if career_swstr_pct is not None else None,
        "swstr_delta_k9":     round(swstr_delta, 3),
        "days_since_last_start": days_since_last_start,
        "last_pitch_count":   last_pitch_count,
        "rest_k9_delta":      round(rest_delta, 3),
        "opp_k_rate":         effective_opp_k_rate,
        "lineup_used":        lineup_used,
        "lineup_count":       len(lineup) if lineup is not None else 0,
        "park_factor":        park_factor,
        "ump_k_adj":          ump_k_adj,
        "starter_mismatch":   starter_mismatch,
        "recent_start_count": len(recent_start_ips),
        "season_k9":          round(season_k9, 2),
        "recent_k9":          round(recent_k9, 2),
        "career_k9":          round(career_k9, 2),
        "ev_over":  {
            "edge":          round(edge_over,    4),
            "ev":            round(ev_over,      4),
            "adj_ev":        round(adj_ev_over,  4),
            "verdict":       over_verdict,
            "win_prob":      round(win_prob_over,  3),
            "movement_conf": round(conf_over,    4),
        },
        "ev_under": {
            "edge":          round(edge_under,    4),
            "ev":            round(ev_under,      4),
            "adj_ev":        round(adj_ev_under,  4),
            "verdict":       under_verdict,
            "win_prob":      round(win_prob_under,  3),
            "movement_conf": round(conf_under,    4),
        },
        "book_odds": odds.get("book_odds") or None,
    }
