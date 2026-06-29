"""CogniSweep production worker supervisor.

This script is a lightweight process supervisor for the background services
CogniSweep needs outside Streamlit: async QA/Pro processing, transactional email
dispatch, operational backups, and optionally the billing webhook receiver.

It is intentionally small and dependency-free so it can run on Windows, Linux,
or a simple VM/container before teams adopt a platform-native process manager.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app_runtime_config import runtime_env

LOGGER = logging.getLogger("errorsweep.worker_supervisor")


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def env(name: str, default: str = "") -> str:
    return runtime_env(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on", "enabled"}


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name, str(default)))
    except (TypeError, ValueError):
        return default


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def log_root() -> Path:
    configured = env("ERRORSWEEP_SUPERVISOR_LOG_DIR")
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / "errorsweep_worker_supervisor"
    root.mkdir(parents=True, exist_ok=True)
    return root


def status_path() -> Path:
    configured = env("ERRORSWEEP_SUPERVISOR_STATUS_FILE")
    return Path(configured) if configured else log_root() / "worker_supervisor_status.json"


@dataclass
class ServiceSpec:
    name: str
    script: str
    args: List[str]
    enabled: bool
    description: str
    restart: bool = True
    min_restart_seconds: int = 5
    process: Optional[subprocess.Popen] = None
    restarts: int = 0
    last_exit_code: Optional[int] = None
    started_at: str = ""
    last_start_at: float = 0.0
    stdout_log: str = ""
    stderr_log: str = ""
    command: List[str] = field(default_factory=list)

    def exists(self) -> bool:
        return (repo_root() / self.script).exists()

    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        if not self.exists():
            return "missing"
        if self.process is None:
            return "not_started"
        code = self.process.poll()
        if code is None:
            return "running"
        return "exited"

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "script": self.script,
            "script_exists": self.exists(),
            "status": self.status(),
            "pid": self.process.pid if self.process and self.process.poll() is None else None,
            "last_exit_code": self.last_exit_code,
            "restarts": self.restarts,
            "started_at": self.started_at,
            "stdout_log": self.stdout_log,
            "stderr_log": self.stderr_log,
            "command": self.command,
        }


def python_executable() -> str:
    configured = env("ERRORSWEEP_SUPERVISOR_PYTHON")
    return configured or sys.executable


def service_specs() -> List[ServiceSpec]:
    async_enabled = env_bool("ERRORSWEEP_SUPERVISOR_ENABLE_ASYNC_PROCESSOR", env_bool("ERRORSWEEP_ASYNC_PROCESSOR_ENABLED", False))
    email_enabled = env_bool("ERRORSWEEP_SUPERVISOR_ENABLE_EMAIL_WORKER", env_bool("ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED", False))
    backup_enabled = env_bool("ERRORSWEEP_SUPERVISOR_ENABLE_BACKUP_WORKER", env_bool("ERRORSWEEP_BACKUP_WORKER_ENABLED", False))
    billing_enabled = env_bool("ERRORSWEEP_SUPERVISOR_ENABLE_BILLING_RECEIVER", env_bool("ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_ENABLED", False))
    return [
        ServiceSpec(
            name="async_processor",
            script="async_workflow_processor.py",
            args=["--loop", "--interval", str(env_int("ERRORSWEEP_ASYNC_PROCESSOR_INTERVAL", 10))],
            enabled=async_enabled,
            description="Processes queued QA/Pro worker payloads.",
        ),
        ServiceSpec(
            name="email_dispatch",
            script="email_dispatch_worker.py",
            args=["--interval", str(env_int("ERRORSWEEP_EMAIL_WORKER_INTERVAL_SECONDS", 60))],
            enabled=email_enabled,
            description="Sends queued transactional email notifications.",
        ),
        ServiceSpec(
            name="operational_backup",
            script="operational_backup_worker.py",
            args=["--interval-hours", str(env_int("ERRORSWEEP_BACKUP_INTERVAL_HOURS", 24))],
            enabled=backup_enabled,
            description="Creates redacted operational backup snapshots.",
        ),
        ServiceSpec(
            name="billing_webhook_receiver",
            script="billing_webhook_receiver.py",
            args=[],
            enabled=billing_enabled,
            description="Receives Stripe/Razorpay billing webhooks.",
        ),
    ]


def write_status(specs: List[ServiceSpec], state: str = "running") -> Dict[str, Any]:
    payload = {
        "service": "errorsweep-worker-supervisor",
        "state": state,
        "generated_at": now_iso(),
        "repo": str(repo_root()),
        "log_dir": str(log_root()),
        "services": [spec.snapshot() for spec in specs],
    }
    path = status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, path)
    return payload


def open_logs(spec: ServiceSpec) -> Dict[str, Any]:
    root = log_root()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    spec.stdout_log = str(root / f"{spec.name}_{stamp}.out.log")
    spec.stderr_log = str(root / f"{spec.name}_{stamp}.err.log")
    return {
        "stdout": open(spec.stdout_log, "ab", buffering=0),
        "stderr": open(spec.stderr_log, "ab", buffering=0),
    }


def start_service(spec: ServiceSpec) -> None:
    if not spec.enabled or not spec.exists():
        return
    command = [python_executable(), str(repo_root() / spec.script), *spec.args]
    log_handles = open_logs(spec)
    spec.command = command
    spec.started_at = now_iso()
    spec.last_start_at = time.time()
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    spec.process = subprocess.Popen(
        command,
        cwd=str(repo_root()),
        stdout=log_handles["stdout"],
        stderr=log_handles["stderr"],
        creationflags=flags,
    )
    LOGGER.info("Started %s pid=%s", spec.name, spec.process.pid)


def stop_service(spec: ServiceSpec, timeout: int = 12) -> None:
    proc = spec.process
    if proc is None or proc.poll() is not None:
        return
    LOGGER.info("Stopping %s pid=%s", spec.name, proc.pid)
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        LOGGER.warning("Killing %s pid=%s after timeout", spec.name, proc.pid)
        proc.kill()
        proc.wait(timeout=5)
    spec.last_exit_code = proc.returncode


def run_supervisor(specs: List[ServiceSpec], poll_seconds: int) -> int:
    stop_requested = False

    def request_stop(signum: int, _frame: Any) -> None:
        nonlocal stop_requested
        LOGGER.info("Received signal %s; stopping services.", signum)
        stop_requested = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, request_stop)
        except (OSError, RuntimeError, ValueError) as exc:
            LOGGER.debug("Unable to install signal handler for %s: %s", sig, exc)

    for spec in specs:
        start_service(spec)
    write_status(specs)

    try:
        while not stop_requested:
            for spec in specs:
                if not spec.enabled or not spec.exists() or spec.process is None:
                    continue
                code = spec.process.poll()
                if code is None:
                    continue
                spec.last_exit_code = code
                LOGGER.warning("%s exited with code %s", spec.name, code)
                if spec.restart and time.time() - spec.last_start_at >= max(1, spec.min_restart_seconds):
                    spec.restarts += 1
                    start_service(spec)
            write_status(specs)
            time.sleep(max(2, int(poll_seconds or 10)))
    finally:
        for spec in specs:
            stop_service(spec)
        write_status(specs, state="stopped")
    return 0


def smoke_specs(specs: List[ServiceSpec]) -> Dict[str, Any]:
    checks = []
    for spec in specs:
        checks.append({
            "name": spec.name,
            "enabled": spec.enabled,
            "script": spec.script,
            "script_exists": spec.exists(),
            "command": [python_executable(), str(repo_root() / spec.script), *spec.args],
        })
    result = {
        "generated_at": now_iso(),
        "enabled_count": sum(1 for spec in specs if spec.enabled),
        "missing_enabled": [spec.name for spec in specs if spec.enabled and not spec.exists()],
        "status_file": str(status_path()),
        "log_dir": str(log_root()),
        "checks": checks,
    }
    write_status(specs, state="smoke")
    return result


def read_status() -> Dict[str, Any]:
    path = status_path()
    if not path.exists():
        return {"available": False, "status_file": str(path), "message": "No supervisor status file found."}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["available"] = True
        payload["status_file"] = str(path)
        return payload
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return {"available": False, "status_file": str(path), "error": safe_text(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and monitor CogniSweep background workers.")
    parser.add_argument("--smoke", action="store_true", help="Validate supervisor configuration and write a status snapshot without starting services.")
    parser.add_argument("--status", action="store_true", help="Print the latest supervisor status snapshot.")
    parser.add_argument("--plan", action="store_true", help="Print configured service commands without starting services.")
    parser.add_argument("--poll-seconds", type=int, default=env_int("ERRORSWEEP_SUPERVISOR_POLL_SECONDS", 10))
    args = parser.parse_args()

    logging.basicConfig(level=env("ERRORSWEEP_SUPERVISOR_LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(message)s")
    specs = service_specs()
    if args.status:
        print(json.dumps(read_status(), ensure_ascii=False, indent=2, default=safe_text))
        return 0
    if args.smoke or args.plan:
        result = smoke_specs(specs)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=safe_text))
        return 1 if result.get("missing_enabled") else 0
    return run_supervisor(specs, args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
