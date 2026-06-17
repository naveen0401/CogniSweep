import os
import tempfile
from pathlib import Path

import editor_job_store
import production_persistence as persistence
from local_file_lock import process_file_lock


LOCK_HELPER = Path("local_file_lock.py")
EDITOR_STORE = Path("editor_job_store.py")
PERSISTENCE = Path("production_persistence.py")
WORKFLOW = Path(".github/workflows/release-gate.yml")
RELEASE_CHECK = Path("deploy/release_check.py")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_local_fallback_uses_process_file_locks():
    lock_helper = source(LOCK_HELPER)
    editor_store = source(EDITOR_STORE)
    persistence_text = source(PERSISTENCE)

    assert "msvcrt.locking" in lock_helper
    assert "fcntl.flock" in lock_helper
    assert "def process_file_lock" in lock_helper

    assert "from local_file_lock import process_file_lock" in editor_store
    assert "_WRITE_LOCK = threading.RLock()" in editor_store
    assert "def _write_guard" in editor_store
    assert "with _write_guard(\"editor_jobs\"):" in editor_store

    assert "from local_file_lock import process_file_lock" in persistence_text
    assert "_LOCAL_WRITE_LOCK = threading.RLock()" in persistence_text
    assert "def _local_write_guard" in persistence_text
    assert "with _local_write_guard(f\"collection_{collection}\"):" in persistence_text
    assert "_write_local_collection_unlocked(collection, records[:1000])" in persistence_text
    assert "_write_local_collection_unlocked(collection, retained)" in persistence_text


def test_process_file_lock_allows_normal_local_editor_flows():
    previous_dir = os.environ.get("ERRORSWEEP_EDITOR_JOB_DIR")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["ERRORSWEEP_EDITOR_JOB_DIR"] = tmp
            with process_file_lock(Path(tmp) / ".direct.lock"):
                assert (Path(tmp) / ".direct.lock").exists()

            job_id = editor_job_store.save_editor_job(
                "cat",
                [{"source": "Hello", "target": "Bonjour"}],
                metadata={"workspace": "Acme", "user_email": "owner@example.com"},
            )
            assert editor_job_store.update_editor_job(
                job_id,
                rows=[{"source": "Hi", "target": "Salut"}],
                workspace="Acme",
                user_email="owner@example.com",
            )
            payload = editor_job_store.load_editor_job(job_id, workspace="Acme", user_email="owner@example.com")
            assert payload
            assert payload["rows"][0]["target"] == "Salut"
            editor_job_store.cleanup_old_jobs(ttl_seconds=1)
    finally:
        if previous_dir is None:
            os.environ.pop("ERRORSWEEP_EDITOR_JOB_DIR", None)
        else:
            os.environ["ERRORSWEEP_EDITOR_JOB_DIR"] = previous_dir


def test_process_file_lock_allows_normal_persistence_collection_flows():
    previous_dir = os.environ.get("ERRORSWEEP_EDITOR_JOB_DIR")
    previous_env = os.environ.get("ERRORSWEEP_ENV")
    original_url = persistence._supabase_url
    original_key = persistence._service_key
    persistence._supabase_url = lambda: ""
    persistence._service_key = lambda: ""
    try:
        os.environ.pop("ERRORSWEEP_ENV", None)
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["ERRORSWEEP_EDITOR_JOB_DIR"] = tmp
            saved = persistence.save_saas_record(
                "projects",
                {"project": "Demo", "workspace": "Acme", "user_email": "owner@example.com"},
            )
            updated = persistence.save_saas_record(
                "projects",
                {**saved, "status": "active"},
            )
            records = persistence.fetch_saas_records(
                "projects",
                workspace="Acme",
                user_email="owner@example.com",
            )
            assert len(records) == 1
            assert records[0]["id"] == updated["id"]
            assert records[0]["status"] == "active"

            assert persistence.delete_saas_record(
                "projects",
                updated["id"],
                workspace="Acme",
                user_email="owner@example.com",
            )
            assert persistence.fetch_saas_records(
                "projects",
                workspace="Acme",
                user_email="owner@example.com",
            ) == []
    finally:
        persistence._supabase_url = original_url
        persistence._service_key = original_key
        if previous_dir is None:
            os.environ.pop("ERRORSWEEP_EDITOR_JOB_DIR", None)
        else:
            os.environ["ERRORSWEEP_EDITOR_JOB_DIR"] = previous_dir
        if previous_env is None:
            os.environ.pop("ERRORSWEEP_ENV", None)
        else:
            os.environ["ERRORSWEEP_ENV"] = previous_env


def test_process_file_lock_checks_are_in_release_gate():
    workflow = source(WORKFLOW)
    release_check = source(RELEASE_CHECK)
    assert "python test_process_file_locks.py" in workflow
    assert "python test_process_file_locks.py" in release_check
    assert '"local_file_lock.py"' in release_check


if __name__ == "__main__":
    test_local_fallback_uses_process_file_locks()
    test_process_file_lock_allows_normal_local_editor_flows()
    test_process_file_lock_allows_normal_persistence_collection_flows()
    test_process_file_lock_checks_are_in_release_gate()
    print("Process file lock checks passed.")
