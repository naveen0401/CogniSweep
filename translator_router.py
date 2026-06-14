"""
CogniSweep built-in translation router.

Commercial-safe self-hosted MT route:
- IndicTrans2 endpoint for Indian languages
- OPUS-MT endpoint for selected lightweight global pairs
- MADLAD-400 remains available only when explicitly enabled
- NLLB removed
- Azure removed

The app calls translate_batch(...) from this module. Keep this public API stable.
"""
from __future__ import annotations

import os
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Set

import requests

LOGGER = logging.getLogger(__name__)

try:
    import streamlit as st
except Exception as exc:
    LOGGER.debug("Streamlit is unavailable in translation router context: %s", exc)
    st = None

from selfhosted_mt_clients import (
    TranslationRouteError,
    estimate_characters,
    protect_text,
    restore_text,
    translate_with_indictrans2,
    translate_with_madlad,
    translate_with_opus_mt,
)

INDIC_LANGS = {
    "asm_Beng", "ben_Beng", "brx_Deva", "doi_Deva", "gom_Deva", "guj_Gujr",
    "hin_Deva", "kan_Knda", "kas_Arab", "kas_Deva", "mai_Deva", "mal_Mlym",
    "mar_Deva", "mni_Beng", "mni_Mtei", "npi_Deva", "ory_Orya", "pan_Guru",
    "san_Deva", "sat_Olck", "snd_Arab", "snd_Deva", "tam_Taml", "tel_Telu",
    "urd_Arab",
}

DEFAULT_OPUS_MT_ENDPOINT = "http://127.0.0.1:8100/translate"
DEFAULT_MADLAD_ENDPOINT = "http://127.0.0.1:8200/translate"
DEFAULT_INDICTRANS2_ENDPOINT = "http://127.0.0.1:8000/translate"
DEFAULT_ACTIVE_MT_ENGINES = "indictrans2,opus"

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
    "dutch": {"iso": "nl", "indic": ""}, "nl": {"iso": "nl", "indic": ""},
    "polish": {"iso": "pl", "indic": ""}, "pl": {"iso": "pl", "indic": ""},
    "swedish": {"iso": "sv", "indic": ""}, "sv": {"iso": "sv", "indic": ""},
    "norwegian": {"iso": "no", "indic": ""}, "no": {"iso": "no", "indic": ""},
    "danish": {"iso": "da", "indic": ""}, "da": {"iso": "da", "indic": ""},
    "greek": {"iso": "el", "indic": ""}, "el": {"iso": "el", "indic": ""},
    "russian": {"iso": "ru", "indic": ""}, "ru": {"iso": "ru", "indic": ""},
    "ukrainian": {"iso": "uk", "indic": ""}, "uk": {"iso": "uk", "indic": ""},
    "arabic": {"iso": "ar", "indic": ""}, "ar": {"iso": "ar", "indic": ""},
    "hebrew": {"iso": "he", "indic": ""}, "he": {"iso": "he", "indic": ""},
    "persian": {"iso": "fa", "indic": ""}, "farsi": {"iso": "fa", "indic": ""}, "fa": {"iso": "fa", "indic": ""},
    "turkish": {"iso": "tr", "indic": ""}, "tr": {"iso": "tr", "indic": ""},
    "swahili": {"iso": "sw", "indic": ""}, "kiswahili": {"iso": "sw", "indic": ""}, "sw": {"iso": "sw", "indic": ""},
    "amharic": {"iso": "am", "indic": ""}, "am": {"iso": "am", "indic": ""},
    "yoruba": {"iso": "yo", "indic": ""}, "yo": {"iso": "yo", "indic": ""},
    "hausa": {"iso": "ha", "indic": ""}, "ha": {"iso": "ha", "indic": ""},
    "zulu": {"iso": "zu", "indic": ""}, "isizulu": {"iso": "zu", "indic": ""}, "zu": {"iso": "zu", "indic": ""},
    "afrikaans": {"iso": "af", "indic": ""}, "af": {"iso": "af", "indic": ""},
    "chinese": {"iso": "zh", "indic": ""}, "zh": {"iso": "zh", "indic": ""},
    "mandarin chinese": {"iso": "zh", "indic": ""},
    "mandarin chinese (simplified)": {"iso": "zh", "indic": ""},
    "mandarin chinese (traditional)": {"iso": "zh", "indic": ""},
    "simplified chinese": {"iso": "zh", "indic": ""},
    "traditional chinese": {"iso": "zh", "indic": ""},
    "japanese": {"iso": "ja", "indic": ""}, "ja": {"iso": "ja", "indic": ""},
    "korean": {"iso": "ko", "indic": ""}, "ko": {"iso": "ko", "indic": ""},
    "vietnamese": {"iso": "vi", "indic": ""}, "vi": {"iso": "vi", "indic": ""},
    "thai": {"iso": "th", "indic": ""}, "th": {"iso": "th", "indic": ""},
    "indonesian": {"iso": "id", "indic": ""}, "bahasa indonesia": {"iso": "id", "indic": ""}, "id": {"iso": "id", "indic": ""},
    "malay": {"iso": "ms", "indic": ""}, "bahasa melayu": {"iso": "ms", "indic": ""}, "ms": {"iso": "ms", "indic": ""},
    "tagalog": {"iso": "tl", "indic": ""}, "tagalog / filipino": {"iso": "tl", "indic": ""}, "tagalog filipino": {"iso": "tl", "indic": ""}, "filipino": {"iso": "tl", "indic": ""}, "tl": {"iso": "tl", "indic": ""}, "fil": {"iso": "tl", "indic": ""},
    "burmese": {"iso": "my", "indic": ""}, "myanmar": {"iso": "my", "indic": ""}, "my": {"iso": "my", "indic": ""},
    "khmer": {"iso": "km", "indic": ""}, "cambodian": {"iso": "km", "indic": ""}, "km": {"iso": "km", "indic": ""},
    "lao": {"iso": "lo", "indic": ""}, "lo": {"iso": "lo", "indic": ""},
    "sinhala": {"iso": "si", "indic": ""}, "si": {"iso": "si", "indic": ""},
    "mongolian": {"iso": "mn", "indic": ""}, "mn": {"iso": "mn", "indic": ""},
}


def _secret(name: str, default: str = "") -> str:
    env = os.environ.get(name)
    if env not in (None, ""):
        return str(env)
    if st is not None:
        try:
            value = st.session_state.get(name)
            if value not in (None, ""):
                return str(value)
        except Exception as exc:
            LOGGER.debug("Unable to read Streamlit session value %s: %s", name, exc)
        try:
            value = st.secrets.get(name)
            if value not in (None, ""):
                return str(value)
        except Exception as exc:
            LOGGER.debug("Unable to read Streamlit secret %s: %s", name, exc)
    return default


def _bool_secret(name: str, default: bool = False) -> bool:
    value = _secret(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on", "enabled"}


def _is_production() -> bool:
    env = _secret("ERRORSWEEP_ENV", _secret("APP_ENV", "")).strip().lower()
    return env in {"prod", "production"}


def _active_engine_names() -> Set[str]:
    configured = _secret("SELF_HOSTED_MT_ACTIVE_ENGINES", DEFAULT_ACTIVE_MT_ENGINES).strip().lower()
    if configured in {"*", "all"}:
        return {"indictrans2", "opus", "madlad"}
    aliases = {
        "indic": "indictrans2",
        "indictrans": "indictrans2",
        "indictrans2": "indictrans2",
        "opus": "opus",
        "opus-mt": "opus",
        "opus_mt": "opus",
        "madlad": "madlad",
        "madlad400": "madlad",
        "madlad-400": "madlad",
    }
    active: Set[str] = set()
    for raw_name in re.split(r"[,;\s]+", configured):
        name = aliases.get(raw_name.strip())
        if name:
            active.add(name)
    return active or {"indictrans2", "opus"}


def _engine_enabled(engine: str, disable_env: str) -> bool:
    return engine in _active_engine_names() and not _bool_secret(disable_env, False)


def _indic_in_process_fallback_enabled() -> bool:
    return _bool_secret("INDICTRANS2_IN_PROCESS_FALLBACK", not _is_production())


def normalize_language(language: str) -> Dict[str, str]:
    raw = (language or "").strip()
    key = raw.lower().replace("-", "_")
    if key in LANGUAGE_MAP:
        return LANGUAGE_MAP[key]
    space_key = key.replace("_", " ")
    if space_key in LANGUAGE_MAP:
        return LANGUAGE_MAP[space_key]
    paren_key = re.sub(r"\s*\([^)]*\)", "", space_key).strip()
    if paren_key in LANGUAGE_MAP:
        return LANGUAGE_MAP[paren_key]
    compact_key = re.sub(r"\s*/\s*", " ", space_key).strip()
    if compact_key in LANGUAGE_MAP:
        return LANGUAGE_MAP[compact_key]
    if "_" in raw and len(raw) >= 7:
        return {"iso": raw.split("_", 1)[0].lower(), "indic": raw}
    return {"iso": key[:2] if key else "en", "indic": ""}


def is_indic_language(language: str) -> bool:
    return normalize_language(language).get("indic", "") in INDIC_LANGS


def current_builtin_engine_label() -> str:
    enabled = []
    if _engine_enabled("indictrans2", "SELF_HOSTED_MT_DISABLE_INDIC"):
        enabled.append("IndicTrans2")
    if _engine_enabled("opus", "SELF_HOSTED_MT_DISABLE_OPUS"):
        enabled.append("OPUS-MT")
    if _engine_enabled("madlad", "SELF_HOSTED_MT_DISABLE_MADLAD"):
        enabled.append("MADLAD-400")
    if enabled:
        return "Included self-hosted MT active: " + " + ".join(enabled)
    return "Self-hosted MT not configured"


def _endpoint_health_url(endpoint: str) -> str:
    endpoint = (endpoint or "").strip().rstrip("/")
    return endpoint[:-10] + "/health" if endpoint.endswith("/translate") else endpoint + "/health"


def builtin_engine_status(timeout: int = 3) -> List[Dict[str, Any]]:
    engines = [
        {
            "engine": "IndicTrans2",
            "endpoint": _secret("INDICTRANS2_ENDPOINT", DEFAULT_INDICTRANS2_ENDPOINT),
            "enabled": _engine_enabled("indictrans2", "SELF_HOSTED_MT_DISABLE_INDIC"),
            "priority": "Indian languages",
        },
        {
            "engine": "OPUS-MT",
            "endpoint": _secret("OPUS_MT_ENDPOINT", DEFAULT_OPUS_MT_ENDPOINT),
            "enabled": _engine_enabled("opus", "SELF_HOSTED_MT_DISABLE_OPUS"),
            "priority": "Lightweight global fallback",
        },
        {
            "engine": "MADLAD-400",
            "endpoint": _secret("MADLAD_ENDPOINT", DEFAULT_MADLAD_ENDPOINT),
            "enabled": _engine_enabled("madlad", "SELF_HOSTED_MT_DISABLE_MADLAD"),
            "priority": "Optional broad fallback",
        },
    ]
    rows: List[Dict[str, Any]] = []
    for item in engines:
        row = dict(item)
        row["ready"] = False
        row["detail"] = "disabled" if not item["enabled"] else "not checked"
        if item["enabled"] and item["endpoint"]:
            try:
                res = requests.get(_endpoint_health_url(item["endpoint"]), timeout=timeout)
                row["ready"] = res.status_code < 400
                row["detail"] = res.json() if row["ready"] else f"HTTP {res.status_code}"
            except Exception as exc:
                row["detail"] = str(exc)[:220]
                if item["engine"] == "IndicTrans2" and _indic_in_process_fallback_enabled():
                    try:
                        import indictrans2_worker

                        models = {
                            "en_indic": indictrans2_worker.model_status(indictrans2_worker.MODEL_EN_INDIC),
                            "indic_en": indictrans2_worker.model_status(indictrans2_worker.MODEL_INDIC_EN),
                            "indic_indic": indictrans2_worker.model_status(indictrans2_worker.MODEL_INDIC_INDIC),
                        }
                        local_ready = all(
                            model["local_path"] and model["has_config"]
                            for model in models.values()
                        )
                        row["ready"] = local_ready
                        row["detail"] = {
                            "http": row["detail"],
                            "in_process_fallback": "ready" if local_ready else "not ready",
                            "models": models,
                        }
                    except Exception as fallback_exc:
                        row["detail"] = f"{row['detail']} | in-process fallback: {fallback_exc}"
        rows.append(row)
    return rows


def smoke_test_builtin_engines(timeout: int = 120) -> List[Dict[str, Any]]:
    tests = [
        {
            "engine": "IndicTrans2",
            "endpoint": _secret("INDICTRANS2_ENDPOINT", DEFAULT_INDICTRANS2_ENDPOINT),
            "api_key": _secret("INDICTRANS2_API_KEY", ""),
            "source_language": "eng_Latn",
            "target_language": "tel_Telu",
            "texts": ["Save changes"],
            "enabled": _engine_enabled("indictrans2", "SELF_HOSTED_MT_DISABLE_INDIC"),
        },
        {
            "engine": "OPUS-MT",
            "endpoint": _secret("OPUS_MT_ENDPOINT", DEFAULT_OPUS_MT_ENDPOINT),
            "api_key": _secret("OPUS_MT_API_KEY", ""),
            "source_language": "English",
            "target_language": "Spanish",
            "texts": ["Save changes"],
            "enabled": _engine_enabled("opus", "SELF_HOSTED_MT_DISABLE_OPUS"),
        },
        {
            "engine": "MADLAD-400",
            "endpoint": _secret("MADLAD_ENDPOINT", DEFAULT_MADLAD_ENDPOINT),
            "api_key": _secret("MADLAD_API_KEY", ""),
            "source_language": "English",
            "target_language": "Spanish",
            "texts": ["Save changes"],
            "enabled": _engine_enabled("madlad", "SELF_HOSTED_MT_DISABLE_MADLAD"),
        },
    ]
    rows: List[Dict[str, Any]] = []
    for test in tests:
        row = {
            "engine": test["engine"],
            "source_language": test["source_language"],
            "target_language": test["target_language"],
            "success": False,
            "translation": "",
            "error": "disabled" if not test["enabled"] else "",
        }
        if not test["enabled"]:
            rows.append(row)
            continue
        try:
            if test["engine"] == "IndicTrans2":
                data = translate_with_indictrans2(
                    endpoint=test["endpoint"],
                    api_key=test["api_key"],
                    source_language=test["source_language"],
                    target_language=test["target_language"],
                    texts=test["texts"],
                    timeout=timeout,
                )
            elif test["engine"] == "MADLAD-400":
                data = translate_with_madlad(
                    endpoint=test["endpoint"],
                    api_key=test["api_key"],
                    source_language=test["source_language"],
                    target_language=test["target_language"],
                    texts=test["texts"],
                    timeout=timeout,
                )
            else:
                data = translate_with_opus_mt(
                    endpoint=test["endpoint"],
                    api_key=test["api_key"],
                    source_language=test["source_language"],
                    target_language=test["target_language"],
                    texts=test["texts"],
                    timeout=timeout,
                )
            translations, usage = data
            row["success"] = bool(translations and translations[0])
            row["translation"] = translations[0] if translations else ""
            row["requests"] = usage.get("requests", 0)
        except Exception as exc:
            if test["engine"] == "IndicTrans2" and _indic_in_process_fallback_enabled():
                try:
                    translations, usage = _translate_with_indictrans2_in_process(
                        source_language=test["source_language"],
                        target_language=test["target_language"],
                        texts=test["texts"],
                    )
                    row["success"] = bool(translations and translations[0])
                    row["translation"] = translations[0] if translations else ""
                    row["requests"] = usage.get("requests", 0)
                    row["engine"] = "IndicTrans2 (in-process)"
                except Exception as fallback_exc:
                    row["error"] = f"{exc} | in-process fallback: {fallback_exc}"[:300]
            else:
                row["error"] = str(exc)[:300]
        rows.append(row)
    return rows


def _apply_engine_usage(usage: Dict[str, Any], provider: str, engine_usage: Dict[str, Any]) -> None:
    usage.update(engine_usage)
    usage["provider"] = provider
    usage["engine"] = engine_usage.get("engine", provider)
    usage["success"] = True


def _translate_with_indictrans2_in_process(
    *,
    source_language: str,
    target_language: str,
    texts: List[str],
    protected_terms: Optional[List[str]] = None,
) -> Tuple[List[str], Dict[str, Any]]:
    import indictrans2_worker

    protected_texts: List[str] = []
    maps = []
    for text in texts:
        protected, mapping = protect_text(text, protected_terms)
        protected_texts.append(protected)
        maps.append(mapping)

    translations, model_name = indictrans2_worker.translate_texts(
        protected_texts,
        indictrans2_worker.normalize_language(source_language),
        indictrans2_worker.normalize_language(target_language),
    )
    translations = [
        restore_text(translation, mapping)
        for translation, mapping in zip(translations, maps)
    ]
    return translations, {
        "provider": "indictrans2",
        "engine": "indictrans2_in_process",
        "model": model_name,
        "characters": estimate_characters(texts),
        "requests": 1,
        "segments": len(texts),
        "managed": True,
    }


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
    route_errors: List[str] = []

    try:
        if should_use_indic and _engine_enabled("indictrans2", "SELF_HOSTED_MT_DISABLE_INDIC"):
            endpoint = _secret("INDICTRANS2_ENDPOINT", DEFAULT_INDICTRANS2_ENDPOINT)
            if endpoint:
                try:
                    translations, engine_usage = translate_with_indictrans2(
                        endpoint=endpoint,
                        api_key=_secret("INDICTRANS2_API_KEY", ""),
                        source_language=source_info.get("indic") or "eng_Latn",
                        target_language=target_info.get("indic") or target_language,
                        texts=texts,
                        protected_terms=protected_terms,
                        timeout=int(_secret("SELF_HOSTED_MT_TIMEOUT", "180")),
                    )
                    _apply_engine_usage(usage, "indictrans2", engine_usage)
                    return translations, usage
                except Exception as exc:
                    route_errors.append(f"IndicTrans2 failed: {exc}")

            if _indic_in_process_fallback_enabled():
                try:
                    translations, engine_usage = _translate_with_indictrans2_in_process(
                        source_language=source_info.get("indic") or "eng_Latn",
                        target_language=target_info.get("indic") or target_language,
                        texts=texts,
                        protected_terms=protected_terms,
                    )
                    _apply_engine_usage(usage, "indictrans2", engine_usage)
                    return translations, usage
                except Exception as exc:
                    route_errors.append(f"IndicTrans2 in-process failed: {exc}")

        if _engine_enabled("opus", "SELF_HOSTED_MT_DISABLE_OPUS"):
            endpoint = _secret("OPUS_MT_ENDPOINT", DEFAULT_OPUS_MT_ENDPOINT)
            if not endpoint:
                route_errors.append("OPUS-MT endpoint is not configured.")
            else:
                try:
                    translations, engine_usage = translate_with_opus_mt(
                        endpoint=endpoint,
                        api_key=_secret("OPUS_MT_API_KEY", ""),
                        source_language=source_info.get("iso", "en"),
                        target_language=target_info.get("iso") or target_language,
                        texts=texts,
                        protected_terms=protected_terms,
                        timeout=int(_secret("SELF_HOSTED_MT_TIMEOUT", "180")),
                    )
                    _apply_engine_usage(usage, "opus_mt", engine_usage)
                    return translations, usage
                except Exception as exc:
                    route_errors.append(f"OPUS-MT failed: {exc}")

        if _engine_enabled("madlad", "SELF_HOSTED_MT_DISABLE_MADLAD"):
            endpoint = _secret("MADLAD_ENDPOINT", DEFAULT_MADLAD_ENDPOINT)
            if endpoint:
                try:
                    translations, engine_usage = translate_with_madlad(
                        endpoint=endpoint,
                        api_key=_secret("MADLAD_API_KEY", ""),
                        source_language=source_info.get("iso", "en"),
                        target_language=target_info.get("iso") or target_language,
                        texts=texts,
                        protected_terms=protected_terms,
                        timeout=int(_secret("MADLAD_TIMEOUT", _secret("SELF_HOSTED_MT_TIMEOUT", "300"))),
                    )
                    _apply_engine_usage(usage, "madlad400", engine_usage)
                    return translations, usage
                except Exception as exc:
                    route_errors.append(f"MADLAD-400 failed: {exc}")

        raise TranslationRouteError("No active MT route succeeded. " + " | ".join(route_errors))
    except Exception as exc:
        usage["success"] = False
        usage["error"] = str(exc)
        raise
