import ast
from pathlib import Path

import language_resource_connectors as lrc


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
PERSISTENCE = ROOT / "production_persistence.py"
SCHEMA = ROOT / "supabase_v42_release_schema.sql"
WORKFLOW = ROOT / ".github" / "workflows" / "release-gate.yml"
RELEASE_CHECK = ROOT / "deploy" / "release_check.py"
SECRETS_TEMPLATE = ROOT / ".streamlit" / "secrets.toml.example"
CAT_EDITOR = ROOT / "assets" / "cat_editor_reference.html"
MEDIA_EDITOR = ROOT / "assets" / "media_editor_reference.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_body(text: str, name: str, next_name: str) -> str:
    start = text.index(f"def {name}")
    end = text.index(f"def {next_name}", start)
    return text[start:end]


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.content = b"{}"

    def raise_for_status(self):
        if self.status_code >= 400:
            error = lrc.requests.HTTPError("request failed")
            error.response = self
            raise error

    def json(self):
        return self.payload


def test_secret_encryption_round_trip_and_masking():
    master_key = "x" * 40
    plaintext = "provider-token-AB12"

    encrypted = lrc.encrypt_api_secret(plaintext, master_key)

    assert encrypted
    assert plaintext not in encrypted
    assert lrc.decrypt_api_secret(encrypted, master_key) == plaintext
    assert lrc.mask_secret_tail(plaintext).endswith("AB12")
    assert plaintext not in lrc.mask_secret_tail(plaintext)

    try:
        lrc.decrypt_api_secret(encrypted, "y" * 40)
    except lrc.LanguageResourceSecretError as exc:
        assert exc.code == "invalid_encrypted_secret"
    else:
        raise AssertionError("decrypting with the wrong key must fail closed")


def test_generic_rest_connector_normalizes_resources_and_segment_lookups():
    calls = []
    original_request = lrc.requests.request

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        calls.append({"method": method, "url": url, "headers": headers or {}, "json": kwargs.get("json")})
        if url.endswith("/resources"):
            return FakeResponse(
                {
                    "identity": {"email": "translator@example.com"},
                    "translation_memories": [{"id": "tm-main", "name": "Product TM"}],
                    "glossaries": [{"id": "gl-main", "name": "Product Terms"}],
                    "dnt_resources": [{"id": "dnt-brand", "name": "Brand DNT"}],
                    "missing_scopes": ["write"],
                }
            )
        if url.endswith("/tm/search"):
            return FakeResponse({"matches": [{"source": "workspace", "target": "कार्यस्थल", "score": 96.4, "resource_name": "Product TM"}]})
        if url.endswith("/terms/lookup"):
            return FakeResponse({"terms": [{"source_term": "workspace", "target_term": "कार्यस्थल", "resource_name": "Product Terms"}]})
        if url.endswith("/dnt/lookup"):
            return FakeResponse({"dnt": [{"term": "CogniSweep", "instruction": "Preserve exactly"}]})
        return FakeResponse({}, 404)

    lrc.requests.request = fake_request
    try:
        connector = lrc.GenericRestLanguageResourceConnector(
            lrc.ConnectorConfig(
                connection_id="lrc_test",
                provider="Generic REST",
                connection_name="Client resources",
                base_url="https://provider.example/api",
                auth_type="Bearer token",
                api_secret="secret-token",
                organization_id="org-1",
                provider_workspace_id="workspace-1",
            )
        )

        tested = connector.test_connection()
        tm = connector.search_tm("workspace", "en", "hi", resource_ids=["tm-main"])
        glossary = connector.lookup_terms("workspace", "en", "hi", resource_ids=["gl-main"])
        dnt = connector.lookup_dnt("CogniSweep", "en", resource_ids=["dnt-brand"])
    finally:
        lrc.requests.request = original_request

    assert tested["provider_account_identity"] == "translator@example.com"
    assert tested["tm_count"] == 1
    assert tested["glossary_count"] == 1
    assert tested["dnt_count"] == 1
    assert tested["missing_scopes"] == ["write"]
    assert tm[0]["target_text"] == "कार्यस्थल"
    assert tm[0]["match_score"] == 96.4
    assert glossary[0]["source_term"] == "workspace"
    assert dnt[0]["term"] == "CogniSweep"
    assert calls[0]["headers"]["Authorization"] == "Bearer secret-token"
    assert calls[0]["headers"]["X-Organization-ID"] == "org-1"
    assert calls[1]["json"]["resource_ids"] == ["tm-main"]


def test_app_keeps_language_resource_keys_server_side():
    app = read(APP)
    editor_resources = function_body(app, "build_editor_language_resources", "render_reference_cat_editor_shell")
    lookup = function_body(app, "external_language_resource_lookup", "add_audit")
    account = function_body(app, "render_language_resource_connections_panel", "render_ai_mt_providers_panel")

    for label in [
        "Language Resource Connections",
        "Connection name",
        "API key / personal access token",
        "Test connection",
        "Save connection",
        "Disable connection",
        "Delete connection",
        "Set personal default",
        "Bind connection to project",
    ]:
        assert label in account

    assert "decrypt_language_resource_secret" in lookup
    assert "encrypted_secret" not in editor_resources
    assert "api_secret" not in editor_resources
    assert "language_resources_json" in app
    assert "Connection status" in read(CAT_EDITOR)
    assert "connectionStatus" in read(MEDIA_EDITOR)


def test_language_resource_connection_form_starts_without_example_fillings():
    app = read(APP)
    account = function_body(app, "render_language_resource_connections_panel", "render_ai_mt_providers_panel")

    assert '"My language resources"' not in account
    assert '"https://provider.example.com/api"' not in account
    assert '"Paste token"' not in account
    assert 'existing.get("source_language") or "en"' not in account
    assert 'existing.get("automatic_lookup_enabled", True)' not in account
    assert 'value=safe_text(existing.get("connection_name"))' in account
    assert 'value=safe_text(existing.get("source_language"))' in account
    assert 'if existing_id else False' in account


def test_language_resource_helpers_do_not_break_existing_session_upserts():
    app = read(APP)
    tree = ast.parse(app)
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upsert_session_record"]
    assert definitions, "upsert_session_record must exist"
    active_definition = definitions[-1]
    arg_names = [arg.arg for arg in active_definition.args.args]
    assert arg_names[:2] == ["collection", "record"]
    assert "identity_key" in arg_names
    assert active_definition.args.defaults, "identity_key must remain optional for signup/login callers"


def test_persistence_schema_and_release_guards_cover_language_resources():
    persistence = read(PERSISTENCE)
    schema = read(SCHEMA).lower()
    workflow = read(WORKFLOW)
    release_check = read(RELEASE_CHECK)
    secrets_template = read(SECRETS_TEMPLATE)

    tree = ast.parse(persistence)
    tables = {}
    columns = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "SAAS_TABLES":
                tables = ast.literal_eval(node.value)
            if isinstance(target, ast.Name) and target.id == "SAAS_COLUMNS":
                columns = ast.literal_eval(node.value)

    for collection, table in {
        "integration_connections": "errorsweep_integration_connections",
        "resource_bindings": "errorsweep_resource_bindings",
        "resource_lookup_cache": "errorsweep_resource_lookup_cache",
        "integration_audit": "errorsweep_integration_audit",
    }.items():
        assert tables[collection] == table
        assert collection in columns
        assert f"create table if not exists public.{table}" in schema
        assert f"alter table public.{table} enable row level security" in schema
        assert f"create policy {table}_tenant_access on public.{table}" in schema

    assert "COGNISWEEP_LANGUAGE_RESOURCE_MASTER_KEY" in secrets_template
    assert "language_resource_connectors.py" in workflow
    assert "python test_language_resource_connectors.py" in workflow
    assert "language_resource_connectors.py" in release_check
    assert "python test_language_resource_connectors.py" in release_check


if __name__ == "__main__":
    test_secret_encryption_round_trip_and_masking()
    test_generic_rest_connector_normalizes_resources_and_segment_lookups()
    test_app_keeps_language_resource_keys_server_side()
    test_language_resource_connection_form_starts_without_example_fillings()
    test_language_resource_helpers_do_not_break_existing_session_upserts()
    test_persistence_schema_and_release_guards_cover_language_resources()
    print("Language resource connector checks passed.")
