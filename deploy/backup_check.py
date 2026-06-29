"""Validate CogniSweep operational backup launch readiness.

Offline mode checks that the scheduled backup worker, supervisor wiring,
templates, and redaction safeguards are present. Use --env-file to validate a
real production configuration and --run-smoke to run a local dry-run backup.
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

try:
    from .checker_utils import aliases_for, cognisweep_env_alias, missing_items_with_aliases as missing_items
except ImportError:  # pragma: no cover - direct script execution
    from checker_utils import aliases_for, cognisweep_env_alias, missing_items_with_aliases as missing_items

ROOT = Path(__file__).resolve().parents[1]
ENV_TEMPLATE_PATH = ROOT / "deploy" / ".env.production.example"
STREAMLIT_TEMPLATE_PATH = ROOT / ".streamlit" / "secrets.toml.example"
COMPOSE_PATH = ROOT / "docker-compose.production.yml"
WORKER_PATH = ROOT / "operational_backup_worker.py"
SUPERVISOR_PATH = ROOT / "worker_supervisor.py"
PERSISTENCE_PATH = ROOT / "production_persistence.py"
STORAGE_PATH = ROOT / "cloud_object_storage.py"

REQUIRED_WORKER_SYMBOLS = [
    "BACKUP_SCHEMA_VERSION",
    "EXCLUDED_COLLECTIONS",
    "SENSITIVE_EXACT_KEYS",
    "configured_collections",
    "build_backup_payload",
    "redact_export_value",
    "run_backup",
    "maybe_store_object",
    "store_backup_manifest",
    "save_audit_event",
]
REQUIRED_TEMPLATE_KEYS = [
    "ERRORSWEEP_BACKUP_PROVIDER",
    "ERRORSWEEP_BACKUP_WORKER_ENABLED",
    "ERRORSWEEP_BACKUP_INTERVAL_HOURS",
    "ERRORSWEEP_BACKUP_RETENTION_DAYS",
    "ERRORSWEEP_BACKUP_OBJECT_STORAGE_ENABLED",
    "ERRORSWEEP_BACKUP_OUTPUT_DIR",
]
REQUIRED_COMPOSE_TOKENS = [
    "errorsweep-worker-supervisor:",
    "worker_supervisor.py",
    "ERRORSWEEP_SUPERVISOR_ENABLE_BACKUP_WORKER",
    "ERRORSWEEP_BACKUP_OUTPUT_DIR",
    "/data/errorsweep/backups",
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
SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|HASH|KEY|SERVICE_ROLE|CREDENTIAL)", re.IGNORECASE)


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
    value = value_for(env, [name])
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on", "enabled"}


def value_for(env: Dict[str, str], names: Sequence[str]) -> str:
    for name in names:
        for candidate in aliases_for(name):
            value = safe_text(env.get(candidate))
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


def require_positive_int(
    results: List[Dict[str, str]],
    env: Dict[str, str],
    area: str,
    check: str,
    name: str,
    action: str,
    *,
    minimum: int = 1,
    status_when_missing: str = "Blocker",
) -> None:
    value = value_for(env, [name])
    try:
        ready = int(value) >= minimum
    except (TypeError, ValueError):
        ready = False
    add(results, area, check, "Pass" if ready else status_when_missing, nonsecret_evidence(name, value), action)


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


def validate_files(results: List[Dict[str, str]]) -> None:
    missing = [
        str(path.relative_to(ROOT))
        for path in [WORKER_PATH, SUPERVISOR_PATH, PERSISTENCE_PATH, STORAGE_PATH]
        if not path.exists()
    ]
    add(
        results,
        "Backup",
        "Backup source files",
        "Pass" if not missing else "Blocker",
        "worker + supervisor + persistence + storage present" if not missing else ", ".join(missing),
        "Keep operational_backup_worker.py, worker_supervisor.py, production_persistence.py, and cloud_object_storage.py in the release branch.",
    )


def validate_worker_contract(results: List[Dict[str, str]]) -> None:
    worker = read_text(WORKER_PATH)
    if not worker:
        add(results, "Backup", "Backup worker contract", "Blocker", "missing", "Restore operational_backup_worker.py.")
        return

    missing_symbols = [symbol for symbol in REQUIRED_WORKER_SYMBOLS if symbol not in worker]
    add(
        results,
        "Backup",
        "Backup worker contract",
        "Pass" if not missing_symbols else "Blocker",
        "snapshot, redaction, manifest, audit, storage hooks present" if not missing_symbols else ", ".join(missing_symbols),
        "Keep the backup worker able to produce redacted snapshots, persist manifests, and write audit records.",
    )

    missing_redaction_tokens = missing_items(
        [
            "auth_tokens",
            "email",
            "password_hash",
            "phone_number",
            "service_role_key",
            "token_hash",
            "private_key",
            "[redacted]",
        ],
        worker,
    )
    add(
        results,
        "Backup",
        "Sensitive-data redaction coverage",
        "Pass" if not missing_redaction_tokens else "Blocker",
        "auth tokens excluded and sensitive fields redacted" if not missing_redaction_tokens else ", ".join(missing_redaction_tokens),
        "Backups must exclude auth tokens and redact secrets before any storage upload.",
    )


def validate_templates(results: List[Dict[str, str]]) -> None:
    env_template = read_text(ENV_TEMPLATE_PATH)
    streamlit_template = read_text(STREAMLIT_TEMPLATE_PATH)
    missing_env = missing_items(REQUIRED_TEMPLATE_KEYS, env_template)
    missing_streamlit = missing_items(
        [
            "ERRORSWEEP_BACKUP_WORKER_ENABLED",
            "ERRORSWEEP_BACKUP_PROVIDER",
            "ERRORSWEEP_BACKUP_RETENTION_DAYS",
        ],
        streamlit_template,
    )
    add(
        results,
        "Backup",
        "Production env backup keys",
        "Pass" if not missing_env else "Warn",
        "backup provider, schedule, retention, object storage keys listed" if not missing_env else ", ".join(missing_env),
        "Keep deploy/.env.production.example aligned with scheduled backup deployment settings.",
    )
    add(
        results,
        "Backup",
        "Streamlit backup secret keys",
        "Pass" if not missing_streamlit else "Warn",
        "backup readiness keys listed" if not missing_streamlit else ", ".join(missing_streamlit),
        "Keep .streamlit/secrets.toml.example aligned for Streamlit-hosted launch checks.",
    )


def validate_compose(results: List[Dict[str, str]]) -> None:
    compose = read_text(COMPOSE_PATH)
    missing = missing_items(REQUIRED_COMPOSE_TOKENS, compose)
    add(
        results,
        "Backup",
        "Compose backup service wiring",
        "Pass" if not missing else "Blocker",
        "supervisor backup worker, backup path, volumes wired" if not missing else ", ".join(missing),
        "Keep operational backups running under the worker supervisor with persistent data/log volumes.",
    )


def validate_env_config(results: List[Dict[str, str]], env_path: Path) -> Optional[Dict[str, str]]:
    if not env_path.exists():
        add(results, "Backup Config", "Production env file", "Blocker", "missing", "Create deploy/.env.production from the non-secret template.")
        return None
    env = parse_env_file(env_path)
    require_value(results, env, "Backup Config", "Backup provider", ["ERRORSWEEP_BACKUP_PROVIDER"], "Set the scheduled database/storage backup provider.")
    require_flag(results, env, "Backup Config", "Backup worker enabled", "ERRORSWEEP_BACKUP_WORKER_ENABLED", "Run operational_backup_worker.py as a managed service.")
    require_positive_int(results, env, "Backup Config", "Backup interval hours", "ERRORSWEEP_BACKUP_INTERVAL_HOURS", "Set a backup cadence in hours.", minimum=1, status_when_missing="Warn")
    require_positive_int(results, env, "Backup Config", "Backup retention days", "ERRORSWEEP_BACKUP_RETENTION_DAYS", "Set backup retention days.", minimum=1, status_when_missing="Warn")
    require_value(results, env, "Backup Config", "Backup output directory", ["ERRORSWEEP_BACKUP_OUTPUT_DIR"], "Set a persistent output directory mounted outside the ephemeral app filesystem.", status_when_missing="Warn")
    require_flag(results, env, "Backup Config", "Backup object-storage upload", "ERRORSWEEP_BACKUP_OBJECT_STORAGE_ENABLED", "Upload backup snapshots through the configured object-storage provider.", status_when_false="Warn")
    require_flag(results, env, "Backup Config", "Supervisor backup worker", "ERRORSWEEP_SUPERVISOR_ENABLE_BACKUP_WORKER", "Enable backup worker under worker_supervisor.py or deploy it as an equivalent managed job.", status_when_false="Warn")
    return env


def run_local_smoke(results: List[Dict[str, str]], timeout: int) -> None:
    with tempfile.TemporaryDirectory(prefix="errorsweep_backup_check_") as temp_dir:
        root = Path(temp_dir)
        env = os.environ.copy()
        env.update(
            {
                "ERRORSWEEP_EDITOR_JOB_DIR": str(root / "editor_jobs"),
                "ERRORSWEEP_OBJECT_STORAGE_PROVIDER": "local",
                "ERRORSWEEP_OBJECT_STORAGE_DIR": str(root / "object_storage"),
                "ERRORSWEEP_BACKUP_OUTPUT_DIR": str(root / "backups"),
                "ERRORSWEEP_BACKUP_OBJECT_STORAGE_ENABLED": "false",
            }
        )
        try:
            completed = subprocess.run(
                [sys.executable, "operational_backup_worker.py", "--once", "--dry-run", "--collections", "users,workspaces,files", "--limit", "3"],
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
                "Backup Smoke",
                "Backup worker dry run",
                "Pass" if completed.returncode == 0 else "Blocker",
                evidence,
                "Fix local backup dry-run failures before deploying scheduled backups.",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            add(results, "Backup Smoke", "Backup worker dry run", "Blocker", safe_text(exc)[:220], "Run operational_backup_worker.py --once --dry-run manually and inspect logs.")


def collect_results(env_path: Optional[Path] = None, *, run_smoke: bool = False, timeout: int = 60) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    validate_files(results)
    validate_worker_contract(results)
    validate_templates(results)
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
        "# CogniSweep Backup Check",
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
    parser = argparse.ArgumentParser(description="Validate CogniSweep operational backup launch readiness.")
    parser.add_argument("--env-file", default="", help="Production env file to validate. Omit for offline worker/template checks.")
    parser.add_argument("--run-smoke", action="store_true", help="Run a local backup worker dry-run smoke check.")
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
