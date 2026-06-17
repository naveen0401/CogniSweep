import json
import os
import time

import billing_webhook_receiver as receiver


def with_receiver_fakes(fetch_impl, persist_impl, fn):
    original_fetch = receiver.fetch_collection
    original_persist = receiver.persist
    try:
        receiver.fetch_collection = fetch_impl
        receiver.persist = persist_impl
        fn()
    finally:
        receiver.fetch_collection = original_fetch
        receiver.persist = original_persist


def test_duplicate_applied_billing_event_is_not_reapplied():
    now = int(time.time())
    saved = []
    existing = {
        "id": "manual-evt_duplicate",
        "workspace": "Acme",
        "user_email": "owner@example.com",
        "provider": "manual",
        "event_id": "evt_duplicate",
        "event_type": "manual.billing_event",
        "status": "paid",
        "signature_status": "not_checked",
        "applied": True,
        "metadata_json": {"applied_messages": ["Subscription recorded as Active: pro."]},
    }

    def fake_fetch(collection, workspace=""):
        assert collection == "billing_events"
        return [existing]

    def fake_persist(collection, record, workspace="", user_email=""):
        saved.append((collection, dict(record)))
        return dict(record)

    def run():
        payload = {
            "id": "evt_duplicate",
            "event_type": "manual.billing_event",
            "status": "paid",
            "workspace": "Acme",
            "email": "owner@example.com",
            "plan": "pro",
            "amount": 3999,
            "created_at": now,
        }
        status_code, response = receiver.process_webhook("manual", json.dumps(payload), {}, apply_updates=True)

        assert status_code == 200
        assert response["ok"] is True
        assert response["duplicate"] is True
        assert response["applied"] is True
        assert response["messages"] == ["Duplicate billing event ignored because it was already applied."]
        assert [collection for collection, _ in saved] == ["billing_events"]

    with_receiver_fakes(fake_fetch, fake_persist, run)


def test_old_billing_event_is_stored_but_not_applied():
    saved = []
    original_window = os.environ.get("ERRORSWEEP_BILLING_WEBHOOK_REPLAY_WINDOW_SECONDS")
    os.environ["ERRORSWEEP_BILLING_WEBHOOK_REPLAY_WINDOW_SECONDS"] = "300"

    def fake_fetch(collection, workspace=""):
        return []

    def fake_persist(collection, record, workspace="", user_email=""):
        saved.append((collection, dict(record)))
        return dict(record)

    def run():
        payload = {
            "id": "evt_old",
            "event_type": "manual.billing_event",
            "status": "paid",
            "workspace": "Acme",
            "email": "owner@example.com",
            "plan": "pro",
            "amount": 3999,
            "created_at": int(time.time()) - 3600,
        }
        status_code, response = receiver.process_webhook("manual", json.dumps(payload), {}, apply_updates=True)

        assert status_code == 400
        assert response["ok"] is False
        assert response["duplicate"] is False
        assert response["applied"] is False
        assert response["event_replay_status"] == "too_old"
        assert response["messages"] == ["Event stored but not applied because replay status is too_old."]
        assert [collection for collection, _ in saved] == ["billing_events"]

    try:
        with_receiver_fakes(fake_fetch, fake_persist, run)
    finally:
        if original_window is None:
            os.environ.pop("ERRORSWEEP_BILLING_WEBHOOK_REPLAY_WINDOW_SECONDS", None)
        else:
            os.environ["ERRORSWEEP_BILLING_WEBHOOK_REPLAY_WINDOW_SECONDS"] = original_window


if __name__ == "__main__":
    test_duplicate_applied_billing_event_is_not_reapplied()
    test_old_billing_event_is_stored_but_not_applied()
    print("Billing webhook replay tests passed.")
