do $$
begin
  if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly') then
    execute 'grant select on public.market_pick_evidence to bbe_ops_readonly';
    execute 'grant select on public.shadow_notification_candidates to bbe_ops_readonly';

    execute 'drop policy if exists bbe_ops_readonly_select_market_pick_evidence on public.market_pick_evidence';
    execute 'create policy bbe_ops_readonly_select_market_pick_evidence on public.market_pick_evidence for select to bbe_ops_readonly using (true)';

    execute 'drop policy if exists bbe_ops_readonly_select_shadow_notification_candidates on public.shadow_notification_candidates';
    execute 'create policy bbe_ops_readonly_select_shadow_notification_candidates on public.shadow_notification_candidates for select to bbe_ops_readonly using (true)';
  end if;
end $$;
