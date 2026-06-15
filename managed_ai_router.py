"""
managed_ai_router.py — CogniSweep Managed AI safe fallback router

What this file does:
1. If the user added their own API key, use that key with the selected provider/base URL.
2. If Managed AI/vLLM is explicitly enabled and reachable, use it.
3. If Managed AI fails or is not configured, fall back to the platform OpenAI key when available.

This module also installs small runtime compatibility helpers for Streamlit Cloud:
- normalize malformed editor query keys like ;review_id -> review_id before app.py reads them
- keep protected pages reload-safe without rewriting visible HTML markup
- keep the signup page scrollable
- keep the login page open while launching the authenticated tool tab
- ensure the main platform owner keeps Unlimited access
"""

from __future__ import annotations

import functools
import inspect
import ipaddress
import json
import os
import re
import socket
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlsplit, urlunsplit

try:
    import streamlit as st
except Exception:
    st = None

# -----------------------------------------------------------------------------
# Runtime compatibility constants
# -----------------------------------------------------------------------------

_PUBLIC_ES_PAGES = {
    "landing", "login", "signup", "verify", "reset", "terms", "privacy",
    "security", "cookies", "dpa", "sso handoff", "billing success",
    "billing cancel", "billing_success", "billing_cancel", "sso_handoff",
}
_PROTECTED_LINK_KEYS = {"es_page", "es_editor", "job_id", "review_id", "task_id"}
_ROUTE_KEYS = {
    "es_page", "es_editor", "job_id", "review_id", "task_id", "es_session",
    "es_restore", "tool_tab", "return_to", "route", "public", "es_restore_miss",
}
_SESSION_COOKIE_NAME = "errorsweep_session"
_SESSION_STORAGE_KEY = "errorsweep_session"
_SESSION_PERSISTENCE_SECONDS = 60 * 60 * 24 * 365 * 10

_MAIN_PLATFORM_OWNER_EMAIL = "adapalanaveen401@gmail.com"
_UNLIMITED_WORKSPACES = {"platform", "naveen unlimited workspace"}
_UNLIMITED_SEATS = 1_000_000
_UNLIMITED_SEGMENTS = 1_000_000_000
_UNLIMITED_CHARACTERS = 1_000_000_000_000
_OWNER_PATCHED = False


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).replace("\u00A0", " ").strip()
    except Exception:
        return ""


def _main_module() -> Any:
    return sys.modules.get("__main__")


def _query_value(params: Any, key: str) -> str:
    try:
        value = params.get(key, "")
        if isinstance(value, list):
            return _safe_text(value[0] if value else "")
        return _safe_text(value)
    except Exception:
        return ""


def _canonical_query_key(raw_key: Any) -> str:
    key = _safe_text(raw_key)
    key = unquote(key)
    key = key.replace("%3B", ";").replace("%3b", ";")
    while key.startswith((";", "&", "?")):
        key = key[1:]
    if key.startswith("amp;"):
        key = key[4:]
    if ";" in key:
        tail = key.split(";")[-1]
        if tail in _ROUTE_KEYS:
            key = tail
    return key


def _normalize_query_params() -> None:
    """Repair malformed route params before app.py calls query_get()."""
    if st is None:
        return
    try:
        params = st.query_params
    except Exception:
        return
    try:
        for raw_key in list(params.keys()):
            clean_key = _canonical_query_key(raw_key)
            if clean_key == raw_key or clean_key not in _ROUTE_KEYS:
                continue
            value = _query_value(params, raw_key)
            if value and not _query_value(params, clean_key):
                params[clean_key] = value
            try:
                del params[raw_key]
            except Exception:
                pass

        es_page = _query_value(params, "es_page")
        for key in ("review_id", "job_id", "es_editor", "task_id"):
            match = re.search(rf"(?:^|[;&]){re.escape(key)}=([^&;]+)", es_page)
            if match and not _query_value(params, key):
                params[key] = match.group(1)
                params["es_page"] = re.split(rf"[;&]{re.escape(key)}=", es_page, 1)[0].strip() or params.get("es_page", "")
    except Exception:
        pass


# Run immediately after Streamlit import. app.py imports this module before its
# route helpers are called, so this is early enough for query_get('review_id').
_normalize_query_params()


# -----------------------------------------------------------------------------
# Signup scroll helper
# -----------------------------------------------------------------------------

def _install_signup_scroll_fix() -> None:
    if st is None:
        return
    try:
        original_html = getattr(st, "html", None)
        if not callable(original_html) or getattr(original_html, "_errorsweep_signup_scroll_fix", False):
            return

        signup_scroll_css = """
        <div id="errorsweep-signup-scroll-marker" aria-hidden="true"></div>
        <style data-errorsweep-signup-scroll="true">
        #errorsweep-signup-scroll-marker { display: none !important; }
        body:has(#errorsweep-signup-scroll-marker) [data-testid="stMainBlockContainer"],
        body:has(#errorsweep-signup-scroll-marker) [data-testid="stAppViewContainer"] .main .block-container,
        body:has(#errorsweep-signup-scroll-marker) .block-container {
          height: 100dvh !important;
          max-height: 100dvh !important;
          min-height: 0 !important;
          overflow-x: hidden !important;
          overflow-y: auto !important;
          overscroll-behavior: contain !important;
          scrollbar-gutter: stable both-edges !important;
          scroll-behavior: smooth !important;
        }
        body:has(#errorsweep-signup-scroll-marker) [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"],
        body:has(#errorsweep-signup-scroll-marker) .block-container > div[data-testid="stVerticalBlock"] {
          height: auto !important;
          max-height: none !important;
          min-height: 100dvh !important;
          overflow: visible !important;
          padding-bottom: 56px !important;
        }
        body:has(#errorsweep-signup-scroll-marker) [data-testid="stMainBlockContainer"]::-webkit-scrollbar,
        body:has(#errorsweep-signup-scroll-marker) .block-container::-webkit-scrollbar { width: 11px; }
        body:has(#errorsweep-signup-scroll-marker) [data-testid="stMainBlockContainer"]::-webkit-scrollbar-track,
        body:has(#errorsweep-signup-scroll-marker) .block-container::-webkit-scrollbar-track { background: rgba(5, 7, 19, .82); }
        body:has(#errorsweep-signup-scroll-marker) [data-testid="stMainBlockContainer"]::-webkit-scrollbar-thumb,
        body:has(#errorsweep-signup-scroll-marker) .block-container::-webkit-scrollbar-thumb {
          background: linear-gradient(180deg, #11f5b5, #4aa8ff);
          border: 2px solid rgba(5, 7, 19, .82);
          border-radius: 999px;
        }
        </style>
        """

        def _current_route_is_signup() -> bool:
            try:
                page = _safe_text(st.query_params.get("es_page", "")).lower()
                public = _safe_text(st.query_params.get("public", "") or st.query_params.get("route", "")).lower()
                compact_page = re.sub(r"[^a-z0-9]+", "", page)
                compact_public = re.sub(r"[^a-z0-9]+", "", public)
                return compact_page in {"signup", "register", "registration"} or compact_public in {"signup", "register", "registration"}
            except Exception:
                return False

        @functools.wraps(original_html)
        def html_with_signup_scroll(body: Any, *args: Any, **kwargs: Any) -> Any:
            if _current_route_is_signup():
                text = str(body)
                if "errorsweep-signup-scroll-marker" not in text:
                    body = signup_scroll_css + text
            return original_html(body, *args, **kwargs)

        setattr(html_with_signup_scroll, "_errorsweep_signup_scroll_fix", True)
        st.html = html_with_signup_scroll
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Protected-link/session helpers
# -----------------------------------------------------------------------------

def _compact_page(value: str) -> str:
    return re.sub(r"\s+", " ", _safe_text(value).replace("+", " ").replace("_", " ").replace("-", " ").lower()).strip()


def _href_needs_session(href: str) -> bool:
    if not href or href.startswith("#") or href.lower().startswith(("mailto:", "tel:", "javascript:")):
        return False
    try:
        split = urlsplit(href)
        query = {_canonical_query_key(k): v for k, v in parse_qsl(split.query, keep_blank_values=True)}
        page = _compact_page(query.get("es_page", ""))
        if page and page in _PUBLIC_ES_PAGES:
            return False
        return any(query.get(key) for key in _PROTECTED_LINK_KEYS) and bool(
            page or query.get("es_editor") or query.get("job_id") or query.get("review_id") or query.get("task_id")
        )
    except Exception:
        return False


def _current_user() -> Dict[str, Any]:
    if st is None:
        return {}
    try:
        user = st.session_state.get("user") or {}
        return user if isinstance(user, dict) else {}
    except Exception:
        return {}


def _current_signed_session_token() -> str:
    if st is None:
        return ""
    try:
        for key in ("_pending_session_cookie", "_post_login_session_token"):
            value = _safe_text(st.session_state.get(key, ""))
            if value:
                return value
        user = _current_user()
        if not user:
            return ""
        signer = getattr(_main_module(), "signed_session_token_for_user", None)
        if callable(signer):
            token = _safe_text(signer(user))
            if token:
                st.session_state["_pending_session_cookie"] = token
                st.session_state["_post_login_session_token"] = token
                return token
    except Exception:
        return ""
    return ""


def _protected_page_session_script(token: str) -> str:
    token_json = json.dumps(token)
    cookie_name_json = json.dumps(_SESSION_COOKIE_NAME)
    storage_key_json = json.dumps(_SESSION_STORAGE_KEY)
    public_pages_json = json.dumps(sorted(_PUBLIC_ES_PAGES))
    protected_keys_json = json.dumps(sorted(_PROTECTED_LINK_KEYS))
    return f"""
    <script>
    (() => {{
      try {{
        const token = {token_json};
        const cookieName = {cookie_name_json};
        const storageKey = {storage_key_json};
        const publicPages = {public_pages_json};
        const protectedKeys = {protected_keys_json};
        const candidateWindows = [window.parent, window.top, window];
        const firstWindow = () => {{
          for (const candidate of candidateWindows) {{
            try {{
              if (candidate && candidate.location) return candidate;
            }} catch (err) {{}}
          }}
          return window;
        }};
        const firstDocument = () => {{
          for (const candidate of candidateWindows) {{
            try {{
              if (candidate && candidate.document) return candidate.document;
            }} catch (err) {{}}
          }}
          return document;
        }};
        const firstStorage = () => {{
          for (const candidate of candidateWindows) {{
            try {{
              if (candidate && candidate.localStorage) return candidate.localStorage;
            }} catch (err) {{}}
          }}
          try {{ return window.localStorage; }} catch (err) {{}}
          return null;
        }};
        const hostWindow = firstWindow();
        const doc = firstDocument();
        const secure = hostWindow.location.protocol === "https:" ? "; Secure" : "";
        try {{
          doc.cookie = cookieName + "=" + encodeURIComponent(token) + "; Max-Age={_SESSION_PERSISTENCE_SECONDS}; Path=/; SameSite=Lax" + secure;
        }} catch (err) {{}}
        try {{
          const storage = firstStorage();
          if (storage) storage.setItem(storageKey, token);
        }} catch (err) {{}}

        const normalizePage = (value) => String(value || "").replace(/[+_-]/g, " ").replace(/\s+/g, " ").trim().toLowerCase();
        const repairParams = (url) => {{
          const repairs = [
            [";review_id", "review_id"], ["amp;review_id", "review_id"], ["%3Breview_id", "review_id"],
            [";job_id", "job_id"], ["amp;job_id", "job_id"], ["%3Bjob_id", "job_id"],
            [";es_editor", "es_editor"], ["amp;es_editor", "es_editor"], ["%3Bes_editor", "es_editor"],
            [";task_id", "task_id"], ["amp;task_id", "task_id"], ["%3Btask_id", "task_id"]
          ];
          repairs.forEach(([bad, good]) => {{
            if (url.searchParams.has(bad) && !url.searchParams.has(good)) {{
              url.searchParams.set(good, url.searchParams.get(bad) || "");
              url.searchParams.delete(bad);
            }}
          }});
          return url;
        }};
        const isProtected = (url) => {{
          const page = normalizePage(url.searchParams.get("es_page"));
          if (page && publicPages.includes(page)) return false;
          return protectedKeys.some((key) => Boolean(url.searchParams.get(key))) || Boolean(page && !publicPages.includes(page));
        }};
        const patchUrl = () => {{
          try {{
            const current = repairParams(new URL(hostWindow.location.href));
            if (isProtected(current) && current.searchParams.get("es_session") !== token) current.searchParams.set("es_session", token);
            if (current.toString() !== hostWindow.location.href) hostWindow.history.replaceState(null, "", current.toString());
          }} catch (err) {{}}
        }};
        const patchLinks = () => {{
          try {{
            doc.querySelectorAll('a[href]').forEach((anchor) => {{
              const raw = String(anchor.getAttribute('href') || '');
              if (!raw || raw === '#' || raw.includes('es_logout=1') || /^(mailto:|tel:|javascript:)/i.test(raw)) return;
              const url = repairParams(new URL(raw, hostWindow.location.href));
              if (url.origin !== hostWindow.location.origin) return;
              if (!isProtected(url)) return;
              url.searchParams.set('es_session', token);
              anchor.setAttribute('href', url.pathname + url.search + url.hash);
            }});
          }} catch (err) {{}}
        }};
        patchUrl();
        patchLinks();
        try {{ new MutationObserver(patchLinks).observe(doc.body, {{ childList: true, subtree: true }}); }} catch (err) {{}}
      }} catch (err) {{}}
    }})();
    </script>
    """


# -----------------------------------------------------------------------------
# Owner unlimited access helpers
# -----------------------------------------------------------------------------

def _is_main_owner_user(user: Optional[Dict[str, Any]] = None) -> bool:
    candidate = user if isinstance(user, dict) else _current_user()
    return _safe_text(candidate.get("email")).lower() == _MAIN_PLATFORM_OWNER_EMAIL


def _unlimited_subscription(workspace: str = "Platform") -> Dict[str, Any]:
    workspace_name = _safe_text(workspace) or "Platform"
    return {
        "workspace": workspace_name,
        "user_email": _MAIN_PLATFORM_OWNER_EMAIL,
        "plan": "Unlimited",
        "status": "Active",
        "billing_cycle": "internal",
        "currency": "INR",
        "base_amount": 0,
        "included_segments": _UNLIMITED_SEGMENTS,
        "included_characters": _UNLIMITED_CHARACTERS,
        "included_seats": _UNLIMITED_SEATS,
        "provider": "internal",
        "provider_customer_id": "",
        "provider_subscription_id": "",
    }


def _unlimited_plan() -> Dict[str, Any]:
    return {
        "name": "Unlimited",
        "monthly": 0,
        "annual": 0,
        "currency": "INR",
        "seats": _UNLIMITED_SEATS,
        "segments": _UNLIMITED_SEGMENTS,
        "characters": _UNLIMITED_CHARACTERS,
        "label": "Unlimited internal access",
        "description": "Unlimited platform-owner access.",
    }


def _ensure_owner_entitlements() -> None:
    if st is None:
        return
    try:
        user = st.session_state.get("user")
        if not isinstance(user, dict) or not _is_main_owner_user(user):
            return
        user.update({
            "email": _MAIN_PLATFORM_OWNER_EMAIL,
            "role": "Platform Owner",
            "account_type": "owner",
            "workspace": _safe_text(user.get("workspace") or "Platform"),
            "plan": "Unlimited",
            "status": "Active",
            "email_verified": True,
        })
        st.session_state["user"] = user
        st.session_state["authenticated"] = True

        users = st.session_state.setdefault("users", [])
        owner_record = {k: user.get(k) for k in ("email", "workspace", "role", "account_type", "plan", "status", "email_verified")}
        for idx, item in enumerate(list(users)):
            if isinstance(item, dict) and _safe_text(item.get("email")).lower() == _MAIN_PLATFORM_OWNER_EMAIL:
                users[idx] = {**item, **owner_record}
                break
        else:
            users.insert(0, owner_record)

        workspaces = st.session_state.setdefault("workspaces", [])
        subscriptions = st.session_state.setdefault("subscriptions", [])
        for workspace_name in {"Platform", "Naveen Unlimited Workspace", _safe_text(user.get("workspace") or "Platform")}:
            if not workspace_name:
                continue
            workspace_record = {"workspace": workspace_name, "owner": _MAIN_PLATFORM_OWNER_EMAIL, "plan": "Unlimited", "status": "Active", "users": 1, "jobs": 0}
            for idx, item in enumerate(list(workspaces)):
                if isinstance(item, dict) and _safe_text(item.get("workspace")).lower() == workspace_name.lower():
                    workspaces[idx] = {**item, **workspace_record}
                    break
            else:
                workspaces.insert(0, workspace_record)

            subscription_record = _unlimited_subscription(workspace_name)
            for idx, item in enumerate(list(subscriptions)):
                if isinstance(item, dict) and _safe_text(item.get("workspace")).lower() == workspace_name.lower():
                    subscriptions[idx] = {**item, **subscription_record}
                    break
            else:
                subscriptions.insert(0, subscription_record)
    except Exception:
        pass


def _owner_unlimited_context(workspace: str = "") -> bool:
    _ensure_owner_entitlements()
    workspace_key = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "")).lower()
    return _is_main_owner_user() or workspace_key in _UNLIMITED_WORKSPACES


def _patch_owner_unlimited_functions() -> None:
    global _OWNER_PATCHED
    if _OWNER_PATCHED:
        _ensure_owner_entitlements()
        return
    module = _main_module()
    if module is None:
        return
    required = [
        "workspace_subscription", "workspace_usage_allowance", "workspace_seat_state",
        "check_workspace_usage_allowance", "check_workspace_seat_allowance", "current_role", "is_owner",
    ]
    if not all(callable(getattr(module, name, None)) for name in required):
        _ensure_owner_entitlements()
        return

    original_workspace_subscription = getattr(module, "workspace_subscription")
    original_workspace_usage_allowance = getattr(module, "workspace_usage_allowance")
    original_workspace_seat_state = getattr(module, "workspace_seat_state")
    original_check_workspace_usage_allowance = getattr(module, "check_workspace_usage_allowance")
    original_check_workspace_seat_allowance = getattr(module, "check_workspace_seat_allowance")
    original_current_role = getattr(module, "current_role")
    original_is_owner = getattr(module, "is_owner")

    @functools.wraps(original_current_role)
    def current_role_with_main_owner() -> str:
        _ensure_owner_entitlements()
        if _is_main_owner_user():
            return "Platform Owner"
        return original_current_role()

    @functools.wraps(original_is_owner)
    def is_owner_with_main_owner() -> bool:
        _ensure_owner_entitlements()
        return _is_main_owner_user() or bool(original_is_owner())

    @functools.wraps(original_workspace_subscription)
    def workspace_subscription_with_main_owner(workspace: str = "") -> Dict[str, Any]:
        _ensure_owner_entitlements()
        workspace_name = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "") or "Platform")
        if _owner_unlimited_context(workspace_name):
            return _unlimited_subscription(workspace_name)
        return original_workspace_subscription(workspace)

    @functools.wraps(original_workspace_usage_allowance)
    def workspace_usage_allowance_with_main_owner(workspace: str = "") -> Dict[str, Any]:
        _ensure_owner_entitlements()
        workspace_name = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "") or "Platform")
        if _owner_unlimited_context(workspace_name):
            return {"subscription": _unlimited_subscription(workspace_name), "plan": _unlimited_plan(), "segments": _UNLIMITED_SEGMENTS, "characters": _UNLIMITED_CHARACTERS, "seats": _UNLIMITED_SEATS}
        return original_workspace_usage_allowance(workspace)

    @functools.wraps(original_workspace_seat_state)
    def workspace_seat_state_with_main_owner(workspace: str = "") -> Dict[str, Any]:
        _ensure_owner_entitlements()
        workspace_name = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "") or "Platform")
        if _owner_unlimited_context(workspace_name):
            return {"workspace": workspace_name, "subscription": _unlimited_subscription(workspace_name), "plan": _unlimited_plan(), "used": 1, "limit": _UNLIMITED_SEATS, "available": _UNLIMITED_SEATS - 1}
        return original_workspace_seat_state(workspace)

    @functools.wraps(original_check_workspace_usage_allowance)
    def check_workspace_usage_allowance_with_main_owner(rows: List[Dict[str, Any]], purpose: str, workspace: str = "") -> Tuple[bool, str, Dict[str, Any]]:
        _ensure_owner_entitlements()
        workspace_name = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "") or "Platform")
        if _owner_unlimited_context(workspace_name):
            requested_segments = len(rows or [])
            requested_characters = sum(
                len(_safe_text(row.get("source", ""))) + len(_safe_text(row.get("target", "")))
                for row in (rows or [])
                if isinstance(row, dict)
            )
            return True, "", {
                "workspace": workspace_name,
                "plan": "Unlimited",
                "status": "active",
                "used_segments": 0,
                "used_characters": 0,
                "requested_segments": requested_segments,
                "requested_characters": requested_characters,
                "projected_segments": requested_segments,
                "projected_characters": requested_characters,
                "segment_limit": _UNLIMITED_SEGMENTS,
                "character_limit": _UNLIMITED_CHARACTERS,
                "unlimited": True,
            }
        return original_check_workspace_usage_allowance(rows, purpose, workspace)

    @functools.wraps(original_check_workspace_seat_allowance)
    def check_workspace_seat_allowance_with_main_owner(workspace: str, email: str, status: str = "Active") -> Tuple[bool, str, Dict[str, Any]]:
        _ensure_owner_entitlements()
        workspace_name = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "") or "Platform")
        if _owner_unlimited_context(workspace_name):
            return True, "", workspace_seat_state_with_main_owner(workspace_name)
        return original_check_workspace_seat_allowance(workspace, email, status)

    setattr(module, "current_role", current_role_with_main_owner)
    setattr(module, "is_owner", is_owner_with_main_owner)
    setattr(module, "workspace_subscription", workspace_subscription_with_main_owner)
    setattr(module, "workspace_usage_allowance", workspace_usage_allowance_with_main_owner)
    setattr(module, "workspace_seat_state", workspace_seat_state_with_main_owner)
    setattr(module, "check_workspace_usage_allowance", check_workspace_usage_allowance_with_main_owner)
    setattr(module, "check_workspace_seat_allowance", check_workspace_seat_allowance_with_main_owner)
    _OWNER_PATCHED = True
    _ensure_owner_entitlements()


# -----------------------------------------------------------------------------
# Runtime installers
# -----------------------------------------------------------------------------

def _install_authenticated_reload_bridge() -> None:
    if st is None:
        return
    try:
        original_markdown = getattr(st, "markdown", None)
        if not callable(original_markdown) or getattr(original_markdown, "_errorsweep_authenticated_reload_bridge", False):
            return

        @functools.wraps(original_markdown)
        def markdown_with_authenticated_reload(body: Any, *args: Any, **kwargs: Any) -> Any:
            _normalize_query_params()
            _patch_owner_unlimited_functions()
            token = _current_signed_session_token()
            text = str(body)
            is_shell_or_nav = "errorsweep-root-shell-marker" in text or "es-topnav" in text or "es-owner-strip" in text or "es-account-menu" in text

            # Do not rewrite HTML before passing it to Streamlit. Rewriting the
            # large top navigation string can make Streamlit display raw markup.
            result = original_markdown(body, *args, **kwargs)

            if token and is_shell_or_nav:
                try:
                    import streamlit.components.v1 as components
                    components.html(_protected_page_session_script(token), height=0, scrolling=False)
                except Exception:
                    pass
            return result

        setattr(markdown_with_authenticated_reload, "_errorsweep_authenticated_reload_bridge", True)
        st.markdown = markdown_with_authenticated_reload
    except Exception:
        pass


def _install_login_new_tab_bridge() -> None:
    if st is None:
        return
    try:
        original_rerun = getattr(st, "rerun", None)
        if not callable(original_rerun) or getattr(original_rerun, "_errorsweep_login_new_tab_bridge", False):
            return

        def _query_value_for_launch(key: str) -> str:
            try:
                value = st.query_params.get(key, "")
                if isinstance(value, list):
                    return _safe_text(value[0] if value else "")
                return _safe_text(value)
            except Exception:
                return ""

        def _called_from_login_flow() -> bool:
            try:
                names = {frame.function for frame in inspect.stack(context=0)[:18]}
                return bool(names & {"render_login", "render_sso_handoff"})
            except Exception:
                return False

        def _build_launch_url(session_token: str) -> str:
            params: Dict[str, str] = {}
            current_route = st.session_state.get("current_route")
            if isinstance(current_route, dict):
                page = _safe_text(current_route.get("es_page") or current_route.get("page"))
                if page:
                    params["es_page"] = page
                for key in ("es_editor", "job_id", "review_id", "task_id"):
                    value = _safe_text(current_route.get(key))
                    if value:
                        params[key] = value
            for key in ("es_page", "es_editor", "job_id", "review_id", "task_id"):
                value = _query_value_for_launch(key)
                if value:
                    params[key] = value
            public_page = re.sub(r"[^a-z0-9]+", "", params.get("es_page", "").lower())
            if not params.get("es_page") or public_page in {"login", "landing", "signup", "register", "registration"}:
                params["es_page"] = "Dashboard"
            params["es_session"] = session_token
            params["tool_tab"] = "1"
            return "?" + urlencode(params)

        def _leave_current_tab_on_login() -> None:
            try:
                for key in list(st.query_params.keys()):
                    try:
                        del st.query_params[key]
                    except Exception:
                        pass
                st.query_params["es_page"] = "Login"
            except Exception:
                pass

        @functools.wraps(original_rerun)
        def rerun_with_login_new_tab(*args: Any, **kwargs: Any) -> Any:
            try:
                _normalize_query_params()
                if _called_from_login_flow() and st.session_state.get("authenticated") and st.session_state.get("user"):
                    _patch_owner_unlimited_functions()
                    session_token = _current_signed_session_token()
                    if session_token:
                        st.session_state["_post_login_tool_launch_url"] = _build_launch_url(session_token)
                        st.session_state["_post_login_session_token"] = session_token
                        st.session_state["_post_login_tool_launch_id"] = uuid.uuid4().hex
                        st.session_state["_login_window_stay_open"] = True
                        _leave_current_tab_on_login()
            except Exception:
                pass
            return original_rerun(*args, **kwargs)

        setattr(rerun_with_login_new_tab, "_errorsweep_login_new_tab_bridge", True)
        st.rerun = rerun_with_login_new_tab
    except Exception:
        pass


_install_signup_scroll_fix()
_install_authenticated_reload_bridge()
_install_login_new_tab_bridge()

# -----------------------------------------------------------------------------
# Managed AI routing
# -----------------------------------------------------------------------------

from openai import OpenAI


@dataclass
class AIRoute:
    provider: str              # user_api | managed_vllm | openai_platform
    model: str
    api_key: str
    base_url: Optional[str]
    managed: bool


def _secret(name: str, default: str = "") -> str:
    if os.environ.get(name):
        return os.environ[name]
    if st is not None:
        try:
            value = st.secrets.get(name)
            if value is not None:
                return str(value)
        except Exception:
            pass
    return default


def _session_value(name: str, default: str = "") -> str:
    if st is not None:
        try:
            return str(st.session_state.get(name, default) or default)
        except Exception:
            pass
    return default


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}


def _normalize_base_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and not url.endswith("/v1"):
        url += "/v1"
    return url


def _is_placeholder_url(url: str) -> bool:
    low = (url or "").lower()
    return (
        not low
        or "yourdomain.com" in low
        or "your-domain" in low
        or "example.com" in low
        or "paste" in low
        or "replace" in low
    )


def _blocked_host_reason(hostname: str) -> str:
    host = (hostname or "").strip().strip("[]").lower()
    if not host:
        return "missing host"
    if host in {"localhost", "ip6-localhost", "ip6-loopback"}:
        return "localhost is not allowed"
    if host.endswith((".localhost", ".local", ".internal", ".lan", ".home")):
        return "local/internal hostnames are not allowed"
    if host in {"metadata.google.internal"}:
        return "cloud metadata hosts are not allowed"

    try:
        ip = ipaddress.ip_address(host)
        candidates = [ip]
    except ValueError:
        candidates = []
        try:
            for info in socket.getaddrinfo(host, None):
                candidates.append(ipaddress.ip_address(info[4][0]))
        except Exception:
            candidates = []

    for ip in candidates:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return f"blocked internal address {ip}"
        if str(ip) == "169.254.169.254":
            return "cloud metadata address is not allowed"
    return ""


def _validate_base_url(url: str) -> str:
    normalized = _normalize_base_url(url)
    if not normalized or _is_placeholder_url(normalized):
        return ""
    parsed = urlparse(normalized)
    if parsed.scheme not in {"https", "http"}:
        raise RuntimeError("BYO AI base URL must use http or https.")
    reason = _blocked_host_reason(parsed.hostname or "")
    if reason:
        raise RuntimeError(f"BYO AI base URL is not allowed: {reason}.")
    return normalized


def _openai_default_model() -> str:
    return _secret("ERRORSWEEP_OPENAI_DEFAULT_MODEL", _secret("OPENAI_MODEL", "gpt-4o-mini"))


def _managed_model() -> str:
    return _secret("ERRORSWEEP_MANAGED_AI_MODEL", "errorsweep-managed")


def platform_openai_route() -> Optional[AIRoute]:
    platform_key = _secret("OPENAI_API_KEY", "").strip()
    if not platform_key:
        return None
    return AIRoute(
        provider="openai_platform",
        model=_openai_default_model(),
        api_key=platform_key,
        base_url=None,
        managed=True,
    )


def _user_provider_label() -> str:
    return _session_value("byo_ai_provider", "Custom OpenAI-compatible").strip() or "Custom OpenAI-compatible"


def select_ai_route(user_openai_key: str = "", purpose: str = "translate") -> AIRoute:
    user_key = (user_openai_key or _session_value("byo_openai_api_key", "")).strip()
    if user_key:
        base_url = _validate_base_url(_session_value("byo_ai_base_url", ""))
        return AIRoute(
            provider=f"user_api:{_user_provider_label()}",
            model=_session_value("byo_openai_model", _openai_default_model()),
            api_key=user_key,
            base_url=base_url or None,
            managed=False,
        )

    managed_enabled = _as_bool(_secret("ERRORSWEEP_MANAGED_AI_ENABLED", "false"), default=False)
    try:
        managed_base_url = _validate_base_url(_secret("ERRORSWEEP_MANAGED_AI_BASE_URL", ""))
    except RuntimeError:
        managed_base_url = ""

    if managed_enabled and managed_base_url:
        return AIRoute(
            provider="managed_vllm",
            model=_managed_model(),
            api_key=_secret("ERRORSWEEP_MANAGED_AI_API_KEY", "errorsweep-managed-token"),
            base_url=managed_base_url,
            managed=True,
        )

    route = platform_openai_route()
    if route:
        return route

    raise RuntimeError(
        "No AI route available. Add OPENAI_API_KEY in Streamlit Secrets, or configure a live Managed AI endpoint."
    )


def get_ai_client(route: AIRoute) -> OpenAI:
    if route.base_url:
        return OpenAI(api_key=route.api_key, base_url=route.base_url, timeout=120, max_retries=1)
    return OpenAI(api_key=route.api_key, timeout=120, max_retries=1)


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"items": data}
    except Exception:
        pass

    return {"items": []}


def _chat_json_items_once(
    route: AIRoute,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    client = get_ai_client(route)
    usage_info = {
        "provider": route.provider,
        "model": route.model,
        "managed": route.managed,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "success": False,
        "error": "",
    }

    try:
        response = client.chat.completions.create(
            model=route.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        data = _extract_json_object(content)

        usage = getattr(response, "usage", None)
        if usage:
            usage_info["input_tokens"] = int(getattr(usage, "prompt_tokens", 0) or 0)
            usage_info["output_tokens"] = int(getattr(usage, "completion_tokens", 0) or 0)
            usage_info["total_tokens"] = int(getattr(usage, "total_tokens", 0) or 0)

        usage_info["success"] = True
        return data.get("items", []), usage_info

    except Exception as exc:
        usage_info["error"] = str(exc)[:700]
        return [], usage_info


def ai_json_items(
    system_prompt: str,
    user_prompt: str,
    route: Optional[AIRoute] = None,
    user_openai_key: str = "",
    temperature: float = 0.0,
    max_tokens: int = 3000,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    try:
        route = route or select_ai_route(user_openai_key=user_openai_key)
    except Exception as exc:
        return [], {
            "provider": "none",
            "model": "",
            "managed": False,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "success": False,
            "error": str(exc)[:700],
        }

    items, usage = _chat_json_items_once(route, system_prompt, user_prompt, temperature, max_tokens)

    if not items and not usage.get("success") and route.provider == "managed_vllm":
        fallback = platform_openai_route()
        if fallback:
            fallback_items, fallback_usage = _chat_json_items_once(
                fallback, system_prompt, user_prompt, temperature, max_tokens
            )
            fallback_usage["error"] = (
                "Managed AI route failed, used platform OpenAI fallback. "
                f"Managed error: {usage.get('error', '')[:350]}"
            )
            return fallback_items, fallback_usage

    return items, usage


if __name__ == "__main__":
    selected = select_ai_route()
    print("Provider:", selected.provider)
    print("Model:", selected.model)
    print("Base URL:", selected.base_url)
