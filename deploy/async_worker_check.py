"""Validate ErrorSweep async worker launch readiness.

Offline mode checks that the queue adapter, HTTP receiver, QA/Pro processor,
supervisor, compose wiring, templates, and dependencies are present. Use
--env-file for production configuration validation and --run-smoke for local
receiver/processor/supervisor smoke checks.
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
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / "deploy" / ".env.production"
ENV_TEMPLATE_PATH = ROOT / "deploy" / ".env.production.example"
STREAMLIT_TEMPLATE_PATH = ROOT / ".streamlit" / "secrets.toml.example"
COMPOSE_PATH = ROOT / "docker-compose.production.yml"
REQUIREMENTS_PATH = ROOT / "requirements.txt"

REQUIRED_FILES = [
    "async_worker_queue.py",
    "async_task_worker.py",
    "async_workflow_processor.py",
    "worker_supervisor.py",
]
REQUIRED_QUEUE_SYMBOLS = [
    "async_backend_status",
    "enqueue_async_task",
    "_enqueue_http",
    "_enqueue_redis",
]
REQUIRED_RECEIVER_SYMBOLS = [
    "accept_task",
    "update_task_status",
    "smoke_check",
    "run_server",
]
REQUIRED_PROCESSOR_SYMBOLS = [
    "process_task_payload",
    "process_next_queued_task",
    "smoke_check",
]
REQUIRED_SUPERVISOR_SYMBOLS = [
    "service_specs",
    "smoke_specs",
    "run_supervisor",
]
REQUIRED_TEMPLATE_KEYS = [
    "ERRORSWEEP_ASYNC_WORKER_URL",
    "ERRORSWEEP_ASYNC_WORKER_TOKEN",
    "ERRORSWEEP_ASYNC_WORKER_SERVICE_ENABLED",
    "ERRORSWEEP_ASYNC_PROCESSOR_ENABLED",
    "ERRORSWEEP_WORKER_SUPERVISOR_ENABLED",
    "ERRORSWEEP_SUPERVISOR_ENABLE_ASYNC_PROCESSOR",
    "ERRORSWEEP_ASYNC_WORKER_DIR",
    "ERRORSWEEP_ASYNC_RESULT_DIR",
]
PLACEHOLDER_MARKERS = (
    "replace-with",
    "your-domain.com",
    "yourdomain.com",
    "your-project",
    "example.com",
    "placeholder",
    "changeme",
    "change-me",
)
SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|KEY)", re.IGNORECASE)


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


def env_bool(env: Dict[str, str], name: str, default: bool = False) -> bool:
    value = safe_text(env.get(name))
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def value_for(env: Dict[str, str], names: Sequence[str]) -> str:
    for name in names:
        value = safe_text(env.get(name))
        if value:
            return value
    return ""


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
    ready = bool(value) and not is_placeholder(value) and len(value) >= min_length
    add(results, area, check, "Pass" if ready else status_when_missing, nonsecret_evidence(names[0], value), action)


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
    value = safe_text(env.get(name))
    add(results, area, check, "Pass" if env_bool(env, name) else status_when_false, "enabled" if env_bool(env, name) else value or "missing", action)


def http_url_ready(value: str) -> bool:
    if is_placeholder(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_files(results: List[Dict[str, str]]) -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    add(
        results,
        "Async",
        "Worker source files",
        "Pass" if not missing else "Blocker",
        "receiver + queue + processor + supervisor present" if not missing else ", ".join(missing),
        "Keep async queue, receiver, processor, and supervisor source files in the deployment branch.",
    )


def validate_symbols(results: List[Dict[str, str]]) -> None:
    checks = [
        ("Queue adapter API", ROOT / "async_worker_queue.py", REQUIRED_QUEUE_SYMBOLS),
        ("Receiver API", ROOT / "async_task_worker.py", REQUIRED_RECEIVER_SYMBOLS),
        ("Workflow processor API", ROOT / "async_workflow_processor.py", REQUIRED_PROCESSOR_SYMBOLS),
        ("Supervisor API", ROOT / "worker_supervisor.py", REQUIRED_SUPERVISOR_SYMBOLS),
    ]
    for label, path, symbols in checks:
        text = read_text(path)
        missing = [symbol for symbol in symbols if f"def {symbol}" not in text]
        add(
            results,
            "Async",
            label,
            "Pass" if not missing else "Blocker",
            "required functions present" if not missing else ", ".join(missing),
            "Keep the async worker contracts stable for Streamlit handoff, receiver status, and processor execution.",
        )


def validate_templates(results: List[Dict[str, str]]) -> None:
    env_template = read_text(ENV_TEMPLATE_PATH)
    streamlit_template = read_text(STREAMLIT_TEMPLATE_PATH)
    missing_env = missing_items(REQUIRED_TEMPLATE_KEYS, env_template)
    missing_streamlit = missing_items(
        [
            "ERRORSWEEP_ASYNC_WORKER_URL",
            "ERRORSWEEP_ASYNC_WORKER_TOKEN",
            "ERRORSWEEP_ASYNC_WORKER_SERVICE_ENABLED",
            "ERRORSWEEP_ASYNC_PROCESSOR_ENABLED",
            "ERRORSWEEP_WORKER_SUPERVISOR_ENABLED",
        ],
        streamlit_template,
    )
    add(
        results,
        "Async",
        "Production env async keys",
        "Pass" if not missing_env else "Warn",
        "receiver/processor/supervisor keys listed" if not missing_env else ", ".join(missing_env),
        "Keep deploy/.env.production.example aligned with async worker deployment settings.",
    )
    add(
        results,
        "Async",
        "Streamlit async secret keys",
        "Pass" if not missing_streamlit else "Warn",
        "handoff keys listed" if not missing_streamlit else ", ".join(missing_streamlit),
        "Keep Streamlit-hosted deployments aware of async handoff settings.",
    )


def validate_requirements(results: List[Dict[str, str]]) -> None:
    packages = {requirement_name(line) for line in read_text(REQUIREMENTS_PATH).splitlines()}
    packages.discard("")
    missing = [package for package in ["requests", "redis", "pandas", "openpyxl"] if package not in packages]
    add(
        results,
        "Async",
        "Worker dependencies",
        "Pass" if not missing else "Blocker",
        "requests, redis, pandas, openpyxl present" if not missing else ", ".join(missing),
        "Keep HTTP, Redis, dataframe, and Excel dependencies available to worker services.",
    )


def validate_compose(results: List[Dict[str, str]]) -> None:
    compose = read_text(COMPOSE_PATH)
    required_tokens = [
        "errorsweep-async-receiver:",
        "errorsweep-worker-supervisor:",
        "async_task_worker.py",
        "worker_supervisor.py",
        "ERRORSWEEP_ASYNC_WORKER_SERVICE_ENABLED",
        "ERRORSWEEP_SUPERVISOR_ENABLE_ASYNC_PROCESSOR",
        "8300:8300",
        "http://127.0.0.1:8300/health",
        "errorsweep-data:",
        "errorsweep-logs:",
    ]
    missing = missing_items(required_tokens, compose)
    add(
        results,
        "Async",
        "Compose async service wiring",
        "Pass" if not missing else "Blocker",
        "receiver, supervisor, healthcheck, volumes wired" if not missing else ", ".join(missing),
        "Keep the async receiver and worker supervisor split from the Streamlit app in production compose.",
    )


def validate_env_config(results: List[Dict[str, str]], env_path: Path) -> Optional[Dict[str, str]]:
    if not env_path.exists():
        add(results, "Async Config", "Production env file", "Blocker", "missing", "Create deploy/.env.production from the non-secret template.")
        return None
    env = parse_env_file(env_path)
    worker_url = safe_text(env.get("ERRORSWEEP_ASYNC_WORKER_URL"))
    redis_url = safe_text(env.get("REDIS_URL") or env.get("CELERY_BROKER_URL"))
    backend = safe_text(env.get("ERRORSWEEP_ASYNC_BACKEND")).lower()
    http_ready = http_url_ready(worker_url)
    redis_ready = bool(redis_url) and not is_placeholder(redis_url)
    external_ready = http_ready or redis_ready

    add(
        results,
        "Async Config",
        "External async backend",
        "Pass" if external_ready else "Blocker",
        "http" if http_ready else "redis" if redis_ready else backend or "missing",
        "Configure ERRORSWEEP_ASYNC_WORKER_URL for the HTTP receiver or REDIS_URL/CELERY_BROKER_URL for a Redis queue.",
    )
    if http_ready:
        require_value(results, env, "Async Config", "Worker bearer token", ["ERRORSWEEP_ASYNC_WORKER_TOKEN"], "Set a shared bearer token for HTTP worker requests.", min_length=16)
        require_flag(results, env, "Async Config", "Receiver service enabled", "ERRORSWEEP_ASYNC_WORKER_SERVICE_ENABLED", "Set ERRORSWEEP_ASYNC_WORKER_SERVICE_ENABLED=true when the HTTP receiver is deployed.")
    if redis_ready:
        add(results, "Async Config", "Redis queue URL", "Pass", "configured", "Use TLS/authenticated Redis for production queues where possible.")
    require_flag(results, env, "Async Config", "Async processor enabled", "ERRORSWEEP_ASYNC_PROCESSOR_ENABLED", "Run async_workflow_processor.py --loop as a managed service.")
    require_flag(results, env, "Async Config", "Worker supervisor enabled", "ERRORSWEEP_WORKER_SUPERVISOR_ENABLED", "Run worker_supervisor.py or document an equivalent platform process manager.", status_when_false="Warn")
    require_flag(results, env, "Async Config", "Supervisor async processor", "ERRORSWEEP_SUPERVISOR_ENABLE_ASYNC_PROCESSOR", "Enable the async processor in the supervisor or deploy it separately.", status_when_false="Warn")
    return env


def run_subprocess_smoke(command: Sequence[str], env_updates: Dict[str, str], timeout: int) -> Dict[str, Any]:
    env = os.environ.copy()
    env.update(env_updates)
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = completed.stdout or completed.stderr or ""
    detail = ""
    try:
        parsed = json.loads(output)
        detail = safe_text(parsed.get("final_status") or parsed.get("state") or parsed.get("enabled_count") or parsed.get("task_id") or "ok")
    except Exception:
        detail = "; ".join(line for line in output.splitlines()[:2] if line)[:220] or f"exit {completed.returncode}"
    return {"returncode": completed.returncode, "detail": detail}


def run_local_smokes(results: List[Dict[str, str]], timeout: int) -> None:
    with tempfile.TemporaryDirectory(prefix="errorsweep_async_check_") as temp_dir:
        root = Path(temp_dir)
        env_updates = {
            "ERRORSWEEP_EDITOR_JOB_DIR": str(root / "editor_jobs"),
            "ERRORSWEEP_ASYNC_WORKER_DIR": str(root / "async_worker"),
            "ERRORSWEEP_ASYNC_RESULT_DIR": str(root / "async_results"),
            "ERRORSWEEP_SUPERVISOR_LOG_DIR": str(root / "supervisor_logs"),
            "ERRORSWEEP_SUPERVISOR_STATUS_FILE": str(root / "supervisor_status.json"),
            "ERRORSWEEP_ASYNC_PROCESSOR_ENABLED": "true",
            "ERRORSWEEP_SUPERVISOR_ENABLE_ASYNC_PROCESSOR": "true",
            "ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED": "false",
            "ERRORSWEEP_BACKUP_WORKER_ENABLED": "false",
        }
        checks = [
            ("Receiver smoke", [sys.executable, "async_task_worker.py", "--smoke"]),
            ("Processor smoke", [sys.executable, "async_workflow_processor.py", "--smoke"]),
            ("Supervisor smoke", [sys.executable, "worker_supervisor.py", "--smoke"]),
        ]
        for label, command in checks:
            try:
                result = run_subprocess_smoke(command, env_updates, timeout)
                add(
                    results,
                    "Async Smoke",
                    label,
                    "Pass" if result["returncode"] == 0 else "Blocker",
                    result["detail"],
                    "Fix local worker smoke failures before deploying the async services.",
                )
            except Exception as exc:
                add(results, "Async Smoke", label, "Blocker", safe_text(exc)[:220], "Run the worker smoke command manually and inspect logs.")


def health_url_for_worker(worker_url: str) -> str:
    url = worker_url.rstrip("/")
    if url.endswith("/tasks"):
        url = url[:-6]
    return f"{url}/health"


def probe_health(results: List[Dict[str, str]], env: Dict[str, str], timeout: int) -> None:
    import requests

    worker_url = safe_text(env.get("ERRORSWEEP_ASYNC_WORKER_URL"))
    if not http_url_ready(worker_url):
        add(results, "Async Probe", "Receiver health", "Blocker", "worker URL missing", "Set ERRORSWEEP_ASYNC_WORKER_URL before probing receiver health.")
        return
    try:
        response = requests.get(health_url_for_worker(worker_url), timeout=timeout)
        status = "Pass" if response.status_code < 500 else "Blocker"
        evidence = f"HTTP {response.status_code}"
        if response.status_code in {401, 403}:
            status = "Warn"
            evidence += " auth-gated"
        add(results, "Async Probe", "Receiver health", status, evidence, "Verify async_task_worker.py is reachable at /health from the deployment environment.")
    except Exception as exc:
        add(results, "Async Probe", "Receiver health", "Blocker", safe_text(exc)[:220], "Check async receiver URL, DNS, TLS, firewall, and service health.")


def collect_results(
    env_path: Optional[Path] = None,
    *,
    run_smoke: bool = False,
    probe_health_enabled: bool = False,
    timeout: int = 120,
) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    validate_files(results)
    validate_symbols(results)
    validate_templates(results)
    validate_requirements(results)
    validate_compose(results)

    env: Optional[Dict[str, str]] = None
    if env_path is not None:
        env = validate_env_config(results, env_path)
    if run_smoke:
        run_local_smokes(results, timeout)
    if probe_health_enabled:
        if env is None:
            add(results, "Async Probe", "Probe configuration", "Blocker", "no env file", "Pass --env-file deploy/.env.production before --probe-health.")
        else:
            probe_health(results, env, min(timeout, 30))
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
        "# ErrorSweep Async Worker Check",
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
    parser = argparse.ArgumentParser(description="Validate ErrorSweep async worker launch readiness.")
    parser.add_argument("--env-file", default="", help="Production env file to validate. Omit for offline adapter/template checks.")
    parser.add_argument("--run-smoke", action="store_true", help="Run local receiver, processor, and supervisor smoke checks.")
    parser.add_argument("--probe-health", action="store_true", help="Probe the configured HTTP async receiver /health endpoint.")
    parser.add_argument("--timeout", type=int, default=120, help="Smoke/probe timeout in seconds.")
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
