"""ErrorSweep browser-session compatibility fixes.

This module is intentionally narrow and invisible: it does not replace the
existing UI. It only keeps the authenticated session available to browser tabs,
reloads, and editor launch links in Streamlit Cloud.
"""
from __future__ import annotations

import builtins
import functools
import json
import logging
import re
import sys
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

LOGGER = logging.getLogger(__name__)
_ORIGINAL_IMPORT = builtins.__import__
_STREAMLIT_PATCHED = False
_COMPONENTS_PATCHED = False

SESSION_COOKIE_NAME = "errorsweep_session"
SESSION_STORAGE_KEY = "errorsweep_session"
SESSION_PERSISTENCE_SECONDS = 60 * 60 * 24 * 365 * 10
PUBLIC_ES_PAGES = {"landing", "login", "signup", "terms", "privacy", "security", "cookies", "dpa"}
EDITOR_HREF_MARKERS = ("es_editor=", "review_id=", "Human+Review+Editor", "Human%20Review%20Editor")


def _main_module() -> Any:
    return sys.modules.get("__main__")


def _streamlit_module() -> Any:
    return sys.modules.get("streamlit")


def _current_user() -> dict[str, Any]:
    st = _streamlit_module()
    if st is None:
        return {}
    try:
        user = st.session_state.get("user") or {}
        return user if isinstance(user, dict) else {}
    except Exception:
        return {}


def _current_session_token() -> str:
    """Create a valid app session token using app.py's own signer."""
    st = _streamlit_module()
    if st is None:
        return ""
    try:
        pending = str(st.session_state.get("_pending_session_cookie", "") or "")
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
            return str(signer(user) or "")
        except Exception:
            LOGGER.debug("Unable to sign ErrorSweep session token", exc_info=True)
    return ""


def _append_query(url: str, **updates: str) -> str:
    if not url or url.startswith("#") or url.lower().startswith(("mailto:", "tel:", "javascript:")):
        return url
    try:
        split = urlsplit(url)
        pairs = dict(parse_qsl(split.query, keep_blank_values=True))
        for key, value in updates.items():
            if value:
                pairs[key] = value
        return urlunsplit((split.scheme, split.netloc, split.path, urlencode(pairs), split.fragment))
    except Exception:
        return url


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
        is_editor = any(marker in href for marker in EDITOR_HREF_MARKERS)
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
    return f"""
<script>
(() => {{
  try {{
    const parentWindow = window.parent || window;
    const doc = parentWindow.document;
    const token = {token_json};
    const cookieName = {cookie_name_json};
    const storageKey = {storage_key_json};
    const secure = parentWindow.location.protocol === "https:" ? "; Secure" : "";
    try {{
      doc.cookie = cookieName + "=" + encodeURIComponent(token) + "; Max-Age={SESSION_PERSISTENCE_SECONDS}; Path=/; SameSite=Lax" + secure;
    }} catch (err) {{}}
    try {{
      parentWindow.localStorage.setItem(storageKey, token);
    }} catch (err) {{}}

    const ensureSessionInUrl = () => {{
      try {{
        const url = new URL(parentWindow.location.href);
        const page = String(url.searchParams.get("es_page") || "").trim().toLowerCase();
        const hasProtectedTarget = Boolean(url.searchParams.get("es_editor") || url.searchParams.get("job_id") || url.searchParams.get("review_id") || (page && !{json.dumps(list(PUBLIC_ES_PAGES))}.includes(page)));
        if (hasProtectedTarget && url.searchParams.get("es_session") !== token) {{
          url.searchParams.set("es_session", token);
          parentWindow.history.replaceState(null, "", url.toString());
        }}
      }} catch (err) {{}}
    }};
    ensureSessionInUrl();

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


def _protected_restore_requested() -> bool:
    st = _streamlit_module()
    if st is None:
        return False
    try:
        params = st.query_params
        page = str(params.get("es_page", "") or "").strip().lower()
        if str(params.get("es_editor", "") or "") or str(params.get("job_id", "") or "") or str(params.get("review_id", "") or ""):
            return True
        return bool(page and page not in PUBLIC_ES_PAGES)
    except Exception:
        return False


def _restore_fallback_html() -> str:
    return """
<div style="box-sizing:border-box;min-height:138px;padding:24px;color:#f8fbff;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#070914;">
  <div style="max-width:700px;margin:0 auto;border:1px solid rgba(84,105,180,.34);border-radius:14px;padding:16px 18px;background:rgba(18,21,38,.86);">
    <div style="font-weight:900;font-size:17px;margin-bottom:6px;">Restoring ErrorSweep session…</div>
    <div style="color:#c2c9e9;font-size:14px;line-height:1.45;">If this does not continue automatically, sign in again and the requested tool/page will reopen.</div>
    <div style="margin-top:12px;"><a target="_top" href="?es_page=Login" style="display:inline-flex;align-items:center;justify-content:center;min-height:36px;padding:0 14px;border-radius:999px;background:linear-gradient(90deg,#00d985,#34bdf6);color:#05131c;text-decoration:none;font-weight:900;">Sign in again</a></div>
  </div>
</div>
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
        text = str(body)
        is_nav = '<nav class="es-topnav"' in text or "<nav class='es-topnav'" in text
        is_editor = _is_editor_markup(text)
        patched_body = _rewrite_anchor_hrefs(body, editor_only=not is_nav, keep_editor_new_tab=True) if (is_nav or is_editor) else body
        result = original_markdown(patched_body, *args, **kwargs)
        if is_nav or is_editor:
            try:
                import streamlit.components.v1 as components
                components.html(_session_bootstrap_script(enable_tool_tab=is_nav), height=0, scrolling=False)
            except Exception:
                pass
        return result

    setattr(markdown_with_session_links, "_errorsweep_session_links", True)
    st.markdown = markdown_with_session_links

    if callable(original_html):
        @functools.wraps(original_html)
        def html_with_session_links(body: Any, *args: Any, **kwargs: Any) -> Any:
            return original_html(_rewrite_anchor_hrefs(body, editor_only=True, keep_editor_new_tab=True), *args, **kwargs)
        setattr(html_with_session_links, "_errorsweep_session_links", True)
        st.html = html_with_session_links

    _STREAMLIT_PATCHED = True


def _patch_components() -> None:
    global _COMPONENTS_PATCHED
    if _COMPONENTS_PATCHED:
        return
    components = sys.modules.get("streamlit.components.v1")
    if components is None:
        return
    original_html = getattr(components, "html", None)
    if not callable(original_html):
        return

    @functools.wraps(original_html)
    def html_with_restore_fallback(html: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(html)
        is_restore_bridge = "es_restore" in text and ("storageKey" in text or "routeStorageKey" in text)
        if is_restore_bridge and _protected_restore_requested():
            html = _restore_fallback_html() + text
            try:
                kwargs["height"] = max(int(kwargs.get("height") or 0), 170)
            except Exception:
                kwargs["height"] = 170
            kwargs.setdefault("scrolling", False)
        return original_html(html, *args, **kwargs)

    setattr(html_with_restore_fallback, "_errorsweep_restore_fallback", True)
    components.html = html_with_restore_fallback
    _COMPONENTS_PATCHED = True


def _patch_all() -> None:
    _patch_streamlit()
    _patch_components()


def _import_hook(name: str, globals: Any = None, locals: Any = None, fromlist: tuple[Any, ...] = (), level: int = 0) -> Any:
    module = _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)
    if name == "streamlit" or name.startswith("streamlit."):
        _patch_all()
    return module


if not getattr(builtins, "_errorsweep_session_patch_installed", False):
    setattr(builtins, "_errorsweep_session_patch_installed", True)
    builtins.__import__ = _import_hook

_patch_all()
