from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_owner_credentials_are_secret_backed() -> None:
    app = read_text("app.py")

    assert "errorsweep_unlimited_adapa_2026" not in app
    assert "adapalanaveen" not in app.lower()
    assert "Naveen Unlimited Workspace" not in app
    assert "ERRORSWEEP_UNLIMITED_ACCESS_EMAIL" in app
    assert "ERRORSWEEP_UNLIMITED_ACCESS_PASSWORD_HASH" in app
    assert "ERRORSWEEP_UNLIMITED_ACCESS_WORKSPACE" in app


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
    test_supabase_schema_has_tenant_rls_policies()
    test_async_queue_fails_closed_in_production()
    test_external_editor_jobs_are_random_and_scoped()
    test_dependencies_are_pinned_and_lockfile_exists()
    test_retired_local_mt_servers_are_absent()
    test_browser_eval_pattern_removed()
    print("Security audit regression checks passed.")
