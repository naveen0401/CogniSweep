"""ErrorSweep speech/transcription helper — v32.

Policy:
- Auto transcription is available only when the user provides a BYO API key.
- Azure Translator is a text translation engine only and is not used for speech-to-text.
- If no user key is provided, the app opens blank transcript rows for human editing.
"""
from __future__ import annotations

import io
import os
import re
from typing import Any, Dict, List, Tuple

from openai import OpenAI

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None


def speech_engine_label(user_openai_key: str = "") -> str:
    if user_openai_key:
        return "User API transcription"
    return "Manual transcription"


def _default_rows(count: int = 10, workflow: str = "Transcription") -> List[Dict[str, Any]]:
    rows = []
    for i in range(max(1, int(count or 1))):
        rows.append({
            "id": i + 1,
            "start": round(i * 3.5, 3),
            "end": round(i * 3.5 + 3.0, 3),
            "source": "",
            "target": "",
            "status": "Draft",
            "match": "Manual",
        })
    return rows


def _split_text_to_rows(text: str, workflow: str = "Transcription") -> List[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return _default_rows(10, workflow=workflow)

    parts = re.split(r"(?<=[.!?।])\s+", text)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= 1:
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
            "source": "",
            "target": part,
            "status": "AI Draft",
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
    """Use user's BYO OpenAI key for transcription."""
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


def transcribe_media_to_rows(
    media_bytes: bytes,
    filename: str,
    mime_type: str,
    user_openai_key: str = "",
    locale: str = "en-US",
    prompt: str = "",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Main speech router for subtitle/transcription editors.

    Auto transcription is only enabled with a user-provided API key.
    No-key users receive blank manual rows from app.py.
    """
    if not user_openai_key:
        return _default_rows(10), {
            "provider": "manual_transcription",
            "engine": "manual_editor",
            "success": False,
            "error": "No user API key available. Manual transcript rows were created.",
            "characters": 0,
            "requests": 0,
        }
    return _openai_transcribe(media_bytes, filename, mime_type, user_openai_key, locale=locale, prompt=prompt)

