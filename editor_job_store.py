"""Tiny JSON-backed editor job store for ErrorSweep v41.

This lets the Streamlit dashboard open CAT/subtitle editors in a separate
browser tab using a job_id. Streamlit session_state is not reliable across
new tabs, so rows are written to a temporary JSON file.

MVP storage: local temp directory. Future production storage: Supabase table
or object storage.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 2  # 48 hours


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
        keep = uuid.uuid4().hex
    return keep[:96]


def _path_for(job_id: str) -> Path:
    return _job_dir() / f"{_safe_job_id(job_id)}.json"


def save_editor_job(job_type: str, rows: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None, job_id: Optional[str] = None) -> str:
    job_id = _safe_job_id(job_id or uuid.uuid4().hex)
    payload = {
        "job_id": job_id,
        "job_type": job_type,
        "rows": rows or [],
        "metadata": metadata or {},
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _path_for(job_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    cleanup_old_jobs()
    return job_id


def load_editor_job(job_id: str) -> Optional[Dict[str, Any]]:
    path = _path_for(job_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload


def update_editor_job(job_id: str, rows: Optional[List[Dict[str, Any]]] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
    payload = load_editor_job(job_id)
    if not payload:
        return False
    if rows is not None:
        payload["rows"] = rows
    if metadata is not None:
        merged = dict(payload.get("metadata") or {})
        merged.update(metadata)
        payload["metadata"] = merged
    payload["updated_at"] = time.time()
    _path_for(job_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def cleanup_old_jobs(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    now = time.time()
    for path in _job_dir().glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            updated = float(payload.get("updated_at") or payload.get("created_at") or 0)
            if updated and now - updated > ttl_seconds:
                path.unlink(missing_ok=True)
        except Exception:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass

