"""Validate CogniSweep billing and webhook launch readiness.

Offline mode checks that billing normalization, signature verification,
standalone webhook receiver wiring, templates, and compose deployment are
present. Use --env-file for provider-specific production config validation,
--run-smoke for a local receiver health smoke, and --probe-health only after
the public webhook receiver is deployed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ENV_TEMPLATE_PATH = ROOT / "deploy" / ".env.production.example"
STREAMLIT_TEMPLATE_PATH = ROOT / ".streamlit" / "secrets.toml.example"
COMPOSE_PATH = ROOT / "docker-compose.production.yml"
RECEIVER_PATH = ROOT / "billing_webhook_receiver.py"
HELPERS_PATH = ROOT / "billing_webhooks.py"
LAUNCH_ENV_CHECK_PATH = ROOT / "deploy" / "launch_env_check.py"

SUPPORTED_PROVIDERS = {"razorpay", "stripe"}
REQUIRED_RECEIVER_SYMBOLS = [
    "process_webhook",
    "verify_signature",
    "event_replay_status",
    "find_existing_billing_event",
    "provider_from_path",
    "BillingWebhookHandler",
    "do_GET",
    "do_POST",
    "run_server",
]
REQUIRED_HELPER_SYMBOLS = [
    "verify_stripe_signature",
    "verify_razorpay_signature",
    "verify_billing_webhook_signature",
    "normalize_billing_webhook",
    "infer_provider",
]
REQUIRED_TEMPLATE_TOKENS = [
    "ERRORSWEEP_BILLING_PROVIDER",
    "ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL",
    "ERRORSWEEP_BILLING_WEBHOOK_SECRET",
    "ERRORSWEEP_WEBHOOK_APPLY_UPDATES",
    "ERRORSWEEP_BILLING_CREATE_PROVIDER_CHECKOUT",
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
    "RAZORPAY_WEBHOOK_SECRET",
    "RAZORPAY_PLAN_ID_PRO",
    "RAZORPAY_PLAN_ID_AGENCY",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_ID_PRO",
    "STRIPE_PRICE_ID_AGENCY",
    "ERRORSWEEP_MONTHLY_MANDATE_LINK_PRO",
    "ERRORSWEEP_MONTHLY_MANDATE_LINK_AGENCY",
    "ERRORSWEEP_TRIAL_MANDATE_LINK",
]
REQUIRED_STREAMLIT_TOKENS = [
    "ERRORSWEEP_BILLING_PROVIDER",
    "ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL",
    "ERRORSWEEP_BILLING_WEBHOOK_SECRET",
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
    "RAZORPAY_WEBHOOK_SECRET",
    "RAZORPAY_PLAN_ID_PRO",
    "RAZORPAY_PLAN_ID_AGENCY",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRICE_ID_PRO",
    "STRIPE_PRICE_ID_AGENCY",
    "ERRORSWEEP_BILLING_CREATE_PROVIDER_CHECKOUT",
]
REQUIRED_COMPOSE_TOKENS = [
    "errorsweep-billing-webhook:",
    "billing_webhook_receiver.py",
    "ERRORSWEEP_BILLING_WEBHOOK_HOST",
    "ERRORSWEEP_BILLING_WEBHOOK_PORT",
    "127.0.0.1:8301:8301",
    "http://127.0.0.1:8301/health",
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
)
SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|KEY|CLIENT_SECRET)", re.IGNORECASE)


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
    return value.lower() in {"1", "true", "yes", "on", "enabled"}


def value_for(env: Dict[str, str], names: Sequence[str]) -> str:
    for name in names:
        value = safe_text(env.get(name))
        if value:
            return value
    return ""


def configured(env: Dict[str, str], names: Sequence[str], min_length: int = 1) -> bool:
    value = value_for(env, names)
    return bool(value) and not is_placeholder(value) and len(value) >= min_length


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


def https_url(value: str) -> bool:
    if is_placeholder(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def webhook_health_url(webhook_url: str) -> str:
    parsed = urlparse(webhook_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}/health"


def validate_files(results: List[Dict[str, str]]) -> None:
    missing = [
        str(path.relative_to(ROOT))
        for path in [RECEIVER_PATH, HELPERS_PATH, LAUNCH_ENV_CHECK_PATH]
        if not path.exists()
    ]
    add(
        results,
        "Billing",
        "Billing source files",
        "Pass" if not missing else "Blocker",
        "receiver + webhook helpers + env writer present" if not missing else ", ".join(missing),
        "Keep billing_webhook_receiver.py, billing_webhooks.py, and launch_env_check.py in the release branch.",
    )


def validate_receiver_contract(results: List[Dict[str, str]]) -> None:
    receiver = read_text(RECEIVER_PATH)
    helpers = read_text(HELPERS_PATH)
    missing_receiver = [symbol for symbol in REQUIRED_RECEIVER_SYMBOLS if symbol not in receiver]
    missing_helpers = [symbol for symbol in REQUIRED_HELPER_SYMBOLS if symbol not in helpers]
    add(
        results,
        "Billing",
        "Webhook receiver contract",
        "Pass" if not missing_receiver else "Blocker",
        "POST routes, health route, signature gate, lifecycle updates present" if not missing_receiver else ", ".join(missing_receiver),
        "Keep standalone billing webhook receiver routes and processing hooks stable for provider callbacks.",
    )
    add(
        results,
        "Billing",
        "Webhook normalization contract",
        "Pass" if not missing_helpers else "Blocker",
        "Stripe/Razorpay normalization and signature helpers present" if not missing_helpers else ", ".join(missing_helpers),
        "Keep provider payload normalization and signature verification helpers available to the app and receiver.",
    )

    signature_tokens = missing_items(["hmac.compare_digest", "Stripe-Signature", "X-Razorpay-Signature", "secret_missing", "invalid"], receiver + helpers)
    add(
        results,
        "Billing",
        "Signature enforcement coverage",
        "Pass" if not signature_tokens else "Blocker",
        "constant-time verification and provider headers covered" if not signature_tokens else ", ".join(signature_tokens),
        "Do not apply live billing events unless Stripe/Razorpay signatures verify.",
    )

    replay_tokens = missing_items(
        [
            "event_replay_status",
            "find_existing_billing_event",
            "duplicate_applied_event",
            "ERRORSWEEP_BILLING_WEBHOOK_REPLAY_WINDOW_SECONDS",
            "too_old",
            "future",
        ],
        receiver,
    )
    add(
        results,
        "Billing",
        "Webhook replay/idempotency coverage",
        "Pass" if not replay_tokens else "Blocker",
        "event replay window and duplicate already-applied events are guarded" if not replay_tokens else ", ".join(replay_tokens),
        "Do not apply stale, future-dated, or already-applied billing provider events.",
    )


def validate_templates(results: List[Dict[str, str]]) -> None:
    env_template = read_text(ENV_TEMPLATE_PATH)
    streamlit_template = read_text(STREAMLIT_TEMPLATE_PATH)
    missing_env = missing_items(REQUIRED_TEMPLATE_TOKENS, env_template)
    missing_streamlit = missing_items(REQUIRED_STREAMLIT_TOKENS, streamlit_template)
    add(
        results,
        "Billing",
        "Production env billing keys",
        "Pass" if not missing_env else "Warn",
        "provider, webhook, plan, checkout, mandate keys listed" if not missing_env else ", ".join(missing_env),
        "Keep deploy/.env.production.example aligned with Razorpay and Stripe launch settings.",
    )
    add(
        results,
        "Billing",
        "Streamlit billing secret keys",
        "Pass" if not missing_streamlit else "Warn",
        "provider, webhook, plan, checkout keys listed" if not missing_streamlit else ", ".join(missing_streamlit),
        "Keep .streamlit/secrets.toml.example aligned for hosted Streamlit deployments.",
    )


def validate_compose(results: List[Dict[str, str]]) -> None:
    compose = read_text(COMPOSE_PATH)
    missing = missing_items(REQUIRED_COMPOSE_TOKENS, compose)
    add(
        results,
        "Billing",
        "Compose billing service wiring",
        "Pass" if not missing else "Blocker",
        "billing webhook service, healthcheck, port, volumes wired" if not missing else ", ".join(missing),
        "Run billing_webhook_receiver.py as a separate production service with persistent logs and health checks.",
    )


def validate_env_config(results: List[Dict[str, str]], env_path: Path) -> Optional[Dict[str, str]]:
    if not env_path.exists():
        add(results, "Billing Config", "Production env file", "Blocker", "missing", "Create deploy/.env.production from the non-secret template.")
        return None

    env = parse_env_file(env_path)
    provider = safe_text(env.get("ERRORSWEEP_BILLING_PROVIDER")).lower()
    webhook_url = safe_text(env.get("ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL"))
    add(
        results,
        "Billing Config",
        "Billing provider",
        "Pass" if provider in SUPPORTED_PROVIDERS else "Blocker",
        provider or "missing",
        "Set ERRORSWEEP_BILLING_PROVIDER to razorpay or stripe.",
    )
    add(
        results,
        "Billing Config",
        "Webhook receiver URL",
        "Pass" if https_url(webhook_url) else "Blocker",
        nonsecret_evidence("ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL", webhook_url),
        "Deploy billing_webhook_receiver.py behind HTTPS and set the public provider callback URL.",
    )
    require_value(results, env, "Billing Config", "Shared webhook secret", ["ERRORSWEEP_BILLING_WEBHOOK_SECRET"], "Set a shared billing webhook secret for receiver fallback and diagnostics.", min_length=8)

    if provider == "razorpay":
        require_value(results, env, "Billing Config", "Razorpay key ID", ["RAZORPAY_KEY_ID"], "Set the live Razorpay key ID.", min_length=8)
        require_value(results, env, "Billing Config", "Razorpay key secret", ["RAZORPAY_KEY_SECRET"], "Set the live Razorpay key secret.", min_length=8)
        require_value(results, env, "Billing Config", "Razorpay webhook secret", ["RAZORPAY_WEBHOOK_SECRET", "ERRORSWEEP_BILLING_WEBHOOK_SECRET"], "Set the Razorpay webhook signing secret.", min_length=8)
        require_value(results, env, "Billing Config", "Razorpay Pro plan ID", ["RAZORPAY_PLAN_ID_PRO"], "Set the live Pro plan ID.", status_when_missing="Warn")
        require_value(results, env, "Billing Config", "Razorpay Agency plan ID", ["RAZORPAY_PLAN_ID_AGENCY"], "Set the live Agency plan ID.", status_when_missing="Warn")
    elif provider == "stripe":
        require_value(results, env, "Billing Config", "Stripe secret key", ["STRIPE_SECRET_KEY", "ERRORSWEEP_STRIPE_SECRET_KEY"], "Set the live Stripe secret key.", min_length=12)
        require_value(results, env, "Billing Config", "Stripe webhook secret", ["STRIPE_WEBHOOK_SECRET", "ERRORSWEEP_BILLING_WEBHOOK_SECRET"], "Set the Stripe webhook signing secret.", min_length=12)
        require_value(results, env, "Billing Config", "Stripe Pro price ID", ["STRIPE_PRICE_ID_PRO"], "Set the live Pro price ID.", status_when_missing="Warn")
        require_value(results, env, "Billing Config", "Stripe Agency price ID", ["STRIPE_PRICE_ID_AGENCY"], "Set the live Agency price ID.", status_when_missing="Warn")

    mandate_ready = configured(env, ["ERRORSWEEP_MONTHLY_MANDATE_LINK_PRO"]) or configured(env, ["ERRORSWEEP_BILLING_CREATE_PROVIDER_CHECKOUT"])
    add(
        results,
        "Billing Config",
        "Recurring checkout path",
        "Pass" if mandate_ready else "Warn",
        "provider checkout or hosted mandate link configured" if mandate_ready else "missing",
        "Configure provider checkout creation or hosted card/UPI mandate links before paid launch.",
    )
    add(
        results,
        "Billing Config",
        "Webhook update mode",
        "Pass" if env_bool(env, "ERRORSWEEP_WEBHOOK_APPLY_UPDATES") else "Warn",
        "enabled" if env_bool(env, "ERRORSWEEP_WEBHOOK_APPLY_UPDATES") else safe_text(env.get("ERRORSWEEP_WEBHOOK_APPLY_UPDATES")) or "missing",
        "Enable lifecycle updates only after signature tests pass in staging.",
    )
    return env


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def probe_url(url: str, timeout: int) -> Dict[str, str]:
    import requests

    try:
        response = requests.get(url, timeout=timeout)
        return {"status": "ok" if response.status_code < 500 else "error", "detail": f"HTTP {response.status_code}"}
    except Exception as exc:
        return {"status": "error", "detail": safe_text(exc)[:220]}


def run_local_smoke(results: List[Dict[str, str]], timeout: int) -> None:
    port = free_local_port()
    env = os.environ.copy()
    env.update(
        {
            "ERRORSWEEP_BILLING_WEBHOOK_HOST": "127.0.0.1",
            "ERRORSWEEP_BILLING_WEBHOOK_PORT": str(port),
            "ERRORSWEEP_WEBHOOK_APPLY_UPDATES": "false",
        }
    )
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [sys.executable, "billing_webhook_receiver.py"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=flags,
    )
    try:
        deadline = time.time() + max(5, timeout)
        last_detail = "not started"
        while time.time() < deadline:
            if proc.poll() is not None:
                stderr = proc.stderr.read() if proc.stderr else ""
                last_detail = stderr.splitlines()[0][:220] if stderr.splitlines() else f"exit {proc.returncode}"
                break
            probe = probe_url(f"http://127.0.0.1:{port}/health", timeout=2)
            last_detail = probe["detail"]
            if probe["status"] == "ok":
                add(results, "Billing Smoke", "Webhook receiver health", "Pass", last_detail, "Keep the standalone billing receiver able to serve /health.")
                return
            time.sleep(0.5)
        add(results, "Billing Smoke", "Webhook receiver health", "Blocker", last_detail, "Run billing_webhook_receiver.py locally and inspect startup logs.")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def probe_receiver_health(results: List[Dict[str, str]], env: Dict[str, str], timeout: int) -> None:
    url = webhook_health_url(safe_text(env.get("ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL")))
    if not url:
        add(results, "Billing Probe", "Webhook receiver health", "Blocker", "webhook URL missing", "Set ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL before probing receiver health.")
        return
    probe = probe_url(url, timeout)
    add(
        results,
        "Billing Probe",
        "Webhook receiver health",
        "Pass" if probe["status"] == "ok" else "Blocker",
        probe["detail"],
        "Verify billing_webhook_receiver.py is reachable at /health from the deployment environment.",
    )


def collect_results(
    env_path: Optional[Path] = None,
    *,
    run_smoke: bool = False,
    probe_health_enabled: bool = False,
    timeout: int = 60,
) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    validate_files(results)
    validate_receiver_contract(results)
    validate_templates(results)
    validate_compose(results)

    env: Optional[Dict[str, str]] = None
    if env_path is not None:
        env = validate_env_config(results, env_path)
    if run_smoke:
        run_local_smoke(results, timeout)
    if probe_health_enabled:
        if env is None:
            add(results, "Billing Probe", "Probe configuration", "Blocker", "no env file", "Pass --env-file deploy/.env.production before --probe-health.")
        else:
            probe_receiver_health(results, env, min(timeout, 30))
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
        "# CogniSweep Billing Check",
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
    parser = argparse.ArgumentParser(description="Validate CogniSweep billing and webhook launch readiness.")
    parser.add_argument("--env-file", default="", help="Production env file to validate. Omit for offline receiver/template checks.")
    parser.add_argument("--run-smoke", action="store_true", help="Run a local billing webhook receiver health smoke check.")
    parser.add_argument("--probe-health", action="store_true", help="Probe the configured public billing webhook receiver /health endpoint.")
    parser.add_argument("--timeout", type=int, default=60, help="Smoke/probe timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    env_path = Path(args.env_file) if args.env_file else None
    results = sorted(
        collect_results(
            env_path=env_path,
            run_smoke=args.run_smoke,
            probe_health_enabled=args.probe_health,
            timeout=max(10, args.timeout),
        ),
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
