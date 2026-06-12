"""
managed_ai_router.py — ErrorSweep Managed AI safe fallback router

What this file does:
1. If the user added their own API key, use that key with the selected provider/base URL.
2. If Managed AI/vLLM is explicitly enabled and reachable, use it.
3. If Managed AI fails or is not configured, fall back to the platform OpenAI key when available.

This prevents the app from showing 59/59 untranslated rows when a placeholder or dead
Managed AI endpoint is configured.
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
from html import escape as _html_escape
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlsplit, urlunsplit

try:
    import streamlit as st
except Exception:
    st = None


_PUBLIC_ES_PAGES = {"landing", "login", "signup", "verify", "reset", "terms", "privacy", "security", "cookies", "dpa", "sso handoff", "billing success", "billing cancel"}
_PROTECTED_LINK_KEYS = {"es_page", "es_editor", "job_id", "review_id", "task_id"}
_SESSION_COOKIE_NAME = "errorsweep_session"
_SESSION_STORAGE_KEY = "errorsweep_session"
_SESSION_PERSISTENCE_SECONDS = 60 * 60 * 24 * 365 * 10
_JOB_EDITOR_DETAILS_PATCHED = False


def _install_signup_scroll_fix() -> None:
    """Enable vertical scrolling only on the public signup page."""
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
        body:has(#errorsweep-signup-scroll-marker) .block-container::-webkit-scrollbar {
          width: 11px;
        }
        body:has(#errorsweep-signup-scroll-marker) [data-testid="stMainBlockContainer"]::-webkit-scrollbar-track,
        body:has(#errorsweep-signup-scroll-marker) .block-container::-webkit-scrollbar-track {
          background: rgba(5, 7, 19, .82);
        }
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
                page = str(st.query_params.get("es_page", "") or "").strip().lower()
                public = str(st.query_params.get("public", "") or st.query_params.get("route", "") or "").strip().lower()
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


def _compact_page(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("+", " ").replace("_", " ").replace("-", " ").strip().lower())


def _href_needs_session(href: str) -> bool:
    if not href or href.startswith("#") or href.lower().startswith(("mailto:", "tel:", "javascript:")):
        return False
    try:
        split = urlsplit(href)
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        page = _compact_page(query.get("es_page", ""))
        if page and page in _PUBLIC_ES_PAGES:
            return False
        return any(query.get(key) for key in _PROTECTED_LINK_KEYS) and bool(page or query.get("es_editor") or query.get("job_id") or query.get("review_id") or query.get("task_id"))
    except Exception:
        return False


def _append_session_to_href(href: str, token: str) -> str:
    if not token or not _href_needs_session(href):
        return href
    try:
        split = urlsplit(href)
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        query["es_session"] = token
        return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))
    except Exception:
        return href


def _rewrite_protected_links(markup: Any, token: str) -> Any:
    if not token:
        return markup
    text = str(markup)
    if "href=" not in text:
        return markup

    def replace_href(match: re.Match[str]) -> str:
        quote_char = match.group(1)
        href = match.group(2)
        return f"href={quote_char}{_append_session_to_href(href, token)}{quote_char}"

    return re.sub(r'href\s*=\s*([\"\'])(.*?)\1', replace_href, text, flags=re.I)


def _current_signed_session_token() -> str:
    if st is None:
        return ""
    try:
        for key in ("_pending_session_cookie", "_post_login_session_token"):
            value = str(st.session_state.get(key, "") or "")
            if value:
                return value
        user = st.session_state.get("user") or {}
        if not user:
            return ""
        signer = getattr(sys.modules.get("__main__"), "signed_session_token_for_user", None)
        if callable(signer):
            token = str(signer(user) or "")
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
          doc.cookie = cookieName + "=" + encodeURIComponent(token) + "; Max-Age={_SESSION_PERSISTENCE_SECONDS}; Path=/; SameSite=Lax" + secure;
        }} catch (err) {{}}
        try {{ parentWindow.localStorage.setItem(storageKey, token); }} catch (err) {{}}
        const url = new URL(parentWindow.location.href);
        const page = String(url.searchParams.get("es_page") || "").replace(/[+_-]/g, " ").replace(/\s+/g, " ").trim().toLowerCase();
        const protectedTarget = Boolean(url.searchParams.get("es_editor") || url.searchParams.get("job_id") || url.searchParams.get("review_id") || url.searchParams.get("task_id") || (page && !publicPages.includes(page)));
        if (protectedTarget && url.searchParams.get("es_session") !== token) {{
          url.searchParams.set("es_session", token);
          parentWindow.history.replaceState(null, "", url.toString());
        }}
      }} catch (err) {{}}
    }})();
    </script>
    """


def _json_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\u00A0", " ").strip()


def _main_module() -> Any:
    return sys.modules.get("__main__")


def _format_time(value: Any) -> str:
    module = _main_module()
    formatter = getattr(module, "format_local_time", None)
    if callable(formatter):
        try:
            return _text(formatter(value))
        except Exception:
            pass
    return _text(value)


def _task_review_id(task: Dict[str, Any]) -> str:
    module = _main_module()
    task_review_job_id = getattr(module, "task_review_job_id", None)
    if callable(task_review_job_id):
        try:
            value = _text(task_review_job_id(task))
            if value:
                return value
        except Exception:
            pass
    metadata = _json_dict(task.get("metadata_json"))
    pro_summary = metadata.get("pro_summary") if isinstance(metadata.get("pro_summary"), dict) else {}
    return _text(
        metadata.get("review_job_id")
        or pro_summary.get("review_job_id")
        or task.get("review_job_id")
        or task.get("active_review_session_id")
        or ""
    )


def _task_editor_target(task: Dict[str, Any]) -> Tuple[str, str]:
    module = _main_module()
    review_id = _task_review_id(task)
    if review_id:
        human_review_editor_link = getattr(module, "human_review_editor_link", None)
        if callable(human_review_editor_link):
            try:
                return _text(human_review_editor_link(review_id)), "Open this job in Human Review Editor"
            except Exception:
                pass
        return "?" + urlencode({"es_page": "Human Review Editor", "review_id": review_id}), "Open this job in Human Review Editor"

    metadata = _json_dict(task.get("metadata_json"))
    job_id = _text(
        metadata.get("editor_job_id")
        or metadata.get("cat_job_id")
        or metadata.get("media_job_id")
        or metadata.get("job_id")
        or task.get("editor_job_id")
        or task.get("job_id")
        or ""
    )
    task_type = _text(task.get("task_type") or metadata.get("task_type") or metadata.get("job_type")).lower()
    if job_id:
        editor_type = _text(metadata.get("editor_type") or metadata.get("job_type") or ("media" if any(part in task_type for part in ("subtitle", "transcription", "media")) else "cat")) or "cat"
        external_editor_url = getattr(module, "external_editor_url", None)
        if callable(external_editor_url):
            try:
                return _text(external_editor_url(editor_type, job_id)), "Open this job in Editor"
            except Exception:
                pass
        return "?" + urlencode({"es_editor": editor_type, "job_id": job_id}), "Open this job in Editor"
    return "", ""


def _task_detail_pairs(task: Dict[str, Any]) -> List[Tuple[str, str]]:
    metadata = _json_dict(task.get("metadata_json"))
    label = _text(task.get("label") or task.get("type") or task.get("task_type") or "Job")
    workflow = _text(task.get("task_type") or metadata.get("workflow") or metadata.get("source") or "workflow")
    status = _text(task.get("status") or metadata.get("status") or "created")
    progress = _text(task.get("progress"))
    processed = _text(task.get("processed_units"))
    total = _text(task.get("total_units") or metadata.get("segments") or metadata.get("row_count"))
    file_name = _text(metadata.get("file_name") or task.get("file_name"))
    language = _text(metadata.get("target_language") or task.get("language") or metadata.get("language"))
    created = _format_time(task.get("created_at") or task.get("created") or metadata.get("created"))
    updated = _format_time(task.get("updated_at") or metadata.get("updated_at"))
    review_id = _task_review_id(task)
    pairs = [
        ("Job", label),
        ("Workflow", workflow),
        ("Status", status),
    ]
    if progress:
        pairs.append(("Progress", f"{progress}%" if progress.isdigit() else progress))
    if processed or total:
        pairs.append(("Units", f"{processed or 0}/{total or 0}"))
    if file_name:
        pairs.append(("File", file_name))
    if language:
        pairs.append(("Language", language))
    if created:
        pairs.append(("Created", created))
    if updated:
        pairs.append(("Updated", updated))
    task_id = _text(task.get("id"))
    if task_id:
        pairs.append(("Task ID", task_id[:12]))
    if review_id:
        pairs.append(("Editor ID", review_id[:12]))
    return pairs


def _render_job_editor_details(task: Dict[str, Any], key_prefix: str = "job") -> None:
    if st is None or not isinstance(task, dict):
        return
    try:
        url, action_label = _task_editor_target(task)
        detail_html = "".join(
            f'<span style="display:inline-flex;flex-direction:column;gap:2px;min-width:120px;padding:8px 10px;border:1px solid rgba(84,105,180,.22);border-radius:10px;background:rgba(9,14,28,.54);"><b style="color:#75f7c4;font-size:10px;text-transform:uppercase;letter-spacing:.08em;">{_html_escape(label)}</b><span style="color:#dce8ff;font-size:12px;line-height:1.35;">{_html_escape(value)}</span></span>'
            for label, value in _task_detail_pairs(task)
            if value
        )
        if not detail_html:
            return
        if url:
            safe_url = _html_escape(_append_session_to_href(url, _current_signed_session_token()))
            action_html = f'<a class="es-task-action-link primary" href="{safe_url}" target="_blank" rel="noopener" style="width:100%;min-height:42px;margin-top:10px;">{_html_escape(action_label)} ↗</a>'
        else:
            action_html = '<div class="es-small" style="margin-top:10px;color:#9fb0db;">Editor opens here automatically after this job creates a Human Review or editor session.</div>'
        st.markdown(
            f'''
            <div class="es-row-card" style="margin-top:10px;border-color:rgba(52,189,246,.28);">
              <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px;">
                <div>
                  <div class="es-code-chip">JOB DETAILS</div>
                  <div style="font-weight:900;color:#f8fbff;margin-top:6px;">Editor-ready job handoff</div>
                </div>
              </div>
              <div style="display:flex;gap:8px;flex-wrap:wrap;">{detail_html}</div>
              {action_html}
            </div>
            ''',
            unsafe_allow_html=True,
        )
    except Exception:
        pass


def _install_job_editor_details_patch() -> None:
    global _JOB_EDITOR_DETAILS_PATCHED
    if _JOB_EDITOR_DETAILS_PATCHED:
        return
    module = _main_module()
    original = getattr(module, "render_task_result_actions", None)
    if not callable(original) or getattr(original, "_errorsweep_job_editor_details_patch", False):
        return

    @functools.wraps(original)
    def render_task_result_actions_with_editor(task: Dict[str, Any], key_prefix: str) -> None:
        original(task, key_prefix)
        _render_job_editor_details(task, key_prefix)

    setattr(render_task_result_actions_with_editor, "_errorsweep_job_editor_details_patch", True)
    setattr(module, "render_task_result_actions", render_task_result_actions_with_editor)
    _JOB_EDITOR_DETAILS_PATCHED = True


def _install_authenticated_reload_bridge() -> None:
    """Keep session token on protected links/current URL so reloads do not blank."""
    if st is None:
        return
    try:
        original_markdown = getattr(st, "markdown", None)
        if not callable(original_markdown) or getattr(original_markdown, "_errorsweep_authenticated_reload_bridge", False):
            return

        @functools.wraps(original_markdown)
        def markdown_with_authenticated_reload(body: Any, *args: Any, **kwargs: Any) -> Any:
            _install_job_editor_details_patch()
            token = _current_signed_session_token()
            text = str(body)
            is_shell_or_nav = "errorsweep-root-shell-marker" in text or "es-topnav" in text or "es-owner-strip" in text or "es-account-menu" in text
            patched_body = _rewrite_protected_links(body, token) if token and "href=" in text else body
            result = original_markdown(patched_body, *args, **kwargs)
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
    """Keep the login page open while launching the authenticated app tab."""
    if st is None:
        return
    try:
        original_rerun = getattr(st, "rerun", None)
        if not callable(original_rerun) or getattr(original_rerun, "_errorsweep_login_new_tab_bridge", False):
            return

        def _query_value(key: str) -> str:
            try:
                value = st.query_params.get(key, "")
                if isinstance(value, list):
                    return str(value[0] if value else "")
                return str(value or "")
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
                page = str(current_route.get("es_page") or current_route.get("page") or "").strip()
                if page:
                    params["es_page"] = page
                for key in ("es_editor", "job_id", "review_id", "task_id"):
                    value = str(current_route.get(key) or "").strip()
                    if value:
                        params[key] = value
            for key in ("es_page", "es_editor", "job_id", "review_id", "task_id"):
                value = _query_value(key).strip()
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
                if _called_from_login_flow() and st.session_state.get("authenticated") and st.session_state.get("user"):
                    session_token = _current_signed_session_token()
                    if session_token:
                        st.session_state["_post_login_tool_launch_url"] = _build_launch_url(session_token)
                        st.session_state["_post_login_session_token"] = session_token
                        st.session_state["_post_login_tool_launch_id"] = uuid.uuid4().hex
                        st.session_state["_login_window_stay_open"] = True
                        _leave_current_tab_on_login()
                        main_module = sys.modules.get("__main__")
                        render_bridge = getattr(main_module, "render_post_login_tool_launch_bridge", None)
                        if callable(render_bridge):
                            render_bridge()
                            st.stop()
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
    """Choose the first route to try.

    Safe default:
    - BYO user key always wins. It can point to OpenAI or any OpenAI-compatible chat-completions API.
    - Managed AI/vLLM is used only when ERRORSWEEP_MANAGED_AI_ENABLED=true
      and the URL is not a placeholder.
    - Otherwise use platform OPENAI_API_KEY.
    """
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
    """One function for OpenAI BYO, Managed vLLM, and platform OpenAI fallback.

    If Managed AI is selected but connection fails, this function automatically
    tries OPENAI_API_KEY as a fallback. This keeps translations working while the
    Managed AI server is not yet live.
    """
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

    # Safe fallback: Managed AI/vLLM failed, but platform OpenAI key is available.
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
