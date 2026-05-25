create schema if not exists pipeline;

create table if not exists pipeline.leads (
    id                   uuid primary key default gen_random_uuid(),
    email                text not null,
    phone                text,
    name                 text not null,
    company              text,
    source               text not null,
    industry_context     text,
    raw_payload          jsonb,
    score                integer,
    tier                 text,
    assigned_to          text,
    speed_to_contact_min integer,
    created_at           timestamptz not null default now(),
    updated_at           timestamptz not null default now(),
    constraint leads_email_unique unique (email)
);

create table if not exists pipeline.events (
    id         uuid primary key default gen_random_uuid(),
    lead_id    uuid references pipeline.leads(id) on delete cascade,
    event_type text not null,
    payload    jsonb,
    created_at timestamptz not null default now()
);

create index if not exists leads_tier_idx on pipeline.leads(tier);
create index if not exists leads_created_at_idx on pipeline.leads(created_at);
create index if not exists events_lead_id_idx on pipeline.events(lead_id);
create index if not exists events_event_type_idx on pipeline.events(event_type);
