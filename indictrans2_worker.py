"""
ErrorSweep IndicTrans2 Worker
-----------------------------
Self-hosted translation endpoint for Indian languages.

Use with ErrorSweep local_translation_engine.py as provider="generic".
Endpoint:
    POST /translate
Payload:
    {
      "texts": ["Welcome Screen", "Upload file"],
      "source_language": "English",
      "target_language": "Telugu",
      "domain": "Software UI"
    }
Response:
    {"translations": ["...", "..."], "engine": "IndicTrans2", ...}

Notes:
- First request downloads the HF model and can take time.
- CPU works for testing but is slow. GPU is recommended for production.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

try:
    from IndicTransToolkit.processor import IndicProcessor
except Exception:  # package layout differs across versions
    try:
        from IndicTransToolkit import IndicProcessor
    except Exception as exc:
        IndicProcessor = None
        _indic_processor_import_error = exc


# Official IndicTrans2 language tags.
LANGUAGE_CODES: Dict[str, str] = {
    "english": "eng_Latn", "en": "eng_Latn", "eng": "eng_Latn", "eng_latn": "eng_Latn",
    "assamese": "asm_Beng", "as": "asm_Beng",
    "bengali": "ben_Beng", "bangla": "ben_Beng", "bn": "ben_Beng",
    "bodo": "brx_Deva",
    "dogri": "doi_Deva",
    "gujarati": "guj_Gujr", "gu": "guj_Gujr",
    "hindi": "hin_Deva", "hi": "hin_Deva",
    "kannada": "kan_Knda", "kn": "kan_Knda",
    "kashmiri arabic": "kas_Arab", "kas_arab": "kas_Arab",
    "kashmiri devanagari": "kas_Deva", "kas_deva": "kas_Deva",
    "konkani": "gom_Deva",
    "maithili": "mai_Deva",
    "malayalam": "mal_Mlym", "ml": "mal_Mlym",
    "manipuri bengali": "mni_Beng", "mni_beng": "mni_Beng",
    "manipuri meitei": "mni_Mtei", "meitei": "mni_Mtei", "mni_mtei": "mni_Mtei",
    "marathi": "mar_Deva", "mr": "mar_Deva",
    "nepali": "npi_Deva", "ne": "npi_Deva",
    "odia": "ory_Orya", "oriya": "ory_Orya", "or": "ory_Orya",
    "punjabi": "pan_Guru", "pa": "pan_Guru",
    "sanskrit": "san_Deva", "sa": "san_Deva",
    "santali": "sat_Olck",
    "sindhi arabic": "snd_Arab", "snd_arab": "snd_Arab",
    "sindhi devanagari": "snd_Deva", "snd_deva": "snd_Deva",
    "tamil": "tam_Taml", "ta": "tam_Taml",
    "telugu": "tel_Telu", "te": "tel_Telu",
    "urdu": "urd_Arab", "ur": "urd_Arab",
}

INDIC_CODES = {v for k, v in LANGUAGE_CODES.items() if v != "eng_Latn"}

MODEL_EN_INDIC = os.getenv("INDICTRANS2_MODEL_EN_INDIC", "ai4bharat/indictrans2-en-indic-dist-200M")
MODEL_INDIC_EN = os.getenv("INDICTRANS2_MODEL_INDIC_EN", "ai4bharat/indictrans2-indic-en-dist-200M")
MODEL_INDIC_INDIC = os.getenv("INDICTRANS2_MODEL_INDIC_INDIC", "ai4bharat/indictrans2-indic-indic-dist-320M")

DEVICE = os.getenv("INDICTRANS2_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
MAX_INPUT_CHARS = int(os.getenv("INDICTRANS2_MAX_INPUT_CHARS", "1200"))
DEFAULT_BATCH_SIZE = int(os.getenv("INDICTRANS2_BATCH_SIZE", "8"))
MAX_NEW_TOKENS = int(os.getenv("INDICTRANS2_MAX_NEW_TOKENS", "256"))
NUM_BEAMS = int(os.getenv("INDICTRANS2_NUM_BEAMS", "5"))

PROTECT_RE = re.compile(
    r"(https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\{\{[^{}]+\}\}|\{[^{}]+\}|%\$?\d*[sd]|%[sd]|<[^>]+>|\$\w+)"
)


def normalize_lang(value: str, default: str = "eng_Latn") -> str:
    if not value:
        return default
    raw = value.strip()
    if raw in set(LANGUAGE_CODES.values()):
        return raw
    key = raw.lower().replace("-", "_").strip()
    if key in LANGUAGE_CODES:
        return LANGUAGE_CODES[key]
    # fr-FR style fallback is not for IndicTrans2, but handle en/te etc.
    short = re.split(r"[-_ ]", key)[0]
    return LANGUAGE_CODES.get(short, default)


def direction_for(src_lang: str, tgt_lang: str) -> str:
    if src_lang == "eng_Latn" and tgt_lang in INDIC_CODES:
        return "en_indic"
    if src_lang in INDIC_CODES and tgt_lang == "eng_Latn":
        return "indic_en"
    if src_lang in INDIC_CODES and tgt_lang in INDIC_CODES:
        return "indic_indic"
    raise ValueError(f"Unsupported IndicTrans2 direction: {src_lang} -> {tgt_lang}")


def model_name_for(direction: str) -> str:
    if direction == "en_indic":
        return MODEL_EN_INDIC
    if direction == "indic_en":
        return MODEL_INDIC_EN
    if direction == "indic_indic":
        return MODEL_INDIC_INDIC
    raise ValueError(f"Unknown direction: {direction}")


class TranslateRequest(BaseModel):
    texts: List[str] = Field(default_factory=list)
    source_language: str = "English"
    target_language: str = "Telugu"
    domain: str = ""


class TranslateResponse(BaseModel):
    translations: List[str]
    engine: str
    source_code: str
    target_code: str
    direction: str
    model: str
    elapsed_seconds: float


class ModelBundle:
    def __init__(self, model_name: str):
        if IndicProcessor is None:
            raise RuntimeError(f"IndicTransToolkit import failed: {_indic_processor_import_error}")
        self.model_name = model_name
        dtype = torch.float16 if DEVICE.startswith("cuda") else torch.float32
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        ).to(DEVICE)
        self.model.eval()
        self.processor = IndicProcessor(inference=True)

    def translate(self, texts: List[str], src_lang: str, tgt_lang: str) -> List[str]:
        if not texts:
            return []
        cleaned_texts = [prepare_text(t) for t in texts]
        placeholders_by_index: List[Dict[str, str]] = []
        protected_texts: List[str] = []
        for text in cleaned_texts:
            safe, mapping = protect_tokens(text)
            protected_texts.append(safe)
            placeholders_by_index.append(mapping)

        batch = self.processor.preprocess_batch(protected_texts, src_lang=src_lang, tgt_lang=tgt_lang)
        inputs = self.tokenizer(
            batch,
            truncation=True,
            padding="longest",
            max_length=512,
            return_tensors="pt",
        ).to(DEVICE)

        with torch.no_grad():
            generated_tokens = self.model.generate(
                **inputs,
                use_cache=True,
                num_beams=NUM_BEAMS,
                num_return_sequences=1,
                max_new_tokens=MAX_NEW_TOKENS,
            )
        decoded = self.tokenizer.batch_decode(
            generated_tokens,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )
        post = self.processor.postprocess_batch(decoded, lang=tgt_lang)
        restored = [restore_tokens(out, placeholders_by_index[i]) for i, out in enumerate(post)]
        return restored


_loaded: Dict[str, ModelBundle] = {}


def get_model(direction: str) -> ModelBundle:
    name = model_name_for(direction)
    if direction not in _loaded:
        _loaded[direction] = ModelBundle(name)
    return _loaded[direction]


def prepare_text(text: str) -> str:
    text = str(text or "").replace("\u00a0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]
    return text


def protect_tokens(text: str) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}

    def repl(match: re.Match) -> str:
        key = f"__ESPH{len(mapping)}__"
        mapping[key] = match.group(0)
        return key

    return PROTECT_RE.sub(repl, text), mapping


def restore_tokens(text: str, mapping: Dict[str, str]) -> str:
    out = text or ""
    for key, value in mapping.items():
        out = out.replace(key, value)
        # Model sometimes inserts spaces around underscore-like tokens.
        out = out.replace(key.replace("_", " "), value)
    return out.strip()


app = FastAPI(title="ErrorSweep IndicTrans2 Worker", version="1.0.0")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "device": DEVICE,
        "loaded_directions": list(_loaded.keys()),
        "models": {
            "en_indic": MODEL_EN_INDIC,
            "indic_en": MODEL_INDIC_EN,
            "indic_indic": MODEL_INDIC_INDIC,
        },
    }


@app.get("/languages")
def languages() -> Dict[str, Any]:
    return {
        "languages": sorted(set(LANGUAGE_CODES.values())),
        "names": sorted(LANGUAGE_CODES.keys()),
    }


@app.post("/translate", response_model=TranslateResponse)
def translate(req: TranslateRequest) -> TranslateResponse:
    started = time.time()
    texts = [prepare_text(t) for t in req.texts]
    if not texts:
        return TranslateResponse(
            translations=[],
            engine="IndicTrans2",
            source_code="eng_Latn",
            target_code=normalize_lang(req.target_language, "tel_Telu"),
            direction="en_indic",
            model=MODEL_EN_INDIC,
            elapsed_seconds=0.0,
        )

    # ErrorSweep commonly sends source_language="auto". For Pro English->Indic files, use English as default.
    src = normalize_lang(req.source_language, "eng_Latn")
    tgt = normalize_lang(req.target_language, "tel_Telu")

    try:
        direction = direction_for(src, tgt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    bundle = get_model(direction)
    out: List[str] = []
    batch_size = max(1, DEFAULT_BATCH_SIZE)
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        out.extend(bundle.translate(batch, src_lang=src, tgt_lang=tgt))

    return TranslateResponse(
        translations=out,
        engine="IndicTrans2",
        source_code=src,
        target_code=tgt,
        direction=direction,
        model=bundle.model_name,
        elapsed_seconds=round(time.time() - started, 3),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("indictrans2_worker:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=False)
