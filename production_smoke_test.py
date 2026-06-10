"""Production smoke-test runner for ErrorSweep.

Use this in CI/CD or before public launch to validate deployment wiring without
importing the Streamlit app or printing secret values.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests

from async_worker_queue import async_backend_status
from cloud_object_storage import object_storage_status
from email_dispatch_worker import dispatch_pending as dry_run_email_dispatch
from operational_backup_worker import configured_collections, run_backup
from production_persistence import persistence_health

LOGGER = logging.getLogger("errorsweep.production_smoke_test")
DEFAULT_SESSION_SECRET = "errorsweep-dev-session-secret-change-me"
PLACEHOLDER_MARKERS = (
    "replace-with",
    "your-domain.com",
    "yourdomain.com",
    "your-project",
    "example.com",
    "placeholder",
)


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value not in (None, ""):
        return str(value).strip()
    return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _configured(*names: str) -> bool:
    return any(bool(_env(name)) and not _is_placeholder(_env(name)) for name in names)


def _is_placeholder(value: str) -> bool:
    lowered = _safe_text(value).lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _status_rank(status: str) -> int:
    return {"Pass": 0, "Warn": 1, "Blocker": 2}.get(status, 1)


def add_result(results: List[Dict[str, str]], area: str, check: str, status: str, evidence: str, action: str) -> None:
    results.append({
        "Area": area,
        "Check": check,
        "Status": status,
        "Evidence": evidence,
        "Action": action,
    })


def billing_provider_ready(provider: str) -> bool:
    provider = _safe_text(provider).lower()
    if provider == "stripe":
        return _configured("STRIPE_SECRET_KEY", "ERRORSWEEP_STRIPE_SECRET_KEY")
    if provider == "razorpay":
        return _configured("RAZORPAY_KEY_ID") and _configured("RAZORPAY_KEY_SECRET")
    return False


def billing_plan_ids_ready(provider: str) -> bool:
    provider = _safe_text(provider).lower()
    if provider == "stripe":
        return _configured("STRIPE_PRICE_ID_PRO") and _configured("STRIPE_PRICE_ID_AGENCY")
    if provider == "razorpay":
        return _configured("RAZORPAY_PLAN_ID_PRO") and _configured("RAZORPAY_PLAN_ID_AGENCY")
    return False


def email_provider_ready(provider: str) -> bool:
    provider = _safe_text(provider).lower()
    if provider == "resend":
        return _configured("RESEND_API_KEY", "ERRORSWEEP_RESEND_API_KEY")
    if provider == "sendgrid":
        return _configured("SENDGRID_API_KEY", "ERRORSWEEP_SENDGRID_API_KEY")
    if provider == "smtp":
        return _configured("SMTP_HOST", "ERRORSWEEP_SMTP_HOST")
    return False


def managed_ai_ready() -> bool:
    return _env_bool("ERRORSWEEP_MANAGED_AI_ENABLED") and _https_url(_env("ERRORSWEEP_MANAGED_AI_BASE_URL"))


def mt_endpoint_ready(name: str) -> bool:
    return _https_url(_env(name)) and not _is_placeholder(_env(name))


def public_probe(url: str, timeout: int) -> Dict[str, str]:
    if not url:
        return {"status": "not_configured", "detail": ""}
    try:
        response = requests.get(url, timeout=timeout)
        return {"status": "ok" if response.status_code < 500 else "error", "detail": f"HTTP {response.status_code}"}
    except Exception as exc:
        return {"status": "error", "detail": _safe_text(exc)[:220]}


def deployment_pack_status() -> Dict[str, Any]:
    required_files = [
        "Dockerfile",
        "docker-compose.production.yml",
        "deploy/.env.production.example",
        "deploy/README_DEPLOYMENT.md",
        "deploy/LAUNCH_RUNBOOK.md",
        "deploy/launch_env_check.py",
        "deploy/release_check.py",
    ]
    required_services = [
        "errorsweep-app:",
        "errorsweep-async-receiver:",
        "errorsweep-worker-supervisor:",
        "errorsweep-billing-webhook:",
    ]
    present_files = [path for path in required_files if Path(path).exists()]
    compose_path = Path("docker-compose.production.yml")
    compose_text = ""
    if compose_path.exists():
        try:
            compose_text = compose_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            compose_text = ""
    present_services = [service for service in required_services if service in compose_text]
    return {
        "required_files": required_files,
        "present_files": present_files,
        "required_services": required_services,
        "present_services": present_services,
        "files_ready": len(present_files) == len(required_files),
        "services_ready": len(present_services) == len(required_services),
    }


def billing_health_url(webhook_url: str) -> str:
    parsed = urlparse(webhook_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}/health"


def collect_results(probe_endpoints: bool = False, probe_timeout: int = 10) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    env_mode = _env("ERRORSWEEP_ENV", _env("ENVIRONMENT", _env("APP_ENV"))).lower()
    public_url = _env("ERRORSWEEP_PUBLIC_BASE_URL")
    session_secret = _env("ERRORSWEEP_SESSION_SECRET")

    add_result(
        results,
        "Core",
        "Production mode",
        "Pass" if env_mode == "production" else "Blocker",
        env_mode or "missing",
        "Set ERRORSWEEP_ENV=production before public traffic.",
    )
    add_result(
        results,
        "Core",
        "Session secret",
        "Pass" if session_secret and session_secret != DEFAULT_SESSION_SECRET else "Blocker",
        "custom configured" if session_secret and session_secret != DEFAULT_SESSION_SECRET else "missing/default",
        "Set ERRORSWEEP_SESSION_SECRET to a long random value.",
    )
    add_result(
        results,
        "Core",
        "Public HTTPS URL",
        "Pass" if _https_url(public_url) else "Blocker",
        public_url or "missing",
        "Set ERRORSWEEP_PUBLIC_BASE_URL to the deployed HTTPS app URL.",
    )
    deployment_status = deployment_pack_status()
    add_result(
        results,
        "Release",
        "Deployment pack files",
        "Pass" if deployment_status["files_ready"] else "Warn",
        f"{len(deployment_status['present_files'])}/{len(deployment_status['required_files'])} present",
        "Keep Dockerfile, docker-compose.production.yml, deploy/.env.production.example, deploy/README_DEPLOYMENT.md, deploy/LAUNCH_RUNBOOK.md, deploy/launch_env_check.py, and deploy/release_check.py with the release branch.",
    )
    add_result(
        results,
        "Release",
        "Deployment service wiring",
        "Pass" if deployment_status["services_ready"] else "Warn",
        f"{len(deployment_status['present_services'])}/{len(deployment_status['required_services'])} services present",
        "Compose should run the app, async receiver, worker supervisor, and billing webhook receiver as separate services.",
    )
    if probe_endpoints and public_url:
        probe = public_probe(public_url, probe_timeout)
        add_result(
            results,
            "Core",
            "Public app probe",
            "Pass" if probe["status"] == "ok" else "Warn",
            probe["detail"],
            "Verify the public app URL and deployment routing.",
        )

    try:
        health = persistence_health()
        table_values = list((health.get("saas_tables") or {}).values())
        supabase_ready = bool(health.get("supabase_configured")) and table_values and all(_safe_text(value) == "ok" for value in table_values)
        add_result(
            results,
            "Persistence",
            "Supabase SaaS tables",
            "Pass" if supabase_ready else "Blocker",
            "configured and reachable" if supabase_ready else _safe_text(health.get("storage_mode") or health.get("error") or "not configured"),
            "Run the release schema and configure SUPABASE_URL plus SUPABASE_SERVICE_ROLE_KEY.",
        )
    except Exception as exc:
        add_result(results, "Persistence", "Supabase SaaS tables", "Blocker", _safe_text(exc)[:220], "Check Supabase credentials and network access.")

    try:
        storage = object_storage_status()
        cloud_ready = storage.get("mode") == "cloud" and bool(storage.get("configured"))
        add_result(
            results,
            "Storage",
            "Object storage",
            "Pass" if cloud_ready else "Warn",
            f"{storage.get('provider', 'local')} / {storage.get('mode', 'local_fallback')}",
            "Configure Supabase Storage, S3, or GCS for multi-instance file durability.",
        )
    except Exception as exc:
        add_result(results, "Storage", "Object storage", "Warn", _safe_text(exc)[:220], "Check object storage provider credentials.")

    try:
        async_status = async_backend_status()
        async_ready = async_status.get("mode") == "external" and bool(async_status.get("ready"))
        async_worker_url = _safe_text(async_status.get("worker_url"))
        add_result(
            results,
            "Async",
            "External QA/Pro worker",
            "Pass" if async_ready else "Warn",
            f"{async_status.get('provider', 'local')} / {async_status.get('mode', 'local_inline')}",
            "Configure ERRORSWEEP_ASYNC_WORKER_URL or REDIS_URL/CELERY_BROKER_URL for large jobs.",
        )
        add_result(
            results,
            "Async",
            "Async receiver service flag",
            "Pass" if _env_bool("ERRORSWEEP_ASYNC_WORKER_SERVICE_ENABLED") else "Warn",
            "enabled" if _env_bool("ERRORSWEEP_ASYNC_WORKER_SERVICE_ENABLED") else "not enabled",
            "Set ERRORSWEEP_ASYNC_WORKER_SERVICE_ENABLED=true when running async_task_worker.py.",
        )
        processor_file = Path("async_workflow_processor.py")
        add_result(
            results,
            "Async",
            "QA/Pro workflow processor",
            "Pass" if processor_file.exists() else "Blocker",
            "available" if processor_file.exists() else "missing",
            "Deploy async_workflow_processor.py with the receiver and run python async_workflow_processor.py --smoke before launch.",
        )
        add_result(
            results,
            "Async",
            "Async processor schedule",
            "Pass" if _env_bool("ERRORSWEEP_ASYNC_PROCESSOR_ENABLED") or _env_bool("ERRORSWEEP_ASYNC_PROCESS_ON_ACCEPT") else "Warn",
            "configured" if _env_bool("ERRORSWEEP_ASYNC_PROCESSOR_ENABLED") or _env_bool("ERRORSWEEP_ASYNC_PROCESS_ON_ACCEPT") else "not configured",
            "Run async_workflow_processor.py --loop as a background process, or enable ERRORSWEEP_ASYNC_PROCESS_ON_ACCEPT for small controlled deployments.",
        )
        supervisor_file = Path("worker_supervisor.py")
        supervisor_enabled = _env_bool("ERRORSWEEP_WORKER_SUPERVISOR_ENABLED")
        add_result(
            results,
            "Workers",
            "Worker supervisor",
            "Pass" if supervisor_file.exists() else "Blocker",
            "available" if supervisor_file.exists() else "missing",
            "Deploy worker_supervisor.py or use your platform process manager to run async, email, backup, and webhook workers.",
        )
        add_result(
            results,
            "Workers",
            "Worker supervisor enabled",
            "Pass" if supervisor_enabled else "Warn",
            "enabled" if supervisor_enabled else "not enabled",
            "Set ERRORSWEEP_WORKER_SUPERVISOR_ENABLED=true when worker_supervisor.py is the managed background process.",
        )
        if probe_endpoints and async_worker_url:
            health_url = async_worker_url.rstrip("/")
            if health_url.endswith("/tasks"):
                health_url = health_url[:-6]
            probe = public_probe(f"{health_url}/health", probe_timeout)
            add_result(results, "Async", "Async receiver health probe", "Pass" if probe["status"] == "ok" else "Warn", probe["detail"], "Check async_task_worker.py deployment health.")
    except Exception as exc:
        add_result(results, "Async", "External QA/Pro worker", "Warn", _safe_text(exc)[:220], "Check async worker settings.")

    openai_ready = _configured("OPENAI_API_KEY")
    add_result(
        results,
        "AI",
        "Production AI fallback route",
        "Pass" if openai_ready or managed_ai_ready() else "Blocker",
        "platform OpenAI" if openai_ready else "managed AI" if managed_ai_ready() else "missing",
        "Configure OPENAI_API_KEY or enable a live HTTPS managed OpenAI-compatible/vLLM endpoint.",
    )
    add_result(
        results,
        "MT",
        "No-key MT minimum route",
        "Pass" if any(mt_endpoint_ready(name) for name in ("OPUS_MT_ENDPOINT", "INDICTRANS2_ENDPOINT", "MADLAD_ENDPOINT")) else "Blocker",
        "configured" if any(mt_endpoint_ready(name) for name in ("OPUS_MT_ENDPOINT", "INDICTRANS2_ENDPOINT", "MADLAD_ENDPOINT")) else "missing",
        "Configure live HTTPS self-hosted MT endpoints before public no-key Pro translation.",
    )
    add_result(
        results,
        "MT",
        "OPUS-MT endpoint",
        "Pass" if mt_endpoint_ready("OPUS_MT_ENDPOINT") else "Blocker",
        _env("OPUS_MT_ENDPOINT") or "missing",
        "Configure OPUS_MT_ENDPOINT as the lightweight no-key MT fallback.",
    )
    add_result(
        results,
        "MT",
        "IndicTrans2 endpoint",
        "Pass" if mt_endpoint_ready("INDICTRANS2_ENDPOINT") else "Blocker",
        _env("INDICTRANS2_ENDPOINT") or "missing",
        "Configure INDICTRANS2_ENDPOINT for Indian-language no-key translation.",
    )
    add_result(
        results,
        "MT",
        "MADLAD-400 endpoint",
        "Pass" if mt_endpoint_ready("MADLAD_ENDPOINT") else "Warn",
        _env("MADLAD_ENDPOINT") or "missing",
        "Configure MADLAD_ENDPOINT after production GPU capacity is approved.",
    )

    provider = _env("ERRORSWEEP_BILLING_PROVIDER").lower()
    webhook_url = _env("ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL")
    add_result(
        results,
        "Billing",
        "Billing provider credentials",
        "Pass" if provider in {"stripe", "razorpay"} and billing_provider_ready(provider) else "Blocker",
        provider or "missing",
        "Configure Stripe or Razorpay keys before accepting paid plans.",
    )
    add_result(
        results,
        "Billing",
        "Provider plan IDs",
        "Pass" if billing_plan_ids_ready(provider) else "Warn",
        "plan IDs configured" if billing_plan_ids_ready(provider) else "plan IDs missing",
        "Configure Pro/Agency plan or price IDs for live subscription checkout.",
    )
    add_result(
        results,
        "Billing",
        "Webhook receiver URL",
        "Pass" if _https_url(webhook_url) else "Blocker",
        webhook_url or "missing",
        "Deploy billing_webhook_receiver.py behind HTTPS and set ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL.",
    )
    add_result(
        results,
        "Billing",
        "Webhook signature secret",
        "Pass" if _configured("STRIPE_WEBHOOK_SECRET", "RAZORPAY_WEBHOOK_SECRET", "ERRORSWEEP_BILLING_WEBHOOK_SECRET") else "Blocker",
        "configured" if _configured("STRIPE_WEBHOOK_SECRET", "RAZORPAY_WEBHOOK_SECRET", "ERRORSWEEP_BILLING_WEBHOOK_SECRET") else "missing",
        "Configure provider webhook secret before applying live billing events.",
    )
    if probe_endpoints and webhook_url:
        probe = public_probe(billing_health_url(webhook_url), probe_timeout)
        add_result(results, "Billing", "Webhook receiver health probe", "Pass" if probe["status"] == "ok" else "Warn", probe["detail"], "Check billing receiver deployment health.")

    email_provider = _env("ERRORSWEEP_EMAIL_PROVIDER").lower()
    email_from = _env("ERRORSWEEP_EMAIL_FROM") or _env("SENDGRID_FROM_EMAIL") or _env("RESEND_FROM_EMAIL")
    add_result(
        results,
        "Email",
        "Transactional email provider",
        "Pass" if email_provider in {"resend", "sendgrid", "smtp"} and email_provider_ready(email_provider) else "Blocker",
        email_provider or "missing",
        "Configure Resend, SendGrid, or SMTP credentials.",
    )
    add_result(
        results,
        "Email",
        "Verified sender",
        "Pass" if email_from and "errorsweep.local" not in email_from else "Blocker",
        "configured" if email_from else "missing",
        "Use a verified production sender domain.",
    )
    add_result(
        results,
        "Email",
        "Dispatch worker enabled",
        "Pass" if _env_bool("ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED") else "Blocker",
        "enabled" if _env_bool("ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED") else "not enabled",
        "Schedule email_dispatch_worker.py so queued notifications send automatically.",
    )
    try:
        dry_email = dry_run_email_dispatch(limit=5, dry_run=True)
        add_result(
            results,
            "Email",
            "Dispatch worker dry run",
            "Pass" if not dry_email.get("failed") else "Warn",
            json.dumps(dry_email, sort_keys=True),
            "Review queued notification records if dry-run failures appear.",
        )
    except Exception as exc:
        add_result(results, "Email", "Dispatch worker dry run", "Warn", _safe_text(exc)[:220], "Check email worker dependencies and persistence access.")

    add_result(
        results,
        "Backup",
        "Backup provider",
        "Pass" if _configured("ERRORSWEEP_BACKUP_PROVIDER") else "Warn",
        _env("ERRORSWEEP_BACKUP_PROVIDER") or "manual only",
        "Configure a scheduled database/storage backup provider.",
    )
    add_result(
        results,
        "Backup",
        "Backup worker enabled",
        "Pass" if _env_bool("ERRORSWEEP_BACKUP_WORKER_ENABLED") else "Blocker",
        "enabled" if _env_bool("ERRORSWEEP_BACKUP_WORKER_ENABLED") else "not enabled",
        "Schedule operational_backup_worker.py for redacted SaaS snapshots.",
    )
    try:
        dry_backup = run_backup(configured_collections(), limit=5, retention_days=30, dry_run=True)
        add_result(
            results,
            "Backup",
            "Backup worker dry run",
            "Pass" if not dry_backup.get("fetch_errors") else "Warn",
            json.dumps({k: v for k, v in dry_backup.items() if k != "fetch_errors"}, sort_keys=True),
            "Review persistence access if backup dry-run errors appear.",
        )
    except Exception as exc:
        add_result(results, "Backup", "Backup worker dry run", "Warn", _safe_text(exc)[:220], "Check backup worker dependencies and persistence access.")

    add_result(
        results,
        "Legal",
        "Legal review flag",
        "Pass" if _env_bool("ERRORSWEEP_LEGAL_REVIEWED") else "Blocker",
        "reviewed" if _env_bool("ERRORSWEEP_LEGAL_REVIEWED") else "draft",
        "Set ERRORSWEEP_LEGAL_REVIEWED=true only after approved Terms, Privacy, DPA, and Cookie Notice are live.",
    )
    add_result(
        results,
        "Edge",
        "CDN/WAF provider",
        "Pass" if _configured("ERRORSWEEP_WAF_PROVIDER") else "Blocker",
        _env("ERRORSWEEP_WAF_PROVIDER") or "missing",
        "Deploy behind HTTPS CDN/WAF with rate limits.",
    )

    sso_enabled = _env_bool("ERRORSWEEP_ENTERPRISE_SSO_ENABLED")
    add_result(
        results,
        "SSO",
        "Enterprise SSO handoff",
        "Pass" if not sso_enabled or _configured("ERRORSWEEP_SSO_HANDOFF_SECRET") else "Warn",
        "enabled" if sso_enabled else "disabled",
        "If enterprise SSO is enabled, configure ERRORSWEEP_SSO_HANDOFF_SECRET and provider metadata.",
    )
    return results


def summarize(results: List[Dict[str, str]]) -> Dict[str, Any]:
    counts = {"Pass": 0, "Warn": 0, "Blocker": 0}
    for row in results:
        counts[row["Status"]] = counts.get(row["Status"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "Blocker" if counts.get("Blocker") else "Warn" if counts.get("Warn") else "Pass",
        "counts": counts,
        "checks": len(results),
    }


def markdown_report(summary: Dict[str, Any], results: List[Dict[str, str]]) -> str:
    lines = [
        "# ErrorSweep Production Smoke Test",
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
        safe = {key: _safe_text(value).replace("|", "\\|").replace("\n", " ") for key, value in row.items()}
        lines.append(f"| {safe['Area']} | {safe['Check']} | {safe['Status']} | {safe['Evidence']} | {safe['Action']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ErrorSweep production smoke checks.")
    parser.add_argument("--markdown", action="store_true", help="Print a Markdown report instead of JSON.")
    parser.add_argument("--probe-endpoints", action="store_true", help="Probe public app and webhook health URLs.")
    parser.add_argument("--probe-timeout", type=int, default=10)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    logging.basicConfig(level=_env("ERRORSWEEP_SMOKE_TEST_LOG_LEVEL", "WARNING").upper(), format="%(asctime)s %(levelname)s %(message)s")
    results = sorted(collect_results(probe_endpoints=args.probe_endpoints, probe_timeout=args.probe_timeout), key=lambda row: (_status_rank(row["Status"]), row["Area"], row["Check"]))
    summary = summarize(results)
    payload = {"summary": summary, "results": results}
    if args.markdown:
        print(markdown_report(summary, results))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.fail_on_warn and (summary["counts"].get("Warn") or summary["counts"].get("Blocker")):
        return 1
    if args.strict and summary["counts"].get("Blocker"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
