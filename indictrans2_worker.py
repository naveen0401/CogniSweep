"""
ErrorSweep IndicTrans2 Self-Hosted Translation Server.

This worker exposes the same /translate contract used by ErrorSweep's built-in
MT router. It is intended for Indian-language routes, while MADLAD-400 handles
broad global coverage and OPUS-MT remains a lightweight fallback.
"""

from __future__ import annotations

import hmac
import logging
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

LOGGER = logging.getLogger(__name__)

try:
    from IndicTransToolkit.processor import IndicProcessor
except Exception as exc:  # pragma: no cover - dependency is optional until worker is installed
    LOGGER.debug("IndicTransToolkit is unavailable until the worker dependency is installed: %s", exc)
    IndicProcessor = None


APP_VERSION = "v1-indictrans2"
SERVER_API_KEY = os.getenv("INDICTRANS2_API_KEY", "").strip()
DEVICE = "cuda" if torch.cuda.is_available() and os.getenv("INDICTRANS2_FORCE_CPU", "false").lower() != "true" else "cpu"
PRELOAD_MODELS = os.getenv("INDICTRANS2_PRELOAD", "false").lower() in {"1", "true", "yes", "on"}

ROOT_DIR = Path(__file__).resolve().parent
LOCAL_MODELS_DIR = ROOT_DIR / "models"


def _model_from_env_or_local(env_name: str, local_folder: str, repo_name: str) -> str:
    configured = os.getenv(env_name, "").strip()
    if configured:
        return configured
    local_path = LOCAL_MODELS_DIR / local_folder
    if (local_path / "config.json").exists():
        return str(local_path)
    return repo_name


MODEL_EN_INDIC = _model_from_env_or_local(
    "INDICTRANS2_EN_INDIC_MODEL",
    "indictrans2-en-indic-dist-200M",
    "ai4bharat/indictrans2-en-indic-dist-200M",
)
MODEL_INDIC_EN = _model_from_env_or_local(
    "INDICTRANS2_INDIC_EN_MODEL",
    "indictrans2-indic-en-dist-200M",
    "ai4bharat/indictrans2-indic-en-dist-200M",
)
MODEL_INDIC_INDIC = _model_from_env_or_local(
    "INDICTRANS2_INDIC_INDIC_MODEL",
    "indictrans2-indic-indic-dist-320M",
    "ai4bharat/indictrans2-indic-indic-dist-320M",
)

LANGUAGE_NAME_TO_INDIC: Dict[str, str] = {
    "assamese": "asm_Beng", "as": "asm_Beng", "asm_beng": "asm_Beng",
    "bengali": "ben_Beng", "bangla": "ben_Beng", "bn": "ben_Beng", "ben_beng": "ben_Beng",
    "bodo": "brx_Deva", "brx": "brx_Deva", "brx_deva": "brx_Deva",
    "dogri": "doi_Deva", "doi": "doi_Deva", "doi_deva": "doi_Deva",
    "english": "eng_Latn", "en": "eng_Latn", "eng_latn": "eng_Latn",
    "goan konkani": "gom_Deva", "konkani": "gom_Deva", "gom": "gom_Deva", "gom_deva": "gom_Deva",
    "gujarati": "guj_Gujr", "gu": "guj_Gujr", "guj_gujr": "guj_Gujr",
    "hindi": "hin_Deva", "hi": "hin_Deva", "hin_deva": "hin_Deva",
    "kannada": "kan_Knda", "kn": "kan_Knda", "kan_knda": "kan_Knda",
    "kashmiri arabic": "kas_Arab", "kas_arab": "kas_Arab",
    "kashmiri devanagari": "kas_Deva", "kas_deva": "kas_Deva",
    "maithili": "mai_Deva", "mai": "mai_Deva", "mai_deva": "mai_Deva",
    "malayalam": "mal_Mlym", "ml": "mal_Mlym", "mal_mlym": "mal_Mlym",
    "marathi": "mar_Deva", "mr": "mar_Deva", "mar_deva": "mar_Deva",
    "meitei bengali": "mni_Beng", "mni_beng": "mni_Beng",
    "meitei": "mni_Mtei", "manipuri": "mni_Mtei", "mni_mtei": "mni_Mtei",
    "nepali": "npi_Deva", "ne": "npi_Deva", "npi_deva": "npi_Deva",
    "odia": "ory_Orya", "oriya": "ory_Orya", "or": "ory_Orya", "ory_orya": "ory_Orya",
    "punjabi": "pan_Guru", "pa": "pan_Guru", "pan_guru": "pan_Guru",
    "sanskrit": "san_Deva", "sa": "san_Deva", "san_deva": "san_Deva",
    "santali": "sat_Olck", "sat": "sat_Olck", "sat_olck": "sat_Olck",
    "sindhi arabic": "snd_Arab", "snd_arab": "snd_Arab",
    "sindhi devanagari": "snd_Deva", "sindhi": "snd_Deva", "snd_deva": "snd_Deva",
    "tamil": "tam_Taml", "ta": "tam_Taml", "tam_taml": "tam_Taml",
    "telugu": "tel_Telu", "te": "tel_Telu", "tel_telu": "tel_Telu",
    "urdu": "urd_Arab", "ur": "urd_Arab", "urd_arab": "urd_Arab",
}

INDIC_CODES = {v for v in LANGUAGE_NAME_TO_INDIC.values() if v != "eng_Latn"}

PROTECTED_PATTERN = re.compile(
    r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%[0-9$.\-+]*[sdif]|<[^>\n]+>|https?://[^\s]+|www\.[^\s]+|[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,})"
)


class TranslateRequest(BaseModel):
    texts: List[str] = Field(default_factory=list)
    source_language: str = "eng_Latn"
    target_language: str = "hin_Deva"
    domain: str = "General"
    api_key: Optional[str] = None


def normalize_language(value: str) -> str:
    raw = (value or "").strip()
    key = raw.lower().replace("-", "_")
    if raw in LANGUAGE_NAME_TO_INDIC.values():
        return raw
    return LANGUAGE_NAME_TO_INDIC.get(key, raw if "_" in raw else key)


def model_for_pair(src: str, tgt: str) -> str:
    if src == "eng_Latn" and tgt in INDIC_CODES:
        return MODEL_EN_INDIC
    if src in INDIC_CODES and tgt == "eng_Latn":
        return MODEL_INDIC_EN
    if src in INDIC_CODES and tgt in INDIC_CODES:
        return MODEL_INDIC_INDIC
    raise HTTPException(status_code=400, detail=f"Unsupported IndicTrans2 pair {src}->{tgt}.")


def model_status(model_name: str) -> Dict[str, object]:
    path = Path(model_name)
    is_local = path.exists()
    return {
        "model": model_name,
        "local_path": is_local,
        "has_config": bool(is_local and (path / "config.json").exists()),
        "has_tokenizer_config": bool(is_local and (path / "tokenizer_config.json").exists()),
    }


def verify_api_key(authorization: Optional[str], request_key: Optional[str]) -> None:
    if not SERVER_API_KEY:
        return
    header_key = ""
    if authorization and authorization.lower().startswith("bearer "):
        header_key = authorization.split(" ", 1)[1].strip()
    supplied = (request_key or header_key or "").strip()
    if not hmac.compare_digest(supplied, SERVER_API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized IndicTrans2 request.")


def protect_text(text: str) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}

    def repl(match: re.Match) -> str:
        marker = f"ZXPH{len(mapping)}QZ"
        mapping[marker] = match.group(0)
        return f" {marker} "

    return PROTECTED_PATTERN.sub(repl, text or ""), mapping


def restore_text(text: str, mapping: Dict[str, str]) -> str:
    restored = text or ""
    for marker, original in mapping.items():
        restored = restored.replace(marker, original)
        restored = restored.replace(marker.lower(), original)
    for original in mapping.values():
        if original not in restored:
            restored = (restored.rstrip() + " " + original).strip()
    restored = re.sub(r"\s+([,.;:!?])", r"\1", restored)
    return restored.strip()


def clear_cuda_cache() -> None:
    if DEVICE == "cuda":
        torch.cuda.empty_cache()


@lru_cache(maxsize=int(os.getenv("INDICTRANS2_MODEL_CACHE_SIZE", "2")))
def load_model(model_name: str):
    if IndicProcessor is None:
        raise RuntimeError("IndicTransToolkit is not installed. Run pip install -r requirements_indictrans2_worker.txt.")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    dtype = torch.float16 if DEVICE == "cuda" else torch.float32
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        torch_dtype=dtype,
    )
    model.to(DEVICE)
    model.eval()
    return tokenizer, model, IndicProcessor(inference=True)


def translate_texts(texts: List[str], src: str, tgt: str) -> Tuple[List[str], str]:
    if not texts:
        return [], model_for_pair(src, tgt)

    model_name = model_for_pair(src, tgt)
    tokenizer, model, processor = load_model(model_name)
    batch_size = int(os.getenv("INDICTRANS2_BATCH_SIZE", "8"))
    max_length = int(os.getenv("INDICTRANS2_MAX_LENGTH", "256"))

    outputs: List[str] = []
    for i in range(0, len(texts), max(1, batch_size)):
        batch = texts[i : i + batch_size]
        protected_batch: List[str] = []
        mappings: List[Dict[str, str]] = []
        for text in batch:
            protected, mapping = protect_text(text)
            protected_batch.append(protected)
            mappings.append(mapping)

        processed = processor.preprocess_batch(protected_batch, src_lang=src, tgt_lang=tgt)
        encoded = tokenizer(
            processed,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        ).to(DEVICE)

        with torch.no_grad():
            generated = model.generate(
                **encoded,
                max_length=max_length,
                num_beams=int(os.getenv("INDICTRANS2_NUM_BEAMS", "1")),
                use_cache=False,
            )

        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        postprocessed = processor.postprocess_batch(decoded, lang=tgt)
        for text, mapping in zip(postprocessed, mappings):
            outputs.append(restore_text(text, mapping))
        clear_cuda_cache()

    return outputs, model_name


app = FastAPI(title="ErrorSweep IndicTrans2 Server", version=APP_VERSION)


@app.on_event("startup")
def preload_models() -> None:
    if not PRELOAD_MODELS:
        return
    load_model(MODEL_EN_INDIC)


@app.get("/health")
def health():
    models = {
        "en_indic": model_status(MODEL_EN_INDIC),
        "indic_en": model_status(MODEL_INDIC_EN),
        "indic_indic": model_status(MODEL_INDIC_INDIC),
    }
    local_models_ready = all(
        item["local_path"] and item["has_config"]
        for item in models.values()
    )
    return {
        "ok": True,
        "version": APP_VERSION,
        "provider": "indictrans2",
        "device": DEVICE,
        "toolkit_installed": IndicProcessor is not None,
        "local_models_ready": local_models_ready,
        "models": models,
    }


@app.post("/translate")
def translate(req: TranslateRequest, authorization: Optional[str] = Header(default=None)):
    verify_api_key(authorization, req.api_key)
    src = normalize_language(req.source_language)
    tgt = normalize_language(req.target_language)

    started = time.time()
    translations, model_name = translate_texts(req.texts, src, tgt)
    elapsed_ms = int((time.time() - started) * 1000)

    return {
        "translations": translations,
        "provider": "indictrans2",
        "model": model_name,
        "source_language": src,
        "target_language": tgt,
        "characters": sum(len(t or "") for t in req.texts),
        "segments": len(req.texts),
        "elapsed_ms": elapsed_ms,
    }
