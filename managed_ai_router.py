"""
managed_ai_router.py

Drop-in router for ErrorSweep Managed AI / Keyless AI.

What it does:
1. If the user has their own OpenAI API key, use OpenAI.
2. If the user has no key, use your self-hosted vLLM server.
3. Both routes use the OpenAI Python SDK, because vLLM is OpenAI-compatible.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

try:
    import streamlit as st
except Exception:  # Allows using this file outside Streamlit too
    st = None

from openai import OpenAI


@dataclass
class AIRoute:
    provider: str          # "openai_byok" or "managed_vllm"
    model: str             # model name to send to the API
    api_key: str           # OpenAI key or private vLLM token
    base_url: Optional[str] # None for OpenAI, https://.../v1 for vLLM
    managed: bool          # True when platform pays/hosts engine


def _secret(name: str, default: str = "") -> str:
    """Read value from environment first, then Streamlit secrets."""
    if os.environ.get(name):
        return os.environ[name]
    if st is not None:
        try:
            value = st.secrets.get(name)
            if value:
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


def _normalize_base_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and not url.endswith("/v1"):
        url += "/v1"
    return url


def select_ai_route(user_openai_key: str = "", purpose: str = "translate") -> AIRoute:
    """
    Main routing logic.

    Use this before QA, Pro translation, scorecard AI, or review AI.
    """

    # 1) User's own key from input/session wins.
    user_key = (user_openai_key or _session_value("byo_openai_api_key", "")).strip()
    if user_key:
        return AIRoute(
            provider="openai_byok",
            model=_session_value("byo_openai_model", _secret("ERRORSWEEP_OPENAI_DEFAULT_MODEL", "gpt-4o-mini")),
            api_key=user_key,
            base_url=None,
            managed=False,
        )

    # 2) Otherwise use your managed vLLM endpoint.
    managed_base_url = _normalize_base_url(_secret("ERRORSWEEP_MANAGED_AI_BASE_URL", ""))
    managed_api_key = _secret("ERRORSWEEP_MANAGED_AI_API_KEY", "errorsweep-managed-token")
    managed_model = _secret("ERRORSWEEP_MANAGED_AI_MODEL", "errorsweep-managed")

    if managed_base_url:
        return AIRoute(
            provider="managed_vllm",
            model=managed_model,
            api_key=managed_api_key,
            base_url=managed_base_url,
            managed=True,
        )

    # 3) Final fallback: platform OpenAI key, if you still want it.
    platform_key = _secret("OPENAI_API_KEY", "")
    if platform_key:
        return AIRoute(
            provider="openai_platform",
            model=_secret("ERRORSWEEP_OPENAI_DEFAULT_MODEL", "gpt-4o-mini"),
            api_key=platform_key,
            base_url=None,
            managed=True,
        )

    raise RuntimeError("No AI route available. Add user API key or configure Managed AI endpoint.")


def get_ai_client(route: AIRoute) -> OpenAI:
    if route.base_url:
        return OpenAI(api_key=route.api_key, base_url=route.base_url, timeout=120, max_retries=1)
    return OpenAI(api_key=route.api_key, timeout=120, max_retries=1)


def _extract_json_object(text: str) -> Dict[str, Any]:
    """Open-source models sometimes wrap JSON in text. This safely extracts it."""
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


def ai_json_items(
    system_prompt: str,
    user_prompt: str,
    route: Optional[AIRoute] = None,
    user_openai_key: str = "",
    temperature: float = 0.0,
    max_tokens: int = 3000,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    One function for both OpenAI and vLLM.

    Expected model response format:
    {
      "items": [ ... ]
    }
    """
    route = route or select_ai_route(user_openai_key=user_openai_key)
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
        usage_info["error"] = str(exc)[:500]
        return [], usage_info


# Simple test from terminal:
# python managed_ai_router.py
if __name__ == "__main__":
    route = select_ai_route()
    print("Using provider:", route.provider)
    print("Using model:", route.model)
    print("Using base_url:", route.base_url)

    items, usage = ai_json_items(
        system_prompt="You are a helpful assistant that extracts error types from logs.",
        user_prompt="Extract error types from this log: '2024-01-01 ERROR Something bad happened'",
        route=route,
        temperature=0.0,
        max_tokens=100,
    )
    print("Extracted items:", items)
    print("Usage info:", usage)