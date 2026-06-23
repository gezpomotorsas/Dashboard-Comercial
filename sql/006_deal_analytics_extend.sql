-- Extensión mínima de deal_analytics (Fase 3 comercial)
-- Idempotente. No crea tablas analíticas paralelas.

alter table deal_analytics add column if not exists zone_value text not null default 'unknown';
alter table deal_analytics add column if not exists zone_label text not null default 'Unknown';
alter table deal_analytics add column if not exists city_value text;
alter table deal_analytics add column if not exists department_value text;

alter table deal_analytics add column if not exists last_effective_contact_at timestamptz;
alter table deal_analytics add column if not exists days_since_effective_contact int;
alter table deal_analytics add column if not exists has_recent_effective_contact_7d boolean not null default false;
alter table deal_analytics add column if not exists has_recent_effective_contact_30d boolean not null default false;
alter table deal_analytics add column if not exists has_recent_effective_contact_60d boolean not null default false;

alter table deal_analytics add column if not exists completed_call_count int not null default 0;
alter table deal_analytics add column if not exists last_call_at timestamptz;
alter table deal_analytics add column if not exists last_communication_at timestamptz;
alter table deal_analytics add column if not exists meeting_count int not null default 0;

alter table deal_analytics add column if not exists open_task_count int not null default 0;
alter table deal_analytics add column if not exists completed_task_count int not null default 0;
alter table deal_analytics add column if not exists overdue_task_count int not null default 0;
alter table deal_analytics add column if not exists tasks_due_next_7d int not null default 0;
alter table deal_analytics add column if not exists oldest_overdue_task_days int;
alter table deal_analytics add column if not exists has_overdue_tasks boolean not null default false;
alter table deal_analytics add column if not exists has_future_task boolean not null default false;
alter table deal_analytics add column if not exists task_data_status text not null default 'partial';

alter table deal_analytics add column if not exists is_unattended boolean not null default false;
alter table deal_analytics add column if not exists unattended_reason text;
alter table deal_analytics add column if not exists alert_reason text;

alter table deal_analytics add column if not exists is_unknown_brand boolean not null default false;
alter table deal_analytics add column if not exists is_unknown_zone boolean not null default false;
alter table deal_analytics add column if not exists is_unknown_stage boolean not null default false;

create index if not exists idx_deal_analytics_zone on deal_analytics (zone_value);
create index if not exists idx_deal_analytics_unattended on deal_analytics (is_unattended);
create index if not exists idx_deal_analytics_overdue_tasks on deal_analytics (has_overdue_tasks);

insert into hubspot_field_mappings (
    object_type, semantic_key, hubspot_property_name, hubspot_property_label, source, priority
) values
    ('deals', 'deal_zone', 'zona', 'Zona', 'custom', 20),
    ('deals', 'deal_zone', 'regional', 'Regional', 'custom', 30),
    ('deals', 'deal_city', 'city', 'City', 'standard', 20),
    ('deals', 'deal_city', 'ciudad', 'Ciudad', 'custom', 30),
    ('deals', 'deal_department', 'departamento', 'Departamento', 'custom', 20),
    ('contacts', 'contact_city', 'city', 'City', 'standard', 30),
    ('contacts', 'contact_city', 'ciudad', 'Ciudad', 'custom', 40)
on conflict (object_type, semantic_key, hubspot_property_name) do nothing;
