"""Validate ErrorSweep built-in MT endpoint launch readiness.

Offline mode checks the router, clients, worker servers, templates, tests, and
requirements. Use --env-file for production endpoint validation, --probe-health
for live /health checks, and --probe-translate after hosted endpoints are
reachable.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / "deploy" / ".env.production"
ENV_TEMPLATE_PATH = ROOT / "deploy" / ".env.production.example"
STREAMLIT_TEMPLATE_PATH = ROOT / ".streamlit" / "secrets.toml.example"

REQUIRED_FILES = [
    "translator_router.py",
    "selfhosted_mt_clients.py",
    "opus_mt_server_v45.py",
    "indictrans2_worker.py",
    "madlad_mt_server.py",
    "start_builtin_mt.ps1",
    "test_builtin_mt_engines.py",
    "test_opus_mt_endpoint.py",
    "test_indictrans2_worker.py",
    "test_madlad_endpoint.py",
]
REQUIRED_DOCS = [
    "README_v45_opus_mt_endpoint.md",
    "README_indictrans2_setup.md",
    "README_madlad400_endpoint.md",
]
REQUIRED_ROUTER_SYMBOLS = [
    "builtin_engine_status",
    "smoke_test_builtin_engines",
    "translate_batch",
    "_endpoint_health_url",
]
REQUIRED_CLIENT_SYMBOLS = [
    "translate_with_indictrans2",
    "translate_with_madlad",
    "translate_with_opus_mt",
    "normalize_endpoint",
    "protect_text",
    "restore_text",
]
SERVER_CONTRACT_TOKENS = {
    "opus_mt_server_v45.py": ["FastAPI", '@app.get("/health")', '@app.post("/translate")', "SERVER_API_KEY"],
    "indictrans2_worker.py": ["FastAPI", '@app.get("/health")', '@app.post("/translate")', "SERVER_API_KEY"],
    "madlad_mt_server.py": ["FastAPI", '@app.get("/health")', '@app.post("/translate")', "SERVER_API_KEY"],
}
REQUIREMENT_FILES = {
    "OPUS-MT": "requirements_opus_mt_server.txt",
    "IndicTrans2": "requirements_indictrans2_worker.txt",
    "MADLAD-400": "requirements_madlad_mt_server.txt",
}
REQUIRED_TEMPLATE_KEYS = [
    "INDICTRANS2_ENDPOINT",
    "MADLAD_ENDPOINT",
    "OPUS_MT_ENDPOINT",
    "SELF_HOSTED_MT_TIMEOUT",
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
SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|KEY|API_KEY)", re.IGNORECASE)

ENGINE_ENV = {
    "OPUS-MT": {
        "endpoint": "OPUS_MT_ENDPOINT",
        "api_key": "OPUS_MT_API_KEY",
        "required": True,
        "source_language": "English",
        "target_language": "Spanish",
        "texts": ["Save changes"],
    },
    "IndicTrans2": {
        "endpoint": "INDICTRANS2_ENDPOINT",
        "api_key": "INDICTRANS2_API_KEY",
        "required": True,
        "source_language": "eng_Latn",
        "target_language": "tel_Telu",
        "texts": ["Save changes"],
    },
    "MADLAD-400": {
        "endpoint": "MADLAD_ENDPOINT",
        "api_key": "MADLAD_API_KEY",
        "required": False,
        "source_language": "English",
        "target_language": "Spanish",
        "texts": ["Save changes"],
    },
}


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


def endpoint_health_url(endpoint: str) -> str:
    endpoint = safe_text(endpoint).rstrip("/")
    return endpoint[:-10] + "/health" if endpoint.endswith("/translate") else endpoint + "/health"


def validate_files(results: List[Dict[str, str]]) -> None:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    add(
        results,
        "MT",
        "MT source/test files",
        "Pass" if not missing else "Blocker",
        "router + clients + workers + tests present" if not missing else ", ".join(missing),
        "Keep router, client, worker, startup, and endpoint test files in the release branch.",
    )
    missing_docs = [path for path in REQUIRED_DOCS if not (ROOT / path).exists()]
    add(
        results,
        "MT",
        "MT setup docs",
        "Pass" if not missing_docs else "Warn",
        "OPUS, IndicTrans2, MADLAD setup docs present" if not missing_docs else ", ".join(missing_docs),
        "Keep setup docs for each self-hosted MT worker with the deployment pack.",
    )


def validate_contracts(results: List[Dict[str, str]]) -> None:
    router = read_text(ROOT / "translator_router.py")
    client = read_text(ROOT / "selfhosted_mt_clients.py")
    missing_router = [symbol for symbol in REQUIRED_ROUTER_SYMBOLS if f"def {symbol}" not in router]
    missing_client = [symbol for symbol in REQUIRED_CLIENT_SYMBOLS if f"def {symbol}" not in client]
    add(
        results,
        "MT",
        "Router API",
        "Pass" if not missing_router else "Blocker",
        "required functions present" if not missing_router else ", ".join(missing_router),
        "Keep built-in MT diagnostics, smoke tests, and translate_batch routing APIs stable.",
    )
    add(
        results,
        "MT",
        "Self-hosted client API",
        "Pass" if not missing_client else "Blocker",
        "required functions present" if not missing_client else ", ".join(missing_client),
        "Keep endpoint normalization, placeholder protection, and provider clients available.",
    )
    for rel_path, tokens in SERVER_CONTRACT_TOKENS.items():
        text = read_text(ROOT / rel_path)
        missing = missing_items(tokens, text)
        add(
            results,
            "MT",
            f"{rel_path} HTTP contract",
            "Pass" if not missing else "Blocker",
            "/health + /translate + auth support" if not missing else ", ".join(missing),
            "Keep every self-hosted MT worker exposing /health and /translate with optional bearer auth.",
        )


def validate_requirements(results: List[Dict[str, str]]) -> None:
    for engine, rel_path in REQUIREMENT_FILES.items():
        path = ROOT / rel_path
        packages = {requirement_name(line) for line in read_text(path).splitlines()}
        packages.discard("")
        missing = [package for package in ["fastapi", "uvicorn", "pydantic", "transformers", "requests"] if package not in packages]
        add(
            results,
            "MT",
            f"{engine} requirements",
            "Pass" if path.exists() and not missing else "Blocker",
            f"{len(packages)} package(s)" if path.exists() and not missing else "missing file" if not path.exists() else ", ".join(missing),
            "Keep worker-specific requirements files complete for separate MT deployments.",
        )


def validate_templates(results: List[Dict[str, str]]) -> None:
    env_template = read_text(ENV_TEMPLATE_PATH)
    streamlit_template = read_text(STREAMLIT_TEMPLATE_PATH)
    missing_env = missing_items(REQUIRED_TEMPLATE_KEYS, env_template)
    missing_streamlit = missing_items(REQUIRED_TEMPLATE_KEYS, streamlit_template)
    add(
        results,
        "MT",
        "Production env MT keys",
        "Pass" if not missing_env else "Warn",
        "endpoint keys listed" if not missing_env else ", ".join(missing_env),
        "Keep deploy/.env.production.example aligned with self-hosted MT endpoint settings.",
    )
    add(
        results,
        "MT",
        "Streamlit MT secret keys",
        "Pass" if not missing_streamlit else "Warn",
        "endpoint keys listed" if not missing_streamlit else ", ".join(missing_streamlit),
        "Keep Streamlit-hosted deployments aware of self-hosted MT endpoint settings.",
    )


def env_bool(env: Dict[str, str], name: str, default: bool = False) -> bool:
    value = safe_text(env.get(name))
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def validate_env_config(results: List[Dict[str, str]], env_path: Path, require_madlad: bool) -> Optional[Dict[str, str]]:
    if not env_path.exists():
        add(results, "MT Config", "Production env file", "Blocker", "missing", "Create deploy/.env.production from the non-secret template.")
        return None
    env = parse_env_file(env_path)
    for engine, config in ENGINE_ENV.items():
        endpoint_key = config["endpoint"]
        endpoint = safe_text(env.get(endpoint_key))
        required = bool(config["required"]) or (engine == "MADLAD-400" and require_madlad)
        status_when_missing = "Blocker" if required else "Warn"
        add(
            results,
            "MT Config",
            f"{engine} endpoint",
            "Pass" if https_url(endpoint) else status_when_missing,
            nonsecret_evidence(endpoint_key, endpoint),
            f"Set {endpoint_key} to a live HTTPS /translate endpoint.",
        )
    timeout_value = safe_text(env.get("SELF_HOSTED_MT_TIMEOUT"))
    try:
        timeout_ok = int(timeout_value or "0") >= 120
    except Exception:
        timeout_ok = False
    add(
        results,
        "MT Config",
        "Self-hosted MT timeout",
        "Pass" if timeout_ok else "Warn",
        timeout_value or "missing",
        "Set SELF_HOSTED_MT_TIMEOUT to at least 120 seconds for model-backed workers.",
    )
    madlad_endpoint_ready = https_url(safe_text(env.get("MADLAD_ENDPOINT")))
    madlad_disabled = env_bool(env, "SELF_HOSTED_MT_DISABLE_MADLAD", False)
    madlad_gpu_approved = env_bool(env, "ERRORSWEEP_MADLAD_GPU_APPROVED", False)
    if madlad_endpoint_ready and not madlad_disabled:
        add(
            results,
            "MT Config",
            "MADLAD GPU decision",
            "Pass" if madlad_gpu_approved else "Warn",
            "approved" if madlad_gpu_approved else "not recorded",
            "Set ERRORSWEEP_MADLAD_GPU_APPROVED=true only after approving GPU-backed MADLAD capacity, or disable/defer MADLAD.",
        )
    return env


def probe_health(results: List[Dict[str, str]], env: Dict[str, str], timeout: int, require_madlad: bool) -> None:
    for engine, config in ENGINE_ENV.items():
        endpoint = safe_text(env.get(config["endpoint"]))
        required = bool(config["required"]) or (engine == "MADLAD-400" and require_madlad)
        status_when_failed = "Blocker" if required else "Warn"
        if not https_url(endpoint):
            add(results, "MT Probe", f"{engine} health", status_when_failed, "endpoint not configured", f"Configure {config['endpoint']} before probing health.")
            continue
        try:
            response = requests.get(endpoint_health_url(endpoint), timeout=timeout)
            add(
                results,
                "MT Probe",
                f"{engine} health",
                "Pass" if response.status_code < 500 else status_when_failed,
                f"HTTP {response.status_code}",
                f"Verify {engine} /health is reachable from the deployment environment.",
            )
        except Exception as exc:
            add(results, "MT Probe", f"{engine} health", status_when_failed, safe_text(exc)[:220], f"Check {engine} DNS, TLS, firewall, model startup, and service health.")


def probe_translate(results: List[Dict[str, str]], env: Dict[str, str], timeout: int, require_madlad: bool) -> None:
    for engine, config in ENGINE_ENV.items():
        endpoint = safe_text(env.get(config["endpoint"]))
        required = bool(config["required"]) or (engine == "MADLAD-400" and require_madlad)
        status_when_failed = "Blocker" if required else "Warn"
        if not https_url(endpoint):
            add(results, "MT Probe", f"{engine} translation", status_when_failed, "endpoint not configured", f"Configure {config['endpoint']} before probing translation.")
            continue
        headers = {"Content-Type": "application/json"}
        api_key = safe_text(env.get(config["api_key"]))
        if api_key and not is_placeholder(api_key):
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "source_language": config["source_language"],
            "target_language": config["target_language"],
            "texts": config["texts"],
        }
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            detail = f"HTTP {response.status_code}"
            status = "Pass" if response.status_code < 400 else status_when_failed
            if response.status_code < 400:
                data = response.json() if response.content else {}
                translations = data.get("translations") or data.get("items") or data.get("outputs") or []
                status = "Pass" if translations else status_when_failed
                detail = "translation returned" if translations else "empty translation"
            add(results, "MT Probe", f"{engine} translation", status, detail, f"Verify {engine} can translate the launch smoke segment.")
        except Exception as exc:
            add(results, "MT Probe", f"{engine} translation", status_when_failed, safe_text(exc)[:220], f"Check {engine} /translate contract, auth token, model loading, and timeout.")


def run_router_smoke(results: List[Dict[str, str]], timeout: int) -> None:
    command = [sys.executable, "test_builtin_mt_engines.py"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
        output = completed.stdout or completed.stderr or ""
        evidence = "; ".join(line for line in output.splitlines()[:3] if line)[:220] or f"exit {completed.returncode}"
        add(
            results,
            "MT Smoke",
            "Router smoke script",
            "Pass" if completed.returncode == 0 else "Warn",
            evidence,
            "Run this with live hosted MT endpoints and review per-engine output before launch.",
        )
    except Exception as exc:
        add(results, "MT Smoke", "Router smoke script", "Warn", safe_text(exc)[:220], "Run test_builtin_mt_engines.py manually after endpoints are reachable.")


def collect_results(
    env_path: Optional[Path] = None,
    *,
    probe_health_enabled: bool = False,
    probe_translate_enabled: bool = False,
    run_router_smoke_enabled: bool = False,
    require_madlad: bool = False,
    timeout: int = 120,
) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    validate_files(results)
    validate_contracts(results)
    validate_requirements(results)
    validate_templates(results)

    env: Optional[Dict[str, str]] = None
    if env_path is not None:
        env = validate_env_config(results, env_path, require_madlad=require_madlad)
    if probe_health_enabled:
        if env is None:
            add(results, "MT Probe", "Health probe configuration", "Blocker", "no env file", "Pass --env-file deploy/.env.production before --probe-health.")
        else:
            probe_health(results, env, min(timeout, 30), require_madlad=require_madlad)
    if probe_translate_enabled:
        if env is None:
            add(results, "MT Probe", "Translation probe configuration", "Blocker", "no env file", "Pass --env-file deploy/.env.production before --probe-translate.")
        else:
            probe_translate(results, env, timeout, require_madlad=require_madlad)
    if run_router_smoke_enabled:
        run_router_smoke(results, timeout)
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
        "# ErrorSweep MT Endpoint Check",
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
    parser = argparse.ArgumentParser(description="Validate ErrorSweep built-in MT endpoint launch readiness.")
    parser.add_argument("--env-file", default="", help="Production env file to validate. Omit for offline code/template checks.")
    parser.add_argument("--probe-health", action="store_true", help="Probe configured MT endpoint /health routes.")
    parser.add_argument("--probe-translate", action="store_true", help="Run one direct /translate probe per configured MT endpoint.")
    parser.add_argument("--run-router-smoke", action="store_true", help="Run test_builtin_mt_engines.py.")
    parser.add_argument("--require-madlad", action="store_true", help="Treat MADLAD-400 as required instead of optional.")
    parser.add_argument("--timeout", type=int, default=120, help="Endpoint probe timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    env_path = Path(args.env_file) if args.env_file else None
    results = sorted(
        collect_results(
            env_path=env_path,
            probe_health_enabled=args.probe_health,
            probe_translate_enabled=args.probe_translate,
            run_router_smoke_enabled=args.run_router_smoke,
            require_madlad=args.require_madlad,
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
