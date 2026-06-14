"""Run a repeatable ErrorSweep launch rehearsal.

This script combines the offline release guard, production env validator,
runtime smoke test, and optional public/worker health probes into one go/no-go
report. It is intentionally secret-safe: it never prints raw secret values.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / "deploy" / ".env.production"
PLACEHOLDER_MARKERS = (
    "replace-with",
    "your-domain.com",
    "yourdomain.com",
    "your-project",
    "example.com",
    "placeholder",
    "changeme",
    "change-me",
    "errorsweep.local",
    "demo workspace",
)
SENSITIVE_MARKERS = ("SECRET", "TOKEN", "PASSWORD", "HASH", "KEY", "SERVICE_ROLE")


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def strip_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if " #" in value:
        value = value.split(" #", 1)[0].strip()
    return value


def parse_env_file(path: Path) -> Tuple[Dict[str, str], List[str]]:
    env: Dict[str, str] = {}
    duplicates: List[str] = []
    if not path.exists():
        return env, duplicates
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
        if not key:
            continue
        if key in env:
            duplicates.append(key)
        env[key] = strip_value(raw_value)
    return env, duplicates


def add_os_env(env: Dict[str, str]) -> Dict[str, str]:
    merged = dict(env)
    for key, value in os.environ.items():
        if key not in merged and value not in (None, ""):
            merged[key] = str(value)
    return merged


def is_placeholder(value: str) -> bool:
    text = safe_text(value).lower()
    if not text:
        return True
    return any(marker in text for marker in PLACEHOLDER_MARKERS)


def value_for(env: Dict[str, str], names: Sequence[str]) -> str:
    for name in names:
        value = safe_text(env.get(name))
        if value:
            return value
    return ""


def redacted_env(env: Dict[str, str]) -> Dict[str, str]:
    cleaned: Dict[str, str] = {}
    for key, value in env.items():
        if any(marker in key.upper() for marker in SENSITIVE_MARKERS):
            cleaned[key] = "configured" if safe_text(value) and not is_placeholder(value) else safe_text(value)
        else:
            cleaned[key] = safe_text(value)
    return cleaned


def status_rank(status: str) -> int:
    return {"Pass": 0, "Warn": 1, "Blocker": 2}.get(status, 1)


def add(results: List[Dict[str, str]], area: str, check: str, status: str, evidence: str, action: str) -> None:
    results.append({
        "Area": area,
        "Check": check,
        "Status": status,
        "Evidence": evidence,
        "Action": action,
    })


def summary_text(payload: Dict[str, Any], fallback_output: str = "") -> Tuple[str, str]:
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    if isinstance(summary, dict):
        counts = summary.get("counts") or {}
        result = safe_text(summary.get("result") or "Warn")
        evidence = (
            f"{summary.get('checks', 0)} check(s); "
            f"{counts.get('Pass', 0)} pass / {counts.get('Warn', 0)} warn / {counts.get('Blocker', 0)} blocker"
        )
        return result, evidence
    first_line = next((line.strip() for line in fallback_output.splitlines() if line.strip()), "no output")
    return "Warn", first_line[:220]


def run_json_command(command: Sequence[str], timeout: int, env: Optional[Dict[str, str]] = None) -> Tuple[str, str, int]:
    runtime_env = os.environ.copy()
    if env:
        runtime_env.update(env)
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=runtime_env,
    )
    output = completed.stdout or completed.stderr or ""
    try:
        payload = json.loads(output)
        result, evidence = summary_text(payload, output)
    except Exception:
        result = "Pass" if completed.returncode == 0 else "Blocker"
        evidence = next((line.strip() for line in output.splitlines() if line.strip()), f"exit {completed.returncode}")[:220]
    return result, evidence, completed.returncode


def public_base_url(env: Dict[str, str], explicit_base_url: str = "") -> str:
    return safe_text(explicit_base_url or value_for(env, ["ERRORSWEEP_PUBLIC_BASE_URL"])).rstrip("/")


def public_base_url_check(base_url: str) -> Tuple[str, str]:
    if not base_url or is_placeholder(base_url):
        return "Blocker", base_url or "missing"
    parsed = urlparse(base_url)
    host = safe_text(parsed.hostname).lower()
    if parsed.scheme == "https" and parsed.netloc:
        return "Pass", base_url
    if parsed.scheme == "http" and host in {"localhost", "127.0.0.1", "::1"}:
        return "Pass", base_url
    return "Blocker", f"{base_url} must be HTTPS for public launch"


def with_query(base_url: str, params: Dict[str, str]) -> str:
    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({key: value for key, value in params.items() if value})
    return urlunparse(parsed._replace(query=urlencode(query)))


def health_url_from_task_url(task_url: str) -> str:
    parsed = urlparse(task_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return urlunparse(parsed._replace(path="/health", params="", query="", fragment=""))


def health_url_from_webhook_url(webhook_url: str) -> str:
    parsed = urlparse(webhook_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return urlunparse(parsed._replace(path="/health", params="", query="", fragment=""))


def probe_http(url: str, timeout: int) -> Tuple[str, str]:
    if not url or is_placeholder(url):
        return "Blocker", "missing or placeholder URL"
    try:
        response = requests.get(url, timeout=timeout)
    except Exception as exc:
        return "Blocker", safe_text(exc)[:220]
    if response.status_code < 500:
        return "Pass", f"HTTP {response.status_code}"
    return "Blocker", f"HTTP {response.status_code}"


def run_public_route_probes(results: List[Dict[str, str]], env: Dict[str, str], base_url: str, timeout: int) -> None:
    if not base_url:
        add(results, "Public Probe", "Public base URL", "Blocker", "missing", "Set ERRORSWEEP_PUBLIC_BASE_URL or pass --base-url.")
        return
    routes = {
        "Landing": with_query(base_url, {"public": "landing"}),
        "Login": with_query(base_url, {"public": "login"}),
        "Signup": with_query(base_url, {"public": "signup"}),
        "Terms": with_query(base_url, {"public": "terms"}),
        "Privacy": with_query(base_url, {"public": "privacy"}),
        "Security": with_query(base_url, {"public": "security"}),
        "Cookie Notice": with_query(base_url, {"public": "cookies"}),
        "DPA": with_query(base_url, {"public": "dpa"}),
        "Billing success": with_query(base_url, {"public": "billing_success", "checkout_id": "rehearsal", "plan": "Pro"}),
        "Billing cancel": with_query(base_url, {"public": "billing_cancel", "checkout_id": "rehearsal", "plan": "Pro"}),
    }
    for label, url in routes.items():
        status, evidence = probe_http(url, timeout)
        add(results, "Public Probe", label, status, evidence, "Public route should return a non-5xx response during launch rehearsal.")


def run_worker_probes(results: List[Dict[str, str]], env: Dict[str, str], base_url: str, timeout: int) -> None:
    app_health = f"{base_url}/_stcore/health" if base_url else ""
    async_health = health_url_from_task_url(value_for(env, ["ERRORSWEEP_ASYNC_WORKER_URL"]))
    billing_health = health_url_from_webhook_url(value_for(env, ["ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL"]))
    probes = [
        ("App health", app_health, "Streamlit public health endpoint should be reachable."),
        ("Async receiver health", async_health, "async_task_worker.py /health should be reachable when HTTP handoff is configured."),
        ("Billing webhook health", billing_health, "billing_webhook_receiver.py /health should be reachable when live webhooks are configured."),
    ]
    for label, url, action in probes:
        status, evidence = probe_http(url, timeout)
        add(results, "Worker Probe", label, status, evidence, action)


def collect_results(args: argparse.Namespace) -> List[Dict[str, str]]:
    env_path = Path(args.env_file).resolve()
    env, duplicates = parse_env_file(env_path)
    if args.include_os_env:
        env = add_os_env(env)
    base_url = public_base_url(env, args.base_url)
    base_url_status, base_url_evidence = public_base_url_check(base_url)
    results: List[Dict[str, str]] = []

    add(
        results,
        "Rehearsal",
        "Environment file",
        "Pass" if env_path.exists() else "Blocker",
        str(env_path.relative_to(ROOT)) if env_path.exists() and env_path.is_relative_to(ROOT) else str(env_path),
        "Create deploy/.env.production from deploy/.env.production.example and fill real values before rehearsal.",
    )
    add(
        results,
        "Rehearsal",
        "Duplicate env keys",
        "Pass" if not duplicates else "Warn",
        "none" if not duplicates else ", ".join(sorted(set(duplicates))),
        "Remove duplicate env keys so rehearsal and runtime use the same value.",
    )
    add(
        results,
        "Rehearsal",
        "Public base URL",
        base_url_status,
        base_url_evidence,
        "Set ERRORSWEEP_PUBLIC_BASE_URL or pass --base-url for route probes.",
    )

    if not args.skip_release_check:
        result, evidence, _ = run_json_command([sys.executable, "deploy/release_check.py", "--json"], args.timeout)
        add(results, "Rehearsal", "Release guard", result, evidence, "Release guard must pass before a launch rehearsal is trusted.")

    if not args.skip_launch_env_check:
        command = [sys.executable, "deploy/launch_env_check.py", "--env-file", str(env_path), "--json"]
        if args.include_os_env:
            command.append("--include-os-env")
        result, evidence, _ = run_json_command(command, args.timeout)
        add(results, "Rehearsal", "Launch env guard", result, evidence, "Resolve env blockers before opening public traffic.")

    if not args.skip_smoke_test:
        smoke_command = [sys.executable, "production_smoke_test.py"]
        if args.probe_workers:
            smoke_command.append("--probe-endpoints")
        result, evidence, _ = run_json_command(smoke_command, args.timeout, env=env)
        add(results, "Rehearsal", "Runtime smoke test", result, evidence, "Resolve smoke blockers before final go/no-go.")

    if args.probe_public:
        run_public_route_probes(results, env, base_url, args.timeout)

    if args.probe_workers:
        run_worker_probes(results, env, base_url, args.timeout)

    return sorted(results, key=lambda row: (status_rank(row["Status"]), row["Area"], row["Check"]))


def summarize(results: List[Dict[str, str]]) -> Dict[str, Any]:
    counts = {"Pass": 0, "Warn": 0, "Blocker": 0}
    for row in results:
        counts[row["Status"]] = counts.get(row["Status"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "Blocker" if counts.get("Blocker") else "Warn" if counts.get("Warn") else "Pass",
        "counts": counts,
        "checks": len(results),
    }


def markdown_report(summary: Dict[str, Any], results: List[Dict[str, str]]) -> str:
    lines = [
        "# ErrorSweep Launch Rehearsal",
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
    parser = argparse.ArgumentParser(description="Run the ErrorSweep launch rehearsal.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Production env file to rehearse.")
    parser.add_argument("--base-url", default="", help="Override ERRORSWEEP_PUBLIC_BASE_URL for route probes.")
    parser.add_argument("--include-os-env", action="store_true", help="Merge host environment variables into the env file values.")
    parser.add_argument("--probe-public", action="store_true", help="Probe public app routes such as landing, login, signup, legal, and billing return routes.")
    parser.add_argument("--probe-workers", action="store_true", help="Probe app, async receiver, and billing webhook health URLs.")
    parser.add_argument("--skip-release-check", action="store_true", help="Skip deploy/release_check.py.")
    parser.add_argument("--skip-launch-env-check", action="store_true", help="Skip deploy/launch_env_check.py.")
    parser.add_argument("--skip-smoke-test", action="store_true", help="Skip production_smoke_test.py.")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds for subprocesses and HTTP probes.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit non-zero on warnings as well as blockers.")
    args = parser.parse_args()

    results = collect_results(args)
    summary = summarize(results)
    payload = {"summary": summary, "results": results}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(markdown_report(summary, results))
    if args.fail_on_warn and (summary["counts"].get("Warn") or summary["counts"].get("Blocker")):
        return 1
    if args.strict and summary["counts"].get("Blocker"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
