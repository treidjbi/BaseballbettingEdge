alter table public.alternative_pick_selection_state
  add column if not exists evaluation_proof jsonb not null default '{}'::jsonb;

create or replace function public.default_alternative_pick_v1_evaluation_proof()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.bundle_id = 'pregame_alternative_pick_methodology_v1'
     and new.evaluation_proof is null then
    new.evaluation_proof := '{}'::jsonb;
  end if;
  return new;
end;
$$;

drop trigger if exists alternative_pick_selection_state_default_v1_proof
  on public.alternative_pick_selection_state;
create trigger alternative_pick_selection_state_default_v1_proof
before insert or update on public.alternative_pick_selection_state
for each row execute function public.default_alternative_pick_v1_evaluation_proof();

alter table public.alternative_pick_selection_state
  add constraint alternative_pick_selection_state_evaluation_proof_object_check
    check (jsonb_typeof(evaluation_proof) = 'object'),
  add constraint alternative_pick_selection_state_evaluation_proof_size_check
    check (octet_length(evaluation_proof::text) <= 32768),
  add constraint alternative_pick_selection_state_v2_evaluation_proof_check
    check (
      bundle_id <> 'pregame_alternative_pick_methodology_v2'
      or (
        evaluation_proof ->> 'schema_version' = 'v2'
        and evaluation_proof ->> 'bundle_id' = bundle_id
        and evaluation_proof ->> 'selector_fingerprint' = selector_fingerprint
        and evaluation_proof #>> '{candidate,candidate_identity}' = candidate_identity
        and evaluation_proof #>> '{candidate,slate_date}' = slate_date::text
        and evaluation_proof #>> '{candidate,normalized_pitcher}' = normalized_pitcher
        and evaluation_proof #>> '{candidate,side}' = side
        and (evaluation_proof #>> '{candidate,model_k_line}')::numeric = model_k_line
        and (evaluation_proof #>> '{candidate,game_time}')::timestamptz = game_time
        and evaluation_proof #>> '{artifact,source_artifact_path}' = source_artifact_path
        and evaluation_proof #>> '{artifact,source_artifact_sha256}' = source_artifact_sha256
        and evaluation_proof #>> '{artifact,source_artifact_byte_sha256}' = source_artifact_byte_sha256
        and evaluation_proof #> '{decision,family_states}' = family_states
        and evaluation_proof #>> '{decision,selection_status}' = selection_status
        and evaluation_proof #>> '{decision,selected_lane}' is not distinct from lane
        and (
          (
            evaluation_proof #>> '{decision,selected_lane}' = 'consensus_core'
            and selector_id = 'no_drag_distinct_family_consensus_core_v2'
          )
          or (
            evaluation_proof #>> '{decision,selected_lane}' = 'reentry_expansion'
            and selector_id = 'moderate_edge_quality_reentry_expansion_v2'
          )
          or (
            evaluation_proof #>> '{decision,selected_lane}' is null and selector_id is null
          )
        )
      )
    );
