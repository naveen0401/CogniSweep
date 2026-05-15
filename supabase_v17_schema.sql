
-- ErrorSweep clean reset v17 helper schema.
-- Run only if these columns/tables are missing. Existing tables are kept.

alter table if exists public.translation_memory
add column if not exists engine text default 'unknown';

create table if not exists public.review_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid null,
  file_name text,
  target_language text,
  status text default 'draft',
  created_at timestamptz default now()
);

create table if not exists public.review_segments (
  id uuid primary key default gen_random_uuid(),
  session_id uuid references public.review_sessions(id) on delete cascade,
  location text,
  source_text text,
  machine_translation text,
  reviewed_translation text,
  review_status text default 'draft',
  reviewer_comment text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.scorecards (
  id uuid primary key default gen_random_uuid(),
  user_id uuid null,
  file_name text,
  target_language text,
  score numeric,
  created_at timestamptz default now()
);

notify pgrst, 'reload schema';

