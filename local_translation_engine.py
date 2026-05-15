"""
ErrorSweep local translation engine connector.

This module is intentionally independent from Streamlit.  It can be used by
app.py, test scripts, or background workers.

Supported engines:
- LibreTranslate: base endpoint, e.g. https://xxx.trycloudflare.com
- IndicTrans2 worker: /translate endpoint, e.g. https://xxx.trycloudflare.com/translate

Main functions expected by ErrorSweep app versions:
- has_local_translation_engine(...)
- select_translation_route(...)
- preflight_translation_engine(...)
- self_hosted_translate_batch(...)
- local_translate_batch_adapter(...)

Important behavior:
- Converts English language names to engine language codes.
- Keeps placeholders, variables, URLs, emails, tags, bullets, emojis, and units safe.
- Allows square-bracket UI labels to localize inside brackets while preserving bracket structure.
- Parses multiple response shapes from different workers.
- Never fabricates translation text if the engine fails.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests


# ==========================================================
# Language maps
# ==========================================================

LIBRE_NAME_TO_CODE: Dict[str, str] = {
    "auto": "auto",
    "automatic": "auto",
    "english": "en",
    "en": "en",
    "french": "fr",
    "fr": "fr",
    "german": "de",
    "de": "de",
    "spanish": "es",
    "es": "es",
    "italian": "it",
    "it": "it",
    "portuguese": "pt",
    "pt": "pt",
    "russian": "ru",
    "ru": "ru",
    "arabic": "ar",
    "ar": "ar",
    "chinese": "zh",
    "simplified chinese": "zh",
    "zh": "zh",
    "japanese": "ja",
    "ja": "ja",
    "korean": "ko",
    "ko": "ko",
    "hindi": "hi",
    "hi": "hi",
}

LIBRE_CODE_TO_NAME: Dict[str, str] = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "hi": "Hindi",
}

# IndicTrans2 / IndicTrans Toolkit language codes.
INDICTRANS_NAME_TO_CODE: Dict[str, str] = {
    "english": "eng_Latn",
    "eng": "eng_Latn",
    "eng_latn": "eng_Latn",
    "assamese": "asm_Beng",
    "asm_beng": "asm_Beng",
    "bengali": "ben_Beng",
    "bangla": "ben_Beng",
    "ben_beng": "ben_Beng",
    "bodo": "brx_Deva",
    "brx_deva": "brx_Deva",
    "dogri": "doi_Deva",
    "doi_deva": "doi_Deva",
    "konkani": "gom_Deva",
    "gom_deva": "gom_Deva",
    "gujarati": "guj_Gujr",
    "guj_gujr": "guj_Gujr",
    "hindi": "hin_Deva",
    "hin_deva": "hin_Deva",
    "kannada": "kan_Knda",
    "kan_knda": "kan_Knda",
    "kashmiri": "kas_Arab",
    "kas_arab": "kas_Arab",
    "maithili": "mai_Deva",
    "mai_deva": "mai_Deva",
    "malayalam": "mal_Mlym",
    "mal_mlym": "mal_Mlym",
    "marathi": "mar_Deva",
    "mar_deva": "mar_Deva",
    "manipuri": "mni_Beng",
    "meitei": "mni_Beng",
    "mni_beng": "mni_Beng",
    "nepali": "npi_Deva",
    "npi_deva": "npi_Deva",
    "odia": "ory_Orya",
    "oriya": "ory_Orya",
    "ory_orya": "ory_Orya",
    "punjabi": "pan_Guru",
    "pan_guru": "pan_Guru",
    "sanskrit": "san_Deva",
    "san_deva": "san_Deva",
    "santali": "sat_Olck",
    "sat_olck": "sat_Olck",
    "sindhi": "snd_Arab",
    "snd_arab": "snd_Arab",
    "tamil": "tam_Taml",
    "tam_taml": "tam_Taml",
    "telugu": "tel_Telu",
    "tel_telu": "tel_Telu",
    "urdu": "urd_Arab",
    "urd_arab": "urd_Arab",
}

INDICTRANS_CODE_TO_NAME: Dict[str, str] = {
    "eng_Latn": "English",
    "asm_Beng": "Assamese",
    "ben_Beng": "Bengali",
    "brx_Deva": "Bodo",
    "doi_Deva": "Dogri",
    "gom_Deva": "Konkani",
    "guj_Gujr": "Gujarati",
    "hin_Deva": "Hindi",
    "kan_Knda": "Kannada",
    "kas_Arab": "Kashmiri",
    "mai_Deva": "Maithili",
    "mal_Mlym": "Malayalam",
    "mar_Deva": "Marathi",
    "mni_Beng": "Manipuri",
    "npi_Deva": "Nepali",
    "ory_Orya": "Odia",
    "pan_Guru": "Punjabi",
    "san_Deva": "Sanskrit",
    "sat_Olck": "Santali",
    "snd_Arab": "Sindhi",
    "tam_Taml": "Tamil",
    "tel_Telu": "Telugu",
    "urd_Arab": "Urdu",
}

INDIC_TARGET_NAMES = {
    name for name, code in INDICTRANS_NAME_TO_CODE.items()
    if code != "eng_Latn"
}
INDIC_TARGET_CODES = {
    code for code in INDICTRANS_CODE_TO_NAME
    if code != "eng_Latn"
}


# ==========================================================
# Data classes
# ==========================================================

@dataclass
class EngineRoute:
    provider: str
    endpoint: str
    source_language: str
    target_language: str
    health_url: str
    reason: str = ""


@dataclass
class PreflightResult:
    ok: bool
    provider: str
    endpoint: str
    health_url: str
    message: str
    details: Optional[Any] = None


# ==========================================================
# General helpers
# ==========================================================

def env_value(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default or "").strip()


def as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def clean_space(text: str) -> str:
    text = as_text(text)
    text = text.replace("\u00A0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def strip_trailing_slash(url: str) -> str:
    return (url or "").strip().rstrip("/")


def looks_like_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def get_segment_source(segment: Dict[str, Any]) -> str:
    return as_text(segment.get("source") or segment.get("text") or segment.get("Source") or "")


def get_segment_location(segment: Dict[str, Any], index: int = 0) -> str:
    return as_text(
        segment.get("location")
        or segment.get("Location")
        or segment.get("id")
        or segment.get("ID")
        or f"Segment {index + 1}"
    )


def chunks(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    size = max(1, int(size or 1))
    for i in range(0, len(items), size):
        yield items[i:i + size]


# ==========================================================
# Endpoint normalization and routing
# ==========================================================

def normalize_libretranslate_endpoint(endpoint: str) -> str:
    endpoint = strip_trailing_slash(endpoint)
    if endpoint.endswith("/translate"):
        endpoint = endpoint[: -len("/translate")]
    if endpoint.endswith("/languages"):
        endpoint = endpoint[: -len("/languages")]
    return endpoint


def normalize_indictrans2_endpoint(endpoint: str) -> str:
    endpoint = strip_trailing_slash(endpoint)
    if endpoint.endswith("/health"):
        endpoint = endpoint[: -len("/health")]
    if not endpoint.endswith("/translate"):
        endpoint = endpoint + "/translate"
    return endpoint


def health_url_for(provider: str, endpoint: str) -> str:
    provider = (provider or "").lower().strip()
    if provider == "libretranslate":
        return normalize_libretranslate_endpoint(endpoint) + "/languages"
    if provider == "indictrans2":
        base = normalize_indictrans2_endpoint(endpoint)
        return base[: -len("/translate")] + "/health"
    return strip_trailing_slash(endpoint)


def libre_code(language: str, default: str = "en") -> str:
    value = clean_space(language).lower().replace("-", " ")
    return LIBRE_NAME_TO_CODE.get(value, value if len(value) <= 3 else default)


def indic_code(language: str, default: str = "eng_Latn") -> str:
    raw = clean_space(language)
    if raw in INDICTRANS_CODE_TO_NAME:
        return raw
    key = raw.lower().replace("-", "_").replace(" ", "_")
    if key in INDICTRANS_NAME_TO_CODE:
        return INDICTRANS_NAME_TO_CODE[key]
    key2 = raw.lower().strip()
    return INDICTRANS_NAME_TO_CODE.get(key2, default)


def is_indic_target(language: str) -> bool:
    raw = clean_space(language)
    if raw in INDIC_TARGET_CODES:
        return True
    key = raw.lower().replace("-", "_").replace(" ", "_")
    return key in INDIC_TARGET_NAMES or (
        key in INDICTRANS_NAME_TO_CODE and INDICTRANS_NAME_TO_CODE[key] in INDIC_TARGET_CODES
    )


def select_translation_route(
    target_language: str,
    source_language: str = "English",
    libretranslate_endpoint: Optional[str] = None,
    indictrans2_endpoint: Optional[str] = None,
    provider: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> Optional[EngineRoute]:
    """Choose the correct local engine for a target language.

    Provider override:
    - provider="libretranslate" forces LibreTranslate.
    - provider="indictrans2" forces IndicTrans2.
    - provider="generic" is treated as IndicTrans2 if endpoint ends with /translate,
      otherwise LibreTranslate for backward compatibility.
    """

    provider = (provider or "").lower().strip()
    endpoint = endpoint or ""

    libretranslate_endpoint = (
        libretranslate_endpoint
        or env_value("LIBRETRANSLATE_ENDPOINT")
        or env_value("LOCAL_TRANSLATION_ENDPOINT")
    )
    indictrans2_endpoint = (
        indictrans2_endpoint
        or env_value("INDICTRANS2_ENDPOINT")
        or (endpoint if "8000" in endpoint or endpoint.endswith("/translate") else "")
    )

    if provider == "libretranslate":
        ep = normalize_libretranslate_endpoint(endpoint or libretranslate_endpoint)
        if not looks_like_url(ep):
            return None
        return EngineRoute(
            provider="libretranslate",
            endpoint=ep,
            source_language=libre_code(source_language, default="en"),
            target_language=libre_code(target_language, default=""),
            health_url=health_url_for("libretranslate", ep),
            reason="provider override",
        )

    if provider == "indictrans2":
        ep = normalize_indictrans2_endpoint(endpoint or indictrans2_endpoint)
        if not looks_like_url(ep):
            return None
        return EngineRoute(
            provider="indictrans2",
            endpoint=ep,
            source_language=indic_code(source_language, default="eng_Latn"),
            target_language=indic_code(target_language, default=""),
            health_url=health_url_for("indictrans2", ep),
            reason="provider override",
        )

    if provider == "generic":
        # Backward compatibility: "generic" with /translate usually means the IndicTrans2 worker.
        if endpoint and (endpoint.endswith("/translate") or "8000" in endpoint):
            ep = normalize_indictrans2_endpoint(endpoint)
            if looks_like_url(ep):
                return EngineRoute(
                    provider="indictrans2",
                    endpoint=ep,
                    source_language=indic_code(source_language, default="eng_Latn"),
                    target_language=indic_code(target_language, default=""),
                    health_url=health_url_for("indictrans2", ep),
                    reason="generic endpoint looks like IndicTrans2",
                )
        ep = normalize_libretranslate_endpoint(endpoint or libretranslate_endpoint)
        if looks_like_url(ep):
            return EngineRoute(
                provider="libretranslate",
                endpoint=ep,
                source_language=libre_code(source_language, default="en"),
                target_language=libre_code(target_language, default=""),
                health_url=health_url_for("libretranslate", ep),
                reason="generic fallback to LibreTranslate",
            )

    # Automatic routing.
    if is_indic_target(target_language):
        ep = normalize_indictrans2_endpoint(indictrans2_endpoint)
        if looks_like_url(ep):
            return EngineRoute(
                provider="indictrans2",
                endpoint=ep,
                source_language=indic_code(source_language, default="eng_Latn"),
                target_language=indic_code(target_language, default=""),
                health_url=health_url_for("indictrans2", ep),
                reason="Indic target language",
            )
        return None

    ep = normalize_libretranslate_endpoint(libretranslate_endpoint)
    if looks_like_url(ep):
        return EngineRoute(
            provider="libretranslate",
            endpoint=ep,
            source_language=libre_code(source_language, default="en"),
            target_language=libre_code(target_language, default=""),
            health_url=health_url_for("libretranslate", ep),
            reason="non-Indic target language",
        )

    return None


def has_local_translation_engine(
    target_language: Optional[str] = None,
    source_language: str = "English",
    endpoint: Optional[str] = None,
    provider: Optional[str] = None,
    libretranslate_endpoint: Optional[str] = None,
    indictrans2_endpoint: Optional[str] = None,
) -> bool:
    if target_language:
        return select_translation_route(
            target_language=target_language,
            source_language=source_language,
            endpoint=endpoint,
            provider=provider,
            libretranslate_endpoint=libretranslate_endpoint,
            indictrans2_endpoint=indictrans2_endpoint,
        ) is not None

    return bool(
        looks_like_url(libretranslate_endpoint or env_value("LIBRETRANSLATE_ENDPOINT") or env_value("LOCAL_TRANSLATION_ENDPOINT"))
        or looks_like_url(indictrans2_endpoint or env_value("INDICTRANS2_ENDPOINT"))
        or looks_like_url(endpoint or "")
    )


def preflight_translation_engine(
    target_language: str,
    source_language: str = "English",
    endpoint: Optional[str] = None,
    provider: Optional[str] = None,
    libretranslate_endpoint: Optional[str] = None,
    indictrans2_endpoint: Optional[str] = None,
    api_key: str = "",
    timeout: int = 20,
) -> PreflightResult:
    route = select_translation_route(
        target_language=target_language,
        source_language=source_language,
        endpoint=endpoint,
        provider=provider,
        libretranslate_endpoint=libretranslate_endpoint,
        indictrans2_endpoint=indictrans2_endpoint,
    )
    if not route:
        return PreflightResult(
            ok=False,
            provider="none",
            endpoint="",
            health_url="",
            message=f"No local translation endpoint is configured for {target_language}.",
        )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        res = requests.get(route.health_url, headers=headers, timeout=timeout)
        if res.status_code >= 400:
            return PreflightResult(
                ok=False,
                provider=route.provider,
                endpoint=route.endpoint,
                health_url=route.health_url,
                message=f"{route.provider} is not ready at {route.health_url}: HTTP {res.status_code}",
                details=res.text[:500],
            )
        try:
            details = res.json()
        except Exception:
            details = res.text[:500]
        return PreflightResult(
            ok=True,
            provider=route.provider,
            endpoint=route.endpoint,
            health_url=route.health_url,
            message=f"{route.provider} is reachable at {route.health_url}.",
            details=details,
        )
    except Exception as exc:
        return PreflightResult(
            ok=False,
            provider=route.provider,
            endpoint=route.endpoint,
            health_url=route.health_url,
            message=f"{route.provider} is not reachable at {route.health_url}: {exc}",
        )


# ==========================================================
# Protected tokens, placeholders, emojis, bullets
# ==========================================================

URL_RE = r"https?://[^\s\]\)<>\"']+"
EMAIL_RE = r"[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,}"
HTML_TAG_RE = r"</?[^>\s]+(?:\s+[^>]*)?>"
PLACEHOLDER_RE = r"\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$\w+|\b[A-Za-z0-9]+_[A-Za-z0-9_]+\b"
CODE_TOKEN_RE = r"`[^`]+`"
PROTECTED_RE = re.compile(
    f"({URL_RE}|{EMAIL_RE}|{HTML_TAG_RE}|{CODE_TOKEN_RE}|{PLACEHOLDER_RE})",
    re.UNICODE,
)

# A pragmatic emoji matcher covering common emoji ranges and variation selectors.
EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\u2600-\u27BF"
    "\uFE0F"
    "\u200D"
    "]+",
    re.UNICODE,
)

LEADING_MARKER_RE = re.compile(
    r"^(\s*(?:[\u2022\u2219\u00B7\u2023\u25E6\u2043\u204C\u204D\u25AA\u25CF\-\*]+|"
    r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+)\s*)+",
    re.UNICODE,
)

COMMON_UNIT_RE = re.compile(
    r"\b(kcal|cal|kg|g|mg|km|m|cm|mm|mins?|minutes?|hrs?|hours?|MB|GB|KB|ms|s|%|°C|°F)\b",
    re.IGNORECASE,
)


@dataclass
class ProtectedText:
    masked_text: str
    tokens: List[str]
    markers: List[str]
    leading_marker: str
    source_emojis: List[str]
    source_units: List[str]
    source_was_bracket_label: bool


def mask_protected_text(source: str) -> ProtectedText:
    text = as_text(source)
    tokens: List[str] = []
    markers: List[str] = []

    def repl(match: re.Match) -> str:
        token = match.group(0)
        marker = f" ZXQPH{len(tokens)}QXZ "
        tokens.append(token)
        markers.append(marker.strip())
        return marker

    masked = PROTECTED_RE.sub(repl, text)
    leading = ""
    m = LEADING_MARKER_RE.match(text)
    if m:
        leading = m.group(0)

    emojis = EMOJI_RE.findall(text)
    units = [u for u in COMMON_UNIT_RE.findall(text)]

    stripped = text.strip()
    source_was_bracket_label = stripped.startswith("[") and stripped.endswith("]") and len(stripped) >= 2

    return ProtectedText(
        masked_text=masked,
        tokens=tokens,
        markers=markers,
        leading_marker=leading,
        source_emojis=emojis,
        source_units=units,
        source_was_bracket_label=source_was_bracket_label,
    )


def unmask_protected_text(translated: str, protected: ProtectedText, source: str = "") -> str:
    text = as_text(translated)

    # Exact marker replacement.
    for marker, token in zip(protected.markers, protected.tokens):
        text = text.replace(marker, token)
        text = text.replace(marker.replace(" ", ""), token)

    # Marker damage repair examples: "ZXQPH 0 QXZ", "ZXQPH0 QXZ", etc.
    for idx, token in enumerate(protected.tokens):
        loose = re.compile(rf"Z\s*X\s*Q\s*P\s*H\s*{idx}\s*Q\s*X\s*Z", re.IGNORECASE)
        text = loose.sub(token, text)

    # If a token disappeared, append it in a safe way.
    for token in protected.tokens:
        if token not in text:
            if text and not text.endswith(" "):
                text += " "
            text += token

    # Preserve leading bullets/icons/emojis when the engine drops them.
    if protected.leading_marker:
        marker_clean = protected.leading_marker.strip()
        if marker_clean and marker_clean not in text[: max(8, len(marker_clean) + 4)]:
            text = protected.leading_marker + text.lstrip()

    # Preserve all source emojis/icons if missing.
    for emoji in protected.source_emojis:
        if emoji and emoji not in text:
            text = emoji + " " + text.lstrip()

    # Preserve common units when the source has them and the target drops them.
    for unit in protected.source_units:
        if unit and not re.search(rf"\b{re.escape(unit)}\b", text, flags=re.IGNORECASE):
            text = text.rstrip()
            text += f" {unit}"

    # Square-bracket UI labels are allowed to localize inside; preserve brackets.
    if protected.source_was_bracket_label:
        t = text.strip()
        if t and not (t.startswith("[") and t.endswith("]")):
            text = f"[{t}]"

    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([({\[])\s+", r"\1", text)
    text = re.sub(r"\s+([)}\]])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()

    return text


# ==========================================================
# Response parsing
# ==========================================================

def _extract_text_from_item(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in (
            "translation",
            "translatedText",
            "translated_text",
            "text",
            "output",
            "target",
            "result",
        ):
            value = item.get(key)
            if isinstance(value, str):
                return value
        if "translation" in item and item["translation"] is not None:
            return str(item["translation"])
    return str(item)


def parse_translation_response(data: Any, expected_count: int = 1) -> List[str]:
    """Parse common translation API response shapes."""
    if data is None:
        return []

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return [data] if expected_count <= 1 else [data]

    if isinstance(data, list):
        return [_extract_text_from_item(x) for x in data]

    if not isinstance(data, dict):
        return [str(data)]

    for key in ("translations", "translated_texts", "translatedTexts", "outputs", "results"):
        if key in data:
            value = data[key]
            if isinstance(value, list):
                return [_extract_text_from_item(x) for x in value]
            if isinstance(value, str):
                return [value]

    for key in ("translatedText", "translated_text", "translation", "text", "output", "result"):
        if key in data:
            value = data[key]
            if isinstance(value, list):
                return [_extract_text_from_item(x) for x in value]
            return [_extract_text_from_item(value)]

    return []


def request_json(
    method: str,
    url: str,
    *,
    json_payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 120,
) -> Any:
    headers = headers or {"Content-Type": "application/json"}
    if method.upper() == "GET":
        res = requests.get(url, headers=headers, timeout=timeout)
    else:
        res = requests.post(url, headers=headers, json=json_payload, timeout=timeout)

    if res.status_code >= 400:
        raise RuntimeError(f"HTTP {res.status_code} from {url}: {res.text[:800]}")

    try:
        return res.json()
    except Exception:
        return res.text


# ==========================================================
# Engine calls
# ==========================================================

def translate_with_libretranslate(
    texts: List[str],
    endpoint: str,
    target_language: str,
    source_language: str = "English",
    api_key: str = "",
    timeout: int = 180,
) -> List[str]:
    endpoint = normalize_libretranslate_endpoint(endpoint)
    source_code = libre_code(source_language, default="en")
    target_code = libre_code(target_language, default="")

    if not target_code:
        raise ValueError(f"Unsupported LibreTranslate target language: {target_language}")
    if not looks_like_url(endpoint):
        raise ValueError(f"Invalid LibreTranslate endpoint: {endpoint}")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: Dict[str, Any] = {
        "q": texts,
        "source": source_code,
        "target": target_code,
        "format": "text",
    }
    if api_key:
        payload["api_key"] = api_key

    try:
        data = request_json(
            "POST",
            endpoint + "/translate",
            json_payload=payload,
            headers=headers,
            timeout=timeout,
        )
        parsed = parse_translation_response(data, expected_count=len(texts))
        if len(parsed) == len(texts):
            return parsed
        if len(parsed) == 1 and len(texts) == 1:
            return parsed
    except Exception:
        # Fall back to one-by-one. Some LibreTranslate builds do not accept q as a list.
        pass

    results: List[str] = []
    for text in texts:
        payload = {
            "q": text,
            "source": source_code,
            "target": target_code,
            "format": "text",
        }
        if api_key:
            payload["api_key"] = api_key
        data = request_json(
            "POST",
            endpoint + "/translate",
            json_payload=payload,
            headers=headers,
            timeout=timeout,
        )
        parsed = parse_translation_response(data, expected_count=1)
        results.append(parsed[0] if parsed else "")
    return results


def translate_with_indictrans2(
    texts: List[str],
    endpoint: str,
    target_language: str,
    source_language: str = "English",
    domain: str = "General",
    api_key: str = "",
    timeout: int = 600,
) -> List[str]:
    endpoint = normalize_indictrans2_endpoint(endpoint)
    source_code = indic_code(source_language, default="eng_Latn")
    target_code = indic_code(target_language, default="")

    if not target_code:
        raise ValueError(f"Unsupported IndicTrans2 target language: {target_language}")
    if not looks_like_url(endpoint):
        raise ValueError(f"Invalid IndicTrans2 endpoint: {endpoint}")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: Dict[str, Any] = {
        "texts": texts,
        "source_language": source_code,
        "target_language": target_code,
        "domain": domain or "General",
    }

    data = request_json(
        "POST",
        endpoint,
        json_payload=payload,
        headers=headers,
        timeout=timeout,
    )
    parsed = parse_translation_response(data, expected_count=len(texts))
    if len(parsed) == len(texts):
        return parsed

    # If worker returned a single string for multiple texts, keep alignment safe by
    # returning it for the first item and blanks for the rest instead of fabricating.
    if len(parsed) == 1 and len(texts) == 1:
        return parsed

    padded = parsed[:len(texts)]
    while len(padded) < len(texts):
        padded.append("")
    return padded


# ==========================================================
# Output validation / post-processing
# ==========================================================

def only_protected_or_blank(text: str) -> bool:
    t = clean_space(text)
    if not t:
        return True
    no_tokens = PROTECTED_RE.sub("", t)
    no_tokens = COMMON_UNIT_RE.sub("", no_tokens)
    no_tokens = EMOJI_RE.sub("", no_tokens)
    no_tokens = re.sub(r"[\s\[\]{}():;,.!?\"'`~\-–—_/\\|•∙·*]+", "", no_tokens)
    return no_tokens == ""


def contains_target_script(text: str, target_language: str) -> bool:
    t = as_text(text)
    target = clean_space(target_language).lower()

    script_ranges = {
        "arabic": r"[\u0600-\u06FF]",
        "ar": r"[\u0600-\u06FF]",
        "urdu": r"[\u0600-\u06FF]",
        "telugu": r"[\u0C00-\u0C7F]",
        "tel_telu": r"[\u0C00-\u0C7F]",
        "hindi": r"[\u0900-\u097F]",
        "hin_deva": r"[\u0900-\u097F]",
        "marathi": r"[\u0900-\u097F]",
        "malayalam": r"[\u0D00-\u0D7F]",
        "mal_mlym": r"[\u0D00-\u0D7F]",
        "tamil": r"[\u0B80-\u0BFF]",
        "tam_taml": r"[\u0B80-\u0BFF]",
        "kannada": r"[\u0C80-\u0CFF]",
        "kan_knda": r"[\u0C80-\u0CFF]",
        "bengali": r"[\u0980-\u09FF]",
        "ben_beng": r"[\u0980-\u09FF]",
        "gujarati": r"[\u0A80-\u0AFF]",
        "guj_gujr": r"[\u0A80-\u0AFF]",
        "odia": r"[\u0B00-\u0B7F]",
        "ory_orya": r"[\u0B00-\u0B7F]",
        "punjabi": r"[\u0A00-\u0A7F]",
        "pan_guru": r"[\u0A00-\u0A7F]",
    }

    code = indic_code(target_language, default="")
    key = code.lower() if code else target
    pattern = script_ranges.get(key) or script_ranges.get(target)
    if not pattern:
        return True
    return bool(re.search(pattern, t))


def is_probably_untranslated(source: str, translation: str, target_language: str) -> bool:
    src = clean_space(source)
    tgt = clean_space(translation)
    if not tgt:
        return True
    if only_protected_or_blank(tgt) and not only_protected_or_blank(src):
        return True
    if src and tgt and src.lower() == tgt.lower() and target_language.lower() not in {"english", "en", "eng_latn"}:
        return True

    # If source has alphabetic English and target is a non-Latin script language,
    # the target should usually include target script.
    if re.search(r"[A-Za-z]{3,}", src) and not contains_target_script(tgt, target_language):
        code = indic_code(target_language, default="")
        if code in INDIC_TARGET_CODES:
            return True
        if clean_space(target_language).lower() in {"arabic", "urdu"}:
            return True

    return False


def postprocess_translation(source: str, raw_translation: str, target_language: str) -> str:
    protected = mask_protected_text(source)
    # raw_translation may still contain markers because the masked source was sent.
    fixed = unmask_protected_text(raw_translation, protected, source=source)

    # If the engine translated only the marker or blanked real content, keep blank so the
    # app quality gate can block output rather than deliver placeholder-only text.
    if is_probably_untranslated(source, fixed, target_language):
        return ""

    return fixed


# ==========================================================
# Public translation functions
# ==========================================================

def self_hosted_translate_batch(
    segments: List[Dict[str, Any]],
    endpoint: str,
    provider: str,
    target_language: str,
    source_language: str = "English",
    domain: str = "General",
    api_key: str = "",
    timeout: int = 600,
    batch_size: int = 20,
) -> List[Dict[str, str]]:
    """Translate a batch through a specified self-hosted engine.

    Returns:
        [{"location": "...", "translation": "..."}, ...]
    """

    provider = (provider or "").lower().strip()
    if provider == "generic":
        provider = "indictrans2" if endpoint and (endpoint.endswith("/translate") or "8000" in endpoint) else "libretranslate"

    route = select_translation_route(
        target_language=target_language,
        source_language=source_language,
        endpoint=endpoint,
        provider=provider,
    )
    if not route:
        return [
            {
                "location": get_segment_location(seg, i),
                "translation": "",
                "error": f"No local translation route for {target_language}",
            }
            for i, seg in enumerate(segments)
        ]

    output: List[Dict[str, str]] = []

    for batch in chunks(segments, batch_size):
        locations = [get_segment_location(seg, i) for i, seg in enumerate(batch)]
        source_texts = [get_segment_source(seg) for seg in batch]

        protected_items = [mask_protected_text(text) for text in source_texts]
        masked_texts = [p.masked_text for p in protected_items]

        try:
            if route.provider == "libretranslate":
                raw_translations = translate_with_libretranslate(
                    texts=masked_texts,
                    endpoint=route.endpoint,
                    target_language=route.target_language,
                    source_language=route.source_language,
                    api_key=api_key,
                    timeout=timeout,
                )
            elif route.provider == "indictrans2":
                raw_translations = translate_with_indictrans2(
                    texts=masked_texts,
                    endpoint=route.endpoint,
                    target_language=route.target_language,
                    source_language=route.source_language,
                    domain=domain,
                    api_key=api_key,
                    timeout=timeout,
                )
            else:
                raise ValueError(f"Unsupported local translation provider: {route.provider}")
        except Exception as exc:
            raw_translations = ["" for _ in source_texts]
            for loc in locations:
                output.append({"location": loc, "translation": "", "error": str(exc)[:500]})
            continue

        while len(raw_translations) < len(source_texts):
            raw_translations.append("")

        for loc, source, raw, protected in zip(locations, source_texts, raw_translations, protected_items):
            fixed = unmask_protected_text(raw, protected, source=source)
            # Keep blank if clearly not translated; ErrorSweep should block incomplete output.
            if is_probably_untranslated(source, fixed, route.target_language):
                fixed = ""
            output.append({"location": loc, "translation": fixed})

    return output


def local_translate_batch_adapter(
    segments: List[Dict[str, Any]],
    target_language: str,
    domain: str = "General",
    source_language: str = "English",
    endpoint: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: str = "",
    libretranslate_endpoint: Optional[str] = None,
    indictrans2_endpoint: Optional[str] = None,
    timeout: int = 600,
    batch_size: int = 20,
) -> List[Dict[str, str]]:
    """Automatic ErrorSweep adapter.

    Use this from app.py instead of calling the engine directly.

    Example:
        result = local_translate_batch_adapter(
            batch,
            target_language="Telugu",
            domain="Software UI",
            source_language="English",
        )
    """

    route = select_translation_route(
        target_language=target_language,
        source_language=source_language,
        endpoint=endpoint,
        provider=provider,
        libretranslate_endpoint=libretranslate_endpoint,
        indictrans2_endpoint=indictrans2_endpoint,
    )

    if not route:
        return [
            {
                "location": get_segment_location(seg, i),
                "translation": "",
                "error": f"No translation endpoint configured for {target_language}",
            }
            for i, seg in enumerate(segments)
        ]

    return self_hosted_translate_batch(
        segments=segments,
        endpoint=route.endpoint,
        provider=route.provider,
        target_language=route.target_language,
        source_language=route.source_language,
        domain=domain,
        api_key=api_key or env_value("LOCAL_TRANSLATION_API_KEY"),
        timeout=timeout,
        batch_size=batch_size,
    )


def translate_single_text(
    text: str,
    target_language: str,
    source_language: str = "English",
    domain: str = "General",
    endpoint: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: str = "",
) -> str:
    result = local_translate_batch_adapter(
        segments=[{"location": "Text", "source": text}],
        target_language=target_language,
        source_language=source_language,
        domain=domain,
        endpoint=endpoint,
        provider=provider,
        api_key=api_key,
        batch_size=1,
    )
    return result[0].get("translation", "") if result else ""


# ==========================================================
# Coverage helper for app.py quality gates
# ==========================================================

def find_missing_or_bad_translations(
    segments: List[Dict[str, Any]],
    translations_by_location: Dict[str, str],
    target_language: str,
) -> List[Dict[str, str]]:
    missing: List[Dict[str, str]] = []
    for i, seg in enumerate(segments):
        loc = get_segment_location(seg, i)
        src = get_segment_source(seg)
        tgt = translations_by_location.get(loc, "")
        if is_probably_untranslated(src, tgt, target_language):
            missing.append({"location": loc, "source": src, "translation": tgt})
    return missing


# ==========================================================
# CLI smoke test
# ==========================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test ErrorSweep local translation engine.")
    parser.add_argument("--text", default="How are you?")
    parser.add_argument("--target", default="French")
    parser.add_argument("--source", default="English")
    parser.add_argument("--provider", default="")
    parser.add_argument("--endpoint", default="")
    args = parser.parse_args()

    print(
        translate_single_text(
            text=args.text,
            source_language=args.source,
            target_language=args.target,
            provider=args.provider or None,
            endpoint=args.endpoint or None,
        )
    )

