from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_owner_credentials_are_secret_backed() -> None:
    app = read_text("app.py")
    billing_config = read_text("billing_config.py")
    source = app + billing_config

    assert "errorsweep_unlimited_adapa_2026" not in source
    assert "adapalanaveen" not in source.lower()
    assert "Naveen Unlimited Workspace" not in source
    assert "ERRORSWEEP_UNLIMITED_ACCESS_EMAIL" in billing_config
    assert "ERRORSWEEP_UNLIMITED_ACCESS_PASSWORD_HASH" in billing_config
    assert "ERRORSWEEP_UNLIMITED_ACCESS_WORKSPACE" in billing_config


def test_runtime_and_billing_config_are_extracted_from_app_module() -> None:
    app = read_text("app.py")
    runtime_config = read_text("app_runtime_config.py")
    platform_constants = read_text("app_platform_constants.py")
    billing_config = read_text("billing_config.py")
    billing_utils = read_text("billing_utils.py")
    auth_security = read_text("auth_security.py")
    text_utils = read_text("text_utils.py")

    assert "from app_runtime_config import" in app
    assert "from app_platform_constants import" in app
    assert "from billing_config import" in app
    assert "from billing_utils import" in app
    assert "from auth_security import" in app
    assert "from text_utils import safe_text" in app
    assert "def runtime_env(" not in app
    assert "SESSION_COLLECTION_LIMITS = {" not in app
    assert "LANGUAGE_CATALOG = [" not in app
    assert "PLAN_CATALOG = [" not in app
    assert "def plan_record(" not in app
    assert "def format_money(" not in app
    assert "def invoice_amounts(" not in app
    assert "def hash_password(" not in app
    assert "def verify_password(" not in app
    assert "def safe_text(" not in app
    assert "def runtime_env(" in runtime_config
    assert "SESSION_COLLECTION_LIMITS = {" in platform_constants
    assert "LANGUAGE_CATALOG = [" in platform_constants
    assert "PLAN_CATALOG = [" in billing_config
    assert "def plan_record(" in billing_utils
    assert "def format_money(" in billing_utils
    assert "def invoice_amounts(" in billing_utils
    assert "def hash_password(" in auth_security
    assert "def verify_password(" in auth_security
    assert "def safe_text(" in text_utils


def test_supabase_schema_has_tenant_rls_policies() -> None:
    schema = read_text("supabase_v42_release_schema.sql").lower()

    assert "enable row level security" in schema
    assert len(re.findall(r"\bcreate policy\b", schema)) >= 20
    assert "errorsweep_workspace_matches" in schema
    assert "errorsweep_email_matches" in schema
    assert "errorsweep_is_platform_owner" in schema


def test_async_queue_fails_closed_in_production() -> None:
    queue = read_text("async_worker_queue.py")

    assert 'mode = "external" if provider in {"http", "redis"} and ready else "local_inline"' in queue
    assert 'if is_production_mode() and mode != "external":' in queue
    assert 'raise RuntimeError(status.get("message") or "External async backend is required in production.")' in queue


def test_external_editor_jobs_are_random_and_scoped() -> None:
    store = read_text("editor_job_store.py")
    persistence = read_text("production_persistence.py")

    assert "os.urandom(24)" in store
    assert "_payload_owned_by(payload" in store
    assert "_tenant_filters(" in persistence
    assert "include_all_workspaces=include_all_workspaces" in persistence


def test_dependencies_are_pinned_and_lockfile_exists() -> None:
    requirements = read_text("requirements.txt")
    lockfile = ROOT / "requirements.lock.txt"

    assert lockfile.exists()
    assert ">=" not in requirements
    assert all("==" in line for line in requirements.splitlines() if line.strip() and not line.startswith("#"))


def test_retired_local_mt_servers_are_absent() -> None:
    retired = [
        "madlad_mt_server.py",
        "opus_mt_server_v45.py",
        "indictrans2_worker.py",
        "local_translation_engine.py",
        "selfhosted_mt_clients.py",
    ]

    for rel_path in retired:
        assert not (ROOT / rel_path).exists(), rel_path


def test_browser_eval_pattern_removed() -> None:
    app = read_text("app.py")

    assert "parentWin.eval" not in app
    assert ".eval(" not in app


if __name__ == "__main__":
    test_owner_credentials_are_secret_backed()
    test_runtime_and_billing_config_are_extracted_from_app_module()
    test_supabase_schema_has_tenant_rls_policies()
    test_async_queue_fails_closed_in_production()
    test_external_editor_jobs_are_random_and_scoped()
    test_dependencies_are_pinned_and_lockfile_exists()
    test_retired_local_mt_servers_are_absent()
    test_browser_eval_pattern_removed()
    print("Security audit regression checks passed.")
