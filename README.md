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
supabase_errorsweep_schema.sql
```

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

## 4. Credit model

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

## 5. Upgrade user plan manually for now

In Supabase Table Editor -> profiles, update:

```text
plan = pro
monthly_credits = 600
```

Later, connect Stripe/Razorpay to update these automatically.
