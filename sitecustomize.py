"""Minimal ErrorSweep query-parameter normalization.

This module does not render UI, open tabs, change navigation, or patch layout. It
only repairs malformed protected-route query keys before app.py reads them. In
particular, some editor links can arrive as `%3Breview_id=...`, which Streamlit
exposes as `;review_id`; app.py expects `review_id`.
"""
from __future__ import annotations

import builtins
import logging
import re
import sys
from typing import Any
from urllib.parse import unquote

LOGGER = logging.getLogger(__name__)
_ORIGINAL_IMPORT = builtins.__import__
_PATCH_INSTALLED_ATTR = "_errorsweep_query_param_normalizer_installed"
_CANONICAL_ROUTE_KEYS = {
    "es_page",
    "es_editor",
    "job_id",
    "review_id",
    "task_id",
    "es_session",
    "es_restore",
    "tool_tab",
    "return_to",
    "route",
    "public",
}


def _query_value(params: Any, key: str) -> str:
    try:
        value = params.get(key, "")
        if isinstance(value, list):
            return str(value[0] if value else "")
        return str(value or "")
    except Exception:
        return ""


def _canonical_key(raw_key: Any) -> str:
    key = str(raw_key or "").strip()
    key = unquote(key)
    key = key.replace("%3B", ";").replace("%3b", ";")
    while key.startswith((";", "&", "?")):
        key = key[1:]
    if key.startswith("amp;"):
        key = key[4:]
    if ";" in key:
        tail = key.split(";")[-1]
        if tail in _CANONICAL_ROUTE_KEYS:
            key = tail
    return key


def _normalize_streamlit_query_params() -> None:
    """Repair malformed query keys such as `;review_id` -> `review_id`."""
    st = sys.modules.get("streamlit")
    if st is None:
        return
    try:
        params = st.query_params
    except Exception:
        return

    try:
        # Copy malformed keys to their canonical names before app.py route logic
        # calls query_get("review_id") / query_get("job_id") / query_get("es_editor").
        for raw_key in list(params.keys()):
            clean_key = _canonical_key(raw_key)
            if clean_key == raw_key or clean_key not in _CANONICAL_ROUTE_KEYS:
                continue
            value = _query_value(params, raw_key)
            if value and not _query_value(params, clean_key):
                params[clean_key] = value
            try:
                del params[raw_key]
            except Exception:
                pass

        # Handle defensive cases where the bad delimiter was embedded into the
        # es_page value instead of parsed as a separate key.
        es_page = _query_value(params, "es_page")
        embedded_review = re.search(r"(?:^|[;&])review_id=([^&;]+)", es_page)
        if embedded_review and not _query_value(params, "review_id"):
            params["review_id"] = embedded_review.group(1)
            params["es_page"] = re.split(r"[;&]review_id=", es_page, 1)[0].strip() or "Human Review Editor"

        embedded_job = re.search(r"(?:^|[;&])job_id=([^&;]+)", es_page)
        if embedded_job and not _query_value(params, "job_id"):
            params["job_id"] = embedded_job.group(1)
            params["es_page"] = re.split(r"[;&]job_id=", es_page, 1)[0].strip() or params.get("es_page", "")
    except Exception:
        LOGGER.debug("Unable to normalize ErrorSweep query parameters", exc_info=True)


def _errorsweep_import_hook(name: str, globals: Any = None, locals: Any = None, fromlist: tuple[Any, ...] = (), level: int = 0) -> Any:
    module = _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)
    if name == "streamlit" or name.startswith("streamlit."):
        _normalize_streamlit_query_params()
    return module


if not getattr(builtins, _PATCH_INSTALLED_ATTR, False):
    setattr(builtins, _PATCH_INSTALLED_ATTR, True)
    builtins.__import__ = _errorsweep_import_hook

# Also run once in case Streamlit was imported before this module was loaded.
_normalize_streamlit_query_params()
