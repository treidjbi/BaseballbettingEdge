# Positive Unit Producer Decision Packet

Date: 2026-07-07

Status: read-only synthesis. This packet does not approve live changes to model
math, thresholds, staking, provider order, notifications, locks, retention, or
dashboard source of truth.

## Executive Answer

The fastest path to a positive-unit model is not to trust the model harder or
open the funnel wider. It is to turn the system into a stricter bet-selection
and execution engine:

1. Keep the current risk-off caps that prevent the worst FIRE exposure from
   coming back.
2. Treat positive CLV as proof that the market-timing layer can work, not as
   proof that every model edge is bettable.
3. Cut or suppress the repeated loss patterns: high raw model edge, model fades
   market favorite, FIRE unders in fade contexts, and rows without price/CLV
   support.
4. Expand only through narrow LEAN/FIRE contexts where current-provider,
   rolling-window, side, K-line, price, quality, Path B, market agreement, and
   CLV slices all survive.
5. Use best-main-line price tracking as the live execution layer: a pick is more
   actionable when the best available price at the same main line is stable or
   improving, and less actionable when the market has already moved against the
   number.

The core diagnosis is simple: the model can find value sometimes, but the
portfolio is still overexposed to cases where the model is confident and the
market/price layer is not confirming it. The solution is selection discipline
plus price execution before any formula or staking change.

## Current Reality

Latest Strong Base Decision Lab sample:

- Clean analyzed rows: 2,722.
- Tracked post-bump portfolio: 1,417 bets, 697-720, -105.53u, -7.4% ROI.
- Nontracked positive-edge or positive-EV PASS expansion check: 9 bets, 1-8,
  -6.95u. Broad PASS expansion is closed.
- Beat-close-price rows: 215 bets, 122-93, +18.19u, +8.5% ROI.
- Beat-close-line rows: 20 bets, 11-9, +3.42u, +17.1% ROI.
- No-or-worse price CLV rows: 1,182 bets, 564-618, -127.14u, -10.8% ROI.
- Edge 6+ rows: 708 bets, 331-377, -86.44u, -12.2% ROI.
- Model-fades-favorite rows: 701 bets, 302-399, -81.46u, -11.6% ROI.

Interpretation:

- Positive CLV is the strongest sign that the process can work.
- The mass losses are concentrated where price confirmation is missing or where
  raw model edge is fighting the market.
- Larger model edge has not meant safer bet. It has often meant larger error.
- The immediate problem is not pick volume. It is letting the wrong volume
  survive.

## What Is Working

Profit rescue remains the strongest live protection layer:

- Older audit showed current FIRE at 536 bets, -34.07u.
- Proposed profit-rescue FIRE retained only 118 rows and moved to +8.35u in the
  same audit.
- Downgraded rows carried -42.42u of avoided exposure.
- FIRE re-entry lab found no ready-for-plan candidate to reopen broad FIRE.

CLV-supported rows are the clearest process anchor:

- Evidence CLV-supported bucket: 235 bets, 133-102, +21.61u, +9.2% ROI.
- Current-provider slice: 20 bets, 15-5, +8.92u.
- Recent slice: 33 bets, 19-14, +2.95u.
- This is not a live selector by itself because final CLV is partly known after
  the bet window, but it tells us the right kind of bet leaves a price trail.

Narrow keep-FIRE and expand-LEAN buckets are promising but not ready:

- Keep FIRE over, moderate EV, normal leash: 170 bets, +23.50u.
- Keep FIRE market-agreed, moderate EV: 141 bets, +21.81u.
- Expand LEAN 4.5 line, low EV, normal leash: 100 bets, +13.42u.
- Expand LEAN low line, capped model fade: 64 bets, +10.50u.
- Expand LEAN low-K standard no-vig: 49 bets, +10.10u.

These are candidate shapes, not promotions. Each still has slice risks or thin
current-provider sample.

## What Is Broken

The model is still overconfident in the wrong places:

- High raw edge is deeply negative, including the current-provider and recent
  slices.
- Model-fades-favorite is deeply negative, including the recent slice.
- No-or-worse price CLV is the largest unit sink.
- FIRE unders, especially when also fading the market favorite, remain a bad
  exposure pattern.
- No-vig and workload labels do not currently rescue the portfolio.
- Projection challenger and market-anchor work are useful research, but neither
  is ready to replace production projection math.

The important lesson is that a stronger base probably means a smaller, better
qualified base first. A larger card is only valuable after the filter learns to
separate confirmable edges from model-confidence traps.

## Operating Policy Draft

### Stage 0 - Current Live Posture

Keep the current posture unchanged until a separate approval plan exists:

- Quality gate stays live.
- MARKET_FAVORITE_REFEREE_MODE stays enforce.
- PROFIT_RESCUE_REFEREE_MODE stays enforce.
- BATTER_HANDEDNESS_MODE stays Path B input canary.
- Market-anchor selector and market-shrink projection stay shadow.
- No broad LEAN, PASS, FIRE 2u, FIRE under, or model-fade reopening.

This stage is mostly defensive, but it is the reason the system is not taking
the worst historical FIRE portfolio again.

### Stage 1 - Exposure Reduction

Candidate cap/suppress families that deserve a separate promotion plan before
any live change:

- Cap high raw edge when market/price confirmation is absent.
- Cap market-fade rows, especially FIRE rows.
- Cap FIRE under plus market-fade rows.
- Suppress or operator-ignore no-or-worse price support when a runtime proxy is
  available.

Strong Base currently marks these as cap-or-suppress watch, not approved live
behavior. The evidence is strong enough to study as a policy, but the exact
runtime proxy must be clean before changing production decisions.

### Stage 2 - Price Execution Layer

The most practical way to connect positive CLV to betting action is to track the
best available price at the main line every 10 minutes.

Proposed execution rule for research and operator review:

- For each pick, identify the current best supported book at the same main
  line.
- Compare that best main-line price to the prior interval.
- Notify only when the best actionable main-line price changes enough to matter.
- Treat better price at same line as supportive.
- Treat worse price at same line as caution.
- Treat line changes separately from price changes, because a better price on a
  different line can be misleading.

This does not make PropLine a model source of truth. It uses live market data as
an execution and timing layer around the already-approved artifact pick.

### Stage 3 - Selective Expansion

The system should only add volume through buckets that are positive across the
right slices, not just positive overall.

Watch candidates:

- LEAN 4.5 line, low EV, normal leash.
- LEAN low-K standard no-vig.
- LEAN low line with capped model-fade context.
- FIRE over, moderate EV, normal leash.
- FIRE market-agreed, moderate EV.
- Market-agreement LEAN with model plus line-half movement, but only after
  current-provider proof catches up.

Minimum before drafting a live promotion plan:

- Strong total sample.
- Current-provider sample that is not just inherited BoltOdds-era behavior.
- Recent rolling-window positive or at least non-damaging.
- Over/under survival.
- Plus/minus price survival.
- K-line survival.
- FIRE 1u/FIRE 2u survival where relevant.
- Quality gate survival.
- Path B survival.
- Market-agreement survival.
- CLV or pre-close proxy support.

### Stage 4 - Projection Research

Projection changes are not the near-term solution.

Market-implied and market-anchor projection work has shown that the market shape
can beat current lambda on error metrics, but selector samples remain too thin
or mixed for production. Use this as a ranking and confirmation research lane,
not a live math replacement.

The near-term production answer should come from bet selection and execution
filters first.

## Decision Gates

No candidate is ready today for automatic live promotion.

The next approval-quality artifact should be a portfolio simulator that answers:

- What would units look like if we kept only retained FIRE plus the strongest
  keep-FIRE buckets?
- What would units look like if we suppressed high-edge/model-fade/no-price
  support buckets?
- What would units look like if selected LEAN buckets were added at flat 1u?
- What happens by side, K-line, price bucket, provider era, current-provider
  only, recent window, quality state, Path B state, market agreement, and CLV
  proxy?
- Does the policy remain positive after removing hindsight-only fields?

If the simulator cannot produce a positive current-provider and recent-window
portfolio without hindsight, the system should keep observing and stay capped.

If the simulator can produce a positive portfolio that survives slices, then
draft a narrow promotion plan for that policy only.

## Practical Recommendation

The most effective next move is to build a Strong Base Portfolio Simulator
before touching live behavior.

Target output:

- Current live portfolio result.
- Proposed strict portfolio result.
- Proposed expansion portfolio result.
- Unit delta from each cap, suppress, keep, and expand rule.
- Hindsight-field flags so we do not accidentally promote a rule that depends
  on final CLV.
- Current-provider and recent-window results shown first.

This gives Tyler the answer he actually needs: not just which buckets look
smart, but whether a realistic decision policy would have turned the post-bump
model into a positive-unit producer without cheating.

Until that exists, the operating answer is:

- Keep the risk-off live caps.
- Do not expand broad volume.
- Treat positive CLV as the execution north star.
- Watch narrow LEAN/FIRE buckets, especially market-confirmed and moderate-EV
  contexts.
- Make the next change a simulation-backed decision policy, not a lambda,
  staking, or provider change.
