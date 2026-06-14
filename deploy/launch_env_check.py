"""Validate ErrorSweep production environment files without exposing secrets.

This script is intentionally standalone. It does not import app.py and it does
not contact providers. Use it before the runtime smoke test to catch missing
or placeholder production settings in deploy/.env.production.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / "deploy" / ".env.production"
DEFAULT_SESSION_SECRET = "errorsweep-dev-session-secret-change-me"

SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|HASH|KEY|CLIENT_SECRET|SERVICE_ROLE|USERNAME|WORKSPACE|ORG)", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PBKDF2_RE = re.compile(r"^pbkdf2_sha256\$(\d+)\$([^$]{16,})\$([A-Za-z0-9_-]{32,})$")
PLACEHOLDER_MARKERS = (
    "replace-with",
    "your-domain.com",
    "yourdomain.com",
    "your-project",
    "example.com",
    "customer.com",
    "changeme",
    "change-me",
    "todo",
    "placeholder",
    "errorsweep.local",
    "demo workspace",
)


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def strip_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].strip()
    return value


def parse_env_file(path: Path) -> Tuple[Dict[str, str], List[str]]:
    env: Dict[str, str] = {}
    duplicates: List[str] = []
    if not path.exists():
        return env, duplicates
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("export "):
            text = text[7:].strip()
        if "=" not in text:
            continue
        key, raw_value = text.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if key in env:
            duplicates.append(key)
        env[key] = strip_value(raw_value)
    return env, duplicates


def add_os_env(env: Dict[str, str]) -> Dict[str, str]:
    merged = dict(env)
    for key, value in os.environ.items():
        if key not in merged and value not in (None, ""):
            merged[key] = str(value)
    return merged


def value_for(env: Dict[str, str], names: Sequence[str]) -> str:
    for name in names:
        value = safe_text(env.get(name))
        if value:
            return value
    return ""


def key_present(env: Dict[str, str], names: Sequence[str]) -> bool:
    return any(name in env and safe_text(env.get(name)) != "" for name in names)


def is_placeholder(value: str) -> bool:
    lowered = safe_text(value).lower()
    if not lowered:
        return True
    if lowered == DEFAULT_SESSION_SECRET:
        return True
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def configured(env: Dict[str, str], names: Sequence[str], min_length: int = 1) -> bool:
    value = value_for(env, names)
    return bool(value) and not is_placeholder(value) and len(value) >= min_length


def pbkdf2_hash_ready(value: str) -> bool:
    match = PBKDF2_RE.match(safe_text(value))
    return bool(match) and int(match.group(1)) >= 260_000


def email_ready(value: str) -> bool:
    text = safe_text(value)
    return bool(text) and not is_placeholder(text) and bool(EMAIL_RE.match(text))


def env_bool(env: Dict[str, str], name: str, default: bool = False) -> bool:
    value = safe_text(env.get(name))
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def https_url(value: str) -> bool:
    if is_placeholder(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def nonsecret_evidence(key: str, value: str) -> str:
    if not safe_text(value):
        return "missing"
    if is_placeholder(value):
        return "placeholder"
    if SENSITIVE_KEY_RE.search(key):
        return "configured"
    return value


def bool_evidence(env: Dict[str, str], name: str) -> str:
    value = safe_text(env.get(name))
    if not value:
        return "missing"
    return "enabled" if env_bool(env, name) else "disabled"


def add(results: List[Dict[str, str]], area: str, check: str, status: str, evidence: str, action: str) -> None:
    results.append({
        "Area": area,
        "Check": check,
        "Status": status,
        "Evidence": evidence,
        "Action": action,
    })


def require_value(
    results: List[Dict[str, str]],
    env: Dict[str, str],
    area: str,
    check: str,
    names: Sequence[str],
    action: str,
    *,
    status_when_missing: str = "Blocker",
    min_length: int = 1,
) -> None:
    value = value_for(env, names)
    status = "Pass" if configured(env, names, min_length=min_length) else status_when_missing
    add(results, area, check, status, nonsecret_evidence(names[0], value), action)


def require_https(
    results: List[Dict[str, str]],
    env: Dict[str, str],
    area: str,
    check: str,
    name: str,
    action: str,
    *,
    status_when_missing: str = "Blocker",
) -> None:
    value = safe_text(env.get(name))
    add(results, area, check, "Pass" if https_url(value) else status_when_missing, nonsecret_evidence(name, value), action)


def require_flag(
    results: List[Dict[str, str]],
    env: Dict[str, str],
    area: str,
    check: str,
    name: str,
    action: str,
    *,
    status_when_false: str = "Blocker",
) -> None:
    add(results, area, check, "Pass" if env_bool(env, name) else status_when_false, bool_evidence(env, name), action)


def env_assignment_re(key: str) -> re.Pattern[str]:
    return re.compile(rf"^(\s*(?:export\s+)?{re.escape(key)}\s*=\s*)(.*?)(\s*)$")


def format_env_value(value: str) -> str:
    text = safe_text(value)
    if re.search(r"\s|#|'|\"", text):
        return json.dumps(text)
    return text


def write_env_updates(path: Path, updates: Dict[str, str]) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist")
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    remaining = dict(updates)
    new_lines: List[str] = []
    for line in lines:
        replacement = line
        for key in list(remaining):
            match = env_assignment_re(key).match(line)
            if match:
                replacement = f"{match.group(1)}{format_env_value(remaining.pop(key))}{match.group(3)}"
                break
        new_lines.append(replacement)
    if remaining:
        new_lines.extend(["", "# Added by deploy/launch_env_check.py billing setup helper"])
        for key, value in remaining.items():
            new_lines.append(f"{key}={format_env_value(value)}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def read_required_secret_env(name: str, label: str, *, min_length: int = 8) -> str:
    env_name = safe_text(name)
    if not env_name:
        raise ValueError(f"Set --{label}.")
    value = safe_text(os.environ.get(env_name, ""))
    if not value:
        raise ValueError(f"{env_name} is not set or is empty.")
    if is_placeholder(value) or len(value) < min_length:
        raise ValueError(f"{env_name} must be at least {min_length} non-placeholder characters.")
    return value


def check_core(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    mode = safe_text(env.get("ERRORSWEEP_ENV")).lower()
    add(results, "Core", "Production mode", "Pass" if mode == "production" else "Blocker", mode or "missing", "Set ERRORSWEEP_ENV=production.")
    require_flag(results, env, "Core", "Public launch preflight lock", "ERRORSWEEP_ENFORCE_PUBLIC_LAUNCH_PREFLIGHT", "Keep ERRORSWEEP_ENFORCE_PUBLIC_LAUNCH_PREFLIGHT=true until all production blockers are cleared.")
    require_https(results, env, "Core", "Public app URL", "ERRORSWEEP_PUBLIC_BASE_URL", "Set ERRORSWEEP_PUBLIC_BASE_URL to the live HTTPS app URL.")
    require_value(results, env, "Core", "Session secret", ["ERRORSWEEP_SESSION_SECRET"], "Use a long random session secret.", min_length=32)


def check_auth(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    owner_email = value_for(env, ["ERRORSWEEP_OWNER_USERNAME"])
    owner_hash = value_for(env, ["ERRORSWEEP_OWNER_PASSWORD_HASH"])
    user_email = value_for(env, ["ERRORSWEEP_USER_USERNAME"])
    user_hash = value_for(env, ["ERRORSWEEP_USER_PASSWORD_HASH"])
    workspace = value_for(env, ["ERRORSWEEP_ORG_NAME"])

    add(
        results,
        "Auth",
        "Owner bootstrap email",
        "Pass" if email_ready(owner_email) else "Blocker",
        nonsecret_evidence("ERRORSWEEP_OWNER_USERNAME", owner_email),
        "Set ERRORSWEEP_OWNER_USERNAME to the production platform owner email.",
    )
    add(
        results,
        "Auth",
        "Owner bootstrap password hash",
        "Pass" if pbkdf2_hash_ready(owner_hash) else "Blocker",
        "configured" if pbkdf2_hash_ready(owner_hash) else nonsecret_evidence("ERRORSWEEP_OWNER_PASSWORD_HASH", owner_hash),
        "Set ERRORSWEEP_OWNER_PASSWORD_HASH to a PBKDF2 hash from deploy/auth_session_check.py --generate-password-hash or --password-env.",
    )
    add(
        results,
        "Auth",
        "Workspace bootstrap email",
        "Pass" if email_ready(user_email) else "Blocker",
        nonsecret_evidence("ERRORSWEEP_USER_USERNAME", user_email),
        "Set ERRORSWEEP_USER_USERNAME to the initial production workspace user email.",
    )
    add(
        results,
        "Auth",
        "Workspace bootstrap password hash",
        "Pass" if pbkdf2_hash_ready(user_hash) else "Blocker",
        "configured" if pbkdf2_hash_ready(user_hash) else nonsecret_evidence("ERRORSWEEP_USER_PASSWORD_HASH", user_hash),
        "Set ERRORSWEEP_USER_PASSWORD_HASH to a PBKDF2 hash from deploy/auth_session_check.py --generate-password-hash or --password-env.",
    )
    add(
        results,
        "Auth",
        "Workspace bootstrap name",
        "Pass" if configured(env, ["ERRORSWEEP_ORG_NAME"]) else "Blocker",
        nonsecret_evidence("ERRORSWEEP_ORG_NAME", workspace),
        "Set ERRORSWEEP_ORG_NAME to the initial production workspace name.",
    )
    role = value_for(env, ["ERRORSWEEP_DEFAULT_USER_ROLE"]) or "Workspace Owner"
    allowed_roles = {"Workspace Owner", "Company Admin", "Workspace Admin", "Project Manager", "Team Lead", "Translator", "Reviewer", "Freelancer", "Client", "Client Viewer", "Billing Admin", "Talent Manager", "Individual Owner", "Individual User", "User"}
    add(
        results,
        "Auth",
        "Workspace bootstrap role",
        "Pass" if role in allowed_roles else "Warn",
        role or "missing",
        "Use a known workspace role, usually Workspace Owner, for the initial workspace user.",
    )
    plaintext_passwords = [key for key in ("ERRORSWEEP_OWNER_PASSWORD", "ERRORSWEEP_USER_PASSWORD") if safe_text(env.get(key))]
    add(
        results,
        "Auth",
        "Plaintext bootstrap passwords",
        "Pass" if not plaintext_passwords else "Blocker",
        "not set" if not plaintext_passwords else ", ".join(plaintext_passwords),
        "Remove plaintext bootstrap password env vars; production login accepts only *_PASSWORD_HASH.",
    )


def check_persistence(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    require_https(results, env, "Persistence", "Supabase URL", "SUPABASE_URL", "Set SUPABASE_URL to the production Supabase project URL; use deploy/supabase_schema_check.py --write-supabase-env for repeatable setup.")
    require_value(results, env, "Persistence", "Supabase anon key", ["SUPABASE_ANON_KEY"], "Set SUPABASE_ANON_KEY in the production secret store; use deploy/supabase_schema_check.py --write-supabase-env.", min_length=24)
    require_value(results, env, "Persistence", "Supabase service role key", ["SUPABASE_SERVICE_ROLE_KEY"], "Set SUPABASE_SERVICE_ROLE_KEY from the production Supabase project; use deploy/supabase_schema_check.py --write-supabase-env.", min_length=24)


def check_storage(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    provider = safe_text(env.get("ERRORSWEEP_OBJECT_STORAGE_PROVIDER")).lower()
    add(
        results,
        "Storage",
        "Object storage provider",
        "Pass" if provider in {"supabase", "s3", "gcs"} else "Blocker",
        provider or "missing",
        "Set ERRORSWEEP_OBJECT_STORAGE_PROVIDER to supabase, s3, or gcs.",
    )
    if provider == "supabase":
        require_value(results, env, "Storage", "Supabase storage bucket", ["SUPABASE_STORAGE_BUCKET"], "Create and set the production Supabase storage bucket.")
    elif provider == "s3":
        require_value(results, env, "Storage", "S3 bucket", ["S3_BUCKET"], "Set S3_BUCKET for production file storage.")
        require_value(results, env, "Storage", "AWS region", ["AWS_REGION"], "Set AWS_REGION for S3 storage.", status_when_missing="Warn")
        if not key_present(env, ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_ROLE_ARN"]):
            add(results, "Storage", "S3 credentials or role", "Warn", "not explicit", "Use an instance role/web identity or inject AWS credentials in the runtime environment.")
    elif provider == "gcs":
        require_value(results, env, "Storage", "GCS bucket", ["GCS_BUCKET"], "Set GCS_BUCKET for production file storage.")
        if not key_present(env, ["GOOGLE_APPLICATION_CREDENTIALS", "GCP_SERVICE_ACCOUNT_JSON"]):
            add(results, "Storage", "GCS credentials", "Warn", "not explicit", "Use workload identity or inject GCS service-account credentials in the runtime environment.")


def check_async(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    require_value(results, env, "Async", "Worker receiver URL", ["ERRORSWEEP_ASYNC_WORKER_URL"], "Set ERRORSWEEP_ASYNC_WORKER_URL to the receiver /tasks endpoint.")
    require_value(results, env, "Async", "Worker bearer token", ["ERRORSWEEP_ASYNC_WORKER_TOKEN"], "Set a shared bearer token for async worker requests.", min_length=16)
    require_flag(results, env, "Async", "Async receiver service enabled", "ERRORSWEEP_ASYNC_WORKER_SERVICE_ENABLED", "Set ERRORSWEEP_ASYNC_WORKER_SERVICE_ENABLED=true when the receiver is deployed.", status_when_false="Warn")
    require_flag(results, env, "Async", "Async processor enabled", "ERRORSWEEP_ASYNC_PROCESSOR_ENABLED", "Run async_workflow_processor.py as a managed background process.", status_when_false="Warn")


def check_workers(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    require_flag(results, env, "Workers", "Worker supervisor enabled", "ERRORSWEEP_WORKER_SUPERVISOR_ENABLED", "Set ERRORSWEEP_WORKER_SUPERVISOR_ENABLED=true or document an equivalent platform process manager.", status_when_false="Warn")
    require_flag(results, env, "Workers", "Supervisor async worker", "ERRORSWEEP_SUPERVISOR_ENABLE_ASYNC_PROCESSOR", "Enable the async processor in the supervisor or deploy it separately.", status_when_false="Warn")
    require_flag(results, env, "Workers", "Supervisor email worker", "ERRORSWEEP_SUPERVISOR_ENABLE_EMAIL_WORKER", "Enable the email dispatch worker in the supervisor or deploy it separately.", status_when_false="Warn")
    require_flag(results, env, "Workers", "Supervisor backup worker", "ERRORSWEEP_SUPERVISOR_ENABLE_BACKUP_WORKER", "Enable the backup worker in the supervisor or deploy it separately.", status_when_false="Warn")


def check_ai_mt(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    openai_ready = configured(env, ["OPENAI_API_KEY"], min_length=12)
    managed_ready = env_bool(env, "ERRORSWEEP_MANAGED_AI_ENABLED") and https_url(safe_text(env.get("ERRORSWEEP_MANAGED_AI_BASE_URL")))
    add(
        results,
        "AI",
        "Production AI fallback route",
        "Pass" if openai_ready or managed_ready else "Blocker",
        "platform OpenAI" if openai_ready else "managed AI" if managed_ready else "missing",
        "Configure OPENAI_API_KEY or enable ERRORSWEEP_MANAGED_AI_ENABLED with a live HTTPS OpenAI-compatible/vLLM endpoint; use deploy/ai_fallback_check.py --write-ai-env for repeatable setup.",
    )
    add(
        results,
        "AI",
        "OpenAI default model",
        "Pass" if configured(env, ["ERRORSWEEP_OPENAI_DEFAULT_MODEL", "OPENAI_MODEL"]) else "Warn",
        nonsecret_evidence("ERRORSWEEP_OPENAI_DEFAULT_MODEL", value_for(env, ["ERRORSWEEP_OPENAI_DEFAULT_MODEL", "OPENAI_MODEL"])),
        "Set ERRORSWEEP_OPENAI_DEFAULT_MODEL for predictable platform fallback behavior.",
    )
    add(
        results,
        "AI",
        "Gemini API key",
        "Pass" if configured(env, ["GEMINI_API_KEY"], min_length=12) else "Warn",
        nonsecret_evidence("GEMINI_API_KEY", value_for(env, ["GEMINI_API_KEY"])),
        "Add GEMINI_API_KEY if Gemini OpenAI-compatible routing will be offered as a platform-managed option.",
    )
    if env_bool(env, "ERRORSWEEP_MANAGED_AI_ENABLED"):
        require_https(results, env, "AI", "Managed AI base URL", "ERRORSWEEP_MANAGED_AI_BASE_URL", "Set a live HTTPS OpenAI-compatible/vLLM base URL when managed AI is enabled.")
        require_value(results, env, "AI", "Managed AI API key", ["ERRORSWEEP_MANAGED_AI_API_KEY"], "Set the managed AI bearer/API token.", status_when_missing="Warn")

    opus_ready = https_url(safe_text(env.get("OPUS_MT_ENDPOINT")))
    indic_ready = https_url(safe_text(env.get("INDICTRANS2_ENDPOINT")))
    madlad_ready = https_url(safe_text(env.get("MADLAD_ENDPOINT")))
    add(
        results,
        "MT",
        "No-key MT minimum route",
        "Pass" if opus_ready or indic_ready or madlad_ready else "Blocker",
        "configured" if opus_ready or indic_ready or madlad_ready else "missing/placeholder",
        "Configure at least one live HTTPS self-hosted MT endpoint so no-key Pro translation has a route.",
    )
    require_https(results, env, "MT", "OPUS-MT endpoint", "OPUS_MT_ENDPOINT", "Configure OPUS_MT_ENDPOINT as the lightweight no-key MT fallback.")
    require_https(results, env, "MT", "IndicTrans2 endpoint", "INDICTRANS2_ENDPOINT", "Configure INDICTRANS2_ENDPOINT for Indian-language no-key translation.")
    require_https(results, env, "MT", "MADLAD-400 endpoint", "MADLAD_ENDPOINT", "Configure MADLAD_ENDPOINT when production GPU capacity is approved.", status_when_missing="Warn")
    require_value(results, env, "MT", "Self-hosted MT timeout", ["SELF_HOSTED_MT_TIMEOUT"], "Set SELF_HOSTED_MT_TIMEOUT for long batch translation requests.", status_when_missing="Warn")


def check_billing(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    provider = safe_text(env.get("ERRORSWEEP_BILLING_PROVIDER")).lower()
    add(
        results,
        "Billing",
        "Billing provider",
        "Pass" if provider in {"stripe", "razorpay"} else "Blocker",
        provider or "missing",
        "Set ERRORSWEEP_BILLING_PROVIDER to stripe or razorpay; use --write-billing-env for repeatable setup.",
    )
    if provider == "stripe":
        require_value(results, env, "Billing", "Stripe secret key", ["STRIPE_SECRET_KEY", "ERRORSWEEP_STRIPE_SECRET_KEY"], "Set the live Stripe secret key with --write-billing-env.", min_length=12)
        require_value(results, env, "Billing", "Stripe webhook secret", ["STRIPE_WEBHOOK_SECRET", "ERRORSWEEP_BILLING_WEBHOOK_SECRET"], "Set the Stripe webhook signing secret with --write-billing-env.", min_length=12)
        require_value(results, env, "Billing", "Stripe Pro price ID", ["STRIPE_PRICE_ID_PRO"], "Set the live Pro price ID with --write-billing-env --pro-plan-id.", status_when_missing="Warn")
        require_value(results, env, "Billing", "Stripe Agency price ID", ["STRIPE_PRICE_ID_AGENCY"], "Set the live Agency price ID with --write-billing-env --agency-plan-id.", status_when_missing="Warn")
    elif provider == "razorpay":
        require_value(results, env, "Billing", "Razorpay key ID", ["RAZORPAY_KEY_ID"], "Set the live Razorpay key ID with --write-billing-env.", min_length=8)
        require_value(results, env, "Billing", "Razorpay key secret", ["RAZORPAY_KEY_SECRET"], "Set the live Razorpay key secret with --write-billing-env.", min_length=8)
        require_value(results, env, "Billing", "Razorpay webhook secret", ["RAZORPAY_WEBHOOK_SECRET", "ERRORSWEEP_BILLING_WEBHOOK_SECRET"], "Set the Razorpay webhook signing secret with --write-billing-env.", min_length=8)
        require_value(results, env, "Billing", "Razorpay Pro plan ID", ["RAZORPAY_PLAN_ID_PRO"], "Set the live Pro plan ID with --write-billing-env --pro-plan-id.", status_when_missing="Warn")
        require_value(results, env, "Billing", "Razorpay Agency plan ID", ["RAZORPAY_PLAN_ID_AGENCY"], "Set the live Agency plan ID with --write-billing-env --agency-plan-id.", status_when_missing="Warn")
    require_https(results, env, "Billing", "Webhook receiver URL", "ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL", "Expose billing_webhook_receiver.py behind HTTPS and set the public URL with --write-billing-env.")
    add(
        results,
        "Billing",
        "Webhook update mode",
        "Pass" if env_bool(env, "ERRORSWEEP_WEBHOOK_APPLY_UPDATES") else "Warn",
        bool_evidence(env, "ERRORSWEEP_WEBHOOK_APPLY_UPDATES"),
        "Keep disabled for early staging, then enable after provider signature tests pass.",
    )


def check_email(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    provider = safe_text(env.get("ERRORSWEEP_EMAIL_PROVIDER")).lower()
    add(
        results,
        "Email",
        "Email provider",
        "Pass" if provider in {"resend", "sendgrid", "smtp"} else "Blocker",
        provider or "missing",
        "Set ERRORSWEEP_EMAIL_PROVIDER to resend, sendgrid, or smtp.",
    )
    if provider == "resend":
        require_value(results, env, "Email", "Resend API key", ["RESEND_API_KEY", "ERRORSWEEP_RESEND_API_KEY"], "Set the production Resend API key.", min_length=12)
    elif provider == "sendgrid":
        require_value(results, env, "Email", "SendGrid API key", ["SENDGRID_API_KEY", "ERRORSWEEP_SENDGRID_API_KEY"], "Set the production SendGrid API key.", min_length=12)
    elif provider == "smtp":
        require_value(results, env, "Email", "SMTP host", ["SMTP_HOST", "ERRORSWEEP_SMTP_HOST"], "Set the production SMTP host.")
        require_value(results, env, "Email", "SMTP username", ["SMTP_USER", "ERRORSWEEP_SMTP_USER"], "Set the production SMTP username.", status_when_missing="Warn")
        require_value(results, env, "Email", "SMTP password", ["SMTP_PASSWORD", "ERRORSWEEP_SMTP_PASSWORD"], "Set the production SMTP password.", min_length=8)
    require_value(results, env, "Email", "Verified sender", ["ERRORSWEEP_EMAIL_FROM", "SENDGRID_FROM_EMAIL", "RESEND_FROM_EMAIL"], "Set a verified production sender address.")
    require_flag(results, env, "Email", "Dispatch worker enabled", "ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED", "Set ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED=true.")


def check_legal_edge_backup(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    require_flag(results, env, "Legal", "Legal review complete", "ERRORSWEEP_LEGAL_REVIEWED", "Set true only after approved Terms, Privacy, DPA, and Cookie Notice are live.")
    require_value(results, env, "Edge", "CDN/WAF provider", ["ERRORSWEEP_WAF_PROVIDER"], "Set the production CDN/WAF provider name.")
    require_value(results, env, "Backup", "Backup provider", ["ERRORSWEEP_BACKUP_PROVIDER"], "Set the scheduled database/storage backup provider.", status_when_missing="Warn")
    require_flag(results, env, "Backup", "Backup worker enabled", "ERRORSWEEP_BACKUP_WORKER_ENABLED", "Set ERRORSWEEP_BACKUP_WORKER_ENABLED=true after backup provider setup.")
    require_value(results, env, "Backup", "Backup retention days", ["ERRORSWEEP_BACKUP_RETENTION_DAYS"], "Set backup retention days.", status_when_missing="Warn")


def check_sso(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    if not env_bool(env, "ERRORSWEEP_ENTERPRISE_SSO_ENABLED"):
        add(results, "SSO", "Enterprise SSO", "Pass", "disabled", "No enterprise SSO env is required unless enterprise SSO is enabled.")
        return
    require_value(results, env, "SSO", "SSO handoff secret", ["ERRORSWEEP_SSO_HANDOFF_SECRET"], "Set a long SSO handoff signing secret.", min_length=24)
    if not key_present(env, ["ERRORSWEEP_SSO_ISSUER_URL", "ERRORSWEEP_SSO_METADATA_URL", "ERRORSWEEP_SSO_CLIENT_ID", "ERRORSWEEP_SSO_ENTITY_ID"]):
        add(results, "SSO", "SSO provider metadata", "Warn", "missing", "Configure OIDC/SAML provider metadata for enabled enterprise SSO.")


def collect_results(env: Dict[str, str], duplicates: Sequence[str], env_path: Path, include_os_env: bool) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    add(
        results,
        "Config",
        "Environment file",
        "Pass" if env_path.exists() else "Blocker",
        str(env_path.relative_to(ROOT)) if env_path.exists() and env_path.is_relative_to(ROOT) else str(env_path),
        "Create deploy/.env.production from deploy/.env.production.example and fill real production values.",
    )
    add(
        results,
        "Config",
        "Duplicate keys",
        "Pass" if not duplicates else "Warn",
        "none" if not duplicates else ", ".join(sorted(set(duplicates))),
        "Remove duplicate env keys so the last parsed value does not hide earlier values.",
    )
    add(
        results,
        "Config",
        "OS environment merge",
        "Pass" if include_os_env else "Warn",
        "enabled" if include_os_env else "disabled",
        "Use --include-os-env if your host injects secrets outside deploy/.env.production.",
    )
    check_core(results, env)
    check_auth(results, env)
    check_persistence(results, env)
    check_storage(results, env)
    check_async(results, env)
    check_workers(results, env)
    check_ai_mt(results, env)
    check_billing(results, env)
    check_email(results, env)
    check_legal_edge_backup(results, env)
    check_sso(results, env)
    return results


def status_rank(status: str) -> int:
    return {"Pass": 0, "Warn": 1, "Blocker": 2}.get(status, 1)


def summarize(results: Sequence[Dict[str, str]]) -> Dict[str, Any]:
    counts = {"Pass": 0, "Warn": 0, "Blocker": 0}
    for row in results:
        counts[row["Status"]] = counts.get(row["Status"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "Blocker" if counts["Blocker"] else "Warn" if counts["Warn"] else "Pass",
        "checks": len(results),
        "counts": counts,
    }


def markdown_report(summary: Dict[str, Any], results: Sequence[Dict[str, str]]) -> str:
    lines = [
        "# ErrorSweep Launch Environment Check",
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


def optional_update(updates: Dict[str, str], key: str, value: str) -> None:
    text = safe_text(value)
    if text:
        updates[key] = text


def write_billing_env(args: argparse.Namespace) -> int:
    env_path = Path(args.env_file)
    if not env_path.is_absolute():
        env_path = ROOT / env_path
    provider = safe_text(args.billing_provider).lower()
    webhook_url = safe_text(args.billing_webhook_url)
    try:
        if provider not in {"razorpay", "stripe"}:
            raise ValueError("--billing-provider must be razorpay or stripe.")
        if not https_url(webhook_url):
            raise ValueError("--billing-webhook-url must be a public HTTPS webhook receiver URL.")

        updates: Dict[str, str] = {
            "ERRORSWEEP_BILLING_PROVIDER": provider,
            "ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL": webhook_url,
            "ERRORSWEEP_WEBHOOK_APPLY_UPDATES": "true" if args.enable_webhook_updates else "false",
            "ERRORSWEEP_BILLING_CREATE_PROVIDER_CHECKOUT": "true" if args.create_provider_checkout else "false",
        }

        if provider == "razorpay":
            key_id = read_required_secret_env(args.razorpay_key_id_env, "razorpay-key-id-env", min_length=8)
            key_secret = read_required_secret_env(args.razorpay_key_secret_env, "razorpay-key-secret-env", min_length=8)
            webhook_secret = read_required_secret_env(args.razorpay_webhook_secret_env, "razorpay-webhook-secret-env", min_length=8)
            updates.update(
                {
                    "RAZORPAY_KEY_ID": key_id,
                    "RAZORPAY_KEY_SECRET": key_secret,
                    "RAZORPAY_WEBHOOK_SECRET": webhook_secret,
                    "ERRORSWEEP_BILLING_WEBHOOK_SECRET": webhook_secret,
                }
            )
            optional_update(updates, "RAZORPAY_PLAN_ID_PRO", args.pro_plan_id)
            optional_update(updates, "RAZORPAY_PLAN_ID_AGENCY", args.agency_plan_id)
            optional_update(updates, "RAZORPAY_PLAN_ID_ENTERPRISE", args.enterprise_plan_id)
        else:
            secret_key = read_required_secret_env(args.stripe_secret_key_env, "stripe-secret-key-env", min_length=12)
            webhook_secret = read_required_secret_env(args.stripe_webhook_secret_env, "stripe-webhook-secret-env", min_length=12)
            updates.update(
                {
                    "STRIPE_SECRET_KEY": secret_key,
                    "STRIPE_WEBHOOK_SECRET": webhook_secret,
                    "ERRORSWEEP_BILLING_WEBHOOK_SECRET": webhook_secret,
                }
            )
            optional_update(updates, "STRIPE_PRICE_ID_PRO", args.pro_plan_id)
            optional_update(updates, "STRIPE_PRICE_ID_AGENCY", args.agency_plan_id)
            optional_update(updates, "STRIPE_PRICE_ID_ENTERPRISE", args.enterprise_plan_id)

        optional_update(updates, "ERRORSWEEP_MONTHLY_MANDATE_LINK_PRO", args.pro_mandate_link)
        optional_update(updates, "ERRORSWEEP_MONTHLY_MANDATE_LINK_AGENCY", args.agency_mandate_link)
        optional_update(updates, "ERRORSWEEP_MONTHLY_MANDATE_LINK_ENTERPRISE", args.enterprise_mandate_link)
        optional_update(updates, "ERRORSWEEP_TRIAL_MANDATE_LINK", args.trial_mandate_link)
        write_env_updates(env_path, updates)
    except Exception as exc:
        print(safe_text(exc), file=sys.stderr)
        return 1

    payload = {
        "env_file": str(env_path),
        "billing_provider": provider,
        "webhook_receiver_url": webhook_url,
        "webhook_updates_enabled": bool(args.enable_webhook_updates),
        "provider_checkout_enabled": bool(args.create_provider_checkout),
        "updated": sorted(updates.keys()),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Updated {env_path}")
        print(f"Billing provider: {provider}")
        print(f"Webhook receiver URL: {webhook_url}")
        print(f"Webhook apply updates: {'enabled' if args.enable_webhook_updates else 'disabled'}")
        print("Billing secrets were read from environment variables and were not printed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ErrorSweep production env configuration without printing secrets.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Path to the production env file to validate.")
    parser.add_argument("--include-os-env", action="store_true", help="Merge existing OS environment values for keys not present in the file.")
    parser.add_argument("--write-billing-env", action="store_true", help="Write billing provider credentials and webhook settings into the env file from environment variables.")
    parser.add_argument("--billing-provider", choices=["razorpay", "stripe"], default="razorpay", help="Billing provider to write with --write-billing-env.")
    parser.add_argument("--billing-webhook-url", default="", help="Public HTTPS billing webhook receiver URL.")
    parser.add_argument("--razorpay-key-id-env", default="", help="Environment variable containing RAZORPAY_KEY_ID.")
    parser.add_argument("--razorpay-key-secret-env", default="", help="Environment variable containing RAZORPAY_KEY_SECRET.")
    parser.add_argument("--razorpay-webhook-secret-env", default="", help="Environment variable containing RAZORPAY_WEBHOOK_SECRET.")
    parser.add_argument("--stripe-secret-key-env", default="", help="Environment variable containing STRIPE_SECRET_KEY.")
    parser.add_argument("--stripe-webhook-secret-env", default="", help="Environment variable containing STRIPE_WEBHOOK_SECRET.")
    parser.add_argument("--pro-plan-id", default="", help="Provider Pro plan/price ID.")
    parser.add_argument("--agency-plan-id", default="", help="Provider Agency plan/price ID.")
    parser.add_argument("--enterprise-plan-id", default="", help="Provider Enterprise plan/price ID.")
    parser.add_argument("--pro-mandate-link", default="", help="Hosted Pro monthly mandate/payment link fallback.")
    parser.add_argument("--agency-mandate-link", default="", help="Hosted Agency monthly mandate/payment link fallback.")
    parser.add_argument("--enterprise-mandate-link", default="", help="Hosted Enterprise monthly mandate/payment link fallback.")
    parser.add_argument("--trial-mandate-link", default="", help="Hosted trial mandate/payment authorization link fallback.")
    parser.add_argument("--enable-webhook-updates", action="store_true", help="Set ERRORSWEEP_WEBHOOK_APPLY_UPDATES=true after provider webhook verification.")
    parser.add_argument("--create-provider-checkout", action="store_true", help="Set ERRORSWEEP_BILLING_CREATE_PROVIDER_CHECKOUT=true after live provider checkout testing.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    if args.write_billing_env:
        return write_billing_env(args)

    env_path = Path(args.env_file)
    if not env_path.is_absolute():
        env_path = ROOT / env_path
    env, duplicates = parse_env_file(env_path)
    if args.include_os_env:
        env = add_os_env(env)
    results = sorted(collect_results(env, duplicates, env_path, include_os_env=args.include_os_env), key=lambda row: (status_rank(row["Status"]), row["Area"], row["Check"]))
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
