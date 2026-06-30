from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
PLATFORM_CONSTANTS = ROOT / "app_platform_constants.py"
CADDYFILE = ROOT / "deploy" / "Caddyfile"
ENV_TEMPLATE = ROOT / "deploy" / ".env.production.example"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"def {name}")
    end = source.index(f"def {next_name}", start)
    return source[start:end]


def test_public_landing_canonical_url_is_configured() -> None:
    app = read(APP)
    platform_constants = read(PLATFORM_CONSTANTS)

    assert "from app_platform_constants import" in app
    assert 'DEFAULT_PUBLIC_LANDING_URL = "https://www.cognisweep.com/solutions/software-localization-tool"' in platform_constants
    assert 'PUBLIC_LANDING_ROUTE = "solutions/software-localization-tool"' in platform_constants
    assert 'runtime_env("ERRORSWEEP_PUBLIC_LANDING_URL", DEFAULT_PUBLIC_LANDING_URL)' in platform_constants


def test_public_landing_route_alias_renders_landing() -> None:
    app = read(APP)
    public_app = function_body(app, "render_public_app", "page_dashboard")
    route_resolver = function_body(app, "get_current_route", "is_authenticated")

    assert "PUBLIC_LANDING_ROUTE" in app
    assert 'if public_route and public_route in PUBLIC_ROUTES:' in route_resolver
    assert 'elif route in {"landing", PUBLIC_LANDING_ROUTE}:' in public_app
    assert 'render_landing_page("explicit_public_landing")' in public_app


def test_public_landing_mounts_koochi_chatbot() -> None:
    app = read(APP)
    landing = app[app.index("def render_landing_page") : app.index("LOGIN_SUBMIT_MASK_ID")]
    koochi = function_body(app, "render_koochi_chatbot", "route_query_for_page")

    assert "render_koochi_chatbot()" in landing
    assert '"name": "Koochi"' in koochi
    assert "Ask Koochi" in koochi
    assert "without a user AI API key" in koochi
    assert "CogniSweep QA, translation, subtitling, transcription, scorecards" in koochi
    assert "removeIfNotLandingRoute" in koochi


def test_root_startup_installs_canonical_redirect_bridge() -> None:
    app = read(APP)
    bridge = function_body(app, "render_public_landing_canonical_redirect_bridge", "render_authenticated_shell_seen_bridge")
    main_start = app.index('if __name__ == "__main__":')
    main_body = app[main_start : app.index("if st.session_state.get(\"authenticated\")", main_start)]

    assert "PUBLIC_LANDING_CANONICAL_URL" in bridge
    assert "window.location.replace(targetUrl.toString())" in bridge
    assert "current.search === \"\"" in bridge
    assert "render_public_landing_canonical_redirect_bridge()" in main_body


def test_caddy_redirects_bare_roots_to_canonical_landing() -> None:
    caddy = read(CADDYFILE)

    assert "{$COGNISWEEP_DOMAIN:cognisweep.com}, {$COGNISWEEP_WWW_DOMAIN:www.cognisweep.com}" in caddy
    assert "@apexLanding" in caddy
    assert "host {$COGNISWEEP_DOMAIN:cognisweep.com}" in caddy
    assert "query \"\"" in caddy
    assert "redir @apexLanding https://{$COGNISWEEP_WWW_DOMAIN:www.cognisweep.com}/solutions/software-localization-tool 308" in caddy
    assert "@wwwRootLanding" in caddy
    assert "redir @wwwRootLanding /solutions/software-localization-tool 308" in caddy
    assert caddy.index("reverse_proxy @billing") < caddy.index("reverse_proxy errorsweep-app:8501")


def test_env_template_names_public_www_landing_url() -> None:
    env_template = read(ENV_TEMPLATE)

    assert "COGNISWEEP_WWW_DOMAIN=www.cognisweep.com" in env_template
    assert "COGNISWEEP_PUBLIC_BASE_URL=https://www.cognisweep.com" in env_template
    assert "COGNISWEEP_PUBLIC_LANDING_URL=https://www.cognisweep.com/solutions/software-localization-tool" in env_template


if __name__ == "__main__":
    test_public_landing_canonical_url_is_configured()
    test_public_landing_route_alias_renders_landing()
    test_public_landing_mounts_koochi_chatbot()
    test_root_startup_installs_canonical_redirect_bridge()
    test_caddy_redirects_bare_roots_to_canonical_landing()
    test_env_template_names_public_www_landing_url()
    print("Public landing URL checks passed.")
