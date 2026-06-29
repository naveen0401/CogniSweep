"""Shared helpers for CogniSweep deployment checkers."""
from __future__ import annotations

import re
from typing import Iterable, List, Set


def cognisweep_env_alias(name: str) -> str:
    if name.startswith("ERRORSWEEP_"):
        return f"COGNISWEEP_{name[len('ERRORSWEEP_'):]}"
    return ""


def aliases_for(name: str) -> List[str]:
    alias = cognisweep_env_alias(name)
    return [name, alias] if alias else [name]


def missing_items_with_aliases(items: Iterable[str], text: str) -> List[str]:
    return [item for item in items if not any(name in text for name in aliases_for(item))]


def template_keys_include(keys: Set[str], name: str) -> bool:
    return any(alias in keys for alias in aliases_for(name))


def template_has_env_key(text: str, key: str) -> bool:
    return any(re.search(rf"^{re.escape(name)}\s*=", text, re.MULTILINE) for name in aliases_for(key))
