
"""
ErrorSweep self-hosted translation adapter.

Purpose:
- Allows ErrorSweep Pro to translate without OpenAI/Gemini API keys.
- Works with self-hosted translation engines such as LibreTranslate or a custom NLLB service.
- Does not store or log text by itself.

Supported providers:
1) libretranslate
   Endpoint example: https://your-libretranslate-server.example.com
   API:
      POST /translate
      { q, source, target, format, api_key? }

2) generic
   Endpoint receives:
      POST <endpoint>
      { texts: [...], source_language, target_language, domain }
   Expected response:
      { translations: ["...", "..."] }
      or [{"translation": "..."}, ...]
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import requests


LANGUAGE_CODE_MAP = {
    # Common LibreTranslate / ISO-ish codes.
    "english": "en", "en": "en",
    "french": "fr", "fr": "fr",
    "spanish": "es", "es": "es",
    "german": "de", "de": "de",
    "italian": "it", "it": "it",
    "portuguese": "pt", "pt": "pt",
    "dutch": "nl", "nl": "nl",
    "polish": "pl", "pl": "pl",
    "russian": "ru", "ru": "ru",
    "ukrainian": "uk", "uk": "uk",
    "greek": "el", "el": "el",
    "turkish": "tr", "tr": "tr",
    "arabic": "ar", "ar": "ar",
    "chinese": "zh", "zh": "zh", "mandarin": "zh",
    "japanese": "ja", "ja": "ja",
    "korean": "ko", "ko": "ko",
    "hindi": "hi", "hi": "hi",
    "telugu": "te", "te": "te",
    "tamil": "ta", "ta": "ta",
    "bengali": "bn", "bangla": "bn", "bn": "bn",
    "urdu": "ur", "ur": "ur",
}


def normalize_language_code(language: str) -> str:
    value = (language or "").strip().lower()
    if not value:
        return "en"

    # fr-FR -> fr, en_US -> en
    short = re.split(r"[-_ ]", value)[0]
    if value in LANGUAGE_CODE_MAP:
        return LANGUAGE_CODE_MAP[value]
    if short in LANGUAGE_CODE_MAP:
        return LANGUAGE_CODE_MAP[short]

    # If user already typed a 2-letter code, pass it through.
    if re.fullmatch(r"[a-z]{2,3}", value):
        return value

    return value


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 60, headers: Optional[Dict[str, str]] = None) -> Any:
    response = requests.post(url, json=payload, headers=headers or {}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def translate_with_libretranslate(
    endpoint: str,
    text: str,
    target_language: str,
    source_language: str = "auto",
    api_key: str = "",
    timeout: int = 60,
) -> str:
    base = endpoint.rstrip("/")
    url = base if base.endswith("/translate") else f"{base}/translate"
    target = normalize_language_code(target_language)
    source = normalize_language_code(source_language) if source_language and source_language != "auto" else "auto"

    payload = {
        "q": text,
        "source": source,
        "target": target,
        "format": "text",
    }
    if api_key:
        payload["api_key"] = api_key

    data = _post_json(url, payload, timeout=timeout)
    if isinstance(data, dict):
        return str(data.get("translatedText") or data.get("translation") or "")
    return ""


def translate_with_generic_endpoint(
    endpoint: str,
    texts: List[str],
    target_language: str,
    source_language: str = "auto",
    domain: str = "",
    api_key: str = "",
    timeout: int = 120,
) -> List[str]:
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "texts": texts,
        "source_language": source_language or "auto",
        "target_language": target_language,
        "domain": domain,
    }
    data = _post_json(endpoint, payload, timeout=timeout, headers=headers)

    if isinstance(data, dict):
        if isinstance(data.get("translations"), list):
            return [str(x.get("translation", x) if isinstance(x, dict) else x) for x in data["translations"]]
        if isinstance(data.get("translated_texts"), list):
            return [str(x) for x in data["translated_texts"]]

    if isinstance(data, list):
        return [str(x.get("translation", x) if isinstance(x, dict) else x) for x in data]

    return [""] * len(texts)


def self_hosted_translate_batch(
    segments: List[Dict[str, Any]],
    endpoint: str,
    provider: str,
    target_language: str,
    source_language: str = "auto",
    domain: str = "",
    api_key: str = "",
    timeout: int = 120,
) -> List[Dict[str, str]]:
    """Translate a batch of ErrorSweep segments with a self-hosted engine."""
    provider = (provider or "libretranslate").strip().lower()
    endpoint = (endpoint or "").strip()
    if not endpoint:
        return [{"location": s.get("location", ""), "translation": ""} for s in segments]

    texts = [str(s.get("source") or s.get("text") or "") for s in segments]
    locations = [str(s.get("location", "")) for s in segments]

    translations: List[str] = []
    if provider == "generic":
        translations = translate_with_generic_endpoint(
            endpoint=endpoint,
            texts=texts,
            target_language=target_language,
            source_language=source_language,
            domain=domain,
            api_key=api_key,
            timeout=timeout,
        )
    else:
        # LibreTranslate is usually one text per call.
        for text in texts:
            if not text:
                translations.append("")
                continue
            try:
                translations.append(
                    translate_with_libretranslate(
                        endpoint=endpoint,
                        text=text,
                        target_language=target_language,
                        source_language=source_language,
                        api_key=api_key,
                        timeout=timeout,
                    )
                )
            except Exception:
                translations.append("")

    # Keep output length aligned to input length.
    if len(translations) < len(segments):
        translations.extend([""] * (len(segments) - len(translations)))

    return [
        {"location": loc, "translation": trans or ""}
        for loc, trans in zip(locations, translations)
    ]