"""Offline release validation for the CogniSweep deployment pack.

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
    "deploy/ai_fallback_check.py",
    "deploy/auth_session_check.py",
    "deploy/async_worker_check.py",
    "deploy/backup_check.py",
    "deploy/billing_check.py",
    "deploy/email_check.py",
    "deploy/legal_check.py",
    "deploy/launch_env_check.py",
    "deploy/mt_endpoint_check.py",
    "deploy/object_storage_check.py",
    "deploy/supabase_schema_check.py",
    "deploy/release_check.py",
    "deploy/launch_rehearsal.py",
    ".github/workflows/release-gate.yml",
]

REQUIRED_ROOT_FILES = [
    "app.py",
    "requirements.txt",
    "requirements.lock.txt",
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

REQUIREMENT_FILES = [
    "requirements.txt",
    "requirements_opus_mt_server.txt",
    "requirements_madlad_mt_server.txt",
    "requirements_indictrans2_worker.txt",
]

LOCKED_REQUIREMENTS_FILE = "requirements.lock.txt"
PINNED_REQUIREMENT_RE = re.compile(
    r"^[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[A-Za-z0-9_.!+*-]+(?:\s*;.+)?$"
)
DOCKER_BASE_DIGEST = "python:3.11-slim@sha256:"
PINNED_PIP_INSTALL = "pip==26.1.2"

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
    "ERRORSWEEP_ENFORCE_PUBLIC_LAUNCH_PREFLIGHT",
    "ERRORSWEEP_PUBLIC_BASE_URL",
    "ERRORSWEEP_SESSION_SECRET",
    "ERRORSWEEP_OWNER_USERNAME",
    "ERRORSWEEP_OWNER_PASSWORD_HASH",
    "ERRORSWEEP_USER_USERNAME",
    "ERRORSWEEP_USER_PASSWORD_HASH",
    "ERRORSWEEP_ORG_NAME",
    "ERRORSWEEP_DEFAULT_USER_ROLE",
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
    "ERRORSWEEP_OBJECT_STORAGE_ALLOW_PUBLIC_URLS",
    "ERRORSWEEP_ASYNC_WORKER_URL",
    "ERRORSWEEP_ASYNC_WORKER_TOKEN",
    "ERRORSWEEP_WORKER_SUPERVISOR_ENABLED",
    "ERRORSWEEP_BILLING_PROVIDER",
    "ERRORSWEEP_BILLING_WEBHOOK_SECRET",
    "ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL",
    "ERRORSWEEP_WEBHOOK_APPLY_UPDATES",
    "ERRORSWEEP_BILLING_CREATE_PROVIDER_CHECKOUT",
    "ERRORSWEEP_EMAIL_PROVIDER",
    "ERRORSWEEP_EMAIL_FROM",
    "ERRORSWEEP_EMAIL_HTML_ENABLED",
    "ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED",
    "ERRORSWEEP_EMAIL_WORKER_INTERVAL_SECONDS",
    "ERRORSWEEP_EMAIL_DISPATCH_BATCH_LIMIT",
    "ERRORSWEEP_BACKUP_PROVIDER",
    "ERRORSWEEP_BACKUP_WORKER_ENABLED",
    "ERRORSWEEP_BACKUP_INTERVAL_HOURS",
    "ERRORSWEEP_BACKUP_RETENTION_DAYS",
    "ERRORSWEEP_BACKUP_OBJECT_STORAGE_ENABLED",
    "ERRORSWEEP_BACKUP_OUTPUT_DIR",
    "ERRORSWEEP_WAF_PROVIDER",
    "INDICTRANS2_ENDPOINT",
    "MADLAD_ENDPOINT",
    "OPUS_MT_ENDPOINT",
    "SELF_HOSTED_MT_TIMEOUT",
]

REQUIRED_STREAMLIT_SECRET_KEYS = [
    "ERRORSWEEP_ENV",
    "ERRORSWEEP_ENFORCE_PUBLIC_LAUNCH_PREFLIGHT",
    "ERRORSWEEP_PUBLIC_BASE_URL",
    "ERRORSWEEP_SESSION_SECRET",
    "ERRORSWEEP_OWNER_USERNAME",
    "ERRORSWEEP_OWNER_PASSWORD_HASH",
    "ERRORSWEEP_USER_USERNAME",
    "ERRORSWEEP_USER_PASSWORD_HASH",
    "ERRORSWEEP_ORG_NAME",
    "ERRORSWEEP_DEFAULT_USER_ROLE",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "ERRORSWEEP_OBJECT_STORAGE_PROVIDER",
    "ERRORSWEEP_OBJECT_STORAGE_ALLOW_PUBLIC_URLS",
    "ERRORSWEEP_ASYNC_WORKER_URL",
    "ERRORSWEEP_ASYNC_WORKER_TOKEN",
    "ERRORSWEEP_BILLING_PROVIDER",
    "ERRORSWEEP_BILLING_WEBHOOK_SECRET",
    "ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL",
    "ERRORSWEEP_BILLING_CREATE_PROVIDER_CHECKOUT",
    "ERRORSWEEP_EMAIL_PROVIDER",
    "ERRORSWEEP_EMAIL_FROM",
    "ERRORSWEEP_LEGAL_REVIEWED",
    "ERRORSWEEP_WAF_PROVIDER",
    "ERRORSWEEP_BACKUP_PROVIDER",
    "ERRORSWEEP_BACKUP_WORKER_ENABLED",
    "ERRORSWEEP_BACKUP_RETENTION_DAYS",
    "INDICTRANS2_ENDPOINT",
    "MADLAD_ENDPOINT",
    "OPUS_MT_ENDPOINT",
]

PYTHON_ENTRYPOINTS = [
    "app.py",
    "deploy/ai_fallback_check.py",
    "deploy/auth_session_check.py",
    "deploy/async_worker_check.py",
    "deploy/backup_check.py",
    "deploy/billing_check.py",
    "deploy/email_check.py",
    "deploy/legal_check.py",
    "deploy/launch_env_check.py",
    "deploy/mt_endpoint_check.py",
    "deploy/object_storage_check.py",
    "deploy/supabase_schema_check.py",
    "deploy/launch_rehearsal.py",
    "production_smoke_test.py",
    "async_task_worker.py",
    "async_workflow_processor.py",
    "worker_supervisor.py",
    "billing_webhook_receiver.py",
    "email_dispatch_worker.py",
    "operational_backup_worker.py",
    "cloud_object_storage.py",
    "production_persistence.py",
    "local_file_lock.py",
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


def active_requirement_lines(text: str) -> List[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def unpinned_requirement_lines(path: str) -> List[str]:
    return [
        line
        for line in active_requirement_lines(read_text(path))
        if not PINNED_REQUIREMENT_RE.fullmatch(line)
    ]


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
    pin_failures = {
        path: lines
        for path in REQUIREMENT_FILES
        if (lines := unpinned_requirement_lines(path))
    }
    add(
        results,
        "Release",
        "Exact dependency pins",
        "Pass" if not pin_failures else "Blocker",
        "all requirements*.txt entries use ==" if not pin_failures else "; ".join(f"{path}: {lines[:3]}" for path, lines in pin_failures.items()),
        "Keep every production and worker requirement exactly pinned; update the lockfile in the same change.",
    )
    lock_text = read_text(LOCKED_REQUIREMENTS_FILE)
    lock_lines = active_requirement_lines(lock_text)
    lock_packages = {requirement_name(line) for line in lock_lines}
    lock_missing_direct = [package for package in packages if package not in lock_packages]
    lock_unpinned = unpinned_requirement_lines(LOCKED_REQUIREMENTS_FILE)
    lock_ok = bool(lock_text) and bool(lock_lines) and not lock_missing_direct and not lock_unpinned
    add(
        results,
        "Release",
        "Production dependency lockfile",
        "Pass" if lock_ok else "Blocker",
        f"{len(lock_lines)} locked package(s)" if lock_ok else f"missing_direct={lock_missing_direct[:5]}; unpinned={lock_unpinned[:5]}; present={bool(lock_text)}",
        "Keep requirements.lock.txt generated from requirements.txt and install it in the production Docker image.",
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
    rls_policy_tables = set(
        re.findall(r"create\s+policy\s+[a-zA-Z_][\w]*\s+on\s+public\.([a-zA-Z_][\w]*)", schema, flags=re.IGNORECASE)
    )
    policy_missing = [table for table in REQUIRED_SUPABASE_TABLES if table not in rls_policy_tables]
    helper_tokens = [
        "create or replace function public.errorsweep_jwt_workspace()",
        "create or replace function public.errorsweep_jwt_email()",
        "create or replace function public.errorsweep_is_platform_owner()",
        "create or replace function public.errorsweep_workspace_matches(row_workspace text)",
        "create or replace function public.errorsweep_email_matches(row_email text)",
    ]
    missing_helpers = [token for token in helper_tokens if token not in schema]
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
    add(
        results,
        "Persistence",
        "Supabase tenant RLS policy coverage",
        "Pass" if not policy_missing and not missing_helpers else "Blocker",
        f"{len(rls_policy_tables)} table policy target(s)" if not policy_missing and not missing_helpers else f"missing_policies={policy_missing}; missing_helpers={len(missing_helpers)}",
        "Keep explicit workspace/user RLS policies for every production table; ENABLE RLS alone is not enough.",
    )


def check_supabase_schema_contract(results: List[Dict[str, str]]) -> None:
    command = [sys.executable, "deploy/supabase_schema_check.py", "--json"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception as exc:
        add(results, "Persistence", "Supabase schema drift check", "Warn", safe_text(exc)[:220], "Run deploy/supabase_schema_check.py manually.")
        return
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        summary = payload.get("summary") or {}
        counts = summary.get("counts") or {}
        blocker_count = int(counts.get("Blocker") or 0)
        warn_count = int(counts.get("Warn") or 0)
        evidence = f"{summary.get('checks', 0)} check(s); {counts.get('Pass', 0)} pass / {warn_count} warn / {blocker_count} blocker"
        status = "Blocker" if blocker_count else "Warn" if warn_count else "Pass"
    except Exception:
        evidence = output.splitlines()[0][:220] if output.splitlines() else f"exit {completed.returncode}"
        status = "Pass" if completed.returncode == 0 else "Blocker"
    add(
        results,
        "Persistence",
        "Supabase schema drift check",
        status,
        evidence,
        "Keep supabase_v42_release_schema.sql aligned with production_persistence.py before running the schema in Supabase.",
    )


def check_object_storage_contract(results: List[Dict[str, str]]) -> None:
    command = [sys.executable, "deploy/object_storage_check.py", "--json"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception as exc:
        add(results, "Storage", "Object storage launch check", "Warn", safe_text(exc)[:220], "Run deploy/object_storage_check.py manually.")
        return
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        summary = payload.get("summary") or {}
        counts = summary.get("counts") or {}
        blocker_count = int(counts.get("Blocker") or 0)
        warn_count = int(counts.get("Warn") or 0)
        evidence = f"{summary.get('checks', 0)} check(s); {counts.get('Pass', 0)} pass / {warn_count} warn / {blocker_count} blocker"
        status = "Blocker" if blocker_count else "Warn" if warn_count else "Pass"
    except Exception:
        evidence = output.splitlines()[0][:220] if output.splitlines() else f"exit {completed.returncode}"
        status = "Pass" if completed.returncode == 0 else "Blocker"
    add(
        results,
        "Storage",
        "Object storage launch check",
        status,
        evidence,
        "Keep cloud_object_storage.py, provider dependencies, and storage env templates ready before configuring production buckets.",
    )


def check_async_worker_contract(results: List[Dict[str, str]]) -> None:
    command = [sys.executable, "deploy/async_worker_check.py", "--json"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception as exc:
        add(results, "Async", "Async worker launch check", "Warn", safe_text(exc)[:220], "Run deploy/async_worker_check.py manually.")
        return
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        summary = payload.get("summary") or {}
        counts = summary.get("counts") or {}
        blocker_count = int(counts.get("Blocker") or 0)
        warn_count = int(counts.get("Warn") or 0)
        evidence = f"{summary.get('checks', 0)} check(s); {counts.get('Pass', 0)} pass / {warn_count} warn / {blocker_count} blocker"
        status = "Blocker" if blocker_count else "Warn" if warn_count else "Pass"
    except Exception:
        evidence = output.splitlines()[0][:220] if output.splitlines() else f"exit {completed.returncode}"
        status = "Pass" if completed.returncode == 0 else "Blocker"
    add(
        results,
        "Async",
        "Async worker launch check",
        status,
        evidence,
        "Keep async queue, receiver, processor, supervisor, compose wiring, and worker templates deploy-ready.",
    )


def check_backup_contract(results: List[Dict[str, str]]) -> None:
    command = [sys.executable, "deploy/backup_check.py", "--json"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception as exc:
        add(results, "Backup", "Backup launch check", "Warn", safe_text(exc)[:220], "Run deploy/backup_check.py manually.")
        return
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        summary = payload.get("summary") or {}
        counts = summary.get("counts") or {}
        blocker_count = int(counts.get("Blocker") or 0)
        warn_count = int(counts.get("Warn") or 0)
        evidence = f"{summary.get('checks', 0)} check(s); {counts.get('Pass', 0)} pass / {warn_count} warn / {blocker_count} blocker"
        status = "Blocker" if blocker_count else "Warn" if warn_count else "Pass"
    except Exception:
        evidence = output.splitlines()[0][:220] if output.splitlines() else f"exit {completed.returncode}"
        status = "Pass" if completed.returncode == 0 else "Blocker"
    add(
        results,
        "Backup",
        "Backup launch check",
        status,
        evidence,
        "Keep operational backup worker, redaction, manifest/audit records, object-storage upload, supervisor wiring, and backup env templates deploy-ready.",
    )


def check_billing_contract(results: List[Dict[str, str]]) -> None:
    command = [sys.executable, "deploy/billing_check.py", "--json"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception as exc:
        add(results, "Billing", "Billing launch check", "Warn", safe_text(exc)[:220], "Run deploy/billing_check.py manually.")
        return
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        summary = payload.get("summary") or {}
        counts = summary.get("counts") or {}
        blocker_count = int(counts.get("Blocker") or 0)
        warn_count = int(counts.get("Warn") or 0)
        evidence = f"{summary.get('checks', 0)} check(s); {counts.get('Pass', 0)} pass / {warn_count} warn / {blocker_count} blocker"
        status = "Blocker" if blocker_count else "Warn" if warn_count else "Pass"
    except Exception:
        evidence = output.splitlines()[0][:220] if output.splitlines() else f"exit {completed.returncode}"
        status = "Pass" if completed.returncode == 0 else "Blocker"
    add(
        results,
        "Billing",
        "Billing launch check",
        status,
        evidence,
        "Keep billing provider env templates, provider signature checks, webhook receiver service, checkout settings, compose wiring, and receiver health smoke deploy-ready.",
    )


def check_email_contract(results: List[Dict[str, str]]) -> None:
    command = [sys.executable, "deploy/email_check.py", "--json"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception as exc:
        add(results, "Email", "Email launch check", "Warn", safe_text(exc)[:220], "Run deploy/email_check.py manually.")
        return
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        summary = payload.get("summary") or {}
        counts = summary.get("counts") or {}
        blocker_count = int(counts.get("Blocker") or 0)
        warn_count = int(counts.get("Warn") or 0)
        evidence = f"{summary.get('checks', 0)} check(s); {counts.get('Pass', 0)} pass / {warn_count} warn / {blocker_count} blocker"
        status = "Blocker" if blocker_count else "Warn" if warn_count else "Pass"
    except Exception:
        evidence = output.splitlines()[0][:220] if output.splitlines() else f"exit {completed.returncode}"
        status = "Pass" if completed.returncode == 0 else "Blocker"
    add(
        results,
        "Email",
        "Email launch check",
        status,
        evidence,
        "Keep provider env templates, transactional templates, Resend/SendGrid/SMTP dispatch worker, supervisor wiring, and dry-run smoke deploy-ready.",
    )


def check_legal_contract(results: List[Dict[str, str]]) -> None:
    command = [sys.executable, "deploy/legal_check.py", "--json"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception as exc:
        add(results, "Legal", "Legal launch check", "Warn", safe_text(exc)[:220], "Run deploy/legal_check.py manually.")
        return
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        summary = payload.get("summary") or {}
        counts = summary.get("counts") or {}
        blocker_count = int(counts.get("Blocker") or 0)
        warn_count = int(counts.get("Warn") or 0)
        evidence = f"{summary.get('checks', 0)} check(s); {counts.get('Pass', 0)} pass / {warn_count} warn / {blocker_count} blocker"
        status = "Blocker" if blocker_count else "Warn" if warn_count else "Pass"
    except Exception:
        evidence = output.splitlines()[0][:220] if output.splitlines() else f"exit {completed.returncode}"
        status = "Pass" if completed.returncode == 0 else "Blocker"
    add(
        results,
        "Legal",
        "Legal launch check",
        status,
        evidence,
        "Keep public legal routes, policy version controls, consent capture, privacy requests, subprocessor register, schema, and legal/WAF env keys deploy-ready.",
    )


def check_ai_fallback_contract(results: List[Dict[str, str]]) -> None:
    command = [sys.executable, "deploy/ai_fallback_check.py", "--json"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception as exc:
        add(results, "AI", "AI fallback launch check", "Warn", safe_text(exc)[:220], "Run deploy/ai_fallback_check.py manually.")
        return
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        summary = payload.get("summary") or {}
        counts = summary.get("counts") or {}
        blocker_count = int(counts.get("Blocker") or 0)
        warn_count = int(counts.get("Warn") or 0)
        evidence = f"{summary.get('checks', 0)} check(s); {counts.get('Pass', 0)} pass / {warn_count} warn / {blocker_count} blocker"
        status = "Blocker" if blocker_count else "Warn" if warn_count else "Pass"
    except Exception:
        evidence = output.splitlines()[0][:220] if output.splitlines() else f"exit {completed.returncode}"
        status = "Pass" if completed.returncode == 0 else "Blocker"
    add(
        results,
        "AI",
        "AI fallback launch check",
        status,
        evidence,
        "Keep managed_ai_router.py, AI env templates, URL safety, and platform fallback wiring deploy-ready.",
    )


def check_auth_session_contract(results: List[Dict[str, str]]) -> None:
    command = [sys.executable, "deploy/auth_session_check.py", "--json"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception as exc:
        add(results, "Auth", "Auth/session launch check", "Warn", safe_text(exc)[:220], "Run deploy/auth_session_check.py manually.")
        return
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        summary = payload.get("summary") or {}
        counts = summary.get("counts") or {}
        blocker_count = int(counts.get("Blocker") or 0)
        warn_count = int(counts.get("Warn") or 0)
        evidence = f"{summary.get('checks', 0)} check(s); {counts.get('Pass', 0)} pass / {warn_count} warn / {blocker_count} blocker"
        status = "Blocker" if blocker_count else "Warn" if warn_count else "Pass"
    except Exception:
        evidence = output.splitlines()[0][:220] if output.splitlines() else f"exit {completed.returncode}"
        status = "Pass" if completed.returncode == 0 else "Blocker"
    add(
        results,
        "Auth",
        "Auth/session launch check",
        status,
        evidence,
        "Keep production session secret, public URL, owner/workspace bootstrap hashes, and auth-token persistence deploy-ready.",
    )


def check_mt_endpoint_contract(results: List[Dict[str, str]]) -> None:
    command = [sys.executable, "deploy/mt_endpoint_check.py", "--json"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    except Exception as exc:
        add(results, "MT", "MT endpoint launch check", "Warn", safe_text(exc)[:220], "Run deploy/mt_endpoint_check.py manually.")
        return
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        summary = payload.get("summary") or {}
        counts = summary.get("counts") or {}
        blocker_count = int(counts.get("Blocker") or 0)
        warn_count = int(counts.get("Warn") or 0)
        evidence = f"{summary.get('checks', 0)} check(s); {counts.get('Pass', 0)} pass / {warn_count} warn / {blocker_count} blocker"
        status = "Blocker" if blocker_count else "Warn" if warn_count else "Pass"
    except Exception:
        evidence = output.splitlines()[0][:220] if output.splitlines() else f"exit {completed.returncode}"
        status = "Pass" if completed.returncode == 0 else "Blocker"
    add(
        results,
        "MT",
        "MT endpoint launch check",
        status,
        evidence,
        "Keep OPUS-MT, IndicTrans2, and MADLAD endpoint contracts, requirements, docs, and launch templates ready.",
    )


def check_required_files(results: List[Dict[str, str]]) -> None:
    missing = [path for path in REQUIRED_DEPLOYMENT_FILES if not (ROOT / path).exists()]
    add(
        results,
        "Release",
        "Deployment pack files",
        "Pass" if not missing else "Blocker",
        "all present" if not missing else ", ".join(missing),
        "Keep Dockerfile, compose, Supabase schema, env example, deployment README, launch runbook, launch checkers, release guard, and launch rehearsal script in the release branch.",
    )


def check_ci_release_gate(results: List[Dict[str, str]]) -> None:
    workflow = read_text(".github/workflows/release-gate.yml")
    required = [
        "workflow_dispatch:",
        "actions/setup-python@v5",
        "python-version: \"3.11\"",
        "python -m pip install -r requirements.txt",
        "deploy/backup_check.py",
        "deploy/billing_check.py",
        "deploy/email_check.py",
        "deploy/legal_check.py",
        "python test_backup_check.py",
        "python test_billing_check.py",
        "python test_billing_webhook_replay.py",
        "python test_email_check.py",
        "python test_email_template_security.py",
        "python test_legal_check.py",
        "python test_ai_json_extraction.py",
        "python test_launch_rehearsal.py",
        "python test_launch_public_lock.py",
        "python test_backup_redaction.py",
        "python test_excel_backlog_security_hardening.py",
        "python test_app_zip_safety.py",
        "python test_process_file_locks.py",
        "python test_async_docx_security.py",
        "python test_async_manifest_security.py",
        "python test_dependency_locking.py",
        "python test_local_translation_engine_routes.py",
        "python test_model_download_integrity.py",
        "python test_persistence_cache_hardening.py",
        "python test_qa_correction_cache.py",
        "python test_subtitle_external_editor_only.py",
        "python test_release_gate_workflow.py",
        "python deploy/release_check.py --strict",
        "python deploy/launch_rehearsal.py",
        "--base-url http://localhost:8501",
        "--skip-release-check",
        "--skip-launch-env-check",
        "--skip-smoke-test",
    ]
    missing = missing_items(required, workflow)
    add(
        results,
        "Release",
        "GitHub Actions release gate",
        "Pass" if workflow and not missing else "Blocker",
        "launch-safe CI workflow present" if workflow and not missing else ", ".join(missing) or "missing workflow",
        "Keep .github/workflows/release-gate.yml running production dependency install, launch-safe tests, release_check.py --strict, and rehearsal smoke without external probes.",
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
        f"FROM {DOCKER_BASE_DIGEST}",
        PINNED_PIP_INSTALL,
        "python -m pip install -r requirements.lock.txt",
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
    opus_dockerfile = read_text("Dockerfile.opus-mt")
    opus_required = [
        f"FROM {DOCKER_BASE_DIGEST}",
        PINNED_PIP_INSTALL,
        "torch==2.12.0",
        "-r /app/requirements_opus_mt_server.txt",
    ]
    opus_missing = missing_items(opus_required, opus_dockerfile)
    add(
        results,
        "MT",
        "OPUS-MT Dockerfile dependency posture",
        "Pass" if not opus_missing else "Warn",
        "digest-pinned base and exact worker dependencies" if not opus_missing else ", ".join(opus_missing),
        "Keep the OPUS-MT image base digest-pinned with exact worker package versions.",
    )


def check_persistence_cache_hardening(results: List[Dict[str, str]]) -> None:
    app = read_text("app.py")
    required = [
        "SAAS_CACHEABLE_COLLECTIONS",
        "@st.cache_data(ttl=SAAS_CACHE_TTL_SECONDS, show_spinner=False)",
        "def _cached_fetch_saas_records",
        "cache_generation",
        "clear_saas_record_cache()",
        "except ValueError as exc:",
        "except requests.RequestException as exc:",
    ]
    missing = missing_items(required, app)
    silent_passes = re.findall(r"except(?:\s+\w+)?(?:\s+as\s+\w+)?:\s*\n\s*pass\b", app)
    cache_block_match = re.search(r"SAAS_CACHEABLE_COLLECTIONS\s*=\s*\{(?P<body>.*?)\n\}", app, re.S)
    cache_block = cache_block_match.group("body") if cache_block_match else ""
    unsafe_cached = [item for item in ['"users"', '"auth_tokens"', '"task_queue"'] if item in cache_block]
    ok = not missing and not silent_passes and not unsafe_cached
    evidence = (
        "cached safe SaaS reads with invalidation and no silent exception passes"
        if ok
        else f"missing={missing}; silent_passes={len(silent_passes)}; unsafe_cached={unsafe_cached}"
    )
    add(
        results,
        "Persistence",
        "App persistence cache and exception hardening",
        "Pass" if ok else "Blocker",
        evidence,
        "Keep hot Supabase reads cache_data-backed, invalidate after writes/deletes, and avoid silent exception swallowing.",
    )


def check_production_persistence_fail_closed(results: List[Dict[str, str]]) -> None:
    app = read_text("app.py")
    persistence = read_text("production_persistence.py")
    workflow = read_text(".github/workflows/release-gate.yml")
    required = [
        "def require_supabase_for_production()",
        "def local_json_fallback_allowed()",
        "blocked_missing_supabase",
        "Supabase persistence is required in production",
        "Production persistence configuration blocked startup",
        "python test_production_persistence_fail_closed.py",
    ]
    combined = "\n".join([app, persistence, workflow])
    missing = missing_items(required, combined)
    add(
        results,
        "Persistence",
        "Production persistence fail-closed fallback",
        "Pass" if not missing else "Blocker",
        "production mode blocks local JSON fallback when Supabase is missing" if not missing else ", ".join(missing),
        "Keep local JSON persistence as development-only; production must use Supabase or stop.",
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
        "127.0.0.1:8300:8300",
        "127.0.0.1:8301:8301",
        "127.0.0.1:6379:6379",
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
    check_ci_release_gate(results)
    check_secret_ignore_rules(results)
    check_requirements(results)
    check_ai_fallback_contract(results)
    check_auth_session_contract(results)
    check_async_worker_contract(results)
    check_backup_contract(results)
    check_billing_contract(results)
    check_email_contract(results)
    check_legal_contract(results)
    check_mt_endpoint_contract(results)
    check_supabase_schema(results)
    check_supabase_schema_contract(results)
    check_object_storage_contract(results)
    check_persistence_cache_hardening(results)
    check_production_persistence_fail_closed(results)
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
        "# CogniSweep Release Check",
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
    parser = argparse.ArgumentParser(description="Run offline CogniSweep release checks.")
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
