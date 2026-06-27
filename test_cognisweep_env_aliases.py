"""Regression coverage for CogniSweep-prefixed deployment settings."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="ignore")


def with_env(updates: dict[str, str | None]) -> dict[str, str | None]:
    previous = {key: os.environ.get(key) for key in updates}
    for key, value in updates.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return previous


def restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def fresh_import(module_name: str):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_app_secret_helpers_support_cognisweep_prefix() -> None:
    app = read("app.py")
    runtime_config = read("app_runtime_config.py")
    platform_constants = read("app_platform_constants.py")

    assert "from app_runtime_config import" in app
    assert "def cognisweep_env_alias" in runtime_config
    assert 'return f"COGNISWEEP_{name[len(\'ERRORSWEEP_\'):]}"' in runtime_config
    assert 'runtime_env("ERRORSWEEP_SESSION_PERSISTENCE_SECONDS"' in platform_constants
    assert "st.secrets.get(alias)" in app


def test_async_worker_queue_accepts_cognisweep_prefix() -> None:
    previous = with_env(
        {
            "ERRORSWEEP_ENV": None,
            "ERRORSWEEP_ASYNC_WORKER_URL": None,
            "ERRORSWEEP_ASYNC_WORKER_TOKEN": None,
            "COGNISWEEP_ENV": "production",
            "COGNISWEEP_ASYNC_WORKER_URL": "https://worker.example.com/tasks",
            "COGNISWEEP_ASYNC_WORKER_TOKEN": "worker-token",
        }
    )
    try:
        queue = fresh_import("async_worker_queue")
        status = queue.async_backend_status()
        assert status["ready"] is True
        assert status["provider"] == "http"
        assert status["mode"] == "external"
        assert status["worker_url"] == "https://worker.example.com/tasks"
    finally:
        restore_env(previous)
        sys.modules.pop("async_worker_queue", None)


def test_production_persistence_accepts_cognisweep_prefix() -> None:
    previous = with_env({"ERRORSWEEP_ENV": None, "COGNISWEEP_ENV": "production"})
    try:
        persistence = fresh_import("production_persistence")
        assert persistence.is_production_mode() is True
    finally:
        restore_env(previous)
        sys.modules.pop("production_persistence", None)


def test_release_checker_accepts_cognisweep_template_keys() -> None:
    release_check = fresh_import("deploy.release_check")
    env_template = read("deploy/.env.production.example")
    secrets_template = read(".streamlit/secrets.toml.example")
    assert release_check.template_has_env_key(env_template, "ERRORSWEEP_PUBLIC_BASE_URL")
    assert release_check.template_has_env_key(env_template, "ERRORSWEEP_OWNER_PASSWORD_HASH")
    assert release_check.template_has_env_key(secrets_template, "ERRORSWEEP_EMAIL_FROM")
    assert "COGNISWEEP_PUBLIC_BASE_URL=" in env_template
    assert 'COGNISWEEP_PUBLIC_BASE_URL = "https://app.cognisweep.com"' in secrets_template


if __name__ == "__main__":
    test_app_secret_helpers_support_cognisweep_prefix()
    test_async_worker_queue_accepts_cognisweep_prefix()
    test_production_persistence_accepts_cognisweep_prefix()
    test_release_checker_accepts_cognisweep_template_keys()
    print("cognisweep env alias tests passed")
