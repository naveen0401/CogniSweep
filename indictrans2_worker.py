
from __future__ import annotations

import os
import traceback
from functools import lru_cache
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


LANG_MAP = {
    "english": "eng_Latn", "eng_latn": "eng_Latn",
    "telugu": "tel_Telu", "tel_telu": "tel_Telu",
    "hindi": "hin_Deva", "hin_deva": "hin_Deva",
    "tamil": "tam_Taml", "tam_taml": "tam_Taml",
    "malayalam": "mal_Mlym", "mal_mlym": "mal_Mlym",
    "kannada": "kan_Knda", "kan_knda": "kan_Knda",
    "bengali": "ben_Beng", "ben_beng": "ben_Beng",
    "marathi": "mar_Deva", "mar_deva": "mar_Deva",
    "gujarati": "guj_Gujr", "guj_gujr": "guj_Gujr",
    "odia": "ory_Orya", "ory_orya": "ory_Orya",
    "punjabi": "pan_Guru", "pan_guru": "pan_Guru",
    "urdu": "urd_Arab", "urd_arab": "urd_Arab",
    "assamese": "asm_Beng", "asm_beng": "asm_Beng",
    "nepali": "npi_Deva", "npi_deva": "npi_Deva",
    "sanskrit": "san_Deva", "san_deva": "san_Deva",
}

SUPPORTED = sorted(set(LANG_MAP.values()))

app = FastAPI(title="ErrorSweep IndicTrans2 Worker", version="v17-clean-reset")


class TranslateRequest(BaseModel):
    texts: List[str] = Field(default_factory=list)
    source_language: str = "eng_Latn"
    target_language: str = "tel_Telu"
    domain: str = "General"


def norm_lang(value: str, default: str = "eng_Latn") -> str:
    raw = (value or "").strip()
    if raw in SUPPORTED:
        return raw
    key = raw.lower().replace("-", "_").replace(" ", "_")
    return LANG_MAP.get(key, default)


@app.exception_handler(Exception)
async def debug_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "traceback": traceback.format_exc()[-6000:],
        },
    )


@lru_cache(maxsize=3)
def load_model(direction: str):
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    from IndicTransToolkit.processor import IndicProcessor

    device = os.environ.get("INDICTRANS2_DEVICE", "cpu")
    if direction == "en_indic":
        model_name = os.environ.get("INDICTRANS2_MODEL_EN_INDIC", "ai4bharat/indictrans2-en-indic-dist-200M")
    elif direction == "indic_en":
        model_name = os.environ.get("INDICTRANS2_MODEL_INDIC_EN", "ai4bharat/indictrans2-indic-en-dist-200M")
    else:
        model_name = os.environ.get("INDICTRANS2_MODEL_INDIC_INDIC", "ai4bharat/indictrans2-indic-indic-dist-320M")

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_name,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    model.to(device)
    model.eval()
    processor = IndicProcessor(inference=True)
    return model_name, tokenizer, model, processor, device


def direction_for(src: str, tgt: str) -> str:
    if src == "eng_Latn" and tgt != "eng_Latn":
        return "en_indic"
    if src != "eng_Latn" and tgt == "eng_Latn":
        return "indic_en"
    if src != "eng_Latn" and tgt != "eng_Latn":
        return "indic_indic"
    return "en_indic"


@app.get("/")
def root():
    return {"service": "ErrorSweep IndicTrans2 Worker", "health": "/health", "translate": "/translate"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "device": os.environ.get("INDICTRANS2_DEVICE", "cpu"),
        "supported_codes": SUPPORTED,
        "models": {
            "en_indic": os.environ.get("INDICTRANS2_MODEL_EN_INDIC", "ai4bharat/indictrans2-en-indic-dist-200M"),
            "indic_en": os.environ.get("INDICTRANS2_MODEL_INDIC_EN", "ai4bharat/indictrans2-indic-en-dist-200M"),
            "indic_indic": os.environ.get("INDICTRANS2_MODEL_INDIC_INDIC", "ai4bharat/indictrans2-indic-indic-dist-320M"),
        },
    }


@app.post("/translate")
def translate(req: TranslateRequest):
    import torch

    texts = [str(x or "") for x in req.texts]
    if not texts:
        return {"translations": []}

    src = norm_lang(req.source_language, "eng_Latn")
    tgt = norm_lang(req.target_language, "tel_Telu")
    direction = direction_for(src, tgt)

    model_name, tokenizer, model, processor, device = load_model(direction)

    max_input_chars = int(os.environ.get("INDICTRANS2_MAX_INPUT_CHARS", "700"))
    batch_size = int(os.environ.get("INDICTRANS2_BATCH_SIZE", "1"))
    max_new_tokens = int(os.environ.get("INDICTRANS2_MAX_NEW_TOKENS", "256"))
    num_beams = int(os.environ.get("INDICTRANS2_NUM_BEAMS", "1"))

    outputs: List[str] = []
    for start in range(0, len(texts), batch_size):
        batch = [x[:max_input_chars] for x in texts[start:start + batch_size]]

        processed = processor.preprocess_batch(batch, src_lang=src, tgt_lang=tgt)
        inputs = tokenizer(
            processed,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                num_beams=num_beams,
                use_cache=False,
            )
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        post = processor.postprocess_batch(decoded, lang=tgt)
        outputs.extend([str(x) for x in post])

    return {
        "translations": outputs,
        "source_language": src,
        "target_language": tgt,
        "direction": direction,
        "model": model_name,
    }

