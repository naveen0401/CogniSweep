"""Validate CogniSweep managed-MT posture.

Bundled local/self-hosted MT engines were retired. This checker keeps launch
docs honest by verifying the legacy engine files and env keys are gone while
allowing the managed Amazon Translate adapter to be enabled explicitly.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / "deploy" / ".env.production"
ENV_TEMPLATE_PATH = ROOT / "deploy" / ".env.production.example"
STREAMLIT_TEMPLATE_PATH = ROOT / ".streamlit" / "secrets.toml.example"
ROUTER_PATH = ROOT / "translator_router.py"

RETIRED_FILES = [
    "Dockerfile.opus-mt",
    "Dockerfile.indictrans2",
    "docker-compose.opus-mt.yml",
    "docker-compose.indictrans2.yml",
    "start_builtin_mt.ps1",
    "selfhosted_mt_clients.py",
    "local_translation_engine.py",
    "indictrans2_worker.py",
    "indictrans2_client.py",
    "opus_mt_server_v45.py",
    "opus_mt_client.py",
    "madlad_mt_server.py",
    "download_models.ps1",
    "model_checksums.sha256.example",
    "errorsweep_v44_self_hosted_mt_no_nllb_media_fix.zip",
    "README_v45_opus_mt_endpoint.md",
    "README_indictrans2_setup.md",
    "README_madlad400_endpoint.md",
    "requirements_opus_mt_server.txt",
    "requirements_indictrans2_worker.txt",
    "requirements_madlad_mt_server.txt",
    "test_builtin_mt_engines.py",
    "test_opus_mt_endpoint.py",
    "test_indictrans2_worker.py",
    "test_madlad_endpoint.py",
    "test_mt_server_hardening.py",
    "test_selfhosted_mt_client_security.py",
    "test_local_translation_engine_routes.py",
]

RETIRED_TOKENS = [
    "SELF_HOSTED_MT",
    "INDICTRANS2",
    "OPUS_MT",
    "MADLAD",
    "LIBRETRANSLATE",
    "LibreTranslate",
    "translate_with_generic_endpoint",
    "self_hosted_translate_batch",
]

REQUIRED_ROUTER_SYMBOLS = [
    "class TranslationRouteError",
    "def current_builtin_engine_label",
    "def builtin_engine_status",
    "def smoke_test_builtin_engines",
    "def translate_batch",
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


def missing_items(items: Iterable[str], text: str) -> List[str]:
    return [item for item in items if item not in text]


def legacy_keys_in_env(env: Dict[str, str]) -> List[str]:
    keys: List[str] = []
    patterns = ("SELF_HOSTED_MT", "INDICTRANS2", "OPUS_MT", "MADLAD")
    for key, value in env.items():
        upper_key = key.upper()
        if any(pattern in upper_key for pattern in patterns) and safe_text(value) and not is_placeholder(value):
            keys.append(key)
    return sorted(keys)


def validate_router(results: List[Dict[str, str]]) -> None:
    text = read_text(ROUTER_PATH)
    missing = missing_items(REQUIRED_ROUTER_SYMBOLS, text)
    add(
        results,
        "MT",
        "Router compatibility API",
        "Pass" if text and not missing else "Blocker",
        "stable API present" if text and not missing else ", ".join(missing) or "missing",
        "Keep translator_router.py import-compatible for Streamlit and async workers.",
    )
    forbidden_imports = [token for token in ("selfhosted_mt_clients", "local_translation_engine", "indictrans2_worker", "opus_mt", "madlad") if token in text]
    add(
        results,
        "MT",
        "Retired engine imports",
        "Pass" if not forbidden_imports else "Blocker",
        "none" if not forbidden_imports else ", ".join(forbidden_imports),
        "Do not reintroduce retired local/self-hosted MT engine imports.",
    )


def validate_retired_files(results: List[Dict[str, str]]) -> None:
    present = [path for path in RETIRED_FILES if (ROOT / path).exists()]
    add(
        results,
        "MT",
        "Retired engine files removed",
        "Pass" if not present else "Blocker",
        "removed" if not present else ", ".join(present),
        "Keep deleted IndicTrans2, OPUS-MT, MADLAD, Libre/local MT, model-download, and endpoint-test artifacts out of the release branch.",
    )


def validate_templates(results: List[Dict[str, str]]) -> None:
    combined = "\n".join([read_text(ENV_TEMPLATE_PATH), read_text(STREAMLIT_TEMPLATE_PATH)])
    active_text = "\n".join(
        line
        for line in combined.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    leaked_tokens = [token for token in RETIRED_TOKENS if token in active_text]
    add(
        results,
        "MT",
        "Retired env keys removed",
        "Pass" if not leaked_tokens else "Blocker",
        "removed" if not leaked_tokens else ", ".join(leaked_tokens),
        "Keep production templates free of retired local/self-hosted MT endpoint settings.",
    )
    managed_markers = ["COGNISWEEP_MT_PROVIDER", "COGNISWEEP_AWS_TRANSLATE_REGION"]
    missing = [marker for marker in managed_markers if marker not in combined]
    add(
        results,
        "MT",
        "Amazon Translate configuration placeholders",
        "Pass" if not missing else "Warn",
        "present" if not missing else ", ".join(missing),
        "Keep optional Amazon Translate provider and region settings documented.",
    )


def validate_env_config(results: List[Dict[str, str]], env_path: Path) -> Optional[Dict[str, str]]:
    if not env_path.exists():
        add(results, "MT Config", "Production env file", "Warn", "missing", "Skip live MT validation until a production env file exists.")
        return None
    env = parse_env_file(env_path)
    legacy_keys = legacy_keys_in_env(env)
    add(
        results,
        "MT Config",
        "Retired production MT keys",
        "Warn" if legacy_keys else "Pass",
        "configured: " + ", ".join(legacy_keys) if legacy_keys else "none",
        "Remove retired MT endpoint/key variables from deploy/.env.production; they are ignored by the app now.",
    )
    provider = safe_text(env.get("COGNISWEEP_MT_PROVIDER") or env.get("ERRORSWEEP_MT_PROVIDER") or "disabled").lower()
    add(
        results,
        "MT Config",
        "Managed MT provider",
        "Pass" if provider in {"disabled", "amazon_translate"} else "Warn",
        provider or "disabled",
        "Use disabled for Human Review only, or amazon_translate for entitled paid workspaces.",
    )
    if provider == "amazon_translate":
        region = safe_text(env.get("COGNISWEEP_AWS_TRANSLATE_REGION") or env.get("ERRORSWEEP_AWS_TRANSLATE_REGION") or env.get("AWS_REGION") or env.get("AWS_DEFAULT_REGION"))
        add(
            results,
            "MT Config",
            "Amazon Translate region",
            "Pass" if region else "Warn",
            region or "default ap-south-1 fallback",
            "Set COGNISWEEP_AWS_TRANSLATE_REGION/ERRORSWEEP_AWS_TRANSLATE_REGION for predictable AWS routing.",
        )
    return env


def collect_results(env_path: Optional[Path] = None) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    validate_router(results)
    validate_retired_files(results)
    validate_templates(results)
    if env_path is not None:
        validate_env_config(results, env_path)
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
        "# CogniSweep Managed MT Check",
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
    parser = argparse.ArgumentParser(description="Validate CogniSweep managed-MT posture.")
    parser.add_argument("--env-file", default="", help="Optional production env file to validate for retired MT keys.")
    parser.add_argument("--probe-health", action="store_true", help="Accepted for backward compatibility; no live MT endpoint is probed.")
    parser.add_argument("--probe-translate", action="store_true", help="Accepted for backward compatibility; no live MT endpoint is probed.")
    parser.add_argument("--run-router-smoke", action="store_true", help="Accepted for backward compatibility; no live MT endpoint is probed.")
    parser.add_argument("--require-madlad", action="store_true", help="Accepted for backward compatibility; MADLAD has been retired.")
    parser.add_argument("--timeout", type=int, default=120, help="Unused compatibility option.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    _ = (args.probe_health, args.probe_translate, args.run_router_smoke, args.require_madlad, args.timeout)
    env_path = Path(args.env_file) if args.env_file else None
    results = sorted(collect_results(env_path=env_path), key=lambda row: (status_rank(row["Status"]), row["Area"], row["Check"]))
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
