"""Sentence segmentation and reconstruction metadata for ErrorSweep Pro.

The Pro editor can expose one source paragraph/cell/node as several sentence
segments. These helpers keep enough metadata on each sentence row for exporters
to join reviewed targets back into the original container.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List


PRO_EXPORT_SUPPORTED_EXTENSIONS = {
    ".csv", ".docx", ".html", ".htm", ".json", ".pptx", ".srt", ".txt",
    ".vtt", ".xlsx", ".xlf", ".xliff", ".xml",
}

SENTENCE_END_CHARS = {".", "!", "?", "।", "。", "！", "？"}
SENTENCE_CLOSERS = set("\"')]}>>")
COMMON_ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc",
    "fig", "no", "dept", "inc", "ltd", "co", "corp", "e.g", "i.e",
}
TIMED_TEXT_KINDS = {"srt_cue", "vtt_cue"}


def safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def build_export_source_asset_from_bytes(data: bytes, file_name: str, mime_type: str = "") -> Dict[str, Any]:
    name = safe_text(file_name) or "translated_file"
    suffix = Path(name).suffix.lower()
    return {
        "file_name": name,
        "suffix": suffix,
        "mime_type": safe_text(mime_type) or "application/octet-stream",
        "size_bytes": len(data or b""),
        "bytes_b64": base64.b64encode(data or b"").decode("ascii"),
        "supported": suffix in PRO_EXPORT_SUPPORTED_EXTENSIONS,
    }


def _token_before_boundary(text: str, end_index: int) -> str:
    prefix = text[:end_index].rstrip(".!?।。！？")
    match = re.search(r"([A-Za-z](?:[A-Za-z]|\.)*)$", prefix)
    return match.group(1).lower() if match else ""


def _is_sentence_boundary(text: str, index: int) -> bool:
    char = text[index]
    if char not in SENTENCE_END_CHARS:
        return False
    if char == ".":
        previous_char = text[index - 1] if index > 0 else ""
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if previous_char.isdigit() and next_char.isdigit():
            return False
        if _token_before_boundary(text, index + 1) in COMMON_ABBREVIATIONS:
            return False
    return True


def split_text_into_sentence_units(text: str) -> List[Dict[str, Any]]:
    """Return sentence units with original offsets and following separators."""
    source = safe_text(text)
    if not source:
        return []

    units: List[Dict[str, Any]] = []
    start = 0
    index = 0
    length = len(source)
    while index < length:
        if not _is_sentence_boundary(source, index):
            index += 1
            continue

        end = index + 1
        while end < length and source[end] in SENTENCE_CLOSERS:
            end += 1
        next_start = end
        while next_start < length and source[next_start].isspace():
            next_start += 1

        if next_start >= length or next_start > end:
            sentence = source[start:end].strip()
            if sentence:
                units.append({
                    "text": sentence,
                    "start": start,
                    "end": end,
                    "joiner_after": source[end:next_start] if next_start < length else "",
                })
            start = next_start
            index = next_start
            continue
        index += 1

    if start < length:
        sentence = source[start:].strip()
        if sentence:
            units.append({"text": sentence, "start": start, "end": length, "joiner_after": ""})

    return units if len(units) > 1 else [{"text": source, "start": 0, "end": len(source), "joiner_after": ""}]


def _jsonable(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=safe_text))
    except Exception:
        return safe_text(value)


def _base_export_ref(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("export_ref") if isinstance(row.get("export_ref"), dict) else {}
    return {
        key: _jsonable(value)
        for key, value in raw.items()
        if key not in {"segment_group_id", "sentence_index", "sentence_count", "original_container_source"}
    }


def _segment_group_id(row: Dict[str, Any], row_index: int, source: str, export_ref: Dict[str, Any]) -> str:
    material = {
        "row_index": row_index,
        "id": safe_text(row.get("id")),
        "location": safe_text(row.get("location")),
        "source": source,
        "export_ref": export_ref,
    }
    digest = hashlib.sha1(json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"proseg-{digest}"


def sentence_segment_rows_for_pro(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Split Pro source rows into sentence rows while preserving export maps."""
    segmented: List[Dict[str, Any]] = []
    for row_index, row in enumerate(rows or [], start=1):
        source = safe_text(row.get("source") or row.get("target"))
        export_ref = _base_export_ref(row)
        if safe_text(export_ref.get("kind")) in TIMED_TEXT_KINDS:
            copied = dict(row)
            copied["id"] = copied.get("id") or len(segmented) + 1
            segmented.append(copied)
            continue

        source_units = split_text_into_sentence_units(source)
        if len(source_units) <= 1:
            copied = dict(row)
            copied["id"] = copied.get("id") or len(segmented) + 1
            segmented.append(copied)
            continue

        target_units = split_text_into_sentence_units(safe_text(row.get("target")))
        split_target = len(target_units) == len(source_units)
        group_id = _segment_group_id(row, row_index, source, export_ref)
        sentence_count = len(source_units)
        for sentence_index, unit in enumerate(source_units):
            target_text = target_units[sentence_index]["text"] if split_target else ""
            location = safe_text(row.get("location") or f"Segment {row.get('id') or row_index}")
            mapped_ref = {
                **export_ref,
                "segment_group_id": group_id,
                "sentence_index": sentence_index,
                "sentence_count": sentence_count,
                "original_container_source": source,
            }
            reconstruction_map = {
                "type": "sentence_split",
                "segment_group_id": group_id,
                "sentence_index": sentence_index,
                "sentence_count": sentence_count,
                "original_id": row.get("id", row_index),
                "original_location": location,
                "original_source": source,
                "source_start": unit["start"],
                "source_end": unit["end"],
                "joiner_after": unit["joiner_after"],
                "export_ref": export_ref,
            }
            item = {
                **row,
                "id": len(segmented) + 1,
                "original_id": row.get("id", row_index),
                "location": f"{location} - Sentence {sentence_index + 1}/{sentence_count}",
                "source": unit["text"],
                "target": target_text,
                "status": "Existing" if target_text else "Untranslated",
                "match": row.get("match", ""),
                "export_ref": mapped_ref,
                "reconstruction_map": reconstruction_map,
            }
            segmented.append(item)
    return segmented
