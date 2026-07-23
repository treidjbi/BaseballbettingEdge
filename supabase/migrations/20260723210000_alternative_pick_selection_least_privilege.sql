-- The original table creation inherited Supabase's default service-role ACL,
-- including DELETE. Rebuild the three runtime role grants explicitly.
revoke all privileges on table public.alternative_pick_selection_state from anon, authenticated;
revoke all privileges on table public.alternative_pick_selection_state from service_role;

grant select, insert, update on table public.alternative_pick_selection_state to service_role;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly') then
    grant select on table public.alternative_pick_selection_state to bbe_ops_readonly;
    drop policy if exists bbe_ops_readonly_select_alternative_pick_selection_state
      on public.alternative_pick_selection_state;
    create policy bbe_ops_readonly_select_alternative_pick_selection_state
      on public.alternative_pick_selection_state
      for select to bbe_ops_readonly using (true);
  end if;
end;
$$;
