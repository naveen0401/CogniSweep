# ErrorSweep SaaS Setup

## 1. Replace GitHub files

Rename:

```text
app_errorsweep_saas_supabase.py -> app.py
requirements_errorsweep_saas_supabase.txt -> requirements.txt
```

Push:

```bash
git add app.py requirements.txt
git commit -m "Add Supabase auth and usage credits"
git push
```

## 2. Supabase setup

Create a Supabase project, then open:

```text
Supabase Dashboard -> SQL Editor
```

Run the contents of:

```text
supabase_v42_release_schema.sql
```

This creates persistent tables for editor jobs, usage events, users,
workspaces, projects, jobs, payments, and audit logs. If Supabase secrets are
not configured, ErrorSweep uses the safe local JSON fallback automatically.

## 3. Streamlit Secrets

In Streamlit Cloud -> App -> Settings -> Secrets:

```toml
OPENAI_API_KEY = "your_openai_key"
GEMINI_API_KEY = "your_gemini_key"

SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your_supabase_anon_key"
SUPABASE_SERVICE_ROLE_KEY = "your_supabase_service_role_key"
```

Never put these keys in GitHub.

## 4. No-key Machine Translation

ErrorSweep can provide MT drafts without user API keys through self-hosted
engines:

```text
MADLAD-400 -> broad global language coverage
IndicTrans2 -> Indian languages when configured
OPUS-MT -> lightweight fallback for tested European pairs
```

For MADLAD-400 setup, see:

```text
README_madlad400_endpoint.md
```

To start local workers on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_builtin_mt.ps1
powershell -ExecutionPolicy Bypass -File .\start_builtin_mt.ps1 -WithMadlad -WithIndicTrans2
```

Then open ErrorSweep Pro and expand **Built-in MT engine diagnostics**.

You can also run:

```powershell
.\.venv\Scripts\python.exe test_builtin_mt_engines.py
```

## 5. Credit model

QA run:

```text
1 credit per 100 segments
+1 credit if Rules ZIP is used
```

Pro translation + review:

```text
3 credits per 75 segments
+ extra review credit when independent review is ON
+1 credit if Rules ZIP is used
```

## 6. Upgrade user plan manually for now

In Supabase Table Editor -> profiles, update:

```text
plan = pro
monthly_credits = 600
```

Later, connect Stripe/Razorpay to update these automatically.
