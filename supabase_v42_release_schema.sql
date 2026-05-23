-- ErrorSweep v42 release hardening schema
-- Run this in Supabase SQL Editor before enabling production persistence.

create extension if not exists pgcrypto;

create table if not exists public.errorsweep_editor_jobs (
    id text primary key,
    job_type text not null default 'cat',
    user_email text,
    workspace text,
    file_name text,
    target_language text,
    status text not null default 'draft',
    row_count integer not null default 0,
    rows jsonb not null default '[]'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_editor_jobs_workspace on public.errorsweep_editor_jobs(workspace);
create index if not exists idx_errorsweep_editor_jobs_user_email on public.errorsweep_editor_jobs(user_email);
create index if not exists idx_errorsweep_editor_jobs_updated_at on public.errorsweep_editor_jobs(updated_at desc);
create index if not exists idx_errorsweep_editor_jobs_status on public.errorsweep_editor_jobs(status);

create table if not exists public.errorsweep_usage_events (
    id uuid primary key default gen_random_uuid(),
    user_email text,
    workspace text,
    purpose text not null,
    provider text,
    model text,
    managed boolean not null default false,
    segments integer not null default 0,
    characters integer not null default 0,
    requests integer not null default 0,
    input_tokens integer not null default 0,
    output_tokens integer not null default 0,
    total_tokens integer not null default 0,
    success boolean not null default true,
    error text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_usage_events_workspace on public.errorsweep_usage_events(workspace);
create index if not exists idx_errorsweep_usage_events_user_email on public.errorsweep_usage_events(user_email);
create index if not exists idx_errorsweep_usage_events_created_at on public.errorsweep_usage_events(created_at desc);
create index if not exists idx_errorsweep_usage_events_purpose on public.errorsweep_usage_events(purpose);

alter table public.errorsweep_editor_jobs enable row level security;
alter table public.errorsweep_usage_events enable row level security;

create or replace view public.errorsweep_usage_daily as
select
    date_trunc('day', created_at) as day,
    workspace,
    purpose,
    provider,
    count(*) as events,
    sum(segments) as segments,
    sum(characters) as characters,
    sum(requests) as requests,
    sum(total_tokens) as total_tokens,
    sum(case when success then 0 else 1 end) as failures
from public.errorsweep_usage_events
group by 1, 2, 3, 4
order by day desc;

create or replace view public.errorsweep_editor_job_summary as
select
    workspace,
    job_type,
    status,
    count(*) as jobs,
    sum(row_count) as total_rows,
    max(updated_at) as latest_update
from public.errorsweep_editor_jobs
group by 1, 2, 3
order by latest_update desc;
