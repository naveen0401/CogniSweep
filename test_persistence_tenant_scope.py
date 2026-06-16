from pathlib import Path
from urllib.parse import parse_qs, urlparse

import production_persistence as pp


APP = Path("app.py")
BILLING_RECEIVER = Path("billing_webhook_receiver.py")
WORKFLOW = Path(".github/workflows/release-gate.yml")


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = [] if payload is None else payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected status {self.status_code}")

    def json(self):
        return self.payload


class FakeRequests:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url))
        return FakeResponse([])

    def patch(self, url, headers=None, json=None, timeout=None):
        self.calls.append(("PATCH", url))
        return FakeResponse([])

    def delete(self, url, headers=None, timeout=None):
        self.calls.append(("DELETE", url))
        return FakeResponse([])


def install_fake_supabase():
    fake = FakeRequests()
    pp._supabase_url = lambda: "https://example.supabase.co"
    pp._service_key = lambda: "service-role"
    pp.requests = fake
    return fake


def query(url):
    return parse_qs(urlparse(url).query)


def assert_raises_value_error(fn, expected):
    try:
        fn()
    except ValueError as exc:
        assert expected in str(exc)
        return
    raise AssertionError("expected ValueError")


def test_saas_fetch_requires_tenant_scope_or_platform_reason():
    install_fake_supabase()
    assert_raises_value_error(
        lambda: pp.fetch_saas_records("users"),
        "requires workspace, user_email, or platform_scope_reason",
    )
    assert_raises_value_error(
        lambda: pp.fetch_saas_records("users", include_all_workspaces=True),
        "include_all_workspaces requires platform_scope_reason",
    )


def test_saas_fetch_delete_and_editor_queries_are_scoped():
    fake = install_fake_supabase()

    pp.fetch_saas_records("jobs", workspace="Acme", limit=10)
    pp.fetch_persistent_usage_events(20, workspace="Acme")
    pp.fetch_persistent_editor_jobs(20, workspace="Acme")
    pp.load_persistent_editor_job("job-123", workspace="Acme")
    pp.update_persistent_editor_job("job-123", rows=[], workspace="Acme")
    pp.delete_saas_record("jobs", "job-123", workspace="Acme")

    for method, url in fake.calls:
        params = query(url)
        assert params.get("workspace") == ["eq.Acme"], f"{method} was not workspace-scoped: {url}"
    assert any("id=eq.job-123" in url for _, url in fake.calls)


def test_platform_wide_reads_must_be_explicitly_labeled():
    fake = install_fake_supabase()

    pp.fetch_saas_records("users", include_all_workspaces=True, platform_scope_reason="login_user_lookup")
    pp.fetch_persistent_usage_events(20, include_all_workspaces=True, platform_scope_reason="owner_usage_audit")
    pp.fetch_persistent_editor_jobs(20, include_all_workspaces=True, platform_scope_reason="owner_recent_editor_jobs")

    assert len(fake.calls) == 3
    for _, url in fake.calls:
        params = query(url)
        assert "workspace" not in params
        assert "user_email" not in params


def test_persistence_health_uses_platform_workspace_probe_scope():
    fake = install_fake_supabase()
    health = pp.persistence_health()

    assert health["storage_mode"] == "supabase"
    assert fake.calls
    for method, url in fake.calls:
        assert method == "GET"
        assert query(url).get("workspace") == ["eq.Platform"], url


def test_application_call_sites_label_platform_scope_reads():
    app = APP.read_text(encoding="utf-8")
    billing = BILLING_RECEIVER.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for reason in [
        "login_user_lookup",
        "auth_token_lookup",
        "sso_handoff_token_lookup",
        "owner_usage_audit",
        "owner_recent_editor_jobs",
        "platform_settings_hydration",
    ]:
        assert f'platform_scope_reason="{reason}"' in app
    assert '"owner_state_hydration"' in app
    assert "platform_scope_reason=platform_reason" in app
    assert 'platform_scope_reason="billing_webhook_reconciliation"' in billing
    assert "python test_persistence_tenant_scope.py" in workflow


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("Persistence tenant-scope checks passed.")
