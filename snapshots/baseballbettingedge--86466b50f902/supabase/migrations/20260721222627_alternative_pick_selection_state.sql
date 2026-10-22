create table if not exists public.alternative_pick_selection_state (
  id uuid primary key default gen_random_uuid(),
  slate_date date not null,
  game_identity text not null,
  candidate_identity text not null,
  candidate_became_current_at timestamptz not null,
  pitcher text not null,
  normalized_pitcher text not null,
  team text not null,
  opp_team text not null,
  game_time timestamptz not null,
  side text not null check (side in ('over', 'under')),
  model_k_line numeric not null,
  provider_posture text not null,
  bundle_id text not null,
  selector_id text,
  selector_fingerprint text not null check (length(selector_fingerprint) = 64),
  checkpoint text not null check (checkpoint in ('provisional', 'frozen_pregame')),
  official_odds integer,
  official_book text,
  official_verdict text,
  lane text check (lane in ('consensus_core', 'reentry_expansion')),
  selection_status text not null check (selection_status in ('selected', 'not_selected', 'pending')),
  family_states jsonb not null default '{}'::jsonb,
  family_count integer not null default 0 check (family_count >= 0),
  reason_codes jsonb not null default '[]'::jsonb,
  source_artifact_path text not null,
  source_artifact_generated_at timestamptz,
  source_artifact_sha256 text not null check (length(source_artifact_sha256) = 64),
  source_artifact_byte_sha256 text not null check (length(source_artifact_byte_sha256) = 64),
  evidence_observation_ids jsonb not null default '[]'::jsonb,
  evidence_observation_count integer not null default 0 check (evidence_observation_count >= 0),
  evidence_first_observed_at timestamptz,
  evidence_last_observed_at timestamptz,
  evidence_freshness_status text not null,
  observed_at timestamptz not null,
  frozen_at timestamptz,
  lock_dedupe_key text,
  lock_artifact_sha256 text check (lock_artifact_sha256 is null or length(lock_artifact_sha256) = 64),
  lock_source_artifact_path text,
  locked_at timestamptz,
  should_lock_at timestamptz,
  minutes_until_start numeric,
  lock_status text check (lock_status is null or lock_status in ('due_now', 'missed_lock')),
  inserted_at timestamptz not null default now(),
  unique (slate_date, game_identity, normalized_pitcher, side, bundle_id, checkpoint),
  check (minutes_until_start is null or minutes_until_start >= 0),
  check (
    (checkpoint = 'provisional' and frozen_at is null and lock_dedupe_key is null and lock_artifact_sha256 is null and lock_source_artifact_path is null
      and locked_at is null and should_lock_at is null and minutes_until_start is null and lock_status is null)
    or
    (checkpoint = 'frozen_pregame' and frozen_at is not null and lock_dedupe_key is not null and lock_artifact_sha256 is not null and lock_source_artifact_path is not null
      and locked_at is not null and should_lock_at is not null and minutes_until_start is not null and lock_status is not null)
  )
);

create function public.alternative_pick_selection_state_reject_frozen_mutation()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  -- Reject when OLD or NEW is frozen_pregame; NEW is only defined on UPDATE.
  -- old.checkpoint = 'frozen_pregame' or new.checkpoint = 'frozen_pregame'
  if old.checkpoint = 'frozen_pregame' or (tg_op = 'UPDATE' and new.checkpoint = 'frozen_pregame') then
    raise exception 'frozen alternative pick state is immutable';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;

create trigger alternative_pick_selection_state_reject_frozen_mutation
before update or delete on public.alternative_pick_selection_state
for each row execute function public.alternative_pick_selection_state_reject_frozen_mutation();

create function public.alternative_pick_selection_state_validate_frozen_link()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.checkpoint <> 'frozen_pregame' then
    return new;
  end if;

  if not (new.frozen_at = new.locked_at) or not (new.observed_at = new.locked_at) or new.frozen_at >= new.game_time then
    raise exception 'frozen alternative pick state must be captured before game start from its lock time';
  end if;

  if not exists (
    select 1
    from public.operational_pick_locks as lock_row
    where lock_row.dedupe_key = new.lock_dedupe_key
      and lock_row.slate_date = new.slate_date
      and lock_row.normalized_pitcher = new.normalized_pitcher
      and lock_row.side = new.side
      and lock_row.locked_k_line = new.model_k_line
      and lock_row.locked_odds = new.official_odds
      and lower(nullif(trim(lock_row.locked_book), '')) is not distinct from lower(nullif(trim(new.official_book), ''))
      and lock_row.game_time = new.game_time
      and lock_row.status_at_capture = new.lock_status
      and lock_row.locked_at = new.locked_at
      and lock_row.observed_at = new.locked_at
      and lock_row.should_lock_at = new.should_lock_at
      and lock_row.minutes_until_start is not distinct from new.minutes_until_start
      and lock_row.source_artifact_sha256 = new.lock_artifact_sha256
      and lock_row.source_artifact_sha256 = new.source_artifact_byte_sha256
      and lock_row.source_artifact_path = new.lock_source_artifact_path
      and length(lock_row.source_artifact_sha256) = 64
      and upper(trim(lock_row.metadata ->> 'team')) = upper(new.team)
      and upper(trim(lock_row.metadata ->> 'opp_team')) = upper(new.opp_team)
  ) then
    raise exception 'frozen alternative pick state must link to the exact operational lock';
  end if;
  return new;
end;
$$;

create trigger alternative_pick_selection_state_validate_frozen_link
before insert on public.alternative_pick_selection_state
for each row execute function public.alternative_pick_selection_state_validate_frozen_link();

alter table public.alternative_pick_selection_state enable row level security;
revoke all privileges on table public.alternative_pick_selection_state from anon, authenticated;
grant select, insert, update on table public.alternative_pick_selection_state to service_role;
