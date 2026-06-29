"""Scheduled operational backup worker for CogniSweep.

This worker creates redacted JSON snapshots from the production persistence
layer. It can run once for a smoke test or loop on a schedule in production.
"""
from __future__ import annotations

import argparse
import json
import logging
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from app_runtime_config import runtime_env
from production_persistence import SAAS_TABLES, fetch_saas_records, save_saas_record

try:
    from cloud_object_storage import build_object_key, object_storage_status, put_file
except ImportError:  # pragma: no cover - optional integration
    build_object_key = None
    object_storage_status = None
    put_file = None

LOGGER = logging.getLogger("errorsweep.backup_worker")

BACKUP_SCHEMA_VERSION = 1
EXPORT_REDACTED_VALUE = "[redacted]"
EXPORT_BINARY_VALUE = "[binary omitted]"
DEFAULT_INTERVAL_HOURS = 24
DEFAULT_RETENTION_DAYS = 30
DEFAULT_RECORD_LIMIT = 1000
EXCLUDED_COLLECTIONS = {"auth_tokens"}
DEFAULT_COLLECTIONS = [
    "users",
    "workspaces",
    "projects",
    "jobs",
    "payments",
    "invoices",
    "subscriptions",
    "checkout_sessions",
    "billing_events",
    "platform_settings",
    "privacy_requests",
    "support_tickets",
    "status_incidents",
    "consent_records",
    "audit_logs",
    "files",
    "notifications",
    "task_queue",
]
SENSITIVE_EXACT_KEYS = {
    "api_key",
    "actor",
    "authorization",
    "checkout_url",
    "client_secret",
    "customer_email",
    "email",
    "email_address",
    "first_name",
    "full_name",
    "key_secret",
    "last_name",
    "name",
    "password",
    "password_hash",
    "phone",
    "phone_number",
    "provider_customer_id",
    "provider_order_id",
    "provider_payment_id",
    "provider_session_id",
    "provider_subscription_id",
    "raw_body",
    "refresh_token",
    "recipient",
    "requested_by",
    "secret",
    "secret_key",
    "service_role_key",
    "session",
    "session_id",
    "signature",
    "token",
    "token_hash",
    "user_email",
    "webhook_signature",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _env(name: str, default: str = "") -> str:
    return runtime_env(name, default).strip()


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() not in {"0", "false", "no", "off"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except (TypeError, ValueError):
        return default


def _sha256_json(value: Any) -> str:
    import hashlib

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_safe_text)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def backup_output_dir() -> Path:
    configured = _env("ERRORSWEEP_BACKUP_OUTPUT_DIR")
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / "errorsweep_operational_backups"
    root.mkdir(parents=True, exist_ok=True)
    return root


def export_key_is_sensitive(key: Any) -> bool:
    lowered = _safe_text(key).lower()
    if lowered in SENSITIVE_EXACT_KEYS:
        return True
    if lowered.endswith(("_api_key", "_secret", "_token", "_token_hash")):
        return True
    return any(marker in lowered for marker in ("password", "private_key", "service_role", "bearer"))


def redact_export_value(key: Any, value: Any) -> Any:
    if export_key_is_sensitive(key):
        return EXPORT_REDACTED_VALUE
    if isinstance(value, dict):
        return {_safe_text(child_key): redact_export_value(child_key, child_value) for child_key, child_value in value.items()}
    if isinstance(value, list):
        return [redact_export_value("", item) for item in value]
    if isinstance(value, tuple):
        return [redact_export_value("", item) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return EXPORT_BINARY_VALUE
    return value


def configured_collections(raw: str = "") -> List[str]:
    raw = raw or _env("ERRORSWEEP_BACKUP_COLLECTIONS")
    if raw:
        requested = [_safe_text(item) for item in raw.split(",") if _safe_text(item)]
    else:
        requested = list(DEFAULT_COLLECTIONS)
    return [item for item in requested if item in SAAS_TABLES and item not in EXCLUDED_COLLECTIONS]


def fetch_backup_records(collections: Iterable[str], limit: int) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, str]]:
    records: Dict[str, List[Dict[str, Any]]] = {}
    errors: Dict[str, str] = {}
    for collection in collections:
        try:
            records[collection] = fetch_saas_records(
                collection,
                limit=limit,
                include_all_workspaces=True,
                platform_scope_reason="operational_backup_snapshot",
            )
        except Exception as exc:
            records[collection] = []
            errors[collection] = _safe_text(exc)[:500]
            LOGGER.warning("Backup fetch failed for %s: %s", collection, exc)
    return records, errors


def build_backup_payload(collections: List[str], limit: int) -> Dict[str, Any]:
    fetched, fetch_errors = fetch_backup_records(collections, limit)
    records_by_collection: Dict[str, List[Any]] = {}
    redacted_fields = set()
    collection_hashes: Dict[str, str] = {}

    for collection, rows in fetched.items():
        redacted_rows: List[Any] = []
        for row in rows:
            if isinstance(row, dict):
                for key in row.keys():
                    if export_key_is_sensitive(key):
                        redacted_fields.add(_safe_text(key))
            redacted_rows.append(redact_export_value("", row))
        records_by_collection[collection] = redacted_rows
        collection_hashes[collection] = _sha256_json(redacted_rows)

    snapshot_sha256 = _sha256_json(records_by_collection)
    return {
        "export_type": "errorsweep_operational_backup",
        "schema_version": BACKUP_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "scope": "All workspaces",
        "requested_by": "operational-backup-worker@cognisweep.local",
        "requested_role": "System",
        "redaction_policy": {
            "auth_tokens": "excluded",
            "sensitive_fields": sorted(redacted_fields),
            "redacted_value": EXPORT_REDACTED_VALUE,
            "binary_value": EXPORT_BINARY_VALUE,
        },
        "record_counts": {collection: len(rows) for collection, rows in records_by_collection.items()},
        "collection_hashes": collection_hashes,
        "fetch_errors": fetch_errors,
        "snapshot_sha256": snapshot_sha256,
        "records": records_by_collection,
    }


def write_backup_file(payload: Dict[str, Any], output_dir: Path) -> Path:
    generated = _safe_text(payload.get("generated_at")).replace(":", "").replace("+", "_")
    digest = _safe_text(payload.get("snapshot_sha256"))[:12] or uuid.uuid4().hex[:12]
    path = output_dir / f"errorsweep_operational_backup_{generated}_{digest}.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=_safe_text)
    path.write_text(text, encoding="utf-8")
    return path


def cleanup_old_backups(output_dir: Path, retention_days: int) -> int:
    cutoff = _now() - timedelta(days=max(1, int(retention_days or DEFAULT_RETENTION_DAYS)))
    removed = 0
    for path in output_dir.glob("errorsweep_operational_backup_*.json"):
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            if modified < cutoff:
                path.unlink()
                removed += 1
        except Exception as exc:
            LOGGER.warning("Unable to clean backup file %s: %s", path, exc)
    return removed


def store_backup_manifest(path: Path, payload: Dict[str, Any], storage_result: Dict[str, Any]) -> Dict[str, Any]:
    record = {
        "id": f"backup-{_safe_text(payload.get('snapshot_sha256'))[:24]}",
        "workspace": "Platform",
        "user_email": "operational-backup-worker@cognisweep.local",
        "file_name": path.name,
        "purpose": "operational_backup",
        "mime_type": "application/json",
        "size_bytes": path.stat().st_size,
        "sha256": _safe_text(payload.get("snapshot_sha256")),
        "storage_key": storage_result.get("storage_key") or str(path),
        "storage_provider": storage_result.get("storage_provider") or "local",
        "storage_bucket": storage_result.get("storage_bucket") or "",
        "public_url": storage_result.get("public_url") or "",
        "local_path": storage_result.get("local_path") or str(path),
        "status": storage_result.get("status") or "stored",
        "created_at": _safe_text(payload.get("generated_at")) or _now_iso(),
        "updated_at": _now_iso(),
    }
    return save_saas_record(
        "files",
        record,
        user={"email": "operational-backup-worker@cognisweep.local", "workspace": "Platform"},
    )


def save_audit_event(payload: Dict[str, Any], manifest: Dict[str, Any], removed: int) -> None:
    counts = payload.get("record_counts") if isinstance(payload.get("record_counts"), dict) else {}
    details = (
        f"snapshot={_safe_text(payload.get('snapshot_sha256'))[:16]}; "
        f"records={sum(int(v or 0) for v in counts.values())}; "
        f"storage={manifest.get('storage_provider', 'local')}; removed_old={removed}"
    )
    save_saas_record(
        "audit_logs",
        {
            "id": uuid.uuid4().hex,
            "workspace": "Platform",
            "time": _now_iso(),
            "actor": "operational-backup-worker@cognisweep.local",
            "action": "Scheduled operational backup created",
            "details": details,
        },
        user={"email": "operational-backup-worker@cognisweep.local", "workspace": "Platform"},
    )


def maybe_store_object(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _bool_env("ERRORSWEEP_BACKUP_OBJECT_STORAGE_ENABLED", True):
        return {
            "storage_provider": "local",
            "storage_bucket": "local",
            "storage_key": str(path),
            "local_path": str(path),
            "public_url": "",
            "status": "stored",
        }
    if put_file is None or build_object_key is None:
        return {
            "storage_provider": "local",
            "storage_bucket": "local",
            "storage_key": str(path),
            "local_path": str(path),
            "public_url": "",
            "status": "stored",
        }
    key = build_object_key(
        "Platform",
        "operational_backup",
        _safe_text(payload.get("snapshot_sha256"))[:24] or uuid.uuid4().hex,
        path.name,
    )
    try:
        return put_file(path, key, content_type="application/json")
    except Exception as exc:
        LOGGER.warning("Object storage backup upload failed, keeping local file only: %s", exc)
        return {
            "storage_provider": "local",
            "storage_bucket": "local",
            "storage_key": str(path),
            "local_path": str(path),
            "public_url": "",
            "status": "stored_local_after_upload_error",
        }


def run_backup(collections: List[str], limit: int, retention_days: int, dry_run: bool = False) -> Dict[str, Any]:
    output_dir = backup_output_dir()
    payload = build_backup_payload(collections, limit)
    record_count = sum(int(v or 0) for v in payload.get("record_counts", {}).values())
    summary: Dict[str, Any] = {
        "snapshot_sha256": payload.get("snapshot_sha256"),
        "collection_count": len(collections),
        "record_count": record_count,
        "fetch_errors": payload.get("fetch_errors", {}),
        "dry_run": dry_run,
        "path": "",
        "storage_provider": "",
        "removed_old": 0,
    }
    if dry_run:
        return summary
    path = write_backup_file(payload, output_dir)
    storage_result = maybe_store_object(path, payload)
    manifest = store_backup_manifest(path, payload, storage_result)
    removed = cleanup_old_backups(output_dir, retention_days)
    save_audit_event(payload, manifest, removed)
    summary.update({
        "path": str(path),
        "storage_provider": storage_result.get("storage_provider", "local"),
        "storage_key": storage_result.get("storage_key", str(path)),
        "removed_old": removed,
    })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Create scheduled CogniSweep operational backups.")
    parser.add_argument("--once", action="store_true", help="Run one backup pass and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Build the backup summary without writing files or manifests.")
    parser.add_argument("--collections", default=_env("ERRORSWEEP_BACKUP_COLLECTIONS"), help="Comma-separated collection list.")
    parser.add_argument("--limit", type=int, default=_int_env("ERRORSWEEP_BACKUP_RECORD_LIMIT", DEFAULT_RECORD_LIMIT))
    parser.add_argument("--retention-days", type=int, default=_int_env("ERRORSWEEP_BACKUP_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
    parser.add_argument("--interval-hours", type=int, default=_int_env("ERRORSWEEP_BACKUP_INTERVAL_HOURS", DEFAULT_INTERVAL_HOURS))
    args = parser.parse_args()

    logging.basicConfig(level=_env("ERRORSWEEP_BACKUP_WORKER_LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(message)s")
    run_once = args.once or _bool_env("ERRORSWEEP_BACKUP_WORKER_ONCE", False)
    collections = configured_collections(args.collections)
    storage_health = object_storage_status() if object_storage_status is not None else {"provider": "local", "mode": "local_fallback"}
    LOGGER.info("Starting CogniSweep backup worker collections=%s storage=%s", len(collections), storage_health)
    while True:
        summary = run_backup(collections, args.limit, args.retention_days, dry_run=args.dry_run)
        LOGGER.info("Operational backup summary: %s", json.dumps(summary, sort_keys=True, default=_safe_text))
        if run_once:
            return 0 if not summary.get("fetch_errors") else 1
        time.sleep(max(300, int(args.interval_hours or DEFAULT_INTERVAL_HOURS) * 3600))


if __name__ == "__main__":
    raise SystemExit(main())
