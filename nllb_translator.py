"""
nllb_translator.py

PHASE 2 — FUTURE SELF-HOSTED ENGINE
Meta NLLB-200 integration for ErrorSweep.

This file is complete and ready to activate later, but should NOT be installed
or enabled in normal Streamlit Cloud builds yet because transformers/torch are
large and this model needs strong CPU/GPU resources.

Activate by setting:
    NLLB_MODE=True

Default model:
    facebook/nllb-200-distilled-600M

Public functions:
    normalize_nllb_language(language)
    translate_text(source_language, target_language, text)
    translate_batch(source_language, target_language, texts)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import streamlit as st
except Exception:
    st = None


class NLLBTranslatorError(Exception):
    """User-friendly NLLB exception."""


@dataclass
class NLLBTranslationUsage:
    provider: str = "nllb_self_hosted"
    engine: str = "nllb"
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


# Common language names to NLLB codes. Extend as needed.
NLLB_LANGUAGE_MAP: Dict[str, str] = {
    "english": "eng_Latn",
    "en": "eng_Latn",
    "eng": "eng_Latn",
    "eng_latn": "eng_Latn",
    "french": "fra_Latn",
    "fr": "fra_Latn",
    "fra": "fra_Latn",
    "german": "deu_Latn",
    "de": "deu_Latn",
    "deu": "deu_Latn",
    "spanish": "spa_Latn",
    "es": "spa_Latn",
    "spa": "spa_Latn",
    "italian": "ita_Latn",
    "it": "ita_Latn",
    "ita": "ita_Latn",
    "portuguese": "por_Latn",
    "pt": "por_Latn",
    "por": "por_Latn",
    "russian": "rus_Cyrl",
    "ru": "rus_Cyrl",
    "arabic": "arb_Arab",
    "ar": "arb_Arab",
    "chinese": "zho_Hans",
    "chinese simplified": "zho_Hans",
    "zh": "zho_Hans",
    "japanese": "jpn_Jpan",
    "ja": "jpn_Jpan",
    "korean": "kor_Hang",
    "ko": "kor_Hang",
    "hindi": "hin_Deva",
    "hi": "hin_Deva",
    "telugu": "tel_Telu",
    "te": "tel_Telu",
    "tamil": "tam_Taml",
    "ta": "tam_Taml",
    "malayalam": "mal_Mlym",
    "ml": "mal_Mlym",
    "kannada": "kan_Knda",
    "kn": "kan_Knda",
    "bengali": "ben_Beng",
    "bangla": "ben_Beng",
    "bn": "ben_Beng",
    "marathi": "mar_Deva",
    "mr": "mar_Deva",
    "gujarati": "guj_Gujr",
    "gu": "guj_Gujr",
    "punjabi": "pan_Guru",
    "pa": "pan_Guru",
    "urdu": "urd_Arab",
    "ur": "urd_Arab",
    "nepali": "npi_Deva",
    "ne": "npi_Deva",
    "sanskrit": "san_Deva",
    "odia": "ory_Orya",
    "oriya": "ory_Orya",
    "or": "ory_Orya",
    "thai": "tha_Thai",
    "th": "tha_Thai",
    "vietnamese": "vie_Latn",
    "vi": "vie_Latn",
    "indonesian": "ind_Latn",
    "id": "ind_Latn",
    "turkish": "tur_Latn",
    "tr": "tur_Latn",
    "dutch": "nld_Latn",
    "nl": "nld_Latn",
    "polish": "pol_Latn",
    "pl": "pol_Latn",
}

PROTECTED_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|\$\w+|<[^>]+>|\b\w+_id\b)",
    flags=re.UNICODE,
)


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


def normalize_nllb_language(language: str, default: str = "eng_Latn") -> str:
    value = (language or "").strip()
    if not value:
        return default
    if re.fullmatch(r"[a-z]{3}_[A-Za-z]{4}", value):
        return value
    key = value.lower().replace("-", "_").strip()
    return NLLB_LANGUAGE_MAP.get(key, value)


def _protect_text(text: str, protected_terms: Optional[Sequence[str]] = None) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}

    def add_token(original: str) -> str:
        token = f"__ESPH_{len(mapping)}__"
        mapping[token] = original
        return token

    protected = PROTECTED_PATTERN.sub(lambda m: add_token(m.group(0)), text or "")
    for term in sorted(set(protected_terms or []), key=len, reverse=True):
        term = str(term).strip()
        if term and term in protected:
            protected = protected.replace(term, add_token(term))
    return protected, mapping


def _restore_text(text: str, mapping: Dict[str, str]) -> str:
    out = text or ""
    for token, original in mapping.items():
        out = out.replace(token, original)
        out = out.replace(token.lower(), original)
        out = out.replace(token.upper(), original)
    return out.strip()


def _add_session_usage(characters: int, requests_count: int = 1) -> None:
    if st is None:
        return
    try:
        st.session_state["nllb_characters_used"] = int(st.session_state.get("nllb_characters_used", 0)) + int(characters)
        st.session_state["nllb_requests_used"] = int(st.session_state.get("nllb_requests_used", 0)) + int(requests_count)
        st.session_state.setdefault("translation_usage_events", [])
        st.session_state["translation_usage_events"].insert(0, {
            "provider": "nllb_self_hosted",
            "characters": int(characters),
            "requests": int(requests_count),
        })
    except Exception:
        pass


@lru_cache(maxsize=1)
def _load_model():
    """Lazy-load NLLB only when NLLB_MODE=True routes here."""
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except Exception as exc:
        raise NLLBTranslatorError(
            "NLLB dependencies are not installed. Install torch and transformers only on the future NLLB server."
        ) from exc

    model_name = _secret("NLLB_MODEL_NAME", "facebook/nllb-200-distilled-600M")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    dtype = torch.float16 if device == "cuda" else torch.float32
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, torch_dtype=dtype)
    model.to(device)
    model.eval()
    return tokenizer, model, device


def translate_batch(
    *,
    source_language: str,
    target_language: str,
    texts: Sequence[str],
    protected_terms: Optional[Sequence[str]] = None,
    batch_size: int = 8,
    max_length: int = 512,
    max_new_tokens: int = 256,
) -> Tuple[List[str], Dict[str, Any]]:
    """Translate a batch with self-hosted NLLB.

    This is intended for the future GPU server. It works on CPU too but will be slow.
    """
    if not texts:
        return [], NLLBTranslationUsage(characters=0, requests=0).to_dict()

    src_code = normalize_nllb_language(source_language, default="eng_Latn")
    tgt_code = normalize_nllb_language(target_language, default="fra_Latn")

    try:
        import torch
    except Exception as exc:
        raise NLLBTranslatorError("NLLB requires torch. Install the NLLB optional requirements on the NLLB server.") from exc

    tokenizer, model, device = _load_model()
    tokenizer.src_lang = src_code
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(tgt_code)
    if forced_bos_token_id is None or forced_bos_token_id < 0:
        raise NLLBTranslatorError(f"Unsupported NLLB target language code: {tgt_code}")

    clean_texts = [str(t or "") for t in texts]
    total_chars = sum(len(t) for t in clean_texts)
    outputs: List[str] = []
    requests_used = 0

    for start in range(0, len(clean_texts), max(1, int(batch_size))):
        chunk = clean_texts[start:start + max(1, int(batch_size))]
        protected_chunk: List[str] = []
        mappings: List[Dict[str, str]] = []
        for text in chunk:
            protected, mapping = _protect_text(text, protected_terms=protected_terms)
            protected_chunk.append(protected)
            mappings.append(mapping)

        encoded = tokenizer(
            protected_chunk,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        )
        encoded = {k: v.to(device) for k, v in encoded.items()}
        with torch.no_grad():
            generated = model.generate(
                **encoded,
                forced_bos_token_id=forced_bos_token_id,
                max_new_tokens=max_new_tokens,
                num_beams=4,
            )
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        for text_out, mapping in zip(decoded, mappings):
            outputs.append(_restore_text(text_out, mapping))
        requests_used += 1

    _add_session_usage(total_chars, requests_used)
    usage = NLLBTranslationUsage(characters=total_chars, requests=requests_used).to_dict()
    return outputs, usage


def translate_text(
    *,
    source_language: str,
    target_language: str,
    text: str,
    protected_terms: Optional[Sequence[str]] = None,
) -> Tuple[str, Dict[str, Any]]:
    outputs, usage = translate_batch(
        source_language=source_language,
        target_language=target_language,
        texts=[text],
        protected_terms=protected_terms,
        batch_size=1,
    )
    return outputs[0] if outputs else "", usage

