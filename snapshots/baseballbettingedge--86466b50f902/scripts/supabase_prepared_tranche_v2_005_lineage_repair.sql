-- One-shot, state-gated repair approved on 2026-09-04.
-- Scope: exactly the 17 TheRundown 2026-07-15 compact groups containing the
-- final 2026-07-16T13:10:41.076339Z poll. No raw row is updated or deleted.

with approved_late_rows as materialized (
  select
    ms.id,
    ms.observed_at,
    mpr.slate_date,
    lower(trim(mpr.provider)) as provider,
    lower(trim(ms.bookmaker_key)) as book_key,
    trim(ms.normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(ms.market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(ms.side)) as side,
    ms.line::numeric as line
  from public.market_snapshots ms
  join public.market_provider_runs mpr on mpr.id = ms.run_id
  where mpr.provider = 'therundown'
    and mpr.slate_date = date '2026-07-15'
    and ms.provider = 'therundown'
    and ms.observed_at = timestamptz '2026-07-16T13:10:41.076339Z'
), affected_keys as materialized (
  select distinct
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    market_key,
    side,
    line
  from approved_late_rows
), raw_rows as materialized (
  select
    affected_keys.slate_date,
    affected_keys.provider,
    affected_keys.book_key,
    affected_keys.normalized_player_name,
    coalesce(
      nullif(trim(ms.player_name), ''),
      nullif(trim(ms.normalized_player_name), ''),
      'unknown'
    ) as player_name,
    affected_keys.market_key,
    affected_keys.side,
    affected_keys.line,
    ms.observed_at,
    ms.american_odds::integer as american_odds,
    ms.id
  from affected_keys
  join public.market_provider_runs mpr
    on mpr.slate_date = affected_keys.slate_date
   and lower(trim(mpr.provider)) = affected_keys.provider
  join public.market_snapshots ms
    on ms.run_id = mpr.id
   and lower(trim(ms.provider)) = affected_keys.provider
   and lower(trim(ms.bookmaker_key)) = affected_keys.book_key
   and trim(ms.normalized_player_name) = affected_keys.normalized_player_name
   and coalesce(nullif(trim(ms.market_key), ''), 'pitcher_strikeouts')
       = affected_keys.market_key
   and lower(trim(ms.side)) = affected_keys.side
   and ms.line::numeric = affected_keys.line
), windowed_rows as (
  select
    raw_rows.*,
    first_value(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name,
                   market_key, side, line
      order by observed_at asc, id asc
      rows between unbounded preceding and unbounded following
    ) as first_odds,
    first_value(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name,
                   market_key, side, line
      order by observed_at desc, id desc
      rows between unbounded preceding and unbounded following
    ) as last_odds,
    lag(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name,
                   market_key, side, line
      order by observed_at asc, id asc
    ) as previous_odds
  from raw_rows
), rebuilt as materialized (
  select
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    min(player_name) as player_name,
    market_key,
    side,
    line,
    min(observed_at) as first_seen_at,
    max(observed_at) as last_seen_at,
    min(first_odds) as first_odds,
    min(last_odds) as last_odds,
    min(american_odds) as min_odds,
    max(american_odds) as max_odds,
    count(*) filter (
      where previous_odds is not null
        and american_odds is not null
        and previous_odds <> american_odds
    )::integer as odds_move_count,
    count(*)::integer as snapshot_count,
    jsonb_agg(id order by observed_at asc, id asc) as source_snapshot_ids
  from windowed_rows
  group by
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    market_key,
    side,
    line
), comparison as materialized (
  select
    rebuilt.*,
    cmlm.id as existing_id,
    cmlm.player_name as old_player_name,
    cmlm.first_seen_at as old_first_seen_at,
    cmlm.last_seen_at as old_last_seen_at,
    cmlm.first_odds as old_first_odds,
    cmlm.last_odds as old_last_odds,
    cmlm.min_odds as old_min_odds,
    cmlm.max_odds as old_max_odds,
    cmlm.odds_move_count as old_odds_move_count,
    cmlm.snapshot_count as old_snapshot_count,
    cmlm.source_snapshot_ids as old_source_snapshot_ids
  from rebuilt
  left join public.compact_market_line_movements cmlm
    on cmlm.slate_date = rebuilt.slate_date
   and cmlm.provider = rebuilt.provider
   and cmlm.book_key = rebuilt.book_key
   and cmlm.normalized_player_name = rebuilt.normalized_player_name
   and cmlm.market_key = rebuilt.market_key
   and cmlm.side = rebuilt.side
   and cmlm.line::numeric = rebuilt.line
), prestate as (
  select
    (select count(*)::bigint from approved_late_rows) as late_source_rows,
    (select count(*)::bigint from approved_late_rows late
      where not exists (
        select 1
        from public.compact_market_line_movements cmlm
        where cmlm.slate_date = late.slate_date
          and cmlm.provider = late.provider
          and cmlm.book_key = late.book_key
          and cmlm.normalized_player_name = late.normalized_player_name
          and cmlm.market_key = late.market_key
          and cmlm.side = late.side
          and cmlm.line::numeric = late.line
          and jsonb_typeof(cmlm.source_snapshot_ids) = 'array'
          and cmlm.source_snapshot_ids ? late.id::text
          and late.observed_at between cmlm.first_seen_at and cmlm.last_seen_at
      )) as unpreserved_late_source_rows,
    (select count(*)::bigint from affected_keys) as affected_group_count,
    (select count(*)::bigint from raw_rows) as source_rows_in_affected_groups,
    count(*)::bigint as rebuilt_group_count,
    count(*) filter (where existing_id is null)::bigint as missing_existing_groups,
    count(*) filter (where existing_id is not null)::bigint as existing_group_count,
    coalesce(sum(old_snapshot_count), 0)::bigint as old_represented_rows,
    coalesce(sum(snapshot_count), 0)::bigint as rebuilt_represented_rows,
    count(*) filter (where old_player_name is distinct from player_name)::bigint
      as player_name_changes,
    count(*) filter (where old_first_seen_at is distinct from first_seen_at)::bigint
      as first_seen_changes,
    count(*) filter (where old_last_seen_at is distinct from last_seen_at)::bigint
      as last_seen_changes,
    count(*) filter (where old_first_odds is distinct from first_odds)::bigint
      as first_odds_changes,
    count(*) filter (where old_last_odds is distinct from last_odds)::bigint
      as last_odds_changes,
    count(*) filter (where old_min_odds is distinct from min_odds)::bigint
      as min_odds_changes,
    count(*) filter (where old_max_odds is distinct from max_odds)::bigint
      as max_odds_changes,
    count(*) filter (
      where old_odds_move_count is distinct from odds_move_count
    )::bigint as odds_move_count_changes,
    count(*) filter (
      where old_snapshot_count is distinct from snapshot_count
    )::bigint as snapshot_count_changes,
    count(*) filter (
      where old_source_snapshot_ids is distinct from source_snapshot_ids
    )::bigint as source_snapshot_ids_changes,
    encode(extensions.digest(coalesce((
      select string_agg(
        jsonb_build_array(
          id, observed_at, slate_date, provider, book_key,
          normalized_player_name, market_key, side, line
        )::text,
        E'\n' order by id::text
      )
      from approved_late_rows
    ), ''), 'sha256'), 'hex') as late_rows_sha256,
    encode(extensions.digest(coalesce((
      select string_agg(
        jsonb_build_array(
          slate_date, provider, book_key, normalized_player_name, player_name,
          market_key, side, line, first_seen_at, last_seen_at, first_odds,
          last_odds, min_odds, max_odds, odds_move_count, snapshot_count,
          source_snapshot_ids
        )::text,
        E'\n' order by slate_date, provider, book_key, normalized_player_name,
          market_key, side, line
      )
      from rebuilt
    ), ''), 'sha256'), 'hex') as rebuilt_rows_sha256,
    encode(extensions.digest(coalesce((
      select string_agg(
        jsonb_build_array(
          slate_date, provider, book_key, normalized_player_name,
          old_player_name, market_key, side, line, old_first_seen_at,
          old_last_seen_at, old_first_odds, old_last_odds, old_min_odds,
          old_max_odds, old_odds_move_count, old_snapshot_count,
          old_source_snapshot_ids
        )::text,
        E'\n' order by slate_date, provider, book_key, normalized_player_name,
          market_key, side, line
      )
      from comparison
    ), ''), 'sha256'), 'hex') as existing_rows_sha256
  from comparison
), execution_gate as (
  select
    prestate.*,
    (
      late_source_rows = 17
      and unpreserved_late_source_rows = 17
      and affected_group_count = 17
      and source_rows_in_affected_groups = 1323
      and rebuilt_group_count = 17
      and missing_existing_groups = 0
      and existing_group_count = 17
      and old_represented_rows = 1306
      and rebuilt_represented_rows = 1323
      and player_name_changes = 0
      and first_seen_changes = 0
      and last_seen_changes = 17
      and first_odds_changes = 0
      and last_odds_changes = 1
      and min_odds_changes = 0
      and max_odds_changes = 0
      and odds_move_count_changes = 1
      and snapshot_count_changes = 17
      and source_snapshot_ids_changes = 17
      and late_rows_sha256
          = '435501093251177170e5def7f3d8bfde5085c35b67d265cd184c79a9aa4988c9'
      and rebuilt_rows_sha256
          = 'debd07cfce0c8ab203dbc590f75c0582ba18675750c76861cca16b124c3863be'
      and existing_rows_sha256
          = '95d756156996d9b732f106f12e0c90dfd603de074597ad0f45ace87aecc418a3'
    ) as source_state_matches
  from prestate
), upserted as (
  insert into public.compact_market_line_movements (
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    player_name,
    market_key,
    side,
    line,
    first_seen_at,
    last_seen_at,
    first_odds,
    last_odds,
    min_odds,
    max_odds,
    odds_move_count,
    snapshot_count,
    source_snapshot_ids,
    updated_at
  )
  select
    rebuilt.slate_date,
    rebuilt.provider,
    rebuilt.book_key,
    rebuilt.normalized_player_name,
    rebuilt.player_name,
    rebuilt.market_key,
    rebuilt.side,
    rebuilt.line,
    rebuilt.first_seen_at,
    rebuilt.last_seen_at,
    rebuilt.first_odds,
    rebuilt.last_odds,
    rebuilt.min_odds,
    rebuilt.max_odds,
    rebuilt.odds_move_count,
    rebuilt.snapshot_count,
    rebuilt.source_snapshot_ids,
    now()
  from rebuilt
  cross join execution_gate
  where execution_gate.source_state_matches
  on conflict (
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    market_key,
    side,
    line
  ) do update set
    player_name = excluded.player_name,
    first_seen_at = excluded.first_seen_at,
    last_seen_at = excluded.last_seen_at,
    first_odds = excluded.first_odds,
    last_odds = excluded.last_odds,
    min_odds = excluded.min_odds,
    max_odds = excluded.max_odds,
    odds_move_count = excluded.odds_move_count,
    snapshot_count = excluded.snapshot_count,
    source_snapshot_ids = excluded.source_snapshot_ids,
    updated_at = excluded.updated_at
  returning 1
)
select jsonb_build_object(
  'provider', 'therundown',
  'source_slate_date', '2026-07-15',
  'late_observed_at', '2026-07-16T13:10:41.076339Z',
  'source_state_matches', execution_gate.source_state_matches,
  'candidate_groups', execution_gate.affected_group_count,
  'upserted_groups', (select count(*)::bigint from upserted),
  'raw_rows_updated', 0,
  'raw_rows_deleted', 0
) as prepared_lineage_repair
from execution_gate;
