"""
ErrorSweep MADLAD-400 Self-Hosted Translation Server.

Commercial-safe broad-coverage MT worker using google/madlad400-3b-mt
(Apache-2.0). This server exposes the same /translate contract used by the
existing self-hosted MT router.

API:
- GET  /health
- POST /translate
"""

from __future__ import annotations

import hmac
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


APP_VERSION = "v1-madlad400"
MODEL_NAME = os.getenv("MADLAD_MODEL_NAME", "google/madlad400-3b-mt").strip()
SERVER_API_KEY = os.getenv("MADLAD_API_KEY", "").strip()
DEVICE = "cuda" if torch.cuda.is_available() and os.getenv("MADLAD_FORCE_CPU", "false").lower() != "true" else "cpu"

LANGUAGE_NAME_TO_CODE: Dict[str, str] = {
    "afrikaans": "af", "af": "af",
    "arabic": "ar", "ar": "ar",
    "bengali": "bn", "bangla": "bn", "bn": "bn",
    "bulgarian": "bg", "bg": "bg",
    "chinese": "zh", "mandarin": "zh", "zh": "zh",
    "croatian": "hr", "hr": "hr",
    "czech": "cs", "cs": "cs",
    "danish": "da", "da": "da",
    "dutch": "nl", "nl": "nl",
    "english": "en", "en": "en",
    "estonian": "et", "et": "et",
    "finnish": "fi", "fi": "fi",
    "french": "fr", "fr": "fr",
    "german": "de", "de": "de",
    "greek": "el", "el": "el",
    "gujarati": "gu", "gu": "gu",
    "hebrew": "he", "iw": "he", "he": "he",
    "hindi": "hi", "hi": "hi",
    "hungarian": "hu", "hu": "hu",
    "indonesian": "id", "id": "id",
    "italian": "it", "it": "it",
    "japanese": "ja", "ja": "ja",
    "kannada": "kn", "kn": "kn",
    "korean": "ko", "ko": "ko",
    "latvian": "lv", "lv": "lv",
    "lithuanian": "lt", "lt": "lt",
    "malay": "ms", "ms": "ms",
    "malayalam": "ml", "ml": "ml",
    "marathi": "mr", "mr": "mr",
    "norwegian": "no", "nb": "no", "no": "no",
    "polish": "pl", "pl": "pl",
    "portuguese": "pt", "pt": "pt",
    "romanian": "ro", "ro": "ro",
    "russian": "ru", "ru": "ru",
    "serbian": "sr", "sr": "sr",
    "slovak": "sk", "sk": "sk",
    "slovenian": "sl", "sl": "sl",
    "spanish": "es", "es": "es",
    "swahili": "sw", "sw": "sw",
    "swedish": "sv", "sv": "sv",
    "tagalog": "tl", "filipino": "tl", "tl": "tl",
    "tamil": "ta", "ta": "ta",
    "telugu": "te", "te": "te",
    "thai": "th", "th": "th",
    "turkish": "tr", "tr": "tr",
    "ukrainian": "uk", "uk": "uk",
    "urdu": "ur", "ur": "ur",
    "vietnamese": "vi", "vi": "vi",
}

PROTECTED_PATTERN = re.compile(
    r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%[0-9$.\-+]*[sdif]|<[^>\n]+>|https?://[^\s]+|www\.[^\s]+|[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,})"
)


class TranslateRequest(BaseModel):
    texts: List[str] = Field(default_factory=list)
    source_language: str = "English"
    target_language: str = "French"
    domain: str = "General"
    api_key: Optional[str] = None


def normalize_language(value: str) -> str:
    key = (value or "").strip().lower().replace("_", "-")
    key = key.split("-", 1)[0] if "-" in key else key
    if key.startswith("<2") and key.endswith(">"):
        key = key[2:-1]
    if re.fullmatch(r"[a-z]{2,3}", key):
        return key
    return LANGUAGE_NAME_TO_CODE.get(key, key[:2] if key else "en")


def verify_api_key(authorization: Optional[str], request_key: Optional[str]) -> None:
    if not SERVER_API_KEY:
        return
    header_key = ""
    if authorization and authorization.lower().startswith("bearer "):
        header_key = authorization.split(" ", 1)[1].strip()
    supplied = (request_key or header_key or "").strip()
    if not hmac.compare_digest(supplied, SERVER_API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized MADLAD request.")


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
        loose = re.compile(r"Z\s*X\s*P\s*H\s*" + re.escape(marker.replace("ZXPH", "").replace("QZ", "")) + r"\s*Q\s*Z", re.I)
        restored = loose.sub(original, restored)
    for original in mapping.values():
        if original not in restored:
            restored = (restored.rstrip() + " " + original).strip()
    restored = re.sub(r"\s+([,.;:!?])", r"\1", restored)
    return restored.strip()


def clear_cuda_cache() -> None:
    if DEVICE == "cuda":
        torch.cuda.empty_cache()


@lru_cache(maxsize=1)
def load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    model.to(DEVICE)
    model.eval()
    return tokenizer, model


def translate_texts(texts: List[str], target_code: str) -> List[str]:
    if not texts:
        return []

    tokenizer, model = load_model()
    batch_size = int(os.getenv("MADLAD_BATCH_SIZE", "4"))
    max_input_length = int(os.getenv("MADLAD_MAX_INPUT_LENGTH", "256"))
    max_new_tokens = int(os.getenv("MADLAD_MAX_NEW_TOKENS", "256"))

    outputs: List[str] = []
    for i in range(0, len(texts), max(1, batch_size)):
        batch = texts[i : i + batch_size]
        protected_batch: List[str] = []
        mappings: List[Dict[str, str]] = []
        for text in batch:
            protected, mapping = protect_text(text)
            protected_batch.append(f"<2{target_code}> {protected}")
            mappings.append(mapping)

        encoded = tokenizer(
            protected_batch,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_input_length,
        ).to(DEVICE)

        with torch.no_grad():
            generated = model.generate(
                **encoded,
                max_new_tokens=max_new_tokens,
                num_beams=int(os.getenv("MADLAD_NUM_BEAMS", "4")),
            )

        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        for text, mapping in zip(decoded, mappings):
            outputs.append(restore_text(text, mapping))
        clear_cuda_cache()

    return outputs


app = FastAPI(title="ErrorSweep MADLAD-400 Server", version=APP_VERSION)


@app.get("/health")
def health():
    model_path = Path(MODEL_NAME)
    is_local = model_path.exists()
    return {
        "ok": True,
        "version": APP_VERSION,
        "provider": "madlad400",
        "model": MODEL_NAME,
        "local_path": is_local,
        "has_config": bool(is_local and (model_path / "config.json").exists()),
        "device": DEVICE,
    }


@app.post("/translate")
def translate(req: TranslateRequest, authorization: Optional[str] = Header(default=None)):
    verify_api_key(authorization, req.api_key)
    target = normalize_language(req.target_language)

    started = time.time()
    translations = translate_texts(req.texts, target)
    elapsed_ms = int((time.time() - started) * 1000)

    return {
        "translations": translations,
        "provider": "madlad400",
        "model": MODEL_NAME,
        "source_language": normalize_language(req.source_language),
        "target_language": target,
        "characters": sum(len(t or "") for t in req.texts),
        "segments": len(req.texts),
        "elapsed_ms": elapsed_ms,
    }
