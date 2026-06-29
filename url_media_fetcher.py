"""Validate and fetch direct media-file URLs for subtitle/transcription jobs.

This module intentionally supports only direct audio/video file links. It does
not scrape or extract media from streaming/social platforms.
"""
from __future__ import annotations

import ipaddress
import mimetypes
import os
import re
import socket
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterable, Optional, Tuple
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse, unquote

import requests

from app_runtime_config import runtime_env


SUPPORTED_MEDIA_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".webm", ".mp3", ".wav", ".m4a"})
MEDIA_CONTENT_PREFIXES = ("audio/", "video/")
HTML_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
OCTET_STREAM_CONTENT_TYPES = {"application/octet-stream", "binary/octet-stream"}


def env_value(name: str, default: str = "") -> str:
    return runtime_env(name, default)


DEFAULT_MEDIA_URL_TIMEOUT_SECONDS = float(env_value("ERRORSWEEP_MEDIA_URL_TIMEOUT_SECONDS", "20"))
DOWNLOAD_CHUNK_BYTES = 1024 * 1024

# These domains host pages or proprietary streaming experiences, not direct
# customer-owned file downloads. Supporting them would require scraping or
# unofficial extraction logic, so CogniSweep blocks them by policy.
BLOCKED_STREAMING_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "facebook.com",
    "fb.watch",
    "vimeo.com",
    "tiktok.com",
    "photos.google.com",
    "photos.app.goo.gl",
)
BLOCKED_PLATFORM_MESSAGE = (
    "Direct platform links aren't supported. Please upload the file directly "
    "or provide a direct download link from cloud storage."
)

BLOCKED_INTERNAL_HOSTS = {"localhost", "metadata.google.internal"}


class DirectMediaUrlError(ValueError):
    """Raised when a submitted URL is not a safe direct media-file URL."""


@dataclass
class FetchedMediaFile:
    """Small UploadedFile-compatible wrapper around a downloaded temp file."""

    path: Path
    name: str
    type: str
    size: int
    source_url: str = ""
    _handle: Optional[BinaryIO] = field(default=None, init=False, repr=False)

    def _open(self) -> BinaryIO:
        if self._handle is None or self._handle.closed:
            self._handle = Path(self.path).open("rb")
        return self._handle

    def read(self, size: int = -1) -> bytes:
        return self._open().read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._open().seek(offset, whence)

    def tell(self) -> int:
        return self._open().tell()

    def close(self) -> None:
        if self._handle is not None and not self._handle.closed:
            self._handle.close()


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _host_matches(host: str, domains: Iterable[str]) -> bool:
    clean_host = host.lower().strip(".")
    return any(clean_host == domain or clean_host.endswith(f".{domain}") for domain in domains)


def _require_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise DirectMediaUrlError("Please enter an http(s) direct media-file URL.")
    if parsed.username or parsed.password:
        raise DirectMediaUrlError("URLs with embedded usernames or passwords are not supported.")
    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        raise DirectMediaUrlError("Please enter a valid direct media-file URL.")
    if _host_matches(host, BLOCKED_STREAMING_DOMAINS):
        raise DirectMediaUrlError(BLOCKED_PLATFORM_MESSAGE)
    if host in BLOCKED_INTERNAL_HOSTS or host.endswith(".local"):
        raise DirectMediaUrlError("Private or internal URLs are not supported. Please provide a public direct media-file URL.")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        _require_public_ip(ip)
        return

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise DirectMediaUrlError("URL host could not be resolved. Please check the direct file link.") from exc

    for info in infos:
        address = info[4][0]
        try:
            resolved_ip = ipaddress.ip_address(address)
        except ValueError:
            raise DirectMediaUrlError("URL host resolved to an unsupported address.") from None
        _require_public_ip(resolved_ip)


def _require_public_ip(ip: ipaddress._BaseAddress) -> None:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise DirectMediaUrlError("Private or internal URLs are not supported. Please provide a public direct media-file URL.")


def _extract_google_drive_id(parsed) -> str:
    query_id = parse_qs(parsed.query).get("id", [""])[0]
    if query_id:
        return query_id
    match = re.search(r"/file/d/([^/]+)", parsed.path)
    return match.group(1) if match else ""


def normalize_direct_media_url(url: str) -> str:
    """Convert common cloud share URLs to direct-download URLs when possible."""
    raw_url = _safe_text(url)
    if not raw_url:
        raise DirectMediaUrlError("Please paste a direct media-file URL.")
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower().strip(".")
    _require_public_http_url(raw_url)

    if _host_matches(host, ("drive.google.com",)):
        file_id = _extract_google_drive_id(parsed)
        if file_id:
            return f"https://drive.google.com/uc?{urlencode({'export': 'download', 'id': file_id})}"

    if _host_matches(host, ("dropbox.com",)):
        query = parse_qs(parsed.query, keep_blank_values=True)
        query["dl"] = ["1"]
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

    return raw_url


def _content_type(headers: Dict[str, str]) -> str:
    raw_type = _safe_text(headers.get("Content-Type") or headers.get("content-type"))
    return raw_type.split(";", 1)[0].strip().lower()


def _content_length(headers: Dict[str, str]) -> int:
    raw_length = _safe_text(headers.get("Content-Length") or headers.get("content-length"))
    if not raw_length:
        return 0
    try:
        return max(0, int(raw_length))
    except ValueError:
        return 0


def _extension_from_url(url: str) -> str:
    path = unquote(urlparse(url).path or "")
    return Path(path).suffix.lower()


def _validate_media_type(media_type: str, final_url: str) -> str:
    if media_type.startswith(MEDIA_CONTENT_PREFIXES):
        return media_type
    if media_type in HTML_CONTENT_TYPES or "html" in media_type:
        raise DirectMediaUrlError("The URL returned a webpage/HTML instead of a media file. Please provide a direct download link.")

    # Some storage buckets serve raw files as application/octet-stream. Accept
    # that only when the final URL still clearly ends in a supported media type.
    if media_type in OCTET_STREAM_CONTENT_TYPES and _extension_from_url(final_url) in SUPPORTED_MEDIA_EXTENSIONS:
        return media_type

    if not media_type:
        raise DirectMediaUrlError("The URL did not report a media Content-Type. Please provide a direct audio/video download link.")
    raise DirectMediaUrlError(f"Unsupported URL Content-Type '{media_type}'. Please provide a direct audio/video file link.")


def _filename_from_headers_or_url(headers: Dict[str, str], final_url: str, media_type: str) -> Tuple[str, str]:
    disposition = _safe_text(headers.get("Content-Disposition") or headers.get("content-disposition"))
    name = ""
    if disposition:
        utf_match = re.search(r"filename\*=UTF-8''([^;]+)", disposition, flags=re.IGNORECASE)
        plain_match = re.search(r'filename="?([^";]+)"?', disposition, flags=re.IGNORECASE)
        if utf_match:
            name = unquote(utf_match.group(1))
        elif plain_match:
            name = plain_match.group(1)

    if not name:
        name = Path(unquote(urlparse(final_url).path or "")).name
    if not name:
        guessed = mimetypes.guess_extension(media_type) if media_type else ""
        name = f"downloaded_media{guessed or '.bin'}"

    name = re.sub(r"[^A-Za-z0-9_. -]+", "_", name).strip(" .") or "downloaded_media"
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_MEDIA_EXTENSIONS:
        guessed = mimetypes.guess_extension(media_type) if media_type else ""
        if guessed in SUPPORTED_MEDIA_EXTENSIONS:
            suffix = guessed
            name = f"{Path(name).stem or 'downloaded_media'}{suffix}"
    if suffix not in SUPPORTED_MEDIA_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_MEDIA_EXTENSIONS))
        raise DirectMediaUrlError(f"Unsupported media format. Supported formats: {supported}.")
    return name, suffix


def fetch_media_url_to_temp(
    url: str,
    *,
    max_bytes: int,
    temp_dir: Optional[Path] = None,
    timeout_seconds: float = DEFAULT_MEDIA_URL_TIMEOUT_SECONDS,
    session: Optional[Any] = None,
) -> Dict[str, Any]:
    """Download a validated direct media URL to a temporary local file."""
    if max_bytes <= 0:
        raise DirectMediaUrlError("Media URL download limit is not configured.")
    normalized_url = normalize_direct_media_url(url)
    _require_public_http_url(normalized_url)
    owns_session = session is None
    client = session or requests.Session()
    headers = {"User-Agent": "CogniSweep direct-media-fetcher/1.0"}
    try:
        response = client.get(normalized_url, stream=True, allow_redirects=True, timeout=timeout_seconds, headers=headers)
    except requests.Timeout as exc:
        if owns_session:
            client.close()
        raise DirectMediaUrlError("Download timed out. Please try a smaller file or a faster direct download link.") from exc
    except requests.RequestException as exc:
        if owns_session:
            client.close()
        raise DirectMediaUrlError("URL unreachable. Please check that the direct media link is public and accessible.") from exc

    try:
        final_url = _safe_text(getattr(response, "url", normalized_url)) or normalized_url
        _require_public_http_url(final_url)
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(response, "status_code", "")
            detail = f" (HTTP {status})" if status else ""
            raise DirectMediaUrlError(f"URL unreachable or access denied{detail}. Please check the direct media link.") from exc

        headers_dict = dict(getattr(response, "headers", {}) or {})
        media_type = _validate_media_type(_content_type(headers_dict), final_url)
        reported_size = _content_length(headers_dict)
        if reported_size and reported_size > max_bytes:
            raise DirectMediaUrlError(f"File too large. Maximum direct URL media size is {max_bytes / (1024 * 1024):.0f} MB.")

        file_name, suffix = _filename_from_headers_or_url(headers_dict, final_url, media_type)
        root = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "errorsweep_url_media"
        root.mkdir(parents=True, exist_ok=True)
        target_path = root / f"url_media_{uuid.uuid4().hex}{suffix}"
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        written = 0
        try:
            with tmp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > max_bytes:
                        raise DirectMediaUrlError(f"File too large. Maximum direct URL media size is {max_bytes / (1024 * 1024):.0f} MB.")
                    handle.write(chunk)
            if written <= 0:
                raise DirectMediaUrlError("The direct media URL returned an empty file.")
            os.replace(tmp_path, target_path)
        except (DirectMediaUrlError, OSError, requests.RequestException):
            try:
                tmp_path.unlink(missing_ok=True)
                target_path.unlink(missing_ok=True)
            finally:
                raise

        return {
            "path": str(target_path),
            "name": file_name,
            "type": media_type if media_type.startswith(MEDIA_CONTENT_PREFIXES) else mimetypes.guess_type(file_name)[0] or "application/octet-stream",
            "size": written,
            "source_url": _safe_text(url),
            "normalized_url": normalized_url,
            "final_url": final_url,
            "temporary_url_media": True,
        }
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
        if owns_session:
            client.close()


def fetched_media_from_record(record: Dict[str, Any]) -> Optional[FetchedMediaFile]:
    path = Path(_safe_text(record.get("path")))
    if not path.exists() or not path.is_file():
        return None
    return FetchedMediaFile(
        path=path,
        name=_safe_text(record.get("name")) or path.name,
        type=_safe_text(record.get("type")) or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        size=int(record.get("size") or path.stat().st_size),
        source_url=_safe_text(record.get("source_url")),
    )


def cleanup_fetched_media_record(record: Dict[str, Any]) -> bool:
    if not record or not record.get("temporary_url_media"):
        return False
    try:
        path = Path(_safe_text(record.get("path"))).resolve()
        path.unlink(missing_ok=True)
        return True
    except (OSError, RuntimeError, ValueError):
        return False
