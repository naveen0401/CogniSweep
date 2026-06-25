import os
import tempfile
from pathlib import Path

import editor_job_store as local_store
import production_persistence as persistence


APP = Path("app.py")
EDITOR_STORE = Path("editor_job_store.py")
PERSISTENCE = Path("production_persistence.py")
WORKFLOW = Path(".github/workflows/release-gate.yml")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_local_editor_job_ids_use_os_urandom_and_scope_loads():
    text = source(EDITOR_STORE)
    assert "os.urandom(24)" in text
    assert "uuid.uuid4" not in text

    previous_dir = os.environ.get("ERRORSWEEP_EDITOR_JOB_DIR")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["ERRORSWEEP_EDITOR_JOB_DIR"] = tmp
            job_id = local_store.save_editor_job(
                "cat",
                [{"source": "Hello", "target": "Bonjour"}],
                metadata={"workspace": "Acme", "user_email": "owner@example.com"},
            )

            assert len(job_id) >= 32
            assert local_store.load_editor_job(job_id, workspace="Acme", user_email="owner@example.com")
            assert local_store.load_editor_job(job_id, workspace="Other", user_email="owner@example.com") is None
            assert local_store.load_editor_job(job_id, workspace="Acme", user_email="other@example.com") is None
            assert local_store.load_editor_job(job_id, allow_platform=True)
            assert not local_store.update_editor_job(job_id, rows=[], workspace="Other", user_email="owner@example.com")
    finally:
        if previous_dir is None:
            os.environ.pop("ERRORSWEEP_EDITOR_JOB_DIR", None)
        else:
            os.environ["ERRORSWEEP_EDITOR_JOB_DIR"] = previous_dir


def test_persistent_local_fallback_requires_editor_scope():
    previous_dir = os.environ.get("ERRORSWEEP_EDITOR_JOB_DIR")
    original_url = persistence._supabase_url
    original_key = persistence._service_key
    persistence._supabase_url = lambda: ""
    persistence._service_key = lambda: ""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["ERRORSWEEP_EDITOR_JOB_DIR"] = tmp
            job_id = persistence.save_persistent_editor_job(
                "cat",
                [{"source": "Hello", "target": "Bonjour"}],
                metadata={"workspace": "Acme", "user_email": "owner@example.com"},
                user={"workspace": "Acme", "email": "owner@example.com"},
            )

            assert persistence.load_persistent_editor_job(job_id, workspace="Acme", user_email="owner@example.com")
            assert persistence.load_persistent_editor_job(job_id, workspace="Other", user_email="owner@example.com") is None
            assert persistence.load_persistent_editor_job(job_id, workspace="Acme", user_email="other@example.com") is None
            assert persistence.load_persistent_editor_job(job_id, include_all_workspaces=True, platform_scope_reason="owner_editor_audit")
            assert not persistence.update_persistent_editor_job(job_id, rows=[], workspace="Other", user_email="owner@example.com")
    finally:
        persistence._supabase_url = original_url
        persistence._service_key = original_key
        if previous_dir is None:
            os.environ.pop("ERRORSWEEP_EDITOR_JOB_DIR", None)
        else:
            os.environ["ERRORSWEEP_EDITOR_JOB_DIR"] = previous_dir


def test_app_editor_open_paths_are_scoped():
    app = source(APP)
    persistence_text = source(PERSISTENCE)
    workflow = source(WORKFLOW)

    for token in [
        "def new_editor_job_id()",
        "session_id = new_editor_job_id()",
        "job_id = new_editor_job_id()",
        "def editor_payload_belongs_to_current_user",
        "def editor_store_scope_kwargs",
        "def editor_persistence_scope",
        "load_editor_job(session_id, **editor_store_scope_kwargs())",
        "load_editor_job(job_id, **editor_store_scope_kwargs())",
        "update_editor_job(job_id, rows=rows, metadata=metadata, **editor_store_scope_kwargs())",
        '**editor_persistence_scope("editor_job_load")',
        '**editor_persistence_scope("external_editor_load")',
        '**editor_persistence_scope("external_editor_update")',
    ]:
        assert token in app

    assert "def _local_editor_payload_in_scope" in persistence_text
    assert "workspace=scope[\"workspace\"]" in persistence_text
    assert "user_email=scope[\"user_email\"]" in persistence_text
    assert "python test_editor_job_security.py" in workflow


def test_submitted_editor_jobs_close_for_lower_roles():
    app = source(APP)

    for token in [
        'EDITOR_SUBMITTED_QUERY_PARAM = "es_editor_submitted"',
        "SUBMITTED_EDITOR_STATUSES",
        "def can_reopen_submitted_editor_task",
        "def editor_payload_is_submitted",
        "if editor_payload_is_submitted(payload):",
        "return can_reopen_submitted_editor_task(candidate)",
        "def submit_external_editor_payload",
        '"status": "submitted"',
        "save_external_editor_payload(job_id, payload, trusted_access_checked=True)",
        "def handle_editor_submit_return",
        "handle_editor_submit_return()",
        "def job_history_record_is_submitted",
        "return can_reopen_submitted_editor_task(user)",
    ]:
        assert token in app


if __name__ == "__main__":
    test_local_editor_job_ids_use_os_urandom_and_scope_loads()
    test_persistent_local_fallback_requires_editor_scope()
    test_app_editor_open_paths_are_scoped()
    test_submitted_editor_jobs_close_for_lower_roles()
    print("Editor job security checks passed.")
