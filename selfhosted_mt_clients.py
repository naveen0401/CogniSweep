"""HTTP clients and placeholder protection for CogniSweep self-hosted MT."""
from __future__ import annotations
import ipaddress
import logging
import os
import re, time
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Tuple
import requests

LOGGER = logging.getLogger(__name__)

class TranslationRouteError(RuntimeError):
    pass

PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|<[^>]+>|%[0-9$.\-+]*[sdif]|https?://\S+|www\.\S+|[\w.+-]+@[\w-]+\.[\w.-]+)")
PRIVATE_HOSTNAMES = {"localhost", "ip6-localhost", "ip6-loopback", "metadata.google.internal"}
PRIVATE_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home")
TRANSIENT_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


def _env_bool(name: str, default: bool = False) -> bool:
    value = str(os.getenv(name, "") or "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.getenv(name, "") or default))
    except Exception:
        value = default
    return max(minimum, min(value, maximum))


def _bounded_float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(str(os.getenv(name, "") or default))
    except Exception:
        value = default
    return max(minimum, min(value, maximum))


def _is_production() -> bool:
    env = str(os.getenv("ERRORSWEEP_ENV") or os.getenv("APP_ENV") or "").strip().lower()
    return env in {"prod", "production"}


def private_endpoints_allowed() -> bool:
    return _env_bool("SELF_HOSTED_MT_ALLOW_PRIVATE_ENDPOINTS", not _is_production())

def estimate_characters(texts: List[str]) -> int:
    return sum(len(str(t or "")) for t in texts)

def normalize_endpoint(endpoint: str) -> str:
    endpoint = (endpoint or "").strip().rstrip("/")
    if not endpoint:
        return ""
    if not endpoint.endswith("/translate"):
        endpoint += "/translate"
    return endpoint


def blocked_endpoint_reason(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "translation endpoint must be an absolute HTTP(S) URL"
    if parsed.username or parsed.password:
        return "translation endpoint must not include credentials"
    if _is_production() and parsed.scheme != "https" and not private_endpoints_allowed():
        return "production translation endpoints must use HTTPS"

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return "translation endpoint host is missing"
    if private_endpoints_allowed():
        return ""
    if host in PRIVATE_HOSTNAMES or host.endswith(PRIVATE_HOST_SUFFIXES):
        return "private/local translation endpoint host is not allowed"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return ""
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or str(ip) == "169.254.169.254":
        return "private/local translation endpoint address is not allowed"
    return ""


def validate_endpoint_for_request(endpoint: str) -> str:
    url = normalize_endpoint(endpoint)
    if not url:
        raise TranslationRouteError("Translation endpoint is missing.")
    reason = blocked_endpoint_reason(url)
    if reason:
        raise TranslationRouteError(reason)
    return url

def protect_text(text: str, extra_terms: Optional[List[str]] = None) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}
    output = str(text or "")
    def add_token(value: str) -> str:
        for tok, original in mapping.items():
            if original == value:
                return tok
        token = f"PH{len(mapping):03d}TOKEN"
        mapping[token] = value
        return f" {token} "
    for match in list(PLACEHOLDER_RE.finditer(output)):
        original = match.group(0)
        output = output.replace(original, add_token(original))
    for term in sorted(extra_terms or [], key=len, reverse=True):
        term = str(term or "").strip()
        if term and term in output:
            output = output.replace(term, add_token(term))
    return output, mapping

def restore_text(text: str, mapping: Dict[str, str]) -> str:
    output = str(text or "")
    for token, original in mapping.items():
        token_pattern = r"\s*".join(re.escape(ch) for ch in token)
        output = re.sub(token_pattern, original, output, flags=re.I)
        compact_pattern = re.escape(token).replace("TOKEN", r"\s*TOKEN")
        output = re.sub(compact_pattern, original, output, flags=re.I)
        if original and original not in output:
            output = f"{output.rstrip()} {original}".strip()
    output = re.sub(r"\s+([,.;:!?])", r"\1", output)
    return output.strip()

def _chunks(items: List[Any], size: int):
    for i in range(0, len(items), max(1, int(size or 20))):
        yield items[i:i+size]

def _retry_sleep_seconds(attempt: int) -> float:
    base = _bounded_float_env("SELF_HOSTED_MT_RETRY_BACKOFF_SECONDS", 0.5, 0.0, 10.0)
    return min(10.0, base * (2 ** max(0, attempt - 1)))


def _post(endpoint: str, api_key: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    url = validate_endpoint_for_request(endpoint)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    attempts = _bounded_int_env("SELF_HOSTED_MT_RETRIES", 2, 0, 5) + 1
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=max(1, int(timeout or 180)))
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(_retry_sleep_seconds(attempt))
                continue
            raise TranslationRouteError(f"Translation endpoint request failed: {exc}") from exc
        if res.status_code >= 400:
            try:
                details = res.json()
            except Exception as exc:
                LOGGER.debug("Translation endpoint error body is not JSON: %s", exc)
                details = res.text[:500]
            if res.status_code in TRANSIENT_HTTP_STATUS_CODES and attempt < attempts:
                time.sleep(_retry_sleep_seconds(attempt))
                continue
            raise TranslationRouteError(f"Translation endpoint returned HTTP {res.status_code}: {details}")
        break
    else:
        raise TranslationRouteError(f"Translation endpoint request failed: {last_error}")
    try:
        return res.json()
    except Exception as exc:
        raise TranslationRouteError(f"Translation endpoint did not return JSON: {exc}")

def _translate(provider: str, endpoint: str, api_key: str, source_language: str, target_language: str, texts: List[str], protected_terms: Optional[List[str]], timeout: int, batch_size: int) -> Tuple[List[str], Dict[str, Any]]:
    start=time.time()
    protected=[]; maps=[]
    for t in texts:
        p,m=protect_text(t, protected_terms)
        protected.append(p); maps.append(m)
    out=[]; requests_count=0
    for batch in _chunks(protected, batch_size):
        data=_post(endpoint, api_key, {"source_language": source_language, "target_language": target_language, "texts": batch}, timeout)
        batch_out=data.get("translations") or data.get("items") or data.get("outputs") or []
        if batch_out and isinstance(batch_out[0], dict):
            batch_out=[x.get("translation", "") for x in batch_out]
        if not isinstance(batch_out, list):
            raise TranslationRouteError(f"{provider} returned invalid translation format.")
        out.extend(str(x or "") for x in batch_out)
        requests_count += 1
    if len(out) < len(texts):
        out.extend([""]*(len(texts)-len(out)))
    out = out[:len(texts)]
    restored=[restore_text(t,m) for t,m in zip(out,maps)]
    return restored, {"provider": provider, "engine": provider, "managed": True, "characters": estimate_characters(texts), "requests": requests_count, "latency_ms": int((time.time()-start)*1000), "success": True, "error": ""}

def translate_with_indictrans2(*, endpoint: str, api_key: str, source_language: str, target_language: str, texts: List[str], protected_terms: Optional[List[str]]=None, timeout: int=180):
    return _translate("indictrans2", endpoint, api_key, source_language, target_language, texts, protected_terms, timeout, 20)

def translate_with_madlad(*, endpoint: str, api_key: str, source_language: str, target_language: str, texts: List[str], protected_terms: Optional[List[str]]=None, timeout: int=300):
    return _translate("madlad400", endpoint, api_key, source_language, target_language, texts, protected_terms, timeout, 8)

def translate_with_opus_mt(*, endpoint: str, api_key: str, source_language: str, target_language: str, texts: List[str], protected_terms: Optional[List[str]]=None, timeout: int=180):
    return _translate("opus_mt", endpoint, api_key, source_language, target_language, texts, protected_terms, timeout, 25)

