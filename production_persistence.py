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
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days local fallback retention
SUPABASE_TIMEOUT = 25


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
        except Exception:
            pass
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


def _write_local_job(payload: Dict[str, Any]) -> None:
    _local_path(payload["job_id"]).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    cleanup_local_jobs()


def _read_local_job(job_id: str) -> Optional[Dict[str, Any]]:
    path = _local_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def cleanup_local_jobs(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    now = time.time()
    for path in _local_root().glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            updated = float(payload.get("updated_at_epoch") or payload.get("created_at_epoch") or 0)
            if updated and now - updated > ttl_seconds:
                path.unlink(missing_ok=True)
        except Exception:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass


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
    except Exception:
        pass

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
    except Exception:
        # Never break the app if DB is unavailable.
        pass
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
        except Exception:
            pass

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
    except Exception:
        pass

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
    except Exception:
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
        with _local_usage_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass

    if not supabase_configured():
        return

    try:
        url = f"{_supabase_url()}/rest/v1/errorsweep_usage_events"
        requests.post(url, headers=_headers({"Prefer": "return=minimal"}), json=record, timeout=SUPABASE_TIMEOUT).raise_for_status()
    except Exception:
        pass


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
        except Exception:
            pass

    events: List[Dict[str, Any]] = []
    try:
        lines = _local_usage_path().read_text(encoding="utf-8").splitlines()
        for line in reversed(lines[-int(limit):]):
            try:
                events.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        pass
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
        except Exception:
            pass

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
        except Exception:
            pass
    return jobs


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
        "error": "",
    }
    if not supabase_configured():
        health["editor_jobs_table"] = "not_checked"
        health["usage_events_table"] = "not_checked"
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

    return health

