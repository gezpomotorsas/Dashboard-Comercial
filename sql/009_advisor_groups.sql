-- Grupos de asesores guardables (manual o importados desde HubSpot)

create table if not exists advisor_groups (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    description text,
    brand_value text,
    source text not null default 'manual',
    hubspot_source_id text,
    hubspot_source_label text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_advisor_groups_brand on advisor_groups (brand_value);
create index if not exists idx_advisor_groups_source on advisor_groups (source, hubspot_source_id);

create table if not exists advisor_group_members (
    id uuid primary key default gen_random_uuid(),
    group_id uuid not null references advisor_groups (id) on delete cascade,
    owner_id text not null,
    owner_name text,
    created_at timestamptz not null default now(),
    unique (group_id, owner_id)
);

create index if not exists idx_advisor_group_members_group on advisor_group_members (group_id);
create index if not exists idx_advisor_group_members_owner on advisor_group_members (owner_id);
