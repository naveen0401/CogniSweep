import os
from pathlib import Path

import async_task_worker
import cloud_object_storage
import email_dispatch_worker


COMPOSE = Path("docker-compose.production.yml")
PERSISTENCE = Path("production_persistence.py")
WORKFLOW = Path(".github/workflows/release-gate.yml")
RELEASE_CHECK = Path("deploy/release_check.py")
ASYNC_CHECK = Path("deploy/async_worker_check.py")
BILLING_CHECK = Path("deploy/billing_check.py")
OBJECT_STORAGE_CHECK = Path("deploy/object_storage_check.py")


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def with_env(values):
    previous = {key: os.environ.get(key) for key in values}
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


def test_async_worker_token_is_required_in_production_and_compared_constant_time():
    previous = with_env(
        {
            "ERRORSWEEP_ENV": "production",
            "ERRORSWEEP_ASYNC_WORKER_TOKEN": None,
            "ERRORSWEEP_ASYNC_WORKER_REQUIRE_TOKEN": None,
        }
    )
    try:
        assert async_task_worker.require_token()
        try:
            async_task_worker.validate_worker_token_config()
            raise AssertionError("Expected missing production worker token to fail closed.")
        except RuntimeError as exc:
            assert "ERRORSWEEP_ASYNC_WORKER_TOKEN is required" in str(exc)
    finally:
        restore_env(previous)

    text = source(Path("async_task_worker.py"))
    assert "hmac.compare_digest" in text


def test_email_dispatch_rejects_header_injection_before_sending():
    previous = with_env(
        {
            "ERRORSWEEP_EMAIL_PROVIDER": "resend",
            "ERRORSWEEP_EMAIL_FROM": "no-reply@example.com",
            "RESEND_API_KEY": "unused-in-this-test",
        }
    )
    try:
        recipient_result = email_dispatch_worker.dispatch_notification(
            {"id": "n1", "recipient": "victim@example.com\nbcc:bad@example.com", "subject": "Hello", "body": "Body"}
        )
        assert recipient_result["status"] == "failed"
        assert "newline" in recipient_result["error"].lower() or "invalid" in recipient_result["error"].lower()

        subject_result = email_dispatch_worker.dispatch_notification(
            {"id": "n2", "recipient": "victim@example.com", "subject": "Hello\r\nBcc: bad@example.com", "body": "Body"}
        )
        assert subject_result["status"] == "failed"
        assert "newline" in subject_result["error"].lower()
    finally:
        restore_env(previous)


def test_object_storage_public_urls_are_opt_in():
    previous = with_env(
        {
            "ERRORSWEEP_OBJECT_STORAGE_PROVIDER": "s3",
            "S3_BUCKET": "errorsweep-test",
            "S3_PUBLIC_BASE_URL": "https://cdn.example.com/files",
            "ERRORSWEEP_OBJECT_STORAGE_ALLOW_PUBLIC_URLS": None,
        }
    )
    try:
        assert cloud_object_storage.public_url_for_key("workspace/file.txt") == ""
        os.environ["ERRORSWEEP_OBJECT_STORAGE_ALLOW_PUBLIC_URLS"] = "true"
        assert cloud_object_storage.public_url_for_key("workspace/file.txt") == "https://cdn.example.com/files/workspace/file.txt"
        assert cloud_object_storage.object_storage_status()["public_urls_enabled"] is True
    finally:
        restore_env(previous)


def test_compose_binds_internal_services_to_localhost():
    compose = source(COMPOSE)
    for token in [
        "127.0.0.1:8300:8300",
        "127.0.0.1:8301:8301",
        "127.0.0.1:6379:6379",
    ]:
        assert token in compose
    assert '"8300:8300"' not in compose
    assert '"8301:8301"' not in compose
    assert '"6379:6379"' not in compose


def test_placeholders_and_release_checks_are_aligned():
    persistence = source(PERSISTENCE)
    assert 'SUPABASE_URL = "https://your-project.supabase.co"' not in persistence
    assert 'SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"' not in persistence

    for path in [WORKFLOW, RELEASE_CHECK, ASYNC_CHECK, BILLING_CHECK, OBJECT_STORAGE_CHECK]:
        text = source(path)
        assert "test_excel_backlog_security_hardening.py" in text or path not in {WORKFLOW, RELEASE_CHECK}
    assert "127.0.0.1:8300:8300" in source(ASYNC_CHECK)
    assert "127.0.0.1:8301:8301" in source(BILLING_CHECK)
    assert "ERRORSWEEP_OBJECT_STORAGE_ALLOW_PUBLIC_URLS" in source(OBJECT_STORAGE_CHECK)


if __name__ == "__main__":
    test_async_worker_token_is_required_in_production_and_compared_constant_time()
    test_email_dispatch_rejects_header_injection_before_sending()
    test_object_storage_public_urls_are_opt_in()
    test_compose_binds_internal_services_to_localhost()
    test_placeholders_and_release_checks_are_aligned()
    print("Excel backlog security hardening checks passed.")
