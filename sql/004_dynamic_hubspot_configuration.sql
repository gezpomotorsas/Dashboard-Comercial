-- Configuración dinámica HubSpot: mapeos semánticos, etapas, dimensiones de negocio
-- Idempotente. No borra históricos.

-- ---------------------------------------------------------------------------
-- Mapeos semánticos campo HubSpot <-> concepto analítico
-- ---------------------------------------------------------------------------

create table if not exists hubspot_field_mappings (
    id uuid primary key default gen_random_uuid(),
    object_type text not null,
    semantic_key text not null,
    hubspot_property_name text not null,
    hubspot_property_label text,
    source text not null check (source in ('standard', 'custom', 'metadata_discovery', 'manual_configuration')),
    priority int not null default 100,
    is_active boolean not null default true,
    validated_at timestamptz,
    validation_status text not null default 'pending'
        check (validation_status in ('pending', 'valid', 'invalid')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (object_type, semantic_key, hubspot_property_name)
);

create index if not exists idx_field_mappings_semantic
    on hubspot_field_mappings (object_type, semantic_key, is_active, priority);

-- ---------------------------------------------------------------------------
-- Clasificación de etapas (fallback configurable)
-- ---------------------------------------------------------------------------

create table if not exists hubspot_stage_classifications (
    id uuid primary key default gen_random_uuid(),
    pipeline_id text not null,
    stage_id text not null,
    normalized_status text not null check (normalized_status in ('open', 'won', 'lost', 'unknown')),
    source text not null default 'manual_configuration',
    is_active boolean not null default true,
    validated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (pipeline_id, stage_id)
);

-- ---------------------------------------------------------------------------
-- Dimensiones de negocio (marca, modelo, etc.)
-- ---------------------------------------------------------------------------

create table if not exists business_dimension_mappings (
    id uuid primary key default gen_random_uuid(),
    dimension_type text not null,
    source_object_type text not null default 'deals',
    source_type text not null,
    source_value text not null,
    normalized_value text not null,
    display_label text not null,
    is_active boolean not null default true,
    priority int not null default 100,
    validated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (dimension_type, source_type, source_value)
);

create index if not exists idx_business_dimension_lookup
    on business_dimension_mappings (dimension_type, source_type, is_active, priority);

-- ---------------------------------------------------------------------------
-- Tipos de asociación HubSpot (caché metadata)
-- ---------------------------------------------------------------------------

create table if not exists hubspot_association_types (
    id uuid primary key default gen_random_uuid(),
    from_object_type text not null,
    to_object_type text not null,
    association_type_id text,
    association_category text,
    association_label text,
    is_active boolean not null default true,
    raw_payload jsonb not null default '{}'::jsonb,
    synced_at timestamptz not null default now(),
  unique (from_object_type, to_object_type, association_type_id, association_category)
);

-- ---------------------------------------------------------------------------
-- Ejecuciones de refresh de metadata
-- ---------------------------------------------------------------------------

create table if not exists hubspot_metadata_refresh_runs (
    id uuid primary key default gen_random_uuid(),
    status text not null check (status in ('started', 'completed', 'completed_with_errors', 'failed')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    properties_synced int not null default 0,
    pipelines_synced int not null default 0,
    stages_synced int not null default 0,
    owners_synced int not null default 0,
    association_types_synced int not null default 0,
    mappings_validated int not null default 0,
    mappings_invalidated int not null default 0,
    field_mapping_version int not null default 1,
    dimension_mapping_version int not null default 1,
    error_message text,
    metadata jsonb not null default '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Seeds: mapeos semánticos estándar HubSpot
-- ---------------------------------------------------------------------------

insert into hubspot_field_mappings (
    object_type, semantic_key, hubspot_property_name, hubspot_property_label, source, priority
) values
    ('deals', 'deal_amount', 'amount', 'Amount', 'standard', 10),
    ('deals', 'deal_stage', 'dealstage', 'Deal Stage', 'standard', 10),
    ('deals', 'deal_pipeline', 'pipeline', 'Pipeline', 'standard', 10),
    ('deals', 'deal_close_date', 'closedate', 'Close Date', 'standard', 10),
    ('deals', 'deal_closed_won', 'hs_is_closed_won', 'Is Closed Won', 'standard', 10),
    ('deals', 'deal_closed_lost', 'hs_is_closed_lost', 'Is Closed Lost', 'standard', 10),
    ('deals', 'owner', 'hubspot_owner_id', 'Owner', 'standard', 10),
    ('contacts', 'owner', 'hubspot_owner_id', 'Owner', 'standard', 10),
    ('contacts', 'contact_brand_interest', 'marca', 'Marca', 'custom', 20),
    ('contacts', 'contact_brand_interest', 'marca_de_interes', 'Marca de interés', 'custom', 30),
    ('contacts', 'contact_model_interest', 'modelo_solicitado', 'Modelo solicitado', 'custom', 20),
    ('contacts', 'contact_source', 'hs_analytics_source', 'Original Source', 'standard', 20),
    ('contacts', 'contact_source', 'origen', 'Origen', 'custom', 30),
    ('deals', 'deal_brand', 'marca', 'Marca', 'custom', 20)
on conflict (object_type, semantic_key, hubspot_property_name) do nothing;

-- Seeds: mapeo pipeline -> marca (migración desde configuración previa)
insert into business_dimension_mappings (
    dimension_type, source_object_type, source_type, source_value, normalized_value, display_label, priority
) values
    ('brand', 'deals', 'pipeline_id', 'default', 'shacman', 'Shacman', 10),
    ('brand', 'deals', 'pipeline_id', '1000390393', 'voyah', 'Voyah', 10),
    ('brand', 'deals', 'pipeline_id', '1963395799', 'mhero', 'MHero', 10)
on conflict (dimension_type, source_type, source_value) do update set
    normalized_value = excluded.normalized_value,
    display_label = excluded.display_label,
    updated_at = now();
