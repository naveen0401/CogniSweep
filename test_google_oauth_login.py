from pathlib import Path


APP = Path("app.py")
ENV_TEMPLATE = Path("deploy/.env.production.example")
STREAMLIT_TEMPLATE = Path(".streamlit/secrets.toml.example")


def source(path: Path = APP) -> str:
    return path.read_text(encoding="utf-8")


def function_body(name: str, end_name: str) -> str:
    text = source()
    start = text.index(f"def {name}(")
    end = text.index(f"def {end_name}(", start)
    return text[start:end]


def test_google_oauth_public_route_and_login_button() -> None:
    text = source()
    public_app = function_body("render_public_app", "page_dashboard")
    login = function_body("render_login", "profile_language_defaults")
    routes_start = text.index("PUBLIC_ROUTES = {")
    routes_body = text[routes_start : text.index("}", routes_start)]

    assert 'OAUTH_CALLBACK_ROUTE = "oauth_callback"' in text
    assert "OAUTH_CALLBACK_ROUTE" in routes_body
    assert 'OAUTH_CALLBACK_ROUTE: "OAuth Callback"' in text
    assert "render_oauth_callback()" in public_app
    assert "google_oauth_config_status()" in login
    assert 'social_oauth_authorize_url("google")' in login
    assert "Continue with Google" in login


def test_google_oauth_callback_verifies_supabase_and_respects_signup_gate() -> None:
    callback = function_body("render_oauth_callback", "render_sso_handoff")
    ensure_user = function_body("ensure_social_login_user", "hydrate_platform_settings")

    assert "render_oauth_fragment_bridge()" in callback
    assert "verify_social_oauth_state" in callback
    assert "verify_supabase_oauth_token" in callback
    assert "record_consent_acceptance" in callback
    assert "login_user(" in callback
    assert 'feature_flag("public_registration")' in ensure_user
    assert "public_signup_launch_gate()" in ensure_user
    assert '"role": "Individual Owner"' in ensure_user
    assert '"account_type": "individual"' in ensure_user


def test_google_oauth_cleanup_and_templates() -> None:
    login_user = function_body("login_user", "render_login_success_handoff")
    route_query = function_body("set_route_query", "public_route_for_es_page")
    env_template = source(ENV_TEMPLATE)
    streamlit_template = source(STREAMLIT_TEMPLATE)

    assert "OAUTH_ACCESS_TOKEN_PARAM" in login_user
    assert "OAUTH_STATE_PARAM" in login_user
    assert "OAUTH_ACCESS_TOKEN_PARAM" in route_query
    assert "OAUTH_STATE_PARAM" in route_query
    assert "COGNISWEEP_SOCIAL_LOGIN_ENABLED=true" in env_template
    assert "COGNISWEEP_GOOGLE_OAUTH_ENABLED=true" in env_template
    assert 'COGNISWEEP_SOCIAL_LOGIN_ENABLED = "true"' in streamlit_template
    assert 'COGNISWEEP_GOOGLE_OAUTH_ENABLED = "true"' in streamlit_template


if __name__ == "__main__":
    test_google_oauth_public_route_and_login_button()
    test_google_oauth_callback_verifies_supabase_and_respects_signup_gate()
    test_google_oauth_cleanup_and_templates()
    print("Google OAuth login checks passed.")
