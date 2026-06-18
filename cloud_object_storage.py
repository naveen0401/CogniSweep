"""Cloud object storage adapter for CogniSweep.

The app can run fully in local mode, but production deployments should set one
of these providers so uploaded files and media previews survive app restarts and
multi-instance scaling:

- Supabase Storage: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_STORAGE_BUCKET
- S3-compatible: S3_BUCKET plus normal AWS_* credentials, optional S3_ENDPOINT_URL
- Google Cloud Storage: GCS_BUCKET plus application-default credentials
"""
from __future__ import annotations

import logging
import mimetypes
import os
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

import requests

LOGGER = logging.getLogger(__name__)


def _cognisweep_env_alias(name: str) -> str:
    if name.startswith("ERRORSWEEP_"):
        return f"COGNISWEEP_{name[len('ERRORSWEEP_'):]}"
    return ""


def _env_value(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value not in (None, ""):
        return str(value)
    alias = _cognisweep_env_alias(name)
    if alias:
        value = os.environ.get(alias)
        if value not in (None, ""):
            return str(value)
    return default


DEFAULT_TIMEOUT = int(_env_value("ERRORSWEEP_OBJECT_STORAGE_TIMEOUT", "60"))


def _secret(name: str, default: str = "") -> str:
    value = _env_value(name, "")
    if value not in (None, ""):
        return str(value)
    try:
        import streamlit as st

        value = st.secrets.get(name)
        if value not in (None, ""):
            return str(value)
        alias = _cognisweep_env_alias(name)
        if alias:
            value = st.secrets.get(alias)
            if value not in (None, ""):
                return str(value)
    except Exception as exc:
        LOGGER.debug("Unable to read secret %s: %s", name, exc)
    return default


def _bool_secret(name: str, default: bool = False) -> bool:
    value = _secret(name, "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _safe_segment(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(value or "").strip())
    return cleaned.strip("._") or "item"


def object_storage_provider() -> str:
    configured = _secret("ERRORSWEEP_OBJECT_STORAGE_PROVIDER", "").strip().lower()
    if configured:
        return configured
    if _secret("SUPABASE_STORAGE_BUCKET", "") and _secret("SUPABASE_URL", "") and _secret("SUPABASE_SERVICE_ROLE_KEY", ""):
        return "supabase"
    if _secret("S3_BUCKET", ""):
        return "s3"
    if _secret("GCS_BUCKET", ""):
        return "gcs"
    return "local"


def object_storage_bucket(provider: Optional[str] = None) -> str:
    provider = provider or object_storage_provider()
    if provider == "supabase":
        return _secret("SUPABASE_STORAGE_BUCKET", "")
    if provider == "s3":
        return _secret("S3_BUCKET", "")
    if provider == "gcs":
        return _secret("GCS_BUCKET", "")
    return _secret("ERRORSWEEP_OBJECT_STORAGE_BUCKET", "local")


def local_object_storage_root() -> Path:
    configured = _secret("ERRORSWEEP_OBJECT_STORAGE_DIR", "")
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / "errorsweep_object_storage"
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_object_key(workspace: str, purpose: str, object_id: str, file_name: str) -> str:
    suffix = Path(file_name or "file").suffix
    base_name = _safe_segment(Path(file_name or "file").stem)
    if suffix:
        base_name = f"{base_name}{suffix.lower()}"
    return "/".join(
        [
            _safe_segment(workspace or "workspace"),
            _safe_segment(purpose or "files"),
            _safe_segment(object_id or "object"),
            base_name,
        ]
    )


def _supabase_headers(content_type: str = "") -> Dict[str, str]:
    key = _secret("SUPABASE_SERVICE_ROLE_KEY", "")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _supabase_url() -> str:
    return _secret("SUPABASE_URL", "").rstrip("/")


def _put_supabase_file(path: Path, key: str, content_type: str) -> Dict[str, Any]:
    url = f"{_supabase_url()}/storage/v1/object/{quote(object_storage_bucket('supabase'))}/{quote(key, safe='/')}"
    headers = _supabase_headers(content_type)
    headers["x-upsert"] = "true"
    with path.open("rb") as handle:
        response = requests.post(url, headers=headers, data=handle, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return {
        "storage_provider": "supabase",
        "storage_bucket": object_storage_bucket("supabase"),
        "storage_key": key,
        "public_url": public_url_for_key(key),
        "status": "stored",
    }


def _put_s3_file(path: Path, key: str, content_type: str) -> Dict[str, Any]:
    try:
        import boto3
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("boto3 is required for S3 object storage. Install requirements.txt.") from exc

    client_kwargs: Dict[str, Any] = {}
    endpoint = _secret("S3_ENDPOINT_URL", "")
    region = _secret("AWS_REGION", _secret("AWS_DEFAULT_REGION", ""))
    if endpoint:
        client_kwargs["endpoint_url"] = endpoint
    if region:
        client_kwargs["region_name"] = region
    client = boto3.client("s3", **client_kwargs)
    extra_args = {"ContentType": content_type} if content_type else {}
    client.upload_file(str(path), object_storage_bucket("s3"), key, ExtraArgs=extra_args)
    return {
        "storage_provider": "s3",
        "storage_bucket": object_storage_bucket("s3"),
        "storage_key": key,
        "public_url": public_url_for_key(key),
        "status": "stored",
    }


def _put_gcs_file(path: Path, key: str, content_type: str) -> Dict[str, Any]:
    try:
        from google.cloud import storage
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("google-cloud-storage is required for GCS object storage. Install requirements.txt.") from exc

    client = storage.Client()
    bucket = client.bucket(object_storage_bucket("gcs"))
    blob = bucket.blob(key)
    blob.upload_from_filename(str(path), content_type=content_type or None)
    return {
        "storage_provider": "gcs",
        "storage_bucket": object_storage_bucket("gcs"),
        "storage_key": key,
        "public_url": public_url_for_key(key),
        "status": "stored",
    }


def _put_local_file(path: Path, key: str, content_type: str) -> Dict[str, Any]:
    target = local_object_storage_root() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() != target.resolve():
        shutil.copyfile(path, target)
    return {
        "storage_provider": "local",
        "storage_bucket": object_storage_bucket("local"),
        "storage_key": str(target),
        "local_path": str(target),
        "public_url": "",
        "status": "stored",
    }


def put_file(path: Path, key: str, content_type: str = "") -> Dict[str, Any]:
    path = Path(path)
    content_type = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    provider = object_storage_provider()
    if provider == "supabase":
        return _put_supabase_file(path, key, content_type)
    if provider == "s3":
        return _put_s3_file(path, key, content_type)
    if provider == "gcs":
        return _put_gcs_file(path, key, content_type)
    return _put_local_file(path, key, content_type)


def public_url_for_key(key: str) -> str:
    if not _bool_secret("ERRORSWEEP_OBJECT_STORAGE_ALLOW_PUBLIC_URLS", False):
        return ""
    provider = object_storage_provider()
    if provider == "supabase" and _secret("SUPABASE_STORAGE_PUBLIC", "").strip().lower() in {"1", "true", "yes"}:
        return f"{_supabase_url()}/storage/v1/object/public/{quote(object_storage_bucket('supabase'))}/{quote(key, safe='/')}"
    if provider == "s3" and _secret("S3_PUBLIC_BASE_URL", ""):
        return f"{_secret('S3_PUBLIC_BASE_URL').rstrip('/')}/{quote(key, safe='/')}"
    if provider == "gcs" and _secret("GCS_PUBLIC_BASE_URL", ""):
        return f"{_secret('GCS_PUBLIC_BASE_URL').rstrip('/')}/{quote(key, safe='/')}"
    return ""


def signed_url_for_key(key: str, expires_in: int = 3600) -> str:
    provider = object_storage_provider()
    if not key:
        return ""
    public_url = public_url_for_key(key)
    if public_url:
        return public_url
    if provider == "supabase":
        url = f"{_supabase_url()}/storage/v1/object/sign/{quote(object_storage_bucket('supabase'))}/{quote(key, safe='/')}"
        response = requests.post(
            url,
            headers={**_supabase_headers("application/json"), "Content-Type": "application/json"},
            json={"expiresIn": int(expires_in)},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        signed = str((response.json() or {}).get("signedURL") or "")
        return f"{_supabase_url()}{signed}" if signed.startswith("/") else signed
    if provider == "s3":
        try:
            import boto3
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("boto3 is required for S3 signed URLs. Install requirements.txt.") from exc
        client_kwargs: Dict[str, Any] = {}
        endpoint = _secret("S3_ENDPOINT_URL", "")
        region = _secret("AWS_REGION", _secret("AWS_DEFAULT_REGION", ""))
        if endpoint:
            client_kwargs["endpoint_url"] = endpoint
        if region:
            client_kwargs["region_name"] = region
        client = boto3.client("s3", **client_kwargs)
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": object_storage_bucket("s3"), "Key": key},
            ExpiresIn=int(expires_in),
        )
    if provider == "gcs":
        try:
            from google.cloud import storage
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("google-cloud-storage is required for GCS signed URLs. Install requirements.txt.") from exc
        client = storage.Client()
        blob = client.bucket(object_storage_bucket("gcs")).blob(key)
        return blob.generate_signed_url(expiration=timedelta(seconds=int(expires_in)), method="GET")
    return key


def object_storage_status() -> Dict[str, Any]:
    provider = object_storage_provider()
    bucket = object_storage_bucket(provider)
    configured = provider == "local" or bool(bucket)
    if provider == "supabase":
        configured = bool(bucket and _supabase_url() and _secret("SUPABASE_SERVICE_ROLE_KEY", ""))
    if provider == "s3":
        configured = bool(bucket)
    if provider == "gcs":
        configured = bool(bucket)
    return {
        "provider": provider,
        "bucket": bucket or "local",
        "configured": configured,
        "mode": "cloud" if provider in {"supabase", "s3", "gcs"} and configured else "local_fallback",
        "public_urls_enabled": _bool_secret("ERRORSWEEP_OBJECT_STORAGE_ALLOW_PUBLIC_URLS", False),
        "local_root": str(local_object_storage_root()),
    }
