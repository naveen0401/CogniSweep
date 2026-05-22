"""ErrorSweep speech/transcription helper.

Phase for subtitle/transcription workflows:
- If a user provides a BYO OpenAI key, use OpenAI speech-to-text.
- If no user key is provided, use Azure Speech fast transcription if configured.
- If neither is configured, return empty starter rows so the editor still opens.

Required only for no-key transcription/subtitling-from-video:
    AZURE_SPEECH_KEY
    AZURE_SPEECH_RESOURCE_NAME   # e.g. my-speech-resource, used in https://<resource>.cognitiveservices.azure.com
Optional:
    AZURE_SPEECH_API_VERSION = 2025-10-15
"""
from __future__ import annotations

import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from openai import OpenAI

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None


def _secret(name: str, default: str = "") -> str:
    env = os.environ.get(name)
    if env not in (None, ""):
        return str(env)
    if st is not None:
        try:
            val = st.secrets.get(name)
            if val not in (None, ""):
                return str(val)
        except Exception:
            pass
    return default


def speech_engine_label(user_openai_key: str = "") -> str:
    if user_openai_key:
        return "User AI transcription"
    if _secret("AZURE_SPEECH_KEY") and _secret("AZURE_SPEECH_RESOURCE_NAME"):
        return "Included speech transcription"
    return "Manual transcription"


def _default_rows(count: int = 10, workflow: str = "Transcription") -> List[Dict[str, Any]]:
    rows = []
    for i in range(max(1, int(count or 1))):
        rows.append({
            "id": i + 1,
            "start": round(i * 3.5, 3),
            "end": round(i * 3.5 + 3.0, 3),
            "source": "" if workflow == "Transcription" else "",
            "target": "",
            "status": "Draft" if workflow == "Transcription" else "Untranslated",
            "match": "Manual",
        })
    return rows


def _split_text_to_rows(text: str, workflow: str = "Transcription") -> List[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return _default_rows(10, workflow=workflow)

    # Split transcript into readable chunks without requiring exact timing.
    parts = re.split(r"(?<=[.!?à¥¤])\s+", text)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
        # fallback: chunk by words
        words = text.split()
        parts = [" ".join(words[i:i + 18]) for i in range(0, len(words), 18)]

    rows = []
    for i, part in enumerate(parts):
        start = round(i * 3.5, 3)
        end = round(start + max(2.0, min(6.0, len(part) / 16.0)), 3)
        rows.append({
            "id": i + 1,
            "start": start,
            "end": end,
            "source": "" if workflow == "Transcription" else part,
            "target": part if workflow == "Transcription" else "",
            "status": "AI Draft" if workflow == "Transcription" else "Transcribed Source",
            "match": "STT",
        })
    return rows or _default_rows(10, workflow=workflow)


def _openai_transcribe(
    media_bytes: bytes,
    filename: str,
    mime_type: str,
    api_key: str,
    locale: str = "en-US",
    prompt: str = "",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Use user's BYO OpenAI key for transcription.

    Uses whisper-1 because it supports verbose_json/SRT-style segment outputs.
    """
    client = OpenAI(api_key=api_key, timeout=180, max_retries=1)
    file_obj = io.BytesIO(media_bytes)
    file_obj.name = filename or "audio.mp4"

    usage = {
        "provider": "openai_user_speech",
        "engine": "whisper-1",
        "success": False,
        "error": "",
        "characters": 0,
        "requests": 1,
    }
    try:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=file_obj,
            response_format="verbose_json",
            language=(locale.split("-")[0] if locale else None),
            prompt=prompt or None,
        )
        # OpenAI SDK may return a model-like object.
        data = response.model_dump() if hasattr(response, "model_dump") else dict(response)
        segments = data.get("segments") or []
        rows = []
        if segments:
            for i, seg in enumerate(segments):
                text = str(seg.get("text", "")).strip()
                if not text:
                    continue
                rows.append({
                    "id": i + 1,
                    "start": float(seg.get("start", i * 3.5) or 0),
                    "end": float(seg.get("end", i * 3.5 + 3) or 0),
                    "source": "",
                    "target": text,
                    "status": "AI Draft",
                    "match": "STT",
                })
        else:
            rows = _split_text_to_rows(str(data.get("text", "")), workflow="Transcription")
        usage["success"] = True
        usage["characters"] = sum(len(r.get("target", "")) for r in rows)
        return rows or _default_rows(10), usage
    except Exception as exc:
        usage["error"] = str(exc)[:500]
        return _default_rows(10), usage


def _azure_fast_transcribe(
    media_bytes: bytes,
    filename: str,
    mime_type: str,
    locale: str = "en-US",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Use Azure Speech fast transcription for no-key users.

    Requires an Azure Speech/Foundry resource, not just Azure Translator.
    """
    key = _secret("AZURE_SPEECH_KEY")
    resource = _secret("AZURE_SPEECH_RESOURCE_NAME")
    api_version = _secret("AZURE_SPEECH_API_VERSION", "2025-10-15")

    usage = {
        "provider": "azure_speech",
        "engine": "fast_transcription",
        "success": False,
        "error": "",
        "characters": 0,
        "requests": 1,
    }
    if not key or not resource:
        usage["error"] = "Azure Speech is not configured. Add AZURE_SPEECH_KEY and AZURE_SPEECH_RESOURCE_NAME."
        return _default_rows(10), usage

    endpoint = f"https://{resource}.cognitiveservices.azure.com/speechtotext/transcriptions:transcribe?api-version={api_version}"
    definition = {"locales": [locale] if locale else []}
    files = {
        "audio": (filename or "media.webm", media_bytes, mime_type or "application/octet-stream"),
        "definition": (None, json.dumps(definition), "application/json"),
    }
    headers = {"Ocp-Apim-Subscription-Key": key}
    try:
        res = requests.post(endpoint, headers=headers, files=files, timeout=240)
        if res.status_code >= 400:
            usage["error"] = f"Azure Speech returned HTTP {res.status_code}: {res.text[:300]}"
            return _default_rows(10), usage
        data = res.json()

        rows: List[Dict[str, Any]] = []
        phrases = data.get("phrases") or []
        for i, phrase in enumerate(phrases):
            text = str(phrase.get("text") or phrase.get("displayText") or "").strip()
            if not text:
                continue
            start_ms = phrase.get("offsetMilliseconds") or phrase.get("offsetInTicks", 0) / 10000
            dur_ms = phrase.get("durationMilliseconds") or phrase.get("durationInTicks", 0) / 10000
            start = float(start_ms or 0) / 1000.0
            end = start + (float(dur_ms or 0) / 1000.0 if dur_ms else 3.0)
            rows.append({
                "id": i + 1,
                "start": round(start, 3),
                "end": round(max(end, start + 0.1), 3),
                "source": "",
                "target": text,
                "status": "AI Draft",
                "match": "STT",
            })

        if not rows:
            combined = data.get("combinedPhrases") or []
            text = " ".join(str(p.get("text", "")) for p in combined if isinstance(p, dict)).strip()
            rows = _split_text_to_rows(text, workflow="Transcription") if text else _default_rows(10)

        usage["success"] = True
        usage["characters"] = sum(len(r.get("target", "")) for r in rows)
        return rows or _default_rows(10), usage
    except Exception as exc:
        usage["error"] = str(exc)[:500]
        return _default_rows(10), usage


def transcribe_media_to_rows(
    media_bytes: bytes,
    filename: str,
    mime_type: str,
    user_openai_key: str = "",
    locale: str = "en-US",
    prompt: str = "",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Main speech router for subtitle/transcription editors."""
    if user_openai_key:
        return _openai_transcribe(media_bytes, filename, mime_type, user_openai_key, locale=locale, prompt=prompt)
    return _azure_fast_transcribe(media_bytes, filename, mime_type, locale=locale)

