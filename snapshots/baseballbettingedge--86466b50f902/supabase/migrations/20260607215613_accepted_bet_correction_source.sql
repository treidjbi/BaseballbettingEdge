alter table public.accepted_bets
  drop constraint if exists accepted_bets_source_check;

alter table public.accepted_bets
  add constraint accepted_bets_source_check
  check (
    source = any (
      array[
        'dashboard_manual'::text,
        'dashboard_correction'::text,
        'notification'::text,
        'shadow_candidate'::text,
        'other'::text
      ]
    )
  );
