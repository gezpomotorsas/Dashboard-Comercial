-- Grupos comerciales de etapa + columnas en deal_analytics
-- Idempotente. Las 3 marcas vehículo comparten semántica de etapa por label.

alter table deal_analytics add column if not exists commercial_group text;
alter table deal_analytics add column if not exists commercial_group_label text;
alter table deal_analytics add column if not exists commercial_group_order int;
alter table deal_analytics add column if not exists is_stale_45d boolean not null default false;

create index if not exists idx_deal_analytics_commercial_group
    on deal_analytics (brand_value, commercial_group, status);

create index if not exists idx_deal_analytics_brand_owner
    on deal_analytics (brand_value, owner_id);

-- Overrides opcionales por pipeline/etapa (si el label no basta)
create table if not exists hubspot_stage_commercial_groups (
    id uuid primary key default gen_random_uuid(),
    pipeline_id text not null,
    stage_id text not null,
    commercial_group text not null,
    commercial_group_label text not null,
    display_order int not null default 100,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (pipeline_id, stage_id)
);
