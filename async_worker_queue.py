"""Async worker queue adapter for ErrorSweep.

This module keeps local development unchanged, while allowing production
deployments to hand long-running QA/Pro work to an external worker through one
of two lightweight routes:

- HTTP worker endpoint: ERRORSWEEP_ASYNC_WORKER_URL
- Redis queue: REDIS_URL, optional ERRORSWEEP_REDIS_QUEUE
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Dict

import requests

LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = int(os.getenv("ERRORSWEEP_ASYNC_QUEUE_TIMEOUT", "20"))


def _secret(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value not in (None, ""):
        return str(value)
    try:
        import streamlit as st

        value = st.secrets.get(name)
        if value not in (None, ""):
            return str(value)
    except Exception as exc:
        LOGGER.debug("Unable to read secret %s: %s", name, exc)
    return default


def async_backend_status() -> Dict[str, Any]:
    configured = _secret("ERRORSWEEP_ASYNC_BACKEND", "").strip().lower()
    worker_url = _secret("ERRORSWEEP_ASYNC_WORKER_URL", _secret("ERRORSWEEP_WORKER_ENDPOINT", "")).strip()
    redis_url = _secret("REDIS_URL", _secret("CELERY_BROKER_URL", "")).strip()
    provider = configured or ("http" if worker_url else "redis" if redis_url else "local")
    if provider in {"celery", "redis_list", "redis-queue"}:
        provider = "redis"
    queue_name = _secret("ERRORSWEEP_REDIS_QUEUE", "errorsweep:tasks")
    ready = provider == "local" or bool(worker_url if provider == "http" else redis_url if provider == "redis" else False)
    return {
        "provider": provider,
        "ready": ready,
        "mode": "external" if provider in {"http", "redis"} and ready else "local_inline",
        "worker_url": worker_url,
        "redis_queue": queue_name,
        "redis_configured": bool(redis_url),
    }


def _enqueue_http(payload: Dict[str, Any], worker_url: str) -> Dict[str, Any]:
    url = worker_url.rstrip("/")
    if not url.endswith("/tasks"):
        url = f"{url}/tasks"
    token = _secret("ERRORSWEEP_ASYNC_WORKER_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else None
    response = requests.post(url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    data = response.json() if response.content else {}
    return {
        "queued": True,
        "provider": "http",
        "external_id": str(data.get("id") or data.get("task_id") or payload.get("task_id") or ""),
        "message": "Queued through HTTP worker.",
    }


def _enqueue_redis(payload: Dict[str, Any], redis_url: str, queue_name: str) -> Dict[str, Any]:
    try:
        import redis
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("redis package is required for Redis async queue support. Install requirements.txt.") from exc
    client = redis.Redis.from_url(redis_url)
    external_id = str(payload.get("task_id") or uuid.uuid4().hex)
    payload = {**payload, "external_id": external_id, "queued_at": time.time()}
    client.rpush(queue_name, json.dumps(payload, ensure_ascii=False))
    return {
        "queued": True,
        "provider": "redis",
        "external_id": external_id,
        "message": f"Queued in Redis list {queue_name}.",
    }


def enqueue_async_task(task: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    status = async_backend_status()
    provider = status.get("provider")
    if provider not in {"http", "redis"} or not status.get("ready"):
        return {
            "queued": False,
            "provider": provider,
            "external_id": "",
            "message": "No external async backend configured; run inline.",
        }

    queue_payload = {
        "task_id": task.get("id"),
        "task_type": task.get("task_type"),
        "label": task.get("label"),
        "workspace": task.get("workspace"),
        "user_email": task.get("user_email"),
        "metadata": task.get("metadata_json") or {},
        "payload": payload,
    }
    if provider == "http":
        return _enqueue_http(queue_payload, str(status.get("worker_url") or ""))
    if provider == "redis":
        redis_url = _secret("REDIS_URL", _secret("CELERY_BROKER_URL", "")).strip()
        return _enqueue_redis(queue_payload, redis_url, str(status.get("redis_queue") or "errorsweep:tasks"))
    return {
        "queued": False,
        "provider": provider,
        "external_id": "",
        "message": "Unsupported async backend; run inline.",
    }
