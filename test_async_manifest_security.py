import os
import tempfile
from pathlib import Path

import async_workflow_processor as worker


TRACKED_ENV = ["ERRORSWEEP_ASYNC_MAX_MANIFEST_BYTES"]


def with_env(values):
    previous = {key: os.environ.get(key) for key in TRACKED_ENV}
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return previous


def restore_env(previous):
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_manifest_rejects_unsupported_file_type_before_reading():
    try:
        worker.manifest_bytes({"file_name": "payload.exe", "local_path": "does-not-matter"})
    except ValueError as exc:
        assert "unsupported file type" in str(exc)
    else:
        raise AssertionError("unsupported queued file type must be rejected")


def test_manifest_rejects_declared_oversized_file_before_reading():
    previous = with_env({"ERRORSWEEP_ASYNC_MAX_MANIFEST_BYTES": "1024"})
    try:
        try:
            worker.manifest_bytes({"file_name": "payload.csv", "size_bytes": 1025, "local_path": "does-not-matter.csv"})
        except ValueError as exc:
            assert "exceeds async worker file limits" in str(exc)
        else:
            raise AssertionError("oversized queued file metadata must be rejected")
    finally:
        restore_env(previous)


def test_manifest_rejects_oversized_local_file():
    previous = with_env({"ERRORSWEEP_ASYNC_MAX_MANIFEST_BYTES": "1024"})
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "payload.csv"
        path.write_bytes(b"x" * 1025)
        try:
            try:
                worker.manifest_bytes({"file_name": "payload.csv", "local_path": str(path)})
            except ValueError as exc:
                assert "exceeds async worker file limits" in str(exc)
            else:
                raise AssertionError("oversized local queued file must be rejected")
        finally:
            restore_env(previous)


def test_remote_manifest_stream_is_size_capped(monkeypatch=None):
    previous = with_env({"ERRORSWEEP_ASYNC_MAX_MANIFEST_BYTES": "1024"})

    class FakeResponse:
        headers = {"Content-Length": "1025"}

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=1024):
            yield b"x" * 1025

        def close(self):
            return None

    original_get = worker.requests.get
    worker.requests.get = lambda *args, **kwargs: FakeResponse()
    try:
        try:
            worker.manifest_bytes({"file_name": "payload.csv", "public_url": "https://files.example.com/payload.csv"})
        except ValueError as exc:
            assert "exceeds async worker file limits" in str(exc)
        else:
            raise AssertionError("oversized remote queued file must be rejected")
    finally:
        worker.requests.get = original_get
        restore_env(previous)


if __name__ == "__main__":
    test_manifest_rejects_unsupported_file_type_before_reading()
    test_manifest_rejects_declared_oversized_file_before_reading()
    test_manifest_rejects_oversized_local_file()
    test_remote_manifest_stream_is_size_capped()
    print("Async manifest security tests passed.")
