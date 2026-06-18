import socket
import tempfile
from pathlib import Path

import requests

from url_media_fetcher import (
    BLOCKED_PLATFORM_MESSAGE,
    DirectMediaUrlError,
    cleanup_fetched_media_record,
    fetch_media_url_to_temp,
    fetched_media_from_record,
    normalize_direct_media_url,
)


class FakeResponse:
    def __init__(self, *, headers=None, body=b"", url="https://8.8.8.8/media.mp4", status_code=200):
        self.headers = headers or {}
        self.body = body
        self.url = url
        self.status_code = status_code
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def iter_content(self, chunk_size=1024 * 1024):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start:start + chunk_size]

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


def with_public_dns(fn):
    original = socket.getaddrinfo
    socket.getaddrinfo = lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]
    try:
        return fn()
    finally:
        socket.getaddrinfo = original


def test_streaming_platforms_are_blocked():
    try:
        normalize_direct_media_url("https://www.youtube.com/watch?v=abc123")
    except DirectMediaUrlError as exc:
        assert str(exc) == BLOCKED_PLATFORM_MESSAGE
    else:
        raise AssertionError("YouTube URL should be rejected")


def test_google_drive_and_dropbox_links_convert_to_direct_downloads():
    google = with_public_dns(lambda: normalize_direct_media_url("https://drive.google.com/file/d/file123/view?usp=sharing"))
    assert google == "https://drive.google.com/uc?export=download&id=file123"

    dropbox = with_public_dns(lambda: normalize_direct_media_url("https://www.dropbox.com/s/demo/video.mp4?dl=0"))
    assert dropbox == "https://www.dropbox.com/s/demo/video.mp4?dl=1"


def test_private_hosts_are_blocked():
    try:
        normalize_direct_media_url("http://127.0.0.1/media.mp4")
    except DirectMediaUrlError as exc:
        assert "Private or internal URLs" in str(exc)
    else:
        raise AssertionError("Private URL should be rejected")


def test_html_content_type_is_rejected():
    response = FakeResponse(headers={"Content-Type": "text/html"}, body=b"<html></html>")
    try:
        fetch_media_url_to_temp("https://8.8.8.8/file.mp4", max_bytes=1024, session=FakeSession(response))
    except DirectMediaUrlError as exc:
        assert "webpage/HTML" in str(exc)
    else:
        raise AssertionError("HTML response should be rejected")


def test_declared_oversized_media_is_rejected_before_download():
    response = FakeResponse(headers={"Content-Type": "video/mp4", "Content-Length": "2048"}, body=b"")
    try:
        fetch_media_url_to_temp("https://8.8.8.8/file.mp4", max_bytes=1024, session=FakeSession(response))
    except DirectMediaUrlError as exc:
        assert "File too large" in str(exc)
    else:
        raise AssertionError("Oversized media should be rejected")


def test_direct_media_download_creates_uploaded_file_compatible_record():
    with tempfile.TemporaryDirectory() as tmp:
        response = FakeResponse(
            headers={"Content-Type": "video/mp4", "Content-Length": "7", "Content-Disposition": 'attachment; filename="clip.mp4"'},
            body=b"mp4data",
        )
        record = fetch_media_url_to_temp(
            "https://8.8.8.8/file.mp4",
            max_bytes=1024,
            temp_dir=Path(tmp),
            session=FakeSession(response),
        )
        assert Path(record["path"]).exists()
        assert record["name"] == "clip.mp4"
        assert record["type"] == "video/mp4"
        assert record["size"] == 7

        wrapped = fetched_media_from_record(record)
        assert wrapped is not None
        assert wrapped.read() == b"mp4data"
        wrapped.close()
        assert cleanup_fetched_media_record(record) is True
        assert not Path(record["path"]).exists()


if __name__ == "__main__":
    test_streaming_platforms_are_blocked()
    test_google_drive_and_dropbox_links_convert_to_direct_downloads()
    test_private_hosts_are_blocked()
    test_html_content_type_is_rejected()
    test_declared_oversized_media_is_rejected_before_download()
    test_direct_media_download_creates_uploaded_file_compatible_record()
    print("Direct media URL fetcher checks passed.")

