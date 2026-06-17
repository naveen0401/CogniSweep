"""
CogniSweep local/self-hosted translation adapter v15.

Key guarantees for localization files:
- Curly placeholders / variables / tags / URLs / emails are preserved by the app-level guard.
- Leading bullets and emoji/icons are preserved exactly, but the following UI text is translated.
- Whole square-bracket UI labels can be localized inside the brackets: [Log In] -> [Connexion].
- Output is never intentionally logged or stored by this adapter.
- Unsupported public translation fallback routing is intentionally not present.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

LOGGER = logging.getLogger(__name__)


LANGUAGE_CODE_MAP = {
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
    "malayalam": "ml", "ml": "ml",
    "kannada": "kn", "kn": "kn",
    "bengali": "bn", "bangla": "bn", "bn": "bn",
    "urdu": "ur", "ur": "ur",
}

PROTECTED_INLINE_RE = re.compile(
    r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$[A-Za-z_][\w]*|<[^>]+>|https?://[^\s]+|www\.[^\s]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})"
)
COMMON_UNIT_RE = re.compile(r"\b(kcal|mins?|sec(?:onds?)?|hrs?|kg|g|mg|km|m|cm|mm|mb|gb|tb|kb|fps|dpi|px|%|°c|°f)\b", re.I)
# Leading visual markers that should be preserved exactly, not translated.
LEADING_VISUAL_RE = re.compile(r"^(\s*(?:(?:[•∙◦▪▫●○\-–—*]+)|(?:[\U0001F300-\U0001FAFF\u2600-\u27BF]\ufe0f?))+\s*)")
TRAILING_BULLET_RE = re.compile(r"(\s*[•∙◦▪▫●○]+\s*)+$")
LOCALIZABLE_BRACKET_RE = re.compile(r"^\[([^\[\]\n]{1,180})\]$")


def normalize_language_code(language: str) -> str:
    value = (language or "").strip().lower()
    if not value:
        return "en"
    short = re.split(r"[-_ ]", value)[0]
    if value in LANGUAGE_CODE_MAP:
        return LANGUAGE_CODE_MAP[value]
    if short in LANGUAGE_CODE_MAP:
        return LANGUAGE_CODE_MAP[short]
    if re.fullmatch(r"[a-z]{2,3}", value):
        return value
    return value


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 60, headers: Optional[Dict[str, str]] = None) -> Any:
    response = requests.post(url, json=payload, headers=headers or {}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _prepare_engine_source(source: str) -> Tuple[str, Dict[str, Any]]:
    """Strip visual UI wrappers before machine translation and store metadata.

    This avoids engines leaving short UI labels untranslated, e.g.:
    - ∙Dashboard -> translate Dashboard -> restore ∙
    - 🏠 Home -> translate Home -> restore 🏠
    - [Welcome Screen] -> translate Welcome Screen -> restore brackets
    """
    original = str(source or "")
    text = original.strip()
    meta: Dict[str, Any] = {"prefix": "", "bracketed": False, "original": original}

    visual = LEADING_VISUAL_RE.match(text)
    if visual:
        meta["prefix"] = visual.group(1)
        text = text[visual.end():].lstrip()

    bracket = LOCALIZABLE_BRACKET_RE.fullmatch(text.strip())
    if bracket:
        meta["bracketed"] = True
        text = bracket.group(1).strip()

    # If the remaining core is empty, use original so we do not create blanks.
    return (text or original), meta


def _restore_visual_wrapper(translation: str, meta: Dict[str, Any]) -> str:
    out = str(translation or "").strip()
    out = re.sub(r"^\s*[ÂÃ]\s*", "", out).strip()
    # Some MT engines duplicate list bullets at the end.
    out = TRAILING_BULLET_RE.sub("", out).strip()

    if meta.get("bracketed") and out and not (out.startswith("[") and out.endswith("]")):
        out = f"[{out.strip('[] ')}]"

    prefix = str(meta.get("prefix") or "")
    if prefix:
        stripped = prefix.strip()
        if stripped and not out.startswith(stripped):
            out = prefix + out.lstrip()
    return out


def _restore_safety(source: str, translation: str) -> str:
    """Final safety restore for tokens that must survive translation."""
    source = str(source or "")
    out = str(translation or "")

    # Restore app-level protected marker variants into original tokens if possible.
    # The app performs a second restore with the true original segment, so this is a local safety net.
    tokens: List[str] = []
    tokens.extend(PROTECTED_INLINE_RE.findall(source))
    tokens.extend([m.group(0) for m in COMMON_UNIT_RE.finditer(source)])

    for idx, token in enumerate(tokens):
        marker_re = re.compile(rf"(?i)[_\s]*(?:P\s*H\s*{idx:03d}\s*T\s*O\s*K\s*E\s*N|E\s*S\s*P\s*H\s*{idx}|Z\s*X\s*P\s*H\s*{idx}\s*Z\s*X|ZXPH\s*{idx}\s*ZX)[_\s]*")
        out = marker_re.sub(token, out)
        if token and token not in out:
            out = (out.rstrip() + " " + token).strip()
    return out


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
    provider = (provider or "generic").strip().lower()
    if provider in {"custom", "endpoint", "self-hosted", "self_hosted"}:
        provider = "generic"
    endpoint = (endpoint or "").strip()
    if not endpoint:
        return [{"location": s.get("location", ""), "translation": ""} for s in segments]

    original_texts = [str(s.get("source") or s.get("text") or "") for s in segments]
    locations = [str(s.get("location", "")) for s in segments]
    prepared = [_prepare_engine_source(t) for t in original_texts]
    engine_texts = [p[0] for p in prepared]
    metas = [p[1] for p in prepared]

    translations: List[str] = []
    if provider == "generic":
        translations = translate_with_generic_endpoint(
            endpoint=endpoint,
            texts=engine_texts,
            target_language=target_language,
            source_language=source_language,
            domain=domain,
            api_key=api_key,
            timeout=timeout,
        )
    else:
        LOGGER.warning("Unsupported self-hosted translation provider '%s'; use provider='generic'.", provider)
        translations = [""] * len(engine_texts)

    if len(translations) < len(segments):
        translations.extend([""] * (len(segments) - len(translations)))

    output: List[Dict[str, str]] = []
    for loc, src, trans, meta in zip(locations, original_texts, translations, metas):
        fixed = _restore_visual_wrapper(trans or "", meta)
        fixed = _restore_safety(src, fixed)
        output.append({"location": loc, "translation": fixed})
    return output
