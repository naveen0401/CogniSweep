"""ErrorSweep v42 production persistence helpers.

Purpose
-------
This module lets the Streamlit MVP keep working exactly as it does now, while
optionally saving editor jobs and usage events to Supabase when the required
secrets are configured.

It has a safe local JSON fallback, so the app will not crash if Supabase is not
ready yet. For release, configure Supabase and run the SQL schema file.

Required Streamlit secrets for production mode
---------------------------------------------
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"

Optional
--------
ERRORSWEEP_EDITOR_JOB_DIR = "/tmp/errorsweep_editor_jobs"
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

LOGGER = logging.getLogger(__name__)

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days local fallback retention
SUPABASE_TIMEOUT = 25
LOCAL_USAGE_MAX_BYTES = int(os.getenv("ERRORSWEEP_USAGE_LOG_MAX_BYTES", str(5 * 1024 * 1024)))
LOCAL_USAGE_KEEP_LINES = int(os.getenv("ERRORSWEEP_USAGE_LOG_KEEP_LINES", "2000"))
_LOCAL_WRITE_LOCK = threading.Lock()

SAAS_TABLES = {
    "users": "errorsweep_users",
    "workspaces": "errorsweep_workspaces",
    "projects": "errorsweep_projects",
    "jobs": "errorsweep_jobs",
    "payments": "errorsweep_payments",
    "invoices": "errorsweep_invoices",
    "subscriptions": "errorsweep_subscriptions",
    "checkout_sessions": "errorsweep_checkout_sessions",
    "billing_events": "errorsweep_billing_events",
    "auth_tokens": "errorsweep_auth_tokens",
    "platform_settings": "errorsweep_platform_settings",
    "privacy_requests": "errorsweep_privacy_requests",
    "support_tickets": "errorsweep_support_tickets",
    "status_incidents": "errorsweep_status_incidents",
    "consent_records": "errorsweep_consent_records",
    "audit_logs": "errorsweep_audit_logs",
    "files": "errorsweep_files",
    "notifications": "errorsweep_notifications",
    "task_queue": "errorsweep_task_queue",
}

SAAS_COLUMNS = {
    "users": {"id", "email", "workspace", "role", "plan", "status", "password_hash", "email_verified", "verified_at", "user_email", "created_at", "updated_at"},
    "workspaces": {"id", "workspace", "owner", "plan", "status", "users", "jobs", "user_email", "created_at", "updated_at"},
    "projects": {"id", "workspace", "user_email", "created", "project", "client", "source", "targets", "domain", "status", "job_count", "created_at", "updated_at"},
    "jobs": {"id", "workspace", "user_email", "created", "type", "language", "assignee", "status", "note", "segments", "project_id", "project", "attachment_count", "attachments_json", "created_at", "updated_at"},
    "payments": {"id", "workspace", "user_email", "date", "user", "plan", "amount", "currency", "status", "created_at", "updated_at"},
    "invoices": {"id", "workspace", "user_email", "invoice_number", "customer_email", "customer_gstin", "plan", "billing_period", "currency", "subtotal", "tax_rate_percent", "tax_amount", "total", "status", "source_payment_id", "notes", "metadata_json", "created_at", "updated_at"},
    "subscriptions": {"id", "workspace", "user_email", "plan", "status", "billing_cycle", "currency", "base_amount", "included_segments", "included_characters", "included_seats", "provider", "provider_customer_id", "provider_subscription_id", "current_period_start", "current_period_end", "cancel_at_period_end", "cancelled_at", "cancellation_reason", "metadata_json", "created_at", "updated_at"},
    "checkout_sessions": {"id", "workspace", "user_email", "plan", "billing_cycle", "currency", "amount", "provider", "status", "checkout_url", "provider_session_id", "metadata_json", "created_at", "updated_at"},
    "billing_events": {"id", "workspace", "user_email", "provider", "event_id", "event_type", "status", "plan", "amount", "currency", "provider_payment_id", "provider_subscription_id", "provider_order_id", "provider_customer_id", "checkout_id", "signature_status", "applied", "raw_sha256", "metadata_json", "created_at", "updated_at"},
    "auth_tokens": {"id", "workspace", "user_email", "email", "token_hash", "token_type", "status", "expires_at", "used_at", "metadata_json", "created_at", "updated_at"},
    "platform_settings": {"id", "workspace", "user_email", "setting_key", "setting_value", "value_type", "metadata_json", "created_at", "updated_at"},
    "privacy_requests": {"id", "workspace", "user_email", "request_type", "requester_email", "subject", "status", "due_at", "fulfilled_at", "owner_notes", "metadata_json", "created_at", "updated_at"},
    "support_tickets": {"id", "workspace", "user_email", "requester_email", "category", "priority", "subject", "message", "status", "owner_reply", "last_response_at", "metadata_json", "created_at", "updated_at"},
    "status_incidents": {"id", "workspace", "user_email", "scope", "incident_type", "severity", "status", "title", "message", "starts_at", "ends_at", "resolved_at", "metadata_json", "created_at", "updated_at"},
    "consent_records": {"id", "workspace", "user_email", "email", "account_type", "role", "terms_version", "privacy_version", "nda_version", "cookie_version", "dpa_version", "accepted_at", "ip_hint", "metadata_json", "created_at", "updated_at"},
    "audit_logs": {"id", "workspace", "user_email", "time", "actor", "action", "details", "created_at", "updated_at"},
    "files": {"id", "workspace", "user_email", "file_name", "purpose", "mime_type", "size_bytes", "sha256", "storage_key", "storage_provider", "storage_bucket", "public_url", "local_path", "status", "expires_at", "created_at", "updated_at"},
    "notifications": {"id", "workspace", "user_email", "recipient", "subject", "event_type", "status", "provider", "body", "error", "metadata_json", "sent_at", "created_at", "updated_at"},
    "task_queue": {"id", "workspace", "user_email", "task_type", "label", "status", "progress", "total_units", "processed_units", "result_ref", "error", "metadata_json", "started_at", "finished_at", "created_at", "updated_at"},
}


# ==========================================================
# Secrets / config
# ==========================================================

def _secret(name: str, default: str = "") -> str:
    env_val = os.environ.get(name)
    if env_val not in (None, ""):
        return str(env_val)
    if st is not None:
        try:
            val = st.secrets.get(name)
            if val not in (None, ""):
                return str(val)
        except Exception as exc:
            LOGGER.debug("Unable to read Streamlit secret %s: %s", name, exc)
    return default


def _supabase_url() -> str:
    return _secret("SUPABASE_URL").rstrip("/")


def _service_key() -> str:
    return _secret("SUPABASE_SERVICE_ROLE_KEY")


def supabase_configured() -> bool:
    return bool(_supabase_url() and _service_key())


def _headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    key = _service_key()
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_job_id(job_id: Optional[str]) -> str:
    raw = str(job_id or uuid.uuid4().hex).strip()
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
    return (safe or uuid.uuid4().hex)[:96]


def _current_user_email(user: Optional[Dict[str, Any]] = None) -> str:
    user = user or {}
    return str(user.get("email") or user.get("username") or "").strip()


def _current_workspace(user: Optional[Dict[str, Any]] = None) -> str:
    user = user or {}
    return str(user.get("workspace") or "Demo Workspace").strip()


# ==========================================================
# Local JSON fallback
# ==========================================================

def _local_root() -> Path:
    configured = _secret("ERRORSWEEP_EDITOR_JOB_DIR")
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / "errorsweep_editor_jobs_v42"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _local_path(job_id: str) -> Path:
    return _local_root() / f"{_safe_job_id(job_id)}.json"


def _local_usage_path() -> Path:
    return _local_root() / "usage_events.jsonl"


def _local_collection_path(collection: str) -> Path:
    safe = "".join(ch for ch in str(collection) if ch.isalnum() or ch in {"-", "_"})
    return _local_root() / f"saas_{safe or 'records'}.json"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def _write_local_job(payload: Dict[str, Any]) -> None:
    with _LOCAL_WRITE_LOCK:
        _atomic_write_text(_local_path(payload["job_id"]), json.dumps(payload, ensure_ascii=False, indent=2))
        cleanup_local_jobs()


def _rotate_local_usage_events() -> None:
    path = _local_usage_path()
    if not path.exists() or path.stat().st_size <= LOCAL_USAGE_MAX_BYTES:
        return
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    retained = lines[-max(1, LOCAL_USAGE_KEEP_LINES):]
    _atomic_write_text(path, "\n".join(retained) + ("\n" if retained else ""))


def _read_local_job(job_id: str) -> Optional[Dict[str, Any]]:
    path = _local_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("Unable to read local editor job %s: %s", path, exc)
        return None


def _read_local_collection(collection: str) -> List[Dict[str, Any]]:
    path = _local_collection_path(collection)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:
        LOGGER.warning("Unable to read local SaaS collection %s: %s", path, exc)
        return []


def _write_local_collection(collection: str, records: List[Dict[str, Any]]) -> None:
    with _LOCAL_WRITE_LOCK:
        _atomic_write_text(_local_collection_path(collection), json.dumps(records, ensure_ascii=False, indent=2))


def _record_id(collection: str, record: Dict[str, Any]) -> str:
    explicit = str(record.get("id") or record.get("record_id") or "").strip()
    if explicit:
        return _safe_job_id(explicit)
    if collection == "users" and record.get("email"):
        return _safe_job_id(str(record.get("email")).lower())
    if collection == "workspaces" and record.get("workspace"):
        return _safe_job_id(str(record.get("workspace")).lower())
    if collection == "subscriptions" and record.get("workspace"):
        return _safe_job_id(f"{record.get('workspace') or ''}-{record.get('plan') or ''}-{record.get('billing_cycle') or ''}")
    if collection == "invoices" and record.get("invoice_number"):
        return _safe_job_id(str(record.get("invoice_number")))
    if collection == "checkout_sessions" and record.get("workspace"):
        return _safe_job_id(f"{record.get('workspace') or ''}-{record.get('plan') or ''}-{record.get('created_at') or _now_iso()}")
    if collection == "billing_events" and record.get("event_id"):
        return _safe_job_id(f"{record.get('provider') or ''}-{record.get('event_id')}")
    if collection == "auth_tokens" and record.get("token_hash"):
        return _safe_job_id(f"{record.get('token_type') or ''}-{record.get('email') or ''}-{record.get('token_hash')}")
    if collection == "platform_settings" and record.get("setting_key"):
        return _safe_job_id(f"platform-{record.get('setting_key')}")
    if collection == "privacy_requests" and record.get("requester_email"):
        return _safe_job_id(
            f"{record.get('workspace') or ''}-{record.get('request_type') or ''}-{record.get('requester_email') or ''}-{record.get('created_at') or _now_iso()}"
        )
    if collection == "support_tickets" and record.get("requester_email"):
        return _safe_job_id(
            f"{record.get('workspace') or ''}-{record.get('requester_email') or ''}-{record.get('subject') or ''}-{record.get('created_at') or _now_iso()}"
        )
    if collection == "status_incidents" and record.get("title"):
        return _safe_job_id(
            f"{record.get('scope') or ''}-{record.get('incident_type') or ''}-{record.get('title') or ''}-{record.get('created_at') or _now_iso()}"
        )
    if collection == "consent_records" and (record.get("email") or record.get("user_email")):
        return _safe_job_id(
            f"{record.get('workspace') or ''}-{record.get('email') or record.get('user_email') or ''}-{record.get('terms_version') or ''}-{record.get('privacy_version') or ''}-{record.get('nda_version') or ''}-{record.get('accepted_at') or record.get('created_at') or _now_iso()}"
        )
    if collection == "projects" and record.get("project"):
        return _safe_job_id(f"{record.get('workspace') or record.get('client') or ''}-{record.get('project')}-{record.get('created') or ''}")
    if collection == "files" and record.get("storage_key"):
        return _safe_job_id(f"{record.get('workspace') or ''}-{record.get('purpose') or ''}-{record.get('storage_key')}")
    if collection == "files" and record.get("sha256"):
        return _safe_job_id(f"{record.get('workspace') or ''}-{record.get('purpose') or ''}-{record.get('sha256')}")
    if collection == "notifications" and record.get("recipient") and record.get("event_type"):
        return _safe_job_id(
            f"{record.get('workspace') or ''}-{record.get('event_type') or ''}-{record.get('recipient') or ''}-{record.get('created_at') or _now_iso()}"
        )
    if collection == "task_queue" and record.get("task_type"):
        return _safe_job_id(
            f"{record.get('workspace') or ''}-{record.get('task_type') or ''}-{record.get('label') or ''}-{record.get('created_at') or _now_iso()}"
        )
    return uuid.uuid4().hex


def _normalise_saas_record(collection: str, record: Dict[str, Any], user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    user = user or {}
    item = dict(record or {})
    item["id"] = _record_id(collection, item)
    item.setdefault("workspace", item.get("client") or _current_workspace(user))
    item.setdefault("user_email", item.get("email") or item.get("actor") or _current_user_email(user))
    item.setdefault("created_at", item.get("created") or item.get("date") or item.get("time") or _now_iso())
    item["updated_at"] = _now_iso()
    return item


def _upsert_local_saas_record(collection: str, record: Dict[str, Any]) -> Dict[str, Any]:
    records = _read_local_collection(collection)
    rid = str(record.get("id"))
    replaced = False
    for idx, existing in enumerate(records):
        if str(existing.get("id")) == rid:
            records[idx] = {**existing, **record}
            replaced = True
            break
    if not replaced:
        records.insert(0, record)
    _write_local_collection(collection, records[:1000])
    return record


def cleanup_local_jobs(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    now = time.time()
    for path in _local_root().glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            updated = float(payload.get("updated_at_epoch") or payload.get("created_at_epoch") or 0)
            if updated and now - updated > ttl_seconds:
                path.unlink(missing_ok=True)
        except Exception as exc:
            LOGGER.warning("Unable to clean local editor job %s: %s", path, exc)
            try:
                path.unlink(missing_ok=True)
            except Exception as unlink_exc:
                LOGGER.warning("Unable to remove local editor job %s: %s", path, unlink_exc)


# ==========================================================
# Editor job persistence
# ==========================================================

def _normalise_payload(job_id: str, job_type: str, rows: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]], user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    user_email = metadata.get("user_email") or _current_user_email(user)
    workspace = metadata.get("workspace") or _current_workspace(user)
    file_name = metadata.get("file_name", "")
    target_language = metadata.get("target_language", "")
    status = metadata.get("status", "draft")
    now = _now_iso()
    epoch = time.time()
    return {
        "job_id": job_id,
        "id": job_id,  # Supabase primary key column is id.
        "job_type": job_type or metadata.get("job_type") or "cat",
        "user_email": user_email,
        "workspace": workspace,
        "file_name": file_name,
        "target_language": target_language,
        "status": status,
        "row_count": len(rows or []),
        "rows": rows or [],
        "metadata": metadata,
        "created_at": metadata.get("created_at") or metadata.get("created") or now,
        "updated_at": now,
        "created_at_epoch": epoch,
        "updated_at_epoch": epoch,
    }


def save_persistent_editor_job(
    job_type: str,
    rows: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    user: Optional[Dict[str, Any]] = None,
) -> str:
    """Save an editor job to Supabase when configured; otherwise local JSON.

    Returns the job_id to pass to the external editor URL.
    """
    jid = _safe_job_id(job_id)
    payload = _normalise_payload(jid, job_type, rows, metadata, user)

    # Always write local fallback so development/testing remains resilient.
    try:
        _write_local_job(payload)
    except Exception as exc:
        LOGGER.error("Failed to write local editor job fallback %s: %s", jid, exc)

    if not supabase_configured():
        return jid

    try:
        # Upsert by id.
        url = f"{_supabase_url()}/rest/v1/errorsweep_editor_jobs?on_conflict=id"
        db_payload = {
            "id": jid,
            "job_type": payload["job_type"],
            "user_email": payload["user_email"],
            "workspace": payload["workspace"],
            "file_name": payload["file_name"],
            "target_language": payload["target_language"],
            "status": payload["status"],
            "row_count": payload["row_count"],
            "rows": payload["rows"],
            "metadata": payload["metadata"],
            "updated_at": payload["updated_at"],
        }
        requests.post(
            url,
            headers=_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            json=db_payload,
            timeout=SUPABASE_TIMEOUT,
        ).raise_for_status()
    except Exception as exc:
        # Never break the app if DB is unavailable.
        LOGGER.error("Failed to save editor job %s to Supabase: %s", jid, exc)
    return jid


def load_persistent_editor_job(job_id: str) -> Optional[Dict[str, Any]]:
    jid = _safe_job_id(job_id)

    if supabase_configured():
        try:
            url = f"{_supabase_url()}/rest/v1/errorsweep_editor_jobs?id=eq.{quote(jid)}&select=*"
            res = requests.get(url, headers=_headers(), timeout=SUPABASE_TIMEOUT)
            res.raise_for_status()
            data = res.json()
            if isinstance(data, list) and data:
                row = data[0]
                metadata = row.get("metadata") or {}
                return {
                    "job_id": row.get("id") or jid,
                    "job_type": row.get("job_type") or metadata.get("job_type") or "cat",
                    "rows": row.get("rows") or [],
                    "metadata": metadata,
                    "title": metadata.get("title") or metadata.get("source") or "ErrorSweep CAT",
                    "target_language": row.get("target_language") or metadata.get("target_language") or "",
                    "file_name": row.get("file_name") or metadata.get("file_name") or "",
                    "created": str(row.get("created_at") or ""),
                    "updated_at": str(row.get("updated_at") or ""),
                }
        except Exception as exc:
            LOGGER.error("Failed to load editor job %s from Supabase: %s", jid, exc)

    return _read_local_job(jid)


def update_persistent_editor_job(
    job_id: str,
    rows: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    status: Optional[str] = None,
) -> bool:
    jid = _safe_job_id(job_id)
    local_payload = _read_local_job(jid) or {
        "job_id": jid,
        "id": jid,
        "job_type": "cat",
        "rows": [],
        "metadata": {},
        "created_at": _now_iso(),
        "created_at_epoch": time.time(),
    }
    if rows is not None:
        local_payload["rows"] = rows
        local_payload["row_count"] = len(rows)
    if metadata is not None:
        merged = dict(local_payload.get("metadata") or {})
        merged.update(metadata)
        local_payload["metadata"] = merged
    if status:
        local_payload["status"] = status
        local_payload.setdefault("metadata", {})["status"] = status
    local_payload["updated_at"] = _now_iso()
    local_payload["updated_at_epoch"] = time.time()

    try:
        _write_local_job(local_payload)
    except Exception as exc:
        LOGGER.error("Failed to update local editor job fallback %s: %s", jid, exc)

    if not supabase_configured():
        return True

    try:
        patch_payload: Dict[str, Any] = {"updated_at": _now_iso()}
        if rows is not None:
            patch_payload["rows"] = rows
            patch_payload["row_count"] = len(rows)
        if metadata is not None:
            patch_payload["metadata"] = local_payload.get("metadata") or {}
        if status:
            patch_payload["status"] = status
        url = f"{_supabase_url()}/rest/v1/errorsweep_editor_jobs?id=eq.{quote(jid)}"
        res = requests.patch(url, headers=_headers({"Prefer": "return=minimal"}), json=patch_payload, timeout=SUPABASE_TIMEOUT)
        res.raise_for_status()
        return True
    except Exception as exc:
        LOGGER.error("Failed to update editor job %s in Supabase: %s", jid, exc)
        return False


# ==========================================================
# Usage event persistence
# ==========================================================

def log_persistent_usage_event(
    usage: Dict[str, Any],
    purpose: str = "translation",
    segment_count: int = 0,
    user: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    user = user or {}
    metadata = metadata or {}
    record = {
        "user_email": _current_user_email(user),
        "workspace": _current_workspace(user),
        "purpose": purpose,
        "provider": usage.get("provider") or usage.get("engine") or "unknown",
        "model": usage.get("model") or usage.get("engine") or "",
        "managed": bool(usage.get("managed", False)),
        "segments": int(segment_count or usage.get("segments") or 0),
        "characters": int(usage.get("characters") or usage.get("char_count") or 0),
        "requests": int(usage.get("requests") or usage.get("request_count") or 0),
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "success": bool(usage.get("success", True)),
        "error": str(usage.get("error") or "")[:1000],
        "metadata": metadata,
        "created_at": _now_iso(),
    }

    # Local audit trail fallback.
    try:
        with _LOCAL_WRITE_LOCK:
            _rotate_local_usage_events()
            with _local_usage_path().open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            _rotate_local_usage_events()
    except Exception as exc:
        LOGGER.error("Failed to write local usage event fallback: %s", exc)

    if not supabase_configured():
        return

    try:
        url = f"{_supabase_url()}/rest/v1/errorsweep_usage_events"
        requests.post(url, headers=_headers({"Prefer": "return=minimal"}), json=record, timeout=SUPABASE_TIMEOUT).raise_for_status()
    except Exception as exc:
        LOGGER.error("Failed to save usage event to Supabase: %s", exc)


def fetch_persistent_usage_events(limit: int = 200) -> List[Dict[str, Any]]:
    if supabase_configured():
        try:
            lim = max(1, min(int(limit), 1000))
            url = f"{_supabase_url()}/rest/v1/errorsweep_usage_events?select=*&order=created_at.desc&limit={lim}"
            res = requests.get(url, headers=_headers(), timeout=SUPABASE_TIMEOUT)
            res.raise_for_status()
            data = res.json()
            if isinstance(data, list):
                return data
        except Exception as exc:
            LOGGER.error("Failed to fetch usage events from Supabase: %s", exc)

    events: List[Dict[str, Any]] = []
    try:
        lines = _local_usage_path().read_text(encoding="utf-8").splitlines()
        for line in reversed(lines[-int(limit):]):
            try:
                events.append(json.loads(line))
            except Exception as exc:
                LOGGER.warning("Failed to parse local usage event: %s", exc)
    except Exception as exc:
        LOGGER.warning("Failed to read local usage events: %s", exc)
    return events


def fetch_persistent_editor_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    if supabase_configured():
        try:
            lim = max(1, min(int(limit), 1000))
            url = f"{_supabase_url()}/rest/v1/errorsweep_editor_jobs?select=id,job_type,user_email,workspace,file_name,target_language,status,row_count,created_at,updated_at&order=updated_at.desc&limit={lim}"
            res = requests.get(url, headers=_headers(), timeout=SUPABASE_TIMEOUT)
            res.raise_for_status()
            data = res.json()
            if isinstance(data, list):
                return data
        except Exception as exc:
            LOGGER.error("Failed to fetch editor jobs from Supabase: %s", exc)

    jobs = []
    for path in sorted(_local_root().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[: int(limit)]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            jobs.append({
                "id": payload.get("job_id") or path.stem,
                "job_type": payload.get("job_type"),
                "file_name": (payload.get("metadata") or {}).get("file_name") or payload.get("file_name"),
                "target_language": (payload.get("metadata") or {}).get("target_language") or payload.get("target_language"),
                "status": (payload.get("metadata") or {}).get("status") or payload.get("status", "draft"),
                "row_count": len(payload.get("rows") or []),
                "updated_at": payload.get("updated_at"),
            })
        except Exception as exc:
            LOGGER.warning("Failed to read local editor job listing %s: %s", path, exc)
    return jobs


# ==========================================================
# SaaS record persistence
# ==========================================================

def save_saas_record(collection: str, record: Dict[str, Any], user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Persist a platform record with Supabase when configured and local JSON fallback.

    Supported collections include users, workspaces, projects, jobs, payments,
    invoices, subscriptions, checkout sessions, auth tokens, platform settings, privacy
    requests, support tickets, status incidents, consent records, files, notifications,
    task queue records, and audit logs.
    The app can keep using session state, while this function gives those records
    durable storage for production SaaS operation.
    """
    if collection not in SAAS_TABLES:
        raise ValueError(f"Unsupported SaaS collection: {collection}")

    payload = _normalise_saas_record(collection, record, user=user)
    try:
        _upsert_local_saas_record(collection, payload)
    except Exception as exc:
        LOGGER.error("Failed to write local SaaS record %s/%s: %s", collection, payload.get("id"), exc)

    if not supabase_configured():
        return payload

    try:
        table = SAAS_TABLES[collection]
        url = f"{_supabase_url()}/rest/v1/{table}?on_conflict=id"
        db_payload = {k: v for k, v in payload.items() if k in SAAS_COLUMNS[collection]}
        requests.post(
            url,
            headers=_headers({"Prefer": "resolution=merge-duplicates,return=representation"}),
            json=db_payload,
            timeout=SUPABASE_TIMEOUT,
        ).raise_for_status()
    except Exception as exc:
        LOGGER.error("Failed to save SaaS record %s/%s to Supabase: %s", collection, payload.get("id"), exc)
    return payload


def fetch_saas_records(
    collection: str,
    workspace: str = "",
    limit: int = 500,
    include_all_workspaces: bool = False,
) -> List[Dict[str, Any]]:
    if collection not in SAAS_TABLES:
        raise ValueError(f"Unsupported SaaS collection: {collection}")

    lim = max(1, min(int(limit), 1000))
    if supabase_configured():
        try:
            table = SAAS_TABLES[collection]
            filters = [f"select=*", f"order=updated_at.desc", f"limit={lim}"]
            if workspace and not include_all_workspaces:
                filters.append(f"workspace=eq.{quote(workspace)}")
            url = f"{_supabase_url()}/rest/v1/{table}?{'&'.join(filters)}"
            res = requests.get(url, headers=_headers(), timeout=SUPABASE_TIMEOUT)
            res.raise_for_status()
            data = res.json()
            if isinstance(data, list):
                return data
        except Exception as exc:
            LOGGER.error("Failed to fetch SaaS records %s from Supabase: %s", collection, exc)

    records = _read_local_collection(collection)
    if workspace and not include_all_workspaces:
        records = [r for r in records if str(r.get("workspace") or "") == workspace]
    return records[:lim]


def delete_saas_record(collection: str, record_id: str) -> bool:
    """Delete a SaaS record from local fallback and Supabase when configured."""
    if collection not in SAAS_TABLES:
        raise ValueError(f"Unsupported SaaS collection: {collection}")

    rid = str(record_id or "").strip()
    if not rid:
        return False

    deleted = False
    try:
        records = _read_local_collection(collection)
        retained = [item for item in records if str(item.get("id") or "") != rid]
        if len(retained) != len(records):
            _write_local_collection(collection, retained)
            deleted = True
    except Exception as exc:
        LOGGER.error("Failed to delete local SaaS record %s/%s: %s", collection, rid, exc)

    if not supabase_configured():
        return deleted

    try:
        table = SAAS_TABLES[collection]
        url = f"{_supabase_url()}/rest/v1/{table}?id=eq.{quote(rid)}"
        requests.delete(
            url,
            headers=_headers({"Prefer": "return=minimal"}),
            timeout=SUPABASE_TIMEOUT,
        ).raise_for_status()
        deleted = True
    except Exception as exc:
        LOGGER.error("Failed to delete SaaS record %s/%s from Supabase: %s", collection, rid, exc)
    return deleted


# ==========================================================
# Diagnostics
# ==========================================================

def persistence_health() -> Dict[str, Any]:
    health = {
        "supabase_configured": supabase_configured(),
        "storage_mode": "supabase" if supabase_configured() else "local_json_fallback",
        "local_job_dir": str(_local_root()),
        "editor_jobs_table": "unknown",
        "usage_events_table": "unknown",
        "saas_tables": {},
        "error": "",
    }
    if not supabase_configured():
        health["editor_jobs_table"] = "not_checked"
        health["usage_events_table"] = "not_checked"
        health["saas_tables"] = {table: "not_checked" for table in SAAS_TABLES.values()}
        return health

    try:
        url = f"{_supabase_url()}/rest/v1/errorsweep_editor_jobs?select=id&limit=1"
        res = requests.get(url, headers=_headers(), timeout=SUPABASE_TIMEOUT)
        health["editor_jobs_table"] = "ok" if res.status_code < 400 else f"error_{res.status_code}"
    except Exception as exc:
        health["editor_jobs_table"] = "error"
        health["error"] = str(exc)[:300]

    try:
        url = f"{_supabase_url()}/rest/v1/errorsweep_usage_events?select=id&limit=1"
        res = requests.get(url, headers=_headers(), timeout=SUPABASE_TIMEOUT)
        health["usage_events_table"] = "ok" if res.status_code < 400 else f"error_{res.status_code}"
    except Exception as exc:
        health["usage_events_table"] = "error"
        if not health["error"]:
            health["error"] = str(exc)[:300]

    for table in SAAS_TABLES.values():
        try:
            url = f"{_supabase_url()}/rest/v1/{table}?select=id&limit=1"
            res = requests.get(url, headers=_headers(), timeout=SUPABASE_TIMEOUT)
            health["saas_tables"][table] = "ok" if res.status_code < 400 else f"error_{res.status_code}"
        except Exception as exc:
            health["saas_tables"][table] = "error"
            if not health["error"]:
                health["error"] = str(exc)[:300]

    return health

