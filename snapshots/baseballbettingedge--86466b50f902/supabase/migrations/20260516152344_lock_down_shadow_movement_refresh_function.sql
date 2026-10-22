revoke execute on function public.refresh_shadow_provider_movement_tracking(timestamptz) from public;
revoke execute on function public.refresh_shadow_provider_movement_tracking(timestamptz) from anon;
revoke execute on function public.refresh_shadow_provider_movement_tracking(timestamptz) from authenticated;
grant execute on function public.refresh_shadow_provider_movement_tracking(timestamptz) to service_role;
grant execute on function public.refresh_shadow_provider_movement_tracking(timestamptz) to postgres;;
