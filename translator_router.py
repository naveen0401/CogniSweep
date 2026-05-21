"""
translator_router.py

Single backend router for ErrorSweep translation.

SWITCHING LOGIC
1. If user has provided their own API key, use existing BYO-key logic.
2. Else if NLLB_MODE=True, use Phase 2 NLLB self-hosted engine.
3. Else use Phase 1 Azure Translator engine as the current default.

This file does not change the UI. Import it from app.py and use translate_batch()
inside the existing Pro translation function.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

try:
    import streamlit as st
except Exception:
    st = None

from azure_translator import AzureTranslatorError


class TranslatorRouterError(Exception):
    """User-friendly routing exception."""


@dataclass
class TranslationRouteUsage:
    provider: str
    engine: str
    characters: int
    requests: int
    success: bool = True
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "engine": self.engine,
            "characters": self.characters,
            "requests": self.requests,
            "success": self.success,
            "error": self.error,
        }


def _secret(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value not in (None, ""):
        return str(value)
    if st is not None:
        try:
            value = st.secrets.get(name)
            if value not in (None, ""):
                return str(value)
        except Exception:
            pass
    return default


def _bool_secret(name: str, default: bool = False) -> bool:
    value = _secret(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "y", "on", "enabled"}


def nllb_mode_enabled() -> bool:
    return _bool_secret("NLLB_MODE", False)


def current_builtin_engine_label() -> str:
    """Safe user-facing label. Do not expose keys, URLs, or internal infrastructure."""
    if nllb_mode_enabled():
        return "Included AI translation"
    if _secret("AZURE_TRANSLATOR_KEY"):
        return "Included AI translation"
    return "Translation engine not configured"


def get_router_status() -> Dict[str, Any]:
    """Owner/admin diagnostic. Safe because it does not expose secret values."""
    return {
        "nllb_mode": nllb_mode_enabled(),
        "azure_configured": bool(_secret("AZURE_TRANSLATOR_KEY")),
        "azure_region_configured": bool(_secret("AZURE_TRANSLATOR_REGION")),
        "nllb_model_name": _secret("NLLB_MODEL_NAME", "facebook/nllb-200-distilled-600M"),
    }


def translate_batch(
    *,
    source_language: str,
    target_language: str,
    texts: Sequence[str],
    user_api_key: str = "",
    protected_terms: Optional[Sequence[str]] = None,
    # Existing BYO-key logic can be injected here without changing it.
    byok_batch_translate_fn: Optional[Callable[..., Tuple[List[str], Dict[str, Any]]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    """Main translate router used by the whole app.

    Returns:
        (translations, usage_dict)

    UI remains unchanged; app.py only calls this function when no BYO key is used.
    """
    clean_texts = [str(t or "") for t in texts]
    char_count = sum(len(t) for t in clean_texts)

    # 1) BYO-Key path: keep existing logic. The app can pass a callable here.
    if (user_api_key or "").strip():
        if byok_batch_translate_fn is None:
            raise TranslatorRouterError(
                "A user API key was provided, but the existing BYO-key translation handler was not passed to translator_router."
            )
        return byok_batch_translate_fn(
            source_language=source_language,
            target_language=target_language,
            texts=clean_texts,
            user_api_key=user_api_key,
            protected_terms=protected_terms or [],
            metadata=metadata or {},
        )

    # 2) Future Phase 2: NLLB self-hosted engine.
    if nllb_mode_enabled():
        try:
            from nllb_translator import translate_batch as nllb_translate_batch
            translations, usage = nllb_translate_batch(
                source_language=source_language,
                target_language=target_language,
                texts=clean_texts,
                protected_terms=protected_terms or [],
            )
            usage = dict(usage or {})
            usage.setdefault("provider", "nllb_self_hosted")
            usage.setdefault("engine", "nllb")
            usage.setdefault("characters", char_count)
            usage.setdefault("success", True)
            return translations, usage
        except Exception as exc:
            raise TranslatorRouterError(f"NLLB translation failed. {str(exc)[:250]}") from exc

    # 3) Current Phase 1: Azure Translator default.
    try:
        from azure_translator import translate_batch as azure_translate_batch
        translations, usage = azure_translate_batch(
            source_language=source_language,
            target_language=target_language,
            texts=clean_texts,
            protected_terms=protected_terms or [],
        )
        usage = dict(usage or {})
        usage.setdefault("provider", "azure_translator")
        usage.setdefault("engine", "azure")
        usage.setdefault("characters", char_count)
        usage.setdefault("success", True)
        return translations, usage
    except AzureTranslatorError:
        raise
    except Exception as exc:
        raise TranslatorRouterError(f"Built-in translation failed. {str(exc)[:250]}") from exc


def translate(
    *,
    source_language: str,
    target_language: str,
    text: str,
    user_api_key: str = "",
    protected_terms: Optional[Sequence[str]] = None,
    byok_translate_fn: Optional[Callable[..., Tuple[str, Dict[str, Any]]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Single-text convenience wrapper around translate_batch()."""
    if user_api_key and byok_translate_fn is not None:
        return byok_translate_fn(
            source_language=source_language,
            target_language=target_language,
            text=text,
            user_api_key=user_api_key,
            protected_terms=protected_terms or [],
            metadata=metadata or {},
        )

    translations, usage = translate_batch(
        source_language=source_language,
        target_language=target_language,
        texts=[text],
        user_api_key=user_api_key,
        protected_terms=protected_terms,
        metadata=metadata,
    )
    return (translations[0] if translations else ""), usage

