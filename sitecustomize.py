"""Runtime compatibility fixes for the ErrorSweep Streamlit shell.

Python imports ``sitecustomize`` automatically when this repository root is on
``sys.path``. Keep this module defensive: it patches Streamlit after Streamlit
has been imported, avoids URL-reload navigation inside the authenticated app,
and adds a visible fallback for auth/session-restore bridges.
"""
from __future__ import annotations

import builtins
import functools
import json
import logging
import re
import sys
from typing import Any, Callable, Iterable, List

LOGGER = logging.getLogger(__name__)

_ORIGINAL_IMPORT = builtins.__import__
_STREAMLIT_PATCHED = False
_COMPONENTS_PATCHED = False

_DEFAULT_WORKSPACE_PAGES = [
    "Dashboard",
    "Projects",
    "Jobs",
    "ErrorSweep QA",
    "ErrorSweep Pro",
    "Subtitle / Transcription Editor",
    "Scorecards",
    "Memory & Rules",
    "Team & Roles",
    "Billing",
    "Account",
    "Admin",
]
_DEFAULT_OWNER_PAGES = [
    "Owner Console",
    "Payments Received",
    "User Access Matrix",
    "All Workspaces",
    "Platform Settings",
    "Platform Audit Logs",
]
_LABEL_MAP = {
    "Dashboard": "Dashboard",
    "Projects": "Projects",
    "Jobs": "Jobs",
    "ErrorSweep QA": "QA Tasks",
    "ErrorSweep Pro": "Pro",
    "Subtitle / Transcription Editor": "Subtitles",
    "Scorecards": "Scorecards",
    "Memory & Rules": "Rules",
    "Team & Roles": "Team",
    "Billing": "Billing",
    "Account": "Account",
    "Admin": "Admin",
}

_SHELL_VISIBILITY_FALLBACK_CSS = """
<style data-errorsweep-shell-visibility-fallback="true">
body:has(#errorsweep-root-shell-marker) [data-testid="stAppViewContainer"],
body:has(#errorsweep-root-shell-marker) [data-testid="stMain"],
body:has(#errorsweep-root-shell-marker) [data-testid="stMainBlockContainer"],
body:has(#errorsweep-root-shell-marker) .block-container,
body:has(#errorsweep-root-shell-marker) .block-container > div[data-testid="stVerticalBlock"],
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_app_shell,
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_app_shell > div[data-testid="stVerticalBlock"] {
  min-height: 0 !important;
  visibility: visible !important;
  opacity: 1 !important;
}
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_shell_content {
  display: block !important;
  box-sizing: border-box !important;
  min-height: 0 !important;
  height: calc(100dvh - 76px) !important;
  max-height: calc(100dvh - 76px) !important;
  width: 100% !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  overscroll-behavior: contain !important;
  scrollbar-gutter: stable both-edges !important;
  padding: var(--es-shell-frame-padding, 0 18px 0) !important;
  visibility: visible !important;
  opacity: 1 !important;
}
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_shell_content > div[data-testid="stVerticalBlock"],
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_page_frame,
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_page_frame > div[data-testid="stVerticalBlock"] {
  display: block !important;
  box-sizing: border-box !important;
  min-height: 1px !important;
  height: auto !important;
  max-height: none !important;
  width: 100% !important;
  max-width: var(--es-shell-content-width, min(1760px, calc(100vw - 56px))) !important;
  margin-left: auto !important;
  margin-right: auto !important;
  overflow: visible !important;
  visibility: visible !important;
  opacity: 1 !important;
}
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_page_frame .element-container,
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_page_frame [data-testid="stElementContainer"] {
  visibility: visible !important;
  opacity: 1 !important;
}
</style>
"""

_NATIVE_TOPNAV_CSS = """
<style data-errorsweep-native-topnav="true">
#errorsweep-native-topnav-marker { display: none !important; }
body:has(#errorsweep-native-topnav-marker) .st-key-errorsweep_native_topnav {
  width: 100% !important;
  max-width: min(1760px, calc(100vw - 56px)) !important;
  margin: 0 auto !important;
  padding: 10px 18px 8px !important;
  border-bottom: 1px solid rgba(84,105,180,.24) !important;
  background: linear-gradient(180deg, rgba(9,14,28,.97), rgba(6,10,20,.94)) !important;
  box-shadow: 0 10px 36px rgba(0,0,0,.22) !important;
}
body:has(#errorsweep-native-topnav-marker) .st-key-errorsweep_native_topnav_title {
  color: #f8fbff !important;
  font-weight: 950 !important;
  letter-spacing: -.03em !important;
  margin: 0 !important;
  line-height: 1.05 !important;
}
body:has(#errorsweep-native-topnav-marker) .st-key-errorsweep_native_topnav_subtitle {
  color: #8ea1dc !important;
  font-size: 11px !important;
  font-weight: 800 !important;
  margin-top: 2px !important;
}
body:has(#errorsweep-native-topnav-marker) .st-key-errorsweep_native_topnav [data-testid="stButton"] > button,
body:has(#errorsweep-native-topnav-marker) .st-key-errorsweep_native_topnav .stButton > button {
  min-height: 38px !important;
  width: 100% !important;
  border-radius: 8px !important;
  border: 1px solid rgba(84,105,180,.30) !important;
  background: rgba(18,21,38,.72) !important;
  color: #dce8ff !important;
  font-weight: 900 !important;
  padding: 8px 10px !important;
  box-shadow: none !important;
}
body:has(#errorsweep-native-topnav-marker) .st-key-errorsweep_native_topnav [data-testid="stButton"] > button:hover,
body:has(#errorsweep-native-topnav-marker) .st-key-errorsweep_native_topnav .stButton > button:hover {
  border-color: rgba(52,189,246,.48) !important;
  background: rgba(52,189,246,.12) !important;
  color: #f8fbff !important;
}
</style>
"""

_AUTH_BRIDGE_FALLBACK = """
<div style="box-sizing:border-box;min-height:150px;padding:28px 24px;color:#f8fbff;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:linear-gradient(135deg,rgba(0,217,133,.12),rgba(52,189,246,.10)),#070914;">
  <div style="max-width:720px;margin:0 auto;border:1px solid rgba(84,105,180,.34);border-radius:14px;padding:18px 20px;background:rgba(18,21,38,.82);box-shadow:0 18px 54px rgba(0,0,0,.25);">
    <div style="font-weight:950;font-size:18px;margin-bottom:6px;">Opening ErrorSweep…</div>
    <div style="color:#c2c9e9;font-size:14px;line-height:1.5;">If this page stays here for more than a few seconds, open the sign-in page again. After signing in, use the in-app buttons across the top to move between pages.</div>
    <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap;">
      <a target="_top" href="?es_page=Login" style="display:inline-flex;align-items:center;justify-content:center;min-height:38px;padding:0 14px;border-radius:999px;background:linear-gradient(90deg,#00d985,#34bdf6);color:#05131c;text-decoration:none;font-weight:950;">Sign in again</a>
      <a target="_top" href="?es_page=Dashboard" style="display:inline-flex;align-items:center;justify-content:center;min-height:38px;padding:0 14px;border-radius:999px;border:1px solid rgba(84,105,180,.40);color:#f8fbff;text-decoration:none;font-weight:900;">Try Dashboard</a>
    </div>
  </div>
</div>
"""


def _main_module() -> Any:
    return sys.modules.get("__main__")


def _call_or_default(func: Any, default: Any = None) -> Any:
    try:
        return func() if callable(func) else default
    except Exception:
        LOGGER.debug("ErrorSweep compatibility callback failed", exc_info=True)
        return default


def _normalize_page(page: str) -> str:
    main = _main_module()
    normalizer = getattr(main, "normalize_es_page", None)
    if callable(normalizer):
        try:
            return normalizer(page)
        except Exception:
            LOGGER.debug("normalize_es_page failed", exc_info=True)
    return str(page or "Dashboard").strip() or "Dashboard"


def _safe_key(value: str) -> str:
    key = re.sub(r"[^A-Za-z0-9_]+", "_", str(value)).strip("_").lower()
    return key or "page"


def _known_pages() -> List[str]:
    main = _main_module()
    pages = _call_or_default(getattr(main, "allowed_pages", None), [])
    if pages:
        return [str(page) for page in pages]
    return list(_DEFAULT_WORKSPACE_PAGES)


def _ordered_pages(order: Iterable[str], allowed: Iterable[str]) -> List[str]:
    allowed_set = set(allowed)
    return [page for page in order if page in allowed_set]


def _is_owner() -> bool:
    main = _main_module()
    return bool(_call_or_default(getattr(main, "is_owner", None), False))


def _current_role() -> str:
    main = _main_module()
    role = _call_or_default(getattr(main, "current_role", None), "User")
    return str(role or "User")


def _sync_route_state(params: dict[str, str]) -> None:
    main = _main_module()
    sync = getattr(main, "sync_browser_route_state", None)
    if callable(sync):
        try:
            sync(params)
        except Exception:
            LOGGER.debug("sync_browser_route_state failed", exc_info=True)


def _native_navigate(page: str) -> None:
    import streamlit as st  # type: ignore

    page_name = _normalize_page(page)
    st.session_state["es_page"] = page_name
    st.session_state["page"] = page_name
    st.session_state["current_route"] = {"page": page_name, "es_page": page_name}
    for stale in ("public", "return_to", "route", "es_editor", "job_id", "review_id"):
        try:
            if stale in st.query_params:
                del st.query_params[stale]
        except Exception:
            LOGGER.debug("Unable to clear query param %s", stale, exc_info=True)
    try:
        st.query_params["es_page"] = page_name
    except Exception:
        LOGGER.debug("Unable to set es_page query param", exc_info=True)
    _sync_route_state({"es_page": page_name})
    st.rerun()


def _render_native_topnav(original_markdown: Callable[..., Any]) -> None:
    import streamlit as st  # type: ignore

    allowed = _known_pages()
    main = _main_module()
    workspace_order = list(getattr(main, "WORKSPACE_PAGES", _DEFAULT_WORKSPACE_PAGES) or _DEFAULT_WORKSPACE_PAGES)
    owner_order = list(getattr(main, "OWNER_PAGES", _DEFAULT_OWNER_PAGES) or _DEFAULT_OWNER_PAGES)
    workspace_pages = _ordered_pages(workspace_order, allowed)
    owner_pages = _ordered_pages(owner_order, allowed) if _is_owner() else []
    active_page = _normalize_page(str(st.session_state.get("page") or st.query_params.get("es_page") or "Dashboard"))
    role = _current_role()
    user = st.session_state.get("user") or {}
    email = str(user.get("email") or "user@errorsweep.local")
    user_label = email.split("@", 1)[0].replace("_", " ").replace(".", " ").title() or "User"
    settings_page = "Platform Settings" if _is_owner() else ("Admin" if "Admin" in allowed else "Account")

    original_markdown(_NATIVE_TOPNAV_CSS, unsafe_allow_html=True)
    original_markdown('<div id="errorsweep-native-topnav-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
    with st.container(key="errorsweep_native_topnav"):
        brand_col, nav_col, action_col = st.columns([0.18, 0.64, 0.18], gap="small")
        with brand_col:
            original_markdown(f'<div class="st-key-errorsweep_native_topnav_title">error<span style="color:#7dd3fc;">sweep</span></div>', unsafe_allow_html=True)
            original_markdown(f'<div class="st-key-errorsweep_native_topnav_subtitle">{user_label} · {role}</div>', unsafe_allow_html=True)
        with nav_col:
            if workspace_pages:
                rows = [workspace_pages[i:i + 7] for i in range(0, len(workspace_pages), 7)]
                for row_index, row in enumerate(rows):
                    cols = st.columns(len(row), gap="small")
                    for col, page in zip(cols, row):
                        label = _LABEL_MAP.get(page, page)
                        button_label = f"● {label}" if page == active_page else label
                        if col.button(button_label, key=f"native_nav_{row_index}_{_safe_key(page)}", use_container_width=True):
                            _native_navigate(page)
            if owner_pages:
                original_markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
                owner_cols = st.columns(min(len(owner_pages), 6), gap="small")
                for idx, page in enumerate(owner_pages[:6]):
                    label = f"● {page}" if page == active_page else page
                    if owner_cols[idx].button(label, key=f"native_owner_nav_{_safe_key(page)}", use_container_width=True):
                        _native_navigate(page)
        with action_col:
            if st.button("Settings", key="native_nav_settings", use_container_width=True):
                _native_navigate(settings_page)
            if st.button("Logout", key="native_nav_logout", use_container_width=True):
                logout = getattr(main, "logout", None)
                if callable(logout):
                    logout()
                else:
                    st.session_state.clear()
                    st.query_params["es_page"] = "Login"
                    st.rerun()


def _should_replace_topnav(body: Any) -> bool:
    text = str(body)
    return '<nav class="es-topnav"' in text or "<nav class='es-topnav'" in text


def _patch_streamlit_markdown() -> None:
    """Inject shell fallback CSS and replace reload anchors with native nav buttons."""
    global _STREAMLIT_PATCHED
    if _STREAMLIT_PATCHED:
        return
    st = sys.modules.get("streamlit")
    if st is None:
        return

    original_markdown = getattr(st, "markdown", None)
    if not callable(original_markdown):
        _STREAMLIT_PATCHED = True
        return
    if getattr(original_markdown, "_errorsweep_shell_fallback", False):
        _STREAMLIT_PATCHED = True
        return

    @functools.wraps(original_markdown)
    def markdown_with_shell_fallback(body: Any, *args: Any, **kwargs: Any) -> Any:
        if _should_replace_topnav(body):
            try:
                _render_native_topnav(original_markdown)
                return None
            except Exception:
                LOGGER.warning("Native ErrorSweep navigation fallback failed; rendering original navigation", exc_info=True)
        result = original_markdown(body, *args, **kwargs)
        try:
            if "errorsweep-root-shell-marker" in str(body):
                original_markdown(_SHELL_VISIBILITY_FALLBACK_CSS, unsafe_allow_html=True)
        except Exception:
            LOGGER.debug("Unable to inject ErrorSweep shell visibility fallback", exc_info=True)
        return result

    setattr(markdown_with_shell_fallback, "_errorsweep_shell_fallback", True)
    st.markdown = markdown_with_shell_fallback  # type: ignore[attr-defined]
    _STREAMLIT_PATCHED = True


def _patch_components_html() -> None:
    """Make auth restore bridges visible instead of leaving a blank page."""
    global _COMPONENTS_PATCHED
    if _COMPONENTS_PATCHED:
        return
    components = sys.modules.get("streamlit.components.v1")
    if components is None:
        return
    original_html = getattr(components, "html", None)
    if not callable(original_html):
        _COMPONENTS_PATCHED = True
        return
    if getattr(original_html, "_errorsweep_auth_bridge_fallback", False):
        _COMPONENTS_PATCHED = True
        return

    @functools.wraps(original_html)
    def html_with_auth_bridge_fallback(html: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(html)
        is_restore_bridge = 'url.searchParams.set("es_restore", token)' in text
        is_login_bridge = 'url.searchParams.set("es_page", "Login")' in text and "returnTo" in text
        if is_restore_bridge or is_login_bridge:
            html = _AUTH_BRIDGE_FALLBACK + text
            try:
                kwargs["height"] = max(int(kwargs.get("height") or 0), 190)
            except Exception:
                kwargs["height"] = 190
            kwargs.setdefault("scrolling", False)
        return original_html(html, *args, **kwargs)

    setattr(html_with_auth_bridge_fallback, "_errorsweep_auth_bridge_fallback", True)
    components.html = html_with_auth_bridge_fallback  # type: ignore[attr-defined]
    _COMPONENTS_PATCHED = True


def _patch_streamlit() -> None:
    _patch_streamlit_markdown()
    _patch_components_html()


def _errorsweep_import_hook(name: str, globals: Any = None, locals: Any = None, fromlist: tuple[Any, ...] = (), level: int = 0) -> Any:
    module = _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)
    if name == "streamlit" or name.startswith("streamlit."):
        _patch_streamlit()
    return module


if not getattr(builtins, "_errorsweep_import_hook_installed", False):
    setattr(builtins, "_errorsweep_import_hook_installed", True)
    builtins.__import__ = _errorsweep_import_hook

_patch_streamlit()
