import os
from contextlib import contextmanager
from pathlib import Path

import production_persistence as pp


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"
RELEASE_CHECK = ROOT / "deploy" / "release_check.py"


@contextmanager
def patched_env(**updates):
    keys = set(updates) | {"SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "ERRORSWEEP_ENV", "ENVIRONMENT", "APP_ENV"}
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        for key, value in updates.items():
            if value is not None:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def assert_raises_runtime_error(fn, expected):
    try:
        fn()
    except RuntimeError as exc:
        assert expected in str(exc)
        return
    raise AssertionError("expected RuntimeError")


def test_production_requires_supabase_configuration():
    with patched_env(ERRORSWEEP_ENV="production"):
        assert pp.is_production_mode()
        assert not pp.local_json_fallback_allowed()
        assert not pp.supabase_configured()
        assert_raises_runtime_error(
            pp.require_supabase_for_production,
            "Supabase persistence is required in production",
        )
        assert_raises_runtime_error(
            lambda: pp.fetch_saas_records("jobs", workspace="Acme"),
            "Supabase persistence is required in production",
        )
        health = pp.persistence_health()
        assert health["storage_mode"] == "blocked_missing_supabase"
        assert health["production_ready"] is False


def test_development_allows_local_json_fallback():
    with patched_env(ERRORSWEEP_ENV="development"):
        assert not pp.is_production_mode()
        assert pp.local_json_fallback_allowed()
        pp.require_supabase_for_production()
        health = pp.persistence_health()
        assert health["storage_mode"] == "local_json_fallback"
        assert health["production_ready"] is True


def test_app_startup_and_release_gate_enforce_persistence_guard():
    app = APP.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    release_check = RELEASE_CHECK.read_text(encoding="utf-8")

    assert "require_supabase_for_production" in app
    assert "Production persistence configuration blocked startup" in app
    assert "python test_production_persistence_fail_closed.py" in workflow
    assert "Production persistence fail-closed fallback" in release_check


if __name__ == "__main__":
    test_production_requires_supabase_configuration()
    test_development_allows_local_json_fallback()
    test_app_startup_and_release_gate_enforce_persistence_guard()
    print("Production persistence fail-closed checks passed.")
