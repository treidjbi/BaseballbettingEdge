# September 8 Season-End Read-Only Preflight

## Outcome

The core season-end research pipeline can rebuild current production history
without changing production state, provided the run stages canonical history
instead of depending on the public unbounded full-history response.

This was a rehearsal only. Every generated artifact was written under a
temporary directory outside the repository. No PropLine/TheRundown request,
model change, database write, deployment, schedule change, notification
change, or retention write occurred during the rehearsal. The only Git change
in preparation was the separately documented creation of the runbook branch;
the rehearsal itself changed no tracked repository content.

## Source State

- Rehearsal date: `2026-09-08` Phoenix time.
- Git base: `origin/main` on the new `codex/season-end-runbook` branch.
- Staged canonical history: `3,675` rows, spanning `2026-03-25` through
  `2026-09-08`.
- Bounded compact market evidence: `5,301` `market_pick_evidence` rows and
  `6,542` `live_market_display_state` rows through September 8.
- Current production artifact date: `2026-09-08`.
- Raw `market_snapshots` were not read by the research rehearsal.
- Current database size at the readiness checkpoint: `6,294,932,627` bytes,
  about `73.3%` of the nominal 8 GiB allocation.
- September 1-7 active-provider preservation check: `366,227` eligible raw
  snapshots, `126,134` represented by compact rows, and a `240,093`-row gap.
- Accepted-bet evidence: `351` rows through `2026-07-27`; later wagers, if any,
  require original receipts rather than inference.

## First Attempt And Correction

The first hybrid build requested the public full-history endpoint and received
HTTP 502. A non-fail-fast shell continued into downstream tools, which wrote
zero-row placeholder reports. Those outputs are invalid and were not used.

The corrected run:

1. enabled fail-fast shell behavior;
2. staged `picks_history` directly from the linked canonical Supabase artifact;
3. rebuilt Gate C through the same hybrid dated-artifact path;
4. staged compact market evidence directly from Supabase;
5. built market agreement, rebuilt Gate C with the fresh tracker, and ran the
   remaining research tools.

Season-end execution must retain both corrections. An output file existing is
not completion evidence; nonzero rows and reconciliation are required.

## Rehearsal Results

| Check | Result |
| --- | ---: |
| Gate C rows | `4,822` |
| Gate C date range | `2026-04-28` through `2026-09-07` |
| Tracked side rows | `2,534` |
| Pick-history reconciliation | `2,444 / 2,444` |
| Duplicate dataset keys | `0` |
| Fresh market-agreement tracker rows | `11,843` |
| Gate C rows with an agreement label | `381` |
| Gate C rows with live-display state | `423` |
| Season-end no-leakage rows | `4,822` |
| Available-pre-lock rows | `4,822` |
| Workload/no-vig source rows | `4,822` |

The maximum Gate C date is September 7 because September 8 games were not yet
graded. That is expected.

## Research Read

The current candidate lab still contains only two scaffold candidates:

| Candidate | Overall rows | Overall PnL | Test rows | Test PnL | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| `model_agrees_with_favorite` | `2,386` | `-137.04u` | `1,712` | `-99.41u` | watch / blocked negative PnL |
| `clean_quality_only` | `2,478` | `-156.00u` | `1,796` | `-109.35u` | watch / blocked negative PnL |

The workload/no-vig audit also remains negative across the broad buckets. The
rehearsal therefore supports the existing conclusion: data plumbing is ready,
but the scaffold packet is not a promotion decision and does not justify a
live model change.

The refreshed seasonal audit now spans March through September, but it still
uses app-selected rows. Its month effects remain descriptive until compared
with an MLB-wide starter K/start baseline.

## Recorded Temporary Hashes

These hashes prove the corrected outputs used for this report. The temporary
files are not canonical season-end artifacts.

| Temporary artifact | SHA-256 |
| --- | --- |
| Gate C JSONL | `f1dfd9c30dfca6801f7fb526fdfa1a458decc021f10e932e59db3d36424cd84f` |
| Gate C manifest | `ece16cf8105d203a0a73df9b32f8d5d94859fe4fc7cffc9f73d1dee0842faf9b` |
| Market-agreement JSONL | `b181689245ed3b347dfca836d619e8a90184fa323ce1ba4ae8d4f582bc08832c` |
| Season-end rebuild JSONL | `ecb7edc8759f0b9a1b744df67195f82b8cb6dfb57b461170dbb76ec74db26fe5` |

## Remaining Gates

- The full season is not graded or frozen.
- The candidate lab is still intentionally narrow and scaffold-only.
- Required decision slices must be populated and reviewed at season end.
- Recent PropLine/TheRundown compact movement history is not exact yet; raw
  evidence must remain preserved until preview-first finalization passes.
- The final accepted-bet record must remain receipt-backed rather than inferred.
- Render service IDs and settings must be resolved live at the shutdown; the
  current local environment does not have an authenticated Render CLI.

The controlling execution sequence is
`docs/superpowers/plans/2026-09-08-season-end-freeze-and-provider-shutdown.md`.
