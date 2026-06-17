"""Validate CogniSweep object-storage launch readiness.

Offline mode checks that the adapter, templates, and dependencies cover the
supported production providers. Use --env-file to validate a real production
configuration, and --probe-write only after a staging/production bucket exists.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / "deploy" / ".env.production"
ADAPTER_PATH = ROOT / "cloud_object_storage.py"
ENV_TEMPLATE_PATH = ROOT / "deploy" / ".env.production.example"
STREAMLIT_TEMPLATE_PATH = ROOT / ".streamlit" / "secrets.toml.example"
REQUIREMENTS_PATH = ROOT / "requirements.txt"

PRODUCTION_PROVIDERS = {"supabase", "s3", "gcs"}
ALL_PROVIDERS = PRODUCTION_PROVIDERS | {"local"}
REQUIRED_ADAPTER_SYMBOLS = [
    "object_storage_provider",
    "object_storage_bucket",
    "local_object_storage_root",
    "build_object_key",
    "put_file",
    "signed_url_for_key",
    "object_storage_status",
]
REQUIRED_TEMPLATE_KEYS = [
    "ERRORSWEEP_OBJECT_STORAGE_PROVIDER",
    "ERRORSWEEP_OBJECT_STORAGE_ALLOW_PUBLIC_URLS",
    "SUPABASE_STORAGE_BUCKET",
    "S3_BUCKET",
    "AWS_REGION",
    "S3_ENDPOINT_URL",
    "GCS_BUCKET",
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
SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|KEY|SERVICE_ACCOUNT|CREDENTIAL)", re.IGNORECASE)


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


def key_present(env: Dict[str, str], names: Sequence[str]) -> bool:
    return any(name in env and safe_text(env.get(name)) != "" and not is_placeholder(safe_text(env.get(name))) for name in names)


def value_for(env: Dict[str, str], names: Sequence[str]) -> str:
    for name in names:
        value = safe_text(env.get(name))
        if value:
            return value
    return ""


def validate_adapter(results: List[Dict[str, str]]) -> None:
    adapter = read_text(ADAPTER_PATH)
    add(
        results,
        "Storage",
        "Object storage adapter",
        "Pass" if adapter else "Blocker",
        "available" if adapter else "missing",
        "Restore cloud_object_storage.py.",
    )
    if not adapter:
        return

    missing_symbols = [symbol for symbol in REQUIRED_ADAPTER_SYMBOLS if f"def {symbol}" not in adapter]
    add(
        results,
        "Storage",
        "Adapter API surface",
        "Pass" if not missing_symbols else "Blocker",
        "required functions present" if not missing_symbols else ", ".join(missing_symbols),
        "Keep the object-storage adapter functions available for uploads, signed URLs, and health checks.",
    )

    missing_providers = [provider for provider in ALL_PROVIDERS if f'"{provider}"' not in adapter and f"'{provider}'" not in adapter]
    add(
        results,
        "Storage",
        "Provider implementation coverage",
        "Pass" if not missing_providers else "Blocker",
        "local + Supabase + S3 + GCS" if not missing_providers else ", ".join(missing_providers),
        "Keep local fallback plus Supabase Storage, S3, and GCS branches implemented.",
    )


def validate_templates(results: List[Dict[str, str]]) -> None:
    env_template = read_text(ENV_TEMPLATE_PATH)
    streamlit_template = read_text(STREAMLIT_TEMPLATE_PATH)
    missing_env = missing_items(REQUIRED_TEMPLATE_KEYS, env_template)
    missing_streamlit = missing_items(["ERRORSWEEP_OBJECT_STORAGE_PROVIDER", "ERRORSWEEP_OBJECT_STORAGE_ALLOW_PUBLIC_URLS", "SUPABASE_STORAGE_BUCKET", "S3_BUCKET", "GCS_BUCKET"], streamlit_template)
    add(
        results,
        "Storage",
        "Production env storage keys",
        "Pass" if not missing_env else "Warn",
        "provider-specific keys listed" if not missing_env else ", ".join(missing_env),
        "Keep deploy/.env.production.example aligned with supported object-storage providers.",
    )
    add(
        results,
        "Storage",
        "Streamlit storage secret keys",
        "Pass" if not missing_streamlit else "Warn",
        "provider-specific keys listed" if not missing_streamlit else ", ".join(missing_streamlit),
        "Keep .streamlit/secrets.toml.example aligned for Streamlit-hosted deployments.",
    )


def validate_requirements(results: List[Dict[str, str]]) -> None:
    packages = {requirement_name(line) for line in read_text(REQUIREMENTS_PATH).splitlines()}
    packages.discard("")
    required = ["requests", "boto3", "google-cloud-storage"]
    missing = [package for package in required if package not in packages]
    add(
        results,
        "Storage",
        "Storage provider dependencies",
        "Pass" if not missing else "Blocker",
        "requests, boto3, google-cloud-storage present" if not missing else ", ".join(missing),
        "Keep HTTP, S3, and GCS dependencies in requirements.txt.",
    )


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
    ready = bool(value) and not is_placeholder(value) and len(value) >= min_length
    add(results, area, check, "Pass" if ready else status_when_missing, nonsecret_evidence(names[0], value), action)


def validate_env_config(results: List[Dict[str, str]], env_path: Path) -> Optional[Dict[str, str]]:
    if not env_path.exists():
        add(results, "Storage", "Production env file", "Blocker", "missing", "Create deploy/.env.production from the non-secret template.")
        return None

    env = parse_env_file(env_path)
    provider = safe_text(env.get("ERRORSWEEP_OBJECT_STORAGE_PROVIDER")).lower()
    add(
        results,
        "Storage",
        "Production storage provider",
        "Pass" if provider in PRODUCTION_PROVIDERS else "Blocker",
        provider or "missing",
        "Set ERRORSWEEP_OBJECT_STORAGE_PROVIDER to supabase, s3, or gcs before public multi-instance launch.",
    )

    if provider == "supabase":
        require_value(results, env, "Storage", "Supabase storage bucket", ["SUPABASE_STORAGE_BUCKET"], "Create and set the production Supabase Storage bucket; use deploy/supabase_schema_check.py --write-supabase-env for Supabase-backed storage.")
        add(
            results,
            "Storage",
            "Supabase project URL",
            "Pass" if https_url(safe_text(env.get("SUPABASE_URL"))) else "Blocker",
            nonsecret_evidence("SUPABASE_URL", safe_text(env.get("SUPABASE_URL"))),
            "Set SUPABASE_URL to the production Supabase project URL; use deploy/supabase_schema_check.py --write-supabase-env.",
        )
        require_value(results, env, "Storage", "Supabase service role key", ["SUPABASE_SERVICE_ROLE_KEY"], "Set SUPABASE_SERVICE_ROLE_KEY for server-side storage writes; use deploy/supabase_schema_check.py --write-supabase-env.", min_length=24)
    elif provider == "s3":
        require_value(results, env, "Storage", "S3 bucket", ["S3_BUCKET"], "Set S3_BUCKET for production object storage.")
        require_value(results, env, "Storage", "AWS region", ["AWS_REGION", "AWS_DEFAULT_REGION"], "Set AWS_REGION/AWS_DEFAULT_REGION for S3.", status_when_missing="Warn")
        if key_present(env, ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_ROLE_ARN"]):
            add(results, "Storage", "S3 credentials or role", "Pass", "configured", "Use least-privilege write/read/delete access for the selected bucket prefix.")
        else:
            add(results, "Storage", "S3 credentials or role", "Warn", "not explicit", "Use instance role, web identity, or injected AWS credentials in the runtime environment.")
    elif provider == "gcs":
        require_value(results, env, "Storage", "GCS bucket", ["GCS_BUCKET"], "Set GCS_BUCKET for production object storage.")
        if key_present(env, ["GOOGLE_APPLICATION_CREDENTIALS", "GCP_SERVICE_ACCOUNT_JSON"]):
            add(results, "Storage", "GCS credentials", "Pass", "configured", "Use least-privilege write/read/delete access for the selected bucket prefix.")
        else:
            add(results, "Storage", "GCS credentials", "Warn", "not explicit", "Use workload identity or injected service-account credentials in the runtime environment.")

    return env


def apply_env_for_probe(env: Dict[str, str]) -> Dict[str, Optional[str]]:
    previous: Dict[str, Optional[str]] = {}
    for key, value in env.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    return previous


def restore_env(previous: Dict[str, Optional[str]]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def cleanup_probe_object(provider: str, env: Dict[str, str], key: str, manifest: Dict[str, Any]) -> str:
    if provider == "local":
        path = Path(safe_text(manifest.get("storage_key") or key))
        if path.exists() and path.is_file():
            path.unlink()
        return "removed"
    if provider == "supabase":
        import requests

        base_url = safe_text(env.get("SUPABASE_URL")).rstrip("/")
        bucket = safe_text(env.get("SUPABASE_STORAGE_BUCKET"))
        service_key = safe_text(env.get("SUPABASE_SERVICE_ROLE_KEY"))
        response = requests.delete(
            f"{base_url}/storage/v1/object/{bucket}",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
            },
            json={"prefixes": [key]},
            timeout=30,
        )
        response.raise_for_status()
        return "removed"
    if provider == "s3":
        import boto3

        client_kwargs: Dict[str, Any] = {}
        if safe_text(env.get("S3_ENDPOINT_URL")):
            client_kwargs["endpoint_url"] = safe_text(env.get("S3_ENDPOINT_URL"))
        if safe_text(env.get("AWS_REGION") or env.get("AWS_DEFAULT_REGION")):
            client_kwargs["region_name"] = safe_text(env.get("AWS_REGION") or env.get("AWS_DEFAULT_REGION"))
        boto3.client("s3", **client_kwargs).delete_object(Bucket=safe_text(env.get("S3_BUCKET")), Key=key)
        return "removed"
    if provider == "gcs":
        from google.cloud import storage

        storage.Client().bucket(safe_text(env.get("GCS_BUCKET"))).blob(key).delete()
        return "removed"
    return "not_applicable"


def probe_write(results: List[Dict[str, str]], env: Dict[str, str]) -> None:
    provider = safe_text(env.get("ERRORSWEEP_OBJECT_STORAGE_PROVIDER")).lower()
    if provider not in PRODUCTION_PROVIDERS:
        add(results, "Storage Probe", "Write/readiness probe", "Blocker", provider or "missing", "Configure a cloud object-storage provider before probing writes.")
        return

    previous = apply_env_for_probe(env)
    key = ""
    manifest: Dict[str, Any] = {}
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from cloud_object_storage import build_object_key, put_file, signed_url_for_key

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
            handle.write("errorsweep object storage launch probe\n")
            temp_path = Path(handle.name)
        try:
            key = build_object_key("Launch Probe", "storage_check", datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"), "object-storage-probe.txt")
            manifest = put_file(temp_path, key, mimetypes.guess_type(temp_path.name)[0] or "text/plain")
            signed_url = safe_text(signed_url_for_key(key, expires_in=300))
            add(
                results,
                "Storage Probe",
                "Probe upload",
                "Pass" if safe_text(manifest.get("status")) == "stored" else "Blocker",
                f"{provider} / {safe_text(manifest.get('storage_bucket')) or 'bucket'}",
                "Verify staging/prod uploads can write through the configured object-storage adapter.",
            )
            add(
                results,
                "Storage Probe",
                "Probe signed URL",
                "Pass" if signed_url.startswith("http") else "Warn",
                "generated" if signed_url else "missing",
                "Verify stored job attachments and media previews can produce download/preview URLs.",
            )
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as exc:
        add(results, "Storage Probe", "Write/readiness probe", "Blocker", safe_text(exc)[:220], "Check bucket credentials, permissions, network access, and provider SDK dependencies.")
    finally:
        try:
            if key:
                cleanup_result = cleanup_probe_object(provider, env, key, manifest)
                add(results, "Storage Probe", "Probe cleanup", "Pass", cleanup_result, "Keep the launch probe bucket prefix tidy after verification.")
        except Exception as exc:
            add(results, "Storage Probe", "Probe cleanup", "Warn", safe_text(exc)[:220], "Remove the tiny launch probe object manually if cleanup failed.")
        restore_env(previous)


def collect_results(env_path: Optional[Path] = None, probe_write_enabled: bool = False) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    validate_adapter(results)
    validate_templates(results)
    validate_requirements(results)

    env: Optional[Dict[str, str]] = None
    if env_path is not None:
        env = validate_env_config(results, env_path)
    if probe_write_enabled:
        if env is None:
            add(results, "Storage Probe", "Probe configuration", "Blocker", "no env file", "Pass --env-file deploy/.env.production before --probe-write.")
        else:
            probe_write(results, env)
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
        "# CogniSweep Object Storage Check",
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
    parser = argparse.ArgumentParser(description="Validate CogniSweep object-storage launch readiness.")
    parser.add_argument("--env-file", default="", help="Production env file to validate. Omit for offline adapter/template checks.")
    parser.add_argument("--probe-write", action="store_true", help="Upload, sign, and best-effort cleanup a tiny probe object.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    env_path = Path(args.env_file) if args.env_file else None
    results = sorted(
        collect_results(env_path=env_path, probe_write_enabled=args.probe_write),
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
