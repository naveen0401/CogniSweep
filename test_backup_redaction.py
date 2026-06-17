from operational_backup_worker import (
    EXPORT_BINARY_VALUE,
    EXPORT_REDACTED_VALUE,
    configured_collections,
    redact_export_value,
)


def test_backup_redacts_common_pii_and_nested_secrets():
    payload = {
        "email": "user@example.com",
        "user_email": "owner@example.com",
        "name": "Private User",
        "metadata": {
            "provider_customer_id": "cus_123",
            "notes": "safe operational note",
            "nested": {"phone_number": "+15551234567"},
        },
        "attachment": b"binary",
    }

    redacted = redact_export_value("", payload)

    assert redacted["email"] == EXPORT_REDACTED_VALUE
    assert redacted["user_email"] == EXPORT_REDACTED_VALUE
    assert redacted["name"] == EXPORT_REDACTED_VALUE
    assert redacted["metadata"]["provider_customer_id"] == EXPORT_REDACTED_VALUE
    assert redacted["metadata"]["nested"]["phone_number"] == EXPORT_REDACTED_VALUE
    assert redacted["metadata"]["notes"] == "safe operational note"
    assert redacted["attachment"] == EXPORT_BINARY_VALUE


def test_backup_never_exports_auth_tokens_collection():
    assert "auth_tokens" not in configured_collections("users,auth_tokens,workspaces")


if __name__ == "__main__":
    test_backup_redacts_common_pii_and_nested_secrets()
    test_backup_never_exports_auth_tokens_collection()
    print("Backup redaction tests passed.")
