"""CogniSweep managed machine-translation routing.

Self-hosted/local MT engines were retired from this repository. Keep this
module's public API stable so the app and async worker can continue to prepare
Human Review rows while a future Amazon Translate adapter is added here.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class TranslationRouteError(RuntimeError):
    """Raised when no managed MT provider is available for a translation run."""


def estimate_characters(texts: List[str]) -> int:
    return sum(len(str(text or "")) for text in texts)


def current_builtin_engine_label() -> str:
    return "Managed MT not configured; Human Review mode active"


def builtin_engine_status(timeout: int = 3) -> List[Dict[str, Any]]:
    _ = timeout
    return [
        {
            "engine": "Amazon Translate",
            "provider": "amazon_translate",
            "enabled": False,
            "ready": False,
            "detail": "future adapter not implemented",
            "priority": "Future managed AWS MT route",
        }
    ]


def smoke_test_builtin_engines(timeout: int = 120) -> List[Dict[str, Any]]:
    _ = timeout
    return [
        {
            "engine": "Amazon Translate",
            "success": False,
            "translation": "",
            "error": "future adapter not implemented",
        }
    ]


def translate_batch(
    *,
    source_language: str,
    target_language: str,
    texts: List[str],
    user_api_key: str = "",
    protected_terms: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    _ = (source_language, target_language, user_api_key, protected_terms, metadata)
    normalized_texts = ["" if text is None else str(text) for text in texts]
    usage = {
        "provider": "managed_mt",
        "engine": "amazon_translate_pending",
        "managed": True,
        "characters": estimate_characters(normalized_texts),
        "requests": 0,
        "success": False,
        "error": "Amazon Translate adapter is not implemented yet; use BYO AI or Human Review.",
        "metadata": metadata or {},
    }
    if not normalized_texts:
        usage["success"] = True
        usage["error"] = ""
        return [], usage
    raise TranslationRouteError(str(usage["error"]))
