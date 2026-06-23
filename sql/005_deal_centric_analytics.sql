-- Fase 3: Analítica centrada en negocios (deal_analytics)
-- Ejecutar manualmente en Supabase SQL Editor después de 001-004.
-- Idempotente. No borra históricos.

-- ---------------------------------------------------------------------------
-- Historial de etapas por negocio
-- ---------------------------------------------------------------------------

create table if not exists hubspot_deal_stage_history (
    id uuid primary key default gen_random_uuid(),
    deal_hubspot_id text not null,
    pipeline_id text,
    stage_id text not null,
    entered_at timestamptz,
    exited_at timestamptz,
    duration_seconds bigint,
    is_current boolean not null default false,
    source text not null default 'sync',
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now(),
    unique (deal_hubspot_id, stage_id, entered_at)
);

create index if not exists idx_stage_history_deal
    on hubspot_deal_stage_history (deal_hubspot_id, is_current desc, entered_at desc);

-- ---------------------------------------------------------------------------
-- Tabla analítica central: 1 fila por negocio
-- ---------------------------------------------------------------------------

create table if not exists deal_analytics (
    deal_id text primary key,

    deal_name text,

    pipeline_id text,
    pipeline_label text,

    stage_id text,
    stage_label text,
    stage_display_order int,

    owner_id text,
    owner_name text,
    owner_active boolean,

    brand_value text not null default 'unknown',
    brand_label text not null default 'Unknown',

    model_value text,
    model_label text,

    source_value text,
    source_label text,

    status text not null default 'unknown'
        check (status in ('open', 'won', 'lost', 'unknown')),
    status_source text,

    amount numeric,
    currency text default 'COP',

    created_at timestamptz,
    closed_at timestamptz,
    last_modified_at timestamptz,

    age_days int,
    days_in_current_stage int,

    first_activity_at timestamptz,
    last_activity_at timestamptz,
    days_since_last_activity int,

    first_effective_contact_at timestamptz,
    first_response_minutes numeric,

    contact_count int not null default 0,
    activity_count int not null default 0,
    effective_contact_count int not null default 0,

    call_count int not null default 0,
    communication_count int not null default 0,
    completed_meeting_count int not null default 0,
    task_count int not null default 0,
    note_count int not null default 0,

    stage_change_count int not null default 0,
    stages_visited_count int not null default 0,

    has_contact boolean not null default false,
    has_owner boolean not null default false,
    has_amount boolean not null default false,
    has_activity boolean not null default false,
    has_effective_contact boolean not null default false,

    has_recent_activity_7d boolean not null default false,
    has_recent_activity_30d boolean not null default false,
    has_recent_activity_60d boolean not null default false,

    is_open boolean not null default false,
    is_won boolean not null default false,
    is_lost boolean not null default false,
    is_stale boolean not null default false,
    is_unknown_pipeline boolean not null default false,

    stale_reason text,

    data_completeness_score numeric,
    activity_data_status text not null default 'partial_60d',
    stage_history_status text not null default 'partial',

    metadata_snapshot_at timestamptz,
    field_mapping_version int not null default 1,
    dimension_mapping_version int not null default 1,
    calculated_at timestamptz not null default now()
);

create index if not exists idx_deal_analytics_pipeline on deal_analytics (pipeline_id);
create index if not exists idx_deal_analytics_stage on deal_analytics (stage_id);
create index if not exists idx_deal_analytics_owner on deal_analytics (owner_id);
create index if not exists idx_deal_analytics_status on deal_analytics (status);
create index if not exists idx_deal_analytics_brand on deal_analytics (brand_value);
create index if not exists idx_deal_analytics_model on deal_analytics (model_value);
create index if not exists idx_deal_analytics_created on deal_analytics (created_at);
create index if not exists idx_deal_analytics_closed on deal_analytics (closed_at);
create index if not exists idx_deal_analytics_age on deal_analytics (age_days);
create index if not exists idx_deal_analytics_stage_age on deal_analytics (days_in_current_stage);
create index if not exists idx_deal_analytics_inactivity on deal_analytics (days_since_last_activity);
create index if not exists idx_deal_analytics_last_activity on deal_analytics (last_activity_at);
create index if not exists idx_deal_analytics_stale on deal_analytics (is_stale);

-- ---------------------------------------------------------------------------
-- Ejecuciones de refresh deal_analytics
-- ---------------------------------------------------------------------------

create table if not exists deal_analytics_runs (
    id uuid primary key default gen_random_uuid(),
    status text not null check (status in ('started', 'running', 'completed', 'completed_with_errors', 'failed')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    deals_processed int not null default 0,
    deals_inserted int not null default 0,
    deals_updated int not null default 0,
    deals_failed int not null default 0,
    metadata_version text,
    field_mapping_version int,
    dimension_mapping_version int,
    duration_seconds numeric,
    error_message text,
    errors jsonb not null default '[]'::jsonb,
    metadata jsonb not null default '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Definiciones KPI (entity_grain = deal)
-- ---------------------------------------------------------------------------

create table if not exists kpi_definitions (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    description text,
    entity_grain text not null default 'deal',
    category text not null,
    population_definition jsonb not null default '{}'::jsonb,
    measure_definition jsonb not null default '{}'::jsonb,
    formula_definition jsonb not null default '{}'::jsonb,
    default_dimensions jsonb not null default '[]'::jsonb,
    allowed_dimensions jsonb not null default '[]'::jsonb,
    time_basis text not null default 'snapshot',
    required_semantic_fields jsonb not null default '[]'::jsonb,
    required_data_sources jsonb not null default '[]'::jsonb,
    unit text,
    direction text,
    formula_version text not null default '1.0',
    is_active boolean not null default true,
    configuration jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Buckets configurables para distribuciones
-- ---------------------------------------------------------------------------

create table if not exists analytics_bucket_config (
    id uuid primary key default gen_random_uuid(),
    bucket_type text not null unique,
    buckets jsonb not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

insert into analytics_bucket_config (bucket_type, buckets) values
    ('deal_age', '[
        {"key":"0-30","min":0,"max":30},
        {"key":"31-60","min":31,"max":60},
        {"key":"61-90","min":61,"max":90},
        {"key":"91-180","min":91,"max":180},
        {"key":"181-365","min":181,"max":365},
        {"key":"366+","min":366,"max":null}
    ]'::jsonb),
    ('stage_age', '[
        {"key":"0-7","min":0,"max":7},
        {"key":"8-15","min":8,"max":15},
        {"key":"16-30","min":16,"max":30},
        {"key":"31-60","min":31,"max":60},
        {"key":"61-90","min":61,"max":90},
        {"key":"91+","min":91,"max":null}
    ]'::jsonb),
    ('inactivity', '[
        {"key":"0-7","min":0,"max":7},
        {"key":"8-15","min":8,"max":15},
        {"key":"16-30","min":16,"max":30},
        {"key":"31-60","min":31,"max":60},
        {"key":"61-90","min":61,"max":90},
        {"key":"91+","min":91,"max":null},
        {"key":"sin_actividad","min":null,"max":null,"no_activity":true}
    ]'::jsonb),
    ('activity_count', '[
        {"key":"0","min":0,"max":0},
        {"key":"1-2","min":1,"max":2},
        {"key":"3-5","min":3,"max":5},
        {"key":"6-10","min":6,"max":10},
        {"key":"11-20","min":11,"max":20},
        {"key":"21+","min":21,"max":null}
    ]'::jsonb),
    ('effective_contact_count', '[
        {"key":"0","min":0,"max":0},
        {"key":"1","min":1,"max":1},
        {"key":"2-3","min":2,"max":3},
        {"key":"4-5","min":4,"max":5},
        {"key":"6+","min":6,"max":null}
    ]'::jsonb)
on conflict (bucket_type) do update set buckets = excluded.buckets, updated_at = now();

-- ---------------------------------------------------------------------------
-- Seeds adicionales de mapeos semánticos para deal analytics
-- ---------------------------------------------------------------------------

insert into hubspot_field_mappings (
    object_type, semantic_key, hubspot_property_name, hubspot_property_label, source, priority
) values
    ('deals', 'deal_name', 'dealname', 'Deal Name', 'standard', 10),
    ('deals', 'deal_owner', 'hubspot_owner_id', 'Owner', 'standard', 10),
    ('deals', 'deal_created_at', 'createdate', 'Create Date', 'standard', 10),
    ('deals', 'deal_closed', 'hs_is_closed', 'Is Closed', 'standard', 10),
    ('deals', 'deal_model', 'modelo_solicitado', 'Modelo solicitado', 'custom', 20),
    ('deals', 'deal_source', 'hs_analytics_source', 'Original Source', 'standard', 20),
    ('deals', 'deal_source', 'origen', 'Origen', 'custom', 30),
    ('deals', 'deal_loss_reason', 'closed_lost_reason', 'Closed Lost Reason', 'standard', 20),
    ('deals', 'deal_vehicle_line', 'linea_de_negocio', 'Línea de negocio', 'custom', 30)
on conflict (object_type, semantic_key, hubspot_property_name) do nothing;

-- ---------------------------------------------------------------------------
-- Seeds KPI definitions (documentación ejecutable)
-- ---------------------------------------------------------------------------

insert into kpi_definitions (code, name, category, time_basis, unit, direction, population_definition, measure_definition, formula_definition, required_semantic_fields) values
    ('total_deals', 'Total negocios', 'portfolio', 'snapshot', 'count', 'informational',
     '{"filter":"all_deals"}'::jsonb, '{"field":"deal_id","agg":"count"}'::jsonb, '{"type":"count"}'::jsonb, '[]'::jsonb),
    ('open_deals', 'Negocios abiertos', 'portfolio', 'snapshot', 'count', 'informational',
     '{"status":"open"}'::jsonb, '{"field":"deal_id","agg":"count"}'::jsonb, '{"type":"count"}'::jsonb, '["deal_stage"]'::jsonb),
    ('open_pipeline_amount', 'Pipeline abierto', 'portfolio', 'snapshot', 'currency', 'higher_is_better',
     '{"status":"open"}'::jsonb, '{"field":"amount","agg":"sum"}'::jsonb, '{"type":"sum"}'::jsonb, '["deal_amount"]'::jsonb),
    ('close_rate', 'Tasa de cierre', 'conversion', 'closed_population', 'percent', 'higher_is_better',
     '{"status_in":["won","lost"]}'::jsonb, '{"formula":"won/(won+lost)"}'::jsonb, '{"type":"ratio"}'::jsonb, '["deal_stage","deal_closed_won","deal_closed_lost"]'::jsonb),
    ('stale_deals', 'Negocios estancados', 'stale', 'snapshot', 'count', 'lower_is_better',
     '{"is_stale":true}'::jsonb, '{"field":"deal_id","agg":"count"}'::jsonb, '{"type":"count"}'::jsonb, '[]'::jsonb)
on conflict (code) do nothing;

-- Vista agregada por asesor (derivada, no duplica deals)
create or replace view owner_deal_analytics as
select
    owner_id,
    max(owner_name) as owner_name,
    bool_or(coalesce(owner_active, false)) as owner_active,
    count(*)::int as assigned_deals,
    count(*) filter (where is_open)::int as open_deals,
    count(*) filter (where is_won)::int as won_deals,
    count(*) filter (where is_lost)::int as lost_deals,
    count(*) filter (where status = 'unknown')::int as unknown_deals,
    coalesce(sum(amount) filter (where is_open), 0) as open_pipeline_amount,
    coalesce(sum(amount) filter (where is_won), 0) as won_amount,
    count(*) filter (where has_recent_activity_7d)::int as managed_7d,
    count(*) filter (where has_recent_activity_30d)::int as managed_30d,
    count(*) filter (where has_recent_activity_60d)::int as managed_60d,
    count(*) filter (where not has_activity)::int as without_activity,
    count(*) filter (where not has_effective_contact)::int as without_effective_contact,
    count(*) filter (where is_stale)::int as stale_deals,
    coalesce(sum(amount) filter (where is_stale), 0) as stale_pipeline_amount,
    avg(activity_count)::numeric as average_activities_per_deal,
    percentile_cont(0.5) within group (order by activity_count)::numeric as median_activities_per_deal,
    case
        when count(*) filter (where is_won or is_lost) > 0
        then round(
            count(*) filter (where is_won)::numeric
            / nullif(count(*) filter (where is_won or is_lost), 0) * 100, 2
        )
        else null
    end as close_rate,
    avg(age_days) filter (where is_won and closed_at is not null and created_at is not null)::numeric
        as average_sales_cycle_days,
    percentile_cont(0.5) within group (order by age_days)
        filter (where is_won and closed_at is not null and created_at is not null)::numeric
        as median_sales_cycle_days,
    count(*) filter (where not has_owner or not has_contact or not has_amount)::int as data_quality_issues
from deal_analytics
where owner_id is not null
group by owner_id;
