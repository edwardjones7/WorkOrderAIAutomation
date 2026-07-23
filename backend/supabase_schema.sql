-- EmailAgent — AppFolio Work-Order Automation schema
-- Run this in the Supabase SQL editor.

create extension if not exists "pgcrypto";

-- ── work_orders ────────────────────────────────────────────────────────────────
-- One row per detected maintenance request. Lifecycle:
--   new -> extracted -> needs_review -> approved -> submitting -> submitted
--                                    \-> ignored           \-> failed
create table if not exists work_orders (
    id                uuid primary key default gen_random_uuid(),

    -- source (Gmail)
    gmail_message_id  text not null,
    gmail_thread_id   text,
    from_email        text,
    subject           text,
    received_at       timestamptz,
    raw_body          text,

    -- extraction output
    extracted         jsonb default '{}'::jsonb,   -- full structured payload from Claude
    property_address  text,                          -- typed columns mirror `extracted` for filtering
    unit              text,
    resident_name     text,
    issue             text,
    category          text,                          -- Plumbing | Electrical | HVAC | Appliance | General | ...
    priority          text,                          -- Low | Medium | High | Emergency
    vendor            text,
    is_emergency      boolean default false,

    is_work_order     boolean,                       -- Claude's classification
    confidence        real,                          -- 0..1
    missing_fields    text[] default '{}',

    status            text not null default 'new',

    -- AppFolio result
    appfolio_ref      text,
    appfolio_url      text,
    submitted_by      text,
    submitted_at      timestamptz,

    error             text,

    created_at        timestamptz default now(),
    updated_at        timestamptz default now()
);

-- Idempotent ingestion: never create two rows for the same email.
create unique index if not exists work_orders_gmail_message_id_key
    on work_orders (gmail_message_id);

create index if not exists work_orders_status_idx on work_orders (status);
create index if not exists work_orders_received_at_idx on work_orders (received_at desc);

-- ── attachments ────────────────────────────────────────────────────────────────
create table if not exists attachments (
    id             uuid primary key default gen_random_uuid(),
    work_order_id  uuid not null references work_orders (id) on delete cascade,
    filename       text,
    mime           text,
    size_bytes     bigint,
    storage_path   text,            -- Supabase Storage object path
    ai_summary     text,            -- optional: what Claude read from this attachment
    created_at     timestamptz default now()
);

create index if not exists attachments_work_order_idx on attachments (work_order_id);

-- ── wo_events ──────────────────────────────────────────────────────────────────
-- Append-only audit log of every state change / automation step.
create table if not exists wo_events (
    id             uuid primary key default gen_random_uuid(),
    work_order_id  uuid references work_orders (id) on delete cascade,
    event_type     text not null,   -- ingested | extracted | status_change | approved | submit_attempt | submitted | failed | note
    from_status    text,
    to_status      text,
    actor          text,            -- 'system' | user email
    detail         jsonb default '{}'::jsonb,   -- screenshots refs, errors, retry counts, etc.
    created_at     timestamptz default now()
);

create index if not exists wo_events_work_order_idx on wo_events (work_order_id, created_at);

-- ── config ─────────────────────────────────────────────────────────────────────
-- Single-row settings / kill switch. Seeded with one row below.
create table if not exists config (
    id                       int primary key default 1,
    ingestion_enabled        boolean default true,   -- master kill switch for Gmail polling
    auto_submit_enabled      boolean default false,  -- if false, everything waits for human approval
    auto_submit_min_conf     real default 0.9,       -- only auto-submit above this confidence (future)
    gmail_history_id         text,                   -- checkpoint for incremental Gmail sync
    slack_webhook_url        text,
    updated_at               timestamptz default now(),
    constraint config_singleton check (id = 1)
);

insert into config (id) values (1) on conflict (id) do nothing;

-- ── updated_at trigger ─────────────────────────────────────────────────────────
create or replace function set_updated_at() returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists work_orders_updated_at on work_orders;
create trigger work_orders_updated_at before update on work_orders
    for each row execute function set_updated_at();

drop trigger if exists config_updated_at on config;
create trigger config_updated_at before update on config
    for each row execute function set_updated_at();
