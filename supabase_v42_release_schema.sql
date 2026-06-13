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

create table if not exists public.errorsweep_users (
    id text primary key,
    email text not null,
    workspace text,
    role text,
    account_type text,
    permission_flags text,
    plan text,
    status text,
    password_hash text,
    email_verified boolean not null default false,
    verified_at timestamptz,
    user_email text,
    full_name text,
    phone text,
    city text,
    country text,
    timezone text,
    profile_type text,
    primary_role text,
    services text,
    languages text,
    domains text,
    tools text,
    certifications text,
    portfolio_url text,
    linkedin_url text,
    availability text,
    weekly_capacity integer,
    rate_currency text,
    hourly_rate numeric,
    per_word_rate numeric,
    work_preference text,
    bio text,
    profile_completion_status text,
    profile_completed_at timestamptz,
    profile_prompt_dismissed_at timestamptz,
    talent_status text,
    talent_search_text text,
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.errorsweep_users add column if not exists full_name text;
alter table public.errorsweep_users add column if not exists account_type text;
alter table public.errorsweep_users add column if not exists permission_flags text;
alter table public.errorsweep_users add column if not exists phone text;
alter table public.errorsweep_users add column if not exists city text;
alter table public.errorsweep_users add column if not exists country text;
alter table public.errorsweep_users add column if not exists timezone text;
alter table public.errorsweep_users add column if not exists profile_type text;
alter table public.errorsweep_users add column if not exists primary_role text;
alter table public.errorsweep_users add column if not exists services text;
alter table public.errorsweep_users add column if not exists languages text;
alter table public.errorsweep_users add column if not exists domains text;
alter table public.errorsweep_users add column if not exists tools text;
alter table public.errorsweep_users add column if not exists certifications text;
alter table public.errorsweep_users add column if not exists portfolio_url text;
alter table public.errorsweep_users add column if not exists linkedin_url text;
alter table public.errorsweep_users add column if not exists availability text;
alter table public.errorsweep_users add column if not exists weekly_capacity integer;
alter table public.errorsweep_users add column if not exists rate_currency text;
alter table public.errorsweep_users add column if not exists hourly_rate numeric;
alter table public.errorsweep_users add column if not exists per_word_rate numeric;
alter table public.errorsweep_users add column if not exists work_preference text;
alter table public.errorsweep_users add column if not exists bio text;
alter table public.errorsweep_users add column if not exists profile_completion_status text;
alter table public.errorsweep_users add column if not exists profile_completed_at timestamptz;
alter table public.errorsweep_users add column if not exists profile_prompt_dismissed_at timestamptz;
alter table public.errorsweep_users add column if not exists talent_status text;
alter table public.errorsweep_users add column if not exists talent_search_text text;
alter table public.errorsweep_users add column if not exists metadata_json jsonb not null default '{}'::jsonb;

create index if not exists idx_errorsweep_users_email on public.errorsweep_users(email);
create index if not exists idx_errorsweep_users_workspace on public.errorsweep_users(workspace);
create index if not exists idx_errorsweep_users_account_type on public.errorsweep_users(account_type);
create index if not exists idx_errorsweep_users_updated_at on public.errorsweep_users(updated_at desc);
create index if not exists idx_errorsweep_users_profile_type on public.errorsweep_users(profile_type);
create index if not exists idx_errorsweep_users_primary_role on public.errorsweep_users(primary_role);
create index if not exists idx_errorsweep_users_profile_completion on public.errorsweep_users(profile_completion_status);
create index if not exists idx_errorsweep_users_talent_status on public.errorsweep_users(talent_status);
create index if not exists idx_errorsweep_users_talent_search on public.errorsweep_users using gin (to_tsvector('simple', coalesce(talent_search_text, '')));

create table if not exists public.errorsweep_workspaces (
    id text primary key,
    workspace text not null,
    owner text,
    plan text,
    status text,
    users integer not null default 0,
    jobs integer not null default 0,
    user_email text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_workspaces_workspace on public.errorsweep_workspaces(workspace);
create index if not exists idx_errorsweep_workspaces_updated_at on public.errorsweep_workspaces(updated_at desc);

create table if not exists public.errorsweep_projects (
    id text primary key,
    workspace text,
    user_email text,
    created text,
    project text,
    client text,
    source text,
    targets text,
    domain text,
    status text,
    job_count integer,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_projects_workspace on public.errorsweep_projects(workspace);
create index if not exists idx_errorsweep_projects_updated_at on public.errorsweep_projects(updated_at desc);

create table if not exists public.errorsweep_jobs (
    id text primary key,
    workspace text,
    user_email text,
    created text,
    type text,
    language text,
    assignee text,
    status text,
    note text,
    segments integer,
    project_id text,
    project text,
    attachment_count integer,
    attachments_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.errorsweep_projects add column if not exists job_count integer;
alter table public.errorsweep_jobs add column if not exists project_id text;
alter table public.errorsweep_jobs add column if not exists project text;
alter table public.errorsweep_jobs add column if not exists attachment_count integer;
alter table public.errorsweep_jobs add column if not exists attachments_json jsonb;

create index if not exists idx_errorsweep_jobs_workspace on public.errorsweep_jobs(workspace);
create index if not exists idx_errorsweep_jobs_status on public.errorsweep_jobs(status);
create index if not exists idx_errorsweep_jobs_updated_at on public.errorsweep_jobs(updated_at desc);

create table if not exists public.errorsweep_payments (
    id text primary key,
    workspace text,
    user_email text,
    date text,
    "user" text,
    plan text,
    amount numeric,
    currency text,
    status text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_payments_workspace on public.errorsweep_payments(workspace);
create index if not exists idx_errorsweep_payments_updated_at on public.errorsweep_payments(updated_at desc);

create table if not exists public.errorsweep_invoices (
    id text primary key,
    workspace text,
    user_email text,
    invoice_number text,
    customer_email text,
    customer_gstin text,
    plan text,
    billing_period text,
    currency text,
    subtotal numeric,
    tax_rate_percent numeric,
    tax_amount numeric,
    total numeric,
    status text,
    source_payment_id text,
    notes text,
    metadata_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists idx_errorsweep_invoices_number on public.errorsweep_invoices(invoice_number);
create index if not exists idx_errorsweep_invoices_workspace on public.errorsweep_invoices(workspace);
create index if not exists idx_errorsweep_invoices_status on public.errorsweep_invoices(status);
create index if not exists idx_errorsweep_invoices_updated_at on public.errorsweep_invoices(updated_at desc);

create table if not exists public.errorsweep_subscriptions (
    id text primary key,
    workspace text,
    user_email text,
    plan text,
    status text,
    billing_cycle text,
    currency text,
    base_amount numeric,
    included_segments integer,
    included_characters bigint,
    included_seats integer,
    provider text,
    provider_customer_id text,
    provider_subscription_id text,
    current_period_start timestamptz,
    current_period_end timestamptz,
    cancel_at_period_end boolean not null default false,
    cancelled_at timestamptz,
    cancellation_reason text,
    metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.errorsweep_subscriptions add column if not exists cancel_at_period_end boolean not null default false;
alter table public.errorsweep_subscriptions add column if not exists cancelled_at timestamptz;
alter table public.errorsweep_subscriptions add column if not exists cancellation_reason text;
alter table public.errorsweep_subscriptions add column if not exists metadata_json jsonb not null default '{}'::jsonb;

create index if not exists idx_errorsweep_subscriptions_workspace on public.errorsweep_subscriptions(workspace);
create index if not exists idx_errorsweep_subscriptions_status on public.errorsweep_subscriptions(status);
create index if not exists idx_errorsweep_subscriptions_updated_at on public.errorsweep_subscriptions(updated_at desc);

create table if not exists public.errorsweep_checkout_sessions (
    id text primary key,
    workspace text,
    user_email text,
    plan text,
    billing_cycle text,
    currency text,
    amount numeric,
    provider text,
    status text,
    checkout_url text,
    provider_session_id text,
    metadata_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_checkout_sessions_workspace on public.errorsweep_checkout_sessions(workspace);
create index if not exists idx_errorsweep_checkout_sessions_status on public.errorsweep_checkout_sessions(status);
create index if not exists idx_errorsweep_checkout_sessions_updated_at on public.errorsweep_checkout_sessions(updated_at desc);

create table if not exists public.errorsweep_billing_events (
    id text primary key,
    workspace text,
    user_email text,
    provider text,
    event_id text,
    event_type text,
    status text,
    plan text,
    amount numeric,
    currency text,
    provider_payment_id text,
    provider_subscription_id text,
    provider_order_id text,
    provider_customer_id text,
    checkout_id text,
    signature_status text,
    applied boolean not null default false,
    raw_sha256 text,
    metadata_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_billing_events_workspace on public.errorsweep_billing_events(workspace);
create index if not exists idx_errorsweep_billing_events_provider on public.errorsweep_billing_events(provider);
create index if not exists idx_errorsweep_billing_events_status on public.errorsweep_billing_events(status);
create index if not exists idx_errorsweep_billing_events_event_id on public.errorsweep_billing_events(event_id);
create index if not exists idx_errorsweep_billing_events_updated_at on public.errorsweep_billing_events(updated_at desc);

create table if not exists public.errorsweep_auth_tokens (
    id text primary key,
    workspace text,
    user_email text,
    email text,
    token_hash text not null,
    token_type text,
    status text,
    expires_at timestamptz,
    used_at timestamptz,
    metadata_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_auth_tokens_email on public.errorsweep_auth_tokens(email);
create index if not exists idx_errorsweep_auth_tokens_hash on public.errorsweep_auth_tokens(token_hash);
create index if not exists idx_errorsweep_auth_tokens_status on public.errorsweep_auth_tokens(status);
create index if not exists idx_errorsweep_auth_tokens_expires_at on public.errorsweep_auth_tokens(expires_at);

create table if not exists public.errorsweep_audit_logs (
    id text primary key,
    workspace text,
    user_email text,
    time text,
    actor text,
    action text,
    details text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_audit_logs_workspace on public.errorsweep_audit_logs(workspace);
create index if not exists idx_errorsweep_audit_logs_actor on public.errorsweep_audit_logs(actor);
create index if not exists idx_errorsweep_audit_logs_updated_at on public.errorsweep_audit_logs(updated_at desc);

create table if not exists public.errorsweep_files (
    id text primary key,
    workspace text,
    user_email text,
    file_name text,
    purpose text,
    mime_type text,
    size_bytes bigint,
    sha256 text,
    storage_key text,
    storage_provider text,
    storage_bucket text,
    public_url text,
    local_path text,
    status text,
    expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.errorsweep_files add column if not exists storage_provider text;
alter table public.errorsweep_files add column if not exists storage_bucket text;
alter table public.errorsweep_files add column if not exists public_url text;
alter table public.errorsweep_files add column if not exists local_path text;

create index if not exists idx_errorsweep_files_workspace on public.errorsweep_files(workspace);
create index if not exists idx_errorsweep_files_sha256 on public.errorsweep_files(sha256);
create index if not exists idx_errorsweep_files_expires_at on public.errorsweep_files(expires_at);
create index if not exists idx_errorsweep_files_updated_at on public.errorsweep_files(updated_at desc);

create table if not exists public.errorsweep_notifications (
    id text primary key,
    workspace text,
    user_email text,
    recipient text,
    subject text,
    event_type text,
    status text,
    provider text,
    body text,
    error text,
    read_at timestamptz,
    dismissed_at timestamptz,
    metadata_json jsonb,
    sent_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.errorsweep_notifications add column if not exists error text;
alter table public.errorsweep_notifications add column if not exists read_at timestamptz;
alter table public.errorsweep_notifications add column if not exists dismissed_at timestamptz;

create index if not exists idx_errorsweep_notifications_workspace on public.errorsweep_notifications(workspace);
create index if not exists idx_errorsweep_notifications_recipient on public.errorsweep_notifications(recipient);
create index if not exists idx_errorsweep_notifications_status on public.errorsweep_notifications(status);
create index if not exists idx_errorsweep_notifications_read_at on public.errorsweep_notifications(read_at);
create index if not exists idx_errorsweep_notifications_dismissed_at on public.errorsweep_notifications(dismissed_at);
create index if not exists idx_errorsweep_notifications_updated_at on public.errorsweep_notifications(updated_at desc);

create table if not exists public.errorsweep_task_queue (
    id text primary key,
    workspace text,
    user_email text,
    task_type text,
    label text,
    status text,
    progress integer not null default 0,
    total_units integer not null default 0,
    processed_units integer not null default 0,
    result_ref text,
    error text,
    metadata_json jsonb,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_task_queue_workspace on public.errorsweep_task_queue(workspace);
create index if not exists idx_errorsweep_task_queue_status on public.errorsweep_task_queue(status);
create index if not exists idx_errorsweep_task_queue_type on public.errorsweep_task_queue(task_type);
create index if not exists idx_errorsweep_task_queue_updated_at on public.errorsweep_task_queue(updated_at desc);

create table if not exists public.errorsweep_platform_settings (
    id text primary key,
    workspace text not null default 'Platform',
    user_email text,
    setting_key text not null unique,
    setting_value jsonb not null default '{}'::jsonb,
    value_type text not null default 'json',
    metadata_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_platform_settings_key on public.errorsweep_platform_settings(setting_key);
create index if not exists idx_errorsweep_platform_settings_updated_at on public.errorsweep_platform_settings(updated_at desc);

create table if not exists public.errorsweep_privacy_requests (
    id text primary key,
    workspace text,
    user_email text,
    request_type text,
    requester_email text,
    subject text,
    status text,
    due_at timestamptz,
    fulfilled_at timestamptz,
    owner_notes text,
    metadata_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_privacy_requests_workspace on public.errorsweep_privacy_requests(workspace);
create index if not exists idx_errorsweep_privacy_requests_status on public.errorsweep_privacy_requests(status);
create index if not exists idx_errorsweep_privacy_requests_due_at on public.errorsweep_privacy_requests(due_at);
create index if not exists idx_errorsweep_privacy_requests_updated_at on public.errorsweep_privacy_requests(updated_at desc);

create table if not exists public.errorsweep_support_tickets (
    id text primary key,
    workspace text,
    user_email text,
    requester_email text,
    category text,
    priority text,
    subject text,
    message text,
    status text,
    owner_reply text,
    last_response_at timestamptz,
    metadata_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_support_tickets_workspace on public.errorsweep_support_tickets(workspace);
create index if not exists idx_errorsweep_support_tickets_requester on public.errorsweep_support_tickets(requester_email);
create index if not exists idx_errorsweep_support_tickets_status on public.errorsweep_support_tickets(status);
create index if not exists idx_errorsweep_support_tickets_priority on public.errorsweep_support_tickets(priority);
create index if not exists idx_errorsweep_support_tickets_updated_at on public.errorsweep_support_tickets(updated_at desc);

create table if not exists public.errorsweep_status_incidents (
    id text primary key,
    workspace text,
    user_email text,
    scope text,
    incident_type text,
    severity text,
    status text,
    title text,
    message text,
    starts_at timestamptz,
    ends_at timestamptz,
    resolved_at timestamptz,
    metadata_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_status_incidents_scope on public.errorsweep_status_incidents(scope);
create index if not exists idx_errorsweep_status_incidents_status on public.errorsweep_status_incidents(status);
create index if not exists idx_errorsweep_status_incidents_severity on public.errorsweep_status_incidents(severity);
create index if not exists idx_errorsweep_status_incidents_updated_at on public.errorsweep_status_incidents(updated_at desc);

create table if not exists public.errorsweep_consent_records (
    id text primary key,
    workspace text,
    user_email text,
    email text,
    account_type text,
    role text,
    terms_version text,
    privacy_version text,
    nda_version text,
    cookie_version text,
    dpa_version text,
    accepted_at timestamptz,
    ip_hint text,
    metadata_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_errorsweep_consent_records_workspace on public.errorsweep_consent_records(workspace);
create index if not exists idx_errorsweep_consent_records_email on public.errorsweep_consent_records(email);
create index if not exists idx_errorsweep_consent_records_versions on public.errorsweep_consent_records(terms_version, privacy_version, nda_version);
create index if not exists idx_errorsweep_consent_records_updated_at on public.errorsweep_consent_records(updated_at desc);

alter table public.errorsweep_editor_jobs enable row level security;
alter table public.errorsweep_usage_events enable row level security;
alter table public.errorsweep_users enable row level security;
alter table public.errorsweep_workspaces enable row level security;
alter table public.errorsweep_projects enable row level security;
alter table public.errorsweep_jobs enable row level security;
alter table public.errorsweep_payments enable row level security;
alter table public.errorsweep_invoices enable row level security;
alter table public.errorsweep_subscriptions enable row level security;
alter table public.errorsweep_checkout_sessions enable row level security;
alter table public.errorsweep_billing_events enable row level security;
alter table public.errorsweep_auth_tokens enable row level security;
alter table public.errorsweep_audit_logs enable row level security;
alter table public.errorsweep_files enable row level security;
alter table public.errorsweep_notifications enable row level security;
alter table public.errorsweep_task_queue enable row level security;
alter table public.errorsweep_platform_settings enable row level security;
alter table public.errorsweep_privacy_requests enable row level security;
alter table public.errorsweep_support_tickets enable row level security;
alter table public.errorsweep_status_incidents enable row level security;
alter table public.errorsweep_consent_records enable row level security;

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

create or replace view public.errorsweep_workspace_summary as
select
    w.workspace,
    w.owner,
    w.plan,
    w.status,
    count(distinct u.id) as users,
    count(distinct p.id) as projects,
    count(distinct j.id) as jobs,
    max(greatest(w.updated_at, coalesce(u.updated_at, w.updated_at), coalesce(p.updated_at, w.updated_at), coalesce(j.updated_at, w.updated_at))) as latest_update
from public.errorsweep_workspaces w
left join public.errorsweep_users u on u.workspace = w.workspace
left join public.errorsweep_projects p on p.workspace = w.workspace
left join public.errorsweep_jobs j on j.workspace = w.workspace
group by 1, 2, 3, 4
order by latest_update desc;
