# CogniSweep Production Deployment Pack

This folder contains the non-secret deployment template for running CogniSweep as separate production processes.

Use `deploy/LAUNCH_RUNBOOK.md` for the phase-by-phase SaaS launch sequence. This README is the short deployment pack reference; the launch runbook is the go/no-go checklist for opening public traffic.

## Services

- `errorsweep-app`: Streamlit application on port `8501`.
- `errorsweep-async-receiver`: HTTP task receiver on port `8300`.
- `errorsweep-worker-supervisor`: managed background workers for async processing, email dispatch, and backups.
- `errorsweep-billing-webhook`: billing webhook receiver on port `8301`.
- `redis`: optional profile for deployments that choose Redis/Celery style queues later.

Naming note: `COGNISWEEP_*` is now the preferred deployment prefix. Existing `ERRORSWEEP_*` secrets, compose service names, database tables, and storage paths remain supported for backward compatibility, so migrate external settings gradually rather than rewriting live infrastructure in one step.

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
   python deploy/backup_check.py --strict
   python deploy/billing_check.py --strict
   python deploy/email_check.py --strict
   python deploy/legal_check.py --strict
   python deploy/mt_endpoint_check.py --strict
   python deploy/object_storage_check.py --strict
   python deploy/supabase_schema_check.py --strict
   ```
6. Generate owner/workspace bootstrap password hashes with:
   ```powershell
   python deploy/auth_session_check.py --generate-password-hash
   ```
   Or write the bootstrap fields directly into the ignored env file from shell environment variables:
   ```powershell
   $env:COGNISWEEP_OWNER_BOOTSTRAP_PASSWORD="<owner-password>"
   $env:COGNISWEEP_WORKSPACE_BOOTSTRAP_PASSWORD="<workspace-password>"
   python deploy/auth_session_check.py --env-file deploy/.env.production --write-bootstrap-env --owner-email owner@cognisweep.com --workspace-email workspace-owner@cognisweep.com --workspace-name "Initial Workspace" --owner-password-env COGNISWEEP_OWNER_BOOTSTRAP_PASSWORD --workspace-password-env COGNISWEEP_WORKSPACE_BOOTSTRAP_PASSWORD
   ```
7. Write Supabase persistence and Supabase Storage settings from shell environment variables:
   ```powershell
   $env:SUPABASE_ANON_KEY="<supabase-anon-key>"
   $env:SUPABASE_SERVICE_ROLE_KEY="<supabase-service-role-key>"
   python deploy/supabase_schema_check.py --env-file deploy/.env.production --write-supabase-env --supabase-url https://your-project.supabase.co --anon-key-env SUPABASE_ANON_KEY --service-role-key-env SUPABASE_SERVICE_ROLE_KEY --storage-bucket cognisweep-files
   ```
8. Write billing provider credentials and webhook settings from shell environment variables:
   ```powershell
   $env:RAZORPAY_KEY_ID="<razorpay-key-id>"
   $env:RAZORPAY_KEY_SECRET="<razorpay-key-secret>"
   $env:RAZORPAY_WEBHOOK_SECRET="<razorpay-webhook-secret>"
   python deploy/launch_env_check.py --env-file deploy/.env.production --write-billing-env --billing-provider razorpay --billing-webhook-url https://billing.cognisweep.com/webhooks/billing/razorpay --razorpay-key-id-env RAZORPAY_KEY_ID --razorpay-key-secret-env RAZORPAY_KEY_SECRET --razorpay-webhook-secret-env RAZORPAY_WEBHOOK_SECRET --pro-plan-id plan_pro --agency-plan-id plan_agency
   ```
9. Point public HTTPS routes at:
   - app: `http://errorsweep-app:8501`
   - async receiver: `http://errorsweep-async-receiver:8300`
   - billing webhook receiver: `http://errorsweep-billing-webhook:8301`
10. Configure `COGNISWEEP_PUBLIC_BASE_URL` and `COGNISWEEP_BILLING_WEBHOOK_RECEIVER_URL` to the public HTTPS URLs users/providers will call.

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
python deploy/backup_check.py --env-file deploy/.env.production --run-smoke --strict
python deploy/billing_check.py --env-file deploy/.env.production --run-smoke --probe-health --strict
python deploy/email_check.py --env-file deploy/.env.production --run-smoke --strict
python deploy/legal_check.py --env-file deploy/.env.production --probe-public --strict
python deploy/mt_endpoint_check.py --env-file deploy/.env.production --probe-health --probe-translate --strict
python deploy/object_storage_check.py --env-file deploy/.env.production --probe-write --strict
python deploy/supabase_schema_check.py --env-file deploy/.env.production --probe-rest --strict
python deploy/release_check.py --run-smoke
python deploy/launch_rehearsal.py --env-file deploy/.env.production --include-os-env --probe-public --probe-workers --strict
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml exec errorsweep-app python production_smoke_test.py --markdown --strict --probe-endpoints
docker compose -f docker-compose.production.yml exec errorsweep-worker-supervisor python worker_supervisor.py --status
```

The strict smoke test should be clean only after production secrets, Supabase, object storage, email, billing, legal, WAF, and backups are configured. The template intentionally contains placeholder values.
The release check is an offline packaging guard. It can run before Docker is available and should pass before every deployment branch is cut. The GitHub Actions release gate `.github/workflows/release-gate.yml` runs on pull requests and release branches to install production dependencies, run launch-safe regression tests, execute `deploy/release_check.py --strict`, and smoke the rehearsal runner without external probes. The launch rehearsal combines release, env, smoke, public-route, async receiver, and billing webhook checks into one go/no-go report. The AI fallback check validates managed_ai_router.py, platform OpenAI/managed endpoint settings, URL safety, optional `/models` or chat probes, and can write route settings with `--write-ai-env`. The auth/session check validates production session/public URL settings, owner/workspace bootstrap hashes, auth-token persistence, and the optional public app probe. The launch env check validates billing settings and can write Stripe/Razorpay credentials with `--write-billing-env`. The async worker check validates receiver/processor/supervisor readiness and can run local smoke plus receiver health probes. The backup check validates operational_backup_worker.py, sensitive-field redaction, manifest/audit persistence, supervisor wiring, and local dry-run backups. The billing check validates provider env coverage, Stripe/Razorpay signature enforcement, standalone webhook receiver wiring, local receiver health, and optional public receiver probes. The email check validates Resend/SendGrid/SMTP provider coverage, transactional templates, supervisor worker wiring, and dry-run dispatch. The legal check validates public Terms/Privacy/Security/Cookie/DPA routes, legal versioning, consent capture, privacy request/export support, subprocessor tracking, schema coverage, and legal/WAF env flags. The MT endpoint check validates router/client/worker contracts and can probe hosted `/health` and `/translate` routes. The object storage check validates provider coverage and can probe the real bucket; the Supabase schema check catches table/column drift before SQL is run against production and can write Supabase env settings with `--write-supabase-env`.

## Notes

- Keep generated uploads, reports, backups, and logs on mounted volumes or cloud object storage.
- Use HTTPS/CDN/WAF in front of public routes; do not expose raw container ports directly to customers.
- Optional MT workers can run as separate services or external endpoints. Keep endpoint URLs in `deploy/.env.production`.
