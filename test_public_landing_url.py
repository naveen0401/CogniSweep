from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app.py"
PLATFORM_CONSTANTS = ROOT / "app_platform_constants.py"
CADDYFILE = ROOT / "deploy" / "Caddyfile"
ENV_TEMPLATE = ROOT / "deploy" / ".env.production.example"
KOOCHI_ICON = ROOT / "assets" / "koochi-chatbot-icon.jpeg"


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
    assert KOOCHI_ICON.exists()
    assert "koochi-chatbot-icon.jpeg" in app
    assert "koochi_avatar_asset_data_uri()" in koochi
    assert '"avatarSrc": avatar_data_uri' in koochi
    assert "Ask Koochi" in koochi
    assert "data-koochi-icon" in koochi
    assert "without a user AI API key" in koochi
    assert "Ask me about CogniSweep QA, translation, media workflows, scorecards" in koochi
    assert "removeIfNotLandingRoute" in koochi


def test_koochi_uses_confident_product_intent_routing() -> None:
    app = read(APP)
    koochi = function_body(app, "render_koochi_chatbot", "route_query_for_page")

    assert "const scoreIntent" in koochi
    assert "const fallbackAnswer" in koochi
    assert "outOfScopeTerms" in koochi
    assert "negativeTerms" in koochi
    assert "best.score < 4" in koochi
    assert "I want to stay accurate" in koochi
    assert "Scorecards compare translator and reviewer/final files" in koochi
    assert "QA report generation is skipped" in koochi
    assert "Koochi itself is a no-API product assistant" in koochi


def test_public_landing_uses_stable_fixed_header_spacing() -> None:
    app = read(APP)
    landing = app[app.index("def render_landing_page") : app.index("LOGIN_SUBMIT_MASK_ID")]

    assert "--es-lp-fixed-header-height" in landing
    assert "padding-top: calc(var(--es-lp-fixed-header-height) + 32px) !important" in landing
    assert "height: var(--es-lp-fixed-header-height) !important" in landing
    assert "padding: 40px clamp(18px, 8vw, 184px) 20px !important" in landing
    assert "font-size: clamp(34px, 3.25vw, 48px) !important" in landing


def test_public_signup_gate_tracks_blockers_without_default_lock() -> None:
    app = read(APP)
    gate = function_body(app, "public_signup_launch_gate", "split_text_lines")
    locked_page = function_body(app, "render_public_signup_launch_locked", "render_signup")

    assert "SIGNUP_BLOCKING_PREFLIGHT_CHECKS" in app
    assert "public_signup_preflight_lock_enabled" in app
    assert 'secret("ERRORSWEEP_LOCK_PUBLIC_SIGNUP_ON_PREFLIGHT", "false")' in app
    assert '"Session secret"' in app
    assert '"Supabase persistence"' in app
    assert 'safe_text(row.get("Check")) in SIGNUP_BLOCKING_PREFLIGHT_CHECKS' in gate
    assert '"locked": bool(blockers) and hard_lock' in gate
    assert '"hard_lock": hard_lock' in gate
    assert '"preflight_blocker_count": len(all_blockers)' in gate
    assert '"ignored_blocker_count"' in gate
    assert "Signup temporarily unavailable" in locked_page
    assert "signup-critical blocker" in locked_page


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
    assert "host cognisweep.com" in caddy
    assert "query \"\"" in caddy
    assert "redir @apexLanding https://www.cognisweep.com/solutions/software-localization-tool 308" in caddy
    assert "@apexCanonicalLanding" in caddy
    assert "redir @apexCanonicalLanding https://www.cognisweep.com/solutions/software-localization-tool 308" in caddy
    assert "@wwwRootLanding" in caddy
    assert "host www.cognisweep.com" in caddy
    assert "redir @wwwRootLanding /solutions/software-localization-tool 308" in caddy
    assert "handle /solutions/software-localization-tool/_stcore/*" in caddy
    assert "handle /solutions/software-localization-tool/static/*" in caddy
    assert "uri strip_prefix /solutions/software-localization-tool" in caddy
    assert caddy.index("reverse_proxy @billing") < caddy.rindex("reverse_proxy errorsweep-app:8501")


def test_env_template_names_public_www_landing_url() -> None:
    env_template = read(ENV_TEMPLATE)

    assert "COGNISWEEP_WWW_DOMAIN=www.cognisweep.com" in env_template
    assert "COGNISWEEP_PUBLIC_BASE_URL=https://www.cognisweep.com" in env_template
    assert "COGNISWEEP_PUBLIC_LANDING_URL=https://www.cognisweep.com/solutions/software-localization-tool" in env_template


if __name__ == "__main__":
    test_public_landing_canonical_url_is_configured()
    test_public_landing_route_alias_renders_landing()
    test_public_landing_mounts_koochi_chatbot()
    test_koochi_uses_confident_product_intent_routing()
    test_public_landing_uses_stable_fixed_header_spacing()
    test_public_signup_gate_tracks_blockers_without_default_lock()
    test_root_startup_installs_canonical_redirect_bridge()
    test_caddy_redirects_bare_roots_to_canonical_landing()
    test_env_template_names_public_www_landing_url()
    print("Public landing URL checks passed.")
