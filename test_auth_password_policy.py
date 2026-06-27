from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
RUNTIME_CONFIG = ROOT / "app_runtime_config.py"
BILLING_CONFIG = ROOT / "billing_config.py"


def read_app() -> str:
    return APP.read_text(encoding="utf-8")


def read_runtime_config() -> str:
    return RUNTIME_CONFIG.read_text(encoding="utf-8")


def read_billing_config() -> str:
    return BILLING_CONFIG.read_text(encoding="utf-8")


def function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"def {name}")
    end = source.index(f"def {next_name}", start)
    return source[start:end]


def test_login_password_verification_is_hash_only() -> None:
    app = read_app()
    verify_login = function_body(app, "verify_login_password", "early_safe_text")
    password_configured = function_body(app, "password_configured", "trim_session_list")

    assert "return verify_password(password, stored_hash)" in verify_login
    assert "hmac.compare_digest(password" not in verify_login
    assert "return bool(secret(hash_secret_name, \"\"))" in password_configured
    assert "or secret(legacy_secret_name" not in password_configured


def test_deploy_expected_branch_is_configurable() -> None:
    app = read_app()
    runtime_config = read_runtime_config()

    assert "from app_runtime_config import" in app
    assert "DEPLOY_EXPECTED_BRANCH" in app
    assert "def cognisweep_env_alias" in runtime_config
    assert 'runtime_env("ERRORSWEEP_EXPECTED_BRANCH", "main")' in runtime_config
    assert 'or "main"' in runtime_config


def test_legacy_dashboard_renderer_removed() -> None:
    app = read_app()

    assert "def _legacy_page_dashboard_unused" not in app


def test_global_command_palette_is_not_exposed_in_header() -> None:
    app = read_app()
    topnav_panel = function_body(app, "render_topnav_panel", "render_native_route_button")
    navigation = function_body(app, "render_navigation", "render_command_palette")
    bridge = function_body(app, "render_app_navigation_bridge", "human_review_editor_link")

    assert "render_topnav_command_panel(active_page)" not in topnav_panel
    assert 'data-es-command-palette-trigger="1"' not in navigation
    assert "{command_tool}" not in navigation
    assert "handleCommandShortcut" in bridge
    assert 'key !== "k"' in bridge


def test_no_hardcoded_personal_unlimited_owner_secret() -> None:
    app = read_app()
    billing_config = read_billing_config()
    source = app + billing_config

    assert "errorsweep_unlimited_adapa_2026" not in source
    assert "adapalanaveen" not in source.lower()
    assert "Naveen Unlimited Workspace" not in source
    assert "ERRORSWEEP_UNLIMITED_ACCESS_WORKSPACE" in billing_config


if __name__ == "__main__":
    test_login_password_verification_is_hash_only()
    test_deploy_expected_branch_is_configurable()
    test_legacy_dashboard_renderer_removed()
    test_global_command_palette_is_not_exposed_in_header()
    test_no_hardcoded_personal_unlimited_owner_secret()
    print("Auth password policy checks passed.")
