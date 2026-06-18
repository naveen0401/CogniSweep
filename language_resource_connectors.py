"""Server-side language-resource connector adapters for CogniSweep.

The editor asks this module for normalized TM, glossary, and DNT results.
Provider-specific API keys stay on the server: keys are encrypted before
persistence, decrypted only immediately before a provider call, and never
returned to browser JavaScript.
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests
from cryptography.fernet import Fernet, InvalidToken


DEFAULT_TIMEOUT_SECONDS = 4
DEFAULT_CACHE_SECONDS = 600
MAX_LOOKUP_TEXT_CHARS = 5000


class LanguageResourceError(Exception):
    """Safe-to-display connector error."""

    def __init__(self, code: str, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class LanguageResourceSecretError(LanguageResourceError):
    """Raised when encryption/decryption cannot be completed."""


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value)


def derive_fernet_key(master_key: str) -> bytes:
    master = _safe_text(master_key).strip()
    if len(master) < 32:
        raise LanguageResourceSecretError(
            "missing_master_key",
            "Language-resource encryption key is missing or too short.",
        )
    digest = hashlib.sha256(master.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_api_secret(api_secret: str, master_key: str) -> str:
    cleaned = _safe_text(api_secret).strip()
    if not cleaned:
        return ""
    token = Fernet(derive_fernet_key(master_key)).encrypt(cleaned.encode("utf-8"))
    return token.decode("ascii")


def decrypt_api_secret(encrypted_secret: str, master_key: str) -> str:
    encrypted = _safe_text(encrypted_secret).strip()
    if not encrypted:
        return ""
    try:
        value = Fernet(derive_fernet_key(master_key)).decrypt(encrypted.encode("ascii"), ttl=None)
    except InvalidToken as exc:
        raise LanguageResourceSecretError(
            "invalid_encrypted_secret",
            "Saved language-resource API key could not be decrypted.",
        ) from exc
    return value.decode("utf-8")


def mask_secret_tail(secret_or_tail: str) -> str:
    value = _safe_text(secret_or_tail).strip()
    tail = value[-4:] if len(value) > 4 else value
    return f"{'•' * 8}{tail}" if tail else "Not saved"


def lookup_hash(
    connection_id: str,
    source_text: str,
    source_language: str,
    target_language: str,
    resource_type: str = "all",
) -> str:
    payload = {
        "connection_id": _safe_text(connection_id),
        "source_text": _safe_text(source_text)[:MAX_LOOKUP_TEXT_CHARS],
        "source_language": _safe_text(source_language).lower(),
        "target_language": _safe_text(target_language).lower(),
        "resource_type": _safe_text(resource_type).lower(),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_resource_list(payload: Any, *keys: str) -> List[Dict[str, str]]:
    """Return provider resources as [{id, name, type}]."""
    candidates: Any = payload
    if isinstance(payload, dict):
        for key in keys:
            if isinstance(payload.get(key), list):
                candidates = payload.get(key)
                break
    if not isinstance(candidates, list):
        return []
    resources: List[Dict[str, str]] = []
    for idx, item in enumerate(candidates):
        if isinstance(item, str):
            rid = item
            name = item
        elif isinstance(item, dict):
            rid = _safe_text(item.get("id") or item.get("resource_id") or item.get("key") or item.get("name") or idx)
            name = _safe_text(item.get("name") or item.get("label") or item.get("title") or rid)
        else:
            continue
        if rid or name:
            resources.append({"id": rid, "name": name, "type": _safe_text(keys[0] if keys else "resource")})
    return resources


def _first_list(payload: Any, keys: Iterable[str]) -> List[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def normalize_tm_results(payload: Any, provider: str, connection_id: str) -> List[Dict[str, Any]]:
    results = []
    for item in _first_list(payload, ("matches", "results", "tm", "translation_memories")):
        if not isinstance(item, dict):
            continue
        source_text = _safe_text(item.get("source_text") or item.get("source") or item.get("src"))
        target_text = _safe_text(item.get("target_text") or item.get("target") or item.get("translation") or item.get("tgt"))
        if not source_text and not target_text:
            continue
        score = item.get("match_score", item.get("score", item.get("similarity")))
        try:
            match_score: Any = round(float(score), 2)
        except (TypeError, ValueError):
            match_score = ""
        results.append(
            {
                "provider": provider,
                "connection_id": connection_id,
                "resource_name": _safe_text(item.get("resource_name") or item.get("memory") or item.get("tm_name")),
                "source_text": source_text,
                "target_text": target_text,
                "match_score": match_score,
                "source_language": _safe_text(item.get("source_language") or item.get("source_lang")),
                "target_language": _safe_text(item.get("target_language") or item.get("target_lang")),
                "domain": _safe_text(item.get("domain")),
                "updated_at": _safe_text(item.get("updated_at") or item.get("modified_at")),
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            }
        )
    return results


def normalize_glossary_results(payload: Any, provider: str, connection_id: str = "") -> List[Dict[str, Any]]:
    results = []
    for item in _first_list(payload, ("terms", "results", "glossary", "glossaries", "entries")):
        if not isinstance(item, dict):
            continue
        source_term = _safe_text(item.get("source_term") or item.get("source") or item.get("term"))
        target_term = _safe_text(item.get("target_term") or item.get("target") or item.get("translation"))
        if not source_term:
            continue
        results.append(
            {
                "provider": provider,
                "connection_id": connection_id,
                "source_term": source_term,
                "target_term": target_term,
                "definition": _safe_text(item.get("definition") or item.get("description")),
                "part_of_speech": _safe_text(item.get("part_of_speech") or item.get("pos")),
                "case_sensitive": bool(item.get("case_sensitive", False)),
                "status": _safe_text(item.get("status") or "approved"),
                "domain": _safe_text(item.get("domain")),
                "resource_name": _safe_text(item.get("resource_name") or item.get("glossary_name") or item.get("termbase")),
            }
        )
    return results


def normalize_dnt_results(payload: Any, provider: str, connection_id: str = "") -> List[Dict[str, Any]]:
    results = []
    for item in _first_list(payload, ("dnt", "terms", "results", "do_not_translate")):
        if isinstance(item, str):
            item = {"term": item}
        if not isinstance(item, dict):
            continue
        term = _safe_text(item.get("term") or item.get("source_term") or item.get("source"))
        if not term:
            continue
        results.append(
            {
                "provider": provider,
                "connection_id": connection_id,
                "term": term,
                "match_mode": _safe_text(item.get("match_mode") or "exact"),
                "case_sensitive": bool(item.get("case_sensitive", True)),
                "scope": _safe_text(item.get("scope") or "personal"),
                "resource_name": _safe_text(item.get("resource_name") or item.get("dnt_list") or item.get("name")),
                "instruction": _safe_text(item.get("instruction") or "Preserve exactly"),
            }
        )
    return results


@dataclass
class ConnectorConfig:
    connection_id: str
    provider: str
    connection_name: str
    base_url: str
    auth_type: str
    api_secret: str
    organization_id: str = ""
    provider_workspace_id: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


class LanguageResourceConnector(ABC):
    def __init__(self, config: ConnectorConfig) -> None:
        self.config = config

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_translation_memories(self) -> List[Dict[str, str]]:
        raise NotImplementedError

    @abstractmethod
    def list_glossaries(self) -> List[Dict[str, str]]:
        raise NotImplementedError

    @abstractmethod
    def list_dnt_resources(self) -> List[Dict[str, str]]:
        raise NotImplementedError

    @abstractmethod
    def search_tm(self, source_text: str, source_language: str, target_language: str, limit: int = 5, resource_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def lookup_terms(self, source_text: str, source_language: str, target_language: str, resource_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def lookup_dnt(self, source_text: str, source_language: str, resource_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def refresh_token_if_needed(self) -> None:
        return None

    def normalize_error(self, error: Exception) -> LanguageResourceError:
        if isinstance(error, LanguageResourceError):
            return error
        if isinstance(error, requests.Timeout):
            return LanguageResourceError("timeout", "External language resource provider timed out.")
        if isinstance(error, requests.HTTPError):
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code in {401, 403}:
                return LanguageResourceError("auth_failed", "External provider rejected the saved API key or scope.", status_code)
            if status_code == 429:
                return LanguageResourceError("rate_limited", "External provider rate limit was reached.", status_code)
            return LanguageResourceError("provider_http_error", "External provider returned an error.", status_code)
        if isinstance(error, requests.RequestException):
            return LanguageResourceError("provider_unreachable", "External provider is unreachable.")
        return LanguageResourceError("provider_error", "External language resource lookup failed.")


class GenericRestLanguageResourceConnector(LanguageResourceConnector):
    """Generic REST adapter.

    Expected endpoints:
    - GET /resources
    - POST /tm/search
    - POST /terms/lookup
    - POST /dnt/lookup

    Provider responses can use common keys such as results/matches/terms; the
    normalizers below convert them into CogniSweep's internal result format.
    """

    def _url(self, path: str) -> str:
        base = self.config.base_url.rstrip("/") + "/"
        return urljoin(base, path.lstrip("/"))

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        auth_type = self.config.auth_type.lower()
        if self.config.api_secret:
            if auth_type in {"api key", "api_key", "x-api-key"}:
                headers["X-API-Key"] = self.config.api_secret
            else:
                headers["Authorization"] = f"Bearer {self.config.api_secret}"
        if self.config.organization_id:
            headers["X-Organization-ID"] = self.config.organization_id
        if self.config.provider_workspace_id:
            headers["X-Workspace-ID"] = self.config.provider_workspace_id
        return headers

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = requests.request(
                method,
                self._url(path),
                headers=self._headers(),
                timeout=max(1, int(self.config.timeout_seconds or DEFAULT_TIMEOUT_SECONDS)),
                **kwargs,
            )
            response.raise_for_status()
        except Exception as exc:
            raise self.normalize_error(exc) from exc
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise LanguageResourceError("malformed_response", "External provider returned non-JSON data.") from exc

    def _resources_payload(self) -> Dict[str, Any]:
        try:
            payload = self._request("GET", "/resources")
        except LanguageResourceError as exc:
            if exc.status_code == 404:
                payload = self._request("GET", "/health")
            else:
                raise
        return payload if isinstance(payload, dict) else {}

    def test_connection(self) -> Dict[str, Any]:
        start = time.perf_counter()
        payload = self._resources_payload()
        latency_ms = int((time.perf_counter() - start) * 1000)
        tm = normalize_resource_list(payload, "translation_memories", "tm", "memories")
        glossaries = normalize_resource_list(payload, "glossaries", "termbases", "terms")
        dnt = normalize_resource_list(payload, "dnt_resources", "dnt", "do_not_translate")
        identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
        return {
            "status": "connected",
            "provider_account_identity": _safe_text(
                identity.get("email") or identity.get("name") or payload.get("account") or payload.get("provider") or self.config.provider
            ),
            "latency_ms": latency_ms,
            "tm_count": len(tm),
            "glossary_count": len(glossaries),
            "dnt_count": len(dnt),
            "missing_scopes": payload.get("missing_scopes") if isinstance(payload.get("missing_scopes"), list) else [],
            "translation_memories": tm,
            "glossaries": glossaries,
            "dnt_resources": dnt,
        }

    def list_translation_memories(self) -> List[Dict[str, str]]:
        return normalize_resource_list(self._resources_payload(), "translation_memories", "tm", "memories")

    def list_glossaries(self) -> List[Dict[str, str]]:
        return normalize_resource_list(self._resources_payload(), "glossaries", "termbases", "terms")

    def list_dnt_resources(self) -> List[Dict[str, str]]:
        return normalize_resource_list(self._resources_payload(), "dnt_resources", "dnt", "do_not_translate")

    def search_tm(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
        limit: int = 5,
        resource_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        payload = {
            "source_text": _safe_text(source_text)[:MAX_LOOKUP_TEXT_CHARS],
            "source_language": _safe_text(source_language),
            "target_language": _safe_text(target_language),
            "limit": max(1, min(int(limit or 5), 10)),
            "resource_ids": resource_ids or [],
        }
        return normalize_tm_results(
            self._request("POST", "/tm/search", json=payload),
            self.config.connection_name or self.config.provider,
            self.config.connection_id,
        )

    def lookup_terms(
        self,
        source_text: str,
        source_language: str,
        target_language: str,
        resource_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        payload = {
            "source_text": _safe_text(source_text)[:MAX_LOOKUP_TEXT_CHARS],
            "source_language": _safe_text(source_language),
            "target_language": _safe_text(target_language),
            "resource_ids": resource_ids or [],
        }
        return normalize_glossary_results(
            self._request("POST", "/terms/lookup", json=payload),
            self.config.connection_name or self.config.provider,
            self.config.connection_id,
        )

    def lookup_dnt(
        self,
        source_text: str,
        source_language: str,
        resource_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        payload = {
            "source_text": _safe_text(source_text)[:MAX_LOOKUP_TEXT_CHARS],
            "source_language": _safe_text(source_language),
            "resource_ids": resource_ids or [],
        }
        return normalize_dnt_results(
            self._request("POST", "/dnt/lookup", json=payload),
            self.config.connection_name or self.config.provider,
            self.config.connection_id,
        )


class InternalCogniSweepResourceConnector:
    """Marker for existing in-app TM/glossary/DNT resources.

    Internal resources are already loaded by app.py from saved workspace rules
    and session state. This class documents that they are part of the same
    connector model, but it intentionally does not receive external secrets.
    """


def make_connector(config: ConnectorConfig) -> LanguageResourceConnector:
    provider = _safe_text(config.provider).lower()
    if provider in {"generic rest", "generic_rest", "generic", "rest"}:
        return GenericRestLanguageResourceConnector(config)
    raise LanguageResourceError("unsupported_provider", "This language-resource provider is not supported yet.")
