"""Standalone async task receiver for ErrorSweep QA/Pro handoffs.

This service gives production deployments a real HTTP endpoint for
ERRORSWEEP_ASYNC_WORKER_URL. It accepts task handoffs from Streamlit, persists a
durable lifecycle record, stores a local spool copy, exposes health/status
endpoints for deployment checks, and can hand queued payloads to the standalone
QA/Pro workflow processor.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote, urlparse

from production_persistence import fetch_saas_records, save_saas_record

LOGGER = logging.getLogger("errorsweep.async_task_worker")
SERVICE_NAME = "errorsweep-async-task-worker"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8300
TERMINAL_STATUSES = {"completed", "failed", "cancelled", "needs_review"}

try:
    from async_workflow_processor import process_next_queued_task, process_task_payload
except Exception as exc:  # pragma: no cover - processor is optional in minimal receiver deployments
    LOGGER.warning("async_workflow_processor import failed: %s", exc)
    process_next_queued_task = None
    process_task_payload = None


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def env_bool(name: str, default: bool = False) -> bool:
    value = safe_text(os.getenv(name)).lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def worker_token() -> str:
    return safe_text(os.getenv("ERRORSWEEP_ASYNC_WORKER_TOKEN"))


def require_token() -> bool:
    return env_bool("ERRORSWEEP_ASYNC_WORKER_REQUIRE_TOKEN", bool(worker_token()))


def process_on_accept() -> bool:
    return env_bool("ERRORSWEEP_ASYNC_PROCESS_ON_ACCEPT", False)


def worker_root() -> Path:
    configured = safe_text(os.getenv("ERRORSWEEP_ASYNC_WORKER_DIR"))
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / "errorsweep_async_worker"
    root.mkdir(parents=True, exist_ok=True)
    return root


def spool_path(task_id: str) -> Path:
    safe = "".join(ch for ch in safe_text(task_id) if ch.isalnum() or ch in {"-", "_"})[:96]
    return worker_root() / f"{safe or uuid.uuid4().hex}.json"


def read_json_body(handler: BaseHTTPRequestHandler, max_bytes: int = 10 * 1024 * 1024) -> Dict[str, Any]:
    raw_length = handler.headers.get("Content-Length", "0")
    try:
        length = int(raw_length)
    except Exception:
        raise ValueError("Content-Length is invalid.")
    if length <= 0:
        return {}
    if length > max_bytes:
        raise ValueError("Request body is too large.")
    raw = handler.rfile.read(length)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Request JSON must be an object.")
    return data


def write_spool(task_id: str, payload: Dict[str, Any], status_record: Dict[str, Any]) -> None:
    document = {
        "service": SERVICE_NAME,
        "received_at": now_iso(),
        "task_id": task_id,
        "payload": payload,
        "status_record": status_record,
    }
    path = spool_path(task_id)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(document, ensure_ascii=False, indent=2, default=safe_text), encoding="utf-8")
    os.replace(temp_path, path)


def read_spool(task_id: str) -> Optional[Dict[str, Any]]:
    path = spool_path(task_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("Unable to read async task spool %s: %s", path, exc)
        return None


def status_from_existing(task_id: str) -> Optional[Dict[str, Any]]:
    try:
        for item in fetch_saas_records("task_queue", limit=1000, include_all_workspaces=True):
            if safe_text(item.get("id")) == safe_text(task_id):
                return item
    except Exception as exc:
        LOGGER.warning("Unable to fetch task status from persistence: %s", exc)
    return None


def task_payload_id(payload: Dict[str, Any]) -> str:
    return safe_text(payload.get("task_id") or payload.get("id") or uuid.uuid4().hex)


def normalize_task_record(payload: Dict[str, Any], status: str = "queued", progress: int = 5, error: str = "") -> Dict[str, Any]:
    task_id = task_payload_id(payload)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    task_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    workflow = safe_text(task_payload.get("workflow") or payload.get("task_type") or metadata.get("workflow"))
    queued_at = now_iso()
    record = {
        "id": task_id,
        "workspace": safe_text(payload.get("workspace") or metadata.get("workspace") or "Unassigned"),
        "user_email": safe_text(payload.get("user_email") or metadata.get("user_email") or "async-worker@errorsweep.local"),
        "task_type": safe_text(payload.get("task_type") or workflow or "external_task"),
        "label": safe_text(payload.get("label") or metadata.get("file_name") or workflow or task_id),
        "status": status,
        "progress": max(0, min(100, int(progress or 0))),
        "total_units": int(metadata.get("total_units") or metadata.get("row_count") or 0),
        "processed_units": 0,
        "result_ref": f"{SERVICE_NAME}:{task_id}",
        "error": safe_text(error)[:1000],
        "metadata_json": {
            **metadata,
            "external_worker": SERVICE_NAME,
            "external_worker_status": status,
            "received_at": queued_at,
            "workflow": workflow,
            "input_files": task_payload.get("input_files") or [],
            "rules_files": task_payload.get("rules_files") or [],
            "parameters": task_payload.get("parameters") or {},
            "processor_attached": False,
            "processor_note": "Task accepted by external worker receiver. Attach QA/Pro processors to execute the stored payload.",
        },
        "started_at": queued_at if status == "running" else "",
        "finished_at": queued_at if status in TERMINAL_STATUSES else "",
        "created_at": queued_at,
        "updated_at": queued_at,
    }
    return record


def persist_task_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return save_saas_record(
        "task_queue",
        record,
        user={
            "email": safe_text(record.get("user_email")) or "async-worker@errorsweep.local",
            "workspace": safe_text(record.get("workspace")) or "Platform",
        },
    )


def accept_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    record = normalize_task_record(payload, status="queued", progress=5)
    persisted = persist_task_record(record)
    write_spool(record["id"], payload, persisted)
    response = {
        "accepted": True,
        "id": record["id"],
        "task_id": record["id"],
        "status": persisted.get("status", "queued"),
        "message": "Task accepted by ErrorSweep async worker receiver.",
    }
    if process_on_accept():
        if process_task_payload is None:
            response["processor_status"] = "unavailable"
            response["processor_message"] = "ERRORSWEEP_ASYNC_PROCESS_ON_ACCEPT is enabled, but async_workflow_processor.py could not be imported."
        else:
            final_record = process_task_payload(payload)
            response["processor_status"] = safe_text(final_record.get("status"))
            response["processor_progress"] = final_record.get("progress")
    return response


def update_task_status(task_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    task_id = safe_text(task_id)
    existing = status_from_existing(task_id) or {}
    if not existing:
        spool = read_spool(task_id) or {}
        payload = spool.get("payload") if isinstance(spool.get("payload"), dict) else {"task_id": task_id}
        existing = normalize_task_record(payload, status="queued", progress=5)
    status = safe_text(updates.get("status") or existing.get("status") or "queued")
    progress = updates.get("progress", existing.get("progress", 0))
    try:
        progress = max(0, min(100, int(progress or 0)))
    except Exception:
        progress = int(existing.get("progress") or 0)
    metadata = existing.get("metadata_json") if isinstance(existing.get("metadata_json"), dict) else {}
    patch_metadata = updates.get("metadata_json") if isinstance(updates.get("metadata_json"), dict) else updates.get("metadata")
    if not isinstance(patch_metadata, dict):
        patch_metadata = {}
    now = now_iso()
    updated = {
        **existing,
        "id": task_id,
        "status": status,
        "progress": progress,
        "processed_units": int(updates.get("processed_units", existing.get("processed_units") or 0) or 0),
        "total_units": int(updates.get("total_units", existing.get("total_units") or 0) or 0),
        "result_ref": safe_text(updates.get("result_ref") or existing.get("result_ref") or f"{SERVICE_NAME}:{task_id}"),
        "error": safe_text(updates.get("error") or "")[:1000],
        "metadata_json": {
            **metadata,
            **patch_metadata,
            "external_worker": SERVICE_NAME,
            "external_worker_status": status,
            "last_worker_update_at": now,
        },
        "updated_at": now,
    }
    if status == "running" and not safe_text(updated.get("started_at")):
        updated["started_at"] = now
    if status in TERMINAL_STATUSES and not safe_text(updated.get("finished_at")):
        updated["finished_at"] = now
    persisted = persist_task_record(updated)
    spool = read_spool(task_id) or {"task_id": task_id, "payload": {}, "service": SERVICE_NAME}
    write_spool(task_id, spool.get("payload") if isinstance(spool.get("payload"), dict) else {"task_id": task_id}, persisted)
    return persisted


def authorize(headers: Any) -> Tuple[bool, str]:
    if not require_token():
        return True, ""
    expected = worker_token()
    provided = safe_text(headers.get("Authorization"))
    if provided.startswith("Bearer "):
        provided = provided[7:].strip()
    if not expected or provided != expected:
        return False, "Missing or invalid worker token."
    return True, ""


class AsyncTaskWorkerHandler(BaseHTTPRequestHandler):
    server_version = "ErrorSweepAsyncWorker/1.0"

    def _json(self, status: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, default=safe_text).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _not_found(self) -> None:
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), fmt % args)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/health":
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": SERVICE_NAME,
                    "time": now_iso(),
                    "token_required": require_token(),
                    "spool_dir": str(worker_root()),
                    "processor_available": process_task_payload is not None,
                    "process_on_accept": process_on_accept(),
                },
            )
            return
        if path.startswith("/tasks/"):
            task_id = unquote(path.split("/tasks/", 1)[1].strip("/"))
            status = status_from_existing(task_id)
            spool = read_spool(task_id)
            if not status and not spool:
                self._not_found()
                return
            self._json(HTTPStatus.OK, {"task_id": task_id, "status": status, "spool": spool})
            return
        self._not_found()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        ok, reason = authorize(self.headers)
        if not ok:
            self._json(HTTPStatus.UNAUTHORIZED, {"error": reason})
            return
        try:
            payload = read_json_body(self)
        except Exception as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": safe_text(exc)})
            return
        try:
            if path == "/tasks":
                self._json(HTTPStatus.ACCEPTED, accept_task(payload))
                return
            if path.startswith("/tasks/") and path.endswith("/status"):
                task_id = unquote(path.split("/tasks/", 1)[1].rsplit("/status", 1)[0].strip("/"))
                updated = update_task_status(task_id, payload)
                self._json(HTTPStatus.OK, {"updated": True, "task_id": task_id, "status": updated})
                return
        except Exception as exc:
            LOGGER.exception("Async worker request failed")
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": safe_text(exc)[:700]})
            return
        self._not_found()


def smoke_check() -> Dict[str, Any]:
    payload = {
        "task_id": f"smoke-{uuid.uuid4().hex[:12]}",
        "task_type": "smoke_test",
        "label": "Async worker smoke test",
        "workspace": "Platform",
        "user_email": "async-worker@errorsweep.local",
        "metadata": {"workflow": "smoke_test"},
        "payload": {"workflow": "smoke_test", "input_files": [], "rules_files": [], "parameters": {}},
    }
    accepted = accept_task(payload)
    updated = update_task_status(payload["task_id"], {"status": "completed", "progress": 100, "processed_units": 1, "total_units": 1})
    return {
        "accepted": accepted,
        "final_status": updated.get("status"),
        "spool_dir": str(worker_root()),
        "processor_available": process_task_payload is not None,
    }


def run_server(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), AsyncTaskWorkerHandler)
    LOGGER.info("Starting %s on http://%s:%s", SERVICE_NAME, host, port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ErrorSweep async task worker receiver.")
    parser.add_argument("--host", default=safe_text(os.getenv("ERRORSWEEP_ASYNC_WORKER_HOST")) or DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=int(os.getenv("ERRORSWEEP_ASYNC_WORKER_PORT", str(DEFAULT_PORT))))
    parser.add_argument("--smoke", action="store_true", help="Persist a smoke-test task and exit.")
    parser.add_argument("--process-once", action="store_true", help="Process the oldest queued worker-spooled task and exit.")
    args = parser.parse_args()
    logging.basicConfig(level=safe_text(os.getenv("ERRORSWEEP_ASYNC_WORKER_LOG_LEVEL")) or "INFO", format="%(asctime)s %(levelname)s %(message)s")
    if args.smoke:
        result = smoke_check()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=safe_text))
        return 0 if result.get("final_status") == "completed" else 1
    if args.process_once:
        if process_next_queued_task is None:
            print(json.dumps({"processed": False, "error": "async_workflow_processor.py is unavailable."}, indent=2))
            return 1
        result = process_next_queued_task()
        print(json.dumps(result or {"processed": False, "message": "No queued worker-spooled tasks."}, ensure_ascii=False, indent=2, default=safe_text))
        return 0
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
