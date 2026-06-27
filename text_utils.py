"""Small text normalization helpers shared across CogniSweep modules."""
from __future__ import annotations

from typing import Any


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\u00A0", " ").strip()
