from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"


def read_app() -> str:
    return APP.read_text(encoding="utf-8")


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

    assert 'os.environ.get("ERRORSWEEP_EXPECTED_BRANCH")' in app
    assert 'os.environ.get("COGNISWEEP_EXPECTED_BRANCH")' in app
    assert 'or "main"' in app


def test_legacy_dashboard_renderer_removed() -> None:
    app = read_app()

    assert "def _legacy_page_dashboard_unused" not in app


def test_global_command_palette_is_mounted() -> None:
    app = read_app()
    topnav_panel = function_body(app, "render_topnav_panel", "render_native_route_button")
    navigation = function_body(app, "render_navigation", "render_command_palette")
    bridge = function_body(app, "render_app_navigation_bridge", "human_review_editor_link")

    assert "render_topnav_command_panel(active_page)" in topnav_panel
    assert 'data-es-command-palette-trigger="1"' in navigation
    assert "{command_tool}" in navigation
    assert "handleCommandShortcut" in bridge
    assert 'key !== "k"' in bridge


if __name__ == "__main__":
    test_login_password_verification_is_hash_only()
    test_deploy_expected_branch_is_configurable()
    test_legacy_dashboard_renderer_removed()
    test_global_command_palette_is_mounted()
    print("Auth password policy checks passed.")
