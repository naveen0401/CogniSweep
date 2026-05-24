"""
ErrorSweep v44 built-in translation router.

Commercial-safe self-hosted MT route:
- IndicTrans2 endpoint for Indian languages
- OPUS-MT endpoint for selected non-Indian/global pairs
- NLLB removed
- Azure removed

The app calls translate_batch(...) from this module. Keep this public API stable.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

try:
    import streamlit as st
except Exception:
    st = None

from selfhosted_mt_clients import (
    TranslationRouteError,
    estimate_characters,
    translate_with_indictrans2,
    translate_with_opus_mt,
)

INDIC_LANGS = {
    "asm_Beng", "ben_Beng", "brx_Deva", "doi_Deva", "gom_Deva", "guj_Gujr",
    "hin_Deva", "kan_Knda", "kas_Arab", "kas_Deva", "mai_Deva", "mal_Mlym",
    "mar_Deva", "mni_Beng", "mni_Mtei", "npi_Deva", "ory_Orya", "pan_Guru",
    "san_Deva", "sat_Olck", "snd_Arab", "snd_Deva", "tam_Taml", "tel_Telu",
    "urd_Arab",
}

LANGUAGE_MAP: Dict[str, Dict[str, str]] = {
    "english": {"iso": "en", "indic": "eng_Latn"}, "en": {"iso": "en", "indic": "eng_Latn"}, "eng_latn": {"iso": "en", "indic": "eng_Latn"},
    "telugu": {"iso": "te", "indic": "tel_Telu"}, "te": {"iso": "te", "indic": "tel_Telu"}, "tel_telu": {"iso": "te", "indic": "tel_Telu"},
    "hindi": {"iso": "hi", "indic": "hin_Deva"}, "hi": {"iso": "hi", "indic": "hin_Deva"}, "hin_deva": {"iso": "hi", "indic": "hin_Deva"},
    "tamil": {"iso": "ta", "indic": "tam_Taml"}, "ta": {"iso": "ta", "indic": "tam_Taml"}, "tam_taml": {"iso": "ta", "indic": "tam_Taml"},
    "kannada": {"iso": "kn", "indic": "kan_Knda"}, "kn": {"iso": "kn", "indic": "kan_Knda"}, "kan_knda": {"iso": "kn", "indic": "kan_Knda"},
    "malayalam": {"iso": "ml", "indic": "mal_Mlym"}, "ml": {"iso": "ml", "indic": "mal_Mlym"}, "mal_mlym": {"iso": "ml", "indic": "mal_Mlym"},
    "marathi": {"iso": "mr", "indic": "mar_Deva"}, "mr": {"iso": "mr", "indic": "mar_Deva"}, "mar_deva": {"iso": "mr", "indic": "mar_Deva"},
    "bengali": {"iso": "bn", "indic": "ben_Beng"}, "bangla": {"iso": "bn", "indic": "ben_Beng"}, "bn": {"iso": "bn", "indic": "ben_Beng"}, "ben_beng": {"iso": "bn", "indic": "ben_Beng"},
    "gujarati": {"iso": "gu", "indic": "guj_Gujr"}, "gu": {"iso": "gu", "indic": "guj_Gujr"}, "guj_gujr": {"iso": "gu", "indic": "guj_Gujr"},
    "punjabi": {"iso": "pa", "indic": "pan_Guru"}, "pa": {"iso": "pa", "indic": "pan_Guru"}, "pan_guru": {"iso": "pa", "indic": "pan_Guru"},
    "urdu": {"iso": "ur", "indic": "urd_Arab"}, "ur": {"iso": "ur", "indic": "urd_Arab"}, "urd_arab": {"iso": "ur", "indic": "urd_Arab"},
    "odia": {"iso": "or", "indic": "ory_Orya"}, "oriya": {"iso": "or", "indic": "ory_Orya"}, "or": {"iso": "or", "indic": "ory_Orya"}, "ory_orya": {"iso": "or", "indic": "ory_Orya"},
    "assamese": {"iso": "as", "indic": "asm_Beng"}, "as": {"iso": "as", "indic": "asm_Beng"}, "asm_beng": {"iso": "as", "indic": "asm_Beng"},
    "nepali": {"iso": "ne", "indic": "npi_Deva"}, "ne": {"iso": "ne", "indic": "npi_Deva"}, "npi_deva": {"iso": "ne", "indic": "npi_Deva"},
    "sanskrit": {"iso": "sa", "indic": "san_Deva"}, "sa": {"iso": "sa", "indic": "san_Deva"}, "san_deva": {"iso": "sa", "indic": "san_Deva"},
    "french": {"iso": "fr", "indic": ""}, "fr": {"iso": "fr", "indic": ""},
    "german": {"iso": "de", "indic": ""}, "de": {"iso": "de", "indic": ""},
    "spanish": {"iso": "es", "indic": ""}, "es": {"iso": "es", "indic": ""},
    "italian": {"iso": "it", "indic": ""}, "it": {"iso": "it", "indic": ""},
    "portuguese": {"iso": "pt", "indic": ""}, "pt": {"iso": "pt", "indic": ""},
    "russian": {"iso": "ru", "indic": ""}, "ru": {"iso": "ru", "indic": ""},
    "arabic": {"iso": "ar", "indic": ""}, "ar": {"iso": "ar", "indic": ""},
    "chinese": {"iso": "zh", "indic": ""}, "zh": {"iso": "zh", "indic": ""},
    "japanese": {"iso": "ja", "indic": ""}, "ja": {"iso": "ja", "indic": ""},
    "korean": {"iso": "ko", "indic": ""}, "ko": {"iso": "ko", "indic": ""},
}


def _secret(name: str, default: str = "") -> str:
    env = os.environ.get(name)
    if env not in (None, ""):
        return str(env)
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
    return value in {"1", "true", "yes", "on", "enabled"}


def normalize_language(language: str) -> Dict[str, str]:
    raw = (language or "").strip()
    key = raw.lower().replace("-", "_")
    if key in LANGUAGE_MAP:
        return LANGUAGE_MAP[key]
    if "_" in raw and len(raw) >= 7:
        return {"iso": raw.split("_", 1)[0].lower(), "indic": raw}
    return {"iso": key[:2] if key else "en", "indic": ""}


def is_indic_language(language: str) -> bool:
    return normalize_language(language).get("indic", "") in INDIC_LANGS


def current_builtin_engine_label() -> str:
    if _secret("INDICTRANS2_ENDPOINT", "") or _secret("OPUS_MT_ENDPOINT", ""):
        return "Included self-hosted MT active"
    return "Self-hosted MT not configured"


def translate_batch(
    *,
    source_language: str,
    target_language: str,
    texts: List[str],
    user_api_key: str = "",
    protected_terms: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    texts = ["" if t is None else str(t) for t in texts]
    protected_terms = protected_terms or []
    metadata = metadata or {}
    usage: Dict[str, Any] = {
        "provider": "self_hosted_mt",
        "engine": "self_hosted_mt",
        "managed": True,
        "characters": estimate_characters(texts),
        "requests": 0,
        "success": False,
        "error": "",
        "metadata": metadata,
    }
    if not texts:
        usage["success"] = True
        return [], usage

    source_info = normalize_language(source_language or "English")
    target_info = normalize_language(target_language)
    should_use_indic = is_indic_language(source_language) or is_indic_language(target_language) or bool(target_info.get("indic"))

    try:
        if should_use_indic and not _bool_secret("SELF_HOSTED_MT_DISABLE_INDIC", False):
            endpoint = _secret("INDICTRANS2_ENDPOINT", "")
            if not endpoint:
                raise TranslationRouteError("Self-hosted IndicTrans2 endpoint is not configured. Add INDICTRANS2_ENDPOINT in Streamlit Secrets.")
            translations, engine_usage = translate_with_indictrans2(
                endpoint=endpoint,
                api_key=_secret("INDICTRANS2_API_KEY", ""),
                source_language=source_info.get("indic") or "eng_Latn",
                target_language=target_info.get("indic") or target_language,
                texts=texts,
                protected_terms=protected_terms,
                timeout=int(_secret("SELF_HOSTED_MT_TIMEOUT", "180")),
            )
            usage.update(engine_usage)
            usage["provider"] = "indictrans2"
            usage["engine"] = engine_usage.get("engine", "indictrans2")
            usage["success"] = True
            return translations, usage

        if not _bool_secret("SELF_HOSTED_MT_DISABLE_OPUS", False):
            endpoint = _secret("OPUS_MT_ENDPOINT", "")
            if not endpoint:
                raise TranslationRouteError("Self-hosted OPUS-MT endpoint is not configured. Add OPUS_MT_ENDPOINT in Streamlit Secrets.")
            translations, engine_usage = translate_with_opus_mt(
                endpoint=endpoint,
                api_key=_secret("OPUS_MT_API_KEY", ""),
                source_language=source_info.get("iso", "en"),
                target_language=target_info.get("iso") or target_language,
                texts=texts,
                protected_terms=protected_terms,
                timeout=int(_secret("SELF_HOSTED_MT_TIMEOUT", "180")),
            )
            usage.update(engine_usage)
            usage["provider"] = "opus_mt"
            usage["engine"] = engine_usage.get("engine", "opus_mt")
            usage["success"] = True
            return translations, usage

        raise TranslationRouteError("No self-hosted MT route is enabled.")
    except Exception as exc:
        usage["success"] = False
        usage["error"] = str(exc)
        raise

