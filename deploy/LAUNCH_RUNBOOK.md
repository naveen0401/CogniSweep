# ErrorSweep SaaS Launch Runbook

Use this runbook to move ErrorSweep from a production-ready code branch to a public SaaS launch. Public traffic should not be enabled until the strict smoke test reports zero blockers.

```powershell
python deploy/release_check.py --strict
python deploy/launch_env_check.py --env-file deploy/.env.production --strict
python production_smoke_test.py --markdown --strict --probe-endpoints
```

The local template intentionally fails several launch gates until real production services, secrets, legal approvals, and edge controls are configured.

## Go/No-Go Rule

Launch is allowed only when all of these are true:

- `deploy/release_check.py --strict` exits successfully.
- `deploy/launch_env_check.py --env-file deploy/.env.production --strict` exits successfully without exposing secrets.
- `production_smoke_test.py --markdown --strict --probe-endpoints` exits successfully in the production environment.
- All required public URLs use HTTPS.
- Billing, email, async workers, backups, object storage, and Supabase persistence are configured with production credentials.
- Legal documents and processor approvals are reviewed and versioned.
- CDN/WAF/rate limiting is active in front of public routes.

## Phase 0: Release Branch Guard

Run the offline packaging check before touching production secrets.

```powershell
python deploy/release_check.py --strict
```

Expected result: no blockers.

This verifies the deployment pack, compose service split, env template coverage, secret ignore rules, and Python syntax for production entry points.

## Phase 1: Production Environment File

Create the real production env file from the non-secret template.

```powershell
Copy-Item deploy/.env.production.example deploy/.env.production
```

Fill the real values in `deploy/.env.production`. Do not commit this file.

Minimum required production identity values:

- `ERRORSWEEP_ENV=production`
- `ERRORSWEEP_PUBLIC_BASE_URL=https://<app-domain>`
- `ERRORSWEEP_SESSION_SECRET=<long-random-secret>`

Validate the file after each setup pass:

```powershell
python deploy/launch_env_check.py --env-file deploy/.env.production
```

Use strict mode before deployment:

```powershell
python deploy/launch_env_check.py --env-file deploy/.env.production --strict
```

## Phase 2: Supabase Persistence

Create or select the production Supabase project, then run the release schema.

Required env keys:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

Required validation:

```powershell
python production_smoke_test.py --markdown
```

The `Supabase SaaS tables` check must pass before launch.

## Phase 3: Object Storage

Choose the production storage provider and create the bucket/container.

Required env keys for Supabase Storage:

- `ERRORSWEEP_OBJECT_STORAGE_PROVIDER=supabase`
- `SUPABASE_STORAGE_BUCKET`

Alternative providers can use the S3 or GCS keys already listed in `deploy/.env.production.example`.

The smoke test must not report local storage fallback as the production path.

## Phase 4: Async Processing

Deploy the async receiver and worker processor as managed services.

Required env keys:

- `ERRORSWEEP_ASYNC_WORKER_URL`
- `ERRORSWEEP_ASYNC_WORKER_TOKEN`
- `ERRORSWEEP_ASYNC_RECEIVER_SERVICE_ENABLED=true`
- `ERRORSWEEP_ASYNC_PROCESSOR_ENABLED=true`
- `ERRORSWEEP_WORKER_SUPERVISOR_ENABLED=true`

Useful checks:

```powershell
python async_workflow_processor.py --smoke
python worker_supervisor.py --status
python production_smoke_test.py --markdown --probe-endpoints
```

## Phase 5: AI Fallback And Built-In MT

Configure production translation routes before public no-key Pro workflows are enabled.

Required platform AI fallback values:

- `OPENAI_API_KEY`, or
- `ERRORSWEEP_MANAGED_AI_ENABLED=true` with `ERRORSWEEP_MANAGED_AI_BASE_URL`

Optional platform AI values:

- `ERRORSWEEP_OPENAI_DEFAULT_MODEL`
- `GEMINI_API_KEY`
- `ERRORSWEEP_MANAGED_AI_API_KEY`
- `ERRORSWEEP_MANAGED_AI_MODEL`

Required no-key MT values:

- `OPUS_MT_ENDPOINT`
- `INDICTRANS2_ENDPOINT`

Recommended after GPU capacity approval:

- `MADLAD_ENDPOINT`

Useful checks:

```powershell
python test_builtin_mt_engines.py
python deploy/launch_env_check.py --env-file deploy/.env.production
```

## Phase 6: Billing

Choose one production billing provider and configure live credentials, plan IDs, and webhook signing.

Required env keys:

- `ERRORSWEEP_BILLING_PROVIDER`
- `ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL`
- `ERRORSWEEP_BILLING_WEBHOOK_SECRET`

Provider-specific required values:

- Razorpay: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, plan IDs, mandate links.
- Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, price IDs, mandate links.

Keep `ERRORSWEEP_WEBHOOK_APPLY_UPDATES=false` until provider test webhooks validate signature checks and event mapping. Turn it on only after successful staging verification.

## Phase 7: Transactional Email

Configure one production email provider and verify the sender domain.

Required env keys:

- `ERRORSWEEP_EMAIL_PROVIDER`
- `ERRORSWEEP_EMAIL_FROM`
- `ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED=true`

Provider-specific keys:

- Resend: `RESEND_API_KEY`
- SendGrid: `SENDGRID_API_KEY`
- SMTP: host, port, username, password, TLS settings

Required validation:

```powershell
python email_dispatch_worker.py --dry-run
python production_smoke_test.py --markdown
```

Run an owner-triggered deliverability test from Platform Settings before launch.

## Phase 8: Legal And Processor Approval

Do not set the launch approval flags until reviewed legal documents are live.

Required env keys:

- `ERRORSWEEP_LEGAL_REVIEWED=true`

Required product checks:

- Terms, Privacy, Cookie Notice, Security, NDA/confidentiality, and DPA routes are current.
- Active external processors are approved in the subprocessor register.
- Customer notices match the live data-routing setup.

## Phase 9: CDN, WAF, And Public Routes

Put HTTPS/CDN/WAF in front of all public endpoints.

Required env key:

- `ERRORSWEEP_WAF_PROVIDER`

Route targets:

- App: `http://errorsweep-app:8501`
- Async receiver: `http://errorsweep-async-receiver:8300`
- Billing webhook receiver: `http://errorsweep-billing-webhook:8301`

Do not expose raw container ports directly to customers.

## Phase 10: Backups

Enable scheduled production backups and verify restore evidence.

Required env keys:

- `ERRORSWEEP_BACKUP_WORKER_ENABLED=true`
- `ERRORSWEEP_BACKUP_PROVIDER`

Useful checks:

```powershell
python operational_backup_worker.py --dry-run
python production_smoke_test.py --markdown
```

Before launch, prepare at least one successful backup snapshot and document restore ownership.

## Phase 11: Build And Start Production Services

Build and start the production compose pack.

```powershell
docker compose --env-file deploy/.env.production -f docker-compose.production.yml build
docker compose --env-file deploy/.env.production -f docker-compose.production.yml up -d
docker compose -f docker-compose.production.yml ps
```

Expected services:

- `errorsweep-app`
- `errorsweep-async-receiver`
- `errorsweep-worker-supervisor`
- `errorsweep-billing-webhook`

## Phase 12: Final Launch Verification

Run strict smoke tests from the deployed environment.

```powershell
python deploy/launch_env_check.py --env-file deploy/.env.production --strict
docker compose --env-file deploy/.env.production -f docker-compose.production.yml exec errorsweep-app python production_smoke_test.py --markdown --strict --probe-endpoints
docker compose --env-file deploy/.env.production -f docker-compose.production.yml exec errorsweep-worker-supervisor python worker_supervisor.py --status
```

Then manually verify:

- Login, signup, password reset, logout.
- Project creation, QA upload, Pro translation, Human Review export, media editor export.
- Billing checkout intent and provider webhook signature handling.
- Transactional email delivery to an external mailbox.
- Object-storage download links and generated ZIP packages.
- Platform Settings launch readiness, tenant diagnostics, processor register, and audit logs.

## Launch Blocker Map

| Smoke-test blocker | Primary fix |
| --- | --- |
| Production mode | Set `ERRORSWEEP_ENV=production`. |
| Public HTTPS URL | Set `ERRORSWEEP_PUBLIC_BASE_URL` to the live HTTPS app URL. |
| Session secret | Set a long unique `ERRORSWEEP_SESSION_SECRET`. |
| Supabase SaaS tables | Run the release schema and configure Supabase env keys. |
| Object storage local fallback | Configure Supabase Storage, S3, or GCS for production. |
| Async receiver or processor | Deploy the receiver/processor services and set worker env keys. |
| Production AI fallback route | Configure `OPENAI_API_KEY` or a live managed OpenAI-compatible/vLLM endpoint. |
| No-key MT minimum route | Configure live HTTPS OPUS-MT and IndicTrans2 endpoints before enabling public no-key Pro workflows. |
| Billing provider credentials | Configure live Razorpay or Stripe credentials. |
| Webhook receiver URL | Set the public HTTPS billing webhook receiver URL. |
| Webhook signature secret | Set the provider webhook signing secret. |
| Transactional email provider | Configure Resend, SendGrid, or SMTP. |
| Verified sender | Set and verify `ERRORSWEEP_EMAIL_FROM`. |
| Dispatch worker enabled | Set `ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED=true`. |
| Backup worker enabled | Set `ERRORSWEEP_BACKUP_WORKER_ENABLED=true` after backup provider setup. |
| CDN/WAF provider | Put the app behind a named WAF/CDN provider and set `ERRORSWEEP_WAF_PROVIDER`. |
| Legal review flag | Set `ERRORSWEEP_LEGAL_REVIEWED=true` only after legal approval. |

## Rollback

If the final smoke test fails after deployment, keep public registration and checkout collection disabled, then stop the compose pack or roll traffic back at the CDN/load balancer.

```powershell
docker compose --env-file deploy/.env.production -f docker-compose.production.yml logs --tail=200
docker compose --env-file deploy/.env.production -f docker-compose.production.yml down
```

Preserve logs, audit snapshots, and backup state before destructive infrastructure changes.
