-- Fase 2.5: columnas indexadas para sincronización de actividades (ventana 60 días)

alter table if exists hubspot_calls
    add column if not exists hubspot_owner_id text,
    add column if not exists activity_timestamp timestamptz;

alter table if exists hubspot_meetings
    add column if not exists hubspot_owner_id text,
    add column if not exists activity_timestamp timestamptz;

alter table if exists hubspot_tasks
    add column if not exists hubspot_owner_id text,
    add column if not exists activity_timestamp timestamptz;

alter table if exists hubspot_emails
    add column if not exists hubspot_owner_id text,
    add column if not exists activity_timestamp timestamptz;

alter table if exists hubspot_communications
    add column if not exists hubspot_owner_id text,
    add column if not exists activity_timestamp timestamptz;

alter table if exists hubspot_notes
    add column if not exists hubspot_owner_id text,
    add column if not exists activity_timestamp timestamptz;

create index if not exists idx_hubspot_calls_activity_ts on hubspot_calls (activity_timestamp);
create index if not exists idx_hubspot_meetings_activity_ts on hubspot_meetings (activity_timestamp);
create index if not exists idx_hubspot_tasks_activity_ts on hubspot_tasks (activity_timestamp);
create index if not exists idx_hubspot_emails_activity_ts on hubspot_emails (activity_timestamp);
create index if not exists idx_hubspot_communications_activity_ts on hubspot_communications (activity_timestamp);
create index if not exists idx_hubspot_notes_activity_ts on hubspot_notes (activity_timestamp);

create index if not exists idx_hubspot_calls_owner on hubspot_calls (hubspot_owner_id);
create index if not exists idx_hubspot_emails_owner on hubspot_emails (hubspot_owner_id);
create index if not exists idx_hubspot_communications_owner on hubspot_communications (hubspot_owner_id);
