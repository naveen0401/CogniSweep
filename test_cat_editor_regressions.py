import re
from pathlib import Path


APP = Path(__file__).with_name("app.py")


def read_app() -> str:
    return APP.read_text(encoding="utf-8")


def active_cat_editor_body(source: str) -> str:
    start = source.index("def render_reference_cat_editor_shell")
    end = source.index("def render_external_media_editor", start)
    return source[start:end]


def test_editor_links_do_not_emit_session_tokens() -> None:
    source = read_app()
    start = source.index("def external_editor_url")
    end = source.index("def render_external_editor_link", start)
    body = source[start:end]
    assert "es_session" not in body


def test_navigation_links_do_not_emit_session_tokens() -> None:
    source = read_app()
    start = source.index("def page_link")
    end = source.index("def public_page_link", start)
    body = source[start:end]
    assert "es_session" not in body
    assert "?route" not in body
    assert "\"es_page\"" in body


def test_auth_redirect_uses_es_page_login_without_route_param() -> None:
    source = read_app()
    auth_start = source.index("def protected_route_requested")
    auth_end = source.index("def get_current_route", auth_start)
    auth_body = source[auth_start:auth_end]
    assert "public_es_route and public_es_route in PUBLIC_ROUTES" in auth_body
    redirect_start = source.index("def redirect_to_login_with_return_to")
    redirect_end = source.index("def require_auth", redirect_start)
    redirect_body = source[redirect_start:redirect_end]
    assert 'st.query_params["es_page"] = "Login"' in redirect_body
    assert 'st.query_params["return_to"] = return_url' in redirect_body
    assert "render_auth_restore_bridge" not in redirect_body
    assert "st.rerun()" not in redirect_body
    assert 'query_set("route", "login")' not in redirect_body


def test_login_es_page_aliases_are_public_and_normalized() -> None:
    source = read_app()
    start = source.index("def normalize_es_page")
    end = source.index("def known_protected_es_pages", start)
    body = source[start:end]
    assert '"login": "Login"' in body
    assert '"sign in": "Login"' in body
    assert '"signin": "Login"' in body
    assert 'key = es_page_alias_key(value)' in body

    public_start = source.index("def public_route_for_es_page")
    public_end = source.index("def is_human_review_editor_page", public_start)
    public_body = source[public_start:public_end]
    assert "normalized_page = normalize_es_page(page)" in public_body
    assert "PUBLIC_ROUTE_PAGE_NAMES.items()" in public_body


def test_login_success_opens_target_route_in_current_tab() -> None:
    source = read_app()
    start = source.index("def login_user")
    end = source.index("def logout", start)
    body = source[start:end]
    assert 'st.session_state["authenticated"] = True' in body
    assert 'st.session_state["es_page"] = launch_page' in body
    assert 'launch_params = login_launch_params(return_to, target_page)' in body
    assert 'st.session_state.page = launch_page if launch_page in known_protected_es_pages() else "Dashboard"' in body
    assert 'set_route_query(launch_params)' in body
    assert 'st.session_state["_post_login_tool_launch_url"] = "?" + urlencode(launch_params)' not in body
    assert 'st.session_state["_login_window_stay_open"] = True' not in body
    assert 'st.session_state.page = "Login"' not in body
    assert 'set_route_query({"es_page": "Login"})' not in body
    assert "apply_return_to(return_to)" not in body


def test_unknown_and_unauthorized_routes_are_separate() -> None:
    source = read_app()
    assert "Unknown or unauthorized route" not in source
    route_start = source.index("def get_current_route")
    route_end = source.index("def require_auth", route_start)
    route_body = source[route_start:route_end]
    assert "legacy_public_route and legacy_public_route in PUBLIC_ROUTES" in route_body

    start = source.index("def render_app")
    end = source.index('if __name__ == "__main__"', start)
    body = source[start:end]
    assert 'st.error(f"Unknown page: {route.get(\'unknown\')}")' in body
    assert 'st.error("You do not have access to this page.")' in body


def test_navigation_uses_central_route_helpers() -> None:
    source = read_app()
    assert "def get_current_route()" in source
    assert "def require_auth(" in source
    assert "def navigate(" in source
    start = source.index("def render_navigation")
    end = source.index("# ==========================================================\n# General helpers", start)
    body = source[start:end]
    assert "es-topnav-link" in body
    assert "page_link(page)" in body
    assert "topnav_quick_" not in body


def test_editor_urls_are_clean_routes_without_session_tokens() -> None:
    source = read_app()
    start = source.index("def external_editor_url")
    end = source.index("def render_external_editor_link", start)
    body = source[start:end]
    assert "route=editor" not in body
    assert "es_editor=" in body
    assert "job_id=" in body
    assert "es_session" not in body


def test_human_review_editor_uses_es_page_review_id_route() -> None:
    source = read_app()
    assert "def navigate_to_human_review_editor(review_id: str = \"\")" in source
    assert "navigate_es_page(\"Human Review Editor\", review_id=review_id)" in source
    assert "set_route_query({\"es_page\": \"Human Review Editor\", \"review_id\": review_id})" in source
    assert "set_route_query({\"route\": \"human_review_editor\"" not in source
    assert "route.get(\"route\") == \"human_review_editor\"" in source
    assert "requested_page in HUMAN_REVIEW_EDITOR_PAGES" in source
    assert "render_external_cat_editor(review_id)" in source
    assert "Review not found." in source
    assert "human_review_editor_link(str(review_job_id))" in source
    assert "render_editor_open_link(\"Open Human Review Editor\"" in source


def test_public_login_and_authenticated_entry_routes_open_dashboard() -> None:
    source = read_app()
    assert "def public_login_link_target() -> str" in source
    assert "target=\"_blank\" rel=\"noopener\"" in source
    assert "AUTHENTICATED_PUBLIC_ENTRY_ROUTES = {\"landing\", \"login\", \"signup\"}" in source
    assert "def authenticated_public_entry_route(route: Dict[str, Any]) -> bool:" in source
    assert "url.searchParams.set(\"es_page\", \"Landing\")" in source
    assert "url.searchParams.set(\"es_page\", \"Login\")" not in source[source.index("def render_logout_bridge"):source.index("def login_launch_params")]
    assert 'return_to = safe_text(st.session_state.pop("post_login_return_to", "")) or query_get("return_to")' in source
    assert 'set_route_query({"es_page": "Dashboard"})' in source
    assert "def authenticated_shell_route_from_session(default_page: str = \"Dashboard\") -> Dict[str, str]:" in source
    assert "def authenticated_login_handoff_route(route: Dict[str, Any]) -> bool:" in source
    assert "login_handoff_route = auth_state == AUTH_STATE_AUTHENTICATED and authenticated_login_handoff_route(route)" in source
    assert "auth_state == AUTH_STATE_AUTHENTICATED and authenticated_public_entry_route(route) and not login_handoff_route" in source
    assert 'if route.get("route") in PUBLIC_ROUTES:\n            route = authenticated_shell_route_from_session()' in source
    assert 'route = {"route": "dashboard", "page": "Dashboard", "es_page": "Dashboard"}' in source
    assert "render_editor_open_link(\"Open Human Review workspace\"" in source


def test_public_entry_routes_use_cookie_provider_not_restore_miss_gate() -> None:
    source = read_app()
    assert "def session_restore_probe_pending" not in source
    assert "def render_session_restore_bridge" not in source
    assert "def render_auth_restore_bridge" not in source
    assert "render_session_restore_checkpoint" not in source
    assert "Checking your session" not in source

    app_start = source.index('if __name__ == "__main__"')
    app_end = source.index('render_router_debug_panel(decision="render_complete")', app_start)
    app_body = source[app_start:app_end]
    assert "restore_session_from_cookie()" in app_body
    assert "sync_browser_session_cookie()" in app_body
    assert "current_auth_state(route)" in app_body
    assert "render_auth_unknown_state(route)" in app_body
    assert "render_session_restore_bridge" not in app_body
    assert "session_restore_probe_pending" not in app_body
    assert 'st.query_params["es_restore_miss"] = "1"' not in app_body
    assert 'url.searchParams.set("es_restore_miss", "1")' not in source


def test_authenticated_login_tab_shows_logged_in_state() -> None:
    source = read_app()
    state_start = source.index("def render_logged_in_login_state")
    state_end = source.index("def render_post_login_tool_launch_bridge", state_start)
    state_body = source[state_start:state_end]
    assert "You are logged in" in state_body
    assert "ErrorSweep is open in another tab" in state_body
    assert "Open Dashboard" in state_body
    assert "?es_logout=1" in state_body
    assert 'st.success("You are logged in")' in state_body
    assert 'button("Open Dashboard"' in state_body
    assert 'button("Logout"' in state_body

    login_start = source.index("def render_login")
    login_end = source.index("def profile_language_defaults", login_start)
    login_body = source[login_start:login_end]
    auth_start = login_body.index("if is_authenticated():")
    auth_end = login_body.index("owner_user =", auth_start)
    auth_branch = login_body[auth_start:auth_end]
    auth_header_start = login_body.index("signup_enabled = feature_flag")
    form_start = login_body.index('with st.form("unified_login"')
    assert auth_start < auth_header_start < form_start
    assert "render_post_login_tool_launch_bridge()" in auth_branch
    assert "render_logged_in_login_state" in auth_branch
    assert "st.rerun()" not in auth_branch
    assert 'st.form("unified_login"' in login_body


def test_login_new_tab_bridge_reruns_before_rendering_status() -> None:
    source = Path(__file__).with_name("managed_ai_router.py").read_text(encoding="utf-8")
    start = source.index("def _install_login_new_tab_bridge")
    end = source.index("_install_signup_scroll_fix()", start)
    body = source[start:end]
    assert 'st.session_state["_post_login_tool_launch_url"] = _build_launch_url()' in body
    assert 'params["es_session"]' not in body
    assert 'st.session_state["_login_window_stay_open"] = True' in body
    assert "_leave_current_tab_on_login()" in body
    assert "render_post_login_tool_launch_bridge" not in body
    assert "return original_rerun(*args, **kwargs)" in body


def test_logout_routes_every_window_to_landing() -> None:
    source = read_app()
    assert 'LOGOUT_BROADCAST_KEY = "errorsweep_logout_broadcast"' in source
    assert "def render_global_logout_listener() -> None" in source
    assert "window.addEventListener(\"storage\"" in source
    assert "clearAuthAndGoLanding" in source
    assert "restoreAuthAndGoDashboard" in source
    assert "event.key === storageKey && event.newValue" in source
    assert "storage.setItem(logoutKey, String(Date.now()))" in source
    assert "landing_redirect_url_js(include_logout_marker=True)" in source
    assert 'url.searchParams.set("es_logout", "1");' in source
    assert 'url.searchParams.set("es_page", "Landing")' in source

    app_start = source.index('if __name__ == "__main__"')
    app_end = source.index('render_router_debug_panel(decision="render_complete")', app_start)
    app_body = source[app_start:app_end]
    assert "render_global_logout_listener()" in app_body
    assert 'if query_get("es_logout") == "1":' in app_body
    assert "logout()" in app_body
    assert app_body.index('if query_get("es_logout") == "1":') < app_body.index("restore_session_from_cookie()")
    assert app_body.index("restore_session_from_cookie()") < app_body.index("sync_browser_session_cookie()")


def test_reload_session_restore_uses_cookie_not_url_only() -> None:
    source = read_app()
    requirements = Path(__file__).with_name("requirements.txt").read_text(encoding="utf-8")
    assert "SESSION_COOKIE_NAME = \"errorsweep_session\"" in source
    assert "SESSION_STORAGE_KEY = \"errorsweep_session\"" in source
    assert "SESSION_COOKIE_CONTROLLER_KEY = \"errorsweep_browser_cookies\"" in source
    assert 'AUTH_CHECK_QUERY_PARAM = "es_auth_checked"' in source
    assert 'AUTH_STATE_UNKNOWN = "unknown"' in source
    assert 'AUTH_STATE_AUTHENTICATED = "authenticated"' in source
    assert 'AUTH_STATE_UNAUTHENTICATED = "unauthenticated"' in source
    assert "streamlit-cookies-controller>=0.0.4" in requirements
    assert "SESSION_PERSISTENCE_SECONDS" in source
    assert "from streamlit_cookies_controller import CookieController" in source
    assert "def browser_session_cookie()" in source
    assert "def browser_cookie_controller()" in source
    assert "def component_session_cookie()" in source
    assert "def sync_component_session_cookie" in source
    assert "def render_browser_session_bootstrap" in source
    assert "def current_auth_state" in source
    assert "def render_auth_unknown_state" in source
    assert "def render_session_restore_bridge()" not in source
    assert "def restore_session_from_cookie()" in source
    assert "token = browser_session_cookie()" in source
    assert "restore_user_from_signed_session(token)" in source
    assert 'st.session_state["_pending_session_cookie"] = token' in source
    assert "sync_browser_session_cookie()" in source
    assert "sync_component_session_cookie(token, clear_cookie=clear_cookie)" in source
    assert "sync_component_session_cookie(session_token)" in source
    assert "return component_session_cookie()" in source
    assert "def browser_cookie_domain_js_function()" in source
    assert "cookieDomainAttribute" in source
    assert 'url.searchParams.set("es_restore", token)' not in source
    assert 'url.searchParams.set("es_session", token)' not in source
    assert 'targetDoc.cookie = name + "=" + encodeURIComponent(value)' in source
    assert 'firstDocument().cookie = cookieName + "=" + encodeURIComponent(token)' in source
    assert 'targetDoc.cookie = cookieName + "=" + encodeURIComponent(sessionToken)' in source
    assert 'const token = cookieToken || storageToken;' in source
    assert 'url.searchParams.set(authCheckedKey, "1")' in source
    assert 'st.caption("Loading...")' in source
    assert "query_clear(\"es_restore\")" in source
    assert "window.parent.document" in source


def test_debug_auth_reports_cookie_state_and_route_decision() -> None:
    source = read_app()
    assert "def set_auth_debug_state" in source
    assert "def render_auth_debug_panel" in source
    debug_start = source.index("def render_auth_debug_panel")
    debug_end = source.index("def restore_user_from_signed_session", debug_start)
    debug_body = source[debug_start:debug_end]
    for key in ("cookie_found", "session_valid", "authenticated", "route_decision", "resolved_route"):
        assert f'"{key}"' in debug_body
    assert 'if query_get("debug_auth") != "1":' in debug_body

    app_start = source.index('if __name__ == "__main__"')
    app_end = source.index('render_router_debug_panel(decision="render_complete")', app_start)
    app_body = source[app_start:app_end]
    assert "render_auth_debug_panel(route" in app_body
    assert '"valid_cookie_root_to_dashboard"' in app_body
    assert '"missing_or_invalid_cookie_show_landing"' in app_body
    assert '"valid_cookie_public_entry_to_dashboard"' in app_body


def test_session_check_page_removed_and_protected_routes_resolve() -> None:
    source = read_app()
    assert "render_session_restore_checkpoint" not in source
    assert "render_session_restore_bridge" not in source
    assert "render_auth_restore_bridge" not in source
    assert "session_restore_probe_pending" not in source
    assert "Checking your session" not in source
    assert "Continue to Login" not in source
    assert "Continue to Landing" not in source

    app_start = source.index('if __name__ == "__main__"')
    app_end = source.index('render_router_debug_panel(decision="render_complete")', app_start)
    app_body = source[app_start:app_end]
    assert "restore_session_from_cookie()" in app_body
    assert "sync_browser_session_cookie()" in app_body
    assert "current_auth_state(route)" in app_body
    assert "render_auth_unknown_state(route)" in app_body
    unknown_idx = app_body.index("render_auth_unknown_state(route)")
    first_public_idx = app_body.index("render_public_app()")
    assert unknown_idx < first_public_idx
    assert '"missing_or_invalid_cookie_show_login"' in app_body
    assert "render_login()" in app_body
    assert "st.session_state[\"auth_return_to\"] = encode_return_to()" in app_body
    assert 'render_public_app()' in app_body
    assert '"missing_or_invalid_cookie_show_landing"' in app_body
    assert 'st.query_params["es_restore_miss"] = "1"' not in app_body


def test_public_login_signup_navigation_ignores_restore_miss() -> None:
    source = read_app()
    link_start = source.index("def public_page_link")
    link_end = source.index("def public_login_link_target", link_start)
    link_body = source[link_start:link_end]
    assert 'return "?" + urlencode({"es_page": page_name})' in link_body
    assert "es_restore_miss" not in link_body

    app_start = source.index('if __name__ == "__main__"')
    app_end = source.index('render_router_debug_panel(decision="render_complete")', app_start)
    app_body = source[app_start:app_end]
    assert 'route_public in {"login", "signup"}' in app_body
    assert 'st.query_params["es_page"] = page_name' in app_body
    assert 'for stale in ("es_restore_miss", "es_session", "es_restore", "tool_tab", "route", "public", "return_to", AUTH_CHECK_QUERY_PARAM)' in app_body
    assert "del st.query_params[stale]" in app_body
    assert 'st.query_params["es_restore_miss"] = "1"' not in app_body

    pending_start = source.index("def auth_bootstrap_pending")
    pending_end = source.index("def current_auth_state", pending_start)
    pending_body = source[pending_start:pending_end]
    assert "if route_name in PUBLIC_ROUTES:" in pending_body
    assert "public_es_route = public_route_for_es_page(query_get(\"es_page\"))" in pending_body
    assert 'route_page = normalize_es_page(route.get("page") or route.get("es_page"))' in pending_body
    assert "if route_page in known_protected_es_pages():" in pending_body
    assert 'route_alias_page = normalize_es_page(ROUTE_PAGE_ALIASES.get(route_name, ""))' in pending_body
    assert "return False" in pending_body
    assert "route_name in AUTHENTICATED_PUBLIC_ENTRY_ROUTES" not in pending_body

    set_route_start = source.index("def set_route_query")
    set_route_end = source.index("def public_route_for_es_page", set_route_start)
    set_route_body = source[set_route_start:set_route_end]
    assert "AUTH_CHECK_QUERY_PARAM" in set_route_body


def test_login_session_persists_until_explicit_logout() -> None:
    source = read_app()
    assert 'SESSION_TOKEN_USER_FIELDS = ("email", "role", "account_type", "workspace", "plan", "status", "email_verified")' in source
    assert "SESSION_COOKIE_MAX_BYTES = 3800" in source
    assert "def compact_session_user_payload" in source

    sign_start = source.index("def signed_session_token_for_user")
    sign_end = source.index("def browser_session_cookie", sign_start)
    sign_body = source[sign_start:sign_end]
    assert "compact_session_user_payload(user)" in sign_body
    assert "\"persistent\": True" in sign_body
    assert "\"iat\": int(time.time())" in sign_body
    assert "\"exp\"" not in sign_body

    restore_start = source.index("def restore_user_from_signed_session")
    restore_end = source.index("def sync_browser_session_cookie", restore_start)
    restore_body = source[restore_start:restore_end]
    assert "find_user_by_email" in restore_body
    assert "SESSION_TOKEN_USER_FIELDS" in restore_body
    assert 'st.session_state.get("authenticated") and st.session_state.get("user")' in restore_body
    assert 'st.session_state["_pending_session_cookie"] = signed_session_token_for_user' in restore_body

    verify_start = source.index("def verify_payload")
    verify_end = source.index("def query_get", verify_start)
    verify_body = source[verify_start:verify_end]
    assert "hmac.compare_digest" in verify_body
    assert "return data" in verify_body
    assert "data.get(\"exp\"" not in verify_body

    sync_start = source.index("def sync_browser_session_cookie")
    sync_end = source.index("def landing_redirect_url_js", sync_start)
    sync_body = source[sync_start:sync_end]
    assert "sync_component_session_cookie(token, clear_cookie=clear_cookie)" in sync_body
    assert "max_age = SESSION_PERSISTENCE_SECONDS if token else 0" in sync_body
    assert "storage.removeItem(storageKey)" in sync_body

    logout_start = source.index("def logout")
    logout_end = source.index("# ==========================================================\n# Data initialization", logout_start)
    logout_body = source[logout_start:logout_end]
    assert 'st.session_state["_clear_session_cookie"] = True' in logout_body
    assert 'query_clear(key)' in logout_body
    assert 'query_set("es_page", "Landing")' in logout_body
    assert "render_logout_bridge()" in logout_body
    assert 'render_landing_page("logout")' in logout_body
    assert "st.rerun()" not in logout_body


def test_refresh_restores_last_authenticated_route() -> None:
    source = read_app()
    assert 'ROUTE_STORAGE_KEY = "errorsweep_route"' in source
    assert 'ROUTE_STORAGE_PARAM_KEYS = ("es_page", "es_editor", "job_id", "review_id")' in source
    assert "def route_query_has_explicit_target()" in source
    assert "def browser_route_storage_params" in source
    assert "def sync_browser_route_state" in source
    assert "def render_route_restore_bridge" in source
    assert "storage.setItem(routeStorageKey, JSON.stringify(value))" in source
    assert "storage.removeItem(routeStorageKey)" in source
    assert "url.searchParams.set(key, String(value))" in source
    assert "if (!hasAnyQuery) return;" in source

    restore_start = source.index("def render_route_restore_bridge")
    restore_end = source.index("def is_human_review_editor_page", restore_start)
    restore_body = source[restore_start:restore_end]
    assert "storage.getItem(routeStorageKey)" in restore_body
    assert 'url.searchParams.set(key, String(value))' in restore_body
    assert 'url.searchParams.set("es_restore", token)' not in restore_body

    app_start = source.index('if __name__ == "__main__"')
    app_end = source.index('render_router_debug_panel(decision="render_complete")', app_start)
    app_body = source[app_start:app_end]
    assert "render_route_restore_bridge()" in app_body
    assert "sync_browser_session_cookie()" in app_body
    assert "authenticated_public_entry_route(route)" in app_body
    assert 'current_route.get("public") != "login"' not in app_body



def test_translation_editor_uses_supplied_html_template() -> None:
    source = read_app()
    body = active_cat_editor_body(source)
    assert 'assets" / "cat_editor_reference.html' in body
    assert "reference_path.read_text" in body
    assert "components.html(html, height=900, scrolling=False)" in body
    assert "const rows =" in body
    assert "json.dumps(component_rows" in body
    assert '"done": is_segment_confirmed(row)' in body
    assert "st.data_editor" not in body
    assert "left_workspace" not in body
    assert "right_workspace" not in body


def test_cat_editor_reference_file_matches_attached_shell() -> None:
    reference = Path(__file__).parent / "assets" / "cat_editor_reference.html"
    assert reference.exists()
    html = reference.read_text(encoding="utf-8")
    assert '<div class="app-shell">' in html
    assert '<header class="app-header"' in html
    assert '<main class="editor-layout"' in html
    assert '<section class="left-column"' in html
    assert '<aside class="right-column"' in html
    assert 'html, body { height: 100%; margin: 0; overflow: hidden; }' in html
    assert 'position: fixed;' in html
    assert 'grid-template-columns: minmax(0, 1fr) 340px;' in html
    assert 'width: 340px;' in html
    assert 'min-width: 340px;' in html
    assert 'max-width: 340px;' in html
    assert '.right-column { display: none; }' not in html
    assert '.right-column { display: flex; }' in html
    assert 'grid-template-rows: 42px minmax(92px, 130px) 42px 38px minmax(0, 1fr) 32px;' in html
    assert '<tbody id="segmentRows"></tbody>' in html
    assert '<h2>Additional Details</h2>' in html
    assert '<button>Confirm</button>' in html
    assert '<button>Complete</button>' not in html
    assert "const uploadedContext = " in html
    assert "function activeContextNeedle(row, text)" in html
    assert "function highlightedContextDocument(row)" in html
    assert "context-highlight" in html
    assert "No exact match for this segment was found in the uploaded context." in html
    assert "Save Page" not in html
    assert "Sort Page" not in html
    assert "Pending only" not in html
    assert 'class="source-search"' in html
    assert 'class="target-search"' in html
    assert 'class="tab active context-menu-trigger"' in html
    assert 'class="context-option" data-context="source" checked' in html
    assert 'class="context-option" data-context="target"' in html
    assert 'filter-menu-trigger' in html
    assert 'data-filter="fuzzy"' in html
    assert 'data-filter="exact100"' in html
    assert 'data-filter="overflow101"' in html
    assert 'data-filter="confirmed"' in html
    assert 'data-filter="pending"' in html
    assert 'id="confirmAll"' in html
    assert '<th class="col-confirm"><label class="done-header">' in html
    assert 'class="confirm-check"' in html
    assert '<h3>Language Resources</h3>' in html
    assert 'id="languageResources"' in html
    assert "function renderLanguageResources()" in html
    assert "renderResourceSection('All Glossary'" in html
    assert "renderResourceSection('DNT list'" in html
    assert "renderResourceSection('TMs'" in html
    assert "Glossary, DNT list, and translation memory resources are not available for this task." in html
    assert "Focused source" not in html
    assert 'id="focusSource"' not in html
    assert "const languageResources = " in html
    assert 'class="target-editor' in html
    assert 'contenteditable="true"' not in html
    assert '<textarea id="focusTarget"' not in html
    assert "function visibleRows()" in html
    assert "function savePage()" in html
    assert "function submitPage()" in html
    assert "function applyFormat(action)" in html
    assert "function sanitizeTargetHtml(html)" in html
    assert "function targetFormatClass(row)" in html
    assert "function autoResizeEditor(editor)" in html
    assert "function syncTargetCell(index, editor)" in html
    assert "function contextPreviewText(row)" in html
    assert "function renderContextDetails(row)" in html
    assert "function restoreAutosavedDraft()" in html
    assert "function autoSaveDraft(" in html
    assert "function rememberSelection()" in html
    assert "target.setRangeText('\\n'" in html
    assert "target.setRangeText('\\u00a0'" in html
    assert "compositionstart" in html
    assert "compositionend" in html
    assert "event.isComposing" in html
    assert "document.execCommand" not in html
    assert "const wrappers = { B:" not in html
    assert "target.innerText = nextValue" not in html
    assert "target.innerHTML = sanitizeTargetHtml" not in html
    assert '>${escapeHtml(r.target)}</td>' not in html
    assert "function setActiveRow(i)" in html
    assert "function confirmActiveSegment()" in html
    assert "function updateSubmitState()" in html
    assert "function updateConfirmAllState()" in html
    assert "function allRowsConfirmed()" in html
    assert "submitButton.disabled = !allConfirmed" in html
    assert "function updateExportButtonState()" in html
    assert "exportButton.disabled = !allConfirmed" in html
    assert "Tick ${pendingCount} more segment" in html
    assert "tabButtons.forEach" in html
    assert "sourceSearchInput.addEventListener" in html
    assert "targetSearchInput.addEventListener" in html
    assert "confirmAllCheck.addEventListener" in html
    assert "contextOptionInputs.forEach" in html
    assert "filterOptionInputs.forEach" in html
    assert "toggleDropdown(filterDropdown, filterTrigger)" in html
    assert "action === 'Confirm'" in html
    assert "action === 'Complete'" not in html
    assert "localStorage.setItem('errorsweep-cat-editor-draft'" in html
    assert "filterMode" not in html
    assert "sortMode" not in html
    assert "pendingOnly" not in html


def test_media_editor_uses_reference_template() -> None:
    source = read_app()
    route_start = source.index("def render_external_media_editor")
    route_end = source.index("def media_editor_time_text", route_start)
    route_body = source[route_start:route_end]
    assert "render_reference_media_editor_shell(job_id, rows, metadata, media_source, media_type, media_name or file_name)" in route_body
    assert "media_source, media_type, media_name = read_media_preview_bytes(metadata)" in route_body

    shell_start = source.index("def render_reference_media_editor_shell")
    shell_end = source.index("def render_external_editor_router", shell_start)
    shell_body = source[shell_start:shell_end]
    assert 'assets" / "media_editor_reference.html' in shell_body
    assert "html.replace(\"__MEDIA_EDITOR_PAYLOAD__\"" in shell_body
    assert "media_preview_component_payload(media_source, media_type, media_name or file_name)" in shell_body
    assert "build_editor_language_resources(workspace_rules())" in shell_body
    assert 'id="media-editor-page-marker"' in shell_body
    assert "body:has(#media-editor-page-marker) .st-key-errorsweep_shell_content" in shell_body
    assert "max-width:var(--es-shell-content-width) !important" in shell_body
    assert "components.html(html, height=900, scrolling=False)" in shell_body
    assert "width:100vw !important" not in shell_body
    assert "max-width:100vw !important" not in shell_body


def test_media_editor_reference_file_restores_workflow_controls() -> None:
    reference = Path(__file__).parent / "assets" / "media_editor_reference.html"
    assert reference.exists()
    html = reference.read_text(encoding="utf-8")
    assert "__MEDIA_EDITOR_PAYLOAD__" in html
    assert '<main class="editor-layout">' in html
    assert '<section class="left-column">' in html
    assert '<aside class="right-column">' in html
    assert 'grid-template-columns: minmax(0, 1fr) minmax(320px, 340px);' in html
    assert 'id="mediaBox"' in html
    assert 'id="mediaRows"' in html
    assert 'class="timing-drawer"' in html
    assert 'id="splitBtn"' in html
    assert 'id="mergeBtn"' in html
    assert 'id="insertBtn"' in html
    assert 'id="submitBtn"' in html
    assert 'id="exportCsvBtn"' in html
    assert 'id="exportSrtBtn"' in html
    assert "Save Draft" not in html
    assert 'id="saveDraftBtn"' not in html
    assert "Focused text" not in html
    assert 'id="focusedText"' not in html
    assert 'id="focusedSaveBtn"' not in html
    assert 'id="focusedApproveBtn"' not in html
    assert 'id="qualityChecks"' in html
    assert "errorsweep-media-editor-draft:${payload.job_id" in html
    assert "localStorage.setItem(draftKey, JSON.stringify" in html
    assert "function restoreAutosavedDraft()" in html
    assert "function scheduleAutoSave()" in html
    assert "function allRowsConfirmed()" in html
    assert "function updateSubmitState()" in html
    assert "function updateExportButtonState()" in html
    assert "button.disabled = !allConfirmed" in html
    assert "button.classList.toggle(\"btn-mint\", allConfirmed)" in html
    assert "[\"exportCsvBtn\", \"exportSrtBtn\"].forEach" in html
    assert "Tick ${pending} more segment" in html
    assert "row.confirmed || row.done || row.status === \"Approved\"" in html
    assert "rows[idx].status = control.checked ? \"Approved\"" in html


def test_human_review_workspace_uses_reference_template() -> None:
    source = read_app()
    assert "def parse_context_upload(" in source
    assert "Upload context file (optional)" in source
    assert "context=uploaded_context" in source
    assert "const uploadedContext = {uploaded_context_json};" in source
    assert "context_file_name" in source
    start = source.index("def render_text_review_editor")
    end = source.index("def render_focused_subtitle_workspace", start)
    body = source[start:end]
    assert "render_reference_cat_editor_shell" in body
    assert "rules=workspace_rules()" in body
    assert "st.data_editor" not in body
    assert "cat_v40" not in body
    assert "main_col, side_col" not in body


def test_unlimited_access_account_bypasses_usage_allowance() -> None:
    source = read_app()
    assert "UNLIMITED_ACCESS_EMAIL = \"adapalanaveen401@gmail.com\"" in source
    assert "UNLIMITED_ACCESS_PASSWORD_HASH" in source
    assert "def is_platform_owner_identity(" in source
    assert "UNLIMITED_ACCESS_EMAIL.lower()" in source
    assert '"workspace": "Platform",' in source
    assert '"role": "Platform Owner",' in source
    assert 'login_user(UNLIMITED_ACCESS_EMAIL, "Platform Owner", "owner", "Platform")' in source
    assert 'login_user(UNLIMITED_ACCESS_EMAIL, "Workspace Owner", "workspace", UNLIMITED_ACCESS_WORKSPACE)' not in source
    assert 'class="es-topnav-owner-tag">Owner tools</div>' in source
    assert "es-topnav-owner-row" in source
    assert "\"name\": \"Unlimited\"" in source
    assert "def ensure_unlimited_access_account()" in source
    assert "Unlimited platform owner sign-in" in source
    assert "plan_name.lower() == \"unlimited\"" in source
    assert "return True, \"\", details" in source


def test_qa_findings_are_rendered_as_readable_labels() -> None:
    source = read_app()
    assert "def qa_finding_label(" in source
    assert "def readable_qa_findings(" in source
    assert "def rows_for_display(" in source
    assert "pd.DataFrame(rows_for_display(review_rows))" in source


def test_human_review_editor_density_is_scoped_to_iframe_shell() -> None:
    source = read_app()
    body = active_cat_editor_body(source)
    assert 'id="human-review-editor-page-marker"' in body
    assert 'class="human-review-editor-page human_review_editor_page"' in body
    assert "body:has(#human-review-editor-page-marker)" in body
    assert "body:has(.human-review-editor)" not in body
    assert "iframe" in body
    assert "height:100% !important" in body
    assert "overflow:hidden !important" in body
    assert '.st-key-errorsweep_shell_content > div[data-testid="stVerticalBlock"] > div:has(iframe)' in body
    assert '.st-key-errorsweep_shell_content > div[data-testid="stVerticalBlock"] > div:has(#human-review-editor-page-marker)' in body
    assert "height:0 !important" in body
    assert "width:100% !important" in body
    assert "max-width:100% !important" in body
    assert "min-width:0 !important" in body
    assert "width:100vw !important" not in body
    assert "max-width:100vw !important" not in body
    assert "zoom:" not in body
    assert "transform: scale" not in body
    assert "font-size:110%" not in body
    assert "font-size:120%" not in body


def test_dashboard_and_human_review_use_separate_page_scopes() -> None:
    source = read_app()
    dashboard_start = source.index("def page_dashboard")
    dashboard_end = source.index("def page_projects", dashboard_start)
    dashboard_body = source[dashboard_start:dashboard_end]
    editor_body = active_cat_editor_body(source)
    assert 'id="errorsweep-dashboard-page-marker"' in dashboard_body
    assert 'class="errorsweep_dashboard_page"' in dashboard_body
    assert "def render_root_app_shell(" in source
    assert "def render_shell_scroll_bridge()" in source
    assert "MutationObserver(applyShellScroll)" in source
    assert "const editorMode = !!editorMarker;" in source
    assert 'scrollTarget.style.overflowY = "hidden"' in source
    assert 'contentKey.style.overflowY = editorMode ? "hidden" : "auto"' in source
    assert 'contentKey.style.overscrollBehavior = editorMode ? "none" : "contain"' in source
    assert "--es-shell-frame-padding: 0 18px 0;" in source
    assert "--es-shell-content-width: min(1760px, calc(100vw - 56px));" in source
    assert "body:has(#errorsweep-root-shell-marker) [data-testid=\"stAppViewContainer\"] .main .block-container" in source
    assert "body:has(#errorsweep-root-shell-marker):not(:has(#human-review-editor-page-marker)):not(:has(#media-editor-page-marker))" not in source
    assert "max-width: var(--es-shell-content-width) !important" in source
    assert ".st-key-errorsweep_app_shell {\n  height: 100dvh !important" in source
    assert "overflow-y: hidden !important;\n  overscroll-behavior: none !important;" in source
    assert ".st-key-errorsweep_page_frame" in source
    assert 'key="errorsweep_page_frame"' in source
    assert "def render_root_app_shell(content_renderer, *, page_frame: bool = True, show_navigation: bool = True)" in source
    assert "page_frame=True" in source
    assert "show_navigation=False" in source
    assert 'const shellFrameWidth = editorMode ? "100%" : "min(1760px, calc(100vw - 56px))";' in source
    assert "const fullBleedEditor = !!(" not in source
    assert "node.style.width = \"100%\"" in source
    assert "node.style.maxWidth = shellFrameWidth" in source
    assert 'appShell.style.maxWidth = shellFrameWidth' in source
    assert 'node.style.maxWidth = "100%"' in source
    assert "node.style.minWidth = \"0\"" in source
    assert "100vw\" : shellFrameWidth" not in source
    assert 'parentDoc.querySelectorAll(".st-key-errorsweep_page_frame")' in source
    assert "rootVertical.style.gridTemplateRows = \"minmax(0, 1fr)\"" in source
    assert "appShellWrapper.style.margin = \"0\"" in source
    assert "render_shell_scroll_bridge()" in source
    assert 'key="errorsweep_app_shell"' in source
    assert 'key="errorsweep_shell_top"' in source
    assert 'key="errorsweep_shell_content"' in source
    assert ".es-topnav-row {" in source
    assert "min-height: 62px;" in source
    assert "flex-wrap: nowrap;" in source
    assert "overflow: hidden;" in source
    assert ".es-topnav-link {" in source
    assert "padding: 0 8px;" in source
    assert ".st-key-errorsweep_app_shell" in source
    assert ".st-key-errorsweep_shell_top" in source
    assert ".st-key-errorsweep_shell_content" in source
    assert 'div:has(#errorsweep-shell-content-row-marker)' in source
    assert "grid-template-rows: auto minmax(0, 1fr) !important" in source
    assert "height: 100dvh !important" in source
    assert "overflow-y: scroll !important" in source
    assert "overscroll-behavior: contain !important" in source
    assert "scrollbar-gutter: stable both-edges !important" in source
    assert "render_root_app_shell(lambda: render_external_editor_router(), page_frame=True, show_navigation=False)" in source
    assert "def render_task_navigation_links(task: Dict[str, Any]) -> None" in source
    assert "task_monitor_link(task_id)" in source
    assert "human_review_editor_link(review_job_id)" in source
    assert "render_usage_task_links()" in source
    assert "body:has(#errorsweep-dashboard-page-marker) .stButton > button" in source
    assert "body:has(#human-review-editor-page-marker) .block-container" not in editor_body
    assert 'body:has(#human-review-editor-page-marker) [data-testid="stMainBlockContainer"]' not in editor_body
    assert "body:has(#human-review-editor-page-marker) .st-key-errorsweep_shell_content" in editor_body
    assert "errorsweep-dashboard-page-marker" not in editor_body
    assert "human-review-editor-page-marker" not in dashboard_body
    assert re.search(r"(?m)^\s*\.stButton\s*>", source) is None


if __name__ == "__main__":
    test_editor_links_do_not_emit_session_tokens()
    test_navigation_links_do_not_emit_session_tokens()
    test_auth_redirect_uses_es_page_login_without_route_param()
    test_login_es_page_aliases_are_public_and_normalized()
    test_login_success_opens_target_route_in_current_tab()
    test_public_login_and_authenticated_entry_routes_open_dashboard()
    test_public_entry_routes_use_cookie_provider_not_restore_miss_gate()
    test_authenticated_login_tab_shows_logged_in_state()
    test_login_new_tab_bridge_reruns_before_rendering_status()
    test_unknown_and_unauthorized_routes_are_separate()
    test_navigation_uses_central_route_helpers()
    test_editor_urls_are_clean_routes_without_session_tokens()
    test_human_review_editor_uses_es_page_review_id_route()
    test_reload_session_restore_uses_cookie_not_url_only()
    test_session_check_page_removed_and_protected_routes_resolve()
    test_public_login_signup_navigation_ignores_restore_miss()
    test_login_session_persists_until_explicit_logout()
    test_refresh_restores_last_authenticated_route()
    test_translation_editor_uses_supplied_html_template()
    test_cat_editor_reference_file_matches_attached_shell()
    test_media_editor_uses_reference_template()
    test_media_editor_reference_file_restores_workflow_controls()
    test_human_review_workspace_uses_reference_template()
    test_unlimited_access_account_bypasses_usage_allowance()
    test_qa_findings_are_rendered_as_readable_labels()
    test_human_review_editor_density_is_scoped_to_iframe_shell()
    test_dashboard_and_human_review_use_separate_page_scopes()
    print("CAT editor regression checks passed.")
