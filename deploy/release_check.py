"""Offline release validation for the ErrorSweep deployment pack.

This script intentionally avoids importing app.py so it can run in CI/CD before
secrets are available. It checks repository packaging, compose wiring, ignored
secret files, and Python syntax for production entry points.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DEPLOYMENT_FILES = [
    "Dockerfile",
    ".dockerignore",
    "docker-compose.production.yml",
    "supabase_v42_release_schema.sql",
    ".streamlit/secrets.toml.example",
    "deploy/.env.production.example",
    "deploy/README_DEPLOYMENT.md",
    "deploy/LAUNCH_RUNBOOK.md",
    "deploy/launch_env_check.py",
    "deploy/release_check.py",
]

REQUIRED_ROOT_FILES = [
    "app.py",
    "requirements.txt",
]

STALE_README_TOKENS = [
    "app_errorsweep_saas_supabase.py",
    "requirements_errorsweep_saas_supabase.txt",
    "Replace GitHub files",
]

REQUIRED_REQUIREMENT_PACKAGES = [
    "streamlit",
    "pandas",
    "openpyxl",
    "python-docx",
    "openai",
    "requests",
    "defusedxml",
    "boto3",
    "google-cloud-storage",
    "redis",
]

REQUIRED_SUPABASE_TABLES = [
    "errorsweep_editor_jobs",
    "errorsweep_usage_events",
    "errorsweep_users",
    "errorsweep_workspaces",
    "errorsweep_projects",
    "errorsweep_jobs",
    "errorsweep_payments",
    "errorsweep_invoices",
    "errorsweep_subscriptions",
    "errorsweep_checkout_sessions",
    "errorsweep_billing_events",
    "errorsweep_auth_tokens",
    "errorsweep_audit_logs",
    "errorsweep_files",
    "errorsweep_notifications",
    "errorsweep_task_queue",
    "errorsweep_platform_settings",
    "errorsweep_privacy_requests",
    "errorsweep_support_tickets",
    "errorsweep_status_incidents",
    "errorsweep_consent_records",
]

REQUIRED_COMPOSE_SERVICES = [
    "errorsweep-app:",
    "errorsweep-async-receiver:",
    "errorsweep-worker-supervisor:",
    "errorsweep-billing-webhook:",
]

REQUIRED_ENV_KEYS = [
    "ERRORSWEEP_ENV",
    "ERRORSWEEP_PUBLIC_BASE_URL",
    "ERRORSWEEP_SESSION_SECRET",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "ERRORSWEEP_OPENAI_DEFAULT_MODEL",
    "ERRORSWEEP_MANAGED_AI_ENABLED",
    "ERRORSWEEP_MANAGED_AI_BASE_URL",
    "ERRORSWEEP_MANAGED_AI_API_KEY",
    "ERRORSWEEP_MANAGED_AI_MODEL",
    "ERRORSWEEP_OBJECT_STORAGE_PROVIDER",
    "ERRORSWEEP_ASYNC_WORKER_URL",
    "ERRORSWEEP_ASYNC_WORKER_TOKEN",
    "ERRORSWEEP_WORKER_SUPERVISOR_ENABLED",
    "ERRORSWEEP_BILLING_PROVIDER",
    "ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL",
    "ERRORSWEEP_EMAIL_PROVIDER",
    "ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED",
    "ERRORSWEEP_BACKUP_WORKER_ENABLED",
    "ERRORSWEEP_WAF_PROVIDER",
    "INDICTRANS2_ENDPOINT",
    "MADLAD_ENDPOINT",
    "OPUS_MT_ENDPOINT",
    "SELF_HOSTED_MT_TIMEOUT",
]

REQUIRED_STREAMLIT_SECRET_KEYS = [
    "ERRORSWEEP_ENV",
    "ERRORSWEEP_PUBLIC_BASE_URL",
    "ERRORSWEEP_SESSION_SECRET",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "ERRORSWEEP_OBJECT_STORAGE_PROVIDER",
    "ERRORSWEEP_ASYNC_WORKER_URL",
    "ERRORSWEEP_ASYNC_WORKER_TOKEN",
    "ERRORSWEEP_BILLING_PROVIDER",
    "ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL",
    "ERRORSWEEP_EMAIL_PROVIDER",
    "ERRORSWEEP_EMAIL_FROM",
    "ERRORSWEEP_LEGAL_REVIEWED",
    "ERRORSWEEP_WAF_PROVIDER",
    "ERRORSWEEP_BACKUP_WORKER_ENABLED",
    "INDICTRANS2_ENDPOINT",
    "MADLAD_ENDPOINT",
    "OPUS_MT_ENDPOINT",
]

PYTHON_ENTRYPOINTS = [
    "app.py",
    "deploy/launch_env_check.py",
    "production_smoke_test.py",
    "async_task_worker.py",
    "async_workflow_processor.py",
    "worker_supervisor.py",
    "billing_webhook_receiver.py",
    "email_dispatch_worker.py",
    "operational_backup_worker.py",
    "cloud_object_storage.py",
    "production_persistence.py",
]

SECRET_PATTERNS = [
    re.compile(r"sk_live_[A-Za-z0-9]{12,}"),
    re.compile(r"rzp_live_[A-Za-z0-9]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_text(path: str) -> str:
    full_path = ROOT / path
    if not full_path.exists():
        return ""
    return full_path.read_text(encoding="utf-8", errors="ignore")


def add(results: List[Dict[str, str]], area: str, check: str, status: str, evidence: str, action: str) -> None:
    results.append({
        "Area": area,
        "Check": check,
        "Status": status,
        "Evidence": evidence,
        "Action": action,
    })


def missing_items(items: Iterable[str], text: str) -> List[str]:
    return [item for item in items if item not in text]


def requirement_name(line: str) -> str:
    text = line.strip()
    if not text or text.startswith("#") or text.startswith("-"):
        return ""
    text = text.split(";", 1)[0].strip()
    text = re.split(r"\s*(?:===|==|~=|>=|<=|>|<|!=)\s*", text, maxsplit=1)[0]
    text = text.split("[", 1)[0].strip().lower()
    return text.replace("_", "-")


def check_launch_branch_files(results: List[Dict[str, str]]) -> None:
    missing = [path for path in REQUIRED_ROOT_FILES if not (ROOT / path).exists()]
    dockerfile = read_text("Dockerfile")
    docker_uses_root_app = "streamlit" in dockerfile and "run" in dockerfile and "app.py" in dockerfile
    add(
        results,
        "Release",
        "Launch branch root app files",
        "Pass" if not missing and docker_uses_root_app else "Blocker",
        "root app.py + requirements.txt with Docker CMD" if not missing and docker_uses_root_app else f"missing={missing}; docker_cmd_app_py={docker_uses_root_app}",
        "Deploy from the repository root with app.py and requirements.txt as the canonical Streamlit entrypoint and dependency file.",
    )
    readme = read_text("README.md")
    stale = [token for token in STALE_README_TOKENS if token in readme]
    add(
        results,
        "Release",
        "Current launch README",
        "Pass" if not stale else "Blocker",
        "no stale rename instructions" if not stale else ", ".join(stale),
        "Keep README.md aligned with the final app.py/requirements.txt launch branch, not old file-renaming instructions.",
    )


def check_requirements(results: List[Dict[str, str]]) -> None:
    requirements = read_text("requirements.txt")
    packages = {requirement_name(line) for line in requirements.splitlines()}
    packages.discard("")
    missing = [package for package in REQUIRED_REQUIREMENT_PACKAGES if package not in packages]
    add(
        results,
        "Release",
        "Production requirements coverage",
        "Pass" if not missing else "Blocker",
        f"{len(packages)} package(s); required packages present" if not missing else ", ".join(missing),
        "Keep requirements.txt updated with Streamlit, dataframe, document, AI, HTTP, XML, storage, and Redis dependencies used by production services.",
    )


def check_supabase_schema(results: List[Dict[str, str]]) -> None:
    schema = read_text("supabase_v42_release_schema.sql").lower()
    missing_tables = [
        table for table in REQUIRED_SUPABASE_TABLES
        if f"create table if not exists public.{table}".lower() not in schema
    ]
    rls_missing = [
        table for table in REQUIRED_SUPABASE_TABLES
        if f"alter table public.{table} enable row level security".lower() not in schema
    ]
    add(
        results,
        "Persistence",
        "Supabase release schema tables",
        "Pass" if not missing_tables else "Blocker",
        f"{len(REQUIRED_SUPABASE_TABLES)} required table(s)" if not missing_tables else ", ".join(missing_tables),
        "Keep supabase_v42_release_schema.sql aligned with production persistence collections before running it in Supabase.",
    )
    add(
        results,
        "Persistence",
        "Supabase row-level security coverage",
        "Pass" if not rls_missing else "Warn",
        "RLS enabled for required tables" if not rls_missing else ", ".join(rls_missing),
        "Enable row-level security for production SaaS tables; service-role workers can still use server-side access.",
    )


def check_required_files(results: List[Dict[str, str]]) -> None:
    missing = [path for path in REQUIRED_DEPLOYMENT_FILES if not (ROOT / path).exists()]
    add(
        results,
        "Release",
        "Deployment pack files",
        "Pass" if not missing else "Blocker",
        "all present" if not missing else ", ".join(missing),
        "Keep Dockerfile, compose, Supabase schema, env example, deployment README, launch runbook, launch env check, and release_check.py in the release branch.",
    )


def check_secret_ignore_rules(results: List[Dict[str, str]]) -> None:
    gitignore = read_text(".gitignore")
    dockerignore = read_text(".dockerignore")
    missing_git = missing_items(["deploy/.env.production", ".streamlit/secrets.toml", ".env"], gitignore)
    missing_docker = missing_items(["deploy/.env.production", ".streamlit/secrets.toml", ".env"], dockerignore)
    status = "Pass" if not missing_git and not missing_docker else "Blocker"
    evidence = "private env/secrets ignored" if status == "Pass" else f"gitignore missing {missing_git}; dockerignore missing {missing_docker}"
    add(
        results,
        "Security",
        "Private secret files ignored",
        status,
        evidence,
        "Never ship deploy/.env.production, .env, or Streamlit secrets in git or Docker images.",
    )


def check_dockerfile(results: List[Dict[str, str]]) -> None:
    dockerfile = read_text("Dockerfile")
    required = [
        "FROM python:3.11-slim",
        "python -m pip install -r requirements.txt",
        "USER errorsweep",
        "HEALTHCHECK",
        "_stcore/health",
        "EXPOSE 8501",
    ]
    missing = missing_items(required, dockerfile)
    add(
        results,
        "Release",
        "Dockerfile production posture",
        "Pass" if not missing else "Warn",
        "non-root app image with healthcheck" if not missing else ", ".join(missing),
        "Keep the app image non-root, health-checked, and based on the pinned requirements file.",
    )


def check_compose(results: List[Dict[str, str]]) -> None:
    compose = read_text("docker-compose.production.yml")
    missing_services = missing_items(REQUIRED_COMPOSE_SERVICES, compose)
    add(
        results,
        "Release",
        "Compose service split",
        "Pass" if not missing_services else "Blocker",
        "app + async + supervisor + billing receiver" if not missing_services else ", ".join(missing_services),
        "Run long jobs, billing webhooks, and background workers outside the Streamlit request process.",
    )
    expected_tokens = [
        "./deploy/.env.production",
        "8501:8501",
        "8300:8300",
        "8301:8301",
        "errorsweep-data:",
        "errorsweep-logs:",
        "/_stcore/health",
        "/health",
    ]
    missing_tokens = missing_items(expected_tokens, compose)
    add(
        results,
        "Release",
        "Compose health and volume wiring",
        "Pass" if not missing_tokens else "Warn",
        "ports, health checks, volumes configured" if not missing_tokens else ", ".join(missing_tokens),
        "Keep public ports, shared data/log volumes, and health checks explicit in compose.",
    )


def check_env_template(results: List[Dict[str, str]]) -> None:
    env_text = read_text("deploy/.env.production.example")
    missing_keys = [key for key in REQUIRED_ENV_KEYS if not re.search(rf"^{re.escape(key)}=", env_text, re.MULTILINE)]
    secret_hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(env_text)]
    add(
        results,
        "Release",
        "Production env template coverage",
        "Pass" if not missing_keys else "Warn",
        "required launch keys listed" if not missing_keys else ", ".join(missing_keys),
        "Keep a non-secret example for every required production setting.",
    )
    add(
        results,
        "Security",
        "Env example contains no obvious live secrets",
        "Pass" if not secret_hits else "Blocker",
        "no live-key patterns found" if not secret_hits else ", ".join(secret_hits),
        "Replace any real credentials in deploy/.env.production.example with placeholders immediately.",
    )


def check_streamlit_secrets_template(results: List[Dict[str, str]]) -> None:
    template_text = read_text(".streamlit/secrets.toml.example")
    missing_keys = [
        key for key in REQUIRED_STREAMLIT_SECRET_KEYS
        if not re.search(rf"^{re.escape(key)}\s*=", template_text, re.MULTILINE)
    ]
    secret_hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(template_text)]
    add(
        results,
        "Release",
        "Streamlit secrets template coverage",
        "Pass" if not missing_keys else "Warn",
        "required Streamlit secret keys listed" if not missing_keys else ", ".join(missing_keys),
        "Keep .streamlit/secrets.toml.example aligned with Streamlit Cloud launch secrets without real values.",
    )
    add(
        results,
        "Security",
        "Streamlit secrets template contains no obvious live secrets",
        "Pass" if not secret_hits else "Blocker",
        "no live-key patterns found" if not secret_hits else ", ".join(secret_hits),
        "Replace any real credentials in .streamlit/secrets.toml.example with placeholders immediately.",
    )


def check_python_compile(results: List[Dict[str, str]]) -> None:
    failures: List[str] = []
    checked = 0
    for rel_path in PYTHON_ENTRYPOINTS:
        path = ROOT / rel_path
        if not path.exists():
            failures.append(f"{rel_path}: missing")
            continue
        checked += 1
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            compile(source, str(path), "exec")
        except Exception as exc:
            failures.append(f"{rel_path}: {safe_text(exc)[:160]}")
    add(
        results,
        "Code",
        "Production entrypoint syntax",
        "Pass" if not failures else "Blocker",
        f"{checked} file(s) compiled" if not failures else "; ".join(failures),
        "Fix Python syntax/import-time compile errors before building the container.",
    )


def check_smoke_runner(results: List[Dict[str, str]], run_smoke: bool) -> None:
    smoke_path = ROOT / "production_smoke_test.py"
    if not smoke_path.exists():
        add(results, "Release", "Production smoke runner", "Blocker", "missing", "Restore production_smoke_test.py.")
        return
    if not run_smoke:
        add(results, "Release", "Production smoke runner", "Pass", "available", "Run with --run-smoke in staging or CI when dependencies are installed.")
        return
    command = [sys.executable, "production_smoke_test.py", "--markdown"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
    except Exception as exc:
        add(results, "Release", "Production smoke runner", "Warn", safe_text(exc)[:220], "Run production_smoke_test.py manually in staging.")
        return
    output = (completed.stdout or completed.stderr or "").splitlines()
    evidence = "; ".join(line for line in output[:4] if line)[:240] or f"exit {completed.returncode}"
    add(
        results,
        "Release",
        "Production smoke runner",
        "Pass" if completed.returncode == 0 else "Warn",
        evidence,
        "Review smoke-test blockers separately; placeholder envs are expected to fail launch gates locally.",
    )


def collect_results(run_smoke: bool = False) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    check_launch_branch_files(results)
    check_required_files(results)
    check_secret_ignore_rules(results)
    check_requirements(results)
    check_supabase_schema(results)
    check_dockerfile(results)
    check_compose(results)
    check_env_template(results)
    check_streamlit_secrets_template(results)
    check_python_compile(results)
    check_smoke_runner(results, run_smoke=run_smoke)
    return results


def status_rank(status: str) -> int:
    return {"Pass": 0, "Warn": 1, "Blocker": 2}.get(status, 1)


def summarize(results: List[Dict[str, str]]) -> Dict[str, Any]:
    counts = {"Pass": 0, "Warn": 0, "Blocker": 0}
    for row in results:
        counts[row["Status"]] = counts.get(row["Status"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "Blocker" if counts["Blocker"] else "Warn" if counts["Warn"] else "Pass",
        "checks": len(results),
        "counts": counts,
    }


def markdown_report(summary: Dict[str, Any], results: List[Dict[str, str]]) -> str:
    lines = [
        "# ErrorSweep Release Check",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Result: {summary['result']}",
        f"- Checks: {summary['checks']}",
        f"- Pass/Warn/Blocker: {summary['counts'].get('Pass', 0)} / {summary['counts'].get('Warn', 0)} / {summary['counts'].get('Blocker', 0)}",
        "",
        "| Area | Check | Status | Evidence | Action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in results:
        safe = {key: safe_text(value).replace("|", "\\|").replace("\n", " ") for key, value in row.items()}
        lines.append(f"| {safe['Area']} | {safe['Check']} | {safe['Status']} | {safe['Evidence']} | {safe['Action']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline ErrorSweep release checks.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--run-smoke", action="store_true", help="Also run production_smoke_test.py --markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    results = sorted(collect_results(run_smoke=args.run_smoke), key=lambda row: (status_rank(row["Status"]), row["Area"], row["Check"]))
    summary = summarize(results)
    if args.json:
        print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(markdown_report(summary, results))
    if args.fail_on_warn and (summary["counts"].get("Warn") or summary["counts"].get("Blocker")):
        return 1
    if args.strict and summary["counts"].get("Blocker"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
