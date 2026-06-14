"""Validate CogniSweep production auth/session launch readiness.

Offline mode checks the app auth contract, deployment templates, persistence
schema, and release wiring without importing app.py or printing secrets. Use
--env-file to validate real production settings, --probe-public-url after the
app is deployed, and --generate-password-hash to create PBKDF2 bootstrap hashes.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
ENV_TEMPLATE_PATH = ROOT / "deploy" / ".env.production.example"
STREAMLIT_TEMPLATE_PATH = ROOT / ".streamlit" / "secrets.toml.example"
DEFAULT_ENV_PATH = ROOT / "deploy" / ".env.production"
DEFAULT_SESSION_SECRET = "errorsweep-dev-session-secret-change-me"
PASSWORD_HASH_ITERATIONS = 260_000

REQUIRED_FILES = [
    "app.py",
    "production_persistence.py",
    "production_smoke_test.py",
    "supabase_v42_release_schema.sql",
    "deploy/launch_env_check.py",
    "deploy/release_check.py",
]
REQUIRED_APP_TOKENS = [
    "DEFAULT_SESSION_SECRET",
    "ERRORSWEEP_SESSION_SECRET",
    "ERRORSWEEP_PUBLIC_BASE_URL",
    "ERRORSWEEP_OWNER_USERNAME",
    "ERRORSWEEP_OWNER_PASSWORD_HASH",
    "ERRORSWEEP_USER_USERNAME",
    "ERRORSWEEP_USER_PASSWORD_HASH",
    "ERRORSWEEP_ORG_NAME",
    "hash_password",
    "verify_password",
    "verify_login_password",
    "hmac.compare_digest",
    "sign_payload",
    "verify_payload",
    "auth_token_hash",
    "create_auth_token",
    "find_auth_token",
    "consume_auth_token",
    "queue_verification_email",
    "queue_password_reset_email",
    "SESSION_COOKIE_NAME",
    "SESSION_STORAGE_KEY",
]
REQUIRED_PERSISTENCE_TOKENS = [
    '"auth_tokens": "errorsweep_auth_tokens"',
    '"auth_tokens": {"id", "workspace", "user_email", "email", "token_hash"',
    'collection == "auth_tokens" and record.get("token_hash")',
]
REQUIRED_SCHEMA_TOKENS = [
    "create table if not exists public.errorsweep_auth_tokens",
    "token_hash text not null",
    "token_type text",
    "expires_at timestamptz",
    "alter table public.errorsweep_auth_tokens enable row level security",
]
REQUIRED_TEMPLATE_KEYS = [
    "ERRORSWEEP_ENV",
    "ERRORSWEEP_PUBLIC_BASE_URL",
    "ERRORSWEEP_SESSION_SECRET",
    "ERRORSWEEP_OWNER_USERNAME",
    "ERRORSWEEP_OWNER_PASSWORD_HASH",
    "ERRORSWEEP_USER_USERNAME",
    "ERRORSWEEP_USER_PASSWORD_HASH",
    "ERRORSWEEP_ORG_NAME",
    "ERRORSWEEP_DEFAULT_USER_ROLE",
]
LEGACY_PASSWORD_KEYS = [
    "ERRORSWEEP_OWNER_PASSWORD",
    "ERRORSWEEP_USER_PASSWORD",
]
REQUIRED_RELEASE_TOKENS = [
    "deploy/auth_session_check.py",
    "check_auth_session_contract",
]
REQUIRED_SMOKE_TOKENS = [
    "deploy/auth_session_check.py",
    "Owner bootstrap credentials",
    "Workspace bootstrap credentials",
]
PLACEHOLDER_MARKERS = (
    "replace-with",
    "your-domain.com",
    "yourdomain.com",
    "your-project",
    "example.com",
    "placeholder",
    "todo",
    "changeme",
    "change-me",
    "demo workspace",
    "errorsweep.local", "cognisweep.local",
)
SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|HASH|KEY|USERNAME|EMAIL|WORKSPACE|ORG)", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PBKDF2_RE = re.compile(r"^pbkdf2_sha256\$(\d+)\$([^$]{16,})\$([A-Za-z0-9_-]{32,})$")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
PRIVATE_HOST_HINTS = (".local", ".internal", ".lan", ".home")


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def add(results: List[Dict[str, str]], area: str, check: str, status: str, evidence: str, action: str) -> None:
    results.append(
        {
            "Area": area,
            "Check": check,
            "Status": status,
            "Evidence": evidence,
            "Action": action,
        }
    )


def status_rank(status: str) -> int:
    return {"Pass": 0, "Warn": 1, "Blocker": 2}.get(status, 1)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def missing_items(items: Iterable[str], text: str) -> List[str]:
    return [item for item in items if item not in text]


def strip_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].strip()
    return value


def parse_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
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
        if key:
            env[key] = strip_env_value(raw_value)
    return env


def is_placeholder(value: str) -> bool:
    lowered = safe_text(value).lower()
    if not lowered:
        return True
    if lowered == DEFAULT_SESSION_SECRET:
        return True
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def nonsecret_evidence(key: str, value: str) -> str:
    if not safe_text(value):
        return "missing"
    if is_placeholder(value):
        return "placeholder"
    if SENSITIVE_KEY_RE.search(key):
        return "configured"
    return value


def env_bool(env: Dict[str, str], name: str, default: bool = False) -> bool:
    value = safe_text(env.get(name))
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def host_is_public(hostname: str) -> bool:
    host = safe_text(hostname).lower()
    if not host or host in LOCAL_HOSTS or any(host.endswith(hint) for hint in PRIVATE_HOST_HINTS):
        return False
    if host.startswith("10.") or host.startswith("192.168.") or host == "169.254.169.254":
        return False
    if re.match(r"^172\.(1[6-9]|2\d|3[0-1])\.", host):
        return False
    return True


def public_https_url(value: str) -> bool:
    if is_placeholder(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and host_is_public(parsed.hostname or "")


def active_template_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def make_password_hash(password: str, iterations: int = PASSWORD_HASH_ITERATIONS) -> str:
    salt = b64url(os.urandom(16))
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${b64url(digest)}"


def generate_temporary_password() -> str:
    return secrets.token_urlsafe(24)


def env_assignment_re(key: str) -> re.Pattern[str]:
    return re.compile(rf"^(\s*(?:export\s+)?{re.escape(key)}\s*=\s*)(.*?)(\s*)$")


def format_env_value(value: str) -> str:
    text = safe_text(value)
    if not text or re.search(r"\s|#|'|\"", text):
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
        new_lines.extend(["", "# Added by deploy/auth_session_check.py bootstrap helper"])
        for key, value in remaining.items():
            new_lines.append(f"{key}={format_env_value(value)}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def pbkdf2_hash_detail(value: str) -> Tuple[bool, str]:
    text = safe_text(value)
    if not text:
        return False, "missing"
    if is_placeholder(text):
        return False, "placeholder"
    match = PBKDF2_RE.match(text)
    if not match:
        return False, "not pbkdf2_sha256"
    iterations = int(match.group(1))
    if iterations < PASSWORD_HASH_ITERATIONS:
        return False, f"weak iteration count ({iterations})"
    return True, "configured"


def validate_files(results: List[Dict[str, str]]) -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    add(
        results,
        "Auth",
        "Auth source/check files",
        "Pass" if not missing else "Blocker",
        "app + persistence + launch checks present" if not missing else ", ".join(missing),
        "Keep app auth code, persistence schema, env checks, smoke runner, and release checks in the branch.",
    )


def validate_contracts(results: List[Dict[str, str]]) -> None:
    app = read_text(ROOT / "app.py")
    persistence = read_text(ROOT / "production_persistence.py")
    schema = read_text(ROOT / "supabase_v42_release_schema.sql").lower()

    missing_app = missing_items(REQUIRED_APP_TOKENS, app)
    add(
        results,
        "Auth",
        "App auth/session contract",
        "Pass" if not missing_app else "Blocker",
        "session signing + PBKDF2 + bootstrap login + auth tokens present" if not missing_app else ", ".join(missing_app),
        "Keep production session signing, PBKDF2 verification, bootstrap credentials, and auth-token flows wired in app.py.",
    )

    missing_persistence = missing_items(REQUIRED_PERSISTENCE_TOKENS, persistence)
    add(
        results,
        "Auth",
        "Auth token persistence contract",
        "Pass" if not missing_persistence else "Blocker",
        "auth_tokens collection maps to token_hash storage" if not missing_persistence else ", ".join(missing_persistence),
        "Keep auth token persistence hash-only and allow-listed in production_persistence.py.",
    )

    missing_schema = [token for token in REQUIRED_SCHEMA_TOKENS if token not in schema]
    add(
        results,
        "Auth",
        "Auth token schema",
        "Pass" if not missing_schema else "Blocker",
        "errorsweep_auth_tokens table fields and RLS are present" if not missing_schema else ", ".join(missing_schema),
        "Keep email verification and password reset token storage in the production Supabase schema.",
    )


def validate_templates(results: List[Dict[str, str]]) -> None:
    env_text = read_text(ENV_TEMPLATE_PATH)
    streamlit_text = read_text(STREAMLIT_TEMPLATE_PATH)
    env_keys = active_template_keys(env_text)
    streamlit_keys = active_template_keys(streamlit_text)

    missing_env = [key for key in REQUIRED_TEMPLATE_KEYS if key not in env_keys]
    missing_streamlit = [key for key in REQUIRED_TEMPLATE_KEYS if key not in streamlit_keys]
    add(
        results,
        "Auth",
        "Production env auth keys",
        "Pass" if not missing_env else "Warn",
        "session + owner/workspace bootstrap keys listed" if not missing_env else ", ".join(missing_env),
        "Keep deploy/.env.production.example aligned with auth/session launch requirements.",
    )
    add(
        results,
        "Auth",
        "Streamlit auth secret keys",
        "Pass" if not missing_streamlit else "Warn",
        "session + owner/workspace bootstrap keys listed" if not missing_streamlit else ", ".join(missing_streamlit),
        "Keep .streamlit/secrets.toml.example aligned with Streamlit-hosted auth/session secrets.",
    )

    active_legacy_env = [key for key in LEGACY_PASSWORD_KEYS if key in env_keys]
    active_legacy_streamlit = [key for key in LEGACY_PASSWORD_KEYS if key in streamlit_keys]
    add(
        results,
        "Auth",
        "Plaintext password template keys",
        "Pass" if not active_legacy_env and not active_legacy_streamlit else "Blocker",
        "plaintext bootstrap password keys omitted" if not active_legacy_env and not active_legacy_streamlit else ", ".join(active_legacy_env + active_legacy_streamlit),
        "Use only ERRORSWEEP_OWNER_PASSWORD_HASH and ERRORSWEEP_USER_PASSWORD_HASH in production templates.",
    )


def validate_release_wiring(results: List[Dict[str, str]]) -> None:
    release = read_text(ROOT / "deploy" / "release_check.py")
    smoke = read_text(ROOT / "production_smoke_test.py")
    launch_env = read_text(ROOT / "deploy" / "launch_env_check.py")

    missing_release = missing_items(REQUIRED_RELEASE_TOKENS, release)
    add(
        results,
        "Auth",
        "Release-check wiring",
        "Pass" if not missing_release else "Warn",
        "auth_session_check included in release_check.py" if not missing_release else ", ".join(missing_release),
        "Run the auth/session launch check from the release guard.",
    )

    missing_smoke = missing_items(REQUIRED_SMOKE_TOKENS, smoke)
    add(
        results,
        "Auth",
        "Smoke-test auth wiring",
        "Pass" if not missing_smoke else "Warn",
        "runtime smoke validates owner/workspace auth" if not missing_smoke else ", ".join(missing_smoke),
        "Keep production_smoke_test.py blocking missing bootstrap credentials.",
    )

    missing_env_check = missing_items(["def check_auth", "ERRORSWEEP_OWNER_PASSWORD_HASH", "ERRORSWEEP_USER_PASSWORD_HASH"], launch_env)
    add(
        results,
        "Auth",
        "Env-check auth wiring",
        "Pass" if not missing_env_check else "Warn",
        "launch_env_check validates bootstrap hashes" if not missing_env_check else ", ".join(missing_env_check),
        "Keep deploy/launch_env_check.py validating owner/workspace PBKDF2 hashes.",
    )


def validate_email(results: List[Dict[str, str]], env: Dict[str, str], key: str, label: str) -> None:
    value = safe_text(env.get(key))
    ready = bool(value) and not is_placeholder(value) and bool(EMAIL_RE.match(value))
    add(
        results,
        "Auth Config",
        label,
        "Pass" if ready else "Blocker",
        nonsecret_evidence(key, value),
        f"Set {key} to the production bootstrap email address.",
    )


def validate_password_hash(results: List[Dict[str, str]], env: Dict[str, str], key: str, label: str) -> None:
    ready, detail = pbkdf2_hash_detail(env.get(key, ""))
    add(
        results,
        "Auth Config",
        label,
        "Pass" if ready else "Blocker",
        detail,
        f"Set {key} to a PBKDF2 hash from deploy/auth_session_check.py --generate-password-hash or --password-env.",
    )


def validate_env_config(results: List[Dict[str, str]], env_path: Path) -> Optional[Dict[str, str]]:
    if not env_path.exists():
        add(results, "Auth Config", "Production env file", "Blocker", "missing", "Create deploy/.env.production from the non-secret template.")
        return None

    env = parse_env_file(env_path)
    mode = safe_text(env.get("ERRORSWEEP_ENV")).lower()
    add(
        results,
        "Auth Config",
        "Production mode",
        "Pass" if mode == "production" else "Blocker",
        mode or "missing",
        "Set ERRORSWEEP_ENV=production before public traffic.",
    )

    public_url = safe_text(env.get("ERRORSWEEP_PUBLIC_BASE_URL"))
    add(
        results,
        "Auth Config",
        "Public HTTPS base URL",
        "Pass" if public_https_url(public_url) else "Blocker",
        nonsecret_evidence("ERRORSWEEP_PUBLIC_BASE_URL", public_url),
        "Set ERRORSWEEP_PUBLIC_BASE_URL to the live public HTTPS app URL used in verification and reset links.",
    )

    session_secret = safe_text(env.get("ERRORSWEEP_SESSION_SECRET"))
    strong_session_secret = not is_placeholder(session_secret) and len(session_secret) >= 32 and len(set(session_secret)) >= 12
    add(
        results,
        "Auth Config",
        "Session signing secret",
        "Pass" if strong_session_secret else "Blocker",
        "configured" if strong_session_secret else nonsecret_evidence("ERRORSWEEP_SESSION_SECRET", session_secret),
        "Set ERRORSWEEP_SESSION_SECRET to a long unique random value, never the development default.",
    )

    validate_email(results, env, "ERRORSWEEP_OWNER_USERNAME", "Owner bootstrap email")
    validate_password_hash(results, env, "ERRORSWEEP_OWNER_PASSWORD_HASH", "Owner bootstrap password hash")
    validate_email(results, env, "ERRORSWEEP_USER_USERNAME", "Workspace bootstrap email")
    validate_password_hash(results, env, "ERRORSWEEP_USER_PASSWORD_HASH", "Workspace bootstrap password hash")

    workspace_name = safe_text(env.get("ERRORSWEEP_ORG_NAME"))
    add(
        results,
        "Auth Config",
        "Workspace bootstrap name",
        "Pass" if workspace_name and not is_placeholder(workspace_name) else "Blocker",
        nonsecret_evidence("ERRORSWEEP_ORG_NAME", workspace_name),
        "Set ERRORSWEEP_ORG_NAME to the initial production workspace name for bootstrap login.",
    )

    default_role = safe_text(env.get("ERRORSWEEP_DEFAULT_USER_ROLE") or "Workspace Owner")
    allowed_roles = {"Workspace Owner", "Company Admin", "Workspace Admin", "Project Manager", "Team Lead", "Translator", "Reviewer", "Freelancer", "Client", "Client Viewer", "Billing Admin", "Talent Manager", "Individual Owner", "Individual User", "User"}
    add(
        results,
        "Auth Config",
        "Workspace bootstrap role",
        "Pass" if default_role in allowed_roles else "Warn",
        default_role or "missing",
        "Use a known workspace role, usually Workspace Owner, for the bootstrap workspace user.",
    )

    active_legacy = [key for key in LEGACY_PASSWORD_KEYS if safe_text(env.get(key))]
    add(
        results,
        "Auth Config",
        "Plaintext bootstrap passwords",
        "Pass" if not active_legacy else "Blocker",
        "not set" if not active_legacy else ", ".join(active_legacy),
        "Remove plaintext ERRORSWEEP_OWNER_PASSWORD / ERRORSWEEP_USER_PASSWORD; production login accepts only *_PASSWORD_HASH.",
    )

    ttl_raw = safe_text(env.get("ERRORSWEEP_AUTH_TOKEN_TTL_SECONDS"))
    if ttl_raw:
        try:
            ttl = int(ttl_raw)
            ttl_ready = 300 <= ttl <= 604800
            evidence = f"{ttl}s"
        except ValueError:
            ttl_ready = False
            evidence = "not numeric"
        add(
            results,
            "Auth Config",
            "Auth token TTL",
            "Pass" if ttl_ready else "Warn",
            evidence,
            "Use a numeric ERRORSWEEP_AUTH_TOKEN_TTL_SECONDS between five minutes and seven days when overriding the default.",
        )

    if env_bool(env, "ERRORSWEEP_ENTERPRISE_SSO_ENABLED"):
        handoff = safe_text(env.get("ERRORSWEEP_SSO_HANDOFF_SECRET"))
        ready = not is_placeholder(handoff) and len(handoff) >= 24
        add(
            results,
            "Auth Config",
            "SSO handoff secret",
            "Pass" if ready else "Blocker",
            "configured" if ready else nonsecret_evidence("ERRORSWEEP_SSO_HANDOFF_SECRET", handoff),
            "Set ERRORSWEEP_SSO_HANDOFF_SECRET before enabling enterprise SSO handoff.",
        )
    return env


def probe_public_url(results: List[Dict[str, str]], env: Dict[str, str], timeout: int) -> None:
    public_url = safe_text(env.get("ERRORSWEEP_PUBLIC_BASE_URL")).rstrip("/")
    if not public_https_url(public_url):
        add(results, "Auth Probe", "Public app probe", "Blocker", "public URL not ready", "Configure a live HTTPS public URL before probing.")
        return
    try:
        response = requests.get(public_url, timeout=timeout)
        add(
            results,
            "Auth Probe",
            "Public app probe",
            "Pass" if response.status_code < 500 else "Warn",
            f"HTTP {response.status_code}",
            "Verify the deployed app responds at ERRORSWEEP_PUBLIC_BASE_URL.",
        )
    except Exception as exc:
        add(results, "Auth Probe", "Public app probe", "Warn", safe_text(exc)[:220], "Check DNS, TLS, CDN/proxy routing, and Streamlit health.")


def collect_results(env_path: Optional[Path] = None, *, probe_public_url_enabled: bool = False, timeout: int = 15) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    validate_files(results)
    validate_contracts(results)
    validate_templates(results)
    validate_release_wiring(results)

    env: Optional[Dict[str, str]] = None
    if env_path is not None:
        env = validate_env_config(results, env_path)
    if probe_public_url_enabled:
        if env is None:
            add(results, "Auth Probe", "Public app probe configuration", "Blocker", "no env file", "Pass --env-file deploy/.env.production before --probe-public-url.")
        else:
            probe_public_url(results, env, max(3, min(timeout, 60)))
    return results


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
        "# CogniSweep Auth/Session Check",
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


def generate_password_hash() -> int:
    password = getpass.getpass("Bootstrap password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not password:
        print("Password cannot be empty.", file=sys.stderr)
        return 1
    if password != confirm:
        print("Passwords did not match.", file=sys.stderr)
        return 1
    print(make_password_hash(password))
    return 0


def generate_password_hash_from_env(env_var: str, *, as_json: bool = False) -> int:
    name = safe_text(env_var)
    if not name:
        print("--password-env requires an environment variable name.", file=sys.stderr)
        return 1
    password = os.environ.get(name, "")
    if not password:
        print(f"{name} is not set or is empty.", file=sys.stderr)
        return 1
    password_hash = make_password_hash(password)
    if as_json:
        print(json.dumps({"password_env": name, "password_hash": password_hash}, indent=2))
    else:
        print(password_hash)
    return 0


def bootstrap_password(password_env: str, *, generate_temporary: bool, label: str) -> Tuple[str, str, bool]:
    env_name = safe_text(password_env)
    if env_name:
        password = os.environ.get(env_name, "")
        if not password:
            raise ValueError(f"{env_name} is not set or is empty.")
        return password, make_password_hash(password), False
    if generate_temporary:
        password = generate_temporary_password()
        return password, make_password_hash(password), True
    raise ValueError(f"Set --{label}-password-env or pass --generate-temporary-passwords.")


def write_bootstrap_env(args: argparse.Namespace) -> int:
    env_path = Path(args.env_file) if args.env_file else DEFAULT_ENV_PATH
    owner_email = safe_text(args.owner_email)
    workspace_email = safe_text(args.workspace_email)
    workspace_name = safe_text(args.workspace_name)
    missing = [
        name
        for name, value in (
            ("--owner-email", owner_email),
            ("--workspace-email", workspace_email),
            ("--workspace-name", workspace_name),
        )
        if not value
    ]
    if missing:
        print(f"Missing required bootstrap value(s): {', '.join(missing)}", file=sys.stderr)
        return 1
    if not EMAIL_RE.match(owner_email):
        print("--owner-email must be a valid email address.", file=sys.stderr)
        return 1
    if not EMAIL_RE.match(workspace_email):
        print("--workspace-email must be a valid email address.", file=sys.stderr)
        return 1

    try:
        owner_password, owner_hash, owner_generated = bootstrap_password(
            args.owner_password_env,
            generate_temporary=args.generate_temporary_passwords,
            label="owner",
        )
        workspace_password, workspace_hash, workspace_generated = bootstrap_password(
            args.workspace_password_env,
            generate_temporary=args.generate_temporary_passwords,
            label="workspace",
        )
        write_env_updates(
            env_path,
            {
                "ERRORSWEEP_OWNER_USERNAME": owner_email,
                "ERRORSWEEP_OWNER_PASSWORD_HASH": owner_hash,
                "ERRORSWEEP_USER_USERNAME": workspace_email,
                "ERRORSWEEP_USER_PASSWORD_HASH": workspace_hash,
                "ERRORSWEEP_ORG_NAME": workspace_name,
            },
        )
    except Exception as exc:
        print(safe_text(exc), file=sys.stderr)
        return 1

    generated_passwords: Dict[str, str] = {}
    if owner_generated:
        generated_passwords["owner_password"] = owner_password
    if workspace_generated:
        generated_passwords["workspace_password"] = workspace_password

    payload = {
        "env_file": str(env_path),
        "updated": [
            "ERRORSWEEP_OWNER_USERNAME",
            "ERRORSWEEP_OWNER_PASSWORD_HASH",
            "ERRORSWEEP_USER_USERNAME",
            "ERRORSWEEP_USER_PASSWORD_HASH",
            "ERRORSWEEP_ORG_NAME",
        ],
        "owner_email": owner_email,
        "workspace_email": workspace_email,
        "workspace_name": workspace_name,
        "generated_passwords": generated_passwords,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Updated {env_path}")
        print(f"Owner bootstrap email: {owner_email}")
        print(f"Workspace bootstrap email: {workspace_email}")
        print(f"Initial workspace: {workspace_name}")
        if generated_passwords:
            print("Generated temporary passwords. Store these securely; they are not written to the env file.")
            for key, value in generated_passwords.items():
                print(f"{key}: {value}")
        else:
            print("Password hashes written from environment variables; plaintext passwords were not printed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CogniSweep production auth/session launch readiness.")
    parser.add_argument("--env-file", default="", help="Production env file to validate. Omit for offline code/template checks.")
    parser.add_argument("--probe-public-url", action="store_true", help="Probe ERRORSWEEP_PUBLIC_BASE_URL.")
    parser.add_argument("--timeout", type=int, default=15, help="Endpoint probe timeout in seconds.")
    parser.add_argument("--generate-password-hash", action="store_true", help="Interactively generate a PBKDF2 hash for bootstrap credentials.")
    parser.add_argument("--password-env", default="", help="Read one password from this environment variable and print its PBKDF2 hash.")
    parser.add_argument("--write-bootstrap-env", action="store_true", help="Write owner/workspace bootstrap emails, workspace name, and PBKDF2 hashes into the env file.")
    parser.add_argument("--owner-email", default="", help="Platform owner bootstrap email used with --write-bootstrap-env.")
    parser.add_argument("--workspace-email", default="", help="Initial workspace owner bootstrap email used with --write-bootstrap-env.")
    parser.add_argument("--workspace-name", default="", help="Initial workspace name used with --write-bootstrap-env.")
    parser.add_argument("--owner-password-env", default="", help="Environment variable containing the owner bootstrap password.")
    parser.add_argument("--workspace-password-env", default="", help="Environment variable containing the workspace bootstrap password.")
    parser.add_argument("--generate-temporary-passwords", action="store_true", help="Generate one-time temporary owner/workspace passwords when password env vars are omitted.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    if args.generate_password_hash:
        return generate_password_hash()
    if args.password_env:
        return generate_password_hash_from_env(args.password_env, as_json=args.json)
    if args.write_bootstrap_env:
        return write_bootstrap_env(args)

    env_path = Path(args.env_file) if args.env_file else None
    results = sorted(
        collect_results(env_path=env_path, probe_public_url_enabled=args.probe_public_url, timeout=args.timeout),
        key=lambda row: (status_rank(row["Status"]), row["Area"], row["Check"]),
    )
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
