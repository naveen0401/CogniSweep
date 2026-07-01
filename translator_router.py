"""CogniSweep managed machine-translation routing."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app_runtime_config import cognisweep_env_alias, runtime_env

LOGGER = logging.getLogger(__name__)


class TranslationRouteError(RuntimeError):
    """Raised when no managed MT provider is available for a translation run."""


LANGUAGE_CODE_MAP = {
    "afrikaans": "af",
    "albanian": "sq",
    "amharic": "am",
    "arabic": "ar",
    "armenian": "hy",
    "azerbaijani": "az",
    "bengali": "bn",
    "bosnian": "bs",
    "bulgarian": "bg",
    "burmese": "my",
    "catalan": "ca",
    "chinese": "zh",
    "chinese simplified": "zh",
    "chinese traditional": "zh-TW",
    "croatian": "hr",
    "czech": "cs",
    "danish": "da",
    "dari": "fa-AF",
    "dutch": "nl",
    "english": "en",
    "estonian": "et",
    "farsi": "fa",
    "persian": "fa",
    "finnish": "fi",
    "french": "fr",
    "french canada": "fr-CA",
    "georgian": "ka",
    "german": "de",
    "greek": "el",
    "gujarati": "gu",
    "haitian creole": "ht",
    "hausa": "ha",
    "hebrew": "he",
    "hindi": "hi",
    "hungarian": "hu",
    "icelandic": "is",
    "indonesian": "id",
    "italian": "it",
    "japanese": "ja",
    "kannada": "kn",
    "kazakh": "kk",
    "korean": "ko",
    "latvian": "lv",
    "lithuanian": "lt",
    "macedonian": "mk",
    "malay": "ms",
    "malayalam": "ml",
    "maltese": "mt",
    "marathi": "mr",
    "mongolian": "mn",
    "norwegian": "no",
    "pashto": "ps",
    "polish": "pl",
    "portuguese": "pt",
    "punjabi": "pa",
    "romanian": "ro",
    "russian": "ru",
    "serbian": "sr",
    "sinhala": "si",
    "slovak": "sk",
    "slovenian": "sl",
    "somali": "so",
    "spanish": "es",
    "swahili": "sw",
    "swedish": "sv",
    "tagalog": "tl",
    "tamil": "ta",
    "telugu": "te",
    "thai": "th",
    "turkish": "tr",
    "ukrainian": "uk",
    "urdu": "ur",
    "uzbek": "uz",
    "vietnamese": "vi",
    "welsh": "cy",
    "yiddish": "yi",
    "yoruba": "yo",
    "zulu": "zu",
}


def _env_value(name: str, default: str = "") -> str:
    value = runtime_env(name, "")
    if value:
        return value
    alias = cognisweep_env_alias(name)
    if alias:
        value = runtime_env(alias, "")
        if value:
            return value
    return default


def mt_provider() -> str:
    return (_env_value("ERRORSWEEP_MT_PROVIDER", _env_value("COGNISWEEP_MT_PROVIDER", "disabled")) or "disabled").strip().lower()


def amazon_translate_region() -> str:
    return (
        _env_value("ERRORSWEEP_AWS_TRANSLATE_REGION")
        or _env_value("COGNISWEEP_AWS_TRANSLATE_REGION")
        or _env_value("AWS_REGION")
        or _env_value("AWS_DEFAULT_REGION")
        or "ap-south-1"
    ).strip()


def amazon_terminology_names() -> List[str]:
    raw = _env_value("ERRORSWEEP_AWS_TRANSLATE_TERMINOLOGY_NAMES", _env_value("COGNISWEEP_AWS_TRANSLATE_TERMINOLOGY_NAMES", ""))
    return [item.strip() for item in raw.replace(";", ",").split(",") if item.strip()]


def normalize_language_code(language: str, *, default: str = "") -> str:
    value = str(language or "").strip()
    if not value:
        return default
    lowered = value.lower().replace("_", "-")
    if lowered in {"auto", "auto-detect", "autodetect", "detect"}:
        return "auto"
    if lowered in LANGUAGE_CODE_MAP:
        return LANGUAGE_CODE_MAP[lowered]
    compact = lowered.split("(", 1)[0].strip()
    if compact in LANGUAGE_CODE_MAP:
        return LANGUAGE_CODE_MAP[compact]
    if 2 <= len(value) <= 8 and all(ch.isalpha() or ch == "-" for ch in value):
        return value
    return default


def amazon_translate_ready() -> Tuple[bool, str]:
    if mt_provider() != "amazon_translate":
        return False, "COGNISWEEP_MT_PROVIDER/ERRORSWEEP_MT_PROVIDER is not amazon_translate"
    try:
        import boto3  # noqa: F401
    except ImportError:
        return False, "boto3 is not installed"
    if not amazon_translate_region():
        return False, "AWS Translate region is not configured"
    return True, "configured"


def estimate_characters(texts: List[str]) -> int:
    return sum(len(str(text or "")) for text in texts)


def current_builtin_engine_label() -> str:
    ready, detail = amazon_translate_ready()
    if ready:
        return f"Amazon Translate ({amazon_translate_region()})"
    return f"Managed MT not configured; Human Review mode active ({detail})"


def builtin_engine_status(timeout: int = 3) -> List[Dict[str, Any]]:
    _ = timeout
    ready, detail = amazon_translate_ready()
    return [
        {
            "engine": "Amazon Translate",
            "provider": "amazon_translate",
            "enabled": mt_provider() == "amazon_translate",
            "ready": ready,
            "detail": detail,
            "region": amazon_translate_region(),
            "priority": "Managed AWS MT route",
        }
    ]


def smoke_test_builtin_engines(timeout: int = 120) -> List[Dict[str, Any]]:
    ready, detail = amazon_translate_ready()
    if not ready:
        return [
            {
                "engine": "Amazon Translate",
                "success": False,
                "translation": "",
                "error": detail,
            }
        ]
    try:
        translations, usage = translate_batch(
            source_language="en",
            target_language="fr",
            texts=["Hello"],
            metadata={"smoke_test": True, "timeout": timeout},
        )
        return [
            {
                "engine": "Amazon Translate",
                "success": bool(translations and translations[0]),
                "translation": translations[0] if translations else "",
                "error": usage.get("error", ""),
            }
        ]
    except Exception as exc:
        return [{"engine": "Amazon Translate", "success": False, "translation": "", "error": str(exc)[:700]}]


def _amazon_translate_client() -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise TranslationRouteError("boto3 is required for Amazon Translate. Install requirements.txt.") from exc
    return boto3.client("translate", region_name=amazon_translate_region())


def _translate_text_with_amazon(client: Any, text: str, source_code: str, target_code: str, terminology_names: List[str]) -> str:
    payload: Dict[str, Any] = {
        "Text": text,
        "SourceLanguageCode": source_code,
        "TargetLanguageCode": target_code,
    }
    if terminology_names:
        payload["TerminologyNames"] = terminology_names
    response = client.translate_text(**payload)
    return str(response.get("TranslatedText") or "")


def translate_with_amazon_translate(
    *,
    source_language: str,
    target_language: str,
    texts: List[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    normalized_texts = ["" if text is None else str(text) for text in texts]
    target_code = normalize_language_code(target_language)
    if not target_code or target_code == "auto":
        raise TranslationRouteError(f"Amazon Translate target language is not supported: {target_language or 'missing'}")
    source_code = normalize_language_code(source_language, default="auto") or "auto"
    terminology_names = amazon_terminology_names()
    client = _amazon_translate_client()
    translations: List[str] = []
    requests = 0
    for text in normalized_texts:
        if not text.strip():
            translations.append("")
            continue
        translations.append(_translate_text_with_amazon(client, text, source_code, target_code, terminology_names))
        requests += 1
    usage = {
        "provider": "amazon_translate",
        "engine": "amazon_translate",
        "model": "amazon_translate",
        "managed": True,
        "billable": True,
        "usage_kind": "managed_mt",
        "characters": estimate_characters(normalized_texts),
        "requests": requests,
        "success": True,
        "error": "",
        "source_language": source_code,
        "target_language": target_code,
        "region": amazon_translate_region(),
        "terminology_names": terminology_names,
        "metadata": metadata or {},
    }
    return translations, usage


def translate_batch(
    *,
    source_language: str,
    target_language: str,
    texts: List[str],
    user_api_key: str = "",
    protected_terms: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    _ = (user_api_key, protected_terms)
    normalized_texts = ["" if text is None else str(text) for text in texts]
    if not normalized_texts:
        usage = {
            "provider": "managed_mt",
            "engine": mt_provider(),
            "managed": True,
            "characters": 0,
            "requests": 0,
            "success": True,
            "error": "",
            "metadata": metadata or {},
        }
        usage["success"] = True
        return [], usage
    provider = mt_provider()
    if provider == "amazon_translate":
        try:
            return translate_with_amazon_translate(
                source_language=source_language,
                target_language=target_language,
                texts=normalized_texts,
                metadata=metadata,
            )
        except Exception as exc:
            LOGGER.warning("Amazon Translate route failed: %s", exc)
            raise TranslationRouteError(str(exc)) from exc
    usage = {
        "provider": "managed_mt",
        "engine": provider or "disabled",
        "managed": True,
        "characters": estimate_characters(normalized_texts),
        "requests": 0,
        "success": False,
        "error": "Managed MT is disabled; use BYO AI or Human Review.",
        "metadata": metadata or {},
    }
    raise TranslationRouteError(str(usage["error"]))
