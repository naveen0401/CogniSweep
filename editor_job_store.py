"""Tiny JSON-backed editor job store for CogniSweep v41.

This lets the Streamlit dashboard open CAT/subtitle editors in a separate
browser tab using a job_id. Streamlit session_state is not reliable across
new tabs, so rows are written to a temporary JSON file.

MVP storage: local temp directory. Future production storage: Supabase table
or object storage.
"""
from __future__ import annotations

import json
import logging
import os
import base64
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from local_file_lock import process_file_lock

DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 2  # 48 hours
LOGGER = logging.getLogger(__name__)
_WRITE_LOCK = threading.RLock()


def _job_dir() -> Path:
    path = os.environ.get("ERRORSWEEP_EDITOR_JOB_DIR")
    if path:
        root = Path(path)
    else:
        root = Path(tempfile.gettempdir()) / "errorsweep_editor_jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_job_id(job_id: str) -> str:
    job_id = str(job_id or "").strip()
    keep = "".join(ch for ch in job_id if ch.isalnum() or ch in {"-", "_"})
    if not keep:
        keep = _random_job_id()
    return keep[:96]


def _random_job_id() -> str:
    return base64.urlsafe_b64encode(os.urandom(24)).decode("ascii").rstrip("=")


def _scope_text(value: Any) -> str:
    return str(value or "").strip()


def _payload_value(payload: Dict[str, Any], *keys: str) -> str:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    for source in (payload, metadata):
        for key in keys:
            value = _scope_text(source.get(key))
            if value:
                return value
    return ""


def _payload_owned_by(
    payload: Dict[str, Any],
    *,
    workspace: str = "",
    user_email: str = "",
    allow_platform: bool = False,
) -> bool:
    if allow_platform:
        return True
    workspace_key = _scope_text(workspace).lower()
    user_key = _scope_text(user_email).lower()
    if not workspace_key and not user_key:
        return False

    payload_workspace = _payload_value(payload, "workspace", "client").lower()
    if workspace_key and payload_workspace and payload_workspace != workspace_key:
        return False

    explicit_users = {
        _scope_text(value).lower()
        for value in (
            _payload_value(payload, "user_email"),
            _payload_value(payload, "email"),
            _payload_value(payload, "owner_email"),
            _payload_value(payload, "assignee"),
            _payload_value(payload, "created_by"),
        )
        if _scope_text(value)
    }
    if user_key and explicit_users:
        return user_key in explicit_users
    return bool(workspace_key and payload_workspace == workspace_key)


def _path_for(job_id: str) -> Path:
    return _job_dir() / f"{_safe_job_id(job_id)}.json"


def _process_lock_path(scope: str = "editor_jobs") -> Path:
    safe = "".join(ch for ch in str(scope or "") if ch.isalnum() or ch in {"-", "_"})
    return _job_dir() / f".{safe or 'editor_jobs'}.lock"


@contextmanager
def _write_guard(scope: str = "editor_jobs"):
    with process_file_lock(_process_lock_path(scope)):
        with _WRITE_LOCK:
            yield


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def save_editor_job(job_type: str, rows: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None, job_id: Optional[str] = None) -> str:
    job_id = _safe_job_id(job_id or _random_job_id())
    payload = {
        "job_id": job_id,
        "job_type": job_type,
        "rows": rows or [],
        "metadata": metadata or {},
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    with _write_guard("editor_jobs"):
        _atomic_write_text(_path_for(job_id), json.dumps(payload, ensure_ascii=False, indent=2))
        _cleanup_old_jobs_unlocked()
    return job_id


def load_editor_job(
    job_id: str,
    *,
    workspace: str = "",
    user_email: str = "",
    allow_platform: bool = False,
) -> Optional[Dict[str, Any]]:
    path = _path_for(job_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("Unable to read editor job %s: %s", path, exc)
        return None
    if not _payload_owned_by(payload, workspace=workspace, user_email=user_email, allow_platform=allow_platform):
        LOGGER.warning("Denied editor job load outside caller scope: %s", _safe_job_id(job_id))
        return None
    return payload


def update_editor_job(
    job_id: str,
    rows: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    *,
    workspace: str = "",
    user_email: str = "",
    allow_platform: bool = False,
) -> bool:
    with _write_guard("editor_jobs"):
        payload = load_editor_job(job_id, workspace=workspace, user_email=user_email, allow_platform=allow_platform)
        if not payload:
            return False
        if rows is not None:
            payload["rows"] = rows
        if metadata is not None:
            merged = dict(payload.get("metadata") or {})
            merged.update(metadata)
            payload["metadata"] = merged
        payload["updated_at"] = time.time()
        _atomic_write_text(_path_for(job_id), json.dumps(payload, ensure_ascii=False, indent=2))
    return True


def _cleanup_old_jobs_unlocked(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    now = time.time()
    for path in _job_dir().glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            updated = float(payload.get("updated_at") or payload.get("created_at") or 0)
            if updated and now - updated > ttl_seconds:
                path.unlink(missing_ok=True)
        except Exception as exc:
            LOGGER.warning("Unable to clean editor job %s: %s", path, exc)
            try:
                path.unlink(missing_ok=True)
            except Exception as unlink_exc:
                LOGGER.warning("Unable to remove editor job %s: %s", path, unlink_exc)


def cleanup_old_jobs(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    with _write_guard("editor_jobs"):
        _cleanup_old_jobs_unlocked(ttl_seconds=ttl_seconds)

