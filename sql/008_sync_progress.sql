-- Campos opcionales de progreso en vivo para sync_runs (PostgreSQL local).
alter table sync_runs add column if not exists last_heartbeat timestamptz;
alter table sync_runs add column if not exists current_phase text;

create index if not exists idx_sync_runs_status_started
    on sync_runs (status, started_at desc);
