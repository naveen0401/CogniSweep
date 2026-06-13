"""Validate ErrorSweep production AI fallback launch readiness.

Offline mode checks router code, templates, and release wiring. Use --env-file
to validate production settings, --probe-models for OpenAI-compatible /models
health, and --probe-chat only when a live route may be called.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / "deploy" / ".env.production"
ENV_TEMPLATE_PATH = ROOT / "deploy" / ".env.production.example"
STREAMLIT_TEMPLATE_PATH = ROOT / ".streamlit" / "secrets.toml.example"

REQUIRED_FILES = [
    "managed_ai_router.py",
    "app.py",
    "async_workflow_processor.py",
    "production_smoke_test.py",
    "deploy/launch_env_check.py",
]
REQUIRED_ROUTER_SYMBOLS = [
    "AIRoute",
    "select_ai_route",
    "platform_openai_route",
    "get_ai_client",
    "ai_json_items",
    "_validate_base_url",
    "_blocked_host_reason",
]
REQUIRED_APP_TOKENS = [
    "ai_json_items",
    "select_ai_route",
    "call_main_api_translate",
    "call_main_api_qa",
]
REQUIRED_TEMPLATE_KEYS = [
    "OPENAI_API_KEY",
    "ERRORSWEEP_OPENAI_DEFAULT_MODEL",
    "GEMINI_API_KEY",
    "ERRORSWEEP_MANAGED_AI_ENABLED",
    "ERRORSWEEP_MANAGED_AI_BASE_URL",
    "ERRORSWEEP_MANAGED_AI_API_KEY",
    "ERRORSWEEP_MANAGED_AI_MODEL",
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
SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|KEY|API_KEY)", re.IGNORECASE)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
PRIVATE_HOST_HINTS = (".local", ".internal", ".lan", ".home", "metadata.google.internal")


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def add(results: List[Dict[str, str]], area: str, check: str, status: str, evidence: str, action: str) -> None:
    results.append({
        "Area": area,
        "Check": check,
        "Status": status,
        "Evidence": evidence,
        "Action": action,
    })


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


def env_bool(env: Dict[str, str], name: str, default: bool = False) -> bool:
    value = safe_text(env.get(name))
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def nonsecret_evidence(key: str, value: str) -> str:
    if not safe_text(value):
        return "missing"
    if is_placeholder(value):
        return "placeholder"
    if SENSITIVE_KEY_RE.search(key):
        return "configured"
    return value


def configured_secret(value: str, min_length: int = 12) -> bool:
    text = safe_text(value)
    return bool(text) and not is_placeholder(text) and len(text) >= min_length


def openai_key_ready(value: str) -> bool:
    text = safe_text(value)
    if not configured_secret(text, min_length=12):
        return False
    return text.startswith("sk-") and len(text) >= 20


def normalize_openai_base_url(value: str) -> str:
    url = safe_text(value).rstrip("/")
    if not url:
        return ""
    return url if url.endswith("/v1") else f"{url}/v1"


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
        new_lines.extend(["", "# Added by deploy/ai_fallback_check.py setup helper"])
        for key, value in remaining.items():
            new_lines.append(f"{key}={format_env_value(value)}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def host_is_public(hostname: str) -> bool:
    host = safe_text(hostname).lower()
    if not host or host in LOCAL_HOSTS or any(host.endswith(hint) for hint in PRIVATE_HOST_HINTS):
        return False
    if host in {"169.254.169.254"}:
        return False
    return True


def https_public_url(value: str) -> bool:
    if is_placeholder(value):
        return False
    parsed = urlparse(normalize_openai_base_url(value))
    return parsed.scheme == "https" and bool(parsed.netloc) and host_is_public(parsed.hostname or "")


def validate_files(results: List[Dict[str, str]]) -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    add(
        results,
        "AI",
        "AI source/check files",
        "Pass" if not missing else "Blocker",
        "router + app + worker + smoke/env checks present" if not missing else ", ".join(missing),
        "Keep managed_ai_router.py and production launch checks in the release branch.",
    )


def validate_contracts(results: List[Dict[str, str]]) -> None:
    router = read_text(ROOT / "managed_ai_router.py")
    app = read_text(ROOT / "app.py")
    missing_router = [symbol for symbol in REQUIRED_ROUTER_SYMBOLS if symbol not in router]
    missing_app = missing_items(REQUIRED_APP_TOKENS, app)
    add(
        results,
        "AI",
        "Managed AI router API",
        "Pass" if not missing_router else "Blocker",
        "route selection + client + SSRF guard symbols present" if not missing_router else ", ".join(missing_router),
        "Keep BYO, managed AI, platform OpenAI fallback, and base-URL validation APIs stable.",
    )
    add(
        results,
        "AI",
        "App AI integration",
        "Pass" if not missing_app else "Blocker",
        "translation + QA call paths use managed_ai_router" if not missing_app else ", ".join(missing_app),
        "Keep Pro translation and AI QA routed through managed_ai_router.",
    )
    security_tokens = ["ipaddress", "socket", "_blocked_host_reason", "169.254.169.254", "_is_placeholder_url"]
    missing_security = missing_items(security_tokens, router)
    add(
        results,
        "AI",
        "Managed AI URL safety",
        "Pass" if not missing_security else "Blocker",
        "private/local/metadata URL guards present" if not missing_security else ", ".join(missing_security),
        "Keep SSRF protections for OpenAI-compatible base URLs before accepting BYO or managed endpoints.",
    )


def validate_requirements(results: List[Dict[str, str]]) -> None:
    requirements = read_text(ROOT / "requirements.txt").lower()
    missing = [package for package in ["openai", "requests"] if package not in requirements]
    add(
        results,
        "AI",
        "AI Python dependencies",
        "Pass" if not missing else "Blocker",
        "openai + requests listed" if not missing else ", ".join(missing),
        "Keep OpenAI SDK and HTTP client dependencies in requirements.txt.",
    )


def validate_templates(results: List[Dict[str, str]]) -> None:
    env_template = read_text(ENV_TEMPLATE_PATH)
    streamlit_template = read_text(STREAMLIT_TEMPLATE_PATH)
    missing_env = missing_items(REQUIRED_TEMPLATE_KEYS, env_template)
    missing_streamlit = missing_items(REQUIRED_TEMPLATE_KEYS, streamlit_template)
    add(
        results,
        "AI",
        "Production env AI keys",
        "Pass" if not missing_env else "Warn",
        "fallback + managed AI keys listed" if not missing_env else ", ".join(missing_env),
        "Keep deploy/.env.production.example aligned with AI fallback settings.",
    )
    add(
        results,
        "AI",
        "Streamlit AI secret keys",
        "Pass" if not missing_streamlit else "Warn",
        "fallback + managed AI keys listed" if not missing_streamlit else ", ".join(missing_streamlit),
        "Keep Streamlit-hosted deployments aware of AI fallback settings.",
    )


def validate_env_config(results: List[Dict[str, str]], env_path: Path) -> Optional[Dict[str, str]]:
    if not env_path.exists():
        add(results, "AI Config", "Production env file", "Blocker", "missing", "Create deploy/.env.production from the non-secret template.")
        return None
    env = parse_env_file(env_path)
    openai_ready = openai_key_ready(env.get("OPENAI_API_KEY", ""))
    managed_enabled = env_bool(env, "ERRORSWEEP_MANAGED_AI_ENABLED")
    managed_base_url = safe_text(env.get("ERRORSWEEP_MANAGED_AI_BASE_URL"))
    managed_ready = managed_enabled and https_public_url(managed_base_url)
    add(
        results,
        "AI Config",
        "Production AI fallback route",
        "Pass" if openai_ready or managed_ready else "Blocker",
        "platform OpenAI" if openai_ready else "managed AI" if managed_ready else "missing",
        "Set OPENAI_API_KEY or enable a live HTTPS public OpenAI-compatible managed AI endpoint; use --write-ai-env for repeatable setup.",
    )
    add(
        results,
        "AI Config",
        "OpenAI API key",
        "Pass" if openai_ready else "Warn",
        nonsecret_evidence("OPENAI_API_KEY", env.get("OPENAI_API_KEY", "")),
        "Set OPENAI_API_KEY for platform fallback with --write-ai-env --ai-route openai, or keep a managed route fully configured.",
    )
    default_model = safe_text(env.get("ERRORSWEEP_OPENAI_DEFAULT_MODEL") or env.get("OPENAI_MODEL"))
    add(
        results,
        "AI Config",
        "OpenAI default model",
        "Pass" if default_model and not is_placeholder(default_model) else "Warn",
        default_model or "missing",
        "Set ERRORSWEEP_OPENAI_DEFAULT_MODEL for predictable platform fallback behavior.",
    )
    add(
        results,
        "AI Config",
        "Managed AI enabled flag",
        "Pass" if managed_enabled or openai_ready else "Warn",
        "enabled" if managed_enabled else "disabled",
        "Enable ERRORSWEEP_MANAGED_AI_ENABLED only when a managed OpenAI-compatible endpoint is live, or rely on OPENAI_API_KEY.",
    )
    if managed_enabled or managed_base_url:
        add(
            results,
            "AI Config",
            "Managed AI base URL",
            "Pass" if https_public_url(managed_base_url) else "Blocker",
            nonsecret_evidence("ERRORSWEEP_MANAGED_AI_BASE_URL", managed_base_url),
            "Set ERRORSWEEP_MANAGED_AI_BASE_URL to a live public HTTPS OpenAI-compatible /v1 base URL.",
        )
        managed_api_key = safe_text(env.get("ERRORSWEEP_MANAGED_AI_API_KEY"))
        status = "Pass" if configured_secret(managed_api_key, min_length=8) else ("Warn" if openai_ready else "Blocker")
        add(
            results,
            "AI Config",
            "Managed AI API key",
            status,
            nonsecret_evidence("ERRORSWEEP_MANAGED_AI_API_KEY", managed_api_key),
            "Set the managed AI bearer/API token, especially when managed AI is the primary route.",
        )
        managed_model = safe_text(env.get("ERRORSWEEP_MANAGED_AI_MODEL"))
        add(
            results,
            "AI Config",
            "Managed AI model",
            "Pass" if managed_model and not is_placeholder(managed_model) else "Warn",
            managed_model or "missing",
            "Set ERRORSWEEP_MANAGED_AI_MODEL to the deployed model name.",
        )
    gemini_key = safe_text(env.get("GEMINI_API_KEY"))
    add(
        results,
        "AI Config",
        "Gemini optional route",
        "Pass" if configured_secret(gemini_key, min_length=12) else "Warn",
        nonsecret_evidence("GEMINI_API_KEY", gemini_key),
        "Configure GEMINI_API_KEY only if Gemini OpenAI-compatible routing will be offered as a platform-managed option.",
    )
    return env


def route_from_env(env: Dict[str, str]) -> Dict[str, str]:
    if env_bool(env, "ERRORSWEEP_MANAGED_AI_ENABLED") and https_public_url(env.get("ERRORSWEEP_MANAGED_AI_BASE_URL", "")):
        return {
            "provider": "managed_ai",
            "base_url": normalize_openai_base_url(env.get("ERRORSWEEP_MANAGED_AI_BASE_URL", "")),
            "api_key": safe_text(env.get("ERRORSWEEP_MANAGED_AI_API_KEY") or "errorsweep-managed-token"),
            "model": safe_text(env.get("ERRORSWEEP_MANAGED_AI_MODEL") or "errorsweep-managed"),
        }
    if openai_key_ready(env.get("OPENAI_API_KEY", "")):
        return {
            "provider": "openai_platform",
            "base_url": "https://api.openai.com/v1",
            "api_key": safe_text(env.get("OPENAI_API_KEY")),
            "model": safe_text(env.get("ERRORSWEEP_OPENAI_DEFAULT_MODEL") or env.get("OPENAI_MODEL") or "gpt-4o-mini"),
        }
    return {}


def probe_models(results: List[Dict[str, str]], env: Dict[str, str], timeout: int) -> None:
    route = route_from_env(env)
    if not route:
        add(results, "AI Probe", "Models probe", "Blocker", "no configured route", "Configure platform OpenAI or managed AI before probing.")
        return
    try:
        response = requests.get(
            f"{route['base_url'].rstrip('/')}/models",
            headers={"Authorization": f"Bearer {route['api_key']}"},
            timeout=min(timeout, 30),
        )
        add(
            results,
            "AI Probe",
            "Models probe",
            "Pass" if response.status_code < 500 else "Warn",
            f"{route['provider']} HTTP {response.status_code}",
            "Verify the configured OpenAI-compatible route exposes /models from the deployment environment.",
        )
    except Exception as exc:
        add(results, "AI Probe", "Models probe", "Warn", safe_text(exc)[:220], "Check AI DNS, TLS, firewall, auth token, and /models compatibility.")


def probe_chat(results: List[Dict[str, str]], env: Dict[str, str], timeout: int) -> None:
    route = route_from_env(env)
    if not route:
        add(results, "AI Probe", "Chat completion probe", "Blocker", "no configured route", "Configure platform OpenAI or managed AI before probing chat completions.")
        return
    payload = {
        "model": route["model"],
        "messages": [
            {"role": "system", "content": "Return only JSON."},
            {"role": "user", "content": '{"items":[{"ok":true}]}'},
        ],
        "temperature": 0,
        "max_tokens": 40,
    }
    try:
        response = requests.post(
            f"{route['base_url'].rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {route['api_key']}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        status = "Pass" if response.status_code < 400 else "Blocker"
        evidence = f"{route['provider']} HTTP {response.status_code}"
        if response.status_code < 400:
            data = response.json() if response.content else {}
            choices = data.get("choices") if isinstance(data, dict) else []
            status = "Pass" if choices else "Blocker"
            evidence = "chat completion returned" if choices else "empty completion"
        add(results, "AI Probe", "Chat completion probe", status, evidence, "Verify the configured model can handle launch smoke chat-completion requests.")
    except Exception as exc:
        add(results, "AI Probe", "Chat completion probe", "Blocker", safe_text(exc)[:220], "Check AI /chat/completions compatibility, model name, auth token, and timeout.")


def collect_results(
    env_path: Optional[Path] = None,
    *,
    probe_models_enabled: bool = False,
    probe_chat_enabled: bool = False,
    timeout: int = 60,
) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    validate_files(results)
    validate_contracts(results)
    validate_requirements(results)
    validate_templates(results)

    env: Optional[Dict[str, str]] = None
    if env_path is not None:
        env = validate_env_config(results, env_path)
    if probe_models_enabled:
        if env is None:
            add(results, "AI Probe", "Models probe configuration", "Blocker", "no env file", "Pass --env-file deploy/.env.production before --probe-models.")
        else:
            probe_models(results, env, timeout)
    if probe_chat_enabled:
        if env is None:
            add(results, "AI Probe", "Chat probe configuration", "Blocker", "no env file", "Pass --env-file deploy/.env.production before --probe-chat.")
        else:
            probe_chat(results, env, timeout)
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
        "# ErrorSweep AI Fallback Check",
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


def read_required_secret_env(name: str, label: str) -> str:
    env_name = safe_text(name)
    if not env_name:
        raise ValueError(f"Set --{label}.")
    value = safe_text(os.environ.get(env_name, ""))
    if not value:
        raise ValueError(f"{env_name} is not set or is empty.")
    return value


def write_ai_env(args: argparse.Namespace) -> int:
    env_path = Path(args.env_file) if args.env_file else DEFAULT_ENV_PATH
    route = safe_text(args.ai_route).lower()
    model = safe_text(args.model) or "gpt-4o-mini"
    updates: Dict[str, str] = {"ERRORSWEEP_OPENAI_DEFAULT_MODEL": model}
    try:
        if route == "openai":
            openai_key = read_required_secret_env(args.openai_key_env, "openai-key-env")
            if not openai_key_ready(openai_key):
                raise ValueError("OpenAI fallback key must look like a production OpenAI API key starting with sk-.")
            updates.update(
                {
                    "OPENAI_API_KEY": openai_key,
                    "ERRORSWEEP_MANAGED_AI_ENABLED": "false",
                    "ERRORSWEEP_MANAGED_AI_BASE_URL": "",
                    "ERRORSWEEP_MANAGED_AI_API_KEY": "",
                }
            )
        elif route == "managed":
            managed_base_url = normalize_openai_base_url(args.managed_base_url)
            if not https_public_url(managed_base_url):
                raise ValueError("--managed-base-url must be a public HTTPS OpenAI-compatible base URL.")
            managed_api_key = read_required_secret_env(args.managed_api_key_env, "managed-api-key-env")
            managed_model = safe_text(args.managed_model) or safe_text(args.model) or "errorsweep-managed"
            if not configured_secret(managed_api_key, min_length=8):
                raise ValueError("Managed AI API key must be at least 8 non-placeholder characters.")
            if not managed_model or is_placeholder(managed_model):
                raise ValueError("Managed AI model must be a non-placeholder model name.")
            updates.update(
                {
                    "OPENAI_API_KEY": "",
                    "ERRORSWEEP_MANAGED_AI_ENABLED": "true",
                    "ERRORSWEEP_MANAGED_AI_BASE_URL": managed_base_url,
                    "ERRORSWEEP_MANAGED_AI_API_KEY": managed_api_key,
                    "ERRORSWEEP_MANAGED_AI_MODEL": managed_model,
                }
            )
        else:
            raise ValueError("--ai-route must be either openai or managed.")
        write_env_updates(env_path, updates)
    except Exception as exc:
        print(safe_text(exc), file=sys.stderr)
        return 1

    payload = {
        "env_file": str(env_path),
        "route": route,
        "updated": sorted(updates.keys()),
        "model": updates.get("ERRORSWEEP_MANAGED_AI_MODEL") or updates.get("ERRORSWEEP_OPENAI_DEFAULT_MODEL") or model,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Updated {env_path}")
        print(f"AI fallback route: {route}")
        print(f"Model: {payload['model']}")
        print("Secrets were read from environment variables and were not printed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ErrorSweep production AI fallback launch readiness.")
    parser.add_argument("--env-file", default="", help="Production env file to validate. Omit for offline code/template checks.")
    parser.add_argument("--write-ai-env", action="store_true", help="Write production AI fallback settings into the env file from environment variables.")
    parser.add_argument("--ai-route", choices=["openai", "managed"], default="openai", help="AI fallback route to write with --write-ai-env.")
    parser.add_argument("--openai-key-env", default="", help="Environment variable containing OPENAI_API_KEY for the platform fallback route.")
    parser.add_argument("--model", default="", help="Default OpenAI-compatible model name for the selected route.")
    parser.add_argument("--managed-base-url", default="", help="Public HTTPS OpenAI-compatible /v1 base URL for the managed route.")
    parser.add_argument("--managed-api-key-env", default="", help="Environment variable containing the managed AI bearer/API token.")
    parser.add_argument("--managed-model", default="", help="Managed AI model name for the managed route.")
    parser.add_argument("--probe-models", action="store_true", help="Probe the configured OpenAI-compatible /models route.")
    parser.add_argument("--probe-chat", action="store_true", help="Run one tiny chat-completions probe against the configured route.")
    parser.add_argument("--timeout", type=int, default=60, help="Endpoint probe timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    if args.write_ai_env:
        return write_ai_env(args)

    env_path = Path(args.env_file) if args.env_file else None
    results = sorted(
        collect_results(
            env_path=env_path,
            probe_models_enabled=args.probe_models,
            probe_chat_enabled=args.probe_chat,
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
