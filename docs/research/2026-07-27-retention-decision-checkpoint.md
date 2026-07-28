# Supabase Retention Decision Checkpoint

Scheduled yes/no review: **2026-08-03**

## Current decision

**NO-GO for deletion.** Keep the Supabase spend cap and current retention rules
unchanged. Tyler approved an early read-only review on July 28; no retention
flag, compaction write, or delete path was enabled.

## July 28 early review

| Measure | Current value |
| --- | ---: |
| Database size | `3,331 MB` (`40.66%` of included 8 GB) |
| `market_snapshots` | `2,374 MB`, about `2.73M` estimated rows |
| Raw rows older than 14 days | `2,003,860` (estimated `1,745 MB`) |
| Raw rows older than 30 days | `1,303,579` (estimated `1,135 MB`) |
| 14-day bounded compact sample | `1,310` groups; `148` uncovered |
| 30-day bounded compact sample | `860` groups; `30` uncovered |
| Exact compact coverage | `false` |
| Eligible for execute | `false` for both windows |

The database grew about `83 MB` from the July 27 checkpoint and remains below
the 6 GB escalation line. The 30-day bounded sample improved, but exact
coverage is still false. Its current examples are retired BoltOdds groups;
the 14-day sample also contains current TheRundown and PropLine groups. A broad
age-only delete would therefore mix retired noise with unreconciled current
provider/CLV evidence.

Decision: keep August 3 as a confirmation review, not an execution date. The
next safe evidence step is an exact provider/date coverage proof. Any compact
backfill is a separate write requiring approval, and any eventual deletion
still requires the exact reviewed statement and Tyler's separate approval.

## July 27 evidence

| Measure | Current value |
| --- | ---: |
| Database size | `3,248 MB` (`39.65%` of included 8 GB) |
| `market_snapshots` | `2,314 MB`, about `2.67M` estimated rows |
| Raw rows older than 14 days | `2,003,860` (estimated `1,735 MB`) |
| Raw rows older than 30 days | `1,257,858` (estimated `1,089 MB`) |
| 14-day bounded compact sample | `1,310` groups; `148` uncovered |
| 30-day bounded compact sample | `1,082` groups; `143` uncovered |
| Exact compact coverage | `false` |
| Eligible for execute | `false` for both windows |

The database remains below the existing 6 GB escalation line, but raw
snapshots dominate storage and bounded compact coverage is no longer clean.
The uncovered examples span retired BoltOdds history and current TheRundown /
PropLine evidence, so a broad age-only deletion would remove unreconciled
research provenance.

## August 3 yes/no test

Answer `YES` only if all of the following are true:

1. exact compact coverage is proved for the proposed provider/date window;
2. the deletion target excludes required provider, CLV, lock, notification,
   Alt V2, and source-of-truth evidence;
3. a dry-run row and byte count is reviewed against a recoverable backup/export;
4. the estimated storage benefit is material enough to justify the operational
   risk; and
5. Tyler separately approves the exact execute statement and window.

Otherwise answer `NO`, keep deletion closed, and choose between another compact
backfill, a narrower provider-specific historical retirement proposal, or
continued observation. Never set `ALLOW_MARKET_SNAPSHOT_DELETE` from this
checkpoint.

## Required evidence refresh

Run once each from the linked repo root:

```powershell
npx supabase db query --linked --file scripts/supabase_storage_guardrail.sql -o json
npx supabase db query --linked --file scripts/supabase_row_volume_guardrail.sql -o json
npx supabase db query --linked --file scripts/supabase_retention_readiness.sql -o json
```

Record database/table growth, 14/30-day row and byte estimates, exact coverage,
uncovered groups by provider, and whether any retained evidence affected picks,
locks, alerts, CLV, UI decisions, or a provider decision.

