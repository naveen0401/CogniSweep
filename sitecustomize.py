"""Runtime compatibility fixes for the ErrorSweep Streamlit shell.

Python imports ``sitecustomize`` automatically when this repository root is on
``sys.path``. Keep this module small and defensive: it only patches Streamlit
after Streamlit itself has been imported, and it injects a CSS fallback when the
authenticated app shell marker is rendered.
"""
from __future__ import annotations

import builtins
import functools
import logging
from typing import Any

LOGGER = logging.getLogger(__name__)

_ORIGINAL_IMPORT = builtins.__import__
_STREAMLIT_PATCHED = False

_SHELL_VISIBILITY_FALLBACK_CSS = """
<style data-errorsweep-shell-visibility-fallback="true">
body:has(#errorsweep-root-shell-marker) [data-testid="stAppViewContainer"],
body:has(#errorsweep-root-shell-marker) [data-testid="stMain"],
body:has(#errorsweep-root-shell-marker) [data-testid="stMainBlockContainer"],
body:has(#errorsweep-root-shell-marker) .block-container,
body:has(#errorsweep-root-shell-marker) .block-container > div[data-testid="stVerticalBlock"],
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_app_shell,
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_app_shell > div[data-testid="stVerticalBlock"] {
  min-height: 0 !important;
  visibility: visible !important;
  opacity: 1 !important;
}
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_shell_content {
  display: block !important;
  box-sizing: border-box !important;
  min-height: 0 !important;
  height: calc(100dvh - 76px) !important;
  max-height: calc(100dvh - 76px) !important;
  width: 100% !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  overscroll-behavior: contain !important;
  scrollbar-gutter: stable both-edges !important;
  padding: var(--es-shell-frame-padding, 0 18px 0) !important;
  visibility: visible !important;
  opacity: 1 !important;
}
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_shell_content > div[data-testid="stVerticalBlock"],
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_page_frame,
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_page_frame > div[data-testid="stVerticalBlock"] {
  display: block !important;
  box-sizing: border-box !important;
  min-height: 1px !important;
  height: auto !important;
  max-height: none !important;
  width: 100% !important;
  max-width: var(--es-shell-content-width, min(1760px, calc(100vw - 56px))) !important;
  margin-left: auto !important;
  margin-right: auto !important;
  overflow: visible !important;
  visibility: visible !important;
  opacity: 1 !important;
}
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_page_frame .element-container,
body:has(#errorsweep-root-shell-marker) .st-key-errorsweep_page_frame [data-testid="stElementContainer"] {
  visibility: visible !important;
  opacity: 1 !important;
}
</style>
"""


def _patch_streamlit_markdown() -> None:
    """Inject authenticated-shell fallback CSS after the root shell marker."""
    global _STREAMLIT_PATCHED
    if _STREAMLIT_PATCHED:
        return
    try:
        import streamlit as st  # type: ignore
    except Exception:
        return

    original_markdown = getattr(st, "markdown", None)
    if not callable(original_markdown):
        _STREAMLIT_PATCHED = True
        return
    if getattr(original_markdown, "_errorsweep_shell_fallback", False):
        _STREAMLIT_PATCHED = True
        return

    @functools.wraps(original_markdown)
    def markdown_with_shell_fallback(body: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_markdown(body, *args, **kwargs)
        try:
            if "errorsweep-root-shell-marker" in str(body):
                original_markdown(_SHELL_VISIBILITY_FALLBACK_CSS, unsafe_allow_html=True)
        except Exception:
            LOGGER.debug("Unable to inject ErrorSweep shell visibility fallback", exc_info=True)
        return result

    setattr(markdown_with_shell_fallback, "_errorsweep_shell_fallback", True)
    st.markdown = markdown_with_shell_fallback  # type: ignore[method-assign]
    _STREAMLIT_PATCHED = True


def _errorsweep_import_hook(name: str, globals: Any = None, locals: Any = None, fromlist: tuple[Any, ...] = (), level: int = 0) -> Any:
    module = _ORIGINAL_IMPORT(name, globals, locals, fromlist, level)
    if name == "streamlit" or name.startswith("streamlit."):
        _patch_streamlit_markdown()
    return module


if not getattr(builtins, "_errorsweep_import_hook_installed", False):
    setattr(builtins, "_errorsweep_import_hook_installed", True)
    builtins.__import__ = _errorsweep_import_hook
