"""Validate CogniSweep transactional email launch readiness.

Offline mode checks that the dispatch worker, transactional templates,
supervisor wiring, provider templates, and dependencies are present. Use
--env-file for provider-specific production config validation and --run-smoke
for a local dry-run dispatch pass that does not send email.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
ENV_TEMPLATE_PATH = ROOT / "deploy" / ".env.production.example"
STREAMLIT_TEMPLATE_PATH = ROOT / ".streamlit" / "secrets.toml.example"
COMPOSE_PATH = ROOT / "docker-compose.production.yml"
REQUIREMENTS_PATH = ROOT / "requirements.txt"
WORKER_PATH = ROOT / "email_dispatch_worker.py"
TEMPLATES_PATH = ROOT / "email_templates.py"
SUPERVISOR_PATH = ROOT / "worker_supervisor.py"

SUPPORTED_PROVIDERS = {"resend", "sendgrid", "smtp"}
REQUIRED_WORKER_SYMBOLS = [
    "dispatch_notification",
    "dispatch_pending",
    "notification_email_payload",
    "email_provider_label",
    "email_from_address",
    "_send_resend",
    "_send_sendgrid",
    "_send_smtp",
]
REQUIRED_TEMPLATE_SYMBOLS = [
    "TEMPLATE_META",
    "template_catalog",
    "render_transactional_email",
    "_template_for_event",
]
REQUIRED_TEMPLATE_EVENTS = [
    "auth.email_verification",
    "auth.password_reset",
    "signup.welcome",
    "job.assigned",
    "qa.completed",
    "pro.completed",
    "billing.checkout_intent",
    "billing.payment_recorded",
    "support.ticket_opened",
    "status.incident_created",
    "privacy_request_opened",
    "email.deliverability_test",
]
REQUIRED_ENV_TOKENS = [
    "ERRORSWEEP_EMAIL_PROVIDER",
    "ERRORSWEEP_EMAIL_HTML_ENABLED",
    "ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED",
    "ERRORSWEEP_EMAIL_WORKER_INTERVAL_SECONDS",
    "ERRORSWEEP_EMAIL_DISPATCH_BATCH_LIMIT",
    "ERRORSWEEP_EMAIL_FROM",
    "RESEND_API_KEY",
    "SENDGRID_API_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_TLS",
]
REQUIRED_STREAMLIT_TOKENS = [
    "ERRORSWEEP_EMAIL_PROVIDER",
    "ERRORSWEEP_EMAIL_FROM",
    "ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED",
    "RESEND_API_KEY",
    "SENDGRID_API_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_TLS",
]
REQUIRED_COMPOSE_TOKENS = [
    "errorsweep-worker-supervisor:",
    "worker_supervisor.py",
    "ERRORSWEEP_SUPERVISOR_ENABLE_EMAIL_WORKER",
    "ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED",
    "errorsweep-data:",
    "errorsweep-logs:",
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
    "errorsweep.local", "cognisweep.local",
)
SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|KEY|CREDENTIAL)", re.IGNORECASE)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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


def requirement_name(line: str) -> str:
    text = line.strip()
    if not text or text.startswith("#") or text.startswith("-"):
        return ""
    text = text.split(";", 1)[0].strip()
    text = re.split(r"\s*(?:===|==|~=|>=|<=|>|<|!=)\s*", text, maxsplit=1)[0]
    text = text.split("[", 1)[0].strip().lower()
    return text.replace("_", "-")


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
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def nonsecret_evidence(key: str, value: str) -> str:
    if not safe_text(value):
        return "missing"
    if is_placeholder(value):
        return "placeholder"
    if SENSITIVE_KEY_RE.search(key):
        return "configured"
    return value


def value_for(env: Dict[str, str], names: Sequence[str]) -> str:
    for name in names:
        for candidate in aliases_for(name):
            value = safe_text(env.get(candidate))
            if value:
                return value
    return ""


def cognisweep_env_alias(name: str) -> str:
    if name.startswith("ERRORSWEEP_"):
        return f"COGNISWEEP_{name[len('ERRORSWEEP_'):]}"
    return ""


def aliases_for(name: str) -> List[str]:
    alias = cognisweep_env_alias(name)
    return [name, alias] if alias else [name]


def configured(env: Dict[str, str], names: Sequence[str], min_length: int = 1) -> bool:
    value = value_for(env, names)
    return bool(value) and not is_placeholder(value) and len(value) >= min_length


def env_bool(env: Dict[str, str], name: str, default: bool = False) -> bool:
    value = value_for(env, [name])
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on", "enabled"}


def require_value(
    results: List[Dict[str, str]],
    env: Dict[str, str],
    area: str,
    check: str,
    names: Sequence[str],
    action: str,
    *,
    min_length: int = 1,
    status_when_missing: str = "Blocker",
) -> None:
    value = value_for(env, names)
    add(results, area, check, "Pass" if configured(env, names, min_length=min_length) else status_when_missing, nonsecret_evidence(names[0], value), action)


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
    value = value_for(env, [name])
    add(results, area, check, "Pass" if env_bool(env, name) else status_when_false, "enabled" if env_bool(env, name) else value or "missing", action)


def valid_sender(value: str) -> bool:
    text = safe_text(value)
    if is_placeholder(text):
        return False
    if "<" in text and ">" in text:
        text = text.rsplit("<", 1)[-1].split(">", 1)[0].strip()
    return bool(EMAIL_RE.match(text))


def validate_files(results: List[Dict[str, str]]) -> None:
    missing = [
        str(path.relative_to(ROOT))
        for path in [WORKER_PATH, TEMPLATES_PATH, SUPERVISOR_PATH]
        if not path.exists()
    ]
    add(
        results,
        "Email",
        "Email source files",
        "Pass" if not missing else "Blocker",
        "dispatch worker + templates + supervisor present" if not missing else ", ".join(missing),
        "Keep email_dispatch_worker.py, email_templates.py, and worker_supervisor.py in the release branch.",
    )


def validate_worker_contract(results: List[Dict[str, str]]) -> None:
    worker = read_text(WORKER_PATH)
    templates = read_text(TEMPLATES_PATH)
    missing_worker = [symbol for symbol in REQUIRED_WORKER_SYMBOLS if symbol not in worker]
    missing_templates = [symbol for symbol in REQUIRED_TEMPLATE_SYMBOLS if symbol not in templates]
    missing_events = [event for event in REQUIRED_TEMPLATE_EVENTS if event not in templates]
    provider_tokens = missing_items(["resend", "sendgrid", "smtp", "dry_run", "provider_pending"], worker)

    add(
        results,
        "Email",
        "Dispatch worker contract",
        "Pass" if not missing_worker and not provider_tokens else "Blocker",
        "Resend, SendGrid, SMTP, dry-run dispatch functions present" if not missing_worker and not provider_tokens else ", ".join(missing_worker + provider_tokens),
        "Keep the dispatch worker able to render and deliver queued notifications through supported providers.",
    )
    add(
        results,
        "Email",
        "Template rendering contract",
        "Pass" if not missing_templates else "Blocker",
        "HTML/plain-text renderer and catalog present" if not missing_templates else ", ".join(missing_templates),
        "Keep deterministic transactional templates available for dispatch and preview.",
    )
    add(
        results,
        "Email",
        "Template event coverage",
        "Pass" if not missing_events else "Warn",
        "auth, billing, support, QA/Pro, status, privacy, deliverability events covered" if not missing_events else ", ".join(missing_events),
        "Keep launch-critical notification event templates covered before public onboarding.",
    )


def validate_templates(results: List[Dict[str, str]]) -> None:
    env_template = read_text(ENV_TEMPLATE_PATH)
    streamlit_template = read_text(STREAMLIT_TEMPLATE_PATH)
    missing_env = missing_items(REQUIRED_ENV_TOKENS, env_template)
    missing_streamlit = missing_items(REQUIRED_STREAMLIT_TOKENS, streamlit_template)
    add(
        results,
        "Email",
        "Production env email keys",
        "Pass" if not missing_env else "Warn",
        "provider, sender, worker, Resend, SendGrid, SMTP keys listed" if not missing_env else ", ".join(missing_env),
        "Keep deploy/.env.production.example aligned with transactional email provider settings.",
    )
    add(
        results,
        "Email",
        "Streamlit email secret keys",
        "Pass" if not missing_streamlit else "Warn",
        "provider, sender, worker, provider secret keys listed" if not missing_streamlit else ", ".join(missing_streamlit),
        "Keep .streamlit/secrets.toml.example aligned for hosted Streamlit deployments.",
    )


def validate_requirements(results: List[Dict[str, str]]) -> None:
    packages = {requirement_name(line) for line in read_text(REQUIREMENTS_PATH).splitlines()}
    packages.discard("")
    missing = [package for package in ["requests"] if package not in packages]
    add(
        results,
        "Email",
        "Email provider dependencies",
        "Pass" if not missing else "Blocker",
        "requests present for Resend/SendGrid APIs; smtplib is stdlib" if not missing else ", ".join(missing),
        "Keep HTTP provider dependencies in requirements.txt.",
    )


def validate_compose(results: List[Dict[str, str]]) -> None:
    compose = read_text(COMPOSE_PATH)
    missing = missing_items(REQUIRED_COMPOSE_TOKENS, compose)
    add(
        results,
        "Email",
        "Compose email worker wiring",
        "Pass" if not missing else "Blocker",
        "supervisor email worker and persistent volumes wired" if not missing else ", ".join(missing),
        "Run email_dispatch_worker.py under worker_supervisor.py or an equivalent managed process.",
    )


def validate_env_config(results: List[Dict[str, str]], env_path: Path) -> Optional[Dict[str, str]]:
    if not env_path.exists():
        add(results, "Email Config", "Production env file", "Blocker", "missing", "Create deploy/.env.production from the non-secret template.")
        return None

    env = parse_env_file(env_path)
    provider = value_for(env, ["ERRORSWEEP_EMAIL_PROVIDER"]).lower()
    sender = value_for(env, ["ERRORSWEEP_EMAIL_FROM", "SENDGRID_FROM_EMAIL", "RESEND_FROM_EMAIL"])
    add(
        results,
        "Email Config",
        "Email provider",
        "Pass" if provider in SUPPORTED_PROVIDERS else "Blocker",
        provider or "missing",
        "Set ERRORSWEEP_EMAIL_PROVIDER to resend, sendgrid, or smtp.",
    )
    add(
        results,
        "Email Config",
        "Verified sender address",
        "Pass" if valid_sender(sender) else "Blocker",
        nonsecret_evidence("ERRORSWEEP_EMAIL_FROM", sender),
        "Set ERRORSWEEP_EMAIL_FROM to a verified production sender domain.",
    )
    require_flag(results, env, "Email Config", "Dispatch worker enabled", "ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED", "Schedule email_dispatch_worker.py for queued notification delivery.")
    require_flag(results, env, "Email Config", "Supervisor email worker", "ERRORSWEEP_SUPERVISOR_ENABLE_EMAIL_WORKER", "Enable email dispatch under worker_supervisor.py or deploy it separately.", status_when_false="Warn")
    if provider == "resend":
        require_value(results, env, "Email Config", "Resend API key", ["RESEND_API_KEY", "ERRORSWEEP_RESEND_API_KEY"], "Set the production Resend API key.", min_length=12)
    elif provider == "sendgrid":
        require_value(results, env, "Email Config", "SendGrid API key", ["SENDGRID_API_KEY", "ERRORSWEEP_SENDGRID_API_KEY"], "Set the production SendGrid API key.", min_length=12)
    elif provider == "smtp":
        require_value(results, env, "Email Config", "SMTP host", ["SMTP_HOST", "ERRORSWEEP_SMTP_HOST"], "Set the production SMTP host.")
        require_value(results, env, "Email Config", "SMTP password", ["SMTP_PASSWORD", "ERRORSWEEP_SMTP_PASSWORD"], "Set the production SMTP password.", min_length=8)
        require_value(results, env, "Email Config", "SMTP username", ["SMTP_USER", "ERRORSWEEP_SMTP_USER"], "Set the production SMTP username.", status_when_missing="Warn")
    add(
        results,
        "Email Config",
        "HTML templates enabled",
        "Pass" if env_bool(env, "ERRORSWEEP_EMAIL_HTML_ENABLED", True) else "Warn",
        "enabled" if env_bool(env, "ERRORSWEEP_EMAIL_HTML_ENABLED", True) else value_for(env, ["ERRORSWEEP_EMAIL_HTML_ENABLED"]) or "missing",
        "Keep branded HTML enabled unless a provider-specific deliverability issue requires plain text temporarily.",
    )
    return env


def run_local_smoke(results: List[Dict[str, str]], timeout: int) -> None:
    with tempfile.TemporaryDirectory(prefix="errorsweep_email_check_") as temp_dir:
        root = Path(temp_dir)
        env = os.environ.copy()
        env.update(
            {
                "ERRORSWEEP_EDITOR_JOB_DIR": str(root / "editor_jobs"),
                "ERRORSWEEP_EMAIL_PROVIDER": "resend",
                "ERRORSWEEP_EMAIL_FROM": "no-reply@example.com",
                "RESEND_API_KEY": "dry-run-placeholder-key",
                "ERRORSWEEP_EMAIL_HTML_ENABLED": "true",
            }
        )
        try:
            completed = subprocess.run(
                [sys.executable, "email_dispatch_worker.py", "--once", "--dry-run", "--limit", "3"],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            output = completed.stdout or completed.stderr or ""
            evidence = "; ".join(line for line in output.splitlines()[:2] if line)[:220] or f"exit {completed.returncode}"
            add(
                results,
                "Email Smoke",
                "Dispatch worker dry run",
                "Pass" if completed.returncode == 0 else "Blocker",
                evidence,
                "Fix local email worker dry-run failures before deploying transactional email.",
            )
        except Exception as exc:
            add(results, "Email Smoke", "Dispatch worker dry run", "Blocker", safe_text(exc)[:220], "Run email_dispatch_worker.py --once --dry-run manually and inspect logs.")


def collect_results(env_path: Optional[Path] = None, *, run_smoke: bool = False, timeout: int = 60) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    validate_files(results)
    validate_worker_contract(results)
    validate_templates(results)
    validate_requirements(results)
    validate_compose(results)
    if env_path is not None:
        validate_env_config(results, env_path)
    if run_smoke:
        run_local_smoke(results, timeout)
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
        "# CogniSweep Email Check",
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
    parser = argparse.ArgumentParser(description="Validate CogniSweep transactional email launch readiness.")
    parser.add_argument("--env-file", default="", help="Production env file to validate. Omit for offline worker/template checks.")
    parser.add_argument("--run-smoke", action="store_true", help="Run a local email dispatch dry-run smoke check.")
    parser.add_argument("--timeout", type=int, default=60, help="Smoke timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    env_path = Path(args.env_file) if args.env_file else None
    results = sorted(
        collect_results(env_path=env_path, run_smoke=args.run_smoke, timeout=max(10, args.timeout)),
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
