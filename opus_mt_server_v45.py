"""
CogniSweep OPUS-MT Self-Hosted Translation Server (v45)

Purpose:
- First practical self-hosted MT endpoint for CogniSweep without Azure/NLLB.
- Starts with English -> French/Spanish/German/Italian/Portuguese.
- Uses Helsinki-NLP OPUS-MT models from Hugging Face.
- OpenAI/API key is not required.

API:
- GET  /health
- GET  /models
- POST /translate

POST /translate body:
{
  "texts": ["Welcome to Docflow"],
  "source_language": "English",
  "target_language": "French",
  "api_key": ""      # optional if you enable SERVER_API_KEY
}

Response:
{
  "translations": ["Bienvenue à Docflow"],
  "provider": "opus-mt",
  "model": "Helsinki-NLP/opus-mt-en-fr"
}
"""

from __future__ import annotations

import os
import re
import time
import hmac
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

# Heavy imports are intentionally below. They load once when the server starts.
import torch
from transformers import MarianMTModel, MarianTokenizer


APP_VERSION = "v45-opus-mt"
SERVER_API_KEY = os.getenv("OPUS_MT_API_KEY", "").strip()
DEVICE = "cuda" if torch.cuda.is_available() and os.getenv("OPUS_MT_FORCE_CPU", "false").lower() != "true" else "cpu"

# Keep first release narrow. Add more pairs only after testing quality and model availability.
SUPPORTED_PAIRS: Dict[Tuple[str, str], str] = {
    ("en", "fr"): "Helsinki-NLP/opus-mt-en-fr",
    ("en", "es"): "Helsinki-NLP/opus-mt-en-es",
    ("en", "de"): "Helsinki-NLP/opus-mt-en-de",
    ("en", "it"): "Helsinki-NLP/opus-mt-en-it",
    ("en", "pt"): "Helsinki-NLP/opus-mt-en-pt",
}

LANGUAGE_NAME_TO_CODE: Dict[str, str] = {
    "english": "en",
    "en": "en",
    "eng": "en",
    "french": "fr",
    "fr": "fr",
    "fra": "fr",
    "spanish": "es",
    "es": "es",
    "spa": "es",
    "german": "de",
    "de": "de",
    "deu": "de",
    "italian": "it",
    "it": "it",
    "ita": "it",
    "portuguese": "pt",
    "pt": "pt",
    "por": "pt",
}

PROTECTED_PATTERN = re.compile(
    r"("
    r"\{\{[^{}]+\}\}"                       # {{placeholder}}
    r"|\{[^{}]+\}"                           # {placeholder}
    r"|%[sd]"                                # %s %d
    r"|%\$\d*[sd]"                           # %$1s etc.
    r"|<[^>\n]+>"                            # tags
    r"|https?://[^\s]+"
    r"|[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,}"
    r"|\b\d+(?:[.,:]\d+)*\b"
    r")"
)


class TranslateRequest(BaseModel):
    texts: List[str] = Field(default_factory=list)
    source_language: str = "English"
    target_language: str = "French"
    domain: str = "General"
    api_key: Optional[str] = None


def normalize_language(value: str) -> str:
    key = (value or "").strip().lower().replace("_", "-")
    key = key.split("-")[0] if len(key) > 3 and "-" in key else key
    return LANGUAGE_NAME_TO_CODE.get(key, key)


def verify_api_key(authorization: Optional[str], request_key: Optional[str]) -> None:
    if not SERVER_API_KEY:
        return
    header_key = ""
    if authorization and authorization.lower().startswith("bearer "):
        header_key = authorization.split(" ", 1)[1].strip()
    supplied = (request_key or header_key or "").strip()
    if not hmac.compare_digest(supplied, SERVER_API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized OPUS-MT request.")


def protect_text(text: str) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}

    def repl(match: re.Match) -> str:
        token = f" ZXPH{len(mapping)}QZ "
        mapping[token.strip()] = match.group(0)
        return token

    return PROTECTED_PATTERN.sub(repl, text or ""), mapping


def restore_text(text: str, mapping: Dict[str, str]) -> str:
    restored = text or ""
    for marker, original in mapping.items():
        restored = restored.replace(marker, original)
        restored = restored.replace(marker.replace(" ", ""), original)
        # Models sometimes add spaces between marker pieces.
        loose = re.compile(r"Z\s*X\s*P\s*H\s*" + re.escape(marker.replace("ZXPH", "").replace("QZ", "")) + r"\s*Q\s*Z", re.I)
        restored = loose.sub(original, restored)

    # If the model dropped a protected token entirely, append it so it is not lost.
    for original in mapping.values():
        if original not in restored:
            restored = (restored.rstrip() + " " + original).strip()

    restored = re.sub(r"\s+([,.;:!?])", r"\1", restored)
    restored = re.sub(r"([({\[])\s+", r"\1", restored)
    restored = re.sub(r"\s+([)}\]])", r"\1", restored)
    return restored.strip()


def clear_cuda_cache() -> None:
    if DEVICE == "cuda":
        torch.cuda.empty_cache()


@lru_cache(maxsize=int(os.getenv("OPUS_MT_MODEL_CACHE_SIZE", "2")))
def load_pair_model(src_code: str, tgt_code: str):
    model_name = SUPPORTED_PAIRS.get((src_code, tgt_code))
    if not model_name:
        supported = ", ".join(f"{s}->{t}" for s, t in SUPPORTED_PAIRS)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported OPUS-MT pair {src_code}->{tgt_code}. Supported: {supported}",
        )

    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    model.to(DEVICE)
    model.eval()
    return model_name, tokenizer, model


def translate_texts(texts: List[str], src_code: str, tgt_code: str) -> Tuple[List[str], str]:
    if not texts:
        return [], SUPPORTED_PAIRS.get((src_code, tgt_code), "")

    model_name, tokenizer, model = load_pair_model(src_code, tgt_code)

    outputs: List[str] = []
    batch_size = int(os.getenv("OPUS_MT_BATCH_SIZE", "8"))
    max_length = int(os.getenv("OPUS_MT_MAX_LENGTH", "256"))

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        protected_batch = []
        mappings = []
        for text in batch:
            protected, mapping = protect_text(text)
            protected_batch.append(protected)
            mappings.append(mapping)

        encoded = tokenizer(
            protected_batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        ).to(DEVICE)

        with torch.no_grad():
            generated = model.generate(
                **encoded,
                max_length=max_length,
                num_beams=4,
                early_stopping=True,
            )

        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        for text, mapping in zip(decoded, mappings):
            outputs.append(restore_text(text, mapping))
        clear_cuda_cache()

    return outputs, model_name


app = FastAPI(title="CogniSweep OPUS-MT Server", version=APP_VERSION)


@app.get("/health")
def health():
    return {
        "ok": True,
        "version": APP_VERSION,
        "provider": "opus-mt",
        "device": DEVICE,
        "supported_pairs": [f"{s}->{t}" for s, t in SUPPORTED_PAIRS],
    }


@app.get("/models")
def models():
    return {
        "provider": "opus-mt",
        "models": [
            {"source": s, "target": t, "model": model}
            for (s, t), model in SUPPORTED_PAIRS.items()
        ],
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
        "provider": "opus-mt",
        "model": model_name,
        "source_language": src,
        "target_language": tgt,
        "characters": sum(len(t or "") for t in req.texts),
        "segments": len(req.texts),
        "elapsed_ms": elapsed_ms,
    }

