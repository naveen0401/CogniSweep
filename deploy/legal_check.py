"""Validate CogniSweep legal and compliance launch readiness.

Offline mode checks public legal routes, policy copy hooks, legal versioning,
consent capture, privacy request/export support, subprocessor tracking, schema
coverage, and template keys. Use --env-file for production legal-review flag
validation and --probe-public after a staging/public app URL is reachable.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

try:
    from .checker_utils import aliases_for, cognisweep_env_alias, missing_items_with_aliases as missing_items
except ImportError:  # pragma: no cover - direct script execution
    from checker_utils import aliases_for, cognisweep_env_alias, missing_items_with_aliases as missing_items

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"
SCHEMA_PATH = ROOT / "supabase_v42_release_schema.sql"
ENV_TEMPLATE_PATH = ROOT / "deploy" / ".env.production.example"
STREAMLIT_TEMPLATE_PATH = ROOT / ".streamlit" / "secrets.toml.example"

LEGAL_ROUTES = ["terms", "privacy", "security", "cookies", "dpa"]
REQUIRED_APP_SYMBOLS = [
    "LEGAL_VERSION_DEFAULTS",
    "legal_version_defaults",
    "legal_versions",
    "set_legal_versions",
    "compliance_ack_label",
    "consent_versions_are_current",
    "record_consent_acceptance",
    "render_public_document",
    "render_legal_version_panel",
    "workspace_privacy_export_payload",
    "render_privacy_request_tracker",
    "subprocessor_register_state",
    "subprocessor_runtime_rows",
    "subprocessor_launch_summary",
]
REQUIRED_PUBLIC_ROUTE_TOKENS = [
    '"terms"',
    '"privacy"',
    '"security"',
    '"cookies"',
    '"dpa"',
    "Terms of Service",
    "Privacy Policy",
    "Security",
    "Cookie Notice",
    "Data Processing Addendum",
]
REQUIRED_SCHEMA_TOKENS = [
    "create table if not exists public.errorsweep_platform_settings",
    "create table if not exists public.errorsweep_privacy_requests",
    "create table if not exists public.errorsweep_consent_records",
    "alter table public.errorsweep_platform_settings enable row level security",
    "alter table public.errorsweep_privacy_requests enable row level security",
    "alter table public.errorsweep_consent_records enable row level security",
]
REQUIRED_TEMPLATE_TOKENS = [
    "ERRORSWEEP_LEGAL_REVIEWED",
    "ERRORSWEEP_WAF_PROVIDER",
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
SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|HASH|KEY|SERVICE_ROLE|USERNAME|WORKSPACE|ORG)", re.IGNORECASE)


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


def nonsecret_evidence(key: str, value: str) -> str:
    if not safe_text(value):
        return "missing"
    if is_placeholder(value):
        return "placeholder"
    if SENSITIVE_KEY_RE.search(key):
        return "configured"
    return value


def https_url(value: str) -> bool:
    if is_placeholder(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def with_query(base_url: str, params: Dict[str, str]) -> str:
    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(params)
    return urlunparse(parsed._replace(query=urlencode(query)))


def validate_app_contract(results: List[Dict[str, str]]) -> None:
    app = read_text(APP_PATH)
    missing_symbols = [symbol for symbol in REQUIRED_APP_SYMBOLS if symbol not in app]
    missing_routes = missing_items(REQUIRED_PUBLIC_ROUTE_TOKENS, app)
    version_tokens = [
        '"terms_version"',
        '"privacy_version"',
        '"nda_version"',
        '"cookie_version"',
        '"dpa_version"',
    ]
    missing_versions = missing_items(version_tokens, app)

    add(
        results,
        "Legal",
        "Legal app contract",
        "Pass" if app and not missing_symbols else "Blocker",
        "public docs, versions, consent, privacy, subprocessor hooks present" if app and not missing_symbols else ", ".join(missing_symbols) or "missing app.py",
        "Keep public legal routes, version controls, consent capture, privacy workflows, and subprocessors wired in app.py.",
    )
    add(
        results,
        "Legal",
        "Public legal document coverage",
        "Pass" if not missing_routes else "Blocker",
        "Terms, Privacy, Security, Cookie Notice, and DPA routes present" if not missing_routes else ", ".join(missing_routes),
        "Keep every public legal document route available before public signup.",
    )
    add(
        results,
        "Legal",
        "Legal version coverage",
        "Pass" if not missing_versions else "Blocker",
        "terms/privacy/NDA/cookie/DPA versions tracked" if not missing_versions else ", ".join(missing_versions),
        "Track active legal document versions so users can re-accept updated policies.",
    )

    if "Draft policy text" in app and "Replace with reviewed legal documents before public launch" in app:
        add(
            results,
            "Legal",
            "Draft policy warning",
            "Pass",
            "draft warning present",
            "Keep visible draft warning until lawyer-reviewed documents replace the placeholder copy.",
        )
    else:
        add(
            results,
            "Legal",
            "Draft policy warning",
            "Warn",
            "missing",
            "Add a clear warning if public legal copy is still draft text.",
        )


def validate_schema(results: List[Dict[str, str]]) -> None:
    schema = read_text(SCHEMA_PATH).lower()
    missing = [token for token in REQUIRED_SCHEMA_TOKENS if token.lower() not in schema]
    add(
        results,
        "Legal",
        "Compliance schema coverage",
        "Pass" if schema and not missing else "Blocker",
        "platform settings, privacy requests, consent records, and RLS present" if schema and not missing else ", ".join(missing) or "missing schema",
        "Keep Supabase release schema aligned with legal versions, privacy requests, consent records, and RLS.",
    )


def validate_templates(results: List[Dict[str, str]]) -> None:
    env_template = read_text(ENV_TEMPLATE_PATH)
    streamlit_template = read_text(STREAMLIT_TEMPLATE_PATH)
    missing_env = missing_items(REQUIRED_TEMPLATE_TOKENS, env_template)
    missing_streamlit = missing_items(REQUIRED_TEMPLATE_TOKENS, streamlit_template)
    add(
        results,
        "Legal",
        "Production env legal keys",
        "Pass" if not missing_env else "Warn",
        "legal review and WAF keys listed" if not missing_env else ", ".join(missing_env),
        "Keep deploy/.env.production.example aligned with legal approval and edge security flags.",
    )
    add(
        results,
        "Legal",
        "Streamlit legal secret keys",
        "Pass" if not missing_streamlit else "Warn",
        "legal review and WAF keys listed" if not missing_streamlit else ", ".join(missing_streamlit),
        "Keep .streamlit/secrets.toml.example aligned for hosted deployments.",
    )


def validate_env_config(results: List[Dict[str, str]], env_path: Path) -> Optional[Dict[str, str]]:
    if not env_path.exists():
        add(results, "Legal Config", "Production env file", "Blocker", "missing", "Create deploy/.env.production from the non-secret template.")
        return None
    env = parse_env_file(env_path)
    legal_ready = env_bool(env, "ERRORSWEEP_LEGAL_REVIEWED")
    public_url = value_for(env, ["ERRORSWEEP_PUBLIC_BASE_URL"])
    waf_provider = value_for(env, ["ERRORSWEEP_WAF_PROVIDER"])
    add(
        results,
        "Legal Config",
        "Legal review approval flag",
        "Pass" if legal_ready else "Blocker",
        "reviewed" if legal_ready else value_for(env, ["ERRORSWEEP_LEGAL_REVIEWED"]) or "missing",
        "Set ERRORSWEEP_LEGAL_REVIEWED=true only after approved Terms, Privacy, Cookie Notice, DPA, and customer processing language are live.",
    )
    add(
        results,
        "Legal Config",
        "Public HTTPS URL",
        "Pass" if https_url(public_url) else "Blocker",
        nonsecret_evidence("ERRORSWEEP_PUBLIC_BASE_URL", public_url),
        "Use a production HTTPS URL for legal links, verification/reset links, and public policy routes.",
    )
    add(
        results,
        "Legal Config",
        "CDN/WAF provider",
        "Pass" if waf_provider and not is_placeholder(waf_provider) else "Blocker",
        nonsecret_evidence("ERRORSWEEP_WAF_PROVIDER", waf_provider),
        "Put public routes behind a named CDN/WAF with edge rate limiting before launch.",
    )
    return env


def probe_public_routes(results: List[Dict[str, str]], base_url: str, timeout: int) -> None:
    if not base_url:
        add(results, "Legal Probe", "Public legal routes", "Blocker", "base URL missing", "Pass --base-url or --env-file with ERRORSWEEP_PUBLIC_BASE_URL before probing.")
        return
    for route in LEGAL_ROUTES:
        url = with_query(base_url.rstrip("/"), {"public": route})
        try:
            response = requests.get(url, timeout=timeout)
            status = "Pass" if response.status_code < 500 else "Blocker"
            evidence = f"{route}: HTTP {response.status_code}"
        except Exception as exc:
            status = "Blocker"
            evidence = f"{route}: {safe_text(exc)[:180]}"
        add(
            results,
            "Legal Probe",
            f"Public {route} route",
            status,
            evidence,
            "Public legal document routes should return a non-5xx response during launch rehearsal.",
        )


def collect_results(
    env_path: Optional[Path] = None,
    *,
    probe_public: bool = False,
    base_url: str = "",
    timeout: int = 30,
) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    validate_app_contract(results)
    validate_schema(results)
    validate_templates(results)

    env: Optional[Dict[str, str]] = None
    if env_path is not None:
        env = validate_env_config(results, env_path)
    if probe_public:
        resolved_base_url = safe_text(base_url) or value_for(env or {}, ["ERRORSWEEP_PUBLIC_BASE_URL"])
        probe_public_routes(results, resolved_base_url, timeout)
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
        "# CogniSweep Legal Check",
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
    parser = argparse.ArgumentParser(description="Validate CogniSweep legal and compliance launch readiness.")
    parser.add_argument("--env-file", default="", help="Production env file to validate. Omit for offline app/schema/template checks.")
    parser.add_argument("--base-url", default="", help="Public app base URL to use with --probe-public.")
    parser.add_argument("--probe-public", action="store_true", help="Probe Terms, Privacy, Security, Cookie Notice, and DPA public routes.")
    parser.add_argument("--timeout", type=int, default=30, help="Public probe timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    env_path = Path(args.env_file) if args.env_file else None
    results = sorted(
        collect_results(
            env_path=env_path,
            probe_public=args.probe_public,
            base_url=args.base_url,
            timeout=max(5, args.timeout),
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
