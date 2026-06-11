"""Invisible ErrorSweep runtime compatibility fixes.

No UI is rendered here. This file only normalizes malformed protected-route query
parameters, keeps editor links usable in new tabs, and ensures the configured
main owner receives platform-owner unlimited access.
"""
from __future__ import annotations

import builtins
import functools
import json
import logging
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

LOGGER = logging.getLogger(__name__)
_ORIGINAL_IMPORT = builtins.__import__
_STREAMLIT_PATCHED = False
_APP_FUNCTIONS_PATCHED = False

SESSION_COOKIE_NAME = "errorsweep_session"
SESSION_STORAGE_KEY = "errorsweep_session"
SESSION_PERSISTENCE_SECONDS = 60 * 60 * 24 * 365 * 10
PUBLIC_ES_PAGES = {"landing", "login", "signup", "terms", "privacy", "security", "cookies", "dpa"}
ROUTE_PARAM_KEYS = {"es_page", "es_editor", "job_id", "review_id", "es_session", "es_restore", "tool_tab", "task_id"}
EDITOR_HREF_MARKERS = ("es_editor=", "job_id=", "review_id=", "Human+Review+Editor", "Human%20Review%20Editor")

MAIN_PLATFORM_OWNER_EMAIL = "adapalanaveen401@gmail.com"
PLATFORM_WORKSPACE = "Platform"
LEGACY_UNLIMITED_WORKSPACE = "Naveen Unlimited Workspace"
UNLIMITED_SEATS = 1_000_000
UNLIMITED_SEGMENTS = 1_000_000_000
UNLIMITED_CHARACTERS = 1_000_000_000_000
UNLIMITED_WORKSPACE_KEYS = {PLATFORM_WORKSPACE.lower(), LEGACY_UNLIMITED_WORKSPACE.lower()}


def _main_module() -> Any:
    return sys.modules.get("__main__")


def _streamlit_module() -> Any:
    return sys.modules.get("streamlit")


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _query_value(value: Any) -> str:
    if isinstance(value, list):
        return _safe_text(value[0] if value else "")
    return _safe_text(value)


def _clean_query_key(key: str) -> str:
    cleaned = _safe_text(key).strip()
    cleaned = cleaned.replace("%3B", ";").replace("%3b", ";")
    while cleaned.startswith((";", "&", "?")):
        cleaned = cleaned[1:]
    if cleaned.startswith("amp;"):
        cleaned = cleaned[4:]
    if ";" in cleaned:
        tail = cleaned.split(";")[-1]
        if tail in ROUTE_PARAM_KEYS:
            cleaned = tail
    return cleaned


def _normalize_query_params() -> None:
    """Repair malformed query keys such as `%3Breview_id` -> `review_id`.

    The current blank editor screen was caused by a URL like:
    `?es_page=Human+Review+Editor&%3Breview_id=<id>`. Streamlit decodes that as
    a key named `;review_id`, so app.py cannot find `review_id`. Normalize it
    before the router reads the parameters.
    """
    st = _streamlit_module()
    if st is None:
        return
    try:
        params = st.query_params
        for raw_key in list(params.keys()):
            clean_key = _clean_query_key(raw_key)
            if clean_key != raw_key and clean_key in ROUTE_PARAM_KEYS:
                value = _query_value(params.get(raw_key, ""))
                if value and not _query_value(params.get(clean_key, "")):
                    params[clean_key] = value
                try:
                    del params[raw_key]
                except Exception:
                    pass

        # Also handle a fully embedded value such as
        # es_page=Human Review Editor;review_id=<id>.
        es_page = _query_value(params.get("es_page", ""))
        embedded = re.search(r"(?:^|[;&])review_id=([^&;]+)", es_page)
        if embedded and not _query_value(params.get("review_id", "")):
            params["review_id"] = embedded.group(1)
            params["es_page"] = re.split(r"[;&]review_id=", es_page, 1)[0].strip() or "Human Review Editor"

        # If any unknown key ends with review_id/job_id/es_editor, copy it to the
        # canonical key instead of letting the route render as blank/error.
        for raw_key in list(params.keys()):
            value = _query_value(params.get(raw_key, ""))
            low = _safe_text(raw_key).lower()
            for canonical in ("review_id", "job_id", "es_editor"):
                if low.endswith(canonical) and value and not _query_value(params.get(canonical, "")):
                    params[canonical] = value
    except Exception:
        LOGGER.debug("Unable to normalize ErrorSweep query params", exc_info=True)


def _current_user() -> Dict[str, Any]:
    st = _streamlit_module()
    if st is None:
        return {}
    try:
        user = st.session_state.get("user") or {}
        return user if isinstance(user, dict) else {}
    except Exception:
        return {}


def _is_main_owner_user(user: Optional[Dict[str, Any]] = None) -> bool:
    candidate = user if isinstance(user, dict) else _current_user()
    email = _safe_text(candidate.get("email")).strip().lower()
    role = _safe_text(candidate.get("role")).strip()
    account_type = _safe_text(candidate.get("account_type")).strip().lower()
    return email == MAIN_PLATFORM_OWNER_EMAIL or role == "Platform Owner" or account_type == "owner"


def _unlimited_subscription(workspace: str = PLATFORM_WORKSPACE) -> Dict[str, Any]:
    workspace = _safe_text(workspace).strip() or PLATFORM_WORKSPACE
    return {
        "workspace": workspace,
        "user_email": MAIN_PLATFORM_OWNER_EMAIL,
        "plan": "Unlimited",
        "status": "Active",
        "billing_cycle": "internal",
        "currency": "INR",
        "base_amount": 0,
        "included_segments": UNLIMITED_SEGMENTS,
        "included_characters": UNLIMITED_CHARACTERS,
        "included_seats": UNLIMITED_SEATS,
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
        "seats": UNLIMITED_SEATS,
        "segments": UNLIMITED_SEGMENTS,
        "characters": UNLIMITED_CHARACTERS,
        "label": "Unlimited internal access",
        "description": "Unlimited platform-owner access.",
    }


def _replace_or_insert_record(rows: List[Dict[str, Any]], matcher: Callable[[Dict[str, Any]], bool], record: Dict[str, Any]) -> None:
    for index, item in enumerate(list(rows)):
        if isinstance(item, dict) and matcher(item):
            rows[index] = {**item, **record}
            return
    rows.insert(0, record)


def _ensure_owner_entitlements() -> None:
    st = _streamlit_module()
    if st is None:
        return
    try:
        user = st.session_state.get("user")
        if not isinstance(user, dict):
            return
        email = _safe_text(user.get("email")).strip().lower()
        if email != MAIN_PLATFORM_OWNER_EMAIL:
            return
        user.update({
            "email": MAIN_PLATFORM_OWNER_EMAIL,
            "role": "Platform Owner",
            "account_type": "owner",
            "workspace": PLATFORM_WORKSPACE,
            "plan": "Unlimited",
            "status": "Active",
            "email_verified": True,
        })
        st.session_state["user"] = user
        st.session_state["authenticated"] = True

        users = st.session_state.setdefault("users", [])
        _replace_or_insert_record(
            users,
            lambda item: _safe_text(item.get("email")).strip().lower() == MAIN_PLATFORM_OWNER_EMAIL,
            {
                "email": MAIN_PLATFORM_OWNER_EMAIL,
                "workspace": PLATFORM_WORKSPACE,
                "role": "Platform Owner",
                "account_type": "owner",
                "plan": "Unlimited",
                "status": "Active",
                "email_verified": True,
            },
        )
        workspaces = st.session_state.setdefault("workspaces", [])
        subscriptions = st.session_state.setdefault("subscriptions", [])
        for workspace_name in (PLATFORM_WORKSPACE, LEGACY_UNLIMITED_WORKSPACE):
            _replace_or_insert_record(
                workspaces,
                lambda item, workspace_name=workspace_name: _safe_text(item.get("workspace")).strip().lower() == workspace_name.lower(),
                {
                    "workspace": workspace_name,
                    "owner": MAIN_PLATFORM_OWNER_EMAIL,
                    "plan": "Unlimited",
                    "status": "Active",
                    "users": 1,
                    "jobs": 0,
                },
            )
            _replace_or_insert_record(
                subscriptions,
                lambda item, workspace_name=workspace_name: _safe_text(item.get("workspace")).strip().lower() == workspace_name.lower(),
                _unlimited_subscription(workspace_name),
            )
    except Exception:
        LOGGER.debug("Unable to ensure ErrorSweep owner entitlements", exc_info=True)


def _patch_app_functions() -> None:
    global _APP_FUNCTIONS_PATCHED
    if _APP_FUNCTIONS_PATCHED:
        return
    module = _main_module()
    if module is None:
        return
    required = [
        "workspace_subscription",
        "workspace_usage_allowance",
        "workspace_seat_state",
        "check_workspace_usage_allowance",
        "check_workspace_seat_allowance",
        "current_role",
        "is_owner",
    ]
    if not all(callable(getattr(module, name, None)) for name in required):
        return

    original_workspace_subscription = getattr(module, "workspace_subscription")
    original_workspace_usage_allowance = getattr(module, "workspace_usage_allowance")
    original_workspace_seat_state = getattr(module, "workspace_seat_state")
    original_check_workspace_usage_allowance = getattr(module, "check_workspace_usage_allowance")
    original_check_workspace_seat_allowance = getattr(module, "check_workspace_seat_allowance")
    original_current_role = getattr(module, "current_role")
    original_is_owner = getattr(module, "is_owner")

    def _is_unlimited_context(workspace: str = "") -> bool:
        _ensure_owner_entitlements()
        workspace_key = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "")).strip().lower()
        return _is_main_owner_user() or workspace_key in UNLIMITED_WORKSPACE_KEYS

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
    def workspace_subscription_with_unlimited_owner(workspace: str = "") -> Dict[str, Any]:
        _ensure_owner_entitlements()
        workspace_name = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "") or PLATFORM_WORKSPACE)
        if _is_unlimited_context(workspace_name):
            return _unlimited_subscription(workspace_name or PLATFORM_WORKSPACE)
        return original_workspace_subscription(workspace)

    @functools.wraps(original_workspace_usage_allowance)
    def workspace_usage_allowance_with_unlimited_owner(workspace: str = "") -> Dict[str, Any]:
        _ensure_owner_entitlements()
        workspace_name = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "") or PLATFORM_WORKSPACE)
        if _is_unlimited_context(workspace_name):
            return {
                "subscription": _unlimited_subscription(workspace_name or PLATFORM_WORKSPACE),
                "plan": _unlimited_plan(),
                "segments": UNLIMITED_SEGMENTS,
                "characters": UNLIMITED_CHARACTERS,
                "seats": UNLIMITED_SEATS,
            }
        return original_workspace_usage_allowance(workspace)

    @functools.wraps(original_workspace_seat_state)
    def workspace_seat_state_with_unlimited_owner(workspace: str = "") -> Dict[str, Any]:
        _ensure_owner_entitlements()
        workspace_name = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "") or PLATFORM_WORKSPACE)
        if _is_unlimited_context(workspace_name):
            return {
                "workspace": workspace_name or PLATFORM_WORKSPACE,
                "subscription": _unlimited_subscription(workspace_name or PLATFORM_WORKSPACE),
                "plan": _unlimited_plan(),
                "used": 1,
                "limit": UNLIMITED_SEATS,
                "available": UNLIMITED_SEATS - 1,
            }
        return original_workspace_seat_state(workspace)

    @functools.wraps(original_check_workspace_usage_allowance)
    def check_workspace_usage_allowance_with_unlimited_owner(rows: List[Dict[str, Any]], purpose: str, workspace: str = ""):
        _ensure_owner_entitlements()
        workspace_name = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "") or PLATFORM_WORKSPACE)
        if _is_unlimited_context(workspace_name):
            requested_segments = len(rows or [])
            requested_characters = sum(
                len(_safe_text(row.get("source", ""))) + len(_safe_text(row.get("target", "")))
                for row in (rows or [])
                if isinstance(row, dict)
            )
            return True, "", {
                "workspace": workspace_name or PLATFORM_WORKSPACE,
                "plan": "Unlimited",
                "status": "active",
                "used_segments": 0,
                "used_characters": 0,
                "requested_segments": requested_segments,
                "requested_characters": requested_characters,
                "projected_segments": requested_segments,
                "projected_characters": requested_characters,
                "segment_limit": UNLIMITED_SEGMENTS,
                "character_limit": UNLIMITED_CHARACTERS,
                "unlimited": True,
            }
        return original_check_workspace_usage_allowance(rows, purpose, workspace)

    @functools.wraps(original_check_workspace_seat_allowance)
    def check_workspace_seat_allowance_with_unlimited_owner(workspace: str, email: str, status: str = "Active"):
        _ensure_owner_entitlements()
        workspace_name = _safe_text(workspace or (_current_user().get("workspace") if _current_user() else "") or PLATFORM_WORKSPACE)
        if _is_unlimited_context(workspace_name):
            return True, "", workspace_seat_state_with_unlimited_owner(workspace_name)
        return original_check_workspace_seat_allowance(workspace, email, status)

    setattr(module, "current_role", current_role_with_main_owner)
    setattr(module, "is_owner", is_owner_with_main_owner)
    setattr(module, "workspace_subscription", workspace_subscription_with_unlimited_owner)
    setattr(module, "workspace_usage_allowance", workspace_usage_allowance_with_unlimited_owner)
    setattr(module, "workspace_seat_state", workspace_seat_state_with_unlimited_owner)
    setattr(module, "check_workspace_usage_allowance", check_workspace_usage_allowance_with_unlimited_owner)
    setattr(module, "check_workspace_seat_allowance", check_workspace_seat_allowance_with_unlimited_owner)
    _APP_FUNCTIONS_PATCHED = True


def _current_session_token() -> str:
    st = _streamlit_module()
    if st is None:
        return ""
    try:
        pending = _safe_text(st.session_state.get("_pending_session_cookie", ""))
        if pending:
            return pending
    except Exception:
        pass
    user = _current_user()
    if not user:
        return ""
    signer = getattr(_main_module(), "signed_session_token_for_user", None)
    if callable(signer):
        try:
            return _safe_text(signer(user))
        except Exception:
            LOGGER.debug("Unable to sign ErrorSweep session token", exc_info=True)
    return ""


def _append_query(url: str, **updates: str) -> str:
    if not url or url.startswith("#") or url.lower().startswith(("mailto:", "tel:", "javascript:")):
        return url
    try:
        split = urlsplit(url)
        pairs = dict(parse_qsl(split.query, keep_blank_values=True))
        clean_pairs: Dict[str, str] = {}
        for key, value in pairs.items():
            clean_key = _clean_query_key(key)
            clean_pairs[clean_key] = value
        for key, value in updates.items():
            if value:
                clean_pairs[key] = value
        return urlunsplit((split.scheme, split.netloc, split.path, urlencode(clean_pairs), split.fragment))
    except Exception:
        return url


def _is_editor_href(href: str) -> bool:
    return any(marker in href for marker in EDITOR_HREF_MARKERS)


def _is_editor_markup(text: str) -> bool:
    return "<a" in text and "href=" in text and any(marker in text for marker in EDITOR_HREF_MARKERS)


def _rewrite_anchor_hrefs(markup: Any, *, editor_only: bool = False, keep_editor_new_tab: bool = True) -> Any:
    text = str(markup)
    token = _current_session_token()
    if not token or "<a" not in text or "href=" not in text:
        return markup

    def replace_href(match: re.Match[str]) -> str:
        quote_char = match.group(1)
        href = match.group(2)
        is_editor = _is_editor_href(href)
        if editor_only and not is_editor:
            return match.group(0)
        if "es_logout=1" in href:
            return match.group(0)
        new_href = _append_query(href, es_session=token)
        return f'href={quote_char}{new_href}{quote_char}'

    text = re.sub(r'href\s*=\s*([\"\'])(.*?)\1', replace_href, text, flags=re.I)
    if keep_editor_new_tab and _is_editor_markup(text):
        if re.search(r'target\s*=\s*([\"\'])_self\1', text, flags=re.I):
            text = re.sub(r'target\s*=\s*([\"\'])_self\1', 'target="_blank"', text, flags=re.I)
        elif "target=" not in text:
            text = re.sub(r'(<a\b)', r'\1 target="_blank" rel="noopener"', text, count=1, flags=re.I)
    return text


def _session_bootstrap_script(*, enable_tool_tab: bool = False) -> str:
    token = _current_session_token()
    if not token:
        return ""
    token_json = json.dumps(token)
    open_tool_json = json.dumps(bool(enable_tool_tab))
    cookie_name_json = json.dumps(SESSION_COOKIE_NAME)
    storage_key_json = json.dumps(SESSION_STORAGE_KEY)
    public_pages_json = json.dumps(sorted(PUBLIC_ES_PAGES))
    return f"""
<script>
(() => {{
  try {{
    const parentWindow = window.parent || window;
    const doc = parentWindow.document;
    const token = {token_json};
    const cookieName = {cookie_name_json};
    const storageKey = {storage_key_json};
    const publicPages = {public_pages_json};
    const secure = parentWindow.location.protocol === "https:" ? "; Secure" : "";
    try {{
      doc.cookie = cookieName + "=" + encodeURIComponent(token) + "; Max-Age={SESSION_PERSISTENCE_SECONDS}; Path=/; SameSite=Lax" + secure;
    }} catch (err) {{}}
    try {{ parentWindow.localStorage.setItem(storageKey, token); }} catch (err) {{}}

    try {{
      const current = new URL(parentWindow.location.href);
      const repairParam = (bad, good) => {{
        if (current.searchParams.has(bad) && !current.searchParams.has(good)) {{
          current.searchParams.set(good, current.searchParams.get(bad) || "");
          current.searchParams.delete(bad);
        }}
      }};
      repairParam(";review_id", "review_id");
      repairParam("amp;review_id", "review_id");
      repairParam(";job_id", "job_id");
      repairParam("amp;job_id", "job_id");
      repairParam(";es_editor", "es_editor");
      repairParam("amp;es_editor", "es_editor");
      const page = String(current.searchParams.get("es_page") || "").trim().toLowerCase();
      const protectedTarget = Boolean(
        current.searchParams.get("es_editor") ||
        current.searchParams.get("job_id") ||
        current.searchParams.get("review_id") ||
        (page && !publicPages.includes(page))
      );
      if (protectedTarget && current.searchParams.get("es_session") !== token) current.searchParams.set("es_session", token);
      if (current.href !== parentWindow.location.href) parentWindow.history.replaceState(null, "", current.toString());
    }} catch (err) {{}}

    const patchEditorLinks = () => {{
      try {{
        const selector = [
          'a[href*="es_editor="]',
          'a[href*="job_id="]',
          'a[href*="review_id="]',
          'a[href*="Human+Review+Editor"]',
          'a[href*="Human%20Review%20Editor"]'
        ].join(',');
        doc.querySelectorAll(selector).forEach((anchor) => {{
          const raw = String(anchor.getAttribute("href") || "");
          if (!raw || raw.includes("es_logout=1")) return;
          const url = new URL(raw, parentWindow.location.href);
          [";review_id", "amp;review_id"].forEach((bad) => {{
            if (url.searchParams.has(bad) && !url.searchParams.has("review_id")) {{
              url.searchParams.set("review_id", url.searchParams.get(bad) || "");
              url.searchParams.delete(bad);
            }}
          }});
          url.searchParams.set("es_session", token);
          anchor.setAttribute("href", url.pathname + url.search + url.hash);
          anchor.setAttribute("target", "_blank");
          anchor.setAttribute("rel", "noopener");
        }});
      }} catch (err) {{}}
    }};
    patchEditorLinks();
    try {{ new MutationObserver(patchEditorLinks).observe(doc.body, {{ childList: true, subtree: true }}); }} catch (err) {{}}

    if ({open_tool_json}) {{
      try {{
        const url = new URL(parentWindow.location.href);
        const isToolTab = url.searchParams.get("tool_tab") === "1";
        const alreadyOpened = parentWindow.sessionStorage.getItem("errorsweep_tool_tab_opened") === "1";
        if (!isToolTab && !alreadyOpened) {{
          parentWindow.sessionStorage.setItem("errorsweep_tool_tab_opened", "1");
          url.searchParams.set("tool_tab", "1");
          url.searchParams.set("es_session", token);
          parentWindow.open(url.toString(), "_blank", "noopener");
        }}
      }} catch (err) {{}}
    }}
  }} catch (err) {{}}
}})();
</script>
"""


def _patch_streamlit() -> None:
    global _STREAMLIT_PATCHED
    if _STREAMLIT_PATCHED:
        return
    st = _streamlit_module()
    if st is None:
        return
    original_markdown = getattr(st, "markdown", None)
    original_html = getattr(st, "html", None)
    if not callable(original_markdown):
        return

    @functools.wraps(original_markdown)
    def markdown_with_session_links(body: Any, *args: Any, **kwargs: Any) -> Any:
        _normalize_query_params()
        _ensure_owner_entitlements()
        _patch_app_functions()
        text = str(body)
        is_nav = '<nav class="es-topnav"' in text or "<nav class='es-topnav'" in text
        is_editor = _is_editor_markup(text)
        patched_body = _rewrite_anchor_hrefs(body, editor_only=not is_nav, keep_editor_new_tab=True) if (is_nav or is_editor) else body
        result = original_markdown(patched_body, *args, **kwargs)
        if is_nav or is_editor:
            try:
                import streamlit.components.v1 as components
                script = _session_bootstrap_script(enable_tool_tab=is_nav)
                if script:
                    components.html(script, height=0, scrolling=False)
            except Exception:
                pass
        return result

    setattr(markdown_with_session_links, "_errorsweep_session_links", True)
    st.markdown = markdown_with_session_links

    if callable(original_html):
        @functools.wraps(original_html)
        def html_with_session_links(body: Any, *args: Any, **kwargs: Any) -> Any:
            _normalize_query_params()
            _ensure_owner_entitlements()
            _patch_app_functions()
            return original_html(_rewrite_anchor_hrefs(body, editor_only=True, keep_editor_new_tab=True), *args, **kwargs)
        setattr(html_with_session_links, "_errorsweep_session_links", True)
        st.html = html_with_session_links

    _STREAMLIT_PATCHED = True


def _patch_all() -> None:
    _normalize_query_params()
    _patch_streamlit()
    _ensure_owner_entitlements()
    _patch_app_functions()


def _import_hook(name: str, globals: Any = None, locals: Any = None, fromlist: Tuple[Any, ...] = (), level: int = 0) -> Any:
    module = _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)
    if name == "streamlit" or name.startswith("streamlit."):
        _patch_all()
    return module


if not getattr(builtins, "_errorsweep_session_patch_installed", False):
    setattr(builtins, "_errorsweep_session_patch_installed", True)
    builtins.__import__ = _import_hook

_patch_all()
