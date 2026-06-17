import os
from pathlib import Path

import async_worker_queue as queue


APP = Path("app.py")
ASYNC_QUEUE = Path("async_worker_queue.py")
ASYNC_CHECK = Path("deploy/async_worker_check.py")
WORKFLOW = Path(".github/workflows/release-gate.yml")


TRACKED_ENV = [
    "ERRORSWEEP_ENV",
    "APP_ENV",
    "ERRORSWEEP_ASYNC_BACKEND",
    "ERRORSWEEP_ASYNC_WORKER_URL",
    "ERRORSWEEP_WORKER_ENDPOINT",
    "REDIS_URL",
    "CELERY_BROKER_URL",
]


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def with_env(values):
    previous = {key: os.environ.get(key) for key in TRACKED_ENV}
    for key in TRACKED_ENV:
        os.environ.pop(key, None)
    os.environ.update(values)
    return previous


def restore_env(previous):
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_local_development_still_allows_inline_fallback():
    previous = with_env({})
    try:
        status = queue.async_backend_status()
        assert status["provider"] == "local"
        assert status["ready"] is True
        assert status["mode"] == "local_inline"
        result = queue.enqueue_async_task({"id": "task-1", "task_type": "qa"}, {"rows": []})
        assert result["queued"] is False
        assert "run inline" in result["message"]
    finally:
        restore_env(previous)


def test_production_without_external_backend_fails_closed():
    previous = with_env({"ERRORSWEEP_ENV": "production"})
    try:
        status = queue.async_backend_status()
        assert status["provider"] == "local"
        assert status["ready"] is False
        assert status["mode"] == "blocked"
        assert "Production requires" in status["message"]
        try:
            queue.enqueue_async_task({"id": "task-1", "task_type": "qa"}, {"rows": []})
        except RuntimeError as exc:
            assert "External async backend" in str(exc) or "Production requires" in str(exc)
        else:
            raise AssertionError("production enqueue must fail closed")
    finally:
        restore_env(previous)


def test_production_http_backend_remains_external():
    previous = with_env({
        "ERRORSWEEP_ENV": "production",
        "ERRORSWEEP_ASYNC_WORKER_URL": "https://worker.example.com/tasks",
    })
    try:
        status = queue.async_backend_status()
        assert status["provider"] == "http"
        assert status["ready"] is True
        assert status["mode"] == "external"
    finally:
        restore_env(previous)


def test_release_gate_covers_async_fail_closed():
    app = source(APP)
    async_queue = source(ASYNC_QUEUE)
    async_check = source(ASYNC_CHECK)
    workflow = source(WORKFLOW)

    assert "Async worker queue is unavailable. Production QA/Pro work was not run inline." in app
    assert "External async backend is required in production." in app
    assert "def is_production_mode" in async_queue
    assert '"mode": mode' in async_queue
    assert '"blocked"' in async_queue
    assert "Production requires ERRORSWEEP_ASYNC_WORKER_URL or REDIS_URL/CELERY_BROKER_URL" in async_queue
    assert "is_production_mode" in async_check
    assert "blocked" in async_check
    assert "python test_async_fail_closed.py" in workflow


if __name__ == "__main__":
    test_local_development_still_allows_inline_fallback()
    test_production_without_external_backend_fails_closed()
    test_production_http_backend_remains_external()
    test_release_gate_covers_async_fail_closed()
    print("Async fail-closed checks passed.")
