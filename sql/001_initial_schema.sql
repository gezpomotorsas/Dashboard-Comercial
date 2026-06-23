-- Esquema inicial idempotente para gezpomotor-hubspot-extractor
-- Ejecutar en Supabase SQL Editor.
--
-- NOTA DE SEGURIDAD:
-- La SUPABASE_SECRET_KEY (sb_secret_...) puede usarse desde backend con acceso elevado.
-- Un cliente público futuro deberá usar publishable key + políticas RLS específicas.
-- No desactivamos RLS globalmente; las tablas quedan protegidas por defecto.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Metadatos
-- ---------------------------------------------------------------------------

create table if not exists hubspot_properties (
    id uuid primary key default gen_random_uuid(),
    object_type text not null,
    name text not null,
    label text,
    type text,
    field_type text,
    group_name text,
    description text,
    options jsonb not null default '[]'::jsonb,
    calculated boolean,
    hidden boolean,
    created_at_hubspot timestamptz,
    updated_at_hubspot timestamptz,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now(),
    unique (object_type, name)
);

create table if not exists hubspot_owners (
    id uuid primary key default gen_random_uuid(),
    hubspot_id text not null unique,
    email text,
    first_name text,
    last_name text,
    user_id bigint,
    teams jsonb not null default '[]'::jsonb,
    archived boolean not null default false,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now()
);

create table if not exists hubspot_pipelines (
    id uuid primary key default gen_random_uuid(),
    pipeline_id text not null unique,
    label text,
    display_order int,
    archived boolean not null default false,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now()
);

create table if not exists hubspot_pipeline_stages (
    id uuid primary key default gen_random_uuid(),
    pipeline_id text not null,
    stage_id text not null,
    label text,
    display_order int,
    metadata jsonb not null default '{}'::jsonb,
    archived boolean not null default false,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now(),
    unique (pipeline_id, stage_id)
);

-- ---------------------------------------------------------------------------
-- Objetos CRM
-- ---------------------------------------------------------------------------

create table if not exists hubspot_contacts (
    id uuid primary key default gen_random_uuid(),
    hubspot_id text not null unique,
    created_at_hubspot timestamptz,
    updated_at_hubspot timestamptz,
    archived boolean not null default false,
    properties jsonb not null default '{}'::jsonb,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now()
);

create table if not exists hubspot_deals (
    id uuid primary key default gen_random_uuid(),
    hubspot_id text not null unique,
    created_at_hubspot timestamptz,
    updated_at_hubspot timestamptz,
    archived boolean not null default false,
    properties jsonb not null default '{}'::jsonb,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now(),
    pipeline_id text,
    dealstage_id text,
    brand text
);

create table if not exists hubspot_calls (
    id uuid primary key default gen_random_uuid(),
    hubspot_id text not null unique,
    created_at_hubspot timestamptz,
    updated_at_hubspot timestamptz,
    archived boolean not null default false,
    properties jsonb not null default '{}'::jsonb,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now()
);

create table if not exists hubspot_meetings (
    id uuid primary key default gen_random_uuid(),
    hubspot_id text not null unique,
    created_at_hubspot timestamptz,
    updated_at_hubspot timestamptz,
    archived boolean not null default false,
    properties jsonb not null default '{}'::jsonb,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now()
);

create table if not exists hubspot_tasks (
    id uuid primary key default gen_random_uuid(),
    hubspot_id text not null unique,
    created_at_hubspot timestamptz,
    updated_at_hubspot timestamptz,
    archived boolean not null default false,
    properties jsonb not null default '{}'::jsonb,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now()
);

create table if not exists hubspot_emails (
    id uuid primary key default gen_random_uuid(),
    hubspot_id text not null unique,
    created_at_hubspot timestamptz,
    updated_at_hubspot timestamptz,
    archived boolean not null default false,
    properties jsonb not null default '{}'::jsonb,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now()
);

create table if not exists hubspot_communications (
    id uuid primary key default gen_random_uuid(),
    hubspot_id text not null unique,
    created_at_hubspot timestamptz,
    updated_at_hubspot timestamptz,
    archived boolean not null default false,
    properties jsonb not null default '{}'::jsonb,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now()
);

create table if not exists hubspot_notes (
    id uuid primary key default gen_random_uuid(),
    hubspot_id text not null unique,
    created_at_hubspot timestamptz,
    updated_at_hubspot timestamptz,
    archived boolean not null default false,
    properties jsonb not null default '{}'::jsonb,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now()
);

create table if not exists hubspot_associations (
    id uuid primary key default gen_random_uuid(),
    from_object_type text not null,
    from_hubspot_id text not null,
    to_object_type text not null,
    to_hubspot_id text not null,
    association_type_id int,
    association_category text,
    association_label text,
    synced_at timestamptz not null default now(),
    unique (from_object_type, from_hubspot_id, to_object_type, to_hubspot_id, association_type_id)
);

-- ---------------------------------------------------------------------------
-- Control de sincronización
-- ---------------------------------------------------------------------------

create table if not exists sync_runs (
    id uuid primary key default gen_random_uuid(),
    source text not null default 'hubspot',
    object_type text not null,
    sync_type text not null,
    status text not null check (status in ('started', 'running', 'completed', 'completed_with_errors', 'failed')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    records_found int not null default 0,
    records_processed int not null default 0,
    records_inserted int not null default 0,
    records_updated int not null default 0,
    records_failed int not null default 0,
    error_message text,
    metadata jsonb not null default '{}'::jsonb
);

create table if not exists sync_errors (
    id uuid primary key default gen_random_uuid(),
    sync_run_id uuid not null references sync_runs(id) on delete cascade,
    object_type text not null,
    hubspot_id text,
    error_type text not null,
    error_message text not null,
    http_status int,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists sync_cursors (
    object_type text primary key,
    last_successful_sync_at timestamptz,
    last_after text,
    updated_at timestamptz not null default now()
);

-- Índices útiles
create index if not exists idx_hubspot_deals_brand on hubspot_deals (brand);
create index if not exists idx_hubspot_deals_pipeline on hubspot_deals (pipeline_id);
create index if not exists idx_sync_runs_object_type on sync_runs (object_type);
create index if not exists idx_sync_errors_sync_run on sync_errors (sync_run_id);
