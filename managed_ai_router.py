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
import ipaddress
import json
import os
import re
import socket
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import streamlit as st
except Exception:
    st = None

from openai import OpenAI


def _install_navigation_click_bridge() -> None:
    """Keep the upgraded HTML nav and route its clicks through Streamlit state.

    The product shell uses custom HTML anchors for the top navigation. On
    Streamlit Cloud those anchors can perform a full browser reload, which can
    lose the current Streamlit session before protected pages render. This patch
    leaves the visible navigation untouched and adds off-screen Streamlit buttons
    that perform the existing ``navigate(page)`` action. A tiny click listener
    redirects top-nav clicks to those buttons, so navigation happens in-session.
    """
    if st is None:
        return
    try:
        original_markdown = getattr(st, "markdown", None)
        if not callable(original_markdown) or getattr(original_markdown, "_errorsweep_nav_click_bridge", False):
            return
        import streamlit.components.v1 as components

        def safe_key(value: str) -> str:
            slug = re.sub(r"[^a-z0-9_]+", "_", str(value or "").lower()).strip("_")
            return slug or "page"

        def main_module() -> Any:
            return sys.modules.get("__main__")

        def normalize_page(page: str) -> str:
            module = main_module()
            normalizer = getattr(module, "normalize_es_page", None)
            if callable(normalizer):
                try:
                    return str(normalizer(page))
                except Exception:
                    pass
            return str(page or "Dashboard").strip() or "Dashboard"

        def current_allowed_pages() -> List[str]:
            module = main_module()
            allowed = getattr(module, "allowed_pages", None)
            if callable(allowed):
                try:
                    pages = allowed()
                    if pages:
                        return [str(page) for page in pages]
                except Exception:
                    pass
            return [
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

        def navigation_targets() -> List[str]:
            module = main_module()
            allowed = current_allowed_pages()
            allowed_set = set(allowed)
            workspace_order = list(getattr(module, "WORKSPACE_PAGES", []) or [
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
            ])
            owner_order = list(getattr(module, "OWNER_PAGES", []) or [])
            is_owner = getattr(module, "is_owner", None)
            owner_enabled = False
            if callable(is_owner):
                try:
                    owner_enabled = bool(is_owner())
                except Exception:
                    owner_enabled = False
            targets: List[str] = []
            for page in workspace_order:
                normalized = normalize_page(page)
                if normalized in allowed_set and normalized not in targets:
                    targets.append(normalized)
            if owner_enabled:
                for page in owner_order:
                    normalized = normalize_page(page)
                    if normalized in allowed_set and normalized not in targets:
                        targets.append(normalized)
            settings_page = "Platform Settings" if owner_enabled else ("Admin" if "Admin" in allowed_set else "Account")
            for page in ("Jobs", "Account", settings_page):
                normalized = normalize_page(page)
                if normalized in allowed_set and normalized not in targets:
                    targets.append(normalized)
            return targets

        def render_click_bridge() -> None:
            module = main_module()
            navigate = getattr(module, "navigate", None)
            if not callable(navigate):
                return
            targets = navigation_targets()
            if not targets:
                return
            key_map = {page: f"errorsweep_nav_click_{safe_key(page)}" for page in targets}
            css = """
            <div id="errorsweep-nav-click-bridge-marker" aria-hidden="true"></div>
            <style>
            #errorsweep-nav-click-bridge-marker { display: none !important; }
            body:has(#errorsweep-nav-click-bridge-marker) .st-key-errorsweep_nav_click_bridge {
              position: fixed !important;
              left: -10000px !important;
              top: auto !important;
              width: 1px !important;
              height: 1px !important;
              min-height: 1px !important;
              overflow: hidden !important;
              opacity: 0 !important;
              z-index: -1 !important;
            }
            body:has(#errorsweep-nav-click-bridge-marker) .st-key-errorsweep_nav_click_bridge * {
              pointer-events: none !important;
            }
            </style>
            """
            original_markdown(css, unsafe_allow_html=True)
            with st.container(key="errorsweep_nav_click_bridge"):
                for page, key in key_map.items():
                    if st.button(f"Open {page}", key=key):
                        navigate(page)
            key_map_json = json.dumps(key_map)
            components.html(
                f"""
                <script>
                (() => {{
                  try {{
                    const parentWindow = window.parent || window;
                    const parentDoc = parentWindow.document;
                    if (!parentDoc || parentDoc.__errorsweepNavClickBridge) return;
                    parentDoc.__errorsweepNavClickBridge = true;
                    const keyMap = {key_map_json};
                    const findActionButton = (page) => {{
                      const key = keyMap[String(page || "")];
                      if (!key) return null;
                      return parentDoc.querySelector(".st-key-" + key + " button");
                    }};
                    const pageFromHref = (href) => {{
                      try {{
                        const loc = parentWindow.location || window.location;
                        const url = new URL(href, loc.href);
                        return url.searchParams.get("es_page") || "";
                      }} catch (err) {{
                        return "";
                      }}
                    }};
                    parentDoc.addEventListener("click", (event) => {{
                      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                      const target = event.target;
                      if (!target || !target.closest) return;
                      const anchor = target.closest("a[href]");
                      if (!anchor) return;
                      if (!anchor.closest(".es-topnav") && !anchor.closest(".es-owner-strip") && !anchor.closest(".es-account-menu")) return;
                      const href = String(anchor.getAttribute("href") || "");
                      if (!href || href === "#" || href.includes("es_logout=1")) return;
                      const page = pageFromHref(href);
                      const button = findActionButton(page);
                      if (!button) return;
                      event.preventDefault();
                      event.stopPropagation();
                      button.click();
                    }}, true);
                  }} catch (err) {{}}
                }})();
                </script>
                """,
                height=0,
                scrolling=False,
            )

        @functools.wraps(original_markdown)
        def markdown_with_nav_click_bridge(body: Any, *args: Any, **kwargs: Any) -> Any:
            result = original_markdown(body, *args, **kwargs)
            try:
                html = str(body)
                if '<nav class="es-topnav"' in html or "<nav class='es-topnav'" in html:
                    render_click_bridge()
            except Exception:
                pass
            return result

        setattr(markdown_with_nav_click_bridge, "_errorsweep_nav_click_bridge", True)
        st.markdown = markdown_with_nav_click_bridge
    except Exception:
        pass


_install_navigation_click_bridge()


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
