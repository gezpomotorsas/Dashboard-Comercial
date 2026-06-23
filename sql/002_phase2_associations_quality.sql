-- Migración fase 2: asociaciones ampliadas + calidad de datos
-- Idempotente. No borra datos existentes.

-- ---------------------------------------------------------------------------
-- hubspot_associations: columnas adicionales
-- ---------------------------------------------------------------------------

alter table hubspot_associations
    add column if not exists raw_payload jsonb not null default '{}'::jsonb;

alter table hubspot_associations
    add column if not exists is_active boolean not null default true;

alter table hubspot_associations
    add column if not exists last_seen_at timestamptz;

create index if not exists idx_hubspot_assoc_from
    on hubspot_associations (from_object_type, from_hubspot_id);

create index if not exists idx_hubspot_assoc_to
    on hubspot_associations (to_object_type, to_hubspot_id);

create index if not exists idx_hubspot_assoc_active
    on hubspot_associations (is_active) where is_active = true;

-- ---------------------------------------------------------------------------
-- Calidad de datos
-- ---------------------------------------------------------------------------

create table if not exists data_quality_rules (
    id uuid primary key default gen_random_uuid(),
    code text not null unique,
    name text not null,
    description text,
    object_type text not null,
    severity text not null check (severity in ('info', 'warning', 'critical')),
    is_active boolean not null default true,
    category text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists data_quality_runs (
    id uuid primary key default gen_random_uuid(),
    status text not null check (status in ('started', 'running', 'completed', 'completed_with_errors', 'failed')),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    rules_executed int not null default 0,
    records_evaluated int not null default 0,
    issues_found int not null default 0,
    error_message text,
    metadata jsonb not null default '{}'::jsonb
);

create table if not exists data_quality_results (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references data_quality_runs(id) on delete cascade,
    rule_id uuid references data_quality_rules(id) on delete set null,
    rule_code text not null,
    object_type text not null,
    hubspot_id text,
    severity text not null check (severity in ('info', 'warning', 'critical')),
    message text not null,
    details jsonb not null default '{}'::jsonb,
    issue_key text not null,
    detected_at timestamptz not null default now(),
    resolved_at timestamptz,
    is_resolved boolean not null default false,
    unique (rule_code, object_type, hubspot_id, issue_key)
);

create index if not exists idx_dq_results_rule_code on data_quality_results (rule_code);
create index if not exists idx_dq_results_object_type on data_quality_results (object_type);
create index if not exists idx_dq_results_hubspot_id on data_quality_results (hubspot_id);
create index if not exists idx_dq_results_severity on data_quality_results (severity);
create index if not exists idx_dq_results_is_resolved on data_quality_results (is_resolved);
create index if not exists idx_dq_results_detected_at on data_quality_results (detected_at);

-- Reglas iniciales
insert into data_quality_rules (code, name, description, object_type, severity, category) values
    ('CONTACT_WITHOUT_OWNER', 'Contacto sin propietario', 'El contacto no tiene hubspot_owner_id', 'contacts', 'warning', 'ownership'),
    ('CONTACT_WITHOUT_EMAIL_AND_PHONE', 'Sin email ni teléfono', 'El contacto no tiene email ni teléfono', 'contacts', 'critical', 'contactability'),
    ('CONTACT_WITHOUT_LIFECYCLE_STAGE', 'Sin etapa de ciclo de vida', 'lifecyclestage vacío', 'contacts', 'info', 'lifecycle'),
    ('CONTACT_WITHOUT_SOURCE', 'Sin fuente', 'Sin propiedad de origen conocida', 'contacts', 'info', 'attribution'),
    ('CONTACT_WITHOUT_BRAND', 'Sin marca inferible', 'No se pudo inferir marca del contacto', 'contacts', 'warning', 'brand'),
    ('CONTACT_WITH_INVALID_EMAIL', 'Email inválido', 'Formato de email inválido', 'contacts', 'warning', 'contactability'),
    ('CONTACT_WITHOUT_NAME', 'Sin nombre', 'firstname y lastname vacíos', 'contacts', 'info', 'identity'),
    ('DEAL_WITHOUT_OWNER', 'Negocio sin propietario', 'Sin hubspot_owner_id', 'deals', 'warning', 'ownership'),
    ('DEAL_WITHOUT_CONTACT', 'Negocio sin contacto', 'Sin asociación contact-deal', 'deals', 'critical', 'associations'),
    ('DEAL_WITHOUT_PIPELINE', 'Sin pipeline', 'pipeline vacío', 'deals', 'critical', 'pipeline'),
    ('DEAL_WITHOUT_STAGE', 'Sin etapa', 'dealstage vacío', 'deals', 'warning', 'pipeline'),
    ('DEAL_WITHOUT_AMOUNT', 'Sin monto', 'amount vacío', 'deals', 'info', 'value'),
    ('DEAL_WITH_UNKNOWN_PIPELINE', 'Pipeline desconocido', 'Pipeline no mapeado a marca', 'deals', 'warning', 'pipeline'),
    ('DEAL_WITH_INVALID_STAGE', 'Etapa inválida', 'dealstage no existe en pipeline', 'deals', 'warning', 'pipeline'),
    ('DEAL_WITHOUT_ACTIVITY', 'Sin actividad', 'Sin asociación a actividades', 'deals', 'info', 'engagement'),
    ('DEAL_STALE', 'Negocio estancado', 'Sin actualización reciente', 'deals', 'warning', 'engagement'),
    ('DEAL_CLOSED_WITHOUT_CLOSE_DATE', 'Cerrado sin fecha', 'closedate vacío en etapa cerrada', 'deals', 'warning', 'pipeline'),
    ('DEAL_WON_WITHOUT_AMOUNT', 'Ganado sin monto', 'Negocio ganado sin amount', 'deals', 'critical', 'value'),
    ('ACTIVITY_WITHOUT_CONTACT_OR_DEAL', 'Actividad huérfana', 'Sin contacto ni negocio asociado', 'activities', 'warning', 'associations'),
    ('ACTIVITY_WITHOUT_OWNER', 'Actividad sin propietario', 'Sin hubspot_owner_id', 'activities', 'info', 'ownership'),
    ('ACTIVITY_WITHOUT_TIMESTAMP', 'Actividad sin fecha', 'hs_timestamp vacío', 'activities', 'warning', 'data'),
    ('CONTACT_WITHOUT_DEAL', 'Contacto sin negocio', 'Sin asociación deal', 'contacts', 'info', 'associations'),
    ('DEAL_WITHOUT_ACTIVITY_ASSOCIATION', 'Negocio sin actividad asociada', 'Sin actividades vinculadas', 'deals', 'info', 'associations'),
    ('ASSOCIATION_REFERENCES_MISSING_OBJECT', 'Asociación rota', 'Apunta a objeto inexistente localmente', 'associations', 'critical', 'integrity')
on conflict (code) do nothing;
