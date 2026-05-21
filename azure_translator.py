"""
azure_translator.py

PHASE 1 — CURRENT BUILT-IN ENGINE
Microsoft Azure Translator integration for ErrorSweep.

Use this while the product is stabilizing and revenue is not yet enough to
self-host a permanent GPU model.

Environment / Streamlit secrets required:
    AZURE_TRANSLATOR_KEY
    AZURE_TRANSLATOR_REGION

Optional:
    AZURE_TRANSLATOR_ENDPOINT = https://api.cognitive.microsofttranslator.com/translate

Public functions:
    translate_text(source_language, target_language, text, protected_terms=None)
    translate_batch(source_language, target_language, texts, protected_terms=None)
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

try:
    import streamlit as st
except Exception:  # lets this module run outside Streamlit too
    st = None


AZURE_TRANSLATOR_ENDPOINT_DEFAULT = "https://api.cognitive.microsofttranslator.com/translate"
AZURE_API_VERSION = "3.0"


class AzureTranslatorError(Exception):
    """User-friendly Azure Translator exception."""


@dataclass
class AzureTranslationUsage:
    provider: str = "azure_translator"
    engine: str = "azure"
    characters: int = 0
    requests: int = 0
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


# Azure Translator language codes. Keep this practical list first; Azure also
# accepts many more ISO language codes. Add more as needed.
AZURE_LANGUAGE_MAP: Dict[str, str] = {
    "auto": "auto",
    "auto-detect": "auto",
    "english": "en",
    "en": "en",
    "french": "fr",
    "fr": "fr",
    "spanish": "es",
    "es": "es",
    "german": "de",
    "de": "de",
    "italian": "it",
    "it": "it",
    "portuguese": "pt",
    "portuguese brazil": "pt",
    "pt": "pt",
    "russian": "ru",
    "ru": "ru",
    "arabic": "ar",
    "ar": "ar",
    "chinese": "zh-Hans",
    "chinese simplified": "zh-Hans",
    "simplified chinese": "zh-Hans",
    "zh": "zh-Hans",
    "zh-hans": "zh-Hans",
    "chinese traditional": "zh-Hant",
    "traditional chinese": "zh-Hant",
    "zh-hant": "zh-Hant",
    "japanese": "ja",
    "ja": "ja",
    "korean": "ko",
    "ko": "ko",
    "hindi": "hi",
    "hi": "hi",
    "telugu": "te",
    "te": "te",
    "tamil": "ta",
    "ta": "ta",
    "malayalam": "ml",
    "ml": "ml",
    "kannada": "kn",
    "kn": "kn",
    "bengali": "bn",
    "bangla": "bn",
    "bn": "bn",
    "marathi": "mr",
    "mr": "mr",
    "gujarati": "gu",
    "gu": "gu",
    "punjabi": "pa",
    "pa": "pa",
    "urdu": "ur",
    "ur": "ur",
    "nepali": "ne",
    "ne": "ne",
    "odia": "or",
    "oriya": "or",
    "or": "or",
    "turkish": "tr",
    "tr": "tr",
    "thai": "th",
    "th": "th",
    "vietnamese": "vi",
    "vi": "vi",
    "indonesian": "id",
    "id": "id",
    "dutch": "nl",
    "nl": "nl",
    "polish": "pl",
    "pl": "pl",
}


# Protected tokens: placeholders, URLs, emails, tags, variables, and format codes.
PROTECTED_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$\w+|<[^>]+>|\b\w+_id\b)",
    flags=re.UNICODE,
)


def _secret(name: str, default: str = "") -> str:
    """Read environment first, then Streamlit secrets."""
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


def normalize_language_code(language: str, *, allow_auto: bool = False) -> str:
    value = (language or "").strip()
    if not value:
        return "auto" if allow_auto else "en"
    key = value.lower().replace("_", "-").strip()
    code = AZURE_LANGUAGE_MAP.get(key, value)
    if code == "auto" and not allow_auto:
        return "en"
    return code


def _protect_text(text: str, protected_terms: Optional[Sequence[str]] = None) -> Tuple[str, Dict[str, str]]:
    """Replace protected terms/placeholders with safe tokens before MT."""
    mapping: Dict[str, str] = {}

    def add_token(original: str) -> str:
        token = f"__ESPH_{len(mapping)}__"
        mapping[token] = original
        return token

    protected = PROTECTED_PATTERN.sub(lambda m: add_token(m.group(0)), text or "")

    # Project/client DNT terms can be protected too.
    for term in sorted(set(protected_terms or []), key=len, reverse=True):
        term = str(term).strip()
        if not term or term not in protected:
            continue
        token = add_token(term)
        protected = protected.replace(term, token)

    return protected, mapping


def _restore_text(text: str, mapping: Dict[str, str]) -> str:
    out = text or ""
    for token, original in mapping.items():
        # Azure usually preserves this exactly, but we handle HTML escaping too.
        out = out.replace(token, original)
        out = out.replace(token.lower(), original)
        out = out.replace(token.upper(), original)
        out = out.replace(token.replace("_", " "), original)
    return out.strip()


def _count_characters(texts: Sequence[str]) -> int:
    return sum(len(t or "") for t in texts)


def _add_session_usage(characters: int, requests_count: int = 1) -> None:
    """Session-level character counter for plan-tier/monthly tracking MVP."""
    if st is None:
        return
    try:
        st.session_state["azure_translator_characters_used"] = int(st.session_state.get("azure_translator_characters_used", 0)) + int(characters)
        st.session_state["azure_translator_requests_used"] = int(st.session_state.get("azure_translator_requests_used", 0)) + int(requests_count)
        st.session_state.setdefault("translation_usage_events", [])
        st.session_state["translation_usage_events"].insert(0, {
            "provider": "azure_translator",
            "characters": int(characters),
            "requests": int(requests_count),
        })
    except Exception:
        pass


def _azure_error_message(status_code: int, payload: Any) -> str:
    message = ""
    code = ""
    if isinstance(payload, dict):
        err = payload.get("error") or payload
        code = str(err.get("code", "")) if isinstance(err, dict) else ""
        message = str(err.get("message", "")) if isinstance(err, dict) else str(payload)
    else:
        message = str(payload)

    if status_code in (401, 403):
        return "Azure Translator credentials are invalid or the region is wrong. Check AZURE_TRANSLATOR_KEY and AZURE_TRANSLATOR_REGION."
    if status_code == 429:
        return "Azure Translator quota or rate limit was reached. Try again later or increase the Azure Translator plan."
    if status_code >= 500:
        return "Azure Translator service is temporarily unavailable. Please retry."
    if code or message:
        return f"Azure Translator returned HTTP {status_code}. {code} {message}".strip()
    return f"Azure Translator returned HTTP {status_code}."


def translate_batch(
    *,
    source_language: str,
    target_language: str,
    texts: Sequence[str],
    protected_terms: Optional[Sequence[str]] = None,
    timeout: int = 45,
    batch_size: int = 50,
) -> Tuple[List[str], Dict[str, Any]]:
    """Translate many strings with Azure Translator.

    Returns (translations, usage_dict). On failure, raises AzureTranslatorError.
    """
    key = _secret("AZURE_TRANSLATOR_KEY")
    region = _secret("AZURE_TRANSLATOR_REGION")
    endpoint = _secret("AZURE_TRANSLATOR_ENDPOINT", AZURE_TRANSLATOR_ENDPOINT_DEFAULT).rstrip("/")

    if not key:
        raise AzureTranslatorError("Built-in translation is not configured: missing AZURE_TRANSLATOR_KEY.")
    if not region:
        raise AzureTranslatorError("Built-in translation is not configured: missing AZURE_TRANSLATOR_REGION.")

    source_code = normalize_language_code(source_language, allow_auto=True)
    target_code = normalize_language_code(target_language, allow_auto=False)

    all_translations: List[str] = []
    total_chars = _count_characters(list(texts))
    requests_used = 0

    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Ocp-Apim-Subscription-Region": region,
        "Content-Type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }

    params: Dict[str, str] = {
        "api-version": AZURE_API_VERSION,
        "to": target_code,
    }
    if source_code and source_code != "auto":
        params["from"] = source_code

    # Do not send huge batches; it makes error handling and retry harder.
    clean_texts = [str(t or "") for t in texts]
    for start in range(0, len(clean_texts), max(1, int(batch_size))):
        chunk = clean_texts[start:start + max(1, int(batch_size))]
        protected_chunk: List[str] = []
        mappings: List[Dict[str, str]] = []
        for text in chunk:
            protected, mapping = _protect_text(text, protected_terms=protected_terms)
            protected_chunk.append(protected)
            mappings.append(mapping)

        body = [{"Text": t} for t in protected_chunk]
        try:
            response = requests.post(endpoint, params=params, headers=headers, json=body, timeout=timeout)
            requests_used += 1
        except requests.RequestException as exc:
            raise AzureTranslatorError(f"Could not connect to Azure Translator. {str(exc)[:180]}") from exc

        try:
            payload = response.json()
        except Exception:
            payload = response.text

        if response.status_code >= 400:
            raise AzureTranslatorError(_azure_error_message(response.status_code, payload))

        if not isinstance(payload, list):
            raise AzureTranslatorError("Azure Translator returned an unexpected response format.")

        for idx, item in enumerate(payload):
            translated = ""
            try:
                translated = item["translations"][0]["text"]
            except Exception:
                translated = ""
            all_translations.append(_restore_text(translated, mappings[idx]))

    _add_session_usage(total_chars, requests_used)
    usage = AzureTranslationUsage(characters=total_chars, requests=requests_used, success=True).to_dict()
    return all_translations, usage


def translate_text(
    *,
    source_language: str,
    target_language: str,
    text: str,
    protected_terms: Optional[Sequence[str]] = None,
    timeout: int = 45,
) -> Tuple[str, Dict[str, Any]]:
    translations, usage = translate_batch(
        source_language=source_language,
        target_language=target_language,
        texts=[text],
        protected_terms=protected_terms,
        timeout=timeout,
        batch_size=1,
    )
    return translations[0] if translations else "", usage

