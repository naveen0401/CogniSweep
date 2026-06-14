"""Check Supabase release schema drift against CogniSweep persistence code.

This is an offline-first launch helper. By default it reads
supabase_v42_release_schema.sql and production_persistence.py without importing
the Streamlit app or printing secrets. Use --probe-rest only after production
Supabase credentials are configured in deploy/.env.production.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = ROOT / "supabase_v42_release_schema.sql"
DEFAULT_PERSISTENCE_PATH = ROOT / "production_persistence.py"
DEFAULT_ENV_PATH = ROOT / "deploy" / ".env.production"

CORE_TABLE_COLUMNS = {
    "errorsweep_editor_jobs": {
        "id",
        "job_type",
        "user_email",
        "workspace",
        "file_name",
        "target_language",
        "status",
        "row_count",
        "rows",
        "metadata",
        "created_at",
        "updated_at",
    },
    "errorsweep_usage_events": {
        "id",
        "user_email",
        "workspace",
        "purpose",
        "provider",
        "model",
        "managed",
        "segments",
        "characters",
        "requests",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "success",
        "error",
        "metadata",
        "created_at",
    },
}

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

SENSITIVE_KEY_RE = re.compile(r"(SECRET|TOKEN|PASSWORD|KEY|SERVICE_ROLE)", re.IGNORECASE)
CREATE_TABLE_RE = re.compile(
    r"create\s+table\s+if\s+not\s+exists\s+public\.([a-zA-Z_][\w]*)\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
ALTER_ADD_COLUMN_RE = re.compile(
    r"alter\s+table\s+public\.([a-zA-Z_][\w]*)\s+add\s+column\s+if\s+not\s+exists\s+(?:\"([^\"]+)\"|([a-zA-Z_][\w]*))",
    re.IGNORECASE,
)
ENABLE_RLS_RE = re.compile(
    r"alter\s+table\s+public\.([a-zA-Z_][\w]*)\s+enable\s+row\s+level\s+security",
    re.IGNORECASE,
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
        new_lines.extend(["", "# Added by deploy/supabase_schema_check.py setup helper"])
        for key, value in remaining.items():
            new_lines.append(f"{key}={format_env_value(value)}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def nonsecret_evidence(key: str, value: str) -> str:
    if not safe_text(value):
        return "missing"
    if is_placeholder(value):
        return "placeholder"
    if SENSITIVE_KEY_RE.search(key):
        return "configured"
    return value


def truncate_items(items: Iterable[str], limit: int = 8) -> str:
    values = list(items)
    if not values:
        return ""
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f", +{len(values) - limit} more"
    return ", ".join(shown) + suffix


def load_literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return ast.literal_eval(node.value)
    raise ValueError(f"{name} assignment not found in {path}")


def load_persistence_contract(path: Path) -> Tuple[Dict[str, str], Dict[str, Set[str]]]:
    tables = load_literal_assignment(path, "SAAS_TABLES")
    columns = load_literal_assignment(path, "SAAS_COLUMNS")
    if not isinstance(tables, dict) or not isinstance(columns, dict):
        raise ValueError("SAAS_TABLES and SAAS_COLUMNS must be literal dictionaries")
    normalized_tables = {safe_text(key): safe_text(value) for key, value in tables.items()}
    normalized_columns = {
        safe_text(key): {safe_text(column) for column in value}
        for key, value in columns.items()
        if isinstance(value, (set, list, tuple))
    }
    return normalized_tables, normalized_columns


def remove_sql_comments(sql: str) -> str:
    return re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)


def column_name_from_line(line: str) -> Optional[str]:
    text = line.strip().rstrip(",").strip()
    if not text:
        return None
    first_word = text.split(None, 1)[0].strip('"').lower()
    if first_word in {"constraint", "primary", "foreign", "unique", "check", "exclude"}:
        return None
    quoted = re.match(r'^"([^"]+)"\s+', text)
    if quoted:
        return quoted.group(1)
    bare = re.match(r"^([a-zA-Z_][\w]*)\s+", text)
    return bare.group(1) if bare else None


def parse_schema(sql: str) -> Tuple[Dict[str, Set[str]], Set[str]]:
    sql_without_comments = remove_sql_comments(sql)
    table_columns: Dict[str, Set[str]] = {}
    for match in CREATE_TABLE_RE.finditer(sql_without_comments):
        table = match.group(1)
        body = match.group(2)
        columns = table_columns.setdefault(table, set())
        for line in body.splitlines():
            name = column_name_from_line(line)
            if name:
                columns.add(name)
    for match in ALTER_ADD_COLUMN_RE.finditer(sql_without_comments):
        table = match.group(1)
        column = match.group(2) or match.group(3)
        if column:
            table_columns.setdefault(table, set()).add(column)
    rls_tables = {match.group(1) for match in ENABLE_RLS_RE.finditer(sql_without_comments)}
    return table_columns, rls_tables


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


def probe_supabase_tables(url: str, service_key: str, tables: Sequence[str], timeout: int) -> Dict[str, str]:
    import requests

    base_url = url.rstrip("/")
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    statuses: Dict[str, str] = {}
    for table in tables:
        endpoint = f"{base_url}/rest/v1/{table}?select=id&limit=1"
        try:
            response = requests.get(endpoint, headers=headers, timeout=timeout)
            statuses[table] = "ok" if response.status_code < 400 else f"error_{response.status_code}"
        except Exception as exc:
            statuses[table] = f"error:{safe_text(exc)[:80]}"
    return statuses


def collect_results(
    schema_path: Path,
    persistence_path: Path,
    *,
    env_path: Optional[Path] = None,
    probe_rest: bool = False,
    probe_timeout: int = 15,
) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    if not schema_path.exists():
        add(results, "Persistence", "Supabase release SQL", "Blocker", "missing", "Restore supabase_v42_release_schema.sql.")
        return results
    if not persistence_path.exists():
        add(results, "Persistence", "Persistence contract", "Blocker", "missing", "Restore production_persistence.py.")
        return results

    try:
        saas_tables, saas_columns = load_persistence_contract(persistence_path)
        add(
            results,
            "Persistence",
            "Persistence contract loaded",
            "Pass",
            f"{len(saas_tables)} SaaS collection(s)",
            "Keep SAAS_TABLES and SAAS_COLUMNS as literal dictionaries so release checks can validate schema drift.",
        )
    except Exception as exc:
        add(results, "Persistence", "Persistence contract loaded", "Blocker", safe_text(exc)[:220], "Fix SAAS_TABLES/SAAS_COLUMNS parsing.")
        return results

    sql = schema_path.read_text(encoding="utf-8", errors="ignore")
    schema_columns, rls_tables = parse_schema(sql)
    expected_columns: Dict[str, Set[str]] = {table: set(columns) for table, columns in CORE_TABLE_COLUMNS.items()}
    for collection, table in saas_tables.items():
        expected_columns[table] = set(saas_columns.get(collection, set()))

    expected_tables = sorted(expected_columns)
    missing_tables = [table for table in expected_tables if table not in schema_columns]
    add(
        results,
        "Persistence",
        "Supabase table coverage",
        "Pass" if not missing_tables else "Blocker",
        f"{len(expected_tables)} expected table(s)" if not missing_tables else truncate_items(missing_tables),
        "Add missing production tables to supabase_v42_release_schema.sql before running it in Supabase.",
    )

    missing_column_entries: List[str] = []
    expected_column_count = 0
    for table in expected_tables:
        expected = expected_columns.get(table, set())
        expected_column_count += len(expected)
        missing = sorted(expected - schema_columns.get(table, set()))
        if missing:
            missing_column_entries.append(f"{table}: {', '.join(missing)}")
    add(
        results,
        "Persistence",
        "Supabase column coverage",
        "Pass" if not missing_column_entries else "Blocker",
        f"{expected_column_count} expected column(s)" if not missing_column_entries else truncate_items(missing_column_entries, limit=5),
        "Keep release SQL columns aligned with production_persistence.SAAS_COLUMNS and core editor/usage records.",
    )

    rls_missing = [table for table in expected_tables if table not in rls_tables]
    add(
        results,
        "Persistence",
        "Supabase RLS coverage",
        "Pass" if not rls_missing else "Blocker",
        "RLS enabled for expected tables" if not rls_missing else truncate_items(rls_missing),
        "Enable row level security for every production table before public launch.",
    )

    if probe_rest:
        env = parse_env_file(env_path or DEFAULT_ENV_PATH)
        supabase_url = safe_text(env.get("SUPABASE_URL"))
        service_key = safe_text(env.get("SUPABASE_SERVICE_ROLE_KEY"))
        url_ready = https_url(supabase_url)
        key_ready = bool(service_key) and not is_placeholder(service_key) and len(service_key) >= 24
        add(
            results,
            "Supabase",
            "REST URL",
            "Pass" if url_ready else "Blocker",
            nonsecret_evidence("SUPABASE_URL", supabase_url),
            "Set SUPABASE_URL to the production HTTPS Supabase project URL; use --write-supabase-env for repeatable setup.",
        )
        add(
            results,
            "Supabase",
            "Service role key",
            "Pass" if key_ready else "Blocker",
            nonsecret_evidence("SUPABASE_SERVICE_ROLE_KEY", service_key),
            "Set SUPABASE_SERVICE_ROLE_KEY in the private production secret store; use --write-supabase-env for repeatable setup.",
        )
        if url_ready and key_ready:
            statuses = probe_supabase_tables(supabase_url, service_key, expected_tables, probe_timeout)
            failures = [f"{table}={status}" for table, status in statuses.items() if status != "ok"]
            add(
                results,
                "Supabase",
                "REST table probe",
                "Pass" if not failures else "Blocker",
                f"{len(statuses)}/{len(expected_tables)} reachable" if not failures else truncate_items(failures, limit=6),
                "Run supabase_v42_release_schema.sql in the production Supabase project, then re-run this probe.",
            )

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
        "# CogniSweep Supabase Schema Check",
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


def write_supabase_env(args: argparse.Namespace) -> int:
    env_path = Path(args.env_file) if args.env_file else DEFAULT_ENV_PATH
    supabase_url = safe_text(args.supabase_url).rstrip("/")
    storage_bucket = safe_text(args.storage_bucket) or "errorsweep-files"
    provider = safe_text(args.object_storage_provider).lower() or "supabase"
    try:
        if not https_url(supabase_url):
            raise ValueError("--supabase-url must be a production HTTPS Supabase project URL.")
        anon_key = read_required_secret_env(args.anon_key_env, "anon-key-env")
        service_role_key = read_required_secret_env(args.service_role_key_env, "service-role-key-env")
        if is_placeholder(anon_key) or len(anon_key) < 24:
            raise ValueError("Supabase anon key must be at least 24 non-placeholder characters.")
        if is_placeholder(service_role_key) or len(service_role_key) < 24:
            raise ValueError("Supabase service role key must be at least 24 non-placeholder characters.")
        if provider not in {"supabase", "s3", "gcs"}:
            raise ValueError("--object-storage-provider must be supabase, s3, or gcs.")
        if provider == "supabase" and (not storage_bucket or is_placeholder(storage_bucket)):
            raise ValueError("--storage-bucket must be a non-placeholder Supabase Storage bucket name.")
        updates = {
            "SUPABASE_URL": supabase_url,
            "SUPABASE_ANON_KEY": anon_key,
            "SUPABASE_SERVICE_ROLE_KEY": service_role_key,
            "ERRORSWEEP_OBJECT_STORAGE_PROVIDER": provider,
        }
        if provider == "supabase":
            updates["SUPABASE_STORAGE_BUCKET"] = storage_bucket
        write_env_updates(env_path, updates)
    except Exception as exc:
        print(safe_text(exc), file=sys.stderr)
        return 1

    payload = {
        "env_file": str(env_path),
        "supabase_url": supabase_url,
        "object_storage_provider": provider,
        "storage_bucket": storage_bucket if provider == "supabase" else "",
        "updated": sorted(updates.keys()),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Updated {env_path}")
        print(f"Supabase URL: {supabase_url}")
        print(f"Object storage provider: {provider}")
        if provider == "supabase":
            print(f"Supabase Storage bucket: {storage_bucket}")
        print("Supabase keys were read from environment variables and were not printed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CogniSweep Supabase release schema coverage.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH), help="Path to supabase_v42_release_schema.sql.")
    parser.add_argument("--persistence", default=str(DEFAULT_PERSISTENCE_PATH), help="Path to production_persistence.py.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH), help="Production env file used only with --probe-rest.")
    parser.add_argument("--write-supabase-env", action="store_true", help="Write Supabase persistence and Supabase Storage env settings from environment variables.")
    parser.add_argument("--supabase-url", default="", help="Production HTTPS Supabase project URL.")
    parser.add_argument("--anon-key-env", default="", help="Environment variable containing SUPABASE_ANON_KEY.")
    parser.add_argument("--service-role-key-env", default="", help="Environment variable containing SUPABASE_SERVICE_ROLE_KEY.")
    parser.add_argument("--storage-bucket", default="errorsweep-files", help="Supabase Storage bucket name when object storage provider is supabase.")
    parser.add_argument("--object-storage-provider", default="supabase", help="Object storage provider to write: supabase, s3, or gcs.")
    parser.add_argument("--probe-rest", action="store_true", help="Probe configured Supabase REST tables with service-role credentials.")
    parser.add_argument("--probe-timeout", type=int, default=15, help="Per-table REST probe timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers are found.")
    args = parser.parse_args()

    if args.write_supabase_env:
        return write_supabase_env(args)

    results = sorted(
        collect_results(
            Path(args.schema),
            Path(args.persistence),
            env_path=Path(args.env_file),
            probe_rest=args.probe_rest,
            probe_timeout=max(1, args.probe_timeout),
        ),
        key=lambda row: (status_rank(row["Status"]), row["Area"], row["Check"]),
    )
    summary = summarize(results)
    if args.json:
        print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2))
    else:
        print(markdown_report(summary, results))
    if args.strict and summary["counts"].get("Blocker"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
