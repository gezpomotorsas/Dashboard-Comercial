-- Metodología de evaluación v2: historial de propietario y tareas históricas
-- Idempotente. No elimina columnas existentes.

alter table deal_analytics add column if not exists historical_task_count int not null default 0;
alter table deal_analytics add column if not exists historical_open_task_count int not null default 0;
alter table deal_analytics add column if not exists historical_completed_task_count int not null default 0;
alter table deal_analytics add column if not exists historical_overdue_task_count int not null default 0;
alter table deal_analytics add column if not exists operational_open_task_count int not null default 0;
alter table deal_analytics add column if not exists operational_overdue_task_count int not null default 0;
alter table deal_analytics add column if not exists operational_has_overdue_tasks boolean not null default false;
alter table deal_analytics add column if not exists operational_has_future_task boolean not null default false;

create table if not exists deal_owner_history (
    id bigserial primary key,
    deal_id text not null,
    owner_id text not null,
    assigned_from timestamptz not null,
    assigned_until timestamptz,
    source text not null default 'snapshot',
    confidence text not null default 'partial',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_deal_owner_history_deal on deal_owner_history (deal_id);
create index if not exists idx_deal_owner_history_owner on deal_owner_history (owner_id);
create index if not exists idx_deal_owner_history_assigned_from on deal_owner_history (assigned_from);

comment on table deal_owner_history is 'Historial de asignación de propietario por negocio (v2 evaluación)';
comment on column deal_analytics.historical_overdue_task_count is 'Tareas vencidas históricas; conservadas en negocios cerrados';
comment on column deal_analytics.operational_overdue_task_count is 'Tareas vencidas operativas; 0 en negocios cerrados';
