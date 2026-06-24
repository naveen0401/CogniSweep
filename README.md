# CogniSweep SaaS

CogniSweep runs from the repository root:

- Streamlit entrypoint: `app.py`
- Production dependency file: `requirements.txt`
- Production deployment pack: `deploy/`

Do not rename legacy generated files into place for launch. The root `app.py` and `requirements.txt` are the canonical files used by Docker, Streamlit, release checks, and production deployment.

## Local Run

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py
```

## Production Release Guard

Run the offline release check before cutting or deploying a launch branch:

```powershell
python deploy/release_check.py --strict
```

Pull requests and pushes to `main`, `master`, and `release/**` also run the GitHub Actions release gate in `.github/workflows/release-gate.yml`. That workflow installs production dependencies, compiles launch entrypoints, runs launch-safe regression tests, runs `deploy/release_check.py --strict`, and exercises the launch rehearsal runner without external probes.

This validates:

- Root `app.py` and `requirements.txt` are present.
- Docker runs `streamlit run app.py`.
- Required production packages are listed in `requirements.txt`.
- Deployment pack files and compose services are present.
- The GitHub Actions release gate is present and launch-safe.
- Private env and secret files are ignored.
- Production entrypoints compile.

## Production Environment

Copy the non-secret template and fill real values outside git:

```powershell
Copy-Item deploy/.env.production.example deploy/.env.production
python deploy/launch_env_check.py --env-file deploy/.env.production --strict
```

Required launch providers include Supabase persistence, cloud object storage, async workers, billing/webhooks, transactional email, legal approval, CDN/WAF, and scheduled backups.
Production translation needs either `OPENAI_API_KEY` or a live managed OpenAI-compatible endpoint for platform fallback. Bundled local/self-hosted MT engines have been removed; Amazon Translate can be added later through a dedicated adapter.

Naming note: some production environment variables and Docker service names still use the legacy `ERRORSWEEP_`/`errorsweep-*` prefix. They are the stable configuration keys for CogniSweep deployments and should stay as-is until a deliberate migration plan updates code, docs, secrets, and existing production environments together.

For Streamlit Cloud-style deployments, copy `.streamlit/secrets.toml.example` into the platform Secrets UI and fill the real values there. Do not commit `.streamlit/secrets.toml`.

## Production Deployment

Use the deployment pack and runbook:

- `deploy/README_DEPLOYMENT.md`
- `deploy/LAUNCH_RUNBOOK.md`
- `deploy/AWS_DEPLOYMENT.md` for EC2 + S3 + CloudFront/AWS WAF hosting
- `deploy/launch_env_check.py`
- `production_smoke_test.py`

Build and start:

```powershell
docker compose --env-file deploy/.env.production -f docker-compose.production.yml build
docker compose --env-file deploy/.env.production -f docker-compose.production.yml up -d
```

Final verification:

```powershell
python deploy/launch_env_check.py --env-file deploy/.env.production --strict
docker compose --env-file deploy/.env.production -f docker-compose.production.yml exec errorsweep-app python production_smoke_test.py --markdown --strict --probe-endpoints
docker compose --env-file deploy/.env.production -f docker-compose.production.yml exec errorsweep-worker-supervisor python worker_supervisor.py --status
```

## Supabase

Create the production Supabase project, then run:

```text
supabase_v42_release_schema.sql
```

Configure at minimum:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

Local JSON fallback is for development only. Public launch must use production Supabase persistence.

## Managed Machine Translation

Bundled local/self-hosted MT engines are retired. Keep `COGNISWEEP_MT_PROVIDER=disabled` for launch. Add Amazon Translate later behind `translator_router.translate_batch(...)` after language-pair tests, terminology tests, IAM permissions, and cost controls are ready.

## Platform AI Fallback

User BYO keys are preferred at runtime. For production fallback, configure one of:

- `OPENAI_API_KEY`
- `ERRORSWEEP_MANAGED_AI_ENABLED=true` with `ERRORSWEEP_MANAGED_AI_BASE_URL`

`GEMINI_API_KEY` can be added when Gemini OpenAI-compatible routing is offered as a managed option.

## Secrets

Never commit API keys, Supabase keys, billing keys, webhook secrets, email credentials, or production env files. Use the deployment platform secret store or `deploy/.env.production` outside git.
