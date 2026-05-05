-- ErrorSweep SaaS Supabase setup
-- Run this once in Supabase Dashboard -> SQL Editor.
-- Keep your SERVICE_ROLE key only in Streamlit Secrets. Never commit it to GitHub.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text unique,
    full_name text,
    plan text not null default 'trial' check (plan in ('trial', 'errorsweep', 'pro', 'agency', 'enterprise')),
    monthly_credits integer not null default 25 check (monthly_credits >= 0),
    used_credits integer not null default 0 check (used_credits >= 0),
    total_files_processed integer not null default 0 check (total_files_processed >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.usage_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(id) on delete cascade,
    workflow text not null check (workflow in ('qa', 'pro')),
    file_name text,
    segments integer not null default 0,
    credits integer not null default 0,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.file_jobs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.profiles(id) on delete cascade,
    workflow text not null check (workflow in ('qa', 'pro')),
    file_name text,
    segments integer not null default 0,
    issues integer not null default 0,
    output_name text,
    credits_charged integer not null default 0,
    created_at timestamptz not null default now()
);

-- Keep updated_at fresh.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
before update on public.profiles
for each row
execute function public.set_updated_at();

-- Create profile automatically after signup.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, email, full_name, plan, monthly_credits, used_credits)
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
        'trial',
        25,
        0
    )
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

-- Atomic credit deduction.
create or replace function public.consume_user_credits(
    p_user_id uuid,
    p_credits integer,
    p_workflow text,
    p_file_name text default null,
    p_segments integer default 0,
    p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_profile public.profiles%rowtype;
    v_remaining integer;
begin
    if p_user_id is null then
        return jsonb_build_object('ok', false, 'message', 'missing_user_id');
    end if;

    if p_credits is null or p_credits < 0 then
        return jsonb_build_object('ok', false, 'message', 'invalid_credit_amount');
    end if;

    if p_workflow not in ('qa', 'pro') then
        return jsonb_build_object('ok', false, 'message', 'invalid_workflow');
    end if;

    select * into v_profile
    from public.profiles
    where id = p_user_id
    for update;

    if not found then
        return jsonb_build_object('ok', false, 'message', 'profile_not_found');
    end if;

    v_remaining := greatest(0, v_profile.monthly_credits - v_profile.used_credits);

    if v_remaining < p_credits then
        return jsonb_build_object(
            'ok', false,
            'message', 'insufficient_credits',
            'remaining', v_remaining,
            'required', p_credits
        );
    end if;

    update public.profiles
    set used_credits = used_credits + p_credits,
        total_files_processed = total_files_processed + 1,
        updated_at = now()
    where id = p_user_id;

    insert into public.usage_logs (user_id, workflow, file_name, segments, credits, metadata)
    values (p_user_id, p_workflow, p_file_name, coalesce(p_segments, 0), p_credits, coalesce(p_metadata, '{}'::jsonb));

    return jsonb_build_object(
        'ok', true,
        'remaining', v_remaining - p_credits,
        'charged', p_credits
    );
end;
$$;

-- Row Level Security.
alter table public.profiles enable row level security;
alter table public.usage_logs enable row level security;
alter table public.file_jobs enable row level security;

drop policy if exists "Users can read own profile" on public.profiles;
create policy "Users can read own profile"
on public.profiles
for select
using (auth.uid() = id);

drop policy if exists "Users can update own basic profile" on public.profiles;
create policy "Users can update own basic profile"
on public.profiles
for update
using (auth.uid() = id)
with check (auth.uid() = id);

drop policy if exists "Users can read own usage logs" on public.usage_logs;
create policy "Users can read own usage logs"
on public.usage_logs
for select
using (auth.uid() = user_id);

drop policy if exists "Users can read own file jobs" on public.file_jobs;
create policy "Users can read own file jobs"
on public.file_jobs
for select
using (auth.uid() = user_id);

-- Service-role controlled writes.
revoke all on function public.consume_user_credits(uuid, integer, text, text, integer, jsonb) from public;
grant execute on function public.consume_user_credits(uuid, integer, text, text, integer, jsonb) to service_role;

-- Helpful indexes.
create index if not exists idx_usage_logs_user_created on public.usage_logs(user_id, created_at desc);
create index if not exists idx_file_jobs_user_created on public.file_jobs(user_id, created_at desc);
