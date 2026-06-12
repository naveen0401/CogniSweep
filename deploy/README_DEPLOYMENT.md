# ErrorSweep Production Deployment Pack

This folder contains the non-secret deployment template for running ErrorSweep as separate production processes.

Use `deploy/LAUNCH_RUNBOOK.md` for the phase-by-phase SaaS launch sequence. This README is the short deployment pack reference; the launch runbook is the go/no-go checklist for opening public traffic.

## Services

- `errorsweep-app`: Streamlit application on port `8501`.
- `errorsweep-async-receiver`: HTTP task receiver on port `8300`.
- `errorsweep-worker-supervisor`: managed background workers for async processing, email dispatch, and backups.
- `errorsweep-billing-webhook`: billing webhook receiver on port `8301`.
- `redis`: optional profile for deployments that choose Redis/Celery style queues later.

## First Setup

1. Copy `deploy/.env.production.example` to `deploy/.env.production`.
2. Fill real secrets in `deploy/.env.production`; never commit that file.
3. For Streamlit Cloud-style deployments, copy the keys from `.streamlit/secrets.toml.example` into the platform Secrets UI and fill real values there.
4. Follow `deploy/LAUNCH_RUNBOOK.md` from Phase 1 through final launch verification.
5. Validate the env file without printing secret values:
   ```powershell
   python deploy/launch_env_check.py --env-file deploy/.env.production --strict
   python deploy/ai_fallback_check.py --strict
   python deploy/auth_session_check.py --strict
   python deploy/async_worker_check.py --strict
   python deploy/mt_endpoint_check.py --strict
   python deploy/object_storage_check.py --strict
   python deploy/supabase_schema_check.py --strict
   ```
6. Generate owner/workspace bootstrap password hashes with:
   ```powershell
   python deploy/auth_session_check.py --generate-password-hash
   ```
7. Point public HTTPS routes at:
   - app: `http://errorsweep-app:8501`
   - async receiver: `http://errorsweep-async-receiver:8300`
   - billing webhook receiver: `http://errorsweep-billing-webhook:8301`
8. Configure `ERRORSWEEP_PUBLIC_BASE_URL` and `ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL` to the public HTTPS URLs users/providers will call.

## Run

```powershell
docker compose --env-file deploy/.env.production -f docker-compose.production.yml build
docker compose --env-file deploy/.env.production -f docker-compose.production.yml up -d
```

## Verify

```powershell
python deploy/launch_env_check.py --env-file deploy/.env.production --strict
python deploy/ai_fallback_check.py --env-file deploy/.env.production --probe-models --strict
python deploy/auth_session_check.py --env-file deploy/.env.production --probe-public-url --strict
python deploy/async_worker_check.py --env-file deploy/.env.production --run-smoke --probe-health --strict
python deploy/mt_endpoint_check.py --env-file deploy/.env.production --probe-health --probe-translate --strict
python deploy/object_storage_check.py --env-file deploy/.env.production --probe-write --strict
python deploy/supabase_schema_check.py --env-file deploy/.env.production --probe-rest --strict
python deploy/release_check.py --run-smoke
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml exec errorsweep-app python production_smoke_test.py --markdown --strict --probe-endpoints
docker compose -f docker-compose.production.yml exec errorsweep-worker-supervisor python worker_supervisor.py --status
```

The strict smoke test should be clean only after production secrets, Supabase, object storage, email, billing, legal, WAF, and backups are configured. The template intentionally contains placeholder values.
The release check is an offline packaging guard. It can run before Docker is available and should pass before every deployment branch is cut. The AI fallback check validates managed_ai_router.py, platform OpenAI/managed endpoint settings, URL safety, and optional `/models` or chat probes. The auth/session check validates production session/public URL settings, owner/workspace bootstrap hashes, auth-token persistence, and the optional public app probe. The async worker check validates receiver/processor/supervisor readiness and can run local smoke plus receiver health probes. The MT endpoint check validates router/client/worker contracts and can probe hosted `/health` and `/translate` routes. The object storage check validates provider coverage and can probe the real bucket; the Supabase schema check catches table/column drift before SQL is run against production.

## Notes

- Keep generated uploads, reports, backups, and logs on mounted volumes or cloud object storage.
- Use HTTPS/CDN/WAF in front of public routes; do not expose raw container ports directly to customers.
- Optional MT workers can run as separate services or external endpoints. Keep endpoint URLs in `deploy/.env.production`.
