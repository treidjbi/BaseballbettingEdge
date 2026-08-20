from __future__ import annotations

import hashlib
import inspect
import re
from datetime import date


ALLOWED_PROVIDERS = ("boltodds", "propline", "the_odds", "therundown")
CLEAN_REGIME_START = date(2026, 4, 28)
MAX_CHUNK_DAYS = 7
BOLTODDS_SUSPENDED_AT = "2026-06-17T17:22:29Z"
_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|truncate|drop|alter|create|grant|revoke|"
    r"vacuum|reindex|merge|call|copy|do)\b",
    re.IGNORECASE,
)


def parse_iso_date(value: str, label: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{label} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc


def validate_provider(value: str) -> str:
    if value not in ALLOWED_PROVIDERS:
        raise ValueError("provider must be an allowed provider")
    return value


def validate_chunk(provider: str, start_date: str, end_date: str) -> tuple[str, date, date]:
    checked_provider = validate_provider(provider)
    start = parse_iso_date(start_date, "start_date")
    end = parse_iso_date(end_date, "end_date")
    if start < CLEAN_REGIME_START:
        raise ValueError("start_date is before the clean regime")
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    if (end - start).days + 1 > MAX_CHUNK_DAYS:
        raise ValueError("chunk may contain at most seven dates")
    return checked_provider, start, end


def assert_select_only(sql: str) -> None:
    scrubbed = re.sub(r"--[^\n]*", " ", sql)
    if sql.count(";") != 1 or not sql.rstrip().endswith(";"):
        raise ValueError("retention SQL must be exactly one statement")
    if not scrubbed.lstrip().lower().startswith(("with ", "select ")):
        raise ValueError("retention SQL must begin with SELECT or WITH")
    match = _FORBIDDEN_SQL.search(scrubbed)
    if match:
        raise ValueError(f"retention SQL contains prohibited token: {match.group(1).lower()}")


def build_chunk_sql(provider: str, start_date: str, end_date: str) -> str:
    checked_provider, start, end = validate_chunk(provider, start_date, end_date)
    start_literal = start.isoformat()
    end_literal = end.isoformat()
    sql = f"""with settings as (
  select
    date '{start_literal}' as start_date,
    date '{end_literal}' as end_date,
    '{checked_provider}'::text as provider,
    (date '{start_literal}'::timestamp at time zone 'America/Phoenix') as observed_start,
    ((date '{end_literal}' + 1)::timestamp at time zone 'America/Phoenix') as observed_end
),
requested_partitions as (
  select series.slate_date::date as slate_date, settings.provider
  from settings
  cross join lateral generate_series(
    settings.start_date, settings.end_date, interval '1 day'
  ) as series(slate_date)
),
target_runs as (
  select mpr.id, mpr.slate_date, mpr.provider, mpr.started_at,
         mpr.completed_at, mpr.status, mpr.request_count
  from public.market_provider_runs mpr
  where mpr.slate_date between date '{start_literal}' and date '{end_literal}'
    and mpr.provider = '{checked_provider}'
),
bounded_observed_source as (
  select
    (ms.observed_at at time zone 'America/Phoenix')::date as observed_slate_date,
    ms.id as snapshot_id,
    ms.run_id,
    ms.provider as snapshot_provider,
    ms.bookmaker_key,
    ms.normalized_player_name,
    ms.market_key,
    ms.side,
    ms.line,
    ms.observed_at,
    mpr.id as run_row_id,
    mpr.slate_date as run_slate_date,
    mpr.provider as run_provider
  from public.market_snapshots ms
  left join public.market_provider_runs mpr on mpr.id = ms.run_id
  cross join settings
  where ms.provider = '{checked_provider}'
    and ms.observed_at >= settings.observed_start
    and ms.observed_at < settings.observed_end
),
bounded_observed_lineage as (
  select
    bounded_observed_source.*,
    (
      run_row_id is not null
      and run_slate_date is distinct from observed_slate_date
      and exists (
        select 1
        from public.compact_market_line_movements cmlm
        where cmlm.slate_date = bounded_observed_source.run_slate_date
          and cmlm.provider = lower(trim(bounded_observed_source.run_provider))
          and cmlm.book_key = lower(trim(bounded_observed_source.bookmaker_key))
          and cmlm.normalized_player_name = trim(bounded_observed_source.normalized_player_name)
          and cmlm.market_key
              = coalesce(nullif(trim(bounded_observed_source.market_key), ''), 'pitcher_strikeouts')
          and cmlm.side = lower(trim(bounded_observed_source.side))
          and cmlm.line::numeric = bounded_observed_source.line::numeric
          and jsonb_typeof(cmlm.source_snapshot_ids) = 'array'
          and cmlm.source_snapshot_ids ? bounded_observed_source.snapshot_id::text
          and bounded_observed_source.observed_at between cmlm.first_seen_at and cmlm.last_seen_at
      )
    ) as slate_date_mismatch_preserved
  from bounded_observed_source
),
bounded_run_source as (
  select
    mpr.slate_date,
    mpr.provider,
    mpr.id as run_row_id,
    mpr.started_at,
    mpr.completed_at,
    mpr.status,
    mpr.request_count,
    ms.id as snapshot_id,
    ms.run_id,
    ms.provider as snapshot_provider,
    ms.bookmaker_key,
    ms.normalized_player_name,
    ms.market_key,
    ms.side,
    ms.line,
    ms.observed_at,
    ms.american_odds,
    pg_column_size(ms)::bigint as logical_bytes
  from target_runs mpr
  join public.market_snapshots ms on ms.run_id = mpr.id
),
valid_raw as (
  select
    slate_date,
    provider,
    lower(trim(bookmaker_key)) as book_key,
    trim(normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(side)) as side,
    line::numeric as line,
    observed_at,
    american_odds::integer as american_odds,
    snapshot_id as id,
    logical_bytes
  from bounded_run_source
  where snapshot_provider = provider
    and nullif(trim(bookmaker_key), '') is not null
    and nullif(trim(normalized_player_name), '') is not null
    and lower(trim(side)) in ('over', 'under')
    and line is not null
),
windowed_raw as (
  select
    slate_date, provider, book_key, normalized_player_name, market_key, side, line,
    observed_at, american_odds, logical_bytes,
    first_value(american_odds) over raw_order as first_odds,
    last_value(american_odds) over raw_order as last_odds,
    lag(american_odds) over raw_order as previous_odds
  from valid_raw
  window raw_order as (
    partition by slate_date, provider, book_key, normalized_player_name, market_key, side, line
    order by observed_at asc, id asc
    rows between unbounded preceding and unbounded following
  )
),
raw_groups as (
  select
    slate_date, provider, book_key, normalized_player_name, market_key, side, line,
    min(observed_at) as first_seen_at,
    max(observed_at) as last_seen_at,
    min(first_odds) as first_odds,
    min(last_odds) as last_odds,
    min(american_odds) as min_odds,
    max(american_odds) as max_odds,
    count(*) filter (
      where previous_odds is not null and american_odds is distinct from previous_odds
    )::integer as odds_move_count,
    count(*)::integer as snapshot_count,
    sum(logical_bytes)::bigint as raw_logical_bytes
  from windowed_raw
  group by slate_date, provider, book_key, normalized_player_name, market_key, side, line
),
bounded_compact_rows as (
  select
    cmlm.id,
    cmlm.slate_date,
    lower(trim(cmlm.provider)) as provider,
    lower(trim(cmlm.book_key)) as book_key,
    trim(cmlm.normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(cmlm.market_key), ''), 'pitcher_strikeouts') as market_key,
    cmlm.market_key as raw_market_key,
    lower(trim(cmlm.side)) as side,
    cmlm.line::numeric as line,
    cmlm.first_seen_at, cmlm.last_seen_at,
    cmlm.first_odds, cmlm.last_odds, cmlm.min_odds, cmlm.max_odds,
    cmlm.odds_move_count, cmlm.snapshot_count, cmlm.source_snapshot_ids
  from public.compact_market_line_movements cmlm
  where cmlm.slate_date between date '{start_literal}' and date '{end_literal}'
    and cmlm.provider = '{checked_provider}'
),
compact_groups as (
  select
    slate_date, provider, book_key, normalized_player_name, market_key, side, line,
    min(first_seen_at) as first_seen_at,
    max(last_seen_at) as last_seen_at,
    min(first_odds) as first_odds,
    min(last_odds) as last_odds,
    min(min_odds) as min_odds,
    max(max_odds) as max_odds,
    max(odds_move_count) as odds_move_count,
    max(snapshot_count) as snapshot_count,
    greatest(count(*) - 1, 0)::integer as compact_duplicate_count
  from bounded_compact_rows
  group by slate_date, provider, book_key, normalized_player_name, market_key, side, line
),
joined_groups as (
  select
    coalesce(raw_groups.slate_date, compact_groups.slate_date) as slate_date,
    coalesce(raw_groups.provider, compact_groups.provider) as provider,
    coalesce(raw_groups.book_key, compact_groups.book_key) as book_key,
    coalesce(
      raw_groups.normalized_player_name, compact_groups.normalized_player_name
    ) as normalized_player_name,
    coalesce(raw_groups.market_key, compact_groups.market_key) as market_key,
    coalesce(raw_groups.side, compact_groups.side) as side,
    coalesce(raw_groups.line, compact_groups.line) as line,
    raw_groups.slate_date is not null as raw_present,
    compact_groups.slate_date is not null as compact_present,
    raw_groups.first_seen_at as raw_first_seen_at,
    compact_groups.first_seen_at as compact_first_seen_at,
    raw_groups.last_seen_at as raw_last_seen_at,
    compact_groups.last_seen_at as compact_last_seen_at,
    raw_groups.first_odds as raw_first_odds,
    compact_groups.first_odds as compact_first_odds,
    raw_groups.last_odds as raw_last_odds,
    compact_groups.last_odds as compact_last_odds,
    raw_groups.min_odds as raw_min_odds,
    compact_groups.min_odds as compact_min_odds,
    raw_groups.max_odds as raw_max_odds,
    compact_groups.max_odds as compact_max_odds,
    raw_groups.odds_move_count as raw_odds_move_count,
    compact_groups.odds_move_count as compact_odds_move_count,
    raw_groups.snapshot_count as raw_snapshot_count,
    compact_groups.snapshot_count as compact_snapshot_count,
    coalesce(raw_groups.raw_logical_bytes, 0)::bigint as raw_logical_bytes,
    coalesce(compact_groups.compact_duplicate_count, 0)::integer as compact_duplicate_count
  from raw_groups
  full outer join compact_groups
    on compact_groups.slate_date = raw_groups.slate_date
   and compact_groups.provider = raw_groups.provider
   and compact_groups.book_key = raw_groups.book_key
   and compact_groups.normalized_player_name = raw_groups.normalized_player_name
   and compact_groups.market_key = raw_groups.market_key
   and compact_groups.side = raw_groups.side
   and compact_groups.line = raw_groups.line
),
unexpected_compact_rows as (
  select compact.*
  from bounded_compact_rows compact
  where not exists (
    select 1
    from raw_groups raw
    where raw.slate_date = compact.slate_date
      and raw.provider = compact.provider
      and raw.book_key = compact.book_key
      and raw.normalized_player_name = compact.normalized_player_name
      and raw.market_key = compact.market_key
      and raw.side = compact.side
      and raw.line = compact.line
  )
),
historical_extra_candidates as (
  select
    unexpected.*,
    case
      when unexpected.provider = 'boltodds'
       and unexpected.slate_date = date '2026-05-17'
       and unexpected.raw_market_key = 'pitcher_strikeouts'
      then 'may17_alias'
      when unexpected.provider = 'boltodds'
       and unexpected.slate_date = date '2026-05-18'
      then 'may18_carryover'
      else null
    end as historical_class
  from unexpected_compact_rows unexpected
),
historical_extra_source_ids as (
  select
    candidate.id as compact_id,
    candidate.historical_class,
    candidate.slate_date as compact_slate_date,
    candidate.provider, candidate.book_key, candidate.normalized_player_name,
    candidate.market_key, candidate.side, candidate.line,
    source.value as source_id_text
  from historical_extra_candidates candidate
  cross join lateral jsonb_array_elements_text(
    case
      when candidate.historical_class is not null
       and jsonb_typeof(candidate.source_snapshot_ids) = 'array'
      then candidate.source_snapshot_ids
      else '[]'::jsonb
    end
  ) source(value)
  where candidate.historical_class is not null
),
historical_extra_distinct_source_ids as (
  select distinct compact_id, source_id_text
  from historical_extra_source_ids
),
historical_extra_resolved_sources as (
  select
    candidate.id as compact_id,
    source_id.source_id_text,
    source_snapshot.id as source_snapshot_id,
    source_snapshot.run_id as source_run_id,
    source_run.id as linked_run_id,
    source_run.slate_date as canonical_slate_date,
    candidate.provider as canonical_provider,
    lower(trim(source_snapshot.bookmaker_key)) as canonical_book_key,
    trim(source_snapshot.normalized_player_name) as canonical_player_name,
    source_snapshot.market_key as canonical_market_key,
    lower(trim(source_snapshot.side)) as canonical_side,
    source_snapshot.line::numeric as canonical_line,
    (
      source_snapshot.id is not null
      and source_run.id is not null
      and source_snapshot.provider = candidate.provider
      and source_run.provider = candidate.provider
      and lower(trim(source_snapshot.bookmaker_key)) = candidate.book_key
      and trim(source_snapshot.normalized_player_name)
          = candidate.normalized_player_name
      and lower(trim(source_snapshot.side)) = candidate.side
      and source_snapshot.line::numeric = candidate.line
      and (
        (
          candidate.historical_class = 'may17_alias'
          and source_snapshot.market_key = 'Strikeouts'
          and source_run.slate_date in (date '2026-05-16', date '2026-05-17')
          and (source_snapshot.observed_at at time zone 'America/Phoenix')::date
              in (date '2026-05-16', date '2026-05-17')
        )
        or (
          candidate.historical_class = 'may18_carryover'
          and source_snapshot.market_key = candidate.raw_market_key
          and source_run.slate_date = date '2026-05-17'
          and (source_snapshot.observed_at at time zone 'America/Phoenix')::date
              = date '2026-05-17'
        )
      )
    ) as class_dimensions_match
  from historical_extra_distinct_source_ids source_id
  join historical_extra_candidates candidate
    on candidate.id = source_id.compact_id
  left join public.market_snapshots source_snapshot
    on source_snapshot.id = case
      when source_id.source_id_text
        ~* '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-5][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$'
      then source_id.source_id_text::uuid
      else null
    end
  left join public.market_provider_runs source_run
    on source_run.id = source_snapshot.run_id
),
historical_extra_listed_counts as (
  select
    compact_id,
    count(*)::bigint as listed_source_count,
    count(distinct source_id_text)::bigint as distinct_listed_source_count,
    count(*) filter (
      where source_id_text is null
         or source_id_text
            !~* '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-5][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$'
    )::bigint as invalid_source_element_count
  from historical_extra_source_ids
  group by compact_id
),
historical_extra_resolved_counts as (
  select
    compact_id,
    count(*) filter (where source_snapshot_id is not null)::bigint
      as resolved_source_count,
    count(*) filter (where linked_run_id is not null)::bigint
      as linked_run_count,
    count(*) filter (where class_dimensions_match)::bigint
      as class_dimension_match_count
  from historical_extra_resolved_sources
  group by compact_id
),
historical_extra_source_shape as (
  select
    candidate.id as compact_id,
    jsonb_typeof(candidate.source_snapshot_ids) = 'array' as source_ids_json_array,
    coalesce(listed.listed_source_count, 0)::bigint as listed_source_count,
    coalesce(listed.distinct_listed_source_count, 0)::bigint
      as distinct_listed_source_count,
    coalesce(listed.invalid_source_element_count, 0)::bigint
      as invalid_source_element_count,
    coalesce(resolved.resolved_source_count, 0)::bigint as resolved_source_count,
    coalesce(resolved.linked_run_count, 0)::bigint as linked_run_count,
    coalesce(resolved.class_dimension_match_count, 0)::bigint
      as class_dimension_match_count
  from historical_extra_candidates candidate
  left join historical_extra_listed_counts listed
    on listed.compact_id = candidate.id
  left join historical_extra_resolved_counts resolved
    on resolved.compact_id = candidate.id
),
historical_extra_canonical_group_map as (
  select distinct
    source.compact_id,
    source.canonical_slate_date as slate_date,
    source.canonical_provider as provider,
    source.canonical_book_key as book_key,
    source.canonical_player_name as normalized_player_name,
    source.canonical_market_key as market_key,
    source.canonical_side as side,
    source.canonical_line as line
  from historical_extra_resolved_sources source
  where source.class_dimensions_match
),
canonical_actual_group_keys as (
  select distinct
    slate_date, provider, book_key, normalized_player_name, market_key, side, line
  from historical_extra_canonical_group_map
),
canonical_actual_rows as (
  select
    canonical_key.slate_date,
    canonical_key.provider,
    canonical_key.book_key,
    canonical_key.normalized_player_name,
    canonical_key.market_key,
    canonical_key.side,
    canonical_key.line,
    canonical_snapshot.observed_at,
    canonical_snapshot.american_odds::integer as american_odds,
    canonical_snapshot.id
  from canonical_actual_group_keys canonical_key
  join public.market_provider_runs canonical_run
    on canonical_run.slate_date = canonical_key.slate_date
   and canonical_run.provider = canonical_key.provider
  join public.market_snapshots canonical_snapshot
    on canonical_snapshot.run_id = canonical_run.id
   and canonical_snapshot.provider = canonical_key.provider
   and lower(trim(canonical_snapshot.bookmaker_key)) = canonical_key.book_key
   and trim(canonical_snapshot.normalized_player_name)
       = canonical_key.normalized_player_name
   and coalesce(nullif(trim(canonical_snapshot.market_key), ''), 'pitcher_strikeouts')
       = canonical_key.market_key
   and lower(trim(canonical_snapshot.side)) = canonical_key.side
   and canonical_snapshot.line::numeric = canonical_key.line
   and nullif(trim(canonical_snapshot.bookmaker_key), '') is not null
   and nullif(trim(canonical_snapshot.normalized_player_name), '') is not null
   and lower(trim(canonical_snapshot.side)) in ('over', 'under')
),
windowed_canonical_actual as (
  select
    slate_date, provider, book_key, normalized_player_name, market_key, side, line,
    observed_at, american_odds, id,
    first_value(american_odds) over canonical_order as first_odds,
    last_value(american_odds) over canonical_order as last_odds,
    lag(american_odds) over canonical_order as previous_odds
  from canonical_actual_rows
  window canonical_order as (
    partition by slate_date, provider, book_key, normalized_player_name,
                 market_key, side, line
    order by observed_at asc, id asc
    rows between unbounded preceding and unbounded following
  )
),
canonical_actual_groups as (
  select
    slate_date, provider, book_key, normalized_player_name, market_key, side, line,
    min(observed_at) as first_seen_at,
    max(observed_at) as last_seen_at,
    min(first_odds) as first_odds,
    min(last_odds) as last_odds,
    min(american_odds) as min_odds,
    max(american_odds) as max_odds,
    count(*) filter (
      where previous_odds is not null and american_odds is distinct from previous_odds
    )::integer as odds_move_count,
    count(*)::integer as snapshot_count,
    array_agg(id::text order by observed_at, id) as source_snapshot_ids,
    array_agg(id::text order by id::text) as distinct_source_snapshot_ids
  from windowed_canonical_actual
  group by slate_date, provider, book_key, normalized_player_name, market_key, side, line
),
canonical_actual_compact as (
  select
    canonical_group.*,
    coalesce(compact_proof.canonical_compact_count, 0)::bigint
      as canonical_compact_count,
    (
      coalesce(compact_proof.canonical_compact_count, 0) = 1
      and coalesce(compact_proof.exact_canonical_compact_count, 0) = 1
    ) as canonical_group_exact
  from canonical_actual_groups canonical_group
  left join lateral (
    select
      count(*)::bigint as canonical_compact_count,
      count(*) filter (
        where canonical_compact.first_seen_at
                is not distinct from canonical_group.first_seen_at
          and canonical_compact.last_seen_at
                is not distinct from canonical_group.last_seen_at
          and canonical_compact.first_odds
                is not distinct from canonical_group.first_odds
          and canonical_compact.last_odds
                is not distinct from canonical_group.last_odds
          and canonical_compact.min_odds
                is not distinct from canonical_group.min_odds
          and canonical_compact.max_odds
                is not distinct from canonical_group.max_odds
          and canonical_compact.odds_move_count
                is not distinct from canonical_group.odds_move_count
          and canonical_compact.snapshot_count
                is not distinct from canonical_group.snapshot_count
          and jsonb_typeof(canonical_compact.source_snapshot_ids) = 'array'
          and coalesce((
            select array_agg(distinct compact_source.value order by compact_source.value)
            from jsonb_array_elements_text(
              case
                when jsonb_typeof(canonical_compact.source_snapshot_ids) = 'array'
                then canonical_compact.source_snapshot_ids
                else '[]'::jsonb
              end
            ) compact_source(value)
          ), '{{}}'::text[]) = canonical_group.distinct_source_snapshot_ids
      )::bigint as exact_canonical_compact_count
    from public.compact_market_line_movements canonical_compact
    where canonical_compact.slate_date = canonical_group.slate_date
      and canonical_compact.provider = canonical_group.provider
      and canonical_compact.book_key = canonical_group.book_key
      and canonical_compact.normalized_player_name
          = canonical_group.normalized_player_name
      and canonical_compact.market_key = canonical_group.market_key
      and canonical_compact.side = canonical_group.side
      and canonical_compact.line = canonical_group.line
  ) compact_proof on true
),
historical_extra_canonical_summary as (
  select
    group_map.compact_id,
    count(*)::bigint as canonical_group_count,
    count(*) filter (
      where coalesce(canonical_compact.canonical_compact_count, 0) = 1
    )::bigint as canonical_compact_count,
    count(*) filter (
      where coalesce(canonical_compact.canonical_group_exact, false)
    )::bigint as exact_canonical_group_count
  from historical_extra_canonical_group_map group_map
  left join canonical_actual_compact canonical_compact
    on canonical_compact.slate_date = group_map.slate_date
   and canonical_compact.provider = group_map.provider
   and canonical_compact.book_key = group_map.book_key
   and canonical_compact.normalized_player_name = group_map.normalized_player_name
   and canonical_compact.market_key = group_map.market_key
   and canonical_compact.side = group_map.side
   and canonical_compact.line = group_map.line
  group by group_map.compact_id
),
historical_extra_listed_source_preservation as (
  select
    source.compact_id,
    count(*) filter (
      where source.class_dimensions_match
        and exists (
          select 1
          from canonical_actual_compact canonical_compact
          where canonical_compact.slate_date = source.canonical_slate_date
            and canonical_compact.provider = source.canonical_provider
            and canonical_compact.book_key = source.canonical_book_key
            and canonical_compact.normalized_player_name
                = source.canonical_player_name
            and canonical_compact.market_key = source.canonical_market_key
            and canonical_compact.side = source.canonical_side
            and canonical_compact.line = source.canonical_line
            and canonical_compact.canonical_group_exact
            and source.source_snapshot_id::text
                = any(canonical_compact.distinct_source_snapshot_ids)
        )
    )::bigint as listed_source_preserved_count
  from historical_extra_resolved_sources source
  group by source.compact_id
),
historical_extra_proof_components as (
  select
    source_shape.compact_id,
    (
      source_shape.source_ids_json_array
      and source_shape.listed_source_count > 0
      and source_shape.distinct_listed_source_count > 0
      and source_shape.invalid_source_element_count = 0
      and source_shape.listed_source_count
          >= source_shape.distinct_listed_source_count
      and source_shape.resolved_source_count
          = source_shape.distinct_listed_source_count
      and source_shape.linked_run_count
          = source_shape.distinct_listed_source_count
      and source_shape.class_dimension_match_count
          = source_shape.distinct_listed_source_count
    ) as all_source_shape_checks_pass,
    (
      coalesce(canonical_summary.canonical_group_count, 0) > 0
      and canonical_summary.canonical_compact_count
          = canonical_summary.canonical_group_count
      and canonical_summary.exact_canonical_group_count
          = canonical_summary.canonical_group_count
    ) as all_canonical_groups_exact,
    (
      coalesce(preservation.listed_source_preserved_count, 0)
          = source_shape.distinct_listed_source_count
      and source_shape.distinct_listed_source_count > 0
    ) as all_listed_sources_preserved
  from historical_extra_source_shape source_shape
  left join historical_extra_canonical_summary canonical_summary
    on canonical_summary.compact_id = source_shape.compact_id
  left join historical_extra_listed_source_preservation preservation
    on preservation.compact_id = source_shape.compact_id
),
historical_extra_proof as (
  select
    candidate.id as compact_id,
    coalesce(proof.all_source_shape_checks_pass, false)
      and coalesce(proof.all_canonical_groups_exact, false)
      and coalesce(proof.all_listed_sources_preserved, false)
      as preserved
  from historical_extra_candidates candidate
  left join historical_extra_proof_components proof
    on proof.compact_id = candidate.id
),
historical_extra_group_proof as (
  select
    candidate.slate_date, candidate.provider, candidate.book_key,
    candidate.normalized_player_name, candidate.market_key,
    candidate.side, candidate.line,
    bool_and(proof.preserved) as preserved
  from historical_extra_candidates candidate
  join historical_extra_proof proof on proof.compact_id = candidate.id
  group by candidate.slate_date, candidate.provider, candidate.book_key,
           candidate.normalized_player_name, candidate.market_key,
           candidate.side, candidate.line
),
coverage_by_partition as (
  select
    joined_groups.slate_date,
    joined_groups.provider,
    coalesce(sum(raw_snapshot_count) filter (where raw_present), 0)::bigint as raw_snapshot_rows,
    coalesce(sum(raw_logical_bytes) filter (where raw_present), 0)::bigint as raw_logical_bytes,
    count(*) filter (where raw_present)::bigint as raw_group_count,
    count(*) filter (where compact_present)::bigint as compact_group_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_first_seen_at is not distinct from compact_first_seen_at
        and raw_last_seen_at is not distinct from compact_last_seen_at
        and raw_first_odds is not distinct from compact_first_odds
        and raw_last_odds is not distinct from compact_last_odds
        and raw_min_odds is not distinct from compact_min_odds
        and raw_max_odds is not distinct from compact_max_odds
        and raw_odds_move_count is not distinct from compact_odds_move_count
        and raw_snapshot_count is not distinct from compact_snapshot_count
    )::bigint as exact_group_count,
    count(*) filter (
      where raw_present and compact_present and (
        raw_first_seen_at is distinct from compact_first_seen_at
        or raw_last_seen_at is distinct from compact_last_seen_at
        or raw_first_odds is distinct from compact_first_odds
        or raw_last_odds is distinct from compact_last_odds
        or raw_min_odds is distinct from compact_min_odds
        or raw_max_odds is distinct from compact_max_odds
        or raw_odds_move_count is distinct from compact_odds_move_count
        or raw_snapshot_count is distinct from compact_snapshot_count
      )
    )::bigint as mismatched_group_count,
    count(*) filter (where raw_present and not compact_present)::bigint as missing_compact_group_count,
    count(*) filter (
      where compact_present and not raw_present
    )::bigint as unexpected_compact_group_count,
    count(*) filter (
      where compact_present and not raw_present
        and coalesce(historical_extra_group_proof.preserved, false)
    )::bigint as preserved_unexpected_compact_group_count,
    count(*) filter (
      where compact_present and not raw_present
        and not coalesce(historical_extra_group_proof.preserved, false)
    )::bigint as unpreserved_unexpected_compact_group_count,
    coalesce(sum(compact_duplicate_count), 0)::bigint as duplicate_compact_group_count,
    count(*) filter (where raw_present and compact_present and raw_first_seen_at is distinct from compact_first_seen_at)::bigint as first_seen_mismatch_count,
    count(*) filter (where raw_present and compact_present and raw_last_seen_at is distinct from compact_last_seen_at)::bigint as last_seen_mismatch_count,
    count(*) filter (where raw_present and compact_present and raw_first_odds is distinct from compact_first_odds)::bigint as first_odds_mismatch_count,
    count(*) filter (where raw_present and compact_present and raw_last_odds is distinct from compact_last_odds)::bigint as last_odds_mismatch_count,
    count(*) filter (where raw_present and compact_present and raw_min_odds is distinct from compact_min_odds)::bigint as min_odds_mismatch_count,
    count(*) filter (where raw_present and compact_present and raw_max_odds is distinct from compact_max_odds)::bigint as max_odds_mismatch_count,
    count(*) filter (where raw_present and compact_present and raw_odds_move_count is distinct from compact_odds_move_count)::bigint as odds_move_count_mismatch_count,
    count(*) filter (where raw_present and compact_present and raw_snapshot_count is distinct from compact_snapshot_count)::bigint as snapshot_count_mismatch_count,
    min(raw_first_seen_at) filter (where raw_present) as first_raw_seen_at,
    max(raw_last_seen_at) filter (where raw_present) as last_raw_seen_at
  from joined_groups
  left join historical_extra_group_proof
    on historical_extra_group_proof.slate_date = joined_groups.slate_date
   and historical_extra_group_proof.provider = joined_groups.provider
   and historical_extra_group_proof.book_key = joined_groups.book_key
   and historical_extra_group_proof.normalized_player_name
       = joined_groups.normalized_player_name
   and historical_extra_group_proof.market_key = joined_groups.market_key
   and historical_extra_group_proof.side = joined_groups.side
   and historical_extra_group_proof.line = joined_groups.line
  group by joined_groups.slate_date, joined_groups.provider
),
coverage_with_preservation_equation as (
  select
    coverage_by_partition.*,
    (
      unexpected_compact_group_count = preserved_unexpected_compact_group_count
        + unpreserved_unexpected_compact_group_count
    ) as preservation_equation_exact
  from coverage_by_partition
),
coverage_with_exactness as (
  select
    requested_partitions.slate_date,
    requested_partitions.provider,
    coalesce(coverage_by_partition.raw_snapshot_rows, 0)::bigint as raw_snapshot_rows,
    coalesce(coverage_by_partition.raw_logical_bytes, 0)::bigint as raw_logical_bytes,
    coalesce(coverage_by_partition.raw_group_count, 0)::bigint as raw_group_count,
    coalesce(coverage_by_partition.compact_group_count, 0)::bigint as compact_group_count,
    coalesce(coverage_by_partition.exact_group_count, 0)::bigint as exact_group_count,
    coalesce(coverage_by_partition.mismatched_group_count, 0)::bigint as mismatched_group_count,
    coalesce(coverage_by_partition.missing_compact_group_count, 0)::bigint as missing_compact_group_count,
    coalesce(coverage_by_partition.unexpected_compact_group_count, 0)::bigint as unexpected_compact_group_count,
    coalesce(
      coverage_by_partition.preserved_unexpected_compact_group_count, 0
    )::bigint as preserved_unexpected_compact_group_count,
    coalesce(
      coverage_by_partition.unpreserved_unexpected_compact_group_count, 0
    )::bigint as unpreserved_unexpected_compact_group_count,
    coalesce(coverage_by_partition.duplicate_compact_group_count, 0)::bigint as duplicate_compact_group_count,
    coalesce(coverage_by_partition.first_seen_mismatch_count, 0)::bigint as first_seen_mismatch_count,
    coalesce(coverage_by_partition.last_seen_mismatch_count, 0)::bigint as last_seen_mismatch_count,
    coalesce(coverage_by_partition.first_odds_mismatch_count, 0)::bigint as first_odds_mismatch_count,
    coalesce(coverage_by_partition.last_odds_mismatch_count, 0)::bigint as last_odds_mismatch_count,
    coalesce(coverage_by_partition.min_odds_mismatch_count, 0)::bigint as min_odds_mismatch_count,
    coalesce(coverage_by_partition.max_odds_mismatch_count, 0)::bigint as max_odds_mismatch_count,
    coalesce(coverage_by_partition.odds_move_count_mismatch_count, 0)::bigint as odds_move_count_mismatch_count,
    coalesce(coverage_by_partition.snapshot_count_mismatch_count, 0)::bigint as snapshot_count_mismatch_count,
    coverage_by_partition.first_raw_seen_at,
    coverage_by_partition.last_raw_seen_at,
    (
      coalesce(coverage_by_partition.missing_compact_group_count, 0) = 0
      and coalesce(coverage_by_partition.unexpected_compact_group_count, 0) = 0
      and coalesce(coverage_by_partition.duplicate_compact_group_count, 0) = 0
      and coalesce(coverage_by_partition.mismatched_group_count, 0) = 0
    ) as coverage_exact,
    (
      coalesce(coverage_by_partition.missing_compact_group_count, 0) = 0
      and coalesce(coverage_by_partition.duplicate_compact_group_count, 0) = 0
      and coalesce(coverage_by_partition.mismatched_group_count, 0) = 0
      and coalesce(
        coverage_by_partition.unpreserved_unexpected_compact_group_count, 0
      ) = 0
      and coalesce(coverage_by_partition.preservation_equation_exact, true)
    ) as retention_preservation_complete
  from requested_partitions
  left join coverage_with_preservation_equation coverage_by_partition
    on coverage_by_partition.slate_date = requested_partitions.slate_date
   and coverage_by_partition.provider = requested_partitions.provider
),
all_provider_anomalies as (
  select
    (ms.observed_at at time zone 'America/Phoenix')::date as slate_date,
    count(*) filter (
      where ms.provider is null
         or ms.provider not in ('boltodds', 'propline', 'the_odds', 'therundown')
    )::bigint as unknown_provider_rows
  from public.market_snapshots ms
  cross join settings
  where ms.observed_at >= settings.observed_start
    and ms.observed_at < settings.observed_end
  group by (ms.observed_at at time zone 'America/Phoenix')::date
),
anomaly_counts as (
  select
    observed_slate_date as slate_date,
    count(*) filter (where run_id is null)::bigint as rows_missing_run_id,
    count(*) filter (where run_id is not null and run_row_id is null)::bigint as rows_missing_run_row,
    count(*) filter (
      where nullif(trim(bookmaker_key), '') is null
         or nullif(trim(normalized_player_name), '') is null
         or lower(trim(side)) not in ('over', 'under')
         or line is null
    )::bigint as rows_missing_group_key,
    count(*) filter (
      where run_row_id is not null and snapshot_provider is distinct from run_provider
    )::bigint as provider_run_mismatch_rows,
    count(*) filter (
      where run_row_id is not null and run_slate_date is distinct from observed_slate_date
    )::bigint as slate_date_mismatch_rows,
    count(*) filter (
      where run_row_id is not null
        and run_slate_date is distinct from observed_slate_date
        and slate_date_mismatch_preserved
    )::bigint as preserved_slate_date_mismatch_rows,
    count(*) filter (
      where run_row_id is not null
        and run_slate_date is distinct from observed_slate_date
        and not slate_date_mismatch_preserved
    )::bigint as unpreserved_slate_date_mismatch_rows
  from bounded_observed_lineage
  group by observed_slate_date
),
source_anomalies as (
  select
    requested_partitions.slate_date,
    requested_partitions.provider,
    coalesce(anomaly_counts.rows_missing_run_id, 0)::bigint as rows_missing_run_id,
    coalesce(anomaly_counts.rows_missing_run_row, 0)::bigint as rows_missing_run_row,
    coalesce(anomaly_counts.rows_missing_group_key, 0)::bigint as rows_missing_group_key,
    coalesce(anomaly_counts.provider_run_mismatch_rows, 0)::bigint as provider_run_mismatch_rows,
    coalesce(anomaly_counts.slate_date_mismatch_rows, 0)::bigint as slate_date_mismatch_rows,
    coalesce(anomaly_counts.preserved_slate_date_mismatch_rows, 0)::bigint as preserved_slate_date_mismatch_rows,
    coalesce(anomaly_counts.unpreserved_slate_date_mismatch_rows, 0)::bigint as unpreserved_slate_date_mismatch_rows,
    coalesce(all_provider_anomalies.unknown_provider_rows, 0)::bigint as unknown_provider_rows
  from requested_partitions
  left join anomaly_counts on anomaly_counts.slate_date = requested_partitions.slate_date
  left join all_provider_anomalies on all_provider_anomalies.slate_date = requested_partitions.slate_date
),
run_summary as (
  select
    slate_date, provider,
    min(started_at) as first_run_at,
    max(coalesce(completed_at, started_at)) as last_run_at,
    count(*)::bigint as run_count,
    count(*) filter (where status = 'completed')::bigint as completed_run_count,
    count(*) filter (where status = 'failed')::bigint as failed_run_count,
    coalesce(sum(request_count), 0)::bigint as request_count
  from target_runs
  group by slate_date, provider
),
book_summary as (
  select slate_date, provider, array_agg(distinct book_key order by book_key) as books_seen
  from valid_raw
  group by slate_date, provider
),
snapshot_summary as (
  select
    slate_date, provider,
    min(observed_at) as first_snapshot_at,
    max(observed_at) as last_snapshot_at,
    count(*)::bigint as snapshot_count,
    coalesce(sum(logical_bytes), 0)::bigint as snapshot_logical_bytes
  from bounded_run_source
  group by slate_date, provider
),
heartbeat_summary as (
  select
    h.slate_date,
    h.provider,
    max(h.observed_at) as last_heartbeat_at,
    max(h.last_message_at) as last_message_at,
    count(*)::bigint as heartbeat_count
  from public.market_feed_heartbeats h
  where h.slate_date between date '{start_literal}' and date '{end_literal}'
    and h.provider = '{checked_provider}'
  group by h.slate_date, h.provider
),
candidate_runtime as (
  select
    requested_partitions.slate_date,
    requested_partitions.provider,
    run_summary.first_run_at,
    run_summary.last_run_at,
    coalesce(run_summary.run_count, 0)::bigint as run_count,
    coalesce(run_summary.completed_run_count, 0)::bigint as completed_run_count,
    coalesce(run_summary.failed_run_count, 0)::bigint as failed_run_count,
    coalesce(run_summary.request_count, 0)::bigint as request_count,
    coalesce(book_summary.books_seen, '{{}}'::text[]) as books_seen,
    snapshot_summary.first_snapshot_at,
    snapshot_summary.last_snapshot_at,
    coalesce(snapshot_summary.snapshot_count, 0)::bigint as snapshot_count,
    coalesce(snapshot_summary.snapshot_logical_bytes, 0)::bigint as snapshot_logical_bytes,
    heartbeat_summary.last_heartbeat_at,
    heartbeat_summary.last_message_at,
    coalesce(heartbeat_summary.heartbeat_count, 0)::bigint as heartbeat_count
  from requested_partitions
  left join run_summary
    on run_summary.slate_date = requested_partitions.slate_date
   and run_summary.provider = requested_partitions.provider
  left join book_summary
    on book_summary.slate_date = requested_partitions.slate_date
   and book_summary.provider = requested_partitions.provider
  left join snapshot_summary
    on snapshot_summary.slate_date = requested_partitions.slate_date
   and snapshot_summary.provider = requested_partitions.provider
  left join heartbeat_summary
    on heartbeat_summary.slate_date = requested_partitions.slate_date
   and heartbeat_summary.provider = requested_partitions.provider
)
select jsonb_build_object(
  'chunk_version', 2,
  'audit_generated_at', now(),
  'complete', true,
  'query_scope', jsonb_build_object(
    'start_date', (select start_date from settings),
    'end_date', (select end_date from settings),
    'provider', (select provider from settings),
    'timezone', 'America/Phoenix'
  ),
  'coverage', coalesce(
    (select jsonb_agg(to_jsonb(coverage_with_exactness) order by slate_date, provider)
     from coverage_with_exactness),
    '[]'::jsonb
  ),
  'source_anomalies', coalesce(
    (select jsonb_agg(to_jsonb(source_anomalies) order by slate_date, provider)
     from source_anomalies),
    '[]'::jsonb
  ),
  'candidate_runtime', coalesce(
    (select jsonb_agg(to_jsonb(candidate_runtime) order by slate_date, provider)
     from candidate_runtime),
    '[]'::jsonb
  )
) as retention_bounded_chunk;"""
    assert_select_only(sql)
    return sql


def build_runtime_boundary_sql(candidate_end_date: str) -> str:
    candidate_end = parse_iso_date(candidate_end_date, "candidate_end_date")
    if candidate_end < CLEAN_REGIME_START:
        raise ValueError("candidate_end_date is before the clean regime")
    candidate_literal = candidate_end.isoformat()
    providers = ", ".join(f"'{provider}'" for provider in ALLOWED_PROVIDERS)
    sql = f"""with settings as (
  select
    date '{candidate_literal}' as candidate_end_date,
    (date '{CLEAN_REGIME_START.isoformat()}'::timestamp at time zone 'America/Phoenix') as candidate_observed_start,
    ((date '{candidate_literal}' + 1)::timestamp at time zone 'America/Phoenix') as candidate_observed_end
),
providers as (
  select unnest(array[{providers}]::text[]) as provider
),
runtime_rows as (
  select
    providers.provider,
    current_run.latest_run_at as current_latest_run_at,
    current_snapshot.latest_snapshot_at as current_latest_snapshot_at,
    current_heartbeat.latest_heartbeat_at as current_latest_heartbeat_at,
    current_message.latest_message_at as current_latest_message_at,
    candidate_run.latest_run_at as candidate_latest_run_at,
    candidate_snapshot.latest_snapshot_at as candidate_latest_snapshot_at,
    candidate_heartbeat.latest_heartbeat_at as candidate_latest_heartbeat_at,
    candidate_message.latest_message_at as candidate_latest_message_at,
    case
      when providers.provider = 'boltodds' and (
        current_run.latest_run_at > timestamp with time zone '{BOLTODDS_SUSPENDED_AT}'
        or current_snapshot.latest_snapshot_at > timestamp with time zone '{BOLTODDS_SUSPENDED_AT}'
        or current_heartbeat.latest_heartbeat_at > timestamp with time zone '{BOLTODDS_SUSPENDED_AT}'
        or current_message.latest_message_at > timestamp with time zone '{BOLTODDS_SUSPENDED_AT}'
      ) then true
      else false
    end as post_boltodds_suspension
  from providers
  cross join settings
  left join lateral (
    select max(coalesce(mpr.completed_at, mpr.started_at)) as latest_run_at
    from public.market_provider_runs mpr
    where mpr.provider = providers.provider
  ) as current_run on true
  left join lateral (
    select ms.observed_at as latest_snapshot_at
    from public.market_snapshots ms
    where ms.provider = providers.provider
    order by ms.observed_at desc, ms.id desc limit 1
  ) as current_snapshot on true
  left join lateral (
    select h.observed_at as latest_heartbeat_at
    from public.market_feed_heartbeats h
    where h.provider = providers.provider
    order by h.observed_at desc, h.id desc limit 1
  ) as current_heartbeat on true
  left join lateral (
    select max(h.last_message_at) as latest_message_at
    from public.market_feed_heartbeats h
    where h.provider = providers.provider
  ) as current_message on true
  left join lateral (
    select max(coalesce(mpr.completed_at, mpr.started_at)) as latest_run_at
    from public.market_provider_runs mpr
    where mpr.provider = providers.provider
      and mpr.slate_date between date '{CLEAN_REGIME_START.isoformat()}' and settings.candidate_end_date
  ) as candidate_run on true
  left join lateral (
    select ms.observed_at as latest_snapshot_at
    from public.market_snapshots ms
    where ms.provider = providers.provider
      and ms.observed_at >= settings.candidate_observed_start
      and ms.observed_at < settings.candidate_observed_end
    order by ms.observed_at desc, ms.id desc limit 1
  ) as candidate_snapshot on true
  left join lateral (
    select h.observed_at as latest_heartbeat_at
    from public.market_feed_heartbeats h
    where h.provider = providers.provider
      and h.observed_at >= settings.candidate_observed_start
      and h.observed_at < settings.candidate_observed_end
    order by h.observed_at desc, h.id desc limit 1
  ) as candidate_heartbeat on true
  left join lateral (
    select max(h.last_message_at) as latest_message_at
    from public.market_feed_heartbeats h
    where h.provider = providers.provider
      and h.observed_at >= settings.candidate_observed_start
      and h.observed_at < settings.candidate_observed_end
  ) as candidate_message on true
)
select jsonb_build_object(
  'runtime_version', 2,
  'generated_at', now(),
  'candidate_end_date', (select candidate_end_date from settings),
  'providers', coalesce(
    (select jsonb_agg(to_jsonb(runtime_rows) order by provider) from runtime_rows),
    '[]'::jsonb
  )
) as retention_runtime_boundary;"""
    assert_select_only(sql)
    return sql


def query_contract_sha256() -> str:
    contract = "\n".join((
        inspect.getsource(build_chunk_sql),
        inspect.getsource(build_runtime_boundary_sql),
        ",".join(ALLOWED_PROVIDERS),
    ))
    return hashlib.sha256(contract.encode("utf-8")).hexdigest()
