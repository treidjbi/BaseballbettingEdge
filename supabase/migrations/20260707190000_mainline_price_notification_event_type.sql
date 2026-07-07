alter table public.notification_events
  drop constraint if exists notification_events_event_type_check;
alter table public.notification_events
  add constraint notification_events_event_type_check
  check (
    event_type in (
      'new_fire_pick',
      'pick_upgraded',
      'pick_downgraded',
      'line_moved_with_us',
      'line_moved_against_us',
      'game_reminder_due',
      'webhook_received',
      'source_degraded',
      'start_window_digest',
      'new_fire_pick_digest',
      'pick_upgraded_digest',
      'pick_downgraded_digest',
      'mainline_best_price_changed'
    )
  );
comment on constraint notification_events_event_type_check
  on public.notification_events is
  'Allows default individual notification events, promoted digest event types, and mainline best-price movement alerts.';
