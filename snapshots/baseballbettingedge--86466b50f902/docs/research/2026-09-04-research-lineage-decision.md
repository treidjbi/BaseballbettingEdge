# Research lineage decision — September 4, 2026

**Gate C's historical file is intact; selective LEAN has several structural
evidence gaps, not merely a missing lock ID. Kumar Rocker's omission is an
unconsumed-lock exception, outside the existing history-repair contract.**

Keep production and historical records unchanged. The useful next decision is
a research-only, decision-time evidence adapter with explicit exclusions.
Repeating the current eligibility counter will not solve the missing inputs.
Do not turn the bounded reconstruction below into formal prospective credit.

This follow-up uses current SELECT-only Supabase reads and bounded served
artifacts captured September 4 starting at 22:24Z; individual timestamps are
retained in the evidence. Research scope is August
15–September 3, the selective-LEAN prospective window to the last closed
slate. The earlier [operating assessment](2026-09-04-operating-and-research-assessment.md)
and [Alt V2 decision](2026-09-04-alt-v2-paired-decision.md) remain preserved.

## 1. Historical Gate C provenance: resolved

The 2,070-row canonical JSONL remains the April 28–June 16 historical research
artifact, generated August 21. Reconstructing Windows CRLF line endings **in
memory** produces its stored manifest hash exactly:

| Representation | SHA-256 |
| --- | --- |
| Current Git/Mac LF JSONL | `6f5745a290b12ab3976a81f5231084eb8619adc855384d1107187ad5c51ff66b` |
| Same bytes with CRLF restored | `e8c7c6d53ca51610213d1b168af58e831f5f8e079f2e28f88944856c3316a0da` |
| Manifest's JSONL hash | `e8c7c6d53ca51610213d1b168af58e831f5f8e079f2e28f88944856c3316a0da` |

The summary Markdown's CRLF hash also matches its manifest exactly. Parsed
row values and counts are identical across both newline representations.
Git blobs at the original attribution commit `319316fe` and current `HEAD`
have the same LF JSONL; the preceding `deed8780` dataset also reproduces its
own manifest under CRLF. This is serialization provenance, not lost evidence.

**Correction to the earlier September 4 assessment:** that check only
normalized toward LF. It did not reconstruct CRLF, so the statement that
line-ending normalization could not explain the mismatch was too broad.
This record supersedes that unresolved-blocker conclusion. No historical
file or manifest was overwritten, and the old artifact is still not current.

## 2. Current bounded reconstruction: useful, but not a hosted-run certificate

The existing pure Gate C builder and market-agreement tracker were run offline
against 20 captured dated artifacts, 441 bounded history rows, 896 compact
market-evidence rows and 1,343 display-state rows. No raw snapshots or provider
calls were used. No scheduled research run or production artifact was written.

| Population | Count | Meaning |
| --- | ---: | --- |
| Rebuilt Gate C side rows | 660 | 20 dates, zero duplicate keys, zero archive outcome recoveries |
| Existing Gate C graded-history reconciliation | 330/330 | Its history-based check passes, including one unlocked graded history row |
| Gate C rows marked tracked with a side outcome | 351 | Broader than consumed operational locks; not automatically prospective picks |
| Operational locks | 330 | 329 consumed, one unconsumed |
| Closed locked history rows | 329 | Every consumed operational lock has matching history in this bounded window |
| Strict research join preview | 314 | Exact identity, game time, quote, book, verdict and timestamp, with consumed-lock/hash/path proof |
| Join exclusions among the 351 tracked side rows | 37 | 15 book disagreements and 22 identities without an operational lock |

The 351 denominator can include history associations without an operational
lock because the builder's `is_tracked_pick` flag denotes a history match.
It is not a consumed-ledger certificate. Likewise, a passing 330/330 history
reconciliation cannot detect Kumar: he is absent from that history denominator.
These measures must remain separate.

The exact join preview appends proof to copies only. It never substitutes a
dated artifact's source path for the lock's source path, infers consumption,
or replaces conflicting book evidence. The 15 book differences include the
previously documented Logan Webb DraftKings/FanDuel disagreement. They need
an explicit distinction between the archived reference book and the actual
locked quote; simply ignoring the mismatch would conceal the issue.

This is a reconstruction from current records, not retrieval of the latest
Render research output. The full historical nomination/baseline audit was
not rerun, and no baseline was redefined from a 20-day subset. No optional
lineup or actual-opportunity backfill was added to this bounded build.

## 3. Selective LEAN: lock enrichment alone still produces zero eligibility

The [frozen selective-LEAN design](../superpowers/specs/2026-08-14-selective-lean-prospective-audit-design.md)
requires displayed LEAN, K-line bucket 2.5–3.5, capped quality and
`model_fades_favorite`. Its fingerprint remains
`4e00a180e35fe75dc8889d47065a25c4351cb37ac55664eb42f01b77c07fd13a`.
No rule, cutoff, sample or diversity gate is changed.

There are 23 matching rows in the bounded final-archive reconstruction:

| Missing requirement | Before preview | After exact lock-only preview |
| --- | ---: | ---: |
| Lock ID, consumption time and lock source path | 23 each | 3 each; book disagreements remain excluded |
| Provider field accepted by this audit | 23 | 23 |
| Market-agreement attribution | 23 | 23 |
| Persisted preclose-proxy label | 23 | 23 |
| Exactly `pre_30` | 1 | 1 |
| Rows passing every required input check | **0** | **0** |

Three distinct problems remain after lock linkage:

1. **Provider field contract:** all 23 rows have an explicit official provider
   (20 TheRundown, three PropLine), but this audit reads only `provider`,
   `live_display_provider` or `odds_source`. Gate C writes
   `official_line_source_provider`, `official_odds_source` and
   `official_market_source_mode` separately. This is a reader/schema gap;
   the movement provider must not be relabeled as the official quote source.
2. **Pregame evidence:** compact history exists, but none of these 23 rows
   receives an eligible market-agreement label in the existing builder. Across
   all 660 rows, only 26 receive one. The latest compact rollups do not provide
   complete exact checkpoints for this candidate set. Do not reinterpret
   post-start, unmatched or missing evidence as neutral agreement.
3. **Preclose proof:** the audit requires a persisted proxy label even though
   its slice renderer can calculate a descriptive fallback label. These are
   different contracts. The 23 frozen-input rule matches independently found
   in the existing Alt V2 proof ledger all have pending Preclose evidence and
   no label; all 23 record `snapshot_page_cap_reached`, with additional
   provider-run caps, ladder ambiguity or immaturity on subsets. Computing a
   label after the game would not recover missing prospective proof. This
   does not justify raising runtime read caps or polling cadence.

### A lock identifier would not prove the candidate inputs were frozen

Applying the same four-field selective-LEAN rule to available immutable Alt
normalized inputs also finds 23 rows, but only **21 overlap** with the archive
matches. These are matches to the selective-LEAN predicate, not Alt selections.

| Identity | Frozen evidence | Final-archive Gate C | Interpretation |
| --- | --- | --- | --- |
| Erick Fedde OVER, August 29 | Model fades favorite; otherwise matches | Relationship unknown | Archive loses a frozen rule match |
| Mason Adams OVER, August 30 | Model fades favorite; otherwise matches | Relationship unknown | Archive loses a frozen rule match |
| Randy Vasquez UNDER, August 21 | Minimal pending proof lacks quality/relationship | Capped/model-fade match | Archive fills information absent from the frozen proof |
| Justin Hagenman OVER, September 2 | Minimal pending proof lacks quality/relationship | Capped/model-fade match | Archive fills information absent from the frozen proof |

Therefore the adapter must distinguish **decision-time inputs** from later
archive context. It may reuse sufficient immutable proofs and exact locks;
it must not give the final archive a prospective label merely because the
quote timestamp matches. The existing no-back-credit rule stays in force.
No result/P&L scoreboard is used to choose between these reconstructions.

## 4. Kumar Rocker: outcome established, operational provenance still missing

The exact August 19 lock is `dabe1657-2a2d-4bbd-a708-4fdc6bd3e9a3`, UNDER 4.5
at FanDuel -138, captured at 23:40:39Z for the August 20 00:05Z game.
Its `consumed_at` is null in the current table and in the earlier captured
packet. No August 18–20 Kumar history row exists. The dated archive still
shows an in-progress card with no tracked pick or actual-K result.

The [official MLB schedule](https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=140&date=2026-08-19&hydrate=probablePitcher)
identifies game 822860, Washington at Texas, at that exact game time. Its
[box score](https://statsapi.mlb.com/api/v1/game/822860/boxscore) records Kumar
Rocker, player 677958, as the starter with **3 strikeouts in 5 innings**.
Thus the quoted UNDER 4.5 would win +0.724638u at -138. That is a hypothetical
quote outcome, not an accepted bet or a repaired official history row.

The existing [repair tool](../../scripts/repair_missing_locked_picks.py)
explicitly rejects an unconsumed lock. The completed August 24 nine-row repair
does not authorize bypassing that condition, setting `consumed_at` now, or
replaying this historical lock. Keep the exception excluded. Its verified
outcome cannot affect Alt V2 or mainline FIRE because it was an unselected
LEAN. It also does not prove a current grading outage.

## 5. Next decision and work treatment

**Recommended next implementation scope:** a standalone, research-only
decision-time linkage adapter, validated offline before any research-runner
integration. This is a proposed scope, not an enacted production change.

| Component | Required evidence and acceptance check | Revisit trigger |
| --- | --- | --- |
| Historical Gate C | Retain LF file and original manifest plus this CRLF proof; no rebuild needed to repair the hash | Parsed content changes, unexplained hash drift or a genuinely newer research window |
| Decision-time adapter | Join exact date/pitcher/side/game/lock quote and consumed proof; retain separate archive and lock books/paths; require frozen selector inputs; missing/duplicate/conflicting evidence stays excluded | A reviewed adapter can explain every inclusion and named exclusion without increasing formal credit by inference |
| Provider reader | Accept explicit official fields under a separately documented precedence; preserve movement-provider fields independently | A test demonstrates correct attribution with no inferred source or changed predicate |
| Agreement / proxy evidence | Reuse existing immutable evidence only when exact identity, observation timing and required inputs pass; require a forward-only collection design for missing cases | Complete pregame evidence appears under an approved research contract, not merely more outcome rows |
| Selective-LEAN counter | Retain frozen hypothesis and baseline; recommend pausing repetitive promotion readouts while these structural gaps persist | Adapter plus evidence contract passes; then evaluate the original 75-row/diversity/return gates, with no back-credit |
| Kumar exception | Preserve unconsumed status and official outcome side evidence | Independent proof of historical consumption, or a separately reviewed historical-recovery policy; a box score alone is insufficient |

Continue ordinary operational health and lock-integrity checks. Alt V2
promotion paths remain retired, and every other candidate retains its own
gates. No raw data was deleted, no source history was modified, no settings
or notifications changed, and no job was dispatched or deployed.

## Evidence and verification

[Source inventory and reproduction](evidence/2026-09-04-research-lineage/README.md)
· [Executed notebook](evidence/2026-09-04-research-lineage/lineage-checks.ipynb)
· [Checks, exclusions and candidate identities](evidence/2026-09-04-research-lineage/analysis.json).
The existing dataset, selective-LEAN and history-repair suites passed **47
tests**. The offline reconstruction validates all 660 dataset rows and
preserves the original canonical files.

Transport limitation: rehashing served JSON did not reproduce the issuer's
stored payload hash for these dated artifacts. A direct SQL JSONB versus
served-JSON comparison for August 30 proves equal values but different number
serialization (for example `0.0` versus `0`); even the SQL-decoded Python
serialization differs from the original issuer hash. Treat stored hashes as
issuer provenance, not a checksum of reserialized API bytes. The captured
response/subset files have independent hashes. No all-artifact byte-integrity
certification or new hash-policy change is claimed here.
